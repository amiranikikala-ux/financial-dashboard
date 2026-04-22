"""Regression tests for retail_sales bundle: by_category_by_month aggregate.

Added for Phase 2.9 (trend_detector unblock). Before this aggregate existed,
`monthly_pnl` had no per-category rollup, `retail_sales.by_category` had no
per-month rollup, and `by_month` had no per-category rollup — so no downstream
tool could ask "how did category X's margin / revenue / volume move MoM?".

These tests pin:
  1. The shape of the new key across empty + populated paths.
  2. The helper function's aggregation math, sort order, margin calc, and the
     "უცნობი თვე" skip rule.
  3. The api_contracts passthrough so the AI-facing summary surfaces the field.
"""

from __future__ import annotations

from collections import defaultdict

from dashboard_pipeline.api_contracts import _project_retail_sales_summary
from dashboard_pipeline.retail_sales import (
    _build_by_category_by_month_rows,
    empty_retail_sales_bundle,
)


# ---------------------------------------------------------------------------
# empty bundle shape
# ---------------------------------------------------------------------------

def test_empty_bundle_exposes_by_category_by_month_key():
    bundle = empty_retail_sales_bundle()
    assert "by_category_by_month" in bundle
    assert bundle["by_category_by_month"] == []


def test_empty_bundle_by_category_by_month_sits_next_to_by_month():
    # Adjacency is not enforced by the dict, but the ordering/insertion sequence
    # is a hint to future readers that these two sections are siblings.
    bundle = empty_retail_sales_bundle()
    keys = list(bundle.keys())
    assert keys.index("by_category_by_month") == keys.index("by_month") + 1


# ---------------------------------------------------------------------------
# helper: aggregation math + sort order
# ---------------------------------------------------------------------------

def _make_stats():
    """Synthetic (category_key, month_key) -> accumulator dict."""
    stats = defaultdict(
        lambda: {
            "row_count": 0,
            "total_quantity": 0.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
        }
    )
    return stats


def test_helper_builds_rows_with_correct_math_and_margin():
    stats = _make_stats()
    stats[("xili", "2025-12")].update(
        row_count=10,
        total_quantity=50.0,
        revenue_ge=1000.0,
        cost_ge=800.0,
        profit_ge=200.0,
    )
    rows = _build_by_category_by_month_rows(stats, {"xili": "ხილი/ბოსტნეული"})

    assert len(rows) == 1
    row = rows[0]
    assert row["category"] == "ხილი/ბოსტნეული"
    assert row["normalized_category"] == "xili"
    assert row["month"] == "2025-12"
    assert row["row_count"] == 10
    assert row["total_quantity"] == 50.0
    assert row["revenue_ge"] == 1000.0
    assert row["cost_ge"] == 800.0
    assert row["profit_ge"] == 200.0
    assert row["gross_margin_pct"] == 20.0


def test_helper_zero_revenue_yields_zero_margin_not_divide_by_zero():
    stats = _make_stats()
    stats[("empty_cat", "2025-10")].update(
        row_count=3, total_quantity=0.0, revenue_ge=0.0, cost_ge=0.0, profit_ge=0.0
    )
    rows = _build_by_category_by_month_rows(stats)
    assert rows[0]["gross_margin_pct"] == 0.0


def test_helper_sorts_by_category_then_month_ascending():
    stats = _make_stats()
    stats[("banana", "2025-11")].update(row_count=1, revenue_ge=10.0, profit_ge=1.0)
    stats[("apple", "2025-12")].update(row_count=1, revenue_ge=10.0, profit_ge=1.0)
    stats[("apple", "2025-10")].update(row_count=1, revenue_ge=10.0, profit_ge=1.0)
    stats[("banana", "2025-09")].update(row_count=1, revenue_ge=10.0, profit_ge=1.0)

    rows = _build_by_category_by_month_rows(stats)
    keys = [(r["normalized_category"], r["month"]) for r in rows]
    assert keys == [
        ("apple", "2025-10"),
        ("apple", "2025-12"),
        ("banana", "2025-09"),
        ("banana", "2025-11"),
    ]


