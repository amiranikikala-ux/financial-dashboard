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
    # Pass-through data-quality block surfaced by synthesize_from_megaplus —
    # used by the UI to warn that NULL-timestamp + legacy-pre-2023 rows are
    # in the totals but invisible in time-series charts.
    dq = bundle.get("data_quality")
    if isinstance(dq, dict):
        summary["data_quality"] = dq
    # Pass-through analytics blocks — basket / payment / time / concentration
    # / forward-looking (forecast / spike / mover / slow_mover).
    for key in (
        "basket_metrics",
        "payment_breakdown",
        "dow_breakdown",
        "hour_breakdown",
        "daily_trend",
        "calendar_heatmap",
        "returns_voids",
        "discount_totals",
        "concentration",
        "registers_per_object",
        "cashiers_per_object",
        "prev_period_compare",
        "spike_alerts",
        "forecast_next30",
        "slow_movers",
        "top_recent_movers",
        "hour_dow_grid",
        "per_object_view",
        "shifts",
        "shift_summary",
        "shift_anomalies",
        "vat_totals",
        "vat_by_month",
        "vat_by_category",
        "returns_by_product",
        "returns_by_cashier",
        "returns_by_month",
        "discount_by_category",
        "discount_lift_summary",
        "by_product_by_month",
    ):
        val = bundle.get(key)
        if val is not None:
            summary[key] = val
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
        "delivery_location": item.get("delivery_location"),
        "store": item.get("store"),
        "is_return": bool(item.get("is_return")),
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


def _build_waybill_store_breakdown(rows):
    breakdown = {}
    for item in rows:
        store_name = _clean_lookup_text(item.get("store")) or "უცნობი"
        entry = breakdown.setdefault(
            store_name,
            {"store": store_name, "row_count": 0, "effective_amount": 0.0},
        )
        entry["row_count"] += 1
        entry["effective_amount"] += _waybill_numeric_value(item, "effective_amount")
    return sorted(
        breakdown.values(),
        key=lambda v: (-float(v.get("effective_amount") or 0), str(v.get("store") or "")),
    )


def _build_waybill_type_breakdown(rows):
    breakdown = {}
    for item in rows:
        wb_type = _clean_lookup_text(item.get("type")) or "უცნობი"
        entry = breakdown.setdefault(
            wb_type,
            {"type": wb_type, "row_count": 0, "effective_amount": 0.0},
        )
        entry["row_count"] += 1
        entry["effective_amount"] += _waybill_numeric_value(item, "effective_amount")
    return sorted(
        breakdown.values(),
        key=lambda v: (-int(v.get("row_count") or 0), str(v.get("type") or "")),
    )


def _build_waybill_calendar_heatmap(rows):
    """Daily activity for the last 365 days from the latest waybill date.

    Returns list of {date, count, amount} ordered by date ascending. Frontend
    renders this as a GitHub-style calendar heatmap.
    """
    from datetime import datetime as _dt, timedelta as _td

    if not rows:
        return []
    max_d = ""
    by_day = {}
    for r in rows:
        d = str(r.get("date") or "")[:10]
        if not d:
            continue
        if d > max_d:
            max_d = d
        e = by_day.setdefault(d, {"count": 0, "amount": 0.0})
        e["count"] += 1
        e["amount"] += _waybill_amount_value(r)
    if not max_d:
        return []
    try:
        end_dt = _dt.strptime(max_d, "%Y-%m-%d")
    except ValueError:
        return []
    start_dt = end_dt - _td(days=364)
    out = []
    cur = start_dt
    while cur <= end_dt:
        ds = cur.strftime("%Y-%m-%d")
        e = by_day.get(ds, {"count": 0, "amount": 0.0})
        out.append({
            "date": ds,
            "count": e["count"],
            "amount": round(e["amount"], 2),
            "weekday": cur.weekday(),
        })
        cur += _td(days=1)
    return out


