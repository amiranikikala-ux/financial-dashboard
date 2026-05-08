"""Tests for dashboard_pipeline.supplier_reconciliation."""
from __future__ import annotations

import pytest

from dashboard_pipeline.supplier_reconciliation import (
    MATCH_THRESHOLD_GE,
    apply_supplier_reconciliation,
    build_supplier_reconciliation,
)


def _data(suppliers=None, inv_summary=None, wb_lines=None):
    return {
        "suppliers": suppliers or [],
        "supplier_invoices_summary": inv_summary or {},
        "supplier_waybill_lines": wb_lines or {},
    }


def test_perfect_match_classified_as_match():
    data = _data(
        suppliers=[{"ორგანიზაცია": "(400000001) ფირმა X"}],
        inv_summary={"400000001": {"total_amount": 1000.0, "invoice_count": 5}},
        wb_lines={"400000001": [{"amount": 1000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    assert len(bundle["rows"]) == 1
    row = bundle["rows"][0]
    assert row["status"] == "match"
    assert row["gap"] == 0.0
    assert row["ratio"] == 1.0
    assert bundle["summary"]["match_count"] == 1


def test_over_invoice_classified_when_gap_positive():
    data = _data(
        inv_summary={"400000002": {"total_amount": 5000.0, "invoice_count": 3}},
        wb_lines={"400000002": [{"amount": 1000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    row = bundle["rows"][0]
    assert row["status"] == "over_invoice"
    assert row["gap"] == 4000.0
    assert row["ratio"] == 5.0


def test_over_waybill_classified_when_gap_negative():
    data = _data(
        inv_summary={"400000003": {"total_amount": 1000.0, "invoice_count": 2}},
        wb_lines={"400000003": [{"amount": 5000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    row = bundle["rows"][0]
    assert row["status"] == "over_waybill"
    assert row["gap"] == -4000.0


def test_returns_subtract_correctly_via_negative_amount():
    """supplier_waybill_lines stores returns with negative amount.
    A straight sum must yield the net, not double-subtract."""
    data = _data(
        inv_summary={"400000004": {"total_amount": 800.0, "invoice_count": 1}},
        wb_lines={"400000004": [
            {"amount": 1000.0, "is_return": False},
            {"amount": -200.0, "is_return": True},  # return reduces net to 800
        ]},
    )
    bundle = build_supplier_reconciliation(data)
    row = bundle["rows"][0]
    assert row["waybill_total"] == 800.0
    assert row["status"] == "match"
    assert row["waybill_count"] == 1
    assert row["waybill_return_count"] == 1


def test_threshold_boundary_gap_just_under_threshold_is_match():
    data = _data(
        inv_summary={"400000005": {"total_amount": 1099.99, "invoice_count": 1}},
        wb_lines={"400000005": [{"amount": 1000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    assert bundle["rows"][0]["status"] == "match"
    assert bundle["rows"][0]["gap"] == 99.99


def test_threshold_boundary_gap_at_threshold_is_flagged():
    data = _data(
        inv_summary={"400000006": {"total_amount": 1100.0, "invoice_count": 1}},
        wb_lines={"400000006": [{"amount": 1000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    assert bundle["rows"][0]["status"] == "over_invoice"


def test_invoice_only_supplier_gets_no_ratio():
    data = _data(
        inv_summary={"400000007": {"total_amount": 500.0, "invoice_count": 1}},
        wb_lines={},
    )
    bundle = build_supplier_reconciliation(data)
    row = bundle["rows"][0]
    assert row["ratio"] is None
    assert row["waybill_total"] == 0.0
    assert row["status"] == "over_invoice"


def test_supplier_not_in_table_marked_in_suppliers_table_false():
    data = _data(
        suppliers=[{"ორგანიზაცია": "(400000008) ფირმა Y"}],
        inv_summary={
            "400000008": {"total_amount": 100.0, "invoice_count": 1},
            "400000009": {"total_amount": 200.0, "invoice_count": 1},  # ghost TID
        },
    )
    bundle = build_supplier_reconciliation(data)
    by_tid = {r["tax_id"]: r for r in bundle["rows"]}
    assert by_tid["400000008"]["in_suppliers_table"] is True
    assert by_tid["400000009"]["in_suppliers_table"] is False
    assert bundle["summary"]["missing_from_suppliers_count"] == 1


def test_summary_aggregates_correct_counts_and_totals():
    data = _data(
        inv_summary={
            "T1": {"total_amount": 1000.0, "invoice_count": 1},
            "T2": {"total_amount": 5000.0, "invoice_count": 1},
            "T3": {"total_amount": 1000.0, "invoice_count": 1},
        },
        wb_lines={
            "T1": [{"amount": 1000.0, "is_return": False}],   # match
            "T2": [{"amount": 1000.0, "is_return": False}],   # over_invoice
            "T3": [{"amount": 5000.0, "is_return": False}],   # over_waybill
        },
    )
    bundle = build_supplier_reconciliation(data)
    s = bundle["summary"]
    assert s["total_suppliers"] == 3
    assert s["match_count"] == 1
    assert s["over_invoice_count"] == 1
    assert s["over_waybill_count"] == 1
    assert s["total_invoice_ge"] == 7000.0
    assert s["total_waybill_ge"] == 7000.0
    assert s["total_gap_ge"] == 0.0
    assert s["match_threshold_ge"] == MATCH_THRESHOLD_GE


def test_rows_sorted_by_absolute_gap_descending():
    data = _data(
        inv_summary={
            "T_BIG": {"total_amount": 10000.0, "invoice_count": 1},
            "T_SMALL": {"total_amount": 100.0, "invoice_count": 1},
            "T_NEG": {"total_amount": 0.0, "invoice_count": 0},
        },
        wb_lines={
            "T_BIG": [{"amount": 1000.0, "is_return": False}],   # gap +9000
            "T_SMALL": [{"amount": 90.0, "is_return": False}],   # gap +10
            "T_NEG": [{"amount": 5000.0, "is_return": False}],   # gap -5000
        },
    )
    rows = build_supplier_reconciliation(data)["rows"]
    assert [r["tax_id"] for r in rows] == ["T_BIG", "T_NEG", "T_SMALL"]


def test_uses_total_amount_real_when_present():
    """When supplier_invoices_summary provides total_amount_real (confirmed-only),
    reconciliation must use that instead of the raw all-status total_amount."""
    data = _data(
        inv_summary={"T1": {
            "total_amount": 4000.0,           # all statuses (inflated)
            "total_amount_real": 1000.0,      # confirmed only
            "invoice_count": 4,
            "real_invoice_count": 1,
        }},
        wb_lines={"T1": [{"amount": 1000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    row = bundle["rows"][0]
    # Should classify as match using real total, not all-status total
    assert row["status"] == "match"
    assert row["invoice_total"] == 1000.0
    assert row["invoice_total_all"] == 4000.0
    assert row["invoice_count"] == 1
    assert row["invoice_count_all"] == 4


def test_falls_back_to_total_amount_when_real_field_absent():
    """Backward compat: legacy data without total_amount_real still works."""
    data = _data(
        inv_summary={"T2": {"total_amount": 1000.0, "invoice_count": 1}},
        wb_lines={"T2": [{"amount": 1000.0, "is_return": False}]},
    )
    bundle = build_supplier_reconciliation(data)
    row = bundle["rows"][0]
    assert row["status"] == "match"
    assert row["invoice_total"] == 1000.0
    assert row["invoice_total_all"] == 1000.0


def test_apply_attaches_bundle_to_data():
    data = _data(
        inv_summary={"T1": {"total_amount": 100.0, "invoice_count": 1}},
    )
    apply_supplier_reconciliation(data)
    assert "supplier_reconciliation" in data
    assert "rows" in data["supplier_reconciliation"]
    assert "summary" in data["supplier_reconciliation"]
