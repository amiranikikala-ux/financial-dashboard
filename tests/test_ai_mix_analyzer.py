"""Phase 2.3 — Category Mix Analyzer tests.

Covers:
* Portfolio computation: revenue-weighted GM against hand-computed value.
* Protected-category canonicalization: 3 cigarette variants → 1 entry with
  raw_labels preserved + weighted margin.
* Protected-never-reduced: no recommended_shift.from_category matches any
  protected substring (the core safety rule).
* DRAG / LIFT classification: margin band (±3pp) + share thresholds.
* Target gap math: gap_pp + gap_profit_ge (positive when below target).
* summary_ka cites live portfolio GM (not memory approximations).
* Per-store mode: store='ოზურგეთი' reads object_breakdown.
* Realism cap: no shift exceeds 20% of source category revenue.
* Empty / error paths: empty by_category, missing retail_sales, bad store.
* Tool registry: MIX_ANALYZER_TOOL in TOOL_SCHEMAS + dispatcher routing.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.constants import (
    MIX_ANALYZER_MAX_SHIFT_PCT,
    PROTECTED_CATEGORY_SUBSTRINGS,
    USER_TARGET_GROSS_MARGIN_PCT,
)
from dashboard_pipeline.ai.mix_analyzer import (
    DEFAULT_TOP_N,
    FLAG_DRAG,
    FLAG_LIFT,
    FLAG_PROTECTED,
    MAX_TOP_N,
    MIN_TOP_N,
    SOURCE_LABEL,
    _canonicalize_protected,
    _compute_portfolio,
    _resolve_protected_override,
    _resolve_store,
    _resolve_target_gm,
    _resolve_top_n,
    analyze_category_mix,
)


TODAY = date(2026, 4, 24)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cat(
    label: str,
    revenue: float,
    profit: float,
    *,
    ozurgeti_share: float = 0.6,
    normalized: str | None = None,
) -> Dict[str, Any]:
    """Build a by_category entry with auto-computed object_breakdown."""
    cost = revenue - profit
    gm = round((profit / revenue * 100.0) if revenue else 0.0, 4)
    ozu_rev = round(revenue * ozurgeti_share, 2)
    ozu_profit = round(profit * ozurgeti_share, 2)
    dva_rev = round(revenue - ozu_rev, 2)
    dva_profit = round(profit - ozu_profit, 2)
    return {
        "category": label,
        "normalized_category": normalized if normalized is not None else label,
        "revenue_ge": round(revenue, 2),
        "cost_ge": round(cost, 2),
        "profit_ge": round(profit, 2),
        "gross_margin_pct": gm,
        "object_breakdown": [
            {
                "object": "ოზურგეთი",
                "revenue_ge": ozu_rev,
                "cost_ge": round(ozu_rev - ozu_profit, 2),
                "profit_ge": ozu_profit,
                "gross_margin_pct": round(
                    (ozu_profit / ozu_rev * 100.0) if ozu_rev else 0.0, 4
                ),
            },
            {
                "object": "დვაბზუ",
                "revenue_ge": dva_rev,
                "cost_ge": round(dva_rev - dva_profit, 2),
                "profit_ge": dva_profit,
                "gross_margin_pct": round(
                    (dva_profit / dva_rev * 100.0) if dva_rev else 0.0, 4
                ),
            },
        ],
    }


def _make_loader(categories: List[Dict[str, Any]]) -> Any:
    payload = {"retail_sales": {"by_category": categories}}

    def _loader() -> Dict[str, Any]:
        return payload

    return _loader


def _mixed_fixture() -> List[Dict[str, Any]]:
    """A small realistic mix: 3 cigarette variants (protected), 1 big drag,
    1 big lift, plus 2 neutral. Total revenue 1,000,000 ₾.

    Hand-computed portfolio: revenue 1,000,000; profit 150,000; GM=15.00%.
    """
    return [
        _cat("0804 | სიგარეტი", 300_000, 30_000),       # cigarettes #1, 10% gm
        _cat("სიგარეტი", 200_000, 24_000),              # cigarettes #2, 12% gm
        _cat("ელ. სიგარეტი", 10_000, 1_800),            # cigarettes #3, 18% gm
        _cat("0105 | ლუდი ქართული", 150_000, 9_000),    # DRAG (6% gm, 15% share)
        _cat("ნაყინი ჭიქა", 90_000, 27_000),            # LIFT (30% gm, 9% share)
        _cat("2101 | პური თეთრი", 150_000, 22_500),     # neutral (15% gm, 15% share)
        _cat("0901 | გაზიანი სასმელი", 100_000, 35_700),  # LIFT (35.7% gm, 10% share)
    ]


# ---------------------------------------------------------------------------
# 1. Basic portfolio computation
# ---------------------------------------------------------------------------


def test_basic_portfolio_computation_matches_weighted_average() -> None:
    """Portfolio GM equals the revenue-weighted average of per-category GMs."""
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    assert "error" not in result
    portfolio = result["portfolio"]
    # Hand-check: Σ revenue = 1,000,000; Σ profit = 150,000; GM = 15.00%.
    assert portfolio["revenue_ge"] == pytest.approx(1_000_000.0, abs=0.01)
    assert portfolio["profit_ge"] == pytest.approx(150_000.0, abs=0.01)
    assert portfolio["gross_margin_pct"] == pytest.approx(15.0, abs=0.01)
    # category_count reflects post-canonicalization structure: 3 cigarette
    # variants merge into 1 protected entry, plus 4 remainder categories = 5.
    assert portfolio["category_count"] == 5


# ---------------------------------------------------------------------------
# 2. Cigarette variants canonicalized
# ---------------------------------------------------------------------------


def test_cigarette_variants_canonicalized_into_one_protected_entry() -> None:
    """All 3 cigarette labels merge into one protected entry with raw_labels
    list preserved + weighted margin across the 3 sources."""
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    protected = result["protected_categories"]
    assert len(protected) == 1
    entry = protected[0]
    assert entry["flag"] == FLAG_PROTECTED
    assert set(entry["raw_labels"]) == {
        "0804 | სიგარეტი",
        "სიგარეტი",
        "ელ. სიგარეტი",
    }
    # Canonical label = shortest raw label.
    assert entry["canonical_label"] == "სიგარეტი"
    # Weighted margin: (30,000 + 24,000 + 1,800) / (300k + 200k + 10k) = 55,800 / 510,000
    assert entry["gross_margin_pct"] == pytest.approx(10.9412, abs=0.001)
    assert entry["revenue_ge"] == pytest.approx(510_000.0, abs=0.01)
    # Portfolio share: 510k / 1,000k = 51.00%.
    assert entry["portfolio_share_pct"] == pytest.approx(51.0, abs=0.01)


# ---------------------------------------------------------------------------
# 3. Protected never recommended for reduction
# ---------------------------------------------------------------------------


def test_no_recommended_shift_targets_protected_substring() -> None:
    """Safety invariant — no recommended_shift.from_category may contain any
    PROTECTED_CATEGORY_SUBSTRINGS entry. Even when cigarettes look like a
    drag (below portfolio GM), they stay untouched."""
    # Force cigarettes to look very drag-like: big share, very low margin.
    cats = [
        _cat("0804 | სიგარეტი", 600_000, 30_000),  # 60% share, 5% gm
        _cat("ნაყინი ჭიქა", 200_000, 60_000),      # 20% share, 30% gm
        _cat("0105 | ლუდი ქართული", 200_000, 16_000),  # 20% share, 8% gm
    ]
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)
    assert "error" not in result

    shifts = result["recommended_shifts"]
    for sub in PROTECTED_CATEGORY_SUBSTRINGS:
        for shift in shifts:
            assert sub not in shift["from_category"], (
                f"Protected substring '{sub}' leaked into recommended "
                f"shift from_category='{shift['from_category']}'"
            )


# ---------------------------------------------------------------------------
# 4. DRAG identification
# ---------------------------------------------------------------------------


def test_drag_category_identified_and_flagged() -> None:
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    drag = result["drag_categories"]
    assert len(drag) >= 1
    # "ლუდი ქართული" has 15% share × 6% margin — well below portfolio GM=15%
    # − 3pp band = 12%, so it must surface.
    assert any("ლუდი" in d["category"] for d in drag)
    for d in drag:
        assert d["flag"] == FLAG_DRAG
        assert d["portfolio_share_pct"] >= 1.0  # min drag share


# ---------------------------------------------------------------------------
# 5. LIFT identification
# ---------------------------------------------------------------------------


def test_lift_category_identified_and_flagged() -> None:
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    lift = result["lift_categories"]
    assert len(lift) >= 1
    # Both ნაყინი (30%) and გაზიანი (35.7%) exceed portfolio_gm (15%) + 3pp = 18%.
    names = [entry["category"] for entry in lift]
    assert any("ნაყინი" in n for n in names) or any("გაზიანი" in n for n in names)
    for entry in lift:
        assert entry["flag"] == FLAG_LIFT
        assert entry["portfolio_share_pct"] >= 0.5  # min lift share
    # Highest-margin lift should be first (sort order).
    assert lift[0]["gross_margin_pct"] == max(
        e["gross_margin_pct"] for e in lift
    )


# ---------------------------------------------------------------------------
# 6. Target gap computation
# ---------------------------------------------------------------------------


def test_target_gap_pp_and_profit_lift_match_hand_compute() -> None:
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    # Default target = 20%; portfolio GM = 15.00%; gap = 5.00pp.
    target = result["target"]
    assert target["gross_margin_pct"] == pytest.approx(
        float(USER_TARGET_GROSS_MARGIN_PCT), abs=0.001
    )
    assert target["gap_pp"] == pytest.approx(5.0, abs=0.01)
    # gap_profit_ge = gap_pp/100 × portfolio_revenue = 0.05 × 1,000,000 = 50,000.
    assert target["gap_profit_ge"] == pytest.approx(50_000.0, abs=0.01)

    # Override: target=14% should yield negative gap (portfolio already ahead).
    result_below = analyze_category_mix(
        loader, today=TODAY, target_gross_margin_pct=14.0
    )
    assert result_below["target"]["gap_pp"] < 0
    assert result_below["target"]["gap_profit_ge"] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# 7. summary_ka cites live portfolio GM
# ---------------------------------------------------------------------------


def test_summary_ka_cites_live_portfolio_gm_and_target() -> None:
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    summary = result["summary_ka"]
    # Portfolio GM 15.00% appears verbatim.
    assert "15.00%" in summary
    # Target 20.00% appears verbatim.
    assert "20.00%" in summary
    # Must not fall back to memory's obsolete "~10%" or "~6%" approximations.
    assert "~10%" not in summary
    assert "~6%" not in summary
    # Must cite the protected category explicitly (🔒 marker).
    assert "🔒" in summary
    assert "სიგარეტი" in summary


# ---------------------------------------------------------------------------
# 8. Per-store mode uses object_breakdown
# ---------------------------------------------------------------------------


def test_per_store_mode_uses_object_breakdown() -> None:
    """Per-store ('ოზურგეთი') pulls from object_breakdown and yields a
    different portfolio than 'total' — fixture uses 60/40 split."""
    cats = _mixed_fixture()
    loader = _make_loader(cats)

    total = analyze_category_mix(loader, today=TODAY, store="total")
    ozu = analyze_category_mix(loader, today=TODAY, store="ოზურგეთი")

    assert "error" not in ozu
    # Ozurgeti share = 60% → revenue = 600,000 (not 1,000,000).
    assert ozu["portfolio"]["revenue_ge"] == pytest.approx(600_000.0, abs=1.0)
    assert ozu["portfolio"]["revenue_ge"] < total["portfolio"]["revenue_ge"]
    # GM should remain ~15% because ozurgeti_share is uniform across categories.
    assert ozu["portfolio"]["gross_margin_pct"] == pytest.approx(15.0, abs=0.1)


# ---------------------------------------------------------------------------
# 9. Realism cap on recommended shifts
# ---------------------------------------------------------------------------


def test_no_shift_exceeds_max_shift_pct_of_source() -> None:
    """Every recommended_shift.revenue_shift_ge must be ≤ 20% of the source
    category's revenue — retail realism cap."""
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY)

    source_revenue = {
        d["category"]: d["revenue_ge"] for d in result["drag_categories"]
    }
    for shift in result["recommended_shifts"]:
        cap_ge = (
            MIX_ANALYZER_MAX_SHIFT_PCT
            / 100.0
            * source_revenue[shift["from_category"]]
        )
        # Allow 0.01 slack for rounding; assert strictly ≤ cap + slack.
        assert shift["revenue_shift_ge"] <= cap_ge + 0.01


