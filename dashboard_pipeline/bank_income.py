"""
Bank income & expense collection: POS terminal income (TBC/BOG),
expense categories, samurneo flow, tax flow, foodmart cashback,
and related Excel writers.
"""
import hashlib
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
from dashboard_pipeline.bank_cache import (
    list_bog_statement_paths,
    read_bank_statement,
)
from dashboard_pipeline.tbc_cache import list_tbc_statement_paths
from dashboard_pipeline.file_utils import (
    find_header_row,
    _excel_cell,
    _save_excel,
    list_bog_bank_statement_xlsx,
    list_tbc_bank_statement_xlsx,
    _find_excel_column_danishnuleba,
)
from dashboard_pipeline.config_loaders import load_object_mapping
from dashboard_pipeline.pipeline_cache import (
    DEFAULT_CACHE_FILENAME,
    compute_file_signature,
    empty_cache,
    file_has_changed,
    get_payload,
    load_cache,
    put_entry,
    save_cache,
)

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


# Physical TBC POS terminal IDs seen in RS.ge official POS export
# (Financial_Analysis/ანგარიშ ფაქტურები/პოს ტერმინალი.xls, 2022-06 → 2026-02).
# Matching by terminal ID eliminates 2.8M ₾ double-count from transit sweeps
# ("ნავაჭრი", "ტერმინალებში მიღებული") that aggregate per-transaction rows.
_DEFAULT_TBC_TERMINAL_IDS = (
    "RS014189",
    "SH079927",
    "SH046092",
    "SH034467",
    "SH060853",
)


def _tbc_income_row_has_terminal(raw, terminal_ids):
    for t in terminal_ids:
        if t and t in raw:
            return True
    return False


# ---------------------------------------------------------------------------
# Samurneo (საქმიანობისთვის აუცილებელი ხარჯი) — TBC + BOG
# ---------------------------------------------------------------------------

