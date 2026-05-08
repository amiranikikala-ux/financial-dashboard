"""User-archived / excluded suppliers (persistent across pipeline runs).

Two orthogonal user flags per supplier:

1. **archived** — display-only flag. Hidden from the main supplier table
   but KPIs/totals/concentration analytics still include it.
2. **excluded_from_analysis** — pipeline-level filter. Sets total_debt=0
   for that supplier in aggregations (e.g. soon-to-be-cancelled waybills
   that the user accidentally accepted; payment will never happen, so
   counting them as debt distorts every analysis).

Storage: ``Financial_Analysis/supplier_archive.json``. Key = tax_id.
Backward-compatible with version 1 — additional fields are optional.

File schema (version 2):

    {
      "version": 2,
      "archived": {
        "<tax_id>": {
          "archived_at": "2026-05-06T22:00:00" | null,
          "note": null,
          "excluded_from_analysis": false,
          "excluded_at": null,
          "exclusion_reason": null
        },
        ...
      }
    }

Notes:
- An entry exists if the user has set ANY flag on this supplier.
- ``archived_at == null`` + ``excluded_from_analysis == true`` means the
  user excluded but did not archive (rare case, supported).
- Atomic write (write-tmp + rename); API endpoint serializes calls
  with a lock at the caller.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ARCHIVE_FILENAME = "supplier_archive.json"


def _path(financial_analysis_dir: Path | None = None) -> Path:
    base = financial_analysis_dir or (Path(__file__).resolve().parent.parent / "Financial_Analysis")
    return base / ARCHIVE_FILENAME


def load(financial_analysis_dir: Path | None = None) -> dict[str, dict]:
    """Return {tax_id: {archived_at, note}} for archived suppliers."""
    path = _path(financial_analysis_dir)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        archived = raw.get("archived") or {}
        out: dict[str, dict] = {}
        for key, val in archived.items():
            if isinstance(val, dict):
                out[str(key)] = val
            elif isinstance(val, str):
                out[str(key)] = {"archived_at": val, "note": None}
        return out
    except (OSError, ValueError) as e:
        logger.warning("supplier_archive: read failed (%s) — treating as empty", e)
        return {}


def is_archived(
    tax_id: str,
    cache: dict[str, dict] | None = None,
    financial_analysis_dir: Path | None = None,
) -> bool:
    if cache is None:
        cache = load(financial_analysis_dir)
    entry = cache.get(str(tax_id))
    if not entry:
        return False
    return bool(entry.get("archived_at"))


def is_excluded_from_analysis(
    tax_id: str,
    cache: dict[str, dict] | None = None,
    financial_analysis_dir: Path | None = None,
) -> bool:
    if cache is None:
        cache = load(financial_analysis_dir)
    entry = cache.get(str(tax_id))
    if not entry:
        return False
    return bool(entry.get("excluded_from_analysis"))


def excluded_entries(
    cache: dict[str, dict] | None = None,
    financial_analysis_dir: Path | None = None,
) -> dict[str, dict]:
    """Return only entries with excluded_from_analysis=True (with reason)."""
    if cache is None:
        cache = load(financial_analysis_dir)
    return {
        tid: dict(entry)
        for tid, entry in cache.items()
        if entry.get("excluded_from_analysis")
    }


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def set_status(
    tax_id: str,
    archived: bool | None = None,
    note: str | None = None,
    excluded_from_analysis: bool | None = None,
    exclusion_reason: str | None = None,
    financial_analysis_dir: Path | None = None,
) -> dict[str, dict]:
    """Update flags for one supplier. Any flag passed as None is left unchanged.

    Removing the entry entirely happens only when both archived=False and
    excluded_from_analysis=False (or were already False). Returns the new
    full map.
    """
    path = _path(financial_analysis_dir)
    current = load(financial_analysis_dir)
    key = str(tax_id).strip()
    if not key:
        raise ValueError("tax_id must not be empty")

    entry = dict(current.get(key) or {})

    if archived is True:
        entry["archived_at"] = _now_iso()
        if note is not None:
            entry["note"] = note
    elif archived is False:
        entry["archived_at"] = None
        if note is not None:
            entry["note"] = note

    if excluded_from_analysis is True:
        entry["excluded_from_analysis"] = True
        entry["excluded_at"] = _now_iso()
        if exclusion_reason is not None:
            entry["exclusion_reason"] = exclusion_reason
    elif excluded_from_analysis is False:
        entry["excluded_from_analysis"] = False
        entry["excluded_at"] = None
        if exclusion_reason is not None:
            entry["exclusion_reason"] = exclusion_reason

    has_archive = bool(entry.get("archived_at"))
    has_exclusion = bool(entry.get("excluded_from_analysis"))
    if not has_archive and not has_exclusion:
        current.pop(key, None)
    else:
        current[key] = entry

    payload = {"version": 2, "archived": current}

    path.parent.mkdir(exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=ARCHIVE_FILENAME + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return current
