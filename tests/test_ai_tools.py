"""Unit tests for dashboard_pipeline.ai.tools.

Covers:
- Section allowlist gating (unknown section returns error, not crash).
- List sections: row cap, total_count, truncated flag.
- Dict / scalar sections: value returned intact.
- Filter semantics: exact match, case-insensitive substring, missing key.
- `TOOL_SCHEMAS` contract shape.
"""

from __future__ import annotations

import json

import pytest

from dashboard_pipeline.ai.tools import (
    ALLOWED_SECTIONS,
    DEFAULT_ROW_LIMIT,
    MAX_OUTPUT_CHARS,
    MAX_ROW_LIMIT,
    SECTION_COLUMN_PROFILES,
    TOOL_SCHEMAS,
    ToolDispatcher,
    _truncate_output,
    get_cached_tool_schemas,
)


# ---------------------------------------------------------------------------
# Synthetic data.json used across tests
# ---------------------------------------------------------------------------

SAMPLE_SUPPLIERS = [
    {
        "tax_id": f"10000000{i}",
        "normalized_supplier": f"Supplier {i}",
        "total_effective": 1000 * i,
        "total_debt": 100 * i,
        "payment_scope": "bank_matched" if i % 2 == 0 else "mixed",
        # Engineering-only fields that SHOULD be pruned when columns="minimal":
        "payment_scope_note": f"internal note {i}",
        "supplier_truth_summary": f"trust-{i}",
        "supplier_truth_sources": [f"src-{i}"],
    }
    for i in range(1, 61)
]


SAMPLE_DATA = {
    "meta": {
        "data_period_label": "2025-01 – 2025-03",
        "generated_at": "2025-03-31T00:00:00Z",
    },
    "suppliers": SAMPLE_SUPPLIERS,
    "supplier_aging": [
        {"supplier": "Supplier 1", "current": 100, "overdue_30": 0},
    ],
    "aging_summary": {"total_current": 100, "total_overdue": 0},
    "monthly_pnl": [
        {"month": "2025-01", "revenue": 80000, "net": 10000},
        {"month": "2025-02", "revenue": 90000, "net": 12000},
    ],
    "financial_ratios": {"current_ratio": 1.5, "gross_margin": 0.35},
    "forecast": {"months": ["2025-04"], "revenue": [95000]},
}


def _loader():
    return SAMPLE_DATA


# ---------------------------------------------------------------------------
# Tool schema contract
# ---------------------------------------------------------------------------

class TestToolSchema:
    def test_read_data_json_schema_shape(self):
        assert len(TOOL_SCHEMAS) >= 1
        tool = TOOL_SCHEMAS[0]
        assert tool["name"] == "read_data_json"
        assert "section" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["required"] == ["section"]
        # enum must be a subset of ALLOWED_SECTIONS
        enum_values = set(tool["input_schema"]["properties"]["section"]["enum"])
        assert enum_values == set(ALLOWED_SECTIONS.keys())

    def test_schema_is_json_serializable(self):
        json.dumps(TOOL_SCHEMAS, ensure_ascii=False)


def _tool_by_name(name: str) -> dict:
    for tool in TOOL_SCHEMAS:
        if tool.get("name") == name:
            return tool
    raise AssertionError(f"tool not found in TOOL_SCHEMAS: {name}")


class TestPhase4C1PartAPokaYoke:
    """Phase 4C.1 Part A — routing hardening on the 5 legacy tools.

    Sprint 4C.1 scoped audit (commit 354ffe7) applied junior-dev-docstring
    discipline to the 3 VAT tools. Part A (this session) extends the same
    discipline to read_data_json + 4 investigator tools so AI routes
    business-data questions to specialized tools (summary_ka-equipped)
    instead of dumping raw rows through read_data_json. These assertions
    pin the new markers so a later refactor can't silently drop them.
    """

    def test_read_data_json_has_anti_triggers_to_specialized_tools(self):
        desc = _tool_by_name("read_data_json")["description"]
        # Triggers section present
        assert "Triggers" in desc
        # Anti-triggers must route to these specialized tools:
        for tool_name in (
            "get_vat_reconciliation_month",
            "compute_waybill_total",
            "forecast_revenue",
            "compute_cash_runway",
            "compute_cash_flow_projection",
            "simulate_scenario",
            "analyze_product_profitability",
            "find_promotion_candidates",
            "detect_trends",
            "analyze_dead_stock",
            "prepare_supplier_brief",
            "build_debt_repayment_plan",
            "recall_context",
        ):
            assert tool_name in desc, (
                f"read_data_json anti-trigger must route to {tool_name}"
            )
        # Workflow discipline
        assert "filter" in desc.lower()
        assert "minimal" in desc.lower()
        assert "source" in desc.lower()

    def test_read_source_code_separates_code_from_data_questions(self):
        desc = _tool_by_name("read_source_code")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Data questions must be routed away from this tool
        assert "read_data_json" in desc
        # Investigator partnership
        assert "grep_code" in desc
        assert "read_excel_source" in desc

    def test_grep_code_separates_code_from_data_questions(self):
        desc = _tool_by_name("grep_code")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Must redirect business-data queries and chat-memory queries
        assert "read_data_json" in desc
        assert "recall_context" in desc

    def test_read_excel_source_surfaces_validate_vs_source_partnership(self):
        desc = _tool_by_name("read_excel_source")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Excel ground-truth partnership
        assert "validate_vs_source" in desc
        assert "read_data_json" in desc

    def test_validate_vs_source_documents_workflow_and_routing(self):
        desc = _tool_by_name("validate_vs_source")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Directs to row-browsing tools when mismatch needs drilling
        assert "read_excel_source" in desc
        assert "read_data_json" in desc
        # Returns contract surfaced so AI knows what it gets
        assert "match" in desc.lower()


