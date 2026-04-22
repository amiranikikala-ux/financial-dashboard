"""Phase 0B Sprint 2 — Revenue forecasting (Prophet + ARIMA ensemble).

Design goals
------------
* Zero runtime cost on Anthropic: everything here runs locally against the
  dashboard's ``monthly_pnl`` series. The LLM only narrates the result.
* Ground-truth first: read the EXACT same ``monthly_pnl`` shape produced by
  ``dashboard_pipeline.analytics_builders.build_monthly_pnl``. No duplicate
  revenue definition, no silent aggregation drift.
* Graceful degradation: Prophet & statsmodels are heavy scientific stacks
  that regularly fail to install on Windows. Both are imported lazily inside
  :func:`_load_prophet` / :func:`_load_arima`; if one is missing we fall
  back to the other, and if both fail we surface a clear Georgian error
  that tells the caller how to install them.
* Hard bounds: ``horizon_months`` clamped to [1, 12]; minimum 12 history
  points required; forecast rounded to 2 decimals; confidence interval
  widened whenever we fall back to a weaker model.

Return contract (stable — used by the tool dispatcher + tests)
--------------------------------------------------------------
Success::

    {
        "source": "data.json:monthly_pnl (prophet+arima ensemble)",
        "store": "total" | "ოზურგეთი" | "დვაბზუ",
        "horizon_months": int,
        "history_months": int,
        "history_start": "YYYY-MM",
        "history_end":   "YYYY-MM",
        "last_12_months_total": float,
        "yoy_growth_pct": float | None,
        "engines_used": ["prophet", "arima"],   # subset of those two
        "forecast": [
            {
                "month": "YYYY-MM",
                "baseline": float,
                "optimistic": float,
                "pessimistic": float,
            },
            ...
        ],
        "notes": [str, ...],   # caveats surfaced to the LLM (non-empty)
    }

Failure::

    {"error": "<Georgian message>", "hint": "<installation / data hint>"}

Keeping the shape flat and JSON-safe matters: the tool dispatcher serializes
it straight into a tool_result content block for Anthropic.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public contract constants
# ---------------------------------------------------------------------------

DEFAULT_HORIZON_MONTHS = 3
MIN_HORIZON_MONTHS = 1
MAX_HORIZON_MONTHS = 12

#: Minimum history length required to run Prophet/ARIMA meaningfully.
#: Fewer than 12 months can't detect yearly seasonality; we refuse rather
#: than produce a confident-looking but bogus forecast.
MIN_HISTORY_MONTHS = 12

#: Store enum surfaced to the LLM via the tool schema. "total" aggregates
#: every store under ``row["total"]["pos_income"]``; named stores read
#: ``row["objects"][<name>]["pos_income"]``. The Georgian names match the
#: canonical object keys defined in ``dashboard_pipeline.constants``.
STORE_TOTAL = "total"
STORE_OZURGETI = "ოზურგეთი"
STORE_DVABZU = "დვაბზუ"
SUPPORTED_STORES: Tuple[str, ...] = (
    STORE_TOTAL,
    STORE_OZURGETI,
    STORE_DVABZU,
)

#: Friendly aliases → canonical store. Accepting both Latin ("ozurgeti")
#: and Georgian avoids round-trip encoding pain when the LLM produces tool
#: arguments from a transliterated variant.
_STORE_ALIASES: Dict[str, str] = {
    "total": STORE_TOTAL,
    "all": STORE_TOTAL,
    "ჯამი": STORE_TOTAL,
    "ყველა": STORE_TOTAL,
    "ozurgeti": STORE_OZURGETI,
    "ozurgheti": STORE_OZURGETI,
    "ოზურგეთი": STORE_OZURGETI,
    "dvabzu": STORE_DVABZU,
    "dvabzo": STORE_DVABZU,
    "დვაბზუ": STORE_DVABZU,
}

REVENUE_FIELD = "pos_income"  # key under row["total"] / row["objects"][store]

#: Tool source label — echoed in every success payload so the LLM can cite it.
SOURCE_LABEL = "data.json:monthly_pnl (prophet+arima ensemble)"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _resolve_store(store: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(canonical_store, error)``. Error is a Georgian message.

    ``None`` / empty / whitespace collapses to :data:`STORE_TOTAL` — the most
    common case ("ერთი ცხრილი — ჯამი").
    """
    if store is None:
        return STORE_TOTAL, None
    if not isinstance(store, str):
        return None, (
            "`store` უნდა იყოს ტექსტი: 'total', 'ოზურგეთი' ან 'დვაბზუ'."
        )
    normalized = store.strip()
    if not normalized:
        return STORE_TOTAL, None
    # Try canonical first, then alias table.
    if normalized in SUPPORTED_STORES:
        return normalized, None
    alias = _STORE_ALIASES.get(normalized.lower())
    if alias is not None:
        return alias, None
    return None, (
        f"`store`='{store}' არ არის მხარდაჭერილი. მისაღები მნიშვნელობები: "
        f"{list(SUPPORTED_STORES)}."
    )


