"""
Retail sales bundle: empty_retail_sales_bundle, collect_retail_sales_bundle.

Extracted from generate_dashboard_data.py lines 5053-5743.

Tier 2 Sprint 2 (2026-04-22) split collect_retail_sales_bundle into
per-file extraction (``_process_retail_sales_file``) and a merge step
that assembles per-file payloads into the full bundle. When invoked
with ``use_cache=True`` and no period filter, unchanged files reuse the
payload stored in ``.pipeline_cache.json`` and skip the Excel re-read.
"""
import hashlib
import json
import os
from collections import defaultdict

import pandas as pd

from dashboard_pipeline.constants import (
    OBJECT_COMMON,
    OBJECT_DVABZU,
    OBJECT_OZURGETI,
    OBJECT_UNALLOCATED,
    RETAIL_SALES_CATEGORY_LIMIT,
    RETAIL_SALES_DUPLICATE_POLICY_MODE,
    RETAIL_SALES_DUPLICATE_SUSPECTED_FILES,
    RETAIL_SALES_PRODUCT_LIMIT,
    RETAIL_SALES_READ_ERROR_LIMIT,
    RETAIL_SALES_ROWS_PREVIEW_LIMIT,
    RETAIL_SALES_TOP_LIMIT,
    _clone_default_object_mapping,
    _month_sort_key,
    _normalize_for_match,
    _parse_rs_datetime,
    _safe_text,
    detect_object,
)
from dashboard_pipeline.date_filters import serialize_period_filter
from dashboard_pipeline.file_utils import (
    _to_financial_relative_path,
    list_retail_sales_files,
)
from dashboard_pipeline.pipeline_cache import (
    DEFAULT_CACHE_FILENAME,
    compute_file_signature,
    file_has_changed,
    get_payload,
    empty_cache,
    load_cache,
    put_entry,
    save_cache,
)
from dashboard_pipeline.supplier_matching import normalize_name


RETAIL_SALES_READ_COLUMNS = {
    "კოდი",
    "შტრიხკოდი",
    "დასახელება",
    "ერთეული",
    "რაოდენობა",
    "ფასი",
    "თვითღირებულება",
    "მოგება",
    "დრო",
    "ობიექტი",
    "ქვეჯგუფი",
}


# ---------------------------------------------------------------------------
# Internal helpers (pure functions)
# ---------------------------------------------------------------------------

def _coerce_float(value):
    if isinstance(value, str):
        value = value.replace(" ", "").replace(",", ".")
    num = pd.to_numeric(value, errors="coerce")
    if pd.isna(num):
        return 0.0
    return float(num)


def _clean_text(value, fallback=""):
    text = _safe_text(value).strip()
    return text if text else fallback


