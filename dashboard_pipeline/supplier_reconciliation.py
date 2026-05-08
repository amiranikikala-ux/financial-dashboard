"""Per-supplier invoice ↔ waybill reconciliation summary (Phase 2).

Phase 1 (foodmart-only) computed `invoice_waybill_match` for a single
TID. Phase 2 generalizes that comparison to all suppliers in the data
set so the owner can spot which vendors have unexplained gaps.

Per-TID computation:
  invoice_total = supplier_invoices_summary[tid]["total_amount"]
  waybill_total = sum(supplier_waybill_lines[tid][*]["amount"])
                  ← returns already carry negative amounts here, so
                    a plain sum yields the net value (positives minus
                    refunded shipments).
  gap           = invoice_total − waybill_total
  ratio         = invoice_total / waybill_total when waybill_total > 0

Classification:
  - "match"        when |gap| < MATCH_THRESHOLD_GE
  - "over_invoice" when gap >= +threshold  (invoice exceeds waybill)
  - "over_waybill" when gap <= −threshold  (waybill exceeds invoice)

The bundle is exposed as ``data["supplier_reconciliation"]`` and read
by the new "reconciliation" UI tab.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MATCH_THRESHOLD_GE = 100.0


def _extract_tid_from_org(org: str) -> str:
    if not isinstance(org, str):
        return ""
    m = re.search(r"\b(\d{9,11})\b", org)
    return m.group(1) if m else ""


def _classify(gap: float) -> str:
    if abs(gap) < MATCH_THRESHOLD_GE:
        return "match"
    return "over_invoice" if gap > 0 else "over_waybill"


def build_supplier_reconciliation(data: dict) -> Dict[str, Any]:
    """Build the per-supplier reconciliation bundle from data.json inputs."""
    inv_summary: Dict[str, dict] = data.get("supplier_invoices_summary") or {}
    wb_lines: Dict[str, list] = data.get("supplier_waybill_lines") or {}
    suppliers: List[dict] = data.get("suppliers") or []

    name_by_tid: Dict[str, str] = {}
    for s in suppliers:
        org = str(s.get("ორგანიზაცია") or "")
        tid = _extract_tid_from_org(org)
        if tid:
            name_by_tid[tid] = org

    all_tids = set(inv_summary.keys()) | set(wb_lines.keys())

    rows: List[dict] = []
    for tid in all_tids:
        inv = inv_summary.get(tid) or {}
        # Use confirmed-only totals — rs.ge registry includes drafts +
        # corrections that don't represent real invoices. Falls back to
        # all-status totals if the supplier_invoices_section data hasn't
        # been refreshed yet (legacy).
        inv_total_all = float(inv.get("total_amount") or 0)
        inv_total = float(inv.get("total_amount_real") or inv_total_all)
        inv_count_all = int(inv.get("invoice_count") or 0)
        inv_count = int(inv.get("real_invoice_count") or inv_count_all)
        last_inv_date = inv.get("last_invoice_date") or None

        wbs = wb_lines.get(tid) or []
        # supplier_waybill_lines stores returns with negative amounts
        # already, so a straight sum gives the correct net.
        wb_total = sum(float(w.get("amount") or 0) for w in wbs)
        wb_pos_count = sum(1 for w in wbs if not w.get("is_return"))
        wb_ret_count = sum(1 for w in wbs if w.get("is_return"))

        gap = inv_total - wb_total
        ratio = (inv_total / wb_total) if wb_total > 0 else None

        rows.append({
            "tax_id": tid,
            "name": name_by_tid.get(tid, ""),
            "invoice_total": round(inv_total, 2),
            "invoice_total_all": round(inv_total_all, 2),
            "invoice_count": inv_count,
            "invoice_count_all": inv_count_all,
            "waybill_total": round(wb_total, 2),
            "waybill_count": wb_pos_count,
            "waybill_return_count": wb_ret_count,
            "gap": round(gap, 2),
            "ratio": round(ratio, 4) if ratio is not None else None,
            "status": _classify(gap),
            "in_suppliers_table": tid in name_by_tid,
            "last_invoice_date": last_inv_date,
        })

    rows.sort(key=lambda r: abs(r["gap"]), reverse=True)

    summary = {
        "total_suppliers": len(rows),
        "match_count": sum(1 for r in rows if r["status"] == "match"),
        "over_invoice_count": sum(1 for r in rows if r["status"] == "over_invoice"),
        "over_waybill_count": sum(1 for r in rows if r["status"] == "over_waybill"),
        "total_invoice_ge": round(sum(r["invoice_total"] for r in rows), 2),
        "total_waybill_ge": round(sum(r["waybill_total"] for r in rows), 2),
        "total_gap_ge": round(sum(r["gap"] for r in rows), 2),
        "match_threshold_ge": MATCH_THRESHOLD_GE,
        "missing_from_suppliers_count": sum(1 for r in rows if not r["in_suppliers_table"]),
    }

    return {"rows": rows, "summary": summary}


def apply_supplier_reconciliation(data: dict) -> dict:
    """Attach the reconciliation bundle to data under the
    ``supplier_reconciliation`` key. Returns the same dict for chaining.
    """
    bundle = build_supplier_reconciliation(data)
    data["supplier_reconciliation"] = bundle
    logger.info(
        "supplier_reconciliation: %d suppliers (match=%d, over_inv=%d, over_wb=%d, gap=%.2f ₾)",
        bundle["summary"]["total_suppliers"],
        bundle["summary"]["match_count"],
        bundle["summary"]["over_invoice_count"],
        bundle["summary"]["over_waybill_count"],
        bundle["summary"]["total_gap_ge"],
    )
    return data
