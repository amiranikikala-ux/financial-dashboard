import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from backend_paths import get_dashboard_data_path, get_dashboard_tab_data_path
from dashboard_pipeline.ai import AIAgent, AIAgentError, load_ai_config
from dashboard_pipeline.ai.prompts import DEFAULT_MODE, SUPPORTED_MODES
from dashboard_pipeline.api_contracts import (
    ALLOWED_TABS,
    DYNAMIC_SOURCE_ARTIFACTS,
    STATIC_RESPONSE_TABS,
    build_response_for_tab,
)
from dashboard_pipeline._validate_aliases import (
    AliasDuplicateError,
    AliasValidationError,
    append_alias_atomic,
)
from dashboard_pipeline.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# API Key Authentication
# ---------------------------------------------------------------------------
DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "").strip()

# Public endpoints that don't require auth (even when key is set)
_PUBLIC_PATHS = {"/api/status", "/docs", "/openapi.json", "/redoc"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header when DASHBOARD_API_KEY is configured."""

    async def dispatch(self, request: Request, call_next):
        if not DASHBOARD_API_KEY:
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS or not path.startswith("/api"):
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if not provided or not hmac.compare_digest(provided, DASHBOARD_API_KEY):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Pipeline scheduler state
# ---------------------------------------------------------------------------
SCHEDULE_INTERVAL_MIN = int(os.environ.get("DASHBOARD_REFRESH_MINUTES", "60"))

_pipeline_lock = Lock()
_pipeline_status = {
    "state": "idle",        # idle | running | error
    "last_run": None,       # ISO timestamp
    "last_duration_s": None,
    "last_error": None,
    "runs_total": 0,
}


def _run_pipeline():
    """Run generate_dashboard_data in a subprocess (thread-safe).

    Streams subprocess stdout/stderr directly to logs/pipeline_subprocess.log
    instead of buffering in memory (capture_output=True). On Windows with
    OneDrive-synced folders, in-memory buffering of the 5-50MB pipeline log
    stream was a primary slowdown — backend GC pressure pushed pipeline runs
    from 3-5 min to 28-30 min and regularly hit the timeout. Streaming to a
    file leaves backend memory untouched.
    """
    acquired = _pipeline_lock.acquire(blocking=False)
    if not acquired:
        logger.info("Pipeline already running, skipping")
        return
    try:
        _pipeline_status["state"] = "running"
        _pipeline_status["last_error"] = None
        start = datetime.now(timezone.utc)
        logger.info("Pipeline regeneration started")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        script = os.path.join(script_dir, "generate_dashboard_data.py")

        log_dir = os.path.join(script_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        subprocess_log_path = os.path.join(log_dir, "pipeline_subprocess.log")

        with open(subprocess_log_path, "ab") as log_handle:
            header = (
                f"\n=== pipeline run @ {start.isoformat()} ===\n"
            ).encode("utf-8")
            log_handle.write(header)
            log_handle.flush()
            result = subprocess.run(
                [sys.executable, script],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                timeout=30 * 60,  # 30 min hard limit; healthy runs are 7-8 min on C:\
                cwd=script_dir,
            )
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        _pipeline_status["last_duration_s"] = round(elapsed, 1)
        _pipeline_status["last_run"] = datetime.now(timezone.utc).isoformat()
        _pipeline_status["runs_total"] += 1

        if result.returncode != 0:
            err_msg = (
                f"pipeline exited with code {result.returncode}; "
                f"see {subprocess_log_path} for details"
            )
            _pipeline_status["state"] = "error"
            _pipeline_status["last_error"] = err_msg
            logger.error("Pipeline failed (%.1fs): %s", elapsed, err_msg)
        else:
            _pipeline_status["state"] = "idle"
            logger.info("Pipeline completed in %.1fs", elapsed)
    except Exception as exc:
        _pipeline_status["state"] = "error"
        _pipeline_status["last_error"] = str(exc)[:500]
        logger.error("Pipeline exception: %s", exc)
    finally:
        _pipeline_lock.release()


def _schedule_pipeline_job():
    """Start APScheduler for periodic pipeline regeneration."""
    if SCHEDULE_INTERVAL_MIN <= 0:
        logger.info("Scheduled refresh disabled (DASHBOARD_REFRESH_MINUTES=0)")
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            _run_pipeline,
            "interval",
            minutes=SCHEDULE_INTERVAL_MIN,
            id="pipeline_refresh",
            max_instances=1,
            misfire_grace_time=60,
        )
        scheduler.start()
        logger.info(
            "Scheduled pipeline refresh every %d min", SCHEDULE_INTERVAL_MIN
        )
        return scheduler
    except ImportError:
        logger.warning("apscheduler not installed — scheduled refresh disabled")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    try:
        load_artifact("suppliers", force=True)
    except Exception as artifact_exc:
        logger.warning("Startup artifact load failed: %s", artifact_exc)
        try:
            load_full_data(force=True)
        except Exception as full_exc:
            logger.warning("Startup full data load failed: %s", full_exc)
    scheduler = _schedule_pipeline_job()
    yield
    # --- shutdown ---
    if scheduler:
        scheduler.shutdown(wait=False)


limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(ApiKeyMiddleware)
if DASHBOARD_API_KEY:
    logger.info("API key auth enabled (key hash: %s...)", hashlib.sha256(DASHBOARD_API_KEY.encode()).hexdigest()[:8])
else:
    logger.info("API key auth disabled (set DASHBOARD_API_KEY to enable)")


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again shortly."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = get_dashboard_data_path()
full_data_cache = {}
full_data_mtime = None
full_data_lock = Lock()
artifact_cache = {}
artifact_lock = Lock()


def _load_json_file_cached(path, cache_store, lock, force=False):
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON file not found at {path}")
    current_mtime = os.path.getmtime(path)
    with lock:
        entry = cache_store.get(path)
        should_reload = (
            force
            or entry is None
            or entry.get("mtime") is None
            or current_mtime != entry.get("mtime")
        )
        if should_reload:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise ValueError(f"JSON root must be an object: {path}")
            cache_store[path] = {
                "mtime": current_mtime,
                "data": loaded,
            }
            logger.info("Loaded %s (mtime=%s)", os.path.basename(path), current_mtime)
        return cache_store[path]["data"]


def load_full_data(force=False):
    global full_data_cache, full_data_mtime
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"data.json not found at {DATA_PATH}")
    current_mtime = os.path.getmtime(DATA_PATH)
    with full_data_lock:
        should_reload = (
            force
            or not full_data_cache
            or full_data_mtime is None
            or current_mtime != full_data_mtime
        )
        if should_reload:
            with open(DATA_PATH, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise ValueError("data.json root must be an object")
            full_data_cache = loaded
            full_data_mtime = current_mtime
            logger.info("Loaded data.json (mtime=%s)", current_mtime)
    return full_data_cache


def load_artifact(name, force=False):
    path = get_dashboard_tab_data_path(name)
    return _load_json_file_cached(path, artifact_cache, artifact_lock, force=force)


def _load_cache_for_tab(tab):
    artifact_name = DYNAMIC_SOURCE_ARTIFACTS.get(tab)
    if artifact_name:
        try:
            return load_artifact(artifact_name)
        except Exception as exc:
            logger.warning("Artifact fallback for %s: %s", tab, exc)
    return load_full_data()


def _has_dynamic_input_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def get_tab_payload(
    tab: str = "suppliers",
    tax_id: str | None = None,
    normalized_supplier: str | None = None,
    product_code: str | None = None,
    normalized_product: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
):
    """
    Build the same JSON object as GET /api/data (synchronous, for scripts/tests).

    Raises ValueError when tab is not in ALLOWED_TABS (same condition as HTTP 400).
    """
    if tab not in ALLOWED_TABS:
        allowed = ", ".join(ALLOWED_TABS)
        raise ValueError(f"Invalid tab '{tab}'. Allowed tabs: {allowed}")

    has_dynamic_inputs = any(
        _has_dynamic_input_value(value)
        for value in (
            tax_id,
            normalized_supplier,
            product_code,
            normalized_product,
            q,
            sort,
            limit,
            from_date,
            to_date,
            from_time,
            to_time,
        )
    )

    if not has_dynamic_inputs and tab in STATIC_RESPONSE_TABS:
        try:
            return load_artifact(tab)
        except Exception as exc:
            logger.warning("Static artifact fallback for %s: %s", tab, exc)

    cache = _load_cache_for_tab(tab)
    return build_response_for_tab(
        cache,
        tab,
        tax_id=tax_id,
        normalized_supplier=normalized_supplier,
        product_code=product_code,
        normalized_product=normalized_product,
        q=q,
        sort=sort,
        limit=limit,
        from_date=from_date,
        to_date=to_date,
        from_time=from_time,
        to_time=to_time,
    )


@app.get("/api/data")
@limiter.limit("60/minute")
async def get_data(
    request: Request,
    tab: str = "suppliers",
    tax_id: str | None = None,
    normalized_supplier: str | None = None,
    product_code: str | None = None,
    normalized_product: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
):
    try:
        return get_tab_payload(
            tab=tab,
            tax_id=tax_id,
            normalized_supplier=normalized_supplier,
            product_code=product_code,
            normalized_product=normalized_product,
            q=q,
            sort=sort,
            limit=limit,
            from_date=from_date,
            to_date=to_date,
            from_time=from_time,
            to_time=to_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to load data for tab '{tab}': {exc}"
        ) from exc


@app.get("/api/status")
async def get_status():
    """Data freshness and pipeline status."""
    data_mtime = None
    data_age_s = None
    try:
        if os.path.exists(DATA_PATH):
            mt = os.path.getmtime(DATA_PATH)
            data_mtime = datetime.fromtimestamp(mt, tz=timezone.utc).isoformat()
            data_age_s = round((datetime.now(timezone.utc) - datetime.fromtimestamp(mt, tz=timezone.utc)).total_seconds())
    except Exception:
        pass
    return {
        "data_file_modified": data_mtime,
        "data_age_seconds": data_age_s,
        "pipeline": {
            **_pipeline_status,
            "schedule_interval_min": SCHEDULE_INTERVAL_MIN,
        },
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/refresh")
@limiter.limit("2/minute")
async def trigger_refresh(request: Request):
    """Manually trigger pipeline regeneration (background)."""
    if _pipeline_status["state"] == "running":
        return {"status": "already_running", "message": "Pipeline is already running"}
    thread = Thread(target=_run_pipeline, daemon=True)
    thread.start()
    return {"status": "started", "message": "Pipeline regeneration started in background"}


# ---------------------------------------------------------------------------
# Phase 4A — Debt Repayment Plan (Autonomous Strategist)
#
# Direct (non-AI) access to ``build_debt_repayment_plan`` for the dedicated
# React page. The AI chat path still uses the tool via the Anthropic
# tool-use loop; this endpoint is for the "Generate Plan" button on the
# 📋 ვალების გეგმა tab — no LLM tokens consumed, sub-second response.
# ---------------------------------------------------------------------------


def _coerce_optional_int(value: Any, *, field: str) -> int | None:
    """Accept int / numeric string / None. 400 on anything else."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):  # bool is int — exclude
        raise HTTPException(
            status_code=400,
            detail=f"`{field}` must be integer or null, got bool.",
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"`{field}` must be integer; got {value!r}.",
            ) from exc
    raise HTTPException(
        status_code=400,
        detail=f"`{field}` must be integer or null.",
    )


def _coerce_priority_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise HTTPException(
            status_code=400,
            detail="`priority_suppliers` must be a list of strings or null.",
        )
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise HTTPException(
                status_code=400,
                detail=(
                    "`priority_suppliers` entries must all be strings; "
                    f"got {type(item).__name__}."
                ),
            )
        token = item.strip()
        if token:
            cleaned.append(token)
    if len(cleaned) > 8:
        raise HTTPException(
            status_code=400,
            detail="`priority_suppliers` is capped at 8 entries.",
        )
    return cleaned or None


@app.post("/api/debt-plan")
@limiter.limit("20/minute")
async def post_debt_plan(request: Request, payload: dict = Body(default={})):
    """Generate a debt repayment plan directly from ``data.json``.

    Bypasses the AI tool-use loop — used by the React page's "Generate Plan"
    button for fast, deterministic plan generation. The same
    ``build_debt_repayment_plan`` helper powers the chat tool, so results
    are identical regardless of path.

    Request body (all optional):
        {
            "priority_suppliers": ["ვასაძე", "406181616"],  # names or tax_ids
            "plan_duration_months": 2,   # 1-6, default 2
            "max_priority_count": 5      # 2-8, default 5
        }

    Response: full plan dict (see ``build_debt_repayment_plan`` docstring).
    """
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object.",
        )

    priority = _coerce_priority_list(payload.get("priority_suppliers"))
    duration = _coerce_optional_int(
        payload.get("plan_duration_months"), field="plan_duration_months"
    )
    max_priority = _coerce_optional_int(
        payload.get("max_priority_count"), field="max_priority_count"
    )

    try:
        from dashboard_pipeline.ai.debt_plan import build_debt_repayment_plan
        plan = build_debt_repayment_plan(
            load_full_data,
            priority_suppliers=priority,
            plan_duration_months=duration,
            max_priority_count=max_priority,
        )
    except Exception as exc:
        logger.exception("debt-plan generation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {type(exc).__name__}",
        ) from exc

    return plan


