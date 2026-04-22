"""
Retail sales bundle: empty_retail_sales_bundle, collect_retail_sales_bundle.

Extracted from generate_dashboard_data.py lines 5053-5743.
"""
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


# ---------------------------------------------------------------------------
# empty_retail_sales_bundle
# ---------------------------------------------------------------------------

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
        "top_objects_by_profit": [],
        "top_categories_by_profit": [],
        "top_products_by_revenue": [],
        "top_products_by_profit": [],
        "rows_preview": [],
        "period_meta": serialize_period_filter(period_filter),
    }


# ---------------------------------------------------------------------------
# collect_retail_sales_bundle
# ---------------------------------------------------------------------------

def collect_retail_sales_bundle(
    object_mapping=None, period_filter=None, source_file_stats=None
):
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

    def _fmt_date(dt):
        if dt is None or pd.isna(dt):
            return None
        return pd.Timestamp(dt).strftime("%Y-%m-%d")

    def _margin_pct(revenue, profit):
        revenue_val = float(revenue or 0)
        if revenue_val == 0:
            return 0.0
        return float((float(profit or 0) / revenue_val) * 100.0)

    def _object_from_path(path):
        parent = _normalize_for_match(os.path.basename(os.path.dirname(path)))
        if "ოზურგეთი" in parent:
            return OBJECT_OZURGETI
        if "დვაბზუ" in parent:
            return OBJECT_DVABZU
        return OBJECT_UNALLOCATED

    def _pick_object(row_value, fallback_object):
        detected = detect_object(
            "rs_waybill",
            rs_location=row_value,
            object_mapping=sales_object_mapping,
        )
        detected = str(detected or "").strip()
        if detected and detected not in {OBJECT_UNALLOCATED, OBJECT_COMMON}:
            return detected
        if fallback_object and fallback_object != OBJECT_UNALLOCATED:
            return fallback_object
        return detected or fallback_object or OBJECT_UNALLOCATED

    def _update_date_range(entry, dt):
        if dt is None or pd.isna(dt):
            return
        if entry.get("min_date") is None or pd.isna(entry.get("min_date")) or dt < entry["min_date"]:
            entry["min_date"] = dt
        if entry.get("max_date") is None or pd.isna(entry.get("max_date")) or dt > entry["max_date"]:
            entry["max_date"] = dt

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

    all_dates = []
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

        file_name = os.path.basename(f)
        fallback_object = _object_from_path(f)
        try:
            df = pd.read_excel(
                f,
                usecols=lambda col: str(col).strip() in RETAIL_SALES_READ_COLUMNS,
            )
        except Exception as exc:
            read_error_count += 1
            if len(bundle["read_errors"]) < RETAIL_SALES_READ_ERROR_LIMIT:
                bundle["read_errors"].append(
                    {
                        "name": file_name,
                        "relative_path": file_rel,
                        "error": str(exc),
                    }
                )
            continue

        if not isinstance(df, pd.DataFrame):
            continue
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        unnamed_cols = [c for c in df.columns if str(c).strip().startswith("Unnamed:")]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols, errors="ignore")

        source_row_count = int(len(df.index))
        total_rows_seen += source_row_count
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
        if period_filter and bool(period_filter.get("applied")):
            excluded_unparseable_count += int(parsed_dates.isna().sum())
            matched_mask = parsed_dates.notna() & (
                parsed_dates >= period_filter["from_ts"]
            ) & (parsed_dates <= period_filter["to_ts"])
            df = df.loc[matched_mask].copy()
            parsed_dates = parsed_dates.loc[matched_mask]
        file_dates = []
        file_revenue = 0.0
        file_cost = 0.0
        file_profit = 0.0
        file_quantity = 0.0
        file_objects = set()
        file_categories = set()
        file_products = set()
        file_profit_fallback_rows = 0
        matched_file_row_count = int(len(df.index))
        matched_rows += matched_file_row_count

        for row_index, row in df.iterrows():
            date_value = parsed_dates.get(row_index, pd.NaT)
            quantity = _coerce_float(row.get("რაოდენობა"))
            revenue_ge = _coerce_float(row.get("ფასი"))
            cost_ge = _coerce_float(row.get("თვითღირებულება"))
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
            product_code = _clean_text(row.get("კოდი"))
            barcode = _clean_text(row.get("შტრიხკოდი"))
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
            file_objects.add(object_label)
            file_categories.add(category_key)
            file_products.add(product_key)

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
            _update_date_range(object_entry, date_value)

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
            _update_date_range(category_entry, date_value)
            category_object_totals = category_entry["object_totals"].setdefault(
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
            category_object_totals["row_count"] += 1
            category_object_totals["total_quantity"] += quantity
            category_object_totals["revenue_ge"] += revenue_ge
            category_object_totals["cost_ge"] += cost_ge
            category_object_totals["profit_ge"] += profit_ge

            if month_key != "უცნობი თვე":
                cm_entry = category_month_stats[(category_key, month_key)]
                cm_entry["row_count"] += 1
                cm_entry["total_quantity"] += quantity
                cm_entry["revenue_ge"] += revenue_ge
                cm_entry["cost_ge"] += cost_ge
                cm_entry["profit_ge"] += profit_ge

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
            _update_date_range(product_entry, date_value)
            product_object_totals = product_entry["object_totals"].setdefault(
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
            product_object_totals["row_count"] += 1
            product_object_totals["total_quantity"] += quantity
            product_object_totals["revenue_ge"] += revenue_ge
            product_object_totals["cost_ge"] += cost_ge
            product_object_totals["profit_ge"] += profit_ge

            if not pd.isna(date_value):
                file_dates.append(date_value)
                all_dates.append(date_value)

            preview_candidates.append(
                {
                    "_sort_date": pd.Timestamp(date_value).timestamp()
                    if not pd.isna(date_value)
                    else float("-inf"),
                    "_sort_revenue": revenue_ge,
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

        bundle["files"].append(
            {
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
                "distinct_object_count": len(file_objects),
                "distinct_category_count": len(file_categories),
                "distinct_product_count": len(file_products),
                "object_from_folder": (
                    fallback_object if fallback_object != OBJECT_UNALLOCATED else None
                ),
                "date_range": {
                    "min": _fmt_date(min(file_dates)) if file_dates else None,
                    "max": _fmt_date(max(file_dates)) if file_dates else None,
                },
                "missing_columns": missing_columns,
            }
        )

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
        "distinct_object_count": len(object_stats),
        "distinct_category_count": len(category_stats),
        "distinct_product_count": len(product_stats),
        "date_range": {
            "min": _fmt_date(min(all_dates)) if all_dates else None,
            "max": _fmt_date(max(all_dates)) if all_dates else None,
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
        for month, stats in sorted(month_stats.items(), key=lambda item: _month_sort_key(item[0]))
    ]

    object_rows = []
    for item in object_stats.values():
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
                    "min": _fmt_date(item.get("min_date")),
                    "max": _fmt_date(item.get("max_date")),
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
    for item in category_stats.values():
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
                    "min": _fmt_date(item.get("min_date")),
                    "max": _fmt_date(item.get("max_date")),
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
        key: entry.get("category") for key, entry in category_stats.items()
    }
    bundle["by_category_by_month"] = _build_by_category_by_month_rows(
        category_month_stats, category_display_names
    )

    product_rows = []
    for item in product_stats.values():
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
                    "min": _fmt_date(item.get("min_date")),
                    "max": _fmt_date(item.get("max_date")),
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

    preview_candidates.sort(
        key=lambda item: (
            float(item.get("_sort_date") or float("-inf")),
            float(item.get("_sort_revenue") or 0),
            str(item.get("product_name") or ""),
        ),
        reverse=True,
    )
    bundle["rows_preview"] = [
        {
            k: v
            for k, v in item.items()
            if not str(k).startswith("_sort_")
        }
        for item in preview_candidates[:RETAIL_SALES_ROWS_PREVIEW_LIMIT]
    ]
    return bundle
