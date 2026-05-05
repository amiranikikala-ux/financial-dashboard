"""Build the orphan_products section of data.json by querying MegaPlus
SQL directly (live), with SOAP-resolved supplier names served from a
small persisted cache.

This module is non-interactive — pipeline-callable. It does NOT touch
rs.ge SOAP. New TINs whose name is unknown to both DISTRIBUTORS and the
cache stay nameless ('best_supplier_name' is None) and are tagged as
'RS_CODES (TIN unknown to DISTRIBUTORS)'. To resolve them, run the
dedicated CLI manually (interactive — needs RS.ge password):

    & "C:\\Users\\tengiz\\OneDrive\\Desktop\\AI აგენტი\\venv\\Scripts\\python.exe" \\
        -m dashboard_pipeline.orphan_resolver

That CLI updates Financial_Analysis/orphan_soap_cache.json, which the
next pipeline run picks up automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from dashboard_pipeline.orphan_resolver import (
    build_orphan_dataframe,
    load_soap_cache,
)
from dashboard_pipeline import orphan_user_status

logger = logging.getLogger(__name__)


def _format_dt(v: Any) -> str | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    return s.split(" ")[0] if s else None


def _round(v: Any, digits: int = 2) -> float:
    try:
        return round(float(v or 0), digits)
    except (ValueError, TypeError):
        return 0.0


def _int(v: Any) -> int:
    try:
        if v is None or pd.isna(v):
            return 0
        return int(v)
    except (ValueError, TypeError):
        return 0


def _clean_str(v: Any) -> str | None:
    """Return None for missing values (None / NaN / empty), trimmed string otherwise."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def build_orphan_products_bundle(financial_analysis_dir: Path) -> dict[str, Any] | None:
    """Live MegaPlus DB query → public JSON bundle for data.json.

    Returns None if the SQL query fails (caller logs and skips).
    """
    try:
        soap_cache = load_soap_cache(financial_analysis_dir)
        df = build_orphan_dataframe(soap_cache)
    except Exception as exc:
        logger.warning("orphan_products: DB query failed — %s", exc)
        return None

    if df is None or df.empty:
        logger.info("orphan_products: 0 orphans returned — section omitted")
        return None

    user_ignored = orphan_user_status.load(financial_analysis_dir)

    # ---- public rows ----
    rows_out: list[dict[str, Any]] = []
    by_resolution = {"resolved_single": 0, "multi_candidate": 0, "no_match": 0}
    by_store_acc: dict[str, dict[str, Any]] = {}
    total_revenue = 0.0
    ignored_count = 0
    ignored_revenue = 0.0
    active_count = 0
    active_revenue = 0.0

    for _, rec in df.iterrows():
        n_cand = _int(rec.get("n_candidates"))
        method = rec.get("resolution_method") or ""
        if n_cand == 0 or method == "NO MATCH":
            bucket = "no_match"
        elif n_cand >= 2:
            bucket = "multi_candidate"
        else:
            bucket = "resolved_single"
        by_resolution[bucket] += 1
        revenue = _round(rec.get("lifetime_revenue"))
        total_revenue += revenue

        store = rec.get("store") or ""
        st_agg = by_store_acc.setdefault(store, {
            "store": store,
            "orphan_count": 0,
            "lifetime_revenue_ge": 0.0,
            "resolved_count": 0,
            "soap_fallback_count": 0,
            "no_match_count": 0,
        })
        st_agg["orphan_count"] += 1
        st_agg["lifetime_revenue_ge"] += revenue
        # pandas wraps missing object cells in NaN (a float, which is truthy);
        # use pd.notna so we only count rows whose DIST_UUID is a real string.
        if pd.notna(rec.get("best_DIST_UUID")) and str(rec.get("best_DIST_UUID")).strip():
            st_agg["resolved_count"] += 1
        if isinstance(method, str) and method.startswith("SOAP"):
            st_agg["soap_fallback_count"] += 1
        if method == "NO MATCH":
            st_agg["no_match_count"] += 1

        all_tins_raw = _clean_str(rec.get("all_candidate_TINs")) or ""
        all_tins = [t.strip() for t in all_tins_raw.split(",") if t.strip()]

        product_id = _int(rec.get("P_ID"))
        ignored_entry = user_ignored.get(f"{store}::{product_id}")
        is_ignored = ignored_entry is not None
        if is_ignored:
            ignored_count += 1
            ignored_revenue += revenue
        else:
            active_count += 1
            active_revenue += revenue

        rows_out.append({
            "store": store,
            "product_id": product_id,
            "product_name": _clean_str(rec.get("P_NAME")),
            "barcode": _clean_str(rec.get("P_BARCODE")) or "",
            "orphan_kind": _clean_str(rec.get("orphan_kind")),
            "lifetime_revenue_ge": revenue,
            "sale_lines": _int(rec.get("sale_lines")),
            "last_sale_at": _format_dt(rec.get("last_sale_at")),
            "n_candidates": n_cand,
            "best_supplier_name": _clean_str(rec.get("best_supplier_name")),
            "best_tin": _clean_str(rec.get("best_TIN")),
            "best_in_distributors": (_clean_str(rec.get("best_in_DISTRIBUTORS")) == "YES"),
            "all_candidate_tins": all_tins,
            "resolution_method": _clean_str(method),
            "resolution_bucket": bucket,
            "user_status": "ignored" if is_ignored else "active",
            "ignored_at": (ignored_entry or {}).get("ignored_at") if is_ignored else None,
        })

    rows_out.sort(key=lambda r: r["lifetime_revenue_ge"], reverse=True)

    # Finalize per-store summary
    by_store: list[dict[str, Any]] = []
    for st in sorted(by_store_acc.values(), key=lambda s: s["store"]):
        st["lifetime_revenue_ge"] = _round(st["lifetime_revenue_ge"])
        st["resolved_pct"] = (
            round(st["resolved_count"] / st["orphan_count"] * 100, 1)
            if st["orphan_count"] else 0.0
        )
        by_store.append(st)

    bundle = {
        "label_ka": "შეუსაბამო პროდუქცია",
        "source": "megaplus_sql_live",
        "source_generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "total_count": len(rows_out),
            "total_revenue_ge": _round(total_revenue),
            "by_resolution": by_resolution,
            "by_store": by_store,
            "user_status_counts": {
                "active": active_count,
                "ignored": ignored_count,
            },
            "user_status_revenue_ge": {
                "active": _round(active_revenue),
                "ignored": _round(ignored_revenue),
            },
        },
        "rows": rows_out,
    }

    logger.info(
        "orphan_products: %d რიგი (%.0f ₾) | resolved=%d, multi=%d, no_match=%d | active=%d, ignored=%d | source=megaplus_sql_live",
        len(rows_out), total_revenue,
        by_resolution["resolved_single"], by_resolution["multi_candidate"],
        by_resolution["no_match"],
        active_count, ignored_count,
    )
    return bundle
