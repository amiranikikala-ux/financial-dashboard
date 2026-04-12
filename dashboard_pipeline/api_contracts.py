from __future__ import annotations

import re


FIELD_DEFAULTS = {
    "meta": {},
    "download_files": [],
    "download_zip_file": "",
    "suppliers": [],
    "waybills": [],
    "imported_products": {},
    "retail_sales": {},
    "pos_terminal_income": {},
    "tbc_expenses": {},
    "bog_expenses": {},
    "tbc_samurneo": {},
    "tax_flow": {},
    "tbc_foodmart_cashback": {},
    "bank_unmatched_analysis": {},
    "monthly_pnl": [],
    "supplier_aging": [],
    "aging_summary": {},
    "ap_monthly_trend": [],
    "financial_ratios": {},
    "forecast": {},
    "budget": {},
    "company_valuation": {},
    "executive_summary": {},
}

IMPORTED_PRODUCTS_SUMMARY_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT = 20
RETAIL_SALES_SUMMARY_CATEGORY_LIMIT = 200
RETAIL_SALES_SUMMARY_PRODUCT_LIMIT = 500
RETAIL_SALES_SUMMARY_MONTH_LIMIT = 24
WAYBILLS_MAX_RESPONSE_LIMIT = 5000
WAYBILL_ALLOWED_SORTS = {"amount_asc", "amount_desc", "date_asc", "date_desc"}

TAB_ALLOWLIST = {
    "suppliers": ["suppliers"],
    "waybills": ["waybills"],
    "analytics": ["suppliers"],
    "cashflow": [
        "pos_terminal_income",
        "tbc_expenses",
        "tbc_samurneo",
        "tax_flow",
        "tbc_foodmart_cashback",
        "bank_unmatched_analysis",
    ],
    "pnl": ["monthly_pnl", "tbc_expenses", "bog_expenses"],
    "working_capital": ["supplier_aging", "aging_summary", "ap_monthly_trend"],
    "ratios": ["financial_ratios"],
    "forecast": ["forecast", "monthly_pnl"],
    "budget": ["budget"],
    "valuation": ["company_valuation"],
    "executive": ["executive_summary"],
    "imported_products": ["imported_products"],
    "retail_sales": ["retail_sales"],
    "executive_export": [
        "monthly_pnl",
        "budget",
        "financial_ratios",
        "supplier_aging",
        "ap_monthly_trend",
        "forecast",
        "company_valuation",
        "executive_summary",
        "imported_products",
        "retail_sales",
    ],
}

