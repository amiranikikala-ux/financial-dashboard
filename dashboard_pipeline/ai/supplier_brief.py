"""Phase 2.12 — Supplier Negotiation Brief builder.

Design goals
------------
* Given a supplier identifier (``tax_id`` or ``supplier_name``), resolve it
  against ``data.json`` (RS waybill ``suppliers`` + ``imported_products``
  + ``supplier_aging``) and return a self-contained brief the user can
  carry into a face-to-face negotiation.
* Surface FOUR strategic signals:
    1. Volume snapshot         — how important is this supplier to me?
    2. Payment profile         — where is my leverage vs. their cash flow?
    3. Price benchmark         — where are alternatives cheaper?
    4. Leverage score          — composite of the above with explainable
                                  component decomposition.
* Emit 2-3 ranked negotiation plays with ask / give / rationale / risk.
* Support a "portfolio mode" (no focused supplier) that returns Pareto
  concentration + annual savings estimate so the AI can answer "whom
  should I negotiate with first?".
* Stay JSON-safe: every dict/list/number/string only — no datetimes,
  pandas objects, or other non-serialisable values in the return payload.
* Relationship discipline: every play carries a ``warning_ka`` when a
  specific move could harm the long-term relationship; the LLM prompt
  will relay that verbatim.

Return contract (success, focused mode)::

    {
        "mode": "focused",
        "supplier": {
            "tax_id": "406181616",
            "resolved_name": "შპს ჯიდიაი",
            "match_confidence": "high" | "medium" | "low",
            "match_source": "tax_id_exact" | "name_fuzzy" | "name_partial",
            "ranking_among_suppliers": int,
        },
        "as_of_date": "YYYY-MM-DD",
        "volume_snapshot": {
            "total_spend_ge": float,
            "portfolio_share_pct": float,
            "waybill_count": int,
            "distinct_product_count": int,
            "distinct_month_count": int,
            "first_waybill_date": "YYYY-MM-DD" | None,
            "last_waybill_date": "YYYY-MM-DD" | None,
            "monthly_avg_ge": float,
            "tenure_months": int,
        },
        "payment_profile": {
            "total_billed_ge": float,
            "total_paid_ge": float,
            "current_debt_ge": float,
            "unpaid_share_pct": float,
            "payment_scope": str,
            "days_since_last_activity": int | None,
            "aging_bucket": str | None,
            "reliability_label": str,
            "reliability_note_ka": str,
        },
        "price_benchmark_summary": {
            "products_with_dual_source": int,
            "products_where_i_am_cheapest": int,
            "products_where_i_am_most_expensive": int,
            "estimated_annual_savings_if_switch_cheapest_ge": float,
        },
        "price_benchmark": [
            {
                "product_code": str,
                "product_name": str,
                "unit": str,
                "my_avg_unit_price_ge": float,
                "my_quantity": float,
                "my_total_spend_ge": float,
                "market_alternatives": [
                    {"supplier": str, "tax_id": str|None, "unit_price_ge": float, "quantity": float}
                ],
                "cheapest_alternative": {"supplier": str, "unit_price_ge": float} | None,
                "gap_pct_vs_cheapest": float,
                "quality_flag": "comparable" | "unit_mismatch" | "low_quantity",
            },
            ...
        ],
        "leverage_score": {
            "score": int,          # 0..100
            "label": "🟢 HIGH" | "🟡 MEDIUM" | "🟠 LOW",
            "components": [
                {"factor": str, "weight": int, "score": int, "note_ka": str},
                ...
            ],
        },
        "negotiation_plays": [
            {
                "rank": int,
                "confidence": "🟢 high" | "🟡 medium" | "🟠 use_only_if_stalled",
                "type": str,
                "ask_ka": str,
                "give_ka": str,
                "rationale_ka": str,
                "evidence_refs": [str, ...],
                "warning_ka": str | None,
            },
            ...
        ],
        "matching_warnings": [str, ...],
        "notes": [str, ...],
    }

Return contract (portfolio mode, no focused supplier)::

    {
        "mode": "portfolio",
        "as_of_date": "YYYY-MM-DD",
        "total_suppliers": int,
        "total_spend_ge": float,
        "concentration": {
            "top_5_share_pct": float,
            "top_10_share_pct": float,
            "top_20_share_pct": float,
            "hhi_index": float,              # Herfindahl–Hirschman index
            "concentration_label": str,      # "low"/"moderate"/"high"/"extreme"
        },
        "top_candidates": [
            {
                "rank": int,
                "tax_id": str,
                "supplier_name": str,
                "total_spend_ge": float,
                "portfolio_share_pct": float,
                "leverage_score": int,
                "leverage_label": str,
                "headline_play_ka": str,
                "estimated_annual_savings_ge": float,
            },
            ...
        ],
        "aggregate_savings_opportunity_ge": float,
        "notes": [str, ...],
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public contract constants
# ---------------------------------------------------------------------------

DEFAULT_LOOKBACK_MONTHS = 12
MIN_LOOKBACK_MONTHS = 1
MAX_LOOKBACK_MONTHS = 36

DEFAULT_TOP_N = 10
MIN_TOP_N = 1
MAX_TOP_N = 50

DEFAULT_BENCHMARK_N = 10
MIN_BENCHMARK_N = 1
MAX_BENCHMARK_N = 30

# Minimum quantity units required before we trust a price comparison.
# Below this, statistical noise dominates.
_MIN_QTY_FOR_BENCHMARK = 5.0

# Leverage score component weights (sum to 100).
_LEVERAGE_WEIGHTS: Dict[str, int] = {
    "portfolio_share": 30,
    "payment_leverage": 20,
    "dual_sourcing": 20,
    "tenure": 15,
    "relationship_health": 15,
}

_LEVERAGE_LABELS: List[Tuple[int, str]] = [
    (70, "🟢 HIGH"),
    (40, "🟡 MEDIUM"),
    (0, "🟠 LOW"),
]


def _label_for_leverage_score(score: int) -> str:
    for threshold, label in _LEVERAGE_LABELS:
        if score >= threshold:
            return label
    return "🟠 LOW"


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------


def _resolve_lookback_months(value: Any) -> int:
    if value is None:
        return DEFAULT_LOOKBACK_MONTHS
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LOOKBACK_MONTHS
    return max(MIN_LOOKBACK_MONTHS, min(n, MAX_LOOKBACK_MONTHS))


def _resolve_top_n(value: Any) -> int:
    if value is None:
        return DEFAULT_TOP_N
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_TOP_N
    return max(MIN_TOP_N, min(n, MAX_TOP_N))


def _resolve_benchmark_n(value: Any) -> int:
    if value is None:
        return DEFAULT_BENCHMARK_N
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_BENCHMARK_N
    return max(MIN_BENCHMARK_N, min(n, MAX_BENCHMARK_N))


# ---------------------------------------------------------------------------
# Normalization + parsing helpers
# ---------------------------------------------------------------------------

_TAX_ID_RE = re.compile(r"\b(\d{9,11})\b")
_PUNCT_RE = re.compile(r"[^\w]+", re.UNICODE)
_LEGAL_PREFIX_RE = re.compile(
    r"^(შპს|სს|ი/მ|ი\.მ|შ\.პ\.ს)\s*", re.IGNORECASE
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _safe_int(value: Any, *, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_tax_id(value: Any) -> str:
    """Pull a 9-11 digit Georgian tax id from a string. Returns "" if none."""
    text = _safe_str(value)
    if not text:
        return ""
    m = _TAX_ID_RE.search(text)
    return m.group(1) if m else ""


def _normalize_name(value: Any) -> str:
    """Georgian-aware name normalization for fuzzy supplier matching.

    1. NFC normalize + lowercase
    2. Strip legal prefix (შპს/სს/ი.მ/…)
    3. Remove tax id parenthetical
    4. Collapse non-word runs to single space
    """
    text = unicodedata.normalize("NFC", _safe_str(value)).lower()
    if not text:
        return ""
    # Drop any "(12345...)" / "123456789-დღგ" fragments.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d{9,11}[\w\-]*", " ", text)
    # Strip leading whitespace so ^შპს / ^სს / ^ი.მ anchors fire after
    # parenthetical cleanup (otherwise '( 12345 ) შპს X' leaves ' შპს X'
    # with a leading space that blocks the prefix regex).
    text = text.lstrip()
    text = _LEGAL_PREFIX_RE.sub("", text)
    text = _PUNCT_RE.sub(" ", text).strip()
    return text


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _months_between(start: Optional[date], end: Optional[date]) -> int:
    if start is None or end is None:
        return 0
    if end < start:
        return 0
    return max(
        1,
        (end.year - start.year) * 12 + (end.month - start.month) + 1,
    )


# ---------------------------------------------------------------------------
# Supplier resolution
# ---------------------------------------------------------------------------


def _index_suppliers_by_tax_id(
    suppliers: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Return {tax_id: supplier_row} dict from the top-level suppliers list."""
    index: Dict[str, Dict[str, Any]] = {}
    for row in suppliers or []:
        if not isinstance(row, dict):
            continue
        org = _safe_str(row.get("ორგანიზაცია"))
        tid = _extract_tax_id(org)
        if tid and tid not in index:
            index[tid] = row
    return index


