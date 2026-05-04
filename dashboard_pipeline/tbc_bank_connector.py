"""
TBC DBI (Direct Bank Integration) SOAP connector — fetches account movements
via WS-Security UsernameToken auth, replacing the manual XLSX download
workflow for `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx`.

Endpoint: https://dbi.tbconline.ge/dbi/dbiService (Standard tier, no cert)
Auth:     env vars TBC_USERNAME + TBC_PASSWORD + DigiPass-supplied Nonce
Account:  env vars TBC_ACCOUNT_NUMBER + TBC_ACCOUNT_CURRENCY (default GEL)

Stage 0/1a/1b/2 PROOFED (2026-05-04): live verified — 104 movements / debit
9,641.40 ₾ / credit 9,994.94 ₾ in window 2026-03-01..2026-03-03 — 100%
parity vs manual XLSX, 4/5 random documentNumber spot-checks exact (1 collision
artifact resolved by composite-key joining).

🔒 DigiPass requirement: TBC DBI requires a 9-digit OTP per call (PIN 0777 →
press button → 9-digit code, valid ~5-15 min). Hardware token cannot be
automated — bank confirmed. Caller passes `nonce=...` to fetch_movements,
or sets TBC_NONCE env var per run.

XLSX-equivalent output: `to_xls_dataframe(movements)` produces a pandas
DataFrame matching the manual-download 23-column Georgian schema (sheet
`GE<...>-GEL`).
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

ENDPOINT = "https://dbi.tbconline.ge/dbi/dbiService"
NS = "http://www.mygemini.com/schemas/mygemini"
WSSE = (
    "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-"
    "secext-1.0.xsd"
)
DATE_FMT = "%Y-%m-%dT%H:%M:%S.000"
DATE_FMT_END = "%Y-%m-%dT%H:%M:%S.999"
PAGE_SIZE_DEFAULT = 700  # per docs


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


class TBCBankError(RuntimeError):
    """TBC DBI returned a SOAP fault, auth failure, or HTTP error."""


@dataclass
class Movement:
    movement_id: str
    payment_id: str
    external_payment_id: str
    debit_credit: int  # 0 = debit (outgoing), 1 = credit (incoming) — TBC convention verified 2026-05-04 live capture
    value_date: str
    description: str
    amount: float
    currency: str
    account_number: str
    account_name: str
    additional_information: str
    document_date: str
    document_number: str
    partner_account_number: str
    partner_name: str
    partner_tax_code: str
    partner_bank_code: str
    partner_bank: str
    intermediary_bank_code: str
    intermediary_bank: str
    charge_detail: str
    taxpayer_code: str
    taxpayer_name: str
    treasury_code: str
    operation_code: str
    additional_description: str
    exchange_rate: str
    partner_personal_number: str
    partner_document_type: str
    partner_document_number: str
    parent_external_payment_id: str
    status_code: str
    transaction_type: str
    raw: dict = field(default_factory=dict)


def _build_envelope(
    user: str,
    password: str,
    nonce: str,
    account: str,
    currency: str,
    period_from: datetime,
    period_to: datetime,
    page_index: int,
    page_size: int,
) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">\n'
        f"  <s:Header>\n"
        f'    <wsse:Security xmlns:wsse="{WSSE}">\n'
        f"      <wsse:UsernameToken>\n"
        f"        <wsse:Username>{html.escape(user)}</wsse:Username>\n"
        f"        <wsse:Password>{html.escape(password)}</wsse:Password>\n"
        f"        <wsse:Nonce>{html.escape(nonce)}</wsse:Nonce>\n"
        f"      </wsse:UsernameToken>\n"
        f"    </wsse:Security>\n"
        f"  </s:Header>\n"
        f"  <s:Body>\n"
        f'    <GetAccountMovementsRequestIo xmlns="{NS}">\n'
        f"      <accountMovementFilterIo>\n"
        f"        <pager>\n"
        f"          <pageIndex>{page_index}</pageIndex>\n"
        f"          <pageSize>{page_size}</pageSize>\n"
        f"        </pager>\n"
        f"        <accountNumber>{html.escape(account)}</accountNumber>\n"
        f"        <accountCurrencyCode>{html.escape(currency)}"
        f"</accountCurrencyCode>\n"
        f"        <periodFrom>{period_from.strftime(DATE_FMT)}</periodFrom>\n"
        f"        <periodTo>{period_to.strftime(DATE_FMT_END)}</periodTo>\n"
        f"      </accountMovementFilterIo>\n"
        f"    </GetAccountMovementsRequestIo>\n"
        f"  </s:Body>\n"
        f"</s:Envelope>\n"
    )


_TAG_RE = re.compile(r"<ns2:([a-zA-Z]+)>([^<]*)</ns2:\1>")
_AMOUNT_RE = re.compile(
    r"<ns2:amount>\s*<ns2:amount>([^<]*)</ns2:amount>\s*"
    r"<ns2:currency>([^<]*)</ns2:currency>\s*</ns2:amount>",
    re.DOTALL,
)


def _parse_int(value: str | None, default: int = 0) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: str | None, default: float = 0.0) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _iter_movements(xml: str) -> Iterable[Movement]:
    for m in re.finditer(
        r"<ns2:accountMovement>([\s\S]*?)</ns2:accountMovement>", xml
    ):
        block = m.group(1)
        # Top-level scalar fields (excluding nested <ns2:amount>...).
        # Strip the amount block out so we don't accidentally pick its inner tags.
        block_no_amount = _AMOUNT_RE.sub("", block)
        scalars = {
            tag: html.unescape(val.strip())
            for tag, val in _TAG_RE.findall(block_no_amount)
        }
        amt_match = _AMOUNT_RE.search(block)
        if amt_match:
            amount = _parse_float(amt_match.group(1))
            currency = amt_match.group(2).strip()
        else:
            amount = 0.0
            currency = ""
        yield Movement(
            movement_id=scalars.get("movementId", ""),
            payment_id=scalars.get("paymentId", ""),
            external_payment_id=scalars.get("externalPaymentId", ""),
            debit_credit=_parse_int(scalars.get("debitCredit")),
            value_date=scalars.get("valueDate", ""),
            description=scalars.get("description", ""),
            amount=amount,
            currency=currency,
            account_number=scalars.get("accountNumber", ""),
            account_name=scalars.get("accountName", ""),
            additional_information=scalars.get("additionalInformation", ""),
            document_date=scalars.get("documentDate", ""),
            document_number=scalars.get("documentNumber", ""),
            partner_account_number=scalars.get("partnerAccountNumber", ""),
            partner_name=scalars.get("partnerName", ""),
            partner_tax_code=scalars.get("partnerTaxCode", ""),
            partner_bank_code=scalars.get("partnerBankCode", ""),
            partner_bank=scalars.get("partnerBank", ""),
            intermediary_bank_code=scalars.get("intermediaryBankCode", ""),
            intermediary_bank=scalars.get("intermediaryBank", ""),
            charge_detail=scalars.get("chargeDetail", ""),
            taxpayer_code=scalars.get("taxpayerCode", ""),
            taxpayer_name=scalars.get("taxpayerName", ""),
            treasury_code=scalars.get("treasuryCode", ""),
            operation_code=scalars.get("operationCode", ""),
            additional_description=scalars.get("additionalDescription", ""),
            exchange_rate=scalars.get("exchangeRate", ""),
            partner_personal_number=scalars.get("partnerPersonalNumber", ""),
            partner_document_type=scalars.get("partnerDocumentType", ""),
            partner_document_number=scalars.get("partnerDocumentNumber", ""),
            parent_external_payment_id=scalars.get(
                "parentExternalPaymentId", ""
            ),
            status_code=scalars.get("statusCode", ""),
            transaction_type=scalars.get("transactionType", ""),
            raw=scalars,
        )


class TBCBankConnector:
    """
    TBC DBI SOAP client — read-only.

    Each call requires a fresh DigiPass nonce (~5-15 min validity per code).
    Pass `nonce` per call, or set TBC_NONCE env var (single-run convenience).

    Pagination handled internally — fetches subsequent pages until totalCount
    reached or empty page returned.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        account: str | None = None,
        currency: str | None = None,
        endpoint: str = ENDPOINT,
        timeout: int = 60,
    ):
        self.username = username or os.environ.get("TBC_USERNAME", "")
        self.password = password or os.environ.get("TBC_PASSWORD", "")
        if not self.username or not self.password:
            raise TBCBankError(
                "TBC credentials missing — set TBC_USERNAME and TBC_PASSWORD "
                "env vars or pass them to TBCBankConnector()."
            )
        self.account = account or os.environ.get("TBC_ACCOUNT_NUMBER", "")
        self.currency = currency or os.environ.get(
            "TBC_ACCOUNT_CURRENCY", "GEL"
        )
        if not self.account:
            raise TBCBankError(
                "TBC_ACCOUNT_NUMBER env var (or `account=`) is required."
            )
        self.endpoint = endpoint
        self.timeout = timeout
        self._session = requests.Session()

    def _post(self, envelope: str) -> str:
        r = self._session.post(
            self.endpoint,
            data=envelope.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{NS}/GetAccountMovements"',
            },
            timeout=self.timeout,
        )
        if r.status_code != 200:
            fault = re.search(
                r"<faultstring[^>]*>([^<]+)</faultstring>", r.text
            )
            msg = fault.group(1) if fault else r.text[:300]
            raise TBCBankError(
                f"TBC SOAP returned HTTP {r.status_code}: {msg}"
            )
        return r.text

    def fetch_movements(
        self,
        period_from: date,
        period_to: date,
        nonce: str | None = None,
        page_size: int = PAGE_SIZE_DEFAULT,
    ) -> list[Movement]:
        """
        Fetch all account movements in [period_from, period_to] (inclusive).

        DigiPass nonce required (5-15 min validity per code). Pages internally
        until totalCount reached.
        """
        nonce = nonce or os.environ.get("TBC_NONCE", "")
        if not nonce:
            raise TBCBankError(
                "TBC nonce missing — pass `nonce=` (DigiPass-generated 9-digit "
                "OTP) or set TBC_NONCE env var. Hardware DigiPass cannot be "
                "automated — request fresh code per run."
            )

        movements: list[Movement] = []
        page_index = 0
        while True:
            envelope = _build_envelope(
                user=self.username,
                password=self.password,
                nonce=nonce,
                account=self.account,
                currency=self.currency,
                period_from=datetime.combine(period_from, datetime.min.time()),
                period_to=datetime.combine(period_to, datetime.max.time()),
                page_index=page_index,
                page_size=page_size,
            )
            xml = self._post(envelope)
            page_movements = list(_iter_movements(xml))
            movements.extend(page_movements)

            total_match = re.search(r"<ns2:totalCount>(\d+)</ns2:totalCount>", xml)
            total = int(total_match.group(1)) if total_match else len(movements)
            if len(movements) >= total or not page_movements:
                break
            page_index += 1

        return movements


