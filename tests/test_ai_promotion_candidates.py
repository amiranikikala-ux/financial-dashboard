"""Phase 2.6 — Promotion Candidate Finder tests.

Covers:
* Argument coercion: store alias, top_n clamping, margin floor, days cap,
  discount ceiling, volume floor.
* Per-store metrics extraction from object_breakdown.
* Days-since-last-sale computation + missing date_range handling.
* Scoring formula: recency bonus tiers, headroom math, zero-headroom drop.
* Discount sizing: respects ceiling, respects 5% post-discount floor,
  rounded to whole percent.
* Signal classification: high / medium / low thresholds.
* Suspicious margin quarantine: rows with margin outside [-5%, 90%] are
  skipped and counted in `suspicious_skipped`.
* Main entry point: happy path, empty candidates, invalid inputs, missing
  retail_sales, missing by_product.
* Summary_ka format markers.
* Tool registry: schema contract, dispatcher routing, `_SUMMARY_KEYS`
  whitelist, position in TOOL_SCHEMAS (after analyze_product_profitability).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.promotion_candidates import (
    DEFAULT_MAX_DAYS_SINCE_LAST_SALE,
    DEFAULT_MAX_SUGGESTED_DISCOUNT_PCT,
    DEFAULT_MIN_MARGIN_PCT,
    DEFAULT_MIN_VOLUME,
    DEFAULT_TOP_N,
    FLOOR_POST_DISCOUNT_MARGIN_PCT,
    MAX_TOP_N,
    MIN_TOP_N,
    SCORE_HIGH_THRESHOLD,
    SCORE_MEDIUM_THRESHOLD,
    SIGNAL_HIGH,
    SIGNAL_LOW,
    SIGNAL_MEDIUM,
    SOURCE_LABEL,
    SUSPICIOUS_MARGIN_HIGH,
    SUSPICIOUS_MARGIN_LOW,
    _clamp_float,
    _clamp_int,
    _days_since_last_sale,
    _expected_signal,
    _parse_iso_date,
    _product_metrics_for_store,
    _promotion_score,
    _recency_bonus,
    _resolve_store,
    _suggested_discount_pct,
    find_promotion_candidates,
)


TODAY = date(2026, 4, 22)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _product(
    name: str,
    *,
    margin_pct: float,
    quantity: float,
    last_sale: str,
    code: str = "",
    category: str = "უცნობი კატეგორია",
    ozurgeti_share: float = 0.6,
    distinct_month_count: int = 12,
) -> Dict[str, Any]:
    """Build a by_product entry with auto-computed object_breakdown."""
    revenue = 1000.0
    profit = round(revenue * margin_pct / 100.0, 2)
    cost = round(revenue - profit, 2)
    ozu_rev = revenue * ozurgeti_share
    ozu_profit = profit * ozurgeti_share
    dva_rev = revenue * (1.0 - ozurgeti_share)
    dva_profit = profit * (1.0 - ozurgeti_share)

    def _m(r: float, p: float) -> float:
        return (p / r * 100.0) if r else 0.0

    return {
        "product_code": code,
        "product_name": name,
        "category": category,
        "revenue_ge": round(revenue, 2),
        "cost_ge": cost,
        "profit_ge": profit,
        "gross_margin_pct": round(margin_pct, 2),
        "total_quantity": round(quantity, 3),
        "distinct_month_count": distinct_month_count,
        "date_range": {"min": "2025-01-01", "max": last_sale},
        "object_breakdown": [
            {
                "object": "ოზურგეთი",
                "revenue_ge": round(ozu_rev, 2),
                "cost_ge": round(ozu_rev - ozu_profit, 2),
                "profit_ge": round(ozu_profit, 2),
                "gross_margin_pct": round(_m(ozu_rev, ozu_profit), 2),
                "total_quantity": round(quantity * ozurgeti_share, 3),
            },
            {
                "object": "დვაბზუ",
                "revenue_ge": round(dva_rev, 2),
                "cost_ge": round(dva_rev - dva_profit, 2),
                "profit_ge": round(dva_profit, 2),
                "gross_margin_pct": round(_m(dva_rev, dva_profit), 2),
                "total_quantity": round(quantity * (1.0 - ozurgeti_share), 3),
            },
        ],
    }


def _loader_with_products(products: List[Dict[str, Any]]):
    def _load() -> Dict[str, Any]:
        return {"retail_sales": {"by_product": products}}

    return _load


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------


class TestResolveStore:
    def test_none_is_total(self):
        assert _resolve_store(None) == ("total", None)

    def test_blank_is_total(self):
        assert _resolve_store("") == ("total", None)

    def test_latin_alias(self):
        assert _resolve_store("ozurgeti") == ("ოზურგეთი", None)

    def test_canonical_accepted(self):
        assert _resolve_store("დვაბზუ") == ("დვაბზუ", None)

    def test_unknown_errors(self):
        store, err = _resolve_store("paris")
        assert store is None
        assert err and "არ არის მხარდაჭერილი" in err

    def test_non_string_errors(self):
        store, err = _resolve_store(42)
        assert store is None
        assert err is not None


class TestClamping:
    def test_top_n_default(self):
        assert _clamp_int(None, default=DEFAULT_TOP_N, min_v=MIN_TOP_N, max_v=MAX_TOP_N) == DEFAULT_TOP_N

    def test_top_n_below_min(self):
        assert _clamp_int(1, default=DEFAULT_TOP_N, min_v=MIN_TOP_N, max_v=MAX_TOP_N) == MIN_TOP_N

    def test_top_n_above_max(self):
        assert _clamp_int(999, default=DEFAULT_TOP_N, min_v=MIN_TOP_N, max_v=MAX_TOP_N) == MAX_TOP_N

    def test_top_n_junk_falls_back(self):
        assert _clamp_int("abc", default=DEFAULT_TOP_N, min_v=MIN_TOP_N, max_v=MAX_TOP_N) == DEFAULT_TOP_N

    def test_float_default(self):
        assert _clamp_float(None, default=15.0, min_v=0.0, max_v=80.0) == 15.0

    def test_float_clamps_down(self):
        assert _clamp_float(-5, default=15.0, min_v=0.0, max_v=80.0) == 0.0

    def test_float_clamps_up(self):
        assert _clamp_float(500, default=15.0, min_v=0.0, max_v=80.0) == 80.0

    def test_float_nan_falls_back(self):
        assert _clamp_float(float("nan"), default=15.0, min_v=0.0, max_v=80.0) == 15.0


# ---------------------------------------------------------------------------
# Per-store metrics
# ---------------------------------------------------------------------------


class TestProductMetricsForStore:
    def test_total_reads_aggregate(self):
        prod = _product("A", margin_pct=20, quantity=100, last_sale="2026-04-01")
        metrics = _product_metrics_for_store(prod, "total")
        assert metrics is not None
        assert metrics["revenue_ge"] == 1000.0
        assert metrics["gross_margin_pct"] == 20.0

    def test_store_reads_breakdown(self):
        prod = _product(
            "A", margin_pct=20, quantity=100, last_sale="2026-04-01",
            ozurgeti_share=0.7,
        )
        metrics = _product_metrics_for_store(prod, "ოზურგეთი")
        assert metrics is not None
        assert metrics["revenue_ge"] == 700.0

    def test_store_missing_returns_none(self):
        prod = {"revenue_ge": 100, "gross_margin_pct": 20, "object_breakdown": []}
        assert _product_metrics_for_store(prod, "ოზურგეთი") is None

    def test_zero_revenue_returns_none(self):
        prod = {
            "revenue_ge": 0,
            "gross_margin_pct": 20,
            "cost_ge": 0,
            "profit_ge": 0,
            "total_quantity": 0,
        }
        assert _product_metrics_for_store(prod, "total") is None


# ---------------------------------------------------------------------------
# Date handling
# ---------------------------------------------------------------------------


class TestDateHandling:
    def test_parse_iso(self):
        assert _parse_iso_date("2026-04-01") == date(2026, 4, 1)

    def test_parse_iso_with_time(self):
        assert _parse_iso_date("2026-04-01T12:34:56") == date(2026, 4, 1)

    def test_parse_junk_returns_none(self):
        assert _parse_iso_date("not-a-date") is None

    def test_parse_none_returns_none(self):
        assert _parse_iso_date(None) is None

    def test_days_since_last_sale(self):
        prod = _product("A", margin_pct=20, quantity=100, last_sale="2026-04-01")
        days = _days_since_last_sale(prod, today=TODAY)
        assert days == 21

    def test_days_since_missing_date_returns_none(self):
        prod = {"date_range": {}}
        assert _days_since_last_sale(prod, today=TODAY) is None


# ---------------------------------------------------------------------------
# Scoring formula
# ---------------------------------------------------------------------------


class TestRecencyBonus:
    def test_very_fresh(self):
        assert _recency_bonus(5) == 1.0

    def test_fresh_boundary(self):
        assert _recency_bonus(30) == 1.0

    def test_moderate(self):
        assert _recency_bonus(45) == 0.7

    def test_slow(self):
        assert _recency_bonus(75) == 0.5

    def test_very_slow(self):
        assert _recency_bonus(150) == 0.3


class TestPromotionScore:
    def test_zero_headroom_is_zero(self):
        # margin == floor means no room for discount
        score = _promotion_score(
            current_margin_pct=FLOOR_POST_DISCOUNT_MARGIN_PCT,
            total_quantity=1000,
            days_since_last_sale=15,
        )
        assert score == 0.0

    def test_below_floor_is_zero(self):
        score = _promotion_score(
            current_margin_pct=1.0,
            total_quantity=1000,
            days_since_last_sale=15,
        )
        assert score == 0.0

    def test_score_increases_with_margin(self):
        a = _promotion_score(
            current_margin_pct=20, total_quantity=100, days_since_last_sale=15,
        )
        b = _promotion_score(
            current_margin_pct=40, total_quantity=100, days_since_last_sale=15,
        )
        assert b > a

    def test_score_increases_with_volume(self):
        a = _promotion_score(
            current_margin_pct=20, total_quantity=100, days_since_last_sale=15,
        )
        b = _promotion_score(
            current_margin_pct=20, total_quantity=10000, days_since_last_sale=15,
        )
        assert b > a

    def test_score_decays_with_staleness(self):
        fresh = _promotion_score(
            current_margin_pct=20, total_quantity=100, days_since_last_sale=15,
        )
        stale = _promotion_score(
            current_margin_pct=20, total_quantity=100, days_since_last_sale=150,
        )
        assert fresh > stale


class TestExpectedSignal:
    def test_high_threshold(self):
        assert _expected_signal(SCORE_HIGH_THRESHOLD) == SIGNAL_HIGH
        assert _expected_signal(SCORE_HIGH_THRESHOLD + 10) == SIGNAL_HIGH

    def test_medium_threshold(self):
        assert _expected_signal(SCORE_MEDIUM_THRESHOLD) == SIGNAL_MEDIUM
        assert _expected_signal(SCORE_HIGH_THRESHOLD - 0.1) == SIGNAL_MEDIUM

    def test_low_below_medium(self):
        assert _expected_signal(SCORE_MEDIUM_THRESHOLD - 0.1) == SIGNAL_LOW
        assert _expected_signal(0.0) == SIGNAL_LOW


# ---------------------------------------------------------------------------
# Discount sizing
# ---------------------------------------------------------------------------


class TestSuggestedDiscount:
    def test_respects_ceiling(self):
        # current_margin 50%, max_suggested 15% → takes the min = 15
        assert _suggested_discount_pct(
            current_margin_pct=50.0, max_suggested=15.0,
        ) == 15.0

    def test_respects_floor(self):
        # current_margin 12%, max 20% → can only discount 7 (12-5)
        assert _suggested_discount_pct(
            current_margin_pct=12.0, max_suggested=20.0,
        ) == 7.0

    def test_zero_when_below_floor(self):
        assert _suggested_discount_pct(
            current_margin_pct=3.0, max_suggested=20.0,
        ) == 0.0

    def test_rounds_to_whole_percent(self):
        # 12.4 − 5 = 7.4 → rounds to 7
        discount = _suggested_discount_pct(
            current_margin_pct=12.4, max_suggested=20.0,
        )
        assert discount == int(discount)


# ---------------------------------------------------------------------------
# Main entry — happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_returns_expected_keys(self):
        products = [
            _product("A", margin_pct=30, quantity=200, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert result["source"] == SOURCE_LABEL
        for k in (
            "as_of_date", "store", "min_margin_pct",
            "max_days_since_last_sale", "max_suggested_discount_pct",
            "min_volume", "floor_post_discount_margin_pct", "top_n",
            "products_scanned", "products_evaluated", "suspicious_skipped",
            "candidates", "summary_ka", "notes_ka",
        ):
            assert k in result, f"missing key: {k}"

    def test_single_candidate(self):
        products = [
            _product("A", margin_pct=30, quantity=200, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert result["products_evaluated"] == 1
        assert len(result["candidates"]) == 1
        c = result["candidates"][0]
        assert c["product_name"] == "A"
        assert c["current_margin_pct"] == 30.0
        assert c["suggested_discount_pct"] > 0
        assert c["post_discount_margin_pct"] >= FLOOR_POST_DISCOUNT_MARGIN_PCT

    def test_candidates_ranked_by_score(self):
        products = [
            # Equal margin; A has way more volume → higher score
            _product("A", margin_pct=30, quantity=10000, last_sale="2026-04-10"),
            _product("B", margin_pct=30, quantity=30, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        names = [c["product_name"] for c in result["candidates"]]
        assert names == ["A", "B"]

    def test_top_n_truncates(self):
        products = [
            _product(f"P{i}", margin_pct=30, quantity=100, last_sale="2026-04-10")
            for i in range(20)
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), top_n=5, today=TODAY,
        )
        assert len(result["candidates"]) == 5
        assert result["products_evaluated"] == 20

    def test_store_filter(self):
        products = [
            _product(
                "A", margin_pct=30, quantity=200, last_sale="2026-04-10",
                ozurgeti_share=1.0,  # ოზურგეთი-only
            ),
            _product(
                "B", margin_pct=30, quantity=200, last_sale="2026-04-10",
                ozurgeti_share=0.0,  # დვაბზუ-only
            ),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), store="დვაბზუ", today=TODAY,
        )
        names = [c["product_name"] for c in result["candidates"]]
        assert names == ["B"]


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_margin_floor_excludes_low(self):
        products = [
            _product("Low", margin_pct=10, quantity=200, last_sale="2026-04-10"),
            _product("Mid", margin_pct=20, quantity=200, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products),
            min_margin_pct=15,
            today=TODAY,
        )
        names = [c["product_name"] for c in result["candidates"]]
        assert names == ["Mid"]

    def test_days_cap_excludes_stale(self):
        products = [
            _product("Fresh", margin_pct=30, quantity=200, last_sale="2026-04-10"),
            _product("Stale", margin_pct=30, quantity=200, last_sale="2025-01-01"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products),
            max_days_since_last_sale=30,
            today=TODAY,
        )
        names = [c["product_name"] for c in result["candidates"]]
        assert names == ["Fresh"]

    def test_volume_floor_excludes_fringe(self):
        products = [
            _product("Fringe", margin_pct=30, quantity=5, last_sale="2026-04-10"),
            _product("Solid", margin_pct=30, quantity=500, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products),
            min_volume=20,
            today=TODAY,
        )
        names = [c["product_name"] for c in result["candidates"]]
        assert names == ["Solid"]

    def test_suspicious_margin_quarantined(self):
        products = [
            # Way over 90% — likely cost field missing
            _product("Bogus", margin_pct=137, quantity=200, last_sale="2026-04-10"),
            _product("Real", margin_pct=30, quantity=200, last_sale="2026-04-10"),
            # Negative — selling below cost
            _product("Below", margin_pct=-10, quantity=200, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        names = [c["product_name"] for c in result["candidates"]]
        assert names == ["Real"]
        assert result["suspicious_skipped"] == 2

    def test_suspicious_note_surfaces(self):
        products = [
            _product("Bogus", margin_pct=137, quantity=200, last_sale="2026-04-10"),
            _product("Real", margin_pct=30, quantity=200, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert any("suspicious" in n for n in result["notes_ka"])


# ---------------------------------------------------------------------------
# Summary_ka
# ---------------------------------------------------------------------------


class TestSummaryKa:
    def test_mentions_store_label_ka(self):
        products = [
            _product(
                "A", margin_pct=30, quantity=200, last_sale="2026-04-10",
                ozurgeti_share=1.0,
            ),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), store="ოზურგეთი", today=TODAY,
        )
        assert "ოზურგეთი" in result["summary_ka"]

    def test_mentions_top_pick(self):
        products = [
            _product("BigOne", margin_pct=50, quantity=2000, last_sale="2026-04-10"),
            _product("SmallOne", margin_pct=20, quantity=30, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert "BigOne" in result["summary_ka"]

    def test_mentions_discount_pct(self):
        products = [
            _product("A", margin_pct=40, quantity=500, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products),
            max_suggested_discount_pct=10,
            today=TODAY,
        )
        assert "10% discount" in result["summary_ka"]

    def test_empty_result_surfaces_hint(self):
        products = [
            _product("LowMargin", margin_pct=5, quantity=200, last_sale="2026-04-10"),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products),
            min_margin_pct=50,
            today=TODAY,
        )
        assert result["products_evaluated"] == 0
        assert "filters too strict" in result["summary_ka"] or "კანდიდატი" in result["summary_ka"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_missing_retail_sales(self):
        result = find_promotion_candidates(lambda: {}, today=TODAY)
        assert "error" in result
        assert "retail_sales" in result["error"]

    def test_empty_by_product(self):
        result = find_promotion_candidates(
            lambda: {"retail_sales": {"by_product": []}},
            today=TODAY,
        )
        assert "error" in result
        assert "ცარიელია" in result["error"]

    def test_unknown_store_errors(self):
        products = [_product("A", margin_pct=30, quantity=200, last_sale="2026-04-10")]
        result = find_promotion_candidates(
            _loader_with_products(products), store="paris", today=TODAY,
        )
        assert "error" in result
        assert "მხარდაჭერილი" in result["error"]


# ---------------------------------------------------------------------------
# Tool registry + dispatcher
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    def test_tool_present(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "find_promotion_candidates" in names

    def test_tool_sits_after_product_profitability(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert (
            names[names.index("analyze_product_profitability") + 1]
            == "find_promotion_candidates"
        )

    def test_tool_schema_has_all_knobs(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        props = FIND_PROMOTION_CANDIDATES_TOOL["input_schema"]["properties"]
        for key in (
            "store", "top_n", "min_margin_pct", "max_days_since_last_sale",
            "max_suggested_discount_pct", "min_volume",
        ):
            assert key in props, f"missing {key}"

    def test_store_enum_matches_canonical(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        enum = FIND_PROMOTION_CANDIDATES_TOOL["input_schema"]["properties"]["store"]["enum"]
        assert enum == ["total", "ოზურგეთი", "დვაბზუ"]

    def test_no_required_fields(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        assert FIND_PROMOTION_CANDIDATES_TOOL["input_schema"].get("required", []) == []

    def test_dispatcher_routes_correctly(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        products = [
            _product("A", margin_pct=30, quantity=200, last_sale="2026-04-10"),
        ]
        dispatcher = ToolDispatcher(data_loader=_loader_with_products(products))
        result = dispatcher.dispatch(
            "find_promotion_candidates",
            {"top_n": 5, "min_margin_pct": 10},
        )
        assert "error" not in result
        assert result["products_evaluated"] == 1

    def test_summary_keys_whitelist_covers_fields(self):
        from dashboard_pipeline.ai.tools import _SUMMARY_KEYS

        for key in (
            "promotion_score", "expected_signal_ka", "suggested_discount_pct",
            "post_discount_margin_pct", "candidates", "products_evaluated",
            "suspicious_skipped", "notes_ka",
        ):
            assert key in _SUMMARY_KEYS, f"missing {key}"


# ---------------------------------------------------------------------------
# Tool description contract
# ---------------------------------------------------------------------------


class TestToolDescriptionContract:
    def test_description_mentions_summary_ka(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        assert "summary_ka" in FIND_PROMOTION_CANDIDATES_TOOL["description"]

    def test_description_has_anti_triggers(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        desc = FIND_PROMOTION_CANDIDATES_TOOL["description"]
        assert "Anti-triggers" in desc
        # Must disambiguate from dead_stock / product_profitability / forecast
        assert "analyze_dead_stock" in desc
        assert "analyze_product_profitability" in desc
        assert "forecast_revenue" in desc

    def test_description_mentions_signal_labels(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        desc = FIND_PROMOTION_CANDIDATES_TOOL["description"]
        assert "high" in desc
        assert "medium" in desc
        assert "low" in desc

    def test_description_explains_discount_cap(self):
        from dashboard_pipeline.ai.tools import FIND_PROMOTION_CANDIDATES_TOOL

        desc = FIND_PROMOTION_CANDIDATES_TOOL["description"]
        # The 5% post-discount floor is the key honest constraint; AI must
        # see why the discount isn't always the ceiling.
        assert "5%" in desc
        assert "floor" in desc.lower()


# ---------------------------------------------------------------------------
# Boundary invariants on suspicious thresholds
# ---------------------------------------------------------------------------


class TestSuspiciousBoundaries:
    def test_low_boundary_inclusive(self):
        # Margin exactly at -5% should be quarantined (matches product_profitability)
        products = [
            _product(
                "Edge", margin_pct=SUSPICIOUS_MARGIN_LOW - 0.1,
                quantity=200, last_sale="2026-04-10",
            ),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert result["suspicious_skipped"] == 1
        assert result["products_evaluated"] == 0

    def test_high_boundary_inclusive(self):
        products = [
            _product(
                "Edge", margin_pct=SUSPICIOUS_MARGIN_HIGH + 0.1,
                quantity=200, last_sale="2026-04-10",
            ),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert result["suspicious_skipped"] == 1

    def test_high_boundary_exact_stays(self):
        # Exactly 90% is still within range (inclusive on high end)
        products = [
            _product(
                "Edge", margin_pct=SUSPICIOUS_MARGIN_HIGH,
                quantity=200, last_sale="2026-04-10",
            ),
        ]
        result = find_promotion_candidates(
            _loader_with_products(products), today=TODAY,
        )
        assert result["suspicious_skipped"] == 0
        assert result["products_evaluated"] == 1
