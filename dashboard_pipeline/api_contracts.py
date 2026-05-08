from __future__ import annotations

from collections import defaultdict

import re

from dashboard_pipeline.analytics_builders import (
    build_ap_monthly_trend,
    build_budget,
    build_company_valuation,
    build_executive_summary,
    build_financial_ratios,
    build_forecast,
    build_monthly_pnl,
    build_supplier_aging,
)
from dashboard_pipeline.constants import _extract_tax_id_from_org
from dashboard_pipeline.date_filters import (
    build_period_caveat_ka,
    build_period_filter,
    matches_period,
    parse_source_datetime,
    serialize_period_filter,
)
from dashboard_pipeline.imported_products import collect_imported_products_bundle
from dashboard_pipeline.retail_sales import collect_retail_sales_bundle
from dashboard_pipeline.supplier_archive import load as _load_supplier_archive
from dashboard_pipeline.supplier_matching import _normalize_waybill_ref
from dashboard_pipeline.truth_boundary import (
    build_payment_scope_summary,
    describe_supplier_payment_scope,
)

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
    "dead_stock_summary": {},
    "supplier_concentration": {},
    "category_anomalies": {},
    "waybill_reconciliation": {},
    "supplier_reconciliation": {"rows": [], "summary": {}},
    "orphan_products": {},
    "duplicate_products": {},
    "supplier_payment_lines": {},
    "supplier_waybill_lines": {},
    "supplier_invoices": {},
    "supplier_invoices_summary": {},
    "our_seller_invoices": [],
    "invoice_waybill_match": [],
    "supplier_invoices_meta": {},
}

# ერთი ჭერი: სრული rollup/API პასუხები დიდი მოცულობისას (OOM-ისგან დასაცავად ზედა საზღვარი).
FULL_VIEW_ROW_CAP = 10_000_000

IMPORTED_PRODUCTS_SUMMARY_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT = FULL_VIEW_ROW_CAP
RETAIL_SALES_SUMMARY_CATEGORY_LIMIT = FULL_VIEW_ROW_CAP
RETAIL_SALES_SUMMARY_PRODUCT_LIMIT = FULL_VIEW_ROW_CAP
RETAIL_SALES_SUMMARY_MONTH_LIMIT = 600
WAYBILLS_MAX_RESPONSE_LIMIT = FULL_VIEW_ROW_CAP
WAYBILL_ALLOWED_SORTS = {"amount_asc", "amount_desc", "date_asc", "date_desc"}

