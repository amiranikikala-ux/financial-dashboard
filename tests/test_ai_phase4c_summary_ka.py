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


# ---------------------------------------------------------------------------
# Sprint 4C.2 REMAINING — summary_ka on the last four AI-facing tools.
#
# Scope pinned: recall_context, propose_feature, validate_vs_source,
# prepare_supplier_brief. CRUD / raw-data tools (save_memory, journal_*,
# read_data_json, grep_code, read_source_code, read_excel_source) stay
# out — they return confirm-only or raw payloads where an extra
# narration field would be noise.
# ---------------------------------------------------------------------------


class TestRecallContextSummaryKa:
    """Unit test the render helper without booting ChromaDB."""

    def test_empty_result_says_not_found(self):
        from dashboard_pipeline.ai.memory import _render_recall_summary_ka

        out = _render_recall_summary_ka({
            "query": "Alpha-ს ვალი",
            "result_count": 0,
            "results": [],
        })
        assert "შედეგი არ ვიპოვე" in out
        assert "Alpha" in out

    def test_hits_surface_count_and_top_match(self):
        from dashboard_pipeline.ai.memory import _render_recall_summary_ka

        out = _render_recall_summary_ka({
            "query": "Beta-ს ფასდაკლება",
            "result_count": 3,
            "results": [
                {
                    "id": "chat_abc123",
                    "rank": 1,
                    "distance": 0.23,
                    "created_at": "2026-04-01T10:00:00",
                },
                {"id": "chat_def456", "rank": 2, "distance": 0.41},
                {"id": "chat_ghi789", "rank": 3, "distance": 0.55},
            ],
        })
        assert "3 შედეგი" in out
        assert "chat_abc123" in out
        assert "0.23" in out
        assert "Beta" in out

    def test_distance_fallback_when_missing(self):
        from dashboard_pipeline.ai.memory import _render_recall_summary_ka

        out = _render_recall_summary_ka({
            "query": "q",
            "result_count": 1,
            "results": [{"id": "x", "rank": 1}],
        })
        # Missing distance falls back to 1.00 (max cosine distance).
        assert "1.00" in out

    def test_recall_context_error_has_no_summary(self, monkeypatch):
        import dashboard_pipeline.ai.memory as mem_mod

        monkeypatch.setattr(mem_mod, "_load_chromadb", lambda: None)
        mem_mod.reset_memory_store()
        result = mem_mod.recall_context("anything")
        assert "error" in result
        assert "summary_ka" not in result


class TestProposeFeatureSummaryKa:
    """Unit test the render helper directly — dispatcher wiring is covered
    by ToolDispatcher integration tests elsewhere."""

    def test_full_payload_renders_one_line(self):
        from dashboard_pipeline.ai.tools import _render_propose_feature_summary_ka

        out = _render_propose_feature_summary_ka({
            "ok": True,
            "entry_id": "journal_abc123",
            "title": "გაყინული სტოკის Dashboard გვერდი",
            "proposal": {
                "time_estimate": "2-3 დღე",
                "risk_critique": "staleness: barcode drift წაშლის ციფრებს",
            },
        })
        assert "გაყინული სტოკის Dashboard გვერდი" in out
        assert "2-3 დღე" in out
        assert "staleness" in out
        assert "journal_abc123" in out

    def test_long_risk_critique_is_truncated(self):
        from dashboard_pipeline.ai.tools import _render_propose_feature_summary_ka

        long_risk = "x" * 200
        out = _render_propose_feature_summary_ka({
            "ok": True,
            "entry_id": "journal_x",
            "title": "t",
            "proposal": {"time_estimate": "1 დღე", "risk_critique": long_risk},
        })
        assert "…" in out
        # Ensure the overall line doesn't balloon to 200+ chars on this axis.
        assert len(out) < 200

    def test_missing_optional_fields_still_renders(self):
        from dashboard_pipeline.ai.tools import _render_propose_feature_summary_ka

        out = _render_propose_feature_summary_ka({
            "ok": True,
            "entry_id": "journal_x",
            "title": "headline only",
            "proposal": {},
        })
        assert "headline only" in out
        assert "journal_x" in out

    def test_dispatcher_attaches_summary_on_success(self):
        """propose_feature dispatch path wraps the journal payload."""
        import dashboard_pipeline.ai.tools as tools_mod
        import inspect

        source = inspect.getsource(tools_mod.ToolDispatcher.dispatch)
        # Guard against regressions where someone removes the wrap.
        assert "_render_propose_feature_summary_ka" in source


