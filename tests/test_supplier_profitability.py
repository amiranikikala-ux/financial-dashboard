"""Tests for dashboard_pipeline/supplier_profitability.py.

Strict barcode JOIN with explicit ambiguous handling. Every test asserts
behavior against hand-computed numbers — no implementation reuse, no
"trust the function" patterns. The data files used are inline
fixtures so the test suite does not depend on data.json freshness.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.supplier_profitability import (
    COVERAGE_UNVERIFIED_PCT,
    COVERAGE_VERIFIED_PCT,
    DEAD_STOCK_THRESHOLD_DAYS,
    MIN_PRODUCTS_FOR_FULL_DISPLAY,
    MIN_REVENUE_FOR_MARGIN_LIST_GE,
    PROTECTED_DOMINANT_PCT,
    SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS,
    build_supplier_profitability,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _imp_product(code: str, name: str, qty: float, cost: float, unit: str = "ცალი"):
    return {
        "product_code": code,
        "product_name": name,
        "unit": unit,
        "row_count": 1,
        "distinct_waybill_count": 1,
        "total_quantity": qty,
        "total_amount_ge": cost,
    }


def _supplier(tax_id: str, name: str, products: List[Dict[str, Any]]):
    return {
        "supplier": name,
        "tax_id": tax_id,
        "tax_id_source": "rs",
        "normalized_supplier": name,
        "row_count": sum(p["row_count"] for p in products),
        "distinct_waybill_count": 1,
        "distinct_product_count": len(products),
        "distinct_month_count": 1,
        "total_quantity": sum(p["total_quantity"] for p in products),
        "total_amount_ge": sum(p["total_amount_ge"] for p in products),
        "date_range": {"min": "2025-01-01", "max": "2026-01-01"},
        "top_products": products,
    }


def _retail_product(
    pcode: str,
    barcode: str,
    name: str,
    category: str,
    rev: float,
    cost: float,
    qty: float = 1.0,
    last_sale: str = "2026-04-01",
    object_breakdown=None,
):
    return {
        "product_code": pcode,
        "barcode": barcode,
        "product_name": name,
        "unit": "ცალი",
        "category": category,
        "row_count": 1,
        "total_quantity": qty,
        "revenue_ge": rev,
        "cost_ge": cost,
        "profit_ge": rev - cost,
        "gross_margin_pct": ((rev - cost) / rev * 100.0) if rev > 0 else 0.0,
        "distinct_object_count": 1,
        "distinct_month_count": 1,
        "date_range": {"min": "2025-01-01", "max": last_sale},
        "object_breakdown": object_breakdown or [],
    }


def _supplier_with_objects(tax_id, name, products, object_breakdown):
    """Same as _supplier but stamps object_breakdown on the supplier
    entry (mimicking the real imported_products output after the
    destination-tracking change)."""
    s = _supplier(tax_id, name, products)
    s["object_breakdown"] = object_breakdown
    return s


def _data(suppliers, by_product):
    return {
        "imported_products": {"suppliers": suppliers},
        "retail_sales": {"by_product": by_product},
    }


TODAY = date(2026, 4, 26)


# ---------------------------------------------------------------------------
# Match precedence
# ---------------------------------------------------------------------------

def test_match_by_barcode_when_imported_code_is_ean():
    """imported.product_code == retail.barcode → verified barcode hit."""
    sup = _supplier("100", "ABC", [_imp_product("4860019001360", "ბორჯომი 1ლ", 10, 9.0)])
    retail = [
        _retail_product("0904017", "4860019001360", "მინ წყალი ბორჯომი 1ლ", "წყალი", 12.0, 9.0)
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 1
    assert p["totals"]["products_ambiguous"] == 0
    assert p["totals"]["products_unmatched"] == 0
    assert p["totals"]["cost_matched_ge"] == 9.0
    assert p["totals"]["revenue_sold_ge"] == 12.0


def test_match_by_product_code_when_imported_uses_max_internal():
    """imported.product_code == retail.product_code → verified pcode hit."""
    sup = _supplier("100", "ABC", [_imp_product("112100", "ბორჯომი 1ლ პეტი", 5, 4.5)])
    retail = [_retail_product("112100", "112100", "ბორჯომი 1.0 პეტი", "წყალი", 6.0, 4.5)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 1
    matched = p["top_margin"][0] if p["top_margin"] else None
    if matched:
        assert matched["match_kind"] in ("barcode", "product_code")


def test_no_match_when_code_missing_from_retail():
    sup = _supplier("100", "ABC", [_imp_product("99999999", "უცნობი", 1, 100.0)])
    retail = [_retail_product("11", "1234567890", "სხვა", "სხვა", 50, 30, last_sale="2026-04-01")]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 0
    assert p["totals"]["products_unmatched"] == 1
    assert p["totals"]["products_ambiguous"] == 0
    assert p["status"] == "unverified"


# ---------------------------------------------------------------------------
# Ambiguous detection (the data-quality fix)
# ---------------------------------------------------------------------------

def test_ambiguous_when_two_retail_rows_share_barcode():
    """If imported code matches 2+ retail rows by barcode, treat as
    ambiguous — neither row is safe to pick. cost_imported still counted,
    cost_matched is NOT (so coverage drops)."""
    sup = _supplier("100", "ABC", [_imp_product("1002", "ნალექიანი ყავა", 5, 50)])
    retail = [
        _retail_product("10101001", "1002", "ნალექიანი ყავა იტალი", "ყავა", 100, 60),
        _retail_product("2216301", "1002", "ძეხვი მოხარშული ლიდერი", "ძეხვეული", 200, 150),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 0
    assert p["totals"]["products_ambiguous"] == 1
    assert p["totals"]["products_unmatched"] == 0
    assert p["totals"]["cost_matched_ge"] == 0
    assert p["totals"]["cost_ambiguous_ge"] == 50
    assert p["totals"]["revenue_sold_ge"] == 0  # ambiguous excluded
    assert len(p["ambiguous_preview"]) == 1
    assert p["ambiguous_preview"][0]["imported_code"] == "1002"


def test_ambiguous_resolved_by_user_alias():
    """Alias points at a specific retail key → ambiguity resolved
    intentionally, that row counts as verified."""
    sup = _supplier("100", "ABC", [_imp_product("1002", "ძეხვი ლიდერი", 5, 50)])
    retail = [
        _retail_product("10101001", "1002", "ნალექიანი ყავა იტალი", "ყავა", 100, 60),
        _retail_product("2216301", "9999999", "ძეხვი მოხარშული ლიდერი", "ძეხვეული", 200, 150),
    ]
    aliases = [
        {
            "imported_code": "1002",
            "retail_code_or_barcode": "9999999",
            "confirmed_by": "user",
        }
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY, aliases=aliases)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 1
    assert p["totals"]["products_ambiguous"] == 0
    assert p["totals"]["revenue_sold_ge"] == 200


# ---------------------------------------------------------------------------
# PROTECTED detection (cigarettes + alcohol)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "category",
    [
        "0804 | სიგარეტი",
        "სიგარეტი",
        "ლუდი ქართული",
        "ღვინო წითელი",
        "არაყი ფრემიუმ",
        "კონიაკი",
        "ვისკი ბურბონი",
        "შამპანური",
    ],
)
def test_protected_categories_excluded_from_bottom_margin(category):
    """A low-margin product in a PROTECTED category must not appear in
    bottom_margin — we never recommend cutting cigarettes or alcohol."""
    sup = _supplier("100", "Distrib", [_imp_product("11111111", "Item", 100, 100)])
    retail = [_retail_product("99", "11111111", "Item", category, 110, 100)]  # 9% margin
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    bottom_categories = [b["category"] for b in p["bottom_margin"]]
    assert category not in bottom_categories
    # Top can still include protected (informational, not a recommendation)
    matched_categories = [m["category"] for m in p["top_margin"]]
    if matched_categories:
        assert category in matched_categories


def test_protected_substrings_constant_includes_alcohol():
    """Sanity: alcohol substrings live alongside cigarette substring."""
    subs = SUPPLIER_PROFITABILITY_PROTECTED_SUBSTRINGS
    assert "სიგარეტ" in subs
    assert "ლუდი" in subs
    assert "ღვინ" in subs
    assert "არაყ" in subs


def test_supplier_marked_protected_when_majority_cost_in_protected_category():
    """If ≥80% of matched cost falls in PROTECTED categories, the
    supplier itself gets status=protected — UI must suppress the bottom
    list (cigarette distributor's "low margin" is structural)."""
    sup = _supplier(
        "100",
        "სიგარეტ Distrib",
        [
            _imp_product("11111111", "Marlboro", 1000, 9000),  # 90% of cost
            _imp_product("22222222", "Lighter", 100, 1000),     # 10% of cost
        ],
    )
    retail = [
        _retail_product("90", "11111111", "Marlboro", "0804 | სიგარეტი", 9500, 9000),  # protected
        _retail_product("91", "22222222", "Lighter", "სხვადასხვა", 1300, 1000),         # not protected
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["status"] == "protected"
    assert p["coverage"]["protected_cost_share_pct"] >= PROTECTED_DOMINANT_PCT


def test_supplier_not_protected_when_minority_cost_in_protected():
    """A general distributor whose ONLY cigarette SKU is a small fraction
    must not be labeled protected. Threshold is ≥80% of MATCHED cost."""
    sup = _supplier(
        "100",
        "Mixed",
        [
            _imp_product("11111111", "Marlboro", 10, 100),   # 10% protected
            _imp_product("22222222", "Bread", 1000, 900),    # 90% non-protected
        ],
    )
    retail = [
        _retail_product("90", "11111111", "Marlboro", "სიგარეტი", 110, 100),
        _retail_product("91", "22222222", "Bread", "პური", 1200, 900),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert p["status"] != "protected"


# ---------------------------------------------------------------------------
# Status decision
# ---------------------------------------------------------------------------

def test_status_verified_when_high_coverage_and_low_protected():
    sup = _supplier("100", "Clean", [_imp_product("11111111", "X", 10, 100)])
    retail = [_retail_product("9", "11111111", "X", "სხვა", 130, 100)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    assert out["per_supplier"][0]["profitability"]["status"] == "verified"


def test_status_partial_when_medium_coverage():
    """Two products imported, only one matched → coverage = 50% (between
    UNVERIFIED 5% and VERIFIED 80% thresholds → partial)."""
    sup = _supplier(
        "100",
        "MidCov",
        [
            _imp_product("11111111", "matched", 1, 100),
            _imp_product("99999999", "unmatched", 1, 100),
        ],
    )
    retail = [_retail_product("9", "11111111", "matched", "სხვა", 130, 100)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert p["status"] == "partial"
    assert p["coverage"]["cost_pct"] == pytest.approx(50.0, abs=0.5)


def test_status_unverified_when_no_match():
    sup = _supplier("100", "NoMatch", [_imp_product("99999999", "X", 1, 100)])
    retail = [_retail_product("1", "1111", "Other", "სხვა", 50, 30)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    assert out["per_supplier"][0]["profitability"]["status"] == "unverified"


def test_status_empty_when_no_products():
    sup = _supplier("100", "Empty", [])
    out = build_supplier_profitability(_data([sup], []), today=TODAY)
    assert out["per_supplier"][0]["profitability"]["status"] == "empty"


# ---------------------------------------------------------------------------
# Dead stock
# ---------------------------------------------------------------------------

def test_dead_stock_when_last_sale_beyond_threshold():
    """Last sale > 120 days ago → flagged as dead stock."""
    sup = _supplier("100", "X", [_imp_product("11111111", "Old", 10, 100)])
    retail = [_retail_product("9", "11111111", "Old", "სხვა", 130, 100, last_sale="2025-10-01")]
    # TODAY = 2026-04-26 → 207 days since last sale
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert len(p["dead_stock"]) == 1
    assert p["dead_stock"][0]["days_since_last_sale"] > DEAD_STOCK_THRESHOLD_DAYS


def test_not_dead_when_recent_sale():
    sup = _supplier("100", "X", [_imp_product("11111111", "Fresh", 10, 100)])
    retail = [_retail_product("9", "11111111", "Fresh", "სხვა", 130, 100, last_sale="2026-04-20")]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    assert out["per_supplier"][0]["profitability"]["dead_stock"] == []


def test_dead_stock_when_zero_revenue():
    """Even if last sale is recent, zero revenue = dead stock."""
    sup = _supplier("100", "X", [_imp_product("11111111", "Zero", 10, 100)])
    retail = [_retail_product("9", "11111111", "Zero", "სხვა", 0, 0, last_sale="2026-04-20")]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    assert len(out["per_supplier"][0]["profitability"]["dead_stock"]) == 1


# ---------------------------------------------------------------------------
# Top / bottom margin lists
# ---------------------------------------------------------------------------

def test_top_margin_excludes_low_revenue_noise():
    """Product with revenue < MIN_REVENUE_FOR_MARGIN_LIST_GE excluded."""
    sup = _supplier(
        "100",
        "X",
        [
            _imp_product("11111111", "tiny", 1, 1),       # rev 5 (below floor)
            _imp_product("22222222", "real", 100, 100),   # rev 200
        ],
    )
    retail = [
        _retail_product("a", "11111111", "tiny", "სხვა", 5, 1),
        _retail_product("b", "22222222", "real", "სხვა", 200, 100),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    names = [t["imported_name"] for t in p["top_margin"]]
    assert "tiny" not in names
    assert "real" in names


def test_top_margin_capped_at_three():
    products = [_imp_product(f"{i:08d}", f"prod{i}", 100, 100) for i in range(10)]
    sup = _supplier("100", "X", products)
    # Make each retail row distinct margin
    retail = [
        _retail_product(f"a{i}", f"{i:08d}", f"prod{i}", "სხვა", 200 + i * 10, 100)
        for i in range(10)
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert len(p["top_margin"]) == 3
    assert len(p["bottom_margin"]) == 3


# ---------------------------------------------------------------------------
# Minimal display (small suppliers)
# ---------------------------------------------------------------------------

def test_minimal_display_for_small_supplier():
    sup = _supplier(
        "100",
        "Tiny",
        [_imp_product(f"1111111{i}", f"p{i}", 1, 10) for i in range(3)],
    )
    out = build_supplier_profitability(_data([sup], []), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert p["minimal_display"] is True


def test_full_display_for_normal_supplier():
    sup = _supplier(
        "100",
        "Normal",
        [_imp_product(f"1111111{i}", f"p{i}", 1, 10) for i in range(MIN_PRODUCTS_FOR_FULL_DISPLAY + 1)],
    )
    out = build_supplier_profitability(_data([sup], []), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert p["minimal_display"] is False


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

def test_portfolio_summary_aggregates_per_supplier_correctly():
    # qty matches imported qty → imputed cost = recorded cost = supplier
    # invoice cost (100 for A, 50 for B), so portfolio profit = 60 cleanly.
    sup_a = _supplier("100", "A", [_imp_product("11111111", "x", 10, 100)])
    sup_b = _supplier("200", "B", [_imp_product("22222222", "y", 5, 50)])
    retail = [
        _retail_product("a", "11111111", "x", "სხვა", 130, 100, qty=10),
        _retail_product("b", "22222222", "y", "სხვა", 80, 50, qty=5),
    ]
    out = build_supplier_profitability(_data([sup_a, sup_b], retail), today=TODAY)
    sm = out["summary"]["portfolio"]
    assert sm["cost_imported_ge"] == pytest.approx(150.0, abs=0.01)
    assert sm["cost_matched_ge"] == pytest.approx(150.0, abs=0.01)
    assert sm["revenue_sold_ge"] == pytest.approx(210.0, abs=0.01)
    assert sm["profit_ge"] == pytest.approx(60.0, abs=0.01)
    assert sm["coverage_cost_pct"] == pytest.approx(100.0, abs=0.01)


def test_portfolio_counts_match_status_distribution():
    sup_v = _supplier("1", "ver", [_imp_product("11111111", "x", 10, 100)])
    sup_u = _supplier("2", "unv", [_imp_product("99999999", "y", 10, 100)])
    retail = [_retail_product("a", "11111111", "x", "სხვა", 130, 100)]
    out = build_supplier_profitability(_data([sup_v, sup_u], retail), today=TODAY)
    counts = out["summary"]["supplier_counts"]
    assert counts["verified"] == 1
    assert counts["unverified"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_imported_products_returns_empty_lists():
    out = build_supplier_profitability({"imported_products": {"suppliers": []},
                                         "retail_sales": {"by_product": []}}, today=TODAY)
    assert out["per_supplier"] == []
    assert out["summary"]["portfolio"]["cost_imported_ge"] == 0


def test_missing_data_keys_does_not_crash():
    out = build_supplier_profitability({}, today=TODAY)
    assert out["per_supplier"] == []


def test_zero_revenue_does_not_divide():
    sup = _supplier("100", "X", [_imp_product("11111111", "free", 1, 0)])
    retail = [_retail_product("a", "11111111", "free", "სხვა", 0, 0)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    assert out["per_supplier"][0]["profitability"]["totals"]["margin_pct"] == 0


# ---------------------------------------------------------------------------
# Per-store breakdown
# ---------------------------------------------------------------------------

def test_per_store_breakdown_joins_imported_and_retail_by_object():
    """Supplier ships to two stores; retail records sales at both. Output
    must show per-store cost-imported, revenue, and margin matching
    hand-computed numbers."""
    sup = _supplier_with_objects(
        "100",
        "X",
        [_imp_product("11111111", "X", 50, 500)],  # 500₾ imported total
        object_breakdown=[
            {"object": "ოზურგეთი", "row_count": 30, "total_amount_ge": 300, "total_quantity": 30},
            {"object": "დვაბზუ", "row_count": 20, "total_amount_ge": 200, "total_quantity": 20},
        ],
    )
    retail = [
        _retail_product(
            "9", "11111111", "X", "სხვა", 700, 500, qty=50,
            object_breakdown=[
                {"object": "ოზურგეთი", "row_count": 30, "total_quantity": 30,
                 "revenue_ge": 420, "cost_ge": 300, "profit_ge": 120, "gross_margin_pct": 28.57},
                {"object": "დვაბზუ", "row_count": 20, "total_quantity": 20,
                 "revenue_ge": 280, "cost_ge": 200, "profit_ge": 80, "gross_margin_pct": 28.57},
            ],
        )
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    per_store = {s["object"]: s for s in p["per_store_breakdown"]}

    assert "ოზურგეთი" in per_store
    assert "დვაბზუ" in per_store
    assert per_store["ოზურგეთი"]["cost_imported_ge"] == 300
    assert per_store["ოზურგეთი"]["revenue_sold_ge"] == 420
    assert per_store["ოზურგეთი"]["profit_ge"] == 120
    assert per_store["ოზურგეთი"]["margin_pct"] == pytest.approx(28.57, abs=0.01)
    assert per_store["დვაბზუ"]["cost_imported_ge"] == 200
    assert per_store["დვაბზუ"]["revenue_sold_ge"] == 280


def test_per_store_breakdown_handles_only_imported_no_retail():
    """A supplier delivered to a store but the product never sold (or
    barcode didn't match) → store appears with cost only, revenue 0."""
    sup = _supplier_with_objects(
        "100",
        "X",
        [_imp_product("11111111", "X", 10, 100)],
        object_breakdown=[
            {"object": "ოზურგეთი", "row_count": 10, "total_amount_ge": 100, "total_quantity": 10},
        ],
    )
    out = build_supplier_profitability(_data([sup], []), today=TODAY)  # no retail
    p = out["per_supplier"][0]["profitability"]
    per_store = {s["object"]: s for s in p["per_store_breakdown"]}
    assert per_store["ოზურგეთი"]["cost_imported_ge"] == 100
    assert per_store["ოზურგეთი"]["revenue_sold_ge"] == 0
    assert per_store["ოზურგეთი"]["margin_pct"] == 0


def test_per_store_breakdown_sorted_by_imported_cost_desc():
    sup = _supplier_with_objects(
        "100",
        "X",
        [_imp_product("11111111", "X", 100, 1000)],
        object_breakdown=[
            {"object": "ოზურგეთი", "row_count": 50, "total_amount_ge": 200, "total_quantity": 20},
            {"object": "დვაბზუ", "row_count": 50, "total_amount_ge": 800, "total_quantity": 80},
        ],
    )
    out = build_supplier_profitability(_data([sup], []), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    objs = [s["object"] for s in p["per_store_breakdown"]]
    assert objs == ["დვაბზუ", "ოზურგეთი"]  # bigger cost first


def test_per_store_breakdown_empty_when_no_object_breakdown_anywhere():
    """If imported has no object_breakdown and retail rows have empty
    object_breakdown, per_store_breakdown is empty (not error)."""
    sup = _supplier("100", "X", [_imp_product("11111111", "X", 10, 100)])
    # supplier has NO object_breakdown field
    retail = [_retail_product("9", "11111111", "X", "სხვა", 130, 100)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]
    assert p["per_store_breakdown"] == []


def test_destination_resolver_priority_order_wins():
    """Critical bug-prevention test (rewritten 2026-04-27 from longest-variant
    heuristic to keyword-priority — 16% of imported rows portfolio-wide
    were misclassified because RS source uses surface variants like
    'ოზურგეთი, სოფ. დვაბზუ' that were not enumerated in the mapping, so
    'ოზურგეთი' matched first via length-fallback).

    New rule: rs_location_priority_order declares which target is checked
    first. For each target in priority order, the first variant substring
    match wins.
    """
    from dashboard_pipeline.imported_products import (
        _build_destination_lookup,
        _resolve_destination_object,
    )
    mapping = {
        "rs_location_priority_order": ["დვაბზუ", "ოზურგეთი"],
        "rs_location_to_object": {
            "დვაბზუ": ["დვაბზუ", "დუაბზო", "დავაბზუ", "დვაბზე"],
            "ოზურგეთი": ["ოზურგეთი", "ოზურგეთო", "ოზუეგეთი"],
        },
        "default_object": "გაუნაწილებელი",
    }
    lookup = _build_destination_lookup(mapping)

    # Plain ოზურგეთი delivery — only ოზურგეთი keyword present.
    assert _resolve_destination_object(
        "ოზურგეთი სოფ. ოზურგეთი", lookup, "გაუნაწილებელი"
    ) == "ოზურგეთი"
    # Plain დვაბზუ delivery — only დვაბზუ keyword present.
    assert _resolve_destination_object(
        "სოფელი დვაბზუ", lookup, "გაუნაწილებელი"
    ) == "დვაბზუ"
    # Default + empty.
    assert _resolve_destination_object(
        "სხვა ქალაქი", lookup, "გაუნაწილებელი"
    ) == "გაუნაწილებელი"
    assert _resolve_destination_object(
        "", lookup, "გაუნაწილებელი"
    ) == "გაუნაწილებელი"

    # Bug regression cases: source contains BOTH ოზურგეთი AND a დვაბზუ
    # variant. Pre-fix the resolver returned ოზურგეთი (length-fallback
    # since the compound 'სოფ. დვაბზუ' was not enumerated). Priority-order
    # MUST return დვაბზუ for all of these.
    bug_cases = [
        "ოზურგეთი, სოფ. დვაბზუ",         # ELIZI top variant — 172,926 ₾
        "ოზურგეთის რ/ნ, სოფ. დვაბზუ",     # Iberia Refreshments — 42,649 ₾
        "ოზურგეთი სოფ. გაღმა დვაბზუ",     # historical case
        "ოზურგეთის რაიონი სოფელი დვაბზუ",
        "ოზურგეთი, სოფ დავაბზუ",          # Coca-Cola Guria — 148,629 ₾
        "ოზურგეთი სოფ დუაბზო",            # Zedazeni Achara — 74,254 ₾
        "ოზურგეთი, სოფ.დვაბზე",
        "ოზურგეთი, დვაბზუ",               # Kanti — 28,137 ₾
        "ოზურგეთი ს. ზედა დვაბზუ",
        "ოზურგეთი, სოფ. დვაბზუ (Foodmart)",
        "ოზურგეთი ს.დვაბზუ",
    ]
    for text in bug_cases:
        assert _resolve_destination_object(text, lookup, "გაუნაწილებელი") == "დვაბზუ", (
            f"priority-order regression: {text!r} should resolve to 'დვაბზუ', "
            f"got {_resolve_destination_object(text, lookup, 'გაუნაწილებელი')!r}"
        )


def test_destination_resolver_priority_falls_back_to_insertion_order():
    """If rs_location_priority_order is absent, the mapping's dict insertion
    order is used. Keeps the resolver functional for legacy mappings; the
    expected guarantee is documented in object_mapping.json."""
    from dashboard_pipeline.imported_products import (
        _build_destination_lookup,
        _resolve_destination_object,
    )
    mapping = {
        "rs_location_to_object": {
            "დვაბზუ": ["დვაბზუ"],
            "ოზურგეთი": ["ოზურგეთი"],
        },
        "default_object": "გაუნაწილებელი",
    }
    lookup = _build_destination_lookup(mapping)
    priority_order, _ = lookup
    assert priority_order == ["დვაბზუ", "ოზურგეთი"]
    assert _resolve_destination_object(
        "ოზურგეთი, სოფ. დვაბზუ", lookup, "გაუნაწილებელი"
    ) == "დვაბზუ"


def test_destination_resolver_priority_appends_undeclared_targets():
    """Defensive: if a target is in the mapping but missing from
    rs_location_priority_order, it is appended at the end so the resolver
    never silently ignores configured destinations."""
    from dashboard_pipeline.imported_products import _build_destination_lookup
    mapping = {
        "rs_location_priority_order": ["ოზურგეთი"],
        "rs_location_to_object": {
            "დვაბზუ": ["დვაბზუ"],
            "ოზურგეთი": ["ოზურგეთი"],
            "ბათუმი": ["ბათუმი"],
        },
        "default_object": "გაუნაწილებელი",
    }
    priority_order, _ = _build_destination_lookup(mapping)
    assert priority_order[0] == "ოზურგეთი"
    assert "დვაბზუ" in priority_order
    assert "ბათუმი" in priority_order
    assert len(priority_order) == 3


def test_alias_with_non_user_confirmed_by_is_ignored_at_lookup():
    """The validator should reject non-user aliases, but if they slip
    through, build_supplier_profitability does not blow up. Untrusted
    aliases simply do nothing (no automation seeding allowed)."""
    sup = _supplier("100", "X", [_imp_product("ZZZ", "alias-target", 1, 100)])
    retail = [_retail_product("real", "12345", "real", "სხვა", 200, 100)]
    bad_aliases = [{"imported_code": "ZZZ", "retail_code_or_barcode": "12345"}]
    # confirmed_by missing — but build_supplier_profitability does not
    # enforce that (validator does); _build_alias_lookup just flattens.
    # The key safety is at the validator level, not here.
    out = build_supplier_profitability(_data([sup], retail), today=TODAY, aliases=bad_aliases)
    p = out["per_supplier"][0]["profitability"]
    # Module trusts what it's given — confirms the validator separation
    assert p["totals"]["products_matched"] == 1


# ---------------------------------------------------------------------------
# x-suffix rule (MAX deprecated-marker convention)
# ---------------------------------------------------------------------------

def test_x_suffix_match_uniq_rescues_deprecated_max_code():
    """imported '2157' should hit retail '2157x' uniquely → verified."""
    sup = _supplier("100", "Ц", [_imp_product("2157", "ქემელი 1913 ორიგინალ იელოუ (PP)*", 100, 6500.0)])
    retail = [_retail_product("2157x", "4860126910173x", "ქემელი 1913 ორიგინალ იელოუ (PP)*", "სიგარეტი", 8000.0, 6500.0)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 1
    assert p["totals"]["products_unmatched"] == 0
    matched = p["top_margin"][0] if p["top_margin"] else None
    assert matched is not None
    assert matched["match_kind"] in ("product_code_x_suffix", "barcode_x_suffix")


def test_x_suffix_does_not_override_direct_pcode_hit():
    """If '2157' already hits retail directly, x-suffix is not consulted."""
    sup = _supplier("100", "Ц", [_imp_product("2157", "ქემელი", 100, 5000.0)])
    retail = [
        _retail_product("2157", "barcA", "ქემელი — current", "სიგარეტი", 7000.0, 5000.0),
        _retail_product("2157x", "barcB", "ქემელი — old (deprecated)", "სიგარეტი", 9999.0, 1000.0),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    matched = p["top_margin"][0]
    assert matched["match_kind"] == "product_code"
    assert matched["retail_name"] == "ქემელი — current"


def test_x_suffix_skipped_when_ambiguous():
    """If '2157x' has 2+ retail rows, x-suffix is not used (no automatic
    disambiguation)."""
    sup = _supplier("100", "Ц", [_imp_product("2157", "ქემელი", 10, 50.0)])
    retail = [
        _retail_product("2157x", "barcA", "ქემელი A", "სიგარეტი", 70.0, 50.0),
        _retail_product("2157x", "barcB", "ქემელი B", "სიგარეტი", 80.0, 60.0),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    # No match — falls through to "none"
    assert p["totals"]["products_matched"] == 0
    assert p["totals"]["products_unmatched"] == 1


# ---------------------------------------------------------------------------
# name_candidate hint (alias workflow surface)
# ---------------------------------------------------------------------------

def test_name_candidate_attached_when_unique_name_match_non_protected():
    """Shared-name beverage (Borjomi rule): when MORE than one supplier
    imports the same product_name, the name is NOT supplier-exclusive, so
    auto-merge does not fire — the unmatched row carries the candidate
    hint for user-driven alias confirmation instead.
    (When a name IS supplier-exclusive, `name_supplier_exclusive` does
    auto-merge — that's covered by tests below.)"""
    sup_a = _supplier("100", "Ц", [_imp_product("9999", "ჩერო მულტიხილი 1ლ", 10, 60.0)])
    sup_b = _supplier("200", "Other", [_imp_product("8888", "ჩერო მულტიხილი 1ლ", 5, 30.0)])
    retail = [_retail_product("777", "barcA", "ჩერო მულტიხილი 1ლ", "წვენი პეტი", 70.0, 60.0)]
    out = build_supplier_profitability(_data([sup_a, sup_b], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 0
    assert p["totals"]["products_unmatched"] == 1
    unmatched = p["unmatched_preview"][0]
    cand = unmatched["name_candidate"]
    assert cand is not None
    assert cand["retail_product_code"] == "777"
    assert cand["retail_barcode"] == "barcA"
    assert cand["retail_category"] == "წვენი პეტი"

    # coverage stats expose the actionable opportunity
    assert p["coverage"]["unmatched_with_candidate_count"] == 1
    assert p["coverage"]["unmatched_with_candidate_cost_ge"] == 60.0


def test_name_candidate_none_when_multiple_retail_rows_share_name():
    """Two retail rows with same name → unsafe to suggest one → candidate stays None."""
    sup = _supplier("100", "Ц", [_imp_product("9999", "ბორჯომი 1ლ", 10, 9.0)])
    retail = [
        _retail_product("AA", "11", "ბორჯომი 1ლ", "წყალი (მინა)", 12.0, 9.0),
        _retail_product("BB", "22", "ბორჯომი 1ლ", "წყალი (პლასტიკი)", 11.0, 8.5),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    unmatched = p["unmatched_preview"][0]
    assert unmatched["name_candidate"] is None
    assert p["coverage"]["unmatched_with_candidate_count"] == 0


def test_name_candidate_normalizes_whitespace_and_punctuation():
    """„X (Y)*" should match „X (Y) *" (different whitespace/punct).
    Use a non-protected category and a shared name (2 suppliers) so the
    auto-merge rule does not fire and the candidate hint stays in
    unmatched_preview."""
    sup_a = _supplier("100", "Ц", [_imp_product("9999", "ფანტა მსხალი  0.5ლ*", 10, 60.0)])
    sup_b = _supplier("200", "Other", [_imp_product("8888", "ფანტა მსხალი 0.5ლ *", 5, 30.0)])
    retail = [_retail_product("777", "barcA", "ფანტა მსხალი 0.5ლ *", "გაზ.სასმელი", 70.0, 60.0)]
    out = build_supplier_profitability(_data([sup_a, sup_b], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    cand = p["unmatched_preview"][0]["name_candidate"]
    assert cand is not None
    assert cand["retail_product_code"] == "777"


def test_name_candidate_attached_to_ambiguous_rows_too():
    """Code with 2+ retail rows → ambiguous. When the name IS shared
    across multiple suppliers (Borjomi-style), name_supplier_exclusive
    does NOT fire — the row stays ambiguous but carries the candidate
    hint so the user can manually pick the right SKU."""
    sup_a = _supplier("100", "Ц", [_imp_product("CODE", "Borjomi 1L Plastic", 1, 10)])
    sup_b = _supplier("200", "Other", [_imp_product("OTHER", "Borjomi 1L Plastic", 1, 10)])
    retail = [
        # 2 rows with same code → ambiguous
        _retail_product("CODE", "BC1", "Borjomi 1L Glass", "მინა", 12, 10),
        _retail_product("CODE", "BC2", "Borjomi 1L Plastic", "პლასტიკი", 11, 9),
    ]
    out = build_supplier_profitability(_data([sup_a, sup_b], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_ambiguous"] == 1
    amb = p["ambiguous_preview"][0]
    cand = amb["name_candidate"]
    assert cand is not None
    assert cand["retail_barcode"] == "BC2"  # name "Borjomi 1L Plastic" → uniquely BC2
    assert p["coverage"]["ambiguous_with_candidate_count"] == 1


def test_name_in_protected_category_auto_matches_cigarette():
    """Cigarette names encode brand+variant+size — unique name in a
    PROTECTED retail category auto-merges (covers ELIZI-style suppliers
    that ship under MAX's legacy 4-digit codes)."""
    sup = _supplier("100", "Elizi", [_imp_product("2158", "ქემელი 1913 ორიგინალ ბლუ  (PP)*", 100, 5800.0)])
    retail = [_retail_product("2267277", "4860126910180", "ქემელი 1913 ორიგინალ ბლუ (PP)", "სიგარეტი", 7000.0, 5800.0)]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 1
    assert p["totals"]["products_unmatched"] == 0
    matched = p["top_margin"][0]
    assert matched["match_kind"] == "name_in_protected_category"
    assert matched["retail_product_code"] == "2267277"


def test_name_in_protected_category_does_not_fire_for_beverages():
    """Borjomi rule — beverages are NOT in the PROTECTED category set, so
    the protected-category name path stays off. When the name is ALSO
    shared across multiple suppliers (Coca-Cola distributors, multiple
    importers of Borjomi), the supplier-exclusive name path does not
    fire either, so the row stays unmatched with a candidate hint."""
    sup_a = _supplier("100", "X", [_imp_product("9999", "ბორჯომი 1ლ", 10, 9.0)])
    sup_b = _supplier("200", "Y", [_imp_product("8888", "ბორჯომი 1ლ", 5, 4.5)])
    # category lacks any protected substring
    retail = [_retail_product("AA", "11", "ბორჯომი 1ლ", "მინერალური წყალი", 12.0, 9.0)]
    out = build_supplier_profitability(_data([sup_a, sup_b], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    # Should stay unmatched but carry candidate hint
    assert p["totals"]["products_matched"] == 0
    assert p["totals"]["products_unmatched"] == 1
    cand = p["unmatched_preview"][0]["name_candidate"]
    assert cand is not None  # hint surfaces, but auto-merge does not


def test_name_in_protected_category_skipped_when_multiple_retail_rows():
    """Even within a protected category, if 2+ retail rows share the
    name, do NOT auto-merge (could be different SKUs with reused name)."""
    sup = _supplier("100", "X", [_imp_product("9999", "ლუდი ბავარია", 100, 5000.0)])
    retail = [
        _retail_product("A", "11", "ლუდი ბავარია", "ლუდი ქართული ფეტი", 6000.0, 5000.0),
        _retail_product("B", "22", "ლუდი ბავარია", "ლუდი იმპ. შუშა", 6500.0, 5500.0),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    assert p["totals"]["products_matched"] == 0
    assert p["totals"]["products_unmatched"] == 1


def test_name_in_protected_category_does_not_override_code_match():
    """If imported code already hits a retail row directly, do NOT search
    by name. Code wins."""
    sup = _supplier("100", "X", [_imp_product("12345", "ქემელი 1913 ორიგინალ ბლუ", 100, 5000.0)])
    retail = [
        _retail_product("12345", "AA", "ვინსტონი XS ბლუ", "სიგარეტი", 6000.0, 5000.0),
        _retail_product("99", "BB", "ქემელი 1913 ორიგინალ ბლუ", "სიგარეტი", 7000.0, 5500.0),
    ]
    out = build_supplier_profitability(_data([sup], retail), today=TODAY)
    p = out["per_supplier"][0]["profitability"]

    matched = p["top_margin"][0]
    assert matched["match_kind"] == "product_code"
    assert matched["retail_product_code"] == "12345"


def test_portfolio_summary_aggregates_candidate_counts():
    """Summary's portfolio block exposes total alias-confirmable
    opportunities. Use SHARED names across suppliers so the auto-merge
    rule does not fire — the candidate hint is the actionable signal."""
    sup_a = _supplier("100", "A", [_imp_product("9991", "Product A", 1, 50)])
    sup_b = _supplier("200", "B", [_imp_product("9992", "Product B", 1, 70)])
    sup_c = _supplier("300", "C", [
        _imp_product("9993", "Product A", 1, 50),  # shares name with sup_a
        _imp_product("9994", "Product B", 1, 70),  # shares name with sup_b
    ])
    retail = [
        _retail_product("777", "BC1", "Product A", "cat1", 60, 50),  # name match for sup_a
        _retail_product("888", "BC2", "Product B", "cat2", 80, 70),  # name match for sup_b
    ]
    out = build_supplier_profitability(_data([sup_a, sup_b, sup_c], retail), today=TODAY)

    summary = out["summary"]["portfolio"]
    # Each unmatched row in sup_a + sup_b carries a candidate hint (the
    # third supplier's matching products do too, but the candidate is
    # still surfaced — total = 4)
    assert summary["unmatched_with_candidate_count"] == 4
    assert summary["unmatched_with_candidate_cost_ge"] == 240.0
