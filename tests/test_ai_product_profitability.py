"""Phase 2.5 — Product Profitability X-Ray tests.

Covers:
* Argument coercion: store alias, top_n clamping, revenue threshold, category.
* Per-store metrics extraction from object_breakdown.
* Flag classification thresholds (HEALTHY / THIN / BLEEDING / SUSPICIOUS).
* Suspicious quarantine: negative + >90% margin excluded from worst/best.
* Revenue-weighted portfolio margin.
* summary_ka format markers.
* Error paths: missing retail_sales, empty by_product, over-restrictive filter.
* Tool registry: index 15 (between simulate_scenario and investigator block),
  dispatcher routing, schema contract.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.product_profitability import (
    DEFAULT_MIN_REVENUE_GE,
    DEFAULT_TOP_N,
    FLAG_BLEEDING,
    FLAG_HEALTHY,
    FLAG_SUSPICIOUS,
    FLAG_THIN,
    MAX_TOP_N,
    MIN_TOP_N,
    SOURCE_LABEL,
    SUSPICIOUS_MARGIN_HIGH,
    SUSPICIOUS_MARGIN_LOW,
    _flag_for_margin,
    _portfolio_margin_pct,
    _product_metrics_for_store,
    _resolve_category_filter,
    _resolve_min_revenue,
    _resolve_store,
    _resolve_top_n,
    analyze_product_profitability,
)


TODAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _product(
    name: str,
    revenue: float,
    profit: float,
    *,
    category: str = "უცნობი კატეგორია",
    code: str = "",
    quantity: float = 1.0,
    ozurgeti_share: float = 0.6,
) -> Dict[str, Any]:
    """Build a by_product entry with auto-computed object_breakdown."""
    cost = revenue - profit
    margin_pct = round((profit / revenue * 100.0) if revenue else 0.0, 2)
    ozu_rev = revenue * ozurgeti_share
    ozu_profit = profit * ozurgeti_share
    dva_rev = revenue * (1.0 - ozurgeti_share)
    dva_profit = profit * (1.0 - ozurgeti_share)

    def _m(r, p):
        return (p / r * 100.0) if r else 0.0

    return {
        "product_code": code,
        "product_name": name,
        "category": category,
        "revenue_ge": round(revenue, 2),
        "cost_ge": round(cost, 2),
        "profit_ge": round(profit, 2),
        "gross_margin_pct": margin_pct,
        "total_quantity": quantity,
        "object_breakdown": [
            {
                "object": "ოზურგეთი",
                "revenue_ge": round(ozu_rev, 2),
                "cost_ge": round(ozu_rev - ozu_profit, 2),
                "profit_ge": round(ozu_profit, 2),
                "gross_margin_pct": round(_m(ozu_rev, ozu_profit), 2),
                "total_quantity": quantity * ozurgeti_share,
            },
            {
                "object": "დვაბზუ",
                "revenue_ge": round(dva_rev, 2),
                "cost_ge": round(dva_rev - dva_profit, 2),
                "profit_ge": round(dva_profit, 2),
                "gross_margin_pct": round(_m(dva_rev, dva_profit), 2),
                "total_quantity": quantity * (1.0 - ozurgeti_share),
            },
        ],
    }


def _loader_with_products(products: List[Dict[str, Any]]):
    def _load():
        return {"retail_sales": {"by_product": products}}

    return _load


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------


class TestResolveStore:
    def test_none_is_total(self):
        assert _resolve_store(None) == ("total", None)

    def test_latin_alias(self):
        assert _resolve_store("ozurgeti") == ("ოზურგეთი", None)

    def test_unknown_errors(self):
        store, err = _resolve_store("paris")
        assert store is None
        assert err and "არ არის მხარდაჭერილი" in err


class TestResolveTopN:
    def test_default(self):
        assert _resolve_top_n(None) == DEFAULT_TOP_N

    def test_clamps_below_min(self):
        assert _resolve_top_n(1) == MIN_TOP_N

    def test_clamps_above_max(self):
        assert _resolve_top_n(9999) == MAX_TOP_N

    def test_junk_falls_back(self):
        assert _resolve_top_n("abc") == DEFAULT_TOP_N


class TestResolveMinRevenue:
    def test_default_when_none(self):
        assert _resolve_min_revenue(None) == DEFAULT_MIN_REVENUE_GE

    def test_negative_falls_back(self):
        assert _resolve_min_revenue(-100) == DEFAULT_MIN_REVENUE_GE

    def test_zero_is_accepted(self):
        assert _resolve_min_revenue(0) == 0.0

    def test_positive_passthrough(self):
        assert _resolve_min_revenue(1000) == 1000.0


class TestResolveCategoryFilter:
    def test_none_is_none(self):
        assert _resolve_category_filter(None) is None

    def test_blank_is_none(self):
        assert _resolve_category_filter("   ") is None

    def test_valid_string(self):
        assert _resolve_category_filter(" ფრენჩიზი ") == "ფრენჩიზი"


# ---------------------------------------------------------------------------
# Per-store metrics extraction
# ---------------------------------------------------------------------------


class TestProductMetricsForStore:
    def test_total_reads_top_level(self):
        p = _product("A", revenue=1000, profit=300)
        metrics = _product_metrics_for_store(p, "total")
        assert metrics is not None
        assert metrics["revenue_ge"] == 1000.0
        assert metrics["profit_ge"] == 300.0

    def test_store_reads_breakdown(self):
        p = _product("A", revenue=1000, profit=300, ozurgeti_share=0.6)
        metrics = _product_metrics_for_store(p, "ოზურგეთი")
        assert metrics is not None
        assert metrics["revenue_ge"] == 600.0

    def test_product_absent_in_store_returns_none(self):
        p = {
            "product_name": "A",
            "revenue_ge": 500,
            "object_breakdown": [
                {"object": "დვაბზუ", "revenue_ge": 500, "cost_ge": 400, "profit_ge": 100},
            ],
        }
        assert _product_metrics_for_store(p, "ოზურგეთი") is None

    def test_zero_revenue_returns_none(self):
        p = _product("A", revenue=0, profit=0)
        assert _product_metrics_for_store(p, "total") is None


# ---------------------------------------------------------------------------
# Flag classification
# ---------------------------------------------------------------------------


class TestFlagForMargin:
    def test_suspicious_negative(self):
        assert _flag_for_margin(-20.0) == FLAG_SUSPICIOUS

    def test_suspicious_above_90(self):
        assert _flag_for_margin(95.0) == FLAG_SUSPICIOUS

    def test_bleeding_below_5pct(self):
        assert _flag_for_margin(3.0) == FLAG_BLEEDING
        assert _flag_for_margin(0.0) == FLAG_BLEEDING

    def test_thin_5_to_15(self):
        assert _flag_for_margin(10.0) == FLAG_THIN

    def test_healthy_above_15(self):
        assert _flag_for_margin(25.0) == FLAG_HEALTHY
        assert _flag_for_margin(50.0) == FLAG_HEALTHY

    def test_boundary_suspicious_low(self):
        # Exactly -5 is still suspicious by contract (strictly less is error).
        assert _flag_for_margin(SUSPICIOUS_MARGIN_LOW) == FLAG_BLEEDING  # -5 is BLEEDING border
        assert _flag_for_margin(SUSPICIOUS_MARGIN_LOW - 0.01) == FLAG_SUSPICIOUS

    def test_boundary_suspicious_high(self):
        assert _flag_for_margin(SUSPICIOUS_MARGIN_HIGH) == FLAG_HEALTHY
        assert _flag_for_margin(SUSPICIOUS_MARGIN_HIGH + 0.01) == FLAG_SUSPICIOUS


# ---------------------------------------------------------------------------
# Portfolio margin
# ---------------------------------------------------------------------------


class TestPortfolioMarginPct:
    def test_revenue_weighted(self):
        qualified = [
            {"revenue_ge": 1000, "profit_ge": 200},  # 20% margin
            {"revenue_ge": 500, "profit_ge": 50},    # 10% margin
        ]
        # Weighted: (200+50) / (1000+500) = 250/1500 = 16.67%
        assert _portfolio_margin_pct(qualified) == pytest.approx(16.67)

    def test_empty_returns_zero(self):
        assert _portfolio_margin_pct([]) == 0.0


# ---------------------------------------------------------------------------
# Top-level tool: success paths
# ---------------------------------------------------------------------------


class TestAnalyzeSuccess:
    def test_basic_ranking(self):
        products = [
            _product("ძვირიანი", revenue=1000, profit=400, category="ფრენჩიზი"),  # 40%
            _product("საშუალო", revenue=1500, profit=150, category="ფრენჩიზი"),   # 10%
            _product("ცუდი", revenue=2000, profit=50, category="ფრენჩიზი"),       # 2.5%
        ]
        result = analyze_product_profitability(
            _loader_with_products(products),
            top_n=5,
            today=TODAY,
        )
        assert "error" not in result
        assert result["source"] == SOURCE_LABEL
        assert result["products_scanned"] == 3
        assert result["products_qualified"] == 3
        # Worst = lowest margin first.
        assert result["worst_performers"][0]["product_name"] == "ცუდი"
        assert result["worst_performers"][0]["flag"] == FLAG_BLEEDING
        # Best = highest margin first.
        assert result["best_performers"][0]["product_name"] == "ძვირიანი"
        assert result["best_performers"][0]["flag"] == FLAG_HEALTHY

    def test_revenue_threshold_excludes_small(self):
        products = [
            _product("Big", revenue=5000, profit=500, category="A"),    # 10%
            _product("Tiny", revenue=100, profit=1, category="A"),      # 1% — below threshold
        ]
        result = analyze_product_profitability(
            _loader_with_products(products),
            min_revenue_threshold_ge=500,
            today=TODAY,
        )
        assert result["products_scanned"] == 2
        assert result["products_qualified"] == 1
        names = [e["product_name"] for e in result["worst_performers"]]
        assert "Tiny" not in names

    def test_category_filter_applied(self):
        products = [
            _product("A1", 1000, 100, category="ფრენჩიზი"),
            _product("A2", 1500, 300, category="ფრენჩიზი"),
            _product("B1", 2000, 200, category="ალკოჰოლი"),
        ]
        result = analyze_product_profitability(
            _loader_with_products(products),
            category_filter="ფრენჩიზი",
            today=TODAY,
        )
        assert result["products_qualified"] == 2
        names = {e["product_name"] for e in result["worst_performers"]}
        assert names == {"A1", "A2"}

    def test_suspicious_quarantined(self):
        products = [
            _product("Normal", 1000, 200, category="A"),   # 20%, HEALTHY
            _product("Negative", 1000, -200, category="A"),  # -20%, SUSPICIOUS
            _product("TooHigh", 1000, 950, category="A"),   # 95%, SUSPICIOUS
        ]
        result = analyze_product_profitability(
            _loader_with_products(products),
            today=TODAY,
        )
        assert result["products_qualified"] == 1
        assert len(result["suspicious"]) == 2
        susp_names = {e["product_name"] for e in result["suspicious"]}
        assert susp_names == {"Negative", "TooHigh"}
        # Quarantined → NOT in worst/best.
        worst_names = {e["product_name"] for e in result["worst_performers"]}
        assert "Negative" not in worst_names
        assert "TooHigh" not in worst_names

    def test_store_filter_uses_breakdown(self):
        products = [
            _product("A", 1000, 200, category="C", ozurgeti_share=0.6),  # 20%
        ]
        result = analyze_product_profitability(
            _loader_with_products(products),
            store="ოზურგეთი",
            today=TODAY,
        )
        assert result["store"] == "ოზურგეთი"
        # Only ოზურგეთი share (600 ₾, 120 ₾ profit).
        e = result["worst_performers"][0]
        assert e["revenue_ge"] == 600.0
        assert e["profit_ge"] == 120.0

    def test_portfolio_margin_computed(self):
        products = [
            _product("A", 1000, 200, category="C"),  # 20%
            _product("B", 500, 50, category="C"),    # 10%
        ]
        result = analyze_product_profitability(
            _loader_with_products(products),
            today=TODAY,
        )
        # Revenue-weighted: (200+50) / (1000+500) = 16.67%.
        assert result["portfolio_margin_pct"] == pytest.approx(16.67)

    def test_summary_ka_has_4c2_format(self):
        products = [_product("A", 1000, 200, category="C")]
        result = analyze_product_profitability(
            _loader_with_products(products),
            today=TODAY,
        )
        summary = result["summary_ka"]
        assert "**" in summary
        assert "·" in summary
        assert "Product X-Ray" in summary
        assert "portfolio margin" in summary


# ---------------------------------------------------------------------------
# Top-level tool: error paths
# ---------------------------------------------------------------------------


class TestAnalyzeErrors:
    def test_missing_retail_sales(self):
        result = analyze_product_profitability(lambda: {}, today=TODAY)
        assert "error" in result
        assert "retail_sales" in result["error"]

    def test_empty_by_product(self):
        result = analyze_product_profitability(
            lambda: {"retail_sales": {"by_product": []}},
            today=TODAY,
        )
        assert "error" in result
        assert "ცარიელია" in result["error"]

    def test_over_restrictive_filter_errors(self):
        products = [_product("A", 1000, 200, category="X")]
        result = analyze_product_profitability(
            _loader_with_products(products),
            category_filter="nonexistent_category",
            today=TODAY,
        )
        assert "error" in result

    def test_unknown_store_errors(self):
        products = [_product("A", 1000, 200)]
        result = analyze_product_profitability(
            _loader_with_products(products),
            store="paris",
            today=TODAY,
        )
        assert "error" in result
        assert "მხარდაჭერილი" in result["error"]


# ---------------------------------------------------------------------------
# Tool registry + dispatcher integration
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    def test_tool_present(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "analyze_product_profitability" in names

    def test_tool_sits_after_simulate_scenario(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [t["name"] for t in TOOL_SCHEMAS]
        assert (
            names[names.index("simulate_scenario") + 1]
            == "analyze_product_profitability"
        )

    def test_tool_schema_has_all_knobs(self):
        from dashboard_pipeline.ai.tools import PRODUCT_PROFITABILITY_XRAY_TOOL

        props = PRODUCT_PROFITABILITY_XRAY_TOOL["input_schema"]["properties"]
        for key in (
            "store", "top_n", "category_filter", "min_revenue_threshold_ge",
        ):
            assert key in props, f"missing {key}"

    def test_tool_schema_has_no_required_fields(self):
        from dashboard_pipeline.ai.tools import PRODUCT_PROFITABILITY_XRAY_TOOL

        required = PRODUCT_PROFITABILITY_XRAY_TOOL["input_schema"].get(
            "required", []
        )
        assert required == []

    def test_dispatcher_routes_correctly(self):
        from dashboard_pipeline.ai.tools import ToolDispatcher

        products = [_product("A", 1000, 200, category="C")]
        dispatcher = ToolDispatcher(data_loader=_loader_with_products(products))
        result = dispatcher.dispatch(
            "analyze_product_profitability",
            {"top_n": 5},
        )
        assert "error" not in result
        assert result["products_qualified"] == 1


# ---------------------------------------------------------------------------
# Tool description contract
# ---------------------------------------------------------------------------


class TestToolDescriptionContract:
    def test_description_mentions_summary_ka(self):
        from dashboard_pipeline.ai.tools import PRODUCT_PROFITABILITY_XRAY_TOOL

        assert "summary_ka" in PRODUCT_PROFITABILITY_XRAY_TOOL["description"]

    def test_description_explains_flags(self):
        from dashboard_pipeline.ai.tools import PRODUCT_PROFITABILITY_XRAY_TOOL

        desc = PRODUCT_PROFITABILITY_XRAY_TOOL["description"]
        assert "HEALTHY" in desc
        assert "BLEEDING" in desc
        assert "SUSPICIOUS" in desc

    def test_description_has_anti_triggers(self):
        from dashboard_pipeline.ai.tools import PRODUCT_PROFITABILITY_XRAY_TOOL

        desc = PRODUCT_PROFITABILITY_XRAY_TOOL["description"]
        assert "Anti-triggers" in desc
        # Must disambiguate from supplier / dead_stock / scenario tools.
        assert "prepare_supplier_brief" in desc
        assert "analyze_dead_stock" in desc
        assert "simulate_scenario" in desc

    def test_description_warns_about_suspicious_data(self):
        from dashboard_pipeline.ai.tools import PRODUCT_PROFITABILITY_XRAY_TOOL

        # Honesty rule — AI must warn user before acting on SUSPICIOUS rows.
        desc = PRODUCT_PROFITABILITY_XRAY_TOOL["description"]
        assert "Excel" in desc or "verification" in desc.lower()