def _build_waybill_duplicate_candidates(rows):
    """Group waybills with identical supplier+date+amount. Returns groups
    with 2+ candidates so the owner can verify whether they're real
    duplicates or coincidence."""
    grouped = {}
    for r in rows:
        sup = str(r.get("supplier") or "").strip()
        d = str(r.get("date") or "")[:10]
        amt = round(_waybill_amount_value(r), 2)
        if not sup or not d or amt == 0:
            continue
        key = (sup, d, amt)
        grouped.setdefault(key, []).append({
            "waybill_number": str(r.get("waybill_number") or ""),
            "status": str(r.get("status") or ""),
            "type": str(r.get("type") or ""),
            "store": str(r.get("store") or ""),
        })
    duplicates = []
    for (sup, d, amt), entries in grouped.items():
        if len(entries) < 2:
            continue
        duplicates.append({
            "supplier": sup,
            "date": d,
            "amount": amt,
            "count": len(entries),
            "total_amount": round(amt * len(entries), 2),
            "waybill_numbers": [e["waybill_number"] for e in entries],
            "stores": list({e["store"] for e in entries if e["store"]}),
        })
    duplicates.sort(key=lambda x: (-x["count"], -abs(x["amount"])))
    return duplicates[:50]


def _build_waybill_month_benchmark(rows):
    """Z-score and percentile of last complete month vs prior 12 months.

    Compares only sums (positive amounts, returns excluded). Returns dict
    with reference month, its amount, mean/std of prior, z-score, rank,
    and percentile. Empty dict if not enough data.
    """
    from datetime import datetime as _dt
    import statistics as _stats

    monthly = {}
    max_d = ""
    for r in rows:
        d = str(r.get("date") or "")[:10]
        if len(d) < 7 or r.get("is_return"):
            continue
        if d > max_d:
            max_d = d
        ym = d[:7]
        monthly[ym] = monthly.get(ym, 0.0) + _waybill_amount_value(r)
    if not max_d or len(max_d) < 10 or len(monthly) < 4:
        return {}
    try:
        max_dt = _dt.strptime(max_d, "%Y-%m-%d")
    except ValueError:
        return {}
    if max_dt.day <= 20:
        if max_dt.month == 1:
            ref_year, ref_month = max_dt.year - 1, 12
        else:
            ref_year, ref_month = max_dt.year, max_dt.month - 1
        ref_ym = f"{ref_year:04d}-{ref_month:02d}"
    else:
        ref_ym = max_d[:7]
    if ref_ym not in monthly:
        return {}
    current_amount = monthly[ref_ym]
    prior_months = sorted([(ym, v) for ym, v in monthly.items() if ym < ref_ym])
    # Use the trailing 12 months max for stable benchmarking
    prior_months = prior_months[-12:]
    if len(prior_months) < 3:
        return {}
    prior_values = [v for _, v in prior_months]
    mean_prior = _stats.mean(prior_values)
    try:
        std_prior = _stats.pstdev(prior_values) if len(prior_values) > 1 else 0.0
    except _stats.StatisticsError:
        std_prior = 0.0
    z_score = round((current_amount - mean_prior) / std_prior, 2) if std_prior else 0.0
    # Rank among prior + current; lower rank = larger value
    all_values = prior_values + [current_amount]
    sorted_vals = sorted(all_values, reverse=True)
    rank = sorted_vals.index(current_amount) + 1
    percentile = round((1 - (rank - 1) / len(sorted_vals)) * 100.0, 1)
    if z_score >= 1.5:
        verdict = "გაცილებით მეტი ვიდრე ჩვეულებრივ"
        verdict_tone = "pos"
    elif z_score >= 0.5:
        verdict = "ოდნავ მეტი ვიდრე ჩვეულებრივ"
        verdict_tone = "pos"
    elif z_score <= -1.5:
        verdict = "გაცილებით ნაკლები ვიდრე ჩვეულებრივ"
        verdict_tone = "neg"
    elif z_score <= -0.5:
        verdict = "ოდნავ ნაკლები ვიდრე ჩვეულებრივ"
        verdict_tone = "neg"
    else:
        verdict = "ჩვეულებრივი დონე"
        verdict_tone = "neutral"
    return {
        "ref_month": ref_ym,
        "ref_amount": round(current_amount, 2),
        "mean_prior_12m": round(mean_prior, 2),
        "std_prior_12m": round(std_prior, 2),
        "z_score": z_score,
        "rank": rank,
        "total_compared": len(sorted_vals),
        "percentile": percentile,
        "verdict_ka": verdict,
        "verdict_tone": verdict_tone,
    }


