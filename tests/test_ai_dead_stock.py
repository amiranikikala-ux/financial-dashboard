"""Phase 2.11 — dead_stock analyzer tests.

Covers:
* Argument coercion and validation (days_threshold / store / top_n).
* Product matching waterfall (code → barcode → name).
* Bucket assignment across the 91/181/365 boundaries.
* Recommended action rule table.
* Frozen cash and expected_freed_cash factors.
* Store filter (total / ოზურგეთი / დვაბზუ / Latin alias).
* Matching warning threshold (30%).
* Edge cases: empty imported_products, empty retail_sales, NaN / None.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.dead_stock import (
    ACTION_DISCOUNT_15,
    ACTION_DISCOUNT_30,
    ACTION_SUPPLIER_RETURN,
    ACTION_WRITE_OFF,
    ALL_ACTIONS,
    BUCKET_181_365,
    BUCKET_365_PLUS,
    BUCKET_91_180,
    BUCKET_ACTIVE,
    BUCKET_UNMATCHED,
    DEFAULT_DAYS_THRESHOLD,
    DEFAULT_TOP_N,
    MAX_DAYS_THRESHOLD,
    MAX_TOP_N,
    MIN_DAYS_THRESHOLD,
    MIN_TOP_N,
    STORE_DVABZU,
    STORE_OZURGETI,
    STORE_TOTAL,
    _bucket_for,
    _build_sales_index,
    _expected_freed_cash,
    _match_imported_to_sales,
    _normalize_code,
    _normalize_name,
    _recommend_action,
    _resolve_days_threshold,
    _resolve_store,
    _resolve_top_n,
    analyze_dead_stock,
)


TODAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _loader_for(data: Dict[str, Any]):
    """Return a zero-arg loader that yields ``data``."""

    def _load():
        return data

    return _load


def _make_imported(
    *,
    code: str,
    name: str = "Generic",
    amount: float = 100.0,
    qty: float = 10.0,
    barcode: str = "",
    distinct_supplier_count: int = 1,
    supplier_name: str = "შპს ტესტი",
) -> Dict[str, Any]:
    return {
        "product_code": code,
        "barcode": barcode,
        "product_name": name,
        "total_amount_ge": amount,
        "total_quantity": qty,
        "distinct_supplier_count": distinct_supplier_count,
        "top_suppliers": [
            {"supplier": supplier_name, "row_count": 1, "total_amount_ge": amount}
        ],
    }


def _make_sales(
    *,
    code: str = "",
    barcode: str = "",
    name: str = "Generic",
    last_sold: str = "2026-04-10",
    gross_margin_pct: float = 15.0,
    object_: str = STORE_OZURGETI,
) -> Dict[str, Any]:
    return {
        "product_code": code,
        "barcode": barcode,
        "product_name": name,
        "gross_margin_pct": gross_margin_pct,
        "date_range": {"min": "2023-01-01", "max": last_sold},
        "object_breakdown": [{"object": object_, "row_count": 1}],
    }


def _default_data(
    *,
    imported: List[Dict[str, Any]],
    sales: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "imported_products": {"products": imported},
        "retail_sales": {"by_product": sales},
    }


# ---------------------------------------------------------------------------
# TestArgumentValidation
# ---------------------------------------------------------------------------


class TestArgumentValidation:
    def test_days_threshold_defaults(self):
        assert _resolve_days_threshold(None) == DEFAULT_DAYS_THRESHOLD

    def test_days_threshold_clamps_below_min(self):
        assert _resolve_days_threshold(0) == MIN_DAYS_THRESHOLD

    def test_days_threshold_clamps_above_max(self):
        assert _resolve_days_threshold(10_000) == MAX_DAYS_THRESHOLD

    def test_days_threshold_accepts_string(self):
        assert _resolve_days_threshold("120") == 120

    def test_days_threshold_falls_back_on_invalid(self):
        assert _resolve_days_threshold("abc") == DEFAULT_DAYS_THRESHOLD

    def test_top_n_defaults(self):
        assert _resolve_top_n(None) == DEFAULT_TOP_N

    def test_top_n_clamps_below_min(self):
        assert _resolve_top_n(0) == MIN_TOP_N

    def test_top_n_clamps_above_max(self):
        assert _resolve_top_n(500) == MAX_TOP_N

    def test_store_default_is_total(self):
        assert _resolve_store(None) == STORE_TOTAL
        assert _resolve_store("") == STORE_TOTAL
        assert _resolve_store("   ") == STORE_TOTAL

    def test_store_latin_alias_resolves(self):
        assert _resolve_store("ozurgeti") == STORE_OZURGETI
        assert _resolve_store("OZURGHETI") == STORE_OZURGETI
        assert _resolve_store("dvabzu") == STORE_DVABZU

    def test_store_georgian_passes_through(self):
        assert _resolve_store("ოზურგეთი") == STORE_OZURGETI
        assert _resolve_store("დვაბზუ") == STORE_DVABZU

    def test_store_unknown_returns_none(self):
        assert _resolve_store("kobuleti") is None
        assert _resolve_store(42) is None


# ---------------------------------------------------------------------------
# TestNameNormalization
# ---------------------------------------------------------------------------


class TestNameNormalization:
    def test_normalize_code_strips_whitespace(self):
        assert _normalize_code("  123 ") == "123"
        assert _normalize_code(None) == ""

    def test_normalize_code_preserves_case(self):
        # Codes are case-sensitive (barcodes are digits, SKUs mix case).
        assert _normalize_code("AbC123") == "AbC123"

    def test_normalize_name_collapses_punctuation(self):
        a = _normalize_name("Coca-Cola 2L (6ც.)")
        b = _normalize_name("coca cola 2l 6ც")
        assert a == b

    def test_normalize_name_handles_georgian(self):
        assert _normalize_name("შეფუთული ქვის პური") == "შეფუთული ქვის პური"

    def test_normalize_name_empty_for_none(self):
        assert _normalize_name(None) == ""
        assert _normalize_name("") == ""


# ---------------------------------------------------------------------------
# TestMatching — code → barcode → name precedence
# ---------------------------------------------------------------------------


class TestCodeMatching:
    def test_exact_code_match(self):
        sales = [_make_sales(code="A1", name="Alpha", last_sold="2026-04-01")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="A1", name="Alpha")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is not None
        assert method == "code"

    def test_code_whitespace_tolerant(self):
        sales = [_make_sales(code="A1", name="Alpha")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="  A1 ", name="Alpha")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is not None
        assert method == "code"

    def test_code_case_preserves_mismatch(self):
        # Codes ARE case-sensitive — 'A1' and 'a1' are different SKUs.
        sales = [_make_sales(code="A1", name="Alpha")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="a1", name="Different product")
        row, method = _match_imported_to_sales(imported, idx)
        # code="a1" not in index; name "Different product" not in index.
        assert row is None

    def test_code_lookup_checks_barcode_side(self):
        # Imported's product_code sometimes equals sales.barcode.
        sales = [_make_sales(code="", barcode="7770001", name="Barish")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="7770001", name="Something")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is not None
        assert method == "barcode"


class TestBarcodeMatching:
    def test_barcode_field_resolves_to_code(self):
        sales = [_make_sales(code="SKU5", name="Widget")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="", barcode="SKU5", name="Other")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is not None
        assert method == "code"

    def test_barcode_to_barcode(self):
        sales = [_make_sales(code="", barcode="9990000", name="Gadget")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="", barcode="9990000", name="Other")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is not None
        assert method == "barcode"


class TestNameMatching:
    def test_fuzzy_name_match(self):
        sales = [_make_sales(code="X", name="Coca-Cola 2L (6ც.)")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="Y", name="coca cola 2l 6ც")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is not None
        assert method == "name"

    def test_name_match_fails_on_unrelated(self):
        sales = [_make_sales(code="X", name="Coca-Cola")]
        idx = _build_sales_index(sales)
        imported = _make_imported(code="Y", name="Pepsi 2L")
        row, method = _match_imported_to_sales(imported, idx)
        assert row is None
        assert method is None


# ---------------------------------------------------------------------------
# TestStaleBucketSplit
# ---------------------------------------------------------------------------


class TestStaleBucketSplit:
    def test_active_zone(self):
        assert _bucket_for(0, threshold=90) == BUCKET_ACTIVE
        assert _bucket_for(45, threshold=90) == BUCKET_ACTIVE
        assert _bucket_for(90, threshold=90) == BUCKET_ACTIVE

    def test_91_to_180_days(self):
        assert _bucket_for(91, threshold=90) == BUCKET_91_180
        assert _bucket_for(150, threshold=90) == BUCKET_91_180
        assert _bucket_for(180, threshold=90) == BUCKET_91_180

    def test_181_to_365_days(self):
        assert _bucket_for(181, threshold=90) == BUCKET_181_365
        assert _bucket_for(300, threshold=90) == BUCKET_181_365
        assert _bucket_for(365, threshold=90) == BUCKET_181_365

    def test_365_plus_days(self):
        assert _bucket_for(366, threshold=90) == BUCKET_365_PLUS
        assert _bucket_for(10_000, threshold=90) == BUCKET_365_PLUS

    def test_none_days_is_unmatched(self):
        assert _bucket_for(None, threshold=90) == BUCKET_UNMATCHED

    def test_threshold_independent_of_subbuckets(self):
        # Wider threshold pushes some "old" rows into ACTIVE, but 91/181/365
        # sub-buckets keep their own boundaries — i.e., we don't recompute.
        assert _bucket_for(120, threshold=180) == BUCKET_ACTIVE
        assert _bucket_for(250, threshold=180) == BUCKET_181_365


# ---------------------------------------------------------------------------
# TestRecommendedAction
# ---------------------------------------------------------------------------


class TestRecommendedAction:
    def test_91_180_gets_discount_15(self):
        assert _recommend_action(
            BUCKET_91_180, distinct_supplier_count=1, gross_margin_pct=20.0
        ) == ACTION_DISCOUNT_15

    def test_181_365_gets_discount_30(self):
        assert _recommend_action(
            BUCKET_181_365, distinct_supplier_count=1, gross_margin_pct=10.0
        ) == ACTION_DISCOUNT_30

    def test_365_plus_single_supplier_gets_return(self):
        assert _recommend_action(
            BUCKET_365_PLUS, distinct_supplier_count=1, gross_margin_pct=10.0
        ) == ACTION_SUPPLIER_RETURN

    def test_365_plus_multi_supplier_gets_write_off(self):
        assert _recommend_action(
            BUCKET_365_PLUS, distinct_supplier_count=3, gross_margin_pct=10.0
        ) == ACTION_WRITE_OFF

    def test_unmatched_gets_write_off(self):
        assert _recommend_action(
            BUCKET_UNMATCHED, distinct_supplier_count=1, gross_margin_pct=0.0
        ) == ACTION_WRITE_OFF


# ---------------------------------------------------------------------------
# TestFrozenCashCalculation
# ---------------------------------------------------------------------------


class TestFrozenCashCalculation:
    def test_discount_15_recovers_85_pct(self):
        assert _expected_freed_cash(ACTION_DISCOUNT_15, 1000.0) == 850.0

    def test_discount_30_recovers_70_pct(self):
        assert _expected_freed_cash(ACTION_DISCOUNT_30, 1000.0) == 700.0

    def test_supplier_return_recovers_100_pct(self):
        assert _expected_freed_cash(ACTION_SUPPLIER_RETURN, 1000.0) == 1000.0

    def test_write_off_recovers_zero(self):
        assert _expected_freed_cash(ACTION_WRITE_OFF, 1000.0) == 0.0

    def test_unknown_action_safe_default(self):
        assert _expected_freed_cash("made_up_action", 1000.0) == 0.0


# ---------------------------------------------------------------------------
# TestStoreFilter (end-to-end through analyze_dead_stock)
# ---------------------------------------------------------------------------


class TestStoreFilter:
    def test_total_includes_everything(self):
        imported = [
            _make_imported(code="A", name="Alpha", amount=100),
            _make_imported(code="B", name="Beta", amount=200),
        ]
        sales = [
            _make_sales(code="A", name="Alpha", last_sold="2026-04-10", object_=STORE_OZURGETI),
            _make_sales(code="B", name="Beta", last_sold="2026-03-01", object_=STORE_DVABZU),
        ]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            store="total",
            today=TODAY,
        )
        assert out["summary"]["matched_count"] == 2

    def test_ozurgeti_filter_drops_dvabzu_sales(self):
        imported = [
            _make_imported(code="A", name="Alpha", amount=100),
            _make_imported(code="B", name="Beta", amount=200),
        ]
        sales = [
            _make_sales(code="A", name="Alpha", object_=STORE_OZURGETI),
            _make_sales(code="B", name="Beta", object_=STORE_DVABZU),
        ]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            store="ოზურგეთი",
            today=TODAY,
        )
        # B is only sold in დვაბზუ → should be unmatched in ოზურგეთი filter.
        assert out["summary"]["matched_count"] == 1
        assert out["summary"]["unmatched_count"] == 1

    def test_invalid_store_returns_error(self):
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=[], sales=[])),
            store="kobuleti",
        )
        assert "error" in out
        assert "უცნობი" in out["error"]


# ---------------------------------------------------------------------------
# TestMatchingWarning
# ---------------------------------------------------------------------------


class TestMatchingWarning:
    def test_warning_fires_above_30_pct(self):
        # 10 imported, 6 unmatched (60% > 30%)
        imported = [
            _make_imported(code=f"I{i}", name=f"Product {i}") for i in range(10)
        ]
        sales = [
            _make_sales(code="I0", name="Product 0"),
            _make_sales(code="I1", name="Product 1"),
            _make_sales(code="I2", name="Product 2"),
            _make_sales(code="I3", name="Product 3"),
        ]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        assert out["summary"]["matching_warning"] is not None
        assert "60.0%" in out["summary"]["matching_warning"]

    def test_warning_silent_below_threshold(self):
        # 10 imported, 1 unmatched (10% < 30%)
        imported = [
            _make_imported(code=f"I{i}", name=f"Product {i}") for i in range(10)
        ]
        sales = [
            _make_sales(code=f"I{i}", name=f"Product {i}") for i in range(9)
        ]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        assert out["summary"]["matching_warning"] is None

    def test_warning_surfaced_in_notes(self):
        imported = [
            _make_imported(code=f"I{i}", name=f"Product {i}") for i in range(10)
        ]
        # 1 sale so the retail_sales block isn't empty (which would be an
        # error exit before we ever compute matching warnings). 9/10 imports
        # will still be unmatched → warning fires.
        sales = [_make_sales(code="I0", name="Product 0")]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        warning = out["summary"]["matching_warning"]
        assert warning is not None
        assert any(warning in n for n in out["notes"])


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_imported_products_returns_error(self):
        out = analyze_dead_stock(
            _loader_for({"imported_products": {"products": []}, "retail_sales": {"by_product": []}}),
            today=TODAY,
        )
        assert "error" in out
        assert "imported_products" in out["error"]

    def test_empty_retail_sales_returns_error(self):
        imported = [_make_imported(code="A", name="Alpha")]
        out = analyze_dead_stock(
            _loader_for({"imported_products": {"products": imported}, "retail_sales": {"by_product": []}}),
            today=TODAY,
        )
        assert "error" in out
        assert "retail_sales" in out["error"]

    def test_missing_date_range_marks_unmatched(self):
        imported = [_make_imported(code="A", name="Alpha")]
        sales = [{
            "product_code": "A",
            "product_name": "Alpha",
            "date_range": {"min": None, "max": None},
            "object_breakdown": [],
        }]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        # date missing → days_since=None → bucket=unmatched
        top = out["top_stale_skus"]
        assert len(top) == 1
        assert top[0]["stale_bucket"] == BUCKET_UNMATCHED

    def test_nan_amounts_handled(self):
        imported = [{
            "product_code": "A",
            "product_name": "Alpha",
            "total_amount_ge": float("nan"),
            "total_quantity": None,
            "distinct_supplier_count": 1,
            "top_suppliers": [],
        }]
        sales = [_make_sales(code="A", name="Alpha", last_sold="2024-01-01")]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        # NaN → coerced to 0.0; no crash
        assert out["summary"]["imported_total_amount"] == 0.0
        assert len(out["top_stale_skus"]) == 1

    def test_top_n_respects_cap(self):
        imported = [
            _make_imported(code=f"I{i}", name=f"P{i}", amount=100 + i)
            for i in range(30)
        ]
        sales = [
            _make_sales(code=f"I{i}", name=f"P{i}", last_sold="2024-01-01")
            for i in range(30)
        ]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            top_n=5,
            today=TODAY,
        )
        assert len(out["top_stale_skus"]) == 5
        # Sorted desc by imported_amount
        amounts = [s["imported_amount"] for s in out["top_stale_skus"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_contract_keys_present(self):
        imported = [_make_imported(code="A", name="Alpha")]
        sales = [_make_sales(code="A", name="Alpha", last_sold="2024-01-01")]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        assert set(out.keys()) >= {
            "as_of_date",
            "days_threshold",
            "store_filter",
            "summary",
            "by_action",
            "top_stale_skus",
            "notes",
        }
        assert set(out["by_action"].keys()) == set(ALL_ACTIONS)


# ---------------------------------------------------------------------------
# End-to-end classification tests (broad coverage)
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_single_sku_classified_correctly(self):
        # 200-day-old SKU → stale_181_365d → discount_30
        imported = [_make_imported(code="A", name="Alpha", amount=1000)]
        sales = [_make_sales(
            code="A",
            name="Alpha",
            last_sold="2025-10-01",  # 2026-04-20 - 2025-10-01 = 201 days
        )]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        top = out["top_stale_skus"]
        assert len(top) == 1
        sku = top[0]
        assert sku["stale_bucket"] == BUCKET_181_365
        assert sku["recommended_action"] == ACTION_DISCOUNT_30
        assert sku["expected_freed_cash"] == 700.0  # 70% of 1000

    def test_active_sku_excluded_from_top_stale(self):
        imported = [_make_imported(code="A", name="Alpha", amount=1000)]
        sales = [_make_sales(code="A", name="Alpha", last_sold="2026-04-15")]  # 5 days ago
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        assert out["summary"]["active_within_threshold_count"] == 1
        # Active SKUs are not in top_stale.
        assert len(out["top_stale_skus"]) == 0

    def test_store_filter_output_display(self):
        imported = [_make_imported(code="A", name="Alpha")]
        sales = [_make_sales(code="A", name="Alpha", object_=STORE_OZURGETI)]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            store="ozurgeti",
            today=TODAY,
        )
        assert out["store_filter"] == STORE_OZURGETI

    def test_total_store_display_is_georgian(self):
        imported = [_make_imported(code="A", name="Alpha")]
        sales = [_make_sales(code="A", name="Alpha")]
        out = analyze_dead_stock(
            _loader_for(_default_data(imported=imported, sales=sales)),
            today=TODAY,
        )
        # Display uses "ჯამი" not "total" for the Georgian-speaking user.
        assert out["store_filter"] == "ჯამი"
