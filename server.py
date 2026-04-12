import json
import os
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend_paths import get_dashboard_data_path, get_dashboard_tab_data_path
from dashboard_pipeline.api_contracts import (
    ALLOWED_TABS,
    DYNAMIC_SOURCE_ARTIFACTS,
    STATIC_RESPONSE_TABS,
    build_response_for_tab,
)

app = FastAPI()

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
            print(f"Loaded {os.path.basename(path)} (mtime={current_mtime}).")
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
            print(f"Loaded data.json (mtime={current_mtime}).")
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
            print(f"Artifact fallback for {tab}: {exc}")
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
            print(f"Static artifact fallback for {tab}: {exc}")

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


@app.on_event("startup")
async def startup_event():
    try:
        load_artifact("suppliers", force=True)
    except Exception as artifact_exc:
        print(f"Startup artifact warning: {artifact_exc}")
        try:
            load_full_data(force=True)
        except Exception as full_exc:
            print(f"Startup warning: {full_exc}")


@app.get("/api/data")
async def get_data(
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
