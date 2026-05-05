"""Unit tests for `dashboard_pipeline.rsge_cache.upsert_rsge_cache`.

Covers the contract that supplier-side amendments on rs.ge (active →
cancelled, amount/comment edits) must overwrite the cached row instead of
being silently dropped as duplicates by the previous append-only-by-ID
implementation. The reconciliation page (`WaybillReconciliation.jsx`)
depends on the cache reflecting current rs.ge state to fire `ghost_ap` /
`amount_mismatch` flags.

No SOAP traffic — Waybill instances are constructed in-process and the
parquet root is monkeypatched to a tmp_path.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard_pipeline import rsge_cache
from dashboard_pipeline.rs_waybill_connector import Waybill


def _wb(
    *,
    wid: str,
    create_date: str,
    status: int = 1,
    full_amount: float = 100.0,
    close_date: str = "",
    waybill_number: str = "",
    seller_tin: str = "404123456",
    seller_name: str = "ტესტ მომწოდებელი",
    waybill_comment: str = "",
) -> Waybill:
    """Minimal Waybill builder with sane defaults for cache-shape testing."""
    return Waybill(
        id=wid,
        waybill_number=waybill_number or wid,
        create_date=create_date,
        status=status,
        type=2,
        seller_tin=seller_tin,
        seller_name=seller_name,
        buyer_tin="400333858",
        buyer_name="შპს ჯეო ფუდთაიმი",
        full_amount=full_amount,
        transport_coast=0.0,
        car_number="",
        driver_tin="",
        driver_name="",
        start_address="",
        end_address="",
        activate_date="",
        begin_date="",
        delivery_date="",
        close_date=close_date,
        seller_st=0,
        par_id=None,
        invoice_id=None,
        waybill_comment=waybill_comment,
        is_corrected=False,
        is_confirmed=False,
        raw={},
    )


@pytest.fixture
def isolated_cache(monkeypatch, tmp_path):
    """Redirect the rsge_cache module's parquet root to a per-test tmp dir."""
    cache_root = tmp_path / "cache"
    rsge_dir = cache_root / "rsge"
    monkeypatch.setattr(rsge_cache, "CACHE_ROOT", cache_root)
    monkeypatch.setattr(rsge_cache, "RSGE_DIR", rsge_dir)
    return rsge_dir


def _read_year(year: int) -> pd.DataFrame:
    """Read one year's cache without hidden columns."""
    return rsge_cache.read_rsge_cache(year)


def test_upsert_into_empty_cache_adds_all(isolated_cache):
    waybills = [
        _wb(wid="W1", create_date="2026-04-15T10:00:00", full_amount=200.0),
        _wb(wid="W2", create_date="2026-04-16T11:00:00", full_amount=350.0),
    ]
    result = rsge_cache.upsert_rsge_cache(waybills)
    assert result == {2026: {"added": 2, "updated": 0}}

    cached = _read_year(2026)
    assert sorted(cached["ID"].tolist()) == ["W1", "W2"]


def test_upsert_idempotent_when_unchanged(isolated_cache):
    """Re-fetching the same waybills must not bump `updated`."""
    waybills = [
        _wb(wid="W1", create_date="2026-04-15T10:00:00", full_amount=200.0),
    ]
    rsge_cache.upsert_rsge_cache(waybills)

    # Re-run with byte-identical input.
    result = rsge_cache.upsert_rsge_cache(waybills)
    assert result == {2026: {"added": 0, "updated": 0}}

    cached = _read_year(2026)
    assert len(cached) == 1


