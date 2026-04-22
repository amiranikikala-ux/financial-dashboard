"""Phase 2.2 — Scenario Simulator (what-if analysis on monthly P&L).

Runs a deterministic what-if against a baseline month pulled from
``monthly_pnl``. Accepts price / volume / expense / fixed-cost knobs and
returns baseline vs scenario side-by-side plus a decision indicator.

Design
------
* **Baseline**: pick a real month from ``monthly_pnl`` (explicit ``YYYY-MM``,
  the default ``"last_month"``, or the smoothed ``"last_3_avg"``). This is
  not a forecast — the baseline is ground-truth history so the user knows
  exactly what they're deviating from.
* **Price × volume coupling**: retail textbook. When ``price_change_pct``
  is supplied without an explicit ``volume_change_pct``, we auto-apply
  price elasticity (default -0.8, price-elastic like grocery staples):
  ``volume_change = price_change × elasticity``.
* **Variable vs fixed cost**: retail expenses are roughly split
  ``cogs_share`` (default 0.5) variable / rest fixed. Volume change scales
  only the variable part. ``expense_change_pct`` is applied on top of the
  scaled total. ``fixed_cost_delta_ge`` adds one-off fixed additions (new
  equipment, additional rent, …).
* **Decision indicator**: 🟢 PROFIT_IMPROVE (net↑ by ≥2% of baseline
  revenue), 🔴 PROFIT_ERODE (net↓ by ≥2%), 🟡 NEUTRAL otherwise. The 2%
  band avoids calling a rounding-error delta "improvement".

Return contract (success)::

    {
        "source": "data.json:monthly_pnl (what-if simulator)",
        "as_of_date": "YYYY-MM-DD",
        "base_period_used": "YYYY-MM" | "last_3_avg",
        "store": "total" | "ოზურგეთი" | "დვაბზუ",
        "scenario_label": str,
        "baseline": {"revenue_ge": float, "expenses_ge": float,
                     "net_ge": float, "margin_pct": float},
        "scenario": {"revenue_ge": float, "expenses_ge": float,
                     "net_ge": float, "margin_pct": float},
        "deltas":   {"revenue_ge": float, "expenses_ge": float,
                     "net_ge": float, "margin_pp": float},
        "adjustments_applied": {
            "price_change_pct": float,
            "volume_change_pct": float,
            "volume_implied_by_elasticity": bool,
            "expense_change_pct": float,
            "fixed_cost_delta_ge": float,
            "elasticity_used": float,
            "cogs_share": float,
        },
        "decision_indicator": "🟢 PROFIT_IMPROVE" | "🟡 NEUTRAL" | "🔴 PROFIT_ERODE",
        "summary_ka": str,
        "notes": [str, ...],
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from dashboard_pipeline.ai.cash_runway import _extract_monthly_series
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

DEFAULT_PRICE_ELASTICITY = -0.8
DEFAULT_COGS_SHARE = 0.5

#: Minimum absolute net delta (as a fraction of baseline revenue) required
#: to call a scenario "improve" or "erode". Smaller deltas are "neutral".
DECISION_BAND_PCT = 2.0

DECISION_IMPROVE = "🟢 PROFIT_IMPROVE"
DECISION_NEUTRAL = "🟡 NEUTRAL"
DECISION_ERODE = "🔴 PROFIT_ERODE"

SOURCE_LABEL = "data.json:monthly_pnl (what-if simulator)"

#: Retail cost-share sanity bounds. Outside this range we warn — retail COGS
#: share is almost always between 30% and 75% of total expenses.
COGS_SHARE_SANE_MIN = 0.1
COGS_SHARE_SANE_MAX = 0.95


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------

def _safe_pct(value: Any, default: float = 0.0) -> float:
    """Parse a percentage knob; None / junk → default."""
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out) or math.isinf(out):
        return default
    return out


def _safe_amount(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(out) or math.isinf(out):
        return default
    return out


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


def _resolve_cogs_share(raw: Any) -> float:
    value = _safe_pct(raw, default=DEFAULT_COGS_SHARE)
    # Accept both 0.5 (fraction) and 50 (percent) — saves the LLM from
    # guessing which convention the tool wants.
    if value > 1.0:
        value = value / 100.0
    # Clamp to [0, 1] to keep the math sound; warn if user passed
    # something outside the sanity band.
    return max(0.0, min(1.0, value))


def _resolve_elasticity(raw: Any) -> float:
    if raw is None:
        return DEFAULT_PRICE_ELASTICITY
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_PRICE_ELASTICITY
    if math.isnan(out) or math.isinf(out):
        return DEFAULT_PRICE_ELASTICITY
    # Clamp to a retail-realistic range. Elasticity > 0 means Giffen good,
    # which a small grocery shop is not. Elasticity < -5 is pathological.
    return max(-5.0, min(0.0, out))


# ---------------------------------------------------------------------------
# Baseline loader
# ---------------------------------------------------------------------------

def _metrics_for_row(
    row: Dict[str, Any],
    store: str,
) -> Optional[Dict[str, float]]:
    """Pull ``{revenue_ge, expenses_ge, net_ge}`` from one monthly_pnl row."""
    if not isinstance(row, dict):
        return None
    if store == STORE_TOTAL:
        block = row.get("total") or {}
    else:
        objects = row.get("objects") or {}
        block = objects.get(store) or {}
    if not isinstance(block, dict):
        return None
    try:
        revenue = float(block.get("pos_income") or 0.0)
        expenses = float(block.get("expenses") or 0.0)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(revenue) and math.isfinite(expenses)):
        return None
    return {
        "revenue_ge": round(revenue, 2),
        "expenses_ge": round(expenses, 2),
        "net_ge": round(revenue - expenses, 2),
    }


def _resolve_baseline(
    monthly_pnl: List[Dict[str, Any]],
    store: str,
    base_period: Any,
) -> Tuple[Optional[Dict[str, float]], Optional[str], Optional[str]]:
    """Return ``(baseline, period_label, error)``.

    Supports:
    * ``"last_month"`` / ``None`` — use the most recent month in the series.
    * ``"last_3_avg"`` — average the three most recent months.
    * explicit ``"YYYY-MM"`` — that specific month; error if not present.
    """
    if not isinstance(monthly_pnl, list) or not monthly_pnl:
        return None, None, (
            "`monthly_pnl` ცარიელია — scenario simulator-ს baseline ვერ აქვს."
        )
    label = None
    if base_period is None or base_period == "last_month":
        # Sort deterministically by month string (YYYY-MM sorts correctly).
        sortable = sorted(
            (row for row in monthly_pnl if isinstance(row, dict) and row.get("month")),
            key=lambda r: str(r["month"]),
        )
        if not sortable:
            return None, None, (
                "`monthly_pnl`-ში ვერ ვიპოვე მწკრივი, რომელსაც `month` ქონდეს."
            )
        chosen = sortable[-1]
        metrics = _metrics_for_row(chosen, store)
        if metrics is None:
            return None, None, (
                f"baseline თვე {chosen.get('month')} — store='{store}'-სთვის "
                f"ციფრები ვერ ამოვკრიბე."
            )
        label = str(chosen.get("month"))
        return metrics, label, None
    if base_period == "last_3_avg":
        sortable = sorted(
            (row for row in monthly_pnl if isinstance(row, dict) and row.get("month")),
            key=lambda r: str(r["month"]),
        )
        if len(sortable) < 3:
            return None, None, (
                f"`last_3_avg`-სთვის 3 თვის ისტორია სჭირდება "
                f"(არსებული: {len(sortable)})."
            )
        window = sortable[-3:]
        totals = {"revenue_ge": 0.0, "expenses_ge": 0.0, "net_ge": 0.0}
        for row in window:
            m = _metrics_for_row(row, store)
            if m is None:
                return None, None, (
                    f"baseline თვე {row.get('month')} — store='{store}'-სთვის "
                    f"ციფრები ვერ ამოვკრიბე."
                )
            for key in totals:
                totals[key] += m[key]
        avg = {key: round(val / 3.0, 2) for key, val in totals.items()}
        label = f"last_3_avg ({window[0]['month']}..{window[-1]['month']})"
        return avg, label, None
    if isinstance(base_period, str):
        # Explicit YYYY-MM.
        target = base_period.strip()
        for row in monthly_pnl:
            if isinstance(row, dict) and str(row.get("month") or "").strip() == target:
                metrics = _metrics_for_row(row, store)
                if metrics is None:
                    return None, None, (
                        f"baseline თვე {target} — store='{store}'-სთვის "
                        f"ციფრები ვერ ამოვკრიბე."
                    )
                return metrics, target, None
        return None, None, (
            f"`base_period`='{target}' ვერ ვიპოვე `monthly_pnl`-ში."
        )
    return None, None, (
        f"`base_period`='{base_period}' ფორმატი არასწორია. "
        f"მისაღები: 'last_month', 'last_3_avg', ან 'YYYY-MM'."
    )


# ---------------------------------------------------------------------------
# Scenario math
# ---------------------------------------------------------------------------

def _apply_scenario(
    baseline: Dict[str, float],
    *,
    price_change_pct: float,
    volume_change_pct: float,
    expense_change_pct: float,
    fixed_cost_delta_ge: float,
    cogs_share: float,
) -> Dict[str, float]:
    """Compute scenario metrics from baseline + adjustment knobs.

    Logic:
    * Revenue = baseline.revenue × (1 + price%) × (1 + volume%).
    * Variable cost = baseline.expenses × cogs_share × (1 + volume%).
    * Fixed cost = baseline.expenses × (1 - cogs_share).
    * Expenses_total = (variable + fixed) × (1 + expense_change%)
                      + fixed_cost_delta_ge.
    * Net = Revenue − Expenses_total.
    """
    p = price_change_pct / 100.0
    v = volume_change_pct / 100.0
    e = expense_change_pct / 100.0

    revenue = baseline["revenue_ge"] * (1.0 + p) * (1.0 + v)
    variable_cost = baseline["expenses_ge"] * cogs_share * (1.0 + v)
    fixed_cost = baseline["expenses_ge"] * (1.0 - cogs_share)
    expenses = (variable_cost + fixed_cost) * (1.0 + e) + fixed_cost_delta_ge
    net = revenue - expenses
    return {
        "revenue_ge": round(revenue, 2),
        "expenses_ge": round(expenses, 2),
        "net_ge": round(net, 2),
    }


def _margin_pct(metrics: Dict[str, float]) -> float:
    rev = metrics.get("revenue_ge") or 0.0
    if rev <= 0:
        return 0.0
    return round(metrics["net_ge"] / rev * 100.0, 2)


def _classify_decision(
    baseline: Dict[str, float],
    scenario: Dict[str, float],
) -> str:
    """Decision band based on net delta as % of baseline revenue."""
    revenue = baseline.get("revenue_ge") or 0.0
    if revenue <= 0:
        return DECISION_NEUTRAL
    delta_net = scenario["net_ge"] - baseline["net_ge"]
    pct = delta_net / revenue * 100.0
    if pct >= DECISION_BAND_PCT:
        return DECISION_IMPROVE
    if pct <= -DECISION_BAND_PCT:
        return DECISION_ERODE
    return DECISION_NEUTRAL


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------

def _render_summary_ka(
    *,
    scenario_label: str,
    base_period: str,
    store_label: str,
    baseline: Dict[str, float],
    scenario: Dict[str, float],
    baseline_margin: float,
    scenario_margin: float,
    decision: str,
    elasticity_auto: bool,
) -> str:
    delta_net = scenario["net_ge"] - baseline["net_ge"]
    delta_margin_pp = round(scenario_margin - baseline_margin, 2)
    label_block = f" · **{scenario_label}**" if scenario_label else ""
    elasticity_note = " · volume=elasticity" if elasticity_auto else ""
    sign = "+" if delta_net >= 0 else ""
    pp_sign = "+" if delta_margin_pp >= 0 else ""
    return (
        f"**scenario** ({base_period}, {store_label}){label_block} · "
        f"net **{baseline['net_ge']:,.0f} → {scenario['net_ge']:,.0f} ₾** "
        f"({sign}{delta_net:,.0f}) · "
        f"margin **{baseline_margin:.1f}% → {scenario_margin:.1f}%** "
        f"({pp_sign}{delta_margin_pp:.1f} pp) · "
        f"{decision}{elasticity_note}"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def simulate_scenario(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    base_period: Any = None,
    store: Any = None,
    price_change_pct: Any = None,
    volume_change_pct: Any = None,
    expense_change_pct: Any = None,
    fixed_cost_delta_ge: Any = None,
    price_elasticity: Any = None,
    cogs_share: Any = None,
    scenario_label: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Run a what-if simulation against a historical baseline month.

    See the module docstring for the full return contract.
    """
    # --- Argument coercion ------------------------------------------------
    canonical_store, store_err = _resolve_store(store)
    if store_err:
        return {"error": store_err, "hint": "გამოიყენე enum-ი: total / ოზურგეთი / დვაბზუ."}
    assert canonical_store is not None

    price_pct = _safe_pct(price_change_pct)
    expense_pct = _safe_pct(expense_change_pct)
    fixed_delta = _safe_amount(fixed_cost_delta_ge)
    elasticity = _resolve_elasticity(price_elasticity)
    share = _resolve_cogs_share(cogs_share)
    label = str(scenario_label or "").strip()

    # Elasticity auto-apply: only when price changes AND user didn't
    # explicitly set volume. We detect "didn't set" as volume_change_pct
    # being None (not 0 — a user explicit 0 should silence elasticity).
    volume_implied = False
    if volume_change_pct is None and price_pct != 0.0:
        volume_pct = round(price_pct * elasticity, 4)
        volume_implied = True
    else:
        volume_pct = _safe_pct(volume_change_pct)

    if price_pct == 0.0 and volume_pct == 0.0 and expense_pct == 0.0 and fixed_delta == 0.0:
        return {
            "error": (
                "სცენარი ცარიელია — არცერთი knob არ შეცვლი. მიუთითე "
                "`price_change_pct`, `volume_change_pct`, `expense_change_pct` "
                "ან `fixed_cost_delta_ge`."
            ),
            "hint": "მაგ: price_change_pct=5 (ფასი +5%), volume_change_pct=-8.",
        }

    if today is None:
        today = date.today()

    # --- Load baseline ----------------------------------------------------
    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("scenario_simulator data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა.",
            "hint": "გადაამოწმე generate_dashboard_data.py-ს output.",
        }

    monthly_pnl = data.get("monthly_pnl") or []
    # _extract_monthly_series isn't needed for single-row baselines but we
    # reuse it for validation — empty / malformed series surfaces early.
    _ = _extract_monthly_series(monthly_pnl)  # noqa: F841

    baseline, period_label, base_err = _resolve_baseline(
        monthly_pnl, canonical_store, base_period
    )
    if base_err:
        return {"error": base_err, "hint": "ცადე base_period='last_month' ან 'last_3_avg'."}
    assert baseline is not None
    assert period_label is not None

    # --- Apply scenario math ---------------------------------------------
    scenario = _apply_scenario(
        baseline,
        price_change_pct=price_pct,
        volume_change_pct=volume_pct,
        expense_change_pct=expense_pct,
        fixed_cost_delta_ge=fixed_delta,
        cogs_share=share,
    )
    baseline_margin = _margin_pct(baseline)
    scenario_margin = _margin_pct(scenario)

    deltas = {
        "revenue_ge": round(scenario["revenue_ge"] - baseline["revenue_ge"], 2),
        "expenses_ge": round(scenario["expenses_ge"] - baseline["expenses_ge"], 2),
        "net_ge": round(scenario["net_ge"] - baseline["net_ge"], 2),
        "margin_pp": round(scenario_margin - baseline_margin, 2),
    }
    decision = _classify_decision(baseline, scenario)

    store_label = {
        STORE_TOTAL: "ორივე მაღაზია",
        STORE_OZURGETI: "ოზურგეთი",
        STORE_DVABZU: "დვაბზუ",
    }.get(canonical_store, canonical_store)
    summary_ka = _render_summary_ka(
        scenario_label=label,
        base_period=period_label,
        store_label=store_label,
        baseline={**baseline},
        scenario=scenario,
        baseline_margin=baseline_margin,
        scenario_margin=scenario_margin,
        decision=decision,
        elasticity_auto=volume_implied,
    )

    notes: List[str] = []
    if volume_implied:
        notes.append(
            f"⚠️ volume_change_pct ცალკე არ მიგითითებია — გამოვიყენე "
            f"elasticity {elasticity:.2f} (price-elastic retail default). "
            f"ცხრილი თითქოს '{price_pct:+.1f}% ფასი → {volume_pct:+.2f}% volume'-ს ვთვლი."
        )
    if share < COGS_SHARE_SANE_MIN or share > COGS_SHARE_SANE_MAX:
        notes.append(
            f"⚠️ cogs_share={share:.2f} retail-ისთვის ატიპურია (ჩვეულებრივ 0.3–0.75). "
            f"შედეგი შეიძლება არასარწმუნო იყოს."
        )
    if baseline["revenue_ge"] <= 0:
        notes.append(
            "⚠️ baseline revenue ≤ 0 — margin pp delta და decision_indicator "
            "კორექტულად ვერ იმუშავებდა, დავაბრუნე NEUTRAL."
        )
    notes.append(
        "ⓘ Scenario-ის მათემატიკა: Revenue×(1+price%)×(1+vol%); "
        f"Variable cost = baseline × cogs_share({share:.2f}) × (1+vol%); "
        "Fixed cost = baseline × (1-cogs_share); "
        "Expenses_total = (Variable+Fixed) × (1+expense%) + fixed_cost_delta."
    )
    notes.append(
        "ⓘ decision band = ±2% of baseline revenue (under it → NEUTRAL, "
        "to avoid calling rounding noise an improvement)."
    )

    return {
        "source": SOURCE_LABEL,
        "as_of_date": today.isoformat(),
        "base_period_used": period_label,
        "store": canonical_store,
        "scenario_label": label,
        "baseline": {
            "revenue_ge": baseline["revenue_ge"],
            "expenses_ge": baseline["expenses_ge"],
            "net_ge": baseline["net_ge"],
            "margin_pct": baseline_margin,
        },
        "scenario": {
            "revenue_ge": scenario["revenue_ge"],
            "expenses_ge": scenario["expenses_ge"],
            "net_ge": scenario["net_ge"],
            "margin_pct": scenario_margin,
        },
        "deltas": deltas,
        "adjustments_applied": {
            "price_change_pct": price_pct,
            "volume_change_pct": volume_pct,
            "volume_implied_by_elasticity": volume_implied,
            "expense_change_pct": expense_pct,
            "fixed_cost_delta_ge": fixed_delta,
            "elasticity_used": elasticity,
            "cogs_share": share,
        },
        "decision_indicator": decision,
        "summary_ka": summary_ka,
        "notes": notes,
    }


__all__ = [
    "DEFAULT_PRICE_ELASTICITY",
    "DEFAULT_COGS_SHARE",
    "DECISION_BAND_PCT",
    "DECISION_IMPROVE",
    "DECISION_NEUTRAL",
    "DECISION_ERODE",
    "SOURCE_LABEL",
    "COGS_SHARE_SANE_MIN",
    "COGS_SHARE_SANE_MAX",
    "simulate_scenario",
]