def _build_waybill_anomaly_data(rows, all_rows):
    """Top-10 single largest waybills (outliers) + spike alerts.

    A spike = supplier whose current-month amount is at least 2× their
    historical monthly average (computed from prior months in all_rows).
    Returns ``top_largest_waybills`` list and ``spike_alerts`` list.
    """
    from datetime import datetime as _dt

    # Top-10 largest single waybills (sorted by absolute amount, returns excluded
    # because their negative values would dominate "smallest" not "largest").
    largest = sorted(
        (r for r in rows if not r.get("is_return")),
        key=lambda r: _waybill_amount_value(r),
        reverse=True,
    )[:10]
    top_largest = [
        {
            "date": str(r.get("date") or "")[:10],
            "supplier": str(r.get("supplier") or ""),
            "waybill_number": str(r.get("waybill_number") or ""),
            "amount": round(_waybill_amount_value(r), 2),
            "store": str(r.get("store") or ""),
            "status": str(r.get("status") or ""),
        }
        for r in largest
    ]

    # Spike alerts: for each supplier, look at their current-month total vs
    # their historical monthly average from earlier months. Flag suppliers
    # whose current-month amount is >= 2× average AND average > 0.
    if not all_rows:
        return {"top_largest_waybills": top_largest, "spike_alerts": []}

    max_d = ""
    for r in all_rows:
        d = str(r.get("date") or "")[:10]
        if d and d > max_d:
            max_d = d
    if not max_d or len(max_d) < 10:
        return {"top_largest_waybills": top_largest, "spike_alerts": []}

    # Use the last *complete* month so partial current-month data doesn't
    # produce false negatives. If today is the 1st-20th, "last complete"
    # is the previous calendar month.
    try:
        max_dt = _dt.strptime(max_d, "%Y-%m-%d")
    except ValueError:
        return {"top_largest_waybills": top_largest, "spike_alerts": []}
    if max_dt.day <= 20:
        if max_dt.month == 1:
            ref_year, ref_month = max_dt.year - 1, 12
        else:
            ref_year, ref_month = max_dt.year, max_dt.month - 1
        ref_ym = f"{ref_year:04d}-{ref_month:02d}"
    else:
        ref_ym = max_d[:7]

    # Aggregate per supplier per month
    sup_month_amount = {}
    for r in all_rows:
        if r.get("is_return"):
            continue
        d = str(r.get("date") or "")[:10]
        if len(d) < 7:
            continue
        sup = str(r.get("supplier") or "").strip()
        if not sup:
            continue
        amt = _waybill_amount_value(r)
        ym = d[:7]
        sup_month_amount.setdefault(sup, {})
        sup_month_amount[sup][ym] = sup_month_amount[sup].get(ym, 0.0) + amt

    spike_alerts = []
    for sup, by_ym in sup_month_amount.items():
        prior = [v for ym, v in by_ym.items() if ym < ref_ym]
        current = by_ym.get(ref_ym, 0.0)
        if not prior or current <= 0:
            continue
        avg_prior = sum(prior) / len(prior)
        if avg_prior <= 0:
            continue
        ratio = current / avg_prior
        if ratio >= 2.0:
            spike_alerts.append({
                "supplier": sup,
                "current_amount": round(current, 2),
                "avg_prior": round(avg_prior, 2),
                "ratio": round(ratio, 2),
                "current_month": ref_ym,
                "prior_months": len(prior),
            })
    spike_alerts.sort(key=lambda x: x["ratio"], reverse=True)
    spike_alerts = spike_alerts[:20]

    return {"top_largest_waybills": top_largest, "spike_alerts": spike_alerts}