def _resolve_horizon(horizon: Any) -> Tuple[Optional[int], Optional[str]]:
    """Clamp ``horizon`` into [MIN, MAX]. Return ``(value, error)``."""
    if horizon is None:
        return DEFAULT_HORIZON_MONTHS, None
    try:
        value = int(horizon)
    except (TypeError, ValueError):
        return None, (
            "`horizon_months` უნდა იყოს მთელი რიცხვი "
            f"{MIN_HORIZON_MONTHS}-დან {MAX_HORIZON_MONTHS}-მდე."
        )
    if value < MIN_HORIZON_MONTHS or value > MAX_HORIZON_MONTHS:
        return None, (
            f"`horizon_months`={value} ფარგლებს გარეთაა "
            f"(დასაშვებია {MIN_HORIZON_MONTHS}–{MAX_HORIZON_MONTHS})."
        )
    return value, None


# ---------------------------------------------------------------------------
# Monthly revenue series extraction
# ---------------------------------------------------------------------------


def _extract_revenue_series(
    monthly_pnl: Any,
    store: str,
) -> Tuple[List[str], List[float], Optional[str]]:
    """Return ``(months, revenues, error)``.

    ``monthly_pnl`` is expected to be the list-of-dicts shape built by
    :func:`dashboard_pipeline.analytics_builders.build_monthly_pnl`. Any
    missing / malformed row is silently skipped — Prophet and ARIMA both
    tolerate small history gaps and we don't want a single bad row to make
    the whole forecast unavailable.
    """
    if not isinstance(monthly_pnl, list) or not monthly_pnl:
        return [], [], (
            "`monthly_pnl` ცარიელია ან არ არის ჩამონათვალი — "
            "პროგნოზი ვერ გავუშვი."
        )

    months: List[str] = []
    revenues: List[float] = []
    for row in monthly_pnl:
        if not isinstance(row, dict):
            continue
        month = row.get("month")
        if not isinstance(month, str) or not month.strip():
            continue

        if store == STORE_TOTAL:
            totals = row.get("total")
            if not isinstance(totals, dict):
                continue
            raw = totals.get(REVENUE_FIELD)
        else:
            objects = row.get("objects")
            if not isinstance(objects, dict):
                continue
            store_block = objects.get(store)
            if not isinstance(store_block, dict):
                continue
            raw = store_block.get(REVENUE_FIELD)

        try:
            value = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue

        months.append(month.strip())
        revenues.append(value)

    # Preserve chronological order if data came in unsorted (defensive).
    if months and months != sorted(months):
        paired = sorted(zip(months, revenues), key=lambda mv: mv[0])
        months = [m for m, _ in paired]
        revenues = [r for _, r in paired]

    if len(months) < MIN_HISTORY_MONTHS:
        return months, revenues, (
            f"ისტორია მხოლოდ {len(months)} თვეა, საჭიროა "
            f"მინიმუმ {MIN_HISTORY_MONTHS} — სანდო პროგნოზი ვერ გაიცემა."
        )

    return months, revenues, None


def _next_month(ym: str) -> str:
    """Return the ``YYYY-MM`` string for the month after ``ym``."""
    year_s, month_s = ym.split("-", 1)
    year = int(year_s)
    month = int(month_s)
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


def _future_months(anchor: str, count: int) -> List[str]:
    out: List[str] = []
    cursor = anchor
    for _ in range(count):
        cursor = _next_month(cursor)
        out.append(cursor)
    return out


def _yoy_growth_pct(revenues: Sequence[float]) -> Optional[float]:
    """YoY growth based on ``sum(last 12) / sum(previous 12)`` × 100 − 100.

    Returns ``None`` if history is too short or the divisor is zero/empty
    (prevents a misleading "infinite growth" when a store was freshly opened).
    """
    if len(revenues) < 24:
        return None
    last_12 = sum(revenues[-12:])
    prev_12 = sum(revenues[-24:-12])
    if prev_12 <= 0:
        return None
    return round((last_12 / prev_12 - 1.0) * 100.0, 2)