TAB_ALLOWLIST = {
    "suppliers": ["suppliers", "supplier_payment_lines", "supplier_invoices", "supplier_invoices_summary", "supplier_invoices_meta"],
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
    "dead_stock": ["dead_stock_summary"],
    "supplier_concentration": ["supplier_concentration"],
    "category_anomalies": ["category_anomalies"],
    "waybill_reconciliation": ["waybill_reconciliation"],
    "supplier_reconciliation": ["supplier_reconciliation"],
    "orphan_products": ["orphan_products"],
    "duplicate_products": ["duplicate_products"],
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
    "dead_stock": {
        "trust_label": "derived",
        "trust_badge_ka": "Dead Stock",
        "scope_ka": (
            "imported_products × retail_sales triangulation with "
            "180-day stale threshold and 4-action salvage plan."
        ),
        "notes_ka": [
            "frozen_cash_estimate არის ZEDA-BOUND, არა ზუსტი დიაგნოზი.",
            "barcode/code drift იწვევს 30%+ unmatched-ს; ციფრები matched_total_amount-ზე უფრო საიმედოა.",
        ],
    },
    "supplier_concentration": {
        "trust_label": "derived",
        "trust_badge_ka": "Supplier Portfolio",
        "scope_ka": (
            "Portfolio concentration (HHI + Pareto top-5/10/20) "
            "and Top-N negotiation candidates ranked by leverage × savings × spend."
        ),
        "notes_ka": [
            "leverage_score არის relative ranking signal, არა absolute savings guarantee.",
            "estimated_annual_savings_ge იყენებს price_benchmark-ს — აქ წყაროს კომპლექტურობა ვარიაციულია.",
        ],
    },
    "category_anomalies": {
        "trust_label": "audited",
        "trust_badge_ka": "MegaPlus Operator Errors",
        "scope_ka": (
            "Per-store MegaPlus PRODUCTS table audit: empty P_GROUP, duplicate "
            "category-name variants, PROTECTED-supplier overview."
        ),
        "notes_ka": [
            "Operator-driven errors — fix in MegaPlus, rerun pipeline, flag clears.",
            "Duplicate clusters group raw P_GROUP by stripped numeric code prefix + lowercase.",
        ],
    },
    "orphan_products": {
        "trust_label": "audited",
        "trust_badge_ka": "MegaPlus Orphans",
        "scope_ka": (
            "PRODUCTS rows whose supplier link is empty/zero/ghost, with the "
            "resolver's best-guess supplier from RS_CODES + DISTRIBUTORS + SOAP."
        ),
        "notes_ka": [
            "Live MegaPlus DB query each pipeline run — fixes in MegaPlus clear automatically.",
            'User-marked "უგულებელყოფილი" persists in Financial_Analysis/orphan_user_status.json.',
        ],
    },
    "duplicate_products": {
        "trust_label": "audited",
        "trust_badge_ka": "MegaPlus Duplicates",
        "scope_ka": (
            "Same P_BARCODE recorded as 2+ distinct P_ID rows. Each cluster lists "
            "all variants with stock (P_QUANT) and lifetime sales; phantom-stock "
            "variants (stock>0, zero sales) are highlighted."
        ),
        "notes_ka": [
            "Live MegaPlus DB query — clean up in MegaPlus and the cluster disappears next pipeline run.",
            "Phantom-stock variants inflate apparent inventory; the active variant often shows negative P_QUANT.",
        ],
    },
    "waybill_reconciliation": {
        "trust_label": "audited",
        "trust_badge_ka": "rs.ge ↔ MegaPlus Reconciliation",
        "scope_ka": (
            "Cross-source check: every rs.ge active waybill must have a "
            "matching MegaPlus GET row (or GACERA for returns). Surfaces "
            "missing receipts, amount mismatches, ghost AP (received "
            "against cancelled rs.ge document), unrecorded returns/"
            "sub-waybills, ±14-day soft-signal possible replacements, "
            "and stale-rs-data flags (GET has it, rs.ge xls doesn't)."
        ),
        "notes_ka": [
            "Closed-store destinations (Tbilisi addresses 2022-2024) are "
            "filtered out — only active stores 1329 დვაბზუ + 1301 ოზურგეთი.",
            "Cancelled+replaced rs.ge waybills (same supplier+date+amount, "
            "different number) are treated as normal noise, not flagged.",
            "Spot-check: 5/5 random rows verified in source 2026-05-02.",
        ],
    },
    "supplier_reconciliation": {
        "trust_label": "derived",
        "trust_badge_ka": "ფაქტურა ↔ ზედნადები",
        "scope_ka": (
            "Per-supplier comparison of rs.ge invoice totals against "
            "rs.ge waybill totals (returns already netted via negative "
            "amounts). Flags suppliers whose absolute gap ≥ 100 ₾ as "
            "either over_invoice (invoice exceeds waybills) or "
            "over_waybill (waybills exceed invoices)."
        ),
        "notes_ka": [
            "Source: supplier_invoices_summary + supplier_waybill_lines.",
            "Gap interpretation is supplier-specific — services-on-invoice, "
            "delayed waybills, or wholesale-vs-list-price patterns can all "
            "produce non-zero gaps; UI table is a starting point for owner "
            "review, not an automatic anomaly verdict.",
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
    "dead_stock",
    "supplier_concentration",
    "category_anomalies",
    "waybill_reconciliation",
    "supplier_reconciliation",
    "orphan_products",
    "duplicate_products",
}

DYNAMIC_SOURCE_ARTIFACTS = {
    "suppliers": "suppliers_source",
    "working_capital": "suppliers_source",
    "waybills": "waybills_source",
    "pnl_summary": "pnl_source",
    "ratios": "ratios_source",
    "forecast": "forecast_source",
    "budget": "budget_source",
    "valuation": "valuation_source",
    "executive": "executive_source",
    "imported_products_supplier_detail": "imported_products_source",
    "imported_products_product_detail": "imported_products_source",
}

PERIOD_META_SUPPRESSED_TABS = {
    "cashflow_summary",
    "cashflow_tbc_expenses_detail",
    "cashflow_bank_unmatched_detail",
    "executive_export",
}


def _base_response(cache):
    meta = cache.get("meta", FIELD_DEFAULTS["meta"])
    download_files = cache.get("download_files", FIELD_DEFAULTS["download_files"])
    return {
        "meta": dict(meta) if isinstance(meta, dict) else {},
        "download_files": list(download_files) if isinstance(download_files, list) else [],
        "download_zip_file": cache.get(
            "download_zip_file", FIELD_DEFAULTS["download_zip_file"]
        ),
    }


def _clean_lookup_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _merge_non_empty_text(*parts):
    merged = []
    seen = set()
    for part in parts:
        text = str(part or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return " ".join(merged)


def _resolve_response_period_meta(tab, response, period_filter):
    if tab in PERIOD_META_SUPPRESSED_TABS:
        return serialize_period_filter(None)
    if tab == "waybills":
        summary = response.get("waybills_summary") or {}
        if isinstance(summary.get("period_meta"), dict):
            return dict(summary.get("period_meta") or {})
    elif tab == "suppliers":
        if isinstance(response.get("suppliers_period_meta"), dict):
            return dict(response.get("suppliers_period_meta") or {})
    elif tab == "working_capital":
        if isinstance(response.get("working_capital_period_meta"), dict):
            return dict(response.get("working_capital_period_meta") or {})
    elif tab == "pnl_summary":
        if isinstance(response.get("pnl_period_meta"), dict):
            return dict(response.get("pnl_period_meta") or {})
    elif tab == "ratios":
        if isinstance(response.get("ratios_period_meta"), dict):
            return dict(response.get("ratios_period_meta") or {})
    elif tab == "forecast":
        if isinstance(response.get("forecast_period_meta"), dict):
            return dict(response.get("forecast_period_meta") or {})
    elif tab == "budget":
        if isinstance(response.get("budget_period_meta"), dict):
            return dict(response.get("budget_period_meta") or {})
    elif tab == "valuation":
        if isinstance(response.get("valuation_period_meta"), dict):
            return dict(response.get("valuation_period_meta") or {})
    elif tab == "executive":
        if isinstance(response.get("executive_period_meta"), dict):
            return dict(response.get("executive_period_meta") or {})
    elif tab == "retail_sales":
        retail = response.get("retail_sales") or {}
        if isinstance(retail.get("period_meta"), dict):
            return dict(retail.get("period_meta") or {})
    elif tab in {
        "imported_products",
        "imported_products_full",
        "imported_products_supplier_detail",
        "imported_products_product_detail",
    }:
        imported = response.get("imported_products") or response.get(
            "imported_products_full"
        ) or {}
        if isinstance(imported.get("period_meta"), dict):
            return dict(imported.get("period_meta") or {})
        detail = response.get("imported_products_supplier_detail") or response.get(
            "imported_products_product_detail"
        ) or {}
        if isinstance(detail.get("period_meta"), dict):
            return dict(detail.get("period_meta") or {})
    return serialize_period_filter(period_filter)


def _resolve_data_period_label(meta, period_meta):
    meta = meta if isinstance(meta, dict) else {}
    explicit_label = _clean_lookup_text(meta.get("data_period_label"))
    if explicit_label is not None:
        return explicit_label
    fallback_label = _clean_lookup_text(meta.get("period_label"))
    if fallback_label is not None:
        return fallback_label
    period_label = _clean_lookup_text((period_meta or {}).get("label_ka"))
    if period_label is not None:
        return period_label
    if bool((period_meta or {}).get("applied")):
        return "არჩეული პერიოდი"
    return "ყველა პერიოდი"


def _build_response_meta(
    cache,
    tab,
    response,
    *,
    period_meta=None,
    period_caveat_ka="",
    data_period_label="",
):
    response = response if isinstance(response, dict) else {}
    response_meta_cfg = TAB_RESPONSE_META.get(tab) or {}
    response_meta = {
        "tab": str(tab or ""),
        "trust_label": str(response_meta_cfg.get("trust_label") or "derived"),
        "trust_badge_ka": str(
            response_meta_cfg.get("trust_badge_ka") or "Derived"
        ),
        "scope_ka": str(
            response_meta_cfg.get("scope_ka") or "დამხმარე ანალიტიკური ხედვა."
        ),
        "notes_ka": [
            str(note).strip()
            for note in (response_meta_cfg.get("notes_ka") or [])
            if str(note).strip()
        ],
        "partial": False,
        "partial_reason": "",
        "period_caveat_ka": str(period_caveat_ka or ""),
        "period_meta": dict(period_meta or {}) if isinstance(period_meta, dict) else {},
        "data_period_label": str(data_period_label or ""),
        "generated_at": "",
        "source_manifest_summary": {},
    }
    meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
    cache_meta = (
        cache.get("meta")
        if isinstance(cache, dict) and isinstance(cache.get("meta"), dict)
        else {}
    )
    generated_at = _clean_lookup_text(meta.get("generated_at")) or _clean_lookup_text(
        cache_meta.get("generated_at")
    )
    if generated_at is not None:
        response_meta["generated_at"] = generated_at
    source_manifest_summary = meta.get("source_manifest_summary")
    if not isinstance(source_manifest_summary, dict):
        source_manifest_summary = cache_meta.get("source_manifest_summary")
    if isinstance(source_manifest_summary, dict):
        response_meta["source_manifest_summary"] = dict(source_manifest_summary)
    if tab == "waybills":
        waybills_summary = (
            response.get("waybills_summary")
            if isinstance(response.get("waybills_summary"), dict)
            else {}
        )
        if bool(waybills_summary.get("has_more")):
            response_meta["partial"] = True
            response_meta["partial_reason"] = (
                "ეკრანზე ჩანს მხოლოდ "
                f"{int(waybills_summary.get('returned_count') or 0)} ჩანაწერი "
                f"{int(waybills_summary.get('total_count') or 0)}-დან."
            )
        elif _clean_lookup_text(waybills_summary.get("query")):
            response_meta["partial"] = True
            response_meta["partial_reason"] = (
                "ძებნის გამო ნაჩვენებია მხოლოდ დამთხვეული ზედნადებები."
            )
    if (
        not response_meta["partial"]
        and bool((period_meta or {}).get("applied"))
        and response_meta["period_caveat_ka"]
    ):
        response_meta["partial"] = True
        response_meta["partial_reason"] = response_meta["period_caveat_ka"]
    return response_meta


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


def _coerce_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _supplier_response_key(tax_id=None, org_name=None):
    normalized_tax_id = _clean_lookup_text(tax_id)
    if normalized_tax_id:
        return f"tax:{normalized_tax_id}"
    normalized_org_name = _clean_lookup_text(org_name)
    if normalized_org_name:
        return f"org:{normalized_org_name}"
    return None


def _lookup_supplier_base_row(source_index, tax_id=None, org_name=None):
    tax_key = _supplier_response_key(tax_id=tax_id)
    if tax_key and tax_key in source_index:
        return source_index[tax_key]
    org_key = _supplier_response_key(org_name=org_name)
    if org_key and org_key in source_index:
        return source_index[org_key]
    return {}


def _seed_supplier_response_row(base_row=None, org_name="", tax_id=None):
    base_row = dict(base_row) if isinstance(base_row, dict) else {}
    org_name = str(
        org_name
        or base_row.get("ორგანიზაცია")
        or base_row.get("org")
        or base_row.get("supplier")
        or ""
    ).strip()
    tax_id = str(
        tax_id or base_row.get("tax_id") or _extract_tax_id_from_org(org_name) or ""
    ).strip()
    payment_scope = describe_supplier_payment_scope(0, 0)
    return {
        "tax_id": tax_id or None,
        "ორგანიზაცია": org_name,
        "waybills_count": 0,
        "total_nominal": 0.0,
        "total_cancelled": 0.0,
        "total_returned": 0.0,
        "total_effective": 0.0,
        "total_paid": 0.0,
        "manual_paid": 0.0,
        "strict_bank_paid": 0.0,
        "bank_paid": 0.0,
        "total_debt": 0.0,
        "payment_scope": payment_scope.get("payment_scope"),
        "payment_scope_note": payment_scope.get("payment_scope_note"),
        "supplier_truth_summary": str(base_row.get("supplier_truth_summary") or ""),
        "supplier_truth_sources": list(base_row.get("supplier_truth_sources") or []),
        "official_name_truth_source": str(
            base_row.get("official_name_truth_source") or ""
        ),
    }


def _build_supplier_source_index(rows):
    source_index = {}
    supplier_names = {}
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        org_name = str(
            item.get("ორგანიზაცია") or item.get("org") or item.get("supplier") or ""
        ).strip()
        tax_id = str(item.get("tax_id") or _extract_tax_id_from_org(org_name) or "").strip()
        for key in (
            _supplier_response_key(tax_id=tax_id),
            _supplier_response_key(org_name=org_name),
        ):
            if key and key not in source_index:
                source_index[key] = item
        if tax_id and tax_id not in supplier_names:
            supplier_names[tax_id] = org_name or tax_id
    return source_index, supplier_names


def _waybill_is_cancelled(item):
    return "გაუქმებული" in str((item or {}).get("status") or "").casefold()


def _waybill_is_returned(item):
    waybill_type = str((item or {}).get("type") or "").casefold()
    return "უკან დაბრუნება" in waybill_type or "დაბრუნება" in waybill_type


def _row_within_period(value, period_filter):
    if not bool((period_filter or {}).get("applied")):
        return True, False
    parsed_value = parse_source_datetime(value)
    if parsed_value is None or parsed_value != parsed_value:
        return False, True
    return bool(matches_period(parsed_value, period_filter)), False


def _filter_period_source_rows(rows, period_filter, date_field="თარიღი"):
    filtered_rows = []
    total_rows_seen = 0
    matched_rows = 0
    excluded_unparseable_count = 0
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        total_rows_seen += 1
        in_period, unparseable = _row_within_period(item.get(date_field), period_filter)
        if unparseable:
            excluded_unparseable_count += 1
            continue
        if not in_period:
            continue
        matched_rows += 1
        filtered_rows.append(dict(item))
    return filtered_rows, total_rows_seen, matched_rows, excluded_unparseable_count


def _filter_pnl_expense_bundle(bundle, period_filter):
    bundle = bundle if isinstance(bundle, dict) else {}
    filtered_categories = []
    total_rows_seen = 0
    matched_rows = 0
    excluded_unparseable_count = 0
    for category in bundle.get("categories") or []:
        if not isinstance(category, dict):
            continue
        lines, category_total_rows, category_matched_rows, category_excluded = (
            _filter_period_source_rows(
                category.get("lines") or [],
                period_filter,
                date_field="თარიღი",
            )
        )
        total_rows_seen += category_total_rows
        matched_rows += category_matched_rows
        excluded_unparseable_count += category_excluded
        filtered_categories.append(
            {
                **dict(category),
                "lines": lines,
                "line_count": len(lines),
                "total_ge": round(
                    sum(_coerce_float(item.get("თანხა")) for item in lines),
                    2,
                ),
                "rows_preview": lines[:300],
            }
        )
    return (
        {"categories": filtered_categories},
        total_rows_seen,
        matched_rows,
        excluded_unparseable_count,
    )


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
        "period_meta": dict(bundle.get("period_meta") or {}),
        "overall": dict(bundle.get("overall") or {}),
        "category_total_count": bundle.get("category_total_count", 0),
        "categories_truncated": bool(bundle.get("categories_truncated")),
        "products_total_count": bundle.get("products_total_count", 0),
        "products_truncated": bool(bundle.get("products_truncated")),
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
        "period_meta": dict(bundle.get("period_meta") or {}),
        "overall": dict(bundle.get("overall") or {}),
        "category_total_count": int(bundle.get("category_total_count") or 0),
        "categories_truncated": bool(bundle.get("categories_truncated")),
        "products_total_count": int(bundle.get("products_total_count") or 0),
        "products_truncated": bool(bundle.get("products_truncated")),
        "by_object": [],
        "by_category": [],
        "by_product": [],
        "by_month": [],
        "by_category_by_month": [],
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
    summary["by_category_by_month"] = [
        item for item in (bundle.get("by_category_by_month") or []) if isinstance(item, dict)
    ]
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
    """None ან <=0 = ყველა ხაზი (სერვერის ზედა ჭერამდე); დადებითი = min(limit, cap)."""
    if value is None:
        return None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    if limit <= 0:
        return None
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


def _waybill_numeric_value(item, field):
    try:
        return float(item.get(field))
    except (TypeError, ValueError):
        return 0.0


def _build_waybill_status_breakdown(rows):
    breakdown = {}
    for item in rows:
        status = _clean_lookup_text(item.get("status")) or "უცნობი სტატუსი"
        entry = breakdown.setdefault(
            status,
            {
                "status": status,
                "row_count": 0,
                "nominal_amount": 0.0,
                "effective_amount": 0.0,
            },
        )
        entry["row_count"] += 1
        entry["nominal_amount"] += _waybill_numeric_value(item, "nominal_amount")
        entry["effective_amount"] += _waybill_numeric_value(item, "effective_amount")
    return sorted(
        breakdown.values(),
        key=lambda value: (
            -int(value.get("row_count") or 0),
            -float(value.get("effective_amount") or 0),
            str(value.get("status") or ""),
        ),
    )


def _build_waybills_response(
    cache, q=None, sort=None, limit=None, period_filter=None, **_kwargs
):
    rows = cache.get("waybills") if isinstance(cache, dict) else None
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
    period_filtered_rows = [
        item for item in projected_rows if matches_period(item.get("date"), period_filter)
    ]
    period_meta = serialize_period_filter(
        period_filter,
        total_rows_seen=len(projected_rows),
        matched_rows=len(period_filtered_rows),
    )
    filtered_rows = period_filtered_rows
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
                requested_query
                or requested_sort is not None
                or applied_limit is not None
                or bool(period_meta.get("applied"))
            ),
            "status_breakdown": _build_waybill_status_breakdown(filtered_rows),
            "total_nominal_amount": float(
                sum(
                    _waybill_numeric_value(item, "nominal_amount")
                    for item in filtered_rows
                )
            ),
            "total_effective_amount": float(
                sum(
                    _waybill_numeric_value(item, "effective_amount")
                    for item in filtered_rows
                )
            ),
            "period_meta": period_meta,
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


def _filter_retail_sales_bundle_by_months(bundle, allowed_months):
    """Slice retail_sales_bundle.by_object_by_month down to allowed months.

    Used in the period-filter pnl response so cash income reflects only
    months that survived filtering. Returns a thin bundle the
    `build_monthly_pnl` helper can consume.
    """
    if not bundle or not allowed_months:
        return None
    rows = (bundle or {}).get("by_object_by_month") or []
    allowed = set(allowed_months)
    sliced = [row for row in rows if str((row or {}).get("month") or "") in allowed]
    if not sliced:
        return None
    return {"by_object_by_month": sliced}


def _build_pnl_summary_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {"monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"])}
    pos_bundle = cache.get("pos_terminal_income") if isinstance(cache, dict) else {}
    tbc_expenses_bundle = cache.get("tbc_expenses") if isinstance(cache, dict) else {}
    bog_expenses_bundle = cache.get("bog_expenses") if isinstance(cache, dict) else {}
    object_mapping = cache.get("object_mapping") if isinstance(cache, dict) else None
    retail_sales_bundle = cache.get("retail_sales") if isinstance(cache, dict) else None
    pos_lines, pos_total_rows, pos_matched_rows, pos_excluded_unparseable = (
        _filter_period_source_rows(
            (pos_bundle or {}).get("pnl_lines") or (pos_bundle or {}).get("lines") or [],
            period_filter,
            date_field="თარიღი",
        )
    )
    (
        filtered_tbc_expenses,
        tbc_total_rows,
        tbc_matched_rows,
        tbc_excluded_unparseable,
    ) = _filter_pnl_expense_bundle(tbc_expenses_bundle, period_filter)
    (
        filtered_bog_expenses,
        bog_total_rows,
        bog_matched_rows,
        bog_excluded_unparseable,
    ) = _filter_pnl_expense_bundle(bog_expenses_bundle, period_filter)
    # Filter retail_sales by the months that survived pos/expense filtering
    # so cash income matches the same period window.
    allowed_months = set()
    for line in pos_lines:
        ts = parse_source_datetime((line or {}).get("თარიღი"))
        if ts is not None and ts == ts:
            allowed_months.add(f"{ts.year:04d}-{ts.month:02d}")
    for category in (filtered_tbc_expenses or {}).get("categories") or []:
        for line in category.get("lines") or []:
            ts = parse_source_datetime((line or {}).get("თარიღი"))
            if ts is not None and ts == ts:
                allowed_months.add(f"{ts.year:04d}-{ts.month:02d}")
    for category in (filtered_bog_expenses or {}).get("categories") or []:
        for line in category.get("lines") or []:
            ts = parse_source_datetime((line or {}).get("თარიღი"))
            if ts is not None and ts == ts:
                allowed_months.add(f"{ts.year:04d}-{ts.month:02d}")
    filtered_retail_bundle = _filter_retail_sales_bundle_by_months(
        retail_sales_bundle, allowed_months
    )
    period_meta = serialize_period_filter(period_filter)
    period_meta["total_rows_seen"] = int(
        pos_total_rows + tbc_total_rows + bog_total_rows
    )
    period_meta["matched_rows"] = int(
        pos_matched_rows + tbc_matched_rows + bog_matched_rows
    )
    period_meta["excluded_unparseable_count"] = int(
        pos_excluded_unparseable
        + tbc_excluded_unparseable
        + bog_excluded_unparseable
    )
    supplier_payment_lines = (
        cache.get("supplier_payment_lines") if isinstance(cache, dict) else None
    )
    return {
        "monthly_pnl": build_monthly_pnl(
            {"pnl_lines": pos_lines},
            filtered_tbc_expenses,
            object_mapping,
            bog_expenses_bundle=filtered_bog_expenses,
            retail_sales_bundle=filtered_retail_bundle,
            supplier_payment_lines=supplier_payment_lines,
        ),
        "pnl_period_meta": period_meta,
    }