def _build_waybill_supplier_analytics(rows, all_rows):
    """Compute per-supplier rankings, HHI concentration, Pareto cumulative,
    new-supplier and silent-supplier insights."""
    from datetime import datetime as _dt

    by_sup = {}
    for r in rows:
        sup = str(r.get("supplier") or "").strip()
        if not sup:
            continue
        amt = _waybill_amount_value(r)
        d = str(r.get("date") or "")[:10]
        e = by_sup.setdefault(
            sup,
            {"supplier": sup, "count": 0, "amount": 0.0, "first_date": d, "last_date": d, "return_count": 0},
        )
        e["count"] += 1
        e["amount"] += amt
        if r.get("is_return"):
            e["return_count"] += 1
        if d:
            if not e["first_date"] or d < e["first_date"]:
                e["first_date"] = d
            if not e["last_date"] or d > e["last_date"]:
                e["last_date"] = d

    sup_list = sorted(by_sup.values(), key=lambda x: x["amount"], reverse=True)
    total = sum(s["amount"] for s in sup_list)

    # Top 10
    top10 = []
    for s in sup_list[:10]:
        top10.append({
            "supplier": s["supplier"],
            "amount": round(s["amount"], 2),
            "count": s["count"],
            "share_pct": round((s["amount"] / total) * 100.0, 2) if total else 0.0,
        })

    # Pareto: cumulative share
    pareto = []
    cum = 0.0
    cum_count_at_80 = None
    for i, s in enumerate(sup_list, start=1):
        cum += s["amount"]
        cum_pct = (cum / total) * 100.0 if total else 0.0
        pareto.append({
            "rank": i,
            "supplier": s["supplier"],
            "amount": round(s["amount"], 2),
            "cumulative_pct": round(cum_pct, 2),
        })
        if cum_count_at_80 is None and cum_pct >= 80.0:
            cum_count_at_80 = i

    # HHI: sum of squared market shares (out of 10000). >2500 = highly concentrated
    if total > 0:
        hhi = round(sum(((s["amount"] / total) * 100.0) ** 2 for s in sup_list), 2)
    else:
        hhi = 0.0
    if hhi >= 2500:
        hhi_class = "მაღალი კონცენტრაცია"
    elif hhi >= 1500:
        hhi_class = "საშუალო"
    else:
        hhi_class = "დაბალი (დივერსიფიცირებული)"

    # New-suppliers per month: month each supplier appeared for the first time
    # (within filtered rows)
    new_per_month = {}
    for s in sup_list:
        fd = s.get("first_date") or ""
        if len(fd) >= 7:
            ym = fd[:7]
            new_per_month[ym] = new_per_month.get(ym, 0) + 1
    new_suppliers_monthly = [
        {"month": k, "new_suppliers": v}
        for k, v in sorted(new_per_month.items())
    ]

    # Silent suppliers — using ALL rows so we know "last seen ever", not just
    # in the current period. Threshold = max_date - 90 days.
    silent_suppliers = []
    max_date = ""
    last_by_sup = {}
    for r in all_rows:
        sup = str(r.get("supplier") or "").strip()
        d = str(r.get("date") or "")[:10]
        if not sup or not d:
            continue
        if d > max_date:
            max_date = d
        if d > last_by_sup.get(sup, ""):
            last_by_sup[sup] = d
    if max_date:
        try:
            cutoff = (_dt.strptime(max_date, "%Y-%m-%d") - __import__("datetime").timedelta(days=90)).strftime("%Y-%m-%d")
        except ValueError:
            cutoff = ""
        if cutoff:
            for sup, ld in last_by_sup.items():
                if ld < cutoff:
                    days = 0
                    try:
                        days = (_dt.strptime(max_date, "%Y-%m-%d") - _dt.strptime(ld, "%Y-%m-%d")).days
                    except ValueError:
                        pass
                    silent_suppliers.append({"supplier": sup, "last_date": ld, "days_silent": days})
            silent_suppliers.sort(key=lambda x: x["days_silent"], reverse=True)
    silent_suppliers = silent_suppliers[:30]

    # Reliability: cancellation/return rate per supplier (top 20 by amount)
    # Cancellation pulled from status field across this supplier's filtered rows.
    sup_status = {}
    for r in rows:
        sup = str(r.get("supplier") or "").strip()
        if not sup:
            continue
        sup_status.setdefault(sup, {"cancelled": 0, "total": 0})
        sup_status[sup]["total"] += 1
        if "გაუქმებული" in str(r.get("status") or ""):
            sup_status[sup]["cancelled"] += 1
    reliability = []
    for s in sup_list[:20]:
        st = sup_status.get(s["supplier"], {"cancelled": 0, "total": 0})
        cancel_pct = (st["cancelled"] / st["total"]) * 100.0 if st["total"] else 0.0
        return_pct = (s["return_count"] / s["count"]) * 100.0 if s["count"] else 0.0
        score = round(100.0 - cancel_pct - (return_pct * 0.5), 2)
        reliability.append({
            "supplier": s["supplier"],
            "amount": round(s["amount"], 2),
            "count": s["count"],
            "cancel_pct": round(cancel_pct, 2),
            "return_pct": round(return_pct, 2),
            "reliability_score": max(0.0, min(100.0, score)),
        })

    return {
        "top_suppliers": top10,
        "supplier_count_total": len(sup_list),
        "supplier_count_for_80pct": cum_count_at_80,
        "pareto": pareto[:50],
        "hhi": hhi,
        "hhi_class": hhi_class,
        "new_suppliers_monthly": new_suppliers_monthly,
        "silent_suppliers": silent_suppliers,
        "supplier_reliability": reliability,
    }


