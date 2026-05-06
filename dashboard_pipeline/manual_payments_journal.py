"""Event-based journal for owner-entered manual cash payments.

Each entry is one row with a UUID, soft-delete column, and timestamps.
Writes are atomic (lock + temp + replace) so concurrent /api/chat tool
calls cannot race the FastAPI POST handler.

This file is *additive* on top of the legacy ``manual_payments.csv``
aggregate that ``manual_payments.py`` produces. The pipeline reads both
and the supplier modal shows journal entries individually with delete
controls.
"""

from __future__ import annotations

import csv
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional

from dashboard_pipeline.file_utils import _financial_analysis_path
from dashboard_pipeline.logging_config import get_logger

logger = get_logger(__name__)

JOURNAL_COLUMNS = (
    "id",
    "tax_id",
    "amount",
    "date",
    "comment",
    "created_at",
    "deleted_at",
)

_write_lock = threading.Lock()


def journal_csv_path() -> str:
    return _financial_analysis_path("manual_payments_journal.csv")


@dataclass
class JournalEntry:
    id: str
    tax_id: str
    amount: float
    date: str
    comment: str
    created_at: str
    deleted_at: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "tax_id": self.tax_id,
            "amount": f"{self.amount:.2f}",
            "date": self.date,
            "comment": self.comment,
            "created_at": self.created_at,
            "deleted_at": self.deleted_at,
        }

    @property
    def is_deleted(self) -> bool:
        return bool(self.deleted_at)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_journal_exists(path: str) -> None:
    if os.path.isfile(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=JOURNAL_COLUMNS)
        writer.writeheader()


def _read_all_rows(path: str) -> List[JournalEntry]:
    if not os.path.isfile(path):
        return []
    rows: List[JournalEntry] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                amount = float((row.get("amount") or "0").strip() or "0")
            except ValueError:
                amount = 0.0
            rows.append(
                JournalEntry(
                    id=str(row.get("id") or "").strip(),
                    tax_id=str(row.get("tax_id") or "").strip(),
                    amount=amount,
                    date=str(row.get("date") or "").strip(),
                    comment=str(row.get("comment") or "").strip(),
                    created_at=str(row.get("created_at") or "").strip(),
                    deleted_at=str(row.get("deleted_at") or "").strip(),
                )
            )
    return rows


def _write_all_rows_atomic(path: str, rows: List[JournalEntry]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dir_name = os.path.dirname(path) or "."
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        dir=dir_name,
        delete=False,
        prefix=".manual_journal_",
        suffix=".tmp",
    ) as tmp:
        writer = csv.DictWriter(tmp, fieldnames=JOURNAL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
        tmp_path = tmp.name

    last_err: Optional[OSError] = None
    for _ in range(20):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError as exc:
            last_err = exc
            time.sleep(0.01)
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    raise last_err if last_err else RuntimeError("atomic replace failed")


def read_active_entries(path: Optional[str] = None) -> List[Dict]:
    """Return all non-deleted journal entries as plain dicts.

    Pipeline / read-only callers should use this. The returned dicts have
    primitive types only and are safe to JSON-encode.
    """
    p = path or journal_csv_path()
    rows = _read_all_rows(p)
    return [
        {
            "id": r.id,
            "tax_id": r.tax_id,
            "amount": r.amount,
            "date": r.date,
            "comment": r.comment,
            "created_at": r.created_at,
        }
        for r in rows
        if not r.is_deleted and r.amount > 0
    ]


def read_entries_for_tax_id(tax_id: str, path: Optional[str] = None) -> List[Dict]:
    tid = str(tax_id or "").strip()
    if not tid:
        return []
    return [e for e in read_active_entries(path) if e["tax_id"] == tid]


def append_entry(
    *,
    tax_id: str,
    amount: float,
    date: str = "",
    comment: str = "",
    path: Optional[str] = None,
) -> Dict:
    """Append one new payment. Returns the saved entry as a dict."""
    p = path or journal_csv_path()
    tid = str(tax_id or "").strip()
    if not tid or not tid.isdigit():
        raise ValueError("tax_id must be a non-empty digit string")
    try:
        amt = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("amount must be numeric") from exc
    if amt <= 0:
        raise ValueError("amount must be > 0")

    entry = JournalEntry(
        id=str(uuid.uuid4()),
        tax_id=tid,
        amount=round(amt, 2),
        date=str(date or "").strip(),
        comment=str(comment or "").strip(),
        created_at=_now_iso(),
        deleted_at="",
    )

    with _write_lock:
        _ensure_journal_exists(p)
        rows = _read_all_rows(p)
        rows.append(entry)
        _write_all_rows_atomic(p, rows)

    logger.info(
        "manual_payments_journal: appended id=%s tax_id=%s amount=%.2f",
        entry.id,
        entry.tax_id,
        entry.amount,
    )
    return {
        "id": entry.id,
        "tax_id": entry.tax_id,
        "amount": entry.amount,
        "date": entry.date,
        "comment": entry.comment,
        "created_at": entry.created_at,
    }


def soft_delete_entry(entry_id: str, path: Optional[str] = None) -> bool:
    """Mark the entry as deleted. Returns True if the row was found+changed."""
    p = path or journal_csv_path()
    eid = str(entry_id or "").strip()
    if not eid:
        return False

    with _write_lock:
        rows = _read_all_rows(p)
        changed = False
        for row in rows:
            if row.id == eid and not row.deleted_at:
                row.deleted_at = _now_iso()
                changed = True
                break
        if not changed:
            return False
        _write_all_rows_atomic(p, rows)

    logger.info("manual_payments_journal: soft-deleted id=%s", eid)
    return True


def aggregate_amount_by_tax_id(path: Optional[str] = None) -> Dict[str, float]:
    """Sum active entries per tax_id. Used by pipeline to add on top of the
    legacy ``manual_payments.csv`` aggregate when computing total_paid."""
    totals: Dict[str, float] = {}
    for e in read_active_entries(path):
        totals[e["tax_id"]] = totals.get(e["tax_id"], 0.0) + float(e["amount"])
    return totals