def test_helper_drops_unknown_month_entries():
    stats = _make_stats()
    stats[("apple", "2025-12")].update(row_count=1, revenue_ge=10.0, profit_ge=1.0)
    stats[("apple", "უცნობი თვე")].update(row_count=5, revenue_ge=50.0, profit_ge=5.0)
    stats[("apple", "")].update(row_count=9, revenue_ge=90.0, profit_ge=9.0)

    rows = _build_by_category_by_month_rows(stats)
    months = [r["month"] for r in rows]
    assert months == ["2025-12"]


def test_helper_falls_back_to_normalized_key_when_display_name_missing():
    stats = _make_stats()
    stats[("orphan_cat", "2025-12")].update(row_count=1, revenue_ge=100.0, profit_ge=25.0)
    rows = _build_by_category_by_month_rows(stats, category_display_names={})
    assert rows[0]["category"] == "orphan_cat"


def test_helper_handles_multiple_categories_and_months():
    stats = _make_stats()
    stats[("xili", "2025-11")].update(row_count=20, revenue_ge=2000.0, profit_ge=400.0)
    stats[("xili", "2025-12")].update(row_count=25, revenue_ge=2500.0, profit_ge=625.0)
    stats[("lubi", "2025-11")].update(row_count=5, revenue_ge=500.0, profit_ge=50.0)
    stats[("lubi", "2025-12")].update(row_count=8, revenue_ge=800.0, profit_ge=96.0)

    rows = _build_by_category_by_month_rows(
        stats, {"xili": "ხილი", "lubi": "ლუდი"}
    )
    assert len(rows) == 4
    xili_rows = [r for r in rows if r["normalized_category"] == "xili"]
    lubi_rows = [r for r in rows if r["normalized_category"] == "lubi"]
    assert [r["month"] for r in xili_rows] == ["2025-11", "2025-12"]
    assert [r["month"] for r in lubi_rows] == ["2025-11", "2025-12"]
    # MoM margin change for xili: 20% -> 25%
    assert xili_rows[0]["gross_margin_pct"] == 20.0
    assert xili_rows[1]["gross_margin_pct"] == 25.0


# ---------------------------------------------------------------------------
# api_contracts passthrough
# ---------------------------------------------------------------------------

def _minimal_bundle_with_category_month_rows():
    bundle = empty_retail_sales_bundle()
    bundle["by_category_by_month"] = [
        {
            "category": "ხილი",
            "normalized_category": "xili",
            "month": "2025-12",
            "row_count": 10,
            "total_quantity": 50.0,
            "revenue_ge": 1000.0,
            "cost_ge": 800.0,
            "profit_ge": 200.0,
            "gross_margin_pct": 20.0,
        },
        "not a dict — must be filtered out",
        {
            "category": "ლუდი",
            "normalized_category": "lubi",
            "month": "2025-12",
            "row_count": 5,
            "total_quantity": 20.0,
            "revenue_ge": 500.0,
            "cost_ge": 450.0,
            "profit_ge": 50.0,
            "gross_margin_pct": 10.0,
        },
    ]
    return bundle


def test_api_contract_passes_by_category_by_month_through():
    bundle = _minimal_bundle_with_category_month_rows()
    summary = _project_retail_sales_summary(bundle)
    assert "by_category_by_month" in summary
    assert len(summary["by_category_by_month"]) == 2
    assert summary["by_category_by_month"][0]["normalized_category"] == "xili"
    assert summary["by_category_by_month"][1]["normalized_category"] == "lubi"


def test_api_contract_empty_bundle_yields_empty_by_category_by_month():
    summary = _project_retail_sales_summary(empty_retail_sales_bundle())
    assert summary.get("by_category_by_month") == []