# ---------------------------------------------------------------------------
# 10. Error paths — empty + missing sections + bad store
# ---------------------------------------------------------------------------


def test_empty_categories_returns_error_with_hint() -> None:
    loader = _make_loader([])
    result = analyze_category_mix(loader, today=TODAY)

    assert "error" in result
    assert "hint" in result
    assert "retail_sales.by_category" in result["error"]


def test_missing_retail_sales_section_returns_error() -> None:
    loader = lambda: {"other_section": {}}
    result = analyze_category_mix(loader, today=TODAY)

    assert "error" in result
    assert "retail_sales" in result["error"]


def test_bad_store_returns_error() -> None:
    cats = _mixed_fixture()
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY, store="batumi")

    assert "error" in result
    assert "batumi" in result["error"]


# ---------------------------------------------------------------------------
# 11. Argument coercion edge cases (compact — part of safety surface)
# ---------------------------------------------------------------------------


def test_top_n_clamped_to_bounds() -> None:
    assert _resolve_top_n(0) == MIN_TOP_N
    assert _resolve_top_n(1_000) == MAX_TOP_N
    assert _resolve_top_n("garbage") == DEFAULT_TOP_N
    assert _resolve_top_n(None) == DEFAULT_TOP_N


def test_target_gm_fallback_on_invalid_input() -> None:
    assert _resolve_target_gm(None) == float(USER_TARGET_GROSS_MARGIN_PCT)
    assert _resolve_target_gm(-5) == float(USER_TARGET_GROSS_MARGIN_PCT)
    assert _resolve_target_gm(150) == float(USER_TARGET_GROSS_MARGIN_PCT)
    assert _resolve_target_gm("x") == float(USER_TARGET_GROSS_MARGIN_PCT)
    assert _resolve_target_gm(18.0) == 18.0


