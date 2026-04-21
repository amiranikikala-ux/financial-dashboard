"""Phase 2.11 — Dead Stock + Salvage Plan analyzer.

Design goals
------------
* Triangulate ``imported_products`` (inventory inflow) and ``retail_sales``
  (sell-through) on product_code → barcode → normalized name and split SKUs
  into stale buckets (active / 91-180d / 181-365d / 365+d / unmatched).
* Recommend a salvage action per bucket (discount_15 / discount_30 /
  supplier_return / write_off) using a transparent rule table — no opaque ML.
* Emit a stable, JSON-safe contract that the AI tool dispatcher can hand
  straight to a tool_result block.
* Surface the well-known matching warning explicitly: when a meaningful
  share of ``imported_products`` SKUs have no retail_sales match (typically
  due to barcode/code drift), the frozen-cash estimate is an upper bound,
  NOT a precise diagnosis. The LLM must repeat that caveat to the user.
* No mutations: this is a diagnostic + recommendation tool. Discounts,
  returns, and write-offs are performed by the user, not the agent.

Return contract (success)::

    {
        "as_of_date": "YYYY-MM-DD",
        "days_threshold": int,
        "store_filter": "ჯამი" | "ოზურგეთი" | "დვაბზუ",
        "summary": {
            "imported_total_count": int,
            "imported_total_amount": float,
            "matched_count": int,
            "matched_total_amount": float,
            "unmatched_count": int,
            "unmatched_total_amount": float,
            "active_within_threshold_count": int,
            "stale_91_180d_count": int,
            "stale_181_365d_count": int,
            "dead_365d_plus_count": int,
            "frozen_cash_estimate": float,
            "matching_warning": str | None,
        },
        "by_action": {
            "discount_15_pct":  {"sku_count": int, "freed_cash_estimate": float},
            "discount_30_pct":  {"sku_count": int, "freed_cash_estimate": float},
            "supplier_return":  {"sku_count": int, "freed_cash_estimate": float},
            "write_off":        {"sku_count": int, "freed_cash_estimate": float},
        },
        "top_stale_skus": [
            {
                "product_code": str,
                "product_name": str,
                "imported_amount": float,
                "imported_quantity": float,
                "last_sold_date": "YYYY-MM-DD" | None,
                "days_since_last_sale": int | None,
                "stale_bucket": "active"|"stale_91_180d"|"stale_181_365d"|"dead_365d_plus"|"unmatched",
                "top_supplier": str,
                "matched": bool,
                "match_method": "code"|"barcode"|"name"|None,
                "recommended_action": "discount_15_pct"|"discount_30_pct"|"supplier_return"|"write_off",
                "expected_freed_cash": float,
            },
            ...
        ],
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

DEFAULT_DAYS_THRESHOLD = 90
MIN_DAYS_THRESHOLD = 30
MAX_DAYS_THRESHOLD = 730  # ~2 years; beyond that the analysis is degenerate

DEFAULT_TOP_N = 20
MIN_TOP_N = 1
MAX_TOP_N = 100

# Bucket keys returned in the contract.
BUCKET_ACTIVE = "active"
BUCKET_91_180 = "stale_91_180d"
BUCKET_181_365 = "stale_181_365d"
BUCKET_365_PLUS = "dead_365d_plus"
BUCKET_UNMATCHED = "unmatched"

# Action keys returned in the contract. Stable enum so prompts and tests can
# pin literal strings.
ACTION_DISCOUNT_15 = "discount_15_pct"
ACTION_DISCOUNT_30 = "discount_30_pct"
ACTION_SUPPLIER_RETURN = "supplier_return"
ACTION_WRITE_OFF = "write_off"
ALL_ACTIONS: Tuple[str, ...] = (
    ACTION_DISCOUNT_15,
    ACTION_DISCOUNT_30,
    ACTION_SUPPLIER_RETURN,
    ACTION_WRITE_OFF,
)

# Fraction of ``imported_amount`` that we expect to recover under each action.
# These are heuristics used as a first-cut estimate; the prompt instructs the
# AI to surface them as "🟡 ვარაუდი" (assumption), not "🟢 ფაქტი".
_FREED_CASH_FACTOR: Dict[str, float] = {
    ACTION_DISCOUNT_15: 0.85,    # 15% off retail → ~85% of original COGS recovered
    ACTION_DISCOUNT_30: 0.70,    # 30% off → ~70% recovered
    ACTION_SUPPLIER_RETURN: 1.00,  # contractual full return — best case
    ACTION_WRITE_OFF: 0.00,      # no cash recovery; opportunity cost only
}

# When a meaningful share of imported SKUs go unmatched, surface this
# warning so the LLM passes it to the user verbatim. Tuned to 30% based on
# the 2026-04-20 baseline probe (74% unmatched on real data — barcode drift).
_UNMATCHED_WARN_THRESHOLD_PCT = 30.0

#: Store enum mirrors :mod:`dashboard_pipeline.ai.forecasting`.
STORE_TOTAL = "total"
STORE_OZURGETI = "ოზურგეთი"
STORE_DVABZU = "დვაბზუ"
SUPPORTED_STORES: Tuple[str, ...] = (STORE_TOTAL, STORE_OZURGETI, STORE_DVABZU)

#: Friendly store aliases — same as forecasting._STORE_ALIASES so the LLM
#: can use either Georgian or transliterated names interchangeably.
_STORE_ALIASES: Dict[str, str] = {
    "total": STORE_TOTAL,
    "all": STORE_TOTAL,
    "ჯამი": STORE_TOTAL,
    "ყველა": STORE_TOTAL,
    "ozurgeti": STORE_OZURGETI,
    "ozurgheti": STORE_OZURGETI,
    "ოზურგეთი": STORE_OZURGETI,
    "dvabzu": STORE_DVABZU,
    "დვაბზუ": STORE_DVABZU,
}


# ---------------------------------------------------------------------------
# Argument coercion / validation
# ---------------------------------------------------------------------------


def _resolve_days_threshold(value: Any) -> int:
    if value is None:
        return DEFAULT_DAYS_THRESHOLD
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DAYS_THRESHOLD
    return max(MIN_DAYS_THRESHOLD, min(n, MAX_DAYS_THRESHOLD))


def _resolve_top_n(value: Any) -> int:
    if value is None:
        return DEFAULT_TOP_N
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_TOP_N
    return max(MIN_TOP_N, min(n, MAX_TOP_N))


def _resolve_store(value: Any) -> Optional[str]:
    """Return canonical store name or ``None`` for invalid input.

    Empty / whitespace / missing → ``"total"``. Unknown store strings
    return ``None`` so callers can emit a Georgian error.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return STORE_TOTAL
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    return _STORE_ALIASES.get(key)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

