"""Phase 2.9 — Trend Detector (MoM / YoY price × volume decomposition).

Reads ``retail_sales.by_category_by_month`` from ``data.json`` and
compares a target month (`current`) against either the previous month
(MoM) or the same month one year earlier (YoY). For each category it
decomposes the revenue change into:

    Δrevenue  = price_effect + volume_effect + mix_effect
    price_effect  = Δavg_price × qty_compare
    volume_effect = Δqty      × avg_price_compare
    mix_effect    = Δavg_price × Δqty                 (residual)

Then ranks categories by signed revenue change, so the AI can explain
**what moved and why** — price shift, volume shift, or mix.

Distinct from ``analyze_product_profitability`` (per-SKU static
snapshot) and from ``analyze_dead_stock`` (stale inventory
liquidation). Use this one when the user asks "რა შეიცვალა?",
"რისი ბრალია რომ ბრუნვა დაეცა?", "YoY / MoM ცვლილება".

Return contract (success)::

    {
        "source": "data.json:retail_sales.by_category_by_month",
        "mode": "MoM" | "YoY",
        "current_period": "2024-08",
        "compare_period": "2024-07" | "2023-08",
        "categories_compared": int,
        "categories_skipped_suspicious": int,
        "totals": {
            "revenue_current_ge": float,
            "revenue_compare_ge": float,
            "delta_revenue_ge": float,
            "delta_pct": float,
            "price_effect_ge": float,
            "volume_effect_ge": float,
            "mix_effect_ge": float,
        },
        "top_positive": [TrendEntry, ...],  # len ≤ top_n
        "top_negative": [TrendEntry, ...],  # len ≤ top_n
        "suspicious": [str, ...],  # category names with unreliable margin
        "summary_ka": str,
        "notes_ka": [str, ...],
    }

Each ``TrendEntry``::

    {
        "category": str,
        "normalized_category": str,
        "revenue_current_ge": float,
        "revenue_compare_ge": float,
        "delta_revenue_ge": float,
        "delta_pct": float,
        "qty_current": float,
        "qty_compare": float,
        "delta_qty": float,
        "avg_price_current": float,
        "avg_price_compare": float,
        "delta_avg_price": float,
        "price_effect_ge": float,
        "volume_effect_ge": float,
        "mix_effect_ge": float,
        "driver": "price" | "volume" | "mix",
        "direction_ka": "📈 ზრდა" | "📉 ვარდნა" | "— სტაბილური",
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


DEFAULT_TOP_N = 5
MIN_TOP_N = 3
MAX_TOP_N = 20

# Mirror X-Ray's sanity window — margins outside it hint at bad cost/price data.
SUSPICIOUS_MARGIN_PCT_LOW = -5.0
SUSPICIOUS_MARGIN_PCT_HIGH = 90.0

# Noise floor: ignore categories with negligible revenue on BOTH sides.
MIN_REVENUE_FOR_COMPARISON_GE = 100.0

VALID_MODES = ("MoM", "YoY")


def _err(msg: str, hint: str = "") -> Dict[str, Any]:
    out = {"error": msg}
    if hint:
        out["hint"] = hint
    return out


def _prev_period(period: str, mode: str) -> Optional[str]:
    """Return YYYY-MM of the comparison period, or None if unparseable."""
    try:
        year, month = period.split("-")
        y, m = int(year), int(month)
    except Exception:
        return None
    if mode == "YoY":
        return f"{y - 1:04d}-{m:02d}"
    # MoM
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


def _index_by_period(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Return {period: {normalized_category: row, ...}, ...}."""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for r in rows:
        period = r.get("month")
        key = r.get("normalized_category") or r.get("category")
        if not period or not key:
            continue
        out.setdefault(period, {})[str(key)] = r
    return out


def _latest_period(by_period: Dict[str, Any]) -> Optional[str]:
    if not by_period:
        return None
    # Prefer periods that look like YYYY-MM. Sort lexicographically.
    candidates = [p for p in by_period.keys() if isinstance(p, str) and len(p) == 7 and p[4] == "-"]
    return max(candidates) if candidates else None


def _safe_div(n: float, d: float) -> float:
    if d == 0:
        return 0.0
    return n / d


