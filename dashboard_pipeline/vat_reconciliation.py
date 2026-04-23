"""
VAT reconciliation — Sprint 5.1

Computes per-month income capture from raw sources and compares against declared turnover.

Core identity (per month):
    cashreg_in  = max(0, max_pos_ge - bank_card_ge)    # cash received at register
    bank_card   = tbc_pos_ge + bog_pos_ge               # card deposits to banks
    total_real  = cashreg_in + bank_card + invoices     # pipeline-known real income
    gap         = total_real - declared                 # under-declaration

Cash outflow side (tracks where register cash went):
    cash_supplier_ge    = manual_payments.csv by month (documented cash supplier payments)
    cash_classified_ge  = cash_outflow_journal.csv by month (user-entered classifications)
    cash_unaccounted_ge = cashreg_in - cash_supplier - cash_classified

    If cash_unaccounted > threshold → AI must ask user to classify (18% VAT liability risk)

No dependency on audit Excel for core fields — declared is overlaid optionally.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

import pandas as pd

from dashboard_pipeline.logging_config import get_logger

logger = get_logger(__name__)


VAT_RATE = 0.18

# Gap classification thresholds (relative to declared)
STATUS_GREEN_MAX_PCT = 0.05   # ≤5%
STATUS_YELLOW_MAX_PCT = 0.15  # 5-15%
# >15% is red

UNACCOUNTED_CASH_THRESHOLD_GE = 5000.0  # ≥5K unaccounted triggers consultation


CATEGORY_VAT_DEFAULTS = {
    "salary_cash": True,
    "personal_withdrawal": True,
    "unknown": True,
    "supplier_undocumented": False,
    "business_expense": False,
    "advance_to_employee": False,
    "return_to_customer": False,
}

CATEGORY_LABELS_KA = {
    "salary_cash": "ხელფასი ხელზე",
    "personal_withdrawal": "პერსონალური ამოღება",
    "supplier_undocumented": "მომწოდებელი ხელზე (არ ფიქსირდებოდა)",
    "business_expense": "ბიზნეს ხარჯი (ქვითრით)",
    "advance_to_employee": "ავანსი თანამშრომელს",
    "return_to_customer": "კლიენტის დაბრუნება",
    "unknown": "უცნობი / დაიკარგა",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_of(date_value) -> Optional[str]:
    if date_value is None:
        return None
    try:
        ts = pd.to_datetime(date_value, errors="coerce")
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return f"{ts.year:04d}-{ts.month:02d}"


def _lines_by_month(lines: List[Dict[str, Any]], amount_field: str = "თანხა") -> Dict[str, float]:
    out: Dict[str, float] = defaultdict(float)
    for line in lines or []:
        m = _month_of(line.get("თარიღი"))
        if not m:
            continue
        try:
            amt = float(line.get(amount_field) or 0)
        except (TypeError, ValueError):
            continue
        out[m] += amt
    return dict(out)


def _retail_sales_by_month(retail_sales_bundle: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    by_month = (retail_sales_bundle or {}).get("by_month") or []
    for row in by_month:
        month = str(row.get("month") or "")
        if not re.match(r"^\d{4}-\d{2}$", month):
            continue
        try:
            out[month] = float(row.get("revenue_ge") or 0)
        except (TypeError, ValueError):
            continue
    return out


def _retail_sales_by_object_month(
    retail_sales_bundle: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    """Sprint 5.8 — per-shop MAX POS revenue per month.

    Returns {"YYYY-MM": {object_label: revenue_ge}} using the bundle's
    `by_object_by_month` section. Missing or mis-shaped entries are skipped.
    Falls back to empty dict when the bundle has no object-month breakdown
    (older cached runs or empty fixture).
    """
    out: Dict[str, Dict[str, float]] = defaultdict(dict)
    rows = (retail_sales_bundle or {}).get("by_object_by_month") or []
    for row in rows:
        month = str(row.get("month") or "")
        if not re.match(r"^\d{4}-\d{2}$", month):
            continue
        obj = str(row.get("object") or "").strip()
        if not obj:
            continue
        try:
            revenue = float(row.get("revenue_ge") or 0)
        except (TypeError, ValueError):
            continue
        out[month][obj] = revenue
    return dict(out)


def _lines_by_object_month(
    lines: List[Dict[str, Any]], amount_field: str = "თანხა"
) -> Dict[str, Dict[str, float]]:
    """Sprint 5.8 — per-shop bank POS income per month.

    Uses the per-line `object` tag populated by `detect_object` in
    `bank_income.py`. When `object` is missing or blank, attributes to
    `გაუნაწილებელი` (unallocated).
    """
    out: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for line in lines or []:
        m = _month_of(line.get("თარიღი"))
        if not m:
            continue
        try:
            amt = float(line.get(amount_field) or 0)
        except (TypeError, ValueError):
            continue
        obj = str(line.get("object") or "").strip() or "გაუნაწილებელი"
        out[m][obj] += amt
    # Defaultdict → plain dict for stable serialization.
    return {month: dict(by_obj) for month, by_obj in out.items()}


# ---------------------------------------------------------------------------
# Audit Excel parser (declared turnover per month)
# ---------------------------------------------------------------------------

def parse_audit_excel(path: str) -> Dict[str, Dict[str, float]]:
    """
    Parses the audit file (e.g. "გაანგარიშება შპს ჯეო ფუდთაიმი.xlsx").
    Expected header row at index 1 with columns:
      პერიოდი, დეკლარირებული ბრუნვა, აფ.გამოწერილი, უფზ რეალიზაცია,
      სალარო, თბს ბანკი პოსტერმინალით, საქ.ბანკი პოსტერმინალით, ...

    Period is either YYYYMM integer or string. Returns a dict keyed by "YYYY-MM".
    """
    if not path or not os.path.isfile(path):
        return {}
    try:
        df = pd.read_excel(path, header=1)
    except Exception as exc:
        logger.warning("audit excel parse failed: %s", exc)
        return {}
    df.columns = [str(c).strip() for c in df.columns]
    rename = {
        "პერიოდი": "period_raw",
        "დეკლარირებული ბრუნვა": "declared_ge",
        "აფ.გამოწერილი": "af_ge",
        "უფზ რეალიზაცია": "ufz_ge",
        "სალარო": "cashreg_ge",
        "თბს ბანკი პოსტერმინალით": "tbc_pos_ge",
        "საქ.ბანკი პოსტერმინალით": "bog_pos_ge",
    }
    df = df.rename(columns=rename)
    if "period_raw" not in df.columns:
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for _, row in df.iterrows():
        raw = str(row.get("period_raw") or "").strip()
        if not re.match(r"^\d{6}", raw):
            continue
        period = f"{raw[:4]}-{raw[4:6]}"
        entry: Dict[str, float] = {}
        for field in ("declared_ge", "af_ge", "ufz_ge", "cashreg_ge", "tbc_pos_ge", "bog_pos_ge"):
            if field in df.columns:
                try:
                    entry[field] = float(pd.to_numeric(row.get(field), errors="coerce") or 0)
                except (TypeError, ValueError):
                    entry[field] = 0.0
        out[period] = entry
    return out


def find_invoices_issued_excel(financial_analysis_dir: str) -> Optional[str]:
    """Auto-detect issued-invoices file (RS.ge "report" export).

    Searches `ანგარიშ ფაქტურები/` subfolder at several plausible locations:
    under the given `Financial_Analysis` dir, and under `Financial_Analysis/`
    folders in the parent directories (workspace root). Returns the first
    `report*.xls*` file found.
    """
    if not financial_analysis_dir:
        return None

    def _scan_ა_ფ_dir(dir_path: str) -> Optional[str]:
        if not dir_path or not os.path.isdir(dir_path):
            return None
        try:
            for name in os.listdir(dir_path):
                lower = name.lower()
                if lower.startswith("report") and (lower.endswith(".xls") or lower.endswith(".xlsx")):
                    return os.path.join(dir_path, name)
        except OSError:
            pass
        return None

    current = financial_analysis_dir
    for _ in range(3):
        if current and os.path.isdir(current):
            # Direct subfolder
            hit = _scan_ა_ფ_dir(os.path.join(current, "ანგარიშ ფაქტურები"))
            if hit:
                return hit
            # Sibling Financial_Analysis (when current is project root or workspace)
            hit = _scan_ა_ფ_dir(os.path.join(current, "Financial_Analysis", "ანგარიშ ფაქტურები"))
            if hit:
                return hit
        next_up = os.path.dirname(current.rstrip(os.sep))
        if not next_up or next_up == current:
            break
        current = next_up
    return None


def parse_invoices_issued(path: str, our_tax_id: str = "400333858") -> Dict[str, float]:
    """
    Parses RS.ge "report" Excel (ა/ფ გამოწერილი). Filters rows where
    `გამყიდველი` contains `our_tax_id` (we are the seller), aggregates
    `ღირებულება დღგ და აქციზის ჩათვლით` (bruto) by `ოპერაციის თარ.` month.
    Returns {"YYYY-MM": amount_ge} dict.
    """
    if not path or not os.path.isfile(path):
        return {}
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        logger.warning("invoices_issued parse failed: %s", exc)
        return {}
    df.columns = [str(c).strip() for c in df.columns]
    if "გამყიდველი" not in df.columns:
        return {}
    amount_col = next((c for c in df.columns if "ღირებულება" in c), None)
    date_col = next((c for c in df.columns if "ოპერაციის" in c and "თარ" in c), None)
    if not amount_col or not date_col:
        return {}
    df_sellers = df[df["გამყიდველი"].astype(str).str.contains(our_tax_id, na=False)].copy()
    if df_sellers.empty:
        return {}
    df_sellers["amount"] = pd.to_numeric(df_sellers[amount_col], errors="coerce").fillna(0)
    df_sellers["month"] = pd.to_datetime(df_sellers[date_col], errors="coerce").dt.to_period("M").astype(str)
    by_month = df_sellers.groupby("month")["amount"].sum().to_dict()
    return {k: float(v) for k, v in by_month.items() if re.match(r"^\d{4}-\d{2}$", k)}


def find_audit_excel(financial_analysis_dir: str) -> Optional[str]:
    """Auto-detect audit file: any xlsx starting with 'გაანგარიშება'.

    Searches up to 2 parent directories from `financial_analysis_dir` to cover
    the common layout: audit file at workspace root, Financial_Analysis/ two
    levels deeper.
    """
    if not financial_analysis_dir:
        return None
    current = financial_analysis_dir
    for _ in range(3):  # financial_analysis_dir, project root, workspace root
        if current and os.path.isdir(current):
            try:
                for name in os.listdir(current):
                    if name.lower().endswith(".xlsx") and name.startswith("გაანგარიშება"):
                        return os.path.join(current, name)
            except OSError:
                pass
        next_up = os.path.dirname(current.rstrip(os.sep))
        if not next_up or next_up == current:
            break
        current = next_up
    return None


# ---------------------------------------------------------------------------
# Cash outflow journal
# ---------------------------------------------------------------------------

def parse_cash_outflow_journal(path: str) -> List[Dict[str, Any]]:
    """
    Loads cash_outflow_journal.csv entries.
    Expected columns: period, amount, purpose_ka, category, vat_applies, notes, entered_at
    """
    if not path or not os.path.isfile(path):
        return []
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception:
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except Exception as exc:
            logger.warning("cash_outflow_journal parse failed: %s", exc)
            return []
    df.columns = [str(c).strip() for c in df.columns]
    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        period = str(row.get("period") or "").strip()
        if not re.match(r"^\d{4}-\d{2}$", period):
            continue
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        category = str(row.get("category") or "unknown").strip().lower()
        vat_raw = row.get("vat_applies")
        if pd.isna(vat_raw) or str(vat_raw).strip() == "":
            vat_applies = CATEGORY_VAT_DEFAULTS.get(category, True)
        else:
            vat_applies = str(vat_raw).strip().lower() in ("true", "1", "yes", "კი")
        out.append({
            "period": period,
            "amount_ge": amount,
            "purpose_ka": str(row.get("purpose_ka") or "").strip(),
            "category": category,
            "category_label_ka": CATEGORY_LABELS_KA.get(category, category),
            "vat_applies": bool(vat_applies),
            "notes": str(row.get("notes") or "").strip(),
            "entered_at": str(row.get("entered_at") or "").strip(),
        })
    return out


def _cash_classified_by_month(journal_entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "total_ge": 0.0,
        "vat_applies_ge": 0.0,
        "entries": [],
        "by_category": defaultdict(float),
    })
    for e in journal_entries:
        period = e["period"]
        amt = float(e["amount_ge"])
        agg[period]["total_ge"] += amt
        if e["vat_applies"]:
            agg[period]["vat_applies_ge"] += amt
        agg[period]["entries"].append(e)
        agg[period]["by_category"][e["category"]] += amt

    out: Dict[str, Dict[str, Any]] = {}
    for period, data in agg.items():
        out[period] = {
            "total_ge": float(data["total_ge"]),
            "vat_applies_ge": float(data["vat_applies_ge"]),
            "entries": data["entries"],
            "by_category": dict(data["by_category"]),
        }
    return out


# ---------------------------------------------------------------------------
# Manual payments aggregation (cash supplier payments)
# ---------------------------------------------------------------------------

def _manual_payments_by_month(manual_journal_full: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregates manual_payments.csv entries by month.

    Accepts the raw-rows shape from `read_manual_journal_rows()` which has
    `row_date` + `amount` fields, OR a test-fixture shape with `თარიღი` + `თანხა`.
    """
    out: Dict[str, float] = defaultdict(float)
    for entry in manual_journal_full or []:
        if not isinstance(entry, dict):
            continue
        date_val = entry.get("row_date") or entry.get("თარიღი") or entry.get("date")
        m = _month_of(date_val)
        if not m:
            continue
        raw_amt = entry.get("amount")
        if raw_amt is None:
            raw_amt = entry.get("თანხა")
        try:
            amt = float(raw_amt or 0)
        except (TypeError, ValueError):
            continue
        out[m] += amt
    return dict(out)


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------