def test_protected_override_semantics() -> None:
    # None → use defaults (caller expected behavior).
    assert _resolve_protected_override(None) is None
    # Empty list = explicit "no protection".
    assert _resolve_protected_override([]) == ()
    # Valid list → cleaned tuple.
    assert _resolve_protected_override(["სიგარეტ", "ალკოჰოლ"]) == (
        "სიგარეტ",
        "ალკოჰოლ",
    )
    # Non-string garbage → fall back to None (use defaults).
    assert _resolve_protected_override([42, None]) is None


def test_store_aliases_resolve() -> None:
    store, err = _resolve_store("total")
    assert err is None
    assert store == "total"
    store, err = _resolve_store("ოზურგეთი")
    assert err is None
    assert store == "ოზურგეთი"


def test_protected_override_empty_disables_protection() -> None:
    """Passing protected_override=[] runs unconstrained — cigarettes enter
    the normal drag pool and may be recommended for reduction."""
    cats = [
        _cat("0804 | სიგარეტი", 600_000, 30_000),  # 60% share, 5% gm
        _cat("ნაყინი ჭიქა", 400_000, 120_000),     # 40% share, 30% gm
    ]
    loader = _make_loader(cats)
    result = analyze_category_mix(loader, today=TODAY, protected_override=[])

    assert "error" not in result
    # No protected entries.
    assert result["protected_categories"] == []
    # Cigarettes become drag and may surface as from_category.
    drag_names = {d["category"] for d in result["drag_categories"]}
    assert any("სიგარეტი" in n for n in drag_names)


