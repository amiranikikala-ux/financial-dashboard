"""
TBC bank statement cache — append-only parquet store.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b — same policy as
BOG `bank_cache.py` and rs.ge `rsge_cache.py`):
- Source = TBC DBI SOAP only (no XLSX in pipeline after wire-in).
- One file per year: `Financial_Analysis/cache/tbc/{year}.parquet`.
- Append-only — old records never mutate; refreshes only ADD new movement IDs.
- Schema matches `tbc_bank_connector.XLS_COLUMNS` (23 Georgian columns) so
  the pipeline's existing XLSX-reader column lookups continue to work.

Public API:
- `read_tbc_cache(year=None) -> pd.DataFrame`     — concat all years if None.
- `write_tbc_cache(year, df) -> Path`             — overwrite one year.
- `append_tbc_cache(df_new) -> dict[int, int]`    — append by movement ID.
- `list_tbc_statement_paths() -> list[Path]`      — sorted parquet paths.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dashboard_pipeline.tbc_bank_connector import XLS_COLUMNS

CACHE_ROOT = (
    Path(__file__).resolve().parent.parent / "Financial_Analysis" / "cache"
)
TBC_DIR = CACHE_ROOT / "tbc"

DATE_COL = "თარიღი"
ENTRY_ID_COL = "ტრანზაქციის ID"
NUMERIC_COLS = ("გასული თანხა", "შემოსული თანხა", "ნაშთი")


def _normalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in df.columns:
        if c == DATE_COL or c in NUMERIC_COLS:
            continue
        df[c] = df[c].fillna("").astype(str)
    return df


def _empty_tbc_frame() -> pd.DataFrame:
    return _normalize_dtypes(pd.DataFrame(columns=list(XLS_COLUMNS)))


def _tbc_path(year: int) -> Path:
    return TBC_DIR / f"{year}.parquet"


def read_tbc_cache(year: int | None = None) -> pd.DataFrame:
    """Read TBC cache. `year=None` → concat all available years."""
    if year is None:
        if not TBC_DIR.exists():
            return _empty_tbc_frame()
        files = sorted(TBC_DIR.glob("*.parquet"))
        if not files:
            return _empty_tbc_frame()
        frames = [pd.read_parquet(f) for f in files]
        return pd.concat(frames, ignore_index=True)
    p = _tbc_path(year)
    if not p.exists():
        return _empty_tbc_frame()
    return pd.read_parquet(p)


def write_tbc_cache(year: int, df: pd.DataFrame) -> Path:
    """Overwrite one year's parquet. Use only for full-rewrite scenarios."""
    TBC_DIR.mkdir(parents=True, exist_ok=True)
    df = _normalize_dtypes(df)
    p = _tbc_path(year)
    df.to_parquet(p, index=False)
    return p


def append_tbc_cache(df_new: pd.DataFrame) -> dict[int, int]:
    """
    Append-only update — add only rows whose `ტრანზაქციის ID` is not already
    present in the matching year's parquet. Old rows never mutate.

    Splits `df_new` by year (from `თარიღი`), dedupes against existing cache,
    writes back. Returns `{year: rows_added}` (0 if nothing new for that year).
    """
    if df_new.empty:
        return {}
    df_new = _normalize_dtypes(df_new)
    if DATE_COL not in df_new.columns:
        raise ValueError(f"append_tbc_cache: missing column {DATE_COL!r}")
    if ENTRY_ID_COL not in df_new.columns:
        raise ValueError(f"append_tbc_cache: missing column {ENTRY_ID_COL!r}")

    df_new = df_new.assign(__year=df_new[DATE_COL].dt.year)
    if df_new["__year"].isna().any():
        bad = df_new[df_new["__year"].isna()]
        raise ValueError(
            f"append_tbc_cache: {len(bad)} row(s) have unparseable dates"
        )

    added: dict[int, int] = {}
    for year, chunk in df_new.groupby("__year"):
        year = int(year)
        chunk = chunk.drop(columns="__year")
        existing = read_tbc_cache(year)
        if not existing.empty:
            seen = set(existing[ENTRY_ID_COL].astype(str))
            chunk = chunk[~chunk[ENTRY_ID_COL].astype(str).isin(seen)]
        if chunk.empty:
            added[year] = 0
            continue
        combined = pd.concat([existing, chunk], ignore_index=True)
        combined = combined.sort_values(DATE_COL, kind="stable").reset_index(drop=True)
        write_tbc_cache(year, combined)
        added[year] = len(chunk)
    return added


def list_tbc_statement_paths() -> list[Path]:
    """Sorted list of TBC cache parquet files (one per year)."""
    if not TBC_DIR.exists():
        return []
    return sorted(TBC_DIR.glob("*.parquet"))


__all__ = [
    "read_tbc_cache",
    "write_tbc_cache",
    "append_tbc_cache",
    "list_tbc_statement_paths",
    "TBC_DIR",
    "CACHE_ROOT",
]