def _classify_status(gap: Optional[float], declared: Optional[float], has_unaccounted: bool) -> str:
    if declared is None or declared <= 0:
        return "no_declared_data"
    if gap is None:
        return "no_declared_data"
    gap_pct = abs(gap) / declared
    base = "green"
    if gap_pct > STATUS_YELLOW_MAX_PCT:
        base = "red"
    elif gap_pct > STATUS_GREEN_MAX_PCT:
        base = "yellow"
    if has_unaccounted:
        # unaccounted always escalates to at least yellow
        if base == "green":
            base = "yellow"
    return base


# ---------------------------------------------------------------------------
# Main compute entry
# ---------------------------------------------------------------------------

def compute_vat_reconciliation(
    *,
    retail_sales_bundle: Dict[str, Any],
    tbc_card_income_bundle: Dict[str, Any],
    bog_pos_income_bundle: Dict[str, Any],
    manual_journal_full: List[Dict[str, Any]],
    audit_excel_path: Optional[str] = None,
    cash_outflow_journal_path: Optional[str] = None,
    invoices_issued_path: Optional[str] = None,
    our_tax_id: str = "400333858",
) -> Dict[str, Any]:
    """
    Builds the vat_reconciliation bundle for data.json.

    All inputs come from already-computed pipeline stages — this is a pure aggregator.
    """
    # Per-month inputs
    max_pos_by_month = _retail_sales_by_month(retail_sales_bundle)
    tbc_pos_by_month = _lines_by_month((tbc_card_income_bundle or {}).get("lines") or [])
    bog_pos_by_month = _lines_by_month((bog_pos_income_bundle or {}).get("lines") or [])
    manual_by_month = _manual_payments_by_month(manual_journal_full or [])

    # Sprint 5.8 — per-shop per-month inputs for by_shop breakdown.
    max_by_obj_month = _retail_sales_by_object_month(retail_sales_bundle)
    tbc_by_obj_month = _lines_by_object_month((tbc_card_income_bundle or {}).get("lines") or [])
    bog_by_obj_month = _lines_by_object_month((bog_pos_income_bundle or {}).get("lines") or [])

    # External sources
    audit_by_month = parse_audit_excel(audit_excel_path) if audit_excel_path else {}
    journal_entries = parse_cash_outflow_journal(cash_outflow_journal_path) if cash_outflow_journal_path else []
    cash_classified_by_month = _cash_classified_by_month(journal_entries)
    invoices_by_month = parse_invoices_issued(invoices_issued_path, our_tax_id=our_tax_id) if invoices_issued_path else {}

    # Collect all months seen anywhere
    all_months = set()
    for d in (max_pos_by_month, tbc_pos_by_month, bog_pos_by_month, manual_by_month, audit_by_month, cash_classified_by_month, invoices_by_month):
        all_months.update(d.keys())
    months_sorted = sorted(all_months)

    by_month: List[Dict[str, Any]] = []
    red_flag_months: List[str] = []
    needs_input_months: List[str] = []

    for period in months_sorted:
        max_pos = float(max_pos_by_month.get(period, 0))
        tbc_pos = float(tbc_pos_by_month.get(period, 0))
        bog_pos = float(bog_pos_by_month.get(period, 0))
        bank_card = tbc_pos + bog_pos

        # cashreg_in: nonnegative version + anomaly signal when bank exceeds max
        raw_gap = max_pos - bank_card
        cashreg_in = max(0.0, raw_gap)
        bank_exceeds_max = (max_pos > 0) and (raw_gap < 0)

        # Sprint 5.8 — per-shop breakdown for audit-per-shop defense.
        # MAX POS side is reliable (retail_sales folder is per-shop).
        # Bank POS side: BOG uses object_mapping.json bog_terminal_to_object
        # (terminal ID → shop, reliable); TBC uses tbc_text_to_object which
        # matches shop name in transaction description (imperfect — many rows
        # fall to "გაუნაწილებელი"). data_quality.tbc_per_shop_reliable flags
        # when TBC attribution is likely complete.
        shops_seen = set()
        shops_seen.update(max_by_obj_month.get(period, {}).keys())
        shops_seen.update(tbc_by_obj_month.get(period, {}).keys())
        shops_seen.update(bog_by_obj_month.get(period, {}).keys())
        by_shop: Dict[str, Dict[str, float]] = {}
        for shop in sorted(shops_seen):
            shop_max = float(max_by_obj_month.get(period, {}).get(shop, 0))
            shop_tbc = float(tbc_by_obj_month.get(period, {}).get(shop, 0))
            shop_bog = float(bog_by_obj_month.get(period, {}).get(shop, 0))
            shop_bank = shop_tbc + shop_bog
            shop_cashreg_raw = shop_max - shop_bank
            shop_cashreg_in = max(0.0, shop_cashreg_raw)
            shop_bank_exceeds = (shop_max > 0) and (shop_cashreg_raw < 0)
            # Only include shops with any activity in the month.
            if shop_max == 0 and shop_bank == 0:
                continue
            by_shop[shop] = {
                "max_pos_ge": shop_max,
                "tbc_pos_ge": shop_tbc,
                "bog_pos_ge": shop_bog,
                "bank_card_ge": shop_bank,
                "cashreg_in_ge": shop_cashreg_in,
                "bank_exceeds_max": shop_bank_exceeds,
            }

        # TBC per-shop reliability: share of TBC attributed to REAL shops
        # (not "გაუნაწილებელი" bucket) should be ≥98% of total TBC. Low
        # reliability → AI should treat per-shop TBC as incomplete.
        tbc_real_attributed = sum(
            v["tbc_pos_ge"] for shop, v in by_shop.items() if shop != "გაუნაწილებელი"
        )
        tbc_per_shop_reliable = (
            tbc_pos == 0 or (tbc_real_attributed / max(tbc_pos, 1)) >= 0.98
        )

        cash_supplier = float(manual_by_month.get(period, 0))
        classified = cash_classified_by_month.get(period, {"total_ge": 0.0, "vat_applies_ge": 0.0, "entries": [], "by_category": {}})
        cash_classified = float(classified["total_ge"])
        cash_unaccounted = max(0.0, cashreg_in - cash_supplier - cash_classified)

        audit_row = audit_by_month.get(period) or {}
        declared = audit_row.get("declared_ge")
        declared_val = float(declared) if declared is not None else None
        # Audit file's own total (for comparison, optional)
        audit_total = (
            float(audit_row.get("cashreg_ge") or 0)
            + float(audit_row.get("tbc_pos_ge") or 0)
            + float(audit_row.get("bog_pos_ge") or 0)
            + float(audit_row.get("af_ge") or 0)
            + float(audit_row.get("ufz_ge") or 0)
        ) if audit_row else None

        # invoices_ge from RS.ge ა/ფ report (Sprint 5.1.1).
        # bruto value (with VAT); audit's af_ge is net — multiply by 1.18 if only audit is available.
        invoices_from_report = invoices_by_month.get(period)
        if invoices_from_report is not None:
            invoices = float(invoices_from_report)
        elif audit_row.get("af_ge"):
            invoices = float(audit_row["af_ge"]) * 1.18  # approximate bruto
        else:
            invoices = None
        total_real = cashreg_in + bank_card + (invoices or 0)
        gap_vs_declared = (total_real - declared_val) if declared_val is not None else None

        has_unaccounted = cash_unaccounted >= UNACCOUNTED_CASH_THRESHOLD_GE
        status = _classify_status(gap_vs_declared, declared_val, has_unaccounted)

        if status == "red":
            red_flag_months.append(period)
        if has_unaccounted:
            needs_input_months.append(period)

        vat_on_unaccounted = cash_unaccounted * VAT_RATE
        vat_on_classified = float(classified["vat_applies_ge"]) * VAT_RATE

        by_month.append({
            "period": period,

            # Income side (computed)
            "max_pos_ge": max_pos,
            "tbc_pos_ge": tbc_pos,
            "bog_pos_ge": bog_pos,
            "bank_card_ge": bank_card,
            "cashreg_in_ge": cashreg_in,
            "invoices_ge": invoices,
            "total_real_ge": total_real,

            # Cash outflow classification
            "cash_supplier_ge": cash_supplier,
            "cash_classified_ge": cash_classified,
            "cash_classified_by_category": dict(classified["by_category"]),
            "cash_unaccounted_ge": cash_unaccounted,

            # Tax liability preview
            "vat_on_unaccounted_ge": vat_on_unaccounted,
            "vat_on_classified_ge": vat_on_classified,
            "vat_total_liability_ge": vat_on_unaccounted + vat_on_classified,

            # Declared side (from audit Excel)
            "declared_ge": declared_val,
            "audit_total_ge": audit_total,
            "audit_snapshot": audit_row or None,
            "gap_vs_declared_ge": gap_vs_declared,

            # Sprint 5.8 — per-shop breakdown.
            "by_shop": by_shop,

            # Quality + status
            "status": status,
            "needs_user_input": has_unaccounted,
            "data_quality": {
                "max_pos_available": max_pos > 0,
                "banks_complete": (tbc_pos + bog_pos) > 0,
                "declared_available": declared_val is not None,
                "bank_exceeds_max": bank_exceeds_max,
                "cash_outflow_classified": cash_classified > 0 or cash_supplier > 0,
                "tbc_per_shop_reliable": tbc_per_shop_reliable,
            },
        })

    # Summary
    total_real_all = sum(r["total_real_ge"] for r in by_month)
    total_declared_all = sum(r["declared_ge"] or 0 for r in by_month)
    total_gap_all = sum((r["gap_vs_declared_ge"] or 0) for r in by_month if r["gap_vs_declared_ge"] is not None)
    total_unaccounted = sum(r["cash_unaccounted_ge"] for r in by_month)
    total_vat_liability = sum(r["vat_total_liability_ge"] for r in by_month)

    return {
        "label_ka": "VAT და აუდიტის შედარება",
        "methodology_ka": (
            "ყოველთვიური შემოსავლის დათვლა raw data-დან: bank_card = TBC POS + BOG POS; "
            "cashreg_in = max(0, MAX_POS − bank_card); total_real = cashreg_in + bank_card + invoices. "
            "declared uploaded audit file-დან. cash_unaccounted = cashreg_in − cash_supplier − cash_classified. "
            "by_shop (Sprint 5.8): per-მაღაზია MAX/TBC/BOG/cashreg_in სადაც retail_sales-ის ფოლდერი გვაძლევს "
            "MAX-ის shop-split-ს და bog_terminal_to_object/tbc_text_to_object mapping-ი გვაძლევს bank-ის shop-split-ს. "
            "TBC attribution text-based, შეიძლება არასრული იყოს — data_quality.tbc_per_shop_reliable ფლაგი გვიჩვენებს."
        ),
        "vat_rate": VAT_RATE,
        "thresholds": {
            "status_green_max_pct": STATUS_GREEN_MAX_PCT,
            "status_yellow_max_pct": STATUS_YELLOW_MAX_PCT,
            "unaccounted_cash_threshold_ge": UNACCOUNTED_CASH_THRESHOLD_GE,
        },
        "date_range_iso": {
            "min": months_sorted[0] if months_sorted else None,
            "max": months_sorted[-1] if months_sorted else None,
        },
        "summary": {
            "months_total": len(months_sorted),
            "months_red": len([r for r in by_month if r["status"] == "red"]),
            "months_yellow": len([r for r in by_month if r["status"] == "yellow"]),
            "months_green": len([r for r in by_month if r["status"] == "green"]),
            "months_no_declared": len([r for r in by_month if r["status"] == "no_declared_data"]),
            "months_needing_user_input": len(needs_input_months),
            "total_real_ge": total_real_all,
            "total_declared_ge": total_declared_all,
            "total_gap_ge": total_gap_all,
            "total_unaccounted_cash_ge": total_unaccounted,
            "total_vat_liability_ge": total_vat_liability,
        },
        "red_flag_months": red_flag_months,
        "needs_user_input_months": needs_input_months,
        "by_month": by_month,
        "uploaded_audit_source": (
            {"path": audit_excel_path, "months_parsed": len(audit_by_month)}
            if audit_excel_path and audit_by_month else None
        ),
        "cash_journal_source": (
            {"path": cash_outflow_journal_path, "entries_parsed": len(journal_entries)}
            if cash_outflow_journal_path and journal_entries else None
        ),
        "invoices_issued_source": (
            {"path": invoices_issued_path, "months_parsed": len(invoices_by_month)}
            if invoices_issued_path and invoices_by_month else None
        ),
    }


