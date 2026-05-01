"""Tests for dashboard_pipeline/category_anomalies.py."""
from __future__ import annotations

import pytest

from dashboard_pipeline.category_anomalies import (
    PROTECTED_TAX_IDS,
    STORE_ID_TO_NAME,
    _build_duplicate_clusters,
    _store_name,
    build_anomaly_bundle,
    normalize_category,
)


# ────────────────────────── normalize_category ────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("შოკოლადის ფილა", "შოკოლადის ფილა"),
        ("1406 | შოკოლადის ფილა", "შოკოლადის ფილა"),
        ("0103 | კონიაკი, ბრენდი", "კონიაკი, ბრენდი"),
        ("07031 | ელემენტები", "ელემენტები"),
        ("1999.1 | სხვა მარკეტინგული საქონელი ", "სხვა მარკეტინგული საქონელი"),
        ("0907 |  ცივი ყავა", "ცივი ყავა"),  # double space inside collapses
        ("  გაყინული ბოსტნეული  ", "გაყინული ბოსტნეული"),  # outer whitespace
        ("ABC", "abc"),  # lowercase
    ],
)
def test_normalize_strips_prefix_whitespace_lowercase(raw: str, expected: str) -> None:
    assert normalize_category(raw) == expected


@pytest.mark.parametrize("falsy", [None, "", "  ", "\t"])
def test_normalize_falsy_input_returns_empty(falsy) -> None:
    assert normalize_category(falsy) == ""


def test_normalize_no_prefix_unchanged_except_case() -> None:
    assert normalize_category("ჩიფსი") == "ჩიფსი"


def test_normalize_does_not_strip_word_starting_with_digits() -> None:
    """`5kg ჩიფსი` should stay — only `<digits> | ` prefixes get stripped."""
    assert normalize_category("5kg ჩიფსი") == "5kg ჩიფსი"


# ────────────────────────── _build_duplicate_clusters ──────────────────────


def test_cluster_skips_singletons() -> None:
    raw_pairs = [("ჩიფსი", 100), ("ნაყინი", 50)]
    clusters = _build_duplicate_clusters(raw_pairs, minority_products=[])
    assert clusters == []


def test_cluster_groups_prefix_variants() -> None:
    raw_pairs = [
        ("ჩიფსი", 527),
        ("2205 | ჩიფსი", 33),
        ("ნაყინი", 200),
    ]
    clusters = _build_duplicate_clusters(raw_pairs, minority_products=[])
    assert len(clusters) == 1
    c = clusters[0]
    assert c["normalized_name"] == "ჩიფსი"
    assert c["majority_variant"] == {"raw_category": "ჩიფსი", "product_count": 527}
    assert c["minority_variants"] == [
        {"raw_category": "2205 | ჩიფსი", "product_count": 33}
    ]


def test_cluster_three_way_majority_picked_correctly() -> None:
    raw_pairs = [
        ("ბისკვიტი", 100),
        ("0615 | ბისკვიტი", 30),
        ("0615  |  ბისკვიტი", 5),  # extra spaces
    ]
    clusters = _build_duplicate_clusters(raw_pairs, minority_products=[])
    assert len(clusters) == 1
    c = clusters[0]
    assert c["majority_variant"]["raw_category"] == "ბისკვიტი"
    assert {v["raw_category"] for v in c["minority_variants"]} == {
        "0615 | ბისკვიტი", "0615  |  ბისკვიტი"
    }


def test_cluster_attaches_minority_products() -> None:
    raw_pairs = [
        ("ჩიფსი", 100),
        ("2205 | ჩიფსი", 5),
    ]
    minority_products = [
        {"product_id": 1, "current_category": "2205 | ჩიფსი", "product_name": "P1",
         "code": "c1", "barcode": "b1", "supplier_name": "", "supplier_tax_id": ""},
        {"product_id": 2, "current_category": "2205 | ჩიფსი", "product_name": "P2",
         "code": "c2", "barcode": "b2", "supplier_name": "", "supplier_tax_id": ""},
        {"product_id": 999, "current_category": "ჩიფსი", "product_name": "P-majority",
         "code": "c9", "barcode": "b9", "supplier_name": "", "supplier_tax_id": ""},
    ]
    clusters = _build_duplicate_clusters(raw_pairs, minority_products=minority_products)
    c = clusters[0]
    # Only minority-variant products attach — majority products excluded.
    attached_ids = {p["product_id"] for p in c["minority_products"]}
    assert attached_ids == {1, 2}


