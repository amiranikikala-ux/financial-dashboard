"""Phase 2.12 — supplier_brief tests.

Covers:
* Argument coercion (lookback_months / top_n / benchmark_n).
* Supplier resolution: tax_id exact, name exact, substring, partial, unknown.
* Volume snapshot: date_range fallback chain, portfolio share, tenure.
* Payment profile: reliability bands, aging integration.
* Price benchmark: dual-source detection, unit price, gap %, quality flags.
* Leverage score: component weights, edge cases.
* Negotiation plays: rank logic, confidence tiers, evidence_refs.
* Portfolio mode: Pareto shares, HHI, top_candidates ranking.
* Matching warnings: fired when confidence is medium/low or imported lookup fails.
* End-to-end: realistic supplier with full surface.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pytest

from dashboard_pipeline.ai.supplier_brief import (
    ALLOWED_PORTFOLIO_SORT_MODES,
    DEFAULT_BENCHMARK_N,
    DEFAULT_LOOKBACK_MONTHS,
    DEFAULT_PORTFOLIO_SORT_BY,
    DEFAULT_TOP_N,
    MAX_BENCHMARK_N,
    MAX_LOOKBACK_MONTHS,
    MAX_TOP_N,
    MIN_BENCHMARK_N,
    MIN_LOOKBACK_MONTHS,
    MIN_TOP_N,
    _build_leverage_score,
    _build_negotiation_plays,
    _build_payment_profile,
    _build_price_benchmark,
    _build_volume_snapshot,
    _clean_display_name,
    _extract_tax_id,
    _find_aging_entry,
    _find_imported_supplier_entry,
    _hhi_index,
    _hhi_label,
    _label_for_leverage_score,
    _months_between,
    _normalize_name,
    _resolve_benchmark_n,
    _resolve_lookback_months,
    _resolve_portfolio_sort_by,
    _resolve_supplier,
    _resolve_top_n,
    prepare_supplier_brief,
)


TODAY = date(2026, 4, 20)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _loader_for(data: Dict[str, Any]):
    def _load():
        return data

    return _load


def _supplier_row(
    *,
    tax_id: str = "406181616",
    name: str = "ჯიდიაი",
    effective: float = 100000.0,
    paid: float = 80000.0,
    waybills: int = 20,
    scope: str = "strict_bank_only",
) -> Dict[str, Any]:
    debt = max(0.0, effective - paid)
    return {
        "ორგანიზაცია": f"({tax_id}-დღგ) შპს {name}",
        "waybills_count": waybills,
        "total_effective": effective,
        "total_paid": paid,
        "total_debt": debt,
        "strict_bank_paid": paid,
        "manual_paid": 0.0,
        "payment_scope": scope,
        "payment_scope_note": "ბანკის ავტო-დადასტურება",
    }


def _aging_row(
    *,
    tax_id: str = "406181616",
    first: str = "2024-05-01",
    last: str = "2026-04-15",
    bucket: str = "0-30",
    debt: float = 20000.0,
    days: int = 5,
) -> Dict[str, Any]:
    return {
        "tax_id": tax_id,
        "org": "test",
        "first_waybill_date": first,
        "last_waybill_date": last,
        "aging_bucket": bucket,
        "total_debt": debt,
        "days_since_last": days,
    }


def _imported_supplier(
    *,
    tax_id: str = "406181616",
    name: str = "ჯიდიაი",
    products: int = 50,
    months: int = 20,
    date_min: str = "2024-05-01",
    date_max: str = "2026-04-15",
) -> Dict[str, Any]:
    return {
        "supplier": f"შპს {name}",
        "tax_id": tax_id,
        "normalized_supplier": name.lower(),
        "distinct_product_count": products,
        "distinct_month_count": months,
        "distinct_waybill_count": 40,
        "total_quantity": 1000.0,
        "total_amount_ge": 100000.0,
        "date_range": {"min": date_min, "max": date_max},
        "top_products": [],
    }


# ---------------------------------------------------------------------------
# Argument coercion
# ---------------------------------------------------------------------------


class TestArgumentCoercion:
    def test_lookback_default_when_none(self):
        assert _resolve_lookback_months(None) == DEFAULT_LOOKBACK_MONTHS

    def test_lookback_default_when_invalid(self):
        assert _resolve_lookback_months("abc") == DEFAULT_LOOKBACK_MONTHS

    def test_lookback_clamps_below_min(self):
        assert _resolve_lookback_months(0) == MIN_LOOKBACK_MONTHS

    def test_lookback_clamps_above_max(self):
        assert _resolve_lookback_months(100) == MAX_LOOKBACK_MONTHS

    def test_top_n_default(self):
        assert _resolve_top_n(None) == DEFAULT_TOP_N

    def test_top_n_clamps_below_min(self):
        assert _resolve_top_n(0) == MIN_TOP_N

    def test_top_n_clamps_above_max(self):
        assert _resolve_top_n(999) == MAX_TOP_N

    def test_benchmark_n_default(self):
        assert _resolve_benchmark_n(None) == DEFAULT_BENCHMARK_N

    def test_benchmark_n_clamps(self):
        assert _resolve_benchmark_n(0) == MIN_BENCHMARK_N
        assert _resolve_benchmark_n(100) == MAX_BENCHMARK_N


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_extract_tax_id_from_parenthetical(self):
        assert _extract_tax_id("(406181616-დღგ) შპს ჯიდიაი") == "406181616"

    def test_extract_tax_id_returns_empty_for_missing(self):
        assert _extract_tax_id("შპს ცარიელი") == ""

    def test_extract_tax_id_handles_none(self):
        assert _extract_tax_id(None) == ""

    def test_normalize_name_strips_legal_prefix(self):
        assert _normalize_name("შპს  ჯიდიაი") == "ჯიდიაი"
        assert _normalize_name("სს კოკა-კოლა") == "კოკა კოლა"

    def test_normalize_name_strips_tax_parenthetical(self):
        assert _normalize_name("(406181616-დღგ) შპს ჯიდიაი") == "ჯიდიაი"

    def test_normalize_name_empty(self):
        assert _normalize_name(None) == ""
        assert _normalize_name("") == ""

    def test_months_between_inclusive(self):
        assert _months_between(date(2025, 1, 1), date(2025, 1, 31)) == 1
        assert _months_between(date(2025, 1, 1), date(2025, 3, 15)) == 3
        assert _months_between(date(2024, 5, 1), date(2026, 4, 15)) == 24

    def test_months_between_handles_reverse_range(self):
        assert _months_between(date(2026, 1, 1), date(2025, 1, 1)) == 0

    def test_months_between_none(self):
        assert _months_between(None, date(2025, 1, 1)) == 0
        assert _months_between(date(2025, 1, 1), None) == 0

    def test_clean_display_name(self):
        assert _clean_display_name("(406181616-დღგ) შპს ჯიდიაი") == "შპს ჯიდიაი"


# ---------------------------------------------------------------------------
# Supplier resolution
# ---------------------------------------------------------------------------


class TestSupplierResolution:
    def setup_method(self):
        self.suppliers = [
            _supplier_row(tax_id="406181616", name="ჯიდიაი", effective=100_000),
            _supplier_row(tax_id="204920381", name="ელიზი ჯგუფი", effective=80_000),
            _supplier_row(tax_id="405152953", name="კოკა-კოლა გურია", effective=60_000),
        ]

    def test_tax_id_exact_high_confidence(self):
        row, source, conf = _resolve_supplier(
            self.suppliers, tax_id="406181616", supplier_name=None
        )
        assert row is not None
        assert conf == "high"
        assert source == "tax_id_exact"

    def test_tax_id_with_dashes_stripped(self):
        row, source, conf = _resolve_supplier(
            self.suppliers, tax_id="406181616-დღგ", supplier_name=None
        )
        assert row is not None
        assert conf == "high"

    def test_name_exact_high_confidence(self):
        row, source, conf = _resolve_supplier(
            self.suppliers, tax_id=None, supplier_name="შპს ჯიდიაი"
        )
        assert row is not None
        assert conf == "high"
        assert source == "name_exact"

    def test_name_substring_medium_confidence(self):
        # Query is a proper substring of normalized supplier name.
        row, source, conf = _resolve_supplier(
            self.suppliers, tax_id=None, supplier_name="კოკა"
        )
        assert row is not None
        assert conf == "medium"
        assert source == "name_substring"

    def test_name_partial_low_confidence(self):
        # Shared token "ჯგუფი" with "ელიზი ჯგუფი" but not substring.
        row, source, conf = _resolve_supplier(
            self.suppliers, tax_id=None, supplier_name="ჯგუფი კომპანია"
        )
        assert row is not None
        assert conf == "low"
        assert source == "name_partial"

    def test_unknown_supplier_returns_none(self):
        row, _src, _conf = _resolve_supplier(
            self.suppliers, tax_id=None, supplier_name="სრულიად ცრუ მომწოდებელი"
        )
        assert row is None

    def test_tax_id_takes_precedence_over_name(self):
        row, source, _conf = _resolve_supplier(
            self.suppliers, tax_id="204920381", supplier_name="ჯიდიაი"
        )
        assert row is not None
        assert _extract_tax_id(row["ორგანიზაცია"]) == "204920381"
        assert source == "tax_id_exact"

    def test_empty_inputs_return_none(self):
        assert _resolve_supplier(self.suppliers, tax_id=None, supplier_name=None)[0] is None
        assert _resolve_supplier(self.suppliers, tax_id="", supplier_name="")[0] is None


# ---------------------------------------------------------------------------
# Volume snapshot
# ---------------------------------------------------------------------------


class TestVolumeSnapshot:
    def test_uses_imported_date_range_when_available(self):
        supplier = _supplier_row(effective=100_000, waybills=40)
        imported = _imported_supplier(
            date_min="2024-05-01", date_max="2026-04-15"
        )
        aging = _aging_row(first="2020-01-01", last="2020-06-01")
        snap = _build_volume_snapshot(
            supplier, imported, aging,
            total_portfolio_ge=1_000_000, ranking=1,
        )
        # imported dates win over aging
        assert snap["first_waybill_date"] == "2024-05-01"
        assert snap["last_waybill_date"] == "2026-04-15"
        assert snap["tenure_months"] == 24
        assert snap["monthly_avg_ge"] == pytest.approx(100_000 / 24, rel=0.01)

    def test_falls_back_to_aging_when_imported_has_null_dates(self):
        supplier = _supplier_row(effective=120_000)
        imported_null = _imported_supplier(date_min=None, date_max=None)
        aging = _aging_row(first="2024-05-01", last="2026-04-15")
        snap = _build_volume_snapshot(
            supplier, imported_null, aging,
            total_portfolio_ge=1_000_000, ranking=1,
        )
        assert snap["first_waybill_date"] == "2024-05-01"
        assert snap["last_waybill_date"] == "2026-04-15"
        assert snap["tenure_months"] == 24

    def test_no_imported_no_aging_zero_tenure(self):
        supplier = _supplier_row(effective=50_000)
        snap = _build_volume_snapshot(
            supplier, None, None,
            total_portfolio_ge=500_000, ranking=1,
        )
        assert snap["tenure_months"] == 0
        assert snap["monthly_avg_ge"] == 0.0

    def test_portfolio_share_pct(self):
        supplier = _supplier_row(effective=250_000)
        snap = _build_volume_snapshot(
            supplier, None, None,
            total_portfolio_ge=1_000_000, ranking=1,
        )
        assert snap["portfolio_share_pct"] == pytest.approx(25.0, rel=0.01)

    def test_portfolio_share_zero_portfolio(self):
        supplier = _supplier_row(effective=10)
        snap = _build_volume_snapshot(
            supplier, None, None,
            total_portfolio_ge=0, ranking=1,
        )
        assert snap["portfolio_share_pct"] == 0.0


# ---------------------------------------------------------------------------
# Payment profile
# ---------------------------------------------------------------------------


class TestPaymentProfile:
    def test_clean_reliability_when_zero_unpaid(self):
        supplier = _supplier_row(effective=100_000, paid=100_000)
        p = _build_payment_profile(supplier, aging_entry=None)
        assert p["current_debt_ge"] == 0.0
        assert p["unpaid_share_pct"] == 0.0
        assert "clean" in p["reliability_label"].lower()

    def test_mostly_clean_when_small_unpaid(self):
        supplier = _supplier_row(effective=100_000, paid=85_000)
        p = _build_payment_profile(supplier, aging_entry=None)
        assert p["unpaid_share_pct"] == pytest.approx(15.0, rel=0.01)
        assert "mostly" in p["reliability_label"].lower()

    def test_mixed_when_medium_unpaid(self):
        supplier = _supplier_row(effective=100_000, paid=60_000)
        p = _build_payment_profile(supplier, aging_entry=None)
        assert "mixed" in p["reliability_label"].lower()

    def test_behind_when_heavily_unpaid(self):
        supplier = _supplier_row(effective=100_000, paid=30_000)
        p = _build_payment_profile(supplier, aging_entry=None)
        assert "behind" in p["reliability_label"].lower()

    def test_aging_integration(self):
        supplier = _supplier_row(effective=100_000, paid=50_000)
        aging = _aging_row(bucket="91-120", days=100)
        p = _build_payment_profile(supplier, aging_entry=aging)
        assert p["days_since_last_activity"] == 100
        assert p["aging_bucket"] == "91-120"

    def test_handles_negative_debt_gracefully(self):
        # Overpayment scenario — unpaid_share should floor at 0%.
        supplier = _supplier_row(effective=100_000, paid=120_000)
        supplier["total_debt"] = -20_000
        p = _build_payment_profile(supplier, aging_entry=None)
        assert p["unpaid_share_pct"] == 0.0


# ---------------------------------------------------------------------------
# Price benchmark
# ---------------------------------------------------------------------------


def _make_product(
    *,
    code: str,
    name: str,
    suppliers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "product_code": code,
        "product_name": name,
        "unit": "ცალი",
        "row_count": sum(int(s.get("row_count", 1)) for s in suppliers),
        "distinct_supplier_count": len(suppliers),
        "distinct_waybill_count": 10,
        "total_quantity": sum(float(s.get("total_quantity", 0)) for s in suppliers),
        "total_amount_ge": sum(float(s.get("total_amount_ge", 0)) for s in suppliers),
        "top_suppliers": suppliers,
    }


class TestPriceBenchmark:
    def test_detects_dual_source_and_gap(self):
        products = [
            _make_product(
                code="SKU-1", name="Cola 2L",
                suppliers=[
                    {"supplier": "შპს ჯიდიაი", "tax_id": "406181616", "total_quantity": 100, "total_amount_ge": 400},
                    {"supplier": "შპს X", "tax_id": "999999999", "total_quantity": 50, "total_amount_ge": 180},
                ],
            )
        ]
        rows, summary = _build_price_benchmark(
            products, focus_tax_id="406181616", focus_name_normalized="ჯიდიაი",
            benchmark_n=10,
        )
        assert len(rows) == 1
        assert summary["products_with_dual_source"] == 1
        assert summary["products_where_i_am_most_expensive"] == 1
        # my_up = 4.0, alt_up = 3.6 → gap +11%
        assert rows[0]["my_avg_unit_price_ge"] == pytest.approx(4.0)
        assert rows[0]["cheapest_alternative"]["unit_price_ge"] == pytest.approx(3.6)
        assert rows[0]["gap_pct_vs_cheapest"] == pytest.approx(11.11, rel=0.01)
        assert rows[0]["quality_flag"] == "comparable"

    def test_single_source_excluded(self):
        products = [
            _make_product(
                code="SKU-1", name="Solo",
                suppliers=[
                    {"supplier": "შპს ჯიდიაი", "tax_id": "406181616", "total_quantity": 100, "total_amount_ge": 400},
                ],
            )
        ]
        rows, summary = _build_price_benchmark(
            products, focus_tax_id="406181616", focus_name_normalized="ჯიდიაი",
            benchmark_n=10,
        )
        assert len(rows) == 0
        assert summary["products_with_dual_source"] == 0

    def test_low_quantity_flag(self):
        products = [
            _make_product(
                code="SKU-1", name="Tiny",
                suppliers=[
                    {"supplier": "შპს ჯიდიაი", "tax_id": "406181616", "total_quantity": 2, "total_amount_ge": 10},
                    {"supplier": "შპს X", "tax_id": "999999999", "total_quantity": 1, "total_amount_ge": 3},
                ],
            )
        ]
        rows, _summary = _build_price_benchmark(
            products, focus_tax_id="406181616", focus_name_normalized="ჯიდიაი",
            benchmark_n=10,
        )
        assert len(rows) == 1
        assert rows[0]["quality_flag"] == "low_quantity"

    def test_cheaper_me_counted(self):
        products = [
            _make_product(
                code="SKU-1", name="Product",
                suppliers=[
                    {"supplier": "შპს ჯიდიაი", "tax_id": "406181616", "total_quantity": 100, "total_amount_ge": 300},
                    {"supplier": "შპს X", "tax_id": "999999999", "total_quantity": 50, "total_amount_ge": 200},
                ],
            )
        ]
        _rows, summary = _build_price_benchmark(
            products, focus_tax_id="406181616", focus_name_normalized="ჯიდიაი",
            benchmark_n=10,
        )
        # me = 3.0, alt = 4.0 → I'm cheaper
        assert summary["products_where_i_am_cheapest"] == 1
        assert summary["products_where_i_am_most_expensive"] == 0

    def test_benchmark_n_limits_rows(self):
        products = [
            _make_product(
                code=f"SKU-{i}", name=f"Prod{i}",
                suppliers=[
                    {"supplier": "ჯიდიაი", "tax_id": "406181616", "total_quantity": 100, "total_amount_ge": 400 + i},
                    {"supplier": "X", "tax_id": "99", "total_quantity": 100, "total_amount_ge": 300},
                ],
            )
            for i in range(5)
        ]
        rows, _summary = _build_price_benchmark(
            products, focus_tax_id="406181616", focus_name_normalized="ჯიდიაი",
            benchmark_n=3,
        )
        assert len(rows) == 3

    def test_savings_estimate_uses_only_comparable_rows(self):
        products = [
            _make_product(
                code="SKU-big", name="Comparable",
                suppliers=[
                    {"supplier": "ჯიდიაი", "tax_id": "406181616", "total_quantity": 100, "total_amount_ge": 1100},
                    {"supplier": "X", "tax_id": "99", "total_quantity": 100, "total_amount_ge": 1000},
                ],
            ),
            _make_product(
                code="SKU-tiny", name="LowQty",
                suppliers=[
                    {"supplier": "ჯიდიაი", "tax_id": "406181616", "total_quantity": 2, "total_amount_ge": 100},
                    {"supplier": "X", "tax_id": "99", "total_quantity": 2, "total_amount_ge": 50},
                ],
            ),
        ]
        _rows, summary = _build_price_benchmark(
            products, focus_tax_id="406181616", focus_name_normalized="ჯიდიაი",
            benchmark_n=10,
        )
        # only the comparable row counts in savings: 1100 × 10% ≈ 110
        assert summary["estimated_annual_savings_if_switch_cheapest_ge"] == pytest.approx(110, rel=0.01)


# ---------------------------------------------------------------------------
# Leverage score
# ---------------------------------------------------------------------------


class TestLeverageScore:
    def _volume(self, **kw):
        base = {
            "total_spend_ge": 100000.0,
            "portfolio_share_pct": 10.0,
            "tenure_months": 12,
        }
        base.update(kw)
        return base

    def _payment(self, **kw):
        base = {
            "unpaid_share_pct": 20.0,
            "days_since_last_activity": 10,
        }
        base.update(kw)
        return base

    def _bench(self, **kw):
        base = {
            "products_with_dual_source": 5,
            "products_where_i_am_most_expensive": 3,
        }
        base.update(kw)
        return base

    def test_score_saturates_high_leverage(self):
        score = _build_leverage_score(
            self._volume(portfolio_share_pct=30, tenure_months=30),
            self._payment(unpaid_share_pct=50, days_since_last_activity=3),
            self._bench(products_with_dual_source=25, products_where_i_am_most_expensive=20),
        )
        assert score["score"] >= 90
        assert score["label"] == "🟢 HIGH"

    def test_score_zero_floor(self):
        score = _build_leverage_score(
            self._volume(portfolio_share_pct=0, tenure_months=0),
            self._payment(unpaid_share_pct=0, days_since_last_activity=None),
            self._bench(products_with_dual_source=0, products_where_i_am_most_expensive=0),
        )
        assert score["score"] == 0
        assert score["label"] == "🟠 LOW"

    def test_label_thresholds(self):
        assert _label_for_leverage_score(100) == "🟢 HIGH"
        assert _label_for_leverage_score(70) == "🟢 HIGH"
        assert _label_for_leverage_score(69) == "🟡 MEDIUM"
        assert _label_for_leverage_score(40) == "🟡 MEDIUM"
        assert _label_for_leverage_score(39) == "🟠 LOW"
        assert _label_for_leverage_score(0) == "🟠 LOW"

    def test_components_sum_equals_total(self):
        score = _build_leverage_score(
            self._volume(), self._payment(), self._bench()
        )
        assert score["score"] == sum(c["score"] for c in score["components"])

    def test_all_components_present(self):
        score = _build_leverage_score(
            self._volume(), self._payment(), self._bench()
        )
        factors = {c["factor"] for c in score["components"]}
        assert factors == {
            "portfolio_share",
            "payment_leverage",
            "dual_sourcing",
            "tenure",
            "relationship_health",
        }


# ---------------------------------------------------------------------------
# Negotiation plays
# ---------------------------------------------------------------------------


class TestNegotiationPlays:
    def test_cash_discount_play_fires_when_debt_and_unpaid(self):
        plays = _build_negotiation_plays(
            volume={"monthly_avg_ge": 10000, "portfolio_share_pct": 2},
            payment={"current_debt_ge": 50000, "unpaid_share_pct": 25},
            benchmark_summary={
                "products_with_dual_source": 0,
                "products_where_i_am_most_expensive": 0,
                "estimated_annual_savings_if_switch_cheapest_ge": 0,
            },
            benchmark_rows=[],
        )
        types = [p["type"] for p in plays]
        assert "cash_discount_for_payment_speed" in types

    def test_cash_discount_play_suppressed_when_no_debt(self):
        plays = _build_negotiation_plays(
            volume={"monthly_avg_ge": 10000, "portfolio_share_pct": 2},
            payment={"current_debt_ge": 0, "unpaid_share_pct": 0},
            benchmark_summary={
                "products_with_dual_source": 0,
                "products_where_i_am_most_expensive": 0,
                "estimated_annual_savings_if_switch_cheapest_ge": 0,
            },
            benchmark_rows=[],
        )
        assert all(p["type"] != "cash_discount_for_payment_speed" for p in plays)

    def test_volume_play_fires_on_large_share(self):
        plays = _build_negotiation_plays(
            volume={"monthly_avg_ge": 50000, "portfolio_share_pct": 10},
            payment={"current_debt_ge": 0, "unpaid_share_pct": 0},
            benchmark_summary={
                "products_with_dual_source": 0,
                "products_where_i_am_most_expensive": 0,
                "estimated_annual_savings_if_switch_cheapest_ge": 0,
            },
            benchmark_rows=[],
        )
        assert any(p["type"] == "volume_commitment_discount" for p in plays)

    def test_dual_source_play_requires_benchmark_row(self):
        bench_row = {
            "product_name": "Prod",
            "gap_pct_vs_cheapest": 10.0,
            "quality_flag": "comparable",
            "cheapest_alternative": {"supplier": "ALT", "unit_price_ge": 5.0},
        }
        plays = _build_negotiation_plays(
            volume={"monthly_avg_ge": 1000, "portfolio_share_pct": 1},
            payment={"current_debt_ge": 0, "unpaid_share_pct": 0},
            benchmark_summary={
                "products_with_dual_source": 3,
                "products_where_i_am_most_expensive": 2,
                "estimated_annual_savings_if_switch_cheapest_ge": 5000,
            },
            benchmark_rows=[bench_row],
        )
        dual = [p for p in plays if p["type"] == "dual_source_leverage"]
        assert len(dual) == 1
        assert dual[0]["confidence"] == "🟠 use_only_if_stalled"
        assert dual[0]["warning_ka"] is not None

    def test_ranks_are_sequential(self):
        plays = _build_negotiation_plays(
            volume={"monthly_avg_ge": 50000, "portfolio_share_pct": 10},
            payment={"current_debt_ge": 50000, "unpaid_share_pct": 25},
            benchmark_summary={
                "products_with_dual_source": 3,
                "products_where_i_am_most_expensive": 2,
                "estimated_annual_savings_if_switch_cheapest_ge": 5000,
            },
            benchmark_rows=[
                {
                    "product_name": "P",
                    "gap_pct_vs_cheapest": 10,
                    "quality_flag": "comparable",
                    "cheapest_alternative": {"supplier": "ALT", "unit_price_ge": 5.0},
                },
            ],
        )
        assert [p["rank"] for p in plays] == list(range(1, len(plays) + 1))

    def test_all_plays_have_evidence_refs(self):
        plays = _build_negotiation_plays(
            volume={"monthly_avg_ge": 50000, "portfolio_share_pct": 10},
            payment={"current_debt_ge": 50000, "unpaid_share_pct": 25},
            benchmark_summary={
                "products_with_dual_source": 3,
                "products_where_i_am_most_expensive": 2,
                "estimated_annual_savings_if_switch_cheapest_ge": 5000,
            },
            benchmark_rows=[
                {
                    "product_name": "P",
                    "gap_pct_vs_cheapest": 10,
                    "quality_flag": "comparable",
                    "cheapest_alternative": {"supplier": "ALT", "unit_price_ge": 5.0},
                },
            ],
        )
        for p in plays:
            assert isinstance(p.get("evidence_refs"), list)
            assert p["evidence_refs"], f"play {p['type']} has no evidence"


# ---------------------------------------------------------------------------
# Portfolio mode + HHI
# ---------------------------------------------------------------------------


class TestPortfolio:
    def test_hhi_low_label(self):
        # 20 suppliers each at 5% → HHI = 20 * 25 = 500
        assert _hhi_index([5.0] * 20) == pytest.approx(500.0)
        assert _hhi_label(500.0) == "moderate"

    def test_hhi_high_label(self):
        # 1 supplier at 100% → HHI = 10000
        assert _hhi_index([100.0]) == pytest.approx(10000.0)
        assert _hhi_label(10000.0) == "extreme"

    def test_hhi_label_bands(self):
        assert _hhi_label(2500) == "extreme"
        assert _hhi_label(1500) == "high"
        assert _hhi_label(500) == "moderate"
        assert _hhi_label(0) == "low"

    def test_portfolio_mode_with_real_looking_data(self):
        suppliers = [
            _supplier_row(tax_id="111111111", name="A", effective=500_000, paid=450_000),
            _supplier_row(tax_id="222222222", name="B", effective=300_000, paid=300_000),
            _supplier_row(tax_id="333333333", name="C", effective=100_000, paid=80_000),
        ]
        aging = [
            _aging_row(tax_id="111111111", first="2024-01-01", last="2026-04-01"),
            _aging_row(tax_id="222222222", first="2024-06-01", last="2026-04-10"),
        ]
        r = prepare_supplier_brief(
            _loader_for({
                "suppliers": suppliers,
                "imported_products": {"suppliers": [], "products": []},
                "supplier_aging": aging,
            }),
            today=TODAY,
        )
        assert r["mode"] == "portfolio"
        assert r["total_suppliers"] == 3
        assert r["total_spend_ge"] == pytest.approx(900_000, rel=0.01)
        assert r["concentration"]["top_5_share_pct"] == pytest.approx(100.0, rel=0.01)
        assert len(r["top_candidates"]) <= 10


# ---------------------------------------------------------------------------
# Phase 2.4 REDUCED — portfolio sort_by + payment-risk enrichment
# ---------------------------------------------------------------------------


class TestPortfolioSortBy:
    """Phase 2.4 REDUCED: sort_by="leverage"|"risk" + payment fields on candidates.

    Supersedes the scrapped `supplier_risk_radar` tool; risk-sort mode ranks
    by unpaid_share_pct DESC → current_debt_ge DESC → total_spend_ge DESC.
    Payment fields are surfaced on every candidate regardless of sort mode.
    """

    def _payload(self) -> Dict[str, Any]:
        # A: high spend, mostly paid (low risk).
        # B: medium spend, half unpaid (moderate risk).
        # C: small spend, fully unpaid (highest risk by share).
        suppliers = [
            _supplier_row(tax_id="111111111", name="A", effective=500_000, paid=490_000),
            _supplier_row(tax_id="222222222", name="B", effective=200_000, paid=100_000),
            _supplier_row(tax_id="333333333", name="C", effective=50_000, paid=0),
        ]
        aging = [
            _aging_row(tax_id="111111111", first="2024-01-01", last="2026-04-01"),
            _aging_row(tax_id="222222222", first="2024-06-01", last="2026-04-10"),
            _aging_row(tax_id="333333333", first="2024-06-01", last="2026-04-10"),
        ]
        return {
            "suppliers": suppliers,
            "imported_products": {"suppliers": [], "products": []},
            "supplier_aging": aging,
        }

    def test_resolve_sort_by_defaults_to_leverage(self):
        assert _resolve_portfolio_sort_by(None) == DEFAULT_PORTFOLIO_SORT_BY
        assert _resolve_portfolio_sort_by(None) == "leverage"

    def test_resolve_sort_by_accepts_known_modes(self):
        for mode in ALLOWED_PORTFOLIO_SORT_MODES:
            assert _resolve_portfolio_sort_by(mode) == mode
            assert _resolve_portfolio_sort_by(mode.upper()) == mode

    def test_resolve_sort_by_falls_back_on_unknown(self):
        assert _resolve_portfolio_sort_by("bogus") == DEFAULT_PORTFOLIO_SORT_BY
        assert _resolve_portfolio_sort_by("") == DEFAULT_PORTFOLIO_SORT_BY
        assert _resolve_portfolio_sort_by(123) == DEFAULT_PORTFOLIO_SORT_BY

    def test_default_portfolio_has_sort_mode_leverage(self):
        r = prepare_supplier_brief(_loader_for(self._payload()), today=TODAY)
        assert r["mode"] == "portfolio"
        assert r["sort_mode"] == "leverage"

    def test_top_candidates_include_payment_fields_in_leverage_mode(self):
        r = prepare_supplier_brief(_loader_for(self._payload()), today=TODAY)
        assert r["top_candidates"], "expected at least one candidate"
        for candidate in r["top_candidates"]:
            assert "current_debt_ge" in candidate
            assert "unpaid_share_pct" in candidate
            assert "reliability_label" in candidate
            assert "aging_bucket" in candidate

    def test_sort_by_risk_ranks_highest_unpaid_share_first(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()), sort_by="risk", today=TODAY,
        )
        assert r["sort_mode"] == "risk"
        candidates = r["top_candidates"]
        assert candidates
        # C has 100% unpaid, B has 50%, A has 2% — risk sort should put C first.
        assert candidates[0]["supplier_name"].endswith("C")
        assert candidates[0]["unpaid_share_pct"] == pytest.approx(100.0, rel=0.01)
        # Monotonic non-increasing by unpaid_share_pct.
        shares = [float(c["unpaid_share_pct"]) for c in candidates]
        assert shares == sorted(shares, reverse=True)

    def test_sort_by_invalid_value_falls_back_to_leverage(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()), sort_by="bogus_mode", today=TODAY,
        )
        assert r["sort_mode"] == "leverage"

    def test_sort_by_risk_summary_ka_surfaces_risk_headline(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()), sort_by="risk", today=TODAY,
        )
        summary = r.get("summary_ka") or ""
        # Risk mode summary should mention "risk" in the #1 slot and debt-at-risk aggregate.
        assert "#1 risk:" in summary
        assert "debt-at-risk" in summary

    def test_sort_by_leverage_summary_ka_unchanged(self):
        r = prepare_supplier_brief(_loader_for(self._payload()), today=TODAY)
        summary = r.get("summary_ka") or ""
        # Backward-compat: leverage summary keeps "#1 call:" phrasing.
        assert "#1 call:" in summary
        assert "#1 risk:" not in summary

    def test_ranking_note_reflects_sort_mode(self):
        r_lev = prepare_supplier_brief(_loader_for(self._payload()), today=TODAY)
        r_risk = prepare_supplier_brief(
            _loader_for(self._payload()), sort_by="risk", today=TODAY,
        )
        assert any("leverage_score" in n for n in r_lev["notes"])
        assert any("payment-risk" in n for n in r_risk["notes"])


# ---------------------------------------------------------------------------
# End-to-end focused mode
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def _payload(self):
        suppliers = [
            _supplier_row(tax_id="406181616", name="ჯიდიაი", effective=900_000, paid=600_000, waybills=600),
            _supplier_row(tax_id="204920381", name="ელიზი ჯგუფი", effective=500_000, paid=500_000, waybills=300),
        ]
        imported = {
            "suppliers": [
                _imported_supplier(
                    tax_id="406181616", name="ჯიდიაი",
                    date_min="2024-05-01", date_max="2026-04-15",
                ),
            ],
            "products": [
                _make_product(
                    code="SKU-1", name="Cola 2L",
                    suppliers=[
                        {"supplier": "შპს ჯიდიაი", "tax_id": "406181616", "total_quantity": 100, "total_amount_ge": 400},
                        {"supplier": "შპს X", "tax_id": "999999999", "total_quantity": 80, "total_amount_ge": 300},
                    ],
                ),
            ],
        }
        aging = [
            _aging_row(tax_id="406181616", first="2024-05-01", last="2026-04-15"),
        ]
        return {
            "suppliers": suppliers,
            "imported_products": imported,
            "supplier_aging": aging,
        }

    def test_focused_brief_has_all_sections(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()), tax_id="406181616", today=TODAY,
        )
        assert r["mode"] == "focused"
        assert r["supplier"]["tax_id"] == "406181616"
        assert r["supplier"]["match_confidence"] == "high"
        assert r["supplier"]["ranking_among_suppliers"] == 1
        assert r["volume_snapshot"]["tenure_months"] > 0
        assert r["payment_profile"]["current_debt_ge"] > 0
        assert isinstance(r["price_benchmark"], list)
        assert r["leverage_score"]["score"] > 0
        assert isinstance(r["negotiation_plays"], list)
        assert len(r["negotiation_plays"]) >= 1

    def test_focused_plays_include_cash_discount_when_debt(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()), tax_id="406181616", today=TODAY,
        )
        types = [p["type"] for p in r["negotiation_plays"]]
        assert "cash_discount_for_payment_speed" in types

    def test_focused_medium_confidence_yields_warning(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()),
            supplier_name="ჯგუფი",  # substring of ელიზი ჯგუფი
            today=TODAY,
        )
        assert r["mode"] == "focused"
        assert r["supplier"]["match_confidence"] == "medium"
        assert len(r["matching_warnings"]) >= 1

    def test_unknown_supplier_returns_error(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()),
            supplier_name="უცნობი XYZ ცრუ",
            today=TODAY,
        )
        assert "error" in r

    def test_empty_suppliers_returns_error(self):
        r = prepare_supplier_brief(
            _loader_for({"suppliers": [], "imported_products": {}, "supplier_aging": []}),
            tax_id="406181616",
            today=TODAY,
        )
        assert "error" in r

    def test_no_identifier_goes_to_portfolio_mode(self):
        r = prepare_supplier_brief(
            _loader_for(self._payload()),
            today=TODAY,
        )
        assert r["mode"] == "portfolio"

    def test_loader_raising_returns_error(self):
        def bad_loader():
            raise RuntimeError("data corrupted")

        r = prepare_supplier_brief(bad_loader, tax_id="123", today=TODAY)
        assert "error" in r


# ---------------------------------------------------------------------------
# Matching warnings
# ---------------------------------------------------------------------------


class TestMatchingWarnings:
    def test_warning_when_confidence_medium(self):
        suppliers = [_supplier_row(tax_id="406181616", name="ჯიდიაი დისტრიბუცია")]
        r = prepare_supplier_brief(
            _loader_for({
                "suppliers": suppliers,
                "imported_products": {"suppliers": [], "products": []},
                "supplier_aging": [],
            }),
            supplier_name="ჯიდიაი",  # substring match only
            today=TODAY,
        )
        assert r["mode"] == "focused"
        assert r["supplier"]["match_confidence"] == "medium"
        assert len(r["matching_warnings"]) >= 1

    def test_warning_when_imported_missing(self):
        suppliers = [_supplier_row(tax_id="406181616", name="ჯიდიაი")]
        r = prepare_supplier_brief(
            _loader_for({
                "suppliers": suppliers,
                "imported_products": {"suppliers": [], "products": []},
                "supplier_aging": [],
            }),
            tax_id="406181616",
            today=TODAY,
        )
        # imported_products.suppliers empty → warning mentions imported lookup
        assert any("imported" in w.lower() for w in r["matching_warnings"])

    def test_no_warning_when_all_green(self):
        suppliers = [_supplier_row(tax_id="406181616", name="ჯიდიაი")]
        imported = {
            "suppliers": [_imported_supplier(tax_id="406181616", name="ჯიდიაი")],
            "products": [],
        }
        r = prepare_supplier_brief(
            _loader_for({
                "suppliers": suppliers,
                "imported_products": imported,
                "supplier_aging": [],
            }),
            tax_id="406181616",
            today=TODAY,
        )
        assert r["supplier"]["match_confidence"] == "high"
        # No medium/low confidence warning, imported found
        assert len(r["matching_warnings"]) == 0


# ---------------------------------------------------------------------------
# _find_imported_supplier_entry + _find_aging_entry
# ---------------------------------------------------------------------------


class TestEntryLookups:
    def test_find_imported_by_tax_id(self):
        imported = [_imported_supplier(tax_id="111111111", name="A")]
        assert _find_imported_supplier_entry(
            imported, tax_id="111111111", resolved_name=""
        ) is not None

    def test_find_imported_by_normalized_name_fallback(self):
        imported = [
            {"supplier": "შპს ჯიდიაი", "tax_id": None, "normalized_supplier": "ჯიდიაი"},
        ]
        assert _find_imported_supplier_entry(
            imported, tax_id="", resolved_name="(406181616-დღგ) შპს ჯიდიაი"
        ) is not None

    def test_find_imported_missing_returns_none(self):
        assert _find_imported_supplier_entry(
            [], tax_id="123", resolved_name="Unknown"
        ) is None

    def test_find_aging_by_tax_id(self):
        aging = [_aging_row(tax_id="111111111")]
        row = _find_aging_entry(aging, tax_id="111111111")
        assert row is not None
        assert row["tax_id"] == "111111111"

    def test_find_aging_missing_returns_none(self):
        assert _find_aging_entry([], tax_id="123") is None


# ---------------------------------------------------------------------------
# Tool surface pin (14 → 15 with Phase 2.12 addition)
# ---------------------------------------------------------------------------


class TestToolSurface:
    def test_prepare_supplier_brief_is_registered(self):
        from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

        names = [s["name"] for s in TOOL_SCHEMAS]
        assert "prepare_supplier_brief" in names
        assert len(TOOL_SCHEMAS) == 26  # Phase 5.1 added 3 VAT tools

    def test_tool_schema_has_required_properties(self):
        from dashboard_pipeline.ai.tools import PREPARE_SUPPLIER_BRIEF_TOOL

        props = PREPARE_SUPPLIER_BRIEF_TOOL["input_schema"]["properties"]
        assert "supplier_name" in props
        assert "tax_id" in props
        assert "lookback_months" in props
        assert "top_n" in props
        assert "benchmark_n" in props
