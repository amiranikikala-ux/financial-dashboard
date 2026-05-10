"""Sprint §8 — dead-stock aggregation in synthesize_from_megaplus.

Verifies the combined-view aggregator pools per-store dead-stock buckets
correctly and that per_object_view passes through the raw per-store
dead_stock_summary unchanged. Backend SQL block in megaplus_backup.py is
covered upstream by live spot-checks (see SPRINT_DEAD_STOCK_*_PREVIEW.md);
this test focuses on the deterministic combine logic in retail_sales.py.
"""
from __future__ import annotations

from dashboard_pipeline.retail_sales import synthesize_from_megaplus


def _store_rollup(store_id, dead_stock_summary):
    """Minimal rollup with only dead_stock_summary populated.

    All other accessors in synthesize_from_megaplus tolerate empty rollups
    via `.get(key) or []` / `or {}`, so this is sufficient for combining
    the dead_stock_summary block.
    """
    return {
        "store_id": store_id,
        "data_range": {"min_timestamp": "2024-01-01", "max_timestamp": "2026-05-09"},
        "totals": {"revenue": 0, "cogs": 0, "profit": 0, "sale_lines": 0},
        "dead_stock_summary": dead_stock_summary,
    }


def _make_item(barcode, qty, getprice, last_sale_date=None):
    """Synthetic dead-stock item matching backend shape."""
    stock_value = qty * getprice
    return {
        "product_id": int(barcode[-4:]) if barcode[-4:].isdigit() else 0,
        "product_code": "",
        "barcode": barcode,
        "product_name": f"item-{barcode}",
        "category": "test",
        "qty": qty,
        "getprice": getprice,
        "sellprice": getprice * 1.5,
        "stock_value": stock_value,
        "active": 1,
        "last_sale_date": last_sale_date,
        "days_since_sale": None if last_sale_date is None else 400,
    }


def _ds_summary(snapshot_date, total_value, dead_value, buckets, neg_alert=None):
    return {
        "snapshot_date": snapshot_date,
        "total_stock_value": total_value,
        "dead_stock_value": dead_value,
        "dead_stock_pct": (dead_value / total_value * 100) if total_value else 0.0,
        "buckets": buckets,
        "negative_stock_alert": neg_alert or {
            "count": 0, "abs_value_total": 0.0, "min_qty": 0.0, "top_items": [],
        },
    }


def _bucket(items, never_sold_count=0):
    return {
        "count": len(items),
        "stock_value": sum(it["stock_value"] for it in items),
        "never_sold_count": never_sold_count,
        "top_items": items,
    }


def _two_store_live(ds_a, ds_b):
    return {
        "stores": {
            "1329": _store_rollup("1329", ds_a),
            "1301": _store_rollup("1301", ds_b),
        }
    }