# Punctuation/whitespace collapse — used for fuzzy product-name matching.
_PUNCT_RE = re.compile(r"[^\w]+", re.UNICODE)


def _normalize_code(value: Any) -> str:
    """Return ``str(value).strip()`` with surrounding whitespace removed.

    Codes are case-sensitive identifiers (barcodes are usually all-digit but
    SKU codes can contain uppercase letters), so we don't lowercase them.
    """
    if value is None:
        return ""
    return str(value).strip()


def _normalize_name(value: Any) -> str:
    """Lowercase, NFC-normalize, strip punctuation/whitespace runs.

    Used for the tertiary fuzzy-name match. Handles Georgian + Latin +
    digits + quotation marks. Empty input returns "".
    """
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value)).lower()
    return _PUNCT_RE.sub(" ", text).strip()


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf guard
        return default
    return f


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
    # Accept "YYYY-MM-DD" or full ISO timestamp; only the date prefix matters.
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Sales-side index (retail_sales → match key dicts)
# ---------------------------------------------------------------------------


def _build_sales_index(
    sales_rows: List[Dict[str, Any]],
    *,
    store_filter: Optional[str] = None,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Build code/barcode/name lookup dicts from retail_sales.by_product.

    When ``store_filter`` is "ოზურგეთი" or "დვაბზუ" (not "total"), only rows
    whose ``object_breakdown`` mentions that store survive — this lets the
    "matched" verdict reflect store-level sell-through, not company-wide.

    The three dicts are tried in order (code → barcode → name) by the
    matcher. If the same key appears twice we keep the first row (sales
    list is sorted by revenue/profit upstream so the first match is the
    most representative).
    """
    by_code: Dict[str, Dict[str, Any]] = {}
    by_barcode: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}

    for row in sales_rows or []:
        if not isinstance(row, dict):
            continue
        if store_filter and store_filter != STORE_TOTAL:
            objects = row.get("object_breakdown") or []
            store_match = any(
                isinstance(o, dict) and o.get("object") == store_filter
                for o in objects
            )
            if not store_match:
                continue

        code = _normalize_code(row.get("product_code"))
        if code and code not in by_code:
            by_code[code] = row
        barcode = _normalize_code(row.get("barcode"))
        if barcode and barcode not in by_barcode:
            by_barcode[barcode] = row
        name = _normalize_name(row.get("product_name"))
        if name and name not in by_name:
            by_name[name] = row

    return {"code": by_code, "barcode": by_barcode, "name": by_name}


def _match_imported_to_sales(
    imported_row: Dict[str, Any],
    index: Dict[str, Dict[str, Dict[str, Any]]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve an imported row against the sales index.

    Returns ``(sales_row_or_None, match_method_or_None)``. Match priority:
    1. ``product_code`` exact (after strip)
    2. ``barcode`` exact (imported sometimes stores barcode in product_code)
    3. Normalized ``product_name`` (lowercased, punctuation collapsed)
    """
    code = _normalize_code(imported_row.get("product_code"))
    if code and code in index["code"]:
        return index["code"][code], "code"
    # Imported "code" is sometimes actually the barcode.
    if code and code in index["barcode"]:
        return index["barcode"][code], "barcode"
    # And sometimes the imported barcode field carries the code.
    barcode = _normalize_code(imported_row.get("barcode"))
    if barcode:
        if barcode in index["code"]:
            return index["code"][barcode], "code"
        if barcode in index["barcode"]:
            return index["barcode"][barcode], "barcode"

    name = _normalize_name(imported_row.get("product_name"))
    if name and name in index["name"]:
        return index["name"][name], "name"
    return None, None


# ---------------------------------------------------------------------------
# Bucket + action classification
# ---------------------------------------------------------------------------


def _bucket_for(days_since_last_sale: Optional[int], threshold: int) -> str:
    """Map ``days_since_last_sale`` to a bucket key.

    ``None`` → ``BUCKET_UNMATCHED``. ``<= threshold`` → ``BUCKET_ACTIVE``.
    The 91/181/365 boundaries are independent of ``threshold`` so users
    can tighten the active/stale boundary without rewriting the discount
    schedule.
    """
    if days_since_last_sale is None:
        return BUCKET_UNMATCHED
    if days_since_last_sale <= threshold:
        return BUCKET_ACTIVE
    if days_since_last_sale <= 180:
        return BUCKET_91_180
    if days_since_last_sale <= 365:
        return BUCKET_181_365
    return BUCKET_365_PLUS


def _recommend_action(
    bucket: str,
    *,
    distinct_supplier_count: int,
    gross_margin_pct: float,
) -> str:
    """Choose a salvage action based on bucket + supplier exclusivity + margin.

    The rules are deliberately simple — the prompt tells the AI that this
    is a first-cut suggestion, not a hard recommendation:

    * ``stale_91_180d`` → 15% discount (margin still cushions a small cut)
    * ``stale_181_365d`` → 30% discount (deeper cut needed to move volume)
    * ``dead_365d_plus`` with single supplier → supplier_return (contract)
    * ``dead_365d_plus`` otherwise → write_off
    * ``unmatched`` → write_off candidate (with a flag the LLM should
      surface — these are usually false positives from barcode drift)
    * ``active`` → no action; treated as keep-stock

    Margin gate: if ``gross_margin_pct < 5%`` we still recommend the
    discount action — the LLM is expected to flag it as "marginal" so the
    user can decide whether to accept the loss.
    """
    if bucket == BUCKET_91_180:
        return ACTION_DISCOUNT_15
    if bucket == BUCKET_181_365:
        return ACTION_DISCOUNT_30
    if bucket == BUCKET_365_PLUS:
        if distinct_supplier_count == 1:
            return ACTION_SUPPLIER_RETURN
        return ACTION_WRITE_OFF
    if bucket == BUCKET_UNMATCHED:
        return ACTION_WRITE_OFF
    # active — no action; we still pick discount_15 as a placeholder so the
    # contract doesn't have to handle None, but this row is filtered out
    # of by_action aggregation upstream.
    return ACTION_DISCOUNT_15


def _expected_freed_cash(action: str, imported_amount: float) -> float:
    factor = _FREED_CASH_FACTOR.get(action, 0.0)
    return round(imported_amount * factor, 2)


# ---------------------------------------------------------------------------
# Top-supplier helper
# ---------------------------------------------------------------------------


def _top_supplier_name(imported_row: Dict[str, Any]) -> str:
    suppliers = imported_row.get("top_suppliers") or []
    if not isinstance(suppliers, list):
        return ""
    for s in suppliers:
        if isinstance(s, dict):
            name = s.get("supplier") or ""
            if name:
                return str(name)
    return ""


def _distinct_supplier_count(imported_row: Dict[str, Any]) -> int:
    n = imported_row.get("distinct_supplier_count")
    if isinstance(n, (int, float)) and n > 0:
        return int(n)
    suppliers = imported_row.get("top_suppliers") or []
    if isinstance(suppliers, list):
        return sum(1 for s in suppliers if isinstance(s, dict))
    return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def analyze_dead_stock(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    days_threshold: Any = None,
    store: Any = None,
    top_n: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Triangulate imported_products + retail_sales for dead-stock signals.

    Parameters
    ----------
    data_loader:
        Zero-argument callable returning the parsed ``data.json`` dict.
        The same loader pattern used by every other tool in
        :mod:`dashboard_pipeline.ai.tools`.
    days_threshold:
        Days-since-last-sale boundary that splits the "active" bucket from
        the stale buckets. Default 90, range 30..730.
    store:
        Optional store filter — ``"total"`` / ``"ოზურგეთი"`` / ``"დვაბზუ"``
        plus Latin aliases (see :data:`_STORE_ALIASES`).
    top_n:
        Maximum number of stale SKUs returned in ``top_stale_skus``.
        Default 20, range 1..100.
    today:
        Override "today" for deterministic tests. Defaults to
        :func:`date.today`.
    """

    # --- Argument validation ----------------------------------------------
    threshold = _resolve_days_threshold(days_threshold)
    n_top = _resolve_top_n(top_n)
    canonical_store = _resolve_store(store)
    if canonical_store is None:
        return {
            "error": (
                f"უცნობი მაღაზია: {store!r}. დასაშვებია: "
                f"{list(SUPPORTED_STORES)} (ან Latin alias 'ozurgeti'/'dvabzu')."
            ),
            "hint": "მაგ: store='total' / 'ოზურგეთი' / 'დვაბზუ'",
        }

    if today is None:
        today = date.today()
    if not isinstance(today, date):
        return {
            "error": "today პარამეტრი უნდა იყოს date ობიექტი ან None",
            "hint": "ჩვეულებრივ ეს არ გადაეცემა — defaults to date.today().",
        }

    # --- Load + shape-check data -----------------------------------------
    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("dead_stock data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა",
            "hint": "გადაამოწმე pipeline-ის ფუნქცია generate_dashboard_data.py-ში.",
        }

    imported_block = data.get("imported_products") or {}
    retail_block = data.get("retail_sales") or {}
    imported_products = imported_block.get("products") or []
    retail_products = retail_block.get("by_product") or []

    if not isinstance(imported_products, list) or not imported_products:
        return {
            "error": (
                "imported_products.products ცარიელია ან არ არის ჩატვირთული — "
                "Dead Stock-ის ანალიზი შეუძლებელია."
            ),
            "hint": (
                "გადაამოწმე Financial_Analysis/შემოტანილი პროდუქცია/ ფაილების "
                "არსებობა და გადაუშვი generate_dashboard_data.py."
            ),
        }
    if not isinstance(retail_products, list) or not retail_products:
        return {
            "error": (
                "retail_sales.by_product ცარიელია ან არ არის ჩატვირთული — "
                "sell-through ვერ ვითვლი."
            ),
            "hint": (
                "გადაამოწმე Financial_Analysis/გაყიდული პროდუქტები სოფ ... "
                "ფაილები + retail_sales pipeline."
            ),
        }

    sales_index = _build_sales_index(
        retail_products, store_filter=canonical_store
    )

    # --- Per-SKU classification ------------------------------------------
    classified: List[Dict[str, Any]] = []
    imported_total_amount = 0.0
    matched_count = 0
    matched_total_amount = 0.0
    unmatched_total_amount = 0.0

    bucket_counts: Dict[str, int] = {
        BUCKET_ACTIVE: 0,
        BUCKET_91_180: 0,
        BUCKET_181_365: 0,
        BUCKET_365_PLUS: 0,
        BUCKET_UNMATCHED: 0,
    }
    by_action_count: Dict[str, int] = {a: 0 for a in ALL_ACTIONS}
    by_action_freed: Dict[str, float] = {a: 0.0 for a in ALL_ACTIONS}

    for row in imported_products:
        if not isinstance(row, dict):
            continue
        imported_amount = _safe_float(row.get("total_amount_ge"))
        imported_qty = _safe_float(row.get("total_quantity"))
        imported_total_amount += imported_amount

        sales_row, match_method = _match_imported_to_sales(row, sales_index)
        if sales_row is None:
            bucket = BUCKET_UNMATCHED
            days_since = None
            last_sold_date: Optional[date] = None
            gross_margin_pct = 0.0
            unmatched_total_amount += imported_amount
        else:
            matched_count += 1
            matched_total_amount += imported_amount
            dr = sales_row.get("date_range") or {}
            last_sold_date = _parse_iso_date(dr.get("max"))
            if last_sold_date is None:
                bucket = BUCKET_UNMATCHED
                days_since = None
            else:
                days_since = (today - last_sold_date).days
                bucket = _bucket_for(days_since, threshold)
            gross_margin_pct = _safe_float(sales_row.get("gross_margin_pct"))

        bucket_counts[bucket] += 1
        action = _recommend_action(
            bucket,
            distinct_supplier_count=_distinct_supplier_count(row),
            gross_margin_pct=gross_margin_pct,
        )
        freed = _expected_freed_cash(action, imported_amount)

        if bucket != BUCKET_ACTIVE:
            by_action_count[action] += 1
            by_action_freed[action] += freed

        classified.append(
            {
                "product_code": _normalize_code(row.get("product_code")),
                "product_name": str(row.get("product_name") or ""),
                "imported_amount": round(imported_amount, 2),
                "imported_quantity": round(imported_qty, 2),
                "last_sold_date": (
                    last_sold_date.isoformat() if last_sold_date else None
                ),
                "days_since_last_sale": days_since,
                "stale_bucket": bucket,
                "top_supplier": _top_supplier_name(row),
                "matched": sales_row is not None,
                "match_method": match_method,
                "recommended_action": action,
                "expected_freed_cash": freed,
            }
        )

    # --- Summary aggregates ----------------------------------------------
    imported_total_count = len(
        [r for r in imported_products if isinstance(r, dict)]
    )
    unmatched_count = imported_total_count - matched_count

    frozen_cash_estimate = round(
        sum(by_action_freed[a] for a in ALL_ACTIONS), 2
    )

    matching_warning: Optional[str] = None
    if imported_total_count > 0:
        unmatched_pct = unmatched_count * 100.0 / imported_total_count
        if unmatched_pct >= _UNMATCHED_WARN_THRESHOLD_PCT:
            matching_warning = (
                f"{unmatched_count}/{imported_total_count} imported SKU "
                f"({unmatched_pct:.1f}%) ვერ დავამთხვიე retail_sales-ს — "
                "code/barcode drift. ციფრი 'frozen_cash_estimate' ზედა "
                "შეფასებაა, არა ზუსტი დიაგნოზი. matched_total_amount "
                "უფრო საიმედოა საფუძვლად."
            )

    # --- Top stale SKUs ---------------------------------------------------
    stale = [
        r for r in classified
        if r["stale_bucket"] not in (BUCKET_ACTIVE,)
    ]
    stale.sort(key=lambda r: r["imported_amount"], reverse=True)
    top_stale = stale[:n_top]

    # --- Notes (caveats surfaced verbatim to the LLM) --------------------
    notes: List[str] = [
        "ციფრები ფაქტობრივ data.json-ზეა (imported_products + retail_sales).",
        f"Store filter: {canonical_store}.",
        f"Days-since-last-sale threshold: {threshold} დღე.",
    ]
    if matching_warning:
        notes.append(matching_warning)
    if canonical_store != STORE_TOTAL:
        notes.append(
            "ⓘ imported_products ფაილში მაღაზიის გარჩევა არ არის — "
            "store filter მოქმედებს მხოლოდ sell-through-ზე "
            "(retail_sales.by_product → object_breakdown). "
            "Per-store imported allocation parking-lot-შია."
        )

    return {
        "as_of_date": today.isoformat(),
        "days_threshold": threshold,
        "store_filter": (
            "ჯამი" if canonical_store == STORE_TOTAL else canonical_store
        ),
        "summary": {
            "imported_total_count": imported_total_count,
            "imported_total_amount": round(imported_total_amount, 2),
            "matched_count": matched_count,
            "matched_total_amount": round(matched_total_amount, 2),
            "unmatched_count": unmatched_count,
            "unmatched_total_amount": round(unmatched_total_amount, 2),
            "active_within_threshold_count": bucket_counts[BUCKET_ACTIVE],
            "stale_91_180d_count": bucket_counts[BUCKET_91_180],
            "stale_181_365d_count": bucket_counts[BUCKET_181_365],
            "dead_365d_plus_count": bucket_counts[BUCKET_365_PLUS],
            "frozen_cash_estimate": frozen_cash_estimate,
            "matching_warning": matching_warning,
        },
        "by_action": {
            action: {
                "sku_count": by_action_count[action],
                "freed_cash_estimate": round(by_action_freed[action], 2),
            }
            for action in ALL_ACTIONS
        },
        "top_stale_skus": top_stale,
        "notes": notes,
    }
