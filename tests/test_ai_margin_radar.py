"""Phase 3.8 — Margin Compression Radar tests.

Covers:
* Window selection: default 6, override 3, clamp out-of-range.
* Compression score formula: |min(Δpp, 0)| × revenue_recent (avg of last 2).
* Sorting: compressing desc by score, expanding desc by Δpp.
* Suspicious-margin filter (-5%..+90%) excludes & counts.
* Thin-data filter (<3 months in window OR rev<1000) excludes & counts.
* Expansion threshold (Δpp > +1pp).
* Protected canonicalization: 3 cigarette variants merge per period.
* Protected isolation: cigarettes never appear in compressing_categories[].
* Protected override [] disables protection.
* Error paths: empty by_category_by_month, missing retail_sales.
* summary_ka cites live numbers.
* Tool registry: MARGIN_RADAR_TOOL present + dispatcher routes.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.margin_radar import (
    DEFAULT_TOP_N,
    FLAG_COMPRESSING,
    FLAG_EXPANDING,
    FLAG_PROTECTED,
    MAX_TOP_N,
    MIN_TOP_N,
    SOURCE_LABEL,
    SUSPICIOUS_MARGIN_PCT_HIGH,
    SUSPICIOUS_MARGIN_PCT_LOW,
    _resolve_top_n,
    _resolve_window_months,
    analyze_margin_compression,
)
from dashboard_pipeline.ai.tools import TOOL_SCHEMAS, ToolDispatcher
from dashboard_pipeline.constants import (
    MARGIN_RADAR_DEFAULT_WINDOW_MONTHS,
    MARGIN_RADAR_EXPANSION_THRESHOLD_PP,
    MARGIN_RADAR_MAX_WINDOW_MONTHS,
    MARGIN_RADAR_MIN_MONTHS_IN_WINDOW,
    MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE,
    MARGIN_RADAR_MIN_WINDOW_MONTHS,
    PROTECTED_CATEGORY_SUBSTRINGS,
)


TODAY = date(2026, 4, 25)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _row(
    *,
    month: str,
    category: str,
    revenue: float,
    profit: float,
    normalized: str | None = None,
) -> Dict[str, Any]:
    cost = revenue - profit
    gm = (profit / revenue * 100.0) if revenue else 0.0
    return {
        "month": month,
        "category": category,
        "normalized_category": normalized if normalized is not None else category,
        "revenue_ge": round(revenue, 2),
        "cost_ge": round(cost, 2),
        "profit_ge": round(profit, 2),
        "gross_margin_pct": round(gm, 4),
        "total_quantity": 1.0,
        "row_count": 1,
    }


def _make_loader(rows: List[Dict[str, Any]]) -> Any:
    payload = {"retail_sales": {"by_category_by_month": rows}}

    def _loader() -> Dict[str, Any]:
        return payload

    return _loader


def _build_series(
    category: str,
    *,
    months: List[str],
    revenue_per_month: float = 10_000.0,
    gm_first: float,
    gm_last: float,
    normalized: str | None = None,
) -> List[Dict[str, Any]]:
    """Linearly interpolate gm_first → gm_last across months."""
    n = len(months)
    rows: List[Dict[str, Any]] = []
    for i, mo in enumerate(months):
        if n <= 1:
            gm = gm_first
        else:
            gm = gm_first + (gm_last - gm_first) * (i / (n - 1))
        profit = revenue_per_month * (gm / 100.0)
        rows.append(
            _row(
                month=mo,
                category=category,
                revenue=revenue_per_month,
                profit=profit,
                normalized=normalized,
            )
        )
    return rows


SIX_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]


def _mixed_fixture() -> List[Dict[str, Any]]:
    """Mix of compressing, expanding, protected, suspicious, and thin-data."""
    rows: List[Dict[str, Any]] = []

    # Compressing — big revenue, big drop. Score = 5.0 × 100,000 = 500,000.
    rows += _build_series(
        "კატეგორია A", months=SIX_MONTHS,
        revenue_per_month=100_000, gm_first=20.0, gm_last=15.0,
    )
    # Compressing — small revenue, big drop. Score = 10.0 × 5,000 = 50,000.
    rows += _build_series(
        "კატეგორია B", months=SIX_MONTHS,
        revenue_per_month=5_000, gm_first=25.0, gm_last=15.0,
    )
    # Expanding — big revenue, big lift.
    rows += _build_series(
        "კატეგორია C", months=SIX_MONTHS,
        revenue_per_month=80_000, gm_first=12.0, gm_last=22.0,
    )
    # Stable inside threshold band — should be evaluated but in NEITHER list.
    rows += _build_series(
        "კატეგორია D", months=SIX_MONTHS,
        revenue_per_month=20_000, gm_first=14.0, gm_last=14.5,  # +0.5pp < 1pp
    )
    # Protected: 3 cigarette variants — all compressing in the window.
    rows += _build_series(
        "0804 | სიგარეტი", months=SIX_MONTHS,
        revenue_per_month=30_000, gm_first=11.0, gm_last=8.0,
    )
    rows += _build_series(
        "სიგარეტი", months=SIX_MONTHS,
        revenue_per_month=20_000, gm_first=12.0, gm_last=9.0,
    )
    rows += _build_series(
        "ელ. სიგარეტი", months=SIX_MONTHS,
        revenue_per_month=1_000, gm_first=15.0, gm_last=10.0,
    )
    return rows


# ---------------------------------------------------------------------------
# 1. Argument coercion
# ---------------------------------------------------------------------------


class TestArgumentCoercion:
    def test_window_default_when_arg_none(self):
        assert _resolve_window_months(None) == MARGIN_RADAR_DEFAULT_WINDOW_MONTHS

    def test_window_clamped_below_min(self):
        assert _resolve_window_months(1) == MARGIN_RADAR_MIN_WINDOW_MONTHS

    def test_window_clamped_above_max(self):
        assert _resolve_window_months(99) == MARGIN_RADAR_MAX_WINDOW_MONTHS

    def test_window_garbage_falls_back_to_default(self):
        assert _resolve_window_months("xyz") == MARGIN_RADAR_DEFAULT_WINDOW_MONTHS

    def test_top_n_default_when_arg_none(self):
        assert _resolve_top_n(None) == DEFAULT_TOP_N

    def test_top_n_clamped_below_min(self):
        assert _resolve_top_n(1) == MIN_TOP_N

    def test_top_n_clamped_above_max(self):
        assert _resolve_top_n(99) == MAX_TOP_N


# ---------------------------------------------------------------------------
# 2. Compression score formula
# ---------------------------------------------------------------------------


class TestCompressionScore:
    def test_score_formula_matches_handcomputed(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        assert "error" not in result

        a = next(c for c in result["compressing_categories"] if c["category"] == "კატეგორია A")
        # gm_first 20.0, gm_last 15.0 → Δ −5.0pp.
        assert a["gm_first_pct"] == pytest.approx(20.0, abs=0.01)
        assert a["gm_last_pct"] == pytest.approx(15.0, abs=0.01)
        assert a["delta_pp"] == pytest.approx(-5.0, abs=0.01)
        # revenue_recent = avg(2026-01, 2026-02) = 100,000 (constant).
        assert a["revenue_recent_ge"] == pytest.approx(100_000.0, abs=0.01)
        # score = 5.0 × 100,000 = 500,000.
        assert a["compression_score"] == pytest.approx(500_000.0, abs=1.0)
        assert a["months_in_window"] == 6
        assert a["flag"] == FLAG_COMPRESSING

    def test_compressing_sorted_by_score_desc(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        scores = [c["compression_score"] for c in result["compressing_categories"]]
        assert scores == sorted(scores, reverse=True), (
            "compressing_categories must be sorted by compression_score desc"
        )


# ---------------------------------------------------------------------------
# 3. Window selection
# ---------------------------------------------------------------------------


class TestWindowSelection:
    def test_window_default_is_6(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        assert result["window"]["months"] == 6
        assert result["window"]["start_period"] == "2025-09"
        assert result["window"]["end_period"] == "2026-02"

    def test_window_override_to_3(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, window_months=3, today=TODAY)
        assert result["window"]["months"] == 3
        assert result["window"]["start_period"] == "2025-12"
        assert result["window"]["end_period"] == "2026-02"


# ---------------------------------------------------------------------------
# 4. Expansion threshold
# ---------------------------------------------------------------------------


class TestExpansionThreshold:
    def test_only_above_threshold_listed_as_expanding(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        # კატეგორია C jumps +10pp → expanding.
        assert any(
            c["category"] == "კატეგორია C" for c in result["expanding_categories"]
        )
        # კატეგორია D moves +0.5pp (below MARGIN_RADAR_EXPANSION_THRESHOLD_PP) → NOT expanding.
        d_in_expanding = any(
            c["category"] == "კატეგორია D" for c in result["expanding_categories"]
        )
        assert not d_in_expanding, (
            "Δpp below expansion threshold (1.0) must not be flagged as expanding"
        )

    def test_expanding_sorted_by_delta_desc(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        deltas = [c["delta_pp"] for c in result["expanding_categories"]]
        assert deltas == sorted(deltas, reverse=True)


# ---------------------------------------------------------------------------
# 5. Suspicious filter
# ---------------------------------------------------------------------------


class TestSuspiciousFilter:
    def test_negative_margin_excludes_category(self):
        rows = _mixed_fixture()
        # Inject one bad row for კატეგორია A so the entire series is dropped.
        bad = _row(
            month="2026-01", category="კატეგორია A",
            revenue=10_000, profit=-1_000,  # gm = -10% < -5% → suspicious
        )
        # Replace the existing 2026-01 row for კატეგორია A (last-occurrence wins
        # by row order in _aggregate_window).
        rows = [r for r in rows if not (r["month"] == "2026-01" and r["category"] == "კატეგორია A")]
        rows.append(bad)
        loader = _make_loader(rows)
        result = analyze_margin_compression(loader, today=TODAY)
        # კატეგორია A must NOT appear in compressing or expanding.
        names_compressing = {c["category"] for c in result["compressing_categories"]}
        names_expanding = {c["category"] for c in result["expanding_categories"]}
        assert "კატეგორია A" not in names_compressing
        assert "კატეგორია A" not in names_expanding
        assert result["categories_skipped_suspicious"] >= 1

    def test_extremely_high_margin_excludes_category(self):
        rows = _build_series(
            "Bizarre", months=SIX_MONTHS,
            revenue_per_month=10_000, gm_first=95.0, gm_last=99.0,  # > 90% → suspicious
        )
        loader = _make_loader(rows)
        result = analyze_margin_compression(loader, today=TODAY)
        assert result["categories_evaluated"] == 0
        assert result["categories_skipped_suspicious"] == 1
        # Bands themselves remain stable constants.
        assert SUSPICIOUS_MARGIN_PCT_LOW == -5.0
        assert SUSPICIOUS_MARGIN_PCT_HIGH == 90.0


# ---------------------------------------------------------------------------
# 6. Thin-data filter
# ---------------------------------------------------------------------------


class TestThinDataFilter:
    def test_fewer_than_min_months_excluded(self):
        # Only 2 months — below MARGIN_RADAR_MIN_MONTHS_IN_WINDOW (3).
        rows = _build_series(
            "Spotty", months=["2026-01", "2026-02"],
            revenue_per_month=10_000, gm_first=15.0, gm_last=10.0,
        )
        # Pad with 4 unrelated full-coverage rows so the all_periods threshold passes.
        rows += _build_series(
            "Filler", months=SIX_MONTHS,
            revenue_per_month=10_000, gm_first=15.0, gm_last=14.0,
        )
        loader = _make_loader(rows)
        result = analyze_margin_compression(loader, today=TODAY)
        names = {c["category"] for c in result["compressing_categories"]}
        assert "Spotty" not in names
        assert result["categories_skipped_thin_data"] >= 1

    def test_low_recent_revenue_excluded(self):
        rows = _build_series(
            "Tiny", months=SIX_MONTHS,
            revenue_per_month=500.0,  # < 1000 → fails noise floor
            gm_first=20.0, gm_last=10.0,
        )
        rows += _build_series(
            "Filler", months=SIX_MONTHS,
            revenue_per_month=10_000, gm_first=15.0, gm_last=14.0,
        )
        loader = _make_loader(rows)
        result = analyze_margin_compression(loader, today=TODAY)
        names = {c["category"] for c in result["compressing_categories"]}
        assert "Tiny" not in names
        assert result["categories_skipped_thin_data"] >= 1
        assert MARGIN_RADAR_MIN_REVENUE_FOR_TRACKING_GE == 1000.0


# ---------------------------------------------------------------------------
# 7. Protected canonicalization
# ---------------------------------------------------------------------------


class TestProtectedCanonicalization:
    def test_three_cigarette_variants_merge_into_one_protected_entry(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        protected = result["protected_info"]
        # All 3 cigarette labels merge into 1 protected entry per substring.
        assert len(protected) == 1
        entry = protected[0]
        assert entry["flag"] == FLAG_PROTECTED
        assert set(entry["raw_labels"]) == {
            "0804 | სიგარეტი",
            "სიგარეტი",
            "ელ. სიგარეტი",
        }
        # Canonical = shortest matching raw label.
        assert entry["canonical_label"] == "სიგარეტი"
        # Each variant compresses, so merged delta_pp must be negative.
        assert entry["delta_pp"] < 0

    def test_protected_entries_never_appear_in_compressing_list(self):
        """Safety invariant — even with a forced-bad fixture, no protected
        substring leaks into compressing_categories."""
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        for sub in PROTECTED_CATEGORY_SUBSTRINGS:
            for entry in result["compressing_categories"]:
                assert sub not in entry["category"], (
                    f"Protected substring '{sub}' leaked into "
                    f"compressing_categories entry '{entry['category']}'"
                )

    def test_protected_override_empty_runs_unconstrained(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(
            loader, protected_override=[], today=TODAY
        )
        # protected_info must be empty when override = []
        assert result["protected_info"] == []
        # And cigarettes can now show up in compressing_categories.
        names = {c["category"] for c in result["compressing_categories"]}
        cigarette_present = any("სიგარეტ" in n for n in names)
        assert cigarette_present, (
            "With protected_override=[], cigarette variants must be "
            "evaluated as normal compressing categories"
        )


# ---------------------------------------------------------------------------
# 8. summary_ka & contract
# ---------------------------------------------------------------------------


class TestSummaryAndContract:
    def test_summary_ka_cites_window_and_top_compressing(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        summary = result["summary_ka"]
        assert "Margin Compression Radar" in summary
        assert "2025-09" in summary  # start_period
        assert "2026-02" in summary  # end_period
        # Top compressor (კატეგორია A) named in summary.
        assert "კატეგორია A" in summary
        # Protected entry's canonical label surfaces.
        assert "სიგარეტი" in summary
        assert "protected" in summary.lower()

    def test_source_label_pinned(self):
        loader = _make_loader(_mixed_fixture())
        result = analyze_margin_compression(loader, today=TODAY)
        assert result["source"] == SOURCE_LABEL
        assert (
            result["source"] == "data.json:retail_sales.by_category_by_month"
        ), "source label is part of the public contract — do not rename"


# ---------------------------------------------------------------------------
# 9. Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_empty_by_category_by_month_returns_error(self):
        loader = _make_loader([])
        result = analyze_margin_compression(loader, today=TODAY)
        assert "error" in result
        assert "ცარიელია" in result["error"] or "by_category_by_month" in result["error"]

    def test_missing_retail_sales_returns_error(self):
        def loader():
            return {"meta": {"ok": True}}
        result = analyze_margin_compression(loader, today=TODAY)
        assert "error" in result

    def test_too_few_months_overall_returns_error(self):
        # Only 2 distinct months total — below MIN_MONTHS_IN_WINDOW (3).
        rows = _build_series(
            "X", months=["2026-01", "2026-02"],
            revenue_per_month=10_000, gm_first=15.0, gm_last=10.0,
        )
        loader = _make_loader(rows)
        result = analyze_margin_compression(loader, today=TODAY)
        assert "error" in result
        assert str(MARGIN_RADAR_MIN_MONTHS_IN_WINDOW) in result["error"]


# ---------------------------------------------------------------------------
# 10. Tool registry & dispatcher
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_margin_radar_present_in_tool_schemas(self):
        names = [t.get("name") for t in TOOL_SCHEMAS]
        assert "margin_radar" in names

    def test_margin_radar_tool_has_required_anti_triggers(self):
        tool = next(t for t in TOOL_SCHEMAS if t["name"] == "margin_radar")
        desc = tool["description"]
        # Must point users away from snapshot-mix and single-period tools.
        assert "mix_analyzer" in desc
        assert "detect_trends" in desc
        # Must enforce the protected-cigarettes invariant in the description.
        assert "PROTECTED" in desc or "protected" in desc

    def test_margin_radar_input_schema_exposes_window_months_arg(self):
        tool = next(t for t in TOOL_SCHEMAS if t["name"] == "margin_radar")
        props = tool["input_schema"]["properties"]
        assert "window_months" in props
        assert props["window_months"]["minimum"] == MARGIN_RADAR_MIN_WINDOW_MONTHS
        assert props["window_months"]["maximum"] == MARGIN_RADAR_MAX_WINDOW_MONTHS

    def test_dispatcher_routes_margin_radar(self):
        loader = _make_loader(_mixed_fixture())
        disp = ToolDispatcher(loader)
        result = disp.dispatch("margin_radar", {"window_months": 6, "top_n": 5})
        assert "error" not in result
        assert "compressing_categories" in result
        assert "expanding_categories" in result
        assert "protected_info" in result


# ---------------------------------------------------------------------------
# Sanity — constants visible (defends against accidental renames)
# ---------------------------------------------------------------------------


def test_expansion_threshold_constant_pinned():
    assert MARGIN_RADAR_EXPANSION_THRESHOLD_PP == 1.0


def test_window_constants_consistent():
    assert MARGIN_RADAR_MIN_WINDOW_MONTHS <= MARGIN_RADAR_DEFAULT_WINDOW_MONTHS
    assert MARGIN_RADAR_DEFAULT_WINDOW_MONTHS <= MARGIN_RADAR_MAX_WINDOW_MONTHS
    assert MARGIN_RADAR_MIN_MONTHS_IN_WINDOW >= 3
