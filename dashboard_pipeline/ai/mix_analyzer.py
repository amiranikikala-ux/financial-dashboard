"""Phase 2.3 — Category Mix Analyzer.

Reads the pre-computed ``retail_sales.by_category`` bundle from ``data.json``
(645 rows, each with revenue_ge + cost_ge + profit_ge + gross_margin_pct +
object_breakdown) and answers "how do I move portfolio gross margin from
where it is today to my target, holding cigarettes constant?".

The tool is **data-driven**, not config-driven: targets and protected
categories live as module-level constants (`USER_TARGET_GROSS_MARGIN_PCT`,
`PROTECTED_CATEGORY_SUBSTRINGS`), but every number quoted in the output
comes from the live data.json — memory-based approximations are not used.

Return contract (success)::

    {
        "source": "data.json:retail_sales.by_category",
        "as_of_date": "YYYY-MM-DD",
        "store": "total" | "ოზურგეთი" | "დვაბზუ",
        "top_n": int,
        "target_gross_margin_pct": float,
        "portfolio": {
            "revenue_ge": float,
            "profit_ge": float,
            "gross_margin_pct": float,
            "category_count": int,
        },
        "target": {
            "gross_margin_pct": float,
            "gap_pp": float,          # signed: positive = below target
            "gap_profit_ge": float,   # absolute profit lift at constant revenue
        },
        "protected_categories": [
            {canonical_label, raw_labels[], revenue_ge, cost_ge, profit_ge,
             gross_margin_pct, portfolio_share_pct, reason_ka, flag},
        ],
        "drag_categories":  [CategoryEntry, ...],   # low margin × high share
        "lift_categories":  [CategoryEntry, ...],   # high margin headroom
        "recommended_shifts": [
            {action_ka, from_category, to_category, revenue_shift_ge, gm_impact_pp},
        ],
        "projected_portfolio": {
            "if_all_recommendations_applied": {
                gross_margin_pct, delta_pp, reaches_target,
            },
        },
        "summary_ka": str,
        "notes": [str, ...],
    }

Each ``CategoryEntry``::

    {
        "category": str,
        "raw_label": str,
        "revenue_ge": float,
        "cost_ge": float,
        "profit_ge": float,
        "gross_margin_pct": float,
        "portfolio_share_pct": float,
        "flag": "🔴 DRAG" | "🟢 LIFT",
    }

Failure::

    {"error": "<Georgian message>", "hint": "<actionable hint>"}
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from dashboard_pipeline.ai.forecasting import (
    STORE_DVABZU,
    STORE_OZURGETI,
    STORE_TOTAL,
    SUPPORTED_STORES,
    _STORE_ALIASES,
)
from dashboard_pipeline.constants import (
    MIX_ANALYZER_MARGIN_BAND_PP,
    MIX_ANALYZER_MAX_SHIFT_PCT,
    MIX_ANALYZER_MIN_DRAG_SHARE_PCT,
    MIX_ANALYZER_MIN_LIFT_SHARE_PCT,
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

FLAG_DRAG = "🔴 DRAG"
FLAG_LIFT = "🟢 LIFT"
FLAG_PROTECTED = "🔒 PROTECTED"

SOURCE_LABEL = "data.json:retail_sales.by_category"

PROTECTED_REASON_KA = (
    "მომხმარებლის გადაწყვეტილება — კარგად გასაყიდი, წილი და მარჟა უცვლელი რჩება."
)


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


def _resolve_target_gm(raw: Any) -> float:
    if raw is None:
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    if math.isnan(value) or math.isinf(value):
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    # Accept 0–100 band; anything else falls back to default.
    if value < 0.0 or value > 100.0:
        return float(USER_TARGET_GROSS_MARGIN_PCT)
    return value


def _resolve_protected_override(raw: Any) -> Optional[Tuple[str, ...]]:
    """Return tuple of substrings to override defaults, or None to keep them.

    Empty list/tuple → explicit "no protected categories" → return empty tuple.
    Invalid input (not a list) → None (use defaults).
    """
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        cleaned = tuple(
            str(x).strip() for x in raw if isinstance(x, str) and str(x).strip()
        )
        # Distinguish "empty override intentionally" from "invalid input" by
        # letting the caller see the empty tuple — means "no protection".
        if not cleaned and len(raw) > 0:
            # user passed non-string garbage only → fall back to default
            return None
        return cleaned
    return None


# ---------------------------------------------------------------------------
# Per-store metric extraction
# ---------------------------------------------------------------------------

def _category_metrics_for_store(
    category: Dict[str, Any],
    store: str,
) -> Optional[Dict[str, float]]:
    """Return ``{revenue_ge, cost_ge, profit_ge, gross_margin_pct}`` for the
    requested store — or ``None`` if this category has zero revenue there.

    For ``store == STORE_TOTAL`` we use the top-level aggregate. For a
    specific store we look up the matching ``object_breakdown`` entry.
    """
    if store == STORE_TOTAL:
        try:
            revenue = float(category.get("revenue_ge") or 0.0)
            cost = float(category.get("cost_ge") or 0.0)
            profit = float(category.get("profit_ge") or 0.0)
            margin = float(category.get("gross_margin_pct") or 0.0)
        except (TypeError, ValueError):
            return None
        if revenue <= 0:
            return None
        return {
            "revenue_ge": round(revenue, 2),
            "cost_ge": round(cost, 2),
            "profit_ge": round(profit, 2),
            "gross_margin_pct": round(margin, 4),
        }

    breakdown = category.get("object_breakdown") or []
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
            margin = float(entry.get("gross_margin_pct") or 0.0)
        except (TypeError, ValueError):
            continue
        if revenue <= 0:
            continue
        return {
            "revenue_ge": round(revenue, 2),
            "cost_ge": round(cost, 2),
            "profit_ge": round(profit, 2),
            "gross_margin_pct": round(margin, 4),
        }
    return None


def _build_category_entry(
    category: Dict[str, Any],
    metrics: Dict[str, float],
) -> Dict[str, Any]:
    normalized = str(category.get("normalized_category") or "").strip()
    raw = str(category.get("category") or "").strip()
    label = normalized or raw or "უცნობი კატეგორია"
    return {
        "category": label,
        "raw_label": raw or normalized or label,
        **metrics,
    }


# ---------------------------------------------------------------------------
# Canonicalization of protected categories
# ---------------------------------------------------------------------------

def _canonicalize_protected(
    entries: List[Dict[str, Any]],
    substrings: Iterable[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merge entries whose label contains any protected substring into one
    combined entry per substring. Returns ``(protected_merged, remainder)``.

    Protected entries carry:
      * ``canonical_label`` — the shortest matching raw label (readable)
      * ``raw_labels`` — list of every merged label (audit trail)
      * weighted gross margin
      * ``reason_ka`` + ``flag`` set to PROTECTED
      * ``portfolio_share_pct`` is filled later by the caller

    Non-matching entries stay in ``remainder`` unchanged.
    """
    subs = [s for s in substrings if s]
    if not subs:
        return [], list(entries)

    merged: List[Dict[str, Any]] = []
    matched_ids: set = set()

    for sub in subs:
        matches = [
            e for e in entries
            if id(e) not in matched_ids and sub in e["category"]
        ]
        if not matches:
            continue
        for m in matches:
            matched_ids.add(id(m))

        total_rev = sum(e["revenue_ge"] for e in matches)
        total_cost = sum(e["cost_ge"] for e in matches)
        total_profit = sum(e["profit_ge"] for e in matches)
        gm = (total_profit / total_rev * 100.0) if total_rev > 0 else 0.0
        canonical = min((e["category"] for e in matches), key=len)
        merged.append(
            {
                "canonical_label": canonical,
                "raw_labels": [e["category"] for e in matches],
                "revenue_ge": round(total_rev, 2),
                "cost_ge": round(total_cost, 2),
                "profit_ge": round(total_profit, 2),
                "gross_margin_pct": round(gm, 4),
                "portfolio_share_pct": 0.0,  # filled by caller
                "reason_ka": PROTECTED_REASON_KA,
                "flag": FLAG_PROTECTED,
            }
        )

    remainder = [e for e in entries if id(e) not in matched_ids]
    return merged, remainder


