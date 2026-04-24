"""Integration tests for Tier 2 Sprint 3f foodmart cashback cache.

Final collector in the per-file cache series (Sprints 3b/3c/3d/3e/3f).
Covers the contract that `collect_tbc_foodmart_cashback` must satisfy
when ``use_cache=True``:

1. Cold vs hot cache equivalence.
2. Plain (use_cache=False) vs cached equivalence.
3. Only changed file is re-read; unchanged files reuse cache.
4. A newly-added file triggers read; others reuse cache.
5. A file removed from disk drops out of the bundle and the cache.
6. A corrupt / malformed cache falls back to a full re-read.
7. Pattern-list change invalidates cache via content_fingerprint.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import bank_income as bank_income_module
from dashboard_pipeline.bank_income import collect_tbc_foodmart_cashback


TBC_COLUMNS = ["თარიღი", "გასული თანხა", "შემოსული თანხა", "დანიშნულება"]


def _write_tbc_xlsx(path: Path, rows):
    df = pd.DataFrame(rows, columns=TBC_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _tbc_row(date_str, credit, note):
    return {
        "თარიღი": date_str,
        "გასული თანხა": None,
        "შემოსული თანხა": credit,
        "დანიშნულება": note,
    }


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    """Two TBC yearly xlsx files with foodmart/cashback-matching rows."""
    tbc_dir = tmp_path / "Financial_Analysis" / "თბს ბანკი ამონაწერი"
    file_2023 = tbc_dir / "2023.xlsx"
    file_2024 = tbc_dir / "2024.xlsx"
    _write_tbc_xlsx(
        file_2023,
        [
            _tbc_row("2023-05-10", 100.0, "ფუდმარტი ქეშბექი მაისი"),
            _tbc_row("2023-06-15", 40.0, "foodmart cashback return"),
            # Non-matching row — will be filtered out
            _tbc_row("2023-07-01", 999.0, "unrelated income row"),
        ],
    )
    _write_tbc_xlsx(
        file_2024,
        [
            _tbc_row("2024-03-20", 250.0, "404460187 ფუდმარტი"),
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


def _comparable(bundle):
    return json.loads(json.dumps(bundle, default=str))


# ---------------------------------------------------------------------------
# 1. Cold vs hot equivalence
# ---------------------------------------------------------------------------

def test_cold_vs_hot_equivalence(fake_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    hot = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert _comparable(cold) == _comparable(hot)
    # 100 + 40 + 250 = 390 (999 unrelated filtered)
    assert cold["total_ge"] == 390.0
    assert cold["line_count"] == 3


# ---------------------------------------------------------------------------
# 2. Plain vs cached
# ---------------------------------------------------------------------------

def test_plain_vs_cached(fake_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    plain = collect_tbc_foodmart_cashback(fake_env["script_dir"])
    cached = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert _comparable(plain) == _comparable(cached)


# ---------------------------------------------------------------------------
# 3. Only changed file is re-read
# ---------------------------------------------------------------------------

def test_only_changed_file_is_reread(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    read_calls = []
    original = bank_income_module._process_tbc_foodmart_cashback_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_foodmart_cashback_file", tracker
    )

    _write_tbc_xlsx(
        fake_env["file_2023"],
        [
            _tbc_row("2023-05-10", 100.0, "ფუდმარტი ქეშბექი მაისი"),
            _tbc_row("2023-08-01", 55.0, "cashback დამატებითი ფუდმარტი"),
        ],
    )
    bundle = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert read_calls == [str(fake_env["file_2023"])]
    # 100 + 55 (new 2023) + 250 (cached 2024) = 405
    assert bundle["total_ge"] == 405.0


# ---------------------------------------------------------------------------
# 4. New file triggers read
# ---------------------------------------------------------------------------

def test_new_file_triggers_read(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    new_file = fake_env["tbc_dir"] / "2025.xlsx"
    _write_tbc_xlsx(
        new_file,
        [_tbc_row("2025-01-05", 500.0, "foodmart cashback 2025")],
    )
    all_files = fake_env["files"] + [str(new_file)]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(all_files),
    )
    read_calls = []
    original = bank_income_module._process_tbc_foodmart_cashback_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_foodmart_cashback_file", tracker
    )
    bundle = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert read_calls == [str(new_file)]
    # 390 (cached) + 500 (new) = 890
    assert bundle["total_ge"] == 890.0


# ---------------------------------------------------------------------------
# 5. Deleted file drops
# ---------------------------------------------------------------------------

def test_deleted_file_drops(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    os.remove(fake_env["file_2024"])
    remaining = [str(fake_env["file_2023"])]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(remaining),
    )
    bundle = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    # 2023 has 100 + 40 = 140; 2024 (250) dropped.
    assert bundle["total_ge"] == 140.0

    with open(cache_file, "r", encoding="utf-8") as handle:
        cache_payload = json.load(handle)
    cache_keys = set(cache_payload["files"].keys())
    assert os.path.normpath(str(fake_env["file_2024"])) not in cache_keys


# ---------------------------------------------------------------------------
# 6. Corrupt cache degrades
# ---------------------------------------------------------------------------

def test_corrupt_cache_degrades(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    cache_file.write_text("not json{")

    read_calls = []
    original = bank_income_module._process_tbc_foodmart_cashback_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_foodmart_cashback_file", tracker
    )
    bundle = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert len(read_calls) == 2  # both TBC files re-read
    assert bundle["total_ge"] == 390.0


# ---------------------------------------------------------------------------
# 7. Pattern change invalidates cache
# ---------------------------------------------------------------------------

def test_pattern_change_invalidates(fake_env, tmp_path, monkeypatch):
    """Simulate a code-level pattern change by monkeypatching the default
    tuple; the fingerprint covers it, so a shift must re-read all files.
    """
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    monkeypatch.setattr(
        bank_income_module,
        "FOODMART_CASHBACK_DEFAULT_PATTERNS",
        ("__will_never_match__",),
    )

    read_calls = []
    original = bank_income_module._process_tbc_foodmart_cashback_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_tbc_foodmart_cashback_file", tracker
    )
    bundle = collect_tbc_foodmart_cashback(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert len(read_calls) == 2  # fingerprint mismatch → re-read
    assert bundle["total_ge"] == 0.0  # new patterns match nothing
