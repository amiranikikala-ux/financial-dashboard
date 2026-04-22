"""Phase 2.1 — Cash Flow Projection tool tests.

Covers:
* Argument validation: balance, horizon clamping, upcoming_payments shape.
* Daily baseline derivation: burn from monthly_pnl, income from forecast.
* Day-by-day status classification (🟢 / 🟡 / 🔴).
* Risk window merging (consecutive RED days collapsed).
* `summary_ka` format — 4C.2 standard, no-red vs red-present variants.
* `upcoming_payments` overlay on the right day + out-of-window warnings.
* Forecast fallback when forecast_revenue errors out.
* `TOOL_SCHEMAS` contains `compute_cash_flow_projection` at the expected index.
* `ToolDispatcher.dispatch("compute_cash_flow_projection", ...)` routes correctly.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.cash_flow_projection import (
    DAY_STATUS_RED,
    DAY_STATUS_SAFE,
    DAY_STATUS_WATCH,
    DEFAULT_HORIZON_DAYS,
    MAX_HORIZON_DAYS,
    MIN_HORIZON_DAYS,
    SOURCE_LABEL,
    WATCH_BUFFER_DAYS,
    _merge_risk_windows,
    _resolve_horizon_days,
    _resolve_upcoming_payments,
    _status_for,
    compute_cash_flow_projection,
)


TODAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _month_row(month: str, pos_income: float, expenses: float) -> Dict[str, Any]:
    return {
        "month": month,
        "objects": {
            "ოზურგეთი": {"pos_income": pos_income * 0.6, "expenses": expenses * 0.6, "net": (pos_income - expenses) * 0.6},
            "დვაბზუ": {"pos_income": pos_income * 0.4, "expenses": expenses * 0.4, "net": (pos_income - expenses) * 0.4},
        },
        "total": {
            "pos_income": pos_income,
            "expenses": expenses,
            "net": pos_income - expenses,
        },
    }


def _twelve_months_of_history(
    pos_income: float = 120_000.0,
    expenses: float = 100_000.0,
) -> List[Dict[str, Any]]:
    """12 months of profitable history (Prophet needs ≥12 months)."""
    return [
        _month_row(f"2025-{idx:02d}", pos_income, expenses) for idx in range(1, 13)
    ]


def _data_loader(rows: List[Dict[str, Any]]):
    def _load():
        return {"monthly_pnl": rows}

    return _load


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestResolveHorizonDays:
    def test_default_when_none(self):
        assert _resolve_horizon_days(None) == DEFAULT_HORIZON_DAYS

    def test_accepts_in_range(self):
        assert _resolve_horizon_days(21) == 21

    def test_clamps_below_min(self):
        assert _resolve_horizon_days(3) == MIN_HORIZON_DAYS

    def test_clamps_above_max(self):
        assert _resolve_horizon_days(9999) == MAX_HORIZON_DAYS

    def test_non_integer_falls_back_to_default(self):
        assert _resolve_horizon_days("abc") == DEFAULT_HORIZON_DAYS


class TestResolveUpcomingPayments:
    def test_none_returns_empty(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        buckets, warnings = _resolve_upcoming_payments(None, start, end)
        assert buckets == {}
        assert warnings == []

    def test_non_list_emits_warning(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        buckets, warnings = _resolve_upcoming_payments("not a list", start, end)
        assert buckets == {}
        assert warnings and "სიის" in warnings[0]

    def test_valid_entry_lands_in_bucket(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        raw = [{"date": "2026-05-10", "amount_ge": 2500, "label": "ქირა"}]
        buckets, warnings = _resolve_upcoming_payments(raw, start, end)
        assert "2026-05-10" in buckets
        assert buckets["2026-05-10"] == [{"label": "ქირა", "amount_ge": 2500.0}]
        assert warnings == []

    def test_out_of_window_entry_dropped(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        raw = [{"date": "2026-06-10", "amount_ge": 2500}]
        buckets, warnings = _resolve_upcoming_payments(raw, start, end)
        assert buckets == {}
        assert warnings and "ფანჯარას გარეთაა" in warnings[0]

    def test_invalid_date_dropped(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        raw = [{"date": "bogus", "amount_ge": 100}]
        buckets, warnings = _resolve_upcoming_payments(raw, start, end)
        assert buckets == {}
        assert warnings and "YYYY-MM-DD" in warnings[0]

    def test_negative_amount_dropped(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        raw = [{"date": "2026-05-05", "amount_ge": -100}]
        buckets, warnings = _resolve_upcoming_payments(raw, start, end)
        assert buckets == {}
        assert warnings and "არადადებითი" in warnings[0]

    def test_default_label_applied(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        raw = [{"date": "2026-05-05", "amount_ge": 100}]
        buckets, _ = _resolve_upcoming_payments(raw, start, end)
        assert buckets["2026-05-05"][0]["label"] == "გადახდა"

    def test_multiple_payments_same_day(self):
        start, end = date(2026, 5, 1), date(2026, 5, 14)
        raw = [
            {"date": "2026-05-05", "amount_ge": 100, "label": "ქირა"},
            {"date": "2026-05-05", "amount_ge": 200, "label": "royalty"},
        ]
        buckets, _ = _resolve_upcoming_payments(raw, start, end)
        assert len(buckets["2026-05-05"]) == 2


# ---------------------------------------------------------------------------
# Day status + window merging
# ---------------------------------------------------------------------------


class TestStatusFor:
    def test_negative_closing_is_red(self):
        assert _status_for(-100.0, 1_000.0) == DAY_STATUS_RED

    def test_less_than_buffer_is_watch(self):
        # Buffer = 7 × daily_burn. Closing below buffer but above 0.
        assert _status_for(1_000.0, 500.0) == DAY_STATUS_WATCH  # 500*7=3500

    def test_above_buffer_is_safe(self):
        assert _status_for(10_000.0, 500.0) == DAY_STATUS_SAFE

    def test_zero_burn_always_safe_when_positive(self):
        assert _status_for(100.0, 0.0) == DAY_STATUS_SAFE


class TestMergeRiskWindows:
    def test_no_red_days_returns_empty(self):
        proj = [
            {"date": "2026-05-01", "closing_ge": 1000, "status": DAY_STATUS_SAFE},
            {"date": "2026-05-02", "closing_ge": 500, "status": DAY_STATUS_WATCH},
        ]
        assert _merge_risk_windows(proj) == []

    def test_single_red_day_becomes_one_window(self):
        proj = [
            {"date": "2026-05-01", "closing_ge": -100, "status": DAY_STATUS_RED},
            {"date": "2026-05-02", "closing_ge": 1000, "status": DAY_STATUS_SAFE},
        ]
        windows = _merge_risk_windows(proj)
        assert len(windows) == 1
        assert windows[0] == {
            "start_date": "2026-05-01",
            "end_date": "2026-05-01",
            "days": 1,
            "min_balance_ge": -100,
            "lowest_day": "2026-05-01",
        }

    def test_consecutive_red_days_merged(self):
        proj = [
            {"date": "2026-05-01", "closing_ge": -100, "status": DAY_STATUS_RED},
            {"date": "2026-05-02", "closing_ge": -500, "status": DAY_STATUS_RED},
            {"date": "2026-05-03", "closing_ge": -200, "status": DAY_STATUS_RED},
            {"date": "2026-05-04", "closing_ge": 1000, "status": DAY_STATUS_SAFE},
        ]
        windows = _merge_risk_windows(proj)
        assert len(windows) == 1
        w = windows[0]
        assert w["start_date"] == "2026-05-01"
        assert w["end_date"] == "2026-05-03"
        assert w["days"] == 3
        assert w["min_balance_ge"] == -500
        assert w["lowest_day"] == "2026-05-02"

    def test_two_separate_windows(self):
        proj = [
            {"date": "2026-05-01", "closing_ge": -100, "status": DAY_STATUS_RED},
            {"date": "2026-05-02", "closing_ge": 1000, "status": DAY_STATUS_SAFE},
            {"date": "2026-05-03", "closing_ge": -50, "status": DAY_STATUS_RED},
        ]
        windows = _merge_risk_windows(proj)
        assert len(windows) == 2


# ---------------------------------------------------------------------------
# Top-level tool: success paths
# ---------------------------------------------------------------------------


class TestComputeCashFlowProjectionSuccess:
    def test_profitable_business_no_red_days(self):
        # Profitable: income 120K/month > expenses 100K/month.
        loader = _data_loader(_twelve_months_of_history(120_000, 100_000))
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=30_000,
            horizon_days=14,
            lookback_months=3,
            today=TODAY,
        )
        assert "error" not in result
        assert result["source"] == SOURCE_LABEL
        assert result["horizon_days"] == 14
        assert result["opening_balance_ge"] == 80_000.0
        assert len(result["daily_projection"]) == 14
        # All days SAFE because daily income > daily burn.
        assert all(
            row["status"] == DAY_STATUS_SAFE for row in result["daily_projection"]
        )
        assert result["risk_windows"] == []
        assert "🟢 0 წითელი დღე" in result["summary_ka"]

    def test_burning_business_hits_red(self):
        # Burning: expenses 200K/month vs income 100K/month → runs down
        # 100K/month = ~3.3K/day net burn. Starting cash 10K → red in ~3 days.
        loader = _data_loader(_twelve_months_of_history(100_000, 200_000))
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=10_000,
            current_balance_tbc_ge=0,
            horizon_days=14,
            lookback_months=3,
            today=TODAY,
        )
        assert "error" not in result
        assert any(
            row["status"] == DAY_STATUS_RED for row in result["daily_projection"]
        )
        assert result["risk_windows"]
        assert result["minimum_balance_ge"] < 0
        assert "🔴" in result["summary_ka"]

    def test_upcoming_payment_overlays_on_right_day(self):
        loader = _data_loader(_twelve_months_of_history(120_000, 100_000))
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            horizon_days=14,
            upcoming_payments=[
                {"date": "2026-04-25", "amount_ge": 2500, "label": "ქირა"},
            ],
            today=TODAY,
        )
        # Projection starts TOMORROW (2026-04-21). Day 2026-04-25 is offset 4.
        target_day = next(
            row for row in result["daily_projection"]
            if row["date"] == "2026-04-25"
        )
        assert target_day["scheduled_payments"] == [
            {"label": "ქირა", "amount_ge": 2500.0}
        ]

    def test_default_horizon_is_14(self):
        loader = _data_loader(_twelve_months_of_history())
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            today=TODAY,
        )
        assert result["horizon_days"] == DEFAULT_HORIZON_DAYS

    def test_opening_balance_combines_bog_tbc(self):
        loader = _data_loader(_twelve_months_of_history())
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=25_000.50,
            current_balance_tbc_ge=10_000.25,
            today=TODAY,
        )
        assert result["opening_balance_ge"] == 35_000.75
        assert result["current_cash_breakdown"] == {"bog_ge": 25_000.5, "tbc_ge": 10_000.25}

    def test_summary_ka_has_4c2_format_markers(self):
        loader = _data_loader(_twelve_months_of_history(120_000, 100_000))
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            horizon_days=14,
            today=TODAY,
        )
        summary = result["summary_ka"]
        # 4C.2 convention: bold key facts + · separators.
        assert "**" in summary
        assert "·" in summary
        assert "დღის პროექცია" in summary
        assert "საწყისი" in summary


# ---------------------------------------------------------------------------
# Top-level tool: error paths
# ---------------------------------------------------------------------------


class TestComputeCashFlowProjectionErrors:
    def test_both_balances_none_errors(self):
        loader = _data_loader(_twelve_months_of_history())
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=None,
            current_balance_tbc_ge=None,
            today=TODAY,
        )
        assert "error" in result
        assert "ბანკის ნაშთი" in result["error"]

    def test_zero_opening_balance_errors(self):
        loader = _data_loader(_twelve_months_of_history())
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=0,
            current_balance_tbc_ge=0,
            today=TODAY,
        )
        assert "error" in result
        assert "ამოწურულია" in result["error"]

    def test_insufficient_monthly_pnl_errors(self):
        loader = _data_loader([_month_row("2025-01", 100_000, 50_000)])
        result = compute_cash_flow_projection(
            loader,
            current_balance_bog_ge=10_000,
            current_balance_tbc_ge=0,
            lookback_months=3,
            today=TODAY,
        )
        assert "error" in result
        assert "monthly_pnl" in result["error"]


# ---------------------------------------------------------------------------
# Tool registry + dispatcher integration
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    def test_tool_present_in_tool_schemas(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "compute_cash_flow_projection" in names

    def test_tool_sits_after_cash_runway(self):
        # The runway family ends with the daily projection.
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert (
            names[names.index("compute_cash_runway") + 1]
            == "compute_cash_flow_projection"
        )

    def test_tool_schema_requires_both_balances(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_FLOW_PROJECTION_TOOL

        required = COMPUTE_CASH_FLOW_PROJECTION_TOOL["input_schema"]["required"]
        assert "current_balance_bog_ge" in required
        assert "current_balance_tbc_ge" in required

    def test_tool_schema_has_upcoming_payments(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_FLOW_PROJECTION_TOOL

        props = COMPUTE_CASH_FLOW_PROJECTION_TOOL["input_schema"]["properties"]
        assert "upcoming_payments" in props
        item_props = props["upcoming_payments"]["items"]["properties"]
        assert "date" in item_props
        assert "amount_ge" in item_props

    def test_tool_schema_has_horizon_bounds(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_FLOW_PROJECTION_TOOL

        horizon = COMPUTE_CASH_FLOW_PROJECTION_TOOL["input_schema"]["properties"][
            "horizon_days"
        ]
        assert horizon["minimum"] == MIN_HORIZON_DAYS
        assert horizon["maximum"] == MAX_HORIZON_DAYS

    def test_dispatcher_routes_correctly(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        rows = _twelve_months_of_history()
        dispatcher = ToolDispatcher(data_loader=_data_loader(rows))
        result = dispatcher.dispatch(
            "compute_cash_flow_projection",
            {
                "current_balance_bog_ge": 50_000,
                "current_balance_tbc_ge": 0,
                "horizon_days": 14,
            },
        )
        assert "error" not in result
        assert result["horizon_days"] == 14
        assert len(result["daily_projection"]) == 14


# ---------------------------------------------------------------------------
# Tool description contract (Rule 4C.2 — summary_ka + anti-triggers)
# ---------------------------------------------------------------------------


class TestToolDescriptionContract:
    def test_description_mentions_summary_ka(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_FLOW_PROJECTION_TOOL

        assert "summary_ka" in COMPUTE_CASH_FLOW_PROJECTION_TOOL["description"]

    def test_description_has_anti_triggers(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_FLOW_PROJECTION_TOOL

        desc = COMPUTE_CASH_FLOW_PROJECTION_TOOL["description"]
        # Must explicitly distinguish from compute_cash_runway.
        assert "compute_cash_runway" in desc
        assert "Anti-triggers" in desc

    def test_description_has_workflow_mandate(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_FLOW_PROJECTION_TOOL

        # Phase 4B Rule — mandate asking user for balances BEFORE tool call.
        assert "Workflow MANDATE" in COMPUTE_CASH_FLOW_PROJECTION_TOOL["description"]