# ---------------------------------------------------------------------------
# Portfolio aggregation
# ---------------------------------------------------------------------------

def _compute_portfolio(
    entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Revenue-weighted portfolio over all entries (protected + remainder).

    Uses ``sum()`` (per Sprint 3e convention) to avoid floating-point drift
    from iterative ``+=`` accumulation.
    """
    revenue = sum(e["revenue_ge"] for e in entries)
    profit = sum(e["profit_ge"] for e in entries)
    gm = (profit / revenue * 100.0) if revenue > 0 else 0.0
    return {
        "revenue_ge": round(revenue, 2),
        "profit_ge": round(profit, 2),
        "gross_margin_pct": round(gm, 4),
        "category_count": len(entries),
    }


# ---------------------------------------------------------------------------
# DRAG / LIFT ranking
# ---------------------------------------------------------------------------

def _rank_drag_lift(
    entries: List[Dict[str, Any]],
    *,
    portfolio_gm: float,
    portfolio_revenue: float,
    band_pp: float,
    min_drag_share_pct: float,
    min_lift_share_pct: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Classify non-protected entries into DRAG (below band and sizable) and
    LIFT (above band with growth room). Adds ``portfolio_share_pct`` + flag.
    """
    if portfolio_revenue <= 0:
        return [], []

    drag: List[Dict[str, Any]] = []
    lift: List[Dict[str, Any]] = []
    for entry in entries:
        share = entry["revenue_ge"] / portfolio_revenue * 100.0
        annotated = {
            "category": entry["category"],
            "raw_label": entry.get("raw_label", entry["category"]),
            "revenue_ge": entry["revenue_ge"],
            "cost_ge": entry["cost_ge"],
            "profit_ge": entry["profit_ge"],
            "gross_margin_pct": entry["gross_margin_pct"],
            "portfolio_share_pct": round(share, 2),
        }
        if (
            entry["gross_margin_pct"] < portfolio_gm - band_pp
            and share >= min_drag_share_pct
        ):
            drag.append({**annotated, "flag": FLAG_DRAG})
        elif (
            entry["gross_margin_pct"] > portfolio_gm + band_pp
            and share >= min_lift_share_pct
        ):
            lift.append({**annotated, "flag": FLAG_LIFT})

    drag.sort(key=lambda e: (-e["portfolio_share_pct"], e["gross_margin_pct"]))
    lift.sort(key=lambda e: (-e["gross_margin_pct"], -e["portfolio_share_pct"]))
    return drag, lift


# ---------------------------------------------------------------------------
# Recommended shifts
# ---------------------------------------------------------------------------

def _suggest_shifts(
    drag: List[Dict[str, Any]],
    lift: List[Dict[str, Any]],
    *,
    target_gap_pp: float,
    portfolio_revenue: float,
    max_shift_pct: float,
    max_pairs: int,
) -> List[Dict[str, Any]]:
    """Greedy: pair each top DRAG with the single best LIFT, size the shift
    to close remaining gap but cap at ``max_shift_pct`` of source revenue.
    Stop once cumulative impact closes the gap or we hit ``max_pairs``.
    """
    if not drag or not lift or target_gap_pp <= 0 or portfolio_revenue <= 0:
        return []

    best_lift = lift[0]
    shifts: List[Dict[str, Any]] = []
    remaining_gap_pp = target_gap_pp

    for source in drag[:max_pairs]:
        if remaining_gap_pp <= 0:
            break
        margin_diff_pp = best_lift["gross_margin_pct"] - source["gross_margin_pct"]
        if margin_diff_pp <= 0:
            continue
        max_shift_ge = max_shift_pct / 100.0 * source["revenue_ge"]
        # gm_impact_pp = X × margin_diff / portfolio_rev  (X in ₾)
        x_needed = remaining_gap_pp * portfolio_revenue / margin_diff_pp
        shift_ge = min(max_shift_ge, x_needed)
        if shift_ge <= 0:
            continue
        gm_impact_pp = shift_ge * margin_diff_pp / portfolio_revenue
        shifts.append(
            {
                "action_ka": (
                    f"გადაანაცვლე {shift_ge:,.0f} ₾ რევენიუ "
                    f"{source['category']}-დან {best_lift['category']}-ში."
                ),
                "from_category": source["category"],
                "to_category": best_lift["category"],
                "revenue_shift_ge": round(shift_ge, 2),
                "gm_impact_pp": round(gm_impact_pp, 3),
            }
        )
        remaining_gap_pp -= gm_impact_pp
    return shifts


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def _project_outcome(
    shifts: List[Dict[str, Any]],
    portfolio_gm: float,
    target_gm: float,
) -> Dict[str, Any]:
    total_impact = sum(s["gm_impact_pp"] for s in shifts)
    new_gm = portfolio_gm + total_impact
    return {
        "if_all_recommendations_applied": {
            "gross_margin_pct": round(new_gm, 3),
            "delta_pp": round(total_impact, 3),
            "reaches_target": new_gm + 1e-9 >= target_gm,
        },
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _build_summary_ka(
    *,
    store_label: str,
    portfolio: Dict[str, Any],
    target_gm: float,
    target_gap_pp: float,
    gap_profit_ge: float,
    protected: List[Dict[str, Any]],
    drag: List[Dict[str, Any]],
    lift: List[Dict[str, Any]],
    shifts: List[Dict[str, Any]],
    projected: Dict[str, Any],
) -> str:
    portfolio_gm = portfolio["gross_margin_pct"]
    parts: List[str] = []
    header = (
        f"**Mix ანალიზი** ({store_label}) · "
        f"ახლანდელი portfolio GM **{portfolio_gm:.2f}%** · "
        f"სამიზნე **{target_gm:.2f}%** · "
    )
    if target_gap_pp > 0:
        header += (
            f"გაპი **+{target_gap_pp:.2f}pp** "
            f"({gap_profit_ge:,.0f} ₾ დამატებითი მოგება, თუ რევენიუ უცვლელი დარჩება)."
        )
    elif target_gap_pp < 0:
        header += (
            f"GM სამიზნეზე **{-target_gap_pp:.2f}pp-ით** მაღალია — მიზანი მიღწეულია."
        )
    else:
        header += "GM სამიზნეს ზუსტად ემთხვევა."
    parts.append(header)

    if protected:
        p = protected[0]
        variants_note = (
            f"{len(p['raw_labels'])} ვარიანტი გაერთიანებული"
            if len(p["raw_labels"]) > 1
            else "1 ვარიანტი"
        )
        parts.append(
            f"🔒 **{p['canonical_label']}** დაცულია "
            f"(წილი {p['portfolio_share_pct']:.1f}%, მარჟა {p['gross_margin_pct']:.2f}% — "
            f"{variants_note})."
        )

    if drag:
        top_drag = drag[0]
        parts.append(
            f"🔴 უდიდესი DRAG: **{top_drag['category']}** "
            f"(წილი {top_drag['portfolio_share_pct']:.1f}%, "
            f"მარჟა {top_drag['gross_margin_pct']:.2f}%)."
        )
    if lift:
        top_lift = lift[0]
        parts.append(
            f"🟢 საუკეთესო LIFT: **{top_lift['category']}** "
            f"(წილი {top_lift['portfolio_share_pct']:.1f}%, "
            f"მარჟა {top_lift['gross_margin_pct']:.2f}%)."
        )

    if shifts:
        proj = projected["if_all_recommendations_applied"]
        if proj["reaches_target"]:
            verdict = "მიზანი მიიღწევა"
        else:
            verdict = (
                f"სამიზნეს სრულად ვერ ეხება realistic ფარგლებში "
                f"(დარჩენა {target_gm - proj['gross_margin_pct']:.2f}pp)"
            )
        parts.append(
            f"რეკომენდაცია: {len(shifts)} გადანაცვლება → "
            f"projected GM **{proj['gross_margin_pct']:.2f}%** "
            f"(+{proj['delta_pp']:.2f}pp) — {verdict}."
        )
    elif target_gap_pp > 0:
        parts.append(
            "რეკომენდაცია: realistic shifts ვერ მოიძებნა — LIFT კატეგორიები "
            "საკმარისი headroom-ით არ არის ან DRAG-ები ზღვრულ share-ს ვერ აკმაყოფილებენ."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_category_mix(
    data_loader: Callable[[], Dict[str, Any]],
    *,
    store: Any = None,
    top_n: Any = None,
    protected_override: Any = None,
    target_gross_margin_pct: Any = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Analyze ``retail_sales.by_category`` and propose category-mix shifts.

    See the module docstring for the full return contract.
    """
    canonical_store, store_err = _resolve_store(store)
    if store_err:
        return {"error": store_err, "hint": "გამოიყენე enum: total / ოზურგეთი / დვაბზუ."}
    assert canonical_store is not None

    n = _resolve_top_n(top_n)
    target_gm = _resolve_target_gm(target_gross_margin_pct)
    override = _resolve_protected_override(protected_override)
    protected_subs: Tuple[str, ...]
    if override is None:
        protected_subs = tuple(PROTECTED_CATEGORY_SUBSTRINGS)
    else:
        protected_subs = override

    if today is None:
        today = date.today()

    try:
        data = data_loader() or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("mix_analyzer data_loader failed: %s", exc)
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
    categories = retail.get("by_category") or []
    if not isinstance(categories, list) or not categories:
        return {
            "error": "`retail_sales.by_category` ცარიელია — mix ანალიზი შეუძლებელია.",
            "hint": (
                "გადაამოწმე რომ retail_sales xlsx ფაილები წაკითხვადია და "
                "active duplicate-policy-ით არის ჩართული."
            ),
        }

    entries: List[Dict[str, Any]] = []
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        metrics = _category_metrics_for_store(cat, canonical_store)
        if metrics is None:
            continue
        entries.append(_build_category_entry(cat, metrics))

    if not entries:
        return {
            "error": (
                f"'{canonical_store}'-ისთვის ერთი კატეგორიაც არ მოიძებნა "
                f"პოზიტიური რევენიუთ."
            ),
            "hint": "სცადე `store='total'`, ან გადაამოწმე რომ object_breakdown ივსება.",
        }

    protected, remainder = _canonicalize_protected(entries, protected_subs)
    portfolio = _compute_portfolio(protected + remainder)

    # Fill portfolio_share_pct on protected entries now that portfolio known.
    portfolio_revenue = portfolio["revenue_ge"]
    if portfolio_revenue <= 0:
        return {
            "error": "portfolio რევენიუ 0-ია — mix ანალიზი შეუძლებელია.",
            "hint": "გადაამოწმე რომ retail_sales-ში revenue_ge სწორად ივსება.",
        }
    for p in protected:
        p["portfolio_share_pct"] = round(
            p["revenue_ge"] / portfolio_revenue * 100.0, 2
        )

    drag, lift = _rank_drag_lift(
        remainder,
        portfolio_gm=portfolio["gross_margin_pct"],
        portfolio_revenue=portfolio_revenue,
        band_pp=MIX_ANALYZER_MARGIN_BAND_PP,
        min_drag_share_pct=MIX_ANALYZER_MIN_DRAG_SHARE_PCT,
        min_lift_share_pct=MIX_ANALYZER_MIN_LIFT_SHARE_PCT,
    )
    drag_top = drag[:n]
    lift_top = lift[:n]

    target_gap_pp = round(target_gm - portfolio["gross_margin_pct"], 4)
    gap_profit_ge = round(max(target_gap_pp, 0.0) / 100.0 * portfolio_revenue, 2)

    shifts = _suggest_shifts(
        drag_top,
        lift_top,
        target_gap_pp=max(target_gap_pp, 0.0),
        portfolio_revenue=portfolio_revenue,
        max_shift_pct=MIX_ANALYZER_MAX_SHIFT_PCT,
        max_pairs=n,
    )
    projected = _project_outcome(
        shifts,
        portfolio_gm=portfolio["gross_margin_pct"],
        target_gm=target_gm,
    )

    store_label = {
        STORE_TOTAL: "ორივე მაღაზია",
        STORE_OZURGETI: "ოზურგეთი",
        STORE_DVABZU: "დვაბზუ",
    }.get(canonical_store, canonical_store)
    summary_ka = _build_summary_ka(
        store_label=store_label,
        portfolio=portfolio,
        target_gm=target_gm,
        target_gap_pp=target_gap_pp,
        gap_profit_ge=gap_profit_ge,
        protected=protected,
        drag=drag_top,
        lift=lift_top,
        shifts=shifts,
        projected=projected,
    )

    notes: List[str] = []
    if protected:
        merged_counts = sum(
            len(p["raw_labels"]) for p in protected if len(p["raw_labels"]) > 1
        )
        if merged_counts:
            notes.append(
                f"🔒 დაცული კატეგორიებში label-ების ვარიანტები გაერთიანებულია "
                f"({merged_counts} raw label → {len(protected)} canonical). "
                f"ცოცხალი შეკვრა იხილე `protected_categories[].raw_labels`-ში."
            )
        else:
            notes.append(
                f"🔒 დაცული კატეგორიები: {len(protected)}. წილი და მარჟა შენარჩუნებულია."
            )
    if target_gap_pp <= 0:
        notes.append(
            "ⓘ portfolio GM სამიზნეზე მაღალია — mix shift-ის საჭიროება ამ მომენტში არაა. "
            "ფოკუსი შეიძლება გადავიტანოთ category-level optimization-ზე (product_profitability)."
        )
    if target_gap_pp > 0 and not shifts:
        notes.append(
            "⚠️ სამიზნე ღიაა, მაგრამ realistic shift-ებით ვერ იხურება. "
            "შესაძლო მიზეზები: LIFT კატეგორია საკმარისად დიდი არაა, ან DRAG-ები "
            "ზღვრულ share-ს ვერ აკმაყოფილებენ. სცადე პარამეტრის გადახედვა ან "
            "product_profitability SKU-დონეზე."
        )
    notes.append(
        "ⓘ რიცხვები `retail_sales.by_category`-დან (retail sales xlsx → pipeline). "
        "Mix shift-ის რეალური გადაწყვეტილება მოითხოვს SKU-დონის ანალიზს "
        "(`analyze_product_profitability`) და მომარაგების/supply-chain შემოწმებას."
    )
    notes.append(
        "ⓘ Cap: ერთი shift მაქსიმუმ source კატეგორიის რევენიუს "
        f"{MIX_ANALYZER_MAX_SHIFT_PCT:.0f}%-ია — realism-ის ზღვარი."
    )

    return {
        "source": SOURCE_LABEL,
        "as_of_date": today.isoformat(),
        "store": canonical_store,
        "top_n": n,
        "target_gross_margin_pct": target_gm,
        "portfolio": portfolio,
        "target": {
            "gross_margin_pct": target_gm,
            "gap_pp": target_gap_pp,
            "gap_profit_ge": gap_profit_ge,
        },
        "protected_categories": protected,
        "drag_categories": drag_top,
        "lift_categories": lift_top,
        "recommended_shifts": shifts,
        "projected_portfolio": projected,
        "summary_ka": summary_ka,
        "notes": notes,
    }


__all__ = [
    "DEFAULT_TOP_N",
    "MIN_TOP_N",
    "MAX_TOP_N",
    "FLAG_DRAG",
    "FLAG_LIFT",
    "FLAG_PROTECTED",
    "SOURCE_LABEL",
    "PROTECTED_REASON_KA",
    "analyze_category_mix",
]
