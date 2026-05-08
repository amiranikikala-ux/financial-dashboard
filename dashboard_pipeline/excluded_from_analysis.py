"""Apply user's "excluded_from_analysis" flag to suppliers data.

When the user marks a supplier with excluded_from_analysis=true (via the
suppliers UI), the pipeline must zero out their debt and remove them
from aggregations — typical reason is "soon-to-be-cancelled waybills"
that the user accidentally accepted, where no payment will ever happen
and counting them as outstanding distorts every analysis.

Reads `Financial_Analysis/supplier_archive.json` (already maintained by
the API). For each excluded TID present in `data["suppliers"]`:
- bumps total_paid to total_effective so total_debt → 0
- sets payment_scope = "excluded_from_analysis"
- writes the user-supplied reason into payment_scope_note
- adds excluded_from_analysis: true and exclusion_reason fields on
  the supplier row so the UI can render a badge / tooltip

Generic over any supplier; no hardcoded TIDs.
"""
import logging
import re
from pathlib import Path
from typing import Dict

from dashboard_pipeline import supplier_archive

logger = logging.getLogger(__name__)


def _extract_tid_from_org(org: str) -> str:
    if not isinstance(org, str):
        return ""
    m = re.search(r"\b(\d{9,11})\b", org)
    return m.group(1) if m else ""


def apply_excluded_from_analysis(data: dict, financial_analysis_dir: Path | None = None) -> dict:
    """Mutate `data["suppliers"]` for excluded suppliers. Returns the same
    dict for chaining."""
    suppliers = data.get("suppliers") or []
    if not suppliers:
        return data

    excluded_map: Dict[str, dict] = supplier_archive.excluded_entries(
        financial_analysis_dir=financial_analysis_dir,
    )
    if not excluded_map:
        return data

    matched = 0
    for s in suppliers:
        org = str(s.get("ორგანიზაცია") or "")
        tid = _extract_tid_from_org(org)
        if not tid or tid not in excluded_map:
            continue

        entry = excluded_map[tid]
        reason = str(entry.get("exclusion_reason") or "").strip() or "(მიზეზი მითითებული არ არის)"
        total_effective = float(s.get("total_effective") or 0)
        original_paid = float(s.get("total_paid") or 0)
        # Bump total_paid to cover total_effective so debt becomes 0.
        # Track how much was added by exclusion (separate from bank/manual).
        excluded_credit = max(0.0, total_effective - original_paid)
        s["bank_paid_pre_exclusion"] = original_paid
        s["excluded_credit"] = round(excluded_credit, 2)
        s["total_paid"] = round(original_paid + excluded_credit, 2)
        s["total_debt"] = 0.0
        s["payment_scope"] = "excluded_from_analysis"
        s["payment_scope_note"] = f"ანალიზიდან მოხსნილი — {reason}"
        s["excluded_from_analysis"] = True
        s["exclusion_reason"] = reason
        s["excluded_at"] = entry.get("excluded_at")
        matched += 1

    if matched:
        logger.info("excluded_from_analysis: applied to %d supplier(s)", matched)
    return data