TAB_RESPONSE_META = {
    "suppliers": {
        "trust_label": "audited",
        "trust_badge_ka": "აუდიტ-ბაზა",
        "scope_ka": "RS truth + strict bank reconciliation + manual journal.",
        "notes_ka": [
            "supplier debt იყენებს RS effective totals-ს.",
            "total_paid მოიცავს strict bank matches-ს და manual/off-bank journal-ს ცალკე breakdown-ით.",
        ],
    },
    "waybills": {
        "trust_label": "audited",
        "trust_badge_ka": "RS register",
        "scope_ka": "RS waybill register view.",
        "notes_ka": [
            "თუ limit/filter ჩართულია, ეკრანზე ჩანს partial list.",
        ],
    },
    "cashflow_summary": {
        "trust_label": "classified-bank",
        "trust_badge_ka": "კლასიფიცირებული ბანკი",
        "scope_ka": "BOG/TBC outgoing bank classification summary.",
        "notes_ka": [
            "ეს არ არის სრული double-entry bank statement audit.",
            "get_bank_payments ფოკუსირდება outgoing/debit supplier-side ხაზებზე.",
        ],
    },
    "cashflow_tbc_expenses_detail": {
        "trust_label": "classified-bank",
        "trust_badge_ka": "კლასიფიცირებული ბანკი",
        "scope_ka": "TBC expense category detail.",
        "notes_ka": [],
    },
    "cashflow_bank_unmatched_detail": {
        "trust_label": "classified-bank",
        "trust_badge_ka": "არამიბმული ბანკი",
        "scope_ka": "Bank unmatched classification detail.",
        "notes_ka": [],
    },
    "pnl_summary": {
        "trust_label": "derived",
        "trust_badge_ka": "Derived",
        "scope_ka": "POS income minus categorized expenses by month/object.",
        "notes_ka": [
            "P&L არის derived management view და არა statutory statement.",
        ],
    },
    "working_capital": {
        "trust_label": "derived",
        "trust_badge_ka": "Derived",
        "scope_ka": "RS purchases vs supplier paid totals and aging.",
        "notes_ka": [
            "payment breakdown გამოყოფს strict bank vs manual/off-bank journal თანხებს.",
        ],
    },
    "ratios": {
        "trust_label": "derived",
        "trust_badge_ka": "Derived",
        "scope_ka": "Ratios derived from P&L and AP views.",
        "notes_ka": [],
    },
    "forecast": {
        "trust_label": "forecast",
        "trust_badge_ka": "Forecast",
        "scope_ka": "SMA-based management forecast.",
        "notes_ka": [
            "Forecast არ არის audited result.",
        ],
    },
    "budget": {
        "trust_label": "plan-vs-actual",
        "trust_badge_ka": "Budget",
        "scope_ka": "Budget plan vs actual management view.",
        "notes_ka": [
            "Annual targets შეიძლება ნაწილობრივ auto-generated იყოს.",
        ],
    },
    "valuation": {
        "trust_label": "derived",
        "trust_badge_ka": "Valuation",
        "scope_ka": "Company valuation derived from sector benchmarks and forecast inputs.",
        "notes_ka": [
            "sector benchmarks არის indicative და არა precision-grade market data.",
        ],
    },
    "executive": {
        "trust_label": "management-summary",
        "trust_badge_ka": "Executive",
        "scope_ka": "High-level management summary over derived views.",
        "notes_ka": [],
    },
    "executive_export": {
        "trust_label": "management-summary",
        "trust_badge_ka": "Executive export",
        "scope_ka": "Export bundle for executive workbook.",
        "notes_ka": [],
    },
    "imported_products": {
        "trust_label": "reference-only",
        "trust_badge_ka": "Reference-only",
        "scope_ka": "Imported-products reference view for supplier/product analysis.",
        "notes_ka": [
            "supplier debt/AP და bank reconciliation totals-ში არ ერთვება.",
        ],
    },
    "imported_products_full": {
        "trust_label": "reference-only",
        "trust_badge_ka": "Reference-only",
        "scope_ka": "Full imported-products bundle.",
        "notes_ka": [],
    },
    "imported_products_supplier_detail": {
        "trust_label": "reference-only",
        "trust_badge_ka": "Reference-only",
        "scope_ka": "Imported-products supplier detail lookup.",
        "notes_ka": [],
    },
    "imported_products_product_detail": {
        "trust_label": "reference-only",
        "trust_badge_ka": "Reference-only",
        "scope_ka": "Imported-products product detail lookup.",
        "notes_ka": [],
    },
    "retail_sales": {
        "trust_label": "reference-only",
        "trust_badge_ka": "Retail source",
        "scope_ka": "Retail sales source summary (sell-through/revenue/cost/profit/margin).",
        "notes_ka": [
            "supplier debt/AP და bank reconciliation truth totals-ში არ ერთვება.",
            "duplicate-suspected file შეიძლება policy-ით იყოს გამორიცხული.",
        ],
    },
}

STATIC_RESPONSE_TABS = {
    "suppliers",
    "analytics",
    "cashflow_summary",
    "cashflow_tbc_expenses_detail",
    "cashflow_bank_unmatched_detail",
    "pnl_summary",
    "working_capital",
    "ratios",
    "forecast",
    "budget",
    "valuation",
    "executive",
    "executive_export",
    "imported_products",
    "retail_sales",
    "imported_products_full",
}

DYNAMIC_SOURCE_ARTIFACTS = {
    "waybills": "waybills_source",
    "imported_products_supplier_detail": "imported_products_source",
    "imported_products_product_detail": "imported_products_source",
}


def _base_response(cache):
    return {
        "meta": cache.get("meta", FIELD_DEFAULTS["meta"]),
        "download_files": cache.get("download_files", FIELD_DEFAULTS["download_files"]),
        "download_zip_file": cache.get(
            "download_zip_file", FIELD_DEFAULTS["download_zip_file"]
        ),
    }


def _clean_lookup_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_lookup_name(value):
    text = _clean_lookup_text(value)
    if text is None:
        return None
    text = text.lower().strip()
    text = re.sub(r'[\"\'„"«»\(\)\[\]]', "", text)
    text = re.sub(r"^(შპს|სს|ი/მ|ი\.მ|შ\.პ\.ს)\s*", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"-დღგ$", "", text).strip()
    return text or None


