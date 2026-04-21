"""One-time Excel/CSV indexer for the AI Advisor `project_index` collection.

Walks ``Financial_Analysis/`` recursively, extracts a text representation
of each Excel/CSV file, and feeds the chunks into the local ChromaDB
``project_index`` collection via
:func:`dashboard_pipeline.ai.memory.index_project_files`.

Run manually after a fresh checkout (or whenever you want to refresh
historical context the AI advisor can recall through the
``recall_context`` tool):

    python index_project_files.py                # default: sampled rows
    python index_project_files.py --full          # index every row
    python index_project_files.py --replace       # drop old chunks first
    python index_project_files.py --max-rows 500
    python index_project_files.py --dir Financial_Analysis/რს\\ ზედნადები/
    python index_project_files.py --dry-run       # preview file list only

Defaults are deliberately conservative:
* Each file capped at ``DEFAULT_MAX_ROWS_PER_FILE = 2000`` rows.
* Sheets capped at the first ``DEFAULT_MAX_SHEETS = 5``.
* Files larger than ``--skip-larger-than`` MB (default 80) are skipped
  unless ``--full`` is passed.

Tags applied to every indexed chunk:
* ``"excel"`` / ``"csv"`` — file kind.
* ``"category:<folder-mapped-name>"`` — see ``_CATEGORY_MAP`` below.
* ``"year:YYYY"`` — extracted from the file name (e.g. ``01--2025.xls``).

Heavy deps (``chromadb`` + ``sentence-transformers``) are imported lazily
through :mod:`dashboard_pipeline.ai.memory`. Pandas + openpyxl + xlrd are
already pinned in ``requirements.txt`` for the dashboard pipeline.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


logger = logging.getLogger("index_project_files")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DATA_DIR = Path("Financial_Analysis")

DEFAULT_MAX_ROWS_PER_FILE = 2_000
DEFAULT_MAX_SHEETS = 5
DEFAULT_SKIP_LARGER_THAN_MB = 80

EXCEL_EXTS = {".xls", ".xlsx", ".xlsm"}
CSV_EXTS = {".csv"}

#: Maps a folder name fragment (lowercase) → human-friendly category tag.
#: Order matters: first match wins, so put the most specific fragments
#: first.
_CATEGORY_MAP: Tuple[Tuple[str, str], ...] = (
    ("რს ზედნადები", "waybills"),
    ("შემოტანილი პროდუქცია", "products"),
    ("გაყიდული პროდუქტები", "sales"),
    ("ბოგ ბანკი", "bank"),
    ("თბს ბანკი", "bank"),
    ("ბანკი", "bank"),
)

#: Files we deliberately skip (config / fixtures, not historical data).
_SKIP_FILES: Tuple[str, ...] = (
    "manual_payments.example.csv",
    "object_mapping.json",
    "budget_config.json",
    "supplier_matching_registry.json",
    "unmatched_overrides.json",
    "tbc_expense_categories.json",
    "tbc_card_income_patterns.json",
    "tbc_samurneo_patterns.json",
    "tax_flow_patterns.json",
    "bog_pos_terminal_income_patterns.json",
    "sector_benchmarks.json",
)

_YEAR_RE = re.compile(r"(20\d{2})")


# ---------------------------------------------------------------------------
# File discovery + tag inference
# ---------------------------------------------------------------------------


def discover_files(root: Path) -> List[Path]:
    """Return every supported file under ``root`` (recursive)."""
    if not root.exists():
        raise FileNotFoundError(f"Data dir does not exist: {root}")
    out: List[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in _SKIP_FILES:
            continue
        suffix = path.suffix.lower()
        if suffix in EXCEL_EXTS or suffix in CSV_EXTS:
            out.append(path)
    return out


def infer_category(path: Path) -> Optional[str]:
    """Look up the category for ``path`` based on its folder name."""
    rel = str(path).replace("\\", "/").lower()
    for fragment, label in _CATEGORY_MAP:
        if fragment.lower() in rel:
            return label
    return None


def infer_year(path: Path) -> Optional[str]:
    """Extract a 20YY year token from the file name, if present."""
    match = _YEAR_RE.search(path.name)
    return match.group(1) if match else None


def build_tags(path: Path) -> List[str]:
    suffix = path.suffix.lower()
    tags: List[str] = []
    if suffix in EXCEL_EXTS:
        tags.append("excel")
    elif suffix in CSV_EXTS:
        tags.append("csv")
    cat = infer_category(path)
    if cat:
        tags.append(f"category:{cat}")
    year = infer_year(path)
    if year:
        tags.append(f"year:{year}")
    return tags


# ---------------------------------------------------------------------------
# File → text extraction
# ---------------------------------------------------------------------------


def _read_csv_text(
    path: Path,
    *,
    max_rows: Optional[int],
) -> Tuple[str, Dict[str, Any]]:
    import pandas as pd  # local import — pandas is heavy

    nrows = max_rows if max_rows and max_rows > 0 else None
    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        nrows=nrows,
        low_memory=False,
    )
    text = df.to_csv(index=False)
    return text, {"rows": int(len(df)), "cols": int(len(df.columns))}


def _read_excel_text(
    path: Path,
    *,
    max_rows: Optional[int],
    max_sheets: int,
) -> Tuple[str, Dict[str, Any]]:
    import pandas as pd  # local import

    engine: Optional[str] = None
    suffix = path.suffix.lower()
    if suffix == ".xls":
        engine = "xlrd"
    elif suffix in {".xlsx", ".xlsm"}:
        engine = "openpyxl"

    nrows = max_rows if max_rows and max_rows > 0 else None
    sheets = pd.read_excel(
        path,
        sheet_name=None,
        nrows=nrows,
        dtype=str,
        engine=engine,
    )

    parts: List[str] = []
    total_rows = 0
    sheet_count = 0
    for name, df in sheets.items():
        if sheet_count >= max_sheets:
            break
        sheet_count += 1
        total_rows += int(len(df))
        parts.append(f"### sheet: {name} ({len(df)} rows × {len(df.columns)} cols)")
        parts.append(df.to_csv(index=False))
        parts.append("")

    text = "\n".join(parts)
    return text, {"rows": total_rows, "sheets": sheet_count}


def extract_text(
    path: Path,
    *,
    max_rows: Optional[int],
    max_sheets: int,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Return ``(text, stats)`` or ``(None, {"error": ...})``."""
    try:
        suffix = path.suffix.lower()
        if suffix in CSV_EXTS:
            return _read_csv_text(path, max_rows=max_rows)
        if suffix in EXCEL_EXTS:
            return _read_excel_text(
                path,
                max_rows=max_rows,
                max_sheets=max_sheets,
            )
        return None, {"error": f"unsupported extension: {suffix}"}
    except Exception as exc:  # noqa: BLE001 — top-level CLI surface
        logger.warning("extract_text failed for %s: %s", path, exc)
        return None, {"error": str(exc)}


