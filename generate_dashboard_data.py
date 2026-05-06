# ============================================================================
# generate_dashboard_data.py — Integration wrapper (Session #19)
# ============================================================================
# All business logic lives in dashboard_pipeline/ modules.
# This file:
#   1. Imports from modules
#   2. Re-exports names for backward compatibility (audit scripts: `import generate_dashboard_data as g`)
#   3. Defines run() orchestration
# ============================================================================

import json
import os
import re
from pathlib import Path

import pandas as pd

from dashboard_pipeline.logging_config import get_logger

logger = get_logger(__name__)

from backend_paths import (
    get_dashboard_data_path,
    get_dashboard_public_dir,
    get_dashboard_tab_data_dir,
)

# ---------------------------------------------------------------------------
# Module imports — constants
# ---------------------------------------------------------------------------
from dashboard_pipeline.constants import (
    OWN_TAX_ID,
    SAMURNEO_LEDGER_CLASS_KA,
    SAMURNEO_LABEL_KA,
    SAMURNEO_ACCOUNTING_NOTE_KA,
    SAMURNEO_EXPENSE_DIRECTION_KA,
    SAMURNEO_RETURN_DIRECTION_KA,
    BANK_UNMATCHED_LEDGER_NOTE_KA,
    TAX_TREASURY_CLUSTER_NOTE_KA,
    TBC_EXPENSES_LEDGER_NOTE_KA,
    BOG_EXPENSES_LEDGER_NOTE_KA,
    ACCOUNTING_ROLE_OPERATING,
    ACCOUNTING_ROLE_STATE_TREASURY,
    BOG_OTHER_EXPENSE_ID,
    BOG_OTHER_EXPENSE_LABEL_KA,
    TBC_OTHER_EXPENSE_ID,
    TBC_OTHER_EXPENSE_LABEL_KA,
    AGING_BUCKET_ORDER,
    IMPORTED_PRODUCTS_SHEET_NAME,
    FULL_ROLLUP_ROW_CAP,
    IMPORTED_PRODUCTS_ROWS_PREVIEW_LIMIT,
    IMPORTED_PRODUCTS_TOP_LIMIT,
    IMPORTED_PRODUCTS_SUPPLIER_TOP_PRODUCTS_LIMIT,
    IMPORTED_PRODUCTS_PRODUCT_TOP_SUPPLIERS_LIMIT,
    IMPORTED_PRODUCTS_PRODUCTS_LIMIT,
    IMPORTED_PRODUCTS_TOP_SUPPLIER_PRODUCT_PAIRS_LIMIT,
    IMPORTED_PRODUCTS_TRUNCATION_ROW_COUNT,
    IMPORTED_PRODUCTS_READ_ERROR_LIMIT,
    IMPORTED_PRODUCTS_CSV_ENCODINGS,
    RETAIL_SALES_READ_ERROR_LIMIT,
    RETAIL_SALES_TOP_LIMIT,
    RETAIL_SALES_CATEGORY_LIMIT,
    RETAIL_SALES_PRODUCT_LIMIT,
    RETAIL_SALES_ROWS_PREVIEW_LIMIT,
    RETAIL_SALES_DUPLICATE_POLICY_MODE,
    RETAIL_SALES_DUPLICATE_SUSPECTED_FILES,
    OBJECT_OZURGETI,
    OBJECT_DVABZU,
    OBJECT_COMMON,
    OBJECT_UNALLOCATED,
    OBJECT_ORDER_BASE,
    DEFAULT_OBJECT_MAPPING,
    DEFAULT_BUDGET_CONFIG,
    DEFAULT_SECTOR_BENCHMARKS,
    BOG_RECEIVER_ID_TO_RS_TAX_ID,
    PARTNER_IBAN_TO_RS_TAX_ID,
    BANK_UNMATCHED_CATEGORY_ORDER,
    _safe_text,
    _normalize_for_match,
    _ordered_unique,
    _object_order_for_pos,
    _object_order_for_monthly_pnl,
    _month_sort_key,
    _match_text_to_object,
    _clone_default_object_mapping,
    _clone_default_budget_config,
    _clone_default_sector_benchmarks,
    detect_object,
    _extract_tax_id_from_org,
    _pick_aging_bucket,
    _empty_aging_summary,
    _to_waybills_df,
    _parse_rs_datetime,
    _month_key,
    _monthly_summary,
    _day_key,
    _daily_summary,
)

# ---------------------------------------------------------------------------
# Module imports — file utilities
# ---------------------------------------------------------------------------
from dashboard_pipeline.bank_cache import list_bog_statement_paths
from dashboard_pipeline.tbc_cache import list_tbc_statement_paths
from dashboard_pipeline.rsge_cache import list_rsge_waybill_paths
from dashboard_pipeline.file_utils import (
    set_anchor_file,
    _financial_analysis_path,
    list_bog_bank_statement_xlsx,
    list_tbc_bank_statement_xlsx,
    list_rs_waybill_files,
    list_imported_product_files,
    list_retail_sales_dvabzu_files,
    list_retail_sales_ozurgeti_files,
    list_retail_sales_files,
    _to_financial_relative_path,
    find_header_row,
    clean_id,
    _find_excel_column_danishnuleba,
    _find_tbc_partner_column,
    _find_tbc_additional_purpose_column,
    _excel_cell,
    _save_excel,
    _read_imported_products_csv,
    _read_imported_products_file,
    _bank_positive_debit_total_ge,
    verify_bank_debit_totals,
    _normalize_iban_ge,
)

# ---------------------------------------------------------------------------
# Module imports — config loaders
# ---------------------------------------------------------------------------
from dashboard_pipeline.config_loaders import (
    load_object_mapping,
    load_budget_config,
    load_sector_benchmarks,
    load_unmatched_overrides,
    load_supplier_matching_registry,
    supplier_matching_registry_path,
)

# ---------------------------------------------------------------------------
# Module imports — bank unmatched
# ---------------------------------------------------------------------------
from dashboard_pipeline.bank_unmatched import (
    analyze_bank_unmatched_rows,
    get_auto_unmatched_category_rules,
    write_bank_unmatched_excel,
    write_bank_unmatched_categories_excel,
    write_bank_unclassified_top_excel,
    write_bank_overrides_audit_excel,
)

# ---------------------------------------------------------------------------
# Module imports — bank income / expenses
# ---------------------------------------------------------------------------
from dashboard_pipeline.bank_income import (
    collect_tbc_card_income,
    collect_bog_pos_terminal_income,
    merge_pos_terminal_income,
    collect_tbc_expense_categories,
    collect_bog_expense_categories,
    collect_tbc_samurneo_flow,
    collect_bog_samurneo_flow,
    merge_samurneo_flows,
    collect_tax_flow,
    collect_tbc_foodmart_cashback,
    write_tbc_card_income_excel,
    write_pos_terminal_income_excel,
    write_tbc_expenses_excel,
    write_tbc_samurneo_excel,
    write_tax_flow_excel,
    write_treasury_incoming_excel,
    write_tbc_foodmart_cashback_excel,
    write_suppliers_excel,
)

# ---------------------------------------------------------------------------
# Module imports — manual payments
# ---------------------------------------------------------------------------
from dashboard_pipeline.manual_payments import (
    manual_payments_csv_path,
    load_manual_payments,
    load_manual_payment_rows,
    sync_manual_payments_journal,
    read_manual_journal_full,
    read_manual_journal_rows,
    collect_rs_suppliers_by_tax_id,
)

# ---------------------------------------------------------------------------
# Module imports — VAT reconciliation (Sprint 5.1)
# ---------------------------------------------------------------------------
from dashboard_pipeline.vat_reconciliation import (
    compute_vat_reconciliation,
    find_audit_excel,
    find_invoices_issued_excel,
)

# ---------------------------------------------------------------------------
# Module imports — analytics builders
# ---------------------------------------------------------------------------
from dashboard_pipeline.analytics_builders import (
    build_monthly_pnl,
    build_supplier_aging,
    build_ap_monthly_trend,
    build_financial_ratios,
    build_forecast,
    build_budget,
    build_company_valuation,
    build_executive_summary,
    build_supplier_concentration,
    tbc_expenses_public_json,
    bog_expenses_public_json,
    publish_download_excels,
)

# ---------------------------------------------------------------------------
# Module imports — supplier matching
# ---------------------------------------------------------------------------
from dashboard_pipeline.supplier_matching import (
    build_supplier_master,
    build_name_to_id_map,
    get_merged_bog_receiver_map,
    canonical_tax_id_from_bog_receiver,
    skip_name_only_supplier_match,
    match_partner_to_id,
    collect_rs_tax_ids,
    infer_bog_receiver_id_to_rs_tax_id,
    normalize_name,
    _supplier_truth_context,
)

# ---------------------------------------------------------------------------
# Module imports — bank reconciliation
# ---------------------------------------------------------------------------
from dashboard_pipeline.bank_reconciliation import (
    get_bank_payments,
    empty_bank_reconciliation_audit,
    _line_for_excel,
    write_bank_ambiguous_excel,
    write_bank_non_supplier_excel,
    write_bank_matched_high_excel,
    build_supplier_payment_lines,
)

# ---------------------------------------------------------------------------
# Module imports — imported products & retail sales
# ---------------------------------------------------------------------------
from dashboard_pipeline.imported_products import (
    collect_imported_products_bundle,
    empty_imported_products_bundle,
)
from dashboard_pipeline.retail_sales import (
    collect_retail_sales_bundle,
    empty_retail_sales_bundle,
    synthesize_from_megaplus as _synthesize_retail_from_megaplus,
)
from dashboard_pipeline.supplier_profitability import (
    build_supplier_profitability,
)
from dashboard_pipeline._validate_aliases import load_and_validate as _load_aliases
from dashboard_pipeline.megaplus_backup import (
    process_all_stores as _process_megaplus_stores,
    read_combined_rollup as _read_megaplus_combined,
)

# ---------------------------------------------------------------------------
# Module imports — API contracts, config validation, export, sources, truth
# ---------------------------------------------------------------------------
from dashboard_pipeline.api_contracts import build_static_api_artifacts
from dashboard_pipeline.config_validation import (
    validate_api_artifacts,
    validate_config_bundle,
)
from dashboard_pipeline.export_artifacts import (
    write_api_artifacts,
)
from dashboard_pipeline.sources import (
    build_source_manifest,
    summarize_source_manifest,
)
from dashboard_pipeline.truth_boundary import (
    build_truth_boundary_summary,
    build_payment_scope_summary,
    build_reconciliation_provenance,
    describe_supplier_payment_scope,
)
from dashboard_pipeline.waybill_amounts import get_effective, get_returned

# ---------------------------------------------------------------------------
# Anchor path for file_utils (must be set before any path-dependent call)
# ---------------------------------------------------------------------------
set_anchor_file(__file__)