def _load_samurneo_patterns(script_dir):
    """Read the shared samurneo config (returns (patterns, include_all)).

    `collect_bog_samurneo_flow` intentionally reads the same
    `tbc_samurneo_patterns.json` — the filter substrings are bank-agnostic.
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "tbc_samurneo_patterns.json"
    )
    if not os.path.isfile(cfg_path):
        return [], True
    try:
        with open(cfg_path, encoding="utf-8") as handle:
            cfg = json.load(handle)
    except Exception:
        return [], True
    include_all = bool(cfg.get("include_all_transactions", True))
    patterns = [
        str(x).lower()
        for x in (cfg.get("match_substrings") or [])
        if str(x).strip()
    ]
    return patterns, include_all


def _content_fingerprint_samurneo(patterns, include_all, bank):
    """Fingerprint the non-file inputs so the cache invalidates on config shifts.

    Separate fingerprints per bank so a future config split (e.g. dedicated
    bog_samurneo_patterns.json) only invalidates one side.
    """
    blob = json.dumps(
        {
            "bank": bank,
            "patterns": sorted(patterns or []),
            "include_all": bool(include_all),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _process_tbc_samurneo_file(path, *, patterns, include_all):
    """Parse one TBC yearly xlsx into per-file samurneo aggregates.

    Returns a JSON-serializable payload. Rows are stored in full (no
    truncation) — the bundle-level truncation to 300 happens at merge time.
    """
    out_exp = []
    out_ret = []
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("TBC samurneo %s: %s", path, exc)
        return {
            "status": "read_error",
            "expense_rows": [],
            "return_rows": [],
            "expense_total_ge": 0.0,
            "return_total_ge": 0.0,
            "expense_line_count": 0,
            "return_line_count": 0,
        }

    cols = list(df.columns)
    debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
    credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
    if not debit_col and not credit_col:
        return {
            "status": "ok",
            "expense_rows": [],
            "return_rows": [],
            "expense_total_ge": 0.0,
            "return_total_ge": 0.0,
            "expense_line_count": 0,
            "return_line_count": 0,
        }

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    for _, row in df.iterrows():
        raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col])
        blob = raw.lower()
        if (not include_all) and patterns and (
            not any(p in blob for p in patterns)
        ):
            continue
        debit_amt = (
            pd.to_numeric(row[debit_col], errors="coerce")
            if debit_col
            else float("nan")
        )
        credit_amt = (
            pd.to_numeric(row[credit_col], errors="coerce")
            if credit_col
            else float("nan")
        )
        base = {
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
        }
        if pd.notna(debit_amt) and float(debit_amt) > 0:
            out_exp.append({
                **base,
                "თანხა": float(debit_amt),
                "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA,
            })
        if pd.notna(credit_amt) and float(credit_amt) > 0:
            out_ret.append({
                **base,
                "თანხა": float(credit_amt),
                "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA,
            })

    exp_total = sum(float(r.get("თანხა") or 0) for r in out_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in out_ret)
    return {
        "status": "ok",
        "expense_rows": out_exp,
        "return_rows": out_ret,
        "expense_total_ge": float(exp_total),
        "return_total_ge": float(ret_total),
        "expense_line_count": len(out_exp),
        "return_line_count": len(out_ret),
    }


def _process_bog_samurneo_file(path, *, patterns, include_all):
    """Parse one BOG yearly cache file into per-file samurneo aggregates."""
    out_exp = []
    out_ret = []
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("BOG samurneo %s: %s", path, exc)
        return {
            "status": "read_error",
            "expense_rows": [],
            "return_rows": [],
            "expense_total_ge": 0.0,
            "return_total_ge": 0.0,
            "expense_line_count": 0,
            "return_line_count": 0,
        }

    cols = list(df.columns)
    debit_col = next(
        (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
        None,
    )
    credit_col = next(
        (c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)),
        None,
    )
    if not debit_col and not credit_col:
        return {
            "status": "ok",
            "expense_rows": [],
            "return_rows": [],
            "expense_total_ge": 0.0,
            "return_total_ge": 0.0,
            "expense_line_count": 0,
            "return_line_count": 0,
        }

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    for _, row in df.iterrows():
        raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col])
        blob = raw.lower()
        if (not include_all) and patterns and (
            not any(p in blob for p in patterns)
        ):
            continue
        debit_amt = (
            pd.to_numeric(row[debit_col], errors="coerce")
            if debit_col
            else float("nan")
        )
        credit_amt = (
            pd.to_numeric(row[credit_col], errors="coerce")
            if credit_col
            else float("nan")
        )
        base = {
            "ბანკი": "BOG",
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
        }
        if pd.notna(debit_amt) and float(debit_amt) > 0:
            out_exp.append({
                **base,
                "თანხა": float(debit_amt),
                "მიმართულება": SAMURNEO_EXPENSE_DIRECTION_KA,
            })
        if pd.notna(credit_amt) and float(credit_amt) > 0:
            out_ret.append({
                **base,
                "თანხა": float(credit_amt),
                "მიმართულება": SAMURNEO_RETURN_DIRECTION_KA,
            })

    exp_total = sum(float(r.get("თანხა") or 0) for r in out_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in out_ret)
    return {
        "status": "ok",
        "expense_rows": out_exp,
        "return_rows": out_ret,
        "expense_total_ge": float(exp_total),
        "return_total_ge": float(ret_total),
        "expense_line_count": len(out_exp),
        "return_line_count": len(out_ret),
    }


def _merge_samurneo_file_payloads(payloads):
    """Combine per-file samurneo payloads into the bundle shape.

    Row order follows file-iteration order (same as pre-refactor).
    """
    all_exp = []
    all_ret = []
    for payload in payloads:
        all_exp.extend(payload.get("expense_rows") or [])
        all_ret.extend(payload.get("return_rows") or [])
    exp_total = sum(float(r.get("თანხა") or 0) for r in all_exp)
    ret_total = sum(float(r.get("თანხა") or 0) for r in all_ret)
    return {
        "expense_total_ge": float(exp_total),
        "return_total_ge": float(ret_total),
        "net_ge": float(ret_total - exp_total),
        "expense_line_count": len(all_exp),
        "return_line_count": len(all_ret),
        "expense_rows_preview": all_exp[:300],
        "return_rows_preview": all_ret[:300],
        "expense_monthly_summary": _monthly_summary(all_exp),
        "return_monthly_summary": _monthly_summary(all_ret),
    }


def _run_cached_per_file(
    files,
    *,
    processor,
    fingerprint,
    use_cache,
    cache_path,
):
    """Generic per-file cache orchestration.

    Used by the samurneo pair (Sprint 3b) and the expense-categories pair
    (Sprint 3c). ``processor(path) → dict`` must return a JSON-serializable
    payload with a ``status`` key; only ``status == "ok"`` payloads are
    cached.
    """
    cache = empty_cache()
    resolved_cache_path = None
    if use_cache:
        resolved_cache_path = cache_path or os.path.abspath(DEFAULT_CACHE_FILENAME)
        cache = load_cache(
            resolved_cache_path, content_fingerprint=fingerprint
        )

    payloads = []
    for f in files:
        payload = None
        if use_cache:
            try:
                if not file_has_changed(f, cache):
                    cached = get_payload(cache, f)
                    if isinstance(cached, dict):
                        payload = cached
            except Exception:
                payload = None
        if payload is None:
            payload = processor(f)
            if use_cache and payload.get("status") == "ok":
                try:
                    sig = compute_file_signature(f)
                    put_entry(cache, f, sig, payload)
                except OSError:
                    pass
        payloads.append(payload)

    if use_cache and resolved_cache_path:
        expected_keys = {os.path.normpath(f) for f in files}
        cache_files = cache.get("files") if isinstance(cache, dict) else None
        if isinstance(cache_files, dict):
            for stale in [k for k in cache_files.keys() if k not in expected_keys]:
                cache_files.pop(stale, None)
        try:
            save_cache(resolved_cache_path, cache)
        except OSError:
            pass

    return payloads


def collect_tbc_samurneo_flow(
    script_dir, *, use_cache: bool = False, cache_path=None
):
    """Aggregate TBC samurneo flow across all TBC yearly xlsx files.

    When ``use_cache=True``, per-file payloads are cached in
    ``.pipeline_cache.json`` (or ``cache_path`` override) keyed by the
    samurneo content-fingerprint so unchanged files skip the Excel re-read
    on subsequent runs.
    """
    patterns, include_all = _load_samurneo_patterns(script_dir)
    fingerprint = _content_fingerprint_samurneo(patterns, include_all, bank="TBC")
    files = [str(p) for p in list_tbc_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_tbc_samurneo_file(
            f, patterns=patterns, include_all=include_all
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    return _merge_samurneo_file_payloads(payloads)


def collect_bog_samurneo_flow(
    script_dir, *, use_cache: bool = False, cache_path=None
):
    """Aggregate BOG samurneo flow across all BOG yearly xlsx files."""
    patterns, include_all = _load_samurneo_patterns(script_dir)
    fingerprint = _content_fingerprint_samurneo(patterns, include_all, bank="BOG")
    files = [str(p) for p in list_bog_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_bog_samurneo_file(
            f, patterns=patterns, include_all=include_all
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    return _merge_samurneo_file_payloads(payloads)


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

TAX_FLOW_DEFAULT_PATTERNS = (
    "საშემოსავლო", "გადასახად", "ბიუჯეტ", "revenue service", "rs.ge",
    "treasury", "tresge22", "204931440", "ge24nb0330100200165022",
    "ge60bg0000000667583800rs", "ge04bg0000000201978600rs",
)
TAX_FLOW_TREASURY_IN_MARKERS = (
    "tresge22", "სახელმწიფო ხაზინა", "204931440", "ge24nb0330100200165022",
)
TAX_FLOW_LABEL_KA = (
    "საგადასახადო / ბიუჯეტი / სახელმწიფო ხაზინა (ბანკის ფილტრი)"
)
TAX_FLOW_OUT_DIRECTION_KA = "საგადასახადო გადარიცხული"
TAX_FLOW_IN_DIRECTION_KA = "საგადასახადო ჩარიცხული"
TAX_FLOW_TREASURY_IN_DIRECTION_KA = "სახელმწიფო ხაზინიდან ჩარიცხული"


def _load_tax_flow_config(script_dir):
    """Read tax_flow_patterns.json or fall back to hardcoded defaults.

    Returns ``(patterns, treasury_in_markers)``. ``treasury_in_markers`` is
    not configurable today; it is returned for symmetry so the fingerprint
    includes it.
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "tax_flow_patterns.json"
    )
    default_patterns = list(TAX_FLOW_DEFAULT_PATTERNS)
    patterns = default_patterns
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as handle:
                cfg = json.load(handle)
            patterns = [
                str(x).lower()
                for x in (cfg.get("match_substrings") or [])
                if str(x).strip()
            ] or default_patterns
        except Exception:
            patterns = default_patterns
    return patterns, list(TAX_FLOW_TREASURY_IN_MARKERS)