def test_combined_totals_sum_across_stores():
    ds_a = _ds_summary("2026-05-09T10:00:00", 100_000, 30_000, {
        "dead_365d_plus":   _bucket([_make_item("8001000000001", 100, 10)]),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    ds_b = _ds_summary("2026-05-09T11:00:00", 80_000, 20_000, {
        "dead_365d_plus":   _bucket([_make_item("8001000000002", 50, 20)]),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    out = synthesize_from_megaplus(_two_store_live(ds_a, ds_b))
    combined = out["dead_stock_summary"]
    assert combined["total_stock_value"] == 180_000
    assert combined["dead_stock_value"] == 50_000
    assert round(combined["dead_stock_pct"], 2) == round(50_000 / 180_000 * 100, 2)


def test_combined_bucket_counts_sum_across_stores():
    items_a = [_make_item("8001000000001", 100, 10), _make_item("8001000000002", 50, 5)]
    items_b = [_make_item("8001000000003", 30, 8)]
    ds_a = _ds_summary("2026-05-09", 1000, 1250, {
        "dead_365d_plus":   _bucket(items_a, never_sold_count=1),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    ds_b = _ds_summary("2026-05-09", 500, 240, {
        "dead_365d_plus":   _bucket(items_b, never_sold_count=0),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    out = synthesize_from_megaplus(_two_store_live(ds_a, ds_b))
    bkt = out["dead_stock_summary"]["buckets"]["dead_365d_plus"]
    assert bkt["count"] == 3
    assert bkt["never_sold_count"] == 1
    assert bkt["stock_value"] == 1000 + 250 + 240


def test_combined_top_items_carry_store_label():
    items_a = [_make_item("8001000000001", 100, 10)]   # stock_value 1000
    items_b = [_make_item("8001000000002", 100, 25)]   # stock_value 2500 → ranks first
    ds_a = _ds_summary("2026-05-09", 5000, 1000, {
        "dead_365d_plus":   _bucket(items_a),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    ds_b = _ds_summary("2026-05-09", 5000, 2500, {
        "dead_365d_plus":   _bucket(items_b),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    out = synthesize_from_megaplus(_two_store_live(ds_a, ds_b))
    top = out["dead_stock_summary"]["buckets"]["dead_365d_plus"]["top_items"]
    assert len(top) == 2
    # Higher stock_value (2500) ranks first; that came from store 1301 = ოზურგეთი.
    assert top[0]["stock_value"] == 2500
    assert top[0]["store"] == "ოზურგეთი"
    assert top[1]["store"] == "დვაბზუ"


def test_combined_negative_stock_alert():
    neg_a = {
        "count": 5, "abs_value_total": 1500.0, "min_qty": -200.0,
        "top_items": [{**_make_item("8001000000001", -50, 10), "stock_value": -500}],
    }
    neg_b = {
        "count": 3, "abs_value_total": 800.0, "min_qty": -50.0,
        "top_items": [{**_make_item("8001000000002", -30, 5), "stock_value": -150}],
    }
    empty_buckets = {
        k: ({"count": 0, "stock_value": 0.0, "never_sold_count": 0} if k == "active_under_90d" else _bucket([]))
        for k in ("dead_365d_plus", "dead_180_365d", "slow_90_180d", "active_under_90d", "free_stock")
    }
    ds_a = _ds_summary("2026-05-09", 0, 0, empty_buckets, neg_alert=neg_a)
    ds_b = _ds_summary("2026-05-09", 0, 0, empty_buckets, neg_alert=neg_b)
    out = synthesize_from_megaplus(_two_store_live(ds_a, ds_b))
    nsa = out["dead_stock_summary"]["negative_stock_alert"]
    assert nsa["count"] == 8
    assert nsa["abs_value_total"] == 2300.0
    # min_qty is the most-negative across stores
    assert nsa["min_qty"] == -200.0
    assert len(nsa["top_items"]) == 2
    # Sorted by abs(stock_value) DESC — −500 ranks before −150
    assert nsa["top_items"][0]["stock_value"] == -500


def test_per_object_view_carries_raw_dead_stock_summary():
    ds_a = _ds_summary("2026-05-09T10:00:00", 100_000, 30_000, {
        "dead_365d_plus":   _bucket([_make_item("8001000000001", 100, 10)]),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    ds_b = _ds_summary("2026-05-09T11:00:00", 80_000, 20_000, {
        "dead_365d_plus":   _bucket([_make_item("8001000000002", 50, 20)]),
        "dead_180_365d":    _bucket([]),
        "slow_90_180d":     _bucket([]),
        "active_under_90d": {"count": 0, "stock_value": 0.0, "never_sold_count": 0},
        "free_stock":       _bucket([]),
    })
    out = synthesize_from_megaplus(_two_store_live(ds_a, ds_b))
    pov = out["per_object_view"]
    assert "დვაბზუ" in pov and "ოზურგეთი" in pov
    # Per-store snapshot_date matches the input rollup's snapshot_date.
    assert pov["დვაბზუ"]["dead_stock_summary"]["snapshot_date"] == "2026-05-09T10:00:00"
    assert pov["ოზურგეთი"]["dead_stock_summary"]["snapshot_date"] == "2026-05-09T11:00:00"
    # Per-store totals equal the input rollup's totals (no aggregation).
    assert pov["დვაბზუ"]["dead_stock_summary"]["total_stock_value"] == 100_000
    assert pov["ოზურგეთი"]["dead_stock_summary"]["total_stock_value"] == 80_000


def test_combined_snapshot_date_uses_latest():
    empty_buckets = {
        k: ({"count": 0, "stock_value": 0.0, "never_sold_count": 0} if k == "active_under_90d" else _bucket([]))
        for k in ("dead_365d_plus", "dead_180_365d", "slow_90_180d", "active_under_90d", "free_stock")
    }
    ds_a = _ds_summary("2026-05-08T23:00:00", 0, 0, empty_buckets)
    ds_b = _ds_summary("2026-05-10T01:00:00", 0, 0, empty_buckets)
    out = synthesize_from_megaplus(_two_store_live(ds_a, ds_b))
    combined = out["dead_stock_summary"]
    # Latest snapshot wins; per-store map preserves both.
    assert combined["snapshot_date"] == "2026-05-10T01:00:00"
    assert combined["snapshot_dates_per_store"]["დვაბზუ"] == "2026-05-08T23:00:00"
    assert combined["snapshot_dates_per_store"]["ოზურგეთი"] == "2026-05-10T01:00:00"


def test_dead_stock_pct_zero_when_no_stock():
    empty_buckets = {
        k: ({"count": 0, "stock_value": 0.0, "never_sold_count": 0} if k == "active_under_90d" else _bucket([]))
        for k in ("dead_365d_plus", "dead_180_365d", "slow_90_180d", "active_under_90d", "free_stock")
    }
    ds_zero = _ds_summary("2026-05-09", 0, 0, empty_buckets)
    out = synthesize_from_megaplus(_two_store_live(ds_zero, ds_zero))
    combined = out["dead_stock_summary"]
    # Avoid div-by-zero — pct must coerce to 0.0 when total_stock_value == 0.
    assert combined["dead_stock_pct"] == 0.0