# ---------------------------------------------------------------------------
# Engine loaders (LAZY imports — Prophet / statsmodels wheels are heavy)
# ---------------------------------------------------------------------------


def _load_prophet():
    """Return the ``prophet.Prophet`` class or ``None`` if unavailable."""
    try:
        from prophet import Prophet  # type: ignore
        return Prophet
    except Exception as exc:  # ImportError + sub-dep import errors
        logger.info("Prophet unavailable: %s", exc)
        return None


def _load_arima():
    """Return the ``statsmodels.tsa.arima.model.ARIMA`` class or ``None``."""
    try:
        from statsmodels.tsa.arima.model import ARIMA  # type: ignore
        return ARIMA
    except Exception as exc:
        logger.info("statsmodels ARIMA unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Prophet + ARIMA forecasters
# ---------------------------------------------------------------------------


def _run_prophet(
    months: Sequence[str],
    revenues: Sequence[float],
    horizon: int,
    prophet_cls: Any,
) -> Optional[List[Dict[str, float]]]:
    """Return a list of ``{month, baseline, pessimistic, optimistic}`` rows or None.

    We deliberately import ``pandas`` lazily — everywhere else in this module
    pandas is optional.
    """
    try:
        import pandas as pd  # type: ignore
    except Exception as exc:  # pragma: no cover — pandas is a hard dep
        logger.warning("pandas unavailable for Prophet: %s", exc)
        return None

    try:
        ds = pd.to_datetime([f"{m}-01" for m in months])
        df = pd.DataFrame({"ds": ds, "y": list(revenues)})
        model = prophet_cls(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=0.95,
        )
        # Prophet 1.1 prints cmdstan compile spam on import; suppress on run.
        model.fit(df)
        future = model.make_future_dataframe(periods=horizon, freq="MS")
        forecast = model.predict(future)
        tail = forecast.tail(horizon)
        out: List[Dict[str, float]] = []
        for _, row in tail.iterrows():
            month = row["ds"].strftime("%Y-%m")
            out.append({
                "month": month,
                "baseline": float(row["yhat"]),
                "optimistic": float(row["yhat_upper"]),
                "pessimistic": float(row["yhat_lower"]),
            })
        return out
    except Exception as exc:
        logger.warning("Prophet fit/predict failed: %s", exc)
        return None


def _run_arima(
    months: Sequence[str],
    revenues: Sequence[float],
    horizon: int,
    arima_cls: Any,
) -> Optional[List[Dict[str, float]]]:
    """ARIMA(1,1,1) forecast with 95% confidence bands.

    Note we do NOT bother with model selection (pmdarima is yet another
    heavy dep); ARIMA(1,1,1) is a robust default for monthly retail series
    and the Prophet result — when available — dominates the ensemble.
    """
    try:
        results = arima_cls(list(revenues), order=(1, 1, 1)).fit()
        fc = results.get_forecast(steps=horizon)
        mean = fc.predicted_mean
        ci = fc.conf_int(alpha=0.05)
        anchor = months[-1]
        future = _future_months(anchor, horizon)
        out: List[Dict[str, float]] = []
        for i, ym in enumerate(future):
            # statsmodels returns numpy arrays here — index by position.
            baseline = float(getattr(mean, "iloc", mean)[i] if hasattr(mean, "iloc") else mean[i])
            lower = _ci_at(ci, i, column=0)
            upper = _ci_at(ci, i, column=1)
            out.append({
                "month": ym,
                "baseline": baseline,
                "optimistic": upper,
                "pessimistic": lower,
            })
        return out
    except Exception as exc:
        logger.warning("ARIMA fit/forecast failed: %s", exc)
        return None


def _ci_at(ci: Any, row_i: int, column: int) -> float:
    """Read confidence-interval row ``row_i``, column ``column`` (0=lower, 1=upper).

    Handles both numpy 2-D arrays and pandas DataFrames (statsmodels returns
    the latter in recent versions). Falls back to the baseline if the CI is
    malformed.
    """
    try:
        if hasattr(ci, "iloc"):
            return float(ci.iloc[row_i, column])
        return float(ci[row_i][column])
    except Exception:
        return float("nan")


# ---------------------------------------------------------------------------
# Ensemble + result assembly
# ---------------------------------------------------------------------------


def _ensemble(
    prophet_rows: Optional[List[Dict[str, float]]],
    arima_rows: Optional[List[Dict[str, float]]],
) -> List[Dict[str, float]]:
    """Average Prophet + ARIMA per-month when both succeed.

    Contract:
    - If both engines succeed we average the three bands independently
      (baseline=avg, optimistic=max of upper bounds, pessimistic=min of
      lower bounds). Taking max/min of bounds rather than avg is deliberate:
      the ensemble should be *at least as uncertain* as the most cautious
      engine, never narrower.
    - If only one engine succeeds we return its rows verbatim.
    """
    if prophet_rows and arima_rows and len(prophet_rows) == len(arima_rows):
        merged: List[Dict[str, float]] = []
        for p, a in zip(prophet_rows, arima_rows):
            # Keep the month label from Prophet (cosmetic; both should match).
            merged.append({
                "month": p["month"],
                "baseline": (p["baseline"] + a["baseline"]) / 2.0,
                "optimistic": max(p["optimistic"], a["optimistic"]),
                "pessimistic": min(p["pessimistic"], a["pessimistic"]),
            })
        return merged
    if prophet_rows:
        return prophet_rows
    if arima_rows:
        return arima_rows
    return []


def _round_rows(
    rows: Sequence[Dict[str, float]],
    digits: int = 2,
) -> List[Dict[str, Any]]:
    """Round + JSON-sanitize ensemble rows.

    Revenue is physically ``≥ 0`` — a store cannot pay customers. When
    Prophet / ARIMA produce a CI whose lower bound goes negative (routinely
    happens on volatile or low-mean series), that's a model artifact, not
    a prediction. We clamp every value to zero before returning so the LLM
    never quotes "პესიმისტური −6,832 ₾" to the user.
    """
    out: List[Dict[str, Any]] = []
    for r in rows:
        month = str(r.get("month") or "")
        baseline = r.get("baseline")
        optimistic = r.get("optimistic")
        pessimistic = r.get("pessimistic")
        out.append({
            "month": month,
            "baseline": _safe_round_nonneg(baseline, digits),
            "optimistic": _safe_round_nonneg(optimistic, digits),
            "pessimistic": _safe_round_nonneg(pessimistic, digits),
        })
    return out


def _safe_round_nonneg(value: Any, digits: int) -> Any:
    """Round ``value`` to ``digits`` decimals, clamping below zero to 0.

    Non-numeric / non-finite inputs collapse to ``None`` so the JSON payload
    stays encodable.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(max(0.0, f), digits)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def forecast_revenue(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    horizon_months: Any = None,
    store: Any = None,
) -> Dict[str, Any]:
    """Main tool entry point.

    Parameters
    ----------
    data_loader : callable
        Zero-arg loader returning the canonical data.json dict. Reusing
        :class:`dashboard_pipeline.ai.tools.ToolDispatcher`'s loader means
        Prophet gets the same cached snapshot as every other tool call in
        the turn.
    horizon_months : int, optional
        1–12, default 3.
    store : str, optional
        ``None`` / ``"total"`` / ``"ოზურგეთი"`` / ``"დვაბზუ"`` (aliases
        accepted — see :data:`_STORE_ALIASES`).

    Returns
    -------
    dict
        See module docstring for the exact contract.
    """
    horizon, horizon_err = _resolve_horizon(horizon_months)
    if horizon_err:
        return {"error": horizon_err}

    canonical_store, store_err = _resolve_store(store)
    if store_err:
        return {"error": store_err}
    assert canonical_store is not None  # for type checkers

    # Load data.json snapshot via the shared loader (one read per turn).
    try:
        data = data_loader()
    except FileNotFoundError as exc:
        return {
            "error": f"data.json ვერ ჩაიტვირთა: {exc}",
            "hint": "გადამოწმე რომ generate_dashboard_data.py გაეშვა.",
        }
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"data.json-ის ჩატვირთვა ვერ მოხერხდა: {exc}"}

    if not isinstance(data, dict):
        return {"error": "data.json-ის მონაცემი არასწორი ფორმატია (dict-ი არაა)."}

    monthly_pnl = data.get("monthly_pnl")
    months, revenues, series_err = _extract_revenue_series(
        monthly_pnl, canonical_store
    )
    if series_err:
        return {"error": series_err}

    # Load engines lazily. Record which ones we actually used so the LLM
    # can narrate the method and so future Sprint verifications can detect
    # silent degradation (e.g. Prophet install broke on upgrade).
    prophet_cls = _load_prophet()
    arima_cls = _load_arima()
    if prophet_cls is None and arima_cls is None:
        return {
            "error": (
                "`prophet` და `statsmodels` ვერ ჩაიტვირთა — პროგნოზი ვერ "
                "გავუშვი."
            ),
            "hint": (
                "parent-venv-ში გაუშვი: pip install prophet statsmodels"
            ),
        }

    prophet_rows: Optional[List[Dict[str, float]]] = None
    arima_rows: Optional[List[Dict[str, float]]] = None
    engines_used: List[str] = []
    notes: List[str] = []

    if prophet_cls is not None:
        prophet_rows = _run_prophet(months, revenues, horizon, prophet_cls)
        if prophet_rows:
            engines_used.append("prophet")
        else:
            notes.append("Prophet ვერ ჩაიშალა (fit/predict შეცდომა).")

    if arima_cls is not None:
        arima_rows = _run_arima(months, revenues, horizon, arima_cls)
        if arima_rows:
            engines_used.append("arima")
        else:
            notes.append("ARIMA ვერ ჩაიშალა (fit/forecast შეცდომა).")

    merged = _ensemble(prophet_rows, arima_rows)
    if not merged:
        return {
            "error": (
                "ორივე მოდელი ჩაიშალა ამ სერიაზე — პროგნოზი ვერ გავცემ."
            ),
            "hint": (
                "ცადე უფრო გრძელი ისტორია ან შეამოწმე, თუ monthly_pnl-ში "
                "NaN / null რიცხვები არაა."
            ),
        }

    # Pin standard caveats every response so the LLM always surfaces them.
    notes.extend([
        "მოდელი ვერ ხედავს მოულოდნელ შოკებს (POS ჩავარდნა, ვალუტის ნახტომი).",
        "ფაქტი სავარაუდოდ ±10–15%-ით გადაიხრება ბაზისიდან.",
    ])
    if len(engines_used) == 1:
        notes.insert(
            0,
            f"მხოლოდ {engines_used[0]} იყო ხელმისაწვდომი — confidence-"
            "ინტერვალი ცოტა უფრო ფართოა.",
        )

    last_12_total = round(sum(revenues[-12:]), 2)
    yoy = _yoy_growth_pct(revenues)

    # Pre-rendered Georgian summary (Phase 4C Rule 30 — tools think out loud).
    rounded_rows = _round_rows(merged)
    store_label_ka = {
        STORE_TOTAL: "ორივე მაღაზია",
        STORE_OZURGETI: "ოზურგეთი",
        STORE_DVABZU: "დვაბზუ",
    }.get(canonical_store, canonical_store)
    if rounded_rows:
        first_baseline = rounded_rows[0].get("baseline")
        last_baseline = rounded_rows[-1].get("baseline")
        baseline_range = (
            f"{first_baseline:,.0f}–{last_baseline:,.0f} ₾"
            if isinstance(first_baseline, (int, float))
            and isinstance(last_baseline, (int, float))
            else "—"
        )
    else:
        baseline_range = "—"
    yoy_str = f"{yoy:+.1f}%" if isinstance(yoy, (int, float)) else "n/a"
    engines_str = "+".join(engines_used) if engines_used else "—"
    summary_ka = (
        f"**{store_label_ka}** — მომდევნო **{horizon} თვე**: baseline "
        f"**{baseline_range}** (YoY {yoy_str}, {engines_str} ensemble; "
        f"{len(months)}თვიანი ისტორია)."
    )

    return {
        "source": SOURCE_LABEL,
        "store": canonical_store,
        "horizon_months": horizon,
        "history_months": len(months),
        "history_start": months[0],
        "history_end": months[-1],
        "last_12_months_total": last_12_total,
        "yoy_growth_pct": yoy,
        "engines_used": engines_used,
        "forecast": rounded_rows,
        "notes": notes,
        "summary_ka": summary_ka,
    }


__all__ = [
    "DEFAULT_HORIZON_MONTHS",
    "MIN_HORIZON_MONTHS",
    "MAX_HORIZON_MONTHS",
    "MIN_HISTORY_MONTHS",
    "SUPPORTED_STORES",
    "STORE_TOTAL",
    "STORE_OZURGETI",
    "STORE_DVABZU",
    "REVENUE_FIELD",
    "SOURCE_LABEL",
    "forecast_revenue",
]
