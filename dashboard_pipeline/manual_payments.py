"""
manual_payments.py — ნაღდი/სხვა არხით გადახდის ჟურნალი (manual_payments.csv).

Extracted from generate_dashboard_data.py lines 6861-7068.
"""

import os
import re

import pandas as pd

from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.file_utils import _financial_analysis_path, clean_id

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------

def manual_payments_csv_path():
    return _financial_analysis_path("manual_payments.csv")


# ---------------------------------------------------------------------------
# Journal column finder
# ---------------------------------------------------------------------------

def _journal_find_col(columns, alternatives):
    low = {str(n).strip().lower().replace(" ", "_"): n for n in columns}
    for a in alternatives:
        a2 = str(a).strip().lower().replace(" ", "_")
        if a2 in low:
            return low[a2]
    for n in columns:
        ns = str(n).strip()
        if ns in alternatives:
            return n
    # Excel/ქართული სათაურები: „თანხა (₾)", „საგადასახადო კოდი" და ა.შ.
    for a in alternatives:
        a2 = str(a).strip().lower()
        if len(a2) < 3:
            continue
        for n in columns:
            ns = str(n).strip().lower()
            if a2 in ns:
                return n
    return None


# ---------------------------------------------------------------------------
# Amount parser
# ---------------------------------------------------------------------------