def _project_imported_products_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    summary = {
        "label_ka": bundle.get("label_ka"),
        "notes_ka": bundle.get("notes_ka"),
        "source_glob": bundle.get("source_glob"),
        "source_format": bundle.get("source_format"),
        "sheet_name": bundle.get("sheet_name"),
        "date_basis_ka": bundle.get("date_basis_ka"),
        "amount_basis_ka": bundle.get("amount_basis_ka"),
        "files_found_count": bundle.get("files_found_count", 0),
        "files_read_count": bundle.get("files_read_count", 0),
        "files_error_count": bundle.get("files_error_count", 0),
        "overall": dict(bundle.get("overall") or {}),
        "truncation_threshold_rows": bundle.get("truncation_threshold_rows"),
        "truncation_suspected_any": bool(bundle.get("truncation_suspected_any")),
        "truncation_suspected_file_count": bundle.get(
            "truncation_suspected_file_count", 0
        ),
        "supplier_top_products_limit": bundle.get("supplier_top_products_limit", 0),
        "by_status": [],
        "by_month": [],
        "suppliers": [],
        "products": [],
        "top_suppliers_by_amount": [],
        "top_products_by_amount": [],
        "top_supplier_product_pairs": [],
    }
    for item in bundle.get("by_status") or []:
        if isinstance(item, dict):
            summary["by_status"].append(
                {
                    "status": item.get("status"),
                    "row_count": item.get("row_count", 0),
                    "total_ge": item.get("total_ge", 0.0),
                }
            )
    for item in bundle.get("by_month") or []:
        if isinstance(item, dict):
            summary["by_month"].append(
                {
                    "month": item.get("month"),
                    "row_count": item.get("row_count", 0),
                    "total_ge": item.get("total_ge", 0.0),
                }
            )
    for item in bundle.get("top_suppliers_by_amount") or []:
        if isinstance(item, dict):
            summary["top_suppliers_by_amount"].append(
                {
                    "supplier": item.get("supplier"),
                    "row_count": item.get("row_count", 0),
                    "total_ge": item.get("total_ge", 0.0),
                    "distinct_waybill_count": item.get("distinct_waybill_count", 0),
                }
            )
    for item in bundle.get("top_products_by_amount") or []:
        if isinstance(item, dict):
            summary["top_products_by_amount"].append(
                {
                    "product_code": item.get("product_code"),
                    "product_name": item.get("product_name"),
                    "unit": item.get("unit"),
                    "quantity": item.get("quantity", 0.0),
                    "total_ge": item.get("total_ge", 0.0),
                    "distinct_waybill_count": item.get("distinct_waybill_count", 0),
                }
            )
    for item in bundle.get("suppliers") or []:
        if isinstance(item, dict):
            summary["suppliers"].append(
                {
                    "supplier": item.get("supplier"),
                    "tax_id": item.get("tax_id"),
                    "distinct_product_count": item.get("distinct_product_count", 0),
                    "distinct_waybill_count": item.get("distinct_waybill_count", 0),
                    "total_amount_ge": item.get("total_amount_ge", 0.0),
                    "date_range": dict(item.get("date_range") or {}),
                }
            )
    for item in bundle.get("products") or []:
        if isinstance(item, dict):
            summary["products"].append(
                {
                    "product_code": item.get("product_code"),
                    "product_name": item.get("product_name"),
                    "distinct_supplier_count": item.get("distinct_supplier_count", 0),
                    "distinct_waybill_count": item.get("distinct_waybill_count", 0),
                    "total_amount_ge": item.get("total_amount_ge", 0.0),
                    "top_supplier_share_pct": item.get("top_supplier_share_pct", 0.0),
                }
            )
    for item in (
        bundle.get("top_supplier_product_pairs") or []
    )[:IMPORTED_PRODUCTS_SUMMARY_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT]:
        if not isinstance(item, dict):
            continue
        quantity = item.get("quantity")
        if quantity is None:
            quantity = item.get("total_quantity", 0.0)
        summary["top_supplier_product_pairs"].append(
            {
                "supplier": item.get("supplier"),
                "product_code": item.get("product_code"),
                "product_name": item.get("product_name"),
                "unit": item.get("unit"),
                "quantity": quantity,
                "total_amount_ge": item.get(
                    "total_amount_ge", item.get("total_ge", 0.0)
                ),
                "distinct_waybill_count": item.get("distinct_waybill_count", 0),
            }
        )
    return summary


def _imported_products_has_source(bundle):
    overall = bundle.get("overall") if isinstance(bundle, dict) else {}
    has_products = bool(bundle.get("products")) if isinstance(bundle, dict) else False
    has_suppliers = bool(bundle.get("suppliers")) if isinstance(bundle, dict) else False
    return has_products or has_suppliers or bool(
        isinstance(overall, dict) and overall.get("row_count")
    )


