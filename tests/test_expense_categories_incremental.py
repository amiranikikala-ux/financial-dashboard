"""Integration tests for bank expense_categories Tier 2 Sprint 3c cache.

Mirrors `test_samurneo_incremental.py`. Covers the contract that
`collect_tbc_expense_categories` and `collect_bog_expense_categories`
must satisfy when `use_cache=True`:

1. Cache-hot bundle equals cache-cold bundle (TBC + BOG).
2. Only changed files are re-read; unchanged files reuse cached payloads.
3. A newly-added file triggers a read on the next run; others reuse cache.
4. A file removed from disk drops out of the merged bundle and the cache.
5. A corrupt / malformed cache falls back to a full re-read (never crashes).
6. A config change (categories) invalidates the cache via
   content_fingerprint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import bank_income as bank_income_module
from dashboard_pipeline.bank_income import (
    collect_bog_expense_categories,
    collect_tbc_expense_categories,
)
from dashboard_pipeline.constants import (
    BOG_OTHER_EXPENSE_ID,
    TBC_OTHER_EXPENSE_ID,
)


TBC_COLUMNS = ["თარიღი", "გასული თანხა", "დანიშნულება"]
BOG_COLUMNS = [
    "თარიღი",
    "დებეტი",
    "ოპერაციის შინაარსი",
    "დანიშნულება",
    "მიმღების დასახელება",
]


def _write_expense_config(script_dir: Path, *, categories=None):
    cfg_dir = script_dir / "Financial_Analysis"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "tbc_expense_categories.json"
    if categories is None:
        categories = [
            {
                "id": "rent",
                "label_ka": "ქირა",
                "accounting_role": "OPERATING",
                "match_substrings": ["ქირა", "rent"],
            },
            {
                "id": "utilities",
                "label_ka": "კომუნალური",
                "accounting_role": "OPERATING",
                "match_substrings": ["კომუნალური", "ელექტრო"],
            },
        ]
    payload = {"categories": categories}
    cfg_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cfg_path


def _write_object_mapping(script_dir: Path):
    """Minimal object_mapping.json so load_object_mapping doesn't return defaults.

    Expense collectors fall back to `load_object_mapping(script_dir)` when
    `object_mapping=None` — that function searches Financial_Analysis/ for
    `object_mapping.json`. Empty dict is enough; detect_object falls back.
    """
    (script_dir / "Financial_Analysis").mkdir(parents=True, exist_ok=True)
    path = script_dir / "Financial_Analysis" / "object_mapping.json"
    path.write_text(json.dumps({}), encoding="utf-8")


def _write_tbc_xlsx(path: Path, rows):
    df = pd.DataFrame(rows, columns=TBC_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _write_bog_xlsx(path: Path, rows):
    df = pd.DataFrame(rows, columns=BOG_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _tbc_row(date_str, debit, note):
    return {
        "თარიღი": date_str,
        "გასული თანხა": debit,
        "დანიშნულება": note,
    }


def _bog_row(date_str, debit, operation, purpose, receiver):
    return {
        "თარიღი": date_str,
        "დებეტი": debit,
        "ოპერაციის შინაარსი": operation,
        "დანიშნულება": purpose,
        "მიმღების დასახელება": receiver,
    }


@pytest.fixture
def fake_tbc_env(tmp_path, monkeypatch):
    _write_expense_config(tmp_path)
    _write_object_mapping(tmp_path)
    tbc_dir = tmp_path / "Financial_Analysis" / "თბს ბანკი ამონაწერი"
    file_2023 = tbc_dir / "2023.xlsx"
    file_2024 = tbc_dir / "2024.xlsx"
    _write_tbc_xlsx(
        file_2023,
        [
            _tbc_row("2023-05-10", 500.0, "ქირა — მაღაზია"),
            _tbc_row("2023-06-15", 120.0, "კომუნალური ხარჯი"),
            _tbc_row("2023-07-01", 75.0, "სხვადასხვა გადახდა"),  # → TBC_OTHER
        ],
    )
    _write_tbc_xlsx(
        file_2024,
        [_tbc_row("2024-02-01", 600.0, "ქირა — მეორე თვე")],
    )
    files = [str(file_2023), str(file_2024)]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(files),
    )
    return {
        "script_dir": str(tmp_path),
        "tbc_dir": tbc_dir,
        "files": files,
        "file_2023": file_2023,
        "file_2024": file_2024,
    }


@pytest.fixture
def fake_bog_env(tmp_path, monkeypatch):
    _write_expense_config(tmp_path)
    _write_object_mapping(tmp_path)
    bog_dir = tmp_path / "Financial_Analysis" / "ბოგ ბანკი ამონაწერი"
    file_2024 = bog_dir / "2024.xlsx"
    _write_bog_xlsx(
        file_2024,
        [
            _bog_row("2024-03-10", 300.0, "გადახდა", "ქირა — bog", "მიმღები ა"),
            _bog_row(
                "2024-04-20", 80.0, "გადახდა", "კომუნალური", "მიმღები ბ"
            ),
            _bog_row(
                "2024-05-01", 50.0, "გადახდა", "უცნობი", "მიმღები გ"
            ),  # → BOG_OTHER
        ],
    )
    files = [str(file_2024)]
    monkeypatch.setattr(
        bank_income_module,
        "list_bog_bank_statement_xlsx",
        lambda: list(files),
    )
    return {
        "script_dir": str(tmp_path),
        "bog_dir": bog_dir,
        "files": files,
        "file_2024": file_2024,
    }


def _comparable(bundle):
    return json.loads(json.dumps(bundle, default=str))


def _cat_total(bundle, cat_id):
    for cat in bundle.get("categories") or []:
        if cat.get("id") == cat_id:
            return float(cat.get("total_ge") or 0)
    return 0.0


# ---------------------------------------------------------------------------
# 1. TBC — cold vs hot equivalence
# ---------------------------------------------------------------------------

def test_tbc_cache_cold_vs_cache_hot_equivalence(fake_tbc_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    hot = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    assert _comparable(cold) == _comparable(hot)
    # 500 + 600 (rent) + 120 (utilities) + 75 (other) = 1295
    assert cold["grand_total_ge"] == 1295.0
    assert _cat_total(cold, "rent") == 1100.0
    assert _cat_total(cold, "utilities") == 120.0
    assert _cat_total(cold, TBC_OTHER_EXPENSE_ID) == 75.0

    plain = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"], use_cache=False
    )
    assert _comparable(plain) == _comparable(hot)


# ---------------------------------------------------------------------------
# 2. BOG — cold vs hot equivalence
# ---------------------------------------------------------------------------

def test_bog_cache_cold_vs_cache_hot_equivalence(fake_bog_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_bog_expense_categories(
        fake_bog_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    hot = collect_bog_expense_categories(
        fake_bog_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    assert _comparable(cold) == _comparable(hot)
    # 300 (rent) + 80 (utilities) + 50 (BOG_OTHER) = 430
    assert cold["grand_total_ge"] == 430.0
    assert _cat_total(cold, "rent") == 300.0
    assert _cat_total(cold, "utilities") == 80.0
    assert _cat_total(cold, BOG_OTHER_EXPENSE_ID) == 50.0


# ---------------------------------------------------------------------------
# 3. Only changed file is re-read
# ---------------------------------------------------------------------------

def test_only_changed_tbc_file_is_reread(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )

    read_calls = []
    original = bank_income_module._process_tbc_expense_categories_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_expense_categories_file", tracker
    )

    _write_tbc_xlsx(
        fake_tbc_env["file_2023"],
        [
            _tbc_row("2023-05-10", 500.0, "ქირა — მაღაზია"),
            _tbc_row("2023-08-11", 200.0, "კომუნალური დამატებითი"),
        ],
    )

    bundle = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    assert read_calls == [str(fake_tbc_env["file_2023"])]
    # 500 (rent, unchanged) + 600 (rent, 2024 cached) + 200 (utilities new) = 1300
    assert bundle["grand_total_ge"] == 1300.0


# ---------------------------------------------------------------------------
# 4. New file triggers read, others reuse cache
# ---------------------------------------------------------------------------

def test_new_tbc_file_triggers_read_others_reuse(
    fake_tbc_env, tmp_path, monkeypatch
):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )

    new_file = fake_tbc_env["tbc_dir"] / "2025.xlsx"
    _write_tbc_xlsx(
        new_file,
        [_tbc_row("2025-01-05", 700.0, "ქირა 2025")],
    )
    all_files = fake_tbc_env["files"] + [str(new_file)]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(all_files),
    )

    read_calls = []
    original = bank_income_module._process_tbc_expense_categories_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_expense_categories_file", tracker
    )

    bundle = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    assert read_calls == [str(new_file)]
    # prior 1295 + 700 (new rent) = 1995
    assert bundle["grand_total_ge"] == 1995.0


# ---------------------------------------------------------------------------
# 5. Deleted file drops from bundle and cache
# ---------------------------------------------------------------------------

def test_deleted_tbc_file_drops_from_bundle(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )

    os.remove(fake_tbc_env["file_2023"])
    remaining = [str(fake_tbc_env["file_2024"])]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(remaining),
    )

    bundle = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    # Only 2024's 600 (rent) survives
    assert bundle["grand_total_ge"] == 600.0

    with open(cache_file, "r", encoding="utf-8") as handle:
        cache_payload = json.load(handle)
    cache_keys = set(cache_payload["files"].keys())
    assert os.path.normpath(str(fake_tbc_env["file_2023"])) not in cache_keys


# ---------------------------------------------------------------------------
# 6. Corrupt cache degrades to full re-read
# ---------------------------------------------------------------------------

def test_corrupt_cache_degrades_to_full_reread(
    fake_tbc_env, tmp_path, monkeypatch
):
    cache_file = tmp_path / ".pipeline_cache.json"
    cache_file.write_text("this is definitely not json{")

    read_calls = []
    original = bank_income_module._process_tbc_expense_categories_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_expense_categories_file", tracker
    )

    bundle = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    assert len(read_calls) == 2  # both TBC files re-read
    assert bundle["grand_total_ge"] == 1295.0


# ---------------------------------------------------------------------------
# 7. Content fingerprint invalidates cache when config changes
# ---------------------------------------------------------------------------

def test_config_change_invalidates_cache(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    # Prime with default categories (rent + utilities)
    collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )

    # Drop "utilities" — now all ex-utilities rows collapse into TBC_OTHER
    _write_expense_config(
        Path(fake_tbc_env["script_dir"]),
        categories=[
            {
                "id": "rent",
                "label_ka": "ქირა",
                "accounting_role": "OPERATING",
                "match_substrings": ["ქირა", "rent"],
            }
        ],
    )

    read_calls = []
    original = bank_income_module._process_tbc_expense_categories_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_expense_categories_file", tracker
    )

    bundle = collect_tbc_expense_categories(
        fake_tbc_env["script_dir"],
        use_cache=True,
        cache_path=str(cache_file),
    )
    # Fingerprint mismatch → both files re-read, grand total unchanged but
    # utilities rows now routed to TBC_OTHER.
    assert len(read_calls) == 2
    assert bundle["grand_total_ge"] == 1295.0
    assert _cat_total(bundle, "rent") == 1100.0
    assert _cat_total(bundle, "utilities") == 0.0
    # 120 (was utilities) + 75 (was other) → both into TBC_OTHER
    assert _cat_total(bundle, TBC_OTHER_EXPENSE_ID) == 195.0
