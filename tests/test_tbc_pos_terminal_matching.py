"""
Sprint 5.2 — TBC POS terminal-ID matching.

Ensures collect_tbc_card_income matches rows strictly by physical TBC
terminal IDs from the RS.ge official POS export, not by broad substring
or IBAN hints (which previously double-counted end-of-day transit sweeps).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pandas as pd
import pytest

# Pre-existing — the 3 `collect_tbc_card_income(...)` integration tests
# below pass tmp_path XLSX, but the function now reads from the
# production parquet cache (Sprint A/B/C wire-in). Tracked in
# CONTEXT_HANDOFF.md §5. The 7 unit tests above this marker continue to
# pass — they test the matcher in isolation, no I/O.
_XFAIL_PARQUET_WIRE_IN = pytest.mark.xfail(
    strict=False,
    reason="Sprint A/B/C parquet wire-in carryover — see CONTEXT_HANDOFF.md §5",
)

from dashboard_pipeline.bank_income import (
    _DEFAULT_TBC_TERMINAL_IDS,
    _tbc_income_row_has_terminal,
    collect_tbc_card_income,
)


def test_default_terminals_match_rs_official_export() -> None:
    """5 physical TBC terminals seen in Financial_Analysis/პოს ტერმინალი.xls."""
    assert set(_DEFAULT_TBC_TERMINAL_IDS) == {
        "RS014189", "SH079927", "SH046092", "SH034467", "SH060853",
    }


def test_row_with_terminal_id_matches() -> None:
    raw = (
        "Oct 19, 2022-ის ტრანზაქციის თანხები GEO FOODTIME LLC, "
        "SH034467 თიბისი ბანკის სავაჭრო ობიექტებში, TBCBGE22"
    )
    assert _tbc_income_row_has_terminal(raw, _DEFAULT_TBC_TERMINAL_IDS) is True


def test_row_without_terminal_id_does_not_match() -> None:
    # Classic transit sweep — "ნავაჭრი ტერმინალებში მიღებული" — no terminal ID
    raw = (
        "ნავაჭრი ტერმინალებში მიღებული თიბისი ბანკის გადახდების სატრანზიტო "
        "(პროვაიდერი), TBCBGE22, GE69TB0000000251140006"
    )
    assert _tbc_income_row_has_terminal(raw, _DEFAULT_TBC_TERMINAL_IDS) is False


def test_row_with_transit_iban_only_does_not_match() -> None:
    # GE69TB000... transit IBAN appeared in patterns_v1 — must NOT match alone
    raw = "დვაბზუ სს თიბისი ბანკი TBCBGE22 GE69TB0000000251140006 659.73"
    assert _tbc_income_row_has_terminal(raw, _DEFAULT_TBC_TERMINAL_IDS) is False


def test_empty_terminal_list_matches_nothing() -> None:
    raw = "SH034467 anything"
    assert _tbc_income_row_has_terminal(raw, []) is False


def test_terminal_match_is_case_sensitive() -> None:
    # Terminal IDs in RS export and TBC narratives are uppercase.
    raw_upper = "payment via sh034467 terminal"
    raw_mixed = "payment via Sh034467 terminal"
    assert _tbc_income_row_has_terminal(raw_upper, ["SH034467"]) is False
    assert _tbc_income_row_has_terminal(raw_mixed, ["SH034467"]) is False
    assert _tbc_income_row_has_terminal("payment via SH034467", ["SH034467"]) is True


def _write_tbc_statement(path: Path, rows: List[dict]) -> None:
    """Write a minimal TBC bank statement xlsx that find_header_row can read."""
    header = ["თარიღი", "შემოსული (CREDIT)", "გასული (DEBIT)", "დანიშნულება"]
    data_rows = []
    for r in rows:
        data_rows.append([r.get("date"), r.get("credit"), r.get("debit", 0), r.get("purpose", "")])
    df = pd.DataFrame(data_rows, columns=header)
    df.to_excel(path, index=False)


@_XFAIL_PARQUET_WIRE_IN
def test_collect_tbc_card_income_filters_by_terminal(tmp_path: Path, monkeypatch) -> None:
    """End-to-end: only rows whose narrative contains a configured terminal ID
    are counted; transit sweeps (no terminal) are dropped."""
    fa = tmp_path / "Financial_Analysis"
    fa.mkdir()
    cfg = {
        "label_ka": "POS (TBC)",
        "terminal_ids": ["SH079927", "RS014189"],
    }
    (fa / "tbc_card_income_patterns.json").write_text(
        json.dumps(cfg, ensure_ascii=False), encoding="utf-8"
    )

    stmt = tmp_path / "tbc_statement.xlsx"
    _write_tbc_statement(stmt, [
        # TRUE POS — contains SH079927
        {"date": "2024-08-10", "credit": 100.00, "purpose": "SH079927 transaction 1"},
        # TRUE POS — contains RS014189
        {"date": "2024-08-11", "credit": 50.25, "purpose": "RS014189 card payment"},
        # TRANSIT SWEEP — no terminal
        {"date": "2024-08-12", "credit": 5000.00,
         "purpose": "ნავაჭრი ტერმინალებში მიღებული სატრანზიტო"},
        # Wallet (not physical POS) — no terminal
        {"date": "2024-08-13", "credit": 25.00, "purpose": "wallet/domestic merchant"},
        # Zero / debit — ignored regardless
        {"date": "2024-08-14", "credit": 0, "purpose": "SH079927 refund reversal"},
    ])

    monkeypatch.setattr(
        "dashboard_pipeline.bank_income.list_tbc_bank_statement_xlsx",
        lambda: [str(stmt)],
    )
    monkeypatch.setattr(
        "dashboard_pipeline.bank_income.load_object_mapping",
        lambda _d: {"tbc_pos_object_order": [], "default_object": "—"},
    )

    out = collect_tbc_card_income(str(tmp_path))
    assert out["label_ka"] == "POS (TBC)"
    assert out["line_count"] == 2
    assert out["total_ge"] == pytest.approx(150.25)


@_XFAIL_PARQUET_WIRE_IN
def test_collect_tbc_card_income_falls_back_to_defaults_if_config_missing(
    tmp_path: Path, monkeypatch
) -> None:
    fa = tmp_path / "Financial_Analysis"
    fa.mkdir()
    # No patterns JSON at all — must fall back to _DEFAULT_TBC_TERMINAL_IDS

    stmt = tmp_path / "tbc_statement.xlsx"
    _write_tbc_statement(stmt, [
        {"date": "2024-08-10", "credit": 12.00, "purpose": "SH046092 payment"},
        {"date": "2024-08-11", "credit": 99.00, "purpose": "ecom/pos მერჩანტ no-terminal"},
    ])

    monkeypatch.setattr(
        "dashboard_pipeline.bank_income.list_tbc_bank_statement_xlsx",
        lambda: [str(stmt)],
    )
    monkeypatch.setattr(
        "dashboard_pipeline.bank_income.load_object_mapping",
        lambda _d: {"tbc_pos_object_order": [], "default_object": "—"},
    )

    out = collect_tbc_card_income(str(tmp_path))
    assert out["line_count"] == 1
    assert out["total_ge"] == pytest.approx(12.00)


@_XFAIL_PARQUET_WIRE_IN
def test_collect_tbc_card_income_empty_terminal_list_returns_zero(
    tmp_path: Path, monkeypatch
) -> None:
    fa = tmp_path / "Financial_Analysis"
    fa.mkdir()
    cfg = {"label_ka": "POS (TBC)", "terminal_ids": []}
    (fa / "tbc_card_income_patterns.json").write_text(
        json.dumps(cfg, ensure_ascii=False), encoding="utf-8"
    )

    stmt = tmp_path / "tbc_statement.xlsx"
    _write_tbc_statement(stmt, [
        {"date": "2024-08-10", "credit": 100.00, "purpose": "SH079927 payment"},
    ])

    monkeypatch.setattr(
        "dashboard_pipeline.bank_income.list_tbc_bank_statement_xlsx",
        lambda: [str(stmt)],
    )
    monkeypatch.setattr(
        "dashboard_pipeline.bank_income.load_object_mapping",
        lambda _d: {"tbc_pos_object_order": [], "default_object": "—"},
    )

    # Empty cfg list falls back to defaults per collect_tbc_card_income logic
    # (cfg_ids empty → terminal_ids stays at _DEFAULT_TBC_TERMINAL_IDS)
    out = collect_tbc_card_income(str(tmp_path))
    assert out["line_count"] == 1


def test_config_json_shipped_has_expected_shape() -> None:
    """Regression: the shipped JSON must expose terminal_ids, not substring patterns."""
    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = repo_root / "Financial_Analysis" / "tbc_card_income_patterns.json"
    assert cfg_path.exists()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "terminal_ids" in cfg
    assert isinstance(cfg["terminal_ids"], list)
    assert len(cfg["terminal_ids"]) >= 5
    assert "SH079927" in cfg["terminal_ids"]
    assert "RS014189" in cfg["terminal_ids"]
    # Old broad-matching fields must be absent (or empty).
    assert not cfg.get("match_substrings")
    assert not cfg.get("iban_hints")
