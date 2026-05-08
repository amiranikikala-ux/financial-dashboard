"""Tests for excluded_from_analysis pipeline application + supplier_archive
schema v2 (archived AND excluded flags can coexist independently)."""
import json
from pathlib import Path

import pytest

from dashboard_pipeline import supplier_archive
from dashboard_pipeline.excluded_from_analysis import apply_excluded_from_analysis


# -- supplier_archive.set_status — schema v2 ----------------------------------


def test_set_archived_only(tmp_path):
    supplier_archive.set_status(
        tax_id="111111111",
        archived=True,
        financial_analysis_dir=tmp_path,
    )
    cache = supplier_archive.load(financial_analysis_dir=tmp_path)
    assert "111111111" in cache
    assert cache["111111111"]["archived_at"]
    assert not cache["111111111"].get("excluded_from_analysis")


def test_set_excluded_only_keeps_entry_without_archive(tmp_path):
    supplier_archive.set_status(
        tax_id="222222222",
        excluded_from_analysis=True,
        exclusion_reason="ზედნადებები გასაუქმებელია",
        financial_analysis_dir=tmp_path,
    )
    cache = supplier_archive.load(financial_analysis_dir=tmp_path)
    assert "222222222" in cache
    assert not cache["222222222"].get("archived_at")
    assert cache["222222222"]["excluded_from_analysis"] is True
    assert cache["222222222"]["exclusion_reason"] == "ზედნადებები გასაუქმებელია"
    assert cache["222222222"]["excluded_at"]


def test_archived_and_excluded_coexist(tmp_path):
    supplier_archive.set_status(
        tax_id="333333333",
        archived=True,
        financial_analysis_dir=tmp_path,
    )
    supplier_archive.set_status(
        tax_id="333333333",
        excluded_from_analysis=True,
        exclusion_reason="test reason",
        financial_analysis_dir=tmp_path,
    )
    cache = supplier_archive.load(financial_analysis_dir=tmp_path)
    entry = cache["333333333"]
    assert entry["archived_at"]
    assert entry["excluded_from_analysis"] is True
    assert entry["exclusion_reason"] == "test reason"


def test_remove_both_flags_drops_entry(tmp_path):
    supplier_archive.set_status(
        tax_id="444444444",
        archived=True,
        excluded_from_analysis=True,
        exclusion_reason="r",
        financial_analysis_dir=tmp_path,
    )
    supplier_archive.set_status(
        tax_id="444444444",
        archived=False,
        excluded_from_analysis=False,
        financial_analysis_dir=tmp_path,
    )
    cache = supplier_archive.load(financial_analysis_dir=tmp_path)
    assert "444444444" not in cache


def test_excluded_entries_filters_correctly(tmp_path):
    supplier_archive.set_status(
        tax_id="555000001",
        archived=True,
        financial_analysis_dir=tmp_path,
    )
    supplier_archive.set_status(
        tax_id="555000002",
        excluded_from_analysis=True,
        exclusion_reason="r",
        financial_analysis_dir=tmp_path,
    )
    excluded = supplier_archive.excluded_entries(financial_analysis_dir=tmp_path)
    assert "555000001" not in excluded
    assert "555000002" in excluded


def test_v1_legacy_data_still_loads(tmp_path):
    """Old v1 schema {archived: {tid: {archived_at, note}}} stays compatible."""
    path = tmp_path / "supplier_archive.json"
    path.write_text(
        json.dumps({
            "version": 1,
            "archived": {
                "666666666": {"archived_at": "2025-01-01T00:00:00", "note": None}
            },
        }),
        encoding="utf-8",
    )
    cache = supplier_archive.load(financial_analysis_dir=tmp_path)
    assert "666666666" in cache
    assert supplier_archive.is_archived("666666666", cache=cache) is True
    assert supplier_archive.is_excluded_from_analysis("666666666", cache=cache) is False


# -- apply_excluded_from_analysis ----------------------------------------------


def test_pipeline_zeros_debt_for_excluded_supplier(tmp_path):
    supplier_archive.set_status(
        tax_id="777777777",
        excluded_from_analysis=True,
        exclusion_reason="ზედნადებები ერთ დღეს გაუქმდება",
        financial_analysis_dir=tmp_path,
    )
    data = {
        "suppliers": [{
            "ორგანიზაცია": "(777777777) Test Supplier",
            "total_effective": 50000,
            "total_paid": 10000,
            "total_debt": 40000,
        }],
    }
    apply_excluded_from_analysis(data, financial_analysis_dir=tmp_path)
    s = data["suppliers"][0]
    assert s["total_debt"] == 0.0
    assert s["total_paid"] == 50000
    assert s["bank_paid_pre_exclusion"] == 10000
    assert s["excluded_credit"] == 40000
    assert s["payment_scope"] == "excluded_from_analysis"
    assert s["excluded_from_analysis"] is True
    assert "ზედნადებები ერთ დღეს გაუქმდება" in s["payment_scope_note"]


def test_pipeline_does_not_touch_non_excluded_suppliers(tmp_path):
    supplier_archive.set_status(
        tax_id="888888888",
        excluded_from_analysis=True,
        exclusion_reason="r",
        financial_analysis_dir=tmp_path,
    )
    data = {
        "suppliers": [
            {
                "ორგანიზაცია": "(888888888) Excluded",
                "total_effective": 100,
                "total_paid": 0,
                "total_debt": 100,
            },
            {
                "ორგანიზაცია": "(123456789) Active",
                "total_effective": 200,
                "total_paid": 50,
                "total_debt": 150,
            },
        ],
    }
    apply_excluded_from_analysis(data, financial_analysis_dir=tmp_path)
    # excluded row → debt 0
    assert data["suppliers"][0]["total_debt"] == 0.0
    assert data["suppliers"][0].get("excluded_from_analysis") is True
    # active row untouched
    assert data["suppliers"][1]["total_debt"] == 150
    assert "excluded_from_analysis" not in data["suppliers"][1]


def test_pipeline_handles_empty_data(tmp_path):
    apply_excluded_from_analysis({}, financial_analysis_dir=tmp_path)
    apply_excluded_from_analysis({"suppliers": []}, financial_analysis_dir=tmp_path)
    # Should not raise.