def _build_forecast_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {
            "forecast": cache.get("forecast", FIELD_DEFAULTS["forecast"]),
            "monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"]),
        }
    pnl_response = _build_pnl_summary_response(cache, period_filter=period_filter)
    monthly_pnl = pnl_response.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"])
    return {
        "forecast": build_forecast(monthly_pnl),
        "monthly_pnl": monthly_pnl,
        "forecast_period_meta": dict(
            pnl_response.get("pnl_period_meta") or serialize_period_filter(period_filter)
        ),
    }


def _build_budget_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {
            "budget": cache.get("budget", FIELD_DEFAULTS["budget"]),
        }
    pnl_response = _build_pnl_summary_response(cache, period_filter=period_filter)
    monthly_pnl = pnl_response.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"])
    budget = build_budget(
        monthly_pnl,
        build_forecast(monthly_pnl),
        cache.get("budget_config") if isinstance(cache, dict) else None,
    )
    return {
        "budget": budget,
        "budget_period_meta": dict(
            pnl_response.get("pnl_period_meta") or serialize_period_filter(period_filter)
        ),
    }


def _build_ratios_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {
            "financial_ratios": cache.get(
                "financial_ratios", FIELD_DEFAULTS["financial_ratios"]
            )
        }
    pnl_response = _build_pnl_summary_response(cache, period_filter=period_filter)
    working_capital_response = _recompute_suppliers_response(
        cache,
        period_filter,
        include_working_capital_fields=True,
    )
    pnl_period_meta = pnl_response.get("pnl_period_meta") or {}
    suppliers_period_meta = working_capital_response.get("suppliers_period_meta") or {}
    period_meta = serialize_period_filter(period_filter)
    period_meta["total_rows_seen"] = int(
        _coerce_float(pnl_period_meta.get("total_rows_seen"))
        + _coerce_float(suppliers_period_meta.get("total_rows_seen"))
    )
    period_meta["matched_rows"] = int(
        _coerce_float(pnl_period_meta.get("matched_rows"))
        + _coerce_float(suppliers_period_meta.get("matched_rows"))
    )
    period_meta["excluded_unparseable_count"] = int(
        _coerce_float(pnl_period_meta.get("excluded_unparseable_count"))
        + _coerce_float(suppliers_period_meta.get("excluded_unparseable_count"))
    )
    return {
        "financial_ratios": build_financial_ratios(
            pnl_response.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"]),
            working_capital_response.get(
                "supplier_aging", FIELD_DEFAULTS["supplier_aging"]
            ),
            working_capital_response.get(
                "ap_monthly_trend", FIELD_DEFAULTS["ap_monthly_trend"]
            ),
        ),
        "meta": working_capital_response.get("meta", {}),
        "ratios_period_meta": period_meta,
    }


