"""Phase 4A — Debt Repayment Plan tests.

Covers:
* Argument coercion: `plan_duration_months` + `max_priority_count` clamping.
* Inflow forecast: series extraction, ±10% bracket, trend classification.
* Criticality scoring: 4-factor weighted sum, normalization, ranking.
* Supplier resolution: tax_id exact match, name fragment match, ambiguity.
* Payment recommendation: boost scaling, debt/duration fallback, floor.
* Confidence labels based on active months.
* Non-priority baseline (historical_monthly × 0.9).
* End-to-end happy paths (auto-detect + user-provided priority).
* Failure paths (no debt, no monthly_pnl, ambiguous user input).
* Tool schema + dispatch routing.
* Prompt markers in chat but not in investigator prompt.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.debt_plan import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MID,
    DEFAULT_MAX_PRIORITY_COUNT,
    DEFAULT_PLAN_DURATION_MONTHS,
    FALLBACK_MIN_MONTHLY_PAYMENT,
    FORECAST_LOOKBACK_MONTHS,
    FORECAST_UNCERTAINTY_PCT,
    MAX_BOOST,
    MAX_PLAN_DURATION_MONTHS,
    MAX_PRIORITY_COUNT,
    MIN_BOOST,
    MIN_PLAN_DURATION_MONTHS,
    MIN_PRIORITY_COUNT,
    NON_PRIORITY_BASELINE_FACTOR,
    WEIGHT_AGING,
    WEIGHT_DEBT,
    WEIGHT_DYSFUNCTION,
    WEIGHT_FREQUENCY,
    _classify_inflow_trend,
    _clamp_int,
    _confidence_for_supplier,
    _extract_monthly_net_series,
    _forecast_monthly_inflow,
    _historical_monthly_paid,
    _normalize_name,
    _normalize_series,
    _payment_dysfunction_ratio,
    _recommend_priority_payment,
    _resolve_priority_inputs,
    _score_criticality,
    _supplier_active_months,
    _supplier_waybill_frequency,
    build_debt_repayment_plan,
)


TODAY = date(2026, 4, 21)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _monthly_pnl_row(month: str, income: float, expenses: float) -> Dict[str, Any]:
    return {
        "month": month,
        "total": {
            "pos_income": income,
            "expenses": expenses,
            "net": income - expenses,
        },
    }


def _supplier(
    *,
    tax_id: str,
    org: str,
    total_debt: float = 0.0,
    total_effective: float = 0.0,
    total_paid: float = 0.0,
    strict_bank_paid: float = 0.0,
    manual_paid: float = 0.0,
    first_waybill_date: str = "2024-01-15",
    last_waybill_date: str = "2026-03-15",
    days_since_last: int = 37,
    aging_bucket: str = "31-60",
    waybill_count: int = 24,
) -> Dict[str, Any]:
    # total_effective defaults to total_paid + total_debt when not given
    if total_effective == 0.0 and (total_debt or total_paid):
        total_effective = total_paid + total_debt
    return {
        "tax_id": tax_id,
        "org": org,
        "total_debt": total_debt,
        "total_effective": total_effective,
        "total_paid": total_paid,
        "strict_bank_paid": strict_bank_paid,
        "manual_paid": manual_paid,
        "first_waybill_date": first_waybill_date,
        "last_waybill_date": last_waybill_date,
        "days_since_last": days_since_last,
        "aging_bucket": aging_bucket,
        "waybill_count": waybill_count,
        "object": "ოზურგეთი",
    }


def _make_loader(
    suppliers: List[Dict[str, Any]],
    monthly_pnl: List[Dict[str, Any]] | None = None,
):
    if monthly_pnl is None:
        monthly_pnl = [
            _monthly_pnl_row("2025-11", 135_000, 120_000),
            _monthly_pnl_row("2025-12", 138_000, 125_000),
            _monthly_pnl_row("2026-01", 142_000, 130_000),
            _monthly_pnl_row("2026-02", 150_000, 135_000),
            _monthly_pnl_row("2026-03", 145_000, 132_000),
        ]

    def _load() -> Dict[str, Any]:
        return {
            "supplier_aging": {"suppliers": suppliers, "summary": {}},
            "monthly_pnl": monthly_pnl,
        }

    return _load


def _canonical_portfolio() -> List[Dict[str, Any]]:
    """A 6-supplier portfolio with varied criticality profiles."""
    return [
        # Priority: large debt + high frequency + moderate aging → top score
        _supplier(
            tax_id="406181616",
            org="შპს ჯიდიაი",
            total_debt=313_000,
            total_paid=900_000,
            first_waybill_date="2023-06-01",
            last_waybill_date="2026-04-15",
            days_since_last=6,
            aging_bucket="0-30",
            waybill_count=180,
        ),
        # Priority: mid debt + old aging + moderate frequency
        _supplier(
            tax_id="405500001",
            org="შპს კოკაკოლა გურია",
            total_debt=18_000,
            total_paid=140_000,
            first_waybill_date="2024-08-10",
            last_waybill_date="2026-03-30",
            days_since_last=22,
            aging_bucket="0-30",
            waybill_count=64,
        ),
        # Priority: small debt but VERY aged + payment dysfunction
        _supplier(
            tax_id="404000002",
            org="ვასაძე",
            total_debt=12_000,
            total_paid=5_000,
            first_waybill_date="2024-01-01",
            last_waybill_date="2026-02-01",
            days_since_last=80,
            aging_bucket="61-90",
            waybill_count=12,
        ),
        # Borderline: steady small supplier
        _supplier(
            tax_id="404000003",
            org="პარტნიორი+",
            total_debt=5_000,
            total_paid=45_000,
            first_waybill_date="2024-05-05",
            last_waybill_date="2026-04-10",
            days_since_last=11,
            aging_bucket="0-30",
            waybill_count=30,
        ),
        # Non-priority: old dormant supplier, small debt
        _supplier(
            tax_id="404000004",
            org="ძველი ნავი",
            total_debt=800,
            total_paid=2_000,
            first_waybill_date="2024-02-01",
            last_waybill_date="2025-07-15",
            days_since_last=280,
            aging_bucket="180+",
            waybill_count=4,
        ),
        # Non-priority: healthy small supplier
        _supplier(
            tax_id="404000005",
            org="სუფთა წყარო",
            total_debt=400,
            total_paid=18_000,
            first_waybill_date="2024-03-01",
            last_waybill_date="2026-04-01",
            days_since_last=20,
            aging_bucket="0-30",
            waybill_count=18,
        ),
    ]


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------


class TestClampInt:
    def test_default_when_none(self):
        assert _clamp_int(None, 5, 1, 10) == 5

    def test_clamp_low(self):
        assert _clamp_int(-3, 5, 1, 10) == 1

    def test_clamp_high(self):
        assert _clamp_int(100, 5, 1, 10) == 10

    def test_in_range(self):
        assert _clamp_int(7, 5, 1, 10) == 7

    def test_string_coerce(self):
        assert _clamp_int("4", 5, 1, 10) == 4

    def test_garbage_falls_back(self):
        assert _clamp_int("abc", 5, 1, 10) == 5


class TestConstants:
    def test_criticality_weights_sum_to_one(self):
        total = WEIGHT_DEBT + WEIGHT_AGING + WEIGHT_FREQUENCY + WEIGHT_DYSFUNCTION
        assert total == pytest.approx(1.0)

    def test_bounds_sensible(self):
        assert MIN_PLAN_DURATION_MONTHS == 1
        assert MAX_PLAN_DURATION_MONTHS >= 6
        assert MIN_PRIORITY_COUNT == 2
        assert MAX_PRIORITY_COUNT >= 5
        assert MIN_BOOST > 1.0
        assert MAX_BOOST > MIN_BOOST
        assert 0 < NON_PRIORITY_BASELINE_FACTOR <= 1.0


# ---------------------------------------------------------------------------
# Inflow forecast
# ---------------------------------------------------------------------------


class TestInflowForecast:
    def test_extract_sorts_oldest_first(self):
        raw = [
            _monthly_pnl_row("2026-02", 100, 90),
            _monthly_pnl_row("2025-12", 80, 70),
            _monthly_pnl_row("2026-01", 90, 80),
        ]
        series = _extract_monthly_net_series(raw)
        assert [s["month"] for s in series] == ["2025-12", "2026-01", "2026-02"]

    def test_skips_invalid_rows(self):
        raw = [
            None,
            {"no_month": 1},
            _monthly_pnl_row("2025-01", 100, 90),
        ]
        series = _extract_monthly_net_series(raw)
        assert len(series) == 1 and series[0]["month"] == "2025-01"

    def test_forecast_insufficient_history(self):
        series = _extract_monthly_net_series(
            [_monthly_pnl_row("2026-02", 100, 90), _monthly_pnl_row("2026-03", 105, 92)]
        )
        assert _forecast_monthly_inflow(series) is None

    def test_forecast_happy_path(self):
        series = _extract_monthly_net_series(
            [
                _monthly_pnl_row("2026-01", 138_000, 125_000),
                _monthly_pnl_row("2026-02", 150_000, 132_000),
                _monthly_pnl_row("2026-03", 145_000, 130_000),
            ]
        )
        out = _forecast_monthly_inflow(series)
        assert out is not None
        assert out["monthly_inflow_ge"] == pytest.approx((138_000 + 150_000 + 145_000) / 3, rel=0.01)
        bracket = out["monthly_inflow_ge"] * FORECAST_UNCERTAINTY_PCT / 100.0
        assert out["low_ge"] == pytest.approx(out["monthly_inflow_ge"] - bracket, abs=0.02)
        assert out["high_ge"] == pytest.approx(out["monthly_inflow_ge"] + bracket, abs=0.02)
        assert out["window_months"] == ["2026-01", "2026-02", "2026-03"]

    def test_forecast_method_mentions_window(self):
        series = _extract_monthly_net_series(
            [
                _monthly_pnl_row("2026-01", 100_000, 80_000),
                _monthly_pnl_row("2026-02", 110_000, 90_000),
                _monthly_pnl_row("2026-03", 120_000, 100_000),
            ]
        )
        out = _forecast_monthly_inflow(series)
        assert "moving average" in out["method"]
        assert str(FORECAST_LOOKBACK_MONTHS) in out["method"]


class TestInflowTrend:
    def test_stable_trend(self):
        rows = [_monthly_pnl_row(f"2025-{idx:02d}", 100_000, 80_000) for idx in range(7, 13)]
        series = _extract_monthly_net_series(rows)
        assert _classify_inflow_trend(series) == "stable"

    def test_growing_trend(self):
        rows = []
        for idx in range(7, 13):
            income = 80_000 if idx <= 9 else 100_000  # 3 prior @80K, recent @100K → +25%
            rows.append(_monthly_pnl_row(f"2025-{idx:02d}", income, 70_000))
        series = _extract_monthly_net_series(rows)
        assert _classify_inflow_trend(series) == "growing"

    def test_declining_trend(self):
        rows = []
        for idx in range(7, 13):
            income = 120_000 if idx <= 9 else 90_000  # prior 120K vs recent 90K → −25%
            rows.append(_monthly_pnl_row(f"2025-{idx:02d}", income, 100_000))
        series = _extract_monthly_net_series(rows)
        assert _classify_inflow_trend(series) == "declining"

    def test_insufficient_history(self):
        rows = [_monthly_pnl_row(f"2026-{idx:02d}", 100_000, 80_000) for idx in (1, 2, 3)]
        series = _extract_monthly_net_series(rows)
        assert _classify_inflow_trend(series) == "insufficient_history"


# ---------------------------------------------------------------------------
# Supplier math helpers
# ---------------------------------------------------------------------------


class TestSupplierHelpers:
    def test_active_months_spanning_years(self):
        s = _supplier(
            tax_id="1",
            org="A",
            first_waybill_date="2024-01-01",
            last_waybill_date="2026-03-15",
        )
        # 2024-01 → 2026-03 = 27 months (inclusive of both endpoints)
        assert _supplier_active_months(s) == 27.0

    def test_active_months_no_last(self):
        s = _supplier(
            tax_id="1", org="A",
            first_waybill_date="2024-05-01",
            last_waybill_date="",
        )
        assert _supplier_active_months(s) == 1.0

    def test_active_months_no_first(self):
        s = _supplier(tax_id="1", org="A", first_waybill_date="", last_waybill_date="")
        assert _supplier_active_months(s) == 1.0

    def test_historical_monthly_paid(self):
        s = _supplier(
            tax_id="1",
            org="A",
            total_paid=60_000,
            first_waybill_date="2024-01-01",
            last_waybill_date="2024-12-31",
        )
        # 12 active months → 5K/mo
        assert _historical_monthly_paid(s) == pytest.approx(5_000.0)

    def test_waybill_frequency(self):
        s = _supplier(
            tax_id="1",
            org="A",
            waybill_count=24,
            first_waybill_date="2024-01-01",
            last_waybill_date="2024-12-31",
        )
        assert _supplier_waybill_frequency(s) == pytest.approx(2.0)

    def test_payment_dysfunction_full_unpaid(self):
        s = _supplier(tax_id="1", org="A", total_effective=10_000, total_paid=0)
        assert _payment_dysfunction_ratio(s) == pytest.approx(1.0)

    def test_payment_dysfunction_fully_paid(self):
        s = _supplier(tax_id="1", org="A", total_effective=10_000, total_paid=10_000)
        assert _payment_dysfunction_ratio(s) == pytest.approx(0.0)

    def test_payment_dysfunction_zero_billed(self):
        s = _supplier(tax_id="1", org="A", total_effective=0, total_paid=0)
        assert _payment_dysfunction_ratio(s) == 0.0


class TestNormalizeSeries:
    def test_nonempty(self):
        assert _normalize_series([10, 20, 40]) == [0.25, 0.5, 1.0]

    def test_all_zero(self):
        assert _normalize_series([0, 0, 0]) == [0.0, 0.0, 0.0]

    def test_empty(self):
        assert _normalize_series([]) == []


# ---------------------------------------------------------------------------
# Criticality scoring
# ---------------------------------------------------------------------------


class TestCriticalityScoring:
    def test_empty_input(self):
        assert _score_criticality([]) == []

    def test_ranks_desc_by_score(self):
        ranked = _score_criticality(_canonical_portfolio())
        scores = [entry[1] for entry in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_top_is_jidiai(self):
        """Jidiai has huge debt + high frequency — should top the ranking."""
        ranked = _score_criticality(_canonical_portfolio())
        top = ranked[0][0]
        assert top["org"].startswith("შპს ჯიდიაი")

    def test_reasons_surface_factors(self):
        ranked = _score_criticality(_canonical_portfolio())
        for supplier, score, reasons in ranked[:3]:
            assert reasons, f"{supplier['org']} missing criticality reasons"
            assert all(isinstance(r, str) and r for r in reasons)

    def test_old_small_debt_still_shows_aging_reason(self):
        ranked = _score_criticality(_canonical_portfolio())
        old_nava = next(
            (r for r in ranked if r[0]["org"] == "ძველი ნავი"), None
        )
        assert old_nava is not None
        joined = " | ".join(old_nava[2])
        assert "ძველი ვალი" in joined


# ---------------------------------------------------------------------------
# Priority supplier resolution
# ---------------------------------------------------------------------------


class TestResolvePriority:
    def test_tax_id_exact(self):
        portfolio = _canonical_portfolio()
        resolved, ambiguous = _resolve_priority_inputs(["406181616"], portfolio)
        assert len(resolved) == 1
        assert resolved[0]["org"].startswith("შპს ჯიდიაი")
        assert not ambiguous

    def test_name_fragment(self):
        portfolio = _canonical_portfolio()
        resolved, ambiguous = _resolve_priority_inputs(["კოკაკოლა"], portfolio)
        assert len(resolved) == 1
        assert "კოკაკოლა" in resolved[0]["org"]
        assert not ambiguous

    def test_unknown_token_marks_ambiguous(self):
        portfolio = _canonical_portfolio()
        resolved, ambiguous = _resolve_priority_inputs(["xyzneverexists"], portfolio)
        assert not resolved
        assert len(ambiguous) == 1
        assert ambiguous[0]["input"] == "xyzneverexists"
        assert ambiguous[0]["candidates"] == []

    def test_ambiguous_fragment_returns_candidates(self):
        portfolio = [
            _supplier(tax_id="1", org="შპს კოკაკოლა გურია", total_debt=10),
            _supplier(tax_id="2", org="კოკაკოლა ბათუმი", total_debt=20),
        ]
        resolved, ambiguous = _resolve_priority_inputs(["კოკაკოლა"], portfolio)
        assert not resolved
        assert len(ambiguous) == 1
        assert len(ambiguous[0]["candidates"]) == 2

    def test_empty_token_skipped(self):
        portfolio = _canonical_portfolio()
        resolved, ambiguous = _resolve_priority_inputs(["", " "], portfolio)
        assert not resolved and not ambiguous

    def test_normalize_name(self):
        assert _normalize_name("  შპს   კოკაკოლა ") == "შპს კოკაკოლა"


# ---------------------------------------------------------------------------
# Priority payment recommendation
# ---------------------------------------------------------------------------


class TestRecommendPriorityPayment:
    def test_uses_debt_over_duration_when_higher(self):
        # Historical × max_boost = 1000 * 1.8 = 1800
        # Debt / duration = 20000 / 2 = 10000 — this must win
        monthly, weekly, days = _recommend_priority_payment(
            total_debt=20_000,
            historical_monthly_paid=1_000,
            criticality_score=1.0,
            plan_duration_months=2,
        )
        assert monthly >= 10_000

    def test_uses_boosted_historical_when_higher(self):
        # Historical × max_boost = 10_000 * 1.8 = 18_000
        # Debt / duration = 10_000 / 4 = 2_500 — boost wins
        monthly, _, _ = _recommend_priority_payment(
            total_debt=10_000,
            historical_monthly_paid=10_000,
            criticality_score=1.0,
            plan_duration_months=4,
        )
        assert monthly == pytest.approx(18_000, abs=100)

    def test_applies_floor_when_history_missing(self):
        monthly, _, _ = _recommend_priority_payment(
            total_debt=500,
            historical_monthly_paid=0,
            criticality_score=0.2,
            plan_duration_months=2,
        )
        assert monthly >= FALLBACK_MIN_MONTHLY_PAYMENT

    def test_rounds_to_clean_numbers(self):
        monthly, weekly, _ = _recommend_priority_payment(
            total_debt=11_333,
            historical_monthly_paid=2_781,
            criticality_score=0.6,
            plan_duration_months=2,
        )
        assert monthly % 100 == 0
        assert weekly % 50 == 0

    def test_days_to_clear_reasonable(self):
        _, _, days = _recommend_priority_payment(
            total_debt=12_000,
            historical_monthly_paid=2_000,
            criticality_score=0.7,
            plan_duration_months=2,
        )
        # Must clear within 2x the duration at worst
        assert 15 <= days <= 90


# ---------------------------------------------------------------------------
# Confidence labels
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_high_for_12plus_months(self):
        s = _supplier(
            tax_id="1", org="A",
            first_waybill_date="2023-01-01",
            last_waybill_date="2024-12-31",
        )
        assert _confidence_for_supplier(s) == CONFIDENCE_HIGH

    def test_mid_for_3_to_11_months(self):
        s = _supplier(
            tax_id="1", org="A",
            first_waybill_date="2026-01-01",
            last_waybill_date="2026-05-01",
        )
        assert _confidence_for_supplier(s) == CONFIDENCE_MID

    def test_low_for_under_3_months(self):
        s = _supplier(
            tax_id="1", org="A",
            first_waybill_date="2026-04-01",
            last_waybill_date="2026-04-15",
        )
        assert _confidence_for_supplier(s) == CONFIDENCE_LOW


# ---------------------------------------------------------------------------
# End-to-end happy paths
# ---------------------------------------------------------------------------


class TestBuildPlanAutoDetect:
    def test_auto_detect_returns_top_priorities(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today=TODAY)
        assert "error" not in plan
        assert len(plan["priority_suppliers"]) <= DEFAULT_MAX_PRIORITY_COUNT
        assert len(plan["priority_suppliers"]) >= 2
        # Top priority must include jidiai (largest debt + frequency)
        top_orgs = [p["org"] for p in plan["priority_suppliers"]]
        assert any("ჯიდიაი" in o for o in top_orgs)

    def test_auto_detect_respects_max_priority_count(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, max_priority_count=3, today=TODAY)
        assert len(plan["priority_suppliers"]) == 3

    def test_forecast_present(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today=TODAY)
        fc = plan["forecast"]
        assert fc["monthly_inflow_ge"] > 0
        assert fc["low_ge"] <= fc["monthly_inflow_ge"] <= fc["high_ge"]
        assert fc["trend"] in {"stable", "growing", "declining", "insufficient_history"}

    def test_priority_entries_shape(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today=TODAY)
        for p in plan["priority_suppliers"]:
            assert {
                "tax_id", "org", "total_debt_ge", "days_since_last",
                "criticality_score", "criticality_reasons",
                "historical_monthly_paid_ge", "recommended_monthly_payment_ge",
                "recommended_weekly_payment_ge", "days_to_clear_est",
                "confidence_label", "rationale_ka",
            }.issubset(p)

    def test_non_priority_summary_present(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today=TODAY)
        np_sum = plan["non_priority_summary"]
        assert np_sum["supplier_count"] >= 0
        # Baseline at 90% of historical paid
        assert np_sum["total_baseline_monthly_ge"] >= 0

    def test_allocation_summary_math(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today=TODAY)
        a = plan["allocation_summary"]
        assert a["buffer_ge"] == pytest.approx(
            a["forecast_ge"] - a["priority_monthly_ge"] - a["non_priority_monthly_ge"],
            abs=0.02,
        )

    def test_summary_ka_nonempty_and_mentions_months(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today=TODAY)
        # Accepts both standalone "თვე" and compounds ("თვიანი", "თვიური").
        assert any(token in plan["summary_ka"] for token in ("თვე", "თვი"))
        assert str(plan["plan_duration_months"]) in plan["summary_ka"]


class TestBuildPlanUserSpecified:
    def test_single_user_priority(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(
            loader, priority_suppliers=["ვასაძე"], today=TODAY
        )
        assert len(plan["priority_suppliers"]) == 1
        assert plan["priority_suppliers"][0]["org"] == "ვასაძე"

    def test_user_priority_overrides_max_count(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(
            loader,
            priority_suppliers=["ვასაძე", "კოკაკოლა"],
            max_priority_count=10,
            today=TODAY,
        )
        assert len(plan["priority_suppliers"]) == 2

    def test_user_priority_by_tax_id(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(
            loader, priority_suppliers=["406181616"], today=TODAY
        )
        assert len(plan["priority_suppliers"]) == 1
        assert plan["priority_suppliers"][0]["tax_id"] == "406181616"

    def test_ambiguous_input_returns_candidates(self):
        portfolio = [
            _supplier(tax_id="1", org="შპს კოკაკოლა გურია", total_debt=10_000,
                     total_paid=50_000, first_waybill_date="2024-01-01",
                     last_waybill_date="2026-03-01"),
            _supplier(tax_id="2", org="კოკაკოლა ბათუმი", total_debt=8_000,
                     total_paid=30_000, first_waybill_date="2024-01-01",
                     last_waybill_date="2026-03-01"),
        ]
        loader = _make_loader(portfolio)
        plan = build_debt_repayment_plan(
            loader, priority_suppliers=["კოკაკოლა"], today=TODAY
        )
        assert "error" in plan
        assert "ambiguous" in plan
        assert len(plan["ambiguous"]) == 1


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


class TestBuildPlanFailures:
    def test_no_debt(self):
        portfolio = [
            _supplier(tax_id="1", org="A", total_debt=0, total_paid=5_000),
        ]
        loader = _make_loader(portfolio)
        plan = build_debt_repayment_plan(loader, today=TODAY)
        assert "error" in plan

    def test_no_monthly_pnl(self):
        loader = _make_loader(_canonical_portfolio(), monthly_pnl=[])
        plan = build_debt_repayment_plan(loader, today=TODAY)
        assert "error" in plan

    def test_monthly_pnl_too_short(self):
        pnl = [_monthly_pnl_row("2026-03", 100_000, 80_000)]
        loader = _make_loader(_canonical_portfolio(), monthly_pnl=pnl)
        plan = build_debt_repayment_plan(loader, today=TODAY)
        assert "error" in plan

    def test_today_wrong_type(self):
        loader = _make_loader(_canonical_portfolio())
        plan = build_debt_repayment_plan(loader, today="2026-04-21")
        assert "error" in plan

    def test_loader_raises(self):
        def bad_loader():
            raise RuntimeError("data corrupted")

        plan = build_debt_repayment_plan(bad_loader, today=TODAY)
        assert "error" in plan


# ---------------------------------------------------------------------------
# Risk flags
# ---------------------------------------------------------------------------


class TestRiskFlags:
    def test_unsustainable_plan_warns(self):
        # Tiny inflow vs huge debt → priority + baseline exceeds 90% of inflow
        low_inflow_pnl = [
            _monthly_pnl_row(f"2025-{idx:02d}", 10_000, 9_000)
            for idx in range(10, 13)
        ]
        loader = _make_loader(_canonical_portfolio(), monthly_pnl=low_inflow_pnl)
        plan = build_debt_repayment_plan(loader, today=TODAY)
        assert plan["allocation_summary"]["sustainable"] is False
        assert any("სუსტაინ" in r or "90%" in r for r in plan["risks"])

    def test_stale_supplier_flagged(self):
        portfolio = _canonical_portfolio()
        # Make "ძველი ნავი" a priority-level candidate by increasing debt
        portfolio[4]["total_debt"] = 50_000
        portfolio[4]["days_since_last"] = 200
        loader = _make_loader(portfolio)
        plan = build_debt_repayment_plan(loader, today=TODAY)
        priority_tids = {p["tax_id"] for p in plan["priority_suppliers"]}
        if "404000004" in priority_tids:
            assert any("ძველი ნავი" in r or "relationship" in r for r in plan["risks"])


# ---------------------------------------------------------------------------
# Tool schema + dispatch
# ---------------------------------------------------------------------------


class TestDebtPlanToolSchema:
    def test_registered(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "build_debt_repayment_plan" in names

    def test_total_schemas_is_21(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        assert len(TOOL_SCHEMAS) == 22

    def test_sits_after_cash_flow_projection(self):
        # Phase 2.1 inserted compute_cash_flow_projection between
        # compute_cash_runway and build_debt_repayment_plan — the runway
        # family now ends with the daily projection, then the debt planner.
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert names[names.index("compute_cash_flow_projection") + 1] == "build_debt_repayment_plan"

    def test_schema_has_all_optional_fields(self):
        from dashboard_pipeline.ai.tools import BUILD_DEBT_PLAN_TOOL

        props = BUILD_DEBT_PLAN_TOOL["input_schema"]["properties"]
        assert set(props) == {
            "priority_suppliers", "plan_duration_months", "max_priority_count",
        }
        assert BUILD_DEBT_PLAN_TOOL["input_schema"]["required"] == []
        assert BUILD_DEBT_PLAN_TOOL["input_schema"]["additionalProperties"] is False

    def test_description_mentions_autonomous(self):
        from dashboard_pipeline.ai.tools import BUILD_DEBT_PLAN_TOOL

        desc = BUILD_DEBT_PLAN_TOOL["description"]
        assert "AUTONOMOUS" in desc or "autonomous" in desc.lower()
        assert "propose" in desc.lower() or "proactive" in desc.lower()
        assert "ask" in desc.lower()  # mentions "do not ask" or similar

    def test_description_mentions_triggers_and_anti(self):
        from dashboard_pipeline.ai.tools import BUILD_DEBT_PLAN_TOOL

        desc = BUILD_DEBT_PLAN_TOOL["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        assert "prepare_supplier_brief" in desc

    def test_max_priority_bounds(self):
        from dashboard_pipeline.ai.tools import BUILD_DEBT_PLAN_TOOL

        mp = BUILD_DEBT_PLAN_TOOL["input_schema"]["properties"]["max_priority_count"]
        assert mp["minimum"] == 2
        assert mp["maximum"] == 8


class TestDebtPlanDispatch:
    def test_dispatch_happy_path(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        loader = _make_loader(_canonical_portfolio())
        disp = ToolDispatcher(loader)
        result = disp.dispatch(
            "build_debt_repayment_plan", {"max_priority_count": 3}
        )
        assert "error" not in result
        assert len(result["priority_suppliers"]) == 3

    def test_dispatch_with_user_priorities(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        loader = _make_loader(_canonical_portfolio())
        disp = ToolDispatcher(loader)
        result = disp.dispatch(
            "build_debt_repayment_plan",
            {"priority_suppliers": ["ვასაძე"]},
        )
        assert "error" not in result
        assert len(result["priority_suppliers"]) == 1
        assert result["priority_suppliers"][0]["org"] == "ვასაძე"


# ---------------------------------------------------------------------------
# Prompt wiring — chat must have Phase 4A markers; investigator stays clean
# ---------------------------------------------------------------------------


class TestDebtPlanPromptChat:
    def test_section_header_present(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "📋 ვალების გეგმა" in SYSTEM_PROMPT_KA
        assert "Phase 4A" in SYSTEM_PROMPT_KA

    def test_phase_4_philosophy_explicit(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        # Section must tag the paradigm shift so the agent cannot default
        # to PULL-ONLY patterns from Phase 3.1 Co-Designer or Phase 3.5 Cash Runway.
        assert "AI proposes" in SYSTEM_PROMPT_KA or "AUTONOMOUS STRATEGIST" in SYSTEM_PROMPT_KA
        assert "არ ელოდება" in SYSTEM_PROMPT_KA

    def test_trigger_phrases_present(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        for phrase in [
            "ვალების გეგმა",
            "კრიტიკული მომწოდებლები",
            "კომპანიებზე როგორ გავანაწილო ფული",
            "პრიორიტეტული გადახდა",
        ]:
            assert phrase in SYSTEM_PROMPT_KA

    def test_immediate_call_workflow(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "IMMEDIATELY call" in SYSTEM_PROMPT_KA or "მაშინვე გამოიძახე" in SYSTEM_PROMPT_KA
        assert "build_debt_repayment_plan" in SYSTEM_PROMPT_KA

    def test_response_format_5_part(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        for marker in [
            "Top-N Priority",
            "Rationale per priority",
            "Allocation Summary",
            "Call-to-action",
        ]:
            assert marker in SYSTEM_PROMPT_KA

    def test_critic_hat_mandate(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "🪞" in SYSTEM_PROMPT_KA
        # Must mandate critic FOR debt plans specifically (not only Co-Designer).
        section_start = SYSTEM_PROMPT_KA.index("📋 ვალების გეგმა")
        next_section = SYSTEM_PROMPT_KA.index("🔄 საკუთარი თავის გასწორების")
        section = SYSTEM_PROMPT_KA[section_start:next_section]
        assert "Critic" in section or "კრიტიკოსი" in section or "ვერ ვიცი" in section

    def test_anti_triggers_route_to_other_tools(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        assert "prepare_supplier_brief" in SYSTEM_PROMPT_KA
        assert "compute_cash_runway" in SYSTEM_PROMPT_KA
        assert "forecast_revenue" in SYSTEM_PROMPT_KA

    def test_cross_tool_chain_present(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        section_start = SYSTEM_PROMPT_KA.index("📋 ვალების გეგმა")
        next_section = SYSTEM_PROMPT_KA.index("🔄 საკუთარი თავის გასწორების")
        section = SYSTEM_PROMPT_KA[section_start:next_section]
        assert "Cross-tool" in section or "analyze_dead_stock" in section

    def test_guardrails_present(self):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

        section_start = SYSTEM_PROMPT_KA.index("📋 ვალების გეგმა")
        next_section = SYSTEM_PROMPT_KA.index("🔄 საკუთარი თავის გასწორების")
        section = SYSTEM_PROMPT_KA[section_start:next_section]
        assert "Guardrail" in section
        assert "sustainable" in section.lower()


class TestDebtPlanPromptInvestigatorUntouched:
    """Do-not-touch rule — investigator prompt MUST stay marker-free."""

    MARKERS = (
        "📋 ვალების გეგმა",
        "Phase 4A",
        "AUTONOMOUS STRATEGIST",
        "build_debt_repayment_plan",
        "IMMEDIATELY call",
        "Top-N Priority",
        "კრიტიკული მომწოდებლები",
    )

    @pytest.mark.parametrize("marker", MARKERS)
    def test_marker_absent(self, marker):
        from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA_INVESTIGATOR

        assert marker not in SYSTEM_PROMPT_KA_INVESTIGATOR


# ---------------------------------------------------------------------------
# Regression: production data.json uses ``supplier_aging`` as a LIST, not a
# ``{"suppliers": [...]}`` dict. Earlier fixtures masked this mismatch.
# ---------------------------------------------------------------------------


class TestSupplierAgingListSchema:
    """Root cause of the 2026-04-21 POST /api/debt-plan smoke failure."""

    def test_active_debt_suppliers_accepts_list(self):
        from dashboard_pipeline.ai.debt_plan import _active_debt_suppliers

        rows = [
            _supplier(
                tax_id="1", org="A", total_debt=5000,
                total_paid=1000, first_waybill_date="2024-01-01",
                last_waybill_date="2026-02-28", days_since_last=10,
                aging_bucket="0-30", waybill_count=5,
            ),
            _supplier(
                tax_id="2", org="B", total_debt=0,
                total_paid=9000, first_waybill_date="2023-01-01",
                last_waybill_date="2026-02-15", days_since_last=20,
                aging_bucket="0-30", waybill_count=12,
            ),
        ]

        active = _active_debt_suppliers(rows)

        assert len(active) == 1
        assert active[0]["tax_id"] == "1"

    def test_active_debt_suppliers_still_accepts_dict(self):
        from dashboard_pipeline.ai.debt_plan import _active_debt_suppliers

        rows = [
            _supplier(
                tax_id="9", org="X", total_debt=7777,
                total_paid=0, first_waybill_date="2025-01-01",
                last_waybill_date="2026-02-01", days_since_last=50,
                aging_bucket="31-60", waybill_count=3,
            ),
        ]

        active = _active_debt_suppliers({"suppliers": rows, "summary": {}})

        assert len(active) == 1
        assert active[0]["total_debt"] == 7777

    def test_active_debt_suppliers_rejects_garbage(self):
        from dashboard_pipeline.ai.debt_plan import _active_debt_suppliers

        assert _active_debt_suppliers(None) == []
        assert _active_debt_suppliers("not-a-list") == []
        assert _active_debt_suppliers(42) == []

    def test_build_plan_with_list_shape_returns_priorities(self):
        """Full pipeline run with production LIST shape — not dict."""
        from dashboard_pipeline.ai.debt_plan import build_debt_repayment_plan

        suppliers = _canonical_portfolio()
        monthly_pnl = [
            _monthly_pnl_row("2025-11", 135_000, 120_000),
            _monthly_pnl_row("2025-12", 138_000, 125_000),
            _monthly_pnl_row("2026-01", 142_000, 130_000),
            _monthly_pnl_row("2026-02", 150_000, 135_000),
            _monthly_pnl_row("2026-03", 145_000, 132_000),
        ]

        def _load() -> Dict[str, Any]:
            return {
                "supplier_aging": suppliers,  # LIST, not dict
                "monthly_pnl": monthly_pnl,
            }

        plan = build_debt_repayment_plan(_load, max_priority_count=3)

        assert "error" not in plan
        assert len(plan["priority_suppliers"]) >= 1
        assert plan["priority_suppliers"][0]["total_debt_ge"] > 0


# ---------------------------------------------------------------------------
# Regression: 2026-04-21 ranking bug — dormant suppliers (1,400+ day old)
# with tiny debts were dominating top-5, crowding out the real 313K ₾
# active debtor. Fix: ACTIVE_CUTOFF_DAYS + debt-dominant weights.
# ---------------------------------------------------------------------------


class TestDormantSupplierQuarantine:
    """Dormant suppliers stay out of auto-detected priority pool."""

    def test_is_dormant_supplier_past_cutoff(self):
        from dashboard_pipeline.ai.debt_plan import (
            ACTIVE_CUTOFF_DAYS,
            _is_dormant_supplier,
        )

        assert _is_dormant_supplier(
            {"days_since_last": ACTIVE_CUTOFF_DAYS + 1}
        ) is True
        assert _is_dormant_supplier(
            {"days_since_last": ACTIVE_CUTOFF_DAYS}
        ) is False
        assert _is_dormant_supplier({"days_since_last": 30}) is False

    def test_is_dormant_supplier_none_is_active(self):
        from dashboard_pipeline.ai.debt_plan import _is_dormant_supplier

        # Missing recency = can't prove dormant → default active.
        assert _is_dormant_supplier({}) is False
        assert _is_dormant_supplier({"days_since_last": None}) is False
        assert _is_dormant_supplier({"days_since_last": "garbage"}) is False

    def test_auto_detect_excludes_dormant_from_priority(self):
        """Tiny-debt zombie + real-debt active → active wins auto-detect."""
        from dashboard_pipeline.ai.debt_plan import build_debt_repayment_plan

        suppliers = [
            # Zombie: 435 ₾ debt, 4 years dormant
            _supplier(
                tax_id="zombie-1", org="Zombie Corp",
                total_debt=435, total_paid=0,
                first_waybill_date="2022-01-01",
                last_waybill_date="2022-06-01",
                days_since_last=1434,
                aging_bucket="180+", waybill_count=1,
            ),
            # Active big debtor: 313K ₾, 52 days stale
            _supplier(
                tax_id="active-1", org="Active Big Co",
                total_debt=313_000, total_paid=500_000,
                first_waybill_date="2023-01-01",
                last_waybill_date="2026-03-01",
                days_since_last=52,
                aging_bucket="31-60", waybill_count=400,
            ),
        ]
        pnl = [
            _monthly_pnl_row("2025-12", 140_000, 130_000),
            _monthly_pnl_row("2026-01", 142_000, 132_000),
            _monthly_pnl_row("2026-02", 145_000, 135_000),
        ]

        def _load() -> Dict[str, Any]:
            return {"supplier_aging": suppliers, "monthly_pnl": pnl}

        plan = build_debt_repayment_plan(_load, max_priority_count=5)

        priority_tax_ids = [
            p["tax_id"] for p in plan["priority_suppliers"]
        ]
        assert "active-1" in priority_tax_ids
        assert "zombie-1" not in priority_tax_ids

    def test_user_specified_priority_bypasses_dormant_filter(self):
        """User explicitly naming a dormant supplier still honored."""
        from dashboard_pipeline.ai.debt_plan import build_debt_repayment_plan

        suppliers = [
            _supplier(
                tax_id="zombie-1", org="Zombie Corp",
                total_debt=500, total_paid=0,
                first_waybill_date="2022-01-01",
                last_waybill_date="2022-06-01",
                days_since_last=1434,
                aging_bucket="180+", waybill_count=1,
            ),
        ]
        pnl = [
            _monthly_pnl_row("2025-12", 140_000, 130_000),
            _monthly_pnl_row("2026-01", 142_000, 132_000),
            _monthly_pnl_row("2026-02", 145_000, 135_000),
        ]

        def _load() -> Dict[str, Any]:
            return {"supplier_aging": suppliers, "monthly_pnl": pnl}

        plan = build_debt_repayment_plan(
            _load,
            priority_suppliers=["Zombie Corp"],
            max_priority_count=5,
        )

        assert "error" not in plan
        assert len(plan["priority_suppliers"]) == 1
        assert plan["priority_suppliers"][0]["tax_id"] == "zombie-1"

    def test_weights_sum_to_one(self):
        from dashboard_pipeline.ai.debt_plan import (
            WEIGHT_AGING,
            WEIGHT_DEBT,
            WEIGHT_DYSFUNCTION,
            WEIGHT_FREQUENCY,
        )

        total = (
            WEIGHT_DEBT + WEIGHT_AGING + WEIGHT_FREQUENCY + WEIGHT_DYSFUNCTION
        )
        assert abs(total - 1.0) < 1e-9

    def test_debt_weight_is_dominant(self):
        from dashboard_pipeline.ai.debt_plan import (
            WEIGHT_AGING,
            WEIGHT_DEBT,
            WEIGHT_DYSFUNCTION,
            WEIGHT_FREQUENCY,
        )

        # Debt must outweigh any single other factor (2026-04-21 rebalance).
        assert WEIGHT_DEBT > WEIGHT_AGING
        assert WEIGHT_DEBT > WEIGHT_FREQUENCY
        assert WEIGHT_DEBT > WEIGHT_DYSFUNCTION
