"""Phase 2.1 — Cash Flow Projection (daily forward-looking cash trajectory).

Complements ``compute_cash_runway`` (static "months left at current burn")
with a DAILY trajectory over a 7–60 day horizon. Identifies specific red
days ("17–19 მაისს cash −8,200 ₾").

Design
------
* Opening balance: user-provided BOG + TBC (same pull as cash_runway).
* Daily income baseline: ``forecast_revenue`` next-month baseline divided
  evenly across days of the horizon (POS income only; retail is roughly
  evenly distributed across the month).
* Daily outflow baseline: last-N-months average expenses / DAYS_PER_MONTH
  (all expenses except POS-revenue, incl. royalty, wages, rent, supplier
  payments amortized).
* Scheduled payments: user-provided ``upcoming_payments`` list of
  ``{date, amount_ge, label}`` — one-off commitments outside the smoothed
  baseline (e.g. loan instalment due on specific day).
* Day status: 🔴 if closing < 0, 🟡 if closing < daily_burn × 7 (less than
  a week of expenses in reserve), 🟢 otherwise.

Return contract (success)::

    {
        "source": "data.json:monthly_pnl + forecast_revenue",
        "as_of_date": "YYYY-MM-DD",
        "horizon_days": int,
        "opening_balance_ge": float,
        "current_cash_breakdown": {"bog_ge": float, "tbc_ge": float},
        "daily_income_baseline_ge": float,
        "daily_burn_ge": float,
        "daily_projection": [
            {
                "date": "YYYY-MM-DD",
                "opening_ge": float,
                "income_ge": float,
                "outflow_ge": float,
                "scheduled_payments": [{"label": str, "amount_ge": float}],
                "closing_ge": float,
                "status": "🟢 SAFE" | "🟡 WATCH" | "🔴 RED",
            },
            ...
        ],
        "risk_windows": [
            {
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD",
                "days": int,
                "min_balance_ge": float,
                "lowest_day": "YYYY-MM-DD",
            },
            ...
        ],
        "ending_balance_ge": float,
        "minimum_balance_ge": float,
        "minimum_balance_date": "YYYY-MM-DD",
        "forecast_engines": ["prophet", "arima"],
        "summary_ka": str,
        "notes": [str, ...],
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from dashboard_pipeline.ai.cash_runway import (
    DAYS_PER_MONTH,
    _extract_monthly_series,
    _resolve_balance,
    _resolve_lookback_months,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_HORIZON_DAYS = 14
MIN_HORIZON_DAYS = 7
MAX_HORIZON_DAYS = 60

DAY_STATUS_SAFE = "🟢 SAFE"
DAY_STATUS_WATCH = "🟡 WATCH"
DAY_STATUS_RED = "🔴 RED"

#: Closing balance below ``daily_burn × WATCH_BUFFER_DAYS`` is YELLOW —
#: less than a week of expenses in reserve.
WATCH_BUFFER_DAYS = 7

SOURCE_LABEL = "data.json:monthly_pnl + forecast_revenue"


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def _resolve_horizon_days(raw: Any) -> int:
    try:
        value = int(raw) if raw is not None else DEFAULT_HORIZON_DAYS
    except (TypeError, ValueError):
        return DEFAULT_HORIZON_DAYS
    if value < MIN_HORIZON_DAYS:
        return MIN_HORIZON_DAYS
    if value > MAX_HORIZON_DAYS:
        return MAX_HORIZON_DAYS
    return value


def _parse_iso_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        y, m, d = value.strip().split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


def _resolve_upcoming_payments(
    raw: Any,
    start: date,
    end: date,
) -> tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
    """Return ``({iso_date: [{label, amount_ge}]}, warnings[])``.

    Silently drop entries that:
    * are not dict with ``date`` + ``amount_ge``
    * have unparseable date
    * fall outside ``[start, end]`` inclusive horizon window
    * have non-positive amount

    Warnings list goes into ``notes`` so the LLM can narrate skipped rows.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    warnings: List[str] = []
    if raw is None:
        return buckets, warnings
    if not isinstance(raw, list):
        warnings.append("`upcoming_payments` სიის ნაცვლად სხვა ტიპი მოვიდა — იგნორირდა.")
        return buckets, warnings

    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            warnings.append(f"`upcoming_payments[{idx}]` ობიექტი არაა — გამოტოვდა.")
            continue
        d = _parse_iso_date(entry.get("date"))
        if d is None:
            warnings.append(
                f"`upcoming_payments[{idx}].date` არასწორია — "
                "მოელოდა 'YYYY-MM-DD'. გამოტოვდა."
            )
            continue
        if d < start or d > end:
            warnings.append(
                f"`upcoming_payments[{idx}]` ({d.isoformat()}) ფანჯარას გარეთაა "
                f"[{start.isoformat()}..{end.isoformat()}] — გამოტოვდა."
            )
            continue
        try:
            amount = float(entry.get("amount_ge"))
        except (TypeError, ValueError):
            warnings.append(
                f"`upcoming_payments[{idx}].amount_ge` რიცხვი არაა — გამოტოვდა."
            )
            continue
        if not math.isfinite(amount) or amount <= 0:
            warnings.append(
                f"`upcoming_payments[{idx}].amount_ge` არადადებითი რიცხვია — გამოტოვდა."
            )
            continue
        label = str(entry.get("label") or "").strip() or "გადახდა"
        buckets.setdefault(d.isoformat(), []).append(
            {"label": label, "amount_ge": round(amount, 2)}
        )
    return buckets, warnings


