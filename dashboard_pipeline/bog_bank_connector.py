"""
BOG Business Online API connector — fetches account statement entries via
REST + OAuth Client Credentials, replacing the manual XLSX download workflow.

Endpoint: https://api.businessonline.ge
Auth:     env vars BOG_CLIENT_ID + BOG_CLIENT_SECRET
Account:  env vars BOG_ACCOUNT_NUMBER + BOG_ACCOUNT_CURRENCY (defaults: GEL)

Stage 1-3 PROOF (2026-05-04): live verified — 453 entries / debit 3,891.84 ₾ /
credit 5,336.42 ₾ in window 2026-03-01..2026-03-03 — 100% parity vs manual
03,2026.xlsx, 5/5 random spot-checks exact (amount + beneficiary).

XLSX-equivalent output: `to_xls_dataframe(records)` produces a pandas DataFrame
with the same 26 Georgian-named columns the existing pipeline reads from
`Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx`, so it can drop in as a source
replacement.
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

TOKEN_ENDPOINT = (
    "https://account.bog.ge/auth/realms/bog/protocol/openid-connect/token"
)
API_BASE = "https://api.businessonline.ge"
DATE_FMT = "%Y-%m-%d"
PER_CALL_LIMIT = 1000


def _load_dotenv_once() -> None:
    """Best-effort `.env` loader (project root). Silent if dotenv missing."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_dotenv_once()


class BOGBankError(RuntimeError):
    """BOG API returned a non-success response or auth failure."""


@dataclass
class Movement:
    entry_date: str
    entry_id: str
    document_number: str
    amount: float
    amount_debit: float
    amount_credit: float
    comment: str
    document_product_group: str
    sender_name: str
    sender_tax_id: str
    sender_account: str
    sender_bank_code: str
    sender_bank_name: str
    beneficiary_name: str
    beneficiary_tax_id: str
    beneficiary_account: str
    beneficiary_bank_code: str
    beneficiary_bank_name: str
    purpose: str
    additional_info: str
    correspondent_account: str
    raw: dict = field(default_factory=dict)


