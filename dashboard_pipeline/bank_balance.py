"""Bank balance fetcher + cache.

Fetches the current balance from BOG (REST) and TBC (SOAP `GetAccountStatement`),
stores results in ``Financial_Analysis/cache/bank_balance.json``. Called from
the bank refresh flow after each connector's statement fetch succeeds, so the
same DigiPass OTP that paid for the TBC movements also pays for the balance
(no extra owner action).

Schema of bank_balance.json:
    {
      "bog": {
        "available": 12345.67,
        "current": 12345.67,
        "currency": "GEL",
        "account": "GE15BG...",
        "fetched_at": "2026-05-14T11:21:33+00:00"
      },
      "tbc": {
        "closing_balance": 9876.54,
        "opening_balance": 9876.54,
        "closing_date": "2026-05-14",
        "currency": "GEL",
        "account": "GE90TB...",
        "fetched_at": "2026-05-14T11:21:33+00:00"
      }
    }
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from dashboard_pipeline.bog_bank_connector import BOGBankConnector
from dashboard_pipeline.tbc_bank_connector import TBCBankConnector

BALANCE_FILE = (
    Path(__file__).resolve().parent.parent
    / "Financial_Analysis"
    / "cache"
    / "bank_balance.json"
)

_balance_lock = threading.Lock()


def _read_state(path: Path | None = None) -> dict:
    p = path or BALANCE_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(state: dict, path: Path | None = None) -> None:
    p = path or BALANCE_FILE
    with _balance_lock:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def fetch_bog_balance(*, state_path: Path | None = None) -> dict:
    """Fetch BOG balance via REST and save to cache.

    Uses the same env-based credentials as the statement fetcher
    (BOG_CLIENT_ID, BOG_CLIENT_SECRET, BOG_ACCOUNT_NUMBER).
    """
    conn = BOGBankConnector()
    balance = conn.fetch_balance()
    record = {
        "available": balance["available"],
        "current": balance["current"],
        "currency": conn.currency,
        "account": conn.account,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    state = _read_state(state_path)
    state["bog"] = record
    _write_state(state, state_path)
    return record


def fetch_tbc_balance(
    nonce: str,
    *,
    as_of: date | None = None,
    state_path: Path | None = None,
) -> dict:
    """Fetch TBC balance via SOAP GetAccountStatement and save to cache.

    `nonce` is the same 9-digit DigiPass OTP used for statement fetch — TBC
    allows reuse across calls within the OTP validity window (verified via
    paginated GetAccountMovements which reuses the same nonce).
    """
    conn = TBCBankConnector()
    balance = conn.fetch_balance(nonce=nonce, as_of=as_of)
    record = {
        "closing_balance": balance["closing_balance"],
        "opening_balance": balance["opening_balance"],
        "closing_date": balance["closing_date"],
        "currency": balance["currency"] or conn.currency,
        "account": conn.account,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    state = _read_state(state_path)
    state["tbc"] = record
    _write_state(state, state_path)
    return record


def load_balances(*, state_path: Path | None = None) -> dict:
    """Return the latest cached balance file (empty dict if missing)."""
    return _read_state(state_path)


__all__ = [
    "fetch_bog_balance",
    "fetch_tbc_balance",
    "load_balances",
    "BALANCE_FILE",
]
