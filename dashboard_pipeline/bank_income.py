"""
Bank income & expense collection: POS terminal income (TBC/BOG),
expense categories, samurneo flow, tax flow, foodmart cashback,
and related Excel writers.
"""
import json
import os
import re
from collections import defaultdict

import pandas as pd

from dashboard_pipeline.logging_config import get_logger
from dashboard_pipeline.constants import (
    SAMURNEO_EXPENSE_DIRECTION_KA,
    SAMURNEO_RETURN_DIRECTION_KA,
    SAMURNEO_LABEL_KA,
    SAMURNEO_ACCOUNTING_NOTE_KA,
    SAMURNEO_LEDGER_CLASS_KA,
    TAX_TREASURY_CLUSTER_NOTE_KA,
    ACCOUNTING_ROLE_OPERATING,
    ACCOUNTING_ROLE_STATE_TREASURY,
    TBC_OTHER_EXPENSE_ID,
    TBC_OTHER_EXPENSE_LABEL_KA,
    BOG_OTHER_EXPENSE_ID,
    BOG_OTHER_EXPENSE_LABEL_KA,
    OBJECT_UNALLOCATED,
    _clone_default_object_mapping,
    _monthly_summary,
    _daily_summary,
    _day_key,
    _object_order_for_pos,
    detect_object,
)
from dashboard_pipeline.file_utils import (
    find_header_row,
    _excel_cell,
    _save_excel,
    list_bog_bank_statement_xlsx,
    list_tbc_bank_statement_xlsx,
    _find_excel_column_danishnuleba,
)
from dashboard_pipeline.config_loaders import load_object_mapping

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Text joining helpers (TBC/BOG row text extraction)
# ---------------------------------------------------------------------------

def _tbc_income_row_text_join(row, cols, credit_col):
    parts = []
    for c in cols:
        if c == credit_col:
            continue
        v = row[c]
        if pd.notna(v) and str(v).strip():
            parts.append(str(v))
    return " ".join(parts)


def _tbc_row_text_join_skip(row, cols, skip_cols=None):
    skip = set(skip_cols or [])
    parts = []
    for c in cols:
        if c in skip:
            continue
        v = row[c]
        if pd.notna(v) and str(v).strip():
            parts.append(str(v))
    return " ".join(parts)


def _tbc_income_matches_blob(blob_lower, patterns, iban_hints):
    for p in patterns:
        if p.lower() in blob_lower:
            return True
    compact_upper = re.sub(r"\s+", "", blob_lower).upper()
    for ib in iban_hints:
        ibc = re.sub(r"\s+", "", str(ib).upper())
        if ibc and ibc in compact_upper:
            return True
    return False


# ---------------------------------------------------------------------------
# Samurneo (საქმიანობისთვის აუცილებელი ხარჯი) — TBC + BOG
# ---------------------------------------------------------------------------