def _decompose(cur: Dict[str, Any], cmp: Dict[str, Any]) -> Dict[str, Any]:
    """Compute per-category price × volume decomposition."""
    rev_c = float(cur.get("revenue_ge") or 0)
    rev_p = float(cmp.get("revenue_ge") or 0)
    qty_c = float(cur.get("total_quantity") or 0)
    qty_p = float(cmp.get("total_quantity") or 0)

    price_c = _safe_div(rev_c, qty_c)
    price_p = _safe_div(rev_p, qty_p)

    d_rev = rev_c - rev_p
    d_qty = qty_c - qty_p
    d_price = price_c - price_p

    price_effect = d_price * qty_p
    volume_effect = d_qty * price_p
    mix_effect = d_price * d_qty

    # Driver classification: largest absolute effect.
    effects = {"price": price_effect, "volume": volume_effect, "mix": mix_effect}
    driver = max(effects.keys(), key=lambda k: abs(effects[k])) if any(effects.values()) else "—"

    if abs(d_rev) < 0.01:
        direction = "— სტაბილური"
    elif d_rev > 0:
        direction = "📈 ზრდა"
    else:
        direction = "📉 ვარდნა"

    pct = _safe_div(d_rev, abs(rev_p)) * 100.0 if rev_p else (100.0 if d_rev > 0 else 0.0)

    return {
        "revenue_current_ge": round(rev_c, 2),
        "revenue_compare_ge": round(rev_p, 2),
        "delta_revenue_ge": round(d_rev, 2),
        "delta_pct": round(pct, 2),
        "qty_current": round(qty_c, 3),
        "qty_compare": round(qty_p, 3),
        "delta_qty": round(d_qty, 3),
        "avg_price_current": round(price_c, 4),
        "avg_price_compare": round(price_p, 4),
        "delta_avg_price": round(d_price, 4),
        "price_effect_ge": round(price_effect, 2),
        "volume_effect_ge": round(volume_effect, 2),
        "mix_effect_ge": round(mix_effect, 2),
        "driver": driver,
        "direction_ka": direction,
    }


def _is_suspicious(row: Dict[str, Any]) -> bool:
    margin = row.get("gross_margin_pct")
    if margin is None:
        return False
    try:
        m = float(margin)
    except (TypeError, ValueError):
        return False
    return m < SUSPICIOUS_MARGIN_PCT_LOW or m > SUSPICIOUS_MARGIN_PCT_HIGH


