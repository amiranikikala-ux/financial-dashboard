"""
One-time BOG cache backfill — fetches statement entries via BOG API and
appends to the year-partitioned parquet cache.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b):
- Source = API only.
- Append-only — re-running over an already-cached window adds 0 rows.
- Error → STOP + raise (no silent skip).

Usage:
    python -m dashboard_pipeline._backfill_bog --start 2025-01-01 --end 2025-03-31
    python -m dashboard_pipeline._backfill_bog --start 2023-01-01 --end 2026-05-04 --dry-run

The window is fetched in monthly chunks. Each chunk is converted to a
26-Georgian-column DataFrame (matching the manual-XLSX schema the pipeline
already reads) and appended to the cache via `append_bog_cache`.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Ensure project root on sys.path when invoked as a script (not -m).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dashboard_pipeline.bank_cache import append_bog_cache, read_bog_cache  # noqa: E402
from dashboard_pipeline.bog_bank_connector import (  # noqa: E402
    BOGBankConnector,
    to_xls_dataframe,
)


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _month_windows(start: date, end: date):
    """Yield (window_start, window_end) tuples in calendar-month chunks."""
    cur = start
    while cur <= end:
        if cur.month == 12:
            next_first = date(cur.year + 1, 1, 1)
        else:
            next_first = date(cur.year, cur.month + 1, 1)
        win_end = min(next_first - timedelta(days=1), end)
        yield cur, win_end
        cur = win_end + timedelta(days=1)


def run_backfill(
    start: date,
    end: date,
    *,
    dry_run: bool = False,
    max_window_days: int = 1,
) -> dict[int, int]:
    """
    Fetch [start, end] in monthly chunks, append to BOG parquet cache.
    Returns `{year: total_rows_added}` aggregated across months.

    `max_window_days` is forwarded to `BOGBankConnector.fetch_statement` —
    keep it 1 for safety (auto-handles >1000-record days), increase only
    after volume profiling.
    """
    if start > end:
        raise ValueError(f"start ({start}) > end ({end})")

    print(f"BOG backfill: {start} .. {end}  (dry_run={dry_run})")
    conn = BOGBankConnector()
    print("  auth check ...", flush=True)
    if not conn.check_auth():
        raise RuntimeError("BOG auth failed — check BOG_CLIENT_ID/SECRET.")
    print("  auth OK")

    totals: dict[int, int] = {}
    api_total = 0

    for win_start, win_end in _month_windows(start, end):
        t0 = time.time()
        movements = conn.fetch_statement(
            win_start, win_end, max_window_days=max_window_days
        )
        api_total += len(movements)
        dt = time.time() - t0

        if dry_run:
            print(
                f"  [dry] {win_start}..{win_end}: api={len(movements):>5}  "
                f"({dt:.1f}s)"
            )
            continue

        df = to_xls_dataframe(movements)
        added = append_bog_cache(df)
        for y, n in added.items():
            totals[y] = totals.get(y, 0) + n
        added_summary = ", ".join(f"{y}+{n}" for y, n in sorted(added.items()))
        print(
            f"  {win_start}..{win_end}: api={len(movements):>5}  "
            f"added={added_summary or '0'}  ({dt:.1f}s)"
        )

    print(f"\nBackfill complete. API total fetched: {api_total:,}")
    if dry_run:
        print("(dry run — no parquet written)")
    else:
        for y in sorted(totals):
            print(f"  cache rows added in {y}: {totals[y]:,}")
        print("\nCurrent cache totals:")
        for y in range(start.year, end.year + 1):
            df = read_bog_cache(y)
            print(f"  {y}: {len(df):,} rows")
    return totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BOG cache backfill (append-only).")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + count only; do not write parquet.",
    )
    ap.add_argument(
        "--max-window-days",
        type=int,
        default=1,
        help="Days per API call (default 1). Auto-falls-back day-by-day "
        "when a window hits the 1000-record cap.",
    )
    args = ap.parse_args(argv)

    try:
        run_backfill(
            _parse_date(args.start),
            _parse_date(args.end),
            dry_run=args.dry_run,
            max_window_days=args.max_window_days,
        )
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
