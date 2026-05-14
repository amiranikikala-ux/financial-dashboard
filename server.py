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
from fastapi.staticfiles import StaticFiles
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
from dashboard_pipeline import (
    cash_expenses_journal,
    manual_payments_journal,
    orphan_user_status,
    supplier_archive,
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
# How often to auto-fetch BOG + rs.ge into the parquet caches (TBC stays
# manual because it requires a DigiPass OTP). 0 disables.
BANK_REFRESH_INTERVAL_MIN = int(os.environ.get("BANK_REFRESH_MINUTES", "60"))

_pipeline_lock = Lock()
_pipeline_status = {
    "state": "idle",        # idle | running | error
    "last_run": None,       # ISO timestamp
    "last_duration_s": None,
    "last_error": None,
    "runs_total": 0,
}

# Bank-cache refresh state (Sprint C step 6 Phase 1) — distinct from
# `_pipeline_status` because bank refresh = remote API fetch into parquet
# caches, whereas pipeline = local recompute of `data.json`. The bank
# orchestrator kicks `_run_pipeline` only after the API fetch finishes.
_bank_refresh_lock = Lock()
_bank_refresh_status = {
    "state": "idle",            # idle | running | error
    "started_at": None,         # ISO timestamp of current/last run start
    "completed_at": None,       # ISO timestamp of last successful completion
    "last_error": None,
    "last_result": None,        # full per-bank dict from refresh_all_banks
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
    """Start APScheduler for periodic pipeline regeneration AND auto bank
    refresh (BOG + rs.ge only — TBC needs an owner-supplied OTP)."""
    if SCHEDULE_INTERVAL_MIN <= 0 and BANK_REFRESH_INTERVAL_MIN <= 0:
        logger.info(
            "All schedulers disabled (DASHBOARD_REFRESH_MINUTES=0, "
            "BANK_REFRESH_MINUTES=0)"
        )
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler(daemon=True)
        if SCHEDULE_INTERVAL_MIN > 0:
            scheduler.add_job(
                _run_pipeline,
                "interval",
                minutes=SCHEDULE_INTERVAL_MIN,
                id="pipeline_refresh",
                max_instances=1,
                misfire_grace_time=60,
            )
            logger.info(
                "Scheduled pipeline refresh every %d min", SCHEDULE_INTERVAL_MIN
            )
        if BANK_REFRESH_INTERVAL_MIN > 0:
            scheduler.add_job(
                lambda: _run_bank_refresh(nonce=None),
                "interval",
                minutes=BANK_REFRESH_INTERVAL_MIN,
                id="bank_refresh_auto",
                max_instances=1,
                misfire_grace_time=300,
            )
            logger.info(
                "Scheduled bank refresh (BOG + rs.ge) every %d min — "
                "TBC stays manual",
                BANK_REFRESH_INTERVAL_MIN,
            )
        scheduler.start()
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
    store: str | None = None,
    status_filter: str | None = None,
    type_filter: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    returns_only: bool | None = None,
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
            store,
            status_filter,
            type_filter,
            amount_min,
            amount_max,
            returns_only,
        )
    )

    if not has_dynamic_inputs and tab in STATIC_RESPONSE_TABS:
        try:
            artifact = load_artifact(tab)
            # archive.json changes between pipeline regenerations are NOT in
            # the static artifact, so re-apply runtime flags (archived +
            # excluded_from_analysis) per request. Mutation is idempotent.
            # Owner-facing impact: 📥 / 🚫 button presses reflect immediately,
            # not after the next pipeline run.
            if tab == "suppliers" and isinstance(artifact, dict):
                from dashboard_pipeline.api_contracts import refresh_archive_runtime_flags
                sups = artifact.get("suppliers")
                if isinstance(sups, list):
                    refresh_archive_runtime_flags(sups)
            return artifact
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
        store=store,
        status_filter=status_filter,
        type_filter=type_filter,
        amount_min=amount_min,
        amount_max=amount_max,
        returns_only=returns_only,
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
    store: str | None = None,
    status_filter: str | None = None,
    type_filter: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    returns_only: bool | None = None,
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
            store=store,
            status_filter=status_filter,
            type_filter=type_filter,
            amount_min=amount_min,
            amount_max=amount_max,
            returns_only=returns_only,
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
        "bank_refresh": dict(_bank_refresh_status),
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
# Bank refresh — Sprint C step 6 Phase 1
# ---------------------------------------------------------------------------