def _load_pipeline_config(script_dir):
    """Load all configs, source manifest, and validate."""
    object_mapping = load_object_mapping(script_dir)
    generated_at = pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    source_manifest = build_source_manifest(
        [
            {
                "label_ka": "BOG ბანკის ამონაწერი",
                "source_kind": "bog_bank_statement",
                "paths": [str(p) for p in list_bog_statement_paths()],
            },
            {
                "label_ka": "TBC ბანკის ამონაწერი",
                "source_kind": "tbc_bank_statement",
                "paths": [str(p) for p in list_tbc_statement_paths()],
            },
            {
                "label_ka": "RS ზედნადები",
                "source_kind": "rs_waybills",
                "paths": list_rsge_waybill_paths(),
            },
            {
                "label_ka": "შემოტანილი პროდუქცია",
                "source_kind": "imported_products",
                "paths": list_imported_product_files(),
            },
            {
                "label_ka": "გაყიდული პროდუქცია — დვაბზუ",
                "source_kind": "retail_sales_dvabzu",
                "paths": list_retail_sales_dvabzu_files(),
            },
            {
                "label_ka": "გაყიდული პროდუქცია — ოზურგეთი",
                "source_kind": "retail_sales_ozurgeti",
                "paths": list_retail_sales_ozurgeti_files(),
            },
        ]
    )
    source_manifest_summary = summarize_source_manifest(source_manifest)
    budget_config = load_budget_config()
    sector_benchmarks = load_sector_benchmarks()
    supplier_registry_cfg = load_supplier_matching_registry()
    unmatched_overrides_cfg = load_unmatched_overrides()
    config_validation = validate_config_bundle(
        object_mapping,
        budget_config,
        sector_benchmarks,
        supplier_registry_cfg,
        unmatched_overrides_cfg,
    )
    logger.info(
        "Config validation: errors=%s | warnings=%s",
        config_validation.get('error_count', 0),
        config_validation.get('warning_count', 0),
    )
    return {
        "object_mapping": object_mapping,
        "generated_at": generated_at,
        "source_manifest": source_manifest,
        "source_manifest_summary": source_manifest_summary,
        "budget_config": budget_config,
        "sector_benchmarks": sector_benchmarks,
        "supplier_registry_cfg": supplier_registry_cfg,
        "unmatched_overrides_cfg": unmatched_overrides_cfg,
        "config_validation": config_validation,
    }


def _collect_income_bundles(script_dir, object_mapping):
    """Collect all income, expense, samurneo, tax, and cashback bundles."""
    logger.info("Reading card and POS income sources...")
    tbc_card_income_bundle = collect_tbc_card_income(
        script_dir, object_mapping=object_mapping, use_cache=True
    )
    bog_pos_income_bundle = collect_bog_pos_terminal_income(
        script_dir, object_mapping=object_mapping, use_cache=True
    )
    pos_terminal_all_rows = list(tbc_card_income_bundle.get("lines") or []) + list(
        bog_pos_income_bundle.get("lines") or []
    )
    pos_terminal_income_bundle = merge_pos_terminal_income(
        tbc_card_income_bundle,
        bog_pos_income_bundle,
        object_mapping=object_mapping,
    )
    logger.info(
        "TBC ბარათის შემოსავალი (კონფიგი): %s ხაზი, %s ₾",
        tbc_card_income_bundle['line_count'],
        f"{tbc_card_income_bundle['total_ge']:,.2f}",
    )
    logger.info(
        "POS ტერმინალი (TBC+BOG): TBC %s ₾ | BOG %s ₾ | ჯამი %s ₾",
        f"{pos_terminal_income_bundle['tbc_total_ge']:,.2f}",
        f"{pos_terminal_income_bundle['bog_total_ge']:,.2f}",
        f"{pos_terminal_income_bundle['total_ge']:,.2f}",
    )

    tbc_expenses_bundle = collect_tbc_expense_categories(
        script_dir, object_mapping=object_mapping, use_cache=True
    )
    _te_lines = sum(
        int(c.get("line_count") or 0)
        for c in (tbc_expenses_bundle.get("categories") or [])
    )
    logger.info(
        "TBC ხარჯები (კატეგორიები): %s ხაზი, %s ₾",
        _te_lines,
        f"{tbc_expenses_bundle.get('grand_total_ge', 0):,.2f}",
    )
    bog_expenses_bundle = collect_bog_expense_categories(
        script_dir, object_mapping=object_mapping, use_cache=True
    )
    _be_lines = sum(
        int(c.get("line_count") or 0)
        for c in (bog_expenses_bundle.get("categories") or [])
    )
    _be_active_categories = sum(
        1
        for c in (bog_expenses_bundle.get("categories") or [])
        if int(c.get("line_count") or 0) > 0
    )
    logger.info(
        "BOG ხარჯები: %s კატეგორია, %s ხაზი, %s ₾ (operating: %s ₾, treasury: %s ₾)",
        _be_active_categories, _be_lines,
        f"{bog_expenses_bundle.get('grand_total_ge', 0):,.2f}",
        f"{bog_expenses_bundle.get('grand_total_operating_expense_ge', 0):,.2f}",
        f"{bog_expenses_bundle.get('grand_total_state_treasury_ge', 0):,.2f}",
    )
    tbc_samurneo_bundle = collect_tbc_samurneo_flow(script_dir, use_cache=True)
    bog_samurneo_bundle = collect_bog_samurneo_flow(script_dir, use_cache=True)
    samurneo_bundle = merge_samurneo_flows(tbc_samurneo_bundle, bog_samurneo_bundle)
    tax_flow_bundle = collect_tax_flow(script_dir, use_cache=True)
    tbc_foodmart_cashback_bundle = collect_tbc_foodmart_cashback(
        script_dir, use_cache=True
    )
    logger.info(
        "სამეურნეო (BOG+TBC): გატანა %s ₾ | შემოტანა %s ₾ | net %s ₾",
        f"{samurneo_bundle['expense_total_ge']:,.2f}",
        f"{samurneo_bundle['return_total_ge']:,.2f}",
        f"{samurneo_bundle['net_ge']:,.2f}",
    )
    logger.info(
        "საგადასახადო (BOG+TBC): გადარიცხული %s ₾ | ჩარიცხული %s ₾ | net %s ₾",
        f"{tax_flow_bundle['out_total_ge']:,.2f}",
        f"{tax_flow_bundle['in_total_ge']:,.2f}",
        f"{tax_flow_bundle['net_ge']:,.2f}",
    )
    logger.info(
        "TBC ფუდმარტი ქეშბექი: %s ხაზი, %s ₾",
        tbc_foodmart_cashback_bundle['line_count'],
        f"{tbc_foodmart_cashback_bundle['total_ge']:,.2f}",
    )
    return {
        "tbc_card_income_bundle": tbc_card_income_bundle,
        "bog_pos_income_bundle": bog_pos_income_bundle,
        "pos_terminal_all_rows": pos_terminal_all_rows,
        "pos_terminal_income_bundle": pos_terminal_income_bundle,
        "tbc_expenses_bundle": tbc_expenses_bundle,
        "bog_expenses_bundle": bog_expenses_bundle,
        "samurneo_bundle": samurneo_bundle,
        "tax_flow_bundle": tax_flow_bundle,
        "tbc_foodmart_cashback_bundle": tbc_foodmart_cashback_bundle,
    }


def _enrich_meta(data, generated_at, source_manifest, source_manifest_summary, config_validation):
    """Enrich data['meta'] with generated_at, truth boundary, reproducibility report."""
    meta = data.setdefault("meta", {})
    meta["generated_at"] = generated_at
    meta["source_manifest_summary"] = source_manifest_summary
    meta["config_validation"] = {
        "ok": bool(config_validation.get("ok")),
        "warning_count": int(config_validation.get("warning_count") or 0),
        "error_count": int(config_validation.get("error_count") or 0),
    }
    empty_reconciliation_meta = empty_bank_reconciliation_audit()
    meta["payment_scope_summary"] = (
        data.get("bank_reconciliation_audit", {}).get("payment_scope_summary")
        or empty_reconciliation_meta.get("payment_scope_summary")
    )
    meta["truth_source_breakdown"] = (
        data.get("bank_reconciliation_audit", {}).get("truth_source_breakdown")
        or empty_reconciliation_meta.get("truth_source_breakdown")
        or {}
    )
    meta["truth_boundary_summary"] = (
        data.get("bank_reconciliation_audit", {}).get("truth_boundary_summary")
        or empty_reconciliation_meta.get("truth_boundary_summary")
        or {}
    )
    meta["strict_bank_only_total"] = float(
        (meta.get("payment_scope_summary") or {}).get("strict_bank_only_total") or 0
    )
    meta["combined_supplier_paid_total"] = float(
        (meta.get("payment_scope_summary") or {}).get("combined_supplier_paid_total") or 0
    )
    meta["manual_vs_bank_gap_total"] = round(
        float(meta.get("combined_supplier_paid_total") or 0)
        - float(meta.get("strict_bank_only_total") or 0),
        2,
    )
    meta["reproducibility_report"] = {
        "generated_at": generated_at,
        "source_manifest_summary": source_manifest_summary,
        "config_validation": meta.get("config_validation"),
        "bank_unmatched_total_ge": float(meta.get("bank_unmatched_total_ge") or 0),
        "bank_recon_ambiguous_amount": float(meta.get("bank_recon_ambiguous_amount") or 0),
        "bank_recon_unmatched_amount": float(meta.get("bank_recon_unmatched_amount") or 0),
        "truth_source_breakdown": meta.get("truth_source_breakdown") or {},
        "truth_boundary_summary": meta.get("truth_boundary_summary") or {},
        "imported_products_truncation_suspected": bool(
            (data.get("imported_products") or {}).get("truncation_suspected_any")
        ),
        "retail_sales_duplicate_policy_mode": str(
            ((data.get("retail_sales") or {}).get("duplicate_policy") or {}).get("mode")
            or ""
        ),
        "retail_sales_duplicate_excluded_file_count": int(
            (
                ((data.get("retail_sales") or {}).get("duplicate_policy") or {}).get(
                    "excluded_file_count"
                )
                or 0
            )
        ),
    }
    data["source_manifest"] = source_manifest


