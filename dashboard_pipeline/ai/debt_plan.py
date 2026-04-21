"""Phase 4A — Debt Repayment Plan Builder.

AUTONOMOUS strategic advisor tool. Given the data.json snapshot alone
(no mandatory user input), composes a 1-2 month debt repayment plan
covering 3-5 AI-auto-detected critical suppliers + historical baseline
minimums for the rest. Designed per Phase 4 philosophy: AI proposes
first, user approves/edits — never "ask first".

Return contract (success)::

    {
        "as_of_date": "YYYY-MM-DD",
        "plan_duration_months": int,
        "forecast": {
            "monthly_inflow_ge": float,
            "method": str,
            "low_ge": float, "high_ge": float,
            "trend": "stable" | "growing" | "declining" | "insufficient_history",
            "window_months": [str, ...],
        },
        "priority_suppliers": [
            {
                "tax_id": str, "org": str,
                "total_debt_ge": float, "total_effective_ge": float,
                "days_since_last": int | None, "aging_bucket": str,
                "waybill_count": int,
                "criticality_score": float,      # 0-1
                "criticality_reasons": [str, ...],
                "historical_monthly_paid_ge": float,
                "recommended_monthly_payment_ge": float,
                "recommended_weekly_payment_ge": float,
                "days_to_clear_est": int,
                "confidence_label": "🟢 მაღალი" | "🟡 საშუალო" | "⚪ დაბალი",
                "rationale_ka": str,
            }, ...
        ],
        "non_priority_summary": {
            "supplier_count": int,
            "total_baseline_monthly_ge": float,
            "average_per_supplier_ge": float,
            "note_ka": str,
        },
        "allocation_summary": {
            "priority_monthly_ge": float,
            "non_priority_monthly_ge": float,
            "buffer_ge": float,
            "buffer_pct": float,
            "forecast_ge": float,
            "sustainable": bool,
        },
        "risks": [str, ...],
        "summary_ka": str,
        "notes": [str, ...],
    }

Failure::

    {"error": "<Georgian msg>", "hint": "<actionable>"}

Ambiguous priority supplier::

    {
        "error": "ვერ დავადგინე რომელი მომწოდებელი გულისხმობდი.",
        "ambiguous": [{"input": "კოკა", "candidates": [
            {"tax_id": "...", "org": "...", "total_debt_ge": float}, ...
        ]}]
    }
"""

from __future__ import annotations

import logging
import math
import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public contract constants
# ---------------------------------------------------------------------------

DEFAULT_PLAN_DURATION_MONTHS = 2
MIN_PLAN_DURATION_MONTHS = 1
MAX_PLAN_DURATION_MONTHS = 6

DEFAULT_MAX_PRIORITY_COUNT = 5
MIN_PRIORITY_COUNT = 2
MAX_PRIORITY_COUNT = 8

# Inflow-forecast window (months of monthly_pnl to average over).
FORECAST_LOOKBACK_MONTHS = 3
FORECAST_UNCERTAINTY_PCT = 10.0  # ±10% bracket around the point estimate.
TREND_DELTA_PCT = 5.0  # >5% change between halves ⇒ growing/declining.

# Criticality weights (must sum to 1.0).
# Re-balanced 2026-04-21: debt amount is now the dominant factor so a
# 313K ₾ active supplier ranks above a 435 ₾ zombie (1,400-day dormant).
WEIGHT_DEBT = 0.50
WEIGHT_AGING = 0.15
WEIGHT_FREQUENCY = 0.20
WEIGHT_DYSFUNCTION = 0.15

# Suppliers with no delivery for longer than this threshold are treated as
# "dormant" — they're excluded from the priority pool entirely and flow
# into the non-priority baseline (relationship is already frozen; a small
# residual debt is not a cash-flow priority).
ACTIVE_CUTOFF_DAYS = 365

# Payment-boost factors applied to historical monthly payment to get
# the "recommended" priority payment, scaled by criticality_score.
MIN_BOOST = 1.20
MAX_BOOST = 1.80

# Safe default boost for suppliers without any historical payment record.
FALLBACK_MIN_MONTHLY_PAYMENT = 1000.0