def _run_bank_refresh(nonce: str | None) -> None:
    """Thread target: call the bank orchestrator, then kick a pipeline regen.

    When ``nonce`` is provided, runs the full BOG + rs.ge + TBC orchestrator
    (TBC consumes the OTP). When ``nonce`` is None, runs BOG + rs.ge only —
    used by the auto-scheduler since TBC's DigiPass code can't be obtained
    without owner action.

    After the API fetch, we trigger `_run_pipeline` so the refreshed parquet
    caches actually flow into `data.json`. The pipeline lock makes this
    race-safe vs the global `/api/refresh` button.
    """
    from dashboard_pipeline.bank_refresh import (
        refresh_all_banks,
        refresh_bog_and_rsge_only,
    )

    if not _bank_refresh_lock.acquire(blocking=False):
        logger.info("Bank refresh already running, skipping")
        return
    try:
        _bank_refresh_status["state"] = "running"
        _bank_refresh_status["started_at"] = datetime.now(timezone.utc).isoformat()
        _bank_refresh_status["last_error"] = None
        if nonce is None:
            logger.info("Bank refresh started (auto: BOG + rs.ge, TBC skipped)")
            result = refresh_bog_and_rsge_only()
        else:
            logger.info("Bank refresh started (manual: BOG + rs.ge + TBC)")
            result = refresh_all_banks(nonce)

        _bank_refresh_status["last_result"] = result
        _bank_refresh_status["completed_at"] = datetime.now(timezone.utc).isoformat()
        _bank_refresh_status["runs_total"] += 1

        any_ok = any(result[k]["ok"] for k in ("bog", "rsge", "tbc"))
        # In auto-mode (nonce=None) TBC is intentionally skipped — don't
        # treat that as a failure.
        check_keys = ("bog", "rsge") if nonce is None else ("bog", "rsge", "tbc")
        all_ok = all(result[k]["ok"] for k in check_keys)
        if all_ok:
            _bank_refresh_status["state"] = "idle"
        else:
            _bank_refresh_status["state"] = "error"
            failures = [
                f"{k}={result[k].get('error', 'failed')}"
                for k in check_keys
                if not result[k]["ok"]
            ]
            _bank_refresh_status["last_error"] = "; ".join(failures)[:500]

        # Phase C — Fetch current balances for successful banks. Failures are
        # logged but do NOT mark the refresh as failed; balance is a "nice to
        # have" on top of the statement fetch.
        try:
            from dashboard_pipeline.bank_balance import (
                fetch_bog_balance,
                fetch_tbc_balance,
            )
            if result["bog"]["ok"]:
                try:
                    fetch_bog_balance()
                    logger.info("BOG balance fetched")
                except Exception as exc:
                    logger.warning("BOG balance fetch failed: %s", exc)
            if nonce and result["tbc"]["ok"]:
                try:
                    fetch_tbc_balance(nonce)
                    logger.info("TBC balance fetched")
                except Exception as exc:
                    logger.warning("TBC balance fetch failed: %s", exc)
        except Exception as exc:
            logger.warning("Balance phase skipped: %s", exc)

        if any_ok:
            # At least one cache changed — kick a pipeline regen so the
            # dashboard sees the new data. `_run_pipeline` is reentrant via
            # `_pipeline_lock` (no-op if a pipeline is already running).
            Thread(target=_run_pipeline, daemon=True).start()
    except Exception as exc:
        _bank_refresh_status["state"] = "error"
        _bank_refresh_status["last_error"] = str(exc)[:500]
        logger.error("Bank refresh exception: %s", exc)
    finally:
        _bank_refresh_lock.release()


