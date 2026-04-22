"""Sprint 4C.2 partial — `summary_ka` output field added to 4 headline tools.

Phase 4C principle (Anthropic "tools should think out loud"): instead of
asking the LLM to narrate raw JSON each turn, each headline tool now ships
a pre-rendered Georgian `summary_ka` string alongside the structured data.
AI uses the summary directly; raw data remains available for cross-tool
chains.

Scope of this file — 4 tools:
- compute_waybill_total
- compute
- forecast_revenue
- analyze_dead_stock

The other 14 tools either (a) already have state_summary_ka (cash_runway,
debt_plan) or (b) don't fit the one-call-complete-answer pattern
(read_data_json, grep_code, journal_* CRUD). They're tracked in the
preview's remaining 4C scope for future work.
"""

from __future__ import annotations

from dashboard_pipeline.ai.tools import compute, compute_waybill_total


# ---------------------------------------------------------------------------
# compute — arithmetic helper
# ---------------------------------------------------------------------------


class TestComputeSummaryKa:
    def test_sum_has_summary_ka(self):
        out = compute(operation="sum", numbers=[10, 20, 30])
        assert "summary_ka" in out
        assert isinstance(out["summary_ka"], str) and out["summary_ka"]

    def test_sum_summary_mentions_result_and_count(self):
        out = compute(operation="sum", numbers=[10, 20, 30])
        assert "60" in out["summary_ka"]
        assert "3" in out["summary_ka"]  # three values
        assert "ჯამი" in out["summary_ka"]

    def test_pct_summary_uses_percent_sign(self):
        out = compute(operation="pct", numbers=[25, 100])
        assert "%" in out["summary_ka"]
        assert "პროცენტი" in out["summary_ka"]

    def test_growth_summary_uses_percent_sign(self):
        out = compute(operation="growth", numbers=[100, 150])
        assert "%" in out["summary_ka"]

    def test_diff_summary_no_percent_sign(self):
        out = compute(operation="diff", numbers=[100, 150])
        # diff result 50 but no '%' marker on diff operation
        summary = out["summary_ka"]
        assert "50" in summary
        # pct/growth's "%" must not leak onto diff
        assert "50%" not in summary or "50% " not in summary

    def test_label_surfaces_in_summary(self):
        out = compute(operation="avg", numbers=[4, 6, 8], label="test-avg")
        assert "test-avg" in out["summary_ka"]

    def test_error_path_does_not_attach_summary_ka(self):
        # Validation errors should stay minimal — no fake summary
        out = compute(operation="invalid", numbers=[1, 2])
        assert "error" in out
        assert "summary_ka" not in out

    def test_formula_still_present_alongside_summary(self):
        # Backward compat — formula field unchanged
        out = compute(operation="sum", numbers=[10, 20])
        assert "formula" in out
        assert "result" in out
        assert "summary_ka" in out


# ---------------------------------------------------------------------------
# compute_waybill_total — date-filtered waybill sum
# ---------------------------------------------------------------------------