# ---------------------------------------------------------------------------
# Burn + income baseline extraction
# ---------------------------------------------------------------------------

def _average_monthly_expense(
    series: List[Dict[str, Any]],
    lookback: int,
) -> float:
    """Mean monthly expense over the last ``lookback`` months (non-negative)."""
    if not series:
        return 0.0
    window = series[-lookback:]
    if not window:
        return 0.0
    total = sum(max(0.0, float(row.get("expense_ge") or 0.0)) for row in window)
    return total / len(window)


def _forecast_next_month_baseline(
    data_loader: Callable[[], Dict[str, Any]],
    store: Any,
) -> tuple[Optional[float], List[str], List[str]]:
    """Return ``(baseline_next_month_ge, engines_used, notes_from_forecast)``.

    ``None`` baseline means the forecast module reported an error — caller
    falls back to recent historical income average.
    """
    from dashboard_pipeline.ai.forecasting import forecast_revenue

    result = forecast_revenue(
        data_loader=data_loader,
        horizon_months=1,
        store=store,
    )
    if not isinstance(result, dict) or "error" in result:
        hint = (result or {}).get("error") if isinstance(result, dict) else None
        return (
            None,
            [],
            [f"forecast_revenue ვერ გავუშვი ({hint or 'უცნობი მიზეზი'})."],
        )
    forecast_rows = result.get("forecast") or []
    if not forecast_rows:
        return (None, [], ["forecast_revenue-მა ცარიელი forecast დააბრუნა."])
    first = forecast_rows[0]
    try:
        baseline = float(first.get("baseline"))
    except (TypeError, ValueError):
        return (None, [], ["forecast_revenue.baseline რიცხვი არაა."])
    engines = list(result.get("engines_used") or [])
    return baseline, engines, []


# ---------------------------------------------------------------------------
# Projection core
# ---------------------------------------------------------------------------

def _status_for(closing: float, daily_burn: float) -> str:
    if closing < 0:
        return DAY_STATUS_RED
    threshold = daily_burn * WATCH_BUFFER_DAYS
    if threshold > 0 and closing < threshold:
        return DAY_STATUS_WATCH
    return DAY_STATUS_SAFE


