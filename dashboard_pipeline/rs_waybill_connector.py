"""
rs.ge SOAP WayBillService connector — fetches buyer waybills (incoming receipts)
directly from rs.ge, replacing the manual XLS download workflow.

Endpoint: https://services.rs.ge/WayBillService/WayBillService.asmx
Auth:     env vars RS_USER + RS_PASS (or pass to RSWaybillConnector(...)).

Stage 3 PROOF (2026-05-04): live verified — sub-user `dashboard_api:400333858`
fetches 531 waybills / 170,677 ₾ in last 30 days, 9/9 spot-check vs UI matches.

XLS-equivalent output: `to_xls_dataframe(waybills)` produces a pandas DataFrame
with the same 21 Georgian-named columns the existing pipeline reads, so it can
drop in as a source replacement.
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import pandas as pd
import requests

ENDPOINT = "https://services.rs.ge/WayBillService/WayBillService.asmx"
NS = "http://tempuri.org/"
DATE_FMT = "%Y-%m-%dT%H:%M:%S"

# Verified mappings (480/531 cross-correlated against 04,2026.xls on 2026-05-04).
STATUS_TEXT = {
    1: "აქტიური",
    2: "დასრულებული",
    -2: "გაუქმებული",
}
TYPE_TEXT = {
    2: "ტრანსპორტირებით",
    3: "ტრანსპორტირების გარეშე",
    5: "უკან დაბრუნება",
    6: "ქვე-ზედნადები",
}
SELLER_ST_TEXT = {0: "გამყიდველი", 1: "მყიდველი"}


class RSWaybillError(RuntimeError):
    """rs.ge SOAP returned a non-success STATUS or HTTP error."""


@dataclass
class Waybill:
    id: str
    waybill_number: str
    create_date: str
    status: int
    type: int
    seller_tin: str
    seller_name: str
    buyer_tin: str
    buyer_name: str
    full_amount: float
    transport_coast: float
    car_number: str
    driver_tin: str
    driver_name: str
    start_address: str
    end_address: str
    activate_date: str
    begin_date: str
    delivery_date: str
    close_date: str
    seller_st: int
    par_id: str | None
    invoice_id: str | None
    waybill_comment: str
    is_corrected: bool
    is_confirmed: bool
    raw: dict = field(default_factory=dict)


def _build_envelope(method: str, params: dict) -> str:
    body = "".join(
        f"<{k}>{html.escape(str(v))}</{k}>"
        for k, v in params.items()
        if v is not None and v != ""
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '               xmlns:xsd="http://www.w3.org/2001/XMLSchema"\n'
        '               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">\n'
        "  <soap:Body>\n"
        f'    <{method} xmlns="{NS}">{body}</{method}>\n'
        "  </soap:Body>\n"
        "</soap:Envelope>\n"
    )


def _extract_result(xml: str, method: str) -> str | None:
    m = re.search(
        rf"<{method}Result[^>]*>(.+?)</{method}Result>", xml, flags=re.DOTALL,
    )
    return m.group(1).strip() if m else None


def _parse_int(value: str | None, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


class RSWaybillConnector:
    """Thin SOAP client for rs.ge WayBillService — read-only."""

    def __init__(
        self,
        user: str | None = None,
        password: str | None = None,
        endpoint: str = ENDPOINT,
        timeout: int = 60,
    ):
        self.user = user or os.environ.get("RS_USER", "")
        self.password = password or os.environ.get("RS_PASS", "")
        if not self.user or not self.password:
            raise RSWaybillError(
                "rs.ge credentials missing — set RS_USER and RS_PASS env vars "
                "or pass user/password to RSWaybillConnector()."
            )
        self.endpoint = endpoint
        self.timeout = timeout
        self._session = requests.Session()

    def _call(self, method: str, params: dict) -> str:
        envelope = _build_envelope(method, params)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{NS}{method}"',
        }
        r = self._session.post(
            self.endpoint,
            data=envelope.encode("utf-8"),
            headers=headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.text

    def check_auth(self) -> bool:
        xml = self._call(
            "chek_service_user", {"su": self.user, "sp": self.password},
        )
        result = _extract_result(xml, "chek_service_user") or ""
        return result.lower() == "true"

    def fetch_buyer_waybills(
        self,
        create_date_s: datetime,
        create_date_e: datetime,
    ) -> list[Waybill]:
        """Fetch all incoming (buyer) waybills created in [start, end] window."""
        params = {
            "su": self.user,
            "sp": self.password,
            "create_date_s": create_date_s.strftime(DATE_FMT),
            "create_date_e": create_date_e.strftime(DATE_FMT),
        }
        xml = self._call("get_buyer_waybills", params)
        m_status = re.search(r"<STATUS>(-?\d+)</STATUS>", xml)
        if m_status and m_status.group(1) not in ("0", ""):
            inner_status = m_status.group(1)
            if inner_status != "0":
                first_block = re.search(r"<WAYBILL>", xml)
                if not first_block:
                    raise RSWaybillError(
                        f"get_buyer_waybills returned STATUS={inner_status} "
                        f"with no waybills (date window {params['create_date_s']} → "
                        f"{params['create_date_e']})"
                    )
        return list(_iter_waybills(xml))

    def get_name_from_tin(self, tin: str) -> str | None:
        xml = self._call(
            "get_name_from_tin",
            {"su": self.user, "sp": self.password, "tin": tin},
        )
        result = _extract_result(xml, "get_name_from_tin")
        if result is None or result.lower() == "null":
            return None
        return result

    def is_vat_payer_tin(self, tin: str) -> bool:
        xml = self._call(
            "is_vat_payer_tin",
            {"su": self.user, "sp": self.password, "tin": tin},
        )
        return (_extract_result(xml, "is_vat_payer_tin") or "").lower() == "true"


def _iter_waybills(xml: str) -> Iterable[Waybill]:
    for m in re.finditer(r"<WAYBILL>([\s\S]*?)</WAYBILL>", xml):
        block = m.group(1)
        f = {
            tag: html.unescape(val)
            for tag, val in re.findall(r"<([A-Z_]+)>([^<]*)</\1>", block)
        }
        yield Waybill(
            id=f.get("ID", ""),
            waybill_number=f.get("WAYBILL_NUMBER", ""),
            create_date=f.get("CREATE_DATE", ""),
            status=_parse_int(f.get("STATUS")),
            type=_parse_int(f.get("TYPE")),
            seller_tin=f.get("SELLER_TIN", ""),
            seller_name=f.get("SELLER_NAME", ""),
            buyer_tin=f.get("BUYER_TIN", ""),
            buyer_name=f.get("BUYER_NAME", ""),
            full_amount=_parse_float(f.get("FULL_AMOUNT")),
            transport_coast=_parse_float(f.get("TRANSPORT_COAST")),
            car_number=f.get("CAR_NUMBER", ""),
            driver_tin=f.get("DRIVER_TIN", ""),
            driver_name=f.get("DRIVER_NAME", ""),
            start_address=f.get("START_ADDRESS", ""),
            end_address=f.get("END_ADDRESS", ""),
            activate_date=f.get("ACTIVATE_DATE", ""),
            begin_date=f.get("BEGIN_DATE", ""),
            delivery_date=f.get("DELIVERY_DATE", ""),
            close_date=f.get("CLOSE_DATE", ""),
            seller_st=_parse_int(f.get("SELLER_ST")),
            par_id=f.get("PAR_ID") or None,
            invoice_id=f.get("INVOICE_ID") or None,
            waybill_comment=f.get("WAYBILL_COMMENT", ""),
            is_corrected=f.get("IS_CORRECTED") == "1",
            is_confirmed=f.get("IS_CONFIRMED") == "1",
            raw=f,
        )


def _format_org(tin: str, name: str, is_vat: bool | None = None) -> str:
    """Match XLS 'ორგანიზაცია' column format: '(TIN[-დღგ]) name'."""
    if not tin and not name:
        return ""
    suffix = "-დღგ" if is_vat else ""
    return f"({tin}{suffix}) {name}".strip()


def _format_driver(tin: str, name: str) -> str:
    """Match XLS 'მძღოლი' format: '(TIN) name'."""
    if not tin and not name:
        return ""
    return f"({tin}) {name}".strip()


def _format_dt(iso: str) -> str:
    """ISO 'YYYY-MM-DDTHH:MM:SS' → XLS 'YYYY-MM-DD HH:MM:SS' (or '' if empty)."""
    if not iso:
        return ""
    return iso.replace("T", " ")


def to_xls_dataframe(
    waybills: Iterable[Waybill],
    vat_payer_tins: set[str] | None = None,
) -> pd.DataFrame:
    """
    Convert Waybill objects → DataFrame matching the manual-download XLS schema
    (`Financial_Analysis/რს ზედნადები/*.xls`, 21 Georgian columns).

    `vat_payer_tins` — set of seller TINs known to be VAT-registered. If provided,
    'ორგანიზაცია' column gets the '-დღგ' suffix. Otherwise that suffix is omitted
    (pipeline tax-id extraction tolerates both formats).
    """
    vat = vat_payer_tins or set()
    rows = []
    for w in waybills:
        # XLS convention: returns (TYPE=5 უკან დაბრუნება) carry a negative amount;
        # SOAP returns FULL_AMOUNT positive. The downstream pipeline's
        # `get_returned` reads raw `თანხა` directly, so we must negate here.
        is_return = w.type == 5
        amount = -abs(w.full_amount) if is_return else w.full_amount
        rows.append({
            "ზედნადები": w.waybill_number,
            "სტატუსი": STATUS_TEXT.get(w.status, str(w.status)),
            "მდგომარეობა": "მისაღები",  # buyer-side endpoint = always incoming
            "კატეგორია": "ჩვეულებრივი",
            "ტიპი": TYPE_TEXT.get(w.type, str(w.type)),
            "ორგანიზაცია": _format_org(
                w.seller_tin, w.seller_name, is_vat=w.seller_tin in vat,
            ),
            "თანხა": f"{amount:g}",
            "მძღოლი": _format_driver(w.driver_tin, w.driver_name),
            "ავტო": w.car_number,
            "ტრანსპ თანხა": f"{w.transport_coast:g}",
            "ტრანსპორტ. დაწყება": w.start_address,
            "მიწოდების ადგილი": w.end_address,
            "გააქტიურების თარ.": _format_dt(w.activate_date),
            "ტრანსპ. დაწყება": _format_dt(w.begin_date),
            "ჩაბარების თარ.": _format_dt(w.delivery_date),
            "გაუქმების თარ.": _format_dt(w.close_date) if w.status == -2 else "",
            "შენიშვნა": w.waybill_comment,
            "ა/ფ ID": w.invoice_id or "0",
            "STAT": "",  # XLS-only derived flag, pipeline does not require
            "ტრანსპორტირების ხარჯი": SELLER_ST_TEXT.get(w.seller_st, ""),
            "ID": w.id,
        })
    columns = [
        "ზედნადები", "სტატუსი", "მდგომარეობა", "კატეგორია", "ტიპი",
        "ორგანიზაცია", "თანხა", "მძღოლი", "ავტო", "ტრანსპ თანხა",
        "ტრანსპორტ. დაწყება", "მიწოდების ადგილი", "გააქტიურების თარ.",
        "ტრანსპ. დაწყება", "ჩაბარების თარ.", "გაუქმების თარ.", "შენიშვნა",
        "ა/ფ ID", "STAT", "ტრანსპორტირების ხარჯი", "ID",
    ]
    return pd.DataFrame(rows, columns=columns)