@app.post("/api/debt-plan/save")
@limiter.limit("20/minute")
async def post_debt_plan_save(request: Request, payload: dict = Body(...)):
    """Persist a user-approved repayment plan to the journal.

    Stores a summary line in the journal as ``kind='repayment_plan'`` with
    structured tags. Full plan JSON storage is deferred to Phase 4A v2 —
    current contract lets the user regenerate any time to see details.

    Request body:
        {
            "title": "📋 ვალების გეგმა — 5 priority @ 28,400 ₾/თვე"  (required),
            "tags": ["phase4a", "duration:2mo", "priority_count:5"]  (optional)
        }

    Response: ``add_journal_entry`` result (``{ok, entry_id, ...}``).
    """
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must be a JSON object.",
        )
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise HTTPException(
            status_code=400,
            detail="`title` must be a non-empty string.",
        )
    tags = payload.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise HTTPException(
            status_code=400,
            detail="`tags` must be a list of strings or null.",
        )

    try:
        from dashboard_pipeline.ai.journal import add_journal_entry
        result = add_journal_entry(
            title=title.strip(),
            kind="repayment_plan",
            tags=tags,
        )
    except Exception as exc:
        logger.exception("debt-plan save failed")
        raise HTTPException(
            status_code=500,
            detail=f"Journal save failed: {type(exc).__name__}",
        ) from exc

    if not result.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error") or "Unknown journal error.",
        )
    return result


