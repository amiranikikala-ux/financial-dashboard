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
    # Bank statements sometimes typo as "ოზურგეტი" (ტ instead of თ) — accept both.
    if "ოზურგეთი" in p or "ოზურგეტი" in p:
        return "ოზურგეთი"
    return None


def _infer_sales_date(deposit_date_str: str, store: str | None) -> str:
    """Shift a bank deposit date back to the cash-sale date it represents.

    Default: 1-day lag (deposit on day N = sales of day N-1).
    ოზურგეთი Monday = Fri+Sat+Sun bundle → attributed to Friday
    (matches daily_money_flow.py convention).
    """
    if not deposit_date_str:
        return deposit_date_str
    try:
        d = pd.to_datetime(deposit_date_str)
    except Exception:  # noqa: BLE001
        return deposit_date_str
    if pd.isna(d):
        return deposit_date_str
    if store == "ოზურგეთი" and d.weekday() == 0:
        return (d - pd.Timedelta(days=3)).strftime("%Y-%m-%d")
    return (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


_CATEGORY_LABEL_KA = {
    "salary": "ხელფასი",
    "rent": "ქირა",
    "utilities": "კომუნალური",
    "owner_withdraw": "მფლობელმა აიღო",
    "other": "სხვა",
}


def _load_cash_expense_lines(start: date, end: date) -> list[dict]:
    """Active cash-expense rows (salary/rent/etc. paid in cash) in [start, end]."""
    try:
        from dashboard_pipeline import cash_expenses_journal as _cej
        entries = _cej.read_active_entries()
    except Exception:  # noqa: BLE001
        return []
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    out: list[dict] = []
    for r in entries:
        d = str(r.get("date") or "")[:10]
        if not (s <= d <= e):
            continue
        try:
            amt = float(r.get("amount") or 0.0)
        except (TypeError, ValueError):
            continue
        if amt <= 0:
            continue
        cat = str(r.get("category") or "")
        out.append(
            {
                "date": d,
                "category": cat,
                "category_label": _CATEGORY_LABEL_KA.get(cat, cat or "სხვა"),
                "amount": round(amt, 2),
                "comment": str(r.get("comment") or ""),
            }
        )
    out.sort(key=lambda x: (x["date"], x["category"]))
    return out


def _load_manual_cash_supplier_lines(
    start: date,
    end: date,
    name_map: dict[str, str] | None = None,
) -> list[dict]:
    """Active manual cash payment rows in [start, end], enriched with name."""
    if not MANUAL_PAYMENTS_FILE.exists():
        return []
    try:
        df = pd.read_csv(MANUAL_PAYMENTS_FILE)
    except Exception:  # noqa: BLE001
        return []
    if df.empty:
        return []
    if "deleted_at" in df.columns:
        active = df[df["deleted_at"].isna() | (df["deleted_at"].astype(str).str.strip() == "")]
    else:
        active = df
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    in_window = active[(active["date"] >= s) & (active["date"] <= e)]
    nm = name_map or {}
    out: list[dict] = []
    for _, r in in_window.iterrows():
        tid = str(r.get("tax_id") or "").split(".")[0]
        out.append(
            {
                "date": str(r.get("date") or ""),
                "tax_id": tid,
                "name": nm.get(tid) or tid,
                "amount": round(float(r.get("amount") or 0.0), 2),
                "comment": str(r.get("comment") or ""),
            }
        )
    out.sort(key=lambda x: (x["date"], x["tax_id"]))
    return out


def _load_bank_cash_deposits(start: date, end: date) -> pd.DataFrame:
    """Read TBC + BOG parquet and return cash-deposit rows whose *sales date*
    (deposit_date shifted back by the typical lag) falls in [start, end].

    This makes the till-change calc match the owner's mental model: a deposit
    booked on May 1 that represents April 30 cash sales counts as April money.
    """
    frames: list[pd.DataFrame] = []
    for bank in ("tbc", "bog"):
        for parquet in (CACHE_ROOT / bank).glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet)
            except Exception:  # noqa: BLE001
                continue
            if df.empty:
                continue
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
        return pd.DataFrame(
            columns=["_day", "_bank", "_in", "_purpose", "_partner", "_sales_date"]
        )
    combined = pd.concat(frames, ignore_index=True)
    cash_mask = (
        (combined["_in"] > 0)
        & combined["_purpose"].str.contains(_CASH_PURPOSE_RE, regex=True, na=False)
    )
    cash = combined.loc[cash_mask].copy()
    cash["_sales_date"] = [
        _infer_sales_date(d, _detect_store(p))
        for d, p in zip(cash["_day"], cash["_purpose"])
    ]
    s = start.strftime("%Y-%m-%d")
    e = end.strftime("%Y-%m-%d")
    return cash[(cash["_sales_date"] >= s) & (cash["_sales_date"] <= e)].copy()