def file_size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Index Financial_Analysis/ Excel + CSV files into the local "
            "ChromaDB project_index collection used by recall_context."
        )
    )
    parser.add_argument(
        "--dir",
        default=str(DEFAULT_DATA_DIR),
        help=f"Data directory (default: {DEFAULT_DATA_DIR}).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS_PER_FILE,
        help=(
            "Max rows per file (default %(default)s). Pass 0 with --full "
            "to keep every row."
        ),
    )
    parser.add_argument(
        "--max-sheets",
        type=int,
        default=DEFAULT_MAX_SHEETS,
        help="Max sheets per Excel file (default %(default)s).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Disable row + sheet caps (full file). Slow; use with care.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop existing chunks for each path before re-indexing.",
    )
    parser.add_argument(
        "--skip-larger-than",
        type=int,
        default=DEFAULT_SKIP_LARGER_THAN_MB,
        help=(
            "Skip files larger than N MB unless --full (default %(default)s)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files + tags + size without indexing.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N files (0 = no limit).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce log verbosity.",
    )
    return parser.parse_args(argv)


def _setup_logging(quiet: bool) -> None:
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=level,
    )


def _format_tags(tags: Iterable[str]) -> str:
    return ", ".join(tags) or "—"


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _setup_logging(args.quiet)

    data_dir = Path(args.dir)
    try:
        files = discover_files(data_dir)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    if args.limit > 0:
        files = files[: args.limit]

    if not files:
        print(f"[info] No Excel/CSV files found under {data_dir}.")
        return 0

    full_mode = bool(args.full)
    max_rows: Optional[int] = None if full_mode else args.max_rows
    if max_rows == 0 and not full_mode:
        max_rows = None  # treat 0 as "no cap" only with --full

    print(f"[info] Discovered {len(files)} candidate files under {data_dir}/.")
    print(
        f"[info] Mode: {'FULL' if full_mode else 'sampled'} | "
        f"max_rows={'∞' if full_mode else max_rows} | "
        f"max_sheets={'∞' if full_mode else args.max_sheets} | "
        f"skip_larger_than={args.skip_larger_than}MB | replace={args.replace}"
    )

    if args.dry_run:
        print("\n[dry-run] Files that would be indexed:")
        for path in files:
            tags = build_tags(path)
            size_mb = file_size_mb(path)
            print(f"  {size_mb:6.2f} MB  {path}  ({_format_tags(tags)})")
        return 0

    # Lazy import — keeps Prophet/Chroma deps optional at module import time.
    from dashboard_pipeline.ai.memory import (
        get_memory_store,
        index_project_files,
    )

    # Warm the store first so we surface dep errors before reading anything.
    try:
        store = get_memory_store()
    except Exception as exc:
        print(f"[error] Memory store unavailable: {exc}", file=sys.stderr)
        return 3

    before_counts = store.counts()
    print(f"[info] Existing collection counts: {before_counts}")

    file_specs: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for idx, path in enumerate(files, start=1):
        size_mb = file_size_mb(path)
        if not full_mode and size_mb > args.skip_larger_than:
            skipped.append(f"{path} ({size_mb:.1f} MB > {args.skip_larger_than})")
            continue
        rel_path = str(path).replace("\\", "/")
        tags = build_tags(path)
        print(
            f"  [{idx:>3}/{len(files)}] reading {size_mb:6.2f} MB  "
            f"{rel_path}  ({_format_tags(tags)}) ..."
        )
        text, stats = extract_text(
            path,
            max_rows=max_rows,
            max_sheets=args.max_sheets,
        )
        if text is None:
            print(f"      └─ skipped: {stats.get('error')}")
            skipped.append(f"{path} (read error: {stats.get('error')})")
            continue
        chars = len(text)
        rows = stats.get("rows", 0)
        sheets = stats.get("sheets", 1)
        print(
            f"      └─ {rows} rows × {sheets} sheet(s) → {chars/1024:.1f} KB text"
        )
        file_specs.append({
            "path": rel_path,
            "text": text,
            "tags": tags,
        })

    if not file_specs:
        print("[info] Nothing to index after filters.")
        return 0

    print(f"\n[info] Indexing {len(file_specs)} files into ChromaDB ...")
    started = time.monotonic()

    seen_count = 0

    def _progress(event: Dict[str, Any]) -> None:
        nonlocal seen_count
        seen_count += 1
        ok = event.get("ok", False)
        chunks = event.get("chunks", 0)
        marker = "✓" if ok else "✗"
        print(
            f"      {marker} {event.get('path')}: "
            f"{chunks} chunks{'' if ok else ' (' + str(event.get('error')) + ')'}"
        )

    result = index_project_files(
        file_specs,
        replace=args.replace,
        on_progress=_progress,
    )

    elapsed = time.monotonic() - started

    if "error" in result:
        print(f"[error] Indexing failed: {result['error']}", file=sys.stderr)
        if "hint" in result:
            print(f"[hint] {result['hint']}", file=sys.stderr)
        return 4

    after_counts = store.counts()
    print("\n[done] Indexing summary:")
    print(f"  files indexed : {result.get('files', 0)}")
    print(f"  chunks added  : {result.get('chunks', 0)}")
    print(f"  before counts : {before_counts}")
    print(f"  after counts  : {after_counts}")
    print(f"  elapsed       : {elapsed:.1f} s")
    if skipped:
        print(f"  skipped       : {len(skipped)}")
        for line in skipped[:10]:
            print(f"    - {line}")
        if len(skipped) > 10:
            print(f"    … +{len(skipped) - 10} more")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