def _build_waybill_quality_trends(rows):
    """Monthly cancellation % and return % trends + type breakdown summary."""
    monthly = {}
    for r in rows:
        d = str(r.get("date") or "")[:10]
        if len(d) < 7:
            continue
        ym = d[:7]
        e = monthly.setdefault(
            ym,
            {"month": ym, "total": 0, "cancelled": 0, "returns": 0, "amount": 0.0, "return_amount": 0.0},
        )
        e["total"] += 1
        e["amount"] += _waybill_amount_value(r)
        if "გაუქმებული" in str(r.get("status") or ""):
            e["cancelled"] += 1
        if r.get("is_return"):
            e["returns"] += 1
            e["return_amount"] += _waybill_amount_value(r)
    out = []
    for ym in sorted(monthly):
        m = monthly[ym]
        cancel_pct = (m["cancelled"] / m["total"]) * 100.0 if m["total"] else 0.0
        return_pct = (m["returns"] / m["total"]) * 100.0 if m["total"] else 0.0
        out.append({
            "month": ym,
            "total": m["total"],
            "cancelled": m["cancelled"],
            "returns": m["returns"],
            "cancel_pct": round(cancel_pct, 2),
            "return_pct": round(return_pct, 2),
            "amount": round(m["amount"], 2),
            "return_amount": round(m["return_amount"], 2),
        })
    return out


