"""Sprint 5.8 — by_object_by_month aggregation in retail_sales.

Covers the per-shop per-month rollup that feeds vat_reconciliation.by_shop.
Tests drive _process_retail_sales_file-ის in-process via DataFrame fixtures + the
per-file serializer + the orchestrator merger via _merge_object_month.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd
import pytest

from dashboard_pipeline.retail_sales import (
    _build_by_object_by_month_rows,
    _merge_object_month,
)


# ---------------------------------------------------------------------------
# _build_by_object_by_month_rows
# ---------------------------------------------------------------------------


def test_builds_sorted_rows_by_object_then_month() -> None:
    stats = {
        ("ოზურგეთი", "2024-08"): {
            "row_count": 100,
            "total_quantity": 200.0,
            "revenue_ge": 50000.0,
            "cost_ge": 40000.0,
            "profit_ge": 10000.0,
        },
        ("ოზურგეთი", "2024-07"): {
            "row_count": 80,
            "total_quantity": 150.0,
            "revenue_ge": 45000.0,
            "cost_ge": 36000.0,
            "profit_ge": 9000.0,
        },
        ("დვაბზუ", "2024-08"): {
            "row_count": 60,
            "total_quantity": 100.0,
            "revenue_ge": 30000.0,
            "cost_ge": 24000.0,
            "profit_ge": 6000.0,
        },
    }
    rows = _build_by_object_by_month_rows(stats)
    # Sorted by (object, month asc).
    assert [(r["object"], r["month"]) for r in rows] == [
        ("დვაბზუ", "2024-08"),
        ("ოზურგეთი", "2024-07"),
        ("ოზურგეთი", "2024-08"),
    ]


def test_computes_margin_pct() -> None:
    stats = {
        ("ოზურგეთი", "2024-08"): {
            "row_count": 10,
            "total_quantity": 20.0,
            "revenue_ge": 100.0,
            "cost_ge": 80.0,
            "profit_ge": 20.0,
        },
    }
    rows = _build_by_object_by_month_rows(stats)
    assert rows[0]["gross_margin_pct"] == pytest.approx(20.0)


def test_skips_unknown_month_rows() -> None:
    stats = {
        ("ოზურგეთი", "უცნობი თვე"): {
            "row_count": 5,
            "total_quantity": 10.0,
            "revenue_ge": 1000.0,
            "cost_ge": 800.0,
            "profit_ge": 200.0,
        },
        ("ოზურგეთი", "2024-08"): {
            "row_count": 10,
            "total_quantity": 20.0,
            "revenue_ge": 2000.0,
            "cost_ge": 1600.0,
            "profit_ge": 400.0,
        },
    }
    rows = _build_by_object_by_month_rows(stats)
    assert len(rows) == 1
    assert rows[0]["month"] == "2024-08"


def test_empty_stats_returns_empty_list() -> None:
    assert _build_by_object_by_month_rows({}) == []


def test_row_shape_has_all_required_keys() -> None:
    stats = {
        ("ოზურგეთი", "2024-08"): {
            "row_count": 5,
            "total_quantity": 10.0,
            "revenue_ge": 1000.0,
            "cost_ge": 800.0,
            "profit_ge": 200.0,
        },
    }
    rows = _build_by_object_by_month_rows(stats)
    required = {
        "object",
        "month",
        "row_count",
        "total_quantity",
        "revenue_ge",
        "cost_ge",
        "profit_ge",
        "gross_margin_pct",
    }
    assert required.issubset(rows[0].keys())


def test_zero_revenue_returns_zero_margin_not_div_by_zero() -> None:
    stats = {
        ("ოზურგეთი", "2024-08"): {
            "row_count": 1,
            "total_quantity": 1.0,
            "revenue_ge": 0.0,
            "cost_ge": 0.0,
            "profit_ge": 0.0,
        },
    }
    rows = _build_by_object_by_month_rows(stats)
    assert rows[0]["gross_margin_pct"] == 0.0


# ---------------------------------------------------------------------------
# _merge_object_month
# ---------------------------------------------------------------------------


def test_merger_sums_across_per_file_payloads() -> None:
    master: dict = {}
    per_file_a = [
        {
            "object": "ოზურგეთი",
            "month": "2024-08",
            "row_count": 50,
            "total_quantity": 100.0,
            "revenue_ge": 25000.0,
            "cost_ge": 20000.0,
            "profit_ge": 5000.0,
        }
    ]
    per_file_b = [
        {
            "object": "ოზურგეთი",
            "month": "2024-08",
            "row_count": 30,
            "total_quantity": 60.0,
            "revenue_ge": 15000.0,
            "cost_ge": 12000.0,
            "profit_ge": 3000.0,
        }
    ]
    _merge_object_month(master, per_file_a)
    _merge_object_month(master, per_file_b)
    key = ("ოზურგეთი", "2024-08")
    assert master[key]["row_count"] == 80
    assert master[key]["revenue_ge"] == pytest.approx(40000.0)
    assert master[key]["profit_ge"] == pytest.approx(8000.0)


def test_merger_keeps_shops_separate() -> None:
    master: dict = {}
    per_file = [
        {
            "object": "ოზურგეთი",
            "month": "2024-08",
            "row_count": 50,
            "total_quantity": 100.0,
            "revenue_ge": 25000.0,
            "cost_ge": 20000.0,
            "profit_ge": 5000.0,
        },
        {
            "object": "დვაბზუ",
            "month": "2024-08",
            "row_count": 20,
            "total_quantity": 40.0,
            "revenue_ge": 10000.0,
            "cost_ge": 8000.0,
            "profit_ge": 2000.0,
        },
    ]
    _merge_object_month(master, per_file)
    assert master[("ოზურგეთი", "2024-08")]["revenue_ge"] == pytest.approx(25000.0)
    assert master[("დვაბზუ", "2024-08")]["revenue_ge"] == pytest.approx(10000.0)


def test_merger_keeps_months_separate() -> None:
    master: dict = {}
    per_file = [
        {
            "object": "ოზურგეთი",
            "month": "2024-07",
            "row_count": 10,
            "total_quantity": 20.0,
            "revenue_ge": 5000.0,
            "cost_ge": 4000.0,
            "profit_ge": 1000.0,
        },
        {
            "object": "ოზურგეთი",
            "month": "2024-08",
            "row_count": 15,
            "total_quantity": 30.0,
            "revenue_ge": 7500.0,
            "cost_ge": 6000.0,
            "profit_ge": 1500.0,
        },
    ]
    _merge_object_month(master, per_file)
    assert len(master) == 2
    assert master[("ოზურგეთი", "2024-07")]["revenue_ge"] == pytest.approx(5000.0)
    assert master[("ოზურგეთი", "2024-08")]["revenue_ge"] == pytest.approx(7500.0)


def test_merger_empty_input_is_noop() -> None:
    master = {("x", "2024-08"): {"row_count": 5, "revenue_ge": 100.0}}
    _merge_object_month(master, [])
    assert master == {("x", "2024-08"): {"row_count": 5, "revenue_ge": 100.0}}


# ---------------------------------------------------------------------------
# Integration: bundle contract
# ---------------------------------------------------------------------------


def test_empty_bundle_exposes_by_object_by_month_key() -> None:
    """Empty bundle must carry the new key so downstream callers don't KeyError."""
    from dashboard_pipeline.retail_sales import empty_retail_sales_bundle

    bundle = empty_retail_sales_bundle()
    assert "by_object_by_month" in bundle
    assert bundle["by_object_by_month"] == []
