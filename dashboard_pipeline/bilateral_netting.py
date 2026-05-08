"""Bilateral netting for suppliers who are also our customers.

When a supplier (e.g., Foodmart) issues invoices to us AND we issue
invoices to them, payments are settled via netting — foodmart deducts
its invoice amount from what it owes us, and transfers only the net
remainder via bank cashback. There is no direct bank payment from us
to such suppliers, so the standard `total_paid` (bank_payments lookup)
returns 0 and the supplier appears as fully indebted in aging — which
is wrong.

This module recomputes `total_paid` / `total_debt` for bilateral
suppliers based on bilateral net position so the suppliers table
reflects reality automatically (no manual journal entry needed).

Logic per configured TID:
  our_total = sum(our_seller_invoices we issued to this TID)
  their_total = sum(supplier_invoices issued by this TID to us)
  cashback = sum(bank inflow from this TID)
  net = our_total - their_total - cashback
        (positive: they still owe us; negative: we owe them beyond what
         cashback covered)
  if net >= 0: goods/services received from them are fully settled via
               netting; total_paid bumped to total_effective, debt = 0
  else:        we owe them |net| of the netting deficit; debt clipped
               at min(total_effective, |net|)
"""
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# Per-TID bilateral configuration.
# Key: supplier tax_id. Value: data.json key holding cashback bundle
# with "total_ge" field (or compatible "total_amount_ge").
BILATERAL_SUPPLIERS: Dict[str, str] = {
    "404460187": "tbc_foodmart_cashback",  # შპს ფუდმარტი
}


def _extract_tid_from_org(org: str) -> str:
    if not isinstance(org, str):
        return ""
    m = re.search(r"\b(\d{9,11})\b", org)
    return m.group(1) if m else ""


def _sum_our_invoices(our_seller_invoices: List[dict], tid: str) -> float:
    return sum(
        float(inv.get("amount") or 0)
        for inv in (our_seller_invoices or [])
        if str(inv.get("customer_tax_id", "")) == tid
    )


def _sum_their_invoices(supplier_invoices: Dict[str, list], tid: str) -> float:
    invs = (supplier_invoices or {}).get(tid, []) or []
    return sum(float(inv.get("amount") or 0) for inv in invs)


def _cashback_total(data: dict, source_key: str) -> float:
    bundle = data.get(source_key) or {}
    if not isinstance(bundle, dict):
        return 0.0
    return float(bundle.get("total_ge") or bundle.get("total_amount_ge") or 0)


def apply_bilateral_netting(data: dict) -> dict:
    """Mutate `data["suppliers"]` for bilateral suppliers.

    Adds: bank_paid_pre_netting, netted_paid; updates total_paid,
    total_debt, payment_scope, payment_scope_note. Returns the same
    dict for chaining.
    """
    suppliers = data.get("suppliers") or []
    our_seller_invoices = data.get("our_seller_invoices") or []
    supplier_invoices = data.get("supplier_invoices") or {}

    matched = 0
    for s in suppliers:
        org = str(s.get("ორგანიზაცია") or "")
        tid = _extract_tid_from_org(org)
        if not tid or tid not in BILATERAL_SUPPLIERS:
            continue

        our_total = _sum_our_invoices(our_seller_invoices, tid)
        their_total = _sum_their_invoices(supplier_invoices, tid)
        cashback = _cashback_total(data, BILATERAL_SUPPLIERS[tid])
        net = our_total - their_total - cashback
        total_effective = float(s.get("total_effective") or 0)

        if net >= 0:
            netted_paid = total_effective
            new_debt = 0.0
            note = (
                f"ორმხრივი კომპენსაცია: ჩვენი ფაქტურა {our_total:,.0f} ₾ "
                f"− მათი ფაქტურა {their_total:,.0f} ₾ "
                f"− cashback {cashback:,.0f} ₾ = ფუდმარტი ჩვენ გვმართებს +{net:,.0f} ₾ "
                f"(მათი ვალი ჩვენგან: 0)"
            )
        else:
            netted_paid = max(0.0, total_effective - abs(net))
            new_debt = max(0.0, total_effective - netted_paid)
            note = (
                f"ორმხრივი კომპენსაცია: ჩვენი ფაქტურა {our_total:,.0f} ₾ "
                f"− მათი ფაქტურა {their_total:,.0f} ₾ "
                f"− cashback {cashback:,.0f} ₾ = ჩვენ ვმართებთ {abs(net):,.0f} ₾"
            )

        original_paid = float(s.get("total_paid") or 0)
        s["bank_paid_pre_netting"] = original_paid
        s["netted_paid"] = round(netted_paid, 2)
        s["total_paid"] = round(original_paid + netted_paid, 2)
        s["total_debt"] = round(new_debt, 2)
        s["payment_scope_note"] = note
        s["payment_scope"] = "bilateral_netted"
        matched += 1

    if matched:
        logger.info("bilateral_netting: applied to %d supplier(s)", matched)
    return data
