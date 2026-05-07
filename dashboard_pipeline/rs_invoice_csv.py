"""rs.ge invoice CSV parser — buyer (incoming) + seller (outgoing) registries.

Parses the manually-downloaded CSVs from rs.ge into normalized DataFrames the
pipeline can plug in directly. Handles the 16 known malformed rows in the
real export by logging+skipping (never silent drop).

Source files (under `Financial_Analysis/რს ფაქტურები/`):
    - "ფაქტურები მყიდველი.csv"   — buyer-side: invoices suppliers issued to us
    - "ფაქტურები გამყიდველი.csv" — seller-side: invoices we issued (line items per row)

Public API:
    parse_buyer_invoices(path)   → DataFrame[InvoiceRow]
    parse_seller_invoices(path)  → DataFrame[InvoiceRow] (grouped by ID)
    extract_tin_and_name(text)   → (tin: str|None, name: str)
    parse_invoice_date(text)     → datetime|None
    split_waybill_field(text)    → list[str]
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

GEORGIAN_MONTH_ABBREVS = {
    "იან": 1, "თებ": 2, "მარ": 3, "აპრ": 4,
    "მაი": 5, "ივნ": 6, "ივლ": 7, "აგვ": 8,
    "სექ": 9, "ოქტ": 10, "ნოე": 11, "დეკ": 12,
}

_DATE_RE = re.compile(r"^\s*(\d{1,2})-([^-\s]+)-(\d{4})(?:\s+(\d{1,2}):(\d{2}):(\d{2}))?\s*$")
_TIN_RE = re.compile(r"^\s*\((\d+)(?:-დღგ)?\)\s*(.*)$")


def parse_invoice_date(value) -> datetime | None:
    """Parse rs.ge date format: '01-აგვ-2026 13:19:12' or '01-აგვ-2026'.

    Returns None for blank, NaN, or unparseable input. Caller decides whether
    to log/skip.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none"):
        return None
    m = _DATE_RE.match(text)
    if not m:
        return None
    day, month_abbr, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = GEORGIAN_MONTH_ABBREVS.get(month_abbr)
    if month is None:
        return None
    hour = int(m.group(4)) if m.group(4) else 0
    minute = int(m.group(5)) if m.group(5) else 0
    second = int(m.group(6)) if m.group(6) else 0
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def extract_tin_and_name(text) -> tuple[str | None, str]:
    """Parse rs.ge counterparty format `(TIN-დღგ) name` or `(TIN) name`.

    Returns (tin, name). tin is None if no leading numeric paren found.
    Empty input → (None, '').
    """
    if text is None:
        return None, ""
    s = str(text).strip()
    if not s or s.lower() in ("nan", "none"):
        return None, ""
    m = _TIN_RE.match(s)
    if not m:
        return None, s
    tin = m.group(1)
    name = m.group(2).strip()
    return tin, name


