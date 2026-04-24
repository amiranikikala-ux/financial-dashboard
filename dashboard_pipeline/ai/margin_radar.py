"""Phase 3.8 — Margin Compression Radar (time-series GM decay tracker).

Reads ``retail_sales.by_category_by_month`` (per-month per-category bundle
already computed by ``generate_dashboard_data.py``) and surfaces categories
whose gross margin is compressing (or expanding) across a rolling window of
months. Sorts by *revenue-weighted* compression score so a 30pp drop on a
1,000 ₾ category does not outrank a 2pp drop on a 100,000 ₾ category.

This tool is the time-series companion to:
* ``mix_analyzer`` (Phase 2.3) — snapshot DRAG/LIFT mix rebalance
* ``detect_trends`` (Phase 2.9) — single-period MoM/YoY decomposition

Design decisions (data-driven, no per-call config):
* Window default = 6 months (range 3..12). Constants in ``constants.py``.
* Suspicious-margin filter mirrors ``trend_detector`` (-5% .. 90%).
* Protected-category canonicalization reuses ``mix_analyzer._canonicalize_protected``
  so cigarette variants merge consistently across both tools.
* Protected entries surface in ``protected_info[]`` separately — they are
  visible (so the AI can flag the signal) but never appear in
  ``compressing_categories[]`` (cannot be a recommendation target).

Return contract (success)::

    {
        "source": "data.json:retail_sales.by_category_by_month",
        "as_of_date": "YYYY-MM-DD",
        "window": {
            "months": int,
            "start_period": "YYYY-MM",
            "end_period": "YYYY-MM",
        },
        "top_n": int,
        "categories_evaluated": int,
        "categories_skipped_thin_data": int,
        "categories_skipped_suspicious": int,
        "target_gross_margin_pct": float | None,
        "compressing_categories": [CompressionEntry, ...],
        "expanding_categories":  [CompressionEntry, ...],
        "protected_info":        [ProtectedEntry, ...],
        "summary_ka": str,
        "notes": [str, ...],
    }

Each ``CompressionEntry``::

    {
        "category": str,
        "raw_label": str,
        "gm_first_pct": float,
        "gm_last_pct": float,
        "delta_pp": float,                 # negative = compression
        "revenue_recent_ge": float,        # avg of last 2 months in window
        "compression_score": float,        # |min(delta_pp, 0)| × revenue_recent
        "months_in_window": int,
        "flag": "🔴 COMPRESSING" | "🟢 EXPANDING",
    }

Each ``ProtectedEntry`` adds ``canonical_label`` + ``raw_labels[]`` and
``flag = "🔒 PROTECTED"`` + ``reason_ka``.

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from dashboard_pipeline.ai.mix_analyzer import (
    PROTECTED_REASON_KA,
    _canonicalize_protected,
)
from dashboard_pipeline.constants import (
    MARGIN_RADAR_DEFAULT_WINDOW_MONTHS,
    MARGIN_RADAR_EXPANSION_THRESHOLD_PP,
    MARGIN_RADAR_MAX_WINDOW_MONTHS,
    MARGIN_RADAR_MIN_MONTHS_IN_WINDOW,
    MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE,
    MARGIN_RADAR_MIN_WINDOW_MONTHS,
    PROTECTED_CATEGORY_SUBSTRINGS,
    USER_TARGET_GROSS_MARGIN_PCT,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_N = 5
MIN_TOP_N = 3
MAX_TOP_N = 15

FLAG_COMPRESSING = "🔴 COMPRESSING"
FLAG_EXPANDING = "🟢 EXPANDING"
FLAG_PROTECTED = "🔒 PROTECTED"

SOURCE_LABEL = "data.json:retail_sales.by_category_by_month"

# Mirror trend_detector — categories with margin outside this band are
# excluded as data-quality issues (negative cost, unit error, etc.).
SUSPICIOUS_MARGIN_PCT_LOW = -5.0
SUSPICIOUS_MARGIN_PCT_HIGH = 90.0


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------

def _resolve_window_months(raw: Any) -> int:
    try:
        value = int(raw) if raw is not None else MARGIN_RADAR_DEFAULT_WINDOW_MONTHS
    except (TypeError, ValueError):
        return MARGIN_RADAR_DEFAULT_WINDOW_MONTHS
    if value < MARGIN_RADAR_MIN_WINDOW_MONTHS:
        return MARGIN_RADAR_MIN_WINDOW_MONTHS
    if value > MARGIN_RADAR_MAX_WINDOW_MONTHS:
        return MARGIN_RADAR_MAX_WINDOW_MONTHS
    return value


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


def _resolve_target_gm(raw: Any) -> Optional[float]:
    """Return user-supplied target GM, default if None, or None if invalid.

    Unlike mix_analyzer, target_gross_margin_pct is *informational only* in
    margin_radar — radar reports trends, not gap closure plans. So an invalid
    value silently falls back to the default rather than erroring.
    """
    if raw is None:
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    if value < 0.0 or value > 100.0:
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    return value


def _resolve_protected_override(raw: Any) -> Optional[Tuple[str, ...]]:
    """Same semantics as mix_analyzer._resolve_protected_override."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        cleaned = tuple(
            str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()
        )
        if not cleaned and len(raw) > 0:
            return None
        return cleaned
    return None


