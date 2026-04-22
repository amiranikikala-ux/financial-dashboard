"""Phase 2.5 — Product Profitability X-Ray.

Given the pre-computed ``retail_sales.by_product`` list from ``data.json``
(each entry carries revenue_ge + cost_ge + profit_ge + gross_margin_pct +
per-object breakdown), rank products to surface:

* **worst_performers** — the lowest-margin products meeting the revenue
  threshold, sorted margin ascending. These are the real money-leakers.
* **best_performers** — highest-margin products, sorted margin descending.
  Useful for "what am I doing right?" analysis.
* **suspicious** — products with margin < 0% or > 90% (very likely a data
  entry error: cost or price miskeyed, unit mismatch, etc.). These are
  quarantined from worst/best so they don't skew the insight.

Return contract (success)::

    {
        "source": "data.json:retail_sales.by_product",
        "as_of_date": "YYYY-MM-DD",
        "store": "total" | "ოზურგეთი" | "დვაბზუ",
        "category_filter": str | None,
        "min_revenue_threshold_ge": float,
        "top_n": int,
        "products_scanned": int,
        "products_qualified": int,     # passed the revenue threshold
        "worst_performers": [ProductEntry, ...],  # len ≤ top_n
        "best_performers":  [ProductEntry, ...],  # len ≤ top_n
        "suspicious":       [ProductEntry, ...],  # any count
        "portfolio_margin_pct": float,
        "summary_ka": str,
        "notes": [str, ...],
    }

Each ``ProductEntry``::

    {
        "product_name": str,
        "category": str,
        "product_code": str,
        "revenue_ge": float,
        "cost_ge": float,
        "profit_ge": float,
        "gross_margin_pct": float,
        "total_quantity": float,
        "flag": "🟢 HEALTHY" | "🟡 THIN" | "🔴 BLEEDING" | "⚠️ SUSPICIOUS",
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import math
from datetime import date
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
MAX_TOP_N = 50

DEFAULT_MIN_REVENUE_GE = 500.0

#: Margin below this band flags 🔴 BLEEDING (below even minimal retail margin).
MARGIN_BLEEDING_PCT = 5.0
#: Margin between BLEEDING and this band flags 🟡 THIN.
MARGIN_THIN_PCT = 15.0

#: Anything outside [-5%, 90%] is suspicious — data entry error or
#: one-off liquidation. Negative margin = selling below cost (losing
#: money per unit); > 90% margin = probably missing cost field.
SUSPICIOUS_MARGIN_LOW = -5.0
SUSPICIOUS_MARGIN_HIGH = 90.0

FLAG_HEALTHY = "🟢 HEALTHY"
FLAG_THIN = "🟡 THIN"
FLAG_BLEEDING = "🔴 BLEEDING"
FLAG_SUSPICIOUS = "⚠️ SUSPICIOUS"

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


def _resolve_top_n(raw: Any) -> int:
    try:
        value = int(raw) if raw is not None else DEFAULT_TOP_N
    except (TypeError, ValueError):
        return DEFAULT_TOP_N
    if value < MIN_TOP_N:
        return MIN_TOP_N
    if value > MAX_TOP_N:
        return MAX_TOP_N
    return value


def _resolve_min_revenue(raw: Any) -> float:
    if raw is None:
        return DEFAULT_MIN_REVENUE_GE
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_MIN_REVENUE_GE
    if math.isnan(value) or math.isinf(value) or value < 0:
        return DEFAULT_MIN_REVENUE_GE
    return value


def _resolve_category_filter(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text or None


# ---------------------------------------------------------------------------
# Per-store revenue extraction
# ---------------------------------------------------------------------------

def _product_metrics_for_store(
    product: Dict[str, Any],
    store: str,
) -> Optional[Dict[str, float]]:
    """Return ``{revenue_ge, cost_ge, profit_ge, gross_margin_pct, total_quantity}``
    for the requested store (or aggregate for 'total').

    Returns ``None`` when the product has no revenue under that store —
    the caller drops these before ranking.
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


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _flag_for_margin(margin_pct: float) -> str:
    if margin_pct < SUSPICIOUS_MARGIN_LOW or margin_pct > SUSPICIOUS_MARGIN_HIGH:
        return FLAG_SUSPICIOUS
    if margin_pct < MARGIN_BLEEDING_PCT:
        return FLAG_BLEEDING
    if margin_pct < MARGIN_THIN_PCT:
        return FLAG_THIN
    return FLAG_HEALTHY


