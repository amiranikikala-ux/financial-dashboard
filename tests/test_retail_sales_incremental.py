"""Integration tests for retail_sales Tier 2 Sprint 2 incremental cache.

Covers the contract that `collect_retail_sales_bundle(use_cache=True)`
must satisfy:

1. Cache-hot bundle equals cache-cold bundle (same inputs → same output,
   regardless of whether Excel was re-read or replayed from cache).
2. Only changed files are re-read; unchanged files reuse cached payloads.
3. A newly-added file triggers a read on the next run; others reuse cache.
4. A file removed from disk drops out of the merged bundle gracefully.
5. A corrupt / malformed cache does NOT crash — falls back to full re-read.
6. When a period filter is applied, the cache is bypassed entirely.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from dashboard_pipeline import retail_sales as retail_sales_module
from dashboard_pipeline.retail_sales import collect_retail_sales_bundle


RETAIL_COLUMNS = [
    "კოდი",
    "შტრიხკოდი",
    "დასახელება",
    "ერთეული",
    "რაოდენობა",
    "ფასი",
    "თვითღირებულება",
    "მოგება",
    "დრო",
    "ობიექტი",
    "ქვეჯგუფი",
]


def _write_retail_xlsx(path: Path, rows):
    """Write a retail_sales-shaped Excel file at `path` from simple row dicts."""
    df = pd.DataFrame(rows, columns=RETAIL_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _row(code, name, qty, price, cost, profit, dt, obj, category, barcode="", unit=""):
    return {
        "კოდი": code,
        "შტრიხკოდი": barcode,
        "დასახელება": name,
        "ერთეული": unit,
        "რაოდენობა": qty,
        "ფასი": price,
        "თვითღირებულება": cost,
        "მოგება": profit,
        "დრო": dt,
        "ობიექტი": obj,
        "ქვეჯგუფი": category,
    }


def _ozurgeti_rows():
    return [
        _row("P1", "პური", 10, 100.0, 60.0, 40.0, "2026-01-10 09:00", "ოზურგეთი", "პური"),
        _row("P2", "რძე", 5, 50.0, 35.0, 15.0, "2026-01-12 14:30", "ოზურგეთი", "რძე"),
    ]


def _dvabzu_rows():
    return [
        _row("P3", "შაქარი", 20, 40.0, 28.0, 12.0, "2026-01-11 10:00", "დვაბზუ", "შაქარი"),
    ]


@pytest.fixture
def fake_retail_files(tmp_path, monkeypatch):
    """Create two retail Excel files under tmp_path and stub the file lister.

    Folder names include "ოზურგეთი" / "დვაბზუ" so _object_from_path picks
    the right fallback object.
    """
    oz_dir = tmp_path / "გაყიდული პროდუქტები სოფ ოზურგეთი"
    dv_dir = tmp_path / "გაყიდული პროდუქტები სოფ დვაბზუ"
    oz_file = oz_dir / "2026-01.xlsx"
    dv_file = dv_dir / "2026-01.xlsx"
    _write_retail_xlsx(oz_file, _ozurgeti_rows())
    _write_retail_xlsx(dv_file, _dvabzu_rows())

    files = [str(oz_file), str(dv_file)]
    monkeypatch.setattr(
        retail_sales_module, "list_retail_sales_files", lambda: list(files)
    )
    return {
        "tmp_path": tmp_path,
        "files": files,
        "ozurgeti_file": oz_file,
        "dvabzu_file": dv_file,
    }


def _comparable(bundle):
    """Strip runtime-variable fields so two bundles can be equated."""
    copy = json.loads(json.dumps(bundle, default=str))
    # rows_preview order ties are broken by product_name string collation;
    # since product_names may repeat across cache-cold and cache-hot runs
    # and ties can land in different orders, compare as multisets.
    copy["rows_preview"] = sorted(
        copy.get("rows_preview") or [],
        key=lambda r: (r.get("date") or "", str(r.get("product_name") or "")),
    )
    return copy


def _run_with_cache(cache_path, object_mapping=None, period_filter=None):
    return collect_retail_sales_bundle(
        object_mapping=object_mapping,
        period_filter=period_filter,
        use_cache=True,
        cache_path=str(cache_path),
    )


def _run_without_cache(object_mapping=None, period_filter=None):
    return collect_retail_sales_bundle(
        object_mapping=object_mapping,
        period_filter=period_filter,
        use_cache=False,
    )


# ---------------------------------------------------------------------------
# 1. Equivalence: cache-cold bundle == cache-hot bundle
# ---------------------------------------------------------------------------

def test_cache_cold_vs_cache_hot_equivalence(fake_retail_files, tmp_path):
    cache_file = tmp_path / ".pipeline_cache.json"
    cold = _run_with_cache(cache_file)
    # Second run: all files unchanged → payloads come from cache
    hot = _run_with_cache(cache_file)
    assert _comparable(cold) == _comparable(hot)
    # Core totals must match exactly, not just within tolerance.
    assert cold["overall"]["row_count"] == hot["overall"]["row_count"] == 3
    assert cold["overall"]["revenue_ge"] == hot["overall"]["revenue_ge"]
    assert cold["files_read_count"] == 2


def test_no_cache_vs_cache_hot_equivalence(fake_retail_files, tmp_path):
    """Plain no-cache run and cache-hot run must produce the same bundle."""
    cache_file = tmp_path / ".pipeline_cache.json"
    # Prime the cache
    _run_with_cache(cache_file)
    # Now compare hot-cache vs no-cache
    hot = _run_with_cache(cache_file)
    plain = _run_without_cache()
    assert _comparable(hot) == _comparable(plain)


def test_only_changed_file_is_reread(fake_retail_files, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    _run_with_cache(cache_file)  # prime cache (both files read)

    read_calls = []
    original = retail_sales_module._process_retail_sales_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        retail_sales_module, "_process_retail_sales_file", tracker
    )

    # Touch + edit ozurgeti file so its signature changes
    oz_file = fake_retail_files["ozurgeti_file"]
    new_rows = _ozurgeti_rows() + [
        _row("P4", "ყველი", 2, 80.0, 50.0, 30.0, "2026-01-15 11:00", "ოზურგეთი", "ყველი"),
    ]
    _write_retail_xlsx(oz_file, new_rows)

    _run_with_cache(cache_file)
    assert read_calls == [str(oz_file)]  # dvabzu file was NOT re-read


def test_new_file_triggers_read_others_reuse(fake_retail_files, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    _run_with_cache(cache_file)  # prime cache

    # Add a brand-new file and update the file list
    new_file = (
        fake_retail_files["tmp_path"]
        / "გაყიდული პროდუქტები სოფ ოზურგეთი"
        / "2026-02.xlsx"
    )
    _write_retail_xlsx(
        new_file,
        [_row("P9", "კარაქი", 3, 60.0, 40.0, 20.0, "2026-02-03 09:00", "ოზურგეთი", "კარაქი")],
    )
    all_files = fake_retail_files["files"] + [str(new_file)]
    monkeypatch.setattr(
        retail_sales_module, "list_retail_sales_files", lambda: list(all_files)
    )

    read_calls = []
    original = retail_sales_module._process_retail_sales_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        retail_sales_module, "_process_retail_sales_file", tracker
    )

    bundle = _run_with_cache(cache_file)
    assert read_calls == [str(new_file)]
    assert bundle["files_read_count"] == 3
    assert bundle["overall"]["row_count"] == 4  # 3 prior + 1 new


def test_deleted_file_drops_from_bundle(fake_retail_files, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    _run_with_cache(cache_file)  # prime cache

    # Remove the ozurgeti file from disk AND from the listing
    oz_file = fake_retail_files["ozurgeti_file"]
    os.remove(oz_file)
    remaining = [fake_retail_files["files"][1]]  # dvabzu only
    monkeypatch.setattr(
        retail_sales_module, "list_retail_sales_files", lambda: list(remaining)
    )

    bundle = _run_with_cache(cache_file)
    assert bundle["files_read_count"] == 1
    assert bundle["overall"]["row_count"] == 1  # only dvabzu's one row

    # Cache must no longer retain the deleted file so it cannot leak.
    with open(cache_file, "r", encoding="utf-8") as handle:
        cache_payload = json.load(handle)
    cache_keys = set(cache_payload["files"].keys())
    assert os.path.normpath(str(oz_file)) not in cache_keys


def test_corrupt_cache_degrades_to_full_reread(fake_retail_files, tmp_path, monkeypatch):
    cache_file = tmp_path / ".pipeline_cache.json"
    cache_file.write_text("this is definitely not json{")

    read_calls = []
    original = retail_sales_module._process_retail_sales_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        retail_sales_module, "_process_retail_sales_file", tracker
    )

    bundle = _run_with_cache(cache_file)
    # Both files were re-read — corrupt cache never gets honored.
    assert len(read_calls) == 2
    assert bundle["files_read_count"] == 2


def test_period_filter_bypasses_cache(fake_retail_files, tmp_path, monkeypatch):
    """With a period filter applied, cache must not be consulted — the
    payload semantics differ (rows outside the window are excluded)."""
    cache_file = tmp_path / ".pipeline_cache.json"
    _run_with_cache(cache_file)  # prime cache (no filter)

    read_calls = []
    original = retail_sales_module._process_retail_sales_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        retail_sales_module, "_process_retail_sales_file", tracker
    )

    # Build a 1-day period_filter that only includes the dvabzu row on Jan 11
    period_filter = {
        "applied": True,
        "from_ts": pd.Timestamp("2026-01-11 00:00:00"),
        "to_ts": pd.Timestamp("2026-01-11 23:59:59"),
    }
    bundle = collect_retail_sales_bundle(
        period_filter=period_filter,
        use_cache=True,
        cache_path=str(cache_file),
    )
    # Both files are fully re-read because cache is bypassed under a filter.
    assert len(read_calls) == 2
    # Only the single dvabzu row falls within the window.
    assert bundle["overall"]["row_count"] == 1


def test_content_fingerprint_invalidates_cache_when_mapping_changes(
    fake_retail_files, tmp_path, monkeypatch
):
    cache_file = tmp_path / ".pipeline_cache.json"
    _run_with_cache(cache_file, object_mapping={"default": "A"})

    read_calls = []
    original = retail_sales_module._process_retail_sales_file

    def tracker(path, **kwargs):
        read_calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(
        retail_sales_module, "_process_retail_sales_file", tracker
    )

    # Different object_mapping → different content_fingerprint → cache
    # drops to empty on load, all files re-read.
    _run_with_cache(cache_file, object_mapping={"default": "B"})
    assert len(read_calls) == 2