# Non-priority baseline minimum = historical_monthly × this factor.
NON_PRIORITY_BASELINE_FACTOR = 0.90

# Sustainability threshold: total monthly outflow must stay ≤ this fraction
# of forecast_inflow to qualify the plan as "sustainable".
SUSTAINABLE_PCT_OF_INFLOW = 0.90

# Buffer is required to be at least this % of forecast_inflow; below it,
# we emit an amber warning in `risks`.
MIN_BUFFER_PCT = 5.0

CONFIDENCE_HIGH = "🟢 მაღალი"
CONFIDENCE_MID = "🟡 საშუალო"
CONFIDENCE_LOW = "⚪ დაბალი"


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(out) or math.isinf(out):
        return 0.0
    return out


def _clamp_int(raw: Any, default: int, lo: int, hi: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


# ---------------------------------------------------------------------------
# Inflow forecast
# ---------------------------------------------------------------------------

def _extract_monthly_net_series(
    monthly_pnl: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    clean: List[Dict[str, Any]] = []
    for row in monthly_pnl or []:
        if not isinstance(row, dict):
            continue
        month = str(row.get("month") or "").strip()
        if not month:
            continue
        total = row.get("total") or {}
        income = _safe_float(total.get("pos_income"))
        expenses = _safe_float(total.get("expenses"))
        net = _safe_float(total.get("net"))
        clean.append(
            {
                "month": month,
                "income_ge": round(income, 2),
                "expense_ge": round(expenses, 2),
                "net_ge": round(net, 2),
            }
        )
    clean.sort(key=lambda r: r["month"])
    return clean


def _classify_inflow_trend(series: List[Dict[str, Any]]) -> str:
    """Compare the latest 3 months vs the prior 3 months income."""
    if len(series) < FORECAST_LOOKBACK_MONTHS * 2:
        return "insufficient_history"
    recent = series[-FORECAST_LOOKBACK_MONTHS:]
    prior = series[-FORECAST_LOOKBACK_MONTHS * 2 : -FORECAST_LOOKBACK_MONTHS]
    recent_avg = sum(r["income_ge"] for r in recent) / len(recent)
    prior_avg = sum(r["income_ge"] for r in prior) / len(prior)
    if prior_avg <= 0:
        return "stable"
    pct = (recent_avg - prior_avg) * 100.0 / prior_avg
    if pct > TREND_DELTA_PCT:
        return "growing"
    if pct < -TREND_DELTA_PCT:
        return "declining"
    return "stable"


def _forecast_monthly_inflow(
    series: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if len(series) < FORECAST_LOOKBACK_MONTHS:
        return None
    window = series[-FORECAST_LOOKBACK_MONTHS:]
    point = sum(w["income_ge"] for w in window) / len(window)
    point = round(max(point, 0.0), 2)
    bracket = round(point * FORECAST_UNCERTAINTY_PCT / 100.0, 2)
    trend = _classify_inflow_trend(series)
    method = (
        f"{FORECAST_LOOKBACK_MONTHS}-თვიანი moving average "
        f"({window[0]['month']} → {window[-1]['month']}); "
        f"±{FORECAST_UNCERTAINTY_PCT:.0f}% uncertainty bracket"
    )
    return {
        "monthly_inflow_ge": point,
        "low_ge": round(max(point - bracket, 0.0), 2),
        "high_ge": round(point + bracket, 2),
        "trend": trend,
        "method": method,
        "window_months": [w["month"] for w in window],
    }


# ---------------------------------------------------------------------------
# Active-suppliers extraction + criticality ranking
# ---------------------------------------------------------------------------

def _active_debt_suppliers(
    supplier_aging: Any,
) -> List[Dict[str, Any]]:
    """Return supplier rows with positive debt.

    Accepts both shapes:
    - list of supplier rows (production ``data.json`` layout)
    - dict with ``suppliers`` key (legacy / test fixtures)
    """
    if isinstance(supplier_aging, list):
        raw: List[Any] = supplier_aging
    elif isinstance(supplier_aging, dict):
        raw = supplier_aging.get("suppliers") or []
    else:
        return []
    out: List[Dict[str, Any]] = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        if _safe_float(s.get("total_debt")) <= 0:
            continue
        out.append(s)
    return out


def _is_dormant_supplier(s: Dict[str, Any]) -> bool:
    """A supplier is dormant when the last delivery is older than
    ``ACTIVE_CUTOFF_DAYS`` (default 365). Dormant suppliers are quarantined
    out of the auto-detected priority pool — their residual debt goes to
    the non-priority baseline instead.

    Returns ``False`` for suppliers with missing or non-numeric
    ``days_since_last`` (unknown recency defaults to active).
    """
    days = s.get("days_since_last") if isinstance(s, dict) else None
    if days is None:
        return False
    try:
        return float(days) > ACTIVE_CUTOFF_DAYS
    except (TypeError, ValueError):
        return False


def _supplier_active_months(s: Dict[str, Any]) -> float:
    """Months since first_waybill_date; floor at 1."""
    first = str(s.get("first_waybill_date") or "").strip()
    last = str(s.get("last_waybill_date") or "").strip()
    if not first:
        return 1.0
    try:
        y1, m1, _ = first.split("-")
        y2, m2, _ = last.split("-") if last else first.split("-")
        months = (int(y2) - int(y1)) * 12 + (int(m2) - int(m1)) + 1
    except (ValueError, AttributeError):
        return 1.0
    return max(float(months), 1.0)


def _historical_monthly_paid(s: Dict[str, Any]) -> float:
    """Total paid (strict_bank + manual) divided by active months."""
    total_paid = _safe_float(s.get("total_paid"))
    months = _supplier_active_months(s)
    return total_paid / months


def _historical_monthly_billed(s: Dict[str, Any]) -> float:
    total_billed = _safe_float(s.get("total_effective"))
    months = _supplier_active_months(s)
    return total_billed / months


def _supplier_waybill_frequency(s: Dict[str, Any]) -> float:
    """Waybills per month (delivery cadence)."""
    waybill_count = int(_safe_float(s.get("waybill_count")))
    months = _supplier_active_months(s)
    return waybill_count / months


def _payment_dysfunction_ratio(s: Dict[str, Any]) -> float:
    """1 - (paid / billed); higher value = more unpaid portion; clamped [0, 1]."""
    billed = _safe_float(s.get("total_effective"))
    paid = _safe_float(s.get("total_paid"))
    if billed <= 0:
        return 0.0
    ratio = paid / billed
    return max(0.0, min(1.0 - ratio, 1.0))


def _normalize_series(values: List[float]) -> List[float]:
    if not values:
        return []
    mx = max(values)
    if mx <= 0:
        return [0.0 for _ in values]
    return [v / mx for v in values]


def _score_criticality(
    suppliers: List[Dict[str, Any]],
) -> List[Tuple[Dict[str, Any], float, List[str]]]:
    """Return (supplier, score, reasons) tuples, ranked desc by score."""
    if not suppliers:
        return []

    debts = [_safe_float(s.get("total_debt")) for s in suppliers]
    ages = [
        float(s.get("days_since_last") or 0) for s in suppliers
    ]  # larger = more stale
    freqs = [_supplier_waybill_frequency(s) for s in suppliers]
    dys = [_payment_dysfunction_ratio(s) for s in suppliers]

    debts_n = _normalize_series(debts)
    ages_n = _normalize_series(ages)
    freqs_n = _normalize_series(freqs)
    dys_n = _normalize_series(dys)  # already 0-1 but normalize vs peer max

    ranked: List[Tuple[Dict[str, Any], float, List[str]]] = []
    for idx, s in enumerate(suppliers):
        score = (
            WEIGHT_DEBT * debts_n[idx]
            + WEIGHT_AGING * ages_n[idx]
            + WEIGHT_FREQUENCY * freqs_n[idx]
            + WEIGHT_DYSFUNCTION * dys_n[idx]
        )
        reasons: List[str] = []
        if debts_n[idx] >= 0.5:
            reasons.append(f"დიდი ვალი ({debts[idx]:,.0f} ₾)")
        if ages_n[idx] >= 0.5 and ages[idx] > 60:
            reasons.append(f"ძველი ვალი ({int(ages[idx])} დღე)")
        if freqs_n[idx] >= 0.5 and freqs[idx] >= 2.0:
            reasons.append(
                f"ხშირი მიწოდება ({freqs[idx]:.1f}/თვე — კრიტიკული supply)"
            )
        if dys_n[idx] >= 0.5 and dys[idx] >= 0.4:
            pct = dys[idx] * 100.0
            reasons.append(f"გადახდის წილი დაბალი ({100 - pct:.0f}% paid)")
        if not reasons:
            reasons.append("შერეული ფაქტორები")
        ranked.append((s, round(score, 4), reasons))

    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Supplier resolution (user-provided priority list)
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def _normalize_name(text: str) -> str:
    return _WS_RE.sub(" ", str(text or "").strip().lower())


def _resolve_priority_inputs(
    inputs: List[str],
    all_suppliers: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Try to match each user-provided token (tax_id or name fragment)
    to exactly one supplier. Returns (resolved, ambiguous)."""
    resolved: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []
    for raw in inputs or []:
        token = str(raw or "").strip()
        if not token:
            continue
        hits: List[Dict[str, Any]] = []
        if token.isdigit():
            for s in all_suppliers:
                if str(s.get("tax_id") or "").strip() == token:
                    hits.append(s)
                    break
        if not hits:
            needle = _normalize_name(token)
            for s in all_suppliers:
                haystack = _normalize_name(s.get("org") or "")
                if needle and needle in haystack:
                    hits.append(s)
        if len(hits) == 1:
            resolved.append(hits[0])
        elif len(hits) == 0:
            ambiguous.append({"input": token, "candidates": []})
        else:
            top = sorted(
                hits,
                key=lambda s: _safe_float(s.get("total_debt")),
                reverse=True,
            )[:5]
            ambiguous.append(
                {
                    "input": token,
                    "candidates": [
                        {
                            "tax_id": str(s.get("tax_id") or ""),
                            "org": str(s.get("org") or ""),
                            "total_debt_ge": round(
                                _safe_float(s.get("total_debt")), 2
                            ),
                        }
                        for s in top
                    ],
                }
            )
    return resolved, ambiguous


# ---------------------------------------------------------------------------
# Plan composition
# ---------------------------------------------------------------------------

def _recommend_priority_payment(
    *,
    total_debt: float,
    historical_monthly_paid: float,
    criticality_score: float,
    plan_duration_months: int,
) -> Tuple[float, float, int]:
    """Return (monthly_payment, weekly_payment, days_to_clear_est).

    Priority recommendation logic:
    1. Start with historical monthly payment × boost factor (scaled by
       criticality).
    2. If that rate would not clear the debt within ``plan_duration_months``,
       bump up to ``total_debt / plan_duration_months`` instead.
    3. Floor at ``FALLBACK_MIN_MONTHLY_PAYMENT`` if the supplier has no
       meaningful history.
    """
    boost = MIN_BOOST + (MAX_BOOST - MIN_BOOST) * max(
        0.0, min(criticality_score, 1.0)
    )
    base = historical_monthly_paid * boost
    required = total_debt / max(plan_duration_months, 1)
    recommended = max(base, required, FALLBACK_MIN_MONTHLY_PAYMENT)
    # Round to the nearest 100 ₾ for cleanliness.
    recommended = round(recommended / 100.0) * 100.0
    weekly = round(recommended / 4.0 / 50.0) * 50.0
    if recommended > 0:
        days = int(round(total_debt / recommended * 30.4375))
    else:
        days = 0
    return float(recommended), float(weekly), days


def _confidence_for_supplier(s: Dict[str, Any]) -> str:
    """Confidence is HIGH when we have ≥12 months of history; MID 3-11; LOW <3."""
    months = _supplier_active_months(s)
    if months >= 12:
        return CONFIDENCE_HIGH
    if months >= 3:
        return CONFIDENCE_MID
    return CONFIDENCE_LOW


def _build_priority_entry(
    s: Dict[str, Any],
    score: float,
    reasons: List[str],
    plan_duration_months: int,
) -> Dict[str, Any]:
    total_debt = round(_safe_float(s.get("total_debt")), 2)
    billed = round(_safe_float(s.get("total_effective")), 2)
    historical_monthly = round(_historical_monthly_paid(s), 2)
    monthly, weekly, days = _recommend_priority_payment(
        total_debt=total_debt,
        historical_monthly_paid=historical_monthly,
        criticality_score=score,
        plan_duration_months=plan_duration_months,
    )
    rationale_bits: List[str] = list(reasons)
    if historical_monthly > 0:
        growth = monthly / historical_monthly
        if growth >= 1.20:
            rationale_bits.append(
                f"ჩემი რჩევა ისტორიულზე {(growth - 1) * 100:.0f}%-ით მეტია — გეგმა {plan_duration_months} თვეში დახურვას ითხოვს"
            )
    else:
        rationale_bits.append(
            "ისტორიული გადახდა არ არის; ვიწყებთ minimum floor-ით"
        )
    return {
        "tax_id": str(s.get("tax_id") or ""),
        "org": str(s.get("org") or ""),
        "total_debt_ge": total_debt,
        "total_effective_ge": billed,
        "days_since_last": s.get("days_since_last"),
        "aging_bucket": str(s.get("aging_bucket") or ""),
        "waybill_count": int(_safe_float(s.get("waybill_count"))),
        "criticality_score": round(float(score), 4),
        "criticality_reasons": list(reasons),
        "historical_monthly_paid_ge": historical_monthly,
        "recommended_monthly_payment_ge": round(monthly, 2),
        "recommended_weekly_payment_ge": round(weekly, 2),
        "days_to_clear_est": days,
        "confidence_label": _confidence_for_supplier(s),
        "rationale_ka": " | ".join(rationale_bits),
    }


def _build_non_priority_summary(
    non_priority: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_baseline = 0.0
    for s in non_priority:
        total_baseline += _historical_monthly_paid(s) * NON_PRIORITY_BASELINE_FACTOR
    total_baseline = round(total_baseline, 2)
    avg = round(
        total_baseline / len(non_priority) if non_priority else 0.0, 2
    )
    return {
        "supplier_count": len(non_priority),
        "total_baseline_monthly_ge": total_baseline,
        "average_per_supplier_ge": avg,
        "note_ka": (
            f"ბოლო მასავი ყოფილი გადახდის {int(NON_PRIORITY_BASELINE_FACTOR * 100)}% — "
            "მიწოდების გაჩერების რისკი ამ ტემპზე არ არის"
        ),
    }


def _compose_summary_ka(
    priority_entries: List[Dict[str, Any]],
    allocation: Dict[str, Any],
    forecast: Dict[str, Any],
    plan_duration_months: int,
) -> str:
    if not priority_entries:
        return "პრიორიტეტული ვალი ამჟამად არ არის — გეგმა საჭირო არ არის."
    parts: List[str] = []
    for p in priority_entries[:3]:
        parts.append(
            f"{p['org'].split(' ')[0][:20]} {p['days_to_clear_est']} დღე"
        )
    priority_pct = round(
        allocation["priority_monthly_ge"] * 100.0 / max(forecast["monthly_inflow_ge"], 1.0),
        1,
    )
    sustainable = "✅ მდგრადია" if allocation["sustainable"] else "⚠️ არამდგრადია"
    return (
        f"📋 {plan_duration_months}-თვიანი გეგმა — {len(priority_entries)} პრიორიტეტი: "
        + ", ".join(parts)
        + f". პრიორიტეტებზე თვიურად {allocation['priority_monthly_ge']:,.0f} ₾ "
        + f"({priority_pct}% forecast-ის). {sustainable}."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_debt_repayment_plan(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    priority_suppliers: Optional[List[str]] = None,
    plan_duration_months: Any = None,
    max_priority_count: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Compose a debt repayment plan.

    Parameters
    ----------
    data_loader:
        Zero-argument callable returning the parsed ``data.json`` dict.
    priority_suppliers:
        Optional list of supplier names or tax IDs to prioritize. When
        ``None``, the tool auto-detects the top-N most critical suppliers
        by a 4-factor score (debt / aging / frequency / dysfunction).
    plan_duration_months:
        Target window (months) to clear priority debts (1..6, default 2).
    max_priority_count:
        Upper bound on auto-detected priority suppliers (2..8, default 5).
        Ignored when the caller specifies ``priority_suppliers`` explicitly.
    today:
        Override "today" for deterministic tests.
    """
    # --- Argument coercion ------------------------------------------------
    duration = _clamp_int(
        plan_duration_months,
        DEFAULT_PLAN_DURATION_MONTHS,
        MIN_PLAN_DURATION_MONTHS,
        MAX_PLAN_DURATION_MONTHS,
    )
    cap = _clamp_int(
        max_priority_count,
        DEFAULT_MAX_PRIORITY_COUNT,
        MIN_PRIORITY_COUNT,
        MAX_PRIORITY_COUNT,
    )
    if today is None:
        today = date.today()
    elif not isinstance(today, date):
        return {
            "error": "today პარამეტრი უნდა იყოს date ობიექტი ან None.",
            "hint": "ჩვეულებრივ ეს არ გადაეცემა.",
        }

    # --- Load data --------------------------------------------------------
    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("debt_plan data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა.",
            "hint": "გადაამოწმე generate_dashboard_data.py-ს output.",
        }

    suppliers_with_debt = _active_debt_suppliers(data.get("supplier_aging") or {})
    if not suppliers_with_debt:
        return {
            "error": "მომწოდებლებს ვალი ამჟამად არ აქვთ — გეგმა არ სჭირდება.",
            "hint": "შეამოწმე supplier_aging — შესაძლოა ყველა ჩამოწერილია.",
        }

    # --- Inflow forecast --------------------------------------------------
    series = _extract_monthly_net_series(data.get("monthly_pnl") or [])
    forecast = _forecast_monthly_inflow(series)
    if forecast is None:
        return {
            "error": (
                f"monthly_pnl-ში {FORECAST_LOOKBACK_MONTHS} თვის ისტორია "
                f"ვერ ვიპოვე (არსებული: {len(series)} თვე)."
            ),
            "hint": "შეამოწმე data.json — monthly_pnl უნდა იყოს სავსე.",
        }

    # --- Priority resolution ---------------------------------------------
    priority_list: List[Dict[str, Any]] = []
    priority_inputs = priority_suppliers if isinstance(priority_suppliers, list) else None

    if priority_inputs:
        resolved, ambiguous = _resolve_priority_inputs(
            priority_inputs, suppliers_with_debt
        )
        if ambiguous:
            return {
                "error": "ვერ დავადგინე რომელი მომწოდებელი გულისხმობდი.",
                "hint": "მიუთითე უფრო ზუსტად (სრული სახელი ან tax_id).",
                "ambiguous": ambiguous,
            }
        priority_list = resolved

    ranked = _score_criticality(suppliers_with_debt)

    if not priority_list:
        # Auto-detect: take top N by criticality score, but skip dormant
        # suppliers (no delivery for ACTIVE_CUTOFF_DAYS+). Those are counted
        # in the non-priority baseline instead — a 1,400-day-old 435 ₾ debt
        # is not a cash-flow priority.
        priority_list = [
            entry[0]
            for entry in ranked
            if not _is_dormant_supplier(entry[0])
        ][:cap]

    # Build name→(score, reasons) lookup from ranked data (covers both paths).
    score_lookup: Dict[str, Tuple[float, List[str]]] = {}
    for s, score, reasons in ranked:
        key = (str(s.get("tax_id") or "") + "|" + str(s.get("org") or "")).lower()
        score_lookup[key] = (score, reasons)

    priority_entries: List[Dict[str, Any]] = []
    priority_tax_ids: set[str] = set()
    for s in priority_list:
        key = (str(s.get("tax_id") or "") + "|" + str(s.get("org") or "")).lower()
        score, reasons = score_lookup.get(key, (0.0, ["სპეციფიცირებული პრიორიტეტი"]))
        priority_entries.append(
            _build_priority_entry(s, score, reasons, duration)
        )
        tid = str(s.get("tax_id") or "").strip()
        if tid:
            priority_tax_ids.add(tid)

    priority_entries.sort(
        key=lambda e: e["criticality_score"], reverse=True
    )

    # --- Non-priority summary --------------------------------------------
    non_priority = [
        s
        for s in suppliers_with_debt
        if str(s.get("tax_id") or "").strip() not in priority_tax_ids
    ]
    non_priority_summary = _build_non_priority_summary(non_priority)

    # --- Allocation + risks ----------------------------------------------
    priority_monthly = round(
        sum(p["recommended_monthly_payment_ge"] for p in priority_entries),
        2,
    )
    non_priority_monthly = non_priority_summary["total_baseline_monthly_ge"]
    forecast_inflow = forecast["monthly_inflow_ge"]
    total_outflow = round(priority_monthly + non_priority_monthly, 2)
    buffer = round(forecast_inflow - total_outflow, 2)
    buffer_pct = (
        round(buffer * 100.0 / forecast_inflow, 2) if forecast_inflow > 0 else 0.0
    )
    sustainable = total_outflow <= SUSTAINABLE_PCT_OF_INFLOW * forecast_inflow

    allocation = {
        "priority_monthly_ge": priority_monthly,
        "non_priority_monthly_ge": non_priority_monthly,
        "buffer_ge": buffer,
        "buffer_pct": buffer_pct,
        "forecast_ge": forecast_inflow,
        "sustainable": sustainable,
    }

    risks: List[str] = []
    if not sustainable:
        risks.append(
            f"⚠️ პრიორიტეტები + baseline = {total_outflow:,.0f} ₾/თვე აღემატება "
            f"forecast-ის 90%-ს ({0.9 * forecast_inflow:,.0f} ₾). მინდა "
            f"ოდენობები შევამციროთ ან გეგმის ვადა გავაგრძელოთ."
        )
    if buffer_pct < MIN_BUFFER_PCT:
        risks.append(
            f"⚠️ buffer მხოლოდ {buffer_pct:.1f}% — თუ forecast ცდება "
            f"±{FORECAST_UNCERTAINTY_PCT:.0f}%-ით, გეგმა ვერ გავა."
        )
    for p in priority_entries:
        if (p.get("days_since_last") or 0) > 120:
            risks.append(
                f"🔴 {p['org'].split(' ')[0][:30]} — {p['days_since_last']} დღე "
                "არ მიმდინარეობს მიწოდება; თუ არ გააბრუნებ, შეიძლება relationship დაკარგო."
            )
    if forecast["trend"] == "declining":
        risks.append(
            "📉 შემოსავალი ბოლო 3 თვეში მცირდება — forecast-ზე ოპტიმისტი ნუ იქნები."
        )

    # --- Notes ------------------------------------------------------------
    notes: List[str] = [
        f"forecast: {forecast['method']}",
        f"კრიტიკულობის წონები: ვალი {WEIGHT_DEBT}, ასაკი {WEIGHT_AGING}, "
        f"მიწოდების სიხშირე {WEIGHT_FREQUENCY}, გადახდის შეფერხება {WEIGHT_DYSFUNCTION}",
        f"ყოველი პრიორიტეტის ტემპი = ისტორიული × {MIN_BOOST:.1f}-{MAX_BOOST:.1f} "
        f"(კრიტიკულობის ქულის მიხედვით) ან debt÷duration — რომელიც მეტია",
        f"baseline არაპრიორიტეტისთვის = ისტორიული × {int(NON_PRIORITY_BASELINE_FACTOR * 100)}%",
    ]
    if forecast["trend"] == "insufficient_history":
        notes.append(
            "ⓘ forecast trend ვერ გამოვთვალე — monthly_pnl-ში 6+ თვე არ არის."
        )

    summary_ka = _compose_summary_ka(
        priority_entries, allocation, forecast, duration
    )

    return {
        "as_of_date": today.isoformat(),
        "plan_duration_months": duration,
        "forecast": forecast,
        "priority_suppliers": priority_entries,
        "non_priority_summary": non_priority_summary,
        "allocation_summary": allocation,
        "risks": risks,
        "summary_ka": summary_ka,
        "notes": notes,
    }