def _content_fingerprint_tax_flow(patterns, treasury_in_markers):
    """Fingerprint non-file inputs so the cache invalidates on config shifts.

    Covers the active ``patterns`` list, the hardcoded
    ``treasury_in_markers`` list, and the ``TAX_TREASURY_CLUSTER_NOTE_KA``
    ledger note (per Sprint 3d preview spec — the note is merge-time only,
    but a change to it signals a semantic shift worth invalidating for).
    """
    blob = json.dumps(
        {
            "patterns": sorted(patterns or []),
            "treasury_in_markers": sorted(treasury_in_markers or []),
            "ledger_note": TAX_TREASURY_CLUSTER_NOTE_KA,
            "default_patterns": sorted(TAX_FLOW_DEFAULT_PATTERNS),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _empty_tax_flow_payload(status):
    return {
        "status": status,
        "out_rows": [],
        "in_rows": [],
        "treasury_in_rows": [],
        "out_total_ge": 0.0,
        "in_total_ge": 0.0,
        "treasury_in_total_ge": 0.0,
        "out_line_count": 0,
        "in_line_count": 0,
        "treasury_in_line_count": 0,
    }


def _process_bog_tax_flow_file(path, *, patterns, treasury_in_markers):
    """Parse one BOG yearly cache file into per-file tax-flow aggregates."""
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("BOG tax flow %s: %s", path, exc)
        return _empty_tax_flow_payload("read_error")

    cols = list(df.columns)
    debit_col = next(
        (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
        None,
    )
    credit_col = next(
        (c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)),
        None,
    )
    if not debit_col and not credit_col:
        return _empty_tax_flow_payload("ok")

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    out_rows, in_rows, treasury_in_rows = [], [], []
    for _, row in df.iterrows():
        raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col]).lower()
        if not any(p in raw for p in patterns):
            continue
        debit_amt = (
            pd.to_numeric(row[debit_col], errors="coerce")
            if debit_col
            else float("nan")
        )
        credit_amt = (
            pd.to_numeric(row[credit_col], errors="coerce")
            if credit_col
            else float("nan")
        )
        base = {
            "ბანკი": "BOG",
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "ტექსტი_მოკლე": raw[:500],
        }
        if pd.notna(debit_amt) and float(debit_amt) > 0:
            out_rows.append({
                **base,
                "თანხა": float(debit_amt),
                "მიმართულება": TAX_FLOW_OUT_DIRECTION_KA,
            })
        if pd.notna(credit_amt) and float(credit_amt) > 0:
            in_rec = {
                **base,
                "თანხა": float(credit_amt),
                "მიმართულება": TAX_FLOW_IN_DIRECTION_KA,
            }
            in_rows.append(in_rec)
            if any(m in raw for m in treasury_in_markers):
                treasury_in_rows.append({
                    **in_rec,
                    "მიმართულება": TAX_FLOW_TREASURY_IN_DIRECTION_KA,
                })

    out_total = sum(float(r.get("თანხა") or 0) for r in out_rows)
    in_total = sum(float(r.get("თანხა") or 0) for r in in_rows)
    treasury_in_total = sum(
        float(r.get("თანხა") or 0) for r in treasury_in_rows
    )
    return {
        "status": "ok",
        "out_rows": out_rows,
        "in_rows": in_rows,
        "treasury_in_rows": treasury_in_rows,
        "out_total_ge": float(out_total),
        "in_total_ge": float(in_total),
        "treasury_in_total_ge": float(treasury_in_total),
        "out_line_count": len(out_rows),
        "in_line_count": len(in_rows),
        "treasury_in_line_count": len(treasury_in_rows),
    }


