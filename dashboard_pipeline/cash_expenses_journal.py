"""Owner-entered cash expenses journal (ნაღდი ხარჯი — salary, rent,
service, owner-personal, etc.).

Each row carries a category so the daily money-flow can attribute cash
outflows from the till that have no corresponding bank line. Mirrors
``manual_payments_journal`` but is keyed by category instead of tax_id,
since these are not supplier payments.
"""

from __future__ import annotations

import csv
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from typing import Dict, List

from dashboard_pipeline.file_utils import _financial_analysis_path
from dashboard_pipeline.logging_config import get_logger

logger = get_logger(__name__)

JOURNAL_COLUMNS = (
    "id",
    "category",
    "amount",
    "date",
    "comment",
    "created_at",
    "deleted_at",
)

VALID_CATEGORIES = ("salary", "rent", "owner", "service", "supplier_cash", "other")

_io_lock = threading.RLock()


def journal_csv_path() -> str:
    return _financial_analysis_path("cash_expenses_journal.csv")


@dataclass
class CashExpenseEntry:
    id: str
    category: str
    amount: float
    date: str
    comment: str
    created_at: str
    deleted_at: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "category": self.category,
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


def _read_all_rows(path: str) -> List[CashExpenseEntry]:
    if not os.path.isfile(path):
        return []
    rows: List[CashExpenseEntry] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                amount = float((row.get("amount") or "0").strip() or "0")
            except ValueError:
                amount = 0.0
            rows.append(
                CashExpenseEntry(
                    id=str(row.get("id") or "").strip(),
                    category=str(row.get("category") or "").strip(),
                    amount=amount,
                    date=str(row.get("date") or "").strip(),
                    comment=str(row.get("comment") or "").strip(),
                    created_at=str(row.get("created_at") or "").strip(),
                    deleted_at=str(row.get("deleted_at") or "").strip(),
                )
            )
    return rows


def _atomic_write(path: str, rows: List[CashExpenseEntry]) -> None:
    """Write the full row list atomically (temp + replace)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="",
        dir=os.path.dirname(path), prefix=".cash_expenses_journal.", suffix=".tmp",
        delete=False,
    )
    try:
        writer = csv.DictWriter(tmp, fieldnames=JOURNAL_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r.to_dict())
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def append_entry(*, category: str, amount: float, date: str = "", comment: str = "") -> Dict[str, str]:
    """Append a single cash-expense entry. Returns the saved row dict."""
    cat = (category or "").strip().lower()
    if cat not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {VALID_CATEGORIES}; got '{category}'")
    if not isinstance(amount, (int, float)) or float(amount) <= 0:
        raise ValueError("amount must be a positive number")
    d = (date or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()
    if len(d) < 8:
        raise ValueError("date must be a non-empty ISO-style string")

    entry = CashExpenseEntry(
        id=str(uuid.uuid4()),
        category=cat,
        amount=float(amount),
        date=d,
        comment=str(comment or "").strip(),
        created_at=_now_iso(),
        deleted_at="",
    )
    path = journal_csv_path()
    with _io_lock:
        _ensure_journal_exists(path)
        rows = _read_all_rows(path)
        rows.append(entry)
        _atomic_write(path, rows)
    logger.info("cash_expenses: appended id=%s category=%s amount=%.2f date=%s", entry.id, entry.category, entry.amount, entry.date)
    return entry.to_dict()


def soft_delete_entry(entry_id: str) -> bool:
    eid = (entry_id or "").strip()
    if not eid:
        return False
    path = journal_csv_path()
    with _io_lock:
        rows = _read_all_rows(path)
        changed = False
        for r in rows:
            if r.id == eid and not r.deleted_at:
                r.deleted_at = _now_iso()
                changed = True
                break
        if changed:
            _atomic_write(path, rows)
    return changed


def read_active_entries() -> List[Dict]:
    path = journal_csv_path()
    rows = _read_all_rows(path)
    return [r.to_dict() for r in rows if not r.is_deleted]
