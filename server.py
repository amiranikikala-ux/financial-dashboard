import hashlib
import hmac
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from backend_paths import get_dashboard_data_path, get_dashboard_tab_data_path
from dashboard_pipeline.api_contracts import (
    ALLOWED_TABS,
    DYNAMIC_SOURCE_ARTIFACTS,
    STATIC_RESPONSE_TABS,
    build_response_for_tab,
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
SCHEDULE_INTERVAL_MIN = int(os.environ.get("DASHBOARD_REFRESH_MINUTES", "30"))

_pipeline_lock = Lock()
_pipeline_status = {
    "state": "idle",        # idle | running | error
    "last_run": None,       # ISO timestamp
    "last_duration_s": None,
    "last_error": None,
    "runs_total": 0,
}


def _run_pipeline():
    """Run generate_dashboard_data in a subprocess (thread-safe)."""
    acquired = _pipeline_lock.acquire(blocking=False)
    if not acquired:
        logger.info("Pipeline already running, skipping")
        return
    try:
        _pipeline_status["state"] = "running"
        _pipeline_status["last_error"] = None
        start = datetime.now(timezone.utc)
        logger.info("Pipeline regeneration started")

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "generate_dashboard_data.py",
        )
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=30 * 60,  # 30 min hard limit
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        _pipeline_status["last_duration_s"] = round(elapsed, 1)
        _pipeline_status["last_run"] = datetime.now(timezone.utc).isoformat()
        _pipeline_status["runs_total"] += 1

        if result.returncode != 0:
            err_msg = (result.stderr or result.stdout or "unknown error")[-500:]
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


def get_tab_payload(
    tab: str = "suppliers",
    tax_id: str | None = None,
    normalized_supplier: str | None = None,
    product_code: str | None = None,
    normalized_product: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
):
    """
    Build the same JSON object as GET /api/data (synchronous, for scripts/tests).

    Raises ValueError when tab is not in ALLOWED_TABS (same condition as HTTP 400).
    """
    if tab not in ALLOWED_TABS:
        allowed = ", ".join(ALLOWED_TABS)
        raise ValueError(f"Invalid tab '{tab}'. Allowed tabs: {allowed}")

    has_dynamic_inputs = any(
        value is not None
        for value in (
            tax_id,
            normalized_supplier,
            product_code,
            normalized_product,
            q,
            sort,
            limit,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
