"""Integration tests for supplier_invoices_section bundle.

Verifies that the Phase 1 bundle has the right shape, foodmart-specific
counts, and is JSON-serializable. Uses real CSV/XLS sources when present.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard_pipeline.supplier_invoices_section import (
    FOODMART_TAX_ID,
    build_supplier_invoices_bundle,
)


@pytest.fixture(scope="module")
def bundle():
    script_dir = Path(__file__).resolve().parent.parent
    if not (script_dir / "Financial_Analysis" / "რს ფაქტურები").exists():
        pytest.skip("rs.ge invoice exports not present (CI fixture only)")
    b = build_supplier_invoices_bundle(script_dir)
    if b is None:
        pytest.skip("bundle returned None — sources missing")
    return b


def test_bundle_has_all_phase1_keys(bundle):
    """Phase 1 contract: 5 top-level keys present."""
    expected_keys = {
        "supplier_invoices",
        "supplier_invoices_summary",
        "our_seller_invoices",
        "invoice_waybill_match",
        "supplier_invoices_meta",
    }
    assert expected_keys.issubset(bundle.keys())


def test_bundle_is_json_serializable(bundle):
    """data.json contract: bundle must be JSON-roundtrip-safe."""
    payload = json.dumps(bundle, ensure_ascii=False)
    restored = json.loads(payload)
    assert isinstance(restored, dict)
    assert restored["supplier_invoices_meta"]["supplier_count"] >= 1


def test_foodmart_invoice_count_matches_known_value(bundle):
    """Verified 2026-05-07: foodmart has 60 incoming invoices, 163,082.25 GEL."""
    fm_summary = bundle["supplier_invoices_summary"][FOODMART_TAX_ID]
    assert fm_summary["invoice_count"] == 60
    assert abs(fm_summary["total_amount"] - 163082.25) < 0.05

    fm_invoices = bundle["supplier_invoices"][FOODMART_TAX_ID]
    assert len(fm_invoices) == 60


def test_foodmart_waybill_match_has_all_60_rows(bundle):
    """Phase 1 waybill match is foodmart-only and covers every foodmart invoice."""
    matches = bundle["invoice_waybill_match"]
    assert len(matches) == 60
    assert all(m["supplier_tax_id"] == FOODMART_TAX_ID for m in matches)
    assert all("matched_waybills" in m for m in matches)
    total = sum(m["invoice_amount"] for m in matches)
    assert abs(total - 163082.25) < 0.05


def test_supplier_summary_aggregates_match_invoice_arrays(bundle):
    """Cross-check: per-supplier summary totals must equal sum of their invoices."""
    for tax_id, summary in bundle["supplier_invoices_summary"].items():
        invoices = bundle["supplier_invoices"][tax_id]
        assert summary["invoice_count"] == len(invoices)
        invoice_total = round(sum(inv["amount"] for inv in invoices), 2)
        assert abs(summary["total_amount"] - invoice_total) < 0.01


def test_xls_path_used_when_available(bundle):
    """We expect XLS source (canonical) — implies 0 skipped rows."""
    meta = bundle["supplier_invoices_meta"]
    if meta["buyer_source"].endswith(".xls"):
        assert meta["buyer_rows_skipped"] == 0
        assert meta["buyer_rows_valid"] == meta["buyer_rows_total"]
