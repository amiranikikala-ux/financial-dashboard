"""rs.ge supplier invoices section — Phase 1 (Foodmart 360°).

Reads the manually-downloaded buyer + seller exports from rs.ge and builds
per-supplier invoice arrays + summaries that get plugged into data.json.

XLS is the canonical source for the buyer side (CSV export drops 8 invoices
mid-row). Seller side has only CSV available.

Outputs (added to data.json):
    supplier_invoices         — {tax_id: [invoice_dict]}
    supplier_invoices_summary — {tax_id: {invoice_count, total_amount, ...}}
    our_seller_invoices       — [invoice_dict] (we → customer)
    invoice_waybill_match     — Phase 1 foodmart-only per-invoice match list
    supplier_invoices_meta    — source file, row counts, supplier count
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dashboard_pipeline.rs_invoice_csv import (
    parse_buyer_invoices,
    parse_seller_invoices,
)

logger = logging.getLogger(__name__)

FOODMART_TAX_ID = "404460187"

BUYER_XLS_REL = "Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი რეესტრი.xls"
BUYER_CSV_REL = "Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი.csv"
SELLER_CSV_REL = "Financial_Analysis/რს ფაქტურები/ფაქტურები გამყიდველი.csv"

# rs.ge buyer-registry status semantics (verified 2026-05-08 against ლაქტალისი
# 166-invoice case: confirmed-only sum ≈ ZED total ≈ bank-paid total, while
# raw all-status sum is ~4× that):
#   დადასტურებული    — final, settled invoice (counts as real)
#   დასადასტურებელი  — most-recent invoice awaiting buyer confirmation (real)
#   პირველადი         — supplier-side draft, not yet finalized (NOT real)
#   კორექტირებული    — superseded version that was replaced by a correction
#                       (NOT real — its replacement appears as დადასტურებული)
#   გაუქმებული       — cancelled (NOT real)
# `total_amount` keeps the legacy all-status sum for backward compat; the new
# `total_amount_real` field is what the reconciliation tab + working-capital
# views should compare against ZED / bank payments.
REAL_INVOICE_STATUSES = frozenset({"დადასტურებული", "დასადასტურებელი"})


def _iso_or_none(value) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return None


def _safe_float(value) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _buyer_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": str(row["invoice_id"]),
        "series": str(row["series"]),
        "status": str(row["status"]),
        "supplier_tax_id": row["supplier_tax_id"],
        "supplier_name": row["supplier_name"],
        "date_issued": _iso_or_none(row["date_issued"]),
        "date_op": _iso_or_none(row["date_op"]),
        "amount": round(_safe_float(row["amount_ge"]), 2),
        "vat": round(_safe_float(row["vat_ge"]), 2),
        "decl_period": str(row["decl_period"]),
        "waybills": list(row["waybills"]) if row["waybills"] else [],
    }


def _seller_row_to_dict(row) -> dict[str, Any]:
    items = row["items"] if row["items"] is not None else []
    safe_items = []
    for it in items:
        safe_items.append({
            "description": str(it.get("description", "")),
            "unit": str(it.get("unit", "")),
            "qty": _safe_float(it.get("qty")),
            "value_ge": round(_safe_float(it.get("value_ge")), 2),
            "vat_ge": round(_safe_float(it.get("vat_ge")), 2),
            "excise_ge": round(_safe_float(it.get("excise_ge")), 2),
            "taxation": str(it.get("taxation", "")),
        })
    return {
        "id": str(row["invoice_id"]),
        "series": str(row["series"]),
        "customer_tax_id": row["customer_tax_id"],
        "customer_name": row["customer_name"],
        "date_issued": _iso_or_none(row["date_issued"]),
        "date_op": _iso_or_none(row["date_op"]),
        "amount": round(_safe_float(row["amount_ge"]), 2),
        "vat": round(_safe_float(row["vat_ge"]), 2),
        "excise": round(_safe_float(row["excise_ge"]), 2),
        "line_count": int(row["line_count"]),
        "items": safe_items,
    }


def _build_summary(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    real_invoices: list[dict[str, Any]] = []
    for inv in invoices:
        st = inv.get("status") or ""
        status_counts[st] = status_counts.get(st, 0) + 1
        if st in REAL_INVOICE_STATUSES:
            real_invoices.append(inv)
    iso_dates = [inv["date_issued"] for inv in invoices if inv.get("date_issued")]
    last_date = max(iso_dates) if iso_dates else None
    return {
        "invoice_count": len(invoices),
        "total_amount": round(sum(inv["amount"] for inv in invoices), 2),
        "total_vat": round(sum(inv["vat"] for inv in invoices), 2),
        "real_invoice_count": len(real_invoices),
        "total_amount_real": round(sum(inv["amount"] for inv in real_invoices), 2),
        "total_vat_real": round(sum(inv["vat"] for inv in real_invoices), 2),
        "status_counts": status_counts,
        "last_invoice_date": last_date,
    }


def _build_foodmart_waybill_match(df_buyer) -> list[dict[str, Any]]:
    """Per-invoice waybill match list for foodmart. Phase 1 scope only.

    Phase 2 will extend this to all suppliers (preview spec).
    """
    fm = df_buyer[df_buyer["supplier_tax_id"] == FOODMART_TAX_ID]
    out: list[dict[str, Any]] = []
    for _, row in fm.iterrows():
        waybills = list(row["waybills"]) if row["waybills"] else []
        out.append({
            "invoice_id": str(row["invoice_id"]),
            "supplier_tax_id": FOODMART_TAX_ID,
            "invoice_amount": round(_safe_float(row["amount_ge"]), 2),
            "matched_waybills": waybills,
            "waybill_count": len(waybills),
            "date_issued": _iso_or_none(row["date_issued"]),
        })
    return out


def build_supplier_invoices_bundle(script_dir: Path) -> dict[str, Any] | None:
    """Build the supplier-invoices section. Returns None if source files missing.

    Pipeline adds the returned dict's keys directly into data.json.
    """
    script_dir = Path(script_dir)
    buyer_xls = script_dir / BUYER_XLS_REL
    buyer_csv = script_dir / BUYER_CSV_REL
    seller_csv = script_dir / SELLER_CSV_REL

    buyer_path = buyer_xls if buyer_xls.exists() else buyer_csv
    if not buyer_path.exists():
        logger.info("rs.ge buyer invoice export not found; skipping supplier_invoices")
        return None
    if not seller_csv.exists():
        logger.info("rs.ge seller invoice export not found; skipping supplier_invoices")
        return None

    df_buyer, stats_b = parse_buyer_invoices(buyer_path)
    df_seller, _ = parse_seller_invoices(seller_csv)

    supplier_invoices: dict[str, list[dict[str, Any]]] = {}
    supplier_summary: dict[str, dict[str, Any]] = {}
    for tax_id, sub in df_buyer.groupby("supplier_tax_id"):
        invoices = [_buyer_row_to_dict(row) for _, row in sub.iterrows()]
        supplier_invoices[tax_id] = invoices
        supplier_summary[tax_id] = _build_summary(invoices)

    our_seller_invoices = [_seller_row_to_dict(row) for _, row in df_seller.iterrows()]
    invoice_waybill_match = _build_foodmart_waybill_match(df_buyer)

    bundle = {
        "supplier_invoices": supplier_invoices,
        "supplier_invoices_summary": supplier_summary,
        "our_seller_invoices": our_seller_invoices,
        "invoice_waybill_match": invoice_waybill_match,
        "supplier_invoices_meta": {
            "buyer_source": str(buyer_path.name),
            "buyer_rows_total": int(stats_b.rows_total),
            "buyer_rows_valid": int(stats_b.rows_valid),
            "buyer_rows_skipped": int(stats_b.rows_skipped),
            "buyer_skip_reasons": dict(stats_b.skip_reasons or {}),
            "seller_invoice_count": len(our_seller_invoices),
            "supplier_count": len(supplier_summary),
        },
    }

    total_buyer_amount = sum(s["total_amount"] for s in supplier_summary.values())
    logger.info(
        "supplier_invoices: %d suppliers, %d buyer invoices (%.2f ₾), %d seller invoices",
        len(supplier_summary),
        stats_b.rows_valid,
        total_buyer_amount,
        len(our_seller_invoices),
    )
    return bundle