def _signed_amount(m: Movement) -> float:
    """XLSX convention: debit positive in 'გასული თანხა', credit positive in 'შემოსული თანხა'."""
    return abs(m.amount)


def _format_dt(iso: str) -> str:
    """ISO 'YYYY-MM-DDTHH:MM:SS' → 'YYYY-MM-DD HH:MM:SS' (or '' if empty)."""
    if not iso:
        return ""
    return iso.replace("T", " ")


XLS_COLUMNS = [
    "თარიღი",
    "დანიშნულება",
    "დამატებითი ინფორმაცია",
    "გასული თანხა",
    "შემოსული თანხა",
    "ნაშთი",
    "ტრანზაქციის ტიპი",
    "საბუთის თარიღი",
    "საბუთის №",
    "პარტნიორის ანგარიში",
    "პარტნიორი",
    "პარტნიორის საგადასახადო კოდი",
    "პარტნიორის ბანკის კოდი",
    "პარტნიორის ბანკი",
    "შუამავალი ბანკის კოდი",
    "შუამავალი ბანკი",
    "ხარჯის ტიპი",
    "გადასახადის გადამხდელის კოდი",
    "გადასახადის გადამხდელის დასახელება",
    "სახაზინო კოდი",
    "ოპ. კოდი",
    "დამატებითი დანიშნულება",
    "ტრანზაქციის ID",
]