def _project_retail_sales_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    duplicate_policy = dict(bundle.get("duplicate_policy") or {})
    duplicate_policy["suspected_files"] = [
        {
            "relative_path": item.get("relative_path"),
            "suspected_duplicate_of": item.get("suspected_duplicate_of"),
            "reason_ka": item.get("reason_ka"),
            "present_in_sources": bool(item.get("present_in_sources")),
            "included_in_totals": bool(item.get("included_in_totals")),
        }
        for item in (duplicate_policy.get("suspected_files") or [])
        if isinstance(item, dict)
    ]
    duplicate_policy["excluded_files"] = [
        item for item in (duplicate_policy.get("excluded_files") or []) if item
    ]
    duplicate_policy["excluded_file_count"] = int(
        duplicate_policy.get("excluded_file_count") or 0
    )
    summary = {
        "label_ka": bundle.get("label_ka"),
        "notes_ka": bundle.get("notes_ka"),
        "source_glob": list(bundle.get("source_glob") or []),
        "source_column_schema_expected": list(
            bundle.get("source_column_schema_expected") or []
        ),
        "amount_basis_ka": bundle.get("amount_basis_ka"),
        "files_found_count": int(bundle.get("files_found_count") or 0),
        "files_read_count": int(bundle.get("files_read_count") or 0),
        "files_error_count": int(bundle.get("files_error_count") or 0),
        "files_skipped_by_policy_count": int(
            bundle.get("files_skipped_by_policy_count") or 0
        ),
        "duplicate_policy": duplicate_policy,
        "overall": dict(bundle.get("overall") or {}),
        "category_total_count": int(bundle.get("category_total_count") or 0),
        "categories_truncated": bool(bundle.get("categories_truncated")),
        "products_total_count": int(bundle.get("products_total_count") or 0),
        "products_truncated": bool(bundle.get("products_truncated")),
        "by_object": [],
        "by_category": [],
        "by_product": [],
        "by_month": [],
        "top_objects_by_profit": [],
        "top_categories_by_profit": [],
        "top_products_by_revenue": [],
        "top_products_by_profit": [],
    }
    for item in bundle.get("by_object") or []:
        if not isinstance(item, dict):
            continue
        summary["by_object"].append(
            {
                "object": item.get("object"),
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": item.get("total_quantity", 0.0),
                "revenue_ge": item.get("revenue_ge", 0.0),
                "cost_ge": item.get("cost_ge", 0.0),
                "profit_ge": item.get("profit_ge", 0.0),
                "gross_margin_pct": item.get("gross_margin_pct", 0.0),
                "distinct_category_count": int(item.get("distinct_category_count") or 0),
                "distinct_product_count": int(item.get("distinct_product_count") or 0),
                "date_range": dict(item.get("date_range") or {}),
            }
        )
    for item in (bundle.get("by_category") or [])[:RETAIL_SALES_SUMMARY_CATEGORY_LIMIT]:
        if not isinstance(item, dict):
            continue
        object_breakdown = item.get("object_breakdown") or []
        dominant = object_breakdown[0] if object_breakdown else {}
        summary["by_category"].append(
            {
                "category": item.get("category"),
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": item.get("total_quantity", 0.0),
                "revenue_ge": item.get("revenue_ge", 0.0),
                "cost_ge": item.get("cost_ge", 0.0),
                "profit_ge": item.get("profit_ge", 0.0),
                "gross_margin_pct": item.get("gross_margin_pct", 0.0),
                "distinct_product_count": int(item.get("distinct_product_count") or 0),
                "dominant_object": dominant.get("object"),
                "dominant_object_revenue_ge": dominant.get("revenue_ge", 0.0),
            }
        )
    for item in (bundle.get("by_product") or [])[:RETAIL_SALES_SUMMARY_PRODUCT_LIMIT]:
        if not isinstance(item, dict):
            continue
        object_breakdown = item.get("object_breakdown") or []
        dominant = object_breakdown[0] if object_breakdown else {}
        summary["by_product"].append(
            {
                "product_code": item.get("product_code"),
                "barcode": item.get("barcode"),
                "product_name": item.get("product_name"),
                "unit": item.get("unit"),
                "category": item.get("category"),
                "row_count": int(item.get("row_count") or 0),
                "total_quantity": item.get("total_quantity", 0.0),
                "revenue_ge": item.get("revenue_ge", 0.0),
                "cost_ge": item.get("cost_ge", 0.0),
                "profit_ge": item.get("profit_ge", 0.0),
                "gross_margin_pct": item.get("gross_margin_pct", 0.0),
                "dominant_object": dominant.get("object"),
                "dominant_object_revenue_ge": dominant.get("revenue_ge", 0.0),
            }
        )
    months = [item for item in (bundle.get("by_month") or []) if isinstance(item, dict)]
    summary["by_month"] = months[-RETAIL_SALES_SUMMARY_MONTH_LIMIT:]
    for key in (
        "top_objects_by_profit",
        "top_categories_by_profit",
        "top_products_by_revenue",
        "top_products_by_profit",
    ):
        projected = []
        for item in bundle.get(key) or []:
            if not isinstance(item, dict):
                continue
            projected.append(
                {
                    "object": item.get("object"),
                    "category": item.get("category"),
                    "product_name": item.get("product_name"),
                    "product_code": item.get("product_code"),
                    "revenue_ge": item.get("revenue_ge", 0.0),
                    "cost_ge": item.get("cost_ge", 0.0),
                    "profit_ge": item.get("profit_ge", 0.0),
                    "gross_margin_pct": item.get("gross_margin_pct", 0.0),
                }
            )
        summary[key] = projected
    return summary


def _coerce_waybill_limit(value):
    if value is None:
        return None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return WAYBILLS_MAX_RESPONSE_LIMIT
    if limit <= 0:
        return WAYBILLS_MAX_RESPONSE_LIMIT
    return min(limit, WAYBILLS_MAX_RESPONSE_LIMIT)