class TestPhase4C1PartBPokaYoke:
    """Phase 4C.1 Part B — routing hardening for 3 remaining gap tools.

    After Part A (read_data_json + 4 investigator tools), the Part B survey
    found only 3 tools with real Triggers/Anti-triggers gaps among the
    remaining 12 candidates: compute_waybill_total had zero Triggers/Anti-
    triggers blocks; analyze_dead_stock had the anti-trigger inline as a
    single trailing line; journal_update_entry lacked structured blocks.
    The other 9 (save_memory / recall_context / journal_add_entry /
    journal_list_entries / prepare_supplier_brief / propose_feature /
    analyze_product_profitability / find_promotion_candidates /
    build_debt_repayment_plan) already carry the discipline.
    """

    def test_compute_waybill_total_has_routing_blocks(self):
        desc = _tool_by_name("compute_waybill_total")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Routing partners for waybill-adjacent questions
        assert "prepare_supplier_brief" in desc
        assert "read_data_json" in desc
        assert "supplier_aging" in desc
        assert "forecast_revenue" in desc
        # Date-field semantics MUST stay documented (wrong pick = wrong number)
        for field in ("transport_start_date", "date", "delivery_date"):
            assert field in desc

    def test_analyze_dead_stock_anti_triggers_in_dedicated_block(self):
        desc = _tool_by_name("analyze_dead_stock")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Critical routing: not every SKU question is dead-stock
        assert "analyze_product_profitability" in desc
        assert "find_promotion_candidates" in desc
        assert "prepare_supplier_brief" in desc
        assert "detect_trends" in desc
        # Honesty rule on frozen_cash_estimate upper-bound still there
        assert "UPPER BOUND" in desc
        assert "matching_warning" in desc

    def test_journal_update_entry_has_structured_blocks(self):
        desc = _tool_by_name("journal_update_entry")["description"]
        assert "Triggers" in desc
        assert "Anti-triggers" in desc
        # Routing partners
        assert "journal_add_entry" in desc
        assert "journal_list_entries" in desc
        # Critical guardrails
        assert "NEVER fabricate" in desc or "never fabricate" in desc.lower()
        # Status semantics preserved
        for status in ("done", "cancelled", "open"):
            assert status in desc


# ---------------------------------------------------------------------------
# Allowlist / error paths
# ---------------------------------------------------------------------------

class TestSectionAllowlist:
    def test_unknown_section_returns_error(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "not_a_section"})
        assert "error" in result
        assert "not_a_section" in result["error"]

    def test_missing_section_in_data(self):
        disp = ToolDispatcher(lambda: {"meta": {"ok": True}})
        result = disp.dispatch("read_data_json", {"section": "suppliers"})
        assert "error" in result
        assert "suppliers" in result["error"]
        assert result["source"] == "data.json"

    def test_empty_arguments_returns_error(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {})
        assert "error" in result

    def test_unknown_tool_name(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("destroy_universe", {})
        assert "error" in result

    def test_invalid_filter_type(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "filter": "bogus"},
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# List section behavior
# ---------------------------------------------------------------------------

class TestListSections:
    def test_list_default_row_limit(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "suppliers"})
        assert "rows" in result
        assert result["total_count"] == 60
        assert result["row_count"] == DEFAULT_ROW_LIMIT
        assert result["truncated"] is True
        assert result["source"] == "data.json:suppliers"

    def test_list_custom_limit(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "limit": 5},
        )
        assert result["row_count"] == 5
        assert result["truncated"] is True
        assert len(result["rows"]) == 5

    def test_list_limit_clamped_to_max(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "limit": MAX_ROW_LIMIT + 999},
        )
        assert result["row_count"] == 60  # clamped to total
        assert result["truncated"] is False

    def test_list_limit_invalid_falls_back_to_default(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "limit": "not-a-number"},
        )
        assert result["row_count"] == DEFAULT_ROW_LIMIT

    def test_list_no_truncation_when_small(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "monthly_pnl"})
        assert result["total_count"] == 2
        assert result["row_count"] == 2
        assert result["truncated"] is False


