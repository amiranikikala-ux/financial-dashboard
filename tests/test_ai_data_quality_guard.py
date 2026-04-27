from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dashboard_pipeline.ai.data_quality_guard import (
    SOURCE_LABEL,
    _best_store_candidate,
    audit_data_quality,
)


def _project_with_imported_csv(tmp_path: Path, destinations: list[str]) -> Path:
    root = tmp_path / "project"
    source_dir = root / "Financial_Analysis" / "შემოტანილი პროდუქცია"
    source_dir.mkdir(parents=True)
    mapping = {
        "rs_location_priority_order": ["დვაბზუ", "ოზურგეთი"],
        "rs_location_to_object": {
            "დვაბზუ": ["დვაბზუ", "სოფ დვაბზუ"],
            "ოზურგეთი": ["ოზურგეთი", "ქ ოზურგეთი"],
        },
        "tbc_text_to_object": {"დვაბზუ": "დვაბზუ", "ოზურგეთი": "ოზურგეთი"},
        "salary_text_to_object": {"დვაბზუ": "დვაბზუ", "ოზურგეთი": "ოზურგეთი"},
        "default_object": "გაუნაწილებელი",
    }
    (root / "Financial_Analysis" / "object_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False),
        encoding="utf-8",
    )
    rows = []
    for idx, destination in enumerate(destinations, start=1):
        rows.append({
            "col_a": idx,
            "col_b": "x",
            "col_c": "y",
            "col_d": "z",
            "ტრანსპორტირების დასრულება": destination,
            "თანხა": 10,
        })
    pd.DataFrame(rows).to_csv(source_dir / "2026.csv", index=False, encoding="utf-8-sig")
    return root


def test_best_store_candidate_detects_dvabzu_typo() -> None:
    result = _best_store_candidate(
        "ოზურგეთის რაიონი სოფ დვაზუს მისამართი",
        {"დვაბზუ": ("დვაბზუ",), "ოზურგეთი": ("ოზურგეთი",)},
    )

    assert result["suggested_object"] == "დვაბზუ"
    assert result["conflict"] is True
    assert result["score"] >= 0.82


def test_store_scan_reports_typo_without_auto_fixing(tmp_path: Path) -> None:
    root = _project_with_imported_csv(
        tmp_path,
        ["ოზურგეთის რაიონი სოფ დვაზუს მისამართი", "სოფ დვაბზუ"],
    )

    result = audit_data_quality(
        lambda: {},
        focus="stores",
        project_root=root,
        min_similarity=0.82,
    )

    assert result["source"] == SOURCE_LABEL
    assert result["risk_level"] == "HIGH"
    assert result["stores"]["issue_count"] == 1
    issue = result["stores"]["issues"][0]
    assert issue["original_value"] == "ოზურგეთის რაიონი სოფ დვაზუს მისამართი"
    assert issue["suggested_object"] == "დვაბზუ"
    assert issue["type"] == "store_mapping_conflict"
    assert issue["action"] == "review_mapping_before_final_analysis"
    assert "ჩუმად არ ცვლის" in result["notes"][0]


def test_exact_store_alias_does_not_create_issue(tmp_path: Path) -> None:
    root = _project_with_imported_csv(tmp_path, ["სოფ დვაბზუ", "ქ ოზურგეთი"])

    result = audit_data_quality(lambda: {}, focus="stores", project_root=root)

    assert result["risk_level"] == "LOW"
    assert result["stores"]["issue_count"] == 0


def test_supplier_scan_flags_same_tax_id_name_variant() -> None:
    data = {
        "suppliers": [
            {"ორგანიზაცია": "შპს ალფა ტრეიდი (123456789)", "total_effective": 1000},
        ],
        "imported_products": {
            "suppliers": [
                {"supplier": "ალფა", "tax_id": "123456789", "total_amount_ge": 1200},
            ]
        },
    }

    result = audit_data_quality(lambda: data, focus="suppliers")

    assert result["risk_level"] == "MEDIUM"
    assert result["suppliers"]["issue_count"] == 1
    issue = result["suppliers"]["issues"][0]
    assert issue["type"] == "same_tax_id_name_variant"
    assert issue["confidence_pct"] == 100.0


def test_supplier_scan_flags_similar_names_without_tax_id() -> None:
    data = {
        "suppliers": [
            {"ორგანიზაცია": "დვაბზუ მარკეტი", "total_effective": 1000},
            {"ორგანიზაცია": "დვაზუ მარკეტი", "total_effective": 900},
        ]
    }

    result = audit_data_quality(lambda: data, focus="suppliers", min_similarity=0.8)

    assert result["risk_level"] == "MEDIUM"
    assert result["suppliers"]["issues"][0]["type"] == "similar_supplier_names"


def test_tool_registered_and_dispatcher_routes(tmp_path: Path) -> None:
    from dashboard_pipeline.ai.tools import DATA_QUALITY_GUARD_TOOL, TOOL_SCHEMAS, ToolDispatcher

    root = _project_with_imported_csv(tmp_path, ["სოფ დვაზუ"])
    dispatcher = ToolDispatcher(lambda: {}, project_root=root)

    result = dispatcher.dispatch(
        "data_quality_guard",
        {"focus": "stores", "min_similarity": 0.8, "top_n": 5},
    )

    assert DATA_QUALITY_GUARD_TOOL in TOOL_SCHEMAS
    assert "data_quality_guard" in [tool["name"] for tool in TOOL_SCHEMAS]
    assert len(TOOL_SCHEMAS) == 29
    assert result["risk_level"] == "HIGH"
    assert dispatcher.calls[-1]["tool"] == "data_quality_guard"
