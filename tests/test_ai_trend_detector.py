"""Phase 2.9 — Trend Detector tests.

Covers:
  * MoM / YoY period resolution (including year rollover on January)
  * price × volume decomposition identity:
        delta_revenue = price_effect + volume_effect + mix_effect
  * Latest-period auto-detection when `period` is omitted
  * Suspicious-margin quarantine (< −5% or > 90%)
  * Noise floor (both sides < 100 ₾ → skipped)
  * category_filter substring
  * Tool registration in TOOL_SCHEMAS + dispatcher routing
  * summary_ka markers (mode, delta, top mover)
  * Input validation (mode, top_n)
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from dashboard_pipeline.ai.trend_detector import (
    MAX_TOP_N,
    MIN_TOP_N,
    _prev_period,
    detect_trends,
)
from dashboard_pipeline.ai.tools import TOOL_SCHEMAS, DETECT_TRENDS_TOOL


def _mk_row(category, month, qty, price, cost=None, margin=None):
    revenue = qty * price
    cost_v = cost if cost is not None else revenue * 0.75
    profit = revenue - cost_v
    if margin is None:
        margin = (profit / revenue * 100.0) if revenue else 0.0
    return {
        "category": category,
        "normalized_category": category,
        "month": month,
        "row_count": 1,
        "total_quantity": qty,
        "revenue_ge": revenue,
        "cost_ge": cost_v,
        "profit_ge": profit,
        "gross_margin_pct": margin,
    }


def _data(rows):
    return {"retail_sales": {"by_category_by_month": rows}}


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------

def test_prev_period_mom_normal():
    assert _prev_period("2024-08", "MoM") == "2024-07"


def test_prev_period_mom_january_rollover():
    assert _prev_period("2024-01", "MoM") == "2023-12"


def test_prev_period_yoy():
    assert _prev_period("2024-08", "YoY") == "2023-08"


def test_prev_period_yoy_january():
    assert _prev_period("2024-01", "YoY") == "2023-01"


def test_prev_period_invalid_returns_none():
    assert _prev_period("bad", "MoM") is None


# ---------------------------------------------------------------------------
# Decomposition identity
# ---------------------------------------------------------------------------

def test_decomposition_identity_holds_per_entry():
    """delta_revenue = price_effect + volume_effect + mix_effect exactly."""
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),  # rev 100
        _mk_row("A", "2024-08", qty=20, price=12),  # rev 240 → +140
    ]
    out = detect_trends(lambda: _data(rows))
    entry = out["top_positive"][0]
    total = entry["price_effect_ge"] + entry["volume_effect_ge"] + entry["mix_effect_ge"]
    assert total == pytest.approx(entry["delta_revenue_ge"], abs=0.02)


def test_volume_driven_classification():
    """Δqty large, Δprice ≈ 0 → driver='volume'."""
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=30, price=10),
    ]
    out = detect_trends(lambda: _data(rows))
    assert out["top_positive"][0]["driver"] == "volume"


def test_price_driven_classification():
    """Δprice large, Δqty ≈ 0 → driver='price'."""
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=10, price=15),
    ]
    out = detect_trends(lambda: _data(rows))
    assert out["top_positive"][0]["driver"] == "price"


def test_direction_labels():
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=20, price=12),
        _mk_row("B", "2024-07", qty=50, price=10),
        _mk_row("B", "2024-08", qty=30, price=9),
    ]
    out = detect_trends(lambda: _data(rows))
    directions = {e["category"]: e["direction_ka"] for e in out["top_positive"] + out["top_negative"]}
    assert directions.get("A") == "📈 ზრდა"
    assert directions.get("B") == "📉 ვარდნა"


# ---------------------------------------------------------------------------
# Auto-period + MoM default
# ---------------------------------------------------------------------------

def test_latest_period_auto_detected():
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=10, price=10),
        _mk_row("A", "2024-09", qty=15, price=10),  # latest
    ]
    out = detect_trends(lambda: _data(rows))
    assert out["current_period"] == "2024-09"
    assert out["compare_period"] == "2024-08"


def test_mode_is_default_mom():
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=10, price=10),
    ]
    out = detect_trends(lambda: _data(rows))
    assert out["mode"] == "MoM"


def test_yoy_mode_selects_prior_year():
    rows = [
        _mk_row("A", "2023-08", qty=10, price=10),
        _mk_row("A", "2024-08", qty=15, price=10),
    ]
    out = detect_trends(lambda: _data(rows), mode="YoY", period="2024-08")
    assert out["compare_period"] == "2023-08"


# ---------------------------------------------------------------------------
# Quarantine + noise floor
# ---------------------------------------------------------------------------

def test_suspicious_margin_low_excluded():
    rows = [
        _mk_row("BAD", "2024-07", qty=100, price=10, margin=-10.0),
        _mk_row("BAD", "2024-08", qty=100, price=10, margin=-10.0),
        _mk_row("OK", "2024-07", qty=10, price=10, margin=20.0),
        _mk_row("OK", "2024-08", qty=20, price=10, margin=20.0),
    ]
    out = detect_trends(lambda: _data(rows))
    assert "BAD" in out["suspicious"]
    assert out["categories_compared"] == 1


def test_suspicious_margin_high_excluded():
    rows = [
        _mk_row("SUS", "2024-07", qty=10, price=10, margin=95.0),
        _mk_row("SUS", "2024-08", qty=20, price=10, margin=95.0),
    ]
    out = detect_trends(lambda: _data(rows))
    assert "SUS" in out["suspicious"]


def test_noise_floor_skips_tiny_categories():
    """Categories < 100 ₾ on BOTH sides are skipped."""
    rows = [
        _mk_row("TINY", "2024-07", qty=5, price=10),  # 50
        _mk_row("TINY", "2024-08", qty=8, price=10),  # 80
        _mk_row("BIG", "2024-07", qty=20, price=10),  # 200
        _mk_row("BIG", "2024-08", qty=30, price=10),  # 300
    ]
    out = detect_trends(lambda: _data(rows))
    cats = {e["category"] for e in out["top_positive"] + out["top_negative"]}
    assert "BIG" in cats
    assert "TINY" not in cats


# ---------------------------------------------------------------------------
# category_filter
# ---------------------------------------------------------------------------

def test_category_filter_substring():
    rows = [
        _mk_row("0100 | ალკოჰოლი", "2024-07", qty=10, price=10),
        _mk_row("0100 | ალკოჰოლი", "2024-08", qty=20, price=10),
        _mk_row("0200 | პური", "2024-07", qty=10, price=10),
        _mk_row("0200 | პური", "2024-08", qty=15, price=10),
    ]
    out = detect_trends(lambda: _data(rows), category_filter="ალკოჰოლი")
    assert out["categories_compared"] == 1
    assert out["top_positive"][0]["category"] == "0100 | ალკოჰოლი"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_invalid_mode_errors():
    out = detect_trends(lambda: _data([]), mode="WTF")
    assert "error" in out
    assert "MoM" in out["error"] or "YoY" in out["error"]


def test_period_not_in_data_errors():
    rows = [_mk_row("A", "2024-07", qty=10, price=10)]
    out = detect_trends(lambda: _data(rows), period="2099-12")
    assert "error" in out


def test_compare_period_missing_errors():
    rows = [_mk_row("A", "2024-07", qty=10, price=10)]
    out = detect_trends(lambda: _data(rows), period="2024-07")  # no prior month
    assert "error" in out


def test_top_n_clamped_to_range():
    rows = []
    for i in range(25):
        rows.append(_mk_row(f"C{i:02d}", "2024-07", qty=10, price=10))
        rows.append(_mk_row(f"C{i:02d}", "2024-08", qty=15 + i, price=10))
    out = detect_trends(lambda: _data(rows), top_n=999)
    assert len(out["top_positive"]) <= MAX_TOP_N
    out = detect_trends(lambda: _data(rows), top_n=1)
    assert len(out["top_positive"]) <= MIN_TOP_N


def test_empty_data_errors():
    out = detect_trends(lambda: {"retail_sales": {"by_category_by_month": []}})
    assert "error" in out


# ---------------------------------------------------------------------------
# Registration + dispatcher
# ---------------------------------------------------------------------------

def test_detect_trends_in_tool_schemas():
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert "detect_trends" in names


def test_detect_trends_schema_shape():
    assert DETECT_TRENDS_TOOL["name"] == "detect_trends"
    props = DETECT_TRENDS_TOOL["input_schema"]["properties"]
    assert set(props.keys()) == {"mode", "period", "top_n", "category_filter"}
    assert props["mode"]["enum"] == ["MoM", "YoY"]
    assert props["period"]["pattern"] == "^[0-9]{4}-[0-9]{2}$"


def test_summary_ka_markers():
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=20, price=12),
    ]
    out = detect_trends(lambda: _data(rows))
    s = out["summary_ka"]
    assert "MoM: 2024-08 vs 2024-07" in s
    assert "price_effect" in s
    assert "volume_effect" in s
    assert "category" in s


def test_notes_identity_stated():
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=20, price=12),
    ]
    out = detect_trends(lambda: _data(rows))
    joined = " | ".join(out["notes_ka"])
    assert "price_effect" in joined
    assert "volume_effect" in joined
    assert "identity" in joined or "≡" in joined


def test_totals_match_sum_of_entries():
    rows = [
        _mk_row("A", "2024-07", qty=10, price=10),
        _mk_row("A", "2024-08", qty=20, price=12),
        _mk_row("B", "2024-07", qty=30, price=10),
        _mk_row("B", "2024-08", qty=25, price=11),
    ]
    out = detect_trends(lambda: _data(rows))
    all_entries = out["top_positive"] + out["top_negative"]
    sum_delta = sum(e["delta_revenue_ge"] for e in all_entries)
    assert sum_delta == pytest.approx(out["totals"]["delta_revenue_ge"], abs=0.02)