def compute_cash_till(
    cashier_day_breakdown: list[dict],
    *,
    start: date,
    end: date,
    supplier_name_map: dict[str, str] | None = None,
    last_complete_day: str | None = None,
) -> dict:
    """Compute per-store cash till change for the [start, end] window.

    Parameters
    ----------
    cashier_day_breakdown
        ``retail_sales.cashier_day_breakdown`` from data.json — each row has
        ``day``, ``object`` (store name), ``cash``, ``card``, ``revenue``.
    start, end
        Inclusive window.
    supplier_name_map
        Optional ``tax_id → org name`` lookup used to label the cash
        supplier-paid drill-down lines.
    last_complete_day
        ISO date string of the last day for which Megaplus data is fully
        loaded across all stores. When supplied, the effective end is
        capped at this day so that the lag-shift logic doesn't pair
        complete bank deposits against partial / missing Megaplus sales —
        which previously produced phantom "outgoing till" amounts at the
        window edge (e.g. 2,330 ₾ on May 13 because a May 14 bank deposit
        shifted onto a Megaplus day with only morning sales captured).

    Returns
    -------
    dict with ``period`` / ``stores`` / ``totals`` plus ``*_lines`` arrays
    that back the Home drill-down UI.
    """
    s_iso = start.strftime("%Y-%m-%d")
    e_iso = end.strftime("%Y-%m-%d")
    if last_complete_day and last_complete_day < e_iso:
        e_iso = last_complete_day
        end = pd.to_datetime(last_complete_day).date()

    # Cash sales per store — aggregate per-day across cashiers for drill-down.
    sales_daily: dict[str, dict[str, float]] = {st: {} for st in KNOWN_STORES}
    for r in cashier_day_breakdown or []:
        d = str(r.get("day") or "")[:10]
        if not (s_iso <= d <= e_iso):
            continue
        obj = r.get("object") or ""
        if obj not in sales_daily:
            continue
        amt = float(r.get("cash") or 0.0)
        if amt == 0:
            continue
        sales_daily[obj][d] = sales_daily[obj].get(d, 0.0) + amt
    sales_lines: dict[str, list[dict]] = {
        st: [
            {"day": d, "amount": round(amt, 2)}
            for d, amt in sorted(sales_daily[st].items())
        ]
        for st in KNOWN_STORES
    }

    # Cash deposits per store — keep per-tx lines. Each row's "day" is the
    # inferred sales date (when cash was earned), with bank_day kept alongside
    # so the owner can still see the original booking date in the drill-down.
    deposit_lines: dict[str, list[dict]] = {st: [] for st in KNOWN_STORES}
    unattributed_deposit_lines: list[dict] = []
    df = _load_bank_cash_deposits(start, end)
    for _, row in df.iterrows():
        store = _detect_store(str(row.get("_purpose") or ""))
        amt = float(row.get("_in") or 0.0)
        sales_d = str(row.get("_sales_date") or "")
        bank_d = str(row.get("_day") or "")
        line = {
            "day": sales_d or bank_d,
            "bank_day": bank_d,
            "bank": str(row.get("_bank") or ""),
            "amount": round(amt, 2),
            "purpose": str(row.get("_purpose") or ""),
        }
        if store:
            deposit_lines[store].append(line)
        else:
            unattributed_deposit_lines.append(line)
    for st in KNOWN_STORES:
        deposit_lines[st].sort(key=lambda x: x["day"])
    unattributed_deposit_lines.sort(key=lambda x: x["day"])

    stores_out: dict[str, dict] = {}
    for st in KNOWN_STORES:
        cs = round(sum(r["amount"] for r in sales_lines[st]), 2)
        cd = round(sum(r["amount"] for r in deposit_lines[st]), 2)
        stores_out[st] = {
            "cash_sales": cs,
            "cash_deposits": cd,
            "till_change": round(cs - cd, 2),
            "sales_lines": sales_lines[st],
            "deposit_lines": deposit_lines[st],
        }

    total_sales = round(sum(s["cash_sales"] for s in stores_out.values()), 2)
    unattributed_deposits = round(
        sum(r["amount"] for r in unattributed_deposit_lines), 2
    )
    total_deposits = round(
        sum(s["cash_deposits"] for s in stores_out.values()) + unattributed_deposits, 2
    )

    # Manual cash payments to suppliers — shared across both tills, no store
    # attribution available. Surfaced as a separate top-level deduction.
    supplier_paid_lines = _load_manual_cash_supplier_lines(
        start, end, supplier_name_map
    )
    cash_supplier_paid = round(sum(r["amount"] for r in supplier_paid_lines), 2)

    # Cash expenses (salary / rent / utilities etc.) — also till outflow.
    cash_expense_lines = _load_cash_expense_lines(start, end)
    cash_expenses_paid = round(sum(r["amount"] for r in cash_expense_lines), 2)

    return {
        "period": {"from": s_iso, "to": e_iso},
        "stores": stores_out,
        "totals": {
            "cash_sales": total_sales,
            "cash_deposits": total_deposits,
            "cash_supplier_paid": cash_supplier_paid,
            "cash_expenses_paid": cash_expenses_paid,
            "till_change": round(total_sales - total_deposits, 2),
            "real_till_change": round(
                total_sales - total_deposits - cash_supplier_paid - cash_expenses_paid,
                2,
            ),
            "unattributed_deposits": unattributed_deposits,
            "supplier_paid_lines": supplier_paid_lines,
            "cash_expense_lines": cash_expense_lines,
            "unattributed_deposit_lines": unattributed_deposit_lines,
        },
    }


__all__ = ["compute_cash_till", "KNOWN_STORES"]
