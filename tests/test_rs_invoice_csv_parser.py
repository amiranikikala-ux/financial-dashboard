"""Unit tests for dashboard_pipeline.rs_invoice_csv parser.

Covers:
- TIN extraction from rs.ge counterparty format
- Georgian date parsing (all 12 months)
- Waybill comma-split with trailing-comma + whitespace edge cases
- Buyer CSV parse: well-formed + malformed rows skip+log
- Seller CSV parse: line-item grouping by ID
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

import pytest

from dashboard_pipeline.rs_invoice_csv import (
    extract_tin_and_name,
    parse_buyer_invoices,
    parse_invoice_date,
    parse_seller_invoices,
    split_waybill_field,
)


# -----------------------------------------------------------------------------
# extract_tin_and_name
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_tin,expected_name", [
    ("(400132192-დღგ) შპს პარტნიორი", "400132192", "შპს პარტნიორი"),
    ("(404460187-დღგ) შპს ფუდმარტი", "404460187", "შპს ფუდმარტი"),
    ("(406181616-დღგ) შპს  ჯიდიაი", "406181616", "შპს  ჯიდიაი"),
    ("(33001062062) კ. ა.", "33001062062", "კ. ა."),
    ("(200179118-დღგ) შპს იფქლი", "200179118", "შპს იფქლი"),
])
def test_tin_extracts_from_well_formed_supplier_label(text, expected_tin, expected_name):
    tin, name = extract_tin_and_name(text)
    assert tin == expected_tin
    assert name == expected_name


@pytest.mark.parametrize("text", ["", "   ", None, "nan", "NaN"])
def test_tin_returns_none_for_blank_input(text):
    tin, name = extract_tin_and_name(text)
    assert tin is None
    assert name == ""


def test_tin_falls_back_to_text_only_when_no_paren():
    tin, name = extract_tin_and_name("just a name no parens")
    assert tin is None
    assert name == "just a name no parens"


# -----------------------------------------------------------------------------
# parse_invoice_date
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("abbr,month_num", [
    ("იან", 1), ("თებ", 2), ("მარ", 3), ("აპრ", 4),
    ("მაი", 5), ("ივნ", 6), ("ივლ", 7), ("აგვ", 8),
    ("სექ", 9), ("ოქტ", 10), ("ნოე", 11), ("დეკ", 12),
])
def test_date_parses_all_twelve_georgian_months(abbr, month_num):
    result = parse_invoice_date(f"15-{abbr}-2026 13:19:12")
    assert result == datetime(2026, month_num, 15, 13, 19, 12)


def test_date_parses_without_time_component():
    result = parse_invoice_date("01-აგვ-2022")
    assert result == datetime(2022, 8, 1, 0, 0, 0)


@pytest.mark.parametrize("text", [
    "", "   ", None, "nan", "90.78", "not a date",
    "32-აგვ-2026 12:00:00",  # invalid day
    "15-XYZ-2026 12:00:00",  # bad month abbr
])
def test_date_returns_none_for_invalid_input(text):
    assert parse_invoice_date(text) is None


# -----------------------------------------------------------------------------
# split_waybill_field
# -----------------------------------------------------------------------------

def test_waybill_split_handles_trailing_comma_and_space():
    # Real CSV row 0 example: '0962583623, 0966670470, 0966670471, 0970130475, '
    out = split_waybill_field("0962583623, 0966670470, 0966670471, 0970130475, ")
    assert out == ["0962583623", "0966670470", "0966670471", "0970130475"]


def test_waybill_split_returns_empty_for_blank():
    assert split_waybill_field("") == []
    assert split_waybill_field(None) == []
    assert split_waybill_field("   ") == []


def test_waybill_split_dedupes_preserving_order():
    out = split_waybill_field("1234, 5678, 1234, 9012")
    assert out == ["1234", "5678", "9012"]


def test_waybill_split_strips_whitespace_per_element():
    out = split_waybill_field("  1234  ,  5678  ")
    assert out == ["1234", "5678"]


def test_waybill_split_handles_single_value():
    assert split_waybill_field("1234567") == ["1234567"]


# -----------------------------------------------------------------------------
# parse_buyer_invoices — fixture-based
# -----------------------------------------------------------------------------

BUYER_CSV_HEADER = (
    "სტატუსი,ID,სერია №,გამყიდველი,მყიდველი (შერწყმული ორგანიზაცია),"
    "გამოწერის თარ.,ოპერაციის თარ.,გამწვანების თარ.,თანხა,რაოდენობა,"
    "დღგ-ს თანხა,დადასტურების თარ.,დეკლ. №,დეკლარაციის პერიოდი (თვე\\,წელი).,"
    "ქვე-მომხმარებელი,მყიდველის ქვე-მომხმარებელი,ზედნადები,უარყოფის თარიღი,"
)


def _write_buyer_csv(tmp_path: Path, body_rows: list[str]) -> Path:
    """Helper: write a buyer-CSV-shaped file with given body rows.

    Body rows are pipe-joined for clarity, then split into 19 CSV columns
    just like the real export. Caller passes raw CSV row strings (not pipes).
    """
    p = tmp_path / "buyer.csv"
    lines = ["სტატუსი,ID,სერია №,გამყიდველი,მყიდველი (შერწყმული ორგანიზაცია),"
             "გამოწერის თარ.,ოპერაციის თარ.,გამწვანების თარ.,თანხა,რაოდენობა,"
             "დღგ-ს თანხა,დადასტურების თარ.,დეკლ. №,\"დეკლარაციის პერიოდი (თვე,წელი).\","
             "ქვე-მომხმარებელი,მყიდველის ქვე-მომხმარებელი,ზედნადები,უარყოფის თარიღი,"]
    lines.extend(body_rows)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return p


def test_buyer_parser_accepts_well_formed_row(tmp_path):
    body = [
        "დადასტურებული,123,ეკ-1,(404460187-დღგ) შპს ფუდმარტი,,"
        "07-მაი-2026 17:45:49,01-აპრ-2026 00:00:00,,2444.87,378.45,"
        "372.91,,,2026-04,,,\"0962583623, 0966670470\",,",
    ]
    df, stats = parse_buyer_invoices(_write_buyer_csv(tmp_path, body))
    assert stats.rows_total == 1
    assert stats.rows_valid == 1
    assert stats.rows_skipped == 0
    row = df.iloc[0]
    assert row["invoice_id"] == "123"
    assert row["supplier_tax_id"] == "404460187"
    assert row["supplier_name"] == "შპს ფუდმარტი"
    assert row["amount_ge"] == 2444.87
    assert row["vat_ge"] == 372.91
    assert row["status"] == "დადასტურებული"
    assert row["waybills"] == ["0962583623", "0966670470"]


def test_buyer_parser_skips_malformed_amount_with_log(tmp_path, caplog):
    body = [
        # row with a date in the amount column (real-world malformed pattern)
        "დადასტურებული,124,ეკ-2,(404460187-დღგ) შპს ფუდმარტი,,"
        "07-მაი-2026 17:45:49,,,15-იან-2026 13:19:12,1,1,,,,,,1234,,",
    ]
    with caplog.at_level(logging.WARNING, logger="dashboard_pipeline.rs_invoice_csv"):
        df, stats = parse_buyer_invoices(_write_buyer_csv(tmp_path, body))
    assert stats.rows_valid == 0
    assert stats.rows_skipped == 1
    assert stats.skip_reasons.get("amount_unparseable") == 1
    assert any("amount unparseable" in rec.message for rec in caplog.records)


def test_buyer_parser_skips_missing_supplier_tin(tmp_path, caplog):
    body = [
        "დადასტურებული,125,ეკ-3,no-tin-supplier,,"
        "07-მაი-2026 17:45:49,,,1000,,,,,,,,1234,,",
    ]
    with caplog.at_level(logging.WARNING, logger="dashboard_pipeline.rs_invoice_csv"):
        df, stats = parse_buyer_invoices(_write_buyer_csv(tmp_path, body))
    assert stats.rows_valid == 0
    assert stats.skip_reasons.get("supplier_tin_missing") == 1


def test_buyer_parser_real_csv_matches_known_counts():
    """Acceptance test: real export should produce 7,402 valid / 16 skipped.

    This is the verified count from 2026-05-07. If this fails after a real
    export refresh, update the expected numbers + investigate the diff.
    """
    real_path = Path("Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი.csv")
    if not real_path.exists():
        pytest.skip("real buyer CSV not present (CI fixture only)")
    df, stats = parse_buyer_invoices(real_path)
    assert stats.rows_valid == 7402, f"valid count drifted: {stats.rows_valid}"
    assert stats.rows_skipped == 16, f"skipped count drifted: {stats.rows_skipped}"
    foodmart = df[df["supplier_tax_id"] == "404460187"]
    assert len(foodmart) == 60
    assert round(float(foodmart["amount_ge"].sum()), 2) == 163082.36 or \
           abs(float(foodmart["amount_ge"].sum()) - 163082.0) < 1.0


def test_buyer_parser_xls_recovers_csv_dropped_invoices():
    """XLS path is the canonical source — must recover 8 invoices CSV drops.

    CSV export truncates 8 invoices mid-row (~1,982 GEL across ასკანა პლიუსი
    + ტიტე 2024). XLS export is structurally clean. Pipeline uses XLS to avoid
    silent data loss. Verified 2026-05-07.
    """
    real_path = Path("Financial_Analysis/რს ფაქტურები/ფაქტურები მყიდველი რეესტრი.xls")
    if not real_path.exists():
        pytest.skip("real buyer XLS not present (CI fixture only)")
    df, stats = parse_buyer_invoices(real_path)
    assert stats.rows_total == 7410
    assert stats.rows_valid == 7410, f"XLS should drop nothing: {stats.rows_skipped} skipped"
    assert stats.rows_skipped == 0

    csv_dropped_ids = {
        "318492895", "320041879", "323372108", "330277037",
        "333156271", "336776811", "338763798", "341262105",
    }
    recovered = df[df["invoice_id"].isin(csv_dropped_ids)]
    assert len(recovered) == 8, f"expected all 8 CSV-dropped invoices, got {len(recovered)}"
    assert abs(float(recovered["amount_ge"].sum()) - 1981.94) < 0.05

    foodmart = df[df["supplier_tax_id"] == "404460187"]
    assert len(foodmart) == 60
    assert abs(float(foodmart["amount_ge"].sum()) - 163082.25) < 0.05


def test_parse_invoice_date_accepts_iso_format():
    """XLS-derived dates come as ISO strings ('2025-12-01 00:00:00')."""
    assert parse_invoice_date("2025-12-01 00:00:00") == datetime(2025, 12, 1, 0, 0, 0)
    assert parse_invoice_date("2026-04-01") == datetime(2026, 4, 1, 0, 0, 0)
    assert parse_invoice_date("2025-08-15 14:30:45") == datetime(2025, 8, 15, 14, 30, 45)


def test_parse_invoice_date_accepts_pandas_timestamp():
    import pandas as pd
    ts = pd.Timestamp("2025-12-01 13:45:00")
    assert parse_invoice_date(ts) == datetime(2025, 12, 1, 13, 45, 0)
    assert parse_invoice_date(pd.NaT) is None


# -----------------------------------------------------------------------------
# parse_seller_invoices — line-item grouping
# -----------------------------------------------------------------------------

SELLER_CSV_HEADER = (
    "საქონელი / მომსახურება,ზომის ერთეული,რაოდ.,ღირებულება დღგ და აქციზის ჩათვლით,"
    "დაბეგვრა,დღგ,აქციზი,ID,სერია №,მყიდველი,გამყიდველი,გამოწერის თარ.,"
    "ოპერაციის თარ.,შენიშვნა,"
)


def _write_seller_csv(tmp_path: Path, body_rows: list[str]) -> Path:
    p = tmp_path / "seller.csv"
    lines = [SELLER_CSV_HEADER]
    lines.extend(body_rows)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return p


def test_seller_parser_groups_line_items_by_id(tmp_path):
    body = [
        "ქსელში წარდგენის,მომსახურება,,5000,ჩვეულებრივი,762.71,,777,ეა-1,"
        "(404460187-დღგ) შპს ფუდმარტი,(400333858-დღგ) შპს ჯეო ფუდთაიმი,"
        "15-აპრ-2026 11:55:15,01-მარ-2026 00:00:00,,",
        "სტიკერი,ცალი,100,3642.47,ჩვეულებრივი,555.63,,777,ეა-1,"
        "(404460187-დღგ) შპს ფუდმარტი,(400333858-დღგ) შპს ჯეო ფუდთაიმი,"
        "15-აპრ-2026 11:55:15,01-მარ-2026 00:00:00,,",
        # different invoice ID
        "სხვა საქონელი,ცალი,1,1500,ჩვეულებრივი,228.81,,888,ეა-2,"
        "(404460187-დღგ) შპს ფუდმარტი,(400333858-დღგ) შპს ჯეო ფუდთაიმი,"
        "20-აპრ-2026 12:00:00,,,",
    ]
    df, stats = parse_seller_invoices(_write_seller_csv(tmp_path, body))
    assert stats.rows_total == 3
    assert stats.rows_valid == 3
    assert len(df) == 2  # two unique invoice IDs

    inv_777 = df[df["invoice_id"] == "777"].iloc[0]
    assert inv_777["amount_ge"] == 8642.47  # 5000 + 3642.47
    assert inv_777["vat_ge"] == 1318.34     # 762.71 + 555.63
    assert inv_777["customer_tax_id"] == "404460187"
    assert inv_777["line_count"] == 2
    assert len(inv_777["items"]) == 2

    inv_888 = df[df["invoice_id"] == "888"].iloc[0]
    assert inv_888["amount_ge"] == 1500.0
    assert inv_888["line_count"] == 1


def test_seller_parser_skips_row_missing_id_or_value(tmp_path, caplog):
    body = [
        # missing ID
        "item,unit,1,100,ჩვ,18,,,,,,,,",
        # missing value
        "item,unit,1,,ჩვ,,,777,,(404460187) ფუდმარტი,(400333858) ჯეო,01-აგვ-2026 12:00:00,,,",
    ]
    with caplog.at_level(logging.WARNING, logger="dashboard_pipeline.rs_invoice_csv"):
        df, stats = parse_seller_invoices(_write_seller_csv(tmp_path, body))
    assert stats.rows_valid == 0
    assert stats.rows_skipped == 2


def test_seller_parser_real_csv_matches_known_counts():
    real_path = Path("Financial_Analysis/რს ფაქტურები/ფაქტურები გამყიდველი.csv")
    if not real_path.exists():
        pytest.skip("real seller CSV not present")
    df, stats = parse_seller_invoices(real_path)
    foodmart = df[df["customer_tax_id"] == "404460187"]
    assert len(foodmart) == 46
    assert abs(float(foodmart["amount_ge"].sum()) - 508573.0) < 1.0