def _build_entry(
    product: Dict[str, Any],
    metrics: Dict[str, float],
) -> Dict[str, Any]:
    return {
        "product_name": str(product.get("product_name") or "").strip() or "უცნობი პროდუქტი",
        "category": str(product.get("category") or "").strip() or "უცნობი კატეგორია",
        "product_code": str(product.get("product_code") or "").strip(),
        "revenue_ge": metrics["revenue_ge"],
        "cost_ge": metrics["cost_ge"],
        "profit_ge": metrics["profit_ge"],
        "gross_margin_pct": metrics["gross_margin_pct"],
        "total_quantity": metrics["total_quantity"],
        "flag": _flag_for_margin(metrics["gross_margin_pct"]),
    }


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------

def _render_summary_ka(
    *,
    store_label: str,
    category_filter: Optional[str],
    products_scanned: int,
    products_qualified: int,
    worst: List[Dict[str, Any]],
    best: List[Dict[str, Any]],
    suspicious: List[Dict[str, Any]],
    portfolio_margin: float,
) -> str:
    cat_block = f" · კატეგორია **{category_filter}**" if category_filter else ""
    worst_block = (
        f" · worst: **{worst[0]['product_name'][:40]}** "
        f"({worst[0]['gross_margin_pct']:.1f}%)"
        if worst else ""
    )
    best_block = (
        f" · best: **{best[0]['product_name'][:40]}** "
        f"({best[0]['gross_margin_pct']:.1f}%)"
        if best else ""
    )
    susp_block = (
        f" · ⚠️ **{len(suspicious)} suspicious** (margin outside [-5%, 90%])"
        if suspicious else ""
    )
    return (
        f"**Product X-Ray** ({store_label}){cat_block} · "
        f"{products_qualified}/{products_scanned} პროდუქტი გააჩერდა "
        f"(revenue ≥ threshold) · portfolio margin **{portfolio_margin:.1f}%**"
        f"{worst_block}{best_block}{susp_block}"
    )