def parse_journal_amount(val):
    """
    Excel/CSV ხშირი ფორმატები: 1 234,56 / 1234,56 / 1.234,56 / (1 234)
    pd.to_numeric ხშირად აბრუნებს NaN-ს და ჟურნალში თანხა უჩინარი რჩება.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if isinstance(val, float) and pd.isna(val):
            return 0.0
        return float(val)
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return 0.0
    s = s.replace("\u00a0", " ").replace("'", "").replace("\u201e", "").replace('"', "")
    s = re.sub(r"\((.*)\)", r"\1", s)
    s = s.replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    elif s.count(",") > 1 and "." not in s:
        s = s.replace(",", "")
    elif s.count(".") > 1 and "," not in s:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return max(0.0, float(s))
    except ValueError:
        n = pd.to_numeric(val, errors="coerce")
        return float(n) if not pd.isna(n) else 0.0


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------

def _read_manual_payments_csv(path):
    """კომა, ავტო ან Excel-ის ; გამყოფი — რომ ხაზები არ შევიდეს ერთ სვეტში."""
    encodings = ("utf-8-sig", "utf-8", "cp1251", "cp1252")
    for enc in encodings:
        for sep in (None, ",", ";"):
            try:
                if sep is None:
                    df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
                else:
                    df = pd.read_csv(path, encoding=enc, sep=sep)
                if df.shape[1] >= 2:
                    return df
            except Exception:
                continue
    return pd.read_csv(path, encoding="utf-8-sig", sep=None, engine="python")


# ---------------------------------------------------------------------------
# RS suppliers by tax ID (used by sync)
# ---------------------------------------------------------------------------

def collect_rs_suppliers_by_tax_id(rs_files):
    """უნიკალური საგადასახადო ID → RS-ის ორგანიზაციის სტრიქონი."""
    by_id = {}
    for f in sorted(rs_files):
        try:
            d = pd.read_excel(f)
            if "ორგანიზაცია" not in d.columns:
                continue
            for org in d["ორგანიზაცია"].dropna().unique():
                s = str(org).strip()
                m = re.search(r"\((\d+)", s)
                if not m:
                    continue
                tid = m.group(1)
                by_id[tid] = s
        except Exception:
            pass
    return by_id


# ---------------------------------------------------------------------------
# Full journal reader
# ---------------------------------------------------------------------------

def read_manual_journal_full(path):
    """
    CSV ყველა ხაზი: tax_id → amount (ჯამი), comment (ბოლო არაცარიელი), company (არასავალდებულო).
    """
    if not os.path.isfile(path):
        return {}
    try:
        df = _read_manual_payments_csv(path)
    except Exception:
        return {}
    if df.empty or len(df.columns) < 2:
        return {}

    tid_col = _journal_find_col(
        df.columns,
        ("tax_id", "taxid", "საგადასახადო", "საგადასახადო_კოდი", "id"),
    )
    amt_col = _journal_find_col(df.columns, ("amount", "თანხა", "sum", "ჯამი", "paid"))
    company_col = _journal_find_col(
        df.columns,
        ("company", "ორგანიზაცია", "კომპანია", "supplier", "მომწოდებელი"),
    )
    comment_col = _journal_find_col(
        df.columns,
        ("comment", "კომენტარი", "note", "შენიშვნა"),
    )
    if tid_col is None:
        tid_col = df.columns[0]
    if amt_col is None:
        amt_col = df.columns[1]

    by_tid = {}
    for _, row in df.iterrows():
        tid = clean_id(row[tid_col])
        if not tid or not tid.isdigit():
            continue
        if tid not in by_tid:
            by_tid[tid] = {"amount": 0.0, "comment": "", "company": ""}
        amt = parse_journal_amount(row[amt_col])
        by_tid[tid]["amount"] += float(amt)
        if company_col and pd.notna(row[company_col]):
            co = str(row[company_col]).strip()
            if co and co.lower() != "nan":
                by_tid[tid]["company"] = co
        if comment_col and pd.notna(row[comment_col]):
            cm = str(row[comment_col]).strip()
            if cm and cm.lower() != "nan":
                by_tid[tid]["comment"] = cm
    return by_tid


# ---------------------------------------------------------------------------
# Sync journal with RS
# ---------------------------------------------------------------------------

def sync_manual_payments_journal(rs_files):
    """
    manual_payments.csv: ყველა RS მომწოდებელი ერთ სვეტზე; არსებული თანხა/კომენტარი ინახება.
    RS-ში აღარ არსებული ID-ები (ხაზი ჟურნალში დარჩა) — ირჩევა ბოლოში.
    """
    path = manual_payments_csv_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rs_map = collect_rs_suppliers_by_tax_id(rs_files)
    if not rs_map:
        return

    prev = read_manual_journal_full(path) if os.path.isfile(path) else {}
    rs_tids = set(rs_map.keys())

    rows = []
    for tid in sorted(rs_map.keys(), key=lambda t: rs_map[t].lower()):
        org = rs_map[tid]
        p = prev.get(tid, {})
        amt = float(p.get("amount", 0) or 0)
        com = str(p.get("comment", "") or "")
        rows.append(
            {"tax_id": tid, "company": org, "amount": amt, "comment": com}
        )

    orphans = []
    for tid, p in prev.items():
        if tid not in rs_tids:
            org = p.get("company") or "(არაა RS ზედნადებში)"
            amt = float(p.get("amount", 0) or 0)
            com = str(p.get("comment", "") or "")
            orphans.append(
                {"tax_id": tid, "company": org, "amount": amt, "comment": com}
            )
    orphans.sort(key=lambda r: str(r["company"]).lower())
    rows.extend(orphans)

    out_df = pd.DataFrame(rows, columns=["tax_id", "company", "amount", "comment"])
    out_df.to_csv(path, index=False, encoding="utf-8-sig")
    n_manual = sum(1 for r in rows if float(r["amount"] or 0) > 0)
    logger.info(
        f"  manual_payments.csv: {len(rs_map)} კომპანია RS-ით, "
        f"ხელით თანხით >0: {n_manual}"
        + (f", დამატებითი ID (არ RS-ში): {len(orphans)}" if orphans else "")
    )


# ---------------------------------------------------------------------------
# Load payments (public API)
# ---------------------------------------------------------------------------

def load_manual_payments():
    """
    ნაღდი / სხვა არხი — იკითხება manual_payments.csv (ჟურნალის ყველა ხაზიდან amount>0 ჯამდება ID-ზე).
    """
    path = manual_payments_csv_path()
    full = read_manual_journal_full(path)
    return {tid: v["amount"] for tid, v in full.items() if v.get("amount", 0) > 0}
