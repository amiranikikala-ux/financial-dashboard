"""Phase 2.6 — Promotion Candidate Finder.

Given ``retail_sales.by_product`` from ``data.json`` (each entry carries
revenue_ge + cost_ge + profit_ge + gross_margin_pct + date_range +
object_breakdown), rank **actively selling** SKUs that have the margin
headroom and volume footprint to respond to a promotional discount.

Distinct from ``analyze_dead_stock`` (which targets stale/dead inventory
for liquidation) and from ``analyze_product_profitability`` (which
surfaces the worst/best margin earners across the portfolio). This tool
builds a **promotion menu** — SKUs you could push with a 5–20% discount
and still keep a healthy post-discount margin.

Return contract (success)::

    {
        "source": "data.json:retail_sales.by_product",
        "as_of_date": "YYYY-MM-DD",
        "store": "total" | "ოზურგეთი" | "დვაბზუ",
        "min_margin_pct": float,
        "max_days_since_last_sale": int,
        "max_suggested_discount_pct": float,
        "floor_post_discount_margin_pct": float,  # 5.0 (fixed v1)
        "top_n": int,
        "products_scanned": int,
        "products_evaluated": int,  # passed all filters
        "candidates": [PromotionCandidate, ...],  # len ≤ top_n
        "summary_ka": str,
        "notes_ka": [str, ...],
    }

Each ``PromotionCandidate``::

    {
        "product_code": str,
        "product_name": str,
        "category": str,
        "current_margin_pct": float,
        "revenue_ge": float,
        "total_quantity": float,
        "days_since_last_sale": int,
        "distinct_month_count": int,
        "store_breakdown": [{"object", "revenue_ge", "total_quantity"}, ...],
        "suggested_discount_pct": float,
        "post_discount_margin_pct": float,
        "promotion_score": float,
        "expected_signal_ka": "🟢 high" | "🟡 medium" | "🟠 low",
        "rationale_ka": str,
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from dashboard_pipeline.ai.forecasting import (
    STORE_DVABZU,
    STORE_OZURGETI,
    STORE_TOTAL,
    SUPPORTED_STORES,
    _STORE_ALIASES,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_N = 10
MIN_TOP_N = 3
MAX_TOP_N = 30

DEFAULT_MIN_MARGIN_PCT = 15.0
MIN_MIN_MARGIN_PCT = 0.0
MAX_MIN_MARGIN_PCT = 80.0

DEFAULT_MAX_DAYS_SINCE_LAST_SALE = 90
MIN_MAX_DAYS_SINCE_LAST_SALE = 1
MAX_MAX_DAYS_SINCE_LAST_SALE = 365

DEFAULT_MAX_SUGGESTED_DISCOUNT_PCT = 20.0
MIN_MAX_SUGGESTED_DISCOUNT_PCT = 1.0
MAX_MAX_SUGGESTED_DISCOUNT_PCT = 40.0

DEFAULT_MIN_VOLUME = 20.0
MIN_MIN_VOLUME = 0.0

#: Post-discount margin floor — v1 hardcoded. Any suggested discount is
#: capped so current_margin − discount ≥ this floor.
FLOOR_POST_DISCOUNT_MARGIN_PCT = 5.0

#: Anything outside [-5%, 90%] is quarantined as likely data-entry error
#: (same rule as product_profitability X-Ray). Negative = selling below
#: cost, > 90% = cost field probably missing. Promoting these risks
#: making noise bigger.
SUSPICIOUS_MARGIN_LOW = -5.0
SUSPICIOUS_MARGIN_HIGH = 90.0

SIGNAL_HIGH = "🟢 high"
SIGNAL_MEDIUM = "🟡 medium"
SIGNAL_LOW = "🟠 low"

SCORE_HIGH_THRESHOLD = 30.0
SCORE_MEDIUM_THRESHOLD = 10.0

SOURCE_LABEL = "data.json:retail_sales.by_product"


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------

def _resolve_store(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    if raw is None:
        return STORE_TOTAL, None
    if not isinstance(raw, str):
        return None, "`store` უნდა იყოს ტექსტი: 'total', 'ოზურგეთი' ან 'დვაბზუ'."
    normalized = raw.strip()
    if not normalized:
        return STORE_TOTAL, None
    if normalized in SUPPORTED_STORES:
        return normalized, None
    alias = _STORE_ALIASES.get(normalized.lower())
    if alias is not None:
        return alias, None
    return None, (
        f"`store`='{raw}' არ არის მხარდაჭერილი. "
        f"მისაღები მნიშვნელობები: {list(SUPPORTED_STORES)}."
    )


def _clamp_int(raw: Any, *, default: int, min_v: int, max_v: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    if value < min_v:
        return min_v
    if value > max_v:
        return max_v
    return value


def _clamp_float(
    raw: Any,
    *,
    default: float,
    min_v: float,
    max_v: Optional[float] = None,
) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if math.isnan(value) or math.isinf(value):
        return default
    if value < min_v:
        return min_v
    if max_v is not None and value > max_v:
        return max_v
    return value


# ---------------------------------------------------------------------------
# Per-store metric extraction
# ---------------------------------------------------------------------------

def _product_metrics_for_store(
    product: Dict[str, Any],
    store: str,
) -> Optional[Dict[str, float]]:
    """Return ``{revenue_ge, cost_ge, profit_ge, gross_margin_pct,
    total_quantity}`` for the requested store (or aggregate for 'total').

    Returns ``None`` when the product has no revenue under that store.
    """
    if store == STORE_TOTAL:
        try:
            revenue = float(product.get("revenue_ge") or 0.0)
            cost = float(product.get("cost_ge") or 0.0)
            profit = float(product.get("profit_ge") or 0.0)
            qty = float(product.get("total_quantity") or 0.0)
            margin = float(product.get("gross_margin_pct") or 0.0)
        except (TypeError, ValueError):
            return None
        if revenue <= 0:
            return None
        return {
            "revenue_ge": round(revenue, 2),
            "cost_ge": round(cost, 2),
            "profit_ge": round(profit, 2),
            "gross_margin_pct": round(margin, 2),
            "total_quantity": round(qty, 3),
        }

    breakdown = product.get("object_breakdown") or []
    if not isinstance(breakdown, list):
        return None
    for entry in breakdown:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("object") or "").strip() != store:
            continue
        try:
            revenue = float(entry.get("revenue_ge") or 0.0)
            cost = float(entry.get("cost_ge") or 0.0)
            profit = float(entry.get("profit_ge") or 0.0)
            qty = float(entry.get("total_quantity") or 0.0)
            margin = float(entry.get("gross_margin_pct") or 0.0)
        except (TypeError, ValueError):
            continue
        if revenue <= 0:
            continue
        return {
            "revenue_ge": round(revenue, 2),
            "cost_ge": round(cost, 2),
            "profit_ge": round(profit, 2),
            "gross_margin_pct": round(margin, 2),
            "total_quantity": round(qty, 3),
        }
    return None


def _store_breakdown(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    breakdown = product.get("object_breakdown") or []
    if not isinstance(breakdown, list):
        return []
    rows: List[Dict[str, Any]] = []
    for entry in breakdown:
        if not isinstance(entry, dict):
            continue
        obj = str(entry.get("object") or "").strip()
        if not obj:
            continue
        try:
            revenue = float(entry.get("revenue_ge") or 0.0)
            qty = float(entry.get("total_quantity") or 0.0)
        except (TypeError, ValueError):
            continue
        if revenue <= 0:
            continue
        rows.append({
            "object": obj,
            "revenue_ge": round(revenue, 2),
            "total_quantity": round(qty, 3),
        })
    return rows


# ---------------------------------------------------------------------------
# Date handling
# ---------------------------------------------------------------------------

def _parse_iso_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _days_since_last_sale(
    product: Dict[str, Any],
    *,
    today: date,
) -> Optional[int]:
    date_range = product.get("date_range") or {}
    last = _parse_iso_date(date_range.get("max"))
    if last is None:
        return None
    return (today - last).days


# ---------------------------------------------------------------------------
# Scoring + discount sizing
# ---------------------------------------------------------------------------

def _recency_bonus(days_since: int) -> float:
    """Decay weight: fresher SKUs rank higher."""
    if days_since <= 30:
        return 1.0
    if days_since <= 60:
        return 0.7
    if days_since <= 90:
        return 0.5
    return 0.3


def _promotion_score(
    *,
    current_margin_pct: float,
    total_quantity: float,
    days_since_last_sale: int,
    floor_margin_pct: float = FLOOR_POST_DISCOUNT_MARGIN_PCT,
) -> float:
    """``margin_headroom × log(1 + volume) × recency_bonus``.

    ``margin_headroom`` = ``max(0, current_margin − floor)``. Volume is
    total_quantity over the aggregation period (so SKUs with richer
    history outrank one-off hits even when margin is equal). Recency is a
    piecewise decay so stale-but-alive SKUs don't dominate fresh ones.
    """
    headroom = max(0.0, current_margin_pct - floor_margin_pct)
    if headroom <= 0:
        return 0.0
    volume_term = math.log1p(max(0.0, total_quantity))
    recency = _recency_bonus(days_since_last_sale)
    return round(headroom * volume_term * recency, 3)


def _expected_signal(score: float) -> str:
    if score >= SCORE_HIGH_THRESHOLD:
        return SIGNAL_HIGH
    if score >= SCORE_MEDIUM_THRESHOLD:
        return SIGNAL_MEDIUM
    return SIGNAL_LOW


def _suggested_discount_pct(
    *,
    current_margin_pct: float,
    max_suggested: float,
    floor_margin_pct: float = FLOOR_POST_DISCOUNT_MARGIN_PCT,
) -> float:
    """Cap discount so post-discount margin stays ≥ floor.

    Always rounded to the nearest integer percent for clean AI output.
    """
    room = max(0.0, current_margin_pct - floor_margin_pct)
    raw = min(max_suggested, room)
    return round(raw, 0)


def _rationale_ka(
    *,
    product_name: str,
    current_margin_pct: float,
    post_discount_margin_pct: float,
    days_since_last_sale: int,
    total_quantity: float,
    signal: str,
) -> str:
    return (
        f"margin **{current_margin_pct:.1f}%** → discount-ის შემდეგ "
        f"**{post_discount_margin_pct:.1f}%**; ბოლო გაყიდვა "
        f"**{days_since_last_sale} დღის წინ**; ჯამი "
        f"**{total_quantity:,.0f} ცალი**. {signal} potential."
    )


# ---------------------------------------------------------------------------
# Entry building
# ---------------------------------------------------------------------------

def _build_candidate(
    product: Dict[str, Any],
    metrics: Dict[str, float],
    *,
    days_since: int,
    max_suggested: float,
) -> Dict[str, Any]:
    current_margin = metrics["gross_margin_pct"]
    discount = _suggested_discount_pct(
        current_margin_pct=current_margin,
        max_suggested=max_suggested,
    )
    post = round(current_margin - discount, 2)
    score = _promotion_score(
        current_margin_pct=current_margin,
        total_quantity=metrics["total_quantity"],
        days_since_last_sale=days_since,
    )
    signal = _expected_signal(score)
    rationale = _rationale_ka(
        product_name=str(product.get("product_name") or ""),
        current_margin_pct=current_margin,
        post_discount_margin_pct=post,
        days_since_last_sale=days_since,
        total_quantity=metrics["total_quantity"],
        signal=signal,
    )
    return {
        "product_code": str(product.get("product_code") or "").strip(),
        "product_name": (
            str(product.get("product_name") or "").strip()
            or "უცნობი პროდუქტი"
        ),
        "category": (
            str(product.get("category") or "").strip() or "უცნობი კატეგორია"
        ),
        "current_margin_pct": current_margin,
        "revenue_ge": metrics["revenue_ge"],
        "total_quantity": metrics["total_quantity"],
        "days_since_last_sale": days_since,
        "distinct_month_count": int(product.get("distinct_month_count") or 0),
        "store_breakdown": _store_breakdown(product),
        "suggested_discount_pct": discount,
        "post_discount_margin_pct": post,
        "promotion_score": score,
        "expected_signal_ka": signal,
        "rationale_ka": rationale,
    }


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------

def _render_summary_ka(
    *,
    store_label: str,
    top_n: int,
    products_scanned: int,
    products_evaluated: int,
    candidates: List[Dict[str, Any]],
) -> str:
    if not candidates:
        return (
            f"**promotion menu** ({store_label}) · 0 კანდიდატი · "
            f"scanned {products_scanned}, filters too strict (შეასუსტე "
            f"`min_margin_pct` ან `max_days_since_last_sale`)."
        )
    top = candidates[0]
    short_name = str(top["product_name"])[:38]
    return (
        f"**promotion menu** ({store_label}) · "
        f"{len(candidates)}/{top_n} SKU · top: **{short_name}** "
        f"(margin {top['current_margin_pct']:.0f}% → "
        f"{top['suggested_discount_pct']:.0f}% discount, "
        f"{top['expected_signal_ka']}) · "
        f"evaluated {products_evaluated}/{products_scanned}"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def find_promotion_candidates(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    store: Any = None,
    top_n: Any = None,
    min_margin_pct: Any = None,
    max_days_since_last_sale: Any = None,
    max_suggested_discount_pct: Any = None,
    min_volume: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Rank actively selling SKUs by their fit for a promotional push.

    See the module docstring for the full return contract.
    """
    canonical_store, store_err = _resolve_store(store)
    if store_err:
        return {
            "error": store_err,
            "hint": "გამოიყენე enum: total / ოზურგეთი / დვაბზუ.",
        }
    assert canonical_store is not None

    n = _clamp_int(top_n, default=DEFAULT_TOP_N, min_v=MIN_TOP_N, max_v=MAX_TOP_N)
    margin_floor = _clamp_float(
        min_margin_pct,
        default=DEFAULT_MIN_MARGIN_PCT,
        min_v=MIN_MIN_MARGIN_PCT,
        max_v=MAX_MIN_MARGIN_PCT,
    )
    max_days = _clamp_int(
        max_days_since_last_sale,
        default=DEFAULT_MAX_DAYS_SINCE_LAST_SALE,
        min_v=MIN_MAX_DAYS_SINCE_LAST_SALE,
        max_v=MAX_MAX_DAYS_SINCE_LAST_SALE,
    )
    max_disc = _clamp_float(
        max_suggested_discount_pct,
        default=DEFAULT_MAX_SUGGESTED_DISCOUNT_PCT,
        min_v=MIN_MAX_SUGGESTED_DISCOUNT_PCT,
        max_v=MAX_MAX_SUGGESTED_DISCOUNT_PCT,
    )
    volume_floor = _clamp_float(
        min_volume,
        default=DEFAULT_MIN_VOLUME,
        min_v=MIN_MIN_VOLUME,
    )

    if today is None:
        today = date.today()

    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("promotion_candidates data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა.",
            "hint": "გადაამოწმე generate_dashboard_data.py-ს output.",
        }

    retail = data.get("retail_sales")
    if not isinstance(retail, dict):
        return {
            "error": "`retail_sales` section data.json-ში არ არის.",
            "hint": (
                "გაუშვი generate_dashboard_data.py და შეამოწმე "
                "retail_sales bundle."
            ),
        }
    products = retail.get("by_product") or []
    if not isinstance(products, list) or not products:
        return {
            "error": (
                "`retail_sales.by_product` ცარიელია — პროდუქტები "
                "ვერ ვრანკავ."
            ),
            "hint": (
                "გადაამოწმე რომ retail_sales ფაილები `Financial_Analysis/"
                "გაყიდული პროდუქტები სოფ *`-ში კითხვადი და active "
                "policy-ით ჩართულია."
            ),
        }

    products_scanned = len(products)

    candidates: List[Dict[str, Any]] = []
    suspicious_skipped = 0
    for product in products:
        if not isinstance(product, dict):
            continue
        metrics = _product_metrics_for_store(product, canonical_store)
        if metrics is None:
            continue
        margin = metrics["gross_margin_pct"]
        if margin < SUSPICIOUS_MARGIN_LOW or margin > SUSPICIOUS_MARGIN_HIGH:
            # Quarantine likely data-entry errors. Same boundary as the
            # X-Ray tool so both tools treat the same rows as suspect.
            suspicious_skipped += 1
            continue
        if margin < margin_floor:
            continue
        if metrics["total_quantity"] < volume_floor:
            continue
        days_since = _days_since_last_sale(product, today=today)
        if days_since is None or days_since < 0:
            continue
        if days_since > max_days:
            continue
        candidate = _build_candidate(
            product,
            metrics,
            days_since=days_since,
            max_suggested=max_disc,
        )
        # Zero-discount candidates (no margin headroom after the floor)
        # are useless for a promotion menu — drop them.
        if candidate["suggested_discount_pct"] <= 0:
            continue
        candidates.append(candidate)

    products_evaluated = len(candidates)

    candidates.sort(key=lambda c: c["promotion_score"], reverse=True)
    top_candidates = candidates[:n]

    store_label = {
        STORE_TOTAL: "ორივე მაღაზია",
        STORE_OZURGETI: "ოზურგეთი",
        STORE_DVABZU: "დვაბზუ",
    }.get(canonical_store, canonical_store)

    summary_ka = _render_summary_ka(
        store_label=store_label,
        top_n=n,
        products_scanned=products_scanned,
        products_evaluated=products_evaluated,
        candidates=top_candidates,
    )

    notes: List[str] = []
    if suspicious_skipped:
        notes.append(
            f"⚠️ {suspicious_skipped} SKU suspicious margin-ით "
            f"([-5%, 90%]-ის მიღმა) გამოვრიცხე — data entry error-ები. "
            f"`analyze_product_profitability` გაჩვენებს რომელია ესენი."
        )
    if not top_candidates:
        notes.append(
            "🟠 ფილტრს ვერც ერთი SKU არ დააკმაყოფილა — "
            "შეამცირე `min_margin_pct` (default 15%), გაზარდე "
            "`max_days_since_last_sale` (default 90 დღე), "
            "ან დაადაბლე `min_volume` (default 20 ცალი)."
        )
    else:
        high_count = sum(
            1 for c in top_candidates if c["expected_signal_ka"] == SIGNAL_HIGH
        )
        low_count = sum(
            1 for c in top_candidates if c["expected_signal_ka"] == SIGNAL_LOW
        )
        if high_count:
            notes.append(
                f"🟢 {high_count} კანდიდატი 'high' signal-ით — margin-იც "
                f"ბევრია და volume-იც. აქ უნდა დაიწყო."
            )
        if low_count:
            notes.append(
                f"🟠 {low_count} კანდიდატი 'low' signal-ით — margin "
                f"ცოტაა ან volume-ი პატარა. promote თუ dead-stock "
                f"ცილდება ამ SKU-ს, მაშინ `analyze_dead_stock` უკეთ "
                f"აჩვენებს."
            )
    notes.append(
        f"ⓘ Post-discount margin floor **{FLOOR_POST_DISCOUNT_MARGIN_PCT:.0f}%** "
        f"hardcoded v1-ში — discount-ი იჭრება ისე რომ margin ამაზე ქვევით "
        f"არ დაიწიოს."
    )
    notes.append(
        "ⓘ 'Promotion menu' first-cut რეკომენდაციაა retail_sales excel "
        "data-დან. ცოცხალი ფასი / ელასტიურობა ვერ ხედავს — ხელით "
        "გადამოწმება სასურველია action-ამდე."
    )

    return {
        "source": SOURCE_LABEL,
        "as_of_date": today.isoformat(),
        "store": canonical_store,
        "min_margin_pct": margin_floor,
        "max_days_since_last_sale": max_days,
        "max_suggested_discount_pct": max_disc,
        "min_volume": volume_floor,
        "floor_post_discount_margin_pct": FLOOR_POST_DISCOUNT_MARGIN_PCT,
        "top_n": n,
        "products_scanned": products_scanned,
        "products_evaluated": products_evaluated,
        "suspicious_skipped": suspicious_skipped,
        "candidates": top_candidates,
        "summary_ka": summary_ka,
        "notes_ka": notes,
    }


__all__ = [
    "DEFAULT_TOP_N",
    "MIN_TOP_N",
    "MAX_TOP_N",
    "DEFAULT_MIN_MARGIN_PCT",
    "DEFAULT_MAX_DAYS_SINCE_LAST_SALE",
    "DEFAULT_MAX_SUGGESTED_DISCOUNT_PCT",
    "DEFAULT_MIN_VOLUME",
    "FLOOR_POST_DISCOUNT_MARGIN_PCT",
    "SIGNAL_HIGH",
    "SIGNAL_MEDIUM",
    "SIGNAL_LOW",
    "SOURCE_LABEL",
    "find_promotion_candidates",
]