def _build_waybill_chart_data(rows):
    """Pre-aggregate filtered waybills for chart rendering on the frontend.

    Returns dict with keys: monthly_trend, yearly_comparison, quarterly_trend,
    day_of_week, store_monthly. Each is shaped for direct use in recharts.
    """
    from datetime import datetime as _dt

    monthly = {}
    yearly_by_month = {}
    quarterly = {}
    dow_count = [0] * 7
    dow_amount = [0.0] * 7
    store_monthly = {}

    for r in rows:
        d = str(r.get("date") or "")[:10]
        if not d:
            continue
        try:
            dt = _dt.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        amt = _waybill_amount_value(r)
        store_name = str(r.get("store") or "უცნობი") or "უცნობი"

        ym = d[:7]
        m_entry = monthly.setdefault(
            ym, {"month": ym, "count": 0, "amount": 0.0, "return_count": 0, "return_amount": 0.0}
        )
        m_entry["count"] += 1
        m_entry["amount"] += amt
        if r.get("is_return"):
            m_entry["return_count"] += 1
            m_entry["return_amount"] += amt

        y = d[:4]
        m_num = int(d[5:7])
        yearly_by_month.setdefault(m_num, {})
        yearly_by_month[m_num][y] = yearly_by_month[m_num].get(y, 0.0) + amt

        q_idx = (dt.month - 1) // 3 + 1
        qkey = f"{y}-Q{q_idx}"
        q_entry = quarterly.setdefault(
            qkey, {"quarter": qkey, "count": 0, "amount": 0.0}
        )
        q_entry["count"] += 1
        q_entry["amount"] += amt

        dow_idx = dt.weekday()
        dow_count[dow_idx] += 1
        dow_amount[dow_idx] += amt

        store_monthly.setdefault(store_name, {})
        store_monthly[store_name][ym] = store_monthly[store_name].get(ym, 0.0) + amt

    # Sort monthly + add 3-month moving average
    monthly_sorted = sorted(monthly.values(), key=lambda x: x["month"])
    for i, m in enumerate(monthly_sorted):
        window = monthly_sorted[max(0, i - 2): i + 1]
        m["ma3_amount"] = round(sum(w["amount"] for w in window) / len(window), 2)
        m["amount"] = round(m["amount"], 2)
        m["return_amount"] = round(m["return_amount"], 2)

    # Yearly comparison reshape: list of 12 month rows with year columns
    month_short_ka = ["იან", "თებ", "მარ", "აპრ", "მაი", "ივნ", "ივლ", "აგვ", "სექ", "ოქტ", "ნოე", "დეკ"]
    years_present = sorted({y for m_data in yearly_by_month.values() for y in m_data})
    yearly_chart = []
    for m_num in range(1, 13):
        row = {"month": month_short_ka[m_num - 1], "month_num": m_num}
        for y in years_present:
            row[y] = round((yearly_by_month.get(m_num) or {}).get(y, 0.0), 2)
        yearly_chart.append(row)

    # Day-of-week
    dow_labels = ["ორშ", "სამ", "ოთხ", "ხუთ", "პარ", "შაბ", "კვი"]
    dow_data = [
        {"day": dow_labels[i], "day_idx": i, "count": dow_count[i], "amount": round(dow_amount[i], 2)}
        for i in range(7)
    ]

    # Store-monthly stacked: list of months with one column per store
    all_months = sorted({ym for s_data in store_monthly.values() for ym in s_data})
    store_keys = sorted(store_monthly.keys())
    store_monthly_chart = []
    for ym in all_months:
        row = {"month": ym}
        for store_key in store_keys:
            row[store_key] = round(store_monthly[store_key].get(ym, 0.0), 2)
        store_monthly_chart.append(row)

    quarterly_sorted = sorted(quarterly.values(), key=lambda x: x["quarter"])
    for q in quarterly_sorted:
        q["amount"] = round(q["amount"], 2)

    return {
        "monthly_trend": monthly_sorted,
        "yearly_comparison": yearly_chart,
        "yearly_keys": years_present,
        "quarterly_trend": quarterly_sorted,
        "day_of_week": dow_data,
        "store_monthly": store_monthly_chart,
        "store_keys": store_keys,
    }