def _clean_code(value, fallback=""):
    """Like _clean_text but strips the trailing ".0" pandas adds when Excel
    stored a numeric code (barcode / product_code) as a number rather than
    text. Without this, the same physical SKU produces TWO by_product rows
    — one keyed on "4860103230027", another on "4860103230027.0" — which
    splits revenue and breaks downstream name-match deduplication.
    """
    text = _safe_text(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text if text else fallback


def _margin_pct(revenue, profit):
    revenue_val = float(revenue or 0)
    if revenue_val == 0:
        return 0.0
    return float((float(profit or 0) / revenue_val) * 100.0)


def _fmt_date(dt):
    if dt is None or pd.isna(dt):
        return None
    return pd.Timestamp(dt).strftime("%Y-%m-%d")


def _iso_or_none(dt):
    """Full timestamp ISO for per-file payload — preserves precision so
    cross-file min/max merge stays consistent."""
    if dt is None or pd.isna(dt):
        return None
    return pd.Timestamp(dt).strftime("%Y-%m-%dT%H:%M:%S")


def _file_date_range_overlaps_period(file_stats, period_filter):
    if not period_filter or not bool(period_filter.get("applied")):
        return True
    if not isinstance(file_stats, dict):
        return True
    date_range = file_stats.get("date_range") or {}
    min_date = str(date_range.get("min") or "").strip()
    max_date = str(date_range.get("max") or "").strip()
    if not min_date or not max_date:
        return True
    from_ts = period_filter.get("from_ts")
    to_ts = period_filter.get("to_ts")
    if from_ts is None or to_ts is None:
        return True
    try:
        min_ts = pd.Timestamp(f"{min_date} 00:00:00")
        max_ts = pd.Timestamp(f"{max_date} 23:59:59")
    except Exception:
        return True
    return not (max_ts < from_ts or min_ts > to_ts)


def _filter_source_files_by_period(files, period_filter=None, source_file_stats=None):
    if not files or not period_filter or not bool(period_filter.get("applied")):
        return files
    stats_by_relative_path = {
        str(item.get("relative_path") or "").strip(): item
        for item in (source_file_stats or [])
        if isinstance(item, dict) and str(item.get("relative_path") or "").strip()
    }
    if not stats_by_relative_path:
        return files
    filtered_files = []
    for path in files:
        file_stats = stats_by_relative_path.get(_to_financial_relative_path(path))
        if file_stats is None or _file_date_range_overlaps_period(file_stats, period_filter):
            filtered_files.append(path)
    return filtered_files


def _category_month_margin_pct(revenue, profit):
    revenue_val = float(revenue or 0)
    if revenue_val == 0:
        return 0.0
    return float((float(profit or 0) / revenue_val) * 100.0)


def _build_by_category_by_month_rows(category_month_stats, category_display_names=None):
    """Serialize per-(category, month) accumulator into sorted list of rows.

    Feeds Phase 2.9 trend_detector: lets AI compare per-category revenue/margin
    month-over-month without scanning raw retail_sales rows.
    """
    display_names = category_display_names or {}
    rows = []
    for (category_key, month_key), stats in category_month_stats.items():
        if not month_key or month_key == "უცნობი თვე":
            continue
        revenue = float(stats.get("revenue_ge") or 0)
        cost = float(stats.get("cost_ge") or 0)
        profit = float(stats.get("profit_ge") or 0)
        quantity = float(stats.get("total_quantity") or 0)
        row_count = int(stats.get("row_count") or 0)
        rows.append(
            {
                "category": display_names.get(category_key) or category_key or "უცნობი კატეგორია",
                "normalized_category": category_key or None,
                "month": month_key,
                "row_count": row_count,
                "total_quantity": quantity,
                "revenue_ge": revenue,
                "cost_ge": cost,
                "profit_ge": profit,
                "gross_margin_pct": float(_category_month_margin_pct(revenue, profit)),
            }
        )
    rows.sort(
        key=lambda row: (
            str(row.get("normalized_category") or ""),
            _month_sort_key(row.get("month") or ""),
        )
    )
    return rows


def _build_by_object_by_month_rows(object_month_stats):
    """Serialize per-(object, month) accumulator into sorted list of rows.

    Feeds Sprint 5.8 vat_reconciliation `by_shop`: lets the AI tool compare
    per-shop MAX POS revenue against per-shop bank POS deposits and surface
    per-shop cashreg_in (= MAX − bank_card) for audit defense.
    """
    rows = []
    for (object_label, month_key), stats in object_month_stats.items():
        if not month_key or month_key == "უცნობი თვე":
            continue
        revenue = float(stats.get("revenue_ge") or 0)
        cost = float(stats.get("cost_ge") or 0)
        profit = float(stats.get("profit_ge") or 0)
        quantity = float(stats.get("total_quantity") or 0)
        row_count = int(stats.get("row_count") or 0)
        rows.append(
            {
                "object": object_label or OBJECT_UNALLOCATED,
                "month": month_key,
                "row_count": row_count,
                "total_quantity": quantity,
                "revenue_ge": revenue,
                "cost_ge": cost,
                "profit_ge": profit,
                "gross_margin_pct": float(_margin_pct(revenue, profit)),
            }
        )
    rows.sort(
        key=lambda row: (
            str(row.get("object") or ""),
            _month_sort_key(row.get("month") or ""),
        )
    )
    return rows


def _object_from_path(path):
    parent = _normalize_for_match(os.path.basename(os.path.dirname(path)))
    if "ოზურგეთი" in parent:
        return OBJECT_OZURGETI
    if "დვაბზუ" in parent:
        return OBJECT_DVABZU
    return OBJECT_UNALLOCATED


def _content_fingerprint(object_mapping) -> str:
    """Fingerprint the non-file inputs so cache invalidates if they shift.

    Covers object_mapping (per-run) + the duplicate-suspected constant
    (code-level). If either changes, the cache is treated as empty so
    we never serve stale per-file aggregates.
    """
    blob = json.dumps(
        {
            "mapping": object_mapping or {},
            "duplicate_suspected": RETAIL_SALES_DUPLICATE_SUSPECTED_FILES,
            "duplicate_policy_mode": RETAIL_SALES_DUPLICATE_POLICY_MODE,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# empty_retail_sales_bundle
# ---------------------------------------------------------------------------

def synthesize_from_megaplus(megaplus_live):
    """Build a `retail_sales`-shaped bundle from `data["megaplus_live"]`.

    Lets `RetailSales.jsx` (and downstream consumers like the AI tools)
    keep their existing schema after the Excel POS folders were retired.
    Per-store rows from each MegaPlus DB rollup are aggregated to the
    portfolio level for `overall` / `by_*` tables; per-store
    contributions stay visible via `by_object` and `by_object_by_month`.

    Field-name mapping (MegaPlus → retail_sales):
      qty_sold → total_quantity, revenue → revenue_ge, cogs → cost_ge,
      profit → profit_ge, margin_pct → gross_margin_pct.
    """
    stores = (megaplus_live or {}).get("stores") or {}
    if not stores:
        return None

    store_label_for = {"1329": "დვაბზუ", "1301": "ოზურგეთი"}

    # ─── overall (portfolio sum) ────────────────────────────────────────────
    overall_revenue = 0.0
    overall_cost = 0.0
    overall_profit = 0.0
    overall_qty = 0.0
    overall_rows = 0
    min_date = None
    max_date = None
    distinct_products: set = set()
    distinct_categories: set = set()
    distinct_objects: set = set()

    for store_id, rollup in stores.items():
        totals = rollup.get("totals") or {}
        overall_revenue += float(totals.get("revenue") or 0)
        overall_cost += float(totals.get("cogs") or 0)
        overall_profit += float(totals.get("profit") or 0)
        overall_qty += sum(float(p.get("qty_sold") or 0) for p in rollup.get("by_product") or [])
        overall_rows += int(totals.get("sale_lines") or 0)
        for p in rollup.get("by_product") or []:
            key = (p.get("barcode") or "").strip() or (p.get("product_code") or "").strip() or str(p.get("product_id"))
            if key:
                distinct_products.add(key)
            cat = p.get("category") or ""
            if cat:
                distinct_categories.add(cat)
        distinct_objects.add(store_label_for.get(str(store_id)) or f"store_{store_id}")

        rng = rollup.get("data_range") or {}
        rmin = (rng.get("min_timestamp") or "")[:10] or None
        rmax = (rng.get("max_timestamp") or "")[:10] or None
        if rmin and (min_date is None or rmin < min_date):
            min_date = rmin
        if rmax and (max_date is None or rmax > max_date):
            max_date = rmax

    overall_margin = (overall_profit / overall_revenue * 100) if overall_revenue > 0 else 0.0

    # ─── by_object ──────────────────────────────────────────────────────────
    by_object = []
    for store_id, rollup in stores.items():
        obj_label = store_label_for.get(str(store_id)) or f"store_{store_id}"
        totals = rollup.get("totals") or {}
        rev = float(totals.get("revenue") or 0)
        cost = float(totals.get("cogs") or 0)
        profit = float(totals.get("profit") or 0)
        qty = sum(float(p.get("qty_sold") or 0) for p in rollup.get("by_product") or [])
        rows = int(totals.get("sale_lines") or 0)
        margin = (profit / rev * 100) if rev > 0 else 0.0
        by_object.append({
            "object": obj_label,
            "row_count": rows,
            "total_quantity": qty,
            "revenue_ge": round(rev, 2),
            "cost_ge": round(cost, 2),
            "profit_ge": round(profit, 2),
            "gross_margin_pct": round(margin, 2),
        })

    # ─── by_month (aggregate across stores) ────────────────────────────────
    month_acc: dict = {}
    for store_id, rollup in stores.items():
        for m in rollup.get("by_month") or []:
            key = m.get("month")
            if not key:
                continue
            cur = month_acc.setdefault(key, {
                "month": key, "row_count": 0, "total_quantity": 0.0,
                "revenue_ge": 0.0, "cost_ge": 0.0, "profit_ge": 0.0,
            })
            cur["row_count"] += int(m.get("row_count") or 0)
            cur["total_quantity"] += float(m.get("qty_sold") or 0)
            cur["revenue_ge"] += float(m.get("revenue") or 0)
            cur["cost_ge"] += float(m.get("cogs") or 0)
            cur["profit_ge"] += float(m.get("profit") or 0)
    by_month = []
    for k in sorted(month_acc.keys()):
        row = month_acc[k]
        rev = row["revenue_ge"]
        margin = (row["profit_ge"] / rev * 100) if rev > 0 else 0.0
        row["gross_margin_pct"] = round(margin, 2)
        by_month.append({k2: round(v, 2) if isinstance(v, float) else v for k2, v in row.items()})

    # ─── by_object_by_month (per-store × per-month) ─────────────────────────
    by_object_by_month = []
    for store_id, rollup in stores.items():
        obj_label = store_label_for.get(str(store_id)) or f"store_{store_id}"
        for m in rollup.get("by_month") or []:
            rev = float(m.get("revenue") or 0)
            cost = float(m.get("cogs") or 0)
            profit = float(m.get("profit") or 0)
            margin = (profit / rev * 100) if rev > 0 else 0.0
            by_object_by_month.append({
                "object": obj_label,
                "month": m.get("month"),
                "row_count": int(m.get("row_count") or 0),
                "total_quantity": float(m.get("qty_sold") or 0),
                "revenue_ge": round(rev, 2),
                "cost_ge": round(cost, 2),
                "profit_ge": round(profit, 2),
                "gross_margin_pct": round(margin, 2),
            })

    # ─── by_category (aggregate across stores by category name) ─────────────
    cat_acc: dict = {}
    for store_id, rollup in stores.items():
        for c in rollup.get("by_category") or []:
            key = c.get("category") or "(უცნობი)"
            cur = cat_acc.setdefault(key, {
                "category": key, "row_count": 0,
                "total_quantity": 0.0, "revenue_ge": 0.0,
                "cost_ge": 0.0, "profit_ge": 0.0,
                "distinct_product_count": 0,
            })
            cur["row_count"] += int(c.get("row_count") or 0)
            cur["total_quantity"] += float(c.get("qty_sold") or 0)
            cur["revenue_ge"] += float(c.get("revenue") or 0)
            cur["cost_ge"] += float(c.get("cogs") or 0)
            cur["profit_ge"] += float(c.get("profit") or 0)
            cur["distinct_product_count"] += int(c.get("distinct_product_count") or 0)
    by_category = []
    for key, row in sorted(cat_acc.items(), key=lambda kv: kv[1]["revenue_ge"], reverse=True):
        rev = row["revenue_ge"]
        row["gross_margin_pct"] = round((row["profit_ge"] / rev * 100) if rev > 0 else 0.0, 2)
        for f in ("revenue_ge", "cost_ge", "profit_ge", "total_quantity"):
            row[f] = round(row[f], 2)
        by_category.append(row)

    # ─── by_category_by_month (cross-tab) ──────────────────────────────────
    cb_acc: dict = {}
    for store_id, rollup in stores.items():
        for cm in rollup.get("by_category_by_month") or []:
            key = (cm.get("month"), cm.get("category") or "(უცნობი)")
            if not key[0]:
                continue
            cur = cb_acc.setdefault(key, {
                "month": key[0], "category": key[1],
                "row_count": 0, "total_quantity": 0.0,
                "revenue_ge": 0.0, "cost_ge": 0.0, "profit_ge": 0.0,
            })
            cur["row_count"] += int(cm.get("row_count") or 0)
            cur["total_quantity"] += float(cm.get("qty_sold") or 0)
            cur["revenue_ge"] += float(cm.get("revenue") or 0)
            cur["cost_ge"] += float(cm.get("cogs") or 0)
            cur["profit_ge"] += float(cm.get("profit") or 0)
    by_category_by_month = []
    for key in sorted(cb_acc.keys()):
        row = cb_acc[key]
        rev = row["revenue_ge"]
        row["gross_margin_pct"] = round((row["profit_ge"] / rev * 100) if rev > 0 else 0.0, 2)
        for f in ("revenue_ge", "cost_ge", "profit_ge", "total_quantity"):
            row[f] = round(row[f], 2)
        by_category_by_month.append(row)

    # ─── by_product (aggregate across stores by barcode/code) ──────────────
    prod_acc: dict = {}
    for store_id, rollup in stores.items():
        obj_label = store_label_for.get(str(store_id)) or f"store_{store_id}"
        for p in rollup.get("by_product") or []:
            barcode = (p.get("barcode") or "").strip()
            code = (p.get("product_code") or "").strip()
            key = barcode or code or f"pid_{p.get('product_id')}"
            if not key:
                continue
            cur = prod_acc.setdefault(key, {
                "product_key": key,
                "product_code": code,
                "barcode": barcode,
                "product_name": p.get("product_name") or "",
                "unit": p.get("unit") or "",
                "category": p.get("category") or "",
                "row_count": 0, "total_quantity": 0.0,
                "revenue_ge": 0.0, "cost_ge": 0.0, "profit_ge": 0.0,
                "object_totals": [],
                "min_date": None, "max_date": None,
            })
            qty = float(p.get("qty_sold") or 0)
            rev = float(p.get("revenue") or 0)
            cost = float(p.get("cogs") or 0)
            profit = float(p.get("profit") or 0)
            rc = int(p.get("row_count") or 0)
            cur["row_count"] += rc
            cur["total_quantity"] += qty
            cur["revenue_ge"] += rev
            cur["cost_ge"] += cost
            cur["profit_ge"] += profit
            obj_margin = (profit / rev * 100) if rev > 0 else 0.0
            cur["object_totals"].append({
                "object": obj_label,
                "row_count": rc,
                "total_quantity": qty,
                "revenue_ge": round(rev, 2),
                "cost_ge": round(cost, 2),
                "profit_ge": round(profit, 2),
                "gross_margin_pct": round(obj_margin, 2),
            })
            for src_field, agg_field, less_is_more in (
                ("min_date", "min_date", True),
                ("max_date", "max_date", False),
            ):
                v = p.get(src_field)
                if not v:
                    continue
                vs = str(v)[:10]
                if cur[agg_field] is None or (less_is_more and vs < cur[agg_field]) or (not less_is_more and vs > cur[agg_field]):
                    cur[agg_field] = vs

    by_product_full = list(prod_acc.values())
    # Compute per-product margin and round
    for row in by_product_full:
        rev = row["revenue_ge"]
        row["gross_margin_pct"] = round((row["profit_ge"] / rev * 100) if rev > 0 else 0.0, 2)
        for f in ("revenue_ge", "cost_ge", "profit_ge", "total_quantity"):
            row[f] = round(row[f], 2)

    # Truncate UI by_product to keep data.json tractable; full list is used
    # only for downstream supplier matching (not serialized verbatim).
    PRODUCT_LIMIT = 1000
    by_product_full.sort(key=lambda r: r.get("revenue_ge", 0), reverse=True)
    by_product = by_product_full[:PRODUCT_LIMIT]

    # Flat key list for /api/aliases/confirm validation — covers the FULL
    # retail universe so aliases targeting products outside the top-1000
    # truncation (kორიდა → გორილა etc.) are accepted.
    retail_known_keys_set = set()
    for row in by_product_full:
        bc = (row.get("barcode") or "").strip()
        pc = (row.get("product_code") or "").strip()
        if bc:
            retail_known_keys_set.add(bc)
        if pc:
            retail_known_keys_set.add(pc)
    retail_known_keys = sorted(retail_known_keys_set)

    # ─── Top lists ──────────────────────────────────────────────────────────
    top_categories_by_profit = sorted(by_category, key=lambda r: r.get("profit_ge", 0), reverse=True)[:25]
    top_objects_by_profit = sorted(by_object, key=lambda r: r.get("profit_ge", 0), reverse=True)
    top_products_by_revenue = sorted(by_product_full, key=lambda r: r.get("revenue_ge", 0), reverse=True)[:50]
    top_products_by_profit = sorted(by_product_full, key=lambda r: r.get("profit_ge", 0), reverse=True)[:50]

    return {
        "label_ka": "გაყიდული პროდუქცია (MegaPlus DB direct)",
        "notes_ka": (
            "MegaPlus per-store SQL backup-დან მიღებული რეტეილ გაყიდვები "
            "(დვაბზუ + ოზურგეთი). Cost-ი GET ცხრილიდან imputed-ია — MAX POS-"
            "ის ცარიელი ORD_GETPRICE ცვლის. წყარო: `Financial_Analysis/მეგა "
            "პლუს backup*/PLUS_<store>_MEGA_<date>.zip`."
        ),
        "source_glob": [
            "Financial_Analysis/მეგა პლუს backup/PLUS_*.zip",
            "Financial_Analysis/მეგა პლუს backup ოზურგეთი/PLUS_*.zip",
        ],
        "amount_basis_ka": (
            "`ORD_jamjam` = revenue, GET-table imputed cost-ი (cost_paid / "
            "qty_bought × MIN(qty_bought, qty_sold) cap-ით) = cost_ge, profit "
            "= revenue − imputed cost."
        ),
        "duplicate_policy": {
            "mode": "megaplus_db_direct",
            "notes_ka": "MegaPlus DB-ში duplicate-ი არ არის — ORDERS.ORD_ACT = 1 ფილტრი იცავს.",
            "suspected_files": [],
            "excluded_files": [],
            "excluded_file_count": 0,
        },
        "files_found_count": len(stores),
        "files_read_count": len(stores),
        "files_error_count": 0,
        "files_skipped_by_policy_count": 0,
        "files_skipped_by_policy": [],
        "files": [],
        "read_errors": [],
        "overall": {
            "row_count": overall_rows,
            "total_quantity": round(overall_qty, 2),
            "revenue_ge": round(overall_revenue, 2),
            "cost_ge": round(overall_cost, 2),
            "profit_ge": round(overall_profit, 2),
            "gross_margin_pct": round(overall_margin, 2),
            "distinct_object_count": len(distinct_objects),
            "distinct_category_count": len(distinct_categories),
            "distinct_product_count": len(distinct_products),
            "date_range": {"min": min_date, "max": max_date},
        },
        "by_object": by_object,
        "category_total_count": len(by_category),
        "categories_truncated": False,
        "by_category": by_category,
        "products_total_count": len(by_product_full),
        "products_truncated": len(by_product_full) > PRODUCT_LIMIT,
        "by_product": by_product,
        "retail_known_keys": retail_known_keys,
        "by_month": by_month,
        "by_category_by_month": by_category_by_month,
        "by_object_by_month": by_object_by_month,
        "top_objects_by_profit": top_objects_by_profit,
        "top_categories_by_profit": top_categories_by_profit,
        "top_products_by_revenue": top_products_by_revenue,
        "top_products_by_profit": top_products_by_profit,
        "rows_preview": [],
        "period_meta": {"applied": False, "label_ka": "MegaPlus DB lifetime"},
    }


def empty_retail_sales_bundle(period_filter=None):
    return {
        "label_ka": "გაყიდული პროდუქცია (retail sales source)",
        "notes_ka": (
            "Retail sales source (დვაბზუ + ოზურგეთი). გამოიყენება sell-through / "
            "revenue / cost / profit / margin ანალიზისთვის და მკაფიოდ გამოყოფილია "
            "supplier debt/AP/bank reconciliation truth boundary-სგან."
        ),
        "source_glob": [
            "Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/*.xlsx",
            "Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/*.xlsx",
        ],
        "source_column_schema_expected": [
            "P_ID",
            "კოდი",
            "შტრიხკოდი",
            "დასახელება",
            "ერთეული",
            "რაოდენობა",
            "ფასი",
            "თვითღირებულება",
            "დრო",
            "ობიექტი",
            "მოგება",
            "ქვეჯგუფი",
            "ცვლა",
        ],
        "amount_basis_ka": "`ფასი` = revenue, `თვითღირებულება` = cost, `მოგება` = profit.",
        "duplicate_policy": {
            "mode": RETAIL_SALES_DUPLICATE_POLICY_MODE,
            "notes_ka": (
                "Duplicate-suspected source default-ად totals-იდან გამორიცხულია, "
                "სანამ explicit inclusion/exclusion policy არ დადგება."
            ),
            "suspected_files": [],
            "excluded_files": [],
            "excluded_file_count": 0,
        },
        "files_found_count": 0,
        "files_read_count": 0,
        "files_error_count": 0,
        "files_skipped_by_policy_count": 0,
        "files_skipped_by_policy": [],
        "files": [],
        "read_errors": [],
        "overall": {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
            "gross_margin_pct": 0.0,
            "distinct_object_count": 0,
            "distinct_category_count": 0,
            "distinct_product_count": 0,
            "date_range": {"min": None, "max": None},
        },
        "by_object": [],
        "category_total_count": 0,
        "categories_truncated": False,
        "by_category": [],
        "products_total_count": 0,
        "products_truncated": False,
        "by_product": [],
        "by_month": [],
        "by_category_by_month": [],
        "by_object_by_month": [],
        "top_objects_by_profit": [],
        "top_categories_by_profit": [],
        "top_products_by_revenue": [],
        "top_products_by_profit": [],
        "rows_preview": [],
        "period_meta": serialize_period_filter(period_filter),
    }


# ---------------------------------------------------------------------------
# _process_retail_sales_file — per-file extraction (cacheable unit)
# ---------------------------------------------------------------------------

def _process_retail_sales_file(
    path: str,
    *,
    object_mapping,
    period_filter=None,
):
    """Parse one retail sales Excel file into a JSON-serializable payload.

    Returns a dict with:
      - ``status``: "ok" or "read_error"
      - ``files_entry``: dict appended to bundle["files"] at merge time
      - ``by_object``, ``by_category``, ``by_product``, ``by_month``,
        ``by_category_by_month``: per-file aggregates merged upstream
      - ``preview_rows``: per-file rows (pre-global-sort)
      - ``date_range_iso``: {min, max} ISO strings for global date range
      - ``total_rows_seen``, ``matched_rows``, ``excluded_unparseable_count``
        for period-filter metadata at the bundle level
      - ``read_error`` (when status=="read_error"): dict for bundle["read_errors"]

    period_filter is honored here for correctness (API path calls with a
    filter), but the caller passes period_filter=None when it wants the
    payload to be cacheable.
    """
    sales_object_mapping = object_mapping or _clone_default_object_mapping()
    file_name = os.path.basename(path)
    file_rel = _to_financial_relative_path(path)
    fallback_object = _object_from_path(path)

    def _pick_object(row_value, fallback):
        detected = detect_object(
            "rs_waybill",
            rs_location=row_value,
            object_mapping=sales_object_mapping,
        )
        detected = str(detected or "").strip()
        if detected and detected not in {OBJECT_UNALLOCATED, OBJECT_COMMON}:
            return detected
        if fallback and fallback != OBJECT_UNALLOCATED:
            return fallback
        return detected or fallback or OBJECT_UNALLOCATED

    try:
        df = pd.read_excel(
            path,
            usecols=lambda col: str(col).strip() in RETAIL_SALES_READ_COLUMNS,
        )
    except Exception as exc:
        return {
            "status": "read_error",
            "read_error": {
                "name": file_name,
                "relative_path": file_rel,
                "error": str(exc),
            },
        }

    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    unnamed_cols = [c for c in df.columns if str(c).strip().startswith("Unnamed:")]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols, errors="ignore")

    source_row_count = int(len(df.index))
    required_summary_cols = [
        "კოდი",
        "დასახელება",
        "რაოდენობა",
        "ფასი",
        "თვითღირებულება",
        "მოგება",
        "დრო",
        "ობიექტი",
        "ქვეჯგუფი",
    ]
    missing_columns = [c for c in required_summary_cols if c not in df.columns]

    parsed_dates = pd.Series(pd.NaT, index=df.index)
    if "დრო" in df.columns:
        date_text = df["დრო"].fillna("").astype(str).str.strip()
        parsed_dates = pd.to_datetime(
            date_text,
            errors="coerce",
            format="%Y-%m-%d %H:%M",
        )
        fallback_mask = parsed_dates.isna() & date_text.ne("")
        if fallback_mask.any():
            parsed_dates.loc[fallback_mask] = date_text.loc[fallback_mask].map(
                _parse_rs_datetime
            )

    excluded_unparseable = 0
    if period_filter and bool(period_filter.get("applied")):
        excluded_unparseable = int(parsed_dates.isna().sum())
        matched_mask = (
            parsed_dates.notna()
            & (parsed_dates >= period_filter["from_ts"])
            & (parsed_dates <= period_filter["to_ts"])
        )
        df = df.loc[matched_mask].copy()
        parsed_dates = parsed_dates.loc[matched_mask]

    file_dates = []
    file_revenue = 0.0
    file_cost = 0.0
    file_profit = 0.0
    file_quantity = 0.0
    file_profit_fallback_rows = 0
    matched_file_row_count = int(len(df.index))

    month_stats = defaultdict(
        lambda: {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
        }
    )
    object_stats = {}
    category_stats = {}
    product_stats = {}
    category_month_stats = defaultdict(
        lambda: {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
        }
    )
    # Sprint 5.8 — per-shop per-month aggregation for VAT-reconciliation by_shop.
    # Keyed by (object, month_key). Mirror shape of category_month_stats.
    object_month_stats = defaultdict(
        lambda: {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
        }
    )
    preview_rows = []

    def _update_range(entry, dt):
        if dt is None or pd.isna(dt):
            return
        if entry.get("min_date") is None or pd.isna(entry.get("min_date")) or dt < entry["min_date"]:
            entry["min_date"] = dt
        if entry.get("max_date") is None or pd.isna(entry.get("max_date")) or dt > entry["max_date"]:
            entry["max_date"] = dt

    for row_index, row in df.iterrows():
        date_value = parsed_dates.get(row_index, pd.NaT)
        quantity = _coerce_float(row.get("რაოდენობა"))
        unit_price = _coerce_float(row.get("ფასი"))
        unit_cost = _coerce_float(row.get("თვითღირებულება"))
        # MAX POS export stores ფასი / თვითღირებულება as PER-UNIT values,
        # so true line revenue and line cost are price × quantity. Sprint 5.5
        # fix (2026-04-23) — prior code summed unit prices directly, which
        # overstated revenue by ~9% on typical months (e.g. 2024-08 pipeline
        # 282K vs direct MAX read 259K) and inflated cashreg_in downstream.
        revenue_ge = unit_price * quantity
        cost_ge = unit_cost * quantity
        raw_profit = pd.to_numeric(
            _safe_text(row.get("მოგება")).replace(",", "."),
            errors="coerce",
        )
        if pd.isna(raw_profit):
            profit_ge = revenue_ge - cost_ge
            file_profit_fallback_rows += 1
        else:
            profit_ge = float(raw_profit)

        month_key = (
            pd.Timestamp(date_value).strftime("%Y-%m")
            if not pd.isna(date_value)
            else "უცნობი თვე"
        )
        object_label = _pick_object(row.get("ობიექტი"), fallback_object)
        category = _clean_text(row.get("ქვეჯგუფი"), "უცნობი კატეგორია")
        category_key = normalize_name(category) or category.lower()
        product_code = _clean_code(row.get("კოდი"))
        barcode = _clean_code(row.get("შტრიხკოდი"))
        product_name = _clean_text(
            row.get("დასახელება"),
            product_code or barcode or "უცნობი პროდუქტი",
        )
        product_name_key = normalize_name(product_name) or product_name.lower()
        unit = _clean_text(row.get("ერთეული"))
        product_key = f"{product_code}||{barcode}||{product_name_key}"

        file_revenue += revenue_ge
        file_cost += cost_ge
        file_profit += profit_ge
        file_quantity += quantity

        month_stats[month_key]["row_count"] += 1
        month_stats[month_key]["total_quantity"] += quantity
        month_stats[month_key]["revenue_ge"] += revenue_ge
        month_stats[month_key]["cost_ge"] += cost_ge
        month_stats[month_key]["profit_ge"] += profit_ge

        object_entry = object_stats.setdefault(
            object_label,
            {
                "object": object_label,
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
                "category_keys": set(),
                "product_keys": set(),
                "month_keys": set(),
                "min_date": None,
                "max_date": None,
            },
        )
        object_entry["row_count"] += 1
        object_entry["total_quantity"] += quantity
        object_entry["revenue_ge"] += revenue_ge
        object_entry["cost_ge"] += cost_ge
        object_entry["profit_ge"] += profit_ge
        object_entry["category_keys"].add(category_key)
        object_entry["product_keys"].add(product_key)
        if month_key != "უცნობი თვე":
            object_entry["month_keys"].add(month_key)
        _update_range(object_entry, date_value)

        category_entry = category_stats.setdefault(
            category_key,
            {
                "category": category,
                "normalized_category": category_key,
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
                "object_totals": {},
                "product_keys": set(),
                "month_keys": set(),
                "min_date": None,
                "max_date": None,
            },
        )
        if category and category_entry["category"] == "უცნობი კატეგორია":
            category_entry["category"] = category
        category_entry["row_count"] += 1
        category_entry["total_quantity"] += quantity
        category_entry["revenue_ge"] += revenue_ge
        category_entry["cost_ge"] += cost_ge
        category_entry["profit_ge"] += profit_ge
        category_entry["product_keys"].add(product_key)
        if month_key != "უცნობი თვე":
            category_entry["month_keys"].add(month_key)
        _update_range(category_entry, date_value)
        cat_object_totals = category_entry["object_totals"].setdefault(
            object_label,
            {
                "object": object_label,
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
            },
        )
        cat_object_totals["row_count"] += 1
        cat_object_totals["total_quantity"] += quantity
        cat_object_totals["revenue_ge"] += revenue_ge
        cat_object_totals["cost_ge"] += cost_ge
        cat_object_totals["profit_ge"] += profit_ge

        if month_key != "უცნობი თვე":
            cm = category_month_stats[(category_key, month_key)]
            cm["row_count"] += 1
            cm["total_quantity"] += quantity
            cm["revenue_ge"] += revenue_ge
            cm["cost_ge"] += cost_ge
            cm["profit_ge"] += profit_ge

            om = object_month_stats[(object_label, month_key)]
            om["row_count"] += 1
            om["total_quantity"] += quantity
            om["revenue_ge"] += revenue_ge
            om["cost_ge"] += cost_ge
            om["profit_ge"] += profit_ge

        product_entry = product_stats.setdefault(
            product_key,
            {
                "product_code": product_code,
                "barcode": barcode,
                "product_name": product_name,
                "unit": unit,
                "category": category,
                "category_key": category_key,
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
                "object_totals": {},
                "month_keys": set(),
                "min_date": None,
                "max_date": None,
            },
        )
        if product_name and product_entry["product_name"] == "უცნობი პროდუქტი":
            product_entry["product_name"] = product_name
        if unit and not product_entry["unit"]:
            product_entry["unit"] = unit
        if product_code and not product_entry["product_code"]:
            product_entry["product_code"] = product_code
        if barcode and not product_entry["barcode"]:
            product_entry["barcode"] = barcode
        if category and product_entry["category"] == "უცნობი კატეგორია":
            product_entry["category"] = category
        product_entry["row_count"] += 1
        product_entry["total_quantity"] += quantity
        product_entry["revenue_ge"] += revenue_ge
        product_entry["cost_ge"] += cost_ge
        product_entry["profit_ge"] += profit_ge
        if month_key != "უცნობი თვე":
            product_entry["month_keys"].add(month_key)
        _update_range(product_entry, date_value)
        prod_object_totals = product_entry["object_totals"].setdefault(
            object_label,
            {
                "object": object_label,
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
            },
        )
        prod_object_totals["row_count"] += 1
        prod_object_totals["total_quantity"] += quantity
        prod_object_totals["revenue_ge"] += revenue_ge
        prod_object_totals["cost_ge"] += cost_ge
        prod_object_totals["profit_ge"] += profit_ge

        if not pd.isna(date_value):
            file_dates.append(date_value)

        preview_rows.append(
            {
                "date": _fmt_date(date_value),
                "file_name": file_name,
                "object": object_label,
                "category": category,
                "product_name": product_name,
                "product_code": product_code,
                "barcode": barcode,
                "quantity": quantity,
                "unit": unit,
                "revenue_ge": revenue_ge,
                "cost_ge": cost_ge,
                "profit_ge": profit_ge,
            }
        )

    files_entry = {
        "name": file_name,
        "relative_path": file_rel,
        "source_row_count": source_row_count,
        "row_count": matched_file_row_count,
        "total_quantity": float(file_quantity),
        "revenue_ge": float(file_revenue),
        "cost_ge": float(file_cost),
        "profit_ge": float(file_profit),
        "gross_margin_pct": float(_margin_pct(file_revenue, file_profit)),
        "profit_fallback_rows": int(file_profit_fallback_rows),
        "distinct_object_count": len(object_stats),
        "distinct_category_count": len(category_stats),
        "distinct_product_count": len(product_stats),
        "object_from_folder": (
            fallback_object if fallback_object != OBJECT_UNALLOCATED else None
        ),
        "date_range": {
            "min": _fmt_date(min(file_dates)) if file_dates else None,
            "max": _fmt_date(max(file_dates)) if file_dates else None,
        },
        "missing_columns": missing_columns,
    }

    by_object_serial = [
        {
            "object": item["object"],
            "row_count": int(item["row_count"]),
            "total_quantity": float(item["total_quantity"]),
            "revenue_ge": float(item["revenue_ge"]),
            "cost_ge": float(item["cost_ge"]),
            "profit_ge": float(item["profit_ge"]),
            "category_keys": sorted(item["category_keys"]),
            "product_keys": sorted(item["product_keys"]),
            "month_keys": sorted(item["month_keys"]),
            "min_date": _iso_or_none(item["min_date"]),
            "max_date": _iso_or_none(item["max_date"]),
        }
        for item in object_stats.values()
    ]

    by_category_serial = [
        {
            "category_key": item["normalized_category"],
            "category_display": item["category"],
            "row_count": int(item["row_count"]),
            "total_quantity": float(item["total_quantity"]),
            "revenue_ge": float(item["revenue_ge"]),
            "cost_ge": float(item["cost_ge"]),
            "profit_ge": float(item["profit_ge"]),
            "product_keys": sorted(item["product_keys"]),
            "month_keys": sorted(item["month_keys"]),
            "min_date": _iso_or_none(item["min_date"]),
            "max_date": _iso_or_none(item["max_date"]),
            "object_totals": [
                {
                    "object": obj["object"],
                    "row_count": int(obj["row_count"]),
                    "total_quantity": float(obj["total_quantity"]),
                    "revenue_ge": float(obj["revenue_ge"]),
                    "cost_ge": float(obj["cost_ge"]),
                    "profit_ge": float(obj["profit_ge"]),
                }
                for obj in item["object_totals"].values()
            ],
        }
        for item in category_stats.values()
    ]

    by_product_serial = [
        {
            "product_key": key,
            "product_code": item["product_code"],
            "barcode": item["barcode"],
            "product_name": item["product_name"],
            "unit": item["unit"],
            "category": item["category"],
            "category_key": item["category_key"],
            "row_count": int(item["row_count"]),
            "total_quantity": float(item["total_quantity"]),
            "revenue_ge": float(item["revenue_ge"]),
            "cost_ge": float(item["cost_ge"]),
            "profit_ge": float(item["profit_ge"]),
            "month_keys": sorted(item["month_keys"]),
            "min_date": _iso_or_none(item["min_date"]),
            "max_date": _iso_or_none(item["max_date"]),
            "object_totals": [
                {
                    "object": obj["object"],
                    "row_count": int(obj["row_count"]),
                    "total_quantity": float(obj["total_quantity"]),
                    "revenue_ge": float(obj["revenue_ge"]),
                    "cost_ge": float(obj["cost_ge"]),
                    "profit_ge": float(obj["profit_ge"]),
                }
                for obj in item["object_totals"].values()
            ],
        }
        for key, item in product_stats.items()
    ]

    by_month_serial = [
        {
            "month": month_key,
            "row_count": int(stats["row_count"]),
            "total_quantity": float(stats["total_quantity"]),
            "revenue_ge": float(stats["revenue_ge"]),
            "cost_ge": float(stats["cost_ge"]),
            "profit_ge": float(stats["profit_ge"]),
        }
        for month_key, stats in month_stats.items()
    ]

    by_object_month_serial = [
        {
            "object": obj_label,
            "month": month_key,
            "row_count": int(stats["row_count"]),
            "total_quantity": float(stats["total_quantity"]),
            "revenue_ge": float(stats["revenue_ge"]),
            "cost_ge": float(stats["cost_ge"]),
            "profit_ge": float(stats["profit_ge"]),
        }
        for (obj_label, month_key), stats in object_month_stats.items()
    ]

    by_cat_month_serial = [
        {
            "category_key": cat_key,
            "month": month_key,
            "row_count": int(stats["row_count"]),
            "total_quantity": float(stats["total_quantity"]),
            "revenue_ge": float(stats["revenue_ge"]),
            "cost_ge": float(stats["cost_ge"]),
            "profit_ge": float(stats["profit_ge"]),
        }
        for (cat_key, month_key), stats in category_month_stats.items()
    ]

    # Cap preview_rows at the global preview limit BEFORE returning, so the
    # per-file cache payload stays small. Sort by (date desc, revenue desc,
    # product_name) — same key the downstream merger uses, so taking top-N
    # per file first and merging is equivalent to taking top-N globally
    # (pigeonhole: union of per-file top-N ⊇ global top-N when the sort
    # key is total-ordered). Pre-Sprint-3a this field stored all matched
    # rows per file (up to ~384k rows × 6 files = ~2M rows cached).
    def _preview_row_sort_key(row):
        date_str = row.get("date") or ""
        ts = 0.0
        if date_str:
            try:
                ts = pd.Timestamp(date_str).timestamp()
            except Exception:
                ts = float("-inf")
        else:
            ts = float("-inf")
        return (ts, float(row.get("revenue_ge") or 0), str(row.get("product_name") or ""))

    if len(preview_rows) > RETAIL_SALES_ROWS_PREVIEW_LIMIT:
        preview_rows.sort(key=_preview_row_sort_key, reverse=True)
        preview_rows = preview_rows[:RETAIL_SALES_ROWS_PREVIEW_LIMIT]

    return {
        "status": "ok",
        "files_entry": files_entry,
        "by_object": by_object_serial,
        "by_category": by_category_serial,
        "by_product": by_product_serial,
        "by_month": by_month_serial,
        "by_category_by_month": by_cat_month_serial,
        "by_object_by_month": by_object_month_serial,
        "preview_rows": preview_rows,
        "date_range_iso": {
            "min": _iso_or_none(min(file_dates)) if file_dates else None,
            "max": _iso_or_none(max(file_dates)) if file_dates else None,
        },
        "total_rows_seen": int(source_row_count),
        "matched_rows": int(matched_file_row_count),
        "excluded_unparseable_count": int(excluded_unparseable),
    }


# ---------------------------------------------------------------------------
# Merge helpers — per-file payloads → master accumulators
# ---------------------------------------------------------------------------

def _merge_min_iso(existing, candidate):
    if candidate is None:
        return existing
    if existing is None or candidate < existing:
        return candidate
    return existing


def _merge_max_iso(existing, candidate):
    if candidate is None:
        return existing
    if existing is None or candidate > existing:
        return candidate
    return existing


def _iso_to_yyyymmdd(iso):
    if not iso:
        return None
    return iso[:10] if len(iso) >= 10 else iso


def _merge_object(master_object_stats, per_file):
    for item in per_file:
        entry = master_object_stats.setdefault(
            item["object"],
            {
                "object": item["object"],
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
                "category_keys": set(),
                "product_keys": set(),
                "month_keys": set(),
                "min_date_iso": None,
                "max_date_iso": None,
            },
        )
        entry["row_count"] += int(item["row_count"])
        entry["total_quantity"] += float(item["total_quantity"])
        entry["revenue_ge"] += float(item["revenue_ge"])
        entry["cost_ge"] += float(item["cost_ge"])
        entry["profit_ge"] += float(item["profit_ge"])
        entry["category_keys"].update(item.get("category_keys") or [])
        entry["product_keys"].update(item.get("product_keys") or [])
        entry["month_keys"].update(item.get("month_keys") or [])
        entry["min_date_iso"] = _merge_min_iso(entry["min_date_iso"], item.get("min_date"))
        entry["max_date_iso"] = _merge_max_iso(entry["max_date_iso"], item.get("max_date"))


def _merge_category(master_category_stats, per_file):
    for item in per_file:
        cat_key = item["category_key"]
        entry = master_category_stats.setdefault(
            cat_key,
            {
                "category": item["category_display"] or "უცნობი კატეგორია",
                "normalized_category": cat_key,
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
                "object_totals": {},
                "product_keys": set(),
                "month_keys": set(),
                "min_date_iso": None,
                "max_date_iso": None,
            },
        )
        display = item.get("category_display") or ""
        if display and entry["category"] == "უცნობი კატეგორია":
            entry["category"] = display
        entry["row_count"] += int(item["row_count"])
        entry["total_quantity"] += float(item["total_quantity"])
        entry["revenue_ge"] += float(item["revenue_ge"])
        entry["cost_ge"] += float(item["cost_ge"])
        entry["profit_ge"] += float(item["profit_ge"])
        entry["product_keys"].update(item.get("product_keys") or [])
        entry["month_keys"].update(item.get("month_keys") or [])
        entry["min_date_iso"] = _merge_min_iso(entry["min_date_iso"], item.get("min_date"))
        entry["max_date_iso"] = _merge_max_iso(entry["max_date_iso"], item.get("max_date"))
        for obj_item in item.get("object_totals") or []:
            obj_entry = entry["object_totals"].setdefault(
                obj_item["object"],
                {
                    "object": obj_item["object"],
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                },
            )
            obj_entry["row_count"] += int(obj_item["row_count"])
            obj_entry["total_quantity"] += float(obj_item["total_quantity"])
            obj_entry["revenue_ge"] += float(obj_item["revenue_ge"])
            obj_entry["cost_ge"] += float(obj_item["cost_ge"])
            obj_entry["profit_ge"] += float(obj_item["profit_ge"])


def _merge_product(master_product_stats, per_file):
    for item in per_file:
        key = item["product_key"]
        entry = master_product_stats.setdefault(
            key,
            {
                "product_code": item.get("product_code") or "",
                "barcode": item.get("barcode") or "",
                "product_name": item.get("product_name") or "უცნობი პროდუქტი",
                "unit": item.get("unit") or "",
                "category": item.get("category") or "უცნობი კატეგორია",
                "category_key": item.get("category_key") or "",
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
                "object_totals": {},
                "month_keys": set(),
                "min_date_iso": None,
                "max_date_iso": None,
            },
        )
        if item.get("product_name") and entry["product_name"] == "უცნობი პროდუქტი":
            entry["product_name"] = item["product_name"]
        if item.get("unit") and not entry["unit"]:
            entry["unit"] = item["unit"]
        if item.get("product_code") and not entry["product_code"]:
            entry["product_code"] = item["product_code"]
        if item.get("barcode") and not entry["barcode"]:
            entry["barcode"] = item["barcode"]
        if item.get("category") and entry["category"] == "უცნობი კატეგორია":
            entry["category"] = item["category"]
        entry["row_count"] += int(item["row_count"])
        entry["total_quantity"] += float(item["total_quantity"])
        entry["revenue_ge"] += float(item["revenue_ge"])
        entry["cost_ge"] += float(item["cost_ge"])
        entry["profit_ge"] += float(item["profit_ge"])
        entry["month_keys"].update(item.get("month_keys") or [])
        entry["min_date_iso"] = _merge_min_iso(entry["min_date_iso"], item.get("min_date"))
        entry["max_date_iso"] = _merge_max_iso(entry["max_date_iso"], item.get("max_date"))
        for obj_item in item.get("object_totals") or []:
            obj_entry = entry["object_totals"].setdefault(
                obj_item["object"],
                {
                    "object": obj_item["object"],
                    "row_count": 0,
                    "total_quantity": 0.0,
                    "revenue_ge": 0.0,
                    "cost_ge": 0.0,
                    "profit_ge": 0.0,
                },
            )
            obj_entry["row_count"] += int(obj_item["row_count"])
            obj_entry["total_quantity"] += float(obj_item["total_quantity"])
            obj_entry["revenue_ge"] += float(obj_item["revenue_ge"])
            obj_entry["cost_ge"] += float(obj_item["cost_ge"])
            obj_entry["profit_ge"] += float(obj_item["profit_ge"])


def _merge_month(master_month_stats, per_file):
    for item in per_file:
        entry = master_month_stats.setdefault(
            item["month"],
            {
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
            },
        )
        entry["row_count"] += int(item["row_count"])
        entry["total_quantity"] += float(item["total_quantity"])
        entry["revenue_ge"] += float(item["revenue_ge"])
        entry["cost_ge"] += float(item["cost_ge"])
        entry["profit_ge"] += float(item["profit_ge"])


def _merge_category_month(master_cat_month, per_file):
    for item in per_file:
        key = (item["category_key"], item["month"])
        entry = master_cat_month.setdefault(
            key,
            {
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
            },
        )
        entry["row_count"] += int(item["row_count"])
        entry["total_quantity"] += float(item["total_quantity"])
        entry["revenue_ge"] += float(item["revenue_ge"])
        entry["cost_ge"] += float(item["cost_ge"])
        entry["profit_ge"] += float(item["profit_ge"])


def _merge_object_month(master_object_month, per_file):
    for item in per_file:
        key = (item["object"], item["month"])
        entry = master_object_month.setdefault(
            key,
            {
                "row_count": 0,
                "total_quantity": 0.0,
                "revenue_ge": 0.0,
                "cost_ge": 0.0,
                "profit_ge": 0.0,
            },
        )
        entry["row_count"] += int(item["row_count"])
        entry["total_quantity"] += float(item["total_quantity"])
        entry["revenue_ge"] += float(item["revenue_ge"])
        entry["cost_ge"] += float(item["cost_ge"])
        entry["profit_ge"] += float(item["profit_ge"])


# ---------------------------------------------------------------------------
# collect_retail_sales_bundle — orchestrator (cacheable when no period filter)
# ---------------------------------------------------------------------------

def collect_retail_sales_bundle(
    object_mapping=None,
    period_filter=None,
    source_file_stats=None,
    *,
    use_cache: bool = False,
    cache_path=None,
):
    """Assemble the retail_sales bundle.

    Tier 2 Sprint 2: when ``use_cache=True`` and no period filter is
    applied, per-file payloads are cached in
    ``.pipeline_cache.json`` (or ``cache_path`` override) and reused for
    unchanged files on the next run. When a period filter is applied the
    cache is bypassed entirely — filtered reads are per-request and
    cheap enough not to need caching.
    """
    files = list_retail_sales_files()
    bundle = empty_retail_sales_bundle(period_filter=period_filter)
    bundle["files_found_count"] = len(files)
    if not files:
        return bundle

    candidate_files = _filter_source_files_by_period(
        files,
        period_filter=period_filter,
        source_file_stats=source_file_stats,
    )

    sales_object_mapping = object_mapping or _clone_default_object_mapping()
    period_applied = bool((period_filter or {}).get("applied"))
    cache_enabled = bool(use_cache) and not period_applied
    cache: dict = empty_cache()
    resolved_cache_path = None
    if cache_enabled:
        resolved_cache_path = cache_path or os.path.abspath(DEFAULT_CACHE_FILENAME)
        cache = load_cache(
            resolved_cache_path,
            content_fingerprint=_content_fingerprint(sales_object_mapping),
        )

    duplicate_suspected_map = {
        f"Financial_Analysis/{str(path).replace(chr(92), '/').strip('/')}": dict(cfg or {})
        for path, cfg in RETAIL_SALES_DUPLICATE_SUSPECTED_FILES.items()
    }
    suspected_records = {
        path: {
            "relative_path": path,
            "suspected_duplicate_of": (
                f"Financial_Analysis/{str(cfg.get('suspected_duplicate_of') or '').replace(chr(92), '/').strip('/')}"
                if str(cfg.get("suspected_duplicate_of") or "").strip()
                else ""
            ),
            "reason_ka": str(cfg.get("reason_ka") or ""),
            "present_in_sources": False,
            "included_in_totals": False,
        }
        for path, cfg in duplicate_suspected_map.items()
    }

    # Master accumulators
    all_dates_iso_min = None
    all_dates_iso_max = None
    master_month_stats = {}
    master_object_stats = {}
    master_category_stats = {}
    master_product_stats = {}
    master_category_month_stats = {}
    master_object_month_stats = {}
    preview_candidates = []
    read_error_count = 0
    total_rows_seen = 0
    matched_rows = 0
    excluded_unparseable_count = 0

    for f in candidate_files:
        file_rel = _to_financial_relative_path(f)
        if file_rel in duplicate_suspected_map:
            suspected_records[file_rel]["present_in_sources"] = True
            bundle["files_skipped_by_policy"].append(file_rel)
            continue

        payload = None
        if cache_enabled:
            try:
                if not file_has_changed(f, cache):
                    payload = get_payload(cache, f)
            except Exception:
                payload = None

        if payload is None:
            payload = _process_retail_sales_file(
                f,
                object_mapping=sales_object_mapping,
                period_filter=period_filter,
            )
            if cache_enabled and payload.get("status") == "ok":
                try:
                    sig = compute_file_signature(f)
                    put_entry(cache, f, sig, payload)
                except OSError:
                    pass  # cannot stat → don't cache; next run will retry

        if payload.get("status") == "read_error":
            read_error_count += 1
            if len(bundle["read_errors"]) < RETAIL_SALES_READ_ERROR_LIMIT:
                bundle["read_errors"].append(payload["read_error"])
            continue

        bundle["files"].append(payload["files_entry"])
        _merge_object(master_object_stats, payload.get("by_object") or [])
        _merge_category(master_category_stats, payload.get("by_category") or [])
        _merge_product(master_product_stats, payload.get("by_product") or [])
        _merge_month(master_month_stats, payload.get("by_month") or [])
        _merge_category_month(
            master_category_month_stats, payload.get("by_category_by_month") or []
        )
        _merge_object_month(
            master_object_month_stats, payload.get("by_object_by_month") or []
        )
        for row in payload.get("preview_rows") or []:
            preview_candidates.append(row)

        date_range_iso = payload.get("date_range_iso") or {}
        all_dates_iso_min = _merge_min_iso(all_dates_iso_min, date_range_iso.get("min"))
        all_dates_iso_max = _merge_max_iso(all_dates_iso_max, date_range_iso.get("max"))
        total_rows_seen += int(payload.get("total_rows_seen") or 0)
        matched_rows += int(payload.get("matched_rows") or 0)
        excluded_unparseable_count += int(payload.get("excluded_unparseable_count") or 0)

    if cache_enabled and resolved_cache_path:
        # Drop cache entries for files that are no longer on disk / no
        # longer in the candidate list so the cache doesn't leak.
        expected_keys = {
            os.path.normpath(f)
            for f in candidate_files
            if _to_financial_relative_path(f) not in duplicate_suspected_map
        }
        cache_files = cache.get("files") if isinstance(cache, dict) else None
        if isinstance(cache_files, dict):
            for stale in [k for k in cache_files.keys() if k not in expected_keys]:
                cache_files.pop(stale, None)
        try:
            save_cache(resolved_cache_path, cache)
        except OSError:
            pass

    bundle["files_read_count"] = len(bundle["files"])
    bundle["files_error_count"] = int(read_error_count)
    bundle["files_skipped_by_policy_count"] = len(bundle["files_skipped_by_policy"])

    for rel_path, record in suspected_records.items():
        if rel_path in bundle["files_skipped_by_policy"]:
            record["present_in_sources"] = True
    bundle["duplicate_policy"]["suspected_files"] = [
        suspected_records[key] for key in sorted(suspected_records)
    ]
    bundle["duplicate_policy"]["excluded_files"] = sorted(bundle["files_skipped_by_policy"])
    bundle["duplicate_policy"]["excluded_file_count"] = int(
        len(bundle["files_skipped_by_policy"])
    )
    bundle["period_meta"] = serialize_period_filter(
        period_filter,
        total_rows_seen=total_rows_seen,
        matched_rows=matched_rows,
        excluded_unparseable_count=excluded_unparseable_count,
    )

    overall_revenue = float(sum(item.get("revenue_ge") or 0 for item in bundle["files"]))
    overall_cost = float(sum(item.get("cost_ge") or 0 for item in bundle["files"]))
    overall_profit = float(sum(item.get("profit_ge") or 0 for item in bundle["files"]))
    overall_quantity = float(
        sum(item.get("total_quantity") or 0 for item in bundle["files"])
    )
    bundle["overall"] = {
        "row_count": int(sum(item.get("row_count") or 0 for item in bundle["files"])),
        "total_quantity": overall_quantity,
        "revenue_ge": overall_revenue,
        "cost_ge": overall_cost,
        "profit_ge": overall_profit,
        "gross_margin_pct": float(_margin_pct(overall_revenue, overall_profit)),
        "distinct_object_count": len(master_object_stats),
        "distinct_category_count": len(master_category_stats),
        "distinct_product_count": len(master_product_stats),
        "date_range": {
            "min": _iso_to_yyyymmdd(all_dates_iso_min),
            "max": _iso_to_yyyymmdd(all_dates_iso_max),
        },
    }

    bundle["by_month"] = [
        {
            "month": month,
            "row_count": int(stats.get("row_count") or 0),
            "total_quantity": float(stats.get("total_quantity") or 0),
            "revenue_ge": float(stats.get("revenue_ge") or 0),
            "cost_ge": float(stats.get("cost_ge") or 0),
            "profit_ge": float(stats.get("profit_ge") or 0),
            "gross_margin_pct": float(
                _margin_pct(stats.get("revenue_ge") or 0, stats.get("profit_ge") or 0)
            ),
        }
        for month, stats in sorted(
            master_month_stats.items(), key=lambda item: _month_sort_key(item[0])
        )
    ]

    object_rows = []
    for item in master_object_stats.values():
        object_rows.append(
            {
                "object": item.get("object") or OBJECT_UNALLOCATED,
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": float(item.get("total_quantity") or 0),
                "revenue_ge": float(item.get("revenue_ge") or 0),
                "cost_ge": float(item.get("cost_ge") or 0),
                "profit_ge": float(item.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(item.get("revenue_ge") or 0, item.get("profit_ge") or 0)
                ),
                "distinct_category_count": len(item.get("category_keys") or set()),
                "distinct_product_count": len(item.get("product_keys") or set()),
                "distinct_month_count": len(item.get("month_keys") or set()),
                "date_range": {
                    "min": _iso_to_yyyymmdd(item.get("min_date_iso")),
                    "max": _iso_to_yyyymmdd(item.get("max_date_iso")),
                },
            }
        )
    bundle["by_object"] = sorted(
        object_rows,
        key=lambda value: (
            -float(value.get("revenue_ge") or 0),
            -float(value.get("profit_ge") or 0),
            str(value.get("object") or ""),
        ),
    )

    category_rows = []
    for item in master_category_stats.values():
        object_breakdown = [
            {
                "object": obj.get("object"),
                "row_count": int(obj.get("row_count") or 0),
                "total_quantity": float(obj.get("total_quantity") or 0),
                "revenue_ge": float(obj.get("revenue_ge") or 0),
                "cost_ge": float(obj.get("cost_ge") or 0),
                "profit_ge": float(obj.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(obj.get("revenue_ge") or 0, obj.get("profit_ge") or 0)
                ),
            }
            for obj in sorted(
                (item.get("object_totals") or {}).values(),
                key=lambda value: (
                    -float(value.get("revenue_ge") or 0),
                    -float(value.get("profit_ge") or 0),
                    str(value.get("object") or ""),
                ),
            )
        ]
        category_rows.append(
            {
                "category": item.get("category") or "უცნობი კატეგორია",
                "normalized_category": item.get("normalized_category") or None,
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": float(item.get("total_quantity") or 0),
                "revenue_ge": float(item.get("revenue_ge") or 0),
                "cost_ge": float(item.get("cost_ge") or 0),
                "profit_ge": float(item.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(item.get("revenue_ge") or 0, item.get("profit_ge") or 0)
                ),
                "distinct_product_count": len(item.get("product_keys") or set()),
                "distinct_month_count": len(item.get("month_keys") or set()),
                "date_range": {
                    "min": _iso_to_yyyymmdd(item.get("min_date_iso")),
                    "max": _iso_to_yyyymmdd(item.get("max_date_iso")),
                },
                "object_breakdown": object_breakdown,
            }
        )
    category_rows = sorted(
        category_rows,
        key=lambda value: (
            -float(value.get("revenue_ge") or 0),
            -float(value.get("profit_ge") or 0),
            str(value.get("category") or ""),
        ),
    )
    bundle["category_total_count"] = len(category_rows)
    bundle["categories_truncated"] = len(category_rows) > RETAIL_SALES_CATEGORY_LIMIT
    bundle["by_category"] = category_rows[:RETAIL_SALES_CATEGORY_LIMIT]

    category_display_names = {
        key: entry.get("category") for key, entry in master_category_stats.items()
    }
    bundle["by_category_by_month"] = _build_by_category_by_month_rows(
        master_category_month_stats, category_display_names
    )
    bundle["by_object_by_month"] = _build_by_object_by_month_rows(
        master_object_month_stats
    )

    product_rows = []
    for item in master_product_stats.values():
        object_breakdown = [
            {
                "object": obj.get("object"),
                "row_count": int(obj.get("row_count") or 0),
                "total_quantity": float(obj.get("total_quantity") or 0),
                "revenue_ge": float(obj.get("revenue_ge") or 0),
                "cost_ge": float(obj.get("cost_ge") or 0),
                "profit_ge": float(obj.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(obj.get("revenue_ge") or 0, obj.get("profit_ge") or 0)
                ),
            }
            for obj in sorted(
                (item.get("object_totals") or {}).values(),
                key=lambda value: (
                    -float(value.get("revenue_ge") or 0),
                    -float(value.get("profit_ge") or 0),
                    str(value.get("object") or ""),
                ),
            )
        ]
        product_rows.append(
            {
                "product_code": item.get("product_code") or "",
                "barcode": item.get("barcode") or "",
                "product_name": item.get("product_name") or "უცნობი პროდუქტი",
                "unit": item.get("unit") or "",
                "category": item.get("category") or "უცნობი კატეგორია",
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": float(item.get("total_quantity") or 0),
                "revenue_ge": float(item.get("revenue_ge") or 0),
                "cost_ge": float(item.get("cost_ge") or 0),
                "profit_ge": float(item.get("profit_ge") or 0),
                "gross_margin_pct": float(
                    _margin_pct(item.get("revenue_ge") or 0, item.get("profit_ge") or 0)
                ),
                "distinct_object_count": len(item.get("object_totals") or {}),
                "distinct_month_count": len(item.get("month_keys") or set()),
                "date_range": {
                    "min": _iso_to_yyyymmdd(item.get("min_date_iso")),
                    "max": _iso_to_yyyymmdd(item.get("max_date_iso")),
                },
                "object_breakdown": object_breakdown,
            }
        )
    product_rows = sorted(
        product_rows,
        key=lambda value: (
            -float(value.get("revenue_ge") or 0),
            -float(value.get("profit_ge") or 0),
            str(value.get("product_name") or ""),
            str(value.get("product_code") or ""),
        ),
    )
    bundle["products_total_count"] = len(product_rows)
    bundle["products_truncated"] = len(product_rows) > RETAIL_SALES_PRODUCT_LIMIT
    bundle["by_product"] = product_rows[:RETAIL_SALES_PRODUCT_LIMIT]

    bundle["top_objects_by_profit"] = sorted(
        bundle["by_object"],
        key=lambda value: (
            -float(value.get("profit_ge") or 0),
            -float(value.get("revenue_ge") or 0),
            str(value.get("object") or ""),
        ),
    )[:RETAIL_SALES_TOP_LIMIT]
    bundle["top_categories_by_profit"] = sorted(
        category_rows,
        key=lambda value: (
            -float(value.get("profit_ge") or 0),
            -float(value.get("revenue_ge") or 0),
            str(value.get("category") or ""),
        ),
    )[:RETAIL_SALES_TOP_LIMIT]
    bundle["top_products_by_revenue"] = product_rows[:RETAIL_SALES_TOP_LIMIT]
    bundle["top_products_by_profit"] = sorted(
        product_rows,
        key=lambda value: (
            -float(value.get("profit_ge") or 0),
            -float(value.get("revenue_ge") or 0),
            str(value.get("product_name") or ""),
            str(value.get("product_code") or ""),
        ),
    )[:RETAIL_SALES_TOP_LIMIT]

    def _preview_sort_key(row):
        date_str = row.get("date") or ""
        ts = 0.0
        if date_str:
            try:
                ts = pd.Timestamp(date_str).timestamp()
            except Exception:
                ts = float("-inf")
        else:
            ts = float("-inf")
        return (ts, float(row.get("revenue_ge") or 0), str(row.get("product_name") or ""))

    preview_candidates.sort(key=_preview_sort_key, reverse=True)
    bundle["rows_preview"] = preview_candidates[:RETAIL_SALES_ROWS_PREVIEW_LIMIT]
    return bundle
