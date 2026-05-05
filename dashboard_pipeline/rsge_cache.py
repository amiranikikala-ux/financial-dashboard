"""
rs.ge waybill cache — upsert-by-ID parquet store.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b — diverges from
BOG/TBC append-only model since 2026-05-08):
- Source = rs.ge SOAP only (no XLS in pipeline after wire-in).
- One file per year: `Financial_Analysis/cache/rsge/{year}.parquet`.
- Upsert-by-ID — incoming waybill replaces the cached row when the ID
  already exists. Catches supplier-side amendments (active → cancelled,
  amount/comment edits). Without this, `WaybillReconciliation.jsx` cannot
  fire `ghost_ap` / `amount_mismatch` flags because the cache silently
  shows the original (stale) row.
- Schema = 21-column XLS-equivalent from `to_xls_dataframe` + 1 hidden
  `_create_date` column for year-partitioning. Pipeline read sites continue
  to consume the 21 XLS columns; the hidden column is filtered out by
  `read_rsge_cache`.

Year remains stable across upserts because rs.ge `create_date` is immutable
on amendments — only `status` / `close_date` / amount / comment change.

Public API:
- `read_rsge_cache(year=None) -> pd.DataFrame`        — concat all years if None.
- `write_rsge_cache(year, df_with_meta) -> Path`      — overwrite one year.
- `upsert_rsge_cache(waybills) -> dict[int, dict]`    — upsert by ID,
                                                        returns per-year
                                                        `{"added": N, "updated": M}`.
- `append_rsge_cache(waybills) -> dict[int, int]`     — DEPRECATED thin
                                                        compat shim (sums
                                                        added+updated).
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


def upsert_rsge_cache(
    waybills: Iterable[Waybill],
) -> dict[int, dict[str, int]]:
    """
    Upsert update — for each incoming waybill:
    - if `ID` is not already cached → ADD as new row
    - if `ID` already exists → REPLACE the existing row in-place

    Catches rs.ge-side amendments after creation: status flips
    (active → cancelled), amount/comment corrections, close_date population
    on cancel. Year remains stable because rs.ge `create_date` is immutable
    on amendments.

    Year is taken from `Waybill.create_date` (rs.ge SOAP creation timestamp).
    Returns `{year: {"added": N, "updated": M}}`. A year with neither new
    nor changed rows still appears in the dict with both counters at 0.
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
            f"upsert_rsge_cache: {bad} waybill(s) have unparseable create_date"
        )
    df = df.copy()
    df[HIDDEN_DATE_COL] = create_dates
    df["__year"] = create_dates.year

    result: dict[int, dict[str, int]] = {}
    for year, chunk in df.groupby("__year"):
        year = int(year)
        chunk = chunk.drop(columns="__year")
        existing = _read_with_hidden(year)

        if existing.empty:
            combined = chunk
            added = len(chunk)
            updated = 0
            changed = True
        else:
            chunk_ids = chunk[ID_COL].astype(str)
            existing_ids = existing[ID_COL].astype(str)
            chunk_id_set = set(chunk_ids)
            existing_id_set = set(existing_ids)
            updating = chunk_id_set & existing_id_set
            new_only = chunk_id_set - existing_id_set

            if updating:
                # Detect whether incoming rows actually differ from cached
                # rows. Same-content re-fetches must not bump `updated`.
                visible_cols = [c for c in chunk.columns if c != HIDDEN_DATE_COL]
                old_view = (
                    existing[existing_ids.isin(updating)]
                    .set_index(existing_ids[existing_ids.isin(updating)])[visible_cols]
                    .sort_index()
                    .astype(str)
                )
                new_view = (
                    chunk[chunk_ids.isin(updating)]
                    .set_index(chunk_ids[chunk_ids.isin(updating)])[visible_cols]
                    .sort_index()
                    .astype(str)
                )
                # Drop rows that are byte-identical (treat NaN as equal-NaN).
                diff_mask = (old_view != new_view).any(axis=1)
                truly_changed_ids = set(diff_mask[diff_mask].index)
            else:
                truly_changed_ids = set()

            updated = len(truly_changed_ids)
            added = len(new_only)
            changed = bool(truly_changed_ids or new_only)

            if not changed:
                combined = existing
            else:
                # Drop rows in `existing` whose ID we are replacing, then
                # concat the (possibly reduced) chunk.
                replace_ids = truly_changed_ids
                kept = existing[~existing_ids.isin(replace_ids)]
                # Only carry rows from chunk that are either new or truly
                # changed — same-content rows from chunk would otherwise
                # duplicate kept rows that we deliberately retained.
                emit_mask = chunk_ids.isin(replace_ids | new_only)
                combined = pd.concat([kept, chunk[emit_mask]], ignore_index=True)

        result[year] = {"added": added, "updated": updated}

        if not changed:
            continue

        combined = combined.sort_values(HIDDEN_DATE_COL, kind="stable")
        combined = combined.reset_index(drop=True)
        write_rsge_cache(year, combined)

    return result


def append_rsge_cache(waybills: Iterable[Waybill]) -> dict[int, int]:
    """
    DEPRECATED thin compat shim around `upsert_rsge_cache`.

    Returns `{year: added + updated}` so legacy `_backfill_rsge.py` output
    formatting (`f"{y}+{n}"`) keeps working without an update. New code
    should call `upsert_rsge_cache` directly to preserve the added/updated
    split.
    """
    detailed = upsert_rsge_cache(waybills)
    return {y: counts["added"] + counts["updated"] for y, counts in detailed.items()}


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
    "upsert_rsge_cache",
    "append_rsge_cache",
    "list_rsge_waybill_paths",
    "read_waybill_file",
    "RSGE_DIR",
    "CACHE_ROOT",
]
