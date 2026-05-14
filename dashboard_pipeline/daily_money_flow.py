"""
Daily money flow aggregator — per-day money in / out / internal / info.

Drives the Home page „დღის ფული" section. For a given date, decomposes:

  IN:
    - cash_megaplus           (Megaplus cash sales)
    - card_megaplus           (Megaplus card sales — what was sold)
    - pos_bank_deposit        (bank TRN/Wallet auto-deposits arriving today)
    - foodmart_cashback       (foodmart cashback credits)
    - other_in                (list of unclassified bank inflows)

  OUT:
    - suppliers               (per-supplier: amount, ap_before, ap_after, returns_today)
    - tax_treasury            (sahaziNo / treasury payments)
    - bank_fees               (COM operations)
    - other_out               (list of unclassified bank outflows)

  INTERNAL (movement only, neither in nor out):
    - own_bank_transfers      (TBC ↔ BOG, both partners = us)
    - cash_to_bank            (cash deposits to own account)

  INFO (no cash impact):
    - waybills_received       (count + total + by-supplier)

Implementation reads TBC + BOG parquet caches directly (one-line categorization)
and joins payment lines to waybills_data for per-supplier AP rolling balance.

Output: dict keyed by date string YYYY-MM-DD.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

logger = logging.getLogger(__name__)

OWN_TIN = "400333858"  # შპს ჯეო ფუდთაიმი

CACHE_ROOT = (
    Path(__file__).resolve().parent.parent / "Financial_Analysis" / "cache"
)


# ----------------------------------------------------------------------------
# Bank-line categorization
# ----------------------------------------------------------------------------

TREASURY_TIN_PATTERN = re.compile(
    r"(200122900|TRESGE22|სახელმწიფო ხაზინა|სახაზინო|ერთიანი სახაზინო|ხაზინის ერთიანი|გადასახადების ერთიანი კოდი)",
    re.IGNORECASE,
)
SAMURNEO_PATTERN = re.compile(r"სამეურნეო", re.IGNORECASE)
SALARY_PATTERN = re.compile(r"ხელფასი|შრომის ანაზღაურება|პრემია", re.IGNORECASE)
RENT_PATTERN = re.compile(r"იჯარა|ქირა", re.IGNORECASE)
REFUND_PATTERN = re.compile(r"ოპერაციის გაუქმება|თანხის დაბრუნება", re.IGNORECASE)
# Incoming refunds — money landing back in our account because a prior
# outgoing transfer was reversed (wrong account, bank correction, etc.).
# Not real revenue; must be excluded from the "ბანკში შემოვიდა" headline.
# NB: samurneo expense refunds ("სამეურნეო ხარჯის დაბრუნება") are caught
# by _is_samurneo first and stay in the samurneo netting bucket.
REFUND_IN_PATTERN = re.compile(
    r"შეცდომით ჩარიცხული|უკან დაბრუნება|დაბრუნებული თანხა",
    re.IGNORECASE,
)
OWNER_PARTNER_PATTERN = re.compile(r"კიკალიშვილი", re.IGNORECASE)
SUPPLIER_DEBT_PATTERN = re.compile(r"დავალიანების დაფარვა", re.IGNORECASE)
BANK_FEE_EXTRA_PATTERN = re.compile(
    r"გადარიცხვის საკომისიო|ამონაწერის საფასური|სტარტაპ ნაკრებ|სტარტაპერი ნაკრებ|საკომისიო:\s*(MAG_|Airnet|Ozurgeti|EP Georgia|SMS)|ინტეგრაციის სისტემით სარგებლობის",
    re.IGNORECASE,
)
SERVICE_TRANSIT_PATTERN = re.compile(
    r"(MAG_GELINK|Airnet|EP Georgia Supply|Ozurgeti cleaning)",
    re.IGNORECASE,
)


def _is_samurneo(purpose: str, partner_name: str) -> bool:
    blob = f"{purpose} {partner_name}"
    return bool(SAMURNEO_PATTERN.search(blob))
FOODMART_TIN = "404460187"
POS_TRN_HINTS = (
    "Wallet/domestic", "VISA", "MASTER", "ბარათებით", "ტრანზაქცი",
    "ნავაჭრი თანხა", "თანხები  GEO FOODTIME", "ერთიანი ანგარიშსწორება",
    "POS",
)
POS_PURPOSE_PATTERN = re.compile(
    r"გადახდა - თარიღი:.*ბარათი:|ნავაჭრი თანხა|ერთიანი ანგარიშსწორება",
    re.IGNORECASE,
)
CASH_DEPOSIT_HINTS = ("ნაღდი შეტანა", "თვითმომსახურების", "სალაროდან", "cash deposit", "შემოწირული ნაღდი")

# TBC cash deposit rows from transit/bank partner — physical cash put into TBC
# by the owner. Partner = TBC bank / transit. Purpose either mentions "ნავაჭრი"
# OR mentions a store name (დვაბზუ / ოზურგეთი / დუვაბზუ) — both are cash deposits
# from the till. Owner confirmed both patterns 2026-05-13.
TBC_CASH_DEPOSIT_PARTNERS = ("თიბისი ბანკი", "სატრანზიტო")
TBC_CASH_DEPOSIT_PURPOSE_RE = re.compile(r"ნავაჭრი|დვაბზუ|დუვაბზუ|ოზურგეთი", re.IGNORECASE)


def _is_own_account(tin: str, name: str) -> bool:
    """A line is internal if both ends are our company."""
    if not tin and not name:
        return False
    return str(tin or "").strip() == OWN_TIN or "ჯეო ფუდთაიმი" in str(name or "")


def _is_treasury(partner_tin: str, partner_name: str, purpose: str) -> bool:
    blob = f"{partner_tin} {partner_name} {purpose}"
    return bool(TREASURY_TIN_PATTERN.search(blob))


def _is_foodmart_cashback(partner_tin: str, partner_name: str, purpose: str) -> bool:
    if str(partner_tin or "").strip() == FOODMART_TIN:
        return True
    return "ფუდმარტი" in str(partner_name or "") and "ქეშბექი" in str(purpose or "")


def _is_pos_deposit(op_type: str, purpose: str, partner_name: str) -> bool:
    blob = f"{op_type} {purpose} {partner_name}"
    if any(h.lower() in blob.lower() for h in POS_TRN_HINTS):
        return True
    if POS_PURPOSE_PATTERN.search(blob):
        return True
    return False


def _is_cash_deposit(op_type: str, purpose: str) -> bool:
    blob = f"{op_type} {purpose}".lower()
    return any(h.lower() in blob for h in CASH_DEPOSIT_HINTS)


def _is_tbc_cash_via_terminal(partner_name: str, purpose: str) -> bool:
    """TBC bank lines where owner physically deposits cash and bank labels
    it as 'ნავაჭრი ...'. Partner is TBC bank / transit account, NOT external."""
    pname = (partner_name or "").lower()
    if not any(p in pname for p in (h.lower() for h in TBC_CASH_DEPOSIT_PARTNERS)):
        return False
    return bool(TBC_CASH_DEPOSIT_PURPOSE_RE.search(purpose or ""))


def _is_salary(purpose: str, partner_name: str) -> bool:
    return bool(SALARY_PATTERN.search(f"{purpose} {partner_name}"))


def _is_rent(purpose: str, partner_name: str) -> bool:
    return bool(RENT_PATTERN.search(f"{purpose} {partner_name}"))


def _is_owner_withdraw(purpose: str, partner_name: str) -> bool:
    """Operational withdraw — purpose says სამეურნეო OR partner is the owner."""
    if SAMURNEO_PATTERN.search(f"{purpose} {partner_name}"):
        return True
    return bool(OWNER_PARTNER_PATTERN.search(partner_name or ""))


def _is_refund_out(purpose: str) -> bool:
    return bool(REFUND_PATTERN.search(purpose or ""))


def _is_refund_in(purpose: str) -> bool:
    return bool(REFUND_IN_PATTERN.search(purpose or ""))


def _is_bank_fee_extra(purpose: str) -> bool:
    return bool(BANK_FEE_EXTRA_PATTERN.search(purpose or ""))


def _is_service_transit(purpose: str) -> bool:
    return bool(SERVICE_TRANSIT_PATTERN.search(purpose or ""))


_PARTNER_PREFIX_RE = re.compile(r"^([^,;]+)")


def _clean_partner_name(name: str) -> str:
    """Strip ", BAGAGE22, GE...", "; X 600...", etc. — keep first segment only.
    Pre-strips Georgian double-comma quotes (,,'') so we don't truncate at
    a quote-internal comma (e.g. "შპს ,,ტკბილი ქვეყანა''" → "შპს ტკბილი ქვეყანა")."""
    if not name:
        return ""
    s = str(name).strip().replace(",,", "").replace("''", "")
    m = _PARTNER_PREFIX_RE.match(s)
    return m.group(1).strip() if m else s


# ----------------------------------------------------------------------------
# Bank cache readers (TBC + BOG)
# ----------------------------------------------------------------------------


def _load_tbc_cache() -> pd.DataFrame:
    files = sorted((CACHE_ROOT / "tbc").glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["_day"] = pd.to_datetime(df["თარიღი"], errors="coerce").dt.date.astype(str)
    df["_out"] = pd.to_numeric(df["გასული თანხა"], errors="coerce").fillna(0.0)
    df["_in"] = pd.to_numeric(df["შემოსული თანხა"], errors="coerce").fillna(0.0)
    df["_partner_tin"] = df.get("პარტნიორის საგადასახადო კოდი", "").astype(str)
    df["_partner_name"] = df.get("პარტნიორი", "").astype(str)
    df["_purpose"] = df.get("დანიშნულება", "").astype(str)
    df["_op_type"] = df.get("ტრანზაქციის ტიპი", "").astype(str)
    df["_bank"] = "TBC"
    return df


def _load_bog_cache() -> pd.DataFrame:
    files = sorted((CACHE_ROOT / "bog").glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["_day"] = pd.to_datetime(df["თარიღი"], errors="coerce").dt.date.astype(str)
    df["_out"] = pd.to_numeric(df["დებეტი"], errors="coerce").fillna(0.0)
    df["_in"] = pd.to_numeric(df["კრედიტი"], errors="coerce").fillna(0.0)
    # BOG: when WE pay, debit is on our account; partner = receiver
    # when WE receive, credit; partner = sender
    df["_partner_tin"] = ""
    df["_partner_name"] = ""
    out_mask = df["_out"] > 0
    in_mask = df["_in"] > 0
    df.loc[out_mask, "_partner_tin"] = df.loc[out_mask, "მიმღების საიდენტიფიკაციო კოდი"].astype(str)
    df.loc[out_mask, "_partner_name"] = df.loc[out_mask, "მიმღების დასახელება"].astype(str)
    df.loc[in_mask, "_partner_tin"] = df.loc[in_mask, "გამგზავნის საიდენტიფიკაციო კოდი"].astype(str)
    df.loc[in_mask, "_partner_name"] = df.loc[in_mask, "გამგზავნის დასახელება"].astype(str)
    df["_purpose"] = df.get("დანიშნულება", "").astype(str)
    df["_op_type"] = df.get("ოპერაციის ტიპი", "").astype(str)
    df["_bank"] = "BOG"
    return df


def _load_bank_lines() -> pd.DataFrame:
    tbc = _load_tbc_cache()
    bog = _load_bog_cache()
    cols = ["_day", "_out", "_in", "_partner_tin", "_partner_name", "_purpose", "_op_type", "_bank"]
    frames = [df[cols] for df in (tbc, bog) if not df.empty]
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)


# ----------------------------------------------------------------------------
# Per-supplier AP rolling balance
# ----------------------------------------------------------------------------


def _build_supplier_ap_timeline(
    waybills_data: list[dict],
    supplier_payment_lines: dict[str, list[dict]],
) -> dict[str, list[tuple[str, float]]]:
    """For each supplier tax_id, return a sorted timeline of cumulative debt.

    Returns: {tax_id: [(date, cumulative_ap_after_this_date), ...]}.
    AP = sum(waybill_amounts incl. negative returns) - sum(payments) through date.
    """
    by_tid: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # Waybills add to AP (returns are already negative)
    for w in waybills_data or []:
        tid = _extract_tax_id(w.get("supplier"))
        if not tid:
            continue
        d = str(w.get("date") or "")[:10]
        if not d:
            continue
        status = str(w.get("status") or "")
        if status == "გაუქმებული":
            continue
        try:
            amt = float(w.get("effective_amount") or w.get("nominal_amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        by_tid[tid][d] += amt

    # Payments reduce AP
    for tid, lines in (supplier_payment_lines or {}).items():
        for ln in lines or []:
            d = str(ln.get("date") or "")[:10]
            if not d:
                continue
            try:
                amt = float(ln.get("amount") or 0)
            except (TypeError, ValueError):
                amt = 0.0
            by_tid[tid][d] -= amt

    timelines: dict[str, list[tuple[str, float]]] = {}
    for tid, by_day in by_tid.items():
        days = sorted(by_day.keys())
        cumulative = 0.0
        timeline = []
        for d in days:
            cumulative += by_day[d]
            timeline.append((d, cumulative))
        timelines[tid] = timeline
    return timelines


def _ap_at_end_of_day(timeline: list[tuple[str, float]], date: str) -> float:
    """Look up cumulative AP at end of `date`. Walks timeline (sorted) and
    returns the cumulative value of the latest entry with day <= date."""
    if not timeline:
        return 0.0
    last = 0.0
    for d, amt in timeline:
        if d <= date:
            last = amt
        else:
            break
    return last


_TAX_ID_RE = re.compile(r"^\(?\s*(\d{9,11})")

# Card brand + time detection in POS line purpose text.
_POS_TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2}|\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})")
_CARD_BRAND_RE = re.compile(r"\b(VISA|MASTER(?:CARD)?|MC|AMEX|MAESTRO)\b", re.IGNORECASE)

# Gross + fee parsers per bank format.
# BOG: "გადახდა - თარიღი: 08/05/2026 18:50:54; თანხა:GEL 88.05; საკომისიო: GEL 1.32; ბარათი: VISA..."
_BOG_GROSS_RE = re.compile(r"თანხა:\s*GEL\s*([\d.]+)")
_BOG_FEE_RE = re.compile(r"საკომისიო:\s*GEL\s*([\d.]+)")
# TBC: "...GEO FOODTIME LLC, TBC BANK, Visa, 2.20, RS014189,..."  (gross before fee deducted)
_TBC_GROSS_RE = re.compile(r"(?:Visa|MasterCard|MC),\s*([\d.]+),", re.IGNORECASE)


def _parse_pos_gross_fee(bank: str, purpose: str, net_amount: float) -> tuple[float, float]:
    """Return (gross, fee) for a POS bank line. Fee = gross - net for TBC
    (description carries only gross); fee parsed explicitly for BOG."""
    if bank == "BOG":
        g = _BOG_GROSS_RE.search(purpose or "")
        f = _BOG_FEE_RE.search(purpose or "")
        gross = float(g.group(1)) if g else 0.0
        fee = float(f.group(1)) if f else 0.0
        return gross, fee
    if bank == "TBC":
        g = _TBC_GROSS_RE.search(purpose or "")
        if g:
            gross = float(g.group(1))
            return gross, max(0.0, gross - net_amount)
        return 0.0, 0.0
    return 0.0, 0.0


def _summarize_pos_line(purpose: str, amount: float) -> dict:
    """Extract time + card brand from a POS bank line purpose for UI display."""
    t = _POS_TIME_RE.search(purpose or "")
    time_str = t.group(1) if t else ""
    # Normalize to HH:MM
    if " " in time_str:
        time_str = time_str.split()[-1][:5]
    else:
        time_str = time_str[:5]
    brand_m = _CARD_BRAND_RE.search(purpose or "")
    brand = (brand_m.group(1).upper() if brand_m else "").replace("MASTERCARD", "MC")
    return {
        "time": time_str,
        "amount": round(float(amount), 2),
        "card_brand": brand,
        "purpose": (purpose or "")[:120],
    }


def _extract_tax_id(supplier: str | None) -> str:
    if not supplier:
        return ""
    m = _TAX_ID_RE.search(str(supplier))
    return m.group(1) if m else ""


def _extract_supplier_name(supplier: str | None) -> str:
    """Strip leading '(tax_id) ' prefix."""
    if not supplier:
        return ""
    s = str(supplier)
    m = re.match(r"^\(\d{9,11}\)\s*(.+)$", s)
    return m.group(1) if m else s


# ----------------------------------------------------------------------------
# Main aggregator
# ----------------------------------------------------------------------------


def compute_daily_money_flow(
    *,
    retail_sales_data: dict,
    waybills_data: list[dict],
    supplier_payment_lines: dict[str, list[dict]],
    suppliers_list: list[dict] | None = None,
    days_back: int = 90,
    end_date: str | None = None,
) -> dict[str, dict]:
    """Compute per-day money flow for the last `days_back` days.

    Returns: {date_str: {in, out, internal, info, totals}}.
    """
    bank_df = _load_bank_lines()
    if bank_df.empty:
        logger.warning("daily_money_flow: bank cache empty — output will be sparse")

    # Cash expenses journal — owner-entered non-bank cash outflows by category
    try:
        from dashboard_pipeline import cash_expenses_journal as _cej
        cash_exp_entries = _cej.read_active_entries()
    except Exception as exc:
        logger.warning("daily_money_flow: cash_expenses_journal read failed: %s", exc)
        cash_exp_entries = []
    cash_exp_by_day: dict[str, list[dict]] = defaultdict(list)
    for e in cash_exp_entries:
        d = (e.get("date") or "")[:10]
        if d:
            cash_exp_by_day[d].append(e)

    # Cash/card per day from cashier_day_breakdown
    cdb = retail_sales_data.get("cashier_day_breakdown") or []
    cash_card_per_day: dict[str, dict[str, float]] = defaultdict(lambda: {"cash": 0.0, "card": 0.0})
    cash_sales_per_store_date: dict[tuple[str, str], float] = {}
    for r in cdb:
        d = str(r.get("day") or "")[:10]
        if not d:
            continue
        try:
            cash_card_per_day[d]["cash"] += float(r.get("cash") or 0)
            cash_card_per_day[d]["card"] += float(r.get("card") or 0)
        except (TypeError, ValueError):
            pass
        obj = (r.get("object") or "").strip()
        if obj:
            try:
                cv = float(r.get("cash") or 0)
            except (TypeError, ValueError):
                cv = 0.0
            if cv > 0:
                cash_sales_per_store_date[(obj, d)] = (
                    cash_sales_per_store_date.get((obj, d), 0.0) + cv
                )

    # Date range: end = latest cashier_day or today; start = end - days_back
    all_days = sorted(cash_card_per_day.keys())
    if end_date:
        last_day = end_date
    elif all_days:
        last_day = all_days[-1]
    else:
        last_day = pd.Timestamp.now().strftime("%Y-%m-%d")
    last_dt = pd.to_datetime(last_day)
    start_dt = last_dt - pd.Timedelta(days=days_back)
    start_day = start_dt.strftime("%Y-%m-%d")

    # AP timelines
    ap_timelines = _build_supplier_ap_timeline(waybills_data, supplier_payment_lines)

    # Supplier name lookup (TIN → human name), built from waybills AND from
    # the comprehensive suppliers list (which includes ფაქტურა-only suppliers
    # who never sent us a ზედნადები). Without the second source, BOG bank lines
    # with valid TIN but no waybill (e.g. cigarette importers, service firms)
    # silently fall to the "unmatched" bucket.
    supplier_name_by_tid: dict[str, str] = {}
    for w in waybills_data or []:
        tid = _extract_tax_id(w.get("supplier"))
        if tid and tid not in supplier_name_by_tid:
            nm = _extract_supplier_name(w.get("supplier"))
            if nm:
                supplier_name_by_tid[tid] = nm
    for s in suppliers_list or []:
        org = str(s.get("ორგანიზაცია") or "")
        tid = _extract_tax_id(org)
        if tid and tid not in supplier_name_by_tid:
            nm = _extract_supplier_name(org)
            if nm:
                supplier_name_by_tid[tid] = nm
    known_supplier_tins = set(supplier_name_by_tid.keys())

    # Reverse lookup: normalized supplier name → tax_id (for bank lines w/ empty TIN).
    # Normalization strips: company-form prefix, Georgian quote decoration
    # (e.g., „ნამე", ,,ნამე'', 'ნამე'), hyphen/space variation. Without this,
    # bank lines like "შპს „ბაგრატი"" or "შპს ქართული სად.-მარკ." don't match the
    # DB form "შპს ბაგრატი" / "შპს ქართული სად. მარკ.".
    _QUOTE_CHARS_RE = re.compile(r"[\"'„”“«»‘’‚‛]")

    def _norm_name(name: str) -> str:
        import html as _html
        s = _html.unescape(str(name or ""))  # &apos; → ', &amp; → &
        s = s.replace(",,", "").replace("''", "")
        s = _QUOTE_CHARS_RE.sub("", s)
        s = re.sub(r"^შპს\s+|^ი\.მ\.\s+|^სს\s+|^ი/მ\s+|^შ\.პ\.ს\.?\s+", "", s.strip(), flags=re.IGNORECASE)
        s = s.replace("-", " ")  # normalize hyphen ↔ space
        s = re.sub(r"\s*&\s*", "&", s)  # "დ & ლ" → "დ&ლ"
        return re.sub(r"\s+", " ", s).strip().lower()

    name_to_tid: dict[str, str] = {}
    for tid, nm in supplier_name_by_tid.items():
        key = _norm_name(nm)
        if key and key not in name_to_tid:
            name_to_tid[key] = tid

    # Pre-seed legacy aliases (curated by humans — handles spelling variants
    # like "ინტერნეიშენალ" vs "ინტერნეიშნლ" that automatic normalization misses).
    try:
        from dashboard_pipeline.supplier_matching import LEGACY_KNOWN_ALIASES as _LA
        for alias, tid in _LA.items():
            key = _norm_name(alias)
            if key and key not in name_to_tid:
                name_to_tid[key] = tid
            if tid not in supplier_name_by_tid:
                supplier_name_by_tid[tid] = alias
                known_supplier_tins.add(tid)
    except Exception as exc:
        logger.warning("daily_money_flow: LEGACY_KNOWN_ALIASES load failed: %s", exc)

    # Cross-bank TIN inference: TBC ხშირად TIN-ს ცარიელად ტოვებს, ხოლო BOG
    # იმავე მომწოდებლისთვის სრულ TIN-ს იცის. ერთ ბანკში გვინახავს TIN-ი იმავე
    # სახელისთვის → მეორე ბანკის ცარიელი-TIN ხაზებზე ვიყენებთ.
    if not bank_df.empty:
        for _, r in bank_df.iterrows():
            tid_b = str(r["_partner_tin"] or "").strip()
            if not tid_b or not re.fullmatch(r"\d{9,11}", tid_b):
                continue
            name_b = str(r["_partner_name"] or "")
            if not name_b:
                continue
            key_full = _norm_name(name_b)
            key_clean = _norm_name(_clean_partner_name(name_b))
            for key in (key_full, key_clean):
                if key and key not in name_to_tid:
                    name_to_tid[key] = tid_b
            # Track this supplier-name → record into supplier_name_by_tid too
            # (only if we don't have a name for that TIN yet)
            if tid_b not in supplier_name_by_tid:
                supplier_name_by_tid[tid_b] = _clean_partner_name(name_b)
                known_supplier_tins.add(tid_b)

    # Prefix-based name match for cases where bank uses shortened form
    # (e.g., "შპს თოლია" in bank, "შპს თოლია ქუთაისი" in DB). We only accept
    # the match if exactly ONE known supplier name STARTS WITH the bank name.
    # Ambiguous prefixes (multiple suppliers) stay unmatched — owner decides.
    def _resolve_by_prefix(short_key: str) -> str:
        if not short_key or len(short_key) < 4:
            return ""
        candidates = [tid for k, tid in name_to_tid.items() if k.startswith(short_key + " ") or k == short_key]
        unique = list(dict.fromkeys(candidates))
        return unique[0] if len(unique) == 1 else ""

    # Waybills indexed by day for "info"
    waybills_by_day: dict[str, list[dict]] = defaultdict(list)
    for w in waybills_data or []:
        d = str(w.get("date") or "")[:10]
        if d:
            waybills_by_day[d].append(w)

    # Index supplier_payment_lines by (tax_id, day) to find which supplier got paid
    pay_by_tid_day: dict[tuple[str, str], list[dict]] = defaultdict(list)
    pay_by_day: dict[str, list[dict]] = defaultdict(list)
    for tid, lines in (supplier_payment_lines or {}).items():
        for ln in lines or []:
            d = str(ln.get("date") or "")[:10]
            if not d:
                continue
            pay_by_tid_day[(tid, d)].append(ln)
            pay_by_day[d].append({**ln, "tax_id": tid})

    # Re-attribute TBC ნავაჭრი cash deposits from bank-deposit date to
    # inferred sales date. Pattern (project_cash_deposit_lag_pattern.md):
    # Dvabzu = 1-day lag; Ozurgeti weekday Tue-Sun = 1-day; Ozurgeti Monday =
    # Fri+Sat+Sun bundle (3-day shift to Friday).
    #
    # Earlier versions tried to "verify" the lag by matching deposit amount
    # against that day's cash sales within ±20%, falling back to the bank
    # date when no match. That broke partial deposits — e.g. 1 აპრ ოზურგ
    # 648.50 ₾ is genuinely 31 მარ ოზურგ money, but the owner had only
    # deposited part of that day's 1,748 ₾ in cash sales, so the 37% gap
    # tripped the guard and the row stayed on April 1, inflating April's
    # "ბანკში შემოვიდა" headline. cash_till.py already uses the simple
    # unconditional shift; we align here so the two views agree.
    def _infer_cash_deposit_sales_date(
        purpose: str, deposit_date: str, deposit_amount: float
    ) -> str:
        if "დვაბზუ" in purpose or "დუვაბზუ" in purpose:
            store = "დვაბზუ"
        elif "ოზურგეთი" in purpose or "ოზურგეტი" in purpose:
            store = "ოზურგეთი"
        else:
            return deposit_date
        d = pd.to_datetime(deposit_date, errors="coerce")
        if pd.isna(d):
            return deposit_date
        if store == "ოზურგეთი" and d.weekday() == 0:
            return (d - pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        return (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    if not bank_df.empty:
        for idx, r in bank_df.iterrows():
            try:
                in_amt = float(r["_in"] or 0)
            except (TypeError, ValueError):
                in_amt = 0.0
            if in_amt <= 0 or str(r["_bank"]) != "TBC":
                continue
            pname = str(r["_partner_name"] or "")
            purpose = str(r["_purpose"] or "")
            if not _is_tbc_cash_via_terminal(pname, purpose):
                continue
            inferred = _infer_cash_deposit_sales_date(
                purpose, str(r["_day"]), in_amt
            )
            if inferred != r["_day"]:
                bank_df.at[idx, "_day"] = inferred

    out_by_day: dict[str, dict] = {}
    bank_by_day = bank_df.groupby("_day") if not bank_df.empty else None

    # Pre-compute total AP across ALL suppliers for each day in the range.
    # Headline "მისაცემი" must include ALL suppliers (including ones with no
    # activity in the period), not just active ones — otherwise the
    # absolute starting/ending numbers misrepresent total debt.
    def _total_ap_at(date_str: str) -> float:
        return sum(_ap_at_end_of_day(tl, date_str) for tl in ap_timelines.values())

    cur = start_dt
    while cur <= last_dt:
        date = cur.strftime("%Y-%m-%d")
        cur += pd.Timedelta(days=1)

        cash = cash_card_per_day.get(date, {}).get("cash", 0.0)
        card = cash_card_per_day.get(date, {}).get("card", 0.0)

        # ----- Bank lines for this day -----
        pos_deposit = 0.0
        pos_deposit_tbc = 0.0
        pos_deposit_bog = 0.0
        pos_gross_tbc = 0.0
        pos_gross_bog = 0.0
        pos_fee_tbc = 0.0
        pos_fee_bog = 0.0
        pos_lines_tbc: list[dict] = []
        pos_lines_bog: list[dict] = []
        samurneo_in_tbc = 0.0
        samurneo_in_bog = 0.0
        other_in_tbc: list[dict] = []
        other_in_bog: list[dict] = []
        foodmart_cashback = 0.0
        other_in: list[dict] = []
        bank_in_total = 0.0

        tax_treasury = 0.0
        tax_treasury_tbc = 0.0
        tax_treasury_bog = 0.0
        bank_fees = 0.0
        bank_fees_tbc = 0.0
        bank_fees_bog = 0.0
        suppliers_out_tbc = 0.0
        suppliers_out_bog = 0.0
        salary_out = 0.0
        salary_items: list[dict] = []
        rent_out = 0.0
        rent_items: list[dict] = []
        owner_withdraw_out = 0.0
        owner_withdraw_items: list[dict] = []
        service_out = 0.0
        service_items: list[dict] = []
        refund_out = 0.0
        refund_items: list[dict] = []
        unmatched_supplier_out = 0.0
        unmatched_supplier_items: list[dict] = []
        other_out: list[dict] = []
        other_out_tbc: list[dict] = []
        other_out_bog: list[dict] = []
        bank_out_total = 0.0
        # Bank-only versions of salary/rent/etc. The *_out vars above are later
        # augmented by cash-journal entries (see cash_expenses_journal loop),
        # so for reconciliation against bank_out_total we need pure bank-side
        # tallies that cash-journal additions do NOT touch.
        bank_salary = 0.0
        bank_rent = 0.0
        bank_owner_withdraw = 0.0
        bank_service = 0.0
        bank_refund = 0.0
        bank_unmatched_supplier = 0.0
        bank_supplier_payments: dict[str, float] = defaultdict(float)
        bank_supplier_payments_tbc: dict[str, float] = defaultdict(float)
        bank_supplier_payments_bog: dict[str, float] = defaultdict(float)
        bank_supplier_purposes: dict[str, list[str]] = defaultdict(list)

        internal_transfers = 0.0
        cash_to_bank = 0.0
        cash_deposit_tbc = 0.0
        cash_deposit_bog = 0.0
        refund_in_tbc = 0.0
        refund_in_bog = 0.0
        refund_in_items: list[dict] = []

        if bank_by_day is not None and date in bank_by_day.groups:
            day_df = bank_by_day.get_group(date)
            for _, r in day_df.iterrows():
                out_amt = float(r["_out"] or 0)
                in_amt = float(r["_in"] or 0)
                ptin = str(r["_partner_tin"] or "").strip()
                pname = str(r["_partner_name"] or "")
                purpose = str(r["_purpose"] or "")
                op = str(r["_op_type"] or "")
                bank = str(r["_bank"] or "")

                # Internal transfer (own ↔ own)
                if _is_own_account(ptin, pname):
                    if in_amt > 0:
                        if _is_cash_deposit(op, purpose):
                            cash_to_bank += in_amt
                            if bank == "TBC":
                                cash_deposit_tbc += in_amt
                            elif bank == "BOG":
                                cash_deposit_bog += in_amt
                        internal_transfers += in_amt
                    if out_amt > 0:
                        internal_transfers += out_amt
                    continue

                # IN side
                if in_amt > 0:
                    # Incoming refund (wrong transfer corrected, etc.) is not
                    # real revenue — track separately and DO NOT roll into
                    # bank_in_total so the "ბანკში შემოვიდა" headline stays
                    # clean. e.g. April 1 2026 had a 1,090.69 ₾ row with
                    # "შეცდომით ჩარიცხული თანხის უკან დაბრუნება" that was
                    # silently inflating April's IN headline.
                    if _is_refund_in(purpose):
                        item_rin = {
                            "bank": bank,
                            "partner": pname or ptin,
                            "tax_id": ptin,
                            "amount": round(in_amt, 2),
                            "purpose": purpose[:120],
                        }
                        refund_in_items.append(item_rin)
                        if bank == "TBC":
                            refund_in_tbc += in_amt
                        elif bank == "BOG":
                            refund_in_bog += in_amt
                        continue
                    bank_in_total += in_amt
                    # TBC "ნავაჭრი" rows from bank transit partner = physical cash deposit
                    # by owner (NOT POS card). Owner confirmed 2026-05-13.
                    if bank == "TBC" and _is_tbc_cash_via_terminal(pname, purpose):
                        cash_deposit_tbc += in_amt
                    elif _is_pos_deposit(op, purpose, pname):
                        pos_deposit += in_amt
                        line = _summarize_pos_line(purpose, in_amt)
                        gross, fee = _parse_pos_gross_fee(bank, purpose, in_amt)
                        if bank == "TBC":
                            pos_deposit_tbc += in_amt
                            pos_gross_tbc += gross
                            pos_fee_tbc += fee
                            pos_lines_tbc.append(line)
                        elif bank == "BOG":
                            pos_deposit_bog += in_amt
                            pos_gross_bog += gross
                            pos_fee_bog += fee
                            pos_lines_bog.append(line)
                    elif _is_foodmart_cashback(ptin, pname, purpose):
                        foodmart_cashback += in_amt
                    elif _is_samurneo(purpose, pname):
                        if bank == "TBC":
                            samurneo_in_tbc += in_amt
                        elif bank == "BOG":
                            samurneo_in_bog += in_amt
                    else:
                        item = {
                            "bank": bank,
                            "partner": pname or ptin,
                            "tax_id": ptin,
                            "amount": round(in_amt, 2),
                            "purpose": purpose[:120],
                        }
                        other_in.append(item)
                        if bank == "TBC":
                            other_in_tbc.append(item)
                        elif bank == "BOG":
                            other_in_bog.append(item)

                # OUT side
                if out_amt > 0:
                    bank_out_total += out_amt
                    item_out = {
                        "bank": bank,
                        "partner": pname or ptin,
                        "tax_id": ptin,
                        "amount": round(out_amt, 2),
                        "purpose": purpose[:120],
                    }
                    if _is_treasury(ptin, pname, purpose):
                        tax_treasury += out_amt
                        if bank == "TBC":
                            tax_treasury_tbc += out_amt
                        elif bank == "BOG":
                            tax_treasury_bog += out_amt
                    elif op == "COM" or _is_bank_fee_extra(purpose):
                        bank_fees += out_amt
                        if bank == "TBC":
                            bank_fees_tbc += out_amt
                        elif bank == "BOG":
                            bank_fees_bog += out_amt
                    elif _is_refund_out(purpose):
                        refund_out += out_amt
                        bank_refund += out_amt
                        refund_items.append(item_out)
                    elif _is_salary(purpose, pname):
                        salary_out += out_amt
                        bank_salary += out_amt
                        salary_items.append(item_out)
                    elif _is_rent(purpose, pname):
                        rent_out += out_amt
                        bank_rent += out_amt
                        rent_items.append(item_out)
                    elif _is_owner_withdraw(purpose, pname):
                        owner_withdraw_out += out_amt
                        bank_owner_withdraw += out_amt
                        owner_withdraw_items.append(item_out)
                    elif _is_service_transit(purpose):
                        service_out += out_amt
                        bank_service += out_amt
                        service_items.append(item_out)
                    else:
                        # Match by TIN; or normalized full name; or cleaned-prefix name;
                        # or prefix-of-known-supplier (last-resort, single-candidate only).
                        norm_full = _norm_name(pname)
                        norm_clean = _norm_name(_clean_partner_name(pname))
                        resolved_tid = (
                            ptin if ptin in known_supplier_tins
                            else name_to_tid.get(norm_full, "")
                            or name_to_tid.get(norm_clean, "")
                            or _resolve_by_prefix(norm_clean)
                            or _resolve_by_prefix(norm_full)
                        )
                        if resolved_tid:
                            bank_supplier_payments[resolved_tid] += out_amt
                            bank_supplier_purposes[resolved_tid].append(purpose[:60])
                            if bank == "TBC":
                                suppliers_out_tbc += out_amt
                                bank_supplier_payments_tbc[resolved_tid] += out_amt
                            elif bank == "BOG":
                                suppliers_out_bog += out_amt
                                bank_supplier_payments_bog[resolved_tid] += out_amt
                            continue
                        # Fallback: purpose says "დავალიანების დაფარვა" → unmatched supplier bucket
                        if SUPPLIER_DEBT_PATTERN.search(purpose):
                            unmatched_supplier_out += out_amt
                            bank_unmatched_supplier += out_amt
                            unmatched_supplier_items.append(item_out)
                            continue
                        other_out.append(item_out)
                        if bank == "TBC":
                            other_out_tbc.append(item_out)
                        elif bank == "BOG":
                            other_out_bog.append(item_out)

        # ----- Cash expenses journal (owner-entered cash outflows by category) -----
        cash_exp_total = 0.0
        for e in cash_exp_by_day.get(date, []):
            cat = (e.get("category") or "").lower()
            try:
                amt = float(e.get("amount") or 0)
            except (TypeError, ValueError):
                amt = 0.0
            if amt <= 0:
                continue
            cash_exp_total += amt
            item = {
                "bank": "ნაღდი",
                "partner": e.get("comment", ""),
                "tax_id": "",
                "amount": round(amt, 2),
                "purpose": e.get("comment", ""),
            }
            if cat == "salary":
                salary_out += amt
                salary_items.append(item)
            elif cat == "rent":
                rent_out += amt
                rent_items.append(item)
            elif cat == "owner":
                owner_withdraw_out += amt
                owner_withdraw_items.append(item)
            elif cat == "service":
                service_out += amt
                service_items.append(item)
            elif cat == "supplier_cash":
                # treat like manual supplier payment without TIN — show as unmatched bucket
                unmatched_supplier_out += amt
                unmatched_supplier_items.append(item)
            else:
                other_out.append(item)

        # ----- Supplier payments + AP roll -----
        # Bank payments: from raw bank-line scan above (bank_supplier_payments).
        # Manual payments: from supplier_payment_lines where source is "manual".
        suppliers_out: list[dict] = []
        supplier_total_paid_bank = 0.0
        supplier_total_paid_manual = 0.0
        sup_agg: dict[str, dict] = {}

        # Manual entries from supplier_payment_lines dated today
        for ln in pay_by_day.get(date, []):
            tid = ln["tax_id"]
            if tid == OWN_TIN or tid not in known_supplier_tins:
                continue
            src = (ln.get("source") or "").lower()
            if "manual" not in src:
                continue
            amt = float(ln.get("amount") or 0)
            entry = sup_agg.setdefault(tid, {
                "tax_id": tid, "amount_bank": 0.0, "amount_manual": 0.0,
                "purposes": [],
            })
            entry["amount_manual"] += amt
            if ln.get("purpose"):
                entry["purposes"].append(str(ln["purpose"])[:60])

        # Bank entries from raw bank scan
        for tid, amt in bank_supplier_payments.items():
            if tid == OWN_TIN:
                continue
            entry = sup_agg.setdefault(tid, {
                "tax_id": tid, "amount_bank": 0.0, "amount_manual": 0.0,
                "purposes": [],
            })
            entry["amount_bank"] += amt
            entry["purposes"].extend(bank_supplier_purposes.get(tid, []))

        # Today's returns per supplier (for the day)
        returns_today: dict[str, float] = defaultdict(float)
        for w in waybills_by_day.get(date, []):
            if not w.get("is_return"):
                continue
            tid = _extract_tax_id(w.get("supplier"))
            if not tid:
                continue
            try:
                amt = float(w.get("effective_amount") or 0)
            except (TypeError, ValueError):
                amt = 0.0
            returns_today[tid] += amt  # already negative

        yesterday = (pd.to_datetime(date) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        for tid, entry in sup_agg.items():
            tl = ap_timelines.get(tid, [])
            ap_before = _ap_at_end_of_day(tl, yesterday)
            ap_after = _ap_at_end_of_day(tl, date)
            total_amt = entry["amount_bank"] + entry["amount_manual"]
            suppliers_out.append({
                "tax_id": tid,
                "supplier_name": supplier_name_by_tid.get(tid, ""),
                "amount": round(total_amt, 2),
                "amount_bank": round(entry["amount_bank"], 2),
                "amount_bank_tbc": round(bank_supplier_payments_tbc.get(tid, 0.0), 2),
                "amount_bank_bog": round(bank_supplier_payments_bog.get(tid, 0.0), 2),
                "amount_manual": round(entry["amount_manual"], 2),
                "ap_before": round(ap_before, 2),
                "ap_after": round(ap_after, 2),
                "returns_today": round(returns_today.get(tid, 0.0), 2),
                "purposes": list(dict.fromkeys(entry.get("purposes", [])))[:3],
            })
            supplier_total_paid_bank += entry["amount_bank"]
            supplier_total_paid_manual += entry["amount_manual"]

        # Returns-only suppliers (no payment today but returned goods)
        for tid, ret_amt in returns_today.items():
            if tid in sup_agg or tid == OWN_TIN:
                continue
            tl = ap_timelines.get(tid, [])
            suppliers_out.append({
                "tax_id": tid,
                "supplier_name": supplier_name_by_tid.get(tid, ""),
                "amount": 0.0,
                "amount_bank": 0.0,
                "amount_manual": 0.0,
                "ap_before": round(_ap_at_end_of_day(tl, yesterday), 2),
                "ap_after": round(_ap_at_end_of_day(tl, date), 2),
                "returns_today": round(ret_amt, 2),
                "purposes": [],
            })

        suppliers_out.sort(key=lambda x: (-x["amount"], -abs(x["returns_today"])))

        # Strip from other_out any bank lines that match suppliers we just listed
        # (they came in via supplier_payment_lines path).
        sup_tids = {s["tax_id"] for s in suppliers_out}
        other_out = [r for r in other_out if r["tax_id"] not in sup_tids]

        # ----- Info: waybills received -----
        # Drop "გაუქმებული" rows from BOTH the count and the sum — they didn't
        # actually arrive (rs.ge operation aborted). effective_amount is already
        # 0 for cancelled (see waybill_amounts.get_effective), so sums were
        # right; the count was leaking the cancelled rows by ~5/month, e.g.
        # April 2026 showed 5 extra ცალი in the "შემოვიდა" headline.
        wbs_today = [
            w for w in waybills_by_day.get(date, [])
            if str(w.get("status") or "") != "გაუქმებული"
        ]
        wbs_regular = [w for w in wbs_today if not w.get("is_return")]
        wbs_returns = [w for w in wbs_today if w.get("is_return")]
        wb_regular_total = sum(float(w.get("effective_amount") or 0) for w in wbs_regular)
        wb_returns_total = sum(float(w.get("effective_amount") or 0) for w in wbs_returns)

        # ----- Totals -----
        # Bank-only: real bank money in / out (the only ledger we have full data for).
        # Cash/card from Megaplus are reported separately (info-only, owner sees in KPI strip).
        # HEADLINE = raw bank_in_total / bank_out_total (accumulated unconditionally
        # inside the bank loop above — single source of truth, cannot silently miss
        # a category). Per-category breakdowns are for display only.
        # 🔴 Reconciliation rule (per AGENTS.md "no silent gap"): the categorized
        # sum MUST equal the raw total. If not, a bank row escaped classification —
        # we surface it as a warning so the owner sees red badge, not a quiet zero.
        supplier_total_paid = supplier_total_paid_bank + supplier_total_paid_manual
        bank_in = bank_in_total
        bank_out = bank_out_total
        cash_journal_out = supplier_total_paid_manual

        in_classified = (
            pos_deposit
            + cash_deposit_tbc + cash_deposit_bog
            + samurneo_in_tbc + samurneo_in_bog
            + foodmart_cashback
            + sum(r["amount"] for r in other_in)
        )
        out_classified = (
            supplier_total_paid_bank
            + tax_treasury + bank_fees
            + bank_salary + bank_rent + bank_owner_withdraw + bank_service
            + bank_refund + bank_unmatched_supplier
            + sum(r["amount"] for r in other_out_tbc)
            + sum(r["amount"] for r in other_out_bog)
        )
        warnings_today: list[str] = []
        in_gap = bank_in_total - in_classified
        out_gap = bank_out_total - out_classified
        if abs(in_gap) > 0.01:
            msg = f"ბანკში შემოვიდა — კატეგორიების ჯამი არ ემთხვევა ცოცხალ მონაცემს: სხვაობა {in_gap:.2f} ₾"
            warnings_today.append(msg)
            logger.error(
                "daily_money_flow %s: IN reconciliation gap %.2f (raw %.2f vs classified %.2f) — "
                "a credit was added to bank_in_total but not into any IN category",
                date, in_gap, bank_in_total, in_classified,
            )
        if abs(out_gap) > 0.01:
            msg = f"ბანკიდან გავიდა — კატეგორიების ჯამი არ ემთხვევა: სხვაობა {out_gap:.2f} ₾"
            warnings_today.append(msg)
            logger.error(
                "daily_money_flow %s: OUT reconciliation gap %.2f (raw %.2f vs classified %.2f) — "
                "a debit was added to bank_out_total but not into any OUT category",
                date, out_gap, bank_out_total, out_classified,
            )

        # Per-bank IN totals
        tbc_other_sum = sum(r["amount"] for r in other_in_tbc)
        bog_other_sum = sum(r["amount"] for r in other_in_bog)
        tbc_in_total = pos_deposit_tbc + samurneo_in_tbc + tbc_other_sum + cash_deposit_tbc
        bog_in_total = pos_deposit_bog + samurneo_in_bog + bog_other_sum + cash_deposit_bog

        out_by_day[date] = {
            "date": date,
            "in": {
                "cash_megaplus": round(cash, 2),
                "card_megaplus": round(card, 2),
                "pos_bank_deposit": round(pos_deposit, 2),
                "pos_bank_deposit_tbc": round(pos_deposit_tbc, 2),
                "pos_bank_deposit_bog": round(pos_deposit_bog, 2),
                "pos_lines_tbc": sorted(pos_lines_tbc, key=lambda x: x.get("time") or ""),
                "pos_lines_bog": sorted(pos_lines_bog, key=lambda x: x.get("time") or ""),
                "foodmart_cashback": round(foodmart_cashback, 2),
                "other": other_in,
                "tbc": {
                    "pos": round(pos_deposit_tbc, 2),
                    "pos_gross": round(pos_gross_tbc, 2),
                    "pos_fee": round(pos_fee_tbc, 2),
                    "cash_deposit": round(cash_deposit_tbc, 2),
                    "samurneo": round(samurneo_in_tbc, 2),
                    "other_items": other_in_tbc,
                    "other_total": round(tbc_other_sum, 2),
                    "total": round(tbc_in_total, 2),
                },
                "bog": {
                    "pos": round(pos_deposit_bog, 2),
                    "pos_gross": round(pos_gross_bog, 2),
                    "pos_fee": round(pos_fee_bog, 2),
                    "cash_deposit": round(cash_deposit_bog, 2),
                    "samurneo": round(samurneo_in_bog, 2),
                    "other_items": other_in_bog,
                    "other_total": round(bog_other_sum, 2),
                    "total": round(bog_in_total, 2),
                },
                "refund_in": round(refund_in_tbc + refund_in_bog, 2),
                "refund_in_tbc": round(refund_in_tbc, 2),
                "refund_in_bog": round(refund_in_bog, 2),
                "refund_in_items": refund_in_items,
                "bank_total": round(bank_in, 2),
                "total": round(cash + card + bank_in, 2),
            },
            "out": {
                "suppliers": suppliers_out,
                "suppliers_total": round(supplier_total_paid, 2),
                "suppliers_total_bank": round(supplier_total_paid_bank, 2),
                "suppliers_total_manual": round(supplier_total_paid_manual, 2),
                "tax_treasury": round(tax_treasury, 2),
                "bank_fees": round(bank_fees, 2),
                "salary": round(salary_out, 2),
                "salary_bank": round(bank_salary, 2),
                "salary_items": salary_items,
                "rent": round(rent_out, 2),
                "rent_bank": round(bank_rent, 2),
                "rent_items": rent_items,
                "owner_withdraw": round(owner_withdraw_out, 2),
                "owner_withdraw_bank": round(bank_owner_withdraw, 2),
                "owner_withdraw_items": owner_withdraw_items,
                "service": round(service_out, 2),
                "service_bank": round(bank_service, 2),
                "service_items": service_items,
                "refund": round(refund_out, 2),
                "refund_bank": round(bank_refund, 2),
                "refund_items": refund_items,
                "unmatched_suppliers": round(unmatched_supplier_out, 2),
                "unmatched_suppliers_bank": round(bank_unmatched_supplier, 2),
                "unmatched_supplier_items": unmatched_supplier_items,
                "other": other_out,
                "tbc": {
                    "suppliers": round(suppliers_out_tbc, 2),
                    "tax_treasury": round(tax_treasury_tbc, 2),
                    "bank_fees": round(bank_fees_tbc, 2),
                    "other_items": other_out_tbc,
                    "other_total": round(sum(r["amount"] for r in other_out_tbc), 2),
                    "total": round(suppliers_out_tbc + tax_treasury_tbc + bank_fees_tbc + sum(r["amount"] for r in other_out_tbc), 2),
                },
                "bog": {
                    "suppliers": round(suppliers_out_bog, 2),
                    "tax_treasury": round(tax_treasury_bog, 2),
                    "bank_fees": round(bank_fees_bog, 2),
                    "other_items": other_out_bog,
                    "other_total": round(sum(r["amount"] for r in other_out_bog), 2),
                    "total": round(suppliers_out_bog + tax_treasury_bog + bank_fees_bog + sum(r["amount"] for r in other_out_bog), 2),
                },
                "bank_total": round(bank_out, 2),
                "cash_journal_total": round(cash_journal_out, 2),
                "cash_expenses_total": round(cash_exp_total, 2),
                "total": round(bank_out + cash_journal_out + cash_exp_total, 2),
            },
            "internal": {
                "own_bank_transfers": round(internal_transfers, 2),
                "cash_to_bank": round(cash_to_bank, 2),
            },
            "info": {
                "waybills_regular_count": len(wbs_regular),
                "waybills_regular_total": round(wb_regular_total, 2),
                "waybills_returns_count": len(wbs_returns),
                "waybills_returns_total": round(wb_returns_total, 2),
            },
            "bank_net": round(bank_in - bank_out, 2),
            "net": round((cash + card + bank_in) - (bank_out + cash_journal_out), 2),
            "total_ap_before": round(_total_ap_at(yesterday), 2),
            "total_ap_after": round(_total_ap_at(date), 2),
            "warnings": warnings_today,
        }

    logger.info(
        "daily_money_flow: computed %d days (%s → %s)",
        len(out_by_day), start_day, last_day,
    )
    return out_by_day


__all__ = ["compute_daily_money_flow"]
