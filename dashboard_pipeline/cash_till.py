"""Per-store cash till computation.

Answers: "how much physical cash should be in my register right now, per
store?"

Formula per store over a period:
    till_change = cash_sales(period, store) − cash_deposits_to_bank(period, store)

`cash_sales` comes from Megaplus daily_trend × cashier_day_breakdown (cash
column per store per day).

`cash_deposits` come from the bank parquet caches — rows recognised as
"ნავაჭრის ჩარიცხვა" terminal deposits, where the purpose text contains
"დვაბზუ" or "ოზურგეთი" (the same detection rule daily_money_flow.py
already uses to re-attribute deposit dates).

Cash journal expenses (salary/rent paid in cash) come from ONE of the two
tills — we can't tell which from the journal — so we return the total
separately and let the UI display it as a shared deduction.

This module is read-only / pure-computation; no caches written.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = ROOT / "Financial_Analysis" / "cache"
MANUAL_PAYMENTS_FILE = (
    ROOT / "Financial_Analysis" / "manual_payments_journal.csv"
)
KNOWN_STORES = ("დვაბზუ", "ოზურგეთი")

# Cash deposit detection — the bank `დანიშნულება` / `ოპერაციის შინაარსი`
# typically reads e.g. "33001022152; სოფ ოზურგეთი ნავაჭრი" or "ნავაჭრი
# თანხა დვაბზუ". Just stem-match "ნავაჭრი" — covers ნავაჭრი / ნავაჭრის /
# ნავაჭრით etc.
_CASH_PURPOSE_RE = re.compile(r"ნავაჭრი")


def _detect_store(purpose: str) -> str | None:
    p = purpose or ""
    if "დვაბზუ" in p or "დუვაბზუ" in p:
        return "დვაბზუ"
    if "ოზურგეთი" in p:
        return "ოზურგეთი"
    return None


def _load_manual_cash_supplier_payments(start: date, end: date) -> float:
    """Sum of active manual cash payments to suppliers in [start, end].

    Manual payments are owner-entered records of cash handed directly to a
    supplier (cigarette importers like ჯიდიაი, plus general suppliers via
    the browser entry UI). Rows with a non-empty ``deleted_at`` are
    excluded.
    """
    if not MANUAL_PAYMENTS_FILE.exists():
        return 0.0
    try:
        df = pd.read_csv(MANUAL_PAYMENTS_FILE)
    except Exception:  # noqa: BLE001
        return 0.0
    if df.empty:
        return 0.0
    # Active rows only (deleted_at empty / NaN)
    if "deleted_at" in df.columns:
        active = df[df["deleted_at"].isna() | (df["deleted_at"].astype(str).str.strip() == "")]
    else:
        active = df
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    in_window = active[(active["date"] >= s) & (active["date"] <= e)]
    return float(in_window["amount"].sum())


def _load_bank_cash_deposits(start: date, end: date) -> pd.DataFrame:
    """Read TBC + BOG parquet, return cash-deposit rows in [start, end]."""
    frames: list[pd.DataFrame] = []
    for bank in ("tbc", "bog"):
        for parquet in (CACHE_ROOT / bank).glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet)
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
            # Normalize columns across banks.
            if bank == "tbc":
                df["_in"] = pd.to_numeric(df.get("შემოსული თანხა", 0), errors="coerce").fillna(0.0)
                df["_purpose"] = df.get("დანიშნულება", "").astype(str)
                df["_partner"] = df.get("პარტნიორი", "").astype(str)
            else:
                df["_in"] = pd.to_numeric(df.get("კრედიტი", 0), errors="coerce").fillna(0.0)
                df["_purpose"] = df.get("ოპერაციის შინაარსი", "").astype(str)
                df["_partner"] = df.get("გამგზავნის დასახელება", "").astype(str)
            df["_day"] = pd.to_datetime(df["თარიღი"], errors="coerce").dt.strftime("%Y-%m-%d")
            df["_bank"] = bank.upper()
            frames.append(df[["_day", "_bank", "_in", "_purpose", "_partner"]])
    if not frames:
        return pd.DataFrame(columns=["_day", "_bank", "_in", "_purpose", "_partner"])
    combined = pd.concat(frames, ignore_index=True)
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    mask = (
        (combined["_day"] >= s)
        & (combined["_day"] <= e)
        & (combined["_in"] > 0)
        & combined["_purpose"].str.contains(_CASH_PURPOSE_RE, regex=True, na=False)
    )
    return combined.loc[mask].copy()


def compute_cash_till(
    cashier_day_breakdown: list[dict],
    *,
    start: date,
    end: date,
) -> dict:
    """Compute per-store cash till change for the [start, end] window.

    Parameters
    ----------
    cashier_day_breakdown
        ``retail_sales.cashier_day_breakdown`` from data.json — each row has
        ``day``, ``object`` (store name), ``cash``, ``card``, ``revenue``.
    start, end
        Inclusive window.

    Returns
    -------
    dict with keys:
        - ``period`` — {"from", "to"}
        - ``stores`` — per-store dict with cash_sales / cash_deposits /
          till_change / day_count
        - ``totals`` — combined cash_sales / cash_deposits / till_change
    """
    s_iso = start.strftime("%Y-%m-%d")
    e_iso = end.strftime("%Y-%m-%d")

    # Cash sales per store
    sales_per_store: dict[str, float] = {st: 0.0 for st in KNOWN_STORES}
    for r in cashier_day_breakdown or []:
        d = str(r.get("day") or "")[:10]
        if not (s_iso <= d <= e_iso):
            continue
        obj = r.get("object") or ""
        if obj not in sales_per_store:
            continue
        sales_per_store[obj] += float(r.get("cash") or 0.0)

    # Cash deposits per store
    deposits_per_store: dict[str, float] = {st: 0.0 for st in KNOWN_STORES}
    unattributed_deposits = 0.0
    df = _load_bank_cash_deposits(start, end)
    for _, row in df.iterrows():
        store = _detect_store(str(row.get("_purpose") or ""))
        amt = float(row.get("_in") or 0.0)
        if store:
            deposits_per_store[store] += amt
        else:
            unattributed_deposits += amt

    stores_out: dict[str, dict] = {}
    for st in KNOWN_STORES:
        cs = round(sales_per_store[st], 2)
        cd = round(deposits_per_store[st], 2)
        stores_out[st] = {
            "cash_sales": cs,
            "cash_deposits": cd,
            "till_change": round(cs - cd, 2),
        }

    total_sales = round(sum(sales_per_store.values()), 2)
    total_deposits = round(sum(deposits_per_store.values()) + unattributed_deposits, 2)

    # Manual cash payments to suppliers — shared across both tills, no store
    # attribution available. Surfaced as a separate top-level deduction.
    cash_supplier_paid = round(_load_manual_cash_supplier_payments(start, end), 2)

    return {
        "period": {"from": s_iso, "to": e_iso},
        "stores": stores_out,
        "totals": {
            "cash_sales": total_sales,
            "cash_deposits": total_deposits,
            "cash_supplier_paid": cash_supplier_paid,
            "till_change": round(total_sales - total_deposits, 2),
            "real_till_change": round(
                total_sales - total_deposits - cash_supplier_paid, 2
            ),
            "unattributed_deposits": round(unattributed_deposits, 2),
        },
    }


__all__ = ["compute_cash_till", "KNOWN_STORES"]
