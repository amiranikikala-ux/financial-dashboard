"""Phase 3.5 — Cash Runway tool + prompt tests.

Covers:
* Argument coercion: balance validation, lookback clamping, zero / negative / NaN.
* Burn-rate computation over monthly_pnl windows (1, 3, 6 months).
* Runway classification thresholds (SAFE ≥ 6, WATCH 2–6, CRITICAL < 2, PROFIT ≤ 0).
* Burn-trend detection (stable / accelerating / decelerating / insufficient_history).
* Status summary message contents per label.
* `TOOL_SCHEMAS` contains `compute_cash_runway` at index 11 and length = 17.
* `ToolDispatcher.dispatch("compute_cash_runway", ...)` routes through the lazy module.
* `SYSTEM_PROMPT_KA` gained 💰 Cash Runway section with triggers / anti-triggers /
  3-step mandatory workflow / honesty rule / guardrail.
* `SYSTEM_PROMPT_KA_INVESTIGATOR` has **zero** Cash Runway markers (do-not-touch).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.cash_runway import (
    DAYS_PER_MONTH,
    DEFAULT_LOOKBACK_MONTHS,
    MAX_LOOKBACK_MONTHS,
    MIN_LOOKBACK_MONTHS,
    RUNWAY_LABEL_CRITICAL,
    RUNWAY_LABEL_PROFIT,
    RUNWAY_LABEL_SAFE,
    RUNWAY_LABEL_WATCH,
    RUNWAY_SAFE_MONTHS,
    RUNWAY_WATCH_MONTHS,
    _classify_runway,
    _compute_burn_trend,
    _extract_monthly_series,
    _resolve_balance,
    _resolve_lookback_months,
    compute_cash_runway,
)


TODAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _month_row(month: str, income: float, expense: float) -> Dict[str, Any]:
    return {
        "month": month,
        "objects": {},
        "total": {
            "pos_income": income,
            "expenses": expense,
            "net": income - expense,
        },
    }


def _data_loader_with_monthly_pnl(
    rows: List[Dict[str, Any]],
):
    def _load():
        return {"monthly_pnl": rows}

    return _load


def _steady_burn_12_months(monthly_burn: float = 20_000.0) -> List[Dict[str, Any]]:
    """Produce 12 months of monthly_pnl with a steady burn_rate."""
    months: List[Dict[str, Any]] = []
    for idx in range(1, 13):
        months.append(
            _month_row(
                month=f"2025-{idx:02d}",
                income=100_000.0,
                expense=100_000.0 + monthly_burn,
            )
        )
    return months


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestResolveBalance:
    def test_positive_number(self):
        assert _resolve_balance(50_000) == 50_000.0

    def test_float_string(self):
        assert _resolve_balance("123.45") == pytest.approx(123.45)

    def test_zero_is_accepted(self):
        assert _resolve_balance(0) == 0.0

    def test_negative_rejected(self):
        assert _resolve_balance(-1) is None

    def test_nan_rejected(self):
        assert _resolve_balance(float("nan")) is None

    def test_inf_rejected(self):
        assert _resolve_balance(float("inf")) is None

    def test_garbage_string_rejected(self):
        assert _resolve_balance("abc") is None

    def test_none_rejected(self):
        assert _resolve_balance(None) is None


class TestResolveLookback:
    def test_default_when_none(self):
        assert _resolve_lookback_months(None) == DEFAULT_LOOKBACK_MONTHS

    def test_clamp_low(self):
        assert _resolve_lookback_months(0) == MIN_LOOKBACK_MONTHS
        assert _resolve_lookback_months(-5) == MIN_LOOKBACK_MONTHS

    def test_clamp_high(self):
        assert _resolve_lookback_months(999) == MAX_LOOKBACK_MONTHS

    def test_string_coerce(self):
        assert _resolve_lookback_months("6") == 6

    def test_garbage_falls_back_to_default(self):
        assert _resolve_lookback_months("abc") == DEFAULT_LOOKBACK_MONTHS


# ---------------------------------------------------------------------------
# Monthly series extraction + trend
# ---------------------------------------------------------------------------


class TestExtractMonthlySeries:
    def test_sorts_oldest_first(self):
        out = _extract_monthly_series(
            [
                _month_row("2026-02", 100, 200),
                _month_row("2025-12", 80, 150),
                _month_row("2026-01", 90, 120),
            ]
        )
        assert [r["month"] for r in out] == ["2025-12", "2026-01", "2026-02"]

    def test_skips_invalid_rows(self):
        out = _extract_monthly_series(
            [None, {"no_month": True}, _month_row("2025-01", 10, 20), "garbage"]
        )
        assert len(out) == 1 and out[0]["month"] == "2025-01"


class TestComputeBurnTrend:
    def test_insufficient_history(self):
        series = _extract_monthly_series(_steady_burn_12_months()[:4])
        assert _compute_burn_trend(series, 3) == "insufficient_history"

    def test_stable(self):
        series = _extract_monthly_series(_steady_burn_12_months(monthly_burn=20_000.0))
        assert _compute_burn_trend(series, 3) == "stable"

    def test_accelerating(self):
        rows = _steady_burn_12_months(monthly_burn=10_000.0)
        # Last 3 months burn 30K, prior 3 still 10K → accelerating.
        for idx in (-3, -2, -1):
            rows[idx]["total"]["expenses"] = 130_000.0
            rows[idx]["total"]["net"] = 100_000.0 - 130_000.0
        series = _extract_monthly_series(rows)
        assert _compute_burn_trend(series, 3) == "accelerating"

    def test_decelerating(self):
        rows = _steady_burn_12_months(monthly_burn=30_000.0)
        # Last 3 months burn 5K, prior 3 still 30K → decelerating.
        for idx in (-3, -2, -1):
            rows[idx]["total"]["expenses"] = 105_000.0
            rows[idx]["total"]["net"] = 100_000.0 - 105_000.0
        series = _extract_monthly_series(rows)
        assert _compute_burn_trend(series, 3) == "decelerating"

    def test_profit_then_burn_flips_to_accelerating(self):
        rows = _steady_burn_12_months(monthly_burn=-5_000.0)  # profit
        for idx in (-3, -2, -1):
            rows[idx]["total"]["expenses"] = 120_000.0
            rows[idx]["total"]["net"] = 100_000.0 - 120_000.0
        series = _extract_monthly_series(rows)
        assert _compute_burn_trend(series, 3) == "accelerating"


# ---------------------------------------------------------------------------
# Runway classification thresholds
# ---------------------------------------------------------------------------


class TestClassifyRunway:
    def test_profit_when_burn_zero_or_negative(self):
        assert _classify_runway(runway_months=999.0, burn_rate=0) == RUNWAY_LABEL_PROFIT
        assert _classify_runway(runway_months=-1.0, burn_rate=-5.0) == RUNWAY_LABEL_PROFIT

    def test_safe_boundary(self):
        assert _classify_runway(RUNWAY_SAFE_MONTHS, 1.0) == RUNWAY_LABEL_SAFE
        assert _classify_runway(RUNWAY_SAFE_MONTHS + 0.1, 1.0) == RUNWAY_LABEL_SAFE

    def test_watch_range(self):
        assert _classify_runway(RUNWAY_WATCH_MONTHS, 1.0) == RUNWAY_LABEL_WATCH
        assert _classify_runway(RUNWAY_SAFE_MONTHS - 0.1, 1.0) == RUNWAY_LABEL_WATCH

    def test_critical_under_watch(self):
        assert _classify_runway(RUNWAY_WATCH_MONTHS - 0.1, 1.0) == RUNWAY_LABEL_CRITICAL
        assert _classify_runway(0.5, 1.0) == RUNWAY_LABEL_CRITICAL


# ---------------------------------------------------------------------------
# End-to-end compute_cash_runway happy paths
# ---------------------------------------------------------------------------


class TestComputeCashRunwayHappy:
    def test_safe_scenario(self):
        # Burn 10K/mo, cash 100K → 10 months runway → SAFE
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(10_000.0))
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=70_000,
            current_balance_tbc_ge=30_000,
            today=TODAY,
        )
        assert r["runway_label"] == RUNWAY_LABEL_SAFE
        assert r["runway_months"] == pytest.approx(10.0, rel=0.02)
        assert r["burn_rate_ge_per_month"] == pytest.approx(10_000.0, rel=0.01)
        assert r["current_cash_ge"] == pytest.approx(100_000.0)
        assert r["current_cash_breakdown"]["bog_ge"] == 70_000.0
        assert r["current_cash_breakdown"]["tbc_ge"] == 30_000.0
        assert r["runway_days"] > 300
        assert r["burn_trend"] == "stable"
        assert "საიმედო" in r["status_summary_ka"] or "მდგრადი" in r["status_summary_ka"]

    def test_watch_scenario(self):
        # Burn 20K/mo, cash 80K → 4 months runway → WATCH
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(20_000.0))
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=30_000,
            today=TODAY,
        )
        assert r["runway_label"] == RUNWAY_LABEL_WATCH
        assert 2.0 <= r["runway_months"] < 6.0
        assert "ფრთხილად" in r["status_summary_ka"]

    def test_critical_scenario(self):
        # Burn 50K/mo, cash 40K → 0.8 months runway → CRITICAL
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(50_000.0))
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=40_000,
            current_balance_tbc_ge=0,
            today=TODAY,
        )
        assert r["runway_label"] == RUNWAY_LABEL_CRITICAL
        assert r["runway_months"] < 2.0
        assert "კრიტიკული" in r["status_summary_ka"]

    def test_profit_scenario(self):
        # Revenue exceeds expenses → burn 0 → PROFIT, runway = ∞ (-1)
        rows = _steady_burn_12_months(monthly_burn=-5_000.0)
        loader = _data_loader_with_monthly_pnl(rows)
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=30_000,
            today=TODAY,
        )
        assert r["runway_label"] == RUNWAY_LABEL_PROFIT
        assert r["runway_months"] == -1.0
        assert r["runway_days"] == -1
        assert r["burn_rate_ge_per_month"] == 0.0

    def test_lookback_customization(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(10_000.0))
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            lookback_months=6,
            today=TODAY,
        )
        assert r["lookback_months"] == 6
        assert len(r["burn_history"]) == 6

    def test_burn_history_contains_month_and_net(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(15_000.0))
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            today=TODAY,
        )
        assert all(
            {"month", "net_ge", "expense_ge", "income_ge"}.issubset(row)
            for row in r["burn_history"]
        )

    def test_lookback_clamped_when_out_of_range(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(10_000.0))
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            lookback_months=999,
            today=TODAY,
        )
        assert r["lookback_months"] == MAX_LOOKBACK_MONTHS


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


class TestComputeCashRunwayFailures:
    def test_both_balances_missing(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months())
        r = compute_cash_runway(loader, today=TODAY)
        assert "error" in r

    def test_both_balances_invalid(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months())
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge="nonsense",
            current_balance_tbc_ge=None,
            today=TODAY,
        )
        assert "error" in r

    def test_both_balances_zero(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months())
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=0,
            current_balance_tbc_ge=0,
            today=TODAY,
        )
        assert "error" in r
        assert "0 ან უარყოფითი" in r["error"] or "ცარიელია" in r["error"]

    def test_monthly_pnl_too_short(self):
        short = _steady_burn_12_months()[:2]
        loader = _data_loader_with_monthly_pnl(short)
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            lookback_months=3,
            today=TODAY,
        )
        assert "error" in r

    def test_loader_raises_returns_error(self):
        def bad_loader():
            raise RuntimeError("data corrupted")

        r = compute_cash_runway(
            bad_loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=10_000,
            today=TODAY,
        )
        assert "error" in r

    def test_today_wrong_type_returns_error(self):
        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months())
        r = compute_cash_runway(
            loader,
            current_balance_bog_ge=50_000,
            current_balance_tbc_ge=0,
            today="2026-04-20",
        )
        assert "error" in r


# ---------------------------------------------------------------------------
# Tool schema + dispatch
# ---------------------------------------------------------------------------


class TestCashRunwayToolSchema:
    def test_registered_in_tool_schemas(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "compute_cash_runway" in names

    def test_tool_schemas_length_is_18(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        assert len(TOOL_SCHEMAS) == 19

    def test_tool_sits_after_supplier_brief(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        cr = names.index("compute_cash_runway")
        sb = names.index("prepare_supplier_brief")
        assert cr == sb + 1

    def test_schema_required_fields(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_RUNWAY_TOOL

        required = set(COMPUTE_CASH_RUNWAY_TOOL["input_schema"]["required"])
        assert required == {"current_balance_bog_ge", "current_balance_tbc_ge"}

    def test_schema_properties_shape(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_RUNWAY_TOOL

        props = COMPUTE_CASH_RUNWAY_TOOL["input_schema"]["properties"]
        assert set(props) == {
            "current_balance_bog_ge",
            "current_balance_tbc_ge",
            "lookback_months",
        }
        assert props["current_balance_bog_ge"]["type"] == "number"
        assert props["lookback_months"]["minimum"] == MIN_LOOKBACK_MONTHS
        assert props["lookback_months"]["maximum"] == MAX_LOOKBACK_MONTHS

    def test_description_mentions_triggers(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_RUNWAY_TOOL

        desc = COMPUTE_CASH_RUNWAY_TOOL["description"]
        assert "რამდენი თვე ვძლებ" in desc
        assert "cash runway" in desc.lower() or "cash-runway" in desc.lower()

    def test_description_mentions_anti_triggers(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_RUNWAY_TOOL

        desc = COMPUTE_CASH_RUNWAY_TOOL["description"]
        assert "Anti-trigger" in desc or "anti-trigger" in desc.lower()

    def test_description_mentions_workflow_mandate(self):
        from dashboard_pipeline.ai.tools import COMPUTE_CASH_RUNWAY_TOOL

        desc = COMPUTE_CASH_RUNWAY_TOOL["description"]
        assert "ask the user" in desc.lower() or "Workflow MANDATE" in desc


class TestCashRunwayDispatch:
    def test_dispatch_happy_path(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months(15_000.0))
        disp = ToolDispatcher(loader)
        result = disp.dispatch(
            "compute_cash_runway",
            {
                "current_balance_bog_ge": 60_000,
                "current_balance_tbc_ge": 20_000,
                "lookback_months": 3,
            },
        )
        assert "error" not in result
        assert result["current_cash_ge"] == 80_000.0
        assert result["runway_label"] in {
            RUNWAY_LABEL_SAFE,
            RUNWAY_LABEL_WATCH,
            RUNWAY_LABEL_CRITICAL,
            RUNWAY_LABEL_PROFIT,
        }

    def test_dispatch_returns_error_on_zero_balance(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        loader = _data_loader_with_monthly_pnl(_steady_burn_12_months())
        disp = ToolDispatcher(loader)
        result = disp.dispatch(
            "compute_cash_runway",
            {"current_balance_bog_ge": 0, "current_balance_tbc_ge": 0},
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Prompt wiring
# ---------------------------------------------------------------------------


class TestCashRunwayPromptChat:
    def test_section_header_present(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "💰 Cash Runway" in SYSTEM_PROMPT_KA
        assert "Phase 3.5" in SYSTEM_PROMPT_KA

    def test_trigger_phrases_present(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        for phrase in [
            "რამდენი თვე ვძლებ",
            "cash runway რა არის",
            "ფული თავდება",
        ]:
            assert phrase in SYSTEM_PROMPT_KA

    def test_anti_triggers_mentioned(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "Anti-triggers" in SYSTEM_PROMPT_KA
        assert "რამდენი ფული მაქვს?" in SYSTEM_PROMPT_KA

    def test_mandatory_workflow_three_steps(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "MANDATORY workflow" in SYSTEM_PROMPT_KA or "სამი ნაბიჯი" in SYSTEM_PROMPT_KA
        assert "1. **Ask first**" in SYSTEM_PROMPT_KA
        assert "2. **Wait for answer**" in SYSTEM_PROMPT_KA
        assert "3. **Call tool with live numbers**" in SYSTEM_PROMPT_KA

    def test_burn_trend_honesty_rule(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        for token in ["accelerating", "decelerating", "insufficient_history"]:
            assert token in SYSTEM_PROMPT_KA

    def test_confidence_labels_block(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        # Looking for the Cash Runway-specific confidence block (not Co-Designer).
        crr_idx = SYSTEM_PROMPT_KA.index("💰 Cash Runway")
        after = SYSTEM_PROMPT_KA[crr_idx:]
        assert "🟢 საიმედო" in after
        assert "🟠 ფრთხილად" in after
        assert "⚪ ვერ დავადგინე" in after

    def test_guardrail_refusing_hallucinated_balance(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "Guardrail" in SYSTEM_PROMPT_KA
        assert "არ ვიცი ახლა რა მიდევს" in SYSTEM_PROMPT_KA


class TestCashRunwayPromptInvestigatorUntouched:
    """Do-not-touch rule — investigator prompt MUST stay Cash-Runway-marker-free."""

    MARKERS = (
        "💰 Cash Runway",
        "Phase 3.5",
        "რამდენი თვე ვძლებ",
        "cash runway რა არის",
        "Anti-triggers",  # present in Co-Designer only in chat
        "MANDATORY workflow",
        "Ask first",
    )

    @pytest.mark.parametrize("marker", MARKERS)
    def test_marker_absent(self, marker):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA_INVESTIGATOR

        assert marker not in SYSTEM_PROMPT_KA_INVESTIGATOR
