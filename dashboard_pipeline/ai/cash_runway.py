"""Phase 3.5 — Cash Runway Calculator.

Given user-provided current cash balance (BOG + TBC) and the historical
`monthly_pnl` series, compute:

* **burn_rate_ge_per_month** — average monthly net outflow over the last
  N months (positive number when business is losing cash; clamped at 0
  when net is positive).
* **runway_months / runway_days** — months/days until cash runs out at
  the current burn rate. ∞ (encoded as ``-1``) when the business is
  profitable.
* **runway_label** — 🟢 SAFE (≥ 6 months) / 🟡 WATCH (2–6 months) /
  🔴 CRITICAL (< 2 months) / 🟢 PROFIT (no burn).
* **burn_trend** — stable / accelerating / decelerating based on the
  last 3 months vs the prior 3 months.

Return contract (success)::

    {
        "as_of_date": "YYYY-MM-DD",
        "current_cash_ge": float,
        "current_cash_breakdown": {"bog_ge": float, "tbc_ge": float},
        "lookback_months": int,
        "burn_rate_ge_per_month": float,
        "burn_trend": "stable" | "accelerating" | "decelerating" | "insufficient_history",
        "burn_history": [{"month": "YYYY-MM", "net_ge": float, "expense_ge": float, "income_ge": float}, ...],
        "runway_months": float | -1.0,   # -1 denotes infinite (profit)
        "runway_days": int | -1,
        "runway_label": "🟢 SAFE" | "🟡 WATCH" | "🔴 CRITICAL" | "🟢 PROFIT",
        "status_summary_ka": str,
        "notes": [str, ...],
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public contract constants
# ---------------------------------------------------------------------------

DEFAULT_LOOKBACK_MONTHS = 3
MIN_LOOKBACK_MONTHS = 1
MAX_LOOKBACK_MONTHS = 12

RUNWAY_LABEL_PROFIT = "🟢 PROFIT"
RUNWAY_LABEL_SAFE = "🟢 SAFE"
RUNWAY_LABEL_WATCH = "🟡 WATCH"
RUNWAY_LABEL_CRITICAL = "🔴 CRITICAL"

RUNWAY_SAFE_MONTHS = 6.0
RUNWAY_WATCH_MONTHS = 2.0
DAYS_PER_MONTH = 30.4375  # average Gregorian month length
TREND_DELTA_PCT = 10.0


# ---------------------------------------------------------------------------
# Argument coercion helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(out) or math.isinf(out):
        return 0.0
    return out


def _resolve_lookback_months(raw: Any) -> int:
    """Clamp a user-provided lookback_months into the [1..12] range."""
    try:
        value = int(raw) if raw is not None else DEFAULT_LOOKBACK_MONTHS
    except (TypeError, ValueError):
        return DEFAULT_LOOKBACK_MONTHS
    if value < MIN_LOOKBACK_MONTHS:
        return MIN_LOOKBACK_MONTHS
    if value > MAX_LOOKBACK_MONTHS:
        return MAX_LOOKBACK_MONTHS
    return value


def _resolve_balance(raw: Any) -> Optional[float]:
    """Positive-or-zero cash balance, else ``None`` when unparseable."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    if value < 0:
        return None
    return value


# ---------------------------------------------------------------------------
# Burn-rate helpers
# ---------------------------------------------------------------------------