def _build_analytics(data, inc, object_mapping, budget_config, sector_benchmarks, supplier_aging_result):
    """Build PnL, ratios, forecast, budget, valuation, executive summary. Mutates data in-place."""
    pos_terminal_income_bundle = inc["pos_terminal_income_bundle"]
    pos_terminal_all_rows = inc["pos_terminal_all_rows"]
    tbc_expenses_bundle = inc["tbc_expenses_bundle"]
    bog_expenses_bundle = inc["bog_expenses_bundle"]

    # Keep raw POS lines only in-process for P&L building; do not leak them into public data.json.
    pos_terminal_pnl_bundle = {
        **pos_terminal_income_bundle,
        "pnl_lines": pos_terminal_all_rows,
    }
    data["monthly_pnl"] = build_monthly_pnl(
        pos_terminal_pnl_bundle,
        tbc_expenses_bundle,
        object_mapping,
        bog_expenses_bundle=bog_expenses_bundle,
        retail_sales_bundle=data.get("retail_sales"),
        supplier_payment_lines=data.get("supplier_payment_lines"),
    )
    data["financial_ratios"] = build_financial_ratios(
        data.get("monthly_pnl", []),
        supplier_aging_result.get("suppliers", []),
        data.get("ap_monthly_trend", []),
    )
    data["forecast"] = build_forecast(data.get("monthly_pnl", []))
    data["budget"] = build_budget(
        data.get("monthly_pnl", []),
        data.get("forecast", {}),
        budget_config,
    )
    data["company_valuation"] = build_company_valuation(
        data.get("monthly_pnl", []),
        data.get("financial_ratios", {}),
        data.get("forecast", {}),
        sector_benchmarks,
    )
    data["executive_summary"] = build_executive_summary(data)

    # --- Logging ---
    monthly_pnl_total_net = sum(
        float((m.get("total") or {}).get("net") or 0)
        for m in data["monthly_pnl"]
    )
    monthly_pnl_objects = _object_order_for_monthly_pnl(object_mapping)
    seen_monthly_objects = set(monthly_pnl_objects)
    for m in data["monthly_pnl"]:
        for obj in (m.get("objects") or {}).keys():
            if obj not in seen_monthly_objects:
                monthly_pnl_objects.append(obj)
                seen_monthly_objects.add(obj)
    logger.info(
        "monthly_pnl: %s თვე | ჯამური net %s ₾ | ობიექტები: %s",
        len(data['monthly_pnl']),
        f"{monthly_pnl_total_net:,.2f}",
        ', '.join(monthly_pnl_objects),
    )
    ratios = data.get("financial_ratios") or {}
    company_ratios = ratios.get("company") or {}
    object_ratios = ratios.get("objects") or {}
    company_net_margin = float(
        company_ratios.get("net_margin_pct")
        if company_ratios.get("net_margin_pct") is not None
        else company_ratios.get("gross_margin_pct")
        or 0
    )
    oz_ratio = object_ratios.get(OBJECT_OZURGETI) or {}
    dv_ratio = object_ratios.get(OBJECT_DVABZU) or {}
    oz_margin = float(
        oz_ratio.get("net_margin_pct")
        if oz_ratio.get("net_margin_pct") is not None
        else oz_ratio.get("gross_margin_pct")
        or 0
    )
    dv_margin = float(
        dv_ratio.get("net_margin_pct")
        if dv_ratio.get("net_margin_pct") is not None
        else dv_ratio.get("gross_margin_pct")
        or 0
    )
    top_risk = (ratios.get("top_risk_suppliers") or [{}])[0]
    top_risk_org = str(top_risk.get("org") or "N/A")
    top_risk_debt = float(top_risk.get("total_debt") or 0)
    top_risk_days = top_risk.get("days_since_last")
    top_risk_days_text = f"{int(top_risk_days)}" if top_risk_days is not None else "0"
    logger.info(
        "Financial Ratios: Net Margin %.1f%% | Payment Ratio %.1f%% | AP Days %s | Avg Monthly Net %s",
        company_net_margin,
        float(company_ratios.get('payment_ratio_pct') or 0),
        int(company_ratios.get('ap_days') or 0),
        f"{float(company_ratios.get('avg_monthly_net') or 0):,.0f}",
    )
    logger.info(
        "  Margins: ozurgeti %.1f%% | dvabzu %.1f%% | TOP risk: [%s] %s (%s days)",
        oz_margin, dv_margin, top_risk_org, f"{top_risk_debt:,.0f}", top_risk_days_text,
    )
    forecast_data = data.get("forecast") or {}
    forecast_months = ((forecast_data.get("forecast") or {}).get("months") or [])
    first_forecast = forecast_months[0] if forecast_months else {}
    first_forecast_total = first_forecast.get("total") or {}
    first_forecast_month = str(first_forecast.get("month") or "N/A")
    first_forecast_net = float(first_forecast_total.get("net") or 0)
    seasonality = forecast_data.get("seasonality") or {}
    strongest_month = seasonality.get("strongest_month") or {}
    weakest_month = seasonality.get("weakest_month") or {}
    yoy = forecast_data.get("yoy") or {}
    logger.info(
        "Forecast (SMA-6): %s months | first: %s net ~%s",
        len(forecast_months), first_forecast_month, f"{first_forecast_net:,.0f}",
    )
    logger.info(
        "Seasonality: strong=[%s] (%.2f) | weak=[%s] (%.2f)",
        str(strongest_month.get('label') or 'N/A'),
        float(strongest_month.get('seasonality_index') or 0),
        str(weakest_month.get('label') or 'N/A'),
        float(weakest_month.get('seasonality_index') or 0),
    )
    logger.info(
        "YoY: income %+.1f%% | expenses %+.1f%% | net %+.1f%%",
        float(yoy.get('income_change_pct') or 0),
        float(yoy.get('expenses_change_pct') or 0),
        float(yoy.get('net_change_pct') or 0),
    )
    budget = data.get("budget") or {}
    annual_budget = budget.get("annual") or {}
    logger.info("Budget:")
    for budget_year in ("2024", "2025"):
        year_data = annual_budget.get(budget_year) or {}
        plan_net = float((year_data.get("plan") or {}).get("net") or 0)
        actual_net = float((year_data.get("actual") or {}).get("net") or 0)
        variance_net = float((year_data.get("variance") or {}).get("net") or 0)
        variance_pct = (float(variance_net / plan_net) * 100.0) if plan_net else 0.0
        logger.info(
            "  %s: plan net %s | actual net %s | variance %s (%+.1f%%)",
            budget_year, f"{plan_net:,.0f}", f"{actual_net:,.0f}",
            f"{variance_net:,.0f}", variance_pct,
        )
    ytd_budget = budget.get("ytd_summary") or {}
    ytd_year = str(ytd_budget.get("current_year") or pd.Timestamp.now().year)
    ytd_plan_net = float((ytd_budget.get("plan_ytd") or {}).get("net") or 0)
    ytd_actual_net = float((ytd_budget.get("actual_ytd") or {}).get("net") or 0)
    ytd_on_track = "yes" if bool(ytd_budget.get("on_track")) else "no"
    logger.info(
        "  %s YTD: plan net %s | actual net %s | on_track: %s",
        ytd_year, f"{ytd_plan_net:,.0f}", f"{ytd_actual_net:,.0f}", ytd_on_track,
    )
    company_valuation = data.get("company_valuation") or {}
    valuation = company_valuation.get("valuation") or {}
    valuation_range = valuation.get("range") or {}
    swot = company_valuation.get("swot") or {}
    logger.info(
        "Valuation: Score %.1f/5.0 | Range %s - %s - %s | SWOT %s/%s/%s/%s",
        float(company_valuation.get('overall_sector_score') or 0),
        f"{float(valuation_range.get('low') or 0):,.0f}",
        f"{float(valuation_range.get('median') or 0):,.0f}",
        f"{float(valuation_range.get('high') or 0):,.0f}",
        len(swot.get('strengths') or []),
        len(swot.get('weaknesses') or []),
        len(swot.get('opportunities') or []),
        len(swot.get('threats') or []),
    )
    executive_summary = data.get("executive_summary") or {}
    audit_readiness = executive_summary.get("audit_readiness") or {}
    executive = executive_summary.get("executive") or {}
    executive_kpis = executive.get("kpis") or {}
    logger.info(
        "Executive: Grade %s (%s/100) | Headline: %s | Decisions: %s | Next: %s | Valuation: %s",
        str(audit_readiness.get('grade') or 'N/A'),
        int(audit_readiness.get('overall_score') or 0),
        str(executive.get('headline_ka') or ''),
        len(executive.get('key_decisions') or []),
        len(executive.get('next_steps') or []),
        f"{float(executive_kpis.get('valuation_median') or 0):,.0f}",
    )


def _write_outputs(data, script_dir, inc):
    """Write Excel downloads, API artifacts, and data.json."""
    tbc_card_income_bundle = inc["tbc_card_income_bundle"]
    pos_terminal_income_bundle = inc["pos_terminal_income_bundle"]
    pos_terminal_all_rows = inc["pos_terminal_all_rows"]
    tbc_expenses_bundle = inc["tbc_expenses_bundle"]
    samurneo_bundle = inc["samurneo_bundle"]
    tax_flow_bundle = inc["tax_flow_bundle"]
    tbc_foodmart_cashback_bundle = inc["tbc_foodmart_cashback_bundle"]

    download_dir = os.path.join(script_dir, "download")
    write_tbc_card_income_excel(tbc_card_income_bundle["lines"], download_dir)
    write_pos_terminal_income_excel(
        pos_terminal_income_bundle, download_dir, pos_terminal_all_rows
    )
    write_tbc_expenses_excel(tbc_expenses_bundle, download_dir)
    write_tbc_samurneo_excel(samurneo_bundle, download_dir)
    write_tax_flow_excel(tax_flow_bundle, download_dir)
    write_treasury_incoming_excel(tax_flow_bundle, download_dir)
    write_tbc_foodmart_cashback_excel(tbc_foodmart_cashback_bundle, download_dir)

    out_dir = get_dashboard_public_dir(script_dir)
    os.makedirs(out_dir, exist_ok=True)
    published = publish_download_excels(download_dir, out_dir)
    data["download_files"] = published.get("files", [])
    data["download_zip_file"] = published.get("zip_file", "")
    if isinstance(data.get("pos_terminal_income"), dict):
        data["pos_terminal_income"].pop("pnl_lines", None)
    artifact_dir = get_dashboard_tab_data_dir(script_dir)
    artifact_dir_rel = os.path.relpath(artifact_dir, script_dir).replace("\\", "/")
    # Pre-rendered JSON for STATIC_RESPONSE_TABS only. Targeted tabs (e.g. waybills with
    # filters; imported_products_supplier_detail / imported_products_product_detail) are
    # built at request time in server.get_tab_payload from *_source artifacts.
    artifacts = build_static_api_artifacts(data)
    api_artifact_validation = validate_api_artifacts(artifacts)
    artifact_manifest = write_api_artifacts(artifact_dir, artifacts)
    data["meta"]["api_artifact_validation"] = {
        "ok": bool(api_artifact_validation.get("ok")),
        "warning_count": int(api_artifact_validation.get("warning_count") or 0),
        "error_count": int(api_artifact_validation.get("error_count") or 0),
    }
    data["meta"]["api_artifact_manifest"] = {
        **artifact_manifest,
        "artifact_dir": artifact_dir_rel,
        "artifacts": {
            name: {
                **info,
                "path": (
                    os.path.relpath(str(info.get("path") or ""), script_dir).replace(
                        "\\", "/"
                    )
                    if str(info.get("path") or "").strip()
                    else ""
                ),
            }
            for name, info in sorted((artifact_manifest.get("artifacts") or {}).items())
        },
    }
    out_file = get_dashboard_data_path(script_dir)

    # Atomic write: write to temp then rename. Keeps the live data.json readable
    # for any concurrent HTTP reader + shortens the OneDrive sync lock window
    # from the multi-minute 131MB write down to a single rename operation.
    tmp_file = out_file + ".tmp"
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, out_file)

    logger.info("Data generated at %s", out_file)
    size_mb = float(os.path.getsize(out_file) / (1024 * 1024))
    logger.info("data.json size: %.2f MB", size_mb)

    # data.json → data.db (SQLite) — Claude/MCP-სთვის ad-hoc ანალიტიკის
    # SQL-ით (ბევრად სწრაფი ვიდრე JSON-ის parse-ი ყოველ კითხვაზე).
    try:
        from dashboard_pipeline.export_sqlite import export_data_json_to_sqlite
        db_path = os.path.join(os.path.dirname(out_file), "data.db")
        export_data_json_to_sqlite(out_file, db_path)
    except Exception as exc:
        logger.warning("SQLite ექსპორტი ჩავარდა: %s", exc)
    logger.info(
        "API artifacts: %s files | errors=%s | warnings=%s",
        data['meta']['api_artifact_manifest']['artifact_count'],
        data['meta']['api_artifact_validation']['error_count'],
        data['meta']['api_artifact_validation']['warning_count'],
    )