# ---------------------------------------------------------------------------
# VAT reconciliation dashboard (Sprint 5.3)
# ---------------------------------------------------------------------------

@app.get("/api/vat-reconciliation")
@limiter.limit("60/minute")
async def get_vat_reconciliation(request: Request):
    """Returns the full ``vat_reconciliation`` section from data.json for the
    dashboard page. All per-month fields + metadata; no filtering here, the
    frontend chooses which months to render.
    """
    data = load_full_data()
    vat = data.get("vat_reconciliation") or {}
    return {
        "by_month": vat.get("by_month") or [],
        "summary": vat.get("summary") or {},
        "red_flag_months": vat.get("red_flag_months") or [],
        "needs_input_months": vat.get("needs_user_input_months") or [],
        "audit_source": vat.get("uploaded_audit_source"),
        "cash_journal_source": vat.get("cash_journal_source"),
        "invoices_issued_source": vat.get("invoices_issued_source"),
        "date_range": vat.get("date_range_iso"),
        "thresholds": vat.get("thresholds"),
        "generated_at": data.get("meta", {}).get("generated_at")
            or data.get("generated_at"),
    }


@app.get("/api/vat-reconciliation/export")
@limiter.limit("30/minute")
async def get_vat_reconciliation_export(request: Request):
    """Returns a formatted VAT reconciliation Excel workbook for download.

    Sheets: Summary (cumulative totals), Monthly (all months × fields),
    Cash_classification (per-category breakdown if any entries), Methodology
    (auditor-friendly explanation). Uses the currently-cached data.json —
    refresh requires a pipeline rerun.
    """
    from dashboard_pipeline.vat_reconciliation_export import build_vat_export_bytes
    data = load_full_data()
    vat = data.get("vat_reconciliation") or {}
    if not vat.get("by_month"):
        raise HTTPException(
            status_code=404,
            detail="VAT reconciliation მონაცემები არ მოიძებნა data.json-ში.",
        )
    try:
        xlsx_bytes = build_vat_export_bytes(vat)
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openpyxl არ არის დაყენებული სერვერზე.",
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    filename = f"VAT_reconciliation_{stamp}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(xlsx_bytes)),
        },
    )