# ---------------------------------------------------------------------------
# Filter semantics
# ---------------------------------------------------------------------------

class TestFilter:
    def test_filter_exact_value(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {
                "section": "suppliers",
                "filter": {"payment_scope": "bank_matched"},
            },
        )
        # Every remaining row must match.
        assert all(r["payment_scope"] == "bank_matched" for r in result["rows"])
        assert result["filter_applied"] == {"payment_scope": "bank_matched"}
        # Exactly half of 60 are bank_matched (even i).
        assert result["filtered_count"] == 30

    def test_filter_substring_case_insensitive(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {
                "section": "suppliers",
                "filter": {"normalized_supplier": "supplier 5"},
                "limit": 100,
            },
        )
        # Matches "Supplier 5", "Supplier 50", "Supplier 51" ...
        names = [r["normalized_supplier"] for r in result["rows"]]
        assert all("supplier 5" in n.lower() for n in names)

    def test_filter_unknown_key_yields_empty(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {
                "section": "suppliers",
                "filter": {"not_a_field": "anything"},
            },
        )
        assert result["rows"] == []
        assert result["filtered_count"] == 0

    def test_filter_numeric_exact(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {
                "section": "suppliers",
                "filter": {"total_effective": 10000},
            },
        )
        assert result["filtered_count"] == 1
        assert result["rows"][0]["total_effective"] == 10000


# ---------------------------------------------------------------------------
# Non-list sections
# ---------------------------------------------------------------------------

class TestNonListSections:
    def test_dict_section_returns_value(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "financial_ratios"})
        assert "value" in result
        assert result["value"]["current_ratio"] == 1.5
        assert result["row_count"] == 1
        assert result["truncated"] is False

    def test_meta_section(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "meta"})
        assert result["value"]["generated_at"] == "2025-03-31T00:00:00Z"


# ---------------------------------------------------------------------------
# Call trace / source attribution
# ---------------------------------------------------------------------------

class TestCallTrace:
    def test_calls_accumulate(self):
        disp = ToolDispatcher(_loader)
        disp.dispatch("read_data_json", {"section": "meta"})
        disp.dispatch("read_data_json", {"section": "monthly_pnl"})
        calls = disp.calls
        assert len(calls) == 2
        assert calls[0]["tool"] == "read_data_json"
        assert calls[0]["result_summary"]["ok"] is True
        assert calls[1]["result_summary"]["section"] == "monthly_pnl"

    def test_error_call_recorded_as_not_ok(self):
        disp = ToolDispatcher(_loader)
        disp.dispatch("read_data_json", {"section": "bogus"})
        calls = disp.calls
        assert len(calls) == 1
        assert calls[0]["result_summary"]["ok"] is False

    def test_data_loader_called_once(self):
        hit_count = {"n": 0}

        def counting_loader():
            hit_count["n"] += 1
            return SAMPLE_DATA

        disp = ToolDispatcher(counting_loader)
        disp.dispatch("read_data_json", {"section": "meta"})
        disp.dispatch("read_data_json", {"section": "suppliers"})
        disp.dispatch("read_data_json", {"section": "monthly_pnl"})
        assert hit_count["n"] == 1

    def test_loader_errors_returned_cleanly(self):
        def broken_loader():
            raise FileNotFoundError("data.json missing")

        disp = ToolDispatcher(broken_loader)
        result = disp.dispatch("read_data_json", {"section": "meta"})
        assert "error" in result
        assert "data.json" in result["error"]


# ---------------------------------------------------------------------------
# JSON safety
# ---------------------------------------------------------------------------

class TestJsonSafety:
    def test_result_is_json_serializable(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "suppliers"})
        encoded = json.dumps(result, ensure_ascii=False)
        assert "data.json:suppliers" in encoded


# ---------------------------------------------------------------------------
# Phase 1 polish: row-limit default + column pruning
# ---------------------------------------------------------------------------