def detect_trends(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    mode: Optional[str] = None,
    period: Optional[str] = None,
    top_n: Optional[int] = None,
    category_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Args:
        mode: 'MoM' (default) or 'YoY'.
        period: YYYY-MM current-period anchor. Default = latest month in
            data.json that has rows.
        top_n: size of top-positive and top-negative lists (3–20, default 5).
        category_filter: optional substring — restrict comparison to
            categories whose `category` string contains this (case-insensitive).
    """
    m_raw = (mode or "MoM").strip()
    m = "YoY" if m_raw.lower() == "yoy" else ("MoM" if m_raw.lower() == "mom" else m_raw)
    if m not in VALID_MODES:
        return _err(
            f"mode must be 'MoM' or 'YoY', got {mode!r}",
            hint="MoM = 1 თვე უკან, YoY = 12 თვე უკან",
        )

    try:
        n = int(top_n) if top_n is not None else DEFAULT_TOP_N
    except (TypeError, ValueError):
        return _err(f"top_n must be integer, got {top_n!r}")
    n = max(MIN_TOP_N, min(MAX_TOP_N, n))

    try:
        data = data_loader()
    except Exception as exc:
        return _err(f"მონაცემების ჩატვირთვა ვერ მოხერხდა: {exc}")

    rs = (data or {}).get("retail_sales") or {}
    rows = rs.get("by_category_by_month") or []
    if not rows:
        return _err(
            "retail_sales.by_category_by_month ცარიელია — pipeline regen საჭიროა.",
            hint="გაუშვი `python generate_dashboard_data.py`",
        )

    by_period = _index_by_period(rows)

    current = period or _latest_period(by_period)
    if not current or current not in by_period:
        return _err(
            f"მიმდინარე პერიოდი ვერ მოიძებნა: {period!r}",
            hint=f"ხელმისაწვდომი თვეები: {sorted(by_period.keys())[-6:]}",
        )

    compare = _prev_period(current, m)
    if not compare or compare not in by_period:
        return _err(
            f"შესადარებელი პერიოდი ვერ მოიძებნა: {compare!r} ({m})",
            hint="ცოტა მონაცემია მოცემული mode-ისთვის",
        )

    cur_by_cat = by_period[current]
    cmp_by_cat = by_period[compare]

    cat_filter_lc = (category_filter or "").strip().lower() or None

    entries: List[Dict[str, Any]] = []
    suspicious: List[str] = []
    totals = {
        "revenue_current_ge": 0.0,
        "revenue_compare_ge": 0.0,
        "delta_revenue_ge": 0.0,
        "price_effect_ge": 0.0,
        "volume_effect_ge": 0.0,
        "mix_effect_ge": 0.0,
    }

    union_keys = set(cur_by_cat) | set(cmp_by_cat)
    categories_evaluated = 0
    for key in union_keys:
        cur = cur_by_cat.get(key) or {}
        cmp = cmp_by_cat.get(key) or {}
        category_label = str(cur.get("category") or cmp.get("category") or key)
        if cat_filter_lc and cat_filter_lc not in category_label.lower():
            continue
        rev_c = float(cur.get("revenue_ge") or 0)
        rev_p = float(cmp.get("revenue_ge") or 0)
        # Noise floor — skip pairs where BOTH sides are negligible.
        if rev_c < MIN_REVENUE_FOR_COMPARISON_GE and rev_p < MIN_REVENUE_FOR_COMPARISON_GE:
            continue

        if _is_suspicious(cur) or _is_suspicious(cmp):
            suspicious.append(category_label)
            continue

        decomp = _decompose(cur, cmp)
        entry = {
            "category": category_label,
            "normalized_category": str(cur.get("normalized_category") or cmp.get("normalized_category") or key),
            **decomp,
        }
        entries.append(entry)
        categories_evaluated += 1
        totals["revenue_current_ge"] += decomp["revenue_current_ge"]
        totals["revenue_compare_ge"] += decomp["revenue_compare_ge"]
        totals["delta_revenue_ge"] += decomp["delta_revenue_ge"]
        totals["price_effect_ge"] += decomp["price_effect_ge"]
        totals["volume_effect_ge"] += decomp["volume_effect_ge"]
        totals["mix_effect_ge"] += decomp["mix_effect_ge"]

    totals_delta_pct = _safe_div(
        totals["delta_revenue_ge"], abs(totals["revenue_compare_ge"]) or 1.0
    ) * 100.0
    totals_rounded = {k: round(v, 2) for k, v in totals.items()}
    totals_rounded["delta_pct"] = round(totals_delta_pct, 2)

    entries_sorted_desc = sorted(entries, key=lambda e: e["delta_revenue_ge"], reverse=True)
    entries_sorted_asc = sorted(entries, key=lambda e: e["delta_revenue_ge"])
    top_positive = [e for e in entries_sorted_desc if e["delta_revenue_ge"] > 0][:n]
    top_negative = [e for e in entries_sorted_asc if e["delta_revenue_ge"] < 0][:n]

    total_arrow = "📈" if totals["delta_revenue_ge"] > 0 else ("📉" if totals["delta_revenue_ge"] < 0 else "—")
    top_pos_summary = (
        f"top+: **{top_positive[0]['category']}** "
        f"({top_positive[0]['delta_revenue_ge']:+,.0f} ₾, driver={top_positive[0]['driver']})"
        if top_positive else "top+: —"
    )
    top_neg_summary = (
        f"top−: **{top_negative[0]['category']}** "
        f"({top_negative[0]['delta_revenue_ge']:+,.0f} ₾, driver={top_negative[0]['driver']})"
        if top_negative else "top−: —"
    )

    summary_ka = (
        f"**{m}: {current} vs {compare}** · {total_arrow} "
        f"ბრუნვა **{totals['delta_revenue_ge']:+,.0f} ₾** "
        f"({totals_rounded['delta_pct']:+.1f}%) · "
        f"price_effect **{totals['price_effect_ge']:+,.0f} ₾** · "
        f"volume_effect **{totals['volume_effect_ge']:+,.0f} ₾** · "
        f"{top_pos_summary} · {top_neg_summary} · "
        f"{categories_evaluated} category · "
        f"⚠️ {len(suspicious)} suspicious გადავამოწმოთ"
    )

    notes: List[str] = [
        "price_effect = Δavg_price × qty_compare (რამდენი ₾ მოიტანა ფასის ცვლილებამ)",
        "volume_effect = Δqty × avg_price_compare (რამდენი ₾ მოიტანა რაოდენობის ცვლილებამ)",
        "mix_effect = Δavg_price × Δqty (ორივე მიმართულებით ცვლილების ინტერაქცია)",
        "identity: price_effect + volume_effect + mix_effect ≡ delta_revenue (ცვლილების სრული დეკომპოზიცია)",
    ]
    if suspicious:
        notes.append(
            f"⚠️ {len(suspicious)} კატეგორია გამოტოვდა margin-ის out-of-range-ის გამო "
            f"(< {SUSPICIOUS_MARGIN_PCT_LOW}% ან > {SUSPICIOUS_MARGIN_PCT_HIGH}%) — "
            f"data quality-ის შემოწმება საჭიროა Excel-ში"
        )
    notes.append(
        "ნოის flor: ≤ 100 ₾-ზე ორივე პერიოდში კატეგორიები გამოტოვდა (one-off-ები არ აჭარბებენ)"
    )

    return {
        "source": "data.json:retail_sales.by_category_by_month",
        "mode": m,
        "current_period": current,
        "compare_period": compare,
        "categories_compared": categories_evaluated,
        "categories_skipped_suspicious": len(suspicious),
        "totals": totals_rounded,
        "top_positive": top_positive,
        "top_negative": top_negative,
        "suspicious": suspicious,
        "summary_ka": summary_ka,
        "notes_ka": notes,
    }
