"""
One-time TBC cache backfill — fetches account movements via TBC DBI SOAP and
appends to the year-partitioned parquet cache.

Architecture (locked 2026-05-05, see CONTEXT_HANDOFF.md §1b):
- Source = SOAP only.
- Append-only — re-running over an already-cached window adds 0 rows.
- Error → STOP + raise (no silent skip).

DigiPass requirement (§4 plan): each TBC SOAP call requires a fresh 9-digit
nonce, valid ~5-15 min. Pagination uses the SAME nonce, so a single OTP can
cover an arbitrary date window (1 month / 1 year — whatever fits in the OTP
validity window). Practical: pass one OTP per year-range.

Usage:
    # Single year (1 OTP):
    python -m dashboard_pipeline._backfill_tbc \\
        --start 2025-01-01 --end 2025-12-31 --nonce 123456789

    # Dry run (no parquet write):
    python -m dashboard_pipeline._backfill_tbc \\
        --start 2025-01-01 --end 2025-03-31 --nonce 123456789 --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dashboard_pipeline.tbc_bank_connector import (  # noqa: E402
    TBCBankConnector,
    to_xls_dataframe,
)
from dashboard_pipeline.tbc_cache import append_tbc_cache, read_tbc_cache  # noqa: E402


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def run_backfill(
    start: date,
    end: date,
    nonce: str,
    *,
    dry_run: bool = False,
) -> dict[int, int]:
    """
    Fetch [start, end] in a single SOAP call (paginated internally) using the
    given nonce, append to TBC parquet cache. Returns `{year: rows_added}`.
    """
    if start > end:
        raise ValueError(f"start ({start}) > end ({end})")
    if not nonce or not nonce.strip():
        raise ValueError("nonce is required (9-digit DigiPass OTP)")

    print(f"TBC backfill: {start} .. {end}  (dry_run={dry_run})")
    print(f"  nonce: {nonce}")

    conn = TBCBankConnector()
    t0 = time.time()
    movements = conn.fetch_movements(start, end, nonce=nonce)
    dt = time.time() - t0
    print(f"  fetched {len(movements):,} movements in {dt:.1f}s")

    if not movements:
        print("  (empty window — nothing to append)")
        return {}

    if dry_run:
        print("(dry run — no parquet written)")
        return {}

    df = to_xls_dataframe(movements)
    added = append_tbc_cache(df)
    added_summary = ", ".join(f"{y}+{n}" for y, n in sorted(added.items())) or "0"
    print(f"  added: {added_summary}")

    print("\nCurrent cache totals:")
    for y in range(start.year, end.year + 1):
        df_y = read_tbc_cache(y)
        print(f"  {y}: {len(df_y):,} rows")

    return added


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TBC cache backfill (append-only).")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument(
        "--nonce", required=True, help="9-digit DigiPass OTP (PIN 0777)"
    )
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
            args.nonce,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
