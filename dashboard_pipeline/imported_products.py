"""
Imported products bundle: empty_imported_products_bundle, collect_imported_products_bundle.

Extracted from generate_dashboard_data.py lines 5746-6488.
"""
import os
import re
from collections import Counter, defaultdict

import pandas as pd

from dashboard_pipeline.constants import (
    IMPORTED_PRODUCTS_PRODUCTS_LIMIT,
    IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT,
    IMPORTED_PRODUCTS_READ_ERROR_LIMIT,
    IMPORTED_PRODUCTS_ROWS_PREVIEW_LIMIT,
    IMPORTED_PRODUCTS_SHEET_NAME,
    IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT,
    IMPORTED_PRODUCTS_TOP_LIMIT,
    IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT,
    IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT,
    _month_sort_key,
    _parse_rs_datetime,
    _safe_text,
)
from dashboard_pipeline.date_filters import serialize_period_filter
from dashboard_pipeline.file_utils import (
    _read_imported_products_file,
    list_imported_product_files,
)
from dashboard_pipeline.supplier_matching import (
    _build_waybill_reference_index,
    _extract_tax_ids_from_text,
    _normalize_waybill_ref,
    normalize_name,
)


# ---------------------------------------------------------------------------
# Destination resolver — turns RS waybill "ტრანსპორტირების დასრულება" free
# text into a canonical store object. Iterates variant strings by length
# descending so the more-specific match wins (avoids false ოზურგეთი match
# on "ოზურგეთი სოფ. გაღმა დვაბზუ" which contains both keywords).
# ---------------------------------------------------------------------------

def _build_destination_lookup(object_mapping):
    """Return a list of (variant_text, target_object) sorted longest first.

    ``object_mapping`` is the parsed `Financial_Analysis/object_mapping.json`
    blob — uses the ``rs_location_to_object`` section. Variants are matched
    case-sensitively against the destination text. The returned list is the
    pre-sorted lookup table the row loop reuses for every imported row.
    """
    rs_map = (object_mapping or {}).get("rs_location_to_object") or {}
    pairs = []
    for obj, variants in rs_map.items():
        if not obj:
            continue
        for variant in variants or []:
            v = (variant or "").strip()
            if v:
                pairs.append((len(v), v, str(obj)))
    pairs.sort(reverse=True)  # longest variant first → most-specific wins
    return [(v, obj) for _, v, obj in pairs]


def _resolve_destination_object(text, lookup_pairs, default_object):
    """Return the canonical object name for an imported destination string.

    Falls back to ``default_object`` when no variant matches. Empty / None
    text also returns the default — keeps the caller arithmetic simple.
    """
    if not text:
        return default_object
    blob = str(text)
    for variant, obj in lookup_pairs:
        if variant in blob:
            return obj
    return default_object


# ---------------------------------------------------------------------------
# empty_imported_products_bundle
# ---------------------------------------------------------------------------

def empty_imported_products_bundle(period_filter=None):
    return {
        "label_ka": "შემოტანილი პროდუქცია (reference)",
        "notes_ka": (
            "Reference/product-line წყარო imported-products export-იდან. CSV არის preferred source, "
            "legacy Excel reader fallback-ად რჩება. ეს ბლოკი არ ერთვება supplier debt-ში, "
            "RS truth totals-ში, bank reconciliation-ში და არსებულ AP ლოგიკაში. "
            "ფაილი, რომელსაც ზუსტად Excel-ის მაქსიმალური რიგების რაოდენობა (1,048,576) აქვს, "
            "შესაძლოა truncate/export limit იყოს — სრულობა გარანტირებული არ არის."
        ),
        "source_glob": "Financial_Analysis/შემოტანილი პროდუქცია/*.csv (preferred), legacy fallback: *.xls / *.xlsx",
        "source_format": None,
        "sheet_name": None,
        "date_basis_ka": (
            "თვე/პერიოდი ითვლება ჯერ `გააქტიურების თარიღი`-ით, "
            "fallback — `ტრანსპორტირების დაწყების თარიღი`."
        ),
        "amount_basis_ka": "`საქონლის ფასი` — თანხა, `რაოდ.` — რაოდენობა.",
        "files_found_count": 0,
        "files_read_count": 0,
        "files_error_count": 0,
        "files": [],
        "read_errors": [],
        "overall": {
            "row_count": 0,
            "total_quantity": 0.0,
            "total_amount_ge": 0.0,
            "distinct_waybill_count": 0,
            "distinct_supplier_count": 0,
            "distinct_product_count": 0,
            "date_range": {"min": None, "max": None},
        },
        "truncation_threshold_rows": IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT,
        "truncation_suspected_any": False,
        "truncation_suspected_file_count": 0,
        "truncation_suspected_files": [],
        "by_status": [],
        "by_month": [],
        "supplier_top_products_limit": IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT,
        "product_top_suppliers_limit": IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT,
        "products_limit": IMPORTED_PRODUCTS_PRODUCTS_LIMIT,
        "top_supplier_product_pairs_limit": IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT,
        "products_total_count": 0,
        "products_truncated": False,
        "top_supplier_product_pairs_total_count": 0,
        "top_supplier_product_pairs_truncated": False,
        "product_concentration_metric": "top_supplier_share_pct",
        "product_concentration_metric_ka": (
            "top_supplier_share_pct = ამ პროდუქტზე ყველაზე დიდი supplier-ის თანხა / "
            "ამ პროდუქტის ჯამური თანხა * 100"
        ),
        "suppliers": [],
        "products": [],
        "top_suppliers_by_amount": [],
        "top_products_by_amount": [],
        "top_supplier_product_pairs": [],
        "rows_preview": [],
        "period_meta": serialize_period_filter(period_filter),
        "rs_waybill_crosscheck": {
            "enabled": False,
            "matched_waybill_count": 0,
            "unmatched_waybill_count": 0,
            "match_rate_pct": 0.0,
            "matched_waybill_preview": [],
            "unmatched_waybill_preview": [],
        },
    }


