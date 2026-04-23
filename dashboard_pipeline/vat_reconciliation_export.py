"""
VAT reconciliation → Excel export (Sprint 5.4).

Produces a bookkeeper/auditor-friendly xlsx with:
  * **Monthly** sheet — every month × every pipeline-computed field
  * **Summary** sheet — cumulative totals + methodology note
  * **Cash classification** sheet — entries from cash_outflow_journal.csv
    (per-category breakdown per month) when any classified entries exist

The workbook takes (vat_reconciliation_bundle, cash_journal_path) and writes
to an io.BytesIO — the caller decides where to persist it (API response
download, local file, etc.).
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import pandas as pd


_MONTHLY_COLUMNS = [
    ("period", "თვე"),
    ("declared_ge", "declared (ბუღალტერი, net) ₾"),
    ("max_pos_ge", "MAX retail ₾"),
    ("tbc_pos_ge", "TBC POS ₾"),
    ("bog_pos_ge", "BOG POS ₾"),
    ("bank_card_ge", "bank_card (TBC+BOG, gross) ₾"),
    ("cashreg_in_ge", "cashreg_in (gross) ₾"),
    ("invoices_ge", "invoices ა/ფ (bruto) ₾"),
    ("total_real_ge", "📦 total_real (gross) ₾"),
    ("total_real_net_ge", "total_real (net = gross ÷ 1.18) ₾"),
    ("cash_supplier_ge", "cash_supplier ₾"),
    ("cash_classified_ge", "cash_classified ₾"),
    ("cash_unaccounted_ge", "🟡 cash_unaccounted ₾"),
    ("vat_on_unaccounted_ge", "VAT on unaccounted (18%) ₾"),
    ("gap_vs_declared_ge", "🔴 gap (net basis, primary) ₾"),
    ("gap_gross_ge", "gap (gross basis, alternative) ₾"),
    ("audit_total_ge", "audit total_real (net) ₾"),
    ("status", "status"),
    ("needs_user_input", "needs classification"),
]

_STATUS_LABELS_KA = {
    "green": "🟢 OK",
    "yellow": "🟡 ყურადღება",
    "red": "🔴 ხარვეზი",
    "no_declared_data": "⚪ declared არ მაქვს",
    "insufficient_data": "⚫ MAX data აკლია",
}

_METHODOLOGY_KA = [
    "მეთოდოლოგია — VAT reconciliation (Sprint 5.1–5.11)",
    "",
    "1. bank_card = TBC POS + BOG POS (ფიზიკური ტერმინალების ID-ით — Sprint 5.2)",
    "   (GROSS: bank deposit-ები commission-ის შემდეგ, VAT-ის ჩათვლით)",
    "2. cashreg_in = max(0, MAX retail − bank_card)  ← nonnegative floor",
    "3. total_real (GROSS) = cashreg_in + bank_card + invoices",
    "4. total_real_net = total_real / 1.18  ← unit conversion (Sprint 5.11)",
    "5. gap (PRIMARY, net basis) = total_real_net − declared",
    "   (aligns with audit's methodology: declared is NET of VAT)",
    "6. gap (ALTERNATIVE, gross basis) = total_real − declared × 1.18",
    "7. VAT exposure = cash_unaccounted × 18%  (worst-case, classification-მდე)",
    "",
    "Sprint 5.11 unit-error fix:",
    "  • BEFORE: gap_vs_declared_ge = total_real (gross) − declared (net) — UNIT-MIXED",
    "    (inflated gap by declared × 0.18 systematically)",
    "  • AFTER: gap_vs_declared_ge = (total_real ÷ 1.18) − declared — NET-BASIS",
    "    (matches audit's own 'სხვაობა ბრუნვაში' column methodology)",
    "  • Per-month cross-check (2024-08, 2025-08, 2025-12): pipeline_gross ≈ audit_net × 1.18",
    "    within 0.3% where pipeline data is complete. Larger residuals mark pipeline",
    "    coverage gaps (missing MAX/BOG/TBC data), NOT pipeline-vs-audit disagreement.",
    "",
    "წყაროები (ground-truth rank):",
    "  • MAX retail — Financial_Analysis/გაყიდული პროდუქტები * (GROSS)",
    "  • TBC POS — თბს ბანკი ამონაწერი, 5 physical terminals (GROSS)",
    "    (RS014189, SH079927, SH046092, SH034467, SH060853)",
    "  • BOG POS — ბოგ ბანკი ამონაწერი, pattern-matched (GROSS)",
    "  • invoices_issued — Financial_Analysis/ანგარიშ ფაქტურები/report*.xls (BRUTO/GROSS)",
    "  • declared — გაანგარიშება შპს ჯეო ფუდთაიმი.xlsx (NET of VAT)",
    "  • cash classification — Financial_Analysis/cash_outflow_journal.csv",
    "",
    "cash classification → VAT exposure ამცირებს:",
    "  • salary_cash, personal_withdrawal, unknown — VAT დარჩება",
    "  • supplier_undocumented, business_expense, advance_to_employee,",
    "    return_to_customer — VAT გაქრება კატეგორიის default-ით",
]


def _format_cell(value):
    """Return the value in a form pandas/Excel can store faithfully."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "დიახ" if value else "—"
    return value