def append_cash_outflow_entry(
    journal_path: str,
    *,
    period: str,
    amount_ge: float,
    purpose_ka: str,
    category: str,
    vat_applies: Optional[bool] = None,
    notes: str = "",
    entered_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Appends a classified cash outflow entry to the journal CSV.
    Creates file with header if missing. Returns the created entry.
    """
    if not re.match(r"^\d{4}-\d{2}$", period):
        raise ValueError(f"period must be YYYY-MM, got {period!r}")
    if amount_ge <= 0:
        raise ValueError(f"amount_ge must be positive, got {amount_ge}")
    category = str(category or "unknown").strip().lower()
    if category not in CATEGORY_VAT_DEFAULTS:
        raise ValueError(f"unknown category: {category!r}. Allowed: {sorted(CATEGORY_VAT_DEFAULTS.keys())}")
    if vat_applies is None:
        vat_applies = CATEGORY_VAT_DEFAULTS[category]
    if entered_at is None:
        entered_at = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

    os.makedirs(os.path.dirname(journal_path) or ".", exist_ok=True)
    file_exists = os.path.isfile(journal_path)

    entry = {
        "period": period,
        "amount": float(amount_ge),
        "purpose_ka": purpose_ka or "",
        "category": category,
        "vat_applies": "true" if vat_applies else "false",
        "notes": notes or "",
        "entered_at": entered_at,
    }

    # Append using csv to preserve encoding
    import csv
    fieldnames = ["period", "amount", "purpose_ka", "category", "vat_applies", "notes", "entered_at"]
    with open(journal_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)

    return {
        **entry,
        "amount_ge": float(amount_ge),
        "vat_applies": bool(vat_applies),
        "category_label_ka": CATEGORY_LABELS_KA.get(category, category),
    }
