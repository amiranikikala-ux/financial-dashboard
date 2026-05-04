"""
File-system helpers: path resolution, file listing wrappers,
Excel header detection, cell parsing, and the shared _save_excel writer.
"""
import glob
import os
import re

import pandas as pd

from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.sources import (
    financial_analysis_path as _pipeline_financial_analysis_path,
    list_bog_bank_statement_xlsx as _pipeline_list_bog_bank_statement_xlsx,
    list_imported_product_files as _pipeline_list_imported_product_files,
    list_retail_sales_dvabzu_files as _pipeline_list_retail_sales_dvabzu_files,
    list_retail_sales_files as _pipeline_list_retail_sales_files,
    list_retail_sales_ozurgeti_files as _pipeline_list_retail_sales_ozurgeti_files,
    list_rs_waybill_files as _pipeline_list_rs_waybill_files,
    list_tbc_bank_statement_xlsx as _pipeline_list_tbc_bank_statement_xlsx,
)
from dashboard_pipeline.constants import (
    IMPORTED_PRODUCTS_CSV_ENCODINGS,
    IMPORTED_PRODUCTS_SHEET_NAME,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# _anchor_file — used by path helpers so they resolve relative to
# generate_dashboard_data.py (the project root script) rather than this module.
# Set once at import time by generate_dashboard_data.py via set_anchor_file().
# ---------------------------------------------------------------------------
_anchor_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generate_dashboard_data.py")


def set_anchor_file(path):
    """Called once from generate_dashboard_data.py to set the anchor for path helpers."""
    global _anchor_file
    _anchor_file = path


def _financial_analysis_path(*parts):
    """Financial_Analysis/ — absolute path (independent of cwd / os.chdir)."""
    return _pipeline_financial_analysis_path(_anchor_file, *parts)


def _sorted_glob_in_financial(subdir, pattern):
    return sorted(glob.glob(os.path.join(_financial_analysis_path(subdir), pattern)))


def list_bog_bank_statement_xlsx():
    """BOG: all `.xlsx` in `Financial_Analysis/ბოგ ბანკი ამონაწერი/` (sorted by name)."""
    return _pipeline_list_bog_bank_statement_xlsx(_anchor_file)


def list_tbc_bank_statement_xlsx():
    """TBC: all `.xlsx` in `Financial_Analysis/თბს ბანკი ამონაწერი/` (sorted by name)."""
    return _pipeline_list_tbc_bank_statement_xlsx(_anchor_file)


def list_rs_waybill_files():
    """RS waybills: all `.xlsx` and `.xls` in `Financial_Analysis/რს ზედნადები/`."""
    return _pipeline_list_rs_waybill_files(_anchor_file)


def list_imported_product_files():
    """Imported products: CSV preferred, legacy fallback: .xls / .xlsx."""
    return _pipeline_list_imported_product_files(_anchor_file)


def list_retail_sales_dvabzu_files():
    """Retail sales source: dvabzu object `.xlsx`."""
    return _pipeline_list_retail_sales_dvabzu_files(_anchor_file)


def list_retail_sales_ozurgeti_files():
    """Retail sales source: ozurgeti object `.xlsx`."""
    return _pipeline_list_retail_sales_ozurgeti_files(_anchor_file)


def list_retail_sales_files():
    """Retail sales source: dvabzu + ozurgeti `.xlsx` files, no duplicates."""
    return _pipeline_list_retail_sales_files(_anchor_file)


def _to_financial_relative_path(path):
    if not path:
        return ""
    abs_path = os.path.abspath(path)
    base = _financial_analysis_path()
    try:
        rel = os.path.relpath(abs_path, base)
    except Exception:
        rel = abs_path
    rel = str(rel).replace("\\", "/").strip("./")
    if rel.startswith("Financial_Analysis/"):
        return rel
    return f"Financial_Analysis/{rel}" if rel else "Financial_Analysis"


# ---------------------------------------------------------------------------
# Excel header detection
# ---------------------------------------------------------------------------

def find_header_row(file_path):
    """
    სათაურის სტრიქონი: ვეძებთ უჯრების ტექსტში რამდენიმე მარკერის ერთად არსებობას,
    რომ ზედა ბლოკში მთლიანად „თარიღი" სიტყვამ არ აირჩიოს არასწორი სტრიქონი.
    """
    df = pd.read_excel(file_path, header=None, nrows=30)
    weights = {
        "თარიღი": 3.0,
        "დებეტი": 2.0,
        "გასული თანხა": 2.0,
        "კრედიტი": 1.0,
        "შემოსული თანხა": 1.0,
        "მიმღების საიდენტიფიკაციო": 2.0,
        "პარტნიორის საგადასახადო კოდი": 2.0,
        "პარტნიორი": 1.0,
        "დანიშნულება": 1.0,
    }
    best_i, best_score = 0, -1.0
    for i, row in df.iterrows():
        line = " ".join(str(x) for x in row.tolist() if not (x is None or (isinstance(x, float) and pd.isna(x))))
        score = 0.0
        for needle, w in weights.items():
            if needle in line:
                score += w
        if score > best_score:
            best_score, best_i = score, i
    if best_score >= 5.0:
        return int(best_i)
    for i, row in df.iterrows():
        if row.astype(str).str.contains("თარიღი", regex=False).any():
            return int(i)
    return 0


def clean_id(val):
    if pd.isna(val):
        return None
    s = str(val).split('.')[0].strip()
    return s if s else None


def _find_excel_column_danishnuleba(cols):
    """BOG/TBC ამონაწერის 'დანიშნულება' (არა 'დამატებითი დანიშნულება')."""
    for c in cols:
        if str(c).strip() == "დანიშნულება":
            return c
    for c in cols:
        s = str(c)
        if "დანიშნულება" in s and "დამატებითი" not in s:
            return c
    return None


def _find_tbc_partner_column(cols):
    """TBC: 'პარტნიორი' — exact header (strip), excluding other 'პარტნიორის …' columns."""
    for c in cols:
        if str(c).strip() == "პარტნიორი":
            return c
    return None


def _find_tbc_additional_purpose_column(cols):
    """TBC: 'დამატებითი დანიშნულება' — not the main 'დანიშნულება'."""
    for c in cols:
        if str(c).strip() == "დამატებითი დანიშნულება":
            return c
    return None


def _excel_cell(row, col):
    if col is None or col not in row.index:
        return ""
    v = row[col]
    if pd.isna(v):
        return ""
    return str(v).strip()


# ---------------------------------------------------------------------------
# Shared Excel writer
# ---------------------------------------------------------------------------

def _save_excel(rows, download_dir, filename):
    """Common Excel save: empty check → openpyxl check → DataFrame → to_excel. Returns path or None."""
    if isinstance(rows, pd.DataFrame):
        if rows.empty:
            return None
        out_df = rows
    else:
        if not rows:
            return None
        out_df = pd.DataFrame(rows)
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        logger.warning("Excel-ისთვის დააყენე: pip install openpyxl")
        return None
    os.makedirs(download_dir, exist_ok=True)
    path = os.path.join(download_dir, filename)
    out_df.to_excel(path, index=False, engine="openpyxl")
    return path


# ---------------------------------------------------------------------------
# Imported products file reading helpers
# ---------------------------------------------------------------------------

def _read_imported_products_csv(path):
    """შემოტანილი პროდუქციის CSV export: utf-8/Excel სხვადასხვა encoding-ის fallback."""
    last_error = None
    for enc in IMPORTED_PRODUCTS_CSV_ENCODINGS:
        for sep in (",", ";", None):
            try:
                if sep is None:
                    df = pd.read_csv(
                        path,
                        encoding=enc,
                        sep=None,
                        engine="python",
                        low_memory=False,
                    )
                else:
                    df = pd.read_csv(
                        path,
                        encoding=enc,
                        sep=sep,
                        low_memory=False,
                    )
                if df.shape[1] < 5:
                    continue
                df = df.copy()
                df.columns = [str(c).strip() for c in df.columns]
                unnamed_cols = [
                    c for c in df.columns if str(c).strip().startswith("Unnamed:")
                ]
                if unnamed_cols:
                    df = df.drop(columns=unnamed_cols, errors="ignore")
                return df
            except Exception as exc:
                last_error = exc
                continue
    if last_error is not None:
        raise last_error
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _read_imported_products_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return _read_imported_products_csv(path), "csv", None
    return pd.read_excel(path, sheet_name=IMPORTED_PRODUCTS_SHEET_NAME), "excel", IMPORTED_PRODUCTS_SHEET_NAME


# ---------------------------------------------------------------------------
# Bank debit verification
# ---------------------------------------------------------------------------

def _bank_positive_debit_total_ge():
    """BOG+TBC all files positive debit total — same filter as get_bank_payments."""
    from dashboard_pipeline.bank_cache import (
        list_bog_statement_paths,
        read_bank_statement,
    )
    from dashboard_pipeline.tbc_cache import list_tbc_statement_paths

    total = 0.0
    for f in list_bog_statement_paths():
        try:
            df = read_bank_statement(f)
            cols = df.columns
            debit_col = next(
                (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None
            )
            if not debit_col:
                continue
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                total += float(amt)
        except Exception:
            continue
    for f in list_tbc_statement_paths():
        try:
            df = read_bank_statement(f)
            cols = df.columns
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            if not debit_col:
                continue
            df = df[
                ~df[debit_col]
                .astype(str)
                .str.contains("Paid|Out|Amount", case=False, na=False)
            ]
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                total += float(amt)
        except Exception:
            continue
    return float(total)


def verify_bank_debit_totals(matched_bank_sum, unmatched_rows, exit_on_fail=True):
    """Verify: bank debit total (Excel) = matched + unmatched."""
    import sys
    tol = 0.02
    bank_total = _bank_positive_debit_total_ge()
    unmatched_sum = sum(float(r.get("თანხა") or 0) for r in unmatched_rows)
    expected = float(matched_bank_sum) + float(unmatched_sum)
    delta = bank_total - expected
    if abs(delta) <= tol:
        logger.info(
            f"  [რეკონცილიაცია OK] ბანკის დებეტი {bank_total:,.2f} ₾ = მიბმული {matched_bank_sum:,.2f} ₾ + არამიბმული {unmatched_sum:,.2f} ₾"
        )
        return True
    logger.error(
        f"  [რეკონცილიაცია ჩავარდა] ბანკის დებეტი (Excel) {bank_total:,.2f} ₾ ≠ მიბმული {matched_bank_sum:,.2f} ₾ + არამიბმული {unmatched_sum:,.2f} ₾ = {expected:,.2f} ₾ | სხვაობა {delta:,.2f} ₾"
    )
    if exit_on_fail:
        sys.exit(1)
    return False


def _normalize_iban_ge(cell_val):
    """IBAN from cell — no spaces/GEL suffix."""
    if cell_val is None or (isinstance(cell_val, float) and pd.isna(cell_val)):
        return None
    s = re.sub(r"\s+", "", str(cell_val).upper())
    s = s.replace("GEL", "")
    m = re.search(r"GE\d{2}[A-Z0-9]{16,22}", s)
    return m.group(0) if m else None
