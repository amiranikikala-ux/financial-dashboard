"""Unit tests for waybill_reconciliation module."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard_pipeline.waybill_reconciliation import (
    classify_destination,
    parse_g_time,
    reconcile,
)


# ─────────────────────────────────────── classify_destination ──────────────────


@pytest.mark.parametrize("addr,expected", [
    ("ლანჩხუთი დვაბზუ", "1329"),
    ("ოზურგეთი, სოფ. დვაბზა", "1329"),  # typo variant — village is დვაბზუ
    ("ოზურგეთი, სოფ.დვაბზა", "1329"),   # without space
    ("ქ. ოზურგეთი სოფ. დვაბზეე", "1329"),  # another typo variant
    ("ოზურგეთი ს. ზედა დვაბზუ", "1329"),  # mixed — Lactalis pattern
    ("სოფ.ოზურგეთი (ოზურგეთი - ნინოშვილი - ლესა)", "1301"),
    ("ქ.ოზურგეთი ნინოშვილი-ლესა", "1301"),
    ("თბილისი, ა. ბარამიძის ქ. 7", "closed"),
    ("თბილისი, ალექსანდრე ბარამიძის ქ. 007", "closed"),
    ("ისაკიანის N:1", "closed"),
    ("ფოთი, ფარნავაზ მეფის ქ.1", "unknown"),
    (None, "unknown"),
    ("", "unknown"),
])
def test_classify_destination(addr, expected):
    assert classify_destination(addr) == expected


# ─────────────────────────────────────── parse_g_time ──────────────────────────


@pytest.mark.parametrize("g_time,expected_str", [
    (2403250001, "2024-03-25"),
    (2507290022, "2025-07-29"),
    ("2403250001", "2024-03-25"),
    (None, None),
    ("invalid", None),
])
def test_parse_g_time(g_time, expected_str):
    result = parse_g_time(g_time)
    if expected_str is None:
        assert result is None
    else:
        assert result.strftime("%Y-%m-%d") == expected_str


# ─────────────────────────────────────── reconcile — empty input ───────────────


def test_reconcile_empty():
    bundle = reconcile(pd.DataFrame(), {})
    assert bundle["totals"]["missing"] == 0
    assert bundle["missing"] == []
    assert bundle["by_supplier"] == []


# ─────────────────────────────────────── reconcile — fixture builders ──────────


def _rs_row(zed, supplier, amount, type_="ტრანსპორტირებით",
            status="აქტიური", destination="ლანჩხუთი დვაბზუ",
            tax_id="111111111", act_date="2024-01-15 10:00",
            cancel_date=None):
    return {
        "zed": zed,
        "zed_base": zed.split("/")[0],
        "status": status,
        "type": type_,
        "tax_id": tax_id,
        "supplier_name": supplier,
        "amount": amount,
        "act_date": pd.Timestamp(act_date),
        "cancel_date": pd.Timestamp(cancel_date) if cancel_date else pd.NaT,
        "destination": destination,
        "source_file": "test.xls",
    }


def _make_rs_df(rows):
    return pd.DataFrame(rows)


def _store_data(get_rows=None, gacera_rows=None, store_id="1329"):
    return {
        "get": get_rows or [],
        "gacera": gacera_rows or [],
        "store_id": store_id,
    }


# ─────────────────────────────────────── category — missing ────────────────────


def test_missing_category_active_store():
    rs = _make_rs_df([
        _rs_row("0123456789", "შპს ტესტი", 100.0, destination="ლანჩხუთი დვაბზუ"),
    ])
    bundle = reconcile(rs, {"1329": _store_data()})
    assert bundle["totals"]["missing"] == 1
    assert bundle["missing"][0]["zed"] == "0123456789"
    assert bundle["missing"][0]["amount"] == 100.0


def test_missing_filtered_for_closed_store():
    rs = _make_rs_df([
        _rs_row("0123456789", "შპს ტესტი", 100.0, destination="თბილისი, ბარამიძის 7"),
    ])
    bundle = reconcile(rs, {"1329": _store_data()})
    assert bundle["totals"]["missing"] == 0
    assert bundle["totals"]["filtered_closed_stores"] == 1


# ─────────────────────────────────────── category — received ───────────────────


def test_received_in_get_no_problem():
    rs = _make_rs_df([
        _rs_row("0123456789", "შპს ტესტი", 100.0),
    ])
    store = _store_data(get_rows=[
        {"zed": "0123456789", "tax_id": "111111111", "total": 100.0, "date": "2024-01-15"},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["missing"] == 0
    assert bundle["totals"]["amount_mismatch"] == 0


# ─────────────────────────────────────── category — amount_mismatch ────────────


def test_amount_mismatch_get():
    rs = _make_rs_df([
        _rs_row("0123456789", "შპს ტესტი", 100.0),
    ])
    store = _store_data(get_rows=[
        {"zed": "0123456789", "tax_id": "111111111", "total": 95.0, "date": "2024-01-15"},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["amount_mismatch"] == 1
    row = bundle["amount_mismatch"][0]
    assert row["amount"] == 100.0
    assert row["get_total"] == 95.0


def test_amount_within_tolerance_passes():
    rs = _make_rs_df([
        _rs_row("0123456789", "შპს ტესტი", 1000.0),
    ])
    store = _store_data(get_rows=[
        {"zed": "0123456789", "tax_id": "111111111", "total": 1004.0, "date": "2024-01-15"},
    ])
    bundle = reconcile(rs, {"1329": store})
    # within 0.5% (5₾) tolerance
    assert bundle["totals"]["amount_mismatch"] == 0


# ─────────────────────────────────────── category — returns ────────────────────


def test_return_with_sign_flip_matches_gacera():
    """rs.ge negative + GACERA positive of same magnitude = matched, no flag."""
    rs = _make_rs_df([
        _rs_row("0820382602", "შპს იფქლი", -6.39, type_="უკან დაბრუნება"),
    ])
    store = _store_data(gacera_rows=[
        {"zed": "0820382602", "orig_zed": None, "tax_id": "200179118", "total": 6.39},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["returns_not_recorded"] == 0


def test_return_not_in_gacera_flagged():
    rs = _make_rs_df([
        _rs_row("0820382602", "შპს იფქლი", -6.39, type_="უკან დაბრუნება"),
    ])
    bundle = reconcile(rs, {"1329": _store_data()})
    assert bundle["totals"]["returns_not_recorded"] == 1


# ─────────────────────────────────────── category — sub-waybills ───────────────


def test_sub_waybill_not_recorded():
    rs = _make_rs_df([
        _rs_row("0789696472/6", "შპს იფქლი", 9.30, type_="ქვე-ზედნადები"),
    ])
    bundle = reconcile(rs, {"1329": _store_data()})
    assert bundle["totals"]["sub_waybills_not_recorded"] == 1


# ─────────────────────────────────────── category — ghost AP ───────────────────


def test_ghost_ap_cancelled_rs_in_get():
    """rs.ge cancelled + MegaPlus GET has it = ghost AP."""
    rs = _make_rs_df([
        _rs_row("0748613258", "შპს ბიდი კომპანი", 38.75,
                status="გაუქმებული", cancel_date="2023-06-26 11:51"),
    ])
    store = _store_data(get_rows=[
        {"zed": "0748613258", "tax_id": "205295296", "total": 38.75, "date": "2023-06-25"},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["ghost_ap"] == 1
    ghost = bundle["ghost_ap"][0]
    assert ghost["zed"] == "0748613258"
    assert ghost["get_total"] == 38.75


# ─────────────────────────────────────── soft signal — possible_replacements ───


def test_possible_replacement_same_supplier_within_window():
    """Missing rs.ge waybill + same-supplier GET row within ±14d at ±10% amount
    surfaces as possible replacement."""
    rs = _make_rs_df([
        _rs_row("0788494784", "შპს ვასაძის პური", 52.0, tax_id="237077961",
                act_date="2023-12-21 10:00"),
    ])
    store = _store_data(get_rows=[
        {"zed": "0790375212/5", "tax_id": "237077961", "total": 53.0, "date": "2023-12-31"},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["possible_replacements"] == 1
    pr = bundle["possible_replacements"][0]
    assert pr["rs_zed"] == "0788494784"
    assert pr["matched_get_zed"] == "0790375212/5"
    # rs 2023-12-21 10:00 → GET 2023-12-31 00:00 = 9 days 14 hours, .days truncates to 9
    assert pr["days_offset"] == 9


def test_possible_replacement_outside_window_no_match():
    rs = _make_rs_df([
        _rs_row("0788494784", "შპს ვასაძის პური", 52.0, tax_id="237077961",
                act_date="2023-12-01 10:00"),
    ])
    store = _store_data(get_rows=[
        {"zed": "0790375212/5", "tax_id": "237077961", "total": 53.0, "date": "2024-01-15"},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["possible_replacements"] == 0


# ─────────────────────────────────────── stale rs.ge data ──────────────────────


def test_stale_rs_data_get_zed_not_in_xls():
    """GET has waybill, no rs.ge xls entry (any status) → stale flag."""
    rs = _make_rs_df([])  # empty rs.ge
    store = _store_data(get_rows=[
        {"zed": "0969025483", "tax_id": "111111111", "total": 395.15, "date": "2026-04-15"},
    ])
    # Empty rs.ge → no "active" rows so nothing to categorize, but stale check needs >=1 row
    # Simulate: add 1 unrelated rs.ge row so rs_df is non-empty
    rs = _make_rs_df([
        _rs_row("0111111111", "სხვა", 1.0, status="დასრულებული"),
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["rs_data_stale"] == 1
    assert bundle["rs_data_stale"][0]["zed"] == "0969025483"


def test_get_zed_in_rs_xls_not_stale():
    rs = _make_rs_df([
        _rs_row("0123456789", "ტესტი", 100.0, status="დასრულებული"),
    ])
    store = _store_data(get_rows=[
        {"zed": "0123456789", "tax_id": "111111111", "total": 100.0, "date": "2024-01-15"},
    ])
    bundle = reconcile(rs, {"1329": store})
    assert bundle["totals"]["rs_data_stale"] == 0


# ─────────────────────────────────────── per-supplier rollup ───────────────────


def test_by_supplier_rollup_aggregates_categories():
    rs = _make_rs_df([
        _rs_row("0111111111", "შპს ტესტი", 100.0, tax_id="222"),
        _rs_row("0222222222", "შპს ტესტი", 200.0, tax_id="222"),
        _rs_row("0333333333", "შპს ტესტი", -10.0, type_="უკან დაბრუნება", tax_id="222"),
    ])
    bundle = reconcile(rs, {"1329": _store_data()})
    sup = bundle["by_supplier"][0]
    assert sup["supplier_name"] == "შპს ტესტი"
    assert sup["missing_count"] == 2
    assert sup["missing_amount"] == 300.0
    assert sup["returns_not_recorded_count"] == 1
    assert sup["total_count"] == 3


# ─────────────────────────────────────── category — wrong_store ────────────────


def test_wrong_store_only_other_dvabzu_dest_received_in_ozurgeti():
    """rs.ge waybill written for დვაბზუ but MegaPlus has it only in ოზურგეთი —
    operator picked the wrong store dropdown."""
    rs = _make_rs_df([
        _rs_row("0848882809", "სს ტრეიდ პარტნერი", 230.09,
                destination="ლანჩხუთი დვაბზუ"),
    ])
    stores = {
        "1329": _store_data(get_rows=[], store_id="1329"),
        "1301": _store_data(get_rows=[
            {"zed": "0848882809", "tax_id": "111111111", "total": 230.09, "date": "2024-09-25"},
        ], store_id="1301"),
    }
    bundle = reconcile(rs, stores)
    assert bundle["totals"]["wrong_store"] == 1
    assert bundle["totals"]["wrong_store_only_other"] == 1
    assert bundle["totals"]["wrong_store_duplicate"] == 0
    assert bundle["totals"]["missing"] == 0
    row = bundle["wrong_store"][0]
    assert row["zed"] == "0848882809"
    assert row["kind"] == "only_other"
    assert row["received_stores"] == ["1301"]
    assert row["received_store_names"] == ["ოზურგეთი"]


def test_wrong_store_only_other_ozurgeti_dest_received_in_dvabzu():
    """Reverse direction — rs.ge for ოზურგეთი, MegaPlus has it in დვაბზუ only."""
    rs = _make_rs_df([
        _rs_row("0823667508", "სს ტრეიდ პარტნერი", 734.61,
                destination="სოფ.ოზურგეთი (ოზურგეთი - ნინოშვილი - ლესა)"),
    ])
    stores = {
        "1329": _store_data(get_rows=[
            {"zed": "0823667508", "tax_id": "111111111", "total": 734.61, "date": "2024-06-07"},
        ], store_id="1329"),
        "1301": _store_data(get_rows=[], store_id="1301"),
    }
    bundle = reconcile(rs, stores)
    assert bundle["totals"]["wrong_store"] == 1
    assert bundle["totals"]["wrong_store_only_other"] == 1
    row = bundle["wrong_store"][0]
    assert row["kind"] == "only_other"
    assert row["received_store_names"] == ["დვაბზუ"]


def test_wrong_store_duplicate_received_in_both():
    """Lactalis pattern — rs.ge dest=დვაბზუ, MegaPlus has it in BOTH stores
    (operator entered the same waybill twice — wrong-store duplicate)."""
    rs = _make_rs_df([
        _rs_row("0917949641", "შპს ლაქტალის ჯორჯია", 170.92,
                destination="ოზურგეთი ს. ზედა დვაბზუ"),
    ])
    stores = {
        "1329": _store_data(get_rows=[
            {"zed": "0917949641", "tax_id": "404898973", "total": 170.92, "date": "2025-08-08"},
        ], store_id="1329"),
        "1301": _store_data(get_rows=[
            {"zed": "0917949641", "tax_id": "404898973", "total": 170.92, "date": "2025-08-08"},
        ], store_id="1301"),
    }
    bundle = reconcile(rs, stores)
    assert bundle["totals"]["wrong_store"] == 1
    assert bundle["totals"]["wrong_store_duplicate"] == 1
    assert bundle["totals"]["amount_mismatch"] == 0
    row = bundle["wrong_store"][0]
    assert row["kind"] == "duplicate"
    assert sorted(row["received_stores"]) == ["1301", "1329"]
    assert row["get_total_all"] == pytest.approx(341.84)
    assert row["get_total_dest"] == pytest.approx(170.92)
    assert row["get_total_other"] == pytest.approx(170.92)


def test_correct_store_match_not_flagged_as_wrong_store():
    """Sanity: when MegaPlus reception matches dest, no wrong_store flag."""
    rs = _make_rs_df([
        _rs_row("0123456789", "შპს ტესტი", 100.0, destination="ლანჩხუთი დვაბზუ"),
    ])
    stores = {
        "1329": _store_data(get_rows=[
            {"zed": "0123456789", "tax_id": "111111111", "total": 100.0, "date": "2024-01-15"},
        ], store_id="1329"),
        "1301": _store_data(store_id="1301"),
    }
    bundle = reconcile(rs, stores)
    assert bundle["totals"]["wrong_store"] == 0
    assert bundle["totals"]["missing"] == 0
    assert bundle["totals"]["amount_mismatch"] == 0


def test_wrong_store_per_supplier_count():
    """Per-supplier rollup includes wrong_store_count."""
    rs = _make_rs_df([
        _rs_row("0111111111", "შპს ტესტი", 100.0, tax_id="222",
                destination="ლანჩხუთი დვაბზუ"),
    ])
    stores = {
        "1329": _store_data(store_id="1329"),
        "1301": _store_data(get_rows=[
            {"zed": "0111111111", "tax_id": "222", "total": 100.0, "date": "2024-01-01"},
        ], store_id="1301"),
    }
    bundle = reconcile(rs, stores)
    sup = bundle["by_supplier"][0]
    assert sup["wrong_store_count"] == 1
    assert sup["missing_count"] == 0
    assert sup["total_count"] == 1


def test_wrong_store_closed_destination_excluded():
    """Closed Tbilisi destinations don't trigger wrong_store flag — they're
    filtered out before categorization just like missing rows are."""
    rs = _make_rs_df([
        _rs_row("0700000000", "შპს ძველი", 50.0,
                destination="თბილისი, ბარამიძის 7"),
    ])
    stores = {
        "1329": _store_data(get_rows=[
            {"zed": "0700000000", "tax_id": "111", "total": 50.0, "date": "2023-01-01"},
        ], store_id="1329"),
        "1301": _store_data(store_id="1301"),
    }
    bundle = reconcile(rs, stores)
    # dest_class = "closed" → not active store → wrong_store should NOT fire
    assert bundle["totals"]["wrong_store"] == 0
    assert bundle["totals"]["filtered_closed_stores"] == 1