def _merge_risk_windows(
    projection: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collapse consecutive 🔴 days into windows."""
    windows: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for row in projection:
        if row["status"] == DAY_STATUS_RED:
            if current is None:
                current = {
                    "start_date": row["date"],
                    "end_date": row["date"],
                    "days": 1,
                    "min_balance_ge": row["closing_ge"],
                    "lowest_day": row["date"],
                }
            else:
                current["end_date"] = row["date"]
                current["days"] += 1
                if row["closing_ge"] < current["min_balance_ge"]:
                    current["min_balance_ge"] = row["closing_ge"]
                    current["lowest_day"] = row["date"]
        else:
            if current is not None:
                windows.append(current)
                current = None
    if current is not None:
        windows.append(current)
    return windows


def _format_ge_date_ka(iso: str) -> str:
    """Render ``YYYY-MM-DD`` as ``DD MMM`` in Georgian month abbreviations."""
    d = _parse_iso_date(iso)
    if d is None:
        return iso
    months_ka = {
        1: "იან", 2: "თებ", 3: "მარტ", 4: "აპრ",
        5: "მაი", 6: "ივნ", 7: "ივლ", 8: "აგვ",
        9: "სექ", 10: "ოქტ", 11: "ნოე", 12: "დეკ",
    }
    return f"{d.day} {months_ka.get(d.month, str(d.month))}"


def _render_summary_ka(
    *,
    horizon_days: int,
    opening: float,
    ending: float,
    minimum_balance: float,
    minimum_date: str,
    risk_windows: List[Dict[str, Any]],
    engines_used: List[str],
    fallback_income: bool,
) -> str:
    red_count = sum(w["days"] for w in risk_windows)
    engines_str = "+".join(engines_used) if engines_used else (
        "history-fallback" if fallback_income else "—"
    )
    if red_count == 0:
        tail = f"მინ. **{minimum_balance:,.0f} ₾** ({_format_ge_date_ka(minimum_date)})"
        return (
            f"**{horizon_days} დღის პროექცია** · საწყისი "
            f"**{opening:,.0f} ₾** · 🟢 0 წითელი დღე · {tail} · "
            f"საბოლოო **{ending:,.0f} ₾** · {engines_str} ensemble"
        )
    if len(risk_windows) == 1:
        w = risk_windows[0]
        if w["start_date"] == w["end_date"]:
            window_str = _format_ge_date_ka(w["start_date"])
        else:
            window_str = (
                f"{_format_ge_date_ka(w['start_date'])}–"
                f"{_format_ge_date_ka(w['end_date'])}"
            )
    else:
        window_str = f"{len(risk_windows)} ფანჯარა"
    return (
        f"**{horizon_days} დღის პროექცია** · საწყისი **{opening:,.0f} ₾** · "
        f"🔴 **{red_count}** წითელი დღე ({window_str}) · "
        f"მინ. **{minimum_balance:,.0f} ₾** ({_format_ge_date_ka(minimum_date)}) · "
        f"{engines_str} ensemble"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_cash_flow_projection(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    current_balance_bog_ge: Any = None,
    current_balance_tbc_ge: Any = None,
    horizon_days: Any = None,
    store: Any = None,
    lookback_months: Any = None,
    upcoming_payments: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute day-by-day cash projection over the next ``horizon_days`` days.

    See the module docstring for the full return contract.
    """
    # --- Argument validation ---------------------------------------------
    bog = _resolve_balance(current_balance_bog_ge)
    tbc = _resolve_balance(current_balance_tbc_ge)
    if bog is None and tbc is None:
        return {
            "error": (
                "ორივე ბანკის ნაშთი ცარიელია — cash flow projection ვერ დავთვალო. "
                "მიუთითე მინიმუმ ერთი (BOG ან TBC) დადებითი რიცხვით."
            ),
            "hint": "მაგ: compute_cash_flow_projection(current_balance_bog_ge=50000, current_balance_tbc_ge=30000)",
        }
    if bog is None:
        bog = 0.0
    if tbc is None:
        tbc = 0.0
    opening = round(bog + tbc, 2)
    if opening <= 0:
        return {
            "error": (
                "ჯამური ნაშთი 0 ან უარყოფითია — cash flow projection არარელევანტურია "
                "(ფული უკვე ამოწურულია)."
            ),
            "hint": "გადაამოწმე ციფრები ბანკის აპში და ისევ ცადე.",
        }

    horizon = _resolve_horizon_days(horizon_days)
    lookback = _resolve_lookback_months(lookback_months)
    if today is None:
        today = date.today()
    elif not isinstance(today, date):
        return {
            "error": "today პარამეტრი უნდა იყოს date ობიექტი ან None.",
            "hint": "ჩვეულებრივ ეს არ გადაეცემა.",
        }

    start_date = today + timedelta(days=1)  # projection starts TOMORROW
    end_date = start_date + timedelta(days=horizon - 1)

    payment_buckets, payment_warnings = _resolve_upcoming_payments(
        upcoming_payments, start_date, end_date
    )

    # --- Load data.json snapshot ------------------------------------------
    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("cash_flow_projection data_loader failed: %s", exc)
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

    # --- Daily baselines --------------------------------------------------
    avg_monthly_expense = _average_monthly_expense(series, lookback)
    daily_burn = round(avg_monthly_expense / DAYS_PER_MONTH, 2)

    forecast_baseline, engines_used, forecast_notes = _forecast_next_month_baseline(
        data_loader, store
    )
    fallback_income = forecast_baseline is None
    if fallback_income:
        # Fallback: average of recent historical POS income
        window = series[-lookback:]
        total_income = sum(max(0.0, float(r.get("income_ge") or 0.0)) for r in window)
        monthly_income_baseline = total_income / len(window) if window else 0.0
    else:
        monthly_income_baseline = forecast_baseline
    daily_income = round(monthly_income_baseline / DAYS_PER_MONTH, 2)

    # --- Iterate day-by-day ----------------------------------------------
    projection: List[Dict[str, Any]] = []
    running = opening
    minimum_balance = opening
    minimum_date = today.isoformat()
    for offset in range(horizon):
        d = start_date + timedelta(days=offset)
        iso = d.isoformat()
        scheduled = payment_buckets.get(iso, [])
        scheduled_total = sum(p["amount_ge"] for p in scheduled)
        opening_day = round(running, 2)
        outflow_day = round(daily_burn + scheduled_total, 2)
        closing_day = round(opening_day + daily_income - outflow_day, 2)
        status = _status_for(closing_day, daily_burn)
        projection.append(
            {
                "date": iso,
                "opening_ge": opening_day,
                "income_ge": daily_income,
                "outflow_ge": outflow_day,
                "scheduled_payments": scheduled,
                "closing_ge": closing_day,
                "status": status,
            }
        )
        if closing_day < minimum_balance:
            minimum_balance = closing_day
            minimum_date = iso
        running = closing_day

    ending_balance = projection[-1]["closing_ge"] if projection else opening
    risk_windows = _merge_risk_windows(projection)

    summary_ka = _render_summary_ka(
        horizon_days=horizon,
        opening=opening,
        ending=ending_balance,
        minimum_balance=minimum_balance,
        minimum_date=minimum_date,
        risk_windows=risk_windows,
        engines_used=engines_used,
        fallback_income=fallback_income,
    )

    notes: List[str] = []
    notes.extend(forecast_notes)
    notes.extend(payment_warnings)
    notes.append(
        f"Daily income ({daily_income:,.2f} ₾) = {'forecast' if not fallback_income else 'historical avg'} "
        f"{monthly_income_baseline:,.0f} ₾/თვე / {DAYS_PER_MONTH:.2f} დღე."
    )
    notes.append(
        f"Daily burn ({daily_burn:,.2f} ₾) = last-{lookback}-month avg expenses "
        f"{avg_monthly_expense:,.0f} ₾/თვე / {DAYS_PER_MONTH:.2f} დღე."
    )
    notes.append(
        "ⓘ Smoothed baseline — POS income არ არის ევნი დღეების მიხედვით "
        "(შაბათ-კვირაზე მაღალი, შუა კვირას დაბალი). ფაქტობრივი ±10–20%."
    )
    if fallback_income:
        notes.insert(
            0,
            "⚠️ forecast_revenue ვერ გავუშვი — income baseline ისტორიული საშ-ია "
            "(confidence უფრო დაბალია).",
        )
    if risk_windows:
        notes.append(
            f"🔴 {len(risk_windows)} რისკის ფანჯარა — ჯამში "
            f"{sum(w['days'] for w in risk_windows)} დღე cash < 0."
        )

    return {
        "source": SOURCE_LABEL,
        "as_of_date": today.isoformat(),
        "horizon_days": horizon,
        "opening_balance_ge": opening,
        "current_cash_breakdown": {
            "bog_ge": round(bog, 2),
            "tbc_ge": round(tbc, 2),
        },
        "daily_income_baseline_ge": daily_income,
        "daily_burn_ge": daily_burn,
        "daily_projection": projection,
        "risk_windows": risk_windows,
        "ending_balance_ge": ending_balance,
        "minimum_balance_ge": minimum_balance,
        "minimum_balance_date": minimum_date,
        "forecast_engines": engines_used,
        "summary_ka": summary_ka,
        "notes": notes,
    }


__all__ = [
    "DEFAULT_HORIZON_DAYS",
    "MIN_HORIZON_DAYS",
    "MAX_HORIZON_DAYS",
    "DAY_STATUS_SAFE",
    "DAY_STATUS_WATCH",
    "DAY_STATUS_RED",
    "WATCH_BUFFER_DAYS",
    "SOURCE_LABEL",
    "compute_cash_flow_projection",
]
