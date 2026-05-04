"""
One-time rs.ge cache backfill — fetches buyer waybills via SOAP and appends
to the year-partitioned parquet cache.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b — same policy as
BOG `_backfill_bog.py`):
- Source = SOAP only.
- Append-only — re-running over an already-cached window adds 0 rows.
- Error → STOP + raise (no silent skip).

Usage:
    python -m dashboard_pipeline._backfill_rsge --start 2026-03-01 --end 2026-03-31
    python -m dashboard_pipeline._backfill_rsge --start 2023-01-01 --end 2026-05-04 --dry-run

The window is fetched in monthly chunks (rs.ge SOAP accepts arbitrary date
ranges; monthly is a safe default).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dashboard_pipeline.rs_waybill_connector import RSWaybillConnector  # noqa: E402
from dashboard_pipeline.rsge_cache import append_rsge_cache, read_rsge_cache  # noqa: E402


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _month_windows(start: date, end: date):
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
) -> dict[int, int]:
    if start > end:
        raise ValueError(f"start ({start}) > end ({end})")

    print(f"rs.ge backfill: {start} .. {end}  (dry_run={dry_run})")
    conn = RSWaybillConnector()
    print("  auth check ...", flush=True)
    if not conn.check_auth():
        raise RuntimeError("rs.ge auth failed — check RS_USER/RS_PASS.")
    print("  auth OK")

    totals: dict[int, int] = {}
    api_total = 0

    for win_start, win_end in _month_windows(start, end):
        t0 = time.time()
        ws = datetime(win_start.year, win_start.month, win_start.day, 0, 0, 0)
        we = datetime(win_end.year, win_end.month, win_end.day, 23, 59, 59)
        waybills = conn.fetch_buyer_waybills(ws, we)
        api_total += len(waybills)
        dt = time.time() - t0

        if dry_run:
            print(
                f"  [dry] {win_start}..{win_end}: api={len(waybills):>5}  "
                f"({dt:.1f}s)"
            )
            continue

        added = append_rsge_cache(waybills)
        for y, n in added.items():
            totals[y] = totals.get(y, 0) + n
        added_summary = ", ".join(f"{y}+{n}" for y, n in sorted(added.items()))
        print(
            f"  {win_start}..{win_end}: api={len(waybills):>5}  "
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
            df = read_rsge_cache(y)
            print(f"  {y}: {len(df):,} rows")
    return totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="rs.ge cache backfill (append-only).")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + count only; do not write parquet.",
    )
    args = ap.parse_args(argv)

    try:
        run_backfill(
            _parse_date(args.start),
            _parse_date(args.end),
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
