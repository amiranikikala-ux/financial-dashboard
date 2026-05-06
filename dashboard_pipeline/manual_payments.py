"""
manual_payments.py — ნაღდი/სხვა არხით გადახდის ჟურნალი (manual_payments.csv).

Extracted from generate_dashboard_data.py lines 6861-7068.
"""

import os
import re

import pandas as pd

from dashboard_pipeline.date_filters import parse_source_datetime
from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.file_utils import _financial_analysis_path, clean_id
from dashboard_pipeline.rsge_cache import read_waybill_file

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


def _normalize_journal_row_date(value):
    ts = parse_source_datetime(value)
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# RS suppliers by tax ID (used by sync)
# ---------------------------------------------------------------------------

def collect_rs_suppliers_by_tax_id(rs_files):
    """უნიკალური საგადასახადო ID → RS-ის ორგანიზაციის სტრიქონი."""
    by_id = {}
    for f in sorted(rs_files):
        try:
            d = read_waybill_file(f)
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


def read_manual_journal_rows(path):
    if not os.path.isfile(path):
        return []
    try:
        df = _read_manual_payments_csv(path)
    except Exception:
        return []
    if df.empty or len(df.columns) < 2:
        return []

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
    row_date_col = _journal_find_col(
        df.columns,
        (
            "row_date",
            "date",
            "payment_date",
            "paid_date",
            "თარიღი",
            "გადახდის თარიღი",
            "გადახდის_თარიღი",
        ),
    )
    if tid_col is None:
        tid_col = df.columns[0]
    if amt_col is None:
        amt_col = df.columns[1]

    rows = []
    for _, row in df.iterrows():
        tid = clean_id(row[tid_col])
        if not tid or not tid.isdigit():
            continue
        amount = float(parse_journal_amount(row[amt_col]))
        company = ""
        if company_col and pd.notna(row[company_col]):
            co = str(row[company_col]).strip()
            if co and co.lower() != "nan":
                company = co
        comment = ""
        if comment_col and pd.notna(row[comment_col]):
            cm = str(row[comment_col]).strip()
            if cm and cm.lower() != "nan":
                comment = cm
        row_date = ""
        if row_date_col and pd.notna(row[row_date_col]):
            row_date = _normalize_journal_row_date(row[row_date_col])
        rows.append(
            {
                "matched_tax_id": tid,
                "matched_supplier_name": company,
                "company": company,
                "amount": amount,
                "comment": comment,
                "row_date": row_date,
                "status": "manual_journal",
                "source_bank": "manual_journal",
                "matched_by": "manual_journal",
                "confidence": "manual",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Full journal reader
# ---------------------------------------------------------------------------

def read_manual_journal_full(path):
    """
    CSV ყველა ხაზი: tax_id → amount (ჯამი), comment (ბოლო არაცარიელი), company (არასავალდებულო).
    """
    rows = read_manual_journal_rows(path)
    if not rows:
        return {}

    by_tid = {}
    for row in rows:
        tid = str(row.get("matched_tax_id") or "").strip()
        if tid not in by_tid:
            by_tid[tid] = {"amount": 0.0, "comment": "", "company": "", "row_date": ""}
        by_tid[tid]["amount"] += float(row.get("amount") or 0)
        co = str(row.get("company") or "").strip()
        if co and co.lower() != "nan":
            by_tid[tid]["company"] = co
        cm = str(row.get("comment") or "").strip()
        if cm and cm.lower() != "nan":
            by_tid[tid]["comment"] = cm
        row_date = str(row.get("row_date") or "").strip()
        if row_date and row_date > str(by_tid[tid].get("row_date") or ""):
            by_tid[tid]["row_date"] = row_date
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
        row_date = str(p.get("row_date", "") or "")
        rows.append(
            {"tax_id": tid, "company": org, "row_date": row_date, "amount": amt, "comment": com}
        )

    orphans = []
    for tid, p in prev.items():
        if tid not in rs_tids:
            org = p.get("company") or "(არაა RS ზედნადებში)"
            amt = float(p.get("amount", 0) or 0)
            com = str(p.get("comment", "") or "")
            row_date = str(p.get("row_date", "") or "")
            orphans.append(
                {"tax_id": tid, "company": org, "row_date": row_date, "amount": amt, "comment": com}
            )
    orphans.sort(key=lambda r: str(r["company"]).lower())
    rows.extend(orphans)

    out_df = pd.DataFrame(rows, columns=["tax_id", "company", "row_date", "amount", "comment"])
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


def load_manual_payment_rows():
    path = manual_payments_csv_path()
    rows = read_manual_journal_rows(path)
    out = [dict(row) for row in rows if float(row.get("amount") or 0) > 0]

    # Append event-based journal entries (manual_payments_journal.csv) so each
    # owner-entered cash payment surfaces individually in the supplier modal
    # with its own UUID — that lets the UI render a 🗑 delete button per row.
    from dashboard_pipeline import manual_payments_journal as _journal

    for entry in _journal.read_active_entries():
        out.append(
            {
                "matched_tax_id": entry["tax_id"],
                "matched_supplier_name": "",
                "company": "",
                "amount": float(entry["amount"]),
                "comment": entry.get("comment") or "",
                "row_date": entry.get("date") or "",
                "status": "manual_journal_v2",
                "source_bank": "manual_journal_v2",
                "matched_by": "manual_journal_v2",
                "confidence": "manual",
                "id": entry["id"],
            }
        )
    return out


def build_manual_payment_source_meta(rows):
    rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]
    dated_rows = [row for row in rows if str(row.get("row_date") or "").strip()]
    undated_rows = [row for row in rows if not str(row.get("row_date") or "").strip()]
    period_correctness_incomplete = len(undated_rows) > 0
    return {
        "manual_journal_row_count": len(rows),
        "dated_row_count": len(dated_rows),
        "undated_row_count": len(undated_rows),
        "manual_journal_total": round(
            sum(float(row.get("amount") or 0) for row in rows),
            2,
        ),
        "date_column_supported": True,
        "period_correctness_incomplete": period_correctness_incomplete,
        "period_correctness_caveat_ka": (
            "manual/off-bank journal-ის თანხები row_date-ის გარეშე ზუსტ period filter-ში სრულად ვერ მოხვდება."
            if period_correctness_incomplete
            else ""
        ),
    }
