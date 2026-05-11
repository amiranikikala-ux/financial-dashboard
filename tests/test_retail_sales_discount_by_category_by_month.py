"""Regression tests for retail_sales.discount_by_category_by_month.

Added when the discount-by-category section was made period-aware (the UI
period filter now sums these per-month rows within the active date range
instead of falling back to lifetime totals). Mirrors the existing pattern
from test_retail_sales_by_category_by_month.py.
"""

from __future__ import annotations

from dashboard_pipeline.api_contracts import _project_retail_sales_summary
from dashboard_pipeline.retail_sales import (
    empty_retail_sales_bundle,
    synthesize_from_megaplus,
)


def _minimal_megaplus_with_discount_rows():
    """Two stores, one shared category across two months."""
    return {
        "stores": {
            "1329": {
                "store_id": "1329",
                "totals": {"revenue": 1000, "cogs": 700, "profit": 300, "sale_lines": 10},
                "data_range": {"min_timestamp": "2026-03-01", "max_timestamp": "2026-04-30"},
                "by_product": [],
                "by_category": [],
                "by_month": [],
                "discount_by_category": [
                    {
                        "category": "ლუდი", "lines": 10, "receipts": 8,
                        "markdown_total": 500.0, "revenue_after_markdown": 1500.0,
                        "revenue_before_markdown": 2000.0, "cost": 1200.0,
                        "profit_actual": 300.0, "profit_if_no_discount": 800.0,
                        "lift_lost_ge": 500.0, "markdown_pct": 25.0,
                    },
                ],
                "discount_by_category_by_month": [
                    {
                        "month": "2026-03", "category": "ლუდი", "lines": 4, "receipts": 3,
                        "markdown_total": 200.0, "revenue_after_markdown": 600.0,
                        "revenue_before_markdown": 800.0, "cost": 480.0,
                        "profit_actual": 120.0, "profit_if_no_discount": 320.0,
                        "markdown_pct": 25.0,
                    },
                    {
                        "month": "2026-04", "category": "ლუდი", "lines": 6, "receipts": 5,
                        "markdown_total": 300.0, "revenue_after_markdown": 900.0,
                        "revenue_before_markdown": 1200.0, "cost": 720.0,
                        "profit_actual": 180.0, "profit_if_no_discount": 480.0,
                        "markdown_pct": 25.0,
                    },
                ],
            },
            "1301": {
                "store_id": "1301",
                "totals": {"revenue": 500, "cogs": 350, "profit": 150, "sale_lines": 5},
                "data_range": {"min_timestamp": "2026-04-01", "max_timestamp": "2026-04-30"},
                "by_product": [],
                "by_category": [],
                "by_month": [],
                "discount_by_category": [
                    {
                        "category": "ლუდი", "lines": 5, "receipts": 4,
                        "markdown_total": 250.0, "revenue_after_markdown": 750.0,
                        "revenue_before_markdown": 1000.0, "cost": 600.0,
                        "profit_actual": 150.0, "profit_if_no_discount": 400.0,
                        "lift_lost_ge": 250.0, "markdown_pct": 25.0,
                    },
                ],
                "discount_by_category_by_month": [
                    {
                        "month": "2026-04", "category": "ლუდი", "lines": 5, "receipts": 4,
                        "markdown_total": 250.0, "revenue_after_markdown": 750.0,
                        "revenue_before_markdown": 1000.0, "cost": 600.0,
                        "profit_actual": 150.0, "profit_if_no_discount": 400.0,
                        "markdown_pct": 25.0,
                    },
                ],
            },
        }
    }


def test_synthesize_emits_combined_discount_by_category_by_month():
    bundle = synthesize_from_megaplus(_minimal_megaplus_with_discount_rows())
    rows = bundle.get("discount_by_category_by_month") or []
    by_month = {r["month"]: r for r in rows}

    assert set(by_month) == {"2026-03", "2026-04"}
    # March: only store 1329 contributed.
    assert by_month["2026-03"]["markdown_total_ge"] == 200.0
    # April: 1329 (300) + 1301 (250) → combined 550.
    assert by_month["2026-04"]["markdown_total_ge"] == 550.0
    assert by_month["2026-04"]["revenue_before_markdown_ge"] == 2200.0  # 1200 + 1000
    assert by_month["2026-04"]["cost_ge"] == 1320.0  # 720 + 600
    # Derived profit_actual: revenue_after − cost = 1650 − 1320 = 330.
    assert by_month["2026-04"]["profit_actual_ge"] == 330.0


def test_synthesize_per_store_view_includes_discount_by_category_by_month():
    bundle = synthesize_from_megaplus(_minimal_megaplus_with_discount_rows())
    pov = bundle.get("per_object_view") or {}
    dvabzu = pov.get("დვაბზუ") or {}
    rows = dvabzu.get("discount_by_category_by_month") or []
    assert len(rows) == 2
    months = {r["month"]: r["markdown_total_ge"] for r in rows}
    assert months == {"2026-03": 200.0, "2026-04": 300.0}


def test_synthesize_drops_rows_with_missing_month():
    payload = _minimal_megaplus_with_discount_rows()
    payload["stores"]["1329"]["discount_by_category_by_month"].append({
        "month": None, "category": "ლუდი", "lines": 99, "receipts": 99,
        "markdown_total": 9999.0, "revenue_after_markdown": 1.0,
        "revenue_before_markdown": 2.0, "cost": 0.0,
    })
    bundle = synthesize_from_megaplus(payload)
    rows = bundle.get("discount_by_category_by_month") or []
    # Junk row with no month must not affect any month bucket.
    for r in rows:
        assert r["markdown_total_ge"] < 9999.0


def test_api_contract_exposes_discount_by_category_by_month():
    bundle = {
        "label_ka": "x", "discount_by_category_by_month": [
            {
                "month": "2026-04", "category": "ლუდი", "lines": 1, "receipts": 1,
                "markdown_total_ge": 10.0, "revenue_after_markdown_ge": 30.0,
                "revenue_before_markdown_ge": 40.0, "cost_ge": 25.0,
                "profit_actual_ge": 5.0, "profit_if_no_discount_ge": 15.0,
                "lift_lost_ge": 10.0, "markdown_pct": 25.0,
            },
        ],
    }
    summary = _project_retail_sales_summary(bundle)
    assert "discount_by_category_by_month" in summary
    assert summary["discount_by_category_by_month"][0]["month"] == "2026-04"


def test_api_contract_empty_bundle_yields_no_discount_by_category_by_month_key():
    summary = _project_retail_sales_summary(empty_retail_sales_bundle())
    # When the source bundle has no megaplus-derived field at all, the allowlist
    # passthrough should omit it (None → skip), not insert an empty placeholder.
    assert "discount_by_category_by_month" not in summary