# ---------------------------------------------------------------------------
# 12. Tool registry + dispatcher
# ---------------------------------------------------------------------------


def test_mix_analyzer_tool_registered_in_schemas() -> None:
    from dashboard_pipeline.ai.tools import MIX_ANALYZER_TOOL, TOOL_SCHEMAS

    assert MIX_ANALYZER_TOOL in TOOL_SCHEMAS
    assert MIX_ANALYZER_TOOL["name"] == "mix_analyzer"
    # Schema must declare all 4 optional input params (documented contract).
    props = MIX_ANALYZER_TOOL["input_schema"]["properties"]
    assert set(props.keys()) == {
        "store",
        "top_n",
        "target_gross_margin_pct",
        "protected_override",
    }
    # Tool count sanity: 27 entries after Phase 2.3 lands.
    assert len(TOOL_SCHEMAS) == 27


def test_dispatcher_routes_mix_analyzer_to_analyze_category_mix() -> None:
    from dashboard_pipeline.ai.tools import ToolDispatcher

    cats = _mixed_fixture()
    loader = _make_loader(cats)
    dispatcher = ToolDispatcher(data_loader=loader)

    response = dispatcher.dispatch("mix_analyzer", {"top_n": 3})
    # dispatcher returns a {"tool_use_id":..., "content": <json>} envelope OR
    # the raw result dict — either way the payload must contain the contract.
    payload = response if isinstance(response, dict) and "portfolio" in response else response
    # Locate the actual result dict whichever shape dispatch returns.
    if isinstance(payload, dict) and "content" in payload:
        import json as _json
        payload = _json.loads(payload["content"])
    assert "portfolio" in payload
    assert "recommended_shifts" in payload
    assert payload["source"] == SOURCE_LABEL


# ---------------------------------------------------------------------------
# 13. Canonicalize / compute portfolio helpers directly
# ---------------------------------------------------------------------------


def test_canonicalize_protected_returns_remainder_untouched() -> None:
    entries = [
        {"category": "სიგარეტი", "raw_label": "სიგარეტი", "revenue_ge": 100.0,
         "cost_ge": 90.0, "profit_ge": 10.0, "gross_margin_pct": 10.0},
        {"category": "ნაყინი", "raw_label": "ნაყინი", "revenue_ge": 200.0,
         "cost_ge": 140.0, "profit_ge": 60.0, "gross_margin_pct": 30.0},
    ]
    protected, remainder = _canonicalize_protected(entries, ("სიგარეტ",))
    assert len(protected) == 1
    assert len(remainder) == 1
    assert remainder[0]["category"] == "ნაყინი"


def test_compute_portfolio_zero_revenue_returns_zero_gm() -> None:
    portfolio = _compute_portfolio([])
    assert portfolio["revenue_ge"] == 0.0
    assert portfolio["profit_ge"] == 0.0
    assert portfolio["gross_margin_pct"] == 0.0
