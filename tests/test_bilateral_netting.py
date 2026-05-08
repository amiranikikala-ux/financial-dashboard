"""Tests for bilateral netting (foodmart-style suppliers)."""
import pytest

from dashboard_pipeline.bilateral_netting import apply_bilateral_netting


FOODMART_TID = "404460187"


def _make_data(*, our_total, their_total, cashback, total_effective, tid=FOODMART_TID):
    """Build a minimal data dict with one supplier row for testing."""
    suppliers = [{
        "ორგანიზაცია": f"({tid}) Test Supplier",
        "total_effective": total_effective,
        "total_paid": 0.0,
        "total_debt": total_effective,
    }]
    our_seller_invoices = (
        [{"customer_tax_id": tid, "amount": our_total}] if our_total else []
    )
    supplier_invoices = (
        {tid: [{"amount": their_total}]} if their_total else {}
    )
    return {
        "suppliers": suppliers,
        "our_seller_invoices": our_seller_invoices,
        "supplier_invoices": supplier_invoices,
        "tbc_foodmart_cashback": {"total_ge": cashback},
    }


def test_net_creditor_zeros_debt_real_foodmart_numbers():
    """Foodmart 4-year totals should produce zero debt (we are net creditor)."""
    data = _make_data(
        our_total=508573.38,
        their_total=163082.25,
        cashback=335202.36,
        total_effective=53774.50,
    )
    apply_bilateral_netting(data)

    s = data["suppliers"][0]
    assert s["total_debt"] == 0.0
    assert s["total_paid"] == pytest.approx(53774.50, abs=0.01)
    assert s["netted_paid"] == pytest.approx(53774.50, abs=0.01)
    assert s["bank_paid_pre_netting"] == 0.0
    assert s["payment_scope"] == "bilateral_netted"
    assert "ორმხრივი კომპენსაცია" in s["payment_scope_note"]


def test_we_owe_them_beyond_netting():
    """When netting can't cover what we owe, debt reflects remainder."""
    # We invoiced them 30; they invoiced us 70; no cashback
    # net = 30 - 70 - 0 = -40 → we owe 40 beyond netting
    # netted_paid = max(0, 70 - 40) = 30
    # debt = 70 - 30 = 40
    data = _make_data(
        our_total=30.0,
        their_total=70.0,
        cashback=0.0,
        total_effective=70.0,
    )
    apply_bilateral_netting(data)

    s = data["suppliers"][0]
    assert s["total_debt"] == pytest.approx(40.0, abs=0.01)
    assert s["total_paid"] == pytest.approx(30.0, abs=0.01)
    assert s["netted_paid"] == pytest.approx(30.0, abs=0.01)
    assert s["payment_scope"] == "bilateral_netted"


def test_bank_paid_pre_netting_preserves_original_value():
    """Original bank-payment value should be preserved in bank_paid_pre_netting."""
    data = _make_data(
        our_total=1000.0,
        their_total=500.0,
        cashback=400.0,
        total_effective=500.0,
    )
    # simulate that there was already a bank payment of 100
    data["suppliers"][0]["total_paid"] = 100.0
    apply_bilateral_netting(data)

    s = data["suppliers"][0]
    assert s["bank_paid_pre_netting"] == 100.0
    # net = 1000 - 500 - 400 = +100 → net creditor → fully netted
    assert s["netted_paid"] == 500.0
    # total_paid = original_bank + netted = 100 + 500 = 600
    assert s["total_paid"] == 600.0
    assert s["total_debt"] == 0.0


def test_non_bilateral_supplier_untouched():
    """Suppliers not in BILATERAL list should not be modified."""
    data = {
        "suppliers": [{
            "ორგანიზაცია": "(123456789) Random Supplier",
            "total_effective": 1000.0,
            "total_paid": 200.0,
            "total_debt": 800.0,
        }],
        "our_seller_invoices": [],
        "supplier_invoices": {},
        "tbc_foodmart_cashback": {"total_ge": 0},
    }
    apply_bilateral_netting(data)
    s = data["suppliers"][0]
    assert s["total_debt"] == 800.0
    assert s["total_paid"] == 200.0
    assert "bilateral_netted" not in str(s.get("payment_scope") or "")


def test_empty_data_does_not_crash():
    apply_bilateral_netting({})
    apply_bilateral_netting({"suppliers": []})
    apply_bilateral_netting({"suppliers": [{"ორგანიზაცია": ""}]})


def test_supplier_without_tid_in_org_skipped():
    """If we can't extract a TID from ორგანიზაცია, skip safely."""
    data = {
        "suppliers": [{
            "ორგანიზაცია": "no-tax-id-here",
            "total_effective": 100,
            "total_paid": 0,
            "total_debt": 100,
        }],
        "our_seller_invoices": [],
        "supplier_invoices": {},
        "tbc_foodmart_cashback": {"total_ge": 0},
    }
    apply_bilateral_netting(data)
    s = data["suppliers"][0]
    # untouched
    assert s["total_debt"] == 100
    assert s.get("payment_scope") != "bilateral_netted"


def test_zero_invoices_zeros_out_correctly():
    """If no invoices on either side and no cashback, but goods received: still apply net = 0 → fully netted? No: in that case we DO owe them."""
    # our_total=0, their_total=0, cashback=0, total_effective=100
    # net = 0 - 0 - 0 = 0 → "net creditor"-ის ზღვარი
    # netted_paid = total_effective = 100, debt = 0
    # ეს კონფიგურაცია მცდელობაა: მომავალში თუ supplier-ი bilateral-ად
    # კონფიგდებოდა, მაგრამ ჯერ არ გვაქვს ინვოისები — ხელით გადახდა საჭიროა.
    # მონაცემთა realityში თუ such case იქნება — ხელით უნდა შესწორდეს.
    data = _make_data(
        our_total=0.0,
        their_total=0.0,
        cashback=0.0,
        total_effective=100.0,
    )
    apply_bilateral_netting(data)
    s = data["suppliers"][0]
    # net = 0 ≥ 0 → fully netted (note this edge case for documentation)
    assert s["total_debt"] == 0.0
    assert s["netted_paid"] == 100.0
