"""Phase 2.2 — Scenario Simulator tests.

Covers:
* Argument coercion: percent knobs, cogs_share (fraction vs percent),
  elasticity clamping, store alias.
* Baseline loader: last_month, last_3_avg, explicit YYYY-MM, not-found.
* Scenario math: pure formula sanity (no adjustments → zero deltas;
  symmetric price↕volume behavior; variable/fixed split).
* Elasticity auto-apply: volume omitted + price set → elasticity-derived;
  volume=0 explicit → overrides elasticity.
* Decision indicator: ±2% band, revenue=0 edge case.
* summary_ka 4C.2 format markers.
* All-zero knobs → error (empty scenario guard).
* Tool registry: index 14 (between debt_plan and investigator), dispatcher
  routing, schema contract.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.scenario_simulator import (
    DECISION_BAND_PCT,
    DECISION_ERODE,
    DECISION_IMPROVE,
    DECISION_NEUTRAL,
    DEFAULT_COGS_SHARE,
    DEFAULT_PRICE_ELASTICITY,
    SOURCE_LABEL,
    _apply_scenario,
    _classify_decision,
    _margin_pct,
    _resolve_baseline,
    _resolve_cogs_share,
    _resolve_elasticity,
    _resolve_store,
    _safe_pct,
    simulate_scenario,
)


TODAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _month_row(month: str, pos_income: float, expenses: float) -> Dict[str, Any]:
    return {
        "month": month,
        "objects": {
            "ოზურგეთი": {
                "pos_income": pos_income * 0.6,
                "expenses": expenses * 0.6,
                "net": (pos_income - expenses) * 0.6,
            },
            "დვაბზუ": {
                "pos_income": pos_income * 0.4,
                "expenses": expenses * 0.4,
                "net": (pos_income - expenses) * 0.4,
            },
        },
        "total": {
            "pos_income": pos_income,
            "expenses": expenses,
            "net": pos_income - expenses,
        },
    }


def _history_12mo(
    pos_income: float = 120_000.0,
    expenses: float = 100_000.0,
) -> List[Dict[str, Any]]:
    return [
        _month_row(f"2025-{idx:02d}", pos_income, expenses) for idx in range(1, 13)
    ]


def _loader(rows: List[Dict[str, Any]]):
    return lambda: {"monthly_pnl": rows}


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------


class TestResolveStore:
    def test_none_is_total(self):
        assert _resolve_store(None) == ("total", None)

    def test_blank_is_total(self):
        assert _resolve_store("   ") == ("total", None)

    def test_georgian_names(self):
        assert _resolve_store("ოზურგეთი") == ("ოზურგეთი", None)
        assert _resolve_store("დვაბზუ") == ("დვაბზუ", None)

    def test_latin_alias(self):
        assert _resolve_store("ozurgeti") == ("ოზურგეთი", None)
        assert _resolve_store("dvabzu") == ("დვაბზუ", None)

    def test_unknown_errors(self):
        store, err = _resolve_store("paris")
        assert store is None
        assert err and "არ არის მხარდაჭერილი" in err


class TestResolveCogsShare:
    def test_none_uses_default(self):
        assert _resolve_cogs_share(None) == DEFAULT_COGS_SHARE

    def test_fraction_accepted(self):
        assert _resolve_cogs_share(0.7) == pytest.approx(0.7)

    def test_percent_accepted(self):
        # 60 (user typed percent) → 0.6
        assert _resolve_cogs_share(60) == pytest.approx(0.6)

    def test_clamped_to_unit_interval(self):
        assert _resolve_cogs_share(-0.3) == 0.0
        assert _resolve_cogs_share(150) == pytest.approx(1.0)


class TestResolveElasticity:
    def test_none_uses_default(self):
        assert _resolve_elasticity(None) == DEFAULT_PRICE_ELASTICITY

    def test_clamps_positive_to_zero(self):
        # Giffen-good direction (positive elasticity) is unrealistic for a
        # grocery shop — clamp to 0.
        assert _resolve_elasticity(2.0) == 0.0

    def test_clamps_extreme_negative(self):
        assert _resolve_elasticity(-9999) == -5.0

    def test_accepts_in_range(self):
        assert _resolve_elasticity(-0.3) == -0.3


class TestSafePct:
    def test_none_is_zero(self):
        assert _safe_pct(None) == 0.0

    def test_numeric_passthrough(self):
        assert _safe_pct(7.5) == 7.5

    def test_junk_is_default(self):
        assert _safe_pct("zzz", default=3.0) == 3.0


# ---------------------------------------------------------------------------
# Baseline loader
# ---------------------------------------------------------------------------


class TestResolveBaseline:
    def test_last_month_picks_most_recent(self):
        rows = _history_12mo(120_000, 100_000)
        baseline, label, err = _resolve_baseline(rows, "total", None)
        assert err is None
        assert baseline == {"revenue_ge": 120_000.0, "expenses_ge": 100_000.0, "net_ge": 20_000.0}
        assert label == "2025-12"

    def test_last_3_avg_smooths(self):
        rows = [
            _month_row("2025-10", 100_000, 80_000),
            _month_row("2025-11", 110_000, 90_000),
            _month_row("2025-12", 120_000, 100_000),
        ]
        baseline, label, err = _resolve_baseline(rows, "total", "last_3_avg")
        assert err is None
        assert baseline["revenue_ge"] == pytest.approx(110_000.0)
        assert baseline["expenses_ge"] == pytest.approx(90_000.0)
        assert "last_3_avg" in label

    def test_last_3_avg_needs_3_months(self):
        rows = [_month_row("2025-12", 100_000, 80_000)]
        baseline, label, err = _resolve_baseline(rows, "total", "last_3_avg")
        assert baseline is None
        assert err and "3 თვის ისტორია" in err

    def test_explicit_month_found(self):
        rows = _history_12mo()
        baseline, label, err = _resolve_baseline(rows, "total", "2025-06")
        assert err is None
        assert label == "2025-06"

    def test_explicit_month_missing(self):
        rows = _history_12mo()
        baseline, label, err = _resolve_baseline(rows, "total", "2020-01")
        assert baseline is None
        assert err and "2020-01" in err

    def test_store_specific_baseline(self):
        rows = _history_12mo(100_000, 80_000)
        baseline, label, err = _resolve_baseline(rows, "ოზურგეთი", None)
        assert err is None
        # ოზურგეთი is 60% of total per fixture.
        assert baseline["revenue_ge"] == pytest.approx(60_000.0)

    def test_empty_series_errors(self):
        baseline, label, err = _resolve_baseline([], "total", None)
        assert baseline is None
        assert err and "ცარიელია" in err


# ---------------------------------------------------------------------------
# Scenario math
# ---------------------------------------------------------------------------


class TestApplyScenario:
    def test_no_knobs_is_identity(self):
        baseline = {"revenue_ge": 100_000.0, "expenses_ge": 70_000.0, "net_ge": 30_000.0}
        result = _apply_scenario(
            baseline,
            price_change_pct=0.0,
            volume_change_pct=0.0,
            expense_change_pct=0.0,
            fixed_cost_delta_ge=0.0,
            cogs_share=0.5,
        )
        assert result["revenue_ge"] == pytest.approx(100_000.0)
        assert result["expenses_ge"] == pytest.approx(70_000.0)
        assert result["net_ge"] == pytest.approx(30_000.0)

    def test_price_raises_revenue_volume_unchanged(self):
        baseline = {"revenue_ge": 100_000.0, "expenses_ge": 70_000.0, "net_ge": 30_000.0}
        result = _apply_scenario(
            baseline,
            price_change_pct=10.0,
            volume_change_pct=0.0,
            expense_change_pct=0.0,
            fixed_cost_delta_ge=0.0,
            cogs_share=0.5,
        )
        assert result["revenue_ge"] == pytest.approx(110_000.0)
        # Expenses unchanged when volume held.
        assert result["expenses_ge"] == pytest.approx(70_000.0)

    def test_volume_scales_variable_cost_only(self):
        baseline = {"revenue_ge": 100_000.0, "expenses_ge": 60_000.0, "net_ge": 40_000.0}
        # cogs_share=0.5 → variable=30K, fixed=30K.
        # +10% volume → revenue ×1.1, variable ×1.1 = 33K, fixed=30K → total=63K.
        result = _apply_scenario(
            baseline,
            price_change_pct=0.0,
            volume_change_pct=10.0,
            expense_change_pct=0.0,
            fixed_cost_delta_ge=0.0,
            cogs_share=0.5,
        )
        assert result["revenue_ge"] == pytest.approx(110_000.0)
        assert result["expenses_ge"] == pytest.approx(63_000.0)

    def test_fixed_cost_delta_additive(self):
        baseline = {"revenue_ge": 100_000.0, "expenses_ge": 60_000.0, "net_ge": 40_000.0}
        result = _apply_scenario(
            baseline,
            price_change_pct=0.0,
            volume_change_pct=0.0,
            expense_change_pct=0.0,
            fixed_cost_delta_ge=5_000.0,
            cogs_share=0.5,
        )
        assert result["expenses_ge"] == pytest.approx(65_000.0)
        assert result["net_ge"] == pytest.approx(35_000.0)

    def test_expense_pct_multiplies_total(self):
        baseline = {"revenue_ge": 100_000.0, "expenses_ge": 60_000.0, "net_ge": 40_000.0}
        # +10% expenses → 66K. Net = 100 - 66 = 34.
        result = _apply_scenario(
            baseline,
            price_change_pct=0.0,
            volume_change_pct=0.0,
            expense_change_pct=10.0,
            fixed_cost_delta_ge=0.0,
            cogs_share=0.5,
        )
        assert result["expenses_ge"] == pytest.approx(66_000.0)


class TestMarginPct:
    def test_standard(self):
        assert _margin_pct({"revenue_ge": 100.0, "net_ge": 20.0}) == 20.0

    def test_zero_revenue_returns_zero(self):
        assert _margin_pct({"revenue_ge": 0.0, "net_ge": 0.0}) == 0.0


class TestClassifyDecision:
    def test_improve_crosses_band(self):
        baseline = {"revenue_ge": 100_000.0, "net_ge": 10_000.0}
        scenario = {"revenue_ge": 100_000.0, "net_ge": 12_500.0}
        # +2.5K on 100K revenue = +2.5% > 2% band → IMPROVE.
        assert _classify_decision(baseline, scenario) == DECISION_IMPROVE

    def test_erode_crosses_band(self):
        baseline = {"revenue_ge": 100_000.0, "net_ge": 10_000.0}
        scenario = {"revenue_ge": 100_000.0, "net_ge": 7_500.0}
        assert _classify_decision(baseline, scenario) == DECISION_ERODE

    def test_within_band_is_neutral(self):
        baseline = {"revenue_ge": 100_000.0, "net_ge": 10_000.0}
        scenario = {"revenue_ge": 100_000.0, "net_ge": 10_500.0}
        # +500 on 100K = +0.5% < 2% band → NEUTRAL.
        assert _classify_decision(baseline, scenario) == DECISION_NEUTRAL

    def test_zero_revenue_baseline_is_neutral(self):
        baseline = {"revenue_ge": 0.0, "net_ge": 0.0}
        scenario = {"revenue_ge": 0.0, "net_ge": 5_000.0}
        assert _classify_decision(baseline, scenario) == DECISION_NEUTRAL


# ---------------------------------------------------------------------------
# Top-level tool: success paths
# ---------------------------------------------------------------------------


class TestSimulateScenarioSuccess:
    def test_price_hike_with_elasticity_auto_applied(self):
        rows = _history_12mo(100_000, 70_000)
        result = simulate_scenario(
            _loader(rows),
            price_change_pct=5.0,  # elasticity -0.8 → volume auto = -4%
            today=TODAY,
        )
        assert "error" not in result
        adjustments = result["adjustments_applied"]
        assert adjustments["volume_implied_by_elasticity"] is True
        assert adjustments["volume_change_pct"] == pytest.approx(-4.0)
        assert adjustments["price_change_pct"] == 5.0

    def test_explicit_volume_overrides_elasticity(self):
        rows = _history_12mo(100_000, 70_000)
        result = simulate_scenario(
            _loader(rows),
            price_change_pct=5.0,
            volume_change_pct=0.0,  # explicit → no elasticity auto
            today=TODAY,
        )
        adjustments = result["adjustments_applied"]
        assert adjustments["volume_implied_by_elasticity"] is False
        assert adjustments["volume_change_pct"] == 0.0

    def test_output_contract_shape(self):
        rows = _history_12mo(100_000, 70_000)
        result = simulate_scenario(
            _loader(rows),
            expense_change_pct=-5.0,
            today=TODAY,
        )
        assert result["source"] == SOURCE_LABEL
        assert set(result.keys()) >= {
            "as_of_date", "base_period_used", "store", "scenario_label",
            "baseline", "scenario", "deltas",
            "adjustments_applied", "decision_indicator",
            "summary_ka", "notes",
        }
        for block in ("baseline", "scenario"):
            assert set(result[block].keys()) == {
                "revenue_ge", "expenses_ge", "net_ge", "margin_pct",
            }
        assert set(result["deltas"].keys()) == {
            "revenue_ge", "expenses_ge", "net_ge", "margin_pp",
        }

    def test_summary_ka_has_4c2_format_markers(self):
        rows = _history_12mo(100_000, 70_000)
        result = simulate_scenario(
            _loader(rows),
            price_change_pct=5.0,
            scenario_label="ფასი +5%",
            today=TODAY,
        )
        summary = result["summary_ka"]
        assert "**" in summary  # bold
        assert "·" in summary  # separator
        assert "scenario" in summary
        assert "pp" in summary  # margin delta unit

    def test_scenario_label_surfaces_in_summary(self):
        rows = _history_12mo(100_000, 70_000)
        result = simulate_scenario(
            _loader(rows),
            price_change_pct=5.0,
            scenario_label="ფასი +5%",
            today=TODAY,
        )
        assert "ფასი +5%" in result["summary_ka"]

    def test_last_3_avg_baseline(self):
        rows = [
            _month_row("2025-10", 100_000, 80_000),
            _month_row("2025-11", 110_000, 90_000),
            _month_row("2025-12", 120_000, 100_000),
        ] + [_month_row(f"2025-{i:02d}", 50_000, 40_000) for i in range(1, 10)]
        result = simulate_scenario(
            _loader(rows),
            base_period="last_3_avg",
            price_change_pct=5.0,
            today=TODAY,
        )
        assert "error" not in result
        assert "last_3_avg" in result["base_period_used"]
        # Avg revenue over last 3 = 110K, not 50K (guards against average
        # mistakenly taking earlier low-revenue months).
        assert result["baseline"]["revenue_ge"] == pytest.approx(110_000.0)


# ---------------------------------------------------------------------------
# Top-level tool: error paths
# ---------------------------------------------------------------------------


class TestSimulateScenarioErrors:
    def test_no_knobs_errors(self):
        rows = _history_12mo()
        result = simulate_scenario(_loader(rows), today=TODAY)
        assert "error" in result
        assert "ცარიელია" in result["error"]

    def test_unknown_store_errors(self):
        rows = _history_12mo()
        result = simulate_scenario(
            _loader(rows),
            store="paris",
            price_change_pct=5.0,
            today=TODAY,
        )
        assert "error" in result
        assert "მხარდაჭერილი" in result["error"]

    def test_missing_monthly_pnl_errors(self):
        loader = lambda: {"monthly_pnl": []}
        result = simulate_scenario(loader, price_change_pct=5.0, today=TODAY)
        assert "error" in result
        assert "ცარიელია" in result["error"]

    def test_unknown_base_period_errors(self):
        rows = _history_12mo()
        result = simulate_scenario(
            _loader(rows),
            base_period="2020-01",
            price_change_pct=5.0,
            today=TODAY,
        )
        assert "error" in result
        assert "2020-01" in result["error"]


# ---------------------------------------------------------------------------
# Tool registry + dispatcher integration
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    def test_tool_present_in_tool_schemas(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "simulate_scenario" in names

    def test_tool_sits_after_debt_plan(self):
        # Phase 2.2 scenario simulator clusters with debt_plan as strategic
        # advisory; sits right after it, before the investigator block.
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert (
            names[names.index("build_debt_repayment_plan") + 1]
            == "simulate_scenario"
        )

    def test_tool_schema_has_no_required_fields(self):
        # scenario_simulator should be fully optional — AI can call it
        # with zero args and get a helpful "empty scenario" error.
        from dashboard_pipeline.ai.tools import SCENARIO_SIMULATOR_TOOL

        required = SCENARIO_SIMULATOR_TOOL["input_schema"].get("required", [])
        assert required == []

    def test_tool_schema_has_all_knobs(self):
        from dashboard_pipeline.ai.tools import SCENARIO_SIMULATOR_TOOL

        props = SCENARIO_SIMULATOR_TOOL["input_schema"]["properties"]
        for key in (
            "base_period", "store",
            "price_change_pct", "volume_change_pct", "expense_change_pct",
            "fixed_cost_delta_ge", "price_elasticity", "cogs_share",
            "scenario_label",
        ):
            assert key in props, f"missing {key} in schema"

    def test_dispatcher_routes_correctly(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        rows = _history_12mo()
        dispatcher = ToolDispatcher(data_loader=_loader(rows))
        result = dispatcher.dispatch(
            "simulate_scenario",
            {"price_change_pct": 5.0},
        )
        assert "error" not in result
        assert result["decision_indicator"] in {
            DECISION_IMPROVE, DECISION_NEUTRAL, DECISION_ERODE,
        }


# ---------------------------------------------------------------------------
# Tool description contract
# ---------------------------------------------------------------------------


class TestToolDescriptionContract:
    def test_description_mentions_summary_ka(self):
        from dashboard_pipeline.ai.tools import SCENARIO_SIMULATOR_TOOL

        assert "summary_ka" in SCENARIO_SIMULATOR_TOOL["description"]

    def test_description_explains_elasticity_autoapply(self):
        from dashboard_pipeline.ai.tools import SCENARIO_SIMULATOR_TOOL

        desc = SCENARIO_SIMULATOR_TOOL["description"]
        assert "elasticity" in desc.lower()
        assert "-0.8" in desc  # default value cited

    def test_description_has_anti_triggers(self):
        from dashboard_pipeline.ai.tools import SCENARIO_SIMULATOR_TOOL

        desc = SCENARIO_SIMULATOR_TOOL["description"]
        assert "Anti-triggers" in desc
        # Must explicitly disambiguate from forecast / cash_flow / historical.
        assert "forecast_revenue" in desc
        assert "compute_cash_flow_projection" in desc