def _project_waybill_row(item):
    if not isinstance(item, dict):
        return None
    return {
        "date": item.get("date"),
        "supplier": item.get("supplier"),
        "waybill_number": item.get("waybill_number"),
        "nominal_amount": item.get("nominal_amount"),
        "status": item.get("status"),
        "type": item.get("type"),
        "effective_amount": item.get("effective_amount"),
    }


def _waybill_amount_value(item):
    try:
        return float(item.get("effective_amount"))
    except (TypeError, ValueError):
        pass
    try:
        return float(item.get("nominal_amount"))
    except (TypeError, ValueError):
        return 0.0


def _waybill_date_value(item):
    return _clean_lookup_text(item.get("date")) or ""


def _build_waybills_response(cache, q=None, sort=None, limit=None, **_kwargs):
    rows = cache.get("waybills", FIELD_DEFAULTS["waybills"])
    rows = rows if isinstance(rows, list) else []
    projected_rows = [
        projected
        for projected in (_project_waybill_row(item) for item in rows)
        if projected is not None
    ]
    requested_query = _clean_lookup_text(q)
    requested_sort = _clean_lookup_text(sort)
    applied_sort = requested_sort if requested_sort in WAYBILL_ALLOWED_SORTS else None
    if requested_sort is not None and applied_sort is None:
        applied_sort = "amount_asc"
    applied_limit = _coerce_waybill_limit(limit)
    filtered_rows = projected_rows
    if requested_query:
        needle = requested_query.lower()
        filtered_rows = [
            item
            for item in filtered_rows
            if needle in str(item.get("supplier") or "").lower()
            or needle in str(item.get("waybill_number") or "").lower()
        ]
    if applied_sort == "amount_desc":
        filtered_rows = sorted(filtered_rows, key=_waybill_amount_value, reverse=True)
    elif applied_sort == "date_desc":
        filtered_rows = sorted(filtered_rows, key=_waybill_date_value, reverse=True)
    elif applied_sort == "date_asc":
        filtered_rows = sorted(filtered_rows, key=_waybill_date_value)
    elif applied_sort == "amount_asc":
        filtered_rows = sorted(filtered_rows, key=_waybill_amount_value)
    returned_rows = (
        filtered_rows[:applied_limit] if applied_limit is not None else filtered_rows
    )
    return {
        "waybills": returned_rows,
        "waybills_summary": {
            "query": requested_query,
            "sort": applied_sort,
            "total_count": len(filtered_rows),
            "returned_count": len(returned_rows),
            "limit": applied_limit,
            "has_more": len(filtered_rows) > len(returned_rows),
            "server_filtered": bool(
                requested_query or requested_sort is not None or applied_limit is not None
            ),
        },
    }