def _portfolio_margin_pct(qualified: List[Dict[str, Any]]) -> float:
    """Revenue-weighted portfolio margin across the qualified entries."""
    total_rev = sum(p["revenue_ge"] for p in qualified)
    if total_rev <= 0:
        return 0.0
    total_profit = sum(p["profit_ge"] for p in qualified)
    return round(total_profit / total_rev * 100.0, 2)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_product_profitability(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    store: Any = None,
    top_n: Any = None,
    category_filter: Any = None,
    min_revenue_threshold_ge: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Analyze ``retail_sales.by_product`` and rank products by margin.

    See the module docstring for the full return contract.
    """
    canonical_store, store_err = _resolve_store(store)
    if store_err:
        return {"error": store_err, "hint": "გამოიყენე enum: total / ოზურგეთი / დვაბზუ."}
    assert canonical_store is not None

    n = _resolve_top_n(top_n)
    threshold = _resolve_min_revenue(min_revenue_threshold_ge)
    cat = _resolve_category_filter(category_filter)

    if today is None:
        today = date.today()

    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("product_profitability data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა.",
            "hint": "გადაამოწმე generate_dashboard_data.py-ს output.",
        }

    retail = data.get("retail_sales")
    if not isinstance(retail, dict):
        return {
            "error": "`retail_sales` section data.json-ში არ არის.",
            "hint": "გაუშვი generate_dashboard_data.py და შეამოწმე retail_sales bundle.",
        }
    products = retail.get("by_product") or []
    if not isinstance(products, list) or not products:
        return {
            "error": "`retail_sales.by_product` ცარიელია — პროდუქტები ვერ ვანალიზებ.",
            "hint": (
                "გადაამოწმე რომ retail_sales ფაილები `Financial_Analysis/გაყიდული "
                "პროდუქტები სოფ *`-ში კითხვადი და active policy-ით ჩართულია."
            ),
        }

    products_scanned = len(products)

    # Build qualified entries: pass store filter, category filter (if any),
    # and revenue threshold. Suspicious go into a separate bucket.
    qualified: List[Dict[str, Any]] = []
    suspicious: List[Dict[str, Any]] = []
    for product in products:
        if not isinstance(product, dict):
            continue
        metrics = _product_metrics_for_store(product, canonical_store)
        if metrics is None:
            continue
        if metrics["revenue_ge"] < threshold:
            continue
        if cat is not None:
            product_cat = str(product.get("category") or "").lower()
            if cat.lower() not in product_cat:
                continue
        entry = _build_entry(product, metrics)
        if entry["flag"] == FLAG_SUSPICIOUS:
            suspicious.append(entry)
        else:
            qualified.append(entry)

    if not qualified and not suspicious:
        return {
            "error": (
                f"ფილტრს ერთი პროდუქტიც არ დააკმაყოფილა "
                f"(store='{canonical_store}', threshold={threshold:.0f} ₾"
                f"{', category=' + cat if cat else ''})."
            ),
            "hint": "შეამცირე threshold ან ცადე უფრო ფართო category_filter.",
        }

    worst = sorted(
        qualified,
        key=lambda e: (e["gross_margin_pct"], -e["revenue_ge"]),
    )[:n]
    best = sorted(
        qualified,
        key=lambda e: (-e["gross_margin_pct"], -e["revenue_ge"]),
    )[:n]

    portfolio_margin = _portfolio_margin_pct(qualified)

    store_label = {
        STORE_TOTAL: "ორივე მაღაზია",
        STORE_OZURGETI: "ოზურგეთი",
        STORE_DVABZU: "დვაბზუ",
    }.get(canonical_store, canonical_store)
    summary_ka = _render_summary_ka(
        store_label=store_label,
        category_filter=cat,
        products_scanned=products_scanned,
        products_qualified=len(qualified),
        worst=worst,
        best=best,
        suspicious=suspicious,
        portfolio_margin=portfolio_margin,
    )

    notes: List[str] = []
    notes.append(
        f"Revenue threshold = {threshold:.0f} ₾ — ქვემოთ მდგომი პროდუქტები "
        "(ერთჯერადი გაყიდვები, outlier-ები) ანალიზში არ შედიან."
    )
    bleeding_count = sum(1 for e in qualified if e["flag"] == FLAG_BLEEDING)
    thin_count = sum(1 for e in qualified if e["flag"] == FLAG_THIN)
    if bleeding_count:
        notes.append(
            f"🔴 {bleeding_count} პროდუქტი margin < 5% — ფასი / შესყიდვის "
            f"პირობა გადახედვას საჭიროებს."
        )
    if thin_count:
        notes.append(
            f"🟡 {thin_count} პროდუქტი margin 5–15% — ფრთხილად: ნებისმიერი "
            f"cost ცვლილება მათ bleeding-ში გადააქცევს."
        )
    if suspicious:
        notes.append(
            f"⚠️ {len(suspicious)} პროდუქტი margin-ი [-5%, 90%]-ის მიღმაა — "
            f"სავარაუდოდ data entry error (cost/price არასწორად აქვს "
            f"ჩაწერილი). გადაამოწმე Excel-ში სანამ action გააკეთებ."
        )
    notes.append(
        "ⓘ Product X-Ray margin-ს ითვლის retail_sales excel data-დან — "
        "აგრეგირებულია data.json generate-ის დროს. ცოცხალი ფასები ვერ ხედავს."
    )

    return {
        "source": SOURCE_LABEL,
        "as_of_date": today.isoformat(),
        "store": canonical_store,
        "category_filter": cat,
        "min_revenue_threshold_ge": threshold,
        "top_n": n,
        "products_scanned": products_scanned,
        "products_qualified": len(qualified),
        "worst_performers": worst,
        "best_performers": best,
        "suspicious": suspicious,
        "portfolio_margin_pct": portfolio_margin,
        "summary_ka": summary_ka,
        "notes": notes,
    }


__all__ = [
    "DEFAULT_TOP_N",
    "MIN_TOP_N",
    "MAX_TOP_N",
    "DEFAULT_MIN_REVENUE_GE",
    "MARGIN_BLEEDING_PCT",
    "MARGIN_THIN_PCT",
    "SUSPICIOUS_MARGIN_LOW",
    "SUSPICIOUS_MARGIN_HIGH",
    "FLAG_HEALTHY",
    "FLAG_THIN",
    "FLAG_BLEEDING",
    "FLAG_SUSPICIOUS",
    "SOURCE_LABEL",
    "analyze_product_profitability",
]