def _build_valuation_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {
            "company_valuation": cache.get(
                "company_valuation", FIELD_DEFAULTS["company_valuation"]
            )
        }
    pnl_response = _build_pnl_summary_response(cache, period_filter=period_filter)
    working_capital_response = _recompute_suppliers_response(
        cache,
        period_filter,
        include_working_capital_fields=True,
    )
    monthly_pnl = pnl_response.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"])
    financial_ratios = build_financial_ratios(
        monthly_pnl,
        working_capital_response.get("supplier_aging", FIELD_DEFAULTS["supplier_aging"]),
        working_capital_response.get(
            "ap_monthly_trend", FIELD_DEFAULTS["ap_monthly_trend"]
        ),
    )
    forecast = build_forecast(monthly_pnl)
    pnl_period_meta = pnl_response.get("pnl_period_meta") or {}
    suppliers_period_meta = working_capital_response.get("suppliers_period_meta") or {}
    period_meta = serialize_period_filter(period_filter)
    period_meta["total_rows_seen"] = int(
        _coerce_float(pnl_period_meta.get("total_rows_seen"))
        + _coerce_float(suppliers_period_meta.get("total_rows_seen"))
    )
    period_meta["matched_rows"] = int(
        _coerce_float(pnl_period_meta.get("matched_rows"))
        + _coerce_float(suppliers_period_meta.get("matched_rows"))
    )
    period_meta["excluded_unparseable_count"] = int(
        _coerce_float(pnl_period_meta.get("excluded_unparseable_count"))
        + _coerce_float(suppliers_period_meta.get("excluded_unparseable_count"))
    )
    return {
        "company_valuation": build_company_valuation(
            monthly_pnl,
            financial_ratios,
            forecast,
            cache.get("sector_benchmarks") if isinstance(cache, dict) else None,
        ),
        "valuation_period_meta": period_meta,
    }