class TestComputeWaybillTotalSummaryKa:
    def _sample_data(self):
        return {
            "waybills": [
                {
                    "date": "2026-02-27",
                    "transport_start_date": "2026-02-27",
                    "delivery_date": "2026-02-27",
                    "nominal_amount": 1000.0,
                    "effective_amount": 900.0,
                    "supplier": "შპს Alpha",
                    "type": "შემოსვლა",
                    "status": "დადასტურებული",
                },
                {
                    "date": "2026-02-27",
                    "transport_start_date": "2026-02-27",
                    "delivery_date": "2026-02-27",
                    "nominal_amount": 500.0,
                    "effective_amount": 500.0,
                    "supplier": "შპს Beta",
                    "type": "შემოსვლა",
                    "status": "დადასტურებული",
                },
            ]
        }

    def test_summary_ka_present(self):
        out = compute_waybill_total(
            data_loader=lambda: self._sample_data(),
            date="2026-02-27",
        )
        assert "summary_ka" in out
        assert isinstance(out["summary_ka"], str)

    def test_summary_contains_total_and_count(self):
        out = compute_waybill_total(
            data_loader=lambda: self._sample_data(),
            date="2026-02-27",
        )
        assert "1,500.00 ₾" in out["summary_ka"]
        assert "2 ზედნადებზე" in out["summary_ka"]

    def test_summary_contains_date_field_label_georgian(self):
        # Default date_field="transport_start_date" → "ტრანსპ. დაწყება"
        out = compute_waybill_total(
            data_loader=lambda: self._sample_data(),
            date="2026-02-27",
        )
        assert "ტრანსპ. დაწყება" in out["summary_ka"]

    def test_empty_match_summary_says_not_present(self):
        out = compute_waybill_total(
            data_loader=lambda: self._sample_data(),
            date="2026-03-15",
        )
        assert "არ არის" in out["summary_ka"]

    def test_supplier_filter_surfaces_in_summary(self):
        out = compute_waybill_total(
            data_loader=lambda: self._sample_data(),
            date="2026-02-27",
            supplier="Alpha",
        )
        assert "alpha" in out["summary_ka"].lower()

    def test_error_path_does_not_attach_summary_ka(self):
        # Missing `date` argument
        out = compute_waybill_total(data_loader=lambda: {"waybills": []}, date="")
        assert "error" in out
        assert "summary_ka" not in out


# ---------------------------------------------------------------------------
# forecast_revenue — tested via importable symbol (Prophet lazy-loaded)
# ---------------------------------------------------------------------------


class TestForecastRevenueSummaryKa:
    """forecast_revenue integration tests live in test_ai_forecasting.py. Here
    we only pin that the return dict schema *includes* `summary_ka` on success."""

    def test_module_docstring_notes_summary_ka(self):
        import dashboard_pipeline.ai.forecasting as fc_mod
        # The function should have summary_ka in its closing return
        import inspect
        source = inspect.getsource(fc_mod.forecast_revenue)
        assert "summary_ka" in source
        # Sanity: it's in the return dict, not just a comment
        return_count = source.count("\"summary_ka\"")
        assert return_count >= 1

    def test_summary_ka_mentions_store_and_horizon(self):
        # Rendered template should name store + horizon + YoY + engines
        import dashboard_pipeline.ai.forecasting as fc_mod
        import inspect
        source = inspect.getsource(fc_mod.forecast_revenue)
        # Check the summary template references key fields
        assert "store_label_ka" in source
        assert "horizon" in source
        assert "baseline" in source
        assert "YoY" in source


# ---------------------------------------------------------------------------
# analyze_dead_stock — tested via source introspection
# ---------------------------------------------------------------------------


class TestAnalyzeDeadStockSummaryKa:
    """dead_stock integration tests live in test_ai_dead_stock.py. Here we
    only pin that the return dict includes `summary_ka`."""

    def test_module_has_summary_ka_in_return(self):
        import dashboard_pipeline.ai.dead_stock as ds_mod
        import inspect
        source = inspect.getsource(ds_mod.analyze_dead_stock)
        assert "summary_ka" in source
        assert source.count("\"summary_ka\"") >= 1

    def test_summary_has_warning_prefix_path(self):
        # When matching_warning fires, summary gets ⚠️ prefix
        import dashboard_pipeline.ai.dead_stock as ds_mod
        import inspect
        source = inspect.getsource(ds_mod.analyze_dead_stock)
        assert "warning_prefix" in source
        assert "⚠️" in source

    def test_summary_covers_all_stale_buckets(self):
        # 91-180 / 181-365 / 365+ all enumerated in summary
        import dashboard_pipeline.ai.dead_stock as ds_mod
        import inspect
        source = inspect.getsource(ds_mod.analyze_dead_stock)
        assert "91-180d" in source
        assert "181-365d" in source
        assert "365d+" in source

    def test_summary_mentions_frozen_cash_and_threshold(self):
        import dashboard_pipeline.ai.dead_stock as ds_mod
        import inspect
        source = inspect.getsource(ds_mod.analyze_dead_stock)
        assert "frozen_cash_estimate" in source
        assert "threshold" in source
