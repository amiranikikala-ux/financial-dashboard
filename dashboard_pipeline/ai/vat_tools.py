"""
AI tools for VAT reconciliation — Sprint 5.1

Three tools:
  - get_vat_reconciliation_month(period): one-month deep dive (main path per user ask)
  - explain_unaccounted_cash(period): triggers consultation flow for unclassified cash
  - record_cash_outflow(period, amount, purpose, category, vat_applies): user answer → journal

All tools are per-month scoped per user's explicit preference.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable, Dict, List, Optional

from dashboard_pipeline.vat_reconciliation import (
    CATEGORY_LABELS_KA,
    CATEGORY_VAT_DEFAULTS,
    UNACCOUNTED_CASH_THRESHOLD_GE,
    VAT_RATE,
    append_cash_outflow_entry,
)


def _validate_period(period: Any) -> Optional[str]:
    if not isinstance(period, str) or not re.match(r"^\d{4}-\d{2}$", period):
        return None
    return period


def _status_emoji(status: str) -> str:
    return {
        "green": "🟢",
        "yellow": "🟡",
        "red": "🔴",
        "no_declared_data": "⚪",
        "insufficient_data": "⚫",
    }.get(status, "⚪")


def _render_month_summary_ka(row: Dict[str, Any]) -> str:
    period = row["period"]
    status = row.get("status", "unknown")
    emoji = _status_emoji(status)
    max_pos = row.get("max_pos_ge") or 0
    bank = row.get("bank_card_ge") or 0
    cashreg_in = row.get("cashreg_in_ge") or 0
    cash_supplier = row.get("cash_supplier_ge") or 0
    cash_classified = row.get("cash_classified_ge") or 0
    cash_unaccounted = row.get("cash_unaccounted_ge") or 0
    declared = row.get("declared_ge")
    gap = row.get("gap_vs_declared_ge")
    dq = row.get("data_quality") or {}

    parts = [f"**{period}** · {emoji} {status}"]

    # Sprint 5.9 — insufficient_data case. Surface the warning FIRST before any
    # numbers so AI doesn't misread negative gap as over-declaration.
    if status == "insufficient_data" or dq.get("max_data_gap_suspected"):
        parts.append(
            "⚠️ **MAX retail_sales Excel ფაილი აკლია ამ თვისთვის** — "
            "gap არ ასახავს რეალობას (data gap, არა over-declaration). "
            "ატვირთე ფაილი `Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/` + "
            "`Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/`-ში და გააკეთე pipeline regen."
        )
    parts.append(f"MAX POS **{max_pos:,.0f} ₾** · ბანკი **{bank:,.0f} ₾** · cashreg_in **{cashreg_in:,.0f} ₾**")

    if cash_unaccounted >= UNACCOUNTED_CASH_THRESHOLD_GE:
        vat_liab = cash_unaccounted * VAT_RATE
        parts.append(
            f"⚠️ დაუხარჯვი ნაღდი **{cash_unaccounted:,.0f} ₾** "
            f"(მომწოდებელი {cash_supplier:,.0f} ₾ + კლასიფიცირებული {cash_classified:,.0f} ₾) — "
            f"პოტენც. დღგ **{vat_liab:,.0f} ₾**"
        )

    if declared is not None and gap is not None:
        parts.append(f"declared **{declared:,.0f} ₾** · gap **{gap:+,.0f} ₾**")
    elif declared is None:
        parts.append("declared: N/A")

    # Sprint 5.8 — surface per-shop breakdown when available (≥2 shops with
    # non-trivial activity). Lets the AI attribute under-declaration to a
    # specific store during audit defense.
    by_shop = row.get("by_shop") or {}
    material_shops = [
        (s, v) for s, v in by_shop.items() if (v.get("max_pos_ge") or 0) >= 1000
    ]
    if len(material_shops) >= 2:
        shop_fragments = []
        for shop, stats in sorted(
            material_shops,
            key=lambda kv: -float(kv[1].get("max_pos_ge") or 0),
        ):
            shop_max = float(stats.get("max_pos_ge") or 0)
            shop_cashreg = float(stats.get("cashreg_in_ge") or 0)
            shop_fragments.append(
                f"**{shop}** MAX {shop_max:,.0f} / cashreg {shop_cashreg:,.0f}"
            )
        parts.append("მაღაზიები: " + " · ".join(shop_fragments))

    return " · ".join(parts)


def _load_vat_row(data_loader: Callable[[], Dict[str, Any]], period: str) -> Optional[Dict[str, Any]]:
    data = data_loader()
    section = data.get("vat_reconciliation") or {}
    for row in section.get("by_month") or []:
        if row.get("period") == period:
            return row
    return None


# ---------------------------------------------------------------------------
# Tool 1: get_vat_reconciliation_month
# ---------------------------------------------------------------------------

def get_vat_reconciliation_month(
    data_loader: Callable[[], Dict[str, Any]],
    period: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns VAT reconciliation details for a single month — the main consumption path.

    Per user's explicit request: prefer single-month queries over full history dumps.
    """
    p = _validate_period(period)
    if not p:
        return {
            "error": "period must be YYYY-MM format (e.g. '2024-08')",
            "provided": period,
        }

    row = _load_vat_row(data_loader, p)
    if row is None:
        data = data_loader()
        section = data.get("vat_reconciliation") or {}
        available = [r.get("period") for r in (section.get("by_month") or [])]
        return {
            "error": f"Period '{p}' not present in vat_reconciliation.",
            "available_periods": available,
            "source": "data.json:vat_reconciliation",
        }

    data = data_loader()
    meta = (data.get("vat_reconciliation") or {}).get("methodology_ka", "")

    summary_ka = _render_month_summary_ka(row)

    return {
        "period": p,
        "row": row,
        "methodology_ka": meta,
        "summary_ka": summary_ka,
        "source": "data.json:vat_reconciliation",
        "vat_rate": VAT_RATE,
        "unaccounted_threshold_ge": UNACCOUNTED_CASH_THRESHOLD_GE,
    }