@app.post("/api/banks/refresh")
@limiter.limit("1/minute")
async def trigger_bank_refresh(request: Request, payload: dict = Body(default={})):
    """Manually fetch fresh data from BOG / rs.ge / TBC into parquet caches.

    Body: `{"nonce": "123456789"}` — 9-digit DigiPass OTP for TBC. BOG and
    rs.ge use stored credentials; only TBC needs the OTP.

    Server-side OTP shape validation runs BEFORE any thread is spawned
    (memory: never let a malformed OTP reach `fetch_movements`).
    """
    from dashboard_pipeline.bank_refresh import OTP_RE

    if _bank_refresh_status["state"] == "running":
        return {
            "status": "already_running",
            "message": "Bank refresh is already running",
        }

    nonce = (payload.get("nonce") or "").strip()
    if not OTP_RE.match(nonce):
        raise HTTPException(
            status_code=400,
            detail="`nonce` must be exactly 9 digits (DigiPass OTP)",
        )

    Thread(target=_run_bank_refresh, args=(nonce,), daemon=True).start()
    return {
        "status": "started",
        "message": "Bank refresh kicked off in background",
    }


@app.get("/api/bank-balance")
@limiter.limit("30/minute")
async def get_bank_balance(request: Request):
    """Return the latest cached bank balances for BOG and TBC.

    Balances are populated as a side-effect of `POST /api/banks/refresh`.
    First-time visitors (no refresh ever) get an empty object.
    """
    from dashboard_pipeline.bank_balance import load_balances
    return load_balances()


@app.get("/api/cash-till")
@limiter.limit("30/minute")
async def get_cash_till(request: Request):
    """Per-store cash till change for [from, to] (defaults to last 14 days).

    Query params: ``from`` and ``to`` (ISO YYYY-MM-DD). ``from`` is read off
    the raw query string because it's a Python reserved word and FastAPI
    can't bind it to a function parameter.
    """
    from datetime import date as _date, timedelta as _td
    from dashboard_pipeline.cash_till import compute_cash_till

    qp = request.query_params
    today = _date.today()
    try:
        start = _date.fromisoformat(qp["from"]) if "from" in qp else today - _td(days=14)
        end = _date.fromisoformat(qp["to"]) if "to" in qp else today
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"bad date: {exc}")

    try:
        data = load_full_data()
        cdb = (data.get("retail_sales") or {}).get("cashier_day_breakdown") or []
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"could not load retail_sales: {exc}"
        )

    return compute_cash_till(cdb, start=start, end=end)