def _process_tbc_tax_flow_file(path, *, patterns, treasury_in_markers):
    """Parse one TBC yearly xlsx into per-file tax-flow aggregates."""
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("TBC tax flow %s: %s", path, exc)
        return _empty_tax_flow_payload("read_error")

    cols = list(df.columns)
    debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
    credit_col = next((c for c in cols if "შემოსული თანხა" in str(c)), None)
    if not debit_col and not credit_col:
        return _empty_tax_flow_payload("ok")

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    out_rows, in_rows, treasury_in_rows = [], [], []
    for _, row in df.iterrows():
        raw = _tbc_row_text_join_skip(row, cols, [debit_col, credit_col]).lower()
        if not any(p in raw for p in patterns):
            continue
        debit_amt = (
            pd.to_numeric(row[debit_col], errors="coerce")
            if debit_col
            else float("nan")
        )
        credit_amt = (
            pd.to_numeric(row[credit_col], errors="coerce")
            if credit_col
            else float("nan")
        )
        base = {
            "ბანკი": "TBC",
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "ტექსტი_მოკლე": raw[:500],
        }
        if pd.notna(debit_amt) and float(debit_amt) > 0:
            out_rows.append({
                **base,
                "თანხა": float(debit_amt),
                "მიმართულება": TAX_FLOW_OUT_DIRECTION_KA,
            })
        if pd.notna(credit_amt) and float(credit_amt) > 0:
            in_rec = {
                **base,
                "თანხა": float(credit_amt),
                "მიმართულება": TAX_FLOW_IN_DIRECTION_KA,
            }
            in_rows.append(in_rec)
            if any(m in raw for m in treasury_in_markers):
                treasury_in_rows.append({
                    **in_rec,
                    "მიმართულება": TAX_FLOW_TREASURY_IN_DIRECTION_KA,
                })

    out_total = sum(float(r.get("თანხა") or 0) for r in out_rows)
    in_total = sum(float(r.get("თანხა") or 0) for r in in_rows)
    treasury_in_total = sum(
        float(r.get("თანხა") or 0) for r in treasury_in_rows
    )
    return {
        "status": "ok",
        "out_rows": out_rows,
        "in_rows": in_rows,
        "treasury_in_rows": treasury_in_rows,
        "out_total_ge": float(out_total),
        "in_total_ge": float(in_total),
        "treasury_in_total_ge": float(treasury_in_total),
        "out_line_count": len(out_rows),
        "in_line_count": len(in_rows),
        "treasury_in_line_count": len(treasury_in_rows),
    }


def _merge_tax_flow_file_payloads(payloads):
    """Combine per-file tax-flow payloads into the bundle shape.

    Row order follows ``payloads`` iteration order (BOG first, TBC second —
    matches the pre-cache collector).
    """
    all_out, all_in, all_treasury_in = [], [], []
    for payload in payloads:
        all_out.extend(payload.get("out_rows") or [])
        all_in.extend(payload.get("in_rows") or [])
        all_treasury_in.extend(payload.get("treasury_in_rows") or [])
    out_total = sum(float(r.get("თანხა") or 0) for r in all_out)
    in_total = sum(float(r.get("თანხა") or 0) for r in all_in)
    treasury_in_total = sum(
        float(r.get("თანხა") or 0) for r in all_treasury_in
    )
    return {
        "label_ka": TAX_FLOW_LABEL_KA,
        "ledger_note_ka": TAX_TREASURY_CLUSTER_NOTE_KA,
        "out_total_ge": float(out_total),
        "in_total_ge": float(in_total),
        "treasury_in_total_ge": float(treasury_in_total),
        "net_ge": float(in_total - out_total),
        "out_line_count": len(all_out),
        "in_line_count": len(all_in),
        "treasury_in_line_count": len(all_treasury_in),
        "out_rows_preview": all_out[:300],
        "in_rows_preview": all_in[:300],
        "treasury_in_rows_preview": all_treasury_in[:300],
        "out_monthly_summary": _monthly_summary(all_out),
        "in_monthly_summary": _monthly_summary(all_in),
        "treasury_in_monthly_summary": _monthly_summary(all_treasury_in),
    }