def _extract_monthly_series(
    monthly_pnl: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normalize monthly_pnl rows into a compact {month, income, expenses, net} list,
    ordered oldest→newest."""
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


def _compute_burn_trend(series: List[Dict[str, Any]], lookback: int) -> str:
    """Compare recent lookback-window vs the prior equal-size window.

    ``accelerating`` if burn_rate_recent exceeds burn_rate_prior by more
    than ``TREND_DELTA_PCT``; ``decelerating`` if it is lower by more
    than ``TREND_DELTA_PCT``; ``stable`` otherwise. Returns
    ``insufficient_history`` when we have less than 2×lookback months.
    """
    if len(series) < lookback * 2:
        return "insufficient_history"
    recent = series[-lookback:]
    prior = series[-lookback * 2:-lookback]
    # Burn rate = average expense − income. Negative means profit.
    def _burn(window: List[Dict[str, Any]]) -> float:
        if not window:
            return 0.0
        total_net = sum(w["net_ge"] for w in window)
        return -total_net / len(window)

    recent_burn = _burn(recent)
    prior_burn = _burn(prior)
    if prior_burn <= 0 and recent_burn <= 0:
        return "stable"
    if prior_burn <= 0 and recent_burn > 0:
        return "accelerating"
    if prior_burn > 0 and recent_burn <= 0:
        return "decelerating"
    pct = (recent_burn - prior_burn) * 100.0 / abs(prior_burn)
    if pct > TREND_DELTA_PCT:
        return "accelerating"
    if pct < -TREND_DELTA_PCT:
        return "decelerating"
    return "stable"


def _classify_runway(runway_months: float, burn_rate: float) -> str:
    if burn_rate <= 0:
        return RUNWAY_LABEL_PROFIT
    if runway_months >= RUNWAY_SAFE_MONTHS:
        return RUNWAY_LABEL_SAFE
    if runway_months >= RUNWAY_WATCH_MONTHS:
        return RUNWAY_LABEL_WATCH
    return RUNWAY_LABEL_CRITICAL


def _build_status_summary_ka(
    *,
    runway_months: float,
    runway_label: str,
    burn_rate: float,
    burn_trend: str,
    cash: float,
) -> str:
    if runway_label == RUNWAY_LABEL_PROFIT:
        return (
            "🟢 ბიზნესი მოგებაზეა — burn rate ≤ 0. Cash runway-ის საზრუნავი "
            "ამ მომენტისთვის არ არის. შეგიძლია strategic ინვესტიცია განიხილო."
        )
    if burn_rate <= 0:  # defensive
        return "🟢 Cash runway მიღებულია burn rate ≤ 0-ზე — გამოძიების საჭიროება."
    months_text = (
        f"{runway_months:.1f} თვე ({int(round(runway_months * DAYS_PER_MONTH))} დღე)"
    )
    trend_text = {
        "stable": "სტაბილური",
        "accelerating": "მზარდი (⚠️ ხარჯი იზრდება)",
        "decelerating": "მცირდება (🟢 ხარჯი ქრება)",
        "insufficient_history": "ცუდი ისტორია",
    }.get(burn_trend, burn_trend)
    if runway_label == RUNWAY_LABEL_CRITICAL:
        core = f"🔴 კრიტიკული — მხოლოდ {months_text} გაქვს დარჩენილი."
    elif runway_label == RUNWAY_LABEL_WATCH:
        core = f"🟡 ფრთხილად — {months_text} გაქვს."
    else:
        core = f"🟢 მდგრადი — {months_text} გაქვს."
    return (
        f"{core} თვიური burn rate ≈ {burn_rate:,.0f} ₾ ({trend_text}). "
        f"ახლანდელი ნაშთი {cash:,.0f} ₾."
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_cash_runway(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    current_balance_bog_ge: Any = None,
    current_balance_tbc_ge: Any = None,
    lookback_months: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute Cash Runway given user-provided current cash balance.

    Parameters
    ----------
    data_loader:
        Zero-argument callable returning the parsed ``data.json`` dict.
    current_balance_bog_ge:
        Current BOG balance in GEL. Non-negative number.
    current_balance_tbc_ge:
        Current TBC balance in GEL. Non-negative number.
    lookback_months:
        Number of recent months to average over (default 3, range 1..12).
    today:
        Override "today" for deterministic tests. Defaults to
        :func:`date.today`.
    """
    # --- Argument validation ---------------------------------------------
    bog = _resolve_balance(current_balance_bog_ge)
    tbc = _resolve_balance(current_balance_tbc_ge)
    if bog is None and tbc is None:
        return {
            "error": (
                "ორივე ბანკის ნაშთი ცარიელია — Cash Runway ვერ დავთვალო. "
                "მიუთითე მინიმუმ ერთი (BOG ან TBC) დადებითი რიცხვით."
            ),
            "hint": "მაგ: compute_cash_runway(current_balance_bog_ge=50000, current_balance_tbc_ge=30000)",
        }
    if bog is None:
        bog = 0.0
    if tbc is None:
        tbc = 0.0
    cash = round(bog + tbc, 2)
    if cash <= 0:
        return {
            "error": (
                "ჯამური ნაშთი 0 ან უარყოფითია — Cash Runway არარ რელევანტურია "
                "(ფული უკვე ამოწურულია)."
            ),
            "hint": "გადაამოწმე ციფრები ბანკის აპში და ისევ ცადე.",
        }

    lookback = _resolve_lookback_months(lookback_months)
    if today is None:
        today = date.today()
    elif not isinstance(today, date):
        return {
            "error": "today პარამეტრი უნდა იყოს date ობიექტი ან None.",
            "hint": "ჩვეულებრივ ეს არ გადაეცემა.",
        }

    # --- Load + validate history -----------------------------------------
    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("cash_runway data_loader failed: %s", exc)
        return {
            "error": "data.json-ის ჩატვირთვა ვერ მოხერხდა.",
            "hint": "გადაამოწმე generate_dashboard_data.py-ს output.",
        }

    monthly_pnl = data.get("monthly_pnl") or []
    series = _extract_monthly_series(monthly_pnl)
    if len(series) < lookback:
        return {
            "error": (
                f"monthly_pnl-ში {lookback} თვის ისტორია ვერ ვიპოვე "
                f"(არსებული: {len(series)} თვე)."
            ),
            "hint": "შეამცირე lookback_months ან გადაამოწმე data.json.",
        }

    window = series[-lookback:]
    avg_net = sum(w["net_ge"] for w in window) / len(window)
    burn_rate = max(-avg_net, 0.0)  # burn = negative of avg net, clamped ≥ 0

    # --- Runway calculation ----------------------------------------------
    if burn_rate <= 0:
        runway_months: float = -1.0
        runway_days: int = -1
    else:
        runway_months = cash / burn_rate
        runway_days = int(round(runway_months * DAYS_PER_MONTH))

    runway_label = _classify_runway(runway_months, burn_rate)
    burn_trend = _compute_burn_trend(series, lookback)
    status_summary = _build_status_summary_ka(
        runway_months=runway_months,
        runway_label=runway_label,
        burn_rate=burn_rate,
        burn_trend=burn_trend,
        cash=cash,
    )

    notes: List[str] = [
        f"Lookback = ბოლო {lookback} თვე ({window[0]['month']} → {window[-1]['month']}).",
        "burn_rate = ბოლო თვეების საშ. (expenses − POS income); POS-ის გარდა შემოსავალი აქ არ ცხარა.",
    ]
    if burn_trend == "accelerating":
        notes.append(
            "⚠️ ხარჯი უფრო სწრაფად იზრდება ვიდრე წინა ფანჯარაში — runway "
            "ციფრი ოპტიმისტურია, რადგან trend ცუდი მიმართულებით მიდის."
        )
    elif burn_trend == "decelerating":
        notes.append(
            "🟢 ხარჯი ქრება წინა ფანჯარასთან შედარებით — runway ციფრი "
            "პესიმისტურია, რადგან trend დადებითი მიმართულებით მიდის."
        )
    elif burn_trend == "insufficient_history":
        notes.append(
            "ⓘ trend ვერ გამოვთვალე — monthly_pnl-ში 2× lookback არ არის. "
            "ციფრი ასახავს მხოლოდ მიმდინარე ფანჯრის საშუალოს."
        )
    if lookback <= 1:
        notes.append(
            "⚠️ 1-თვიანი ფანჯარა ცალსახად მოკლე-დროულ ვარიაციას ექვემდებარება "
            "(capex / royalty / payday). სტრატეგიული გადაწყვეტილებისთვის "
            "გამოიყენე lookback_months=3 ან მეტი."
        )

    return {
        "as_of_date": today.isoformat(),
        "current_cash_ge": cash,
        "current_cash_breakdown": {
            "bog_ge": round(bog, 2),
            "tbc_ge": round(tbc, 2),
        },
        "lookback_months": lookback,
        "burn_rate_ge_per_month": round(burn_rate, 2),
        "burn_trend": burn_trend,
        "burn_history": window,
        "runway_months": (
            round(runway_months, 2) if runway_months >= 0 else -1.0
        ),
        "runway_days": runway_days,
        "runway_label": runway_label,
        "status_summary_ka": status_summary,
        "notes": notes,
    }