def _build_base_meta(inc, retail_overall, retail_duplicate_policy):
    """Build meta keys shared between empty-RS and filled-RS paths."""
    tbc_card_income_bundle = inc["tbc_card_income_bundle"]
    pos_terminal_income_bundle = inc["pos_terminal_income_bundle"]
    tbc_expenses_bundle = inc["tbc_expenses_bundle"]
    samurneo_bundle = inc["samurneo_bundle"]
    tax_flow_bundle = inc["tax_flow_bundle"]
    tbc_foodmart_cashback_bundle = inc["tbc_foodmart_cashback_bundle"]
    return {
        "tbc_card_income_total_ge": float(tbc_card_income_bundle["total_ge"]),
        "tbc_card_income_line_count": int(tbc_card_income_bundle["line_count"]),
        "pos_terminal_income_total_ge": float(pos_terminal_income_bundle.get("total_ge") or 0),
        "pos_terminal_income_tbc_total_ge": float(pos_terminal_income_bundle.get("tbc_total_ge") or 0),
        "pos_terminal_income_bog_total_ge": float(pos_terminal_income_bundle.get("bog_total_ge") or 0),
        "tbc_expenses_grand_total_ge": float(
            tbc_expenses_bundle.get("grand_total_ge") or 0
        ),
        "tbc_expenses_operating_total_ge": float(
            tbc_expenses_bundle.get("grand_total_operating_expense_ge") or 0
        ),
        "tbc_expenses_treasury_total_ge": float(
            tbc_expenses_bundle.get("grand_total_state_treasury_ge") or 0
        ),
        "tbc_expenses_total_lines": sum(
            int(c.get("line_count") or 0)
            for c in (tbc_expenses_bundle.get("categories") or [])
        ),
        "tbc_samurneo_expense_total_ge": float(samurneo_bundle.get("expense_total_ge") or 0),
        "tbc_samurneo_return_total_ge": float(samurneo_bundle.get("return_total_ge") or 0),
        "tbc_samurneo_net_ge": float(samurneo_bundle.get("net_ge") or 0),
        "tax_out_total_ge": float(tax_flow_bundle.get("out_total_ge") or 0),
        "tax_in_total_ge": float(tax_flow_bundle.get("in_total_ge") or 0),
        "tax_treasury_in_total_ge": float(tax_flow_bundle.get("treasury_in_total_ge") or 0),
        "tax_treasury_in_line_count": int(tax_flow_bundle.get("treasury_in_line_count") or 0),
        "tax_net_ge": float(tax_flow_bundle.get("net_ge") or 0),
        "tbc_foodmart_cashback_total_ge": float(tbc_foodmart_cashback_bundle.get("total_ge") or 0),
        "tbc_foodmart_cashback_line_count": int(tbc_foodmart_cashback_bundle.get("line_count") or 0),
        "retail_sales_row_count": int(retail_overall.get("row_count") or 0),
        "retail_sales_total_quantity": float(retail_overall.get("total_quantity") or 0),
        "retail_sales_revenue_ge": float(retail_overall.get("revenue_ge") or 0),
        "retail_sales_cost_ge": float(retail_overall.get("cost_ge") or 0),
        "retail_sales_profit_ge": float(retail_overall.get("profit_ge") or 0),
        "retail_sales_gross_margin_pct": float(
            retail_overall.get("gross_margin_pct") or 0
        ),
        "retail_sales_distinct_object_count": int(
            retail_overall.get("distinct_object_count") or 0
        ),
        "retail_sales_distinct_category_count": int(
            retail_overall.get("distinct_category_count") or 0
        ),
        "retail_sales_distinct_product_count": int(
            retail_overall.get("distinct_product_count") or 0
        ),
        "retail_sales_duplicate_excluded_file_count": int(
            retail_duplicate_policy.get("excluded_file_count") or 0
        ),
    }


def _audit_iban_taxid_conflicts(script_dir):
    """ბანკის ამონაწერების სკანი: ვპოვებ ერთ IBAN-ს, რომელზეც სხვადასხვა
    საგადასახადო ID-ით ხდება გადარიცხვა. ეს ჩვეულებრივ ნიშნავს, რომ ერთი
    და იგივე იურიდიული პირი ჩაწერილია სხვადასხვა ID-ით RS-ში (მაგ. ფირმის
    გადარქმევა / ხელახალი რეგისტრაცია), ან მონაცემების შეცდომაა.

    ფუნქცია არ აერთიანებს row-ებს ცხრილში (user-ის წესი: სხვადასხვა ID =
    სხვადასხვა კომპანია); მხოლოდ ლოგში გვაფრთხილებს, რომ ხელით გადამოწმდეს.
    """
    import glob

    bank_dirs = [
        ('TBC', os.path.join(script_dir, 'Financial_Analysis', 'თბს ბანკი ამონაწერი'), 'tbc'),
        ('BOG', os.path.join(script_dir, 'Financial_Analysis', 'ბოგ ბანკი ამონაწერი'), 'bog'),
    ]

    iban_to_records = {}
    iban_re = re.compile(r'^GE\d{2}[A-Z]{2}\d{16,19}[A-Z]{0,3}$')

    def _add(iban, tax_id, name):
        iban = str(iban or '').strip()
        tax_id = str(tax_id or '').strip()
        if not iban or not tax_id:
            return
        if not iban_re.match(iban):
            return
        if tax_id == OWN_TAX_ID:
            return  # ჩვენი საკუთარი IBAN-ს არ ვიწერ
        iban_to_records.setdefault(iban, {}).setdefault(tax_id, set()).add(str(name or '').strip())

    for bank_name, bank_dir, kind in bank_dirs:
        if not os.path.isdir(bank_dir):
            continue
        for path in sorted(glob.glob(os.path.join(bank_dir, '*.xlsx'))):
            try:
                if kind == 'tbc':
                    df_b = pd.read_excel(path, dtype=str).fillna('')
                    if 'პარტნიორის ანგარიში' not in df_b.columns:
                        continue
                    for _, row in df_b.iterrows():
                        _add(
                            row.get('პარტნიორის ანგარიში', ''),
                            row.get('პარტნიორის საგადასახადო კოდი', ''),
                            row.get('პარტნიორი', ''),
                        )
                else:  # bog — header at row index 8
                    df_b = pd.read_excel(path, header=8, dtype=str).fillna('')
                    # outgoing payments: recipient = supplier (col 16/17/18)
                    if 'მიმღების ანგარიშის ნომერი' in df_b.columns:
                        for _, row in df_b.iterrows():
                            _add(
                                row.get('მიმღების ანგარიშის ნომერი', ''),
                                row.get('მიმღების საიდენტიფიკაციო კოდი', ''),
                                row.get('მიმღების დასახელება', ''),
                            )
            except Exception as exc:
                logger.warning('IBAN audit: ვერ წავიკითხე %s — %s', path, exc)
                continue

    # კონფლიქტის შემთხვევები — IBAN, რომელზეც > 1 ID
    conflicts = {iban: ids for iban, ids in iban_to_records.items() if len(ids) > 1}
    if not conflicts:
        logger.info('IBAN audit: 0 კონფლიქტი (ერთი ანგარიში — ერთი ID).')
        return []

    summary_rows = []
    for iban, ids_map in conflicts.items():
        ids_list = sorted(ids_map.keys())
        names_summary = ' / '.join(
            f'{tid} → ' + ', '.join(sorted(n for n in names if n))
            for tid, names in sorted(ids_map.items())
        )
        summary_rows.append({
            'iban': iban,
            'tax_ids': ids_list,
            'names_summary': names_summary,
        })
        logger.warning(
            'IBAN კონფლიქტი: %s ←→ %s ID (%s)', iban, len(ids_list), names_summary,
        )
    logger.warning(
        'IBAN audit: სულ %s ანგარიში გვაქვს > 1 ID-ით. ხელით გადაამოწმე — '
        'შეიძლება გადარქმევა ან მონაცემების შეცდომაა.',
        len(conflicts),
    )
    return summary_rows