# ---------------------------------------------------------------------------
# Tool 2: explain_unaccounted_cash
# ---------------------------------------------------------------------------

def explain_unaccounted_cash(
    data_loader: Callable[[], Dict[str, Any]],
    period: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Surfaces the unaccounted cash for a month + generates a consultation prompt
    asking the user to classify. Flags 18% VAT liability if unanswered.
    """
    p = _validate_period(period)
    if not p:
        return {"error": "period must be YYYY-MM format (e.g. '2024-08')"}

    row = _load_vat_row(data_loader, p)
    if row is None:
        return {"error": f"Period '{p}' not present in vat_reconciliation."}

    cashreg_in = float(row.get("cashreg_in_ge") or 0)
    cash_supplier = float(row.get("cash_supplier_ge") or 0)
    cash_classified = float(row.get("cash_classified_ge") or 0)
    cash_unaccounted = float(row.get("cash_unaccounted_ge") or 0)
    vat_liability = cash_unaccounted * VAT_RATE

    classified_breakdown = row.get("cash_classified_by_category") or {}

    categories_hint = [
        {"id": cid, "label_ka": CATEGORY_LABELS_KA[cid], "vat_applies_default": CATEGORY_VAT_DEFAULTS[cid]}
        for cid in CATEGORY_LABELS_KA.keys()
    ]

    if cash_unaccounted < UNACCOUNTED_CASH_THRESHOLD_GE:
        prompt_ka = (
            f"**{p}**: ნაღდი დაუხარჯვი **{cash_unaccounted:,.0f} ₾** — "
            f"ზღვრული {UNACCOUNTED_CASH_THRESHOLD_GE:,.0f} ₾ ქვემოთ. მოქმედება არ ითხოვს."
        )
        needs_input = False
    else:
        prompt_ka = (
            f"**{p}**-ში ნაღდი ფული შემოვიდა **{cashreg_in:,.0f} ₾** (MAX POS − ბანკი). "
            f"მომწოდებელზე ხელზე გასული (`manual_payments`) — **{cash_supplier:,.0f} ₾**. "
            f"უკვე კლასიფიცირებული (`cash_outflow_journal`) — **{cash_classified:,.0f} ₾**. "
            f"\n\n❓ დარჩენილი **{cash_unaccounted:,.0f} ₾** სად წავიდა?\n\n"
            f"თუ ხარჯად ვერ დასაბუთდება → **18% დღგ = {vat_liability:,.0f} ₾** გადასახდელი.\n\n"
            f"გთხოვ განაწილება ერთ ან რამდენიმე კატეგორიას შორის: "
            f"ხელფასი_ხელზე / პერსონალური_ამოღება / მომწოდებელი_ხელზე_არდოკუმენტირებული / "
            f"ბიზნეს_ხარჯი_ქვითრით / ავანსი_თანამშრომელს / კლიენტის_დაბრუნება / უცნობი."
        )
        needs_input = True

    return {
        "period": p,
        "cashreg_in_ge": cashreg_in,
        "cash_supplier_ge": cash_supplier,
        "cash_classified_ge": cash_classified,
        "cash_unaccounted_ge": cash_unaccounted,
        "classified_breakdown": classified_breakdown,
        "potential_vat_liability_ge": vat_liability,
        "vat_rate": VAT_RATE,
        "threshold_ge": UNACCOUNTED_CASH_THRESHOLD_GE,
        "needs_user_input": needs_input,
        "prompt_ka": prompt_ka,
        "summary_ka": prompt_ka,
        "categories": categories_hint,
        "source": "data.json:vat_reconciliation",
    }


# ---------------------------------------------------------------------------
# Tool 3: record_cash_outflow
# ---------------------------------------------------------------------------

def record_cash_outflow(
    data_loader: Callable[[], Dict[str, Any]],
    project_root: Optional[str] = None,
    period: Optional[str] = None,
    amount_ge: Optional[float] = None,
    purpose_ka: Optional[str] = None,
    category: Optional[str] = None,
    vat_applies: Optional[bool] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Appends a user-classified cash outflow entry to cash_outflow_journal.csv.
    Returns the recorded entry + updated remaining unaccounted for the month.

    NOTE: The data.json is NOT regenerated automatically — user must re-run
    `python generate_dashboard_data.py` for the vat_reconciliation totals to
    reflect the new entry. The returned `remaining_unaccounted_preview_ge` is
    an in-memory preview only.
    """
    p = _validate_period(period)
    if not p:
        return {"error": "period must be YYYY-MM format (e.g. '2024-08')"}
    try:
        amt = float(amount_ge) if amount_ge is not None else 0.0
    except (TypeError, ValueError):
        return {"error": f"amount_ge must be a positive number, got {amount_ge!r}"}
    if amt <= 0:
        return {"error": f"amount_ge must be positive, got {amt}"}

    cat = str(category or "").strip().lower()
    if cat not in CATEGORY_VAT_DEFAULTS:
        return {
            "error": f"unknown category: {category!r}",
            "allowed_categories": sorted(CATEGORY_VAT_DEFAULTS.keys()),
        }

    root = project_root or os.getcwd()
    journal_path = os.path.join(root, "Financial_Analysis", "cash_outflow_journal.csv")

    try:
        entry = append_cash_outflow_entry(
            journal_path,
            period=p,
            amount_ge=amt,
            purpose_ka=purpose_ka or "",
            category=cat,
            vat_applies=vat_applies,
            notes=notes or "",
        )
    except Exception as exc:
        return {"error": f"failed to write journal: {exc}"}

    # Build preview of remaining unaccounted (current data.json + this entry)
    row = _load_vat_row(data_loader, p) or {}
    current_unaccounted = float(row.get("cash_unaccounted_ge") or 0)
    remaining_preview = max(0.0, current_unaccounted - amt)

    preview_vat = remaining_preview * VAT_RATE

    summary_ka = (
        f"✅ ჩაიწერა `{journal_path.split(os.sep)[-1]}`: **{p}** · **{amt:,.0f} ₾** · "
        f"{entry['category_label_ka']}"
        + (f" · დღგ 18%" if entry["vat_applies"] else " · დღგ არ იხდება")
        + (f" — {purpose_ka}" if purpose_ka else "")
        + f"\nდარჩენილი დაუხარჯვი (preview): **{remaining_preview:,.0f} ₾** · "
        + f"პოტენც. დღგ **{preview_vat:,.0f} ₾**."
        + "\n\n(მონაცემები ფიზიკურად განახლდება `python generate_dashboard_data.py`-ის შემდეგ.)"
    )

    return {
        "status": "ok",
        "period": p,
        "entry": entry,
        "previous_unaccounted_ge": current_unaccounted,
        "remaining_unaccounted_preview_ge": remaining_preview,
        "preview_vat_liability_ge": preview_vat,
        "journal_path": journal_path,
        "summary_ka": summary_ka,
        "notes_ka": ["Re-run pipeline to refresh data.json totals"],
        "requires_pipeline_rerun": True,
    }