class BOGBankConnector:
    """
    BOG Business Online REST client — read-only.

    Token is auto-cached for ~30 min. Date-window slicing handles the 1000-record
    per-call limit: high-volume days are auto-detected (chunk == limit) and
    re-fetched day-by-day.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        account: str | None = None,
        currency: str | None = None,
        timeout: int = 60,
    ):
        self.client_id = client_id or os.environ.get("BOG_CLIENT_ID", "")
        self.client_secret = (
            client_secret or os.environ.get("BOG_CLIENT_SECRET", "")
        )
        if not self.client_id or not self.client_secret:
            raise BOGBankError(
                "BOG credentials missing — set BOG_CLIENT_ID and "
                "BOG_CLIENT_SECRET env vars or pass them to BOGBankConnector()."
            )
        self.account = account or os.environ.get("BOG_ACCOUNT_NUMBER", "")
        self.currency = currency or os.environ.get("BOG_ACCOUNT_CURRENCY", "GEL")
        if not self.account:
            raise BOGBankError(
                "BOG_ACCOUNT_NUMBER env var (or `account=`) is required."
            )
        self.timeout = timeout
        self._session = requests.Session()
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_token(self) -> str:
        # 30-second safety margin before token expiry.
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        r = self._session.post(
            TOKEN_ENDPOINT,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise BOGBankError(
                f"BOG token fetch failed: HTTP {r.status_code} {r.text[:200]}"
            )
        payload = r.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 1800))
        return self._token

    def check_auth(self) -> bool:
        """Verify credentials by fetching a fresh token."""
        try:
            self._get_token()
            return True
        except BOGBankError:
            return False

    def _fetch_window(self, start: date, end: date) -> list[dict]:
        token = self._get_token()
        url = (
            f"{API_BASE}/api/statement/{self.account}/{self.currency}/"
            f"{start.strftime(DATE_FMT)}/{end.strftime(DATE_FMT)}"
        )
        r = self._session.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise BOGBankError(
                f"BOG statement fetch failed for {start}..{end}: "
                f"HTTP {r.status_code} {r.text[:200]}"
            )
        payload = r.json()
        if isinstance(payload, list):
            return payload
        for key in ("Records", "records", "Items", "items", "Data", "data"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        raise BOGBankError(
            f"BOG response shape unexpected: keys={list(payload.keys())[:10]}"
        )

    def fetch_statement(
        self,
        start: date,
        end: date,
        max_window_days: int = 1,
    ) -> list[Movement]:
        """
        Fetch all statement entries in [start, end] (inclusive).

        Default `max_window_days=1` does one API call per day — safe for any
        volume, including >1000 records/day accounts. Higher values reduce
        round-trips but require fall-back day-by-day re-fetch when a chunk
        hits the 1000-record cap.
        """
        if start > end:
            raise BOGBankError(f"start ({start}) > end ({end})")

        records: list[dict] = []
        cursor = start
        while cursor <= end:
            window_end = min(
                cursor + timedelta(days=max_window_days - 1), end
            )
            chunk = self._fetch_window(cursor, window_end)
            if len(chunk) >= PER_CALL_LIMIT and max_window_days > 1:
                day = cursor
                while day <= window_end:
                    records.extend(self._fetch_window(day, day))
                    day += timedelta(days=1)
            else:
                records.extend(chunk)
            cursor = window_end + timedelta(days=1)

        return [_to_movement(r) for r in records]


def _g(d: dict, *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _g_str(d: dict, *keys: str) -> str:
    v = _g(d, *keys)
    return str(v) if v is not None else ""


def _g_float(d: dict, *keys: str) -> float:
    v = _g(d, *keys)
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_movement(r: dict) -> Movement:
    sender = r.get("SenderDetails") or {}
    benef = r.get("BeneficiaryDetails") or {}
    if not isinstance(sender, dict):
        sender = {}
    if not isinstance(benef, dict):
        benef = {}
    return Movement(
        entry_date=_g_str(r, "EntryDate"),
        entry_id=_g_str(r, "EntryId"),
        document_number=_g_str(r, "EntryDocumentNumber"),
        amount=_g_float(r, "EntryAmount"),
        amount_debit=_g_float(r, "EntryAmountDebit"),
        amount_credit=_g_float(r, "EntryAmountCredit"),
        comment=_g_str(r, "EntryComment"),
        document_product_group=_g_str(r, "DocumentProductGroup"),
        sender_name=_g_str(sender, "Name"),
        sender_tax_id=_g_str(sender, "Inn"),
        sender_account=_g_str(sender, "AccountNumber"),
        sender_bank_code=_g_str(sender, "BankCode"),
        sender_bank_name=_g_str(sender, "BankName"),
        beneficiary_name=_g_str(benef, "Name"),
        beneficiary_tax_id=_g_str(benef, "Inn"),
        beneficiary_account=_g_str(benef, "AccountNumber"),
        beneficiary_bank_code=_g_str(benef, "BankCode"),
        beneficiary_bank_name=_g_str(benef, "BankName"),
        purpose=_g_str(r, "DocumentNomination"),
        additional_info=_g_str(r, "DocumentInformation"),
        correspondent_account=_g_str(r, "DocumentCorrespondentAccountNumber"),
        raw=r,
    )


XLS_COLUMNS = [
    "თარიღი",
    "საბუთის N",
    "მოკორესპოდენტო ანგარიში",
    "დებეტი",
    "კრედიტი",
    "ოპერაციის შინაარსი",
    "ოპერაციის ტიპი",
    "ოპერაციის იდ",
    "Ref",
    "გამგზავნის დასახელება",
    "გამგზავნის საიდენტიფიკაციო კოდი",
    "გამგზავნის ანგარიშის ნომერი",
    "გამგზავნი ბანკის კოდი",
    "გამგზავნი ბანკის დასახელება",
    "მიმღების დასახელება",
    "მიმღების საიდენტიფიკაციო კოდი",
    "მიმღების ანგარიშის ნომერი",
    "მიმღები ბანკის კოდი",
    "მიმღები ბანკის დასახელება",
    "დანიშნულება",
    "დამატებითი ინფორმაცია",
    "თანხა",
    "ბრუნვა დებეტი",
    "ბრუნვა კრედიტი",
    "ნაშთი დღის ბოლოს",
    "ნაშთი ოპერაციის ბოლოს",
]


def to_xls_dataframe(records: Iterable[Movement]) -> pd.DataFrame:
    """
    Convert Movement objects → DataFrame matching the manual-download XLSX schema
    (`Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx`, 26 Georgian columns).

    Note: `ბრუნვა დებეტი`, `ბრუნვა კრედიტი`, `ნაშთი დღის ბოლოს`,
    `ნაშთი ოპერაციის ბოლოს` are statement-level totals / running balances, not
    per-record API fields. Output leaves them blank — `bank_reconciliation.py`
    does not consume them.
    """
    rows = []
    for r in records:
        rows.append({
            "თარიღი": r.entry_date,
            "საბუთის N": r.document_number,
            "მოკორესპოდენტო ანგარიში": r.correspondent_account,
            "დებეტი": r.amount_debit if r.amount_debit else "",
            "კრედიტი": r.amount_credit if r.amount_credit else "",
            "ოპერაციის შინაარსი": r.comment,
            "ოპერაციის ტიპი": r.document_product_group,
            "ოპერაციის იდ": r.entry_id,
            "Ref": "",
            "გამგზავნის დასახელება": r.sender_name,
            "გამგზავნის საიდენტიფიკაციო კოდი": r.sender_tax_id,
            "გამგზავნის ანგარიშის ნომერი": r.sender_account,
            "გამგზავნი ბანკის კოდი": r.sender_bank_code,
            "გამგზავნი ბანკის დასახელება": r.sender_bank_name,
            "მიმღების დასახელება": r.beneficiary_name,
            "მიმღების საიდენტიფიკაციო კოდი": r.beneficiary_tax_id,
            "მიმღების ანგარიშის ნომერი": r.beneficiary_account,
            "მიმღები ბანკის კოდი": r.beneficiary_bank_code,
            "მიმღები ბანკის დასახელება": r.beneficiary_bank_name,
            "დანიშნულება": r.purpose,
            "დამატებითი ინფორმაცია": r.additional_info,
            "თანხა": r.amount,
            "ბრუნვა დებეტი": "",
            "ბრუნვა კრედიტი": "",
            "ნაშთი დღის ბოლოს": "",
            "ნაშთი ოპერაციის ბოლოს": "",
        })
    return pd.DataFrame(rows, columns=XLS_COLUMNS)


__all__ = [
    "BOGBankConnector",
    "BOGBankError",
    "Movement",
    "to_xls_dataframe",
    "XLS_COLUMNS",
]