def _project_cashflow_pos_terminal_income(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    daily_summary = []
    for item in bundle.get("daily_summary") or []:
        if isinstance(item, dict):
            daily_summary.append(
                {
                    "day": item.get("day"),
                    "tbc_total_ge": item.get("tbc_total_ge", 0.0),
                    "bog_total_ge": item.get("bog_total_ge", 0.0),
                    "total_ge": item.get("total_ge", 0.0),
                }
            )
    return {
        "label_ka": bundle.get("label_ka"),
        "tbc_total_ge": bundle.get("tbc_total_ge", 0.0),
        "bog_total_ge": bundle.get("bog_total_ge", 0.0),
        "total_ge": bundle.get("total_ge", 0.0),
        "tbc_line_count": bundle.get("tbc_line_count", 0),
        "bog_line_count": bundle.get("bog_line_count", 0),
        "line_count": bundle.get("line_count", 0),
        "daily_summary": daily_summary,
    }


def _project_tbc_expenses_category_summary(item):
    if not isinstance(item, dict):
        return None
    return {
        "id": item.get("id"),
        "label_ka": item.get("label_ka"),
        "accounting_role": item.get("accounting_role"),
        "line_count": item.get("line_count", 0),
        "total_ge": item.get("total_ge", 0.0),
    }


def _project_cashflow_tbc_expenses_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    categories = [
        projected
        for projected in (
            _project_tbc_expenses_category_summary(item)
            for item in (bundle.get("categories") or [])
        )
        if projected is not None
    ]
    salary_breakdown = []
    for item in bundle.get("salary_breakdown") or []:
        if isinstance(item, dict):
            salary_breakdown.append(
                {
                    "name": item.get("name"),
                    "total_ge": item.get("total_ge", 0.0),
                }
            )
    return {
        "ledger_note_ka": bundle.get("ledger_note_ka"),
        "grand_total_ge": bundle.get("grand_total_ge", 0.0),
        "grand_total_operating_expense_ge": bundle.get(
            "grand_total_operating_expense_ge", 0.0
        ),
        "grand_total_state_treasury_ge": bundle.get(
            "grand_total_state_treasury_ge", 0.0
        ),
        "salary_breakdown": salary_breakdown,
        "categories": categories,
    }


def _project_bank_unmatched_category_summary(item):
    if not isinstance(item, dict):
        return None
    return {
        "id": item.get("id"),
        "label_ka": item.get("label_ka"),
        "confidence": item.get("confidence"),
        "line_count": item.get("line_count", 0),
        "total_ge": item.get("total_ge", 0.0),
    }


def _project_cashflow_bank_unmatched_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    categories = [
        projected
        for projected in (
            _project_bank_unmatched_category_summary(item)
            for item in (bundle.get("categories") or [])
        )
        if projected is not None
    ]
    top_unclassified_signatures = []
    for item in bundle.get("top_unclassified_signatures") or []:
        if isinstance(item, dict):
            top_unclassified_signatures.append(
                {
                    "signature": item.get("signature"),
                    "line_count": item.get("line_count", 0),
                    "total_ge": item.get("total_ge", 0.0),
                }
            )
    return {
        "ledger_note_ka": bundle.get("ledger_note_ka"),
        "total_ge": bundle.get("total_ge", 0.0),
        "line_count": bundle.get("line_count", 0),
        "categorized_total_ge": bundle.get("categorized_total_ge", 0.0),
        "uncategorized_total_ge": bundle.get("uncategorized_total_ge", 0.0),
        "dynamic_promoted_total_ge": bundle.get("dynamic_promoted_total_ge", 0.0),
        "dynamic_promoted_line_count": bundle.get("dynamic_promoted_line_count", 0),
        "confidence_totals": dict(bundle.get("confidence_totals") or {}),
        "manual_override_approved_lines": bundle.get(
            "manual_override_approved_lines", 0
        ),
        "manual_override_rejected_lines": bundle.get(
            "manual_override_rejected_lines", 0
        ),
        "top_unclassified_signatures": top_unclassified_signatures,
        "categories": categories,
    }


def _project_cashflow_tbc_samurneo_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    return {
        "label_ka": bundle.get("label_ka"),
        "accounting_note_ka": bundle.get("accounting_note_ka"),
        "ledger_classification_ka": bundle.get("ledger_classification_ka"),
        "expense_total_ge": bundle.get("expense_total_ge", 0.0),
        "return_total_ge": bundle.get("return_total_ge", 0.0),
        "net_ge": bundle.get("net_ge", 0.0),
        "expense_line_count": bundle.get("expense_line_count", 0),
        "return_line_count": bundle.get("return_line_count", 0),
        "tbc_expense_total_ge": bundle.get("tbc_expense_total_ge", 0.0),
        "bog_expense_total_ge": bundle.get("bog_expense_total_ge", 0.0),
        "tbc_return_total_ge": bundle.get("tbc_return_total_ge", 0.0),
        "bog_return_total_ge": bundle.get("bog_return_total_ge", 0.0),
    }


def _project_cashflow_tax_flow_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    return {
        "label_ka": bundle.get("label_ka"),
        "ledger_note_ka": bundle.get("ledger_note_ka"),
        "out_total_ge": bundle.get("out_total_ge", 0.0),
        "in_total_ge": bundle.get("in_total_ge", 0.0),
        "net_ge": bundle.get("net_ge", 0.0),
        "out_line_count": bundle.get("out_line_count", 0),
        "in_line_count": bundle.get("in_line_count", 0),
        "treasury_in_total_ge": bundle.get("treasury_in_total_ge", 0.0),
        "treasury_in_line_count": bundle.get("treasury_in_line_count", 0),
    }


def _project_cashflow_foodmart_summary(bundle):
    bundle = bundle if isinstance(bundle, dict) else {}
    return {
        "label_ka": bundle.get("label_ka"),
        "total_ge": bundle.get("total_ge", 0.0),
        "line_count": bundle.get("line_count", 0),
    }


def _build_cashflow_summary_response(cache, **_kwargs):
    return {
        "pos_terminal_income": _project_cashflow_pos_terminal_income(
            cache.get("pos_terminal_income", FIELD_DEFAULTS["pos_terminal_income"])
        ),
        "tbc_expenses": _project_cashflow_tbc_expenses_summary(
            cache.get("tbc_expenses", FIELD_DEFAULTS["tbc_expenses"])
        ),
        "tbc_samurneo": _project_cashflow_tbc_samurneo_summary(
            cache.get("tbc_samurneo", FIELD_DEFAULTS["tbc_samurneo"])
        ),
        "tax_flow": _project_cashflow_tax_flow_summary(
            cache.get("tax_flow", FIELD_DEFAULTS["tax_flow"])
        ),
        "tbc_foodmart_cashback": _project_cashflow_foodmart_summary(
            cache.get("tbc_foodmart_cashback", FIELD_DEFAULTS["tbc_foodmart_cashback"])
        ),
        "bank_unmatched_analysis": _project_cashflow_bank_unmatched_summary(
            cache.get("bank_unmatched_analysis", FIELD_DEFAULTS["bank_unmatched_analysis"])
        ),
    }


def _build_cashflow_tbc_expenses_detail_response(cache, **_kwargs):
    return {"tbc_expenses": cache.get("tbc_expenses", FIELD_DEFAULTS["tbc_expenses"])}


def _build_cashflow_bank_unmatched_detail_response(cache, **_kwargs):
    return {
        "bank_unmatched_analysis": cache.get(
            "bank_unmatched_analysis", FIELD_DEFAULTS["bank_unmatched_analysis"]
        )
    }


def _build_pnl_summary_response(cache, **_kwargs):
    return {"monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"])}


