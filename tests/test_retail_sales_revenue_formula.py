"""
Sprint 5.5 — retail_sales line revenue = price × quantity regression test.

Pre-Sprint-5.5 `_process_retail_sales_file` summed ფასი (unit price) as
revenue_ge and თვითღირებულება (unit cost) as cost_ge, without multiplying
by რაოდენობა. That over-counted revenue by ~9% on typical months
(e.g. 2024-08 pipeline 282K vs direct MAX read 259K). This test pins the
correct formula so the bug cannot silently regress.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import retail_sales as rs
from dashboard_pipeline.constants import _clone_default_object_mapping


RETAIL_COLUMNS = [
    "კოდი", "შტრიხკოდი", "დასახელება", "ერთეული",
    "რაოდენობა", "ფასი", "თვითღირებულება", "მოგება",
    "დრო", "ობიექტი", "ქვეჯგუფი",
]


def _row(code, qty, price, cost, profit, dt, obj="ოზურგეთი", cat="test"):
    return {
        "კოდი": code, "შტრიხკოდი": "", "დასახელება": f"p_{code}", "ერთეული": "ცალი",
        "რაოდენობა": qty, "ფასი": price, "თვითღირებულება": cost, "მოგება": profit,
        "დრო": dt, "ობიექტი": obj, "ქვეჯგუფი": cat,
    }


def _write_xlsx(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=RETAIL_COLUMNS)
    df.to_excel(path, index=False)


def _run(path):
    return rs._process_retail_sales_file(
        str(path), object_mapping=_clone_default_object_mapping()
    )


def _month_row(payload, month):
    for m in payload.get("by_month") or []:
        if m.get("month") == month:
            return m
    return {}


def test_line_revenue_is_price_times_quantity(tmp_path):
    """Row: qty=3, unit_price=10 → line revenue must be 30, not 10."""
    path = tmp_path / "ოზ" / "test.xlsx"
    _write_xlsx(path, [
        _row("A", qty=3, price=10, cost=6, profit=12, dt="2024-08-01 10:00"),
    ])
    out = _run(path)
    assert out["files_entry"]["revenue_ge"] == pytest.approx(30.0)
    assert out["files_entry"]["cost_ge"] == pytest.approx(18.0)
    assert out["files_entry"]["profit_ge"] == pytest.approx(12.0)


def test_quantity_zero_yields_zero_revenue_not_unit_price(tmp_path):
    """Row: qty=0, unit_price=13 → line revenue must be 0 (phantom item bug)."""
    path = tmp_path / "ოზ" / "test.xlsx"
    _write_xlsx(path, [
        _row("A", qty=0, price=13, cost=10, profit=0, dt="2024-08-01 10:00"),
    ])
    out = _run(path)
    assert out["files_entry"]["revenue_ge"] == pytest.approx(0.0)
    assert out["files_entry"]["cost_ge"] == pytest.approx(0.0)


def test_fractional_quantity(tmp_path):
    """Row: qty=0.5 (half kg), unit_price=20 → line revenue must be 10."""
    path = tmp_path / "ოზ" / "test.xlsx"
    _write_xlsx(path, [
        _row("A", qty=0.5, price=20, cost=14, profit=3, dt="2024-08-02 10:00"),
    ])
    out = _run(path)
    assert out["files_entry"]["revenue_ge"] == pytest.approx(10.0)
    assert out["files_entry"]["cost_ge"] == pytest.approx(7.0)


def test_month_aggregation_uses_line_revenue(tmp_path):
    """Sum across rows must equal sum(price × qty), not sum(price)."""
    path = tmp_path / "ოზ" / "test.xlsx"
    _write_xlsx(path, [
        _row("A", qty=3, price=10, cost=6, profit=12, dt="2024-08-01 10:00"),
        _row("B", qty=2, price=15, cost=10, profit=10, dt="2024-08-02 10:00"),
        _row("C", qty=0, price=50, cost=40, profit=0, dt="2024-08-03 10:00"),  # phantom
    ])
    out = _run(path)
    # (3×10) + (2×15) + (0×50) = 60 — NOT 10+15+50 = 75
    assert out["files_entry"]["revenue_ge"] == pytest.approx(60.0)
    assert _month_row(out, "2024-08")["revenue_ge"] == pytest.approx(60.0)
    assert _month_row(out, "2024-08")["cost_ge"] == pytest.approx(38.0)  # (3×6)+(2×10)+(0×40)


def test_profit_falls_back_to_revenue_minus_cost_when_max_column_missing(tmp_path):
    """When მოგება is NaN, profit should be (price × qty) − (cost × qty)."""
    path = tmp_path / "ოზ" / "test.xlsx"
    _write_xlsx(path, [
        _row("A", qty=2, price=10, cost=6, profit="", dt="2024-08-01 10:00"),
    ])
    out = _run(path)
    # revenue=20, cost=12, profit=8 (not 10-6=4)
    assert out["files_entry"]["profit_ge"] == pytest.approx(8.0)
    assert out["files_entry"]["profit_fallback_rows"] == 1