def _build_waybill_extra_kpis(filtered_rows, period_filter, all_rows):
    """Compute extra KPIs: avg/median/max amount, return rate, daily avg count,
    active/new suppliers, period-over-period velocity."""
    import statistics as _stats
    from datetime import datetime as _dt, timedelta as _td

    amounts = [_waybill_amount_value(r) for r in filtered_rows]
    return_count = sum(1 for r in filtered_rows if r.get("is_return"))
    return_amount = sum(_waybill_amount_value(r) for r in filtered_rows if r.get("is_return"))

    # Date range from filtered rows
    dates_iso = [str(r.get("date") or "")[:10] for r in filtered_rows if r.get("date")]
    dates_iso = [d for d in dates_iso if d]
    if dates_iso:
        min_date = min(dates_iso)
        max_date = max(dates_iso)
        try:
            d1 = _dt.strptime(min_date, "%Y-%m-%d")
            d2 = _dt.strptime(max_date, "%Y-%m-%d")
            day_span = max(1, (d2 - d1).days + 1)
        except ValueError:
            day_span = 1
    else:
        min_date = max_date = ""
        day_span = 1

    # Suppliers in current filtered set
    current_suppliers = set()
    for r in filtered_rows:
        sup = str(r.get("supplier") or "")
        if sup:
            current_suppliers.add(sup)

    # New suppliers: appear in filtered but not in all_rows BEFORE min_date.
    # Only meaningful when a period filter is applied (otherwise min_date is
    # the dataset's first date and every supplier counts as "new").
    new_suppliers_count = 0
    if period_filter is not None and min_date and current_suppliers:
        prior_suppliers = set()
        for r in all_rows:
            d = str(r.get("date") or "")[:10]
            if d and d < min_date:
                sup = str(r.get("supplier") or "")
                if sup:
                    prior_suppliers.add(sup)
        new_suppliers_count = len(current_suppliers - prior_suppliers)

    # Period-over-period velocity: compare filtered total to same-length window before
    velocity_pct = None
    prev_total = None
    if period_filter is not None and min_date and max_date and day_span > 0:
        try:
            d1 = _dt.strptime(min_date, "%Y-%m-%d")
            prev_end = d1 - _td(days=1)
            prev_start = prev_end - _td(days=day_span - 1)
            ps_iso = prev_start.strftime("%Y-%m-%d")
            pe_iso = prev_end.strftime("%Y-%m-%d")
            prev_amount = 0.0
            for r in all_rows:
                d = str(r.get("date") or "")[:10]
                if d and ps_iso <= d <= pe_iso:
                    prev_amount += _waybill_amount_value(r)
            prev_total = round(prev_amount, 2)
            current_total = sum(amounts)
            if prev_amount > 0:
                velocity_pct = round(((current_total - prev_amount) / prev_amount) * 100.0, 2)
        except (ValueError, TypeError):
            pass

    total_amount = sum(amounts)
    return {
        "avg_amount": round(total_amount / len(amounts), 2) if amounts else 0.0,
        "median_amount": round(_stats.median(amounts), 2) if amounts else 0.0,
        "max_amount": round(max(amounts), 2) if amounts else 0.0,
        "min_amount": round(min(amounts), 2) if amounts else 0.0,
        "return_count": return_count,
        "return_amount": round(return_amount, 2),
        "return_pct": round((return_count / len(filtered_rows)) * 100.0, 2) if filtered_rows else 0.0,
        "daily_avg_count": round(len(filtered_rows) / day_span, 2) if day_span else 0.0,
        "daily_avg_amount": round(total_amount / day_span, 2) if day_span else 0.0,
        "active_suppliers_count": len(current_suppliers),
        "new_suppliers_count": new_suppliers_count,
        "prev_period_total": prev_total,
        "velocity_pct": velocity_pct,
        "date_min": min_date,
        "date_max": max_date,
        "day_span": day_span,
    }