class TestRowLimitDefault:
    def test_default_row_limit_is_10(self):
        """Phase 1 polish: tighter default to curb context bloat."""
        assert DEFAULT_ROW_LIMIT == 10


class TestColumnPruning:
    def test_default_is_minimal_and_prunes_suppliers(self):
        """Columns default to 'minimal' and engineering fields are dropped."""
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "limit": 3},
        )
        assert result["columns"] == "minimal"
        assert "columns_kept" in result
        assert "payment_scope" in result["columns_kept"]

        for row in result["rows"]:
            # Pruned fields must be gone.
            assert "payment_scope_note" not in row
            assert "supplier_truth_summary" not in row
            assert "supplier_truth_sources" not in row
            # Kept fields still present.
            assert "tax_id" in row
            assert "total_effective" in row
            assert "payment_scope" in row

    def test_columns_all_keeps_every_field(self):
        """Pass `columns='all'` to opt out of pruning."""
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "limit": 3, "columns": "all"},
        )
        assert result["columns"] == "all"
        assert "columns_kept" not in result
        for row in result["rows"]:
            # Engineering fields retained.
            assert "payment_scope_note" in row
            assert "supplier_truth_summary" in row

    def test_minimal_without_profile_skips_pruning(self):
        """Sections with no profile entry pass rows through intact."""
        # `aging_summary` is a dict (not a list) — covered elsewhere.
        # Use a synthetic list section without a profile to exercise this path.
        disp = ToolDispatcher(lambda: {
            **SAMPLE_DATA,
            # `retail_sales` is allowlisted but has no SECTION_COLUMN_PROFILES entry.
            "retail_sales": [
                {"period": "2025-01", "net_sales": 123.45, "misc_field": True},
            ],
        })
        result = disp.dispatch(
            "read_data_json",
            {"section": "retail_sales"},
        )
        assert result["columns"] == "minimal"
        assert "columns_kept" not in result
        # Every original field is retained because no profile exists.
        assert result["rows"][0] == {
            "period": "2025-01",
            "net_sales": 123.45,
            "misc_field": True,
        }

    def test_invalid_columns_value_falls_back_to_minimal(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "read_data_json",
            {"section": "suppliers", "limit": 1, "columns": "bogus"},
        )
        assert result["columns"] == "minimal"

    def test_profile_keeps_only_fields_actually_present(self):
        """Minimal profile should not add missing keys — it's a filter."""
        disp = ToolDispatcher(_loader)
        result = disp.dispatch("read_data_json", {"section": "monthly_pnl"})
        # Sample data only has month/revenue/net — profile also mentions cogs etc.
        # Missing keys must NOT appear as None.
        for row in result["rows"]:
            assert set(row.keys()) == {"month", "revenue", "net"}


class TestColumnsInSchema:
    def test_schema_exposes_columns_enum(self):
        tool = TOOL_SCHEMAS[0]
        props = tool["input_schema"]["properties"]
        assert "columns" in props
        assert props["columns"]["enum"] == ["minimal", "all"]

    def test_profiles_are_lists_of_strings(self):
        for section, cols in SECTION_COLUMN_PROFILES.items():
            assert section in ALLOWED_SECTIONS, (
                f"Profile references section '{section}' not in allowlist"
            )
            assert isinstance(cols, list)
            assert all(isinstance(c, str) for c in cols)
            assert len(cols) == len(set(cols)), (
                f"Profile '{section}' has duplicate columns"
            )


# ---------------------------------------------------------------------------
# Phase 1 polish: Anthropic prompt caching — tool schema annotation
# ---------------------------------------------------------------------------


class TestCachedToolSchemas:
    def test_cached_schemas_have_cache_control_on_last(self):
        cached = get_cached_tool_schemas()
        assert cached[-1]["cache_control"] == {"type": "ephemeral"}

    def test_cached_does_not_mutate_module_constant(self):
        _ = get_cached_tool_schemas()
        assert "cache_control" not in TOOL_SCHEMAS[-1]

    def test_cached_is_json_serializable(self):
        cached = get_cached_tool_schemas()
        # Must still round-trip through JSON (Anthropic SDK serializes it).
        json.dumps(cached, ensure_ascii=False)

    def test_cached_preserves_name_and_schema(self):
        cached = get_cached_tool_schemas()
        assert cached[0]["name"] == "read_data_json"
        # Schema body untouched.
        assert (
            cached[0]["input_schema"]
            == TOOL_SCHEMAS[0]["input_schema"]
        )


# ---------------------------------------------------------------------------
# Waybills section allowlist + column profile (bug fix 2026-04-18 02:55)
# ---------------------------------------------------------------------------


