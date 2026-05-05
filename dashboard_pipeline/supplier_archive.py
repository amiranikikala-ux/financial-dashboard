"""User-archived suppliers (persistent across pipeline runs).

The user marks a supplier as „დაარქივებული" when they want it removed
from the active suppliers table (e.g. one-off material/service vendors).
Archiving is a display-only flag — payment data still flows through
KPIs, totals, and concentration analytics unchanged.

Storage: ``Financial_Analysis/supplier_archive.json``. Key = tax_id.

File schema:

    {
      "version": 1,
      "archived": {
        "<tax_id>": {
          "archived_at": "2026-05-06T22:00:00",
          "note": null
        },
        ...
      }
    }

Atomic write (write-tmp + rename); the API endpoint serializes calls
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
    return str(tax_id) in cache


def set_status(
    tax_id: str,
    archived: bool,
    note: str | None = None,
    financial_analysis_dir: Path | None = None,
) -> dict[str, dict]:
    """Toggle archived flag for one supplier. Returns the new full archived map."""
    path = _path(financial_analysis_dir)
    current = load(financial_analysis_dir)
    key = str(tax_id).strip()
    if not key:
        raise ValueError("tax_id must not be empty")

    if archived:
        current[key] = {
            "archived_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "note": note,
        }
    else:
        current.pop(key, None)

    payload = {"version": 1, "archived": current}

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