@app.get("/api/freshness")
@limiter.limit("60/minute")
async def get_data_freshness(request: Request):
    """Return how current each data source is.

    Reads:
      - `Financial_Analysis/cache/.last_refresh.json` — bank caches (TBC/BOG/rsge)
      - `Financial_Analysis/მეგაპლიუსის არქიტექტურა/*/_megaplus_state.json` —
        Megaplus ZIP ingest state per store
    """
    import json as _json
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parent
    out: dict = {"banks": {}, "megaplus": {}}

    bank_state = root / "Financial_Analysis" / "cache" / ".last_refresh.json"
    if bank_state.exists():
        try:
            out["banks"] = _json.loads(bank_state.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            out["banks"] = {}

    mp_root = root / "Financial_Analysis" / "მეგაპლიუსის არქიტექტურა"
    if mp_root.exists():
        for store_dir in mp_root.iterdir():
            state_file = store_dir / "_megaplus_state.json"
            if state_file.exists():
                try:
                    s = _json.loads(state_file.read_text(encoding="utf-8"))
                    out["megaplus"][store_dir.name] = {
                        "last_backup_date": s.get("last_backup_date"),
                        "last_processed_at": s.get("last_processed_at"),
                    }
                except Exception:  # noqa: BLE001
                    continue

    return out


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
    """Collect every barcode and product_code from the FULL retail universe
    so aliases targeting products outside the top-1000 dashboard slice
    (kორიდა → გორილა etc.) are accepted.

    Pipeline serializes ``retail_sales.retail_known_keys`` (flat string list
    covering all 8460+ products). Falls back to walking the truncated
    ``by_product`` slice if that field is missing — keeps the endpoint
    functional with older data.json files."""
    rs = data.get("retail_sales") or {}
    flat = rs.get("retail_known_keys")
    if isinstance(flat, list) and flat:
        return {str(k).strip() for k in flat if str(k).strip()}
    keys: set = set()
    for row in rs.get("by_product") or []:
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
# Orphan products — user status (ignored / active)
# ---------------------------------------------------------------------------
_orphan_status_lock = Lock()


@app.post("/api/orphan-products/status")
@limiter.limit("60/minute")
async def post_orphan_status(request: Request, payload: dict = Body(...)):
    """Toggle the user's "ignored" flag on a single orphan product.

    Body:
        {
            "store":       "დვაბზუ",       (required)
            "product_id":  12345,            (required)
            "ignored":     true,             (required boolean)
            "note":        "..."             (optional)
        }

    Persists to ``Financial_Analysis/orphan_user_status.json``. The
    dashboard's `data["orphan_products"].rows` exposes user_status on
    every pipeline run, so the change becomes visible after the next
    pipeline cycle (or immediate refresh).
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    store = payload.get("store")
    if not isinstance(store, str) or not store.strip():
        raise HTTPException(status_code=400, detail="`store` is required (string).")

    product_id_raw = payload.get("product_id")
    try:
        product_id = int(product_id_raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="`product_id` must be an integer.")

    ignored_raw = payload.get("ignored")
    if not isinstance(ignored_raw, bool):
        raise HTTPException(status_code=400, detail="`ignored` must be a boolean.")

    note = payload.get("note")
    if note is not None and not isinstance(note, str):
        raise HTTPException(status_code=400, detail="`note` must be a string when provided.")

    with _orphan_status_lock:
        try:
            new_map = orphan_user_status.set_status(
                store=store.strip(),
                product_id=product_id,
                ignored=ignored_raw,
                note=note,
            )
        except OSError as exc:
            logger.error("orphan status write failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"ფაილის ჩაწერა ვერ მოხერხდა: {exc}")

    logger.info(
        "orphan status %s: %s::%d (total ignored=%d)",
        "ignored" if ignored_raw else "cleared",
        store.strip(), product_id, len(new_map),
    )
    return {
        "success": True,
        "store": store.strip(),
        "product_id": product_id,
        "user_status": "ignored" if ignored_raw else "active",
        "ignored_count_total": len(new_map),
    }


# ---------------------------------------------------------------------------
# Suppliers — user archive flag
# ---------------------------------------------------------------------------
_supplier_archive_lock = Lock()


@app.post("/api/suppliers/archive")
@limiter.limit("60/minute")
async def post_supplier_archive(request: Request, payload: dict = Body(...)):
    """Update the user's archive / exclusion flags on a single supplier.

    Body (all flag fields optional — only the fields you pass are changed):
        {
            "tax_id":                 "200000000",   (required)
            "archived":               true,          (optional bool — back-compat)
            "note":                   "...",         (optional string)
            "excluded_from_analysis": true,          (optional bool — exclude from totals)
            "exclusion_reason":       "..."          (required string when excluded=true)
        }
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    tax_id = payload.get("tax_id")
    archived_raw = payload.get("archived")
    note = payload.get("note")
    excluded_raw = payload.get("excluded_from_analysis")
    exclusion_reason = payload.get("exclusion_reason")

    if not isinstance(tax_id, str) or not tax_id.strip():
        raise HTTPException(status_code=400, detail="`tax_id` (string) is required.")
    if archived_raw is not None and not isinstance(archived_raw, bool):
        raise HTTPException(status_code=400, detail="`archived` must be a boolean when provided.")
    if note is not None and not isinstance(note, str):
        raise HTTPException(status_code=400, detail="`note` must be a string when provided.")
    if excluded_raw is not None and not isinstance(excluded_raw, bool):
        raise HTTPException(status_code=400, detail="`excluded_from_analysis` must be a boolean when provided.")
    if exclusion_reason is not None and not isinstance(exclusion_reason, str):
        raise HTTPException(status_code=400, detail="`exclusion_reason` must be a string when provided.")
    if excluded_raw is True and not (exclusion_reason and exclusion_reason.strip()):
        raise HTTPException(
            status_code=400,
            detail="`exclusion_reason` is required when excluded_from_analysis=true.",
        )
    if archived_raw is None and excluded_raw is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of `archived` / `excluded_from_analysis` must be provided.",
        )

    with _supplier_archive_lock:
        try:
            new_map = supplier_archive.set_status(
                tax_id=tax_id.strip(),
                archived=archived_raw,
                note=note,
                excluded_from_analysis=excluded_raw,
                exclusion_reason=exclusion_reason,
            )
        except OSError as exc:
            logger.error("supplier archive write failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"ფაილის ჩაწერა ვერ მოხერხდა: {exc}")

    archived_count = sum(1 for e in new_map.values() if e.get("archived_at"))
    excluded_count = sum(1 for e in new_map.values() if e.get("excluded_from_analysis"))
    entry = new_map.get(tax_id.strip()) or {}
    logger.info(
        "supplier archive update: tax_id=%s archived=%s excluded=%s (totals: archived=%d excluded=%d)",
        tax_id.strip(),
        bool(entry.get("archived_at")),
        bool(entry.get("excluded_from_analysis")),
        archived_count,
        excluded_count,
    )
    return {
        "success": True,
        "tax_id": tax_id.strip(),
        "archived": bool(entry.get("archived_at")),
        "excluded_from_analysis": bool(entry.get("excluded_from_analysis")),
        "exclusion_reason": entry.get("exclusion_reason"),
        "archived_count_total": archived_count,
        "excluded_count_total": excluded_count,
    }


# ---------------------------------------------------------------------------
# Manual cash payments journal — owner-entered cash payments to suppliers
# ---------------------------------------------------------------------------


@app.get("/api/manual-payments")
@limiter.limit("120/minute")
async def get_manual_payments(request: Request, tax_id: str | None = None):
    """List active journal entries. Optionally filter by ?tax_id=..."""
    try:
        if tax_id:
            entries = manual_payments_journal.read_entries_for_tax_id(tax_id)
        else:
            entries = manual_payments_journal.read_active_entries()
    except OSError as exc:
        logger.error("manual_payments journal read failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"ჟურნალის წაკითხვა ვერ მოხერხდა: {exc}")
    return {"entries": entries, "count": len(entries)}


@app.post("/api/manual-payments")
@limiter.limit("60/minute")
async def post_manual_payment(request: Request, payload: dict = Body(...)):
    """Append one manual cash payment to the journal.

    Body:
        {
            "tax_id":  "406181616",        (required, digit string)
            "amount":  72972.50,           (required, > 0)
            "date":    "2026-05-07",       (optional, ISO date)
            "comment": "ჯიდიაი ნაღდი"     (optional)
        }
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    tax_id = payload.get("tax_id")
    amount = payload.get("amount")
    date = payload.get("date") or ""
    comment = payload.get("comment") or ""

    if not isinstance(tax_id, str) or not tax_id.strip():
        raise HTTPException(status_code=400, detail="`tax_id` (string) is required.")
    if not isinstance(amount, (int, float)):
        raise HTTPException(status_code=400, detail="`amount` (number) is required.")
    if isinstance(date, str) is False:
        raise HTTPException(status_code=400, detail="`date` must be a string when provided.")
    if isinstance(comment, str) is False:
        raise HTTPException(status_code=400, detail="`comment` must be a string when provided.")

    try:
        saved = manual_payments_journal.append_entry(
            tax_id=tax_id.strip(),
            amount=float(amount),
            date=date.strip(),
            comment=comment.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        logger.error("manual_payments journal write failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"ჟურნალში ჩაწერა ვერ მოხერხდა: {exc}")

    return {"success": True, "entry": saved}


@app.delete("/api/manual-payments/{entry_id}")
@limiter.limit("60/minute")
async def delete_manual_payment(request: Request, entry_id: str):
    """Soft-delete one journal entry by ID."""
    eid = (entry_id or "").strip()
    if not eid:
        raise HTTPException(status_code=400, detail="entry_id is required.")
    try:
        ok = manual_payments_journal.soft_delete_entry(eid)
    except OSError as exc:
        logger.error("manual_payments journal delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"წაშლა ვერ მოხერხდა: {exc}")
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found or already deleted.")
    return {"success": True, "id": eid}


# ---------------------------------------------------------------------------
# Cash expenses journal — non-bank cash outflows by category
# ---------------------------------------------------------------------------


@app.get("/api/cash-expenses")
@limiter.limit("60/minute")
async def get_cash_expenses(request: Request):
    """Return all active (non-deleted) cash-expense entries."""
    try:
        entries = cash_expenses_journal.read_active_entries()
    except OSError as exc:
        logger.error("cash_expenses_journal read failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"წაკითხვა ვერ მოხერხდა: {exc}")
    return {"entries": entries}


@app.post("/api/cash-expenses")
@limiter.limit("60/minute")
async def post_cash_expense(request: Request, payload: dict = Body(...)):
    """Append one cash-expense entry to the journal.

    Body:
        {
            "category": "salary",       (required, one of: salary, rent, owner, service, supplier_cash, other)
            "amount":   1500.00,        (required, > 0)
            "date":     "2026-04-30",   (optional, ISO date; defaults to today UTC)
            "comment":  "ხელფასი — დვაბზუ აპრილი"  (optional)
        }
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")
    category = payload.get("category")
    amount = payload.get("amount")
    date = payload.get("date") or ""
    comment = payload.get("comment") or ""
    if not isinstance(category, str) or not category.strip():
        raise HTTPException(status_code=400, detail="`category` (string) is required.")
    if not isinstance(amount, (int, float)):
        raise HTTPException(status_code=400, detail="`amount` (number) is required.")
    if not isinstance(date, str):
        raise HTTPException(status_code=400, detail="`date` must be a string.")
    if not isinstance(comment, str):
        raise HTTPException(status_code=400, detail="`comment` must be a string.")
    try:
        saved = cash_expenses_journal.append_entry(
            category=category.strip(),
            amount=float(amount),
            date=date.strip(),
            comment=comment.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        logger.error("cash_expenses_journal write failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"ჩაწერა ვერ მოხერხდა: {exc}")
    return {"success": True, "entry": saved}


@app.delete("/api/cash-expenses/{entry_id}")
@limiter.limit("60/minute")
async def delete_cash_expense(request: Request, entry_id: str):
    """Soft-delete one cash-expense entry by ID."""
    eid = (entry_id or "").strip()
    if not eid:
        raise HTTPException(status_code=400, detail="entry_id is required.")
    try:
        ok = cash_expenses_journal.soft_delete_entry(eid)
    except OSError as exc:
        logger.error("cash_expenses_journal delete failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"წაშლა ვერ მოხერხდა: {exc}")
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found or already deleted.")
    return {"success": True, "id": eid}


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


# ---------------------------------------------------------------------------
# Static frontend serving — single entry point at http://localhost:8000/
#
# Mount must come AFTER every @app.<verb>("/api/...") route is registered so
# that explicit API routes win over the catch-all static handler. With this
# in place the user has ONE URL to remember instead of juggling :5173 (Vite),
# :8000 (API), and a half-dozen Run_Dashboard*.bat scripts. The PWA service
# worker, /data.json, /tab-data/*, /assets/*, /download/* — all served from
# the same origin, no CORS, no port confusion.
#
# `html=True` makes StaticFiles serve `index.html` at / and on any unmatched
# path (SPA fallback). The app uses hash-based routing so the fallback isn't
# strictly required for navigation, but it's cheap insurance.
#
# Skipped silently if `rs-dashboard/dist/` doesn't exist yet — happens on a
# fresh checkout before the first `npm run build`. API still serves /api/*.
# ---------------------------------------------------------------------------
_DIST_PATH = Path(__file__).resolve().parent / "rs-dashboard" / "dist"
if _DIST_PATH.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST_PATH), html=True), name="static")
    logger.info("Frontend mount: %s → / (single-port mode)", _DIST_PATH)
else:
    logger.info("Frontend mount: skipped (dist not built at %s)", _DIST_PATH)


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
