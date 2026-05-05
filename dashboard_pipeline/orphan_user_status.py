"""User-overridden status for orphan products (persistent across pipeline runs).

Currently a single state is supported: "ignored" — the user explicitly
marked the orphan as „უგულებელყოფილი" so it disappears from the active
worklist. Storage lives at `Financial_Analysis/orphan_user_status.json`.

Default state for any (store, product_id) NOT in the file is "active"
("გასასწორებელი" in the UI). If the user fixes the orphan in MegaPlus
(adds a real supplier), the row falls out of the orphan SQL on the
next pipeline run — no manual cleanup required here.

File schema (forward-compatible — version field reserved for migrations):

    {
      "version": 1,
      "ignored": {
        "<store>::<product_id>": {
          "ignored_at": "2026-05-05T22:00:00",
          "note": null
        },
        ...
      }
    }

Concurrency note: the API endpoint serializes writes with a lock at the
caller; this module only does atomic file replace (write-tmp + rename).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

USER_STATUS_FILENAME = "orphan_user_status.json"


def _path(financial_analysis_dir: Path | None = None) -> Path:
    base = financial_analysis_dir or (Path(__file__).resolve().parent.parent / "Financial_Analysis")
    return base / USER_STATUS_FILENAME


def _make_key(store: str, product_id: int) -> str:
    return f"{store}::{int(product_id)}"


def load(financial_analysis_dir: Path | None = None) -> dict[str, dict]:
    """Return {key: {ignored_at, note}} for ignored orphans. Empty if file missing."""
    path = _path(financial_analysis_dir)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        ignored = raw.get("ignored") or {}
        out: dict[str, dict] = {}
        for key, val in ignored.items():
            if isinstance(val, dict):
                out[str(key)] = val
            elif isinstance(val, str):
                # tolerate legacy bare-timestamp form
                out[str(key)] = {"ignored_at": val, "note": None}
        return out
    except (OSError, ValueError) as e:
        logger.warning("orphan_user_status: read failed (%s) — treating as empty", e)
        return {}


def is_ignored(
    store: str,
    product_id: int,
    cache: dict[str, dict] | None = None,
    financial_analysis_dir: Path | None = None,
) -> bool:
    if cache is None:
        cache = load(financial_analysis_dir)
    return _make_key(store, product_id) in cache


def set_status(
    store: str,
    product_id: int,
    ignored: bool,
    note: str | None = None,
    financial_analysis_dir: Path | None = None,
) -> dict[str, dict]:
    """Toggle ignored flag for one orphan. Returns the new full ignored map."""
    path = _path(financial_analysis_dir)
    current = load(financial_analysis_dir)
    key = _make_key(store, product_id)

    if ignored:
        current[key] = {
            "ignored_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "note": note,
        }
    else:
        current.pop(key, None)

    payload = {"version": 1, "ignored": current}

    # Atomic replace — write tmp + rename
    path.parent.mkdir(exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=USER_STATUS_FILENAME + ".",
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
