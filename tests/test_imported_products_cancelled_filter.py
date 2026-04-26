"""Regression tests for cancelled-status filtering in imported_products bundle.

Sprint A/B follow-up (2026-04-27): RS waybills marked გაუქმებული represent
operations that were created in RS.ge then cancelled before completion — no
goods delivered, no payment owed. Counting them in cost_imported / supplier
totals overstated portfolio cost by ~110K ₾ before this fix landed.

These tests pin three behaviours so the fix cannot silently regress:

1. Cancelled rows do not contribute to row counts, amounts, supplier stats,
   product stats, or any other aggregate.
2. The drop count + amount surface in ``bundle["overall"]`` mirroring the
   existing ``duplicate_rows_dropped`` / ``duplicate_amount_dropped_ge``
   tally so it stays auditable.
3. Cancelled rows are filtered BEFORE the composite-key dedup, so a
   cancelled row sharing the same (waybill, code, name, amount, qty) as a
   legitimate active row does not "win" the dedup slot and cause the
   active row to be silently dropped as a duplicate.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import imported_products
from dashboard_pipeline.imported_products import (
    CANCELLED_STATUS_KA,
    collect_imported_products_bundle,
)


def _make_row(
    *,
    code: str = "1234",
    name: str = "ტესტ პროდუქტი",
    amount: float = 100.0,
    qty: float = 1.0,
    status: str = "აქტიური",
    waybill: str = "WB-A",
    supplier: str = "(204920381) შპს ტესტ",
    activation: str = "2025-06-15",
    transport: str = "2025-06-15",
    destination: str = "ოზურგეთი",
    unit: str = "ცალი",
    buyer: str = "შპს მყიდველი",
):
    return {
        "საქონლის კოდი": code,
        "საქონლის დასახელება": name,
        "ზომის ერთეული": unit,
        "რაოდ.": qty,
        "ერთეულის ფასი": amount,
        "საქონლის ფასი": amount,
        "დაბეგვრა": "",
        "ზედნადების ნომერი": waybill,
        "სტატუსი": status,
        "მყიდველი": buyer,
        "გამყიდველი": supplier,
        "ზედნადების ტიპი": "",
        "ტრანსპორტირების დაწყება": "",
        "ტრანსპორტირების დასრულება": destination,
        "მძღოლი": "",
        "ა/მ ნომერი": "",
        "გააქტიურების თარიღი": activation,
        "ტრანსპორტირების დაწყების თარიღი": transport,
        "ტრანსპ. თანხა": "",
        "შენიშვნა": "",
        "ქვე-მომხმარებელი": "",
        "ფირნიშის ან ცნობის ნომერი": "",
        "დოკუმენტის N": "",
    }


@pytest.fixture()
def patched_pipeline(monkeypatch, tmp_path):
    """Patch the file-listing + reader so the bundle reads our in-memory rows."""

    holder = {"rows": []}

    fake_path = str(tmp_path / "fake.csv")

    def _fake_list_files():
        return [fake_path]

    def _fake_read(path):
        df = pd.DataFrame(holder["rows"])
        return df, "csv", None

    monkeypatch.setattr(imported_products, "list_imported_product_files", _fake_list_files)
    monkeypatch.setattr(imported_products, "_read_imported_products_file", _fake_read)
    return holder


def test_cancelled_rows_excluded_from_totals(patched_pipeline):
    patched_pipeline["rows"] = [
        _make_row(code="A1", amount=100.0, qty=1.0, waybill="W1", status="აქტიური"),
        _make_row(code="A2", amount=200.0, qty=2.0, waybill="W1", status="აქტიური"),
        _make_row(code="A3", amount=999.0, qty=9.0, waybill="W2", status=CANCELLED_STATUS_KA),
    ]
    bundle = collect_imported_products_bundle()

    overall = bundle["overall"]
    # Only the 2 active rows count
    assert overall["row_count"] == 2
    assert overall["total_amount_ge"] == pytest.approx(300.0)
    # Cancelled tally surfaces for visibility
    assert overall["cancelled_rows_dropped"] == 1
    assert overall["cancelled_amount_dropped_ge"] == pytest.approx(999.0)
    # Suppliers list reflects only active rows
    suppliers = bundle["suppliers"]
    assert len(suppliers) == 1
    assert suppliers[0]["total_amount_ge"] == pytest.approx(300.0)
    assert suppliers[0]["row_count"] == 2


def test_cancelled_status_does_not_appear_in_by_status(patched_pipeline):
    patched_pipeline["rows"] = [
        _make_row(code="A1", amount=100.0, qty=1.0, waybill="W1", status="აქტიური"),
        _make_row(code="A2", amount=200.0, qty=2.0, waybill="W2", status="დასრულებული"),
        _make_row(code="A3", amount=999.0, qty=9.0, waybill="W3", status=CANCELLED_STATUS_KA),
        _make_row(code="A4", amount=500.0, qty=5.0, waybill="W4", status=CANCELLED_STATUS_KA),
    ]
    bundle = collect_imported_products_bundle()

    statuses = {row["status"]: row for row in bundle["by_status"]}
    assert "აქტიური" in statuses
    assert "დასრულებული" in statuses
    # Cancelled is filtered out before the by_status accumulator runs
    assert CANCELLED_STATUS_KA not in statuses
    # But the tally on overall reflects the drop
    assert bundle["overall"]["cancelled_rows_dropped"] == 2
    assert bundle["overall"]["cancelled_amount_dropped_ge"] == pytest.approx(1499.0)


def test_cancelled_does_not_poison_dedup_seen_set(patched_pipeline):
    """A cancelled row sharing the composite key of an active row must not
    cause the active row to be dropped as a 'duplicate'."""
    shared_kwargs = {"code": "X1", "amount": 50.0, "qty": 1.0, "waybill": "W1"}
    patched_pipeline["rows"] = [
        # Cancelled row appears FIRST in iteration order
        _make_row(status=CANCELLED_STATUS_KA, **shared_kwargs),
        # Active row with identical composite key
        _make_row(status="აქტიური", **shared_kwargs),
    ]
    bundle = collect_imported_products_bundle()

    overall = bundle["overall"]
    # The active row is preserved; only the cancelled is filtered
    assert overall["row_count"] == 1
    assert overall["total_amount_ge"] == pytest.approx(50.0)
    assert overall["cancelled_rows_dropped"] == 1
    # Crucial: the active row is NOT counted as a dedup drop
    assert overall["duplicate_rows_dropped"] == 0


def test_no_cancelled_rows_keeps_zero_tally(patched_pipeline):
    patched_pipeline["rows"] = [
        _make_row(code="A1", amount=100.0, qty=1.0, waybill="W1", status="აქტიური"),
        _make_row(code="A2", amount=200.0, qty=2.0, waybill="W2", status="დასრულებული"),
    ]
    bundle = collect_imported_products_bundle()

    overall = bundle["overall"]
    assert overall["row_count"] == 2
    assert overall["total_amount_ge"] == pytest.approx(300.0)
    assert overall["cancelled_rows_dropped"] == 0
    assert overall["cancelled_amount_dropped_ge"] == 0.0


def test_cancelled_amount_tally_uses_raw_amount(patched_pipeline):
    """Cancelled amount tally must reflect what was dropped (face value),
    independent of dedup logic."""
    patched_pipeline["rows"] = [
        _make_row(code="A1", amount=12.34, qty=1.0, waybill="W1", status=CANCELLED_STATUS_KA),
        _make_row(code="A2", amount=56.78, qty=2.0, waybill="W2", status=CANCELLED_STATUS_KA),
        _make_row(code="A3", amount=99.99, qty=1.0, waybill="W3", status="აქტიური"),
    ]
    bundle = collect_imported_products_bundle()

    overall = bundle["overall"]
    assert overall["row_count"] == 1
    assert overall["total_amount_ge"] == pytest.approx(99.99)
    assert overall["cancelled_rows_dropped"] == 2
    assert overall["cancelled_amount_dropped_ge"] == pytest.approx(69.12)