def test_upsert_replaces_status_change(isolated_cache):
    """Active → cancelled must overwrite the cached row."""
    create_iso = "2026-04-15T10:00:00"
    initial = [_wb(wid="W1", create_date=create_iso, status=1, full_amount=200.0)]
    rsge_cache.upsert_rsge_cache(initial)

    cancelled = [
        _wb(
            wid="W1",
            create_date=create_iso,
            status=-2,
            full_amount=200.0,
            close_date="2026-05-01T09:00:00",
        )
    ]
    result = rsge_cache.upsert_rsge_cache(cancelled)
    assert result == {2026: {"added": 0, "updated": 1}}

    cached = _read_year(2026)
    assert len(cached) == 1
    row = cached.iloc[0]
    assert row["ID"] == "W1"
    assert row["სტატუსი"] == "გაუქმებული"
    assert row["გაუქმების თარ."] == "2026-05-01 09:00:00"


def test_upsert_replaces_amount_change(isolated_cache):
    """Amount correction (200 → 150) must overwrite the cached row."""
    create_iso = "2026-04-15T10:00:00"
    rsge_cache.upsert_rsge_cache(
        [_wb(wid="W1", create_date=create_iso, full_amount=200.0)]
    )
    result = rsge_cache.upsert_rsge_cache(
        [_wb(wid="W1", create_date=create_iso, full_amount=150.0)]
    )
    assert result == {2026: {"added": 0, "updated": 1}}

    cached = _read_year(2026)
    assert len(cached) == 1
    assert cached.iloc[0]["თანხა"] == "150"


def test_upsert_mixed_new_and_changed(isolated_cache):
    """Batch with both new IDs and content-changed IDs splits counters."""
    rsge_cache.upsert_rsge_cache([
        _wb(wid="W1", create_date="2026-04-15T10:00:00", full_amount=200.0),
        _wb(wid="W2", create_date="2026-04-16T11:00:00", full_amount=300.0),
    ])

    second_batch = [
        # W1 unchanged → no update, no add
        _wb(wid="W1", create_date="2026-04-15T10:00:00", full_amount=200.0),
        # W2 amount changed → update
        _wb(wid="W2", create_date="2026-04-16T11:00:00", full_amount=275.0),
        # W3 new → add
        _wb(wid="W3", create_date="2026-04-17T12:00:00", full_amount=120.0),
        # W4 new → add
        _wb(wid="W4", create_date="2026-04-18T13:00:00", full_amount=80.0),
    ]
    result = rsge_cache.upsert_rsge_cache(second_batch)
    assert result == {2026: {"added": 2, "updated": 1}}

    cached = _read_year(2026)
    assert sorted(cached["ID"].tolist()) == ["W1", "W2", "W3", "W4"]
    w2_row = cached[cached["ID"] == "W2"].iloc[0]
    assert w2_row["თანხა"] == "275"


def test_upsert_year_partition_preserved(isolated_cache):
    """Waybills spanning multiple years update each partition independently."""
    result = rsge_cache.upsert_rsge_cache([
        _wb(wid="W2025", create_date="2025-12-30T10:00:00", full_amount=100.0),
        _wb(wid="W2026", create_date="2026-01-05T10:00:00", full_amount=200.0),
    ])
    assert result == {
        2025: {"added": 1, "updated": 0},
        2026: {"added": 1, "updated": 0},
    }

    assert _read_year(2025)["ID"].tolist() == ["W2025"]
    assert _read_year(2026)["ID"].tolist() == ["W2026"]


def test_upsert_empty_input_returns_empty(isolated_cache):
    assert rsge_cache.upsert_rsge_cache([]) == {}


def test_append_rsge_cache_compat_shim_returns_summed_int(isolated_cache):
    """Legacy `append_rsge_cache` keeps its `{year: int}` return shape."""
    rsge_cache.upsert_rsge_cache([
        _wb(wid="W1", create_date="2026-04-15T10:00:00", full_amount=200.0),
    ])
    result = rsge_cache.append_rsge_cache([
        _wb(wid="W1", create_date="2026-04-15T10:00:00", full_amount=999.0),  # update
        _wb(wid="W2", create_date="2026-04-16T11:00:00", full_amount=300.0),  # add
    ])
    # Return shape is {year: int} where int = added + updated.
    assert result == {2026: 2}