def _build_monthly_df(by_month: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for m in by_month:
        row = {}
        for key, label in _MONTHLY_COLUMNS:
            if key == "status":
                row[label] = _STATUS_LABELS_KA.get(m.get("status"), m.get("status") or "")
            else:
                row[label] = _format_cell(m.get(key))
        rows.append(row)
    return pd.DataFrame(rows, columns=[lbl for _, lbl in _MONTHLY_COLUMNS])


def _compute_summary(by_month: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cumulative totals — mirrors dashboard summary card math."""
    s = {
        "declared_ge": 0.0,
        "max_pos_ge": 0.0,
        "bank_card_ge": 0.0,
        "cashreg_in_ge": 0.0,
        "invoices_ge": 0.0,
        "total_real_ge": 0.0,
        "total_real_net_ge": 0.0,
        "cash_unaccounted_ge": 0.0,
        "cash_classified_ge": 0.0,
        "cash_supplier_ge": 0.0,
        "gap_vs_declared_ge": 0.0,
        "gap_gross_ge": 0.0,
        "months_total": len(by_month),
        "months_with_declared": 0,
        "months_red": 0,
        "months_yellow": 0,
        "months_green": 0,
    }
    for m in by_month:
        for k in (
            "max_pos_ge", "bank_card_ge", "cashreg_in_ge", "invoices_ge",
            "total_real_ge", "total_real_net_ge",
            "cash_unaccounted_ge", "cash_classified_ge",
            "cash_supplier_ge",
        ):
            s[k] += float(m.get(k) or 0)
        if m.get("declared_ge") is not None:
            s["declared_ge"] += float(m["declared_ge"])
            s["months_with_declared"] += 1
        if m.get("gap_vs_declared_ge") is not None:
            s["gap_vs_declared_ge"] += float(m["gap_vs_declared_ge"])
        if m.get("gap_gross_ge") is not None:
            s["gap_gross_ge"] += float(m["gap_gross_ge"])
        status = m.get("status")
        if status == "red":
            s["months_red"] += 1
        elif status == "yellow":
            s["months_yellow"] += 1
        elif status == "green":
            s["months_green"] += 1
    s["vat_exposure_ge"] = s["cash_unaccounted_ge"] * 0.18
    return s


def _build_summary_df(s: Dict[str, Any]) -> pd.DataFrame:
    undeclared_pct = (
        (s["gap_vs_declared_ge"] / s["declared_ge"] * 100.0)
        if s["declared_ge"] > 0 else 0.0
    )
    rows = [
        ("Declared (ბუღალტერი, net)", round(s["declared_ge"], 2)),
        ("MAX retail (total register)", round(s["max_pos_ge"], 2)),
        ("bank_card (TBC+BOG, gross)", round(s["bank_card_ge"], 2)),
        ("cashreg_in (MAX − bank_card, gross)", round(s["cashreg_in_ge"], 2)),
        ("invoices (ა/ფ bruto)", round(s["invoices_ge"], 2)),
        ("📦 total_real (gross)", round(s["total_real_ge"], 2)),
        ("📦 total_real (net = gross ÷ 1.18)", round(s.get("total_real_net_ge", 0.0), 2)),
        ("", ""),
        ("🔴 Gap vs declared (net basis — primary)", round(s["gap_vs_declared_ge"], 2)),
        ("Gap % of declared", f"{undeclared_pct:.1f}%"),
        ("Gap vs declared (gross basis — alternative)", round(s.get("gap_gross_ge", 0.0), 2)),
        ("", ""),
        ("cash_supplier (manual_payments)", round(s["cash_supplier_ge"], 2)),
        ("cash_classified (journal)", round(s["cash_classified_ge"], 2)),
        ("🟡 cash_unaccounted", round(s["cash_unaccounted_ge"], 2)),
        ("VAT exposure (18% of unaccounted)", round(s["vat_exposure_ge"], 2)),
        ("", ""),
        ("Months total", s["months_total"]),
        ("Months with declared data", s["months_with_declared"]),
        ("🔴 Red months", s["months_red"]),
        ("🟡 Yellow months", s["months_yellow"]),
        ("🟢 Green months", s["months_green"]),
    ]
    return pd.DataFrame(rows, columns=["მაჩვენებელი", "ღირებულება"])


def _build_classification_df(by_month: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    """Cash classification per month × category. Returns None if all empty."""
    rows = []
    for m in by_month:
        per_cat = m.get("cash_classified_by_category") or {}
        if not per_cat:
            continue
        for cat, sub in per_cat.items():
            total = float((sub or {}).get("total_ge") or 0)
            vat = float((sub or {}).get("vat_applies_ge") or 0)
            count = int((sub or {}).get("entries_count") or 0)
            rows.append({
                "თვე": m.get("period"),
                "კატეგორია": cat,
                "ჩანაწერები": count,
                "ჯამი ₾": round(total, 2),
                "დღგ გადასახდელი ₾": round(vat, 2),
            })
    if not rows:
        return None
    return pd.DataFrame(rows, columns=["თვე", "კატეგორია", "ჩანაწერები", "ჯამი ₾", "დღგ გადასახდელი ₾"])


def _build_methodology_df() -> pd.DataFrame:
    return pd.DataFrame({"განმარტება": _METHODOLOGY_KA})


def build_vat_export_bytes(vat_bundle: Dict[str, Any]) -> bytes:
    """
    Build a VAT reconciliation Excel workbook (BytesIO).

    Args:
        vat_bundle: the `vat_reconciliation` section from data.json
            (must contain `by_month`, optionally `summary`).

    Returns:
        bytes — the full .xlsx workbook contents.
    """
    import openpyxl  # noqa: F401  — ensures engine available, raises otherwise
    by_month = vat_bundle.get("by_month") or []
    monthly_df = _build_monthly_df(by_month)
    summary_df = _build_summary_df(_compute_summary(by_month))
    methodology_df = _build_methodology_df()
    classification_df = _build_classification_df(by_month)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        monthly_df.to_excel(writer, sheet_name="Monthly", index=False)
        if classification_df is not None and not classification_df.empty:
            classification_df.to_excel(writer, sheet_name="Cash_classification", index=False)
        methodology_df.to_excel(writer, sheet_name="Methodology", index=False)

        # Auto-fit column widths (rough: max chars × 1.1, capped at 40)
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = 10
                for cell in col:
                    try:
                        v = "" if cell.value is None else str(cell.value)
                        max_len = max(max_len, min(len(v), 60))
                    except Exception:
                        pass
                letter = col[0].column_letter
                sheet.column_dimensions[letter].width = max_len * 1.1

    return buf.getvalue()