def collect_tbc_samurneo_flow(script_dir):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_samurneo_patterns.json")
    patterns = []
    include_all = True
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            include_all = bool(cfg.get("include_all_transactions", True))
            patterns = [str(x).lower() for x in (cfg.get("match_substrings") or []) if str(x).strip()]
        except Exception:
            include_all = True
            patterns = []

    out_exp = []
    out_ret = []
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col])
                blob = raw.lower()
                if (not include_all) and patterns and (not any(p in blob for p in patterns)):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {"ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col),
                        "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw}
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_exp.append({**base, "თანხა": float(debit_amt), "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA})
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    out_ret.append({**base, "თანხა": float(credit_amt), "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA})
        except Exception as e:
            logger.error("TBC samurneo %s: %s", f, e)

    exp_total = sum(float(r.get("თანხა") or 0) for r in out_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in out_ret)
    return {
        "expense_total_ge": float(exp_total), "return_total_ge": float(ret_total),
        "net_ge": float(ret_total - exp_total),
        "expense_line_count": len(out_exp), "return_line_count": len(out_ret),
        "expense_rows_preview": out_exp[:300], "return_rows_preview": out_ret[:300],
        "expense_monthly_summary": _monthly_summary(out_exp),
        "return_monthly_summary": _monthly_summary(out_ret),
    }


def collect_bog_samurneo_flow(script_dir):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_samurneo_patterns.json")
    patterns = []
    include_all = True
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            include_all = bool(cfg.get("include_all_transactions", True))
            patterns = [str(x).lower() for x in (cfg.get("match_substrings") or []) if str(x).strip()]
        except Exception:
            include_all = True
            patterns = []

    out_exp = []
    out_ret = []
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None)
            credit_col = next((c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col])
                blob = raw.lower()
                if (not include_all) and patterns and (not any(p in blob for p in patterns)):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {"ბანკი": "BOG", "ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col),
                        "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw}
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_exp.append({**base, "თანხა": float(debit_amt), "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA})
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    out_ret.append({**base, "თანხა": float(credit_amt), "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA})
        except Exception as e:
            logger.error("BOG samurneo %s: %s", f, e)

    exp_total = sum(float(r.get("თანხა") or 0) for r in out_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in out_ret)
    return {
        "expense_total_ge": float(exp_total), "return_total_ge": float(ret_total),
        "net_ge": float(ret_total - exp_total),
        "expense_line_count": len(out_exp), "return_line_count": len(out_ret),
        "expense_rows_preview": out_exp[:300], "return_rows_preview": out_ret[:300],
        "expense_monthly_summary": _monthly_summary(out_exp),
        "return_monthly_summary": _monthly_summary(out_ret),
    }


def merge_samurneo_flows(tbc_bundle, bog_bundle):
    tbc_bundle = tbc_bundle or {}
    bog_bundle = bog_bundle or {}
    tbc_exp = float(tbc_bundle.get("expense_total_ge") or 0)
    tbc_ret = float(tbc_bundle.get("return_total_ge") or 0)
    bog_exp = float(bog_bundle.get("expense_total_ge") or 0)
    bog_ret = float(bog_bundle.get("return_total_ge") or 0)
    all_exp_rows = (tbc_bundle.get("expense_rows_preview") or []) + (bog_bundle.get("expense_rows_preview") or [])
    all_ret_rows = (tbc_bundle.get("return_rows_preview") or []) + (bog_bundle.get("return_rows_preview") or [])
    return {
        "tbc_expense_total_ge": tbc_exp, "tbc_return_total_ge": tbc_ret,
        "bog_expense_total_ge": bog_exp, "bog_return_total_ge": bog_ret,
        "expense_total_ge": float(tbc_exp + bog_exp), "return_total_ge": float(tbc_ret + bog_ret),
        "net_ge": float((tbc_ret + bog_ret) - (tbc_exp + bog_exp)),
        "expense_line_count": int((tbc_bundle.get("expense_line_count") or 0) + (bog_bundle.get("expense_line_count") or 0)),
        "return_line_count": int((tbc_bundle.get("return_line_count") or 0) + (bog_bundle.get("return_line_count") or 0)),
        "expense_rows_preview": all_exp_rows[:300], "return_rows_preview": all_ret_rows[:300],
        "expense_monthly_summary": _monthly_summary(all_exp_rows),
        "return_monthly_summary": _monthly_summary(all_ret_rows),
        "label_ka": SAMURNEO_LABEL_KA,
        "accounting_note_ka": SAMURNEO_ACCOUNTING_NOTE_KA,
        "ledger_classification_ka": SAMURNEO_LEDGER_CLASS_KA,
    }


def write_tbc_samurneo_excel(bundle, download_dir):
    exp_rows = bundle.get("expense_rows_preview", [])
    ret_rows = bundle.get("return_rows_preview", [])
    all_rows = []
    for r in exp_rows:
        all_rows.append({
            "ბანკი": r.get("ბანკი", "TBC"), "ბუღალტრული_კლასიფიკაცია": SAMURNEO_LEDGER_CLASS_KA,
            "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA, "ფაილი": r.get("ფაილი", ""),
            "თარიღი": r.get("თარიღი", ""), "თანხა": float(r.get("თანხა") or 0),
            "საინით": -abs(float(r.get("თანხა") or 0)), "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
        })
    for r in ret_rows:
        all_rows.append({
            "ბანკი": r.get("ბანკი", "TBC"), "ბუღალტრული_კლასიფიკაცია": SAMURNEO_LEDGER_CLASS_KA,
            "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA, "ფაილი": r.get("ფაილი", ""),
            "თარიღი": r.get("თარიღი", ""), "თანხა": float(r.get("თანხა") or 0),
            "საინით": abs(float(r.get("თანხა") or 0)), "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", ""),
        })
    path = _save_excel(all_rows, download_dir, "TBC_სამეურნეო_მოძრაობა.xlsx")
    if path:
        logger.info(
            f"  Excel (სამეურნეო / საქმიანობისთვის აუცილებელი ხარჯი) → {path} "
            f"(გასვლა {bundle.get('expense_total_ge', 0):,.2f} ₾ | დაბრუნება {bundle.get('return_total_ge', 0):,.2f} ₾)"
        )


# ---------------------------------------------------------------------------
# Tax flow (საგადასახადო მოძრაობა — BOG + TBC)
# ---------------------------------------------------------------------------

def collect_tax_flow(script_dir):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tax_flow_patterns.json")
    default_patterns = [
        "საშემოსავლო", "გადასახად", "ბიუჯეტ", "revenue service", "rs.ge",
        "treasury", "tresge22", "204931440", "ge24nb0330100200165022",
        "ge60bg0000000667583800rs", "ge04bg0000000201978600rs",
    ]
    treasury_in_markers = ["tresge22", "სახელმწიფო ხაზინა", "204931440", "ge24nb0330100200165022"]
    patterns = default_patterns
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            patterns = [str(x).lower() for x in (cfg.get("match_substrings") or []) if str(x).strip()] or default_patterns
        except Exception:
            patterns = default_patterns

    out_rows = []
    in_rows = []
    treasury_in_rows = []

    # BOG
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None)
            credit_col = next((c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col]).lower()
                if not any(p in raw for p in patterns):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {"ბანკი": "BOG", "ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col), "ტექსტი_მოკლე": raw[:500]}
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_rows.append({**base, "თანხა": float(debit_amt), "მიმართულება": "საგადასახადო გადარიცხული"})
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    in_rec = {**base, "თანხა": float(credit_amt), "მიმართულება": "საგადასახადო ჩარიცხული"}
                    in_rows.append(in_rec)
                    if any(m in raw for m in treasury_in_markers):
                        treasury_in_rows.append({**in_rec, "მიმართულება": "სახელმწიფო ხაზინიდან ჩარიცხული"})
        except Exception as e:
            logger.error("BOG tax flow %s: %s", f, e)

    # TBC
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
            if not debit_col and not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col]).lower()
                if not any(p in raw for p in patterns):
                    continue
                debit_amt = pd.to_numeric(row[debit_col], errors="coerce") if debit_col else float("nan")
                credit_amt = pd.to_numeric(row[credit_col], errors="coerce") if credit_col else float("nan")
                base = {"ბანკი": "TBC", "ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col), "ტექსტი_მოკლე": raw[:500]}
                if pd.notna(debit_amt) and float(debit_amt) > 0:
                    out_rows.append({**base, "თანხა": float(debit_amt), "მიმართულება": "საგადასახადო გადარიცხული"})
                if pd.notna(credit_amt) and float(credit_amt) > 0:
                    in_rec = {**base, "თანხა": float(credit_amt), "მიმართულება": "საგადასახადო ჩარიცხული"}
                    in_rows.append(in_rec)
                    if any(m in raw for m in treasury_in_markers):
                        treasury_in_rows.append({**in_rec, "მიმართულება": "სახელმწიფო ხაზინიდან ჩარიცხული"})
        except Exception as e:
            logger.error("TBC tax flow %s: %s", f, e)

    out_total = sum(float(r.get("თანხა") or 0) for r in out_rows)
    in_total = sum(float(r.get("თანხა") or 0) for r in in_rows)
    treasury_in_total = sum(float(r.get("თანხა") or 0) for r in treasury_in_rows)
    return {
        "label_ka": "საგადასახადო / ბიუჯეტი / სახელმწიფო ხაზინა (ბანკის ფილტრი)",
        "ledger_note_ka": TAX_TREASURY_CLUSTER_NOTE_KA,
        "out_total_ge": float(out_total), "in_total_ge": float(in_total),
        "treasury_in_total_ge": float(treasury_in_total),
        "net_ge": float(in_total - out_total),
        "out_line_count": len(out_rows), "in_line_count": len(in_rows),
        "treasury_in_line_count": len(treasury_in_rows),
        "out_rows_preview": out_rows[:300], "in_rows_preview": in_rows[:300],
        "treasury_in_rows_preview": treasury_in_rows[:300],
        "out_monthly_summary": _monthly_summary(out_rows),
        "in_monthly_summary": _monthly_summary(in_rows),
        "treasury_in_monthly_summary": _monthly_summary(treasury_in_rows),
    }


def write_tax_flow_excel(bundle, download_dir):
    out_rows = bundle.get("out_rows_preview", [])
    in_rows = bundle.get("in_rows_preview", [])
    rows = []
    for r in out_rows:
        rows.append({"ბანკი": r.get("ბანკი", ""), "მიმართულება": "საგადასახადო გადარიცხული",
                      "ფაილი": r.get("ფაილი", ""), "თარიღი": r.get("თარიღი", ""),
                      "თანხა": float(r.get("თანხა") or 0), "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", "")})
    for r in in_rows:
        rows.append({"ბანკი": r.get("ბანკი", ""), "მიმართულება": "საგადასახადო ჩარიცხული",
                      "ფაილი": r.get("ფაილი", ""), "თარიღი": r.get("თარიღი", ""),
                      "თანხა": float(r.get("თანხა") or 0), "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", "")})
    path = _save_excel(rows, download_dir, "საგადასახადო_მოძრაობა.xlsx")
    if path:
        logger.info(f"  Excel (საგადასახადო) → {path} "
                     f"(გადარიცხული {bundle.get('out_total_ge', 0):,.2f} ₾ | ჩარიცხული {bundle.get('in_total_ge', 0):,.2f} ₾)")


def write_treasury_incoming_excel(bundle, download_dir):
    rows = [{"ბანკი": r.get("ბანკი", ""), "მიმართულება": "სახელმწიფო ხაზინიდან ჩარიცხული",
             "ფაილი": r.get("ფაილი", ""), "თარიღი": r.get("თარიღი", ""),
             "თანხა": float(r.get("თანხა") or 0), "ტექსტი_მოკლე": r.get("ტექსტი_მოკლე", "")}
            for r in bundle.get("treasury_in_rows_preview", [])]
    path = _save_excel(rows, download_dir, "სახელმწიფო_ხაზინა_ჩარიცხვები.xlsx")
    if path:
        logger.info(f"  Excel (სახელმწიფო ხაზინა ჩარიცხვები) → {path} "
                     f"({bundle.get('treasury_in_line_count', 0)} ხაზი, {bundle.get('treasury_in_total_ge', 0):,.2f} ₾)")


# ---------------------------------------------------------------------------
# Foodmart cashback (TBC)
# ---------------------------------------------------------------------------

def collect_tbc_foodmart_cashback(script_dir):
    patterns = ["ფუდმარტ", "foodmart", "404460187", "ge06tb7064936020100010",
                "ქეშბექ", "cashback", "cash back", "მომსახურების ღირებულება"]
    rows = []
    total = 0.0
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
            if not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[credit_col], errors="coerce")
                if pd.isna(amt) or float(amt) <= 0:
                    continue
                raw = _tbc_row_text_join_skip(row, cols, [credit_col]).lower()
                if not any(p in raw for p in patterns):
                    continue
                total += float(amt)
                rows.append({"ბანკი": "TBC", "ფაილი": os.path.basename(f),
                             "თარიღი": _excel_cell(row, date_col), "თანხა": float(amt), "ტექსტი_მოკლე": raw[:500]})
        except Exception as e:
            logger.error("TBC foodmart cashback %s: %s", f, e)
    return {"label_ka": "ფუდმარტის ქეშბექი/შემოსავალი", "total_ge": float(total),
            "line_count": len(rows), "rows_preview": rows[:300], "monthly_summary": _monthly_summary(rows)}


def write_tbc_foodmart_cashback_excel(bundle, download_dir):
    rows = bundle.get("rows_preview", [])
    path = _save_excel(rows, download_dir, "TBC_ფუდმარტი_ქეშბექი.xlsx")
    if path:
        logger.info(f"  Excel (TBC ფუდმარტი ქეშბექი) → {path} "
                     f"({bundle.get('line_count', 0)} ხაზი, {bundle.get('total_ge', 0):,.2f} ₾)")


# ---------------------------------------------------------------------------
# POS terminal income (BOG + TBC)
# ---------------------------------------------------------------------------

def collect_bog_pos_terminal_income(script_dir, object_mapping=None):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "bog_pos_terminal_income_patterns.json")
    default_patterns = ["გადახდა - თარიღი", "ტერმინალის id", "ბარათი:", "ტრანზაქციის დეტალები",
                        "დანიშნულება ჩარიცხვა", "pos", "პოს"]
    patterns = default_patterns
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            patterns = [str(x).lower() for x in (cfg.get("match_substrings") or []) if str(x).strip()] or default_patterns
        except Exception:
            patterns = default_patterns

    object_mapping = object_mapping or load_object_mapping(script_dir)
    lines = []
    total = 0.0
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            credit_col = next((c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)), None)
            if not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[credit_col], errors="coerce")
                if pd.isna(amt) or float(amt) <= 0:
                    continue
                raw = _tbc_row_text_join_skip(row, cols, [credit_col])
                blob_lower = raw.lower()
                if not any(p in blob_lower for p in patterns):
                    continue
                total += float(amt)
                lines.append({"ბანკი": "BOG", "ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col),
                              "თანხა": float(amt), "object": detect_object("bog_pos", text=raw, object_mapping=object_mapping),
                              "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw})
        except Exception as e:
            logger.error("BOG POS income %s: %s", f, e)
    return {"label_ka": "POS ტერმინალის შემოსავალი (BOG)", "total_ge": float(total), "line_count": len(lines), "lines": lines}


def collect_tbc_card_income(script_dir, object_mapping=None):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_card_income_patterns.json")
    empty = {"total_ge": 0.0, "lines": [], "line_count": 0, "label_ka": ""}
    if not os.path.isfile(cfg_path):
        return empty
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return empty
    patterns = [str(p) for p in cfg.get("match_substrings", []) if str(p).strip()]
    iban_hints = [str(p) for p in cfg.get("iban_hints", []) if str(p).strip()]
    label_ka = str(cfg.get("label_ka", "") or "")
    if not patterns and not iban_hints:
        return {**empty, "label_ka": label_ka}

    object_mapping = object_mapping or load_object_mapping(script_dir)
    lines = []
    total = 0.0
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            credit_col = next((c for c in cols if "შემოსული" in str(c) and "გასული" not in str(c)), None)
            if not credit_col:
                credit_col = next((c for c in cols if "incoming" in str(c).lower()), None)
            if not credit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[credit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                raw = _tbc_income_row_text_join(row, cols, credit_col)
                blob_lower = raw.lower()
                if not _tbc_income_matches_blob(blob_lower, patterns, iban_hints):
                    continue
                total += float(amt)
                lines.append({"ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col),
                              "თანხა": float(amt), "object": detect_object("tbc_pos", text=raw, object_mapping=object_mapping),
                              "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw})
        except Exception as e:
            logger.error("TBC card income %s: %s", f, e)
    return {"total_ge": total, "lines": lines, "line_count": len(lines), "label_ka": label_ka}


def merge_pos_terminal_income(tbc_bundle, bog_bundle, object_mapping=None):
    object_mapping = object_mapping or _clone_default_object_mapping()
    pos_objects = _object_order_for_pos(object_mapping)
    default_object = str(object_mapping.get("default_object") or OBJECT_UNALLOCATED)
    tbc_total = float((tbc_bundle or {}).get("total_ge") or 0)
    bog_total = float((bog_bundle or {}).get("total_ge") or 0)
    tbc_lines = list((tbc_bundle or {}).get("lines") or [])
    bog_lines = list((bog_bundle or {}).get("lines") or [])
    all_lines = tbc_lines + bog_lines
    tbc_daily = _daily_summary(tbc_lines)
    bog_daily = _daily_summary(bog_lines)
    tbc_daily_map = {r.get("day"): float(r.get("total_ge") or 0) for r in tbc_daily}
    bog_daily_map = {r.get("day"): float(r.get("total_ge") or 0) for r in bog_daily}
    all_days = sorted(set(tbc_daily_map.keys()) | set(bog_daily_map.keys()))
    object_daily = defaultdict(lambda: defaultdict(float))
    for line in all_lines:
        d = _day_key(line.get("თარიღი"))
        obj = str(line.get("object") or default_object)
        object_daily[d][obj] += float(line.get("თანხა") or 0)
    daily_combined = []
    for d in all_days:
        tbc_d = float(tbc_daily_map.get(d) or 0)
        bog_d = float(bog_daily_map.get(d) or 0)
        daily_combined.append({"day": d, "tbc_total_ge": tbc_d, "bog_total_ge": bog_d,
                               "total_ge": float(tbc_d + bog_d),
                               "by_object": {obj: float(object_daily[d].get(obj) or 0) for obj in pos_objects}})
    return {
        "label_ka": "POS ტერმინალის შემოსავალი (TBC+BOG)",
        "tbc_total_ge": float(tbc_total), "bog_total_ge": float(bog_total),
        "total_ge": float(tbc_total + bog_total),
        "tbc_line_count": int((tbc_bundle or {}).get("line_count") or 0),
        "bog_line_count": int((bog_bundle or {}).get("line_count") or 0),
        "line_count": len(all_lines), "rows_preview": all_lines[:400],
        "monthly_summary": _monthly_summary(all_lines), "daily_summary": daily_combined,
    }


def write_pos_terminal_income_excel(bundle, download_dir, full_rows=None):
    rows = list(full_rows or []) or bundle.get("rows_preview", [])
    path = _save_excel(rows, download_dir, "POS_ტერმინალი_TBC_BOG.xlsx")
    if path:
        logger.info(f"  Excel (POS ტერმინალი TBC+BOG) → {path} "
                     f"(TBC {bundle.get('tbc_total_ge', 0):,.2f} ₾ | BOG {bundle.get('bog_total_ge', 0):,.2f} ₾ | "
                     f"ჯამი {bundle.get('total_ge', 0):,.2f} ₾ | ხაზები {len(rows)})")


def write_tbc_card_income_excel(lines, download_dir):
    path = _save_excel(lines, download_dir, "TBC_ბარათის_შემოსავალი.xlsx")
    if path:
        tot = sum(float(r.get("თანხა") or 0) for r in lines)
        logger.info(f"  Excel (TBC ბარათის შემოსავალი) → {path} ({len(lines)} ხაზი, {tot:,.2f} ₾)")


# ---------------------------------------------------------------------------
# Expense categories (TBC + BOG)
# ---------------------------------------------------------------------------

def _tbc_expense_cat_matches(cat, blob_lower):
    mall = [str(x).lower() for x in (cat.get("match_all") or []) if str(x).strip()]
    if mall and all(m in blob_lower for m in mall):
        return True
    return _tbc_income_matches_blob(blob_lower, cat["patterns"], [])


def _match_tbc_expense_category(blob_lower, cats_norm):
    compact_upper = re.sub(r"\s+", "", blob_lower).upper()
    for cat in cats_norm:
        if _tbc_expense_cat_matches(cat, blob_lower):
            return cat["id"]
    for cat in cats_norm:
        for ib in cat["ibans"]:
            ibc = re.sub(r"\s+", "", str(ib).upper())
            if ibc and ibc in compact_upper:
                return cat["id"]
    return None


def _is_non_operating_tbc_residual(blob_lower):
    text = (blob_lower or "").strip()
    if not text:
        return False
    treasury_markers = ("revenue service", "rs.ge", "tresge", "სახაზინო", "ხაზინის", "საბიუჯეტო", "გადასახადების ერთიანი კოდი")
    internal_transfer_markers = ("internal transfer", "between own accounts", "own account transfer", "საკუთარ ანგარიშ", "შიდა გადარიცხ")
    all_markers = treasury_markers + internal_transfer_markers
    return any(marker in text for marker in all_markers)


def _normalize_cats_from_json(raw_cats):
    cats_norm = []
    for c in raw_cats:
        cid = str(c.get("id", "")).strip()
        if not cid:
            continue
        role = str(c.get("accounting_role") or ACCOUNTING_ROLE_OPERATING).strip()
        if role not in (ACCOUNTING_ROLE_OPERATING, ACCOUNTING_ROLE_STATE_TREASURY):
            role = ACCOUNTING_ROLE_OPERATING
        cats_norm.append({
            "id": cid, "label_ka": str(c.get("label_ka", "") or ""), "accounting_role": role,
            "patterns": [str(p) for p in c.get("match_substrings", []) if str(p).strip()],
            "match_all": [str(p) for p in c.get("match_all_substrings", []) if str(p).strip()],
            "ibans": [str(p) for p in c.get("iban_hints", []) if str(p).strip()],
        })
    return cats_norm


def collect_tbc_expense_categories(script_dir, object_mapping=None):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_expense_categories.json")
    empty = {"categories": [], "grand_total_ge": 0.0, "grand_total_operating_expense_ge": 0.0, "grand_total_state_treasury_ge": 0.0}
    if not os.path.isfile(cfg_path):
        return empty
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return empty
    raw_cats = cfg.get("categories", [])
    if not raw_cats:
        return empty
    cats_norm = _normalize_cats_from_json(raw_cats)
    if not cats_norm:
        return empty

    other_cat = {"id": TBC_OTHER_EXPENSE_ID, "label_ka": TBC_OTHER_EXPENSE_LABEL_KA,
                 "accounting_role": ACCOUNTING_ROLE_OPERATING, "patterns": [], "match_all": [], "ibans": []}
    cats_with_other = list(cats_norm) + [other_cat]
    object_mapping = object_mapping or load_object_mapping(script_dir)
    buckets = {c["id"]: [] for c in cats_with_other}
    for f in list_tbc_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
            if not debit_col:
                continue
            df = df[~df[debit_col].astype(str).str.contains("Paid|Out|Amount", case=False, na=False)]
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                raw = _tbc_income_row_text_join(row, cols, debit_col)
                blob_lower = raw.lower()
                mid = _match_tbc_expense_category(blob_lower, cats_norm)
                if not mid:
                    if _is_non_operating_tbc_residual(blob_lower):
                        continue
                    mid = TBC_OTHER_EXPENSE_ID
                obj_source = "tbc_salary" if mid == "salary_payments" else "tbc_expense"
                buckets[mid].append({
                    "კატეგორია_id": mid, "ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col),
                    "თანხა": float(amt), "object": detect_object(obj_source, text=raw, object_mapping=object_mapping),
                    "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
                })
        except Exception as e:
            logger.error("TBC expenses %s: %s", f, e)

    return _build_expense_result(cats_with_other, buckets)


def collect_bog_expense_categories(script_dir, object_mapping=None):
    cfg_path = os.path.join(script_dir, "Financial_Analysis", "tbc_expense_categories.json")
    empty = {"categories": [], "grand_total_ge": 0.0, "grand_total_operating_expense_ge": 0.0, "grand_total_state_treasury_ge": 0.0}
    if not os.path.isfile(cfg_path):
        return empty
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return empty
    raw_cats = cfg.get("categories", [])
    if not raw_cats:
        return empty
    cats_norm = _normalize_cats_from_json(raw_cats)
    if not cats_norm:
        return empty

    other_cat = {"id": BOG_OTHER_EXPENSE_ID, "label_ka": BOG_OTHER_EXPENSE_LABEL_KA,
                 "accounting_role": ACCOUNTING_ROLE_OPERATING, "patterns": [], "match_all": [], "ibans": []}
    cats_with_other = list(cats_norm) + [other_cat]
    object_mapping = object_mapping or load_object_mapping(script_dir)
    buckets = {c["id"]: [] for c in cats_with_other}
    for f in list_bog_bank_statement_xlsx():
        try:
            header_idx = find_header_row(f)
            df = pd.read_excel(f, header=header_idx)
            cols = list(df.columns)
            debit_col = next((c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)), None)
            if not debit_col:
                continue
            date_col = next((c for c in cols if "თარიღი" in str(c)), None)
            operation_col = next((c for c in cols if "ოპერაციის შინაარსი" in str(c)), None)
            purpose_col = _find_excel_column_danishnuleba(cols)
            receiver_col = next((c for c in cols if "მიმღების დასახელება" in str(c)), None)
            for _, row in df.iterrows():
                amt = pd.to_numeric(row[debit_col], errors="coerce")
                if pd.isna(amt) or amt <= 0:
                    continue
                text_parts = []
                for col in (operation_col, purpose_col, receiver_col):
                    val = _excel_cell(row, col)
                    if val:
                        text_parts.append(val)
                raw = " | ".join(text_parts).strip()
                if not raw:
                    raw = _tbc_row_text_join_skip(row, cols, [debit_col])
                blob_lower = raw.lower()
                mid = _match_tbc_expense_category(blob_lower, cats_norm)
                if not mid:
                    mid = BOG_OTHER_EXPENSE_ID
                obj_source = "tbc_salary" if mid == "salary_payments" else "tbc_expense"
                buckets[mid].append({
                    "კატეგორია_id": mid, "ფაილი": os.path.basename(f), "თარიღი": _excel_cell(row, date_col),
                    "თანხა": float(amt), "object": detect_object(obj_source, text=raw, object_mapping=object_mapping),
                    "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
                })
        except Exception as e:
            logger.error("BOG expenses %s: %s", f, e)

    return _build_expense_result(cats_with_other, buckets)


def _build_expense_result(cats_with_other, buckets):
    out_cats = []
    grand = 0.0
    grand_operating = 0.0
    grand_treasury = 0.0
    label_by_id = {c["id"]: c["label_ka"] for c in cats_with_other}
    for c in cats_with_other:
        cid = c["id"]
        role = c.get("accounting_role") or ACCOUNTING_ROLE_OPERATING
        lines = buckets.get(cid, [])
        t = sum(float(x.get("თანხა") or 0) for x in lines)
        grand += t
        if role == ACCOUNTING_ROLE_STATE_TREASURY:
            grand_treasury += t
        else:
            grand_operating += t
        out_cats.append({"id": cid, "label_ka": label_by_id.get(cid, cid), "accounting_role": role,
                         "total_ge": float(t), "line_count": len(lines), "lines": lines, "rows_preview": lines[:150]})
    return {"categories": out_cats, "grand_total_ge": float(grand),
            "grand_total_operating_expense_ge": float(grand_operating),
            "grand_total_state_treasury_ge": float(grand_treasury)}


def write_tbc_expenses_excel(tbc_expenses_bundle, download_dir):
    cats = tbc_expenses_bundle.get("categories") or []
    rows = []
    for c in cats:
        label = c.get("label_ka", c.get("id", ""))
        role = c.get("accounting_role") or ACCOUNTING_ROLE_OPERATING
        role_ka = "სახელმწიფო ხაზინა" if role == ACCOUNTING_ROLE_STATE_TREASURY else "საოპერაციო ხარჯი"
        for line in c.get("lines") or []:
            r = dict(line)
            r["კატეგორია"] = label
            r["ბუღალტრული_როლი"] = role_ka
            rows.append(r)
    path = _save_excel(rows, download_dir, "TBC_ხარჯები_კატეგორიები.xlsx")
    if path:
        tot = sum(float(r.get("თანხა") or 0) for r in rows)
        logger.info(f"  Excel (TBC ხარჯები კატეგორიებით) → {path} ({len(rows)} ხაზი, {tot:,.2f} ₾)")


# write_suppliers_excel lives here since it's a bank-related Excel export
def write_suppliers_excel(suppliers_data, download_dir):
    rows = [{"ორგანიზაცია": r.get("ორგანიზაცია"), "რაოდენობა": r.get("waybills_count"),
             "ნომინალური": float(r.get("total_nominal") or 0), "რეალური ჯამი": float(r.get("total_effective") or 0),
             "strict ბანკით გადახდა": float(r.get("strict_bank_paid") or r.get("bank_paid") or 0),
             "ნაღდით გადახდა": float(r.get("manual_paid") or 0),
             "სულ გადახდილი": float(r.get("total_paid") or 0),
             "დავალიანება": float(r.get("total_debt") or 0),
             "გადახდის scope": r.get("payment_scope")}
            for r in (suppliers_data or [])]
    path = _save_excel(rows, download_dir, "მომწოდებლები_RS.xlsx")
    if path:
        logger.info(f"  Excel → {path}")