# ---------------------------------------------------------------------------
# collect_imported_products_bundle
# ---------------------------------------------------------------------------

def collect_imported_products_bundle(
    rs_files=None, period_filter=None, known_rs_refs=None,
    object_mapping=None,
):
    files = list_imported_product_files()
    bundle = empty_imported_products_bundle(period_filter=period_filter)
    bundle["files_found_count"] = len(files)
    if not files:
        return bundle

    # Pre-compute destination → object lookup once per run. None mapping
    # gracefully degrades to "გაუნაწილებელი" for every row, so the
    # downstream object_breakdown lists stay populated even if the caller
    # forgot to pass mapping.
    _dest_lookup = _build_destination_lookup(object_mapping)
    _dest_default = (object_mapping or {}).get("default_object") or "გაუნაწილებელი"
    file_exts = {os.path.splitext(path)[1].lower() for path in files}
    if file_exts == {".csv"}:
        bundle["source_format"] = "csv"
        bundle["source_glob"] = "Financial_Analysis/შემოტანილი პროდუქცია/*.csv"
        bundle["sheet_name"] = None
    else:
        bundle["source_format"] = "excel"
        bundle["source_glob"] = "Financial_Analysis/შემოტანილი პროდუქცია/*.xls / *.xlsx"
        bundle["sheet_name"] = IMPORTED_PRODUCTS_SHEET_NAME

    required_summary_cols = [
        "საქონლის კოდი",
        "საქონლის დასახელება",
        "რაოდ.",
        "საქონლის ფასი",
        "ზედნადების ნომერი",
        "სტატუსი",
        "გამყიდველი",
        "გააქტიურების თარიღი",
        "ტრანსპორტირების დაწყების თარიღი",
    ]

    def _coerce_float(value):
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            return 0.0
        return float(num)

    def _clean_text(value, fallback=""):
        text = _safe_text(value).strip()
        return text if text else fallback

    def _pick_date(row):
        dt = _parse_rs_datetime(row.get("გააქტიურების თარიღი"))
        if pd.isna(dt):
            dt = _parse_rs_datetime(row.get("ტრანსპორტირების დაწყების თარიღი"))
        return dt

    def _fmt_date(dt):
        if dt is None or pd.isna(dt):
            return None
        return pd.Timestamp(dt).strftime("%Y-%m-%d")

    def _clean_supplier_display(value):
        text = _safe_text(value).strip()
        if not text:
            return ""
        cleaned = text
        for tid in _extract_tax_ids_from_text(text):
            cleaned = re.sub(r"\(?\s*" + re.escape(tid) + r"\s*\)?", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -\u2013,")
        return cleaned or text

    def _normalize_supplier_key(value):
        cleaned = _clean_supplier_display(value)
        normalized = normalize_name(cleaned)
        if normalized:
            return normalized
        raw = _safe_text(value).strip()
        return normalize_name(raw) or raw.lower()

    def _update_entry_date_range(entry, dt):
        if dt is None or pd.isna(dt):
            return
        if entry.get("min_date") is None or pd.isna(entry.get("min_date")) or dt < entry["min_date"]:
            entry["min_date"] = dt
        if entry.get("max_date") is None or pd.isna(entry.get("max_date")) or dt > entry["max_date"]:
            entry["max_date"] = dt

    def _merge_supplier_entries(target, source):
        target["row_count"] += int(source.get("row_count") or 0)
        target["total_ge"] += float(source.get("total_ge") or 0)
        target["quantity"] += float(source.get("quantity") or 0)
        target["waybill_refs"].update(source.get("waybill_refs") or set())
        target["month_keys"].update(source.get("month_keys") or set())
        target["tax_ids"].update(source.get("tax_ids") or set())
        target["display_names"].update(source.get("display_names") or Counter())
        _update_entry_date_range(target, source.get("min_date"))
        _update_entry_date_range(target, source.get("max_date"))
        # merge per-destination buckets (defaultdict on target)
        if "objects" not in target:
            target["objects"] = defaultdict(lambda: {"row_count": 0, "total_ge": 0.0, "quantity": 0.0})
        for obj_key, obj_stats in (source.get("objects") or {}).items():
            bucket = target["objects"][obj_key]
            bucket["row_count"] += int(obj_stats.get("row_count") or 0)
            bucket["total_ge"] += float(obj_stats.get("total_ge") or 0)
            bucket["quantity"] += float(obj_stats.get("quantity") or 0)
        for product_key, product_item in (source.get("products") or {}).items():
            target_product = target["products"].setdefault(
                product_key,
                {
                    "product_code": product_item.get("product_code") or "",
                    "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                    "unit": product_item.get("unit") or "",
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            if product_item.get("unit") and not target_product["unit"]:
                target_product["unit"] = product_item["unit"]
            if (
                product_item.get("product_name")
                and target_product["product_name"] == "უცნობი პროდუქცია"
            ):
                target_product["product_name"] = product_item["product_name"]
            target_product["row_count"] += int(product_item.get("row_count") or 0)
            target_product["total_ge"] += float(product_item.get("total_ge") or 0)
            target_product["quantity"] += float(product_item.get("quantity") or 0)
            target_product["waybill_refs"].update(product_item.get("waybill_refs") or set())
            target_product["month_keys"].update(product_item.get("month_keys") or set())
            _update_entry_date_range(target_product, product_item.get("min_date"))
            _update_entry_date_range(target_product, product_item.get("max_date"))

    def _pick_supplier_display(entry):
        display_names = entry.get("display_names") or Counter()
        if display_names:
            return sorted(
                display_names.items(),
                key=lambda item: (
                    -int(item[1]),
                    item[0] == "უცნობი მომწოდებელი",
                    -len(str(item[0])),
                    str(item[0]),
                ),
            )[0][0]
        fallback = _safe_text(entry.get("supplier")).strip()
        return fallback or "უცნობი მომწოდებელი"

    known_rs_refs = set(known_rs_refs or [])
    if not known_rs_refs and rs_files:
        known_rs_refs = set(
            (_build_waybill_reference_index(rs_files) or {}).get("known_refs") or set()
        )
    bundle["rs_waybill_crosscheck"]["enabled"] = bool(known_rs_refs)

    all_dates = []
    imported_waybill_refs = set()
    preview_candidates = []
    read_error_count = 0
    total_rows_seen = 0
    matched_rows = 0
    excluded_unparseable_count = 0
    status_stats = defaultdict(lambda: {"row_count": 0, "total_ge": 0.0, "quantity": 0.0})
    month_stats = defaultdict(lambda: {"row_count": 0, "total_ge": 0.0, "quantity": 0.0})
    supplier_stats = {}
    product_stats = {}

    # ------- მონაცემთა deduplication ------
    # CSV ფაილები ხშირად გადაფარვით ფიქსირდება (მაგ. „2025.csv" და
    # „2026-01-02.csv" სადაც 2025 წლის ბოლო ჩანაწერებიც ფიგურირებს). pipeline-ს
    # თუ ეს არ აღმოვაჩენი, ერთი row 2-ჯერ ემატება ჯამში → ცრუ overpayment
    # მომწოდებელზე და ცრუ კონცენტრაცია მთლიან მონაცემთა ბაზაში. composite
    # key (waybill + product code/name + amount + quantity) საკმაოდ სანდოა
    # რათა ერთი ფიზიკური ხაზი მხოლოდ ერთხელ ითვლებოდეს.
    seen_row_keys = set()
    duplicate_rows_dropped = 0
    duplicate_amount_dropped = 0.0

    for f in files:
        file_name = os.path.basename(f)
        file_ext = os.path.splitext(file_name)[1].lower()
        try:
            df, source_format, sheet_name = _read_imported_products_file(f)
        except Exception as e:
            read_error_count += 1
            if len(bundle["read_errors"]) < IMPORTED_PRODUCTS_READ_ERROR_LIMIT:
                bundle["read_errors"].append(
                    {
                        "name": file_name,
                        "source_format": file_ext.lstrip(".") or "unknown",
                        "sheet_name": IMPORTED_PRODUCTS_SHEET_NAME
                        if file_ext in {".xls", ".xlsx"}
                        else None,
                        "error": str(e),
                    }
                )
            continue

        row_count = int(len(df.index))
        total_rows_seen += row_count
        truncation_suspected = row_count == IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT
        total_amount_ge = 0.0
        total_quantity = 0.0
        file_dates = []
        file_waybill_refs = set()
        file_suppliers = set()
        file_products = set()
        missing_columns = [c for c in required_summary_cols if c not in df.columns]
        matched_file_row_count = 0

        for _, row in df.iterrows():
            amount_ge = _coerce_float(row.get("საქონლის ფასი"))
            quantity = _coerce_float(row.get("რაოდ."))
            status = _clean_text(row.get("სტატუსი"), "უცნობი სტატუსი")
            supplier_name = _clean_text(row.get("გამყიდველი"), "უცნობი მომწოდებელი")
            supplier_display = _clean_supplier_display(supplier_name) or supplier_name
            supplier_tax_ids = _extract_tax_ids_from_text(supplier_name)
            supplier_tax_id = supplier_tax_ids[0] if len(supplier_tax_ids) == 1 else ""
            product_code = _clean_text(row.get("საქონლის კოდი"))
            product_name = _clean_text(
                row.get("საქონლის დასახელება"),
                product_code or "უცნობი პროდუქცია",
            )
            unit = _clean_text(row.get("ზომის ერთეული"))
            waybill_number = _clean_text(row.get("ზედნადების ნომერი"))
            waybill_ref = _normalize_waybill_ref(waybill_number)
            destination_text = _clean_text(row.get("ტრანსპორტირების დასრულება"))
            destination_object = _resolve_destination_object(
                destination_text, _dest_lookup, _dest_default
            )
            dt = _pick_date(row)
            if dt is not None and not pd.isna(dt):
                dt = pd.Timestamp(dt)
            if period_filter and bool(period_filter.get("applied")):
                if dt is None or pd.isna(dt):
                    excluded_unparseable_count += 1
                    continue
                if dt < period_filter["from_ts"] or dt > period_filter["to_ts"]:
                    continue

            # dedupe by composite key — same physical row across overlapping files
            row_key = (
                waybill_ref or "",
                product_code or "",
                product_name or "",
                round(amount_ge, 2),
                round(quantity, 4),
            )
            if row_key in seen_row_keys:
                duplicate_rows_dropped += 1
                duplicate_amount_dropped += amount_ge
                continue
            seen_row_keys.add(row_key)

            matched_rows += 1
            matched_file_row_count += 1
            month_key = dt.strftime("%Y-%m") if not pd.isna(dt) else "უცნობი თვე"
            normalized_supplier = _normalize_supplier_key(supplier_name)
            supplier_key = (
                f"tax_id:{supplier_tax_id}"
                if supplier_tax_id
                else f"name:{normalized_supplier or supplier_name.lower()}"
            )
            product_name_key = normalize_name(product_name) or product_name.lower()
            product_key = f"{product_code}||{product_name_key}"

            total_amount_ge += amount_ge
            total_quantity += quantity
            status_stats[status]["row_count"] += 1
            status_stats[status]["total_ge"] += amount_ge
            status_stats[status]["quantity"] += quantity
            month_stats[month_key]["row_count"] += 1
            month_stats[month_key]["total_ge"] += amount_ge
            month_stats[month_key]["quantity"] += quantity

            supplier_entry = supplier_stats.setdefault(
                supplier_key,
                {
                    "supplier": supplier_display,
                    "normalized_supplier": normalized_supplier,
                    "tax_id": supplier_tax_id,
                    "tax_ids": set([supplier_tax_id]) if supplier_tax_id else set(),
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                    "display_names": Counter(),
                    "products": {},
                    "objects": defaultdict(lambda: {"row_count": 0, "total_ge": 0.0, "quantity": 0.0}),
                },
            )
            if supplier_display and supplier_entry["supplier"] == "უცნობი მომწოდებელი":
                supplier_entry["supplier"] = supplier_display
            if normalized_supplier and not supplier_entry.get("normalized_supplier"):
                supplier_entry["normalized_supplier"] = normalized_supplier
            if supplier_tax_id and not supplier_entry.get("tax_id"):
                supplier_entry["tax_id"] = supplier_tax_id
            supplier_entry["row_count"] += 1
            supplier_entry["total_ge"] += amount_ge
            supplier_entry["quantity"] += quantity
            if supplier_display:
                supplier_entry["display_names"][supplier_display] += 1
            if supplier_tax_id:
                supplier_entry["tax_ids"].add(supplier_tax_id)
            if month_key != "უცნობი თვე":
                supplier_entry["month_keys"].add(month_key)
            _update_entry_date_range(supplier_entry, dt)
            obj_bucket = supplier_entry["objects"][destination_object]
            obj_bucket["row_count"] += 1
            obj_bucket["total_ge"] += amount_ge
            obj_bucket["quantity"] += quantity

            product_entry = product_stats.setdefault(
                product_key,
                {
                    "product_code": product_code,
                    "product_name": product_name,
                    "unit": unit,
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                },
            )
            if unit and not product_entry["unit"]:
                product_entry["unit"] = unit
            if product_name and product_entry["product_name"] == "უცნობი პროდუქცია":
                product_entry["product_name"] = product_name
            product_entry["row_count"] += 1
            product_entry["total_ge"] += amount_ge
            product_entry["quantity"] += quantity

            supplier_product_entry = supplier_entry["products"].setdefault(
                product_key,
                {
                    "product_code": product_code,
                    "product_name": product_name,
                    "unit": unit,
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                },
            )
            if unit and not supplier_product_entry["unit"]:
                supplier_product_entry["unit"] = unit
            if (
                product_name
                and supplier_product_entry["product_name"] == "უცნობი პროდუქცია"
            ):
                supplier_product_entry["product_name"] = product_name
            supplier_product_entry["row_count"] += 1
            supplier_product_entry["total_ge"] += amount_ge
            supplier_product_entry["quantity"] += quantity
            if month_key != "უცნობი თვე":
                supplier_product_entry["month_keys"].add(month_key)
            _update_entry_date_range(supplier_product_entry, dt)

            if waybill_ref:
                imported_waybill_refs.add(waybill_ref)
                file_waybill_refs.add(waybill_ref)
                supplier_entry["waybill_refs"].add(waybill_ref)
                product_entry["waybill_refs"].add(waybill_ref)
                supplier_product_entry["waybill_refs"].add(waybill_ref)
            if supplier_name and supplier_name != "უცნობი მომწოდებელი":
                file_suppliers.add(supplier_key)
            if product_code or product_name:
                file_products.add(product_key)
            if not pd.isna(dt):
                file_dates.append(dt)
                all_dates.append(dt)

            preview_candidates.append(
                {
                    "_sort_date": pd.Timestamp(dt).timestamp() if not pd.isna(dt) else float("-inf"),
                    "_sort_amount": amount_ge,
                    "file_name": file_name,
                    "activation_date": _fmt_date(
                        _parse_rs_datetime(row.get("გააქტიურების თარიღი"))
                    ),
                    "transport_start_date": _fmt_date(
                        _parse_rs_datetime(row.get("ტრანსპორტირების დაწყების თარიღი"))
                    ),
                    "waybill_number": waybill_number,
                    "status": status,
                    "buyer": _clean_text(row.get("მყიდველი")),
                    "supplier": supplier_name,
                    "product_code": product_code,
                    "product_name": product_name,
                    "unit": unit,
                    "quantity": quantity,
                    "amount_ge": amount_ge,
                }
            )

        file_summary = {
            "name": file_name,
            "source_format": source_format,
            "sheet_name": sheet_name,
            "row_count": matched_file_row_count,
            "truncation_suspected": truncation_suspected,
            "date_range": {
                "min": _fmt_date(min(file_dates)) if file_dates else None,
                "max": _fmt_date(max(file_dates)) if file_dates else None,
            },
            "total_amount_ge": float(total_amount_ge),
            "total_quantity": float(total_quantity),
            "distinct_waybill_count": len(file_waybill_refs),
            "distinct_supplier_count": len(file_suppliers),
            "distinct_product_count": len(file_products),
            "missing_columns": missing_columns,
        }
        if known_rs_refs:
            matched_refs = file_waybill_refs & known_rs_refs
            unmatched_refs = file_waybill_refs - known_rs_refs
            file_summary["rs_waybill_crosscheck"] = {
                "matched_waybill_count": len(matched_refs),
                "unmatched_waybill_count": len(unmatched_refs),
            }
        bundle["files"].append(file_summary)

    bundle["files_read_count"] = len(bundle["files"])
    bundle["files_error_count"] = int(read_error_count)
    bundle["truncation_suspected_files"] = [
        item["name"] for item in bundle["files"] if item.get("truncation_suspected")
    ]
    bundle["truncation_suspected_file_count"] = len(bundle["truncation_suspected_files"])
    bundle["truncation_suspected_any"] = bundle["truncation_suspected_file_count"] > 0
    supplier_keys_by_normalized_tax_id = defaultdict(set)
    for supplier_key, item in supplier_stats.items():
        if item.get("tax_id") and item.get("normalized_supplier"):
            supplier_keys_by_normalized_tax_id[item["normalized_supplier"]].add(supplier_key)

    merged_supplier_keys = set()
    for supplier_key, item in list(supplier_stats.items()):
        if supplier_key in merged_supplier_keys:
            continue
        if item.get("tax_id"):
            continue
        normalized_supplier = item.get("normalized_supplier") or ""
        if not normalized_supplier:
            continue
        candidate_keys = supplier_keys_by_normalized_tax_id.get(normalized_supplier) or set()
        if len(candidate_keys) != 1:
            continue
        target_key = next(iter(candidate_keys))
        if target_key == supplier_key:
            continue
        _merge_supplier_entries(supplier_stats[target_key], item)
        merged_supplier_keys.add(supplier_key)

    supplier_entries_with_keys = [
        (key, item) for key, item in supplier_stats.items() if key not in merged_supplier_keys
    ]
    supplier_entries = [item for _, item in supplier_entries_with_keys]
    bundle["overall"] = {
        "row_count": int(sum(item.get("row_count") or 0 for item in bundle["files"])),
        "total_quantity": float(sum(item.get("total_quantity") or 0 for item in bundle["files"])),
        "total_amount_ge": float(sum(item.get("total_amount_ge") or 0 for item in bundle["files"])),
        "distinct_waybill_count": len(imported_waybill_refs),
        "distinct_supplier_count": len(supplier_entries),
        "distinct_product_count": len(product_stats),
        "date_range": {
            "min": _fmt_date(min(all_dates)) if all_dates else None,
            "max": _fmt_date(max(all_dates)) if all_dates else None,
        },
        "duplicate_rows_dropped": int(duplicate_rows_dropped),
        "duplicate_amount_dropped_ge": round(float(duplicate_amount_dropped), 2),
    }

    bundle["by_status"] = [
        {
            "status": status,
            "row_count": int(stats["row_count"]),
            "total_ge": float(stats["total_ge"]),
            "quantity": float(stats["quantity"]),
        }
        for status, stats in sorted(
            status_stats.items(),
            key=lambda item: (-float(item[1]["total_ge"]), item[0]),
        )
    ]
    bundle["by_month"] = [
        {
            "month": month,
            "row_count": int(stats["row_count"]),
            "total_ge": float(stats["total_ge"]),
            "quantity": float(stats["quantity"]),
        }
        for month, stats in sorted(month_stats.items(), key=lambda item: _month_sort_key(item[0]))
    ]
    bundle["suppliers"] = [
        {
            "supplier": _pick_supplier_display(item),
            "tax_id": item.get("tax_id") or None,
            "tax_id_source": "supplier_text" if item.get("tax_id") else None,
            "normalized_supplier": item.get("normalized_supplier") or None,
            "row_count": int(item["row_count"]),
            "distinct_waybill_count": len(item["waybill_refs"]),
            "distinct_product_count": len(item["products"]),
            "distinct_month_count": len(item["month_keys"]),
            "total_quantity": float(item["quantity"]),
            "total_amount_ge": float(item["total_ge"]),
            "date_range": {
                "min": _fmt_date(item.get("min_date")),
                "max": _fmt_date(item.get("max_date")),
            },
            "object_breakdown": [
                {
                    "object": obj_key,
                    "row_count": int(obj_stats["row_count"]),
                    "total_amount_ge": round(float(obj_stats["total_ge"]), 2),
                    "total_quantity": float(obj_stats["quantity"]),
                }
                for obj_key, obj_stats in sorted(
                    (item.get("objects") or {}).items(),
                    key=lambda x: -float(x[1]["total_ge"]),
                )
            ],
            "top_products": [
                {
                    "product_code": product_item["product_code"],
                    "product_name": product_item["product_name"],
                    "unit": product_item["unit"],
                    "row_count": int(product_item["row_count"]),
                    "distinct_waybill_count": len(product_item["waybill_refs"]),
                    "total_quantity": float(product_item["quantity"]),
                    "total_amount_ge": float(product_item["total_ge"]),
                }
                for product_item in sorted(
                    item["products"].values(),
                    key=lambda value: (
                        -float(value["total_ge"]),
                        -int(value["row_count"]),
                        str(value["product_name"]),
                        str(value["product_code"]),
                    ),
                )[:IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT]
            ],
        }
        for item in sorted(
            supplier_entries,
            key=lambda value: (
                -float(value["total_ge"]),
                -int(value["row_count"]),
                _pick_supplier_display(value),
            ),
        )
    ]
    product_rollup = {}
    supplier_product_pairs = []
    for supplier_key, supplier_item in supplier_entries_with_keys:
        supplier_display = _pick_supplier_display(supplier_item)
        supplier_tax_id = supplier_item.get("tax_id") or None
        for product_key, product_item in (supplier_item.get("products") or {}).items():
            product_rollup_entry = product_rollup.setdefault(
                product_key,
                {
                    "product_code": product_item.get("product_code") or "",
                    "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                    "unit": product_item.get("unit") or "",
                    "row_count": 0,
                    "total_ge": 0.0,
                    "quantity": 0.0,
                    "waybill_refs": set(),
                    "month_keys": set(),
                    "min_date": None,
                    "max_date": None,
                    "suppliers": {},
                },
            )
            if product_item.get("unit") and not product_rollup_entry["unit"]:
                product_rollup_entry["unit"] = product_item["unit"]
            if (
                product_item.get("product_name")
                and product_rollup_entry["product_name"] == "უცნობი პროდუქცია"
            ):
                product_rollup_entry["product_name"] = product_item["product_name"]
            product_rollup_entry["row_count"] += int(product_item.get("row_count") or 0)
            product_rollup_entry["total_ge"] += float(product_item.get("total_ge") or 0)
            product_rollup_entry["quantity"] += float(product_item.get("quantity") or 0)
            product_rollup_entry["waybill_refs"].update(product_item.get("waybill_refs") or set())
            product_rollup_entry["month_keys"].update(product_item.get("month_keys") or set())
            _update_entry_date_range(product_rollup_entry, product_item.get("min_date"))
            _update_entry_date_range(product_rollup_entry, product_item.get("max_date"))

            product_rollup_entry["suppliers"][supplier_key] = {
                "supplier": supplier_display,
                "tax_id": supplier_tax_id,
                "row_count": int(product_item.get("row_count") or 0),
                "distinct_waybill_count": len(product_item.get("waybill_refs") or set()),
                "total_quantity": float(product_item.get("quantity") or 0),
                "total_amount_ge": float(product_item.get("total_ge") or 0),
            }
            supplier_product_pairs.append(
                {
                    "supplier": supplier_display,
                    "tax_id": supplier_tax_id,
                    "product_code": product_item.get("product_code") or "",
                    "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                    "unit": product_item.get("unit") or "",
                    "row_count": int(product_item.get("row_count") or 0),
                    "distinct_waybill_count": len(product_item.get("waybill_refs") or set()),
                    "distinct_month_count": len(product_item.get("month_keys") or set()),
                    "total_quantity": float(product_item.get("quantity") or 0),
                    "total_amount_ge": float(product_item.get("total_ge") or 0),
                    "date_range": {
                        "min": _fmt_date(product_item.get("min_date")),
                        "max": _fmt_date(product_item.get("max_date")),
                    },
                }
            )

    sorted_product_rollup = sorted(
        product_rollup.values(),
        key=lambda value: (
            -float(value["total_ge"]),
            -int(value["row_count"]),
            str(value["product_name"]),
            str(value["product_code"]),
        ),
    )
    bundle["products_total_count"] = len(sorted_product_rollup)
    bundle["products_truncated"] = len(sorted_product_rollup) > IMPORTED_PRODUCTS_PRODUCTS_LIMIT
    bundle["products"] = []
    for product_item in sorted_product_rollup[:IMPORTED_PRODUCTS_PRODUCTS_LIMIT]:
        sorted_top_suppliers = sorted(
            product_item["suppliers"].values(),
            key=lambda value: (
                -float(value["total_amount_ge"]),
                -int(value["row_count"]),
                str(value["supplier"]),
            ),
        )
        top_supplier_amount = (
            float(sorted_top_suppliers[0]["total_amount_ge"])
            if sorted_top_suppliers
            else 0.0
        )
        product_total_amount = float(product_item.get("total_ge") or 0)
        top_supplier_share_pct = (
            float((top_supplier_amount / product_total_amount) * 100.0)
            if product_total_amount
            else 0.0
        )
        bundle["products"].append(
            {
                "product_code": product_item.get("product_code") or "",
                "product_name": product_item.get("product_name") or "უცნობი პროდუქცია",
                "unit": product_item.get("unit") or "",
                "row_count": int(product_item.get("row_count") or 0),
                "distinct_supplier_count": len(product_item.get("suppliers") or {}),
                "distinct_waybill_count": len(product_item.get("waybill_refs") or set()),
                "distinct_month_count": len(product_item.get("month_keys") or set()),
                "total_quantity": float(product_item.get("quantity") or 0),
                "total_amount_ge": float(product_total_amount),
                "top_supplier_share_pct": float(top_supplier_share_pct),
                "date_range": {
                    "min": _fmt_date(product_item.get("min_date")),
                    "max": _fmt_date(product_item.get("max_date")),
                },
                "top_suppliers": sorted_top_suppliers[
                    :IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT
                ],
            }
        )

    sorted_supplier_product_pairs = sorted(
        supplier_product_pairs,
        key=lambda value: (
            -float(value["total_amount_ge"]),
            -int(value["row_count"]),
            str(value["supplier"]),
            str(value["product_name"]),
            str(value["product_code"]),
        ),
    )
    bundle["top_supplier_product_pairs_total_count"] = len(sorted_supplier_product_pairs)
    bundle["top_supplier_product_pairs_truncated"] = (
        len(sorted_supplier_product_pairs)
        > IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT
    )
    bundle["top_supplier_product_pairs"] = sorted_supplier_product_pairs[
        :IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT
    ]
    bundle["top_suppliers_by_amount"] = [
        {
            "supplier": _pick_supplier_display(item),
            "row_count": int(item["row_count"]),
            "total_ge": float(item["total_ge"]),
            "quantity": float(item["quantity"]),
            "distinct_waybill_count": len(item["waybill_refs"]),
        }
        for item in sorted(
            supplier_entries,
            key=lambda value: (
                -float(value["total_ge"]),
                -int(value["row_count"]),
                _pick_supplier_display(value),
            ),
        )[:IMPORTED_PRODUCTS_TOP_LIMIT]
    ]
    bundle["top_products_by_amount"] = [
        {
            "product_code": item["product_code"],
            "product_name": item["product_name"],
            "unit": item["unit"],
            "row_count": int(item["row_count"]),
            "total_ge": float(item["total_ge"]),
            "quantity": float(item["quantity"]),
            "distinct_waybill_count": len(item["waybill_refs"]),
        }
        for item in sorted(
            product_stats.values(),
            key=lambda value: (
                -float(value["total_ge"]),
                -int(value["row_count"]),
                str(value["product_name"]),
                str(value["product_code"]),
            ),
        )[:IMPORTED_PRODUCTS_TOP_LIMIT]
    ]

    preview_candidates.sort(
        key=lambda item: (
            float(item["_sort_date"]),
            float(item["_sort_amount"]),
            str(item["product_name"]),
        ),
        reverse=True,
    )
    bundle["rows_preview"] = [
        {k: v for k, v in item.items() if not k.startswith("_sort_")}
        for item in preview_candidates[:IMPORTED_PRODUCTS_ROWS_PREVIEW_LIMIT]
    ]

    bundle["period_meta"] = serialize_period_filter(
        period_filter,
        total_rows_seen=total_rows_seen,
        matched_rows=matched_rows,
        excluded_unparseable_count=excluded_unparseable_count,
    )

    matched_refs = imported_waybill_refs & known_rs_refs
    unmatched_refs = imported_waybill_refs - known_rs_refs
    total_refs = len(imported_waybill_refs)
    match_rate_pct = float((len(matched_refs) / total_refs) * 100.0) if total_refs else 0.0
    bundle["rs_waybill_crosscheck"] = {
        "enabled": bool(known_rs_refs),
        "matched_waybill_count": len(matched_refs),
        "unmatched_waybill_count": len(unmatched_refs),
        "match_rate_pct": float(match_rate_pct),
        "matched_waybill_preview": sorted(matched_refs)[:20],
        "unmatched_waybill_preview": sorted(unmatched_refs)[:20],
    }
    return bundle
