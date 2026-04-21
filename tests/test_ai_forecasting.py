"""Regression tests for Phase 0B Sprint 2 — `forecast_revenue` tool.

Pins the stable contract exposed to Anthropic + the LLM:

* `TOOL_SCHEMAS` registration + position + count (7 → 8 in Sprint 2; the
  count is asserted via the dedicated test and updated again in Sprint 3).
* Tool schema shape: store enum, horizon bounds, required fields.
* Input validation: horizon out of range / non-int, unknown store,
  non-string store, Georgian error messages for each failure mode.
* Monthly revenue extraction against the exact `monthly_pnl` shape
  produced by `build_monthly_pnl` (row has `total` + `objects` blocks).
* YoY growth: correct %, `None` when history < 24 months, `None` when
  prev-12 sum is zero.
* Month arithmetic (`_next_month`, `_future_months`) — including year
  roll-over at December.
* Ensemble semantics: Prophet-only, ARIMA-only, both-averaged, both-None.
* Full `forecast_revenue` happy path with stubbed Prophet + ARIMA
  classes injected via monkeypatch. Verifies `engines_used`, caveat
  `notes`, rounded forecast rows, and source label.
* Error paths: data_loader raises, data_loader returns non-dict,
  monthly_pnl short history, both engines unavailable (hint surfaced).
* Dispatcher routing: `ToolDispatcher.dispatch("forecast_revenue", ...)`
  reaches the forecasting module (lazy import is NOT a footgun).

Prophet / statsmodels are heavyweight scientific deps that frequently
fail to import on fresh Windows checkouts. To keep this suite fast and
reproducible we ALWAYS stub both via monkeypatch rather than install
the real wheels.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai import forecasting
from dashboard_pipeline.ai.forecasting import (
    DEFAULT_HORIZON_MONTHS,
    MAX_HORIZON_MONTHS,
    MIN_HISTORY_MONTHS,
    MIN_HORIZON_MONTHS,
    SOURCE_LABEL,
    STORE_DVABZU,
    STORE_OZURGETI,
    STORE_TOTAL,
    SUPPORTED_STORES,
    _ensemble,
    _extract_revenue_series,
    _future_months,
    _next_month,
    _resolve_horizon,
    _resolve_store,
    _yoy_growth_pct,
    forecast_revenue,
)
from dashboard_pipeline.ai.tools import (
    FORECAST_REVENUE_TOOL,
    TOOL_SCHEMAS,
    ToolDispatcher,
)


# ---------------------------------------------------------------------------
# Synthetic monthly_pnl — 30 months of plausible retail numbers
# ---------------------------------------------------------------------------


def _make_monthly_pnl(months: int = 30) -> List[Dict[str, Any]]:
    """Build a deterministic monthly_pnl list with both store blocks present.

    Ozurgeti ~80K + 500 per month (gentle growth), Dvabzu ~20K + 150 per month.
    Both mostly-flat — Prophet/ARIMA stubs can return anything; these tests
    don't care about forecast *values*, only that the series is correctly
    parsed and routed.
    """
    # Anchor at 2024-01 so 30 months land on 2026-06 (realistic for our test
    # fixtures — the real dashboard data ends around 2026-04).
    year, month = 2024, 1
    rows: List[Dict[str, Any]] = []
    for i in range(months):
        ym = f"{year:04d}-{month:02d}"
        ozurgeti_income = 80_000.0 + 500.0 * i
        dvabzu_income = 20_000.0 + 150.0 * i
        rows.append({
            "month": ym,
            "objects": {
                STORE_OZURGETI: {
                    "pos_income": ozurgeti_income,
                    "expenses": 40_000.0,
                    "net": ozurgeti_income - 40_000.0,
                },
                STORE_DVABZU: {
                    "pos_income": dvabzu_income,
                    "expenses": 12_000.0,
                    "net": dvabzu_income - 12_000.0,
                },
                "საერთო": {"pos_income": 0.0, "expenses": 5_000.0, "net": -5_000.0},
            },
            "total": {
                "pos_income": ozurgeti_income + dvabzu_income,
                "expenses": 57_000.0,
                "net": ozurgeti_income + dvabzu_income - 57_000.0,
            },
        })
        month += 1
        if month == 13:
            month = 1
            year += 1
    return rows


def _make_loader(data: Dict[str, Any]):
    def _loader():
        return data
    return _loader


# ---------------------------------------------------------------------------
# Tool schema registration
# ---------------------------------------------------------------------------


class TestForecastToolSchema:
    def test_registered_in_tool_schemas(self):
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "forecast_revenue" in names

    def test_tool_count_is_18(self):
        """Sprint 2 grew TOOL_SCHEMAS to 8; Sprint 3 added recall_context +
        save_memory → 10; Sprint 4 added journal_add_entry /
        journal_list_entries / journal_update_entry → 13; Phase 2.11 added
        analyze_dead_stock → 14; Phase 2.12 added prepare_supplier_brief → 15;
        Phase 3.1 added propose_feature → 16; Phase 3.5 added compute_cash_runway → 17;
        Phase 4A added build_debt_repayment_plan → 18.
        Pin the current expected total to catch silent churn either direction."""
        assert len(TOOL_SCHEMAS) == 18

    def test_forecast_revenue_index(self):
        """Sits in the compute-family cluster (index 3 right after `compute`)."""
        assert TOOL_SCHEMAS[3]["name"] == "forecast_revenue"

    def test_schema_shape(self):
        props = FORECAST_REVENUE_TOOL["input_schema"]["properties"]
        assert "horizon_months" in props
        assert "store" in props
        assert props["horizon_months"]["minimum"] == MIN_HORIZON_MONTHS
        assert props["horizon_months"]["maximum"] == MAX_HORIZON_MONTHS
        # Both fields optional (required=[])
        assert FORECAST_REVENUE_TOOL["input_schema"]["required"] == []
        assert FORECAST_REVENUE_TOOL["input_schema"]["additionalProperties"] is False

    def test_store_enum_has_3_canonical_values(self):
        enum = FORECAST_REVENUE_TOOL["input_schema"]["properties"]["store"]["enum"]
        assert enum == ["total", STORE_OZURGETI, STORE_DVABZU]

    def test_description_mentions_prophet_and_arima(self):
        desc = FORECAST_REVENUE_TOOL["description"].lower()
        assert "prophet" in desc
        assert "arima" in desc

    def test_description_forbids_historical_use(self):
        """Prompt-level guardrail: tool desc must steer LLM away from past queries."""
        assert "NEVER run this for historical" in FORECAST_REVENUE_TOOL["description"]


# ---------------------------------------------------------------------------
# Store / horizon resolution
# ---------------------------------------------------------------------------


class TestResolveStore:
    def test_none_defaults_to_total(self):
        store, err = _resolve_store(None)
        assert store == STORE_TOTAL
        assert err is None

    def test_empty_string_defaults_to_total(self):
        store, err = _resolve_store("")
        assert store == STORE_TOTAL
        assert err is None

    def test_whitespace_string_defaults_to_total(self):
        store, err = _resolve_store("   ")
        assert store == STORE_TOTAL
        assert err is None

    def test_canonical_total(self):
        store, err = _resolve_store("total")
        assert store == STORE_TOTAL
        assert err is None

    def test_canonical_georgian_ozurgeti(self):
        store, err = _resolve_store(STORE_OZURGETI)
        assert store == STORE_OZURGETI
        assert err is None

    def test_canonical_georgian_dvabzu(self):
        store, err = _resolve_store(STORE_DVABZU)
        assert store == STORE_DVABZU
        assert err is None

    def test_latin_alias_ozurgeti(self):
        store, err = _resolve_store("ozurgeti")
        assert store == STORE_OZURGETI
        assert err is None

    def test_latin_alias_dvabzu(self):
        store, err = _resolve_store("dvabzu")
        assert store == STORE_DVABZU
        assert err is None

    def test_georgian_jami_alias(self):
        store, err = _resolve_store("ჯამი")
        assert store == STORE_TOTAL
        assert err is None

    def test_case_insensitive_alias(self):
        store, err = _resolve_store("OZURGETI")
        assert store == STORE_OZURGETI
        assert err is None

    def test_unknown_string_rejects_with_georgian_error(self):
        store, err = _resolve_store("tbilisi")
        assert store is None
        assert err is not None
        assert "tbilisi" in err
        # Georgian guidance — not just English
        assert "მხარდაჭერილი" in err or "მისაღები" in err

    def test_non_string_type_rejects(self):
        store, err = _resolve_store(123)
        assert store is None
        assert err is not None


class TestResolveHorizon:
    def test_none_defaults_to_three(self):
        value, err = _resolve_horizon(None)
        assert value == DEFAULT_HORIZON_MONTHS == 3
        assert err is None

    def test_valid_integer(self):
        for h in (MIN_HORIZON_MONTHS, 3, 6, MAX_HORIZON_MONTHS):
            value, err = _resolve_horizon(h)
            assert value == h
            assert err is None

    def test_zero_rejects(self):
        value, err = _resolve_horizon(0)
        assert value is None
        assert err is not None

    def test_above_max_rejects(self):
        value, err = _resolve_horizon(MAX_HORIZON_MONTHS + 1)
        assert value is None
        assert err is not None

    def test_negative_rejects(self):
        value, err = _resolve_horizon(-1)
        assert value is None
        assert err is not None

    def test_non_int_string_rejects(self):
        value, err = _resolve_horizon("abc")
        assert value is None
        assert err is not None

    def test_numeric_string_accepted_as_int(self):
        value, err = _resolve_horizon("6")
        assert value == 6
        assert err is None


# ---------------------------------------------------------------------------
# Revenue series extraction
# ---------------------------------------------------------------------------


class TestExtractRevenueSeries:
    def test_total_happy_path(self):
        pnl = _make_monthly_pnl(30)
        months, revenues, err = _extract_revenue_series(pnl, STORE_TOTAL)
        assert err is None
        assert len(months) == 30
        assert len(revenues) == 30
        # First month = 2024-01, Ozurgeti 80_000 + Dvabzu 20_000 = 100_000
        assert revenues[0] == pytest.approx(100_000.0)

    def test_store_ozurgeti_reads_objects_block(self):
        pnl = _make_monthly_pnl(30)
        months, revenues, err = _extract_revenue_series(pnl, STORE_OZURGETI)
        assert err is None
        assert revenues[0] == pytest.approx(80_000.0)

    def test_store_dvabzu_reads_objects_block(self):
        pnl = _make_monthly_pnl(30)
        _, revenues, err = _extract_revenue_series(pnl, STORE_DVABZU)
        assert err is None
        assert revenues[0] == pytest.approx(20_000.0)

    def test_empty_pnl_rejects(self):
        months, revenues, err = _extract_revenue_series([], STORE_TOTAL)
        assert months == []
        assert revenues == []
        assert err is not None
        assert "ცარიელი" in err or "არ არის" in err

    def test_not_a_list_rejects(self):
        _, _, err = _extract_revenue_series({"oops": 1}, STORE_TOTAL)
        assert err is not None

    def test_too_short_history_rejects(self):
        pnl = _make_monthly_pnl(MIN_HISTORY_MONTHS - 1)
        months, _, err = _extract_revenue_series(pnl, STORE_TOTAL)
        assert err is not None
        assert str(MIN_HISTORY_MONTHS) in err
        # Partial history still returned so the caller can surface it.
        assert len(months) == MIN_HISTORY_MONTHS - 1

    def test_exactly_min_history_accepted(self):
        pnl = _make_monthly_pnl(MIN_HISTORY_MONTHS)
        _, revenues, err = _extract_revenue_series(pnl, STORE_TOTAL)
        assert err is None
        assert len(revenues) == MIN_HISTORY_MONTHS

    def test_malformed_row_skipped_not_fatal(self):
        pnl = _make_monthly_pnl(15)
        # Poison one row — should be silently dropped, rest succeed.
        pnl[5] = {"month": "2024-06", "objects": "not-a-dict"}
        _, revenues, err = _extract_revenue_series(pnl, STORE_OZURGETI)
        # Only 14 survive; ≥12 is enough, so no error.
        assert err is None
        assert len(revenues) == 14

    def test_missing_store_block_skipped(self):
        pnl = _make_monthly_pnl(15)
        # Drop Ozurgeti from one row → that month skipped for Ozurgeti queries.
        pnl[7]["objects"].pop(STORE_OZURGETI)
        _, revenues, err = _extract_revenue_series(pnl, STORE_OZURGETI)
        assert err is None
        assert len(revenues) == 14

    def test_non_finite_value_skipped(self):
        pnl = _make_monthly_pnl(15)
        pnl[3]["total"]["pos_income"] = float("nan")
        _, revenues, err = _extract_revenue_series(pnl, STORE_TOTAL)
        assert err is None
        assert len(revenues) == 14

    def test_out_of_order_rows_sorted(self):
        """Shuffled months should be restored to chronological order."""
        pnl = _make_monthly_pnl(15)
        pnl = [pnl[7], pnl[0], pnl[14], *pnl[1:7], *pnl[8:14]]
        months, _, err = _extract_revenue_series(pnl, STORE_TOTAL)
        assert err is None
        assert months == sorted(months)


# ---------------------------------------------------------------------------
# Month arithmetic
# ---------------------------------------------------------------------------


class TestMonthArithmetic:
    def test_next_month_mid_year(self):
        assert _next_month("2026-03") == "2026-04"

    def test_next_month_december_rolls_year(self):
        assert _next_month("2026-12") == "2027-01"

    def test_future_months_sequence(self):
        seq = _future_months("2026-04", 3)
        assert seq == ["2026-05", "2026-06", "2026-07"]

    def test_future_months_year_rollover(self):
        seq = _future_months("2025-11", 4)
        assert seq == ["2025-12", "2026-01", "2026-02", "2026-03"]

    def test_future_months_zero(self):
        assert _future_months("2026-04", 0) == []


# ---------------------------------------------------------------------------
# YoY growth
# ---------------------------------------------------------------------------


class TestYoYGrowth:
    def test_none_for_short_history(self):
        assert _yoy_growth_pct([100.0] * 23) is None

    def test_zero_prev_period_returns_none(self):
        series = [0.0] * 12 + [1_000.0] * 12
        assert _yoy_growth_pct(series) is None

    def test_flat_series_zero_growth(self):
        series = [1_000.0] * 24
        assert _yoy_growth_pct(series) == 0.0

    def test_ten_percent_growth(self):
        prev = [100.0] * 12
        curr = [110.0] * 12
        assert _yoy_growth_pct(prev + curr) == 10.0

    def test_decline_returns_negative(self):
        prev = [100.0] * 12
        curr = [80.0] * 12
        assert _yoy_growth_pct(prev + curr) == -20.0


# ---------------------------------------------------------------------------
# Ensemble semantics
# ---------------------------------------------------------------------------


class TestEnsemble:
    def test_prophet_only_returns_prophet(self):
        p = [{"month": "2026-05", "baseline": 100, "optimistic": 110, "pessimistic": 90}]
        assert _ensemble(p, None) == p

    def test_arima_only_returns_arima(self):
        a = [{"month": "2026-05", "baseline": 200, "optimistic": 220, "pessimistic": 180}]
        assert _ensemble(None, a) == a

    def test_both_none_returns_empty(self):
        assert _ensemble(None, None) == []

    def test_both_average_baseline_widen_bounds(self):
        p = [{"month": "2026-05", "baseline": 100.0, "optimistic": 110.0, "pessimistic": 90.0}]
        a = [{"month": "2026-05", "baseline": 200.0, "optimistic": 240.0, "pessimistic": 160.0}]
        merged = _ensemble(p, a)
        assert len(merged) == 1
        row = merged[0]
        # Baseline is arithmetic mean
        assert row["baseline"] == pytest.approx(150.0)
        # Bounds widen: max of upper, min of lower
        assert row["optimistic"] == pytest.approx(240.0)
        assert row["pessimistic"] == pytest.approx(90.0)

    def test_mismatched_lengths_falls_through_to_prophet(self):
        """Length mismatch is a model bug — fall back to a single engine rather than splice."""
        p = [{"month": "2026-05", "baseline": 100, "optimistic": 110, "pessimistic": 90}]
        a = [
            {"month": "2026-05", "baseline": 200, "optimistic": 240, "pessimistic": 160},
            {"month": "2026-06", "baseline": 210, "optimistic": 250, "pessimistic": 170},
        ]
        # Ensemble currently prefers Prophet when lengths don't match.
        assert _ensemble(p, a) == p


# ---------------------------------------------------------------------------
# Full forecast_revenue — stubbed engines
# ---------------------------------------------------------------------------


class _FakeProphet:
    """Minimal Prophet stand-in.

    Supports the methods forecasting.py calls: `.fit(df)` +
    `.make_future_dataframe(periods=, freq=)` + `.predict(future)`. Returns a
    pandas DataFrame with deterministic yhat / yhat_lower / yhat_upper.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def fit(self, df):
        # Grab history length so predict() knows how many rows to fabricate.
        self._history_len = len(df)
        return self

    def make_future_dataframe(self, periods: int, freq: str = "MS"):
        import pandas as pd
        # Build a simple monthly index starting from 2024-01 for total rows
        # (history + periods). The actual values aren't used — predict()
        # regenerates ds itself.
        total = self._history_len + periods
        ds = pd.date_range("2024-01-01", periods=total, freq="MS")
        self._future_periods = periods
        return pd.DataFrame({"ds": ds})

    def predict(self, future):
        import pandas as pd
        # Return yhat lane 1000, lower 800, upper 1200 for each future row.
        ds = future["ds"]
        yhat = [1_000.0] * len(ds)
        lower = [800.0] * len(ds)
        upper = [1_200.0] * len(ds)
        return pd.DataFrame({
            "ds": ds,
            "yhat": yhat,
            "yhat_lower": lower,
            "yhat_upper": upper,
        })