def _build_executive_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {
            "executive_summary": cache.get(
                "executive_summary", FIELD_DEFAULTS["executive_summary"]
            )
        }
    pnl_response = _build_pnl_summary_response(cache, period_filter=period_filter)
    working_capital_response = _recompute_suppliers_response(
        cache,
        period_filter,
        include_working_capital_fields=True,
    )
    monthly_pnl = pnl_response.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"])
    supplier_aging = working_capital_response.get(
        "supplier_aging", FIELD_DEFAULTS["supplier_aging"]
    )
    ap_monthly_trend = working_capital_response.get(
        "ap_monthly_trend", FIELD_DEFAULTS["ap_monthly_trend"]
    )
    financial_ratios = build_financial_ratios(
        monthly_pnl, supplier_aging, ap_monthly_trend
    )
    forecast = build_forecast(monthly_pnl)
    budget_config = cache.get("budget_config") or {}
    budget = build_budget(monthly_pnl, forecast, budget_config)
    company_valuation = build_company_valuation(
        monthly_pnl,
        financial_ratios,
        forecast,
        cache.get("sector_benchmarks") if isinstance(cache, dict) else None,
    )
    synthetic_data = {
        "monthly_pnl": monthly_pnl,
        "financial_ratios": financial_ratios,
        "forecast": forecast,
        "budget": budget,
        "company_valuation": company_valuation,
        "supplier_aging": supplier_aging,
        "tbc_expenses": cache.get("pnl_source_tbc_expenses")
        or cache.get("tbc_expenses")
        or {},
        "bog_expenses": cache.get("pnl_source_bog_expenses")
        or cache.get("bog_expenses")
        or {},
        "pos_terminal_income": cache.get("pnl_source_pos_terminal_income")
        or cache.get("pos_terminal_income")
        or {},
        "meta": cache.get("meta") or {},
        "bank_unmatched_analysis": cache.get("bank_unmatched_analysis") or {},
    }
    executive_summary = build_executive_summary(synthetic_data)
    pnl_period_meta = pnl_response.get("pnl_period_meta") or {}
    suppliers_period_meta = working_capital_response.get("suppliers_period_meta") or {}
    period_meta = serialize_period_filter(period_filter)
    period_meta["total_rows_seen"] = int(
        _coerce_float(pnl_period_meta.get("total_rows_seen"))
        + _coerce_float(suppliers_period_meta.get("total_rows_seen"))
    )
    period_meta["matched_rows"] = int(
        _coerce_float(pnl_period_meta.get("matched_rows"))
        + _coerce_float(suppliers_period_meta.get("matched_rows"))
    )
    period_meta["excluded_unparseable_count"] = int(
        _coerce_float(pnl_period_meta.get("excluded_unparseable_count"))
        + _coerce_float(suppliers_period_meta.get("excluded_unparseable_count"))
    )
    return {
        "executive_summary": executive_summary,
        "executive_period_meta": period_meta,
    }


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


def _known_imported_products_waybill_refs(cache):
    rows = cache.get("waybills") if isinstance(cache, dict) else None
    rows = rows if isinstance(rows, list) else []
    refs = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        ref = _normalize_waybill_ref(item.get("waybill_number"))
        if ref:
            refs.add(ref)
    return refs


def _resolve_imported_products_bundle(cache, period_filter=None):
    cached_bundle = cache.get("imported_products", FIELD_DEFAULTS["imported_products"])
    cached_bundle = (
        cached_bundle if isinstance(cached_bundle, dict) else FIELD_DEFAULTS["imported_products"]
    )
    if not bool((period_filter or {}).get("applied")):
        return cached_bundle
    return collect_imported_products_bundle(
        period_filter=period_filter,
        known_rs_refs=_known_imported_products_waybill_refs(cache),
    )


def _build_imported_products_response(cache, period_filter=None, **_kwargs):
    bundle = _resolve_imported_products_bundle(cache, period_filter=period_filter)
    return {"imported_products": _project_imported_products_summary(bundle)}


def _build_imported_products_full_response(cache, period_filter=None, **_kwargs):
    bundle = _resolve_imported_products_bundle(cache, period_filter=period_filter)
    return {"imported_products_full": bundle}