@app.post("/api/vat-reconciliation/cash-outflow")
@limiter.limit("30/minute")
async def post_vat_cash_outflow(request: Request, payload: dict = Body(...)):
    """Append a classified cash-outflow entry to cash_outflow_journal.csv.

    Mirrors the AI `record_cash_outflow` tool for the dashboard's manual-entry
    form. Does NOT regenerate data.json — the response includes an in-memory
    preview of remaining unaccounted cash; totals update on next pipeline run.

    Request body:
        {
            "period": "2024-08",
            "amount_ge": 15000.0,
            "purpose_ka": "ხელფასი გიორგის",
            "category": "salary_cash",
            "vat_applies": true,       (optional; defaults per category)
            "notes": "..."             (optional)
        }
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    from dashboard_pipeline.ai.vat_tools import record_cash_outflow

    try:
        amount = float(payload.get("amount_ge"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount_ge must be a positive number.")

    va = payload.get("vat_applies")
    if va is not None and not isinstance(va, bool):
        raise HTTPException(status_code=400, detail="vat_applies must be boolean or omitted.")

    result = record_cash_outflow(
        load_full_data,
        project_root=os.path.dirname(os.path.abspath(__file__)),
        period=payload.get("period"),
        amount_ge=amount,
        purpose_ka=payload.get("purpose_ka") or "",
        category=payload.get("category"),
        vat_applies=va,
        notes=payload.get("notes") or "",
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ---------------------------------------------------------------------------
# Sprint C — Supplier alias confirmation
# ---------------------------------------------------------------------------
def _build_retail_known_keys(data: dict) -> set:
    """Mirror generate_dashboard_data.py:1657-1664 — collect every barcode
    and product_code present in retail_sales.by_product so the endpoint
    rejects aliases pointing at rows that don't exist."""
    keys: set = set()
    for row in (data.get("retail_sales") or {}).get("by_product") or []:
        bc = (row.get("barcode") or "").strip()
        pc = (row.get("product_code") or "").strip()
        if bc:
            keys.add(bc)
        if pc:
            keys.add(pc)
    return keys