class _FakeARIMAResults:
    def __init__(self, horizon: int):
        self._horizon = horizon

    def get_forecast(self, steps: int):
        return _FakeARIMAForecast(steps)


class _FakeARIMAForecast:
    def __init__(self, steps: int):
        self._steps = steps

    @property
    def predicted_mean(self):
        # Return a flat mean slightly different from Prophet's stub so the
        # ensemble average is non-trivial.
        return [500.0] * self._steps

    def conf_int(self, alpha: float = 0.05):
        # lower / upper rows — 2-D list, indexable by [i][0] / [i][1].
        return [[300.0, 700.0] for _ in range(self._steps)]


class _FakeARIMA:
    def __init__(self, data, order=None):
        self._data = list(data)
        self._order = order

    def fit(self):
        return _FakeARIMAResults(horizon=0)


def _install_fake_engines(monkeypatch):
    monkeypatch.setattr(forecasting, "_load_prophet", lambda: _FakeProphet)
    monkeypatch.setattr(forecasting, "_load_arima", lambda: _FakeARIMA)


class TestForecastRevenueHappyPath:
    def test_total_horizon_default_3(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})

        result = forecast_revenue(loader)

        assert "error" not in result
        assert result["source"] == SOURCE_LABEL
        assert result["store"] == STORE_TOTAL
        assert result["horizon_months"] == 3
        assert result["history_months"] == 30
        assert result["history_start"] == "2024-01"
        # Sprint 2 goes to 2026-06 on a 30-month anchor window.
        assert len(result["forecast"]) == 3
        assert result["engines_used"] == ["prophet", "arima"]
        assert result["notes"]
        # Standard caveats always surface.
        joined = " ".join(result["notes"])
        assert "±10" in joined or "10–15" in joined or "10-15" in joined

    def test_custom_horizon_6(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader, horizon_months=6)
        assert len(result["forecast"]) == 6
        assert result["horizon_months"] == 6

    def test_store_ozurgeti_passthrough(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader, store=STORE_OZURGETI)
        assert result["store"] == STORE_OZURGETI

    def test_latin_alias_normalized(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader, store="ozurgeti")
        assert result["store"] == STORE_OZURGETI

    def test_forecast_rows_rounded_to_2dp(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader)
        for row in result["forecast"]:
            for key in ("baseline", "optimistic", "pessimistic"):
                assert isinstance(row[key], float)
                # Round to 2dp means the value == round(value, 2)
                assert row[key] == round(row[key], 2)

    def test_forecast_rows_never_negative(self, monkeypatch):
        """Revenue is physically ≥ 0. Statistical CI lower bounds that go
        negative on volatile series must be clamped to 0 before the LLM
        sees the payload. Install engines whose pessimistic forecast is
        negative and confirm the final row reports 0.00, not the raw value.
        """

        class _NegProphet:
            def __init__(self, **_):
                pass

            def fit(self, df):
                self._n = len(df)
                return self

            def make_future_dataframe(self, periods, freq="MS"):
                import pandas as pd
                total = self._n + periods
                ds = pd.date_range("2024-01-01", periods=total, freq="MS")
                return pd.DataFrame({"ds": ds})

            def predict(self, future):
                import pandas as pd
                n = len(future)
                return pd.DataFrame({
                    "ds": future["ds"],
                    "yhat": [100.0] * n,
                    "yhat_lower": [-50.0] * n,  # negative lower bound
                    "yhat_upper": [250.0] * n,
                })

        monkeypatch.setattr(forecasting, "_load_prophet", lambda: _NegProphet)
        monkeypatch.setattr(forecasting, "_load_arima", lambda: None)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader)
        assert "error" not in result
        for row in result["forecast"]:
            assert row["pessimistic"] >= 0.0
            assert row["baseline"] >= 0.0
            assert row["optimistic"] >= 0.0

    def test_ensemble_baseline_is_prophet_arima_mean(self, monkeypatch):
        """Prophet stub => 1000, ARIMA stub => 500. Ensemble baseline = 750."""
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader)
        first = result["forecast"][0]
        assert first["baseline"] == pytest.approx(750.0)
        # Bounds widen: max(1200, 700)=1200 upper, min(800, 300)=300 lower
        assert first["optimistic"] == pytest.approx(1_200.0)
        assert first["pessimistic"] == pytest.approx(300.0)

    def test_yoy_growth_present_for_long_history(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader)
        # Our synthetic series grows linearly, so YoY growth should be positive.
        assert result["yoy_growth_pct"] is not None
        assert result["yoy_growth_pct"] > 0

    def test_yoy_growth_none_for_short_history(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(12)  # min history but <24 → YoY undefined
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader)
        assert result["yoy_growth_pct"] is None

    def test_last_12_months_total_is_sum_of_tail(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        loader = _make_loader({"monthly_pnl": pnl})
        result = forecast_revenue(loader, store=STORE_OZURGETI)
        # Last 12 of Ozurgeti = sum(80_000 + 500*i) for i in [18..29]
        expected = sum(80_000.0 + 500.0 * i for i in range(18, 30))
        assert result["last_12_months_total"] == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Degraded / error paths
# ---------------------------------------------------------------------------


class TestForecastRevenueErrors:
    def test_bad_horizon_returns_error(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        loader = _make_loader({"monthly_pnl": _make_monthly_pnl(30)})
        result = forecast_revenue(loader, horizon_months=99)
        assert "error" in result
        assert "horizon_months" in result["error"]

    def test_unknown_store_returns_error(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        loader = _make_loader({"monthly_pnl": _make_monthly_pnl(30)})
        result = forecast_revenue(loader, store="tbilisi")
        assert "error" in result

    def test_data_loader_raises_is_captured(self, monkeypatch):
        _install_fake_engines(monkeypatch)

        def _loader():
            raise FileNotFoundError("no data.json")

        result = forecast_revenue(_loader)
        assert "error" in result
        assert "data.json" in result["error"]

    def test_data_loader_returns_non_dict(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        result = forecast_revenue(lambda: ["nope"])
        assert "error" in result

    def test_missing_monthly_pnl_key(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        loader = _make_loader({"something_else": 1})
        result = forecast_revenue(loader)
        assert "error" in result

    def test_short_history_rejects(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        loader = _make_loader({"monthly_pnl": _make_monthly_pnl(6)})
        result = forecast_revenue(loader)
        assert "error" in result
        assert str(MIN_HISTORY_MONTHS) in result["error"]

    def test_no_engines_available_surfaces_install_hint(self, monkeypatch):
        monkeypatch.setattr(forecasting, "_load_prophet", lambda: None)
        monkeypatch.setattr(forecasting, "_load_arima", lambda: None)
        loader = _make_loader({"monthly_pnl": _make_monthly_pnl(30)})
        result = forecast_revenue(loader)
        assert "error" in result
        assert "hint" in result
        assert "pip install" in result["hint"]

    def test_prophet_only_degrades_gracefully(self, monkeypatch):
        monkeypatch.setattr(forecasting, "_load_prophet", lambda: _FakeProphet)
        monkeypatch.setattr(forecasting, "_load_arima", lambda: None)
        loader = _make_loader({"monthly_pnl": _make_monthly_pnl(30)})
        result = forecast_revenue(loader)
        assert "error" not in result
        assert result["engines_used"] == ["prophet"]
        # Degraded-mode warning surfaces first in notes.
        assert any("მხოლოდ prophet" in note.lower() or "prophet" in note.lower() for note in result["notes"])

    def test_arima_only_degrades_gracefully(self, monkeypatch):
        monkeypatch.setattr(forecasting, "_load_prophet", lambda: None)
        monkeypatch.setattr(forecasting, "_load_arima", lambda: _FakeARIMA)
        loader = _make_loader({"monthly_pnl": _make_monthly_pnl(30)})
        result = forecast_revenue(loader)
        assert "error" not in result
        assert result["engines_used"] == ["arima"]


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


class TestDispatcherRouting:
    def test_dispatcher_routes_forecast_revenue(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        disp = ToolDispatcher(lambda: {"monthly_pnl": pnl})
        result = disp.dispatch("forecast_revenue", {"horizon_months": 2})
        assert "error" not in result
        assert result["horizon_months"] == 2
        assert len(result["forecast"]) == 2

    def test_dispatcher_call_trace_surfaces_engines_used(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        pnl = _make_monthly_pnl(30)
        disp = ToolDispatcher(lambda: {"monthly_pnl": pnl})
        disp.dispatch("forecast_revenue", {})
        trace = disp.calls
        assert trace
        last = trace[-1]
        assert last["tool"] == "forecast_revenue"
        summary = last["result_summary"]
        assert summary["ok"] is True
        assert summary["engines_used"] == ["prophet", "arima"]
        assert summary["horizon_months"] == 3

    def test_dispatcher_forwards_unknown_store_error(self, monkeypatch):
        _install_fake_engines(monkeypatch)
        disp = ToolDispatcher(lambda: {"monthly_pnl": _make_monthly_pnl(30)})
        result = disp.dispatch("forecast_revenue", {"store": "tbilisi"})
        assert "error" in result


# ---------------------------------------------------------------------------
# Prompt wiring — forecast section is reachable from SYSTEM_PROMPT_KA
# ---------------------------------------------------------------------------


class TestPromptWiring:
    def test_chat_prompt_mentions_forecast_revenue_tool(self):
        from dashboard_pipeline.ai.prompts import build_system_prompt

        text = build_system_prompt(mode="chat")
        assert "forecast_revenue" in text
        assert "🔮" in text
        assert "პროგნოზი" in text or "მომავალი" in text

    def test_investigator_prompt_does_not_include_forecast_section(self):
        """Investigator prompt is untouched by Sprint 2 — pin that."""
        from dashboard_pipeline.ai.prompts import build_system_prompt

        text = build_system_prompt(mode="investigate")
        assert "forecast_revenue" not in text
        assert "პროგნოზირება (CRITICAL — Phase 0B Sprint 2)" not in text


# ---------------------------------------------------------------------------
# Constants + exports sanity
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_supported_stores_tuple(self):
        assert SUPPORTED_STORES == (STORE_TOTAL, STORE_OZURGETI, STORE_DVABZU)

    def test_horizon_bounds(self):
        assert MIN_HORIZON_MONTHS == 1
        assert MAX_HORIZON_MONTHS == 12
        assert DEFAULT_HORIZON_MONTHS == 3

    def test_min_history_is_12(self):
        assert MIN_HISTORY_MONTHS == 12

    def test_source_label_is_useful(self):
        assert "data.json" in SOURCE_LABEL
        assert "monthly_pnl" in SOURCE_LABEL