def _build_imported_products_supplier_detail_response(
    cache, tax_id=None, normalized_supplier=None, period_filter=None, **_kwargs
):
    bundle = _resolve_imported_products_bundle(cache, period_filter=period_filter)
    entry, match_type, ambiguous = _find_imported_products_supplier_entry(
        bundle, tax_id=tax_id, normalized_supplier=normalized_supplier
    )
    return {
        "imported_products_supplier_detail": {
            "label_ka": bundle.get("label_ka"),
            "supplier_top_products_limit": bundle.get("supplier_top_products_limit", 0),
            "truncation_suspected_any": bool(bundle.get("truncation_suspected_any")),
            "period_meta": dict(bundle.get("period_meta") or {}),
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
    cache, product_code=None, normalized_product=None, period_filter=None, **_kwargs
):
    bundle = _resolve_imported_products_bundle(cache, period_filter=period_filter)
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
            "period_meta": dict(bundle.get("period_meta") or {}),
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


def _build_retail_sales_response(cache, period_filter=None, **_kwargs):
    if bool((period_filter or {}).get("applied")):
        cached_bundle = cache.get("retail_sales") if isinstance(cache, dict) else {}
        bundle = collect_retail_sales_bundle(
            period_filter=period_filter,
            source_file_stats=(cached_bundle or {}).get("files"),
        )
    else:
        bundle = cache.get("retail_sales", FIELD_DEFAULTS["retail_sales"])
    return {"retail_sales": _project_retail_sales_summary(bundle)}


def _recompute_suppliers_response(
    cache, period_filter, include_working_capital_fields=False
):
    source_suppliers = cache.get("suppliers") if isinstance(cache, dict) else []
    source_waybills = cache.get("waybills") if isinstance(cache, dict) else []
    source_payment_rows = (
        cache.get("supplier_payment_rows") if isinstance(cache, dict) else []
    )
    source_payment_meta = (
        cache.get("supplier_payment_source_meta") or {} if isinstance(cache, dict) else {}
    )

    source_index, supplier_names = _build_supplier_source_index(source_suppliers)
    payment_name_hints = {}
    recomputed_rows = {}
    period_waybills = []
    total_rows_seen = 0
    matched_rows = 0
    excluded_unparseable_count = 0

    for item in source_waybills or []:
        if not isinstance(item, dict):
            continue
        total_rows_seen += 1
        in_period, unparseable = _row_within_period(item.get("date"), period_filter)
        if unparseable:
            excluded_unparseable_count += 1
            continue
        if not in_period:
            continue
        matched_rows += 1
        period_waybills.append(dict(item))
        org_name = str(item.get("supplier") or item.get("ორგანიზაცია") or "").strip()
        tax_id = str(_extract_tax_id_from_org(org_name) or "").strip()
        row_key = _supplier_response_key(tax_id=tax_id, org_name=org_name)
        if not row_key:
            continue
        if row_key not in recomputed_rows:
            base_row = _lookup_supplier_base_row(source_index, tax_id=tax_id, org_name=org_name)
            recomputed_rows[row_key] = _seed_supplier_response_row(
                base_row=base_row,
                org_name=org_name,
                tax_id=tax_id,
            )
        entry = recomputed_rows[row_key]
        nominal_amount = _coerce_float(item.get("nominal_amount"))
        effective_amount = _coerce_float(item.get("effective_amount"))
        cancelled = _waybill_is_cancelled(item)
        returned = _waybill_is_returned(item) and not cancelled
        entry["waybills_count"] += 0 if cancelled else 1
        entry["total_nominal"] += nominal_amount
        entry["total_cancelled"] += nominal_amount if cancelled else 0.0
        entry["total_returned"] += nominal_amount if returned else 0.0
        entry["total_effective"] += effective_amount
        if tax_id:
            supplier_names.setdefault(tax_id, org_name or tax_id)

    strict_payments = defaultdict(float)
    manual_payments = defaultdict(float)
    for item in source_payment_rows or []:
        if not isinstance(item, dict):
            continue
        total_rows_seen += 1
        in_period, unparseable = _row_within_period(item.get("row_date"), period_filter)
        if unparseable:
            excluded_unparseable_count += 1
            continue
        if not in_period:
            continue
        matched_rows += 1
        tax_id = str(item.get("matched_tax_id") or "").strip()
        if not tax_id:
            continue
        amount = _coerce_float(item.get("amount"))
        if amount == 0:
            continue
        supplier_name = str(
            item.get("matched_supplier_name") or item.get("company") or ""
        ).strip()
        if supplier_name:
            supplier_names.setdefault(tax_id, supplier_name)
            payment_name_hints.setdefault(tax_id, supplier_name)
        is_manual = str(item.get("source_bank") or "").strip() == "manual_journal"
        if is_manual:
            manual_payments[tax_id] += amount
        else:
            strict_payments[tax_id] += amount

    for tax_id in sorted(set(strict_payments.keys()) | set(manual_payments.keys())):
        org_name = supplier_names.get(tax_id) or payment_name_hints.get(tax_id) or ""
        row_key = _supplier_response_key(tax_id=tax_id, org_name=org_name)
        if not row_key:
            continue
        if row_key not in recomputed_rows:
            base_row = _lookup_supplier_base_row(source_index, tax_id=tax_id, org_name=org_name)
            if not org_name:
                org_name = str(base_row.get("ორგანიზაცია") or "").strip()
            if not org_name:
                org_name = f"({tax_id}) — არაა RS ზედნადებში"
            recomputed_rows[row_key] = _seed_supplier_response_row(
                base_row=base_row,
                org_name=org_name,
                tax_id=tax_id,
            )

    extra_supplier_count = 0
    for entry in recomputed_rows.values():
        tax_id = str(entry.get("tax_id") or _extract_tax_id_from_org(entry.get("ორგანიზაცია")) or "").strip()
        strict_amount = _coerce_float(strict_payments.get(tax_id)) if tax_id else 0.0
        manual_amount = _coerce_float(manual_payments.get(tax_id)) if tax_id else 0.0
        total_paid = strict_amount + manual_amount
        payment_scope = describe_supplier_payment_scope(strict_amount, manual_amount)
        entry["tax_id"] = tax_id or None
        entry["waybills_count"] = int(entry.get("waybills_count") or 0)
        entry["total_nominal"] = round(_coerce_float(entry.get("total_nominal")), 2)
        entry["total_cancelled"] = round(_coerce_float(entry.get("total_cancelled")), 2)
        entry["total_returned"] = round(_coerce_float(entry.get("total_returned")), 2)
        entry["total_effective"] = round(_coerce_float(entry.get("total_effective")), 2)
        entry["manual_paid"] = round(manual_amount, 2)
        entry["strict_bank_paid"] = round(strict_amount, 2)
        entry["bank_paid"] = round(strict_amount, 2)
        entry["total_paid"] = round(total_paid, 2)
        entry["total_debt"] = round(
            _coerce_float(entry.get("total_effective")) - total_paid,
            2,
        )
        entry["payment_scope"] = payment_scope.get("payment_scope")
        entry["payment_scope_note"] = payment_scope.get("payment_scope_note")
        supplier_names.setdefault(tax_id, entry.get("ორგანიზაცია") or tax_id)
        has_waybill_activity = any(
            abs(_coerce_float(entry.get(field))) > 0
            for field in (
                "total_nominal",
                "total_cancelled",
                "total_returned",
                "total_effective",
            )
        ) or int(entry.get("waybills_count") or 0) > 0
        if not has_waybill_activity and total_paid != 0:
            extra_supplier_count += 1

    suppliers = sorted(
        (dict(entry) for entry in recomputed_rows.values()),
        key=lambda item: (
            -_coerce_float(item.get("total_effective")),
            str(item.get("ორგანიზაცია") or ""),
        ),
    )
    supplier_aging_result = build_supplier_aging(suppliers, period_waybills)
    payment_scope_summary = build_payment_scope_summary(
        dict(strict_payments),
        dict(manual_payments),
        supplier_names=supplier_names,
    )
    combined_payments = defaultdict(float)
    for tax_id, amount in strict_payments.items():
        combined_payments[tax_id] += float(amount or 0)
    for tax_id, amount in manual_payments.items():
        combined_payments[tax_id] += float(amount or 0)
    ap_monthly_trend = build_ap_monthly_trend(
        period_waybills,
        dict(combined_payments),
        strict_bank_payments=dict(strict_payments),
        manual_payments=dict(manual_payments),
    )
    meta = dict(cache.get("meta") or {}) if isinstance(cache, dict) else {}
    meta["payment_scope_summary"] = payment_scope_summary
    meta["manual_payments_total"] = float(
        payment_scope_summary.get("manual_journal_total") or 0
    )
    meta["manual_payments_rows_with_amount"] = int(
        payment_scope_summary.get("manual_supplier_count") or 0
    )
    meta["suppliers_only_journal_or_bank"] = int(extra_supplier_count)
    meta["strict_bank_only_total"] = float(
        payment_scope_summary.get("strict_bank_only_total") or 0
    )
    meta["combined_supplier_paid_total"] = float(
        payment_scope_summary.get("combined_supplier_paid_total") or 0
    )
    meta["manual_vs_bank_gap_total"] = round(
        float(meta.get("combined_supplier_paid_total") or 0)
        - float(meta.get("strict_bank_only_total") or 0),
        2,
    )
    meta["period_caveat_ka"] = str(
        source_payment_meta.get("period_correctness_caveat_ka") or ""
    )
    period_meta = serialize_period_filter(period_filter)
    period_meta["total_rows_seen"] = int(total_rows_seen)
    period_meta["matched_rows"] = int(matched_rows)
    period_meta["excluded_unparseable_count"] = int(excluded_unparseable_count)
    response = {
        "suppliers": suppliers,
        "supplier_aging": supplier_aging_result.get("suppliers") or [],
        "meta": meta,
        "suppliers_period_meta": period_meta,
    }
    if include_working_capital_fields:
        response["aging_summary"] = dict(
            supplier_aging_result.get("summary") or FIELD_DEFAULTS["aging_summary"]
        )
        response["ap_monthly_trend"] = ap_monthly_trend
    return response


def _annotate_archive_flag(suppliers):
    archived_map = _load_supplier_archive()
    if not archived_map:
        for sup in suppliers:
            sup["archived"] = False
        return suppliers
    for sup in suppliers:
        tid = _extract_tax_id_from_org(sup.get("ორგანიზაცია"))
        sup["archived"] = bool(tid and tid in archived_map)
    return suppliers


def _build_suppliers_response(cache, period_filter=None, **_kwargs):
    concentration = cache.get(
        "supplier_concentration", FIELD_DEFAULTS["supplier_concentration"]
    )
    payment_lines = cache.get(
        "supplier_payment_lines", FIELD_DEFAULTS["supplier_payment_lines"]
    )
    waybill_lines = cache.get(
        "supplier_waybill_lines", FIELD_DEFAULTS["supplier_waybill_lines"]
    )
    supplier_invoices = cache.get(
        "supplier_invoices", FIELD_DEFAULTS["supplier_invoices"]
    )
    supplier_invoices_summary = cache.get(
        "supplier_invoices_summary", FIELD_DEFAULTS["supplier_invoices_summary"]
    )
    supplier_invoices_meta = cache.get(
        "supplier_invoices_meta", FIELD_DEFAULTS["supplier_invoices_meta"]
    )
    our_seller_invoices = cache.get(
        "our_seller_invoices", FIELD_DEFAULTS["our_seller_invoices"]
    )
    tbc_foodmart_cashback = cache.get(
        "tbc_foodmart_cashback", FIELD_DEFAULTS["tbc_foodmart_cashback"]
    )
    supplier_reconciliation = cache.get(
        "supplier_reconciliation", FIELD_DEFAULTS["supplier_reconciliation"]
    )
    if not bool((period_filter or {}).get("applied")):
        return {
            "suppliers": _annotate_archive_flag(
                list(cache.get("suppliers", FIELD_DEFAULTS["suppliers"]))
            ),
            "supplier_concentration": concentration,
            "supplier_payment_lines": payment_lines,
            "supplier_waybill_lines": waybill_lines,
            "supplier_invoices": supplier_invoices,
            "supplier_invoices_summary": supplier_invoices_summary,
            "supplier_invoices_meta": supplier_invoices_meta,
            "our_seller_invoices": our_seller_invoices,
            "tbc_foodmart_cashback": tbc_foodmart_cashback,
            "supplier_reconciliation": supplier_reconciliation,
        }
    recomputed = _recompute_suppliers_response(cache, period_filter)
    recomputed["suppliers"] = _annotate_archive_flag(
        list(recomputed.get("suppliers", []))
    )
    recomputed["supplier_concentration"] = concentration
    recomputed["supplier_payment_lines"] = payment_lines
    recomputed["supplier_waybill_lines"] = waybill_lines
    recomputed["supplier_invoices"] = supplier_invoices
    recomputed["supplier_invoices_summary"] = supplier_invoices_summary
    recomputed["supplier_invoices_meta"] = supplier_invoices_meta
    recomputed["our_seller_invoices"] = our_seller_invoices
    recomputed["tbc_foodmart_cashback"] = tbc_foodmart_cashback
    recomputed["supplier_reconciliation"] = supplier_reconciliation
    return recomputed


def _build_working_capital_response(cache, period_filter=None, **_kwargs):
    if not bool((period_filter or {}).get("applied")):
        return {
            "supplier_aging": cache.get(
                "supplier_aging", FIELD_DEFAULTS["supplier_aging"]
            ),
            "aging_summary": cache.get("aging_summary", FIELD_DEFAULTS["aging_summary"]),
            "ap_monthly_trend": cache.get(
                "ap_monthly_trend", FIELD_DEFAULTS["ap_monthly_trend"]
            ),
        }
    recomputed = _recompute_suppliers_response(
        cache,
        period_filter,
        include_working_capital_fields=True,
    )
    return {
        "supplier_aging": recomputed.get(
            "supplier_aging", FIELD_DEFAULTS["supplier_aging"]
        ),
        "aging_summary": recomputed.get("aging_summary", FIELD_DEFAULTS["aging_summary"]),
        "ap_monthly_trend": recomputed.get(
            "ap_monthly_trend", FIELD_DEFAULTS["ap_monthly_trend"]
        ),
        "meta": recomputed.get("meta", {}),
        "working_capital_period_meta": recomputed.get(
            "suppliers_period_meta",
            serialize_period_filter(period_filter),
        ),
    }


SPECIAL_TAB_BUILDERS = {
    "suppliers": _build_suppliers_response,
    "working_capital": _build_working_capital_response,
    "cashflow_summary": _build_cashflow_summary_response,
    "cashflow_tbc_expenses_detail": _build_cashflow_tbc_expenses_detail_response,
    "cashflow_bank_unmatched_detail": _build_cashflow_bank_unmatched_detail_response,
    "pnl_summary": _build_pnl_summary_response,
    "ratios": _build_ratios_response,
    "forecast": _build_forecast_response,
    "budget": _build_budget_response,
    "valuation": _build_valuation_response,
    "executive": _build_executive_response,
    "waybills": _build_waybills_response,
    "imported_products": _build_imported_products_response,
    "imported_products_full": _build_imported_products_full_response,
    "imported_products_supplier_detail": _build_imported_products_supplier_detail_response,
    "imported_products_product_detail": _build_imported_products_product_detail_response,
    "retail_sales": _build_retail_sales_response,
}

ALLOWED_TABS = sorted(set(TAB_ALLOWLIST) | set(SPECIAL_TAB_BUILDERS))


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
    from_date=None,
    to_date=None,
    from_time=None,
    to_time=None,
):
    period_filter = build_period_filter(
        from_date=from_date,
        to_date=to_date,
        from_time=from_time,
        to_time=to_time,
    )
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
                period_filter=period_filter,
            )
        )
    else:
        for field in TAB_ALLOWLIST[tab]:
            response[field] = cache.get(field, FIELD_DEFAULTS.get(field, {}))
    period_meta = _resolve_response_period_meta(tab, response, period_filter)
    period_caveat_ka = _merge_non_empty_text(
        build_period_caveat_ka(period_meta),
        (response.get("meta") or {}).get("period_caveat_ka"),
    )
    data_period_label = _resolve_data_period_label(response.get("meta"), period_meta)
    response["meta"]["data_period_label"] = data_period_label
    response["meta"]["period"] = (
        dict(period_meta) if isinstance(period_meta, dict) else {}
    )
    response["meta"]["period_caveat_ka"] = period_caveat_ka
    response["response_meta"] = _build_response_meta(
        cache,
        tab,
        response,
        period_meta=period_meta,
        period_caveat_ka=period_caveat_ka,
        data_period_label=data_period_label,
    )
    return response


