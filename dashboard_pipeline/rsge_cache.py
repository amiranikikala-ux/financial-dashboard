"""
rs.ge waybill cache — append-only parquet store.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b — same policy as
BOG bank_cache.py):
- Source = rs.ge SOAP only (no XLS in pipeline after wire-in).
- One file per year: `Financial_Analysis/cache/rsge/{year}.parquet`.
- Append-only — old records never mutate; refreshes only ADD new IDs.
- Schema = 21-column XLS-equivalent from `to_xls_dataframe` + 1 hidden
  `_create_date` column for year-partitioning. Pipeline read sites continue
  to consume the 21 XLS columns; the hidden column is filtered out by
  `read_rsge_cache`.

Public API:
- `read_rsge_cache(year=None) -> pd.DataFrame`        — concat all years if None.
- `write_rsge_cache(year, df_with_meta) -> Path`      — overwrite one year.
- `append_rsge_cache(waybills) -> dict[int, int]`     — append by ID.
- `list_rsge_waybill_paths() -> list[Path]`           — sorted parquet paths.
- `read_waybill_file(path) -> pd.DataFrame`           — auto-dispatch parquet/xls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from dashboard_pipeline.rs_waybill_connector import Waybill, to_xls_dataframe

CACHE_ROOT = (
    Path(__file__).resolve().parent.parent / "Financial_Analysis" / "cache"
)
RSGE_DIR = CACHE_ROOT / "rsge"

ID_COL = "ID"
HIDDEN_DATE_COL = "_create_date"
XLS_COLUMNS = (
    "ზედნადები", "სტატუსი", "მდგომარეობა", "კატეგორია", "ტიპი",
    "ორგანიზაცია", "თანხა", "მძღოლი", "ავტო", "ტრანსპ თანხა",
    "ტრანსპორტ. დაწყება", "მიწოდების ადგილი", "გააქტიურების თარ.",
    "ტრანსპ. დაწყება", "ჩაბარების თარ.", "გაუქმების თარ.", "შენიშვნა",
    "ა/ფ ID", "STAT", "ტრანსპორტირების ხარჯი", "ID",
)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(XLS_COLUMNS))


def _rsge_path(year: int) -> Path:
    return RSGE_DIR / f"{year}.parquet"


def read_rsge_cache(year: int | None = None) -> pd.DataFrame:
    """Read rs.ge cache (XLS-shaped, hidden columns stripped)."""
    if year is None:
        if not RSGE_DIR.exists():
            return _empty_frame()
        files = sorted(RSGE_DIR.glob("*.parquet"))
        if not files:
            return _empty_frame()
        frames = [pd.read_parquet(f) for f in files]
        df = pd.concat(frames, ignore_index=True)
    else:
        p = _rsge_path(year)
        if not p.exists():
            return _empty_frame()
        df = pd.read_parquet(p)
    visible = [c for c in df.columns if not c.startswith("_")]
    return df[visible]


def _read_with_hidden(year: int) -> pd.DataFrame:
    p = _rsge_path(year)
    if not p.exists():
        return pd.DataFrame(columns=[*XLS_COLUMNS, HIDDEN_DATE_COL])
    return pd.read_parquet(p)


def write_rsge_cache(year: int, df: pd.DataFrame) -> Path:
    """Overwrite one year's parquet (must contain hidden `_create_date`)."""
    if HIDDEN_DATE_COL not in df.columns:
        raise ValueError(
            f"write_rsge_cache: missing hidden column {HIDDEN_DATE_COL!r}"
        )
    RSGE_DIR.mkdir(parents=True, exist_ok=True)
    p = _rsge_path(year)
    df.to_parquet(p, index=False)
    return p


def append_rsge_cache(waybills: Iterable[Waybill]) -> dict[int, int]:
    """
    Append-only update — add only waybills whose `ID` is not already cached
    in the matching year's parquet. Old rows never mutate.

    Year is taken from `Waybill.create_date` (rs.ge SOAP creation timestamp).
    Returns `{year: rows_added}`.
    """
    waybills = list(waybills)
    if not waybills:
        return {}

    df = to_xls_dataframe(waybills)
    create_dates = pd.to_datetime(
        [w.create_date for w in waybills], errors="coerce",
    )
    if create_dates.isna().any():
        bad = sum(create_dates.isna())
        raise ValueError(
            f"append_rsge_cache: {bad} waybill(s) have unparseable create_date"
        )
    df = df.copy()
    df[HIDDEN_DATE_COL] = create_dates
    df["__year"] = create_dates.year

    added: dict[int, int] = {}
    for year, chunk in df.groupby("__year"):
        year = int(year)
        chunk = chunk.drop(columns="__year")
        existing = _read_with_hidden(year)
        if not existing.empty:
            seen = set(existing[ID_COL].astype(str))
            chunk = chunk[~chunk[ID_COL].astype(str).isin(seen)]
        if chunk.empty:
            added[year] = 0
            continue
        combined = pd.concat([existing, chunk], ignore_index=True)
        combined = combined.sort_values(HIDDEN_DATE_COL, kind="stable")
        combined = combined.reset_index(drop=True)
        write_rsge_cache(year, combined)
        added[year] = len(chunk)
    return added


def list_rsge_waybill_paths() -> list[Path]:
    """Sorted list of rs.ge cache parquet files (one per year)."""
    if not RSGE_DIR.exists():
        return []
    return sorted(RSGE_DIR.glob("*.parquet"))


def read_waybill_file(path) -> pd.DataFrame:
    """Auto-dispatch: parquet → read_parquet (hidden cols stripped); xls → read_excel.

    Returned DataFrame uses the same 21 Georgian XLS columns whether the
    source is parquet or xls, so downstream column-lookup code is unaffected.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        df = pd.read_parquet(p)
        visible = [c for c in df.columns if not c.startswith("_")]
        return df[visible]
    if suffix in (".xls", ".xlsx"):
        return pd.read_excel(p, dtype=str)
    raise ValueError(f"read_waybill_file: unsupported extension {suffix!r} ({p})")


__all__ = [
    "read_rsge_cache",
    "write_rsge_cache",
    "append_rsge_cache",
    "list_rsge_waybill_paths",
    "read_waybill_file",
    "RSGE_DIR",
    "CACHE_ROOT",
]
