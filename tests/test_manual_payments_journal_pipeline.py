"""Pipeline integration — journal entries flow into supplier_payment_lines.

Pins the contract: every active journal entry shows up as one row in the
supplier's payment list with ``source='manual'`` and a passthrough ``id``
so the UI can render a per-row 🗑 delete button.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dashboard_pipeline import manual_payments_journal as mpj
from dashboard_pipeline.bank_reconciliation import build_supplier_payment_lines
from dashboard_pipeline import manual_payments


@pytest.fixture
def isolated_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    journal = tmp_path / "manual_payments_journal.csv"
    legacy_csv = tmp_path / "manual_payments.csv"
    legacy_csv.write_text("tax_id,company,row_date,amount,comment\n", encoding="utf-8-sig")
    monkeypatch.setattr(mpj, "journal_csv_path", lambda: str(journal))
    monkeypatch.setattr(manual_payments, "manual_payments_csv_path", lambda: str(legacy_csv))
    yield journal


def test_journal_entries_surface_in_payment_lines(isolated_journal: Path):
    e1 = mpj.append_entry(tax_id="406181616", amount=72972.50, date="2026-05-07", comment="ჯიდიაი")
    e2 = mpj.append_entry(tax_id="406181616", amount=5000.00, date="2026-05-06", comment="ცდა")

    manual_rows = manual_payments.load_manual_payment_rows()
    lines = build_supplier_payment_lines([], manual_rows)

    assert "406181616" in lines
    journal_lines = [l for l in lines["406181616"] if l.get("source") == "manual"]
    assert len(journal_lines) == 2
    ids = {l["id"] for l in journal_lines}
    assert ids == {e1["id"], e2["id"]}
    amounts = {l["amount"] for l in journal_lines}
    assert amounts == {72972.50, 5000.00}


def test_deleted_entries_do_not_surface(isolated_journal: Path):
    e1 = mpj.append_entry(tax_id="111", amount=100, path=str(isolated_journal))
    e2 = mpj.append_entry(tax_id="111", amount=200, path=str(isolated_journal))
    mpj.soft_delete_entry(e1["id"], path=str(isolated_journal))

    manual_rows = manual_payments.load_manual_payment_rows()
    lines = build_supplier_payment_lines([], manual_rows)

    journal_lines = [l for l in lines.get("111", []) if l.get("source") == "manual"]
    journal_ids = {l.get("id") for l in journal_lines if l.get("id")}
    assert e1["id"] not in journal_ids
    assert e2["id"] in journal_ids


def test_payment_lines_include_id_for_journal_only(isolated_journal: Path):
    mpj.append_entry(tax_id="111", amount=100, path=str(isolated_journal))

    bank_row = {
        "matched_tax_id": "111",
        "amount": 50.0,
        "row_date": "2026-05-01",
        "source_bank": "TBC",
        "raw_purpose": "purchase",
    }
    manual_rows = manual_payments.load_manual_payment_rows()
    lines = build_supplier_payment_lines([bank_row], manual_rows)

    bank_lines = [l for l in lines["111"] if l["source"] != "manual"]
    manual_lines = [l for l in lines["111"] if l["source"] == "manual"]

    assert len(bank_lines) == 1
    assert "id" not in bank_lines[0]
    assert len(manual_lines) == 1
    assert manual_lines[0].get("id")


def test_empty_journal_has_no_effect(isolated_journal: Path):
    manual_rows = manual_payments.load_manual_payment_rows()
    bank_row = {
        "matched_tax_id": "111",
        "amount": 50.0,
        "row_date": "2026-05-01",
        "source_bank": "TBC",
        "raw_purpose": "purchase",
    }
    lines = build_supplier_payment_lines([bank_row], manual_rows)
    assert "111" in lines
    assert all(l["source"] != "manual" for l in lines["111"])