class TestWaybillsSection:
    """`waybills` (list of 21k individual waybills) must be queryable with a
    date filter so users can ask daily-granularity questions without the AI
    falling back to huge dict sections (retail_sales / imported_products) and
    hitting Anthropic's 413 RequestTooLargeError.
    """

    def test_waybills_in_allowlist(self):
        assert "waybills" in ALLOWED_SECTIONS
        desc = ALLOWED_SECTIONS["waybills"]
        # Description should mention filtering by date so the LLM picks it up.
        assert "filter" in desc.lower()
        assert "date" in desc.lower()

    def test_waybills_has_column_profile(self):
        profile = SECTION_COLUMN_PROFILES.get("waybills")
        assert profile is not None
        # Core analytical fields that a user needs for daily queries.
        assert "date" in profile
        assert "supplier" in profile
        assert "effective_amount" in profile
        assert "nominal_amount" in profile

    def test_waybills_date_filter_substring(self):
        """`_match_filter` does substring match on strings; date filter works."""
        rows = [
            {"date": "2026-02-28 21:16:00", "supplier": "A", "effective_amount": 100.0},
            {"date": "2026-02-27 10:00:00", "supplier": "B", "effective_amount": 200.0},
            {"date": "2026-02-28 09:00:00", "supplier": "C", "effective_amount": 50.0},
        ]
        disp = ToolDispatcher(lambda: {"waybills": rows})
        result = disp.dispatch(
            "read_data_json",
            {"section": "waybills", "filter": {"date": "2026-02-28"}, "limit": 10},
        )
        assert "error" not in result
        assert result["filtered_count"] == 2
        returned_dates = [r["date"] for r in result["rows"]]
        assert all("2026-02-28" in d for d in returned_dates)


# ---------------------------------------------------------------------------
# _truncate_output dict safety rail (bug fix 2026-04-18 02:55)
# ---------------------------------------------------------------------------


class TestTruncateOutputDictSafety:
    """Prevent 413 RequestTooLargeError caused by huge dict sections
    (retail_sales = ~34 MB, imported_products = ~34 MB) being passed through
    `_apply_filter_and_limit` unchanged because `_truncate_output` only halved
    list rows and ignored dict values.
    """

    def test_small_dict_passes_through_unchanged(self):
        payload = {
            "value": {"a": 1, "b": 2, "c": "ok"},
            "row_count": 1,
            "total_count": 1,
            "truncated": False,
        }
        result = _truncate_output(payload)
        assert result == payload

    def test_large_dict_clamped_to_metadata(self):
        # Build a dict that definitely exceeds MAX_OUTPUT_CHARS when serialized.
        bloat = {
            f"key_{i:04d}": "x" * 200
            for i in range(500)
        }
        payload = {
            "value": bloat,
            "row_count": 1,
            "total_count": 1,
            "truncated": False,
            "section": "retail_sales",
        }
        result = _truncate_output(payload)
        # Value is dropped; metadata + reason are surfaced instead.
        assert result["value"] is None
        assert result["truncated"] is True
        assert "truncation_reason" in result
        assert str(MAX_OUTPUT_CHARS) in result["truncation_reason"] or \
            f"{MAX_OUTPUT_CHARS:,}" in result["truncation_reason"]
        meta = result.get("metadata")
        assert meta is not None
        assert meta["value_type"] == "dict"
        assert meta["key_count"] == 500
        assert isinstance(meta["top_level_keys"], list)

    def test_large_list_value_clamped_to_metadata(self):
        """Non-``rows`` list values (wrapped in ``value`` by _apply_filter_and_limit
        when the section isn't a top-level list) also get clamped."""
        big_list = ["x" * 100 for _ in range(500)]
        payload = {
            "value": big_list,
            "row_count": 1,
            "total_count": 1,
            "truncated": False,
        }
        result = _truncate_output(payload)
        assert result["value"] is None
        assert result["truncated"] is True
        meta = result.get("metadata", {})
        assert meta.get("value_type") == "list"
        assert meta.get("item_count") == 500

    def test_large_rows_payload_still_halved(self):
        """Sanity: list sections (has ``rows``) still use the row-halving
        strategy rather than the new dict safety rail."""
        big_rows = [{"k": "x" * 200, "i": i} for i in range(500)]
        payload = {
            "rows": big_rows,
            "row_count": len(big_rows),
            "total_count": len(big_rows),
            "truncated": False,
        }
        result = _truncate_output(payload)
        # rows still present (halved), not metadata-replaced.
        assert "rows" in result
        assert "value" not in result
        assert "metadata" not in result
        assert result["truncated"] is True
        assert result["row_count"] < len(big_rows)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
