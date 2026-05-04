"""
Bank statement cache — append-only parquet store.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b):
- Source = bank API only (no XLSX in pipeline).
- One file per bank per year: `Financial_Analysis/cache/{bank}/{year}.parquet`.
- Append-only — old records never mutate; refreshes only ADD new EntryIds.
- Schema matches `bog_bank_connector.XLS_COLUMNS` (26 Georgian columns) so the
  pipeline's existing XLSX-reader column lookups continue to work.

Public API:
- `read_bog_cache(year=None) -> pd.DataFrame`  — concat all years if year=None.
- `write_bog_cache(year, df) -> Path`           — overwrite one year (use rarely).
- `append_bog_cache(df_new) -> dict[int, int]`  — append by entry_id, returns
   per-year row counts added (0 if everything was already cached).

The DataFrame returned by `read_bog_cache` has typed columns:
- `თარიღი`         → datetime64[ns]
- `დებეტი`/`კრედიტი`/`თანხა` → float64 with NaN for blanks
- everything else  → string (empty string for nulls)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dashboard_pipeline.bog_bank_connector import XLS_COLUMNS

CACHE_ROOT = (
    Path(__file__).resolve().parent.parent / "Financial_Analysis" / "cache"
)
BOG_DIR = CACHE_ROOT / "bog"

DATE_COL = "თარიღი"
ENTRY_ID_COL = "ოპერაციის იდ"
NUMERIC_COLS = ("დებეტი", "კრედიტი", "თანხა")


def _normalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce columns to parquet-friendly dtypes."""
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


def _empty_bog_frame() -> pd.DataFrame:
    df = pd.DataFrame(columns=list(XLS_COLUMNS))
    return _normalize_dtypes(df)


def _bog_path(year: int) -> Path:
    return BOG_DIR / f"{year}.parquet"


def read_bog_cache(year: int | None = None) -> pd.DataFrame:
    """Read BOG cache. `year=None` → concat all available years."""
    if year is None:
        if not BOG_DIR.exists():
            return _empty_bog_frame()
        files = sorted(BOG_DIR.glob("*.parquet"))
        if not files:
            return _empty_bog_frame()
        frames = [pd.read_parquet(f) for f in files]
        return pd.concat(frames, ignore_index=True)
    p = _bog_path(year)
    if not p.exists():
        return _empty_bog_frame()
    return pd.read_parquet(p)


def write_bog_cache(year: int, df: pd.DataFrame) -> Path:
    """Overwrite one year's parquet. Use only for full-rewrite scenarios."""
    BOG_DIR.mkdir(parents=True, exist_ok=True)
    df = _normalize_dtypes(df)
    p = _bog_path(year)
    df.to_parquet(p, index=False)
    return p


def append_bog_cache(df_new: pd.DataFrame) -> dict[int, int]:
    """
    Append-only update — add only rows whose `ოპერაციის იდ` is not already
    present in the matching year's parquet. Old rows are never modified.

    Splits `df_new` by year, dedupes against existing cache, writes back.
    Returns `{year: rows_added}` (0 if nothing new for that year).
    """
    if df_new.empty:
        return {}
    df_new = _normalize_dtypes(df_new)
    if DATE_COL not in df_new.columns:
        raise ValueError(f"append_bog_cache: missing column {DATE_COL!r}")
    if ENTRY_ID_COL not in df_new.columns:
        raise ValueError(f"append_bog_cache: missing column {ENTRY_ID_COL!r}")

    df_new = df_new.assign(__year=df_new[DATE_COL].dt.year)
    if df_new["__year"].isna().any():
        bad = df_new[df_new["__year"].isna()]
        raise ValueError(
            f"append_bog_cache: {len(bad)} row(s) have unparseable dates"
        )

    added: dict[int, int] = {}
    for year, chunk in df_new.groupby("__year"):
        year = int(year)
        chunk = chunk.drop(columns="__year")
        existing = read_bog_cache(year)
        if not existing.empty:
            seen = set(existing[ENTRY_ID_COL].astype(str))
            chunk = chunk[~chunk[ENTRY_ID_COL].astype(str).isin(seen)]
        if chunk.empty:
            added[year] = 0
            continue
        combined = pd.concat([existing, chunk], ignore_index=True)
        combined = combined.sort_values(DATE_COL, kind="stable").reset_index(drop=True)
        write_bog_cache(year, combined)
        added[year] = len(chunk)
    return added


def list_bog_statement_paths() -> list[Path]:
    """Sorted list of BOG cache parquet files (one per year)."""
    if not BOG_DIR.exists():
        return []
    return sorted(BOG_DIR.glob("*.parquet"))


def read_bank_statement(path) -> pd.DataFrame:
    """Auto-dispatch: parquet → read_parquet; xlsx/xls → find_header_row + read_excel.

    Returned DataFrame uses the same Georgian column names whether the source
    is parquet or XLSX, so downstream column-lookup code is unaffected.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(p)
    if suffix in (".xlsx", ".xls"):
        from dashboard_pipeline.file_utils import find_header_row
        header_idx = find_header_row(str(p))
        return pd.read_excel(p, header=header_idx)
    raise ValueError(f"read_bank_statement: unsupported extension {suffix!r} ({p})")


__all__ = [
    "read_bog_cache",
    "write_bog_cache",
    "append_bog_cache",
    "list_bog_statement_paths",
    "read_bank_statement",
    "BOG_DIR",
    "CACHE_ROOT",
]