def build_static_api_artifacts(cache):
    artifacts = {}
    for tab in sorted(STATIC_RESPONSE_TABS):
        artifacts[tab] = build_response_for_tab(cache, tab)
    artifacts["suppliers_source"] = {
        **_base_response(cache),
        "suppliers": cache.get("suppliers", FIELD_DEFAULTS["suppliers"]),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
        "supplier_payment_rows": cache.get("supplier_payment_rows", []),
        "supplier_payment_source_meta": cache.get("supplier_payment_source_meta", {}),
    }
    artifacts["waybills_source"] = {
        **_base_response(cache),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
    }
    artifacts["pnl_source"] = {
        **_base_response(cache),
        "pos_terminal_income": cache.get(
            "pnl_source_pos_terminal_income",
            FIELD_DEFAULTS["pos_terminal_income"],
        ),
        "tbc_expenses": cache.get(
            "pnl_source_tbc_expenses",
            FIELD_DEFAULTS["tbc_expenses"],
        ),
        "bog_expenses": cache.get(
            "pnl_source_bog_expenses",
            FIELD_DEFAULTS["bog_expenses"],
        ),
        "object_mapping": cache.get("pnl_source_object_mapping", {}),
    }
    artifacts["forecast_source"] = {
        **_base_response(cache),
        "forecast": cache.get("forecast", FIELD_DEFAULTS["forecast"]),
        "monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"]),
        "pos_terminal_income": cache.get(
            "pnl_source_pos_terminal_income",
            FIELD_DEFAULTS["pos_terminal_income"],
        ),
        "tbc_expenses": cache.get(
            "pnl_source_tbc_expenses",
            FIELD_DEFAULTS["tbc_expenses"],
        ),
        "bog_expenses": cache.get(
            "pnl_source_bog_expenses",
            FIELD_DEFAULTS["bog_expenses"],
        ),
        "object_mapping": cache.get("pnl_source_object_mapping", {}),
    }
    artifacts["budget_source"] = {
        **_base_response(cache),
        "budget": cache.get("budget", FIELD_DEFAULTS["budget"]),
        "forecast": cache.get("forecast", FIELD_DEFAULTS["forecast"]),
        "monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"]),
        "pos_terminal_income": cache.get(
            "pnl_source_pos_terminal_income",
            FIELD_DEFAULTS["pos_terminal_income"],
        ),
        "tbc_expenses": cache.get(
            "pnl_source_tbc_expenses",
            FIELD_DEFAULTS["tbc_expenses"],
        ),
        "bog_expenses": cache.get(
            "pnl_source_bog_expenses",
            FIELD_DEFAULTS["bog_expenses"],
        ),
        "object_mapping": cache.get("pnl_source_object_mapping", {}),
        "budget_config": cache.get("budget_config", {}),
    }
    artifacts["ratios_source"] = {
        **_base_response(cache),
        "financial_ratios": cache.get(
            "financial_ratios", FIELD_DEFAULTS["financial_ratios"]
        ),
        "suppliers": cache.get("suppliers", FIELD_DEFAULTS["suppliers"]),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
        "supplier_payment_rows": cache.get("supplier_payment_rows", []),
        "supplier_payment_source_meta": cache.get(
            "supplier_payment_source_meta", {}
        ),
        "pos_terminal_income": cache.get(
            "pnl_source_pos_terminal_income",
            FIELD_DEFAULTS["pos_terminal_income"],
        ),
        "tbc_expenses": cache.get(
            "pnl_source_tbc_expenses",
            FIELD_DEFAULTS["tbc_expenses"],
        ),
        "bog_expenses": cache.get(
            "pnl_source_bog_expenses",
            FIELD_DEFAULTS["bog_expenses"],
        ),
        "object_mapping": cache.get("pnl_source_object_mapping", {}),
    }
    artifacts["valuation_source"] = {
        **_base_response(cache),
        "company_valuation": cache.get(
            "company_valuation", FIELD_DEFAULTS["company_valuation"]
        ),
        "financial_ratios": cache.get(
            "financial_ratios", FIELD_DEFAULTS["financial_ratios"]
        ),
        "forecast": cache.get("forecast", FIELD_DEFAULTS["forecast"]),
        "monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"]),
        "suppliers": cache.get("suppliers", FIELD_DEFAULTS["suppliers"]),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
        "supplier_payment_rows": cache.get("supplier_payment_rows", []),
        "supplier_payment_source_meta": cache.get(
            "supplier_payment_source_meta", {}
        ),
        "pos_terminal_income": cache.get(
            "pnl_source_pos_terminal_income",
            FIELD_DEFAULTS["pos_terminal_income"],
        ),
        "tbc_expenses": cache.get(
            "pnl_source_tbc_expenses",
            FIELD_DEFAULTS["tbc_expenses"],
        ),
        "bog_expenses": cache.get(
            "pnl_source_bog_expenses",
            FIELD_DEFAULTS["bog_expenses"],
        ),
        "object_mapping": cache.get("pnl_source_object_mapping", {}),
        "sector_benchmarks": cache.get("sector_benchmarks", {}),
    }
    artifacts["executive_source"] = {
        **_base_response(cache),
        "executive_summary": cache.get(
            "executive_summary", FIELD_DEFAULTS["executive_summary"]
        ),
        "company_valuation": cache.get(
            "company_valuation", FIELD_DEFAULTS["company_valuation"]
        ),
        "financial_ratios": cache.get(
            "financial_ratios", FIELD_DEFAULTS["financial_ratios"]
        ),
        "forecast": cache.get("forecast", FIELD_DEFAULTS["forecast"]),
        "budget": cache.get("budget", FIELD_DEFAULTS["budget"]),
        "budget_config": cache.get("budget_config", {}),
        "monthly_pnl": cache.get("monthly_pnl", FIELD_DEFAULTS["monthly_pnl"]),
        "supplier_aging": cache.get("supplier_aging", FIELD_DEFAULTS["supplier_aging"]),
        "suppliers": cache.get("suppliers", FIELD_DEFAULTS["suppliers"]),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
        "supplier_payment_rows": cache.get("supplier_payment_rows", []),
        "supplier_payment_source_meta": cache.get(
            "supplier_payment_source_meta", {}
        ),
        "pos_terminal_income": cache.get(
            "pnl_source_pos_terminal_income",
            FIELD_DEFAULTS["pos_terminal_income"],
        ),
        "tbc_expenses": cache.get(
            "pnl_source_tbc_expenses",
            FIELD_DEFAULTS["tbc_expenses"],
        ),
        "bog_expenses": cache.get(
            "pnl_source_bog_expenses",
            FIELD_DEFAULTS["bog_expenses"],
        ),
        "object_mapping": cache.get("pnl_source_object_mapping", {}),
        "sector_benchmarks": cache.get("sector_benchmarks", {}),
        "bank_unmatched_analysis": cache.get(
            "bank_unmatched_analysis", FIELD_DEFAULTS["bank_unmatched_analysis"]
        ),
    }
    artifacts["imported_products_source"] = {
        **_base_response(cache),
        "waybills": cache.get("waybills", FIELD_DEFAULTS["waybills"]),
        "imported_products": cache.get(
            "imported_products", FIELD_DEFAULTS["imported_products"]
        ),
    }
    artifacts["retail_sales_source"] = {
        **_base_response(cache),
        "retail_sales": cache.get("retail_sales", FIELD_DEFAULTS["retail_sales"]),
    }
    return artifacts