def _find_imported_products_supplier_entry(bundle, tax_id=None, normalized_supplier=None):
    suppliers = bundle.get("suppliers") if isinstance(bundle, dict) else None
    suppliers = suppliers if isinstance(suppliers, list) else []
    requested_tax_id = _clean_lookup_text(tax_id)
    requested_normalized_supplier = _clean_lookup_text(normalized_supplier)
    if requested_tax_id:
        for item in suppliers:
            if not isinstance(item, dict):
                continue
            if _clean_lookup_text(item.get("tax_id")) == requested_tax_id:
                return item, "tax_id", False
    if requested_normalized_supplier:
        candidates = []
        for item in suppliers:
            if not isinstance(item, dict):
                continue
            if _clean_lookup_text(item.get("normalized_supplier")) == requested_normalized_supplier:
                candidates.append(item)
        if len(candidates) == 1:
            return candidates[0], "name_fallback", False
        if len(candidates) > 1:
            return None, None, True
    return None, None, False


def _find_imported_products_product_entry(
    bundle, product_code=None, normalized_product=None
):
    products = bundle.get("products") if isinstance(bundle, dict) else None
    products = products if isinstance(products, list) else []
    requested_product_code = _clean_lookup_text(product_code)
    requested_normalized_product = _normalize_lookup_name(normalized_product)
    if requested_product_code:
        candidates = []
        for item in products:
            if not isinstance(item, dict):
                continue
            if _clean_lookup_text(item.get("product_code")) == requested_product_code:
                candidates.append(item)
        if requested_normalized_product:
            candidates = [
                item
                for item in candidates
                if _normalize_lookup_name(item.get("product_name"))
                == requested_normalized_product
            ]
        if len(candidates) == 1:
            match_type = "product_code+name" if requested_normalized_product else "product_code"
            return candidates[0], match_type, False
        if len(candidates) > 1:
            return None, None, True
    if requested_normalized_product:
        candidates = []
        for item in products:
            if not isinstance(item, dict):
                continue
            if _normalize_lookup_name(item.get("product_name")) == requested_normalized_product:
                candidates.append(item)
        if len(candidates) == 1:
            return candidates[0], "name_fallback", False
        if len(candidates) > 1:
            return None, None, True
    return None, None, False


def _build_imported_products_response(cache, **_kwargs):
    bundle = cache.get("imported_products", FIELD_DEFAULTS["imported_products"])
    return {"imported_products": _project_imported_products_summary(bundle)}


def _build_imported_products_full_response(cache, **_kwargs):
    bundle = cache.get("imported_products", FIELD_DEFAULTS["imported_products"])
    return {"imported_products_full": bundle}


def _build_imported_products_supplier_detail_response(
    cache, tax_id=None, normalized_supplier=None, **_kwargs
):
    bundle = cache.get("imported_products", FIELD_DEFAULTS["imported_products"])
    entry, match_type, ambiguous = _find_imported_products_supplier_entry(
        bundle, tax_id=tax_id, normalized_supplier=normalized_supplier
    )
    return {
        "imported_products_supplier_detail": {
            "label_ka": bundle.get("label_ka"),
            "supplier_top_products_limit": bundle.get("supplier_top_products_limit", 0),
            "truncation_suspected_any": bool(bundle.get("truncation_suspected_any")),
            "has_source": _imported_products_has_source(bundle),
            "requested": {
                "tax_id": _clean_lookup_text(tax_id),
                "normalized_supplier": _clean_lookup_text(normalized_supplier),
            },
            "match_type": match_type,
            "ambiguous": ambiguous,
            "entry": entry,
        }
    }


def _build_imported_products_product_detail_response(
    cache, product_code=None, normalized_product=None, **_kwargs
):
    bundle = cache.get("imported_products", FIELD_DEFAULTS["imported_products"])
    entry, match_type, ambiguous = _find_imported_products_product_entry(
        bundle,
        product_code=product_code,
        normalized_product=normalized_product,
    )
    return {
        "imported_products_product_detail": {
            "label_ka": bundle.get("label_ka"),
            "product_top_suppliers_limit": bundle.get("product_top_suppliers_limit", 0),
            "products_total_count": bundle.get("products_total_count", 0),
            "products_truncated": bool(bundle.get("products_truncated")),
            "truncation_suspected_any": bool(bundle.get("truncation_suspected_any")),
            "has_source": _imported_products_has_source(bundle),
            "requested": {
                "product_code": _clean_lookup_text(product_code),
                "normalized_product": _normalize_lookup_name(normalized_product),
            },
            "match_type": match_type,
            "ambiguous": ambiguous,
            "entry": entry,
        }
    }


