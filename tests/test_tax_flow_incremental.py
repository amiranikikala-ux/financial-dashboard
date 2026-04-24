"""Integration tests for Tier 2 Sprint 3d tax_flow incremental cache.

Mirrors `test_samurneo_incremental.py` / `test_expense_categories_incremental.py`.
Covers the contract that `collect_tax_flow` must satisfy when
``use_cache=True``:

1. Cross-bank cache-hot bundle equals cache-cold bundle (BOG + TBC).
2. Plain (use_cache=False) bundle equals cached bundle.
3. Only changed files are re-read; unchanged files reuse cached payloads.
4. A newly-added file triggers a read on the next run; others reuse cache.
5. A file removed from disk drops out of the merged bundle and the cache.
6. A corrupt / malformed cache falls back to a full re-read (never crashes).
7. A config change (patterns) invalidates the cache via content_fingerprint.
8. Treasury-incoming markers survive cache round-trip on both banks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import bank_income as bank_income_module
from dashboard_pipeline.bank_income import collect_tax_flow


TBC_COLUMNS = ["თარიღი", "გასული თანხა", "შემოსული თანხა", "დანიშნულება"]
BOG_COLUMNS = ["თარიღი", "დებეტი", "კრედიტი", "დანიშნულება"]


def _write_tax_flow_config(script_dir: Path, *, patterns=None):
    cfg_dir = script_dir / "Financial_Analysis"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "tax_flow_patterns.json"
    payload = {"match_substrings": list(patterns) if patterns else []}
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
def fake_env(tmp_path, monkeypatch):
    """Two BOG files + two TBC files covering out / in / treasury_in rows."""
    # No config file → fall back to default patterns (includes "გადასახად").
    bog_dir = tmp_path / "Financial_Analysis" / "ბოგ ბანკი ამონაწერი"
    tbc_dir = tmp_path / "Financial_Analysis" / "თბს ბანკი ამონაწერი"
    bog_2023 = bog_dir / "2023.xlsx"
    bog_2024 = bog_dir / "2024.xlsx"
    tbc_2023 = tbc_dir / "2023.xlsx"
    tbc_2024 = tbc_dir / "2024.xlsx"

    _write_bog_xlsx(
        bog_2023,
        [
            # out (debit >0, matches "გადასახად")
            _bog_row("2023-05-10", 100.0, None, "საშემოსავლო გადასახადი"),
            # in non-treasury (credit >0, matches "ბიუჯეტ", no treasury marker)
            _bog_row("2023-06-15", None, 40.0, "ბიუჯეტიდან ჩარიცხვა ზოგადი"),
        ],
    )
    _write_bog_xlsx(
        bog_2024,
        [
            # treasury in (credit >0, matches pattern + treasury marker "tresge22")
            _bog_row(
                "2024-03-20",
                None,
                250.0,
                "revenue service TRESGE22 დაფინანსება",
            ),
        ],
    )
    _write_tbc_xlsx(
        tbc_2023,
        [
            # out + matches pattern
            _tbc_row("2023-07-01", 75.0, None, "გადასახადი ბიუჯეტში"),
        ],
    )
    _write_tbc_xlsx(
        tbc_2024,
        [
            # treasury in (credit >0, "სახელმწიფო ხაზინა" marker)
            _tbc_row(
                "2024-09-12",
                None,
                500.0,
                "სახელმწიფო ხაზინა rs.ge დაბრუნება",
            ),
            # non-matching row (should be skipped)
            _tbc_row("2024-10-01", None, 999.0, "რაიმე სხვა უცხო რიგი"),
        ],
    )
    bog_files = [str(bog_2023), str(bog_2024)]
    tbc_files = [str(tbc_2023), str(tbc_2024)]
    monkeypatch.setattr(
        bank_income_module,
        "list_bog_bank_statement_xlsx",
        lambda: list(bog_files),
    )
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(tbc_files),
    )
    return {
        "script_dir": str(tmp_path),
        "bog_dir": bog_dir,
        "tbc_dir": tbc_dir,
        "bog_files": bog_files,
        "tbc_files": tbc_files,
        "bog_2023": bog_2023,
        "bog_2024": bog_2024,
        "tbc_2023": tbc_2023,
        "tbc_2024": tbc_2024,
    }


def _comparable(bundle):
    return json.loads(json.dumps(bundle, default=str))


# ---------------------------------------------------------------------------
# 1. Cross-bank cold vs hot equivalence
# ---------------------------------------------------------------------------

def test_cold_vs_hot_equivalence(fake_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    hot = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert _comparable(cold) == _comparable(hot)
    # out = 100 (BOG 2023) + 75 (TBC 2023)
    assert cold["out_total_ge"] == 175.0
    # in = 40 (BOG 2023) + 250 (BOG 2024 treasury) + 500 (TBC 2024 treasury)
    assert cold["in_total_ge"] == 790.0
    # treasury_in = 250 (BOG) + 500 (TBC)
    assert cold["treasury_in_total_ge"] == 750.0
    assert cold["out_line_count"] == 2
    assert cold["in_line_count"] == 3
    assert cold["treasury_in_line_count"] == 2


# ---------------------------------------------------------------------------
# 2. Plain (use_cache=False) equals cached bundle
# ---------------------------------------------------------------------------

def test_plain_vs_cached_equivalence(fake_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    plain = collect_tax_flow(fake_env["script_dir"], use_cache=False)
    cached = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert _comparable(plain) == _comparable(cached)


# ---------------------------------------------------------------------------
# 3. Only changed file is re-read
# ---------------------------------------------------------------------------

def test_only_changed_file_is_reread(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    bog_calls = []
    tbc_calls = []
    original_bog = bank_income_module._process_bog_tax_flow_file
    original_tbc = bank_income_module._process_tbc_tax_flow_file

    def bog_tracker(path, **kwargs):
        bog_calls.append(path)
        return original_bog(path, **kwargs)

    def tbc_tracker(path, **kwargs):
        tbc_calls.append(path)
        return original_tbc(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_bog_tax_flow_file", bog_tracker
    )
    monkeypatch.setattr(
        bank_income_module, "_process_tbc_tax_flow_file", tbc_tracker
    )

    # Mutate only BOG 2023; the other three files stay untouched.
    _write_bog_xlsx(
        fake_env["bog_2023"],
        [
            _bog_row("2023-05-10", 100.0, None, "საშემოსავლო გადასახადი"),
            _bog_row("2023-08-01", 30.0, None, "გადასახადი დამატებითი"),
        ],
    )

    bundle = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert bog_calls == [str(fake_env["bog_2023"])]
    assert tbc_calls == []
    # out changed: 100 + 30 (BOG 2023) + 75 (TBC 2023 cached) = 205
    assert bundle["out_total_ge"] == 205.0
    # in unchanged: 250 (BOG cached) + 500 (TBC cached) = 750 (lost 40 from removed row)
    assert bundle["in_total_ge"] == 750.0
    assert bundle["treasury_in_total_ge"] == 750.0


# ---------------------------------------------------------------------------
# 4. New file triggers read, others reuse cache
# ---------------------------------------------------------------------------

def test_new_file_triggers_read_others_reuse(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    new_tbc = fake_env["tbc_dir"] / "2025.xlsx"
    _write_tbc_xlsx(
        new_tbc,
        [_tbc_row("2025-01-05", 999.0, None, "გადასახადი 2025")],
    )
    all_tbc = fake_env["tbc_files"] + [str(new_tbc)]
    monkeypatch.setattr(
        bank_income_module,
        "list_tbc_bank_statement_xlsx",
        lambda: list(all_tbc),
    )

    bog_calls = []
    tbc_calls = []
    original_bog = bank_income_module._process_bog_tax_flow_file
    original_tbc = bank_income_module._process_tbc_tax_flow_file

    def bog_tracker(path, **kwargs):
        bog_calls.append(path)
        return original_bog(path, **kwargs)

    def tbc_tracker(path, **kwargs):
        tbc_calls.append(path)
        return original_tbc(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_bog_tax_flow_file", bog_tracker
    )
    monkeypatch.setattr(
        bank_income_module, "_process_tbc_tax_flow_file", tbc_tracker
    )

    bundle = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert bog_calls == []
    assert tbc_calls == [str(new_tbc)]
    # out: 100 (BOG 2023) + 75 (TBC 2023) + 999 (new) = 1174
    assert bundle["out_total_ge"] == 1174.0


# ---------------------------------------------------------------------------
# 5. Deleted file drops from bundle and cache
# ---------------------------------------------------------------------------

def test_deleted_file_drops_from_bundle(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    os.remove(fake_env["bog_2024"])
    remaining_bog = [str(fake_env["bog_2023"])]
    monkeypatch.setattr(
        bank_income_module,
        "list_bog_bank_statement_xlsx",
        lambda: list(remaining_bog),
    )

    bundle = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    # bog_2024 contributed 250 in_total + 250 treasury_in; removing it:
    # in = 40 (BOG 2023 in) + 500 (TBC 2024 treasury) = 540
    assert bundle["in_total_ge"] == 540.0
    # treasury_in = 500 (only TBC 2024)
    assert bundle["treasury_in_total_ge"] == 500.0
    assert bundle["treasury_in_line_count"] == 1

    with open(cache_file, "r", encoding="utf-8") as handle:
        cache_payload = json.load(handle)
    cache_keys = set(cache_payload["files"].keys())
    assert os.path.normpath(str(fake_env["bog_2024"])) not in cache_keys


# ---------------------------------------------------------------------------
# 6. Corrupt cache degrades to full re-read
# ---------------------------------------------------------------------------

def test_corrupt_cache_degrades_to_full_reread(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    cache_file.write_text("this is definitely not json{")

    bog_calls = []
    tbc_calls = []
    original_bog = bank_income_module._process_bog_tax_flow_file
    original_tbc = bank_income_module._process_tbc_tax_flow_file

    def bog_tracker(path, **kwargs):
        bog_calls.append(path)
        return original_bog(path, **kwargs)

    def tbc_tracker(path, **kwargs):
        tbc_calls.append(path)
        return original_tbc(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_bog_tax_flow_file", bog_tracker
    )
    monkeypatch.setattr(
        bank_income_module, "_process_tbc_tax_flow_file", tbc_tracker
    )

    bundle = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    assert len(bog_calls) == 2  # both BOG files re-read
    assert len(tbc_calls) == 2  # both TBC files re-read
    assert bundle["out_total_ge"] == 175.0
    assert bundle["in_total_ge"] == 790.0


# ---------------------------------------------------------------------------
# 7. Config change invalidates cache
# ---------------------------------------------------------------------------

def test_config_change_invalidates_cache(fake_env, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    # Prime with default patterns (no config file → defaults apply).
    collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    # Write a config that NEVER matches anything. Fingerprint must detect
    # the flip and re-read every file (not serve cached rows from default
    # patterns).
    _write_tax_flow_config(
        Path(fake_env["script_dir"]),
        patterns=["__will_never_match__"],
    )

    bog_calls = []
    tbc_calls = []
    original_bog = bank_income_module._process_bog_tax_flow_file
    original_tbc = bank_income_module._process_tbc_tax_flow_file

    def bog_tracker(path, **kwargs):
        bog_calls.append(path)
        return original_bog(path, **kwargs)

    def tbc_tracker(path, **kwargs):
        tbc_calls.append(path)
        return original_tbc(path, **kwargs)

    monkeypatch.setattr(
        bank_income_module, "_process_bog_tax_flow_file", bog_tracker
    )
    monkeypatch.setattr(
        bank_income_module, "_process_tbc_tax_flow_file", tbc_tracker
    )

    bundle = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    # Fingerprint mismatch → all four files re-read.
    assert len(bog_calls) == 2
    assert len(tbc_calls) == 2
    # New config filters everything out.
    assert bundle["out_total_ge"] == 0.0
    assert bundle["in_total_ge"] == 0.0
    assert bundle["treasury_in_total_ge"] == 0.0


# ---------------------------------------------------------------------------
# 8. Treasury-incoming markers survive cache round-trip (BOG + TBC)
# ---------------------------------------------------------------------------

def test_treasury_markers_survive_cache_roundtrip(fake_env, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )
    hot = collect_tax_flow(
        fake_env["script_dir"], use_cache=True, cache_path=str(cache_file)
    )

    # Treasury-in rows must carry the special direction label and the bank
    # tag that was assigned at per-file processing time.
    banks = {r.get("ბანკი") for r in cold["treasury_in_rows_preview"]}
    assert banks == {"BOG", "TBC"}
    directions = {r.get("მიმართულება") for r in cold["treasury_in_rows_preview"]}
    assert directions == {"სახელმწიფო ხაზინიდან ჩარიცხული"}

    # Hot-cache round-trip preserves the row set 1:1.
    assert _comparable(cold["treasury_in_rows_preview"]) == _comparable(
        hot["treasury_in_rows_preview"]
    )
    # Totals match treasury_in_total_ge sum.
    total_from_rows = sum(
        float(r.get("თანხა") or 0) for r in cold["treasury_in_rows_preview"]
    )
    assert total_from_rows == cold["treasury_in_total_ge"]