def _process_rs_suppliers(df, agg_df, rs_files, supplier_registry_cfg, script_dir):
    """Bank reconciliation, supplier enrichment, aging, waybills, and excel writes.

    Returns dict with all supplier/bank results needed for data dict assembly.
    """
    # ----- ხელით გადახდების ჟურნალი (ყველა კომპანია RS-იდან) -----
    sync_manual_payments_journal(rs_files)
    supplier_master = build_supplier_master(
        rs_files, supplier_registry=supplier_registry_cfg
    )
    # ----- Merge with Bank Payments -----
    (
        bank_payments,
        bank_unmatched_rows,
        _bank_reconciliation_ok,
        bank_reconciliation_audit,
        bank_reconciliation_status_rows,
    ) = get_bank_payments(
        rs_files,
        supplier_registry=supplier_registry_cfg,
        supplier_master=supplier_master,
    )
    bank_unmatched_sum = float(
        (bank_reconciliation_audit.get("ambiguous_amount") or 0)
        + (bank_reconciliation_audit.get("unmatched_amount") or 0)
    )
    bank_unmatched_analysis = analyze_bank_unmatched_rows(bank_unmatched_rows)
    logger.info(
        "ბანკი — strict audit: total %s ხაზი / %s ₾ | matched %s (%s ₾)",
        bank_reconciliation_audit.get('total_outgoing_relevant_rows', 0),
        f"{float(bank_reconciliation_audit.get('total_outgoing_relevant_amount') or 0):,.2f}",
        bank_reconciliation_audit.get('matched_high_confidence_rows', 0),
        f"{float(bank_reconciliation_audit.get('matched_high_confidence_amount') or 0):,.2f}",
    )
    logger.info(
        "ბანკი — არამიბმული ხაზები (RS-თან): %s ხაზი, %s ₾",
        len(bank_unmatched_rows), f"{bank_unmatched_sum:,.2f}",
    )
    logger.info(
        "ბანკი — ავტომატური კატეგორიზაცია: %s ₾ (არაკატეგორიზებული: %s ₾)",
        f"{bank_unmatched_analysis['categorized_total_ge']:,.2f}",
        f"{bank_unmatched_analysis['uncategorized_total_ge']:,.2f}",
    )
    if bank_unmatched_analysis.get("manual_override_approved_lines", 0) or bank_unmatched_analysis.get("manual_override_rejected_lines", 0):
        logger.info(
            "ხელით override: approve %s | reject %s",
            bank_unmatched_analysis.get('manual_override_approved_lines', 0),
            bank_unmatched_analysis.get('manual_override_rejected_lines', 0),
        )
    if float(bank_unmatched_analysis.get("dynamic_promoted_total_ge") or 0) > 0:
        logger.info(
            "მათგან ავტო-ჯგუფებით დაჭერილი: %s ₾ (%s ხაზი)",
            f"{bank_unmatched_analysis['dynamic_promoted_total_ge']:,.2f}",
            bank_unmatched_analysis.get('dynamic_promoted_line_count', 0),
        )

    agg_df['supplier_id'] = agg_df['ორგანიზაცია'].apply(_extract_tax_id_from_org)
    strict_bank_only_map = (
        bank_reconciliation_audit.get("strict_payments_by_supplier") or {}
    )
    manual_only = (
        bank_reconciliation_audit.get("manual_payments_by_supplier") or {}
    )

    supplier_truth_cache = {}

    def _supplier_truth_fields(s_id):
        if s_id is None or pd.isna(s_id):
            return {
                "supplier_truth_summary": "",
                "supplier_truth_sources": [],
                "official_name_truth_source": "",
            }
        tid = str(s_id).strip()
        if not tid or tid.lower() == "nan":
            return {
                "supplier_truth_summary": "",
                "supplier_truth_sources": [],
                "official_name_truth_source": "",
            }
        cached = supplier_truth_cache.get(tid)
        if cached is None:
            truth_context = _supplier_truth_context(tid, supplier_master)
            cached = {
                "supplier_truth_summary": str(
                    truth_context.get("supplier_truth_summary") or ""
                ),
                "supplier_truth_sources": list(
                    truth_context.get("truth_sources") or []
                ),
                "official_name_truth_source": str(
                    truth_context.get("official_name_truth_source") or ""
                ),
            }
            supplier_truth_cache[tid] = cached
        return cached
    
    def get_paid_amount(s_id):
        if not s_id: return 0.0
        return bank_payments.get(s_id, 0.0)

    def get_strict_bank_paid(s_id):
        if not s_id:
            return 0.0
        return float(strict_bank_only_map.get(s_id, 0) or 0)
        
    agg_df['total_paid'] = agg_df['supplier_id'].apply(get_paid_amount)
    def get_manual_paid(s_id):
        if not s_id:
            return 0.0
        return float(manual_only.get(s_id, 0) or 0)

    agg_df['manual_paid'] = agg_df['supplier_id'].apply(get_manual_paid)
    agg_df['strict_bank_paid'] = agg_df['supplier_id'].apply(get_strict_bank_paid)
    agg_df['bank_paid'] = agg_df['strict_bank_paid']
    agg_df['total_debt'] = agg_df['total_effective'] - agg_df['total_paid']
    agg_df['payment_scope'] = agg_df.apply(
        lambda row: describe_supplier_payment_scope(
            row.get('strict_bank_paid'), row.get('manual_paid')
        ).get('payment_scope'),
        axis=1,
    )
    agg_df['payment_scope_note'] = agg_df.apply(
        lambda row: describe_supplier_payment_scope(
            row.get('strict_bank_paid'), row.get('manual_paid')
        ).get('payment_scope_note'),
        axis=1,
    )
    agg_df['supplier_truth_summary'] = agg_df['supplier_id'].apply(
        lambda s_id: _supplier_truth_fields(s_id).get(
            'supplier_truth_summary', ''
        )
    )
    agg_df['supplier_truth_sources'] = agg_df['supplier_id'].apply(
        lambda s_id: list(
            _supplier_truth_fields(s_id).get('supplier_truth_sources') or []
        )
    )
    agg_df['official_name_truth_source'] = agg_df['supplier_id'].apply(
        lambda s_id: _supplier_truth_fields(s_id).get(
            'official_name_truth_source', ''
        )
    )

    rs_ids = set(agg_df['supplier_id'].dropna().astype(str))
    paid_mapped_to_rs = sum(bank_payments.get(sid, 0.0) for sid in rs_ids)
    bank_orphan = sum(amt for pid, amt in bank_payments.items() if pid not in rs_ids)
    logger.info(
        "Reconciliation: RS მომწოდებლებზე მიბმული: %s ₾ | ბანკშია მაგრამ RS სიაში არაა: %s ₾",
        f"{paid_mapped_to_rs:,.2f}", f"{bank_orphan:,.2f}",
    )

    # RS ზედნადებში არ არსებული, მაგრამ manual_payments.csv-ში ან ბანკში (ორფანი) არის
    jfull = read_manual_journal_full(manual_payments_csv_path())
    bank_tids_positive = {
        k
        for k, v in bank_payments.items()
        if k and float(v or 0) != 0
    }
    extra_rows = []
    extra_supplier_count = 0
    for tid in set(jfull.keys()) | bank_tids_positive:
        if tid in rs_ids:
            continue
        tp = float(bank_payments.get(tid, 0) or 0)
        mp = float((jfull.get(tid) or {}).get("amount", 0) or 0)
        if tp == 0 and mp == 0:
            continue
        co = str((jfull.get(tid) or {}).get("company") or "").strip()
        if not co or co == "(არაა RS ზედნადებში)":
            co = f"({tid}) — არაა RS ზედნადებში"
        extra_rows.append(
            {
                "ორგანიზაცია": co,
                "waybills_count": 0,
                "total_nominal": 0.0,
                "total_cancelled": 0.0,
                "total_returned": 0.0,
                "total_effective": 0.0,
                "supplier_id": tid,
                "total_paid": tp,
                "manual_paid": mp,
                "strict_bank_paid": tp - mp,
                "bank_paid": tp - mp,
                "total_debt": 0.0 - tp,
                "payment_scope": describe_supplier_payment_scope(tp - mp, mp).get(
                    "payment_scope"
                ),
                "payment_scope_note": describe_supplier_payment_scope(
                    tp - mp, mp
                ).get("payment_scope_note"),
            }
        )
    if extra_rows:
        extra_supplier_count = len(extra_rows)
        agg_df = pd.concat(
            [agg_df, pd.DataFrame(extra_rows)], ignore_index=True
        )
        logger.info(
            "დეშბორდი: +%s მომწოდებელი (მხოლოდ ჟურნალი/ბანკი, RS ზედნადის გარეშე)",
            extra_supplier_count,
        )

    # Sort
    agg_df = agg_df.sort_values('total_effective', ascending=False)

    # ----- მომწოდებლების ცხრილის გაწმენდა (0% შეცდომის წესი) -----
    # მხოლოდ კომპანიები, რომლებმაც RS-ის ზედნადებები გაწერეს, უნდა იყვნენ
    # ცხრილში. გამოვაცილოთ:
    #   1) საკუთარი კომპანია (OWN_TAX_ID) — შიდა ზედნადები / მაღაზიათშორისი
    #      გადარიცხვა მომწოდებლად არ უნდა ჩაითვალოს;
    #   2) ხაზები 0 ზედნადებით — ე.ი. „არაა RS ზედნადებში" სინთეტიკური
    #      placeholder-ები manual journal-ის ან off-bank გადახდებისთვის.
    pre_filter_count = len(agg_df)
    own_company_mask = agg_df['supplier_id'] == OWN_TAX_ID
    no_waybill_mask = agg_df['waybills_count'].fillna(0).astype(int) <= 0
    drop_mask = own_company_mask | no_waybill_mask
    if drop_mask.any():
        own_company_dropped = int(own_company_mask.sum())
        no_waybill_dropped = int(no_waybill_mask.sum())
        agg_df = agg_df.loc[~drop_mask].copy()
        # filter-მა მოაცილა "მხოლოდ ჟურნალი/ბანკი" placeholder-ები →
        # extra_supplier_count გადავტვირთოთ რომ meta-მ TrustBanner-ს არ
        # აჩვენოს warning ცხრილიდან გამქრალ row-ებზე.
        extra_supplier_count = 0
        logger.info(
            "მომწოდებლების ცხრილი გაწმენდილია: -%s (%s+%s) → %s კომპანია "
            "(საკუთარი ფირმა + 0-ზედნადებიანი placeholder-ები მოიხსნა)",
            pre_filter_count - len(agg_df),
            own_company_dropped,
            no_waybill_dropped,
            len(agg_df),
        )

    # Cleanup
    del agg_df['supplier_id']

    suppliers_data = agg_df.replace({float('nan'): None}).to_dict(orient='records')
    supplier_aging_result = build_supplier_aging(suppliers_data, df)
    ap_monthly_trend = build_ap_monthly_trend(
        df,
        bank_payments,
        strict_bank_payments=strict_bank_only_map,
        manual_payments=manual_only,
    )
    logger.info("Aging summary:")
    for bucket in AGING_BUCKET_ORDER:
        b = supplier_aging_result["summary"].get(
            bucket, {"count": 0, "total_debt": 0.0}
        )
        logger.info(
            "  %s დღე: %s მომწოდებელი, %s ₾",
            bucket, int(b.get('count') or 0),
            f"{float(b.get('total_debt') or 0):,.2f}",
        )
    if ap_monthly_trend:
        logger.info(
            "AP trend: %s თვე, ბოლო თვე cumulative debt: %s ₾",
            len(ap_monthly_trend),
            f"{float(ap_monthly_trend[-1].get('cumulative_debt') or 0):,.2f}",
        )
    else:
        logger.info("AP trend: 0 თვე, ბოლო თვე cumulative debt: 0.00 ₾")

    download_dir = os.path.join(script_dir, "download")
    bank_unmatched_only_rows = bank_reconciliation_status_rows.get("unmatched", [])
    bank_ambiguous_rows = bank_reconciliation_status_rows.get("ambiguous", [])
    bank_non_supplier_rows = bank_reconciliation_status_rows.get("non_supplier", [])
    bank_matched_high_rows = bank_reconciliation_status_rows.get("matched_high", [])
    supplier_payment_lines = build_supplier_payment_lines(
        bank_matched_high_rows, load_manual_payment_rows()
    )
    write_suppliers_excel(suppliers_data, download_dir)
    write_bank_unmatched_excel(
        [_line_for_excel(r) for r in bank_unmatched_only_rows],
        download_dir,
    )
    write_bank_ambiguous_excel(bank_ambiguous_rows, download_dir)
    write_bank_non_supplier_excel(bank_non_supplier_rows, download_dir)
    write_bank_matched_high_excel(bank_matched_high_rows, download_dir)
    write_bank_unmatched_categories_excel(bank_unmatched_analysis, download_dir)
    write_bank_unclassified_top_excel(bank_unmatched_analysis, download_dir)
    write_bank_overrides_audit_excel(bank_unmatched_analysis, download_dir)

    safe_cols = {
        'გააქტიურების თარ.': 'date',
        'ორგანიზაცია': 'supplier',
        'ზედნადები': 'waybill_number',
        'თანხა': 'nominal_amount',
        'სტატუსი': 'status',
        'ტიპი': 'type',
        'ეფექტური თანხა': 'effective_amount'
    }
    
    waybills_df = df[[c for c in safe_cols.keys() if c in df.columns]].rename(columns=safe_cols)
    waybills_df = waybills_df.fillna("N/A")

    waybills_data = waybills_df.to_dict(orient='records')
    supplier_waybill_lines = _build_supplier_waybill_lines(waybills_data)

    manual_grand = float(sum(manual_only.values()))
    return {
        "suppliers_data": suppliers_data,
        "waybills_data": waybills_data,
        "supplier_aging_result": supplier_aging_result,
        "ap_monthly_trend": ap_monthly_trend,
        "bank_reconciliation_audit": bank_reconciliation_audit,
        "bank_unmatched_analysis": bank_unmatched_analysis,
        "bank_unmatched_sum": bank_unmatched_sum,
        "bank_orphan": bank_orphan,
        "extra_supplier_count": extra_supplier_count,
        "manual_grand": manual_grand,
        "manual_only": manual_only,
        "strict_bank_only_map": strict_bank_only_map,
        "supplier_payment_lines": supplier_payment_lines,
        "supplier_waybill_lines": supplier_waybill_lines,
    }