def _build_retail_sales_response(cache, **_kwargs):
    bundle = cache.get("retail_sales", FIELD_DEFAULTS["retail_sales"])
    return {"retail_sales": _project_retail_sales_summary(bundle)}


SPECIAL_TAB_BUILDERS = {
    "cashflow_summary": _build_cashflow_summary_response,
    "cashflow_tbc_expenses_detail": _build_cashflow_tbc_expenses_detail_response,
    "cashflow_bank_unmatched_detail": _build_cashflow_bank_unmatched_detail_response,
    "pnl_summary": _build_pnl_summary_response,
    "waybills": _build_waybills_response,
    "imported_products": _build_imported_products_response,
    "imported_products_full": _build_imported_products_full_response,
    "imported_products_supplier_detail": _build_imported_products_supplier_detail_response,
    "imported_products_product_detail": _build_imported_products_product_detail_response,
    "retail_sales": _build_retail_sales_response,
}

ALLOWED_TABS = sorted(set(TAB_ALLOWLIST) | set(SPECIAL_TAB_BUILDERS))


def _build_response_meta(cache, tab, response):
    tab_meta = dict(TAB_RESPONSE_META.get(tab) or {})
    payload_meta = {
        "tab": tab,
        "trust_label": tab_meta.get("trust_label") or "derived",
        "trust_badge_ka": tab_meta.get("trust_badge_ka") or "Derived",
        "scope_ka": tab_meta.get("scope_ka") or "",
        "notes_ka": list(tab_meta.get("notes_ka") or []),
        "generated_at": (cache.get("meta") or {}).get("generated_at"),
        "source_manifest_summary": (cache.get("meta") or {}).get(
            "source_manifest_summary"
        )
        or {},
        "partial": False,
        "partial_reason": "",
    }
    if tab == "waybills":
        summary = response.get("waybills_summary") or {}
        if bool(summary.get("has_more")):
            payload_meta["partial"] = True
            payload_meta["partial_reason"] = (
                "Waybill response is capped; use export/search for full coverage."
            )
    elif tab in {
        "imported_products",
        "imported_products_full",
        "imported_products_supplier_detail",
        "imported_products_product_detail",
    }:
        bundle = response.get("imported_products") or response.get("imported_products_full") or {}
        if not bundle:
            detail = response.get("imported_products_supplier_detail") or response.get(
                "imported_products_product_detail"
            ) or {}
            if bool(detail.get("truncation_suspected_any")):
                payload_meta["partial"] = True
                payload_meta["partial_reason"] = "Imported-products source may be truncated."
        elif bool(bundle.get("truncation_suspected_any")):
            payload_meta["partial"] = True
            payload_meta["partial_reason"] = "Imported-products source may be truncated."
    elif tab == "retail_sales":
        retail = response.get("retail_sales") or {}
        if bool(retail.get("categories_truncated")) or bool(retail.get("products_truncated")):
            payload_meta["partial"] = True
            payload_meta["partial_reason"] = (
                "Retail-sales summary is capped; use source artifact for full list."
            )
        elif int(retail.get("files_error_count") or 0) > 0:
            payload_meta["partial"] = True
            payload_meta["partial_reason"] = (
                "Retail-sales source has unreadable files; totals may be incomplete."
            )
    return payload_meta


def build_response_for_tab(
    cache,
    tab,
    tax_id=None,
    normalized_supplier=None,
    product_code=None,
    normalized_product=None,
    q=None,
    sort=None,
    limit=None,
):
    response = _base_response(cache)
    if tab in SPECIAL_TAB_BUILDERS:
        response.update(
            SPECIAL_TAB_BUILDERS[tab](
                cache,
                tax_id=tax_id,
                normalized_supplier=normalized_supplier,
                product_code=product_code,
                normalized_product=normalized_product,
                q=q,
                sort=sort,
                limit=limit,
            )
        )
    else:
        for field in TAB_ALLOWLIST[tab]:
            response[field] = cache.get(field, FIELD_DEFAULTS.get(field, {}))
    response["response_meta"] = _build_response_meta(cache, tab, response)
    return response


def build_static_api_artifacts(cache):
    artifacts = {}
    for tab in sorted(STATIC_RESPONSE_TABS):
        artifacts[tab] = build_response_for_tab(cache, tab)
    artifacts["waybills_source"] = {
        **_base_response(cache),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
    }
    artifacts["imported_products_source"] = {
        **_base_response(cache),
        "imported_products": cache.get(
            "imported_products", FIELD_DEFAULTS["imported_products"]
        ),
    }
    artifacts["retail_sales_source"] = {
        **_base_response(cache),
        "retail_sales": cache.get("retail_sales", FIELD_DEFAULTS["retail_sales"]),
    }
    return artifacts