# ---------------------------------------------------------------------------
# Period & series helpers
# ---------------------------------------------------------------------------

def _is_period_string(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 7
        and value[4] == "-"
        and value[:4].isdigit()
        and value[5:].isdigit()
    )


def _all_periods(rows: List[Dict[str, Any]]) -> List[str]:
    """Return sorted unique YYYY-MM periods present in rows."""
    seen = {r.get("month") for r in rows}
    return sorted(p for p in seen if _is_period_string(p))


def _window_periods(all_periods: List[str], window_months: int) -> List[str]:
    """Return the last ``window_months`` periods from sorted all_periods.

    If fewer than window_months periods exist, returns whatever is there —
    caller decides whether to error out via MIN_MONTHS_IN_WINDOW.
    """
    if not all_periods:
        return []
    return all_periods[-window_months:]


def _is_suspicious(gm_pct: Any) -> bool:
    if gm_pct is None:
        return False
    try:
        m = float(gm_pct)
    except (TypeError, ValueError):
        return False
    return m < SUSPICIOUS_MARGIN_PCT_LOW or m > SUSPICIOUS_MARGIN_PCT_HIGH


# ---------------------------------------------------------------------------
# Per-category aggregation across the window
# ---------------------------------------------------------------------------

def _aggregate_window(
    rows: List[Dict[str, Any]],
    window: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Group rows by canonical category key, keeping only window periods.

    Returns ``{key: {"category": str, "raw_label": str,
                     "by_period": {period: row}, ...}}`` so downstream code
    can compute per-canonical aggregates (revenue/cost/profit summed per
    period across raw labels — needed before canonicalization step).

    NB: raw labels are kept distinct here (so the canonicalizer can later
    merge cigarette variants); per-period values are stored as-is per raw
    label and aggregated by the canonicalizer.
    """
    window_set = set(window)
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        period = row.get("month")
        if period not in window_set:
            continue
        key = row.get("normalized_category") or row.get("category")
        if not key:
            continue
        key_str = str(key)
        bucket = grouped.setdefault(
            key_str,
            {
                "category": key_str,
                "raw_label": str(row.get("category") or key_str),
                "by_period": {},
            },
        )
        bucket["by_period"][period] = row
    return grouped


def _series_metrics(
    by_period: Dict[str, Dict[str, Any]],
    window: List[str],
) -> Optional[Dict[str, Any]]:
    """Compute first/last GM, recent revenue (last 2 months avg), and
    months_in_window for one canonical (post-merge) category. Returns None
    if data is too thin or any window point is suspicious.
    """
    available = [p for p in window if p in by_period]
    if len(available) < MARGIN_RADAR_MIN_MONTHS_IN_WINDOW:
        return {"_skip": "thin_data"}

    # Suspicious filter — drop the whole category if any window point is bad.
    for p in available:
        if _is_suspicious(by_period[p].get("gross_margin_pct")):
            return {"_skip": "suspicious"}

    first_period = available[0]
    last_period = available[-1]
    first_row = by_period[first_period]
    last_row = by_period[last_period]

    try:
        gm_first = float(first_row.get("gross_margin_pct") or 0.0)
        gm_last = float(last_row.get("gross_margin_pct") or 0.0)
    except (TypeError, ValueError):
        return {"_skip": "thin_data"}

    # Revenue smoothing: average of last 2 available periods.
    recent_periods = available[-2:]
    revenues = []
    for p in recent_periods:
        try:
            revenues.append(float(by_period[p].get("revenue_ge") or 0.0))
        except (TypeError, ValueError):
            continue
    if not revenues:
        return {"_skip": "thin_data"}
    rev_recent = sum(revenues) / len(revenues)

    if rev_recent < MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE:
        return {"_skip": "thin_data"}

    delta_pp = gm_last - gm_first
    return {
        "gm_first_pct": round(gm_first, 4),
        "gm_last_pct": round(gm_last, 4),
        "delta_pp": round(delta_pp, 4),
        "revenue_recent_ge": round(rev_recent, 2),
        "months_in_window": len(available),
        "first_period": first_period,
        "last_period": last_period,
    }


# ---------------------------------------------------------------------------
# Canonical pre-merge for per-period rows (cigarettes have 3 variants)
# ---------------------------------------------------------------------------

def _merge_protected_series(
    grouped: Dict[str, Dict[str, Any]],
    substrings: Tuple[str, ...],
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Walk grouped buckets; for each protected substring, sum revenue/cost
    per period across all matching raw labels into one canonical bucket.

    Returns (remainder_grouped, protected_buckets) where ``protected_buckets``
    has the same structure as a grouped value plus ``canonical_label`` +
    ``raw_labels[]``.

    Why not reuse mix_analyzer._canonicalize_protected directly? That helper
    works on snapshot entries (one row per category). Here we need to merge
    across *time-series rows* — sum revenues per period, then recompute
    margin per period from the summed values. Different shape, same intent.
    """
    if not substrings:
        return grouped, []

    protected_buckets: List[Dict[str, Any]] = []
    consumed_keys: set = set()

    for sub in substrings:
        matches = [
            (k, v) for k, v in grouped.items()
            if k not in consumed_keys and sub in v["category"]
        ]
        if not matches:
            continue

        # Sum revenue/cost per period across matched raw labels.
        merged_by_period: Dict[str, Dict[str, Any]] = {}
        all_periods_seen: set = set()
        raw_labels: List[str] = []
        for key, bucket in matches:
            consumed_keys.add(key)
            raw_labels.append(bucket["raw_label"])
            for period, row in bucket["by_period"].items():
                all_periods_seen.add(period)
                slot = merged_by_period.setdefault(
                    period,
                    {"month": period, "revenue_ge": 0.0, "cost_ge": 0.0,
                     "profit_ge": 0.0},
                )
                try:
                    slot["revenue_ge"] += float(row.get("revenue_ge") or 0.0)
                    slot["cost_ge"] += float(row.get("cost_ge") or 0.0)
                    slot["profit_ge"] += float(row.get("profit_ge") or 0.0)
                except (TypeError, ValueError):
                    continue

        # Recompute per-period margin from summed revenue/profit.
        for period, slot in merged_by_period.items():
            rev = slot["revenue_ge"]
            slot["gross_margin_pct"] = (
                (slot["profit_ge"] / rev * 100.0) if rev > 0 else 0.0
            )

        canonical = min((label for _, b in matches for label in [b["category"]]), key=len)
        protected_buckets.append(
            {
                "canonical_label": canonical,
                "raw_labels": raw_labels,
                "category": canonical,
                "by_period": merged_by_period,
            }
        )

    remainder = {k: v for k, v in grouped.items() if k not in consumed_keys}
    return remainder, protected_buckets


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary_ka(
    *,
    window_months: int,
    start_period: str,
    end_period: str,
    target_gm: Optional[float],
    compressing: List[Dict[str, Any]],
    expanding: List[Dict[str, Any]],
    protected_info: List[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    header = (
        f"**Margin Compression Radar** · ფანჯარა "
        f"**{window_months} თვე** ({start_period} → {end_period})"
    )
    if target_gm is not None:
        header += f" · სამიზნე GM **{target_gm:.2f}%** (informational)"
    header += "."
    parts.append(header)

    if compressing:
        top = compressing[0]
        parts.append(
            f"🔴 უმძიმესი compression: **{top['category']}** "
            f"({top['gm_first_pct']:.2f}% → {top['gm_last_pct']:.2f}%, "
            f"Δ **{top['delta_pp']:+.2f}pp**, recent revenue {top['revenue_recent_ge']:,.0f} ₾)."
        )
        if len(compressing) > 1:
            parts.append(
                f"სხვა compressing კატეგორიები: {len(compressing) - 1} "
                f"(ცხრილი `compressing_categories[]`-ში)."
            )
    else:
        parts.append("🔴 compressing კატეგორია — ვერ მოიძებნა (ფანჯარა + filter-ები აკმაყოფილებენ კრიტერიუმებს).")

    if expanding:
        top = expanding[0]
        parts.append(
            f"🟢 ყველაზე ძლიერი expansion: **{top['category']}** "
            f"({top['gm_first_pct']:.2f}% → {top['gm_last_pct']:.2f}%, "
            f"Δ **{top['delta_pp']:+.2f}pp**)."
        )

    if protected_info:
        for p in protected_info:
            verdict = (
                "compressing" if p["delta_pp"] < 0
                else ("expanding" if p["delta_pp"] > 0 else "stable")
            )
            parts.append(
                f"🔒 **{p.get('canonical_label', p['category'])}** ({verdict} "
                f"{p['delta_pp']:+.2f}pp, recent revenue {p['revenue_recent_ge']:,.0f} ₾) "
                f"— protected, informational only, რეკომენდაცია არ ეძლევა."
            )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_margin_compression(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    window_months: Any = None,
    top_n: Any = None,
    target_gross_margin_pct: Any = None,
    protected_override: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """See module docstring for the full return contract."""
    win = _resolve_window_months(window_months)
    n = _resolve_top_n(top_n)
    target_gm = _resolve_target_gm(target_gross_margin_pct)
    override = _resolve_protected_override(protected_override)
    protected_subs: Tuple[str, ...] = (
        tuple(PROTECTED_CATEGORY_SUBSTRINGS) if override is None else override
    )

    if today is None:
        today = date.today()

    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("margin_radar data_loader failed: %s", exc)
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
    rows = retail.get("by_category_by_month") or []
    if not isinstance(rows, list) or not rows:
        return {
            "error": (
                "`retail_sales.by_category_by_month` ცარიელია — margin radar "
                "შეუძლებელია."
            ),
            "hint": "გაუშვი `python generate_dashboard_data.py` და გაიმეორე ანალიზი.",
        }

    all_periods = _all_periods(rows)
    if len(all_periods) < MARGIN_RADAR_MIN_MONTHS_IN_WINDOW:
        return {
            "error": (
                f"მონაცემთა შემცველი თვეების რაოდენობა ({len(all_periods)}) "
                f"მინიმუმს ({MARGIN_RADAR_MIN_MONTHS_IN_WINDOW}) ვერ აღწევს — "
                f"trend ვერ დადგინდება."
            ),
            "hint": "გადაამოწმე rs Excel ფაილების coverage.",
        }

    window = _window_periods(all_periods, win)
    if len(window) < MARGIN_RADAR_MIN_MONTHS_IN_WINDOW:
        return {
            "error": (
                f"ფანჯარაში მხოლოდ {len(window)} თვე მოხვდა — minimum "
                f"{MARGIN_RADAR_MIN_MONTHS_IN_WINDOW}."
            ),
            "hint": "შეამცირე window_months ან გადაამოწმე pipeline output.",
        }

    grouped = _aggregate_window(rows, window)
    remainder, protected_groups = _merge_protected_series(grouped, protected_subs)

    # Score the remainder (non-protected) categories.
    compressing: List[Dict[str, Any]] = []
    expanding: List[Dict[str, Any]] = []
    skipped_thin = 0
    skipped_suspicious = 0
    evaluated = 0

    for key, bucket in remainder.items():
        metrics = _series_metrics(bucket["by_period"], window)
        if metrics is None or "_skip" in metrics:
            if metrics and metrics.get("_skip") == "suspicious":
                skipped_suspicious += 1
            else:
                skipped_thin += 1
            continue
        evaluated += 1

        delta_pp = metrics["delta_pp"]
        rev_recent = metrics["revenue_recent_ge"]
        compression_score = abs(min(delta_pp, 0.0)) * rev_recent
        entry = {
            "category": bucket["category"],
            "raw_label": bucket["raw_label"],
            "gm_first_pct": metrics["gm_first_pct"],
            "gm_last_pct": metrics["gm_last_pct"],
            "delta_pp": delta_pp,
            "revenue_recent_ge": rev_recent,
            "compression_score": round(compression_score, 2),
            "months_in_window": metrics["months_in_window"],
        }
        if delta_pp < 0:
            compressing.append({**entry, "flag": FLAG_COMPRESSING})
        elif delta_pp > MARGIN_RADAR_EXPANSION_THRESHOLD_PP:
            expanding.append({**entry, "flag": FLAG_EXPANDING})
        # ±threshold band → ignored (noise floor); still counts as evaluated.

    compressing.sort(key=lambda e: -e["compression_score"])
    expanding.sort(key=lambda e: -e["delta_pp"])
    compressing_top = compressing[:n]
    expanding_top = expanding[:n]

    # Score protected groups separately (informational).
    protected_info: List[Dict[str, Any]] = []
    for bucket in protected_groups:
        metrics = _series_metrics(bucket["by_period"], window)
        if metrics is None or "_skip" in metrics:
            # Surface even thin-data protected entries with a note — user
            # cares about cigarettes regardless of data quality. But mark
            # the gap so the AI can warn about it.
            protected_info.append(
                {
                    "canonical_label": bucket["canonical_label"],
                    "raw_labels": bucket["raw_labels"],
                    "category": bucket["category"],
                    "gm_first_pct": None,
                    "gm_last_pct": None,
                    "delta_pp": 0.0,
                    "revenue_recent_ge": 0.0,
                    "compression_score": 0.0,
                    "months_in_window": 0,
                    "reason_ka": PROTECTED_REASON_KA,
                    "flag": FLAG_PROTECTED,
                    "data_quality_note_ka": (
                        f"ფანჯარაში მონაცემები ვერ მოიკრიფა "
                        f"({metrics.get('_skip') if metrics else 'unknown'})"
                    ),
                }
            )
            continue
        delta_pp = metrics["delta_pp"]
        rev_recent = metrics["revenue_recent_ge"]
        compression_score = abs(min(delta_pp, 0.0)) * rev_recent
        protected_info.append(
            {
                "canonical_label": bucket["canonical_label"],
                "raw_labels": bucket["raw_labels"],
                "category": bucket["category"],
                "gm_first_pct": metrics["gm_first_pct"],
                "gm_last_pct": metrics["gm_last_pct"],
                "delta_pp": delta_pp,
                "revenue_recent_ge": rev_recent,
                "compression_score": round(compression_score, 2),
                "months_in_window": metrics["months_in_window"],
                "reason_ka": PROTECTED_REASON_KA,
                "flag": FLAG_PROTECTED,
            }
        )

    summary_ka = _build_summary_ka(
        window_months=len(window),
        start_period=window[0],
        end_period=window[-1],
        target_gm=target_gm,
        compressing=compressing_top,
        expanding=expanding_top,
        protected_info=protected_info,
    )

    notes: List[str] = [
        (
            f"ფანჯარა: ბოლო {len(window)} თვე ({window[0]} → {window[-1]}). "
            "შესაცვლელად გადააწოდე `window_months` (3..12)."
        ),
        (
            f"compression_score = |min(Δpp, 0)| × revenue_recent. "
            f"მხოლოდ Δpp < 0 ანგარიშდება. რანჟირება desc."
        ),
        (
            f"expansion threshold: Δpp > +{MARGIN_RADAR_EXPANSION_THRESHOLD_PP:.1f}pp. "
            "ამის ქვემოთ — noise."
        ),
        (
            "🔒 protected კატეგორიები (`protected_info[]`) ცალკე bucket-ში — "
            "ხილვადი informational signal-ად, მაგრამ რეკომენდაცია არ ეძლევა."
        ),
    ]
    if skipped_thin:
        notes.append(
            f"ⓘ {skipped_thin} კატეგორია გამოტოვდა მონაცემთა სიმცირის გამო "
            f"(< {MARGIN_RADAR_MIN_MONTHS_IN_WINDOW} თვე ფანჯარაში ან "
            f"recent revenue < {MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE:.0f} ₾)."
        )
    if skipped_suspicious:
        notes.append(
            f"⚠️ {skipped_suspicious} კატეგორია გამოტოვდა margin-ის out-of-range-ის "
            f"გამო ([{SUSPICIOUS_MARGIN_PCT_LOW}%..{SUSPICIOUS_MARGIN_PCT_HIGH}%])."
        )
    notes.append(
        "ⓘ Δpp არის raw historical (gm_last − gm_first), არ არის forecast — "
        "trend-ის ექსტრაპოლაციაზე დასკვნა არ უნდა გავაკეთოთ."
    )

    return {
        "source": SOURCE_LABEL,
        "as_of_date": today.isoformat(),
        "window": {
            "months": len(window),
            "start_period": window[0],
            "end_period": window[-1],
        },
        "top_n": n,
        "categories_evaluated": evaluated,
        "categories_skipped_thin_data": skipped_thin,
        "categories_skipped_suspicious": skipped_suspicious,
        "target_gross_margin_pct": target_gm,
        "compressing_categories": compressing_top,
        "expanding_categories": expanding_top,
        "protected_info": protected_info,
        "summary_ka": summary_ka,
        "notes": notes,
    }


__all__ = [
    "DEFAULT_TOP_N",
    "MIN_TOP_N",
    "MAX_TOP_N",
    "FLAG_COMPRESSING",
    "FLAG_EXPANDING",
    "FLAG_PROTECTED",
    "SOURCE_LABEL",
    "SUSPICIOUS_MARGIN_PCT_LOW",
    "SUSPICIOUS_MARGIN_PCT_HIGH",
    "analyze_margin_compression",
]
