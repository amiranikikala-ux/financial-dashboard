"""Apply service-supplier override: invoice-based debt instead of waybill-based.

Service suppliers (consulting, transport, rent, communications) typically have
no waybills issued — only invoices. The default debt formula
``total_debt = total_effective(waybills) - total_paid(bank)`` therefore
produces a false negative for them: bank payments exceed waybill total
(which is near zero).

For each tax_id listed in ``Financial_Analysis/service_suppliers.json`` this
module overrides:
    total_effective = invoice ``total_amount_real``
    total_debt      = invoice ``total_amount_real`` - total_paid

The original waybill ``total_effective`` is preserved on the row as
``waybill_total_effective`` for traceability, and the row is marked with
``is_service_supplier = true``.
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def _extract_tid_from_org(org: str) -> str:
    if not isinstance(org, str):
        return ""
    m = re.search(r"\b(\d{9,11})\b", org)
    return m.group(1) if m else ""


def _default_financial_analysis_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "Financial_Analysis"


def _load_service_suppliers(financial_analysis_dir: Path) -> Dict[str, dict]:
    config_path = financial_analysis_dir / "service_suppliers.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as fh:
            payload = json.load(fh) or {}
    except Exception as exc:
        logger.warning("service_suppliers.json read failed: %s", exc)
        return {}
    out: Dict[str, dict] = {}
    for entry in payload.get("suppliers") or []:
        tid = str(entry.get("tax_id") or "").strip()
        if tid:
            out[tid] = entry
    return out


def apply_service_supplier_debt(data: dict, financial_analysis_dir: Path | None = None) -> dict:
    """Mutate ``data["suppliers"]`` for service suppliers. Returns the same dict."""
    suppliers = data.get("suppliers") or []
    if not suppliers:
        return data

    fa_dir = financial_analysis_dir or _default_financial_analysis_dir()
    service_map = _load_service_suppliers(fa_dir)
    if not service_map:
        return data

    invoices_summary = data.get("supplier_invoices_summary") or {}
    matched = 0
    skipped_no_invoice = 0
    for s in suppliers:
        org = str(s.get("ორგანიზაცია") or "")
        tid = _extract_tid_from_org(org)
        if not tid or tid not in service_map:
            continue
        inv = invoices_summary.get(tid) or {}
        invoice_real = float(inv.get("total_amount_real") or 0)
        if invoice_real <= 0:
            skipped_no_invoice += 1
            logger.warning(
                "service_supplier %s has no real invoice total — skipping override",
                tid,
            )
            continue
        original_effective = float(s.get("total_effective") or 0)
        total_paid = float(s.get("total_paid") or 0)
        s["waybill_total_effective"] = round(original_effective, 2)
        s["total_effective"] = round(invoice_real, 2)
        s["total_debt"] = round(invoice_real - total_paid, 2)
        s["is_service_supplier"] = True
        s["service_supplier_reason"] = str(service_map[tid].get("reason") or "").strip()
        matched += 1

    if matched or skipped_no_invoice:
        logger.info(
            "service_supplier_debt: applied=%d skipped_no_invoice=%d",
            matched,
            skipped_no_invoice,
        )
    return data