def _aliases_file_path() -> Path:
    """Resolve ``product_aliases.json`` relative to this module.

    Extracted so tests can ``monkeypatch.setattr(server, "_aliases_file_path",
    lambda: tmp_path / "product_aliases.json")`` without touching the
    repo-tracked file."""
    return (
        Path(os.path.dirname(os.path.abspath(__file__)))
        / "Financial_Analysis"
        / "product_aliases.json"
    )


@app.post("/api/aliases/confirm")
@limiter.limit("30/minute")
async def post_alias_confirm(request: Request, payload: dict = Body(...)):
    """Append a user-confirmed alias to ``Financial_Analysis/product_aliases.json``.

    Triggered by the "დადასტურდი ალიასი" button next to each pipeline-suggested
    ``name_candidate`` in SupplierModal. Does NOT regenerate ``data.json`` —
    coverage updates on the next pipeline run (manual /api/refresh or hourly).

    Body:
        {
            "imported_code":            "2006",         (required)
            "retail_code_or_barcode":   "2247377",      (required)
            "imported_supplier_taxid":  "400123456",    (optional, audit trail)
            "imported_name_sample":     "...",          (optional, audit trail)
            "note":                     "..."           (optional)
        }

    Status codes:
        200 — alias appended, returns canonical entry + total count + UI hint
        400 — empty/missing required field, or retail_code_or_barcode unknown
        409 — imported_code already confirmed (idempotent guard)
        503 — data.json missing on disk
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    try:
        data = load_full_data()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    retail_known_keys = _build_retail_known_keys(data)
    aliases_path = _aliases_file_path()

    try:
        canonical = append_alias_atomic(aliases_path, payload, retail_known_keys)
    except AliasDuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AliasValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        logger.error("alias confirm failed to write %s: %s", aliases_path, exc)
        raise HTTPException(status_code=500, detail=f"ფაილის ჩაწერა ვერ მოხერხდა: {exc}")

    try:
        existing = json.loads(aliases_path.read_text(encoding="utf-8"))
        alias_count = len(existing.get("aliases") or [])
    except Exception:
        alias_count = 1

    logger.info(
        "alias confirmed: imported=%s -> retail=%s (total=%d)",
        canonical.get("imported_code"),
        canonical.get("retail_code_or_barcode"),
        alias_count,
    )
    return {
        "success": True,
        "alias": canonical,
        "alias_count": alias_count,
        "hint_ka": (
            'დადასტურდა — მომდევნო pipeline run-ი ანალიზში დაამატებს. '
            'ხელით განახლება: „განაახლე მონაცემები" ღილაკი.'
        ),
    }


# ---------------------------------------------------------------------------
# AI Advisor — Phase 1 MVP Chat
# ---------------------------------------------------------------------------
_ai_agent_lock = Lock()
_ai_agent: AIAgent | None = None
_ai_config_snapshot = None


def _get_ai_agent() -> AIAgent:
    """Lazily build a cached AIAgent from current .env configuration.

    If AI is not configured, raises HTTPException 503 with a Georgian message.
    """
    global _ai_agent, _ai_config_snapshot
    with _ai_agent_lock:
        if _ai_agent is None:
            config = load_ai_config()
            if not config.is_enabled:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "AI Advisor არ არის კონფიგურირებული. "
                        "გთხოვთ, .env-ში მიუთითოთ ANTHROPIC_API_KEY."
                    ),
                )
            try:
                _ai_agent = AIAgent(config=config, data_loader=load_full_data)
                _ai_config_snapshot = config.redacted()
                logger.info("AI agent initialized: %s", _ai_config_snapshot)
            except AIAgentError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return _ai_agent


def _extract_chat_mode(payload: dict) -> str:
    """Return a validated chat mode from the request body.

    - Missing / ``None`` / empty string → :data:`DEFAULT_MODE` (``"chat"``).
    - Any string member of :data:`SUPPORTED_MODES` (case-insensitive) is
      accepted and normalized.
    - Anything else → :class:`HTTPException` 400 with the list of valid
      modes, so the frontend fails fast.
    """
    raw = payload.get("mode") if isinstance(payload, dict) else None
    if raw is None:
        return DEFAULT_MODE
    if not isinstance(raw, str):
        raise HTTPException(
            status_code=400,
            detail=(
                "`mode` must be a string; expected one of "
                f"{list(SUPPORTED_MODES)}."
            ),
        )
    normalized = raw.strip().lower()
    if not normalized:
        return DEFAULT_MODE
    if normalized not in SUPPORTED_MODES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown `mode`: {raw!r}. "
                f"Supported values: {list(SUPPORTED_MODES)}."
            ),
        )
    return normalized


def _extract_think_flag(payload: dict) -> bool:
    """Return a validated ``think`` flag from the request body.

    Phase 0B.1 — Extended Thinking (ღრმა ფიქრი).

    - Missing / ``None`` / falsy → ``False`` (chat mode default).
    - Explicit ``True`` / ``False`` (boolean) → passed through.
    - Non-boolean → :class:`HTTPException` 400 so the frontend fails fast
      rather than silently ignoring a typo like ``{"think": "yes"}``.

    Note: the deployment-level ``AI_ENABLE_THINKING`` env var is the
    *upstream* gate — if it is ``false``, the agent silently ignores
    ``think=True``. This helper only validates wire-level shape.
    """
    if not isinstance(payload, dict):
        return False
    raw = payload.get("think")
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    raise HTTPException(
        status_code=400,
        detail="`think` must be a boolean (true or false).",
    )


@app.post("/api/chat")
@limiter.limit("30/minute")
async def post_chat(
    request: Request,
    payload: dict = Body(...),
):
    """AI Advisor chat turn.

    Request body:
        {
            "message": "<user text>",
            "history": [...] (optional; prior messages array from last response),
            "mode": "chat" | "investigate" (optional; default "chat")
        }

    Response:
        {
            "reply": "<assistant text>",
            "sources": [...],          # tool call trace
            "usage": {...},            # token counts + model + stop_reason + mode
            "history": [...]           # updated history for next turn
        }
    """
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(
            status_code=400,
            detail="`message` must be a non-empty string.",
        )
    if len(message) > 8000:
        raise HTTPException(
            status_code=400,
            detail="`message` too long (max 8000 characters).",
        )

    history = payload.get("history") if isinstance(payload, dict) else None
    if history is not None and not isinstance(history, list):
        raise HTTPException(
            status_code=400,
            detail="`history` must be a list of message objects.",
        )

    mode = _extract_chat_mode(payload)
    think = _extract_think_flag(payload)

    agent = _get_ai_agent()
    try:
        result = agent.chat(
            message=message, history=history, mode=mode, think=think
        )
    except AIAgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI chat failed")
        raise HTTPException(
            status_code=500,
            detail=f"AI chat failed: {type(exc).__name__}",
        ) from exc
    return result


# ---------------------------------------------------------------------------
# AI Advisor — Streaming SSE endpoint (Phase 1 polish follow-up)
# ---------------------------------------------------------------------------
_SSE_EVENT_SENTINEL = object()


def _format_sse_event(event: dict) -> str:
    """Encode an event dict as a single SSE message frame.

    Frame format (per W3C SSE spec):
        event: <type>\n
        data: <json>\n
        \n

    The trailing blank line terminates the event.
    """
    evt_type = event.get("type") or "message"
    data = json.dumps(event, ensure_ascii=False, default=str)
    return f"event: {evt_type}\ndata: {data}\n\n"


async def _sse_stream_bridge(sync_gen):
    """Bridge a synchronous generator into an async byte stream.

    The Anthropic SDK's ``messages.stream()`` is synchronous; each iteration
    blocks on network I/O. Running ``next()`` in a thread pool lets the
    FastAPI event loop keep serving other requests while we wait.
    """
    loop = asyncio.get_running_loop()
    try:
        while True:
            nxt = await loop.run_in_executor(
                None, lambda: next(sync_gen, _SSE_EVENT_SENTINEL)
            )
            if nxt is _SSE_EVENT_SENTINEL:
                break
            yield _format_sse_event(nxt).encode("utf-8")
    except asyncio.CancelledError:
        # Client disconnected — close the underlying generator cleanly.
        try:
            sync_gen.close()
        except Exception:  # pragma: no cover — defensive
            pass
        raise
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("SSE bridge crashed")
        yield _format_sse_event(
            {"type": "error", "error": f"sse bridge failed: {type(exc).__name__}"}
        ).encode("utf-8")


@app.post("/api/chat/stream")
@limiter.limit("30/minute")
async def post_chat_stream(
    request: Request,
    payload: dict = Body(...),
):
    """AI Advisor chat turn streamed as Server-Sent Events.

    Same body contract as ``/api/chat``. Response is ``text/event-stream``
    with event types: ``delta``, ``tool_call``, ``tool_result``, ``sources``,
    ``usage``, ``history``, ``done``, ``error``.

    Tool calls still resolve server-side — only the final-text deltas travel
    to the client. Prompt caching (Phase 1 polish) remains active on the
    ``system`` + ``tools`` prefix, so streaming stacks cleanly on top of
    a cache hit for ~2s first-token latency.
    """
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(
            status_code=400,
            detail="`message` must be a non-empty string.",
        )
    if len(message) > 8000:
        raise HTTPException(
            status_code=400,
            detail="`message` too long (max 8000 characters).",
        )

    history = payload.get("history") if isinstance(payload, dict) else None
    if history is not None and not isinstance(history, list):
        raise HTTPException(
            status_code=400,
            detail="`history` must be a list of message objects.",
        )

    mode = _extract_chat_mode(payload)
    think = _extract_think_flag(payload)

    agent = _get_ai_agent()
    try:
        sync_gen = agent.chat_stream(
            message=message, history=history, mode=mode, think=think
        )
    except AIAgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI chat_stream init failed")
        raise HTTPException(
            status_code=500,
            detail=f"AI chat stream failed: {type(exc).__name__}",
        ) from exc

    return StreamingResponse(
        _sse_stream_bridge(sync_gen),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering (nginx) so chunks flush immediately.
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Allow port override via command line
    port = 8000
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--port="):
                port = int(arg.split("=")[1])
            elif arg == "--port" and len(sys.argv) > sys.argv.index(arg) + 1:
                port = int(sys.argv[sys.argv.index(arg) + 1])
    
    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=False)