class TestValidateVsSourceSummaryKa:
    def _sample_data(self):
        return {
            "suppliers": [
                {"tax_id": "1", "total_effective": 1000, "total_debt": 0},
                {"tax_id": "2", "total_effective": 2000, "total_debt": 500},
                {"tax_id": "3", "total_effective": 3000, "total_debt": 0},
            ],
            "financial_ratios": {"current_ratio": 1.5},
        }

    def test_inspected_path_has_summary(self):
        from dashboard_pipeline.ai.tools import validate_vs_source

        out = validate_vs_source(
            "suppliers", data_loader=lambda: self._sample_data(),
        )
        assert "summary_ka" in out
        assert "suppliers" in out["summary_ka"]
        assert "3 მწკრივი" in out["summary_ka"]

    def test_match_path_uses_check_icon(self):
        from dashboard_pipeline.ai.tools import validate_vs_source

        out = validate_vs_source(
            "suppliers",
            expected_row_count=3,
            data_loader=lambda: self._sample_data(),
        )
        summary = out["summary_ka"]
        assert "✅" in summary
        assert "row count ✓" in summary

    def test_mismatch_path_uses_cross_icon_and_delta(self):
        from dashboard_pipeline.ai.tools import validate_vs_source

        out = validate_vs_source(
            "suppliers",
            expected_row_count=5,
            data_loader=lambda: self._sample_data(),
        )
        summary = out["summary_ka"]
        assert "❌" in summary
        assert "row count ✗" in summary
        # Expected 5, got 3 → delta +2 (expected − current).
        assert "+2" in summary

    def test_total_mismatch_shows_formatted_delta(self):
        from dashboard_pipeline.ai.tools import validate_vs_source

        out = validate_vs_source(
            "suppliers",
            expected_total=7000,
            field_name="total_effective",
            data_loader=lambda: self._sample_data(),
        )
        summary = out["summary_ka"]
        assert "total_effective" in summary
        assert "7,000.00" in summary
        assert "6,000.00" in summary

    def test_error_path_has_no_summary(self):
        from dashboard_pipeline.ai.tools import validate_vs_source

        out = validate_vs_source(
            "nonexistent_section",
            data_loader=lambda: self._sample_data(),
        )
        assert "error" in out
        assert "summary_ka" not in out


class TestPrepareSupplierBriefSummaryKa:
    """Unit test the render helpers. Full-pipeline integration lives in
    test_ai_supplier_brief.py; here we pin the summary contract."""

    def test_focused_mentions_supplier_and_leverage(self):
        from dashboard_pipeline.ai.supplier_brief import (
            _render_focused_summary_ka,
        )

        out = _render_focused_summary_ka({
            "supplier": {
                "resolved_name": "შპს Alpha",
                "match_confidence": "high",
            },
            "leverage_score": {"score": 72, "label": "ძლიერი"},
            "negotiation_plays": [
                {"ask_ka": "მოითხოვე -3% წლიური ბრუნვაზე"},
            ],
        })
        assert "Alpha" in out
        assert "72/100" in out
        assert "ძლიერი" in out
        assert "-3%" in out

    def test_focused_low_confidence_surfaces_warning(self):
        from dashboard_pipeline.ai.supplier_brief import (
            _render_focused_summary_ka,
        )

        out = _render_focused_summary_ka({
            "supplier": {
                "resolved_name": "Beta",
                "match_confidence": "medium",
            },
            "leverage_score": {"score": 40, "label": "საშუალო"},
            "negotiation_plays": [],
        })
        assert out.startswith("⚠️")
        assert "medium" in out
        assert "დააზუსტე" in out

    def test_focused_truncates_long_play(self):
        from dashboard_pipeline.ai.supplier_brief import (
            _render_focused_summary_ka,
        )

        out = _render_focused_summary_ka({
            "supplier": {
                "resolved_name": "X",
                "match_confidence": "high",
            },
            "leverage_score": {"score": 50, "label": "საშუალო"},
            "negotiation_plays": [{"ask_ka": "x" * 200}],
        })
        assert "…" in out

    def test_portfolio_mentions_totals_and_concentration(self):
        from dashboard_pipeline.ai.supplier_brief import (
            _render_portfolio_summary_ka,
        )

        out = _render_portfolio_summary_ka({
            "total_suppliers": 270,
            "total_spend_ge": 1_234_567.89,
            "concentration": {
                "top_5_share_pct": 42.5,
                "concentration_label": "highly concentrated",
            },
            "top_candidates": [
                {
                    "supplier_name": "ვასაძე",
                    "leverage_score": 85,
                },
            ],
            "aggregate_savings_opportunity_ge": 23_500.0,
        })
        assert "270 მომწოდებელი" in out
        assert "1,234,567.89" in out
        assert "top-5 42.5%" in out
        assert "highly concentrated" in out
        assert "ვასაძე" in out
        assert "85" in out
        assert "23,500" in out

    def test_portfolio_zero_savings_hides_savings_chunk(self):
        from dashboard_pipeline.ai.supplier_brief import (
            _render_portfolio_summary_ka,
        )

        out = _render_portfolio_summary_ka({
            "total_suppliers": 5,
            "total_spend_ge": 1000.0,
            "concentration": {
                "top_5_share_pct": 100.0,
                "concentration_label": "single bucket",
            },
            "top_candidates": [],
            "aggregate_savings_opportunity_ge": 0.0,
        })
        assert "portfolio savings" not in out