def collect_tax_flow(script_dir, *, use_cache: bool = False, cache_path=None):
    """Aggregate cross-bank tax-flow rows across BOG + TBC yearly xlsx files.

    When ``use_cache=True``, per-file payloads are cached in
    ``.pipeline_cache.json`` (or ``cache_path`` override) keyed by the
    tax-flow content-fingerprint. BOG and TBC paths are disjoint (different
    directories), so a single combined ``_run_cached_per_file`` call with a
    path-dispatching processor keeps cache entries from both banks alive in
    the same cache file (calling the helper twice would wipe the first
    bank's entries as "stale" on the second pass).
    """
    patterns, treasury_in_markers = _load_tax_flow_config(script_dir)
    fingerprint = _content_fingerprint_tax_flow(patterns, treasury_in_markers)

    bog_files = [str(p) for p in list_bog_statement_paths()]
    tbc_files = [str(p) for p in list_tbc_statement_paths()]
    bog_norm = {os.path.normpath(p) for p in bog_files}
    all_files = list(bog_files) + list(tbc_files)

    def _dispatch(path):
        if os.path.normpath(path) in bog_norm:
            return _process_bog_tax_flow_file(
                path,
                patterns=patterns,
                treasury_in_markers=treasury_in_markers,
            )
        return _process_tbc_tax_flow_file(
            path,
            patterns=patterns,
            treasury_in_markers=treasury_in_markers,
        )

    payloads = _run_cached_per_file(
        all_files,
        processor=_dispatch,
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    return _merge_tax_flow_file_payloads(payloads)


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

FOODMART_CASHBACK_DEFAULT_PATTERNS = (
    "ფუდმარტ", "foodmart", "404460187", "ge06tb7064936020100010",
    "ქეშბექ", "cashback", "cash back", "მომსახურების ღირებულება",
)
FOODMART_CASHBACK_LABEL_KA = "ფუდმარტის ქეშბექი/შემოსავალი"


def _content_fingerprint_foodmart_cashback(patterns):
    """Fingerprint non-file inputs for foodmart-cashback cache.

    Patterns are hardcoded today (no config file on disk). Including them
    in the fingerprint anyway means a future code-level change to the
    default pattern tuple will invalidate stale caches automatically.
    """
    blob = json.dumps(
        {
            "patterns": sorted(patterns or []),
            "default_patterns": sorted(FOODMART_CASHBACK_DEFAULT_PATTERNS),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _empty_foodmart_cashback_payload(status):
    return {
        "status": status,
        "rows": [],
        "total_ge": 0.0,
        "line_count": 0,
    }


def _process_tbc_foodmart_cashback_file(path, *, patterns):
    """Parse one TBC yearly xlsx into per-file foodmart-cashback payload.

    Rows are returned in full (no truncation) — the bundle-level cap to
    300 rows happens at merge time (matches samurneo template).
    """
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("TBC foodmart cashback %s: %s", path, exc)
        return _empty_foodmart_cashback_payload("read_error")

    cols = list(df.columns)
    credit_col = next(
        (c for c in cols if "შემოსული თანხა" in str(c)), None
    )
    if not credit_col:
        return _empty_foodmart_cashback_payload("ok")

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    rows = []
    total = 0.0
    for _, row in df.iterrows():
        amt = pd.to_numeric(row[credit_col], errors="coerce")
        if pd.isna(amt) or float(amt) <= 0:
            continue
        raw = _tbc_row_text_join_skip(row, cols, [credit_col]).lower()
        if not any(p in raw for p in patterns):
            continue
        total += float(amt)
        rows.append({
            "ბანკი": "TBC",
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "თანხა": float(amt),
            "ტექსტი_მოკლე": raw[:500],
        })
    return {
        "status": "ok",
        "rows": rows,
        "total_ge": float(total),
        "line_count": len(rows),
    }


def _merge_foodmart_cashback_payloads(payloads):
    """Combine per-file foodmart-cashback payloads into the bundle shape."""
    all_rows = []
    for payload in payloads:
        all_rows.extend(payload.get("rows") or [])
    total = sum(float(r.get("თანხა") or 0) for r in all_rows)
    return {
        "label_ka": FOODMART_CASHBACK_LABEL_KA,
        "total_ge": float(total),
        "line_count": len(all_rows),
        "rows_preview": all_rows[:300],
        "monthly_summary": _monthly_summary(all_rows),
    }


def collect_tbc_foodmart_cashback(
    script_dir, *, use_cache: bool = False, cache_path=None
):
    """Aggregate TBC foodmart cashback/income across all TBC yearly xlsx files.

    When ``use_cache=True``, per-file payloads are cached keyed by a
    fingerprint over the match patterns so a future change to the
    hardcoded default list invalidates stale caches automatically.
    """
    patterns = list(FOODMART_CASHBACK_DEFAULT_PATTERNS)
    fingerprint = _content_fingerprint_foodmart_cashback(patterns)
    files = [str(p) for p in list_tbc_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_tbc_foodmart_cashback_file(
            f, patterns=patterns
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    return _merge_foodmart_cashback_payloads(payloads)


def write_tbc_foodmart_cashback_excel(bundle, download_dir):
    rows = bundle.get("rows_preview", [])
    path = _save_excel(rows, download_dir, "TBC_ფუდმარტი_ქეშბექი.xlsx")
    if path:
        logger.info(f"  Excel (TBC ფუდმარტი ქეშბექი) → {path} "
                     f"({bundle.get('line_count', 0)} ხაზი, {bundle.get('total_ge', 0):,.2f} ₾)")


# ---------------------------------------------------------------------------
# POS terminal income (BOG + TBC)
# ---------------------------------------------------------------------------

BOG_POS_DEFAULT_PATTERNS = (
    "გადახდა - თარიღი", "ტერმინალის id", "ბარათი:", "ტრანზაქციის დეტალები",
    "დანიშნულება ჩარიცხვა", "pos", "პოს",
)
BOG_POS_LABEL_KA = "POS ტერმინალის შემოსავალი (BOG)"


def _load_bog_pos_patterns(script_dir):
    """Read bog_pos_terminal_income_patterns.json or fall back to defaults."""
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis",
        "bog_pos_terminal_income_patterns.json",
    )
    default_patterns = list(BOG_POS_DEFAULT_PATTERNS)
    if not os.path.isfile(cfg_path):
        return default_patterns
    try:
        with open(cfg_path, encoding="utf-8") as handle:
            cfg = json.load(handle)
    except Exception:
        return default_patterns
    patterns = [
        str(x).lower()
        for x in (cfg.get("match_substrings") or [])
        if str(x).strip()
    ]
    return patterns or default_patterns


def _content_fingerprint_bog_pos(patterns, object_mapping):
    """Fingerprint non-file inputs for BOG POS income cache.

    Covers the patterns list (bog_pos_terminal_income_patterns.json), the
    hardcoded default list, and the object_mapping (affects the ``object``
    field tagged on each cached line). Any change invalidates the cache.
    """
    blob = json.dumps(
        {
            "patterns": sorted(patterns or []),
            "default_patterns": sorted(BOG_POS_DEFAULT_PATTERNS),
            "mapping": object_mapping or {},
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _empty_bog_pos_payload(status):
    return {
        "status": status,
        "lines": [],
        "total_ge": 0.0,
        "line_count": 0,
    }


def _process_bog_pos_terminal_income_file(path, *, patterns, object_mapping):
    """Parse one BOG yearly cache file into per-file POS-income aggregates."""
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("BOG POS income %s: %s", path, exc)
        return _empty_bog_pos_payload("read_error")

    cols = list(df.columns)
    credit_col = next(
        (c for c in cols if "კრედიტი" in str(c) and "ბრუნვა" not in str(c)),
        None,
    )
    if not credit_col:
        return _empty_bog_pos_payload("ok")

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    lines = []
    total = 0.0
    for _, row in df.iterrows():
        amt = pd.to_numeric(row[credit_col], errors="coerce")
        if pd.isna(amt) or float(amt) <= 0:
            continue
        raw = _tbc_row_text_join_skip(row, cols, [credit_col])
        blob_lower = raw.lower()
        if not any(p in blob_lower for p in patterns):
            continue
        total += float(amt)
        lines.append({
            "ბანკი": "BOG",
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "თანხა": float(amt),
            "object": detect_object(
                "bog_pos", text=raw, object_mapping=object_mapping
            ),
            "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
        })
    return {
        "status": "ok",
        "lines": lines,
        "total_ge": float(total),
        "line_count": len(lines),
    }


def _merge_bog_pos_payloads(payloads):
    """Combine per-file BOG POS-income payloads into bundle shape."""
    all_lines = []
    for payload in payloads:
        all_lines.extend(payload.get("lines") or [])
    total = sum(float(r.get("თანხა") or 0) for r in all_lines)
    return {
        "label_ka": BOG_POS_LABEL_KA,
        "total_ge": float(total),
        "line_count": len(all_lines),
        "lines": all_lines,
    }


def collect_bog_pos_terminal_income(
    script_dir, object_mapping=None, *, use_cache: bool = False, cache_path=None
):
    """Aggregate BOG POS terminal income across all BOG yearly xlsx files.

    When ``use_cache=True``, per-file payloads are cached keyed by a
    fingerprint covering patterns + object_mapping. The emitted ``object``
    tag per line comes from ``object_mapping`` at read time, so any
    mapping change must invalidate the cache — handled via fingerprint.
    """
    patterns = _load_bog_pos_patterns(script_dir)
    object_mapping = object_mapping or load_object_mapping(script_dir)
    fingerprint = _content_fingerprint_bog_pos(patterns, object_mapping)
    files = [str(p) for p in list_bog_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_bog_pos_terminal_income_file(
            f, patterns=patterns, object_mapping=object_mapping
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    return _merge_bog_pos_payloads(payloads)


def _load_tbc_card_income_config(script_dir):
    """Read tbc_card_income_patterns.json or fall back to defaults.

    Returns ``(terminal_ids, label_ka)``. ``terminal_ids`` is the resolved
    list (config override if non-empty, else ``_DEFAULT_TBC_TERMINAL_IDS``).
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "tbc_card_income_patterns.json"
    )
    label_ka = ""
    terminal_ids = list(_DEFAULT_TBC_TERMINAL_IDS)
    if not os.path.isfile(cfg_path):
        return terminal_ids, label_ka
    try:
        with open(cfg_path, encoding="utf-8") as handle:
            cfg = json.load(handle)
    except Exception:
        return terminal_ids, label_ka
    label_ka = str(cfg.get("label_ka", "") or "")
    cfg_ids = [
        str(x).strip()
        for x in (cfg.get("terminal_ids") or [])
        if str(x).strip()
    ]
    if cfg_ids:
        terminal_ids = cfg_ids
    return terminal_ids, label_ka


def _content_fingerprint_tbc_card_income(
    terminal_ids, label_ka, object_mapping
):
    """Fingerprint non-file inputs for TBC card-income cache.

    Covers the active terminal_ids (Sprint 5.2/5.12-critical — the whole
    point of the terminal-ID filter is to exclude transit-IBAN aggregates
    that would double-count), label_ka, the hardcoded default terminal
    list, and the object_mapping.
    """
    blob = json.dumps(
        {
            "terminal_ids": sorted(terminal_ids or []),
            "default_terminal_ids": sorted(_DEFAULT_TBC_TERMINAL_IDS),
            "label_ka": label_ka or "",
            "mapping": object_mapping or {},
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _empty_tbc_card_income_payload(status):
    return {
        "status": status,
        "lines": [],
        "total_ge": 0.0,
        "line_count": 0,
    }


def _process_tbc_card_income_file(path, *, terminal_ids, object_mapping):
    """Parse one TBC yearly xlsx into per-file card-income aggregates.

    Matches rows by ``terminal_ids`` (physical POS terminal IDs present
    in the row text). This is the Sprint 5.2 filter that eliminates the
    2.8M ₾ double-count from transit-IBAN aggregates; Sprint 5.12
    diagnosed that pre-2024-04 TBC statements omit physical IDs on some
    legitimate rows — the cache must not alter this filter semantics.
    """
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("TBC card income %s: %s", path, exc)
        return _empty_tbc_card_income_payload("read_error")

    cols = list(df.columns)
    credit_col = next(
        (c for c in cols if "შემოსული" in str(c) and "გასული" not in str(c)),
        None,
    )
    if not credit_col:
        credit_col = next(
            (c for c in cols if "incoming" in str(c).lower()), None
        )
    if not credit_col:
        return _empty_tbc_card_income_payload("ok")

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)
    lines = []
    total = 0.0
    for _, row in df.iterrows():
        amt = pd.to_numeric(row[credit_col], errors="coerce")
        if pd.isna(amt) or amt <= 0:
            continue
        raw = _tbc_income_row_text_join(row, cols, credit_col)
        if not _tbc_income_row_has_terminal(raw, terminal_ids):
            continue
        total += float(amt)
        lines.append({
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "თანხა": float(amt),
            "object": detect_object(
                "tbc_pos", text=raw, object_mapping=object_mapping
            ),
            "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
        })
    return {
        "status": "ok",
        "lines": lines,
        "total_ge": float(total),
        "line_count": len(lines),
    }


def _merge_tbc_card_income_payloads(payloads, label_ka):
    """Combine per-file TBC card-income payloads into bundle shape."""
    all_lines = []
    for payload in payloads:
        all_lines.extend(payload.get("lines") or [])
    total = sum(float(r.get("თანხა") or 0) for r in all_lines)
    return {
        "total_ge": float(total),
        "lines": all_lines,
        "line_count": len(all_lines),
        "label_ka": label_ka,
    }


def collect_tbc_card_income(
    script_dir, object_mapping=None, *, use_cache: bool = False, cache_path=None
):
    """Aggregate TBC card-income across all TBC yearly xlsx files.

    When ``use_cache=True``, per-file payloads are cached keyed by a
    fingerprint covering terminal_ids + label_ka + object_mapping. The
    terminal-ID filter is Sprint 5.2-critical (excludes transit-IBAN
    aggregates that would double-count in post-2024-04 statements);
    Sprint 3e preserves it byte-identically and only accelerates
    repeat reads when no input has changed.
    """
    terminal_ids, label_ka = _load_tbc_card_income_config(script_dir)
    if not terminal_ids:
        return {
            "total_ge": 0.0,
            "lines": [],
            "line_count": 0,
            "label_ka": label_ka,
        }
    object_mapping = object_mapping or load_object_mapping(script_dir)
    fingerprint = _content_fingerprint_tbc_card_income(
        terminal_ids, label_ka, object_mapping
    )
    files = [str(p) for p in list_tbc_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_tbc_card_income_file(
            f, terminal_ids=terminal_ids, object_mapping=object_mapping
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    return _merge_tbc_card_income_payloads(payloads, label_ka)


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


def _empty_expense_bundle():
    return {
        "categories": [],
        "grand_total_ge": 0.0,
        "grand_total_operating_expense_ge": 0.0,
        "grand_total_state_treasury_ge": 0.0,
    }


def _load_expense_categories_config(script_dir):
    """Return (raw_cfg_blob, cats_norm) or (None, None) on missing/empty config.

    ``raw_cfg_blob`` is the raw dict parsed from
    `tbc_expense_categories.json` and feeds the content_fingerprint so any
    config edit invalidates both TBC and BOG caches.
    """
    cfg_path = os.path.join(
        script_dir, "Financial_Analysis", "tbc_expense_categories.json"
    )
    if not os.path.isfile(cfg_path):
        return None, None
    try:
        with open(cfg_path, encoding="utf-8") as handle:
            cfg = json.load(handle)
    except Exception:
        return None, None
    raw_cats = cfg.get("categories", [])
    if not raw_cats:
        return cfg, None
    cats_norm = _normalize_cats_from_json(raw_cats)
    if not cats_norm:
        return cfg, None
    return cfg, cats_norm


def _content_fingerprint_expense_categories(
    cfg_blob, object_mapping, bank, other_id
):
    """Fingerprint non-file inputs for expense-categories cache.

    Covers the full config JSON blob, the object_mapping (per-run) and the
    bank-scoped "other" category id so TBC/BOG caches stay disjoint.
    """
    blob = json.dumps(
        {
            "cfg": cfg_blob or {},
            "mapping": object_mapping or {},
            "bank": bank,
            "other_id": other_id,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _process_tbc_expense_categories_file(
    path, *, cats_norm, object_mapping, other_id
):
    """Parse one TBC yearly xlsx into per-category row lists.

    Returns ``{"status": "ok" | "read_error", "rows_by_category": {cat_id: [rows...]}}``.
    Bucketing + grand totals happen at merge time.
    """
    rows_by_category = {}
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("TBC expenses %s: %s", path, exc)
        return {"status": "read_error", "rows_by_category": {}}

    cols = list(df.columns)
    debit_col = next((c for c in cols if "გასული თანხა" in str(c)), None)
    if not debit_col:
        return {"status": "ok", "rows_by_category": {}}

    df = df[~df[debit_col].astype(str).str.contains(
        "Paid|Out|Amount", case=False, na=False
    )]
    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    file_name = os.path.basename(path)

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
            mid = other_id
        obj_source = "tbc_salary" if mid == "salary_payments" else "tbc_expense"
        rows_by_category.setdefault(mid, []).append({
            "კატეგორია_id": mid,
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "თანხა": float(amt),
            "object": detect_object(
                obj_source, text=raw, object_mapping=object_mapping
            ),
            "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
        })
    return {"status": "ok", "rows_by_category": rows_by_category}


def _process_bog_expense_categories_file(
    path, *, cats_norm, object_mapping, other_id
):
    """Parse one BOG yearly cache file into per-category row lists."""
    rows_by_category = {}
    try:
        df = read_bank_statement(path)
    except Exception as exc:
        logger.error("BOG expenses %s: %s", path, exc)
        return {"status": "read_error", "rows_by_category": {}}

    cols = list(df.columns)
    debit_col = next(
        (c for c in cols if "დებეტი" in str(c) and "ბრუნვა" not in str(c)),
        None,
    )
    if not debit_col:
        return {"status": "ok", "rows_by_category": {}}

    date_col = next((c for c in cols if "თარიღი" in str(c)), None)
    operation_col = next(
        (c for c in cols if "ოპერაციის შინაარსი" in str(c)), None
    )
    purpose_col = _find_excel_column_danishnuleba(cols)
    receiver_col = next(
        (c for c in cols if "მიმღების დასახელება" in str(c)), None
    )
    file_name = os.path.basename(path)

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
            mid = other_id
        obj_source = "tbc_salary" if mid == "salary_payments" else "tbc_expense"
        rows_by_category.setdefault(mid, []).append({
            "კატეგორია_id": mid,
            "ფაილი": file_name,
            "თარიღი": _excel_cell(row, date_col),
            "თანხა": float(amt),
            "object": detect_object(
                obj_source, text=raw, object_mapping=object_mapping
            ),
            "ტექსტი_მოკლე": (raw[:500] + "...") if len(raw) > 500 else raw,
        })
    return {"status": "ok", "rows_by_category": rows_by_category}


def _merge_expense_file_payloads(cats_with_other, payloads):
    """Flatten per-file payloads into the bundle-shaped buckets.

    File iteration order is preserved so row ordering matches the
    pre-refactor behavior exactly.
    """
    buckets = {c["id"]: [] for c in cats_with_other}
    for payload in payloads:
        rows_by_category = payload.get("rows_by_category") or {}
        for cat_id, rows in rows_by_category.items():
            if cat_id in buckets:
                buckets[cat_id].extend(rows)
            else:
                # Defensive — a cached payload may reference a category id
                # that has since been removed from config. Drop it rather
                # than crash; fingerprint change will rebuild the cache.
                continue
    return buckets


def collect_tbc_expense_categories(
    script_dir, object_mapping=None, *, use_cache: bool = False, cache_path=None
):
    """Aggregate TBC expense categories across all TBC yearly xlsx files.

    When ``use_cache=True``, per-file payloads are cached in
    ``.pipeline_cache.json`` (or ``cache_path`` override). The cache
    invalidates whenever the expense-categories config, object_mapping, or
    bank identity changes (via ``_content_fingerprint_expense_categories``).
    """
    cfg_blob, cats_norm = _load_expense_categories_config(script_dir)
    if cats_norm is None:
        return _empty_expense_bundle()

    other_cat = {
        "id": TBC_OTHER_EXPENSE_ID,
        "label_ka": TBC_OTHER_EXPENSE_LABEL_KA,
        "accounting_role": ACCOUNTING_ROLE_OPERATING,
        "patterns": [],
        "match_all": [],
        "ibans": [],
    }
    cats_with_other = list(cats_norm) + [other_cat]
    object_mapping = object_mapping or load_object_mapping(script_dir)
    fingerprint = _content_fingerprint_expense_categories(
        cfg_blob, object_mapping, bank="TBC", other_id=TBC_OTHER_EXPENSE_ID
    )
    files = [str(p) for p in list_tbc_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_tbc_expense_categories_file(
            f,
            cats_norm=cats_norm,
            object_mapping=object_mapping,
            other_id=TBC_OTHER_EXPENSE_ID,
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    buckets = _merge_expense_file_payloads(cats_with_other, payloads)
    return _build_expense_result(cats_with_other, buckets)


def collect_bog_expense_categories(
    script_dir, object_mapping=None, *, use_cache: bool = False, cache_path=None
):
    """Aggregate BOG expense categories across all BOG yearly xlsx files."""
    cfg_blob, cats_norm = _load_expense_categories_config(script_dir)
    if cats_norm is None:
        return _empty_expense_bundle()

    other_cat = {
        "id": BOG_OTHER_EXPENSE_ID,
        "label_ka": BOG_OTHER_EXPENSE_LABEL_KA,
        "accounting_role": ACCOUNTING_ROLE_OPERATING,
        "patterns": [],
        "match_all": [],
        "ibans": [],
    }
    cats_with_other = list(cats_norm) + [other_cat]
    object_mapping = object_mapping or load_object_mapping(script_dir)
    fingerprint = _content_fingerprint_expense_categories(
        cfg_blob, object_mapping, bank="BOG", other_id=BOG_OTHER_EXPENSE_ID
    )
    files = [str(p) for p in list_bog_statement_paths()]
    payloads = _run_cached_per_file(
        files,
        processor=lambda f: _process_bog_expense_categories_file(
            f,
            cats_norm=cats_norm,
            object_mapping=object_mapping,
            other_id=BOG_OTHER_EXPENSE_ID,
        ),
        fingerprint=fingerprint,
        use_cache=bool(use_cache),
        cache_path=cache_path,
    )
    buckets = _merge_expense_file_payloads(cats_with_other, payloads)
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
