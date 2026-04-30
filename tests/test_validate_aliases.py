"""Tests for dashboard_pipeline/_validate_aliases.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard_pipeline._validate_aliases import (
    AliasDuplicateError,
    AliasValidationError,
    append_alias_atomic,
    load_and_validate,
    load_aliases_file,
    validate_aliases,
)


def _write(tmp_path: Path, content) -> Path:
    p = tmp_path / "product_aliases.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return p


def test_missing_file_returns_empty_no_errors(tmp_path: Path):
    parsed, errors = load_aliases_file(tmp_path / "nope.json")
    assert parsed == {"version": 1, "aliases": []}
    assert errors == []


def test_invalid_json_returns_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{ this is not json", encoding="utf-8")
    parsed, errors = load_aliases_file(p)
    assert parsed is None
    assert any("invalid JSON" in e for e in errors)


def test_top_level_must_be_object(tmp_path: Path):
    p = _write(tmp_path, ["array", "not", "object"])
    parsed, errors = load_aliases_file(p)
    assert parsed is None


def test_missing_aliases_key_treated_as_empty(tmp_path: Path):
    p = _write(tmp_path, {"version": 1})
    parsed, errors = load_aliases_file(p)
    assert parsed["aliases"] == []
    assert any("missing or non-list" in e for e in errors)


def test_valid_user_alias_passes(tmp_path: Path):
    p = _write(
        tmp_path,
        {
            "version": 1,
            "aliases": [
                {
                    "imported_code": "01-00008088",
                    "retail_code_or_barcode": "4860119260841",
                    "confirmed_by": "user",
                    "confirmed_at": "2026-04-26",
                }
            ],
        },
    )
    safe, errors = load_and_validate(p, {"4860119260841", "1234567890123"})
    assert len(safe) == 1
    assert safe[0]["imported_code"] == "01-00008088"
    assert safe[0]["retail_code_or_barcode"] == "4860119260841"
    assert errors == []


def test_alias_with_confirmed_by_not_user_rejected(tmp_path: Path):
    p = _write(
        tmp_path,
        {
            "version": 1,
            "aliases": [
                {
                    "imported_code": "X",
                    "retail_code_or_barcode": "Y",
                    "confirmed_by": "automation",
                }
            ],
        },
    )
    safe, errors = load_and_validate(p, {"Y"})
    assert safe == []
    assert any("confirmed_by must be" in e for e in errors)


def test_alias_with_missing_target_rejected(tmp_path: Path):
    p = _write(
        tmp_path,
        {
            "version": 1,
            "aliases": [
                {
                    "imported_code": "X",
                    "retail_code_or_barcode": "DOES_NOT_EXIST",
                    "confirmed_by": "user",
                }
            ],
        },
    )
    safe, errors = load_and_validate(p, {"OTHER", "STUFF"})
    assert safe == []
    assert any("does not exist in current retail_sales" in e for e in errors)


def test_duplicate_imported_code_rejected_second_time(tmp_path: Path):
    """First occurrence wins; second is rejected with explicit error."""
    p = _write(
        tmp_path,
        {
            "version": 1,
            "aliases": [
                {"imported_code": "X", "retail_code_or_barcode": "Y", "confirmed_by": "user"},
                {"imported_code": "X", "retail_code_or_barcode": "Z", "confirmed_by": "user"},
            ],
        },
    )
    safe, errors = load_and_validate(p, {"Y", "Z"})
    assert len(safe) == 1
    assert safe[0]["retail_code_or_barcode"] == "Y"
    assert any("duplicate imported_code" in e for e in errors)


def test_empty_imported_code_rejected(tmp_path: Path):
    p = _write(
        tmp_path,
        {
            "version": 1,
            "aliases": [
                {"imported_code": "", "retail_code_or_barcode": "Y", "confirmed_by": "user"},
            ],
        },
    )
    safe, errors = load_and_validate(p, {"Y"})
    assert safe == []
    assert any("empty imported_code" in e for e in errors)


def test_whitespace_in_codes_normalized(tmp_path: Path):
    p = _write(
        tmp_path,
        {
            "version": 1,
            "aliases": [
                {
                    "imported_code": "  X  ",
                    "retail_code_or_barcode": "  Y  ",
                    "confirmed_by": "user",
                }
            ],
        },
    )
    safe, errors = load_and_validate(p, {"Y"})
    assert len(safe) == 1
    assert safe[0]["imported_code"] == "X"
    assert safe[0]["retail_code_or_barcode"] == "Y"


def test_non_dict_alias_skipped(tmp_path: Path):
    p = _write(tmp_path, {"version": 1, "aliases": ["not-a-dict"]})
    safe, errors = load_and_validate(p, {"Y"})
    assert safe == []
    assert any("not an object" in e for e in errors)


# ---------------------------------------------------------------------------
# append_alias_atomic — Sprint C confirm-button helper
# ---------------------------------------------------------------------------


def test_append_alias_atomic_appends_valid_entry(tmp_path: Path):
    """Empty-file path: helper seeds the canonical document, appends one
    entry, and stamps confirmed_by=user + confirmed_at."""
    p = tmp_path / "product_aliases.json"
    canonical = append_alias_atomic(
        p,
        {
            "imported_code": "2006",
            "retail_code_or_barcode": "2247377",
            "imported_supplier_taxid": "400123456",
            "imported_name_sample": "შეფუთული აგურა რუხი",
        },
        retail_known_keys={"2247377", "4860103230058"},
    )

    assert canonical["imported_code"] == "2006"
    assert canonical["retail_code_or_barcode"] == "2247377"
    assert canonical["confirmed_by"] == "user"
    assert canonical["confirmed_at"]  # non-empty ISO timestamp
    assert canonical["imported_name_sample"] == "შეფუთული აგურა რუხი"

    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["aliases"] == [canonical]
    assert on_disk["version"] == 1


def test_append_alias_atomic_rejects_unknown_retail_key(tmp_path: Path):
    """Validation gate: unknown retail key raises AliasValidationError
    and the file is never created."""
    p = tmp_path / "product_aliases.json"
    with pytest.raises(AliasValidationError) as exc_info:
        append_alias_atomic(
            p,
            {"imported_code": "X", "retail_code_or_barcode": "GHOST"},
            retail_known_keys={"REAL_ONE"},
        )
    assert "GHOST" in str(exc_info.value)
    assert exc_info.value.kind == "validation"
    assert not p.exists()


def test_append_alias_atomic_rejects_duplicate_imported_code(tmp_path: Path):
    """Second confirm of the same imported_code raises AliasDuplicateError
    (which the endpoint maps to HTTP 409, not 400)."""
    p = tmp_path / "product_aliases.json"
    append_alias_atomic(
        p,
        {"imported_code": "2006", "retail_code_or_barcode": "2247377"},
        retail_known_keys={"2247377"},
    )

    with pytest.raises(AliasDuplicateError) as exc_info:
        append_alias_atomic(
            p,
            {"imported_code": "2006", "retail_code_or_barcode": "2247377"},
            retail_known_keys={"2247377"},
        )
    assert exc_info.value.kind == "duplicate"

    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert len(on_disk["aliases"]) == 1


def test_append_alias_atomic_overwrites_stale_tmp(tmp_path: Path):
    """If a previous failed write left a sibling .tmp, the next successful
    append must clear it (no orphan files left around)."""
    p = tmp_path / "product_aliases.json"
    stale = p.with_suffix(p.suffix + ".tmp")
    stale.write_text("STALE GARBAGE", encoding="utf-8")

    append_alias_atomic(
        p,
        {"imported_code": "2006", "retail_code_or_barcode": "2247377"},
        retail_known_keys={"2247377"},
    )

    assert p.exists()
    assert not stale.exists()
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert len(on_disk["aliases"]) == 1