def split_waybill_field(text) -> list[str]:
    """Parse comma-separated waybill numbers field — handles trailing commas
    and stray whitespace. Returns deduped, order-preserved list of non-empty
    strings.
    """
    if text is None:
        return []
    s = str(text)
    if not s.strip() or s.lower() in ("nan", "none"):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for piece in s.split(","):
        t = piece.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _to_float(value) -> float | None:
    """Best-effort numeric conversion. Returns None for unparseable.
    Treats malformed CSV cells (date-strings landing in number columns) as None.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().replace(",", ".")
    if not s or s.lower() in ("nan", "none"):
        return None
    if "-" in s and any(ch.isalpha() for ch in s):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


@dataclass
class ParseStats:
    rows_total: int = 0
    rows_valid: int = 0
    rows_skipped: int = 0
    skip_reasons: dict | None = None

    def __post_init__(self):
        if self.skip_reasons is None:
            self.skip_reasons = {}

    def note_skip(self, reason: str) -> None:
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1
        self.rows_skipped += 1


def parse_buyer_invoices(path: str | Path) -> tuple[pd.DataFrame, ParseStats]:
    """Parse the buyer-side CSV (incoming invoices: suppliers → us).

    Returns (DataFrame, stats). DataFrame columns:
        invoice_id, series, status, supplier_tax_id, supplier_name,
        date_issued, date_op, amount_ge, vat_ge, quantity, decl_period,
        waybills (list[str]), confirmed_at, raw_row_index
    """
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    stats = ParseStats(rows_total=len(raw))

    out_rows: list[dict] = []
    for idx, row in raw.iterrows():
        amount = _to_float(row.get("თანხა"))
        if amount is None:
            stats.note_skip("amount_unparseable")
            logger.warning(
                "rs_invoice buyer row %d: skipping (amount unparseable: %r)",
                idx, row.get("თანხა")
            )
            continue

        date_issued = parse_invoice_date(row.get("გამოწერის თარ."))
        if date_issued is None:
            stats.note_skip("date_issued_unparseable")
            logger.warning(
                "rs_invoice buyer row %d: skipping (date_issued unparseable: %r)",
                idx, row.get("გამოწერის თარ.")
            )
            continue

        sup_tin, sup_name = extract_tin_and_name(row.get("გამყიდველი"))
        if not sup_tin:
            stats.note_skip("supplier_tin_missing")
            logger.warning(
                "rs_invoice buyer row %d: skipping (supplier TIN missing: %r)",
                idx, row.get("გამყიდველი")
            )
            continue

        out_rows.append({
            "invoice_id": str(row.get("ID") or "").strip(),
            "series": str(row.get("სერია №") or "").strip(),
            "status": str(row.get("სტატუსი") or "").strip(),
            "supplier_tax_id": sup_tin,
            "supplier_name": sup_name,
            "date_issued": date_issued,
            "date_op": parse_invoice_date(row.get("ოპერაციის თარ.")),
            "amount_ge": round(amount, 2),
            "vat_ge": round(_to_float(row.get("დღგ-ს თანხა")) or 0.0, 2),
            "quantity": _to_float(row.get("რაოდენობა")),
            "decl_period": str(row.get("დეკლარაციის პერიოდი (თვე,წელი).") or "").strip(),
            "waybills": split_waybill_field(row.get("ზედნადები")),
            "confirmed_at": parse_invoice_date(row.get("დადასტურების თარ.")),
            "raw_row_index": int(idx),
        })
        stats.rows_valid += 1

    df = pd.DataFrame(out_rows)
    logger.info(
        "rs_invoice buyer parsed: %d/%d valid, %d skipped (%s)",
        stats.rows_valid, stats.rows_total, stats.rows_skipped,
        ", ".join(f"{k}={v}" for k, v in (stats.skip_reasons or {}).items()) or "—",
    )
    return df, stats


def parse_seller_invoices(path: str | Path) -> tuple[pd.DataFrame, ParseStats]:
    """Parse the seller-side CSV (outgoing invoices: us → customers).

    Source CSV is line-item-exploded (one row per product line). This function
    groups by invoice ID so the returned DataFrame has one row per invoice with
    aggregated amounts and an `items` list of (description, unit, qty, value, vat).
    """
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    stats = ParseStats(rows_total=len(raw))

    item_rows: list[dict] = []
    for idx, row in raw.iterrows():
        invoice_id = str(row.get("ID") or "").strip()
        value = _to_float(row.get("ღირებულება დღგ და აქციზის ჩათვლით"))
        if not invoice_id or value is None:
            stats.note_skip("missing_id_or_value")
            logger.warning(
                "rs_invoice seller row %d: skipping (id=%r value=%r)",
                idx, invoice_id, row.get("ღირებულება დღგ და აქციზის ჩათვლით")
            )
            continue

        date_issued = parse_invoice_date(row.get("გამოწერის თარ."))
        cust_tin, cust_name = extract_tin_and_name(row.get("მყიდველი"))
        seller_tin, seller_name = extract_tin_and_name(row.get("გამყიდველი"))

        item_rows.append({
            "invoice_id": invoice_id,
            "series": str(row.get("სერია №") or "").strip(),
            "customer_tax_id": cust_tin,
            "customer_name": cust_name,
            "seller_tax_id": seller_tin,
            "seller_name": seller_name,
            "date_issued": date_issued,
            "date_op": parse_invoice_date(row.get("ოპერაციის თარ.")),
            "item_description": str(row.get("საქონელი / მომსახურება") or "").strip(),
            "item_unit": str(row.get("ზომის ერთეული") or "").strip(),
            "item_qty": _to_float(row.get("რაოდ.")),
            "item_value_ge": round(value, 2),
            "item_vat_ge": round(_to_float(row.get("დღგ")) or 0.0, 2),
            "item_excise_ge": round(_to_float(row.get("აქციზი")) or 0.0, 2),
            "taxation": str(row.get("დაბეგვრა") or "").strip(),
            "note": str(row.get("შენიშვნა") or "").strip(),
            "raw_row_index": int(idx),
        })
        stats.rows_valid += 1

    items_df = pd.DataFrame(item_rows)
    if items_df.empty:
        logger.info("rs_invoice seller parsed: 0 items, returning empty frame")
        return items_df, stats

    grouped: list[dict] = []
    for invoice_id, sub in items_df.groupby("invoice_id"):
        first = sub.iloc[0]
        grouped.append({
            "invoice_id": invoice_id,
            "series": first["series"],
            "customer_tax_id": first["customer_tax_id"],
            "customer_name": first["customer_name"],
            "seller_tax_id": first["seller_tax_id"],
            "seller_name": first["seller_name"],
            "date_issued": first["date_issued"],
            "date_op": first["date_op"],
            "amount_ge": round(float(sub["item_value_ge"].sum()), 2),
            "vat_ge": round(float(sub["item_vat_ge"].sum()), 2),
            "excise_ge": round(float(sub["item_excise_ge"].sum()), 2),
            "items": [
                {
                    "description": r["item_description"],
                    "unit": r["item_unit"],
                    "qty": r["item_qty"],
                    "value_ge": r["item_value_ge"],
                    "vat_ge": r["item_vat_ge"],
                    "excise_ge": r["item_excise_ge"],
                    "taxation": r["taxation"],
                }
                for _, r in sub.iterrows()
            ],
            "line_count": int(len(sub)),
        })

    df = pd.DataFrame(grouped)
    logger.info(
        "rs_invoice seller parsed: %d items → %d invoices, %d skipped (%s)",
        stats.rows_valid, len(df), stats.rows_skipped,
        ", ".join(f"{k}={v}" for k, v in (stats.skip_reasons or {}).items()) or "—",
    )
    return df, stats
