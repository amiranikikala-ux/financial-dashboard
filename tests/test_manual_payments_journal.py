"""Owner-entered manual payments journal — append, list, soft-delete."""

from __future__ import annotations

import pytest

from dashboard_pipeline import manual_payments_journal as mpj


@pytest.fixture
def journal(tmp_path):
    return str(tmp_path / "journal.csv")


def test_read_returns_empty_when_file_missing(journal):
    assert mpj.read_active_entries(journal) == []
    assert mpj.aggregate_amount_by_tax_id(journal) == {}


def test_append_entry_round_trips(journal):
    saved = mpj.append_entry(tax_id="406181616", amount=72972.0, comment="ჯიდიაი ნაღდი", path=journal)
    assert saved["tax_id"] == "406181616"
    assert saved["amount"] == 72972.0
    assert saved["id"]
    entries = mpj.read_active_entries(journal)
    assert len(entries) == 1
    assert entries[0]["id"] == saved["id"]
    assert entries[0]["amount"] == 72972.0


def test_append_rejects_invalid_tax_id(journal):
    with pytest.raises(ValueError):
        mpj.append_entry(tax_id="", amount=100, path=journal)
    with pytest.raises(ValueError):
        mpj.append_entry(tax_id="abc", amount=100, path=journal)


def test_append_rejects_non_positive_amount(journal):
    with pytest.raises(ValueError):
        mpj.append_entry(tax_id="123", amount=0, path=journal)
    with pytest.raises(ValueError):
        mpj.append_entry(tax_id="123", amount=-50, path=journal)


def test_multiple_entries_for_same_supplier(journal):
    mpj.append_entry(tax_id="111", amount=100, path=journal)
    mpj.append_entry(tax_id="111", amount=200, path=journal)
    mpj.append_entry(tax_id="222", amount=50, path=journal)
    entries = mpj.read_active_entries(journal)
    assert len(entries) == 3
    totals = mpj.aggregate_amount_by_tax_id(journal)
    assert totals == {"111": 300.0, "222": 50.0}


def test_soft_delete_marks_entry_inactive(journal):
    e1 = mpj.append_entry(tax_id="111", amount=100, path=journal)
    e2 = mpj.append_entry(tax_id="111", amount=200, path=journal)
    assert mpj.soft_delete_entry(e1["id"], path=journal) is True

    active = mpj.read_active_entries(journal)
    assert len(active) == 1
    assert active[0]["id"] == e2["id"]
    assert mpj.aggregate_amount_by_tax_id(journal) == {"111": 200.0}


def test_soft_delete_unknown_id_returns_false(journal):
    mpj.append_entry(tax_id="111", amount=100, path=journal)
    assert mpj.soft_delete_entry("nonexistent-uuid", path=journal) is False
    assert len(mpj.read_active_entries(journal)) == 1


def test_soft_delete_idempotent(journal):
    e = mpj.append_entry(tax_id="111", amount=100, path=journal)
    assert mpj.soft_delete_entry(e["id"], path=journal) is True
    assert mpj.soft_delete_entry(e["id"], path=journal) is False


def test_read_entries_for_tax_id_filters(journal):
    mpj.append_entry(tax_id="111", amount=100, path=journal)
    mpj.append_entry(tax_id="222", amount=50, path=journal)
    mpj.append_entry(tax_id="111", amount=300, path=journal)

    entries = mpj.read_entries_for_tax_id("111", path=journal)
    assert len(entries) == 2
    assert sum(e["amount"] for e in entries) == 400.0
    assert mpj.read_entries_for_tax_id("999", path=journal) == []


def test_amount_rounded_to_two_decimals(journal):
    e = mpj.append_entry(tax_id="111", amount=100.4567, path=journal)
    assert e["amount"] == 100.46
    assert mpj.read_active_entries(journal)[0]["amount"] == 100.46


def test_each_entry_gets_unique_id(journal):
    e1 = mpj.append_entry(tax_id="111", amount=100, path=journal)
    e2 = mpj.append_entry(tax_id="111", amount=100, path=journal)
    assert e1["id"] != e2["id"]


def test_csv_format_has_expected_headers(journal):
    mpj.append_entry(tax_id="111", amount=100, path=journal)
    with open(journal, "r", encoding="utf-8-sig") as f:
        first_line = f.readline().strip()
    assert "id" in first_line
    assert "tax_id" in first_line
    assert "amount" in first_line
    assert "deleted_at" in first_line


def test_atomic_write_does_not_corrupt_on_concurrent_reads(journal, tmp_path):
    import threading
    import time

    e_first = mpj.append_entry(tax_id="111", amount=100, path=journal)
    errors = []
    reads_seen = []

    def reader():
        try:
            for _ in range(50):
                rows = mpj.read_active_entries(journal)
                reads_seen.append(len(rows))
                time.sleep(0.001)
        except Exception as exc:
            errors.append(exc)

    def writer():
        try:
            for i in range(20):
                mpj.append_entry(tax_id="111", amount=10 + i, path=journal)
                time.sleep(0.001)
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=reader)
    t2 = threading.Thread(target=writer)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == []
    final_count = len(mpj.read_active_entries(journal))
    assert final_count == 21  # 1 initial + 20 writes
    assert all(c >= 1 for c in reads_seen)