def _build_supplier_waybill_lines(waybills_data):
    """Index waybills by supplier tax_id for the SupplierModal "ზედნადებები"
    panel. Drops cancelled (გაუქმებული) entries — keeps active + completed +
    return-type rows so the user sees the full live picture per supplier."""
    by_tid = {}
    for row in waybills_data or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip()
        if status == "გაუქმებული":
            continue
        org = str(row.get("supplier") or "")
        tid = str(_extract_tax_id_from_org(org) or "").strip()
        if not tid:
            continue
        date_str = str(row.get("date") or "")[:10]
        try:
            amount = float(row.get("effective_amount") or row.get("nominal_amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        wb_type = str(row.get("type") or "").strip()
        by_tid.setdefault(tid, []).append({
            "date": date_str,
            "waybill_number": str(row.get("waybill_number") or ""),
            "amount": amount,
            "status": status,
            "type": wb_type,
            "is_return": "დაბრუნება" in wb_type,
        })
    for tid, lines in by_tid.items():
        lines.sort(key=lambda r: r.get("date") or "", reverse=True)
    return by_tid


def _read_and_parse_rs(rs_files, object_mapping):
    """Read RS Excel files, parse columns, compute amounts/flags, aggregate by org.

    Returns (df, agg_df) or (None, None) if no RS data.
    """
    from dashboard_pipeline.rsge_cache import read_waybill_file
    all_rs = []
    for f in rs_files:
        try:
            df = read_waybill_file(f)
            df['file_source'] = os.path.basename(f)
            all_rs.append(df)
        except Exception as e:
            logger.error("RS file %s: %s", f, e)

    if not all_rs:
        logger.warning("No RS files found!")
        return None, None

    df = pd.concat(all_rs, ignore_index=True)
    logger.info(
        "RS: ნომინალი + რეალური ჯამი + დაბრუნება — data.json (total_cancelled შიგნით, UI-ზე არა)."
    )
    rs_location_col = next(
        (c for c in df.columns if "მიწოდების ადგილი" in str(c)),
        None,
    )
    if not rs_location_col:
        rs_location_col = next(
            (
                c
                for c in df.columns
                if "მიწოდების" in str(c) and "ადგილი" in str(c)
            ),
            None,
        )
    if rs_location_col:
        df["object"] = df[rs_location_col].apply(
            lambda x: detect_object(
                "rs_waybill",
                rs_location=x,
                object_mapping=object_mapping,
            )
        )
    else:
        df["object"] = detect_object("rs_waybill", object_mapping=object_mapping)

    # Parse Dates safely
    if 'გააქტიურების თარ.' in df.columns:
        df['გააქტიურების თარ.'] = df['გააქტიურების თარ.'].astype(str)
    
    # Flags checking text
    df['უკან დაბრუნება (ფლეგი)'] = df['ტიპი'].astype(str).str.contains('უკან დაბრუნება', case=False, na=False)
    df['გაუქმებული (ფლეგი)'] = df['სტატუსი'].astype(str).str.contains('გაუქმებული', case=False, na=False)
    
    # Calculate amounts
    raw_amt = pd.to_numeric(df['თანხა'], errors='coerce').fillna(0.0)
    df['ნომინალური თანხა'] = raw_amt
    df['გაუქმებული_თანხა'] = raw_amt.where(df['გაუქმებული (ფლეგი)'], 0.0)

    df['ეფექტური თანხა'] = df.apply(get_effective, axis=1)
    df['დაბრუნებული თანხა'] = df.apply(get_returned, axis=1)
    df['_აქტიური_ხაზი'] = (~df['გაუქმებული (ფლეგი)']).astype(int)
    rs_object_agg = df.groupby('object').agg(
        waybills_count=('_აქტიური_ხაზი', 'sum'),
        total_effective=('ეფექტური თანხა', 'sum'),
    ).reset_index()
    rs_object_summary = ", ".join(
        f"{r['object']}: {float(r['total_effective']):,.2f} ₾"
        for _, r in rs_object_agg.iterrows()
    )
    logger.info("RS ობიექტების ეფექტური ჯამი: %s", rs_object_summary or 'მონაცემი არ არის')

    # ----- ორგანიზაციის სახელის ნორმალიზაცია (1) -----
    # RS-ის ექსპორტი ხშირად ერთსა და იმავე ID-ს ორი ფორმით აჩვენებს:
    #   "(415118535) შპს ვემედინა"      — ნაწილი ფაილებიდან
    #   "(415118535-დღგ) შპს ვემედინა"  — ნაწილი ფაილებიდან (VAT ფლაგი)
    # ეს groupby-ს თვალში ორი განსხვავებული "ორგანიზაცია"-ა და ერთი
    # მომწოდებელი ცხრილში 2-ჯერ ჩნდება + ბანკის გადახდა (tax_id-ით) ორჯერვე
    # ენიშნება → ცრუ overpayment. ნორმალიზაცია „(ID) NAME" ფორმაზე ერთიანად.
    df['ორგანიზაცია'] = df['ორგანიზაცია'].astype(str).str.replace(
        r'\(\s*(\d{8,11})\s*[^)]*\)', r'(\1)', regex=True,
    )
    # trailing whitespace/control chars (e.g. "შპს ტიტე 2024\r\r")
    df['ორგანიზაცია'] = df['ორგანიზაცია'].str.replace(r'\s+$', '', regex=True)

    # ----- ნორმალიზაცია (2): ერთი tax_id → ერთი კანონიკური სახელი -----
    # ერთი ID-ით სხვადასხვა სახელი მაინც ხდება (RS ხან ლათინურად ხან
    # ქართულად ხან „შპს" → „სს" გადააქცევს ერთსა და იმავე ID-ში). ვიჭერ
    # ყველაზე გრძელ/ინფორმატიულ ვერსიას ყოველი tax_id-ისთვის და მთლიან
    # df-ში იმავე სახელად ვცვლი — groupby ერთხაზიანად ხდება.
    df['_tax_id'] = df['ორგანიზაცია'].apply(_extract_tax_id_from_org).fillna('')

    def _strip_taxid_prefix(org):
        return re.sub(r'^\(\s*\d{8,11}[^)]*\)\s*', '', str(org)).strip()

    canonical_names_by_tax_id = (
        df.assign(_clean_name=df['ორგანიზაცია'].apply(_strip_taxid_prefix))
          .loc[df['_tax_id'] != '']
          .groupby('_tax_id')['_clean_name']
          .apply(lambda s: max((n for n in s.dropna() if n), key=len, default=''))
          .to_dict()
    )

    def _canonicalize_org(row):
        tid = row['_tax_id']
        if not tid:
            return row['ორგანიზაცია']
        name = canonical_names_by_tax_id.get(tid, '')
        return f'({tid}) {name}'.strip() if name else f'({tid})'

    df['ორგანიზაცია'] = df.apply(_canonicalize_org, axis=1)
    df = df.drop(columns=['_tax_id'])

    # Group by Organization
    agg_df = df.groupby('ორგანიზაცია').agg(
        waybills_count=('_აქტიური_ხაზი', 'sum'),
        total_nominal=('ნომინალური თანხა', 'sum'),
        total_cancelled=('გაუქმებული_თანხა', 'sum'),
        total_returned=('დაბრუნებული თანხა', 'sum'),
        total_effective=('ეფექტური თანხა', 'sum'),
    ).reset_index()

    return df, agg_df


def run():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    cfg = _load_pipeline_config(script_dir)
    object_mapping = cfg["object_mapping"]
    generated_at = cfg["generated_at"]
    source_manifest = cfg["source_manifest"]
    source_manifest_summary = cfg["source_manifest_summary"]
    budget_config = cfg["budget_config"]
    sector_benchmarks = cfg["sector_benchmarks"]
    supplier_registry_cfg = cfg["supplier_registry_cfg"]
    config_validation = cfg["config_validation"]

    inc = _collect_income_bundles(script_dir, object_mapping)
    tbc_card_income_bundle = inc["tbc_card_income_bundle"]
    pos_terminal_all_rows = inc["pos_terminal_all_rows"]
    pos_terminal_income_bundle = inc["pos_terminal_income_bundle"]
    tbc_expenses_bundle = inc["tbc_expenses_bundle"]
    bog_expenses_bundle = inc["bog_expenses_bundle"]
    samurneo_bundle = inc["samurneo_bundle"]
    tax_flow_bundle = inc["tax_flow_bundle"]
    tbc_foodmart_cashback_bundle = inc["tbc_foodmart_cashback_bundle"]

    logger.info("Reading RS files...")
    rs_files = list_rsge_waybill_paths()
    imported_products_bundle = collect_imported_products_bundle(
        rs_files, object_mapping=object_mapping
    )
    imported_overall = imported_products_bundle.get("overall") or {}
    logger.info(
        "შემოტანილი პროდუქცია (reference): %s ფაილი, %s ხაზი, %s ₾",
        imported_products_bundle.get('files_read_count', 0),
        int(imported_overall.get('row_count') or 0),
        f"{float(imported_overall.get('total_amount_ge') or 0):,.2f}",
    )
    if imported_products_bundle.get("truncation_suspected_any"):
        logger.warning(
            "truncate/export limit ეჭვი: %s",
            ", ".join(imported_products_bundle.get("truncation_suspected_files") or []),
        )
    retail_sales_bundle = collect_retail_sales_bundle(
        object_mapping=object_mapping, use_cache=True
    )
    retail_overall = retail_sales_bundle.get("overall") or {}
    logger.info(
        "Retail sales (reference-only): %s ფაილი, %s ხაზი, revenue %s ₾ | profit %s ₾ | margin %s%%",
        retail_sales_bundle.get('files_read_count', 0),
        int(retail_overall.get('row_count') or 0),
        f"{float(retail_overall.get('revenue_ge') or 0):,.2f}",
        f"{float(retail_overall.get('profit_ge') or 0):,.2f}",
        f"{float(retail_overall.get('gross_margin_pct') or 0):.2f}",
    )
    retail_duplicate_policy = retail_sales_bundle.get("duplicate_policy") or {}
    if int(retail_duplicate_policy.get("excluded_file_count") or 0) > 0:
        logger.warning(
            "duplicate-suspected ფაილი totals-იდან გამორიცხულია: %s",
            ", ".join(retail_duplicate_policy.get("excluded_files") or []),
        )
    df, agg_df = _read_and_parse_rs(rs_files, object_mapping)

    if df is None:
        supplier_aging_result = {"suppliers": [], "summary": _empty_aging_summary()}
        ap_monthly_trend = []
        bank_reconciliation_audit = empty_bank_reconciliation_audit()
        data = {
            "suppliers": [],
            "waybills": [],
            "imported_products": imported_products_bundle,
            "retail_sales": retail_sales_bundle,
            "tbc_card_income": {
                "label_ka": tbc_card_income_bundle["label_ka"],
                "total_ge": float(tbc_card_income_bundle["total_ge"]),
                "line_count": int(tbc_card_income_bundle["line_count"]),
                "rows_preview": tbc_card_income_bundle["lines"][:300],
                "monthly_summary": _monthly_summary(tbc_card_income_bundle["lines"]),
            },
            "pos_terminal_income": pos_terminal_income_bundle,
            "tbc_expenses": tbc_expenses_public_json(tbc_expenses_bundle),
            "bog_expenses": bog_expenses_public_json(bog_expenses_bundle),
            "tbc_samurneo": samurneo_bundle,
            "tax_flow": tax_flow_bundle,
            "tbc_foodmart_cashback": tbc_foodmart_cashback_bundle,
            "bank_unmatched_analysis": analyze_bank_unmatched_rows([]),
            "bank_reconciliation_audit": bank_reconciliation_audit,
            "supplier_aging": supplier_aging_result["suppliers"],
            "aging_summary": supplier_aging_result["summary"],
            "ap_monthly_trend": ap_monthly_trend,
            "meta": {
                "manual_payments_total": 0.0,
                "manual_payments_rows_with_amount": 0,
                "suppliers_only_journal_or_bank": 0,
                "bank_orphan_total_ge": 0.0,
                "bank_unmatched_total_ge": 0.0,
                "bank_unmatched_line_count": 0,
                "bank_unmatched_categorized_total_ge": 0.0,
                "bank_unmatched_uncategorized_total_ge": 0.0,
                "bank_unmatched_dynamic_promoted_total_ge": 0.0,
                "bank_unmatched_confidence_high_ge": 0.0,
                "bank_unmatched_confidence_medium_ge": 0.0,
                "bank_unmatched_confidence_low_ge": 0.0,
                "bank_unmatched_manual_override_approved_lines": 0,
                "bank_unmatched_manual_override_rejected_lines": 0,
                "bank_recon_total_outgoing_amount": 0.0,
                "bank_recon_matched_high_amount": 0.0,
                "bank_recon_ambiguous_amount": 0.0,
                "bank_recon_non_supplier_amount": 0.0,
                "bank_recon_unmatched_amount": 0.0,
                "bank_recon_skipped_amount": 0.0,
                **_build_base_meta(inc, retail_overall, retail_duplicate_policy),
            },
        }
    else:
        rs_result = _process_rs_suppliers(
            df, agg_df, rs_files, supplier_registry_cfg, script_dir
        )
        suppliers_data = rs_result["suppliers_data"]
        waybills_data = rs_result["waybills_data"]
        supplier_aging_result = rs_result["supplier_aging_result"]
        ap_monthly_trend = rs_result["ap_monthly_trend"]
        bank_reconciliation_audit = rs_result["bank_reconciliation_audit"]
        bank_unmatched_analysis = rs_result["bank_unmatched_analysis"]
        bank_unmatched_sum = rs_result["bank_unmatched_sum"]
        bank_orphan = rs_result["bank_orphan"]
        extra_supplier_count = rs_result["extra_supplier_count"]
        manual_grand = rs_result["manual_grand"]
        manual_only = rs_result["manual_only"]

        # ----- IBAN/Tax-ID კონფლიქტის audit -----
        # თუ ერთი ანგარიშის ნომერი ბანკის ამონაწერებში სხვადასხვა საგადასახადო
        # ID-ით ფიქსირდება, ეს ჩვეულებრივ ნიშნავს ფირმის გადარქმევას ან
        # ხელახალ რეგისტრაციას (იგივე იურიდიული პირი). user-ის წესი არ
        # გვაერთიანებინებს ცხრილში (სხვადასხვა ID = სხვადასხვა კომპანია),
        # მაგრამ წინასწარ ვაფრთხილებთ რომ ხელით შემოწმდეს.
        iban_conflicts = _audit_iban_taxid_conflicts(script_dir)

        data = {
            "suppliers": suppliers_data,
            "waybills": waybills_data,
            "imported_products": imported_products_bundle,
            "retail_sales": retail_sales_bundle,
            "tbc_card_income": {
                "label_ka": tbc_card_income_bundle["label_ka"],
                "total_ge": float(tbc_card_income_bundle["total_ge"]),
                "line_count": int(tbc_card_income_bundle["line_count"]),
                "rows_preview": tbc_card_income_bundle["lines"][:300],
                "monthly_summary": _monthly_summary(tbc_card_income_bundle["lines"]),
            },
            "pos_terminal_income": pos_terminal_income_bundle,
            "tbc_expenses": tbc_expenses_public_json(tbc_expenses_bundle),
            "bog_expenses": bog_expenses_public_json(bog_expenses_bundle),
            "tbc_samurneo": samurneo_bundle,
            "tax_flow": tax_flow_bundle,
            "tbc_foodmart_cashback": tbc_foodmart_cashback_bundle,
            "bank_unmatched_analysis": bank_unmatched_analysis,
            "bank_reconciliation_audit": bank_reconciliation_audit,
            "supplier_aging": supplier_aging_result["suppliers"],
            "aging_summary": supplier_aging_result["summary"],
            "ap_monthly_trend": ap_monthly_trend,
            "supplier_payment_lines": rs_result.get("supplier_payment_lines") or {},
            "supplier_waybill_lines": rs_result.get("supplier_waybill_lines") or {},
            # supplier_concentration ცარიელ placeholder-ად ვამატებ; ქვემოთ
            # data dict-ის აშენების მერე ვაქცევ რეალურ payload-ად რომ
            # `prepare_supplier_brief` ხედავდეს ფინალურ suppliers + meta-ს.
            "supplier_concentration": None,
            "meta": {
                "manual_payments_total": manual_grand,
                "manual_payments_rows_with_amount": len(
                    [a for a in manual_only.values() if a > 0]
                ),
                "suppliers_only_journal_or_bank": extra_supplier_count,
                "iban_taxid_conflicts": iban_conflicts,
                "bank_orphan_total_ge": float(bank_orphan),
                "bank_unmatched_total_ge": float(bank_unmatched_sum),
                "bank_unmatched_line_count": int(
                    (bank_reconciliation_audit.get("ambiguous_rows") or 0)
                    + (bank_reconciliation_audit.get("unmatched_rows") or 0)
                ),
                "bank_unmatched_categorized_total_ge": float(
                    bank_unmatched_analysis.get("categorized_total_ge") or 0
                ),
                "bank_unmatched_uncategorized_total_ge": float(
                    bank_unmatched_analysis.get("uncategorized_total_ge") or 0
                ),
                "bank_unmatched_dynamic_promoted_total_ge": float(
                    bank_unmatched_analysis.get("dynamic_promoted_total_ge") or 0
                ),
                "bank_unmatched_confidence_high_ge": float(
                    (bank_unmatched_analysis.get("confidence_totals") or {}).get("high", 0)
                ),
                "bank_unmatched_confidence_medium_ge": float(
                    (bank_unmatched_analysis.get("confidence_totals") or {}).get("medium", 0)
                ),
                "bank_unmatched_confidence_low_ge": float(
                    (bank_unmatched_analysis.get("confidence_totals") or {}).get("low", 0)
                ),
                "bank_unmatched_manual_override_approved_lines": int(
                    bank_unmatched_analysis.get("manual_override_approved_lines", 0)
                ),
                "bank_unmatched_manual_override_rejected_lines": int(
                    bank_unmatched_analysis.get("manual_override_rejected_lines", 0)
                ),
                "bank_recon_total_outgoing_amount": float(
                    bank_reconciliation_audit.get("total_outgoing_relevant_amount") or 0
                ),
                "bank_recon_matched_high_amount": float(
                    bank_reconciliation_audit.get("matched_high_confidence_amount") or 0
                ),
                "bank_recon_ambiguous_amount": float(
                    bank_reconciliation_audit.get("ambiguous_amount") or 0
                ),
                "bank_recon_non_supplier_amount": float(
                    bank_reconciliation_audit.get("non_supplier_amount") or 0
                ),
                "bank_recon_unmatched_amount": float(
                    bank_reconciliation_audit.get("unmatched_amount") or 0
                ),
                "bank_recon_skipped_amount": float(
                    bank_reconciliation_audit.get("skipped_explicit_amount") or 0
                ),
                **_build_base_meta(inc, retail_overall, retail_duplicate_policy),
            },
        }

    # Sprint 5.1 — VAT reconciliation section (computed from raw pipeline outputs)
    financial_analysis_dir = os.path.join(script_dir, "Financial_Analysis")
    audit_excel_path = find_audit_excel(financial_analysis_dir)
    invoices_issued_path = find_invoices_issued_excel(financial_analysis_dir)
    cash_journal_path = os.path.join(financial_analysis_dir, "cash_outflow_journal.csv")
    manual_rows = read_manual_journal_rows(manual_payments_csv_path())
    data["vat_reconciliation"] = compute_vat_reconciliation(
        retail_sales_bundle=retail_sales_bundle,
        tbc_card_income_bundle=tbc_card_income_bundle,
        bog_pos_income_bundle=inc["bog_pos_income_bundle"],
        manual_journal_full=manual_rows,
        audit_excel_path=audit_excel_path,
        cash_outflow_journal_path=cash_journal_path,
        invoices_issued_path=invoices_issued_path,
    )
    vat_summary = data["vat_reconciliation"]["summary"]
    logger.info(
        "VAT reconciliation: %s თვე (red %s | yellow %s | green %s | no-declared %s) · "
        "total_real %s ₾ (gross) / %s ₾ (net) · declared %s ₾ (net) · "
        "gap %s ₾ (net basis, primary) · unaccounted cash %s ₾",
        vat_summary["months_total"],
        vat_summary["months_red"],
        vat_summary["months_yellow"],
        vat_summary["months_green"],
        vat_summary["months_no_declared"],
        f"{vat_summary['total_real_ge']:,.2f}",
        f"{vat_summary.get('total_real_net_ge', 0):,.2f}",
        f"{vat_summary['total_declared_ge']:,.2f}",
        f"{vat_summary['total_gap_ge']:+,.2f}",
        f"{vat_summary['total_unaccounted_cash_ge']:,.2f}",
    )

    _enrich_meta(data, generated_at, source_manifest, source_manifest_summary, config_validation)

    _build_analytics(
        data, inc, object_mapping, budget_config, sector_benchmarks,
        supplier_aging_result,
    )

    # ----- მომწოდებლების კონცენტრაცია (HHI + Top-N + ბერკეტი) -----
    # widget-ი UI-ში არსებობდა, მაგრამ pipeline ფუნქციას არ უძახდა — ე.ი.
    # ცოცხალი მონაცემები არ გვქონდა. ახლა ვადგენ ფინალურ data-ზე
    # (suppliers + analytics უკვე ჩაწერილია).
    try:
        data["supplier_concentration"] = build_supplier_concentration(data)
        sc = data["supplier_concentration"]
        if isinstance(sc, dict) and sc.get("available"):
            conc = sc.get("concentration") or {}
            logger.info(
                "მომწოდებლების კონცენტრაცია: HHI=%s, Top-5=%.1f%%, Top-10=%.1f%%",
                int(conc.get("hhi_index") or 0),
                float(conc.get("top_5_share_pct") or 0),
                float(conc.get("top_10_share_pct") or 0),
            )
        else:
            logger.warning(
                "მომწოდებლების კონცენტრაცია — ვერ აშენდა: %s",
                (sc or {}).get("reason_ka") or "უცნობი",
            )
    except Exception as exc:
        logger.warning("მომწოდებლების კონცენტრაცია — ვერ აშენდა: %s", exc)

    # MegaPlus daily SQL Server backup (PLUS_*.zip in per-store watch folders).
    # Auto-discovers two layouts under Financial_Analysis:
    #   - legacy `მეგა პლუს backup*` siblings
    #   - `მეგაპლიუსის არქიტექტურა/<store>/` subfolders with PLUS_*.zip
    # Adding a new store = drop ZIPs into either layout, no code change.
    #
    # Two-phase design:
    #   1. process_all_stores — restores any new ZIP into its per-store SQL DB
    #      and refreshes the cached `_megaplus_live.json` next to each folder.
    #   2. read_combined_rollup — always reads the cached JSONs so data.json
    #      keeps the supplier rollup populated on EVERY pipeline run, not just
    #      runs that happen to pick up a new ZIP.
    #
    # Runs BEFORE supplier_profitability so the matcher can prefer
    # MegaPlus-derived per-product data over the (now retired) Excel POS
    # `retail_sales.by_product`. Non-fatal on failure — the rest of the
    # dashboard still builds.
    try:
        from dashboard_pipeline.megaplus_backup import _discover_watch_folders as _megaplus_discover
        fa_dir = Path(script_dir) / "Financial_Analysis"
        megaplus_folders = _megaplus_discover(fa_dir)
        if megaplus_folders:
            try:
                refreshed = _process_megaplus_stores(megaplus_folders)
            except Exception as exc:
                logger.warning("MegaPlus DB backup-ი refresh ვერ მოხერხდა (cache-ი მაინც გამოვიყენო): %s", exc)
                refreshed = None
            if refreshed is not None:
                for store_id, rollup in refreshed.get("stores", {}).items():
                    logger.info(
                        "MegaPlus DB backup-ი refresh — store %s: %s მომწოდებელი, %s ₾ გაყიდვა, %.2f%% მარჟა",
                        store_id,
                        len(rollup.get("suppliers", [])),
                        f"{float(rollup['totals']['revenue']):,.0f}",
                        float(rollup['totals']['margin_pct'] or 0),
                    )
            else:
                logger.info("MegaPlus DB backup-ი — ახალი ZIP არ არის, cache-დან წაიკითხება")

            megaplus_combined = _read_megaplus_combined(megaplus_folders)
            if megaplus_combined is not None:
                data["megaplus_live"] = megaplus_combined
                logger.info(
                    "MegaPlus cache → data.json: %s store ჩაიტვირთა (%s)",
                    len(megaplus_combined.get("stores", {})),
                    ", ".join(sorted(megaplus_combined.get("stores", {}).keys())),
                )

                # Pull each store's `category_anomalies` bundle (computed inside
                # _read_supplier_rollups → cached in _megaplus_live.json) up to
                # a single top-level `data["category_anomalies"]` so the
                # frontend tab renders one combined view across stores.
                stores_bundles = []
                totals = {
                    "empty_category_count": 0,
                    "duplicate_cluster_count": 0,
                    "duplicate_minority_product_count": 0,
                    "protected_supplier_distinct_categories": 0,
                }
                for sid, rollup in (megaplus_combined.get("stores") or {}).items():
                    bundle = (rollup or {}).get("category_anomalies")
                    if not bundle:
                        continue
                    stores_bundles.append(bundle)
                    s = bundle.get("summary") or {}
                    for k in totals:
                        totals[k] += int(s.get(k) or 0)
                if stores_bundles:
                    data["category_anomalies"] = {
                        "totals": totals,
                        "stores": stores_bundles,
                    }
                    logger.info(
                        "category_anomalies → data.json: ცარიელი=%d, დუბლიკატი ჯგუფები=%d "
                        "(პროდუქტები=%d), PROTECTED კატეგორიები=%d",
                        totals["empty_category_count"],
                        totals["duplicate_cluster_count"],
                        totals["duplicate_minority_product_count"],
                        totals["protected_supplier_distinct_categories"],
                    )

                # rs.ge ↔ MegaPlus waybill reconciliation. Pure cross-source
                # categorization — surfaces missing receipts, amount mismatches,
                # ghost AP (cancelled-rs-but-received-in-MegaPlus), unrecorded
                # returns/sub-waybills, soft-signal "possible replacement"
                # ±14-day matches, and stale-rs-data flags.
                try:
                    from dashboard_pipeline.waybill_reconciliation import (
                        load_rs_waybills,
                        reconcile,
                    )
                    rsge_paths = list_rsge_waybill_paths()
                    if rsge_paths:
                        rs_df = load_rs_waybills(rsge_paths)
                        per_store_data = {}
                        for sid, rollup in (megaplus_combined.get("stores") or {}).items():
                            wd = (rollup or {}).get("waybill_data")
                            if wd:
                                per_store_data[sid] = wd
                        if not rs_df.empty and per_store_data:
                            recon_bundle = reconcile(rs_df, per_store_data)
                            data["waybill_reconciliation"] = recon_bundle
                            t = recon_bundle.get("totals", {})
                            logger.info(
                                "waybill_reconciliation → data.json: "
                                "🔴 missing=%d (%.0f ₾) · 🔄 wrong_store=%d "
                                "(only_other=%d, duplicate=%d) · 🟠 amount_mismatch=%d · "
                                "👻 ghost_ap=%d · 🟡 returns=%d / sub=%d · "
                                "⚠️ possible_replacement=%d · 🆕 stale=%d "
                                "(filtered closed-store=%d)",
                                t.get("missing", 0), t.get("missing_amount_sum", 0),
                                t.get("wrong_store", 0),
                                t.get("wrong_store_only_other", 0),
                                t.get("wrong_store_duplicate", 0),
                                t.get("amount_mismatch", 0),
                                t.get("ghost_ap", 0),
                                t.get("returns_not_recorded", 0),
                                t.get("sub_waybills_not_recorded", 0),
                                t.get("possible_replacements", 0),
                                t.get("rs_data_stale", 0),
                                t.get("filtered_closed_stores", 0),
                            )
                        else:
                            logger.info("waybill_reconciliation: rs.ge xls or MegaPlus waybill_data missing — skipped")
                    else:
                        logger.info("waybill_reconciliation: rs.ge folder not found — skipped")
                except Exception as exc:
                    logger.warning("waybill_reconciliation: ვერ ჩატარდა: %s", exc)

                # Synthesize a `retail_sales`-shaped bundle from MegaPlus so
                # `RetailSales.jsx` and other downstream consumers (the AI
                # tools, sqlite export, etc.) keep their existing schema
                # after the Excel POS folders were retired. Only injects
                # when the existing retail_sales is empty (no Excel files
                # present) — never overwrites Excel-derived data.
                existing_retail = data.get("retail_sales") or {}
                excel_files_count = int((existing_retail.get("files_read_count") or 0))
                if excel_files_count == 0:
                    synthetic = _synthesize_retail_from_megaplus(megaplus_combined)
                    if synthetic is not None:
                        data["retail_sales"] = synthetic
                        ov = synthetic.get("overall") or {}
                        logger.info(
                            "retail_sales synthesized from MegaPlus: revenue %.0f ₾ / cost %.0f ₾ / "
                            "profit %.0f ₾ / margin %.2f%% / %d products / %d months",
                            float(ov.get("revenue_ge") or 0),
                            float(ov.get("cost_ge") or 0),
                            float(ov.get("profit_ge") or 0),
                            float(ov.get("gross_margin_pct") or 0),
                            int(synthetic.get("products_total_count") or 0),
                            len(synthetic.get("by_month") or []),
                        )
                        # The first _build_analytics pass ran before MegaPlus
                        # synthesized retail_sales — so monthly_pnl had no
                        # cash income. Rebuild now that retail_sales is fully
                        # populated; this overwrites monthly_pnl, financial_
                        # ratios, forecast, budget, valuation, executive.
                        logger.info(
                            "Rebuilding analytics after retail_sales synthesis "
                            "to surface Megaplus სალარო cash income"
                        )
                        _build_analytics(
                            data, inc, object_mapping, budget_config,
                            sector_benchmarks, supplier_aging_result,
                        )
                        # VAT reconciliation also reads retail_sales for max_pos_ge
                        # / cashreg_in_ge. Its first pass at line 1647 ran before
                        # synthesis, so every month had max_pos_ge=0. Recompute
                        # now with the synthesized bundle.
                        data["vat_reconciliation"] = compute_vat_reconciliation(
                            retail_sales_bundle=data["retail_sales"],
                            tbc_card_income_bundle=tbc_card_income_bundle,
                            bog_pos_income_bundle=inc["bog_pos_income_bundle"],
                            manual_journal_full=manual_rows,
                            audit_excel_path=audit_excel_path,
                            cash_outflow_journal_path=cash_journal_path,
                            invoices_issued_path=invoices_issued_path,
                        )
            else:
                logger.info("MegaPlus cache ცარიელია — data.json-ში megaplus_live არ ჩაიდება")
        else:
            logger.info("MegaPlus DB backup-ი — watch folder-ი არ არის, ნაბიჯი გამოტოვდა")
    except Exception as exc:
        logger.warning("MegaPlus DB backup-ი — ვერ ჩაიტვირთა: %s", exc)

    # ----- per-supplier პროდუქციული მოგება (strict barcode JOIN) -----
    # imported_products (ვინ-რა-მომიტანა) ↔ retail by_product (რა-რა-
    # ფასად-გავყიდე) — barcode/code-ით 1:1, name-fuzzy-ი აკრძალულია
    # (memory: project_product_match_barcode_only).
    #
    # Retail source preference (set inside build_supplier_profitability):
    #   1. data["megaplus_live"] (MegaPlus DB direct) — primary going forward.
    #   2. data["retail_sales"]["by_product"] (Excel POS) — legacy fallback.
    #
    # შედეგი წერს per-supplier "profitability" ობიექტს მათ entry-ში
    # data["imported_products"]["suppliers"][i]-ზე, რომ SupplierModal-მ
    # extra fetch-ის გარეშე წაიკითხოს.
    try:
        # retail_known_keys feeds the alias validator's "does this code
        # exist in retail?" check. Same preference order — MegaPlus first.
        retail_known_keys: set[str] = set()
        for store_rollup in ((data.get("megaplus_live") or {}).get("stores") or {}).values():
            for row in store_rollup.get("by_product") or []:
                bc = (row.get("barcode") or "").strip()
                pc = (row.get("product_code") or "").strip()
                if bc:
                    retail_known_keys.add(bc)
                if pc:
                    retail_known_keys.add(pc)
        if not retail_known_keys:
            for row in (data.get("retail_sales") or {}).get("by_product") or []:
                bc = (row.get("barcode") or "").strip()
                pc = (row.get("product_code") or "").strip()
                if bc:
                    retail_known_keys.add(bc)
                if pc:
                    retail_known_keys.add(pc)
        aliases_path = Path(script_dir) / "Financial_Analysis" / "product_aliases.json"
        safe_aliases, alias_errors = _load_aliases(aliases_path, retail_known_keys)
        for err in alias_errors:
            logger.warning("product_aliases.json: %s", err)

        prof = build_supplier_profitability(data, aliases=safe_aliases)
        # ჩაწერე profitability უკან თითოეულ supplier-ზე (tax_id-ით lookup)
        per_sup_by_taxid = {row["tax_id"]: row["profitability"] for row in prof["per_supplier"]}
        for sup_entry in (data.get("imported_products") or {}).get("suppliers") or []:
            tx = sup_entry.get("tax_id") or ""
            if tx in per_sup_by_taxid:
                sup_entry["profitability"] = per_sup_by_taxid[tx]
        # summary ცალკე გასცეს — DataQualityPage-ი წაიკითხავს
        data.setdefault("imported_products", {})["profitability_summary"] = prof["summary"]

        sc = prof["summary"]["supplier_counts"]
        port = prof["summary"]["portfolio"]
        logger.info(
            "პროდუქციული მოგება: %d verified, %d partial, %d unverified, "
            "%d protected, %d empty · ფინანსური დაფარვა %.1f%% (%.0f / %.0f ₾) · "
            "მომგება %.1f%% (%.0f / %.0f ₾)",
            sc.get("verified", 0), sc.get("partial", 0), sc.get("unverified", 0),
            sc.get("protected", 0), sc.get("empty", 0),
            port.get("coverage_cost_pct", 0),
            port.get("cost_matched_ge", 0), port.get("cost_imported_ge", 0),
            port.get("margin_pct", 0),
            port.get("profit_ge", 0), port.get("revenue_sold_ge", 0),
        )
    except Exception as exc:
        logger.warning("პროდუქციული მოგება — ვერ აშენდა: %s", exc)

    # ----- შეუსაბამო პროდუქცია (PRODUCTS orphans) -----
    # Live MegaPlus DB query. Non-fatal on failure.
    try:
        from dashboard_pipeline.orphan_products_section import build_orphan_products_bundle
        fa_dir = Path(script_dir) / "Financial_Analysis"
        orphan_bundle = build_orphan_products_bundle(fa_dir)
        if orphan_bundle is not None:
            data["orphan_products"] = orphan_bundle
    except Exception as exc:
        logger.warning("orphan_products: ვერ ჩაიდო data.json-ში: %s", exc)

    # ----- დუბლირებული პროდუქცია (PRODUCTS duplicate barcodes) -----
    # Surfaces same-barcode rows split across distinct P_IDs and flags
    # phantom-stock cases (variant with P_QUANT>0 and zero sales). Live
    # MegaPlus DB query. Non-fatal on failure.
    try:
        from dashboard_pipeline.duplicate_products_section import build_duplicate_products_bundle
        dup_bundle = build_duplicate_products_bundle()
        if dup_bundle is not None:
            data["duplicate_products"] = dup_bundle
    except Exception as exc:
        logger.warning("duplicate_products: ვერ ჩაიდო data.json-ში: %s", exc)

    _write_outputs(data, script_dir, inc)

if __name__ == "__main__":
    run()
