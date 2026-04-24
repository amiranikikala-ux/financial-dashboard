"""Integration tests for bank samurneo Tier 2 Sprint 3b incremental cache.

Mirrors `test_retail_sales_incremental.py`. Covers the contract that
`collect_tbc_samurneo_flow` and `collect_bog_samurneo_flow` must satisfy
when `use_cache=True`:

1. Cache-hot bundle equals cache-cold bundle (TBC + BOG).
2. Only changed files are re-read; unchanged files reuse cached payloads.
3. A newly-added file triggers a read on the next run; others reuse cache.
4. A file removed from disk drops out of the merged bundle and the cache.
5. A corrupt / malformed cache falls back to a full re-read (never crashes).
6. A config change (patterns/include_all) invalidates the cache via the
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
    collect_bog_samurneo_flow,
    collect_tbc_samurneo_flow,
)


TBC_COLUMNS = ["თარიღი", "გასული თანხა", "შემოსული თანხა", "დანიშნულება"]
BOG_COLUMNS = ["თარიღი", "დებეტი", "კრედიტი", "დანიშნულება"]


def _write_samurneo_config(script_dir: Path, *, include_all=True, patterns=None):
    cfg_dir = script_dir / "Financial_Analysis"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "tbc_samurneo_patterns.json"
    payload = {
        "include_all_transactions": bool(include_all),
        "match_substrings": list(patterns or []),
    }
    cfg_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cfg_path


def _write_tbc_xlsx(path: Path, rows):
    df = pd.DataFrame(rows, columns=TBC_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _write_bog_xlsx(path: Path, rows):
    df = pd.DataFrame(rows, columns=BOG_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _tbc_row(date_str, debit, credit, note):
    return {
        "თარიღი": date_str,
        "გასული თანხა": debit,
        "შემოსული თანხა": credit,
        "დანიშნულება": note,
    }


def _bog_row(date_str, debit, credit, note):
    return {
        "თარიღი": date_str,
        "დებეტი": debit,
        "კრედიტი": credit,
        "დანიშნულება": note,
    }


@pytest.fixture
def fake_tbc_env(tmp_path, monkeypatch):
    """Two TBC yearly xlsx files under tmp_path + patched file lister."""
    _write_samurneo_config(tmp_path, include_all=True)
    tbc_dir = tmp_path / "Financial_Analysis" / "თბს ბანკი ამონაწერი"
    file_2023 = tbc_dir / "2023.xlsx"
    file_2024 = tbc_dir / "2024.xlsx"
    _write_tbc_xlsx(
        file_2023,
        [
            _tbc_row("2023-05-10", 100.0, None, "სამეურნეო ხარჯი — მაღაზია"),
            _tbc_row("2023-06-15", None, 40.0, "სამეურნეო ხარჯის დაბრუნება"),
        ],
    )
    _write_tbc_xlsx(
        file_2024,
        [
            _tbc_row("2024-02-01", 250.0, None, "სამეურნეო ხარჯი — მეორე"),
        ],
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
    """One BOG yearly xlsx under tmp_path + patched file lister."""
    _write_samurneo_config(tmp_path, include_all=True)
    bog_dir = tmp_path / "Financial_Analysis" / "ბოგ ბანკი ამონაწერი"
    file_2024 = bog_dir / "2024.xlsx"
    _write_bog_xlsx(
        file_2024,
        [
            _bog_row("2024-03-10", 75.0, None, "სამეურნეო ხარჯი — bog"),
            _bog_row("2024-04-20", None, 25.0, "სამეურნეო დაბრუნება — bog"),
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


# ---------------------------------------------------------------------------
# 1. TBC — cold vs hot equivalence
# ---------------------------------------------------------------------------

def test_tbc_cache_cold_vs_cache_hot_equivalence(fake_tbc_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    hot = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert _comparable(cold) == _comparable(hot)
    assert cold["expense_total_ge"] == 350.0
    assert cold["return_total_ge"] == 40.0
    assert cold["expense_line_count"] == 2
    assert cold["return_line_count"] == 1

    plain = collect_tbc_samurneo_flow(fake_tbc_env["script_dir"], use_cache=False)
    assert _comparable(plain) == _comparable(hot)


# ---------------------------------------------------------------------------
# 2. BOG — cold vs hot equivalence
# ---------------------------------------------------------------------------

def test_bog_cache_cold_vs_cache_hot_equivalence(fake_bog_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_bog_samurneo_flow(
        fake_bog_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    hot = collect_bog_samurneo_flow(
        fake_bog_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert _comparable(cold) == _comparable(hot)
    assert cold["expense_total_ge"] == 75.0
    assert cold["return_total_ge"] == 25.0
    # BOG rows tagged with ბანკი=BOG
    exp_row = cold["expense_rows_preview"][0]
    assert exp_row.get("ბანკი") == "BOG"


# ---------------------------------------------------------------------------
# 3. Only changed file is re-read
# ---------------------------------------------------------------------------

def test_only_changed_tbc_file_is_reread(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    read_calls = []
    original = bank_income_module._process_tbc_samurneo_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(bank_income_module, "_process_tbc_samurneo_file", tracker)

    # Mutate the 2023 file; 2024 stays untouched.
    _write_tbc_xlsx(
        fake_tbc_env["file_2023"],
        [
            _tbc_row("2023-05-10", 100.0, None, "სამეურნეო ხარჯი"),
            _tbc_row("2023-07-11", 55.0, None, "სამეურნეო დამატებითი"),
        ],
    )

    bundle = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert read_calls == [str(fake_tbc_env["file_2023"])]
    # 100 (unchanged original row) + 55 (new) + 250 (2024 cached)
    assert bundle["expense_total_ge"] == 405.0


# ---------------------------------------------------------------------------
# 4. New file triggers read, others reuse cache
# ---------------------------------------------------------------------------

def test_new_tbc_file_triggers_read_others_reuse(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    new_file = fake_tbc_env["tbc_dir"] / "2025.xlsx"
    _write_tbc_xlsx(
        new_file,
        [_tbc_row("2025-01-05", 500.0, None, "სამეურნეო 2025")],
    )
    all_files = fake_tbc_env["files"] + [str(new_file)]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(all_files),
    )

    read_calls = []
    original = bank_income_module._process_tbc_samurneo_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(bank_income_module, "_process_tbc_samurneo_file", tracker)

    bundle = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert read_calls == [str(new_file)]
    # 100 + 250 (cached) + 500 (new) = 850
    assert bundle["expense_total_ge"] == 850.0


# ---------------------------------------------------------------------------
# 5. Deleted file drops from bundle and cache
# ---------------------------------------------------------------------------

def test_deleted_tbc_file_drops_from_bundle(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    os.remove(fake_tbc_env["file_2023"])
    remaining = [str(fake_tbc_env["file_2024"])]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(remaining),
    )

    bundle = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    # Only 2024's 250 survives.
    assert bundle["expense_total_ge"] == 250.0
    assert bundle["return_total_ge"] == 0.0

    with open(cache_file, "r", encoding="utf-8") as handle:
        cache_payload = json.load(handle)
    cache_keys = set(cache_payload["files"].keys())
    assert os.path.normpath(str(fake_tbc_env["file_2023"])) not in cache_keys


# ---------------------------------------------------------------------------
# 6. Corrupt cache degrades to full re-read
# ---------------------------------------------------------------------------

def test_corrupt_cache_degrades_to_full_reread(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    cache_file.write_text("this is definitely not json{")

    read_calls = []
    original = bank_income_module._process_tbc_samurneo_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(bank_income_module, "_process_tbc_samurneo_file", tracker)

    bundle = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert len(read_calls) == 2  # both TBC files re-read
    assert bundle["expense_total_ge"] == 350.0


# ---------------------------------------------------------------------------
# 7. Content fingerprint invalidates cache when config changes
# ---------------------------------------------------------------------------

def test_config_change_invalidates_cache(fake_tbc_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    # Prime cache with include_all=True
    collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    # Flip config — include_all=False with no patterns means every row gets
    # filtered out. The fingerprint must detect the flip and re-read both
    # files (not serve the cached rows from include_all=True).
    _write_samurneo_config(
        Path(fake_tbc_env["script_dir"]),
        include_all=False,
        patterns=["__will_never_match__"],
    )

    read_calls = []
    original = bank_income_module._process_tbc_samurneo_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(bank_income_module, "_process_tbc_samurneo_file", tracker)

    bundle = collect_tbc_samurneo_flow(
        fake_tbc_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert len(read_calls) == 2  # fingerprint mismatch → both files re-read
    # New config filters everything out.
    assert bundle["expense_total_ge"] == 0.0
    assert bundle["return_total_ge"] == 0.0