def _index_suppliers_by_name(
    suppliers: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Return {normalized_name: supplier_row} for fuzzy name lookup."""
    index: Dict[str, Dict[str, Any]] = {}
    for row in suppliers or []:
        if not isinstance(row, dict):
            continue
        org = _safe_str(row.get("ორგანიზაცია"))
        norm = _normalize_name(org)
        if norm and norm not in index:
            index[norm] = row
    return index


def _resolve_supplier(
    suppliers: List[Dict[str, Any]],
    *,
    tax_id: Optional[str],
    supplier_name: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """Resolve a supplier row with explicit match confidence.

    Returns ``(row_or_None, match_source, match_confidence)``.

    Match precedence:
      1. ``tax_id`` exact — high confidence
      2. ``supplier_name`` exact normalized — high confidence
      3. ``supplier_name`` substring (normalized) — medium confidence
      4. ``supplier_name`` partial token overlap — low confidence
    """
    tid = _safe_str(tax_id)
    if tid:
        tid_clean = _extract_tax_id(tid) or tid
        by_tid = _index_suppliers_by_tax_id(suppliers)
        if tid_clean in by_tid:
            return by_tid[tid_clean], "tax_id_exact", "high"

    name = _safe_str(supplier_name)
    if not name:
        return None, "", ""

    normalized = _normalize_name(name)
    if not normalized:
        return None, "", ""

    by_name = _index_suppliers_by_name(suppliers)
    if normalized in by_name:
        return by_name[normalized], "name_exact", "high"

    # Substring match — our normalized query is contained in a supplier's
    # normalized name, OR vice-versa.
    candidates: List[Tuple[int, Dict[str, Any], str]] = []
    query_tokens = set(normalized.split())
    for nm, row in by_name.items():
        row_tokens = set(nm.split())
        if not row_tokens:
            continue
        if normalized in nm or nm in normalized:
            score = 2  # substring hit
        else:
            overlap = query_tokens & row_tokens
            if not overlap:
                continue
            score = 1  # partial token overlap
        # Prefer longer shared prefix; use name length as deterministic tie.
        candidates.append((score, row, nm))

    if not candidates:
        return None, "", ""

    # Best match = highest score, then shortest name (most specific).
    candidates.sort(key=lambda item: (-item[0], len(item[2])))
    best_score, best_row, _ = candidates[0]
    confidence = "medium" if best_score >= 2 else "low"
    source = "name_substring" if best_score >= 2 else "name_partial"
    return best_row, source, confidence


# ---------------------------------------------------------------------------
# Volume snapshot
# ---------------------------------------------------------------------------


def _find_imported_supplier_entry(
    imported_suppliers: List[Dict[str, Any]],
    *,
    tax_id: str,
    resolved_name: str,
) -> Optional[Dict[str, Any]]:
    """Look up a supplier inside ``imported_products.suppliers``.

    The imported-products list uses its own ``tax_id`` + ``supplier`` +
    ``normalized_supplier`` keys. We try tax_id first, then the
    normalized name.
    """
    if not isinstance(imported_suppliers, list):
        return None

    tid = _safe_str(tax_id)
    if tid:
        for row in imported_suppliers:
            if not isinstance(row, dict):
                continue
            if _safe_str(row.get("tax_id")) == tid:
                return row

    normalized_query = _normalize_name(resolved_name)
    if not normalized_query:
        return None

    for row in imported_suppliers:
        if not isinstance(row, dict):
            continue
        candidates = [
            _safe_str(row.get("normalized_supplier")),
            _normalize_name(row.get("supplier")),
        ]
        if any(c and c == normalized_query for c in candidates):
            return row

    # Fallback: substring match (expensive but bounded).
    for row in imported_suppliers:
        if not isinstance(row, dict):
            continue
        name_norm = _normalize_name(row.get("supplier"))
        if name_norm and (name_norm in normalized_query or normalized_query in name_norm):
            return row
    return None


def _build_volume_snapshot(
    supplier_row: Dict[str, Any],
    imported_entry: Optional[Dict[str, Any]],
    aging_entry: Optional[Dict[str, Any]],
    *,
    total_portfolio_ge: float,
    ranking: int,
) -> Dict[str, Any]:
    """Build the volume section from RS waybills + imported_products overlay.

    Date range resolution order:
      1. ``imported_products.suppliers[].date_range`` (most precise)
      2. ``supplier_aging[].first_waybill_date`` / ``last_waybill_date``
         (reliable fallback; populated from RS waybills even when the
         imported-products bundle has no month_keys)
    """
    total_eff = _safe_float(supplier_row.get("total_effective"))
    waybills = _safe_int(supplier_row.get("waybills_count"))

    distinct_products = 0
    distinct_months = 0
    first_dt: Optional[date] = None
    last_dt: Optional[date] = None

    if imported_entry:
        distinct_products = _safe_int(imported_entry.get("distinct_product_count"))
        distinct_months = _safe_int(imported_entry.get("distinct_month_count"))
        dr = imported_entry.get("date_range") or {}
        first_dt = _parse_iso_date(dr.get("min"))
        last_dt = _parse_iso_date(dr.get("max"))

    if (first_dt is None or last_dt is None) and aging_entry:
        # supplier_aging carries first/last waybill dates extracted from RS.
        first_dt = first_dt or _parse_iso_date(aging_entry.get("first_waybill_date"))
        last_dt = last_dt or _parse_iso_date(aging_entry.get("last_waybill_date"))

    tenure = _months_between(first_dt, last_dt)
    monthly_avg = total_eff / tenure if tenure > 0 else 0.0

    share_pct = (
        total_eff / total_portfolio_ge * 100.0
        if total_portfolio_ge > 0
        else 0.0
    )

    return {
        "total_spend_ge": round(total_eff, 2),
        "portfolio_share_pct": round(share_pct, 2),
        "waybill_count": waybills,
        "distinct_product_count": distinct_products,
        "distinct_month_count": distinct_months,
        "first_waybill_date": first_dt.isoformat() if first_dt else None,
        "last_waybill_date": last_dt.isoformat() if last_dt else None,
        "monthly_avg_ge": round(monthly_avg, 2),
        "tenure_months": tenure,
    }


# ---------------------------------------------------------------------------
# Payment profile
# ---------------------------------------------------------------------------


# Reliability labels keyed by unpaid-share bands (descending priority).
_RELIABILITY_BANDS: List[Tuple[float, str, str]] = [
    (60.0, "🔴 behind", "ვადები ძლიერ გადაცილებულია — მოლაპარაკების წინ საჭიროა ვალის დაფარვის გეგმა"),
    (30.0, "🟡 mixed", "ნაწილობრივ დავალიანებული — cash timing play შეიძლება იმუშაოს"),
    (10.0, "🟢 mostly_clean", "დიდი წილი დროულად ფარდება — ფასდაკლების ლეგიტიმური მოთხოვნა"),
    (0.0, "🟢 clean", "ფაქტობრივად ყველაფერი დროულად ფარდება"),
]


def _reliability_for_unpaid_share(unpaid_pct: float) -> Tuple[str, str]:
    for threshold, label, note in _RELIABILITY_BANDS:
        if unpaid_pct >= threshold:
            return label, note
    return _RELIABILITY_BANDS[-1][1:]


def _find_aging_entry(
    aging_rows: List[Dict[str, Any]],
    *,
    tax_id: str,
) -> Optional[Dict[str, Any]]:
    if not tax_id or not isinstance(aging_rows, list):
        return None
    for row in aging_rows:
        if isinstance(row, dict) and _safe_str(row.get("tax_id")) == tax_id:
            return row
    return None


def _build_payment_profile(
    supplier_row: Dict[str, Any],
    aging_entry: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    billed = _safe_float(supplier_row.get("total_effective"))
    paid = _safe_float(supplier_row.get("total_paid"))
    debt = _safe_float(supplier_row.get("total_debt"), default=billed - paid)

    unpaid_pct = (debt / billed * 100.0) if billed > 0 else 0.0
    unpaid_pct = max(0.0, unpaid_pct)  # Guard against negative debt from refunds.
    reliability_label, reliability_note = _reliability_for_unpaid_share(unpaid_pct)

    days_since = None
    aging_bucket = None
    if aging_entry:
        days_since = aging_entry.get("days_since_last")
        aging_bucket = aging_entry.get("aging_bucket")
        if days_since is not None:
            try:
                days_since = int(days_since)
            except (TypeError, ValueError):
                days_since = None

    return {
        "total_billed_ge": round(billed, 2),
        "total_paid_ge": round(paid, 2),
        "current_debt_ge": round(debt, 2),
        "unpaid_share_pct": round(unpaid_pct, 2),
        "payment_scope": _safe_str(supplier_row.get("payment_scope")),
        "payment_scope_note_ka": _safe_str(supplier_row.get("payment_scope_note")),
        "days_since_last_activity": days_since,
        "aging_bucket": _safe_str(aging_bucket) or None,
        "reliability_label": reliability_label,
        "reliability_note_ka": reliability_note,
    }


# ---------------------------------------------------------------------------
# Price benchmark
# ---------------------------------------------------------------------------


def _unit_price(amount_ge: float, quantity: float) -> Optional[float]:
    if quantity <= 0:
        return None
    return round(amount_ge / quantity, 4)


def _build_price_benchmark(
    products: List[Dict[str, Any]],
    *,
    focus_tax_id: str,
    focus_name_normalized: str,
    benchmark_n: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (benchmark_rows, benchmark_summary).

    A row is included when:
      * the focused supplier appears in ``top_suppliers``
      * there is at least one OTHER supplier in ``top_suppliers``

    For each matching row we compute:
      * ``my_avg_unit_price_ge`` = focused supplier's amount / qty
      * ``cheapest_alternative`` = alt supplier with lowest unit price
        (after filtering unit_mismatch + low_quantity cases)
      * ``gap_pct_vs_cheapest`` = (my_up - alt_up) / alt_up * 100
    """
    rows: List[Dict[str, Any]] = []
    cheaper_for_me = 0
    more_expensive_alt = 0
    total_savings = 0.0

    for product in products or []:
        if not isinstance(product, dict):
            continue
        top_suppliers = product.get("top_suppliers") or []
        if not isinstance(top_suppliers, list) or len(top_suppliers) < 2:
            continue

        my_entry: Optional[Dict[str, Any]] = None
        alt_entries: List[Dict[str, Any]] = []
        for entry in top_suppliers:
            if not isinstance(entry, dict):
                continue
            entry_tid = _safe_str(entry.get("tax_id"))
            entry_name_norm = _normalize_name(entry.get("supplier"))
            is_me = False
            if focus_tax_id and entry_tid == focus_tax_id:
                is_me = True
            elif focus_name_normalized and entry_name_norm == focus_name_normalized:
                is_me = True
            if is_me and my_entry is None:
                my_entry = entry
            elif not is_me:
                alt_entries.append(entry)

        if my_entry is None or not alt_entries:
            continue

        my_qty = _safe_float(my_entry.get("total_quantity"))
        my_amount = _safe_float(my_entry.get("total_amount_ge"))
        my_up = _unit_price(my_amount, my_qty)
        if my_up is None:
            continue

        quality_flag = "comparable"
        if my_qty < _MIN_QTY_FOR_BENCHMARK:
            quality_flag = "low_quantity"

        market_alts: List[Dict[str, Any]] = []
        best_alt: Optional[Dict[str, Any]] = None
        for entry in alt_entries:
            alt_qty = _safe_float(entry.get("total_quantity"))
            alt_amount = _safe_float(entry.get("total_amount_ge"))
            alt_up = _unit_price(alt_amount, alt_qty)
            if alt_up is None:
                continue
            alt_row = {
                "supplier": _safe_str(entry.get("supplier")),
                "tax_id": _safe_str(entry.get("tax_id")) or None,
                "unit_price_ge": alt_up,
                "quantity": round(alt_qty, 2),
            }
            if alt_qty < _MIN_QTY_FOR_BENCHMARK:
                alt_row["flag"] = "low_quantity"
            market_alts.append(alt_row)
            if alt_qty >= _MIN_QTY_FOR_BENCHMARK and (
                best_alt is None or alt_up < best_alt["unit_price_ge"]
            ):
                best_alt = alt_row

        if not market_alts:
            continue

        if best_alt is None:
            # All alternatives are low-quantity — still surface but flag it.
            best_alt = min(market_alts, key=lambda r: r["unit_price_ge"])
            if quality_flag == "comparable":
                quality_flag = "low_quantity"

        gap_pct = (
            (my_up - best_alt["unit_price_ge"]) / best_alt["unit_price_ge"] * 100.0
            if best_alt["unit_price_ge"] > 0
            else 0.0
        )

        if gap_pct < 0:
            cheaper_for_me += 1
        elif gap_pct > 0:
            more_expensive_alt += 1
            if quality_flag == "comparable":
                savings = my_amount * (gap_pct / 100.0)
                total_savings += max(0.0, savings)

        rows.append(
            {
                "product_code": _safe_str(product.get("product_code")),
                "product_name": _safe_str(product.get("product_name")),
                "unit": _safe_str(product.get("unit")),
                "my_avg_unit_price_ge": my_up,
                "my_quantity": round(my_qty, 2),
                "my_total_spend_ge": round(my_amount, 2),
                "market_alternatives": market_alts,
                "cheapest_alternative": {
                    "supplier": best_alt["supplier"],
                    "unit_price_ge": best_alt["unit_price_ge"],
                },
                "gap_pct_vs_cheapest": round(gap_pct, 2),
                "quality_flag": quality_flag,
            }
        )

    rows.sort(key=lambda r: r["my_total_spend_ge"], reverse=True)
    summary = {
        "products_with_dual_source": len(rows),
        "products_where_i_am_cheapest": cheaper_for_me,
        "products_where_i_am_most_expensive": more_expensive_alt,
        "estimated_annual_savings_if_switch_cheapest_ge": round(
            total_savings, 2
        ),
    }
    return rows[:benchmark_n], summary


# ---------------------------------------------------------------------------
# Leverage score
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _score_portfolio_share(share_pct: float) -> Tuple[int, str]:
    """Max score = 100% of weight when share >= 15%."""
    ratio = _clamp(share_pct / 15.0)
    note = f"{share_pct:.1f}% წილი მთლიან შესყიდვებში"
    return round(ratio * _LEVERAGE_WEIGHTS["portfolio_share"]), note


def _score_payment_leverage(unpaid_pct: float) -> Tuple[int, str]:
    """High unpaid share = high leverage (supplier wants cash).

    Saturates at 40%+ unpaid.
    """
    ratio = _clamp(unpaid_pct / 40.0)
    note = f"{unpaid_pct:.1f}% მიმდინარე დავალიანება = cash timing leverage"
    return round(ratio * _LEVERAGE_WEIGHTS["payment_leverage"]), note


def _score_dual_sourcing(
    products_with_dual: int, products_i_am_more_expensive: int
) -> Tuple[int, str]:
    """Dual-sourced SKUs give competitive leverage.

    Max score at 20+ dual-sourced where I'm more expensive on some.
    """
    if products_with_dual == 0:
        return 0, "dual-source-ი არ მოიძებნა"
    ratio = _clamp(products_with_dual / 20.0)
    mix_bonus = _clamp(products_i_am_more_expensive / max(products_with_dual, 1))
    final = ratio * (0.6 + 0.4 * mix_bonus)
    note = (
        f"{products_with_dual} dual-source პროდუქტი, "
        f"{products_i_am_more_expensive}-ზე ალტ უფრო იაფია"
    )
    return round(final * _LEVERAGE_WEIGHTS["dual_sourcing"]), note


def _score_tenure(tenure_months: int) -> Tuple[int, str]:
    """Long tenure = more credibility in negotiation.

    Saturates at 18 months.
    """
    ratio = _clamp(tenure_months / 18.0)
    note = f"{tenure_months} თვე ისტორიაში"
    return round(ratio * _LEVERAGE_WEIGHTS["tenure"]), note


def _score_relationship_health(days_since: Optional[int]) -> Tuple[int, str]:
    """Recent activity = healthy relationship.

    <=7d = full weight; >90d = zero.
    """
    if days_since is None:
        return 0, "ბოლო აქტივობის თარიღი უცნობია"
    if days_since <= 7:
        ratio = 1.0
    elif days_since >= 90:
        ratio = 0.0
    else:
        ratio = _clamp(1.0 - (days_since - 7) / (90.0 - 7.0))
    note = f"ბოლო აქტივობა {days_since} დღის წინ"
    return round(ratio * _LEVERAGE_WEIGHTS["relationship_health"]), note


def _build_leverage_score(
    volume: Dict[str, Any],
    payment: Dict[str, Any],
    benchmark_summary: Dict[str, Any],
) -> Dict[str, Any]:
    components: List[Dict[str, Any]] = []
    total = 0
    for factor, weight in _LEVERAGE_WEIGHTS.items():
        if factor == "portfolio_share":
            pts, note = _score_portfolio_share(
                float(volume.get("portfolio_share_pct") or 0)
            )
        elif factor == "payment_leverage":
            pts, note = _score_payment_leverage(
                float(payment.get("unpaid_share_pct") or 0)
            )
        elif factor == "dual_sourcing":
            pts, note = _score_dual_sourcing(
                int(benchmark_summary.get("products_with_dual_source") or 0),
                int(benchmark_summary.get("products_where_i_am_most_expensive") or 0),
            )
        elif factor == "tenure":
            pts, note = _score_tenure(int(volume.get("tenure_months") or 0))
        elif factor == "relationship_health":
            pts, note = _score_relationship_health(
                payment.get("days_since_last_activity")
            )
        else:  # pragma: no cover — defensive
            pts, note = 0, ""
        pts = max(0, min(pts, weight))
        total += pts
        components.append(
            {
                "factor": factor,
                "weight": weight,
                "score": pts,
                "note_ka": note,
            }
        )
    return {
        "score": total,
        "label": _label_for_leverage_score(total),
        "components": components,
    }


# ---------------------------------------------------------------------------
# Negotiation plays
# ---------------------------------------------------------------------------


def _build_negotiation_plays(
    volume: Dict[str, Any],
    payment: Dict[str, Any],
    benchmark_summary: Dict[str, Any],
    benchmark_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Generate 2-3 ranked plays tailored to leverage signals."""
    plays: List[Dict[str, Any]] = []

    current_debt = float(payment.get("current_debt_ge") or 0)
    unpaid_pct = float(payment.get("unpaid_share_pct") or 0)
    monthly_avg = float(volume.get("monthly_avg_ge") or 0)
    share_pct = float(volume.get("portfolio_share_pct") or 0)
    dual_count = int(benchmark_summary.get("products_with_dual_source") or 0)
    more_expensive = int(benchmark_summary.get("products_where_i_am_most_expensive") or 0)
    savings = float(benchmark_summary.get("estimated_annual_savings_if_switch_cheapest_ge") or 0)

    # Play 1: cash discount for payment speed (strong when unpaid_pct >= 10)
    if current_debt > 0 and unpaid_pct >= 10:
        ask_pct = 4 if unpaid_pct < 30 else 6
        plays.append(
            {
                "rank": len(plays) + 1,
                "confidence": "🟢 high",
                "type": "cash_discount_for_payment_speed",
                "ask_ka": f"{ask_pct}% ფასდაკლება მომდევნო 3 თვის შესყიდვაზე",
                "give_ka": f"{current_debt:,.0f} ₾ დავალიანება 15 დღეში დაფარდება",
                "rationale_ka": (
                    f"მომწოდებელს cash flow problem უფრო ძვირი უჯდება ვიდრე "
                    f"{ask_pct}% margin-ის დათმობა. "
                    f"კონკრეტული deadline + explicit amount."
                ),
                "evidence_refs": [
                    "payment_profile.current_debt_ge",
                    "payment_profile.unpaid_share_pct",
                ],
                "warning_ka": None,
            }
        )

    # Play 2: volume commitment (strong when share >= 3% and monthly_avg >= 20K)
    if share_pct >= 3 and monthly_avg >= 20000:
        commit = round(monthly_avg * 3 / 1000) * 1000  # round to 1K
        plays.append(
            {
                "rank": len(plays) + 1,
                "confidence": "🟡 medium",
                "type": "volume_commitment_discount",
                "ask_ka": "3% volume discount + ფასდაფიქსირება მომდევნო კვარტალზე",
                "give_ka": f"{commit:,.0f} ₾ blanket order commitment 3 თვეში",
                "rationale_ka": (
                    "Predictable volume = მომწოდებლის planning benefit. "
                    "ცნობილი cashflow მათაც სჭირდებათ."
                ),
                "evidence_refs": [
                    "volume_snapshot.monthly_avg_ge",
                    "volume_snapshot.portfolio_share_pct",
                ],
                "warning_ka": None,
            }
        )

    # Play 3: dual-source leverage (only when we actually have competitive signal)
    if dual_count >= 1 and more_expensive >= 1:
        confidence = "🟠 use_only_if_stalled"
        top_product = None
        for row in benchmark_rows:
            if row.get("gap_pct_vs_cheapest", 0) > 0 and row.get("quality_flag") == "comparable":
                top_product = row
                break
        if top_product:
            alt_name = (top_product.get("cheapest_alternative") or {}).get(
                "supplier", "ალტერნატიული მომწოდებელი"
            )
            plays.append(
                {
                    "rank": len(plays) + 1,
                    "confidence": confidence,
                    "type": "dual_source_leverage",
                    "ask_ka": "ფასების გათანაბრება ალტერნატიულ მომწოდებელთან",
                    "give_ka": "volume-ის 60%+ აქ ვტოვებ",
                    "rationale_ka": (
                        f"{more_expensive} პროდუქტზე ალტ supplier უფრო იაფია "
                        f"(მაგ: {top_product.get('product_name', '')[:40]} — "
                        f"{alt_name}). სავარაუდო წლიური დაზოგვა: "
                        f"{savings:,.0f} ₾."
                    ),
                    "evidence_refs": [
                        "price_benchmark_summary.products_where_i_am_most_expensive",
                        "price_benchmark_summary.estimated_annual_savings_if_switch_cheapest_ge",
                        "price_benchmark[0]",
                    ],
                    "warning_ka": (
                        "Last-resort. Relationship-ი სასიცოცხლოა — ეს ref-ი "
                        "მხოლოდ მაშინ გამოიყენე, როცა 1-ლი და 2-ლი play-ები "
                        "უარყვეს."
                    ),
                }
            )

    # Renumber ranks after filters
    for i, p in enumerate(plays, start=1):
        p["rank"] = i
    return plays


# ---------------------------------------------------------------------------
# Portfolio-mode
# ---------------------------------------------------------------------------


def _hhi_index(shares_pct: List[float]) -> float:
    """Herfindahl-Hirschman Index on share-percent values."""
    return round(sum((s) ** 2 for s in shares_pct), 2)


_HHI_LABELS: List[Tuple[float, str]] = [
    (2500.0, "extreme"),
    (1500.0, "high"),
    (500.0, "moderate"),
    (0.0, "low"),
]


def _hhi_label(hhi: float) -> str:
    for threshold, label in _HHI_LABELS:
        if hhi >= threshold:
            return label
    return "low"


def _build_portfolio_report(
    suppliers: List[Dict[str, Any]],
    imported_block: Dict[str, Any],
    aging_rows: List[Dict[str, Any]],
    *,
    top_n: int,
    today: date,
) -> Dict[str, Any]:
    """Pareto concentration + top-N candidates ranked by leverage."""
    total_portfolio = sum(
        _safe_float(s.get("total_effective")) for s in suppliers or []
    )

    ranked = sorted(
        [s for s in suppliers or [] if isinstance(s, dict)],
        key=lambda s: _safe_float(s.get("total_effective")),
        reverse=True,
    )

    def _share(n: int) -> float:
        if total_portfolio <= 0:
            return 0.0
        slab = sum(_safe_float(s.get("total_effective")) for s in ranked[:n])
        return round(slab / total_portfolio * 100.0, 2)

    shares = [
        _safe_float(s.get("total_effective")) / total_portfolio * 100.0
        for s in ranked
        if total_portfolio > 0
    ]
    hhi = _hhi_index(shares)

    imported_suppliers = imported_block.get("suppliers") or []
    products = imported_block.get("products") or []

    top_candidates: List[Dict[str, Any]] = []
    aggregate_savings = 0.0

    for idx, row in enumerate(ranked[: top_n * 2]):  # over-sample, then rank
        org = _safe_str(row.get("ორგანიზაცია"))
        tid = _extract_tax_id(org)
        imported_entry = _find_imported_supplier_entry(
            imported_suppliers, tax_id=tid, resolved_name=org
        )
        aging_entry = _find_aging_entry(aging_rows, tax_id=tid)
        volume = _build_volume_snapshot(
            row,
            imported_entry,
            aging_entry,
            total_portfolio_ge=total_portfolio,
            ranking=idx + 1,
        )
        payment = _build_payment_profile(row, aging_entry)
        benchmark_rows, benchmark_summary = _build_price_benchmark(
            products,
            focus_tax_id=tid,
            focus_name_normalized=_normalize_name(org),
            benchmark_n=3,
        )
        leverage = _build_leverage_score(volume, payment, benchmark_summary)
        plays = _build_negotiation_plays(
            volume, payment, benchmark_summary, benchmark_rows
        )
        headline = plays[0]["ask_ka"] if plays else "არცერთი დეტალური play-ი ვერ შემუშავდა"

        savings = float(
            benchmark_summary.get("estimated_annual_savings_if_switch_cheapest_ge") or 0
        )
        aggregate_savings += savings

        top_candidates.append(
            {
                "rank": idx + 1,
                "tax_id": tid or None,
                "supplier_name": _clean_display_name(org),
                "total_spend_ge": round(
                    _safe_float(row.get("total_effective")), 2
                ),
                "portfolio_share_pct": volume["portfolio_share_pct"],
                "leverage_score": leverage["score"],
                "leverage_label": leverage["label"],
                "headline_play_ka": headline,
                "estimated_annual_savings_ge": round(savings, 2),
            }
        )

    # Re-rank by leverage*savings (practical "who to call first" order).
    top_candidates.sort(
        key=lambda c: (
            -int(c["leverage_score"]),
            -float(c["estimated_annual_savings_ge"]),
            -float(c["total_spend_ge"]),
        ),
    )
    for i, c in enumerate(top_candidates[:top_n], start=1):
        c["rank"] = i

    trimmed_candidates = top_candidates[:top_n]
    total_supplier_count = len(
        [s for s in suppliers or [] if isinstance(s, dict)]
    )
    payload: Dict[str, Any] = {
        "mode": "portfolio",
        "as_of_date": today.isoformat(),
        "total_suppliers": total_supplier_count,
        "total_spend_ge": round(total_portfolio, 2),
        "concentration": {
            "top_5_share_pct": _share(5),
            "top_10_share_pct": _share(10),
            "top_20_share_pct": _share(20),
            "hhi_index": hhi,
            "concentration_label": _hhi_label(hhi),
        },
        "top_candidates": trimmed_candidates,
        "aggregate_savings_opportunity_ge": round(aggregate_savings, 2),
        "notes": [
            "Portfolio ranking ითვლება leverage_score × savings-ის მიხედვით (არა ცარიელი spend).",
            "თითო მომწოდებელზე focused brief-ისთვის გადააპროცესიე `prepare_supplier_brief(supplier_name=...)` ან `tax_id=...`.",
        ],
    }
    payload["summary_ka"] = _render_portfolio_summary_ka(payload)
    return payload


def _clean_display_name(org_string: str) -> str:
    """Strip the '(123456789-დღგ)' prefix from RS organization strings."""
    text = _safe_str(org_string)
    if not text:
        return ""
    text = re.sub(r"\(\s*\d{9,11}[\w\-]*\s*\)\s*", "", text)
    return text.strip(" -\u2013,")


def _render_focused_summary_ka(payload: Dict[str, Any]) -> str:
    """One-sentence Georgian summary of a focused supplier brief.

    Surface order: supplier name, leverage score/label, #1 play, warning
    marker when match_confidence is not ``high``. Truncates the first
    play to stay one-line — the full text lives in
    ``negotiation_plays[0].ask_ka``.
    """
    supplier = payload.get("supplier") or {}
    name = str(supplier.get("resolved_name") or "").strip() or "მომწოდებელი"
    confidence = str(supplier.get("match_confidence") or "").strip()
    leverage = payload.get("leverage_score") or {}
    score = leverage.get("score")
    label = str(leverage.get("label") or "").strip()

    plays = payload.get("negotiation_plays") or []
    first_ask = ""
    if isinstance(plays, list) and plays:
        first_ask = str(plays[0].get("ask_ka") or "").strip()
    if len(first_ask) > 70:
        first_ask = first_ask[:67].rstrip() + "…"

    prefix = "⚠️ " if confidence in ("medium", "low") else ""
    parts: List[str] = [f"{prefix}**{name}**"]
    if isinstance(score, (int, float)):
        lev_chunk = f"leverage **{int(score)}/100**"
        if label:
            lev_chunk += f" ({label})"
        parts.append(lev_chunk)
    if first_ask:
        parts.append(f"#1 play: *{first_ask}*")
    elif not plays:
        parts.append("play-ი ვერ შემუშავდა")
    if confidence in ("medium", "low"):
        parts.append(f"match: {confidence} — დააზუსტე")
    return " · ".join(parts)


def _render_portfolio_summary_ka(payload: Dict[str, Any]) -> str:
    """One-sentence Georgian summary of a portfolio supplier brief.

    Surface order: total supplier count + spend, concentration label,
    first call + leverage, full-portfolio savings opportunity.
    """
    total_suppliers = payload.get("total_suppliers") or 0
    total_spend = payload.get("total_spend_ge") or 0.0
    concentration = payload.get("concentration") or {}
    top_5 = concentration.get("top_5_share_pct")
    conc_label = str(concentration.get("concentration_label") or "").strip()
    candidates = payload.get("top_candidates") or []
    savings = payload.get("aggregate_savings_opportunity_ge") or 0.0

    parts: List[str] = [
        f"**{int(total_suppliers)} მომწოდებელი**, "
        f"სულ {float(total_spend):,.2f} ₾"
    ]
    if isinstance(top_5, (int, float)):
        conc_chunk = f"top-5 {top_5:g}%"
        if conc_label:
            conc_chunk += f" ({conc_label})"
        parts.append(conc_chunk)

    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        first_name = str(first.get("supplier_name") or "").strip() or "?"
        first_lev = first.get("leverage_score")
        if isinstance(first_lev, (int, float)):
            parts.append(
                f"#1 call: **{first_name}** (leverage {int(first_lev)})"
            )
        else:
            parts.append(f"#1 call: **{first_name}**")

    if isinstance(savings, (int, float)) and savings > 0:
        parts.append(
            f"portfolio savings: **{float(savings):,.2f} ₾/წელი**"
        )

    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def prepare_supplier_brief(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    supplier_name: Any = None,
    tax_id: Any = None,
    lookback_months: Any = None,
    top_n: Any = None,
    benchmark_n: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Build a negotiation brief for a single supplier (or portfolio report).

    Parameters
    ----------
    data_loader:
        Zero-argument callable returning the parsed ``data.json`` dict.
    supplier_name:
        Supplier display name (fuzzy match against ``ორგანიზაცია``).
    tax_id:
        Exact 9-11 digit Georgian tax id. Takes precedence over
        ``supplier_name`` when both are supplied.
    lookback_months:
        How many months back to consider (default 12, range 1..36). Clamped.
    top_n:
        Max candidates in portfolio mode (default 10, range 1..50).
    benchmark_n:
        Max rows in ``price_benchmark`` (default 10, range 1..30).
    today:
        Override "today" for deterministic tests. Defaults to
        :func:`date.today`.
    """

    # --- Argument coercion ------------------------------------------------
    months = _resolve_lookback_months(lookback_months)
    n_top = _resolve_top_n(top_n)
    n_benchmark = _resolve_benchmark_n(benchmark_n)

    if today is None:
        today = date.today()
    if not isinstance(today, date):
        return {
            "error": "today პარამეტრი უნდა იყოს date ობიექტი ან None",
            "hint": "ჩვეულებრივ ეს არ გადაეცემა — defaults to date.today().",
        }

    # --- Load data -------------------------------------------------------
    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("supplier_brief data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა",
            "hint": "გადაამოწმე generate_dashboard_data.py pipeline.",
        }

    suppliers = data.get("suppliers") or []
    imported_block = data.get("imported_products") or {}
    aging_rows = data.get("supplier_aging") or []

    if not isinstance(suppliers, list) or not suppliers:
        return {
            "error": (
                "suppliers ცარიელია ან არ არის ჩატვირთული — brief ვერ აეწყო."
            ),
            "hint": "გადაუშვი generate_dashboard_data.py და გადაამოწმე RS waybill files.",
        }

    has_focus = bool(_safe_str(tax_id) or _safe_str(supplier_name))

    # --- Portfolio mode --------------------------------------------------
    if not has_focus:
        return _build_portfolio_report(
            suppliers,
            imported_block,
            aging_rows,
            top_n=n_top,
            today=today,
        )

    # --- Focused mode ----------------------------------------------------
    supplier_row, match_source, match_confidence = _resolve_supplier(
        suppliers, tax_id=_safe_str(tax_id), supplier_name=_safe_str(supplier_name)
    )

    if supplier_row is None:
        return {
            "error": (
                f"მომწოდებელი ვერ ვიპოვე — tax_id={tax_id!r}, "
                f"name={supplier_name!r}. გადაამოწმე სწორი მართლწერა / ტექსტი."
            ),
            "hint": (
                "დაამატე ზუსტი საგადასახადო ნომერი (9-11 ციფრი), ან "
                "გადააპროცესიე `prepare_supplier_brief()` supplier_name/tax_id "
                "პარამეტრების გარეშე portfolio-wide-ი სანახავად."
            ),
        }

    org = _safe_str(supplier_row.get("ორგანიზაცია"))
    resolved_tid = _extract_tax_id(org)
    total_portfolio = sum(
        _safe_float(s.get("total_effective")) for s in suppliers
    )
    ranking = 1
    sorted_suppliers = sorted(
        [s for s in suppliers if isinstance(s, dict)],
        key=lambda s: _safe_float(s.get("total_effective")),
        reverse=True,
    )
    for idx, row in enumerate(sorted_suppliers, start=1):
        if row is supplier_row:
            ranking = idx
            break

    imported_entry = _find_imported_supplier_entry(
        imported_block.get("suppliers") or [],
        tax_id=resolved_tid,
        resolved_name=org,
    )
    aging_entry = _find_aging_entry(aging_rows, tax_id=resolved_tid)
    volume = _build_volume_snapshot(
        supplier_row,
        imported_entry,
        aging_entry,
        total_portfolio_ge=total_portfolio,
        ranking=ranking,
    )

    payment = _build_payment_profile(supplier_row, aging_entry)

    benchmark_rows, benchmark_summary = _build_price_benchmark(
        imported_block.get("products") or [],
        focus_tax_id=resolved_tid,
        focus_name_normalized=_normalize_name(org),
        benchmark_n=n_benchmark,
    )

    leverage = _build_leverage_score(volume, payment, benchmark_summary)
    plays = _build_negotiation_plays(
        volume, payment, benchmark_summary, benchmark_rows
    )

    # --- Warnings + notes ------------------------------------------------
    matching_warnings: List[str] = []
    if match_confidence in ("medium", "low"):
        matching_warnings.append(
            f"მომწოდებლის იდენტიფიცირება '{match_confidence}' ნდობით — "
            "მოითხოვე user-ის დადასტურება ვიდრე brief-ის ციფრებს გაიმეორებ."
        )
    if imported_entry is None:
        matching_warnings.append(
            "ამ მომწოდებელს imported_products.suppliers-ში ვერ დავამთხვიე — "
            "volume snapshot იმ ბიჯს არ მოიცავს (waybill_count + total_spend "
            "იმუშავებს, პროდუქტების სიღრმე კი არა)."
        )

    notes: List[str] = [
        "ციფრები ფაქტობრივ data.json-ზეა (suppliers + imported_products + supplier_aging).",
        f"Lookback window: {months} თვე.",
    ]
    if match_confidence != "high":
        notes.append(
            "Match confidence != high → უპირველესად დააზუსტე მომწოდებელი user-თან."
        )
    if plays:
        notes.append(
            "Relationship-ი აქ ყოველთვის > margin. #3 play-ი 'last-resort' — "
            "არ გამოიყენო სანამ #1 და #2 არ უარყვეს."
        )
    else:
        notes.append(
            "არცერთი play-ი ვერ შემუშავდა (volume/payment/dual-source signals "
            "სუსტია). Advanced context-ისთვის `analyze_dead_stock` ან "
            "`forecast_revenue` გამოიყენე."
        )

    payload: Dict[str, Any] = {
        "mode": "focused",
        "supplier": {
            "tax_id": resolved_tid or None,
            "resolved_name": _clean_display_name(org),
            "raw_org_string": org,
            "match_confidence": match_confidence,
            "match_source": match_source,
            "ranking_among_suppliers": ranking,
        },
        "as_of_date": today.isoformat(),
        "lookback_months": months,
        "volume_snapshot": volume,
        "payment_profile": payment,
        "price_benchmark_summary": benchmark_summary,
        "price_benchmark": benchmark_rows,
        "leverage_score": leverage,
        "negotiation_plays": plays,
        "matching_warnings": matching_warnings,
        "notes": notes,
    }
    payload["summary_ka"] = _render_focused_summary_ka(payload)
    return payload
