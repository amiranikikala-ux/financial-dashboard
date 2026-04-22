"""Unit tests for Phase 2 Investigator tools in dashboard_pipeline.ai.tools.

Covers:
- Path allowlist + traversal prevention for both data and code roots.
- `read_source_code`: line_range, max cap, allowlist, absolute/traversal reject.
- `grep_code`: regex, max_hits, path restriction, invalid regex.
- `read_excel_source`: csv/xlsx, sheet, nrows cap, unicode subdirs, allowlist.
- `validate_vs_source`: row count + total comparison, source hint, error paths.
- `TOOL_SCHEMAS` extended with 4 new tools; cache_control stays on last only.
- `ToolDispatcher` routes every new investigator tool; original tool keeps working.

All file-system tests use a synthetic fake project under ``tmp_path`` so the
real 30 MB Excel/CSV sources are never read. Unicode directory names are
exercised to catch encoding regressions on Windows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

from dashboard_pipeline.ai.tools import (
    ALLOWED_CODE_ROOTS,
    ALLOWED_DATA_ROOTS,
    INVESTIGATOR_TOOL_NAMES,
    MAX_EXCEL_NROWS,
    MAX_GREP_HITS,
    MAX_SOURCE_LINES,
    TOOL_SCHEMAS,
    ToolDispatcher,
    _resolve_safe_path,
    get_cached_tool_schemas,
    grep_code,
    read_excel_source,
    read_source_code,
    validate_vs_source,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    """Build a minimal, allowlist-matching project tree under tmp_path."""
    # ---- Financial_Analysis/ ----
    fa = tmp_path / "Financial_Analysis"
    fa.mkdir()
    (fa / "test.csv").write_text(
        "month,revenue,cost\n2025-01,1000,600\n2025-02,1200,700\n",
        encoding="utf-8",
    )
    pd.DataFrame({"month": ["2025-01", "2025-02"], "revenue": [1000, 1200]}).to_excel(
        fa / "test.xlsx", index=False
    )

    # Unicode subdir mimicking real layout ("რს ზედნადები", etc.)
    sub = fa / "რს ზედნადები"
    sub.mkdir()
    pd.DataFrame({"date": ["2025-01-15"], "amount": [500]}).to_excel(
        sub / "2025.xlsx", index=False
    )

    # ---- Code roots ----
    dp = tmp_path / "dashboard_pipeline"
    dp.mkdir()
    (dp / "__init__.py").write_text("", encoding="utf-8")
    # Deterministic content for grep + line_range tests.
    # Line numbering (1-indexed):
    # 1: import pandas as pd
    # 2: (blank)
    # 3: MAGIC_CONSTANT = 42
    # 4: (blank)
    # 5: def hello():
    # 6:     return 'world'
    # 7: (blank)
    # 8: def second_func():
    # 9:     return MAGIC_CONSTANT
    (dp / "pipeline_mod.py").write_text(
        "import pandas as pd\n"
        "\n"
        "MAGIC_CONSTANT = 42\n"
        "\n"
        "def hello():\n"
        "    return 'world'\n"
        "\n"
        "def second_func():\n"
        "    return MAGIC_CONSTANT\n",
        encoding="utf-8",
    )

    rs_src = tmp_path / "rs-dashboard" / "src"
    rs_src.mkdir(parents=True)
    (rs_src / "App.jsx").write_text(
        "import React from 'react';\n"
        "export default function App() {\n"
        "  return <div>MAGIC_CONSTANT ref</div>;\n"
        "}\n",
        encoding="utf-8",
    )

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text(
        "def test_one():\n    assert True\n", encoding="utf-8"
    )

    (tmp_path / "server.py").write_text(
        "# fake server\nAPP_NAME = 'dashboard'\n", encoding="utf-8"
    )
    (tmp_path / "generate_dashboard_data.py").write_text(
        "# fake generator\n", encoding="utf-8"
    )
    (tmp_path / "backend_paths.py").write_text(
        "# fake backend paths\n", encoding="utf-8"
    )

    # ---- Paths that MUST be rejected ----
    (tmp_path / ".env").write_text("SECRET=foo\n", encoding="utf-8")
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "creds.txt").write_text("pwd=123\n", encoding="utf-8")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "mod.js").write_text("// vendored\n", encoding="utf-8")

    return tmp_path


@pytest.fixture
def sample_data() -> Dict[str, Any]:
    return {
        "meta": {"data_period_label": "2025-01 – 2025-03"},
        "suppliers": [
            {"tax_id": "1", "total_effective": 1000, "total_debt": 0},
            {"tax_id": "2", "total_effective": 2000, "total_debt": 500},
            {"tax_id": "3", "total_effective": 3000, "total_debt": 0},
        ],
        "monthly_pnl": [
            {"month": "2025-01", "revenue": 10000, "net": 500},
            {"month": "2025-02", "revenue": 12000, "net": 800},
        ],
        "financial_ratios": {"current_ratio": 1.5},
    }


@pytest.fixture
def sample_loader(sample_data):
    def _loader() -> Dict[str, Any]:
        return sample_data

    return _loader


# ---------------------------------------------------------------------------
# Allowed-roots contract
# ---------------------------------------------------------------------------


class TestAllowedRootsContract:
    def test_data_roots_contain_financial_analysis(self):
        assert "Financial_Analysis" in ALLOWED_DATA_ROOTS

    def test_code_roots_contain_expected_entries(self):
        for expected in (
            "dashboard_pipeline",
            "rs-dashboard/src",
            "tests",
            "server.py",
            "generate_dashboard_data.py",
            "backend_paths.py",
        ):
            assert expected in ALLOWED_CODE_ROOTS, (
                f"{expected!r} missing from ALLOWED_CODE_ROOTS"
            )

    def test_sensitive_paths_not_allowlisted(self):
        for root in ALLOWED_CODE_ROOTS + ALLOWED_DATA_ROOTS:
            assert not root.startswith(".env"), (
                f"{root!r} in allowlist — secrets must never be exposed"
            )
            assert "secret" not in root.lower()
            assert "node_modules" not in root


# ---------------------------------------------------------------------------
# read_source_code
# ---------------------------------------------------------------------------


class TestReadSourceCode:
    def test_reads_pipeline_file(self, fake_project):
        result = read_source_code(
            "dashboard_pipeline/pipeline_mod.py", project_root=fake_project
        )
        assert "error" not in result
        assert "MAGIC_CONSTANT = 42" in result["source"]
        assert result["file_path"] == "dashboard_pipeline/pipeline_mod.py"
        assert result["line_start"] == 1
        assert result["total_lines"] >= 9

    def test_reads_server_py_exact_file(self, fake_project):
        result = read_source_code("server.py", project_root=fake_project)
        assert "error" not in result
        assert "APP_NAME" in result["source"]

    def test_reads_rs_dashboard_jsx(self, fake_project):
        result = read_source_code(
            "rs-dashboard/src/App.jsx", project_root=fake_project
        )
        assert "error" not in result
        assert "React" in result["source"]

    def test_line_range_partial_slice(self, fake_project):
        # Lines 5–6 in the fixture are `def hello():` and `    return 'world'`.
        result = read_source_code(
            "dashboard_pipeline/pipeline_mod.py",
            line_range={"start": 5, "end": 6},
            project_root=fake_project,
        )
        assert result["line_start"] == 5
        assert result["line_end"] == 6
        assert "def hello" in result["source"]
        assert "return 'world'" in result["source"]
        # Line 3 (MAGIC_CONSTANT) is OUTSIDE the range — must not leak in.
        assert "MAGIC_CONSTANT = 42" not in result["source"]

    def test_rejects_env_file(self, fake_project):
        result = read_source_code(".env", project_root=fake_project)
        assert "error" in result

    def test_rejects_secrets_dir(self, fake_project):
        result = read_source_code(
            "secrets/creds.txt", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_node_modules(self, fake_project):
        result = read_source_code(
            "node_modules/mod.js", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_path_traversal(self, fake_project):
        result = read_source_code(
            "../../../etc/passwd", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_absolute_path(self, fake_project):
        result = read_source_code(
            "C:/Windows/System32/cmd.exe", project_root=fake_project
        )
        assert "error" in result

    def test_file_not_found(self, fake_project):
        result = read_source_code(
            "dashboard_pipeline/missing.py", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_non_code_extension_in_code_root(self, fake_project):
        """A binary/unknown file under a code root must be rejected."""
        (fake_project / "dashboard_pipeline" / "blob.bin").write_bytes(b"\x00\x01\x02")
        result = read_source_code(
            "dashboard_pipeline/blob.bin", project_root=fake_project
        )
        assert "error" in result

    def test_source_lines_cap_enforced(self, fake_project):
        big = fake_project / "dashboard_pipeline" / "big.py"
        big.write_text(
            "\n".join(f"line_{i}" for i in range(1, 3 * MAX_SOURCE_LINES + 1)),
            encoding="utf-8",
        )
        result = read_source_code(
            "dashboard_pipeline/big.py",
            line_range={"start": 1, "end": 3 * MAX_SOURCE_LINES},
            project_root=fake_project,
        )
        # Slice must be capped
        assert result["line_end"] - result["line_start"] + 1 <= MAX_SOURCE_LINES
        assert result["truncated"] is True

    def test_default_line_range_bounded(self, fake_project):
        big = fake_project / "dashboard_pipeline" / "med.py"
        big.write_text(
            "\n".join(f"line_{i}" for i in range(1, 2 * MAX_SOURCE_LINES + 1)),
            encoding="utf-8",
        )
        result = read_source_code(
            "dashboard_pipeline/med.py", project_root=fake_project
        )
        assert result["line_start"] == 1
        assert result["line_end"] <= MAX_SOURCE_LINES

    def test_empty_file_path_rejected(self, fake_project):
        assert "error" in read_source_code("", project_root=fake_project)
        assert "error" in read_source_code(None, project_root=fake_project)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# grep_code
# ---------------------------------------------------------------------------


class TestGrepCode:
    def test_basic_match_across_roots(self, fake_project):
        result = grep_code("MAGIC_CONSTANT", project_root=fake_project)
        assert "error" not in result
        assert result["total_hits"] >= 2
        paths = {hit["file_path"].replace("\\", "/") for hit in result["hits"]}
        assert any("pipeline_mod.py" in p for p in paths)
        assert any("App.jsx" in p for p in paths)

    def test_returns_line_numbers(self, fake_project):
        result = grep_code("MAGIC_CONSTANT", project_root=fake_project)
        for hit in result["hits"]:
            assert isinstance(hit["line_number"], int)
            assert hit["line_number"] >= 1
            assert "MAGIC_CONSTANT" in hit["line"]

    def test_path_restriction_to_subdir(self, fake_project):
        result = grep_code(
            "MAGIC_CONSTANT",
            path="rs-dashboard/src",
            project_root=fake_project,
        )
        assert "error" not in result
        paths = {hit["file_path"].replace("\\", "/") for hit in result["hits"]}
        assert paths  # at least one hit
        assert all(p.startswith("rs-dashboard/src") for p in paths)

    def test_max_hits_cap(self, fake_project):
        manyline = "\n".join(f"pattern_match_{i}" for i in range(200))
        (fake_project / "dashboard_pipeline" / "many.py").write_text(
            manyline, encoding="utf-8"
        )
        result = grep_code(
            "pattern_match_", max_hits=10, project_root=fake_project
        )
        assert len(result["hits"]) <= 10
        assert result["truncated"] is True

    def test_max_hits_clamped_to_ceiling(self, fake_project):
        result = grep_code(
            "hello", max_hits=9999, project_root=fake_project
        )
        assert "error" not in result
        assert result["max_hits"] <= MAX_GREP_HITS

    def test_invalid_regex_returns_error(self, fake_project):
        result = grep_code("[unclosed", project_root=fake_project)
        assert "error" in result

    def test_empty_pattern_rejected(self, fake_project):
        assert "error" in grep_code("", project_root=fake_project)

    def test_rejects_env_scope(self, fake_project):
        result = grep_code(
            "SECRET", path=".env", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_node_modules_scope(self, fake_project):
        result = grep_code(
            "vendored", path="node_modules", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_traversal_path(self, fake_project):
        result = grep_code(
            "anything", path="../..", project_root=fake_project
        )
        assert "error" in result

    def test_no_hits_returns_empty_list(self, fake_project):
        result = grep_code(
            "zzzz_definitely_not_found_zzzz", project_root=fake_project
        )
        assert result["hits"] == []
        assert result["total_hits"] == 0
        assert result["truncated"] is False


# ---------------------------------------------------------------------------
# read_excel_source
# ---------------------------------------------------------------------------


class TestReadExcelSource:
    def test_read_csv(self, fake_project):
        result = read_excel_source(
            "Financial_Analysis/test.csv", project_root=fake_project
        )
        assert "error" not in result
        assert result["source_type"] == "csv"
        assert "month" in result["columns"]
        assert len(result["rows"]) == 2

    def test_read_xlsx(self, fake_project):
        result = read_excel_source(
            "Financial_Analysis/test.xlsx", project_root=fake_project
        )
        assert "error" not in result
        assert result["source_type"] == "xlsx"
        assert "month" in result["columns"]
        assert len(result["rows"]) == 2

    def test_read_xlsx_in_georgian_subdir(self, fake_project):
        result = read_excel_source(
            "Financial_Analysis/რს ზედნადები/2025.xlsx",
            project_root=fake_project,
        )
        assert "error" not in result
        assert result["source_type"] == "xlsx"
        assert len(result["rows"]) == 1

    def test_nrows_request_capped(self, fake_project):
        rows = ["a,b"] + [f"{i},{i * 2}" for i in range(500)]
        (fake_project / "Financial_Analysis" / "big.csv").write_text(
            "\n".join(rows), encoding="utf-8"
        )
        result = read_excel_source(
            "Financial_Analysis/big.csv",
            nrows=10000,
            project_root=fake_project,
        )
        assert len(result["rows"]) <= MAX_EXCEL_NROWS

    def test_default_nrows_small(self, fake_project):
        rows = ["a,b"] + [f"{i},{i * 2}" for i in range(100)]
        (fake_project / "Financial_Analysis" / "med.csv").write_text(
            "\n".join(rows), encoding="utf-8"
        )
        result = read_excel_source(
            "Financial_Analysis/med.csv", project_root=fake_project
        )
        assert len(result["rows"]) <= 20

    def test_rejects_outside_financial_analysis(self, fake_project):
        result = read_excel_source(
            "dashboard_pipeline/pipeline_mod.py", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_traversal(self, fake_project):
        result = read_excel_source(
            "../etc/passwd", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_absolute_path(self, fake_project):
        result = read_excel_source(
            "C:/Windows/System32/cmd.exe", project_root=fake_project
        )
        assert "error" in result

    def test_file_not_found(self, fake_project):
        result = read_excel_source(
            "Financial_Analysis/missing.csv", project_root=fake_project
        )
        assert "error" in result

    def test_rejects_unsupported_extension(self, fake_project):
        (fake_project / "Financial_Analysis" / "notes.txt").write_text(
            "hello", encoding="utf-8"
        )
        result = read_excel_source(
            "Financial_Analysis/notes.txt", project_root=fake_project
        )
        assert "error" in result

    def test_rows_are_json_serializable(self, fake_project):
        result = read_excel_source(
            "Financial_Analysis/test.csv", project_root=fake_project
        )
        json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# validate_vs_source
# ---------------------------------------------------------------------------


class TestValidateVsSource:
    def test_returns_current_row_count(self, sample_loader):
        result = validate_vs_source("suppliers", data_loader=sample_loader)
        assert "error" not in result
        assert result["current_row_count"] == 3
        assert result["section"] == "suppliers"

    def test_row_count_match(self, sample_loader):
        result = validate_vs_source(
            "suppliers",
            expected_row_count=3,
            data_loader=sample_loader,
        )
        assert result["row_count_match"] is True
        assert result["status"] == "match"

    def test_row_count_mismatch(self, sample_loader):
        result = validate_vs_source(
            "suppliers",
            expected_row_count=5,
            data_loader=sample_loader,
        )
        assert result["row_count_match"] is False
        assert result["status"] == "mismatch"
        assert result["row_count_delta"] == 5 - 3  # expected − actual

    def test_unknown_section(self, sample_loader):
        result = validate_vs_source(
            "nonexistent_section", data_loader=sample_loader
        )
        assert "error" in result

    def test_dict_section_uses_one(self, sample_loader):
        result = validate_vs_source(
            "financial_ratios",
            expected_row_count=1,
            data_loader=sample_loader,
        )
        assert result["current_row_count"] == 1

    def test_source_hint_provided(self, sample_loader):
        result = validate_vs_source("suppliers", data_loader=sample_loader)
        assert "source_hint" in result
        assert isinstance(result["source_hint"], str)

    def test_total_compare_match(self, sample_loader):
        # sum(total_effective) = 1000 + 2000 + 3000 = 6000
        result = validate_vs_source(
            "suppliers",
            expected_total=6000,
            field_name="total_effective",
            data_loader=sample_loader,
        )
        assert result["total_match"] is True
        assert abs(result["current_total"] - 6000) < 0.01

    def test_total_compare_mismatch(self, sample_loader):
        result = validate_vs_source(
            "suppliers",
            expected_total=7000,
            field_name="total_effective",
            data_loader=sample_loader,
        )
        assert result["total_match"] is False
        assert result["status"] == "mismatch"

    def test_total_requested_without_field_name(self, sample_loader):
        result = validate_vs_source(
            "suppliers",
            expected_total=6000,
            data_loader=sample_loader,
        )
        assert "error" in result

    def test_no_expected_values_is_inspection_only(self, sample_loader):
        result = validate_vs_source("suppliers", data_loader=sample_loader)
        assert result["status"] == "inspected"
        assert "row_count_match" not in result
        assert "total_match" not in result


# ---------------------------------------------------------------------------
# Extended TOOL_SCHEMAS
# ---------------------------------------------------------------------------


class TestExtendedToolSchemas:
    def test_all_tools_exposed(self):
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "read_data_json" in names
        assert "compute_waybill_total" in names
        assert "compute" in names
        assert "forecast_revenue" in names
        assert "recall_context" in names
        assert "save_memory" in names
        assert "read_source_code" in names
        assert "grep_code" in names
        assert "read_excel_source" in names
        assert "validate_vs_source" in names
        # 10 = read_data_json, compute_waybill_total, compute,
        #      forecast_revenue, recall_context, save_memory,
        #      read_source_code, grep_code, read_excel_source,
        #      validate_vs_source.
        # (forecast_revenue added in Phase 0B Sprint 2;
        #  recall_context + save_memory added in Phase 0B Sprint 3;
        #  journal_add_entry / journal_list_entries / journal_update_entry
        #  added in Phase 0B Sprint 4 → 13; analyze_dead_stock added in
        #  Phase 2.11 → 14; prepare_supplier_brief added in Phase 2.12 →
        #  15; propose_feature added in Phase 3.1 → 16;
        #  compute_cash_runway added in Phase 3.5 → 17;
        #  build_debt_repayment_plan added in Phase 4A → 18;
        #  compute_cash_flow_projection added in Phase 2.1 → 19.)
        assert len(TOOL_SCHEMAS) == 19

    def test_investigator_tool_names_set(self):
        assert set(INVESTIGATOR_TOOL_NAMES) == {
            "read_source_code",
            "grep_code",
            "read_excel_source",
            "validate_vs_source",
        }

    def test_cache_control_only_on_last(self):
        cached = get_cached_tool_schemas()
        assert cached[-1]["cache_control"] == {"type": "ephemeral"}
        for tool in cached[:-1]:
            assert "cache_control" not in tool

    def test_module_constant_stays_cache_control_free(self):
        """`TOOL_SCHEMAS` itself must never carry cache_control."""
        _ = get_cached_tool_schemas()
        for tool in TOOL_SCHEMAS:
            assert "cache_control" not in tool

    def test_schemas_json_serializable(self):
        json.dumps(TOOL_SCHEMAS, ensure_ascii=False)

    def test_read_source_code_schema_shape(self):
        tool = next(t for t in TOOL_SCHEMAS if t["name"] == "read_source_code")
        props = tool["input_schema"]["properties"]
        assert "file_path" in props
        assert "line_range" in props
        assert tool["input_schema"]["required"] == ["file_path"]

    def test_grep_code_schema_shape(self):
        tool = next(t for t in TOOL_SCHEMAS if t["name"] == "grep_code")
        props = tool["input_schema"]["properties"]
        assert "pattern" in props
        assert "path" in props
        assert "max_hits" in props
        assert tool["input_schema"]["required"] == ["pattern"]

    def test_read_excel_source_schema_shape(self):
        tool = next(t for t in TOOL_SCHEMAS if t["name"] == "read_excel_source")
        props = tool["input_schema"]["properties"]
        assert "file_path" in props
        assert "sheet" in props
        assert "nrows" in props
        assert tool["input_schema"]["required"] == ["file_path"]

    def test_validate_vs_source_schema_shape(self):
        tool = next(
            t for t in TOOL_SCHEMAS if t["name"] == "validate_vs_source"
        )
        props = tool["input_schema"]["properties"]
        assert "section" in props
        assert "expected_row_count" in props
        assert "expected_total" in props
        assert "field_name" in props
        assert tool["input_schema"]["required"] == ["section"]


# ---------------------------------------------------------------------------
# Dispatcher routing
# ---------------------------------------------------------------------------


class TestDispatcherInvestigator:
    def test_dispatch_read_source_code(self, fake_project, sample_loader):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        result = disp.dispatch(
            "read_source_code",
            {"file_path": "dashboard_pipeline/pipeline_mod.py"},
        )
        assert "error" not in result
        assert "MAGIC_CONSTANT" in result["source"]
        assert disp.calls[-1]["tool"] == "read_source_code"

    def test_dispatch_grep_code(self, fake_project, sample_loader):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        result = disp.dispatch("grep_code", {"pattern": "MAGIC_CONSTANT"})
        assert "error" not in result
        assert result["total_hits"] >= 2

    def test_dispatch_read_excel_source(self, fake_project, sample_loader):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        result = disp.dispatch(
            "read_excel_source",
            {"file_path": "Financial_Analysis/test.csv"},
        )
        assert "error" not in result
        assert result["source_type"] == "csv"

    def test_dispatch_validate_vs_source(self, fake_project, sample_loader):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        result = disp.dispatch(
            "validate_vs_source",
            {"section": "suppliers", "expected_row_count": 3},
        )
        assert "error" not in result
        assert result["row_count_match"] is True

    def test_dispatch_read_data_json_still_works(
        self, fake_project, sample_loader
    ):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        result = disp.dispatch("read_data_json", {"section": "meta"})
        assert "error" not in result
        assert "value" in result

    def test_dispatcher_without_project_root_falls_back_to_default(
        self, sample_loader
    ):
        """Old callers (no project_root kwarg) must still construct."""
        disp = ToolDispatcher(sample_loader)
        assert disp.calls == []

    def test_unknown_tool_errors(self, fake_project, sample_loader):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        result = disp.dispatch("format_drive", {})
        assert "error" in result

    def test_call_trace_captures_investigator_result_summary(
        self, fake_project, sample_loader
    ):
        disp = ToolDispatcher(sample_loader, project_root=fake_project)
        disp.dispatch(
            "read_source_code",
            {"file_path": "dashboard_pipeline/pipeline_mod.py"},
        )
        summary = disp.calls[-1]["result_summary"]
        assert summary["ok"] is True
        assert summary.get("tool") == "read_source_code" or "tool" not in summary


# ---------------------------------------------------------------------------
# _resolve_safe_path regression — OneDrive + non-ASCII ancestor + traversal
# ---------------------------------------------------------------------------


class TestResolveSafePathRegression:
    """Regression tests for the OneDrive + Georgian-folder bug.

    Background: on Windows + OneDrive, ``Path.resolve(strict=False)`` follows
    OS-level junctions / reparse points. When the project root sits under an
    ancestor with non-ASCII characters (e.g. ``AI აგენტი``), ``resolve`` could
    silently relocate certain Georgian subfolder paths outside ``project_root``.
    The fix replaced ``.resolve()`` with ``.absolute()`` and added an explicit
    ``..`` segment rejection. These tests pin both halves of the contract.
    """

    def test_rejects_dotdot_at_start(self, fake_project):
        assert (
            _resolve_safe_path(
                "../etc/passwd", ALLOWED_DATA_ROOTS, fake_project
            )
            is None
        )

    def test_rejects_dotdot_in_middle_segment(self, fake_project):
        # ``Financial_Analysis`` is allowlisted, but the embedded ``..`` must
        # still escape the allowlist intent — explicit reject required since
        # we no longer rely on ``Path.resolve`` to canonicalise this away.
        assert (
            _resolve_safe_path(
                "Financial_Analysis/../etc/passwd",
                ALLOWED_DATA_ROOTS,
                fake_project,
            )
            is None
        )

    def test_rejects_dotdot_inside_subdir(self, fake_project):
        assert (
            _resolve_safe_path(
                "Financial_Analysis/რს ზედნადები/../../../etc/passwd",
                ALLOWED_DATA_ROOTS,
                fake_project,
            )
            is None
        )

    def test_rejects_backslash_dotdot_segment(self, fake_project):
        # ``\..\`` must be rejected the same way as ``/../`` after normalization.
        assert (
            _resolve_safe_path(
                "Financial_Analysis\\..\\etc\\passwd",
                ALLOWED_DATA_ROOTS,
                fake_project,
            )
            is None
        )

    def test_normal_paths_still_resolve(self, fake_project):
        resolved = _resolve_safe_path(
            "Financial_Analysis/test.csv", ALLOWED_DATA_ROOTS, fake_project
        )
        assert resolved is not None
        assert resolved.name == "test.csv"

    def test_works_under_non_ascii_ancestor(self, tmp_path):
        """Reproduces the OneDrive scenario: project root has a non-ASCII parent.

        Before the fix, ``Path.resolve(strict=False)`` could return a path
        that escaped ``project_root`` for some Georgian subfolders even though
        the file legitimately existed. The new implementation uses
        ``Path.absolute()`` (lexical join + drive normalisation) so non-ASCII
        ancestors no longer matter.
        """
        non_ascii_parent = tmp_path / "AI აგენტი"
        non_ascii_parent.mkdir()
        project_root = non_ascii_parent / "financial-dashboard"
        project_root.mkdir()
        fa = project_root / "Financial_Analysis"
        fa.mkdir()
        georgian_subdir = fa / "ბოგ ბანკი ამონაწერი"
        georgian_subdir.mkdir()
        target = georgian_subdir / "02--2026.xlsx"
        target.write_bytes(b"fake xlsx payload")

        resolved = _resolve_safe_path(
            "Financial_Analysis/ბოგ ბანკი ამონაწერი/02--2026.xlsx",
            ALLOWED_DATA_ROOTS,
            project_root,
        )

        assert resolved is not None, (
            "Georgian subfolder under non-ASCII ancestor must resolve "
            "successfully (regression: OneDrive + non-ASCII path bug)"
        )
        assert resolved.name == "02--2026.xlsx"
        assert resolved.exists()

    def test_backslash_form_under_non_ascii_ancestor(self, tmp_path):
        """The Anthropic agent sometimes emits Windows-style backslashes."""
        non_ascii_parent = tmp_path / "AI აგენტი"
        non_ascii_parent.mkdir()
        project_root = non_ascii_parent / "financial-dashboard"
        project_root.mkdir()
        fa = project_root / "Financial_Analysis"
        fa.mkdir()
        sub = fa / "თბს ბანკი ამონაწერი"
        sub.mkdir()
        target = sub / "2024.xlsx"
        target.write_bytes(b"fake xlsx payload")

        resolved = _resolve_safe_path(
            "Financial_Analysis\\თბს ბანკი ამონაწერი\\2024.xlsx",
            ALLOWED_DATA_ROOTS,
            project_root,
        )

        assert resolved is not None
        assert resolved.name == "2024.xlsx"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