def _build_waybills_response(
    cache, q=None, sort=None, limit=None, period_filter=None,
    store=None, status_filter=None, type_filter=None,
    amount_min=None, amount_max=None, returns_only=None,
    **_kwargs
):
    rows = cache.get("waybills") if isinstance(cache, dict) else None
    rows = rows if isinstance(rows, list) else []
    projected_rows = [
        projected
        for projected in (_project_waybill_row(item) for item in rows)
        if projected is not None
    ]
    # Fallback: pipeline-generated cache may be older than this code and
    # missing the store/is_return enrichment. Compute on the fly so KPIs and
    # the store filter work without waiting for the next pipeline regen.
    needs_store = any(not row.get("store") and row.get("delivery_location") for row in projected_rows[:50])
    for row in projected_rows:
        row["is_return"] = "დაბრუნება" in str(row.get("type") or "")
    if needs_store:
        try:
            from dashboard_pipeline.constants import detect_object
            from dashboard_pipeline.config_loaders import load_object_mapping
            import os as _os
            _script_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            object_mapping = load_object_mapping(_script_dir)
            for row in projected_rows:
                if not row.get("store"):
                    delivery = str(row.get("delivery_location") or "").strip()
                    if delivery and delivery != "N/A":
                        row["store"] = detect_object(
                            "rs_waybill",
                            text=delivery,
                            object_mapping=object_mapping,
                            rs_location=delivery,
                        )
        except Exception:
            pass
    requested_query = _clean_lookup_text(q)
    requested_sort = _clean_lookup_text(sort)
    applied_sort = requested_sort if requested_sort in WAYBILL_ALLOWED_SORTS else None
    if requested_sort is not None and applied_sort is None:
        applied_sort = "amount_asc"
    applied_limit = _coerce_waybill_limit(limit)

    requested_store = _clean_lookup_text(store)
    requested_status = _clean_lookup_text(status_filter)
    requested_type = _clean_lookup_text(type_filter)
    try:
        amt_min = float(amount_min) if amount_min not in (None, "") else None
    except (TypeError, ValueError):
        amt_min = None
    try:
        amt_max = float(amount_max) if amount_max not in (None, "") else None
    except (TypeError, ValueError):
        amt_max = None
    returns_only_flag = bool(returns_only) and str(returns_only).lower() not in ("0", "false", "")

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
    if requested_store:
        filtered_rows = [r for r in filtered_rows if str(r.get("store") or "") == requested_store]
    if requested_status:
        filtered_rows = [r for r in filtered_rows if str(r.get("status") or "") == requested_status]
    if requested_type:
        filtered_rows = [r for r in filtered_rows if requested_type in str(r.get("type") or "")]
    if returns_only_flag:
        filtered_rows = [r for r in filtered_rows if r.get("is_return")]
    if amt_min is not None:
        filtered_rows = [r for r in filtered_rows if _waybill_amount_value(r) >= amt_min]
    if amt_max is not None:
        filtered_rows = [r for r in filtered_rows if _waybill_amount_value(r) <= amt_max]

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

    extra_kpis = _build_waybill_extra_kpis(filtered_rows, period_filter, projected_rows)
    chart_data = _build_waybill_chart_data(filtered_rows)
    supplier_analytics = _build_waybill_supplier_analytics(filtered_rows, projected_rows)
    quality_trends = _build_waybill_quality_trends(filtered_rows)
    anomaly_data = _build_waybill_anomaly_data(filtered_rows, projected_rows)
    calendar_heatmap = _build_waybill_calendar_heatmap(filtered_rows)
    duplicate_candidates = _build_waybill_duplicate_candidates(filtered_rows)
    month_benchmark = _build_waybill_month_benchmark(filtered_rows)

    return {
        "waybills": returned_rows,
        "waybills_summary": {
            **chart_data,
            **supplier_analytics,
            **anomaly_data,
            "quality_trends": quality_trends,
            "calendar_heatmap": calendar_heatmap,
            "duplicate_candidates": duplicate_candidates,
            "month_benchmark": month_benchmark,
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
                or requested_store
                or requested_status
                or requested_type
                or returns_only_flag
                or amt_min is not None
                or amt_max is not None
            ),
            "status_breakdown": _build_waybill_status_breakdown(filtered_rows),
            "store_breakdown": _build_waybill_store_breakdown(filtered_rows),
            "type_breakdown": _build_waybill_type_breakdown(filtered_rows),
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
            "filters": {
                "store": requested_store,
                "status": requested_status,
                "type": requested_type,
                "returns_only": returns_only_flag,
                "amount_min": amt_min,
                "amount_max": amt_max,
            },
            **extra_kpis,
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
        entry = archived_map.get(tid) if tid else None
        sup["archived"] = bool(entry and entry.get("archived_at"))
    return suppliers


def refresh_archive_runtime_flags(suppliers):
    """Re-apply live archive.json flags (archived + excluded_from_analysis)
    to a possibly-cached suppliers list. Used by the static-artifact
    serving path so 📥 / 🚫 button presses are visible without waiting
    for the next pipeline regeneration."""
    archived_map = _load_supplier_archive()
    for sup in suppliers:
        tid = _extract_tax_id_from_org(sup.get("ორგანიზაცია"))
        entry = archived_map.get(tid) if tid else None
        sup["archived"] = bool(entry and entry.get("archived_at"))
        sup["excluded_from_analysis"] = bool(entry and entry.get("excluded_from_analysis"))
        if entry and entry.get("exclusion_reason"):
            sup["exclusion_reason"] = entry["exclusion_reason"]
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
    store=None,
    status_filter=None,
    type_filter=None,
    amount_min=None,
    amount_max=None,
    returns_only=None,
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
                store=store,
                status_filter=status_filter,
                type_filter=type_filter,
                amount_min=amount_min,
                amount_max=amount_max,
                returns_only=returns_only,
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