def to_xls_dataframe(movements: Iterable[Movement]) -> pd.DataFrame:
    """
    Convert Movement objects → DataFrame matching the manual-download XLSX
    schema (`Financial_Analysis/თბს ბანკი ამონაწერი/<year>.xlsx`, 23 columns,
    sheet `<IBAN>-<CURRENCY>`).

    Note: `ნაშთი` (running balance) is statement-level, not per-record API
    field. Output leaves it blank — pipeline does not consume it.

    debitCredit==0 → outgoing (გასული თანხა)
    debitCredit==1 → incoming (შემოსული თანხა)
    """
    rows = []
    for m in movements:
        amt = _signed_amount(m)
        is_debit = m.debit_credit == 0
        rows.append({
            "თარიღი": _format_dt(m.value_date),
            "დანიშნულება": m.description,
            "დამატებითი ინფორმაცია": m.additional_information,
            "გასული თანხა": amt if is_debit else "",
            "შემოსული თანხა": amt if not is_debit else "",
            "ნაშთი": "",
            "ტრანზაქციის ტიპი": m.transaction_type,
            "საბუთის თარიღი": _format_dt(m.document_date),
            "საბუთის №": m.document_number,
            "პარტნიორის ანგარიში": m.partner_account_number,
            "პარტნიორი": m.partner_name,
            "პარტნიორის საგადასახადო კოდი": m.partner_tax_code,
            "პარტნიორის ბანკის კოდი": m.partner_bank_code,
            "პარტნიორის ბანკი": m.partner_bank,
            "შუამავალი ბანკის კოდი": m.intermediary_bank_code,
            "შუამავალი ბანკი": m.intermediary_bank,
            "ხარჯის ტიპი": m.charge_detail,
            "გადასახადის გადამხდელის კოდი": m.taxpayer_code,
            "გადასახადის გადამხდელის დასახელება": m.taxpayer_name,
            "სახაზინო კოდი": m.treasury_code,
            "ოპ. კოდი": m.operation_code,
            "დამატებითი დანიშნულება": m.additional_description,
            "ტრანზაქციის ID": m.movement_id,
        })
    return pd.DataFrame(rows, columns=XLS_COLUMNS)


__all__ = [
    "TBCBankConnector",
    "TBCBankError",
    "Movement",
    "to_xls_dataframe",
    "XLS_COLUMNS",
]