def test_cluster_sorted_by_total_minority_count() -> None:
    raw_pairs = [
        ("A", 100),
        ("0001 | A", 5),    # cluster total minority = 5
        ("B", 50),
        ("0002 | B", 30),   # cluster total minority = 30
    ]
    clusters = _build_duplicate_clusters(raw_pairs, minority_products=[])
    assert [c["normalized_name"] for c in clusters] == ["b", "a"]


# ────────────────────────── _store_name ────────────────────────────────────


def test_store_name_known() -> None:
    assert _store_name("1329") == "დვაბზუ"
    assert _store_name("1301") == "ოზურგეთი"


def test_store_name_unknown_falls_back() -> None:
    assert _store_name("9999") == "store_9999"


# ────────────────────────── build_anomaly_bundle (SQL via mock cursor) ─────


class MockCursor:
    """Minimal pyodbc-cursor stand-in that returns scripted result sets per
    SQL fragment. Each `execute` call advances `_step`; subsequent `fetchall`
    returns the rows pre-loaded for that step.
    """

    def __init__(self, scripts: list[list[tuple]]) -> None:
        self._scripts = scripts
        self._step = -1

    def execute(self, sql: str, *params) -> None:
        self._step += 1

    def fetchall(self) -> list[tuple]:
        return self._scripts[self._step]


def test_build_anomaly_bundle_assembles_summary_and_keys() -> None:
    # Step 0: empty_category → 1 product
    # Step 1: distinct categories → ჩიფსი 50, 2205|ჩიფსი 5
    # Step 2: minority products → 1 product in '2205 | ჩიფსი'
    # Step 3: protected supplier overview → ELIZI 100% სიგარეტი
    scripts = [
        [(42, "code42", "barcode42", "Empty Product", "Sup", "111111111")],
        [("ჩიფსი", 50), ("2205 | ჩიფსი", 5)],
        [(7, "code7", "barcode7", "P", "2205 | ჩიფსი", "Sup", "111111111")],
        [("204920381", "ელიზი ჯგუფი შპს", "სიგარეტი", 134)],
    ]
    cur = MockCursor(scripts)
    bundle = build_anomaly_bundle(cur, "1329")

    assert bundle["store_id"] == "1329"
    assert bundle["store_name"] == "დვაბზუ"

    s = bundle["summary"]
    assert s["empty_category_count"] == 1
    assert s["duplicate_cluster_count"] == 1
    assert s["duplicate_minority_product_count"] == 5
    assert s["protected_supplier_distinct_categories"] == 1

    assert len(bundle["empty_category_products"]) == 1
    assert bundle["empty_category_products"][0]["product_id"] == 42

    cluster = bundle["duplicate_clusters"][0]
    assert cluster["normalized_name"] == "ჩიფსი"
    assert cluster["majority_variant"]["product_count"] == 50
    assert len(cluster["minority_products"]) == 1

    protected = bundle["protected_supplier_overview"][0]
    assert protected["supplier_label"] == "ELIZI"
    assert protected["categories"] == [{"raw_category": "სიგარეტი", "product_count": 134}]


def test_protected_tax_ids_constant_lists_known_cigarette_importers() -> None:
    """Sanity check — drift detector. If this list changes, supplier_profitability
    PROTECTED rule + this anomaly module must move together."""
    assert set(PROTECTED_TAX_IDS) == {"204920381", "406181616", "420424393"}


def test_store_id_to_name_constant_covers_active_stores() -> None:
    assert "1329" in STORE_ID_TO_NAME
    assert "1301" in STORE_ID_TO_NAME
