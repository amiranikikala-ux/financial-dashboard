"""Sprint 5.1 — VAT reconciliation tests.

Covers:
* parse_audit_excel — period normalization + numeric coercion
* parse_cash_outflow_journal — category validation + vat_applies default
* compute_vat_reconciliation — full bundle structure + per-month identity
* append_cash_outflow_entry — CSV write + header + category enum
* find_audit_excel — auto-detect by filename prefix
* Status classification thresholds (green/yellow/red)
* AI tools — get_vat_reconciliation_month, explain_unaccounted_cash,
  record_cash_outflow: input validation, output shape, summary_ka markers.
* Tool registry — all three schemas present in TOOL_SCHEMAS.
* Dispatch routing — name matching for each tool.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from dashboard_pipeline.vat_reconciliation import (
    CATEGORY_LABELS_KA,
    CATEGORY_VAT_DEFAULTS,
    STATUS_GREEN_MAX_PCT,
    STATUS_YELLOW_MAX_PCT,
    UNACCOUNTED_CASH_THRESHOLD_GE,
    VAT_RATE,
    _classify_status,
    append_cash_outflow_entry,
    compute_vat_reconciliation,
    find_audit_excel,
    find_invoices_issued_excel,
    parse_audit_excel,
    parse_cash_outflow_journal,
    parse_invoices_issued,
)


# ---------------------------------------------------------------------------
# parse_audit_excel
# ---------------------------------------------------------------------------

def _write_audit_excel(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Writes a minimal audit-shaped xlsx (header row at index 1)."""
    header = [
        "პერიოდი",
        "დეკლარირებული ბრუნვა",
        "აფ.გამოწერილი",
        "უფზ რეალიზაცია",
        "სალარო",
        "თბს ბანკი პოსტერმინალით",
        "საქ.ბანკი პოსტერმინალით",
        "ბანკები ჯამში",
    ]
    # Row 0 = totals placeholder, row 1 = header, rows 2+ = data
    df_rows = [[None] * len(header), header]
    for r in rows:
        df_rows.append([
            r.get("period"),
            r.get("declared", 0),
            r.get("af", 0),
            r.get("ufz", 0),
            r.get("cashreg", 0),
            r.get("tbc", 0),
            r.get("bog", 0),
            0,
        ])
    pd.DataFrame(df_rows).to_excel(path, index=False, header=False)


def test_parse_audit_excel_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "გაანგარიშება.xlsx"
    _write_audit_excel(f, [
        {"period": 202408, "declared": 139485, "af": 16603, "cashreg": 142413, "tbc": 6697, "bog": 71200},
        {"period": 202501, "declared": 154374, "af": 10644, "cashreg": 76494, "tbc": 4087, "bog": 40193},
    ])
    result = parse_audit_excel(str(f))
    assert set(result.keys()) == {"2024-08", "2025-01"}
    aug = result["2024-08"]
    assert aug["declared_ge"] == pytest.approx(139485)
    assert aug["cashreg_ge"] == pytest.approx(142413)
    assert aug["tbc_pos_ge"] == pytest.approx(6697)
    assert aug["bog_pos_ge"] == pytest.approx(71200)


def test_parse_audit_excel_missing_path_returns_empty() -> None:
    assert parse_audit_excel("") == {}
    assert parse_audit_excel("/nonexistent/path.xlsx") == {}


def test_find_audit_excel_prefix(tmp_path: Path) -> None:
    (tmp_path / "manual_payments.csv").write_text("x")
    (tmp_path / "გაანგარიშება test.xlsx").write_text("x")
    found = find_audit_excel(str(tmp_path))
    assert found is not None
    assert Path(found).name.startswith("გაანგარიშება")


def test_find_audit_excel_missing_returns_none(tmp_path: Path) -> None:
    assert find_audit_excel(str(tmp_path)) is None


def test_find_audit_excel_searches_up_to_workspace_root(tmp_path: Path) -> None:
    """Audit file lives at workspace root; Financial_Analysis is two levels deeper."""
    workspace = tmp_path / "workspace"
    project = workspace / "project"
    fa = project / "Financial_Analysis"
    fa.mkdir(parents=True)
    audit_file = workspace / "გაანგარიშება დამუშავებული.xlsx"
    audit_file.write_text("x")
    found = find_audit_excel(str(fa))
    assert found is not None
    assert Path(found).parent == workspace


# ---------------------------------------------------------------------------
# parse_invoices_issued + find_invoices_issued_excel (Sprint 5.1.1)
# ---------------------------------------------------------------------------

def _write_invoices_excel(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Writes RS.ge report-style Excel (header in row 0)."""
    header = [
        "საქონელი / მომსახურება", "ზომის ერთეული", "რაოდ.",
        "ღირებულება დღგ და აქციზის ჩათვლით", "დაბეგვრა",
        "დღგ", "აქციზი", "ID", "სერია №", "მყიდველი",
        "გამყიდველი", "გამოწერის თარ.", "ოპერაციის თარ.", "შენიშვნა",
    ]
    df_rows = []
    for r in rows:
        df_rows.append([
            r.get("product", "მარკეტინგული"),
            "მომსახურება", None, r.get("amount", 0), "ჩვეულებრივი",
            0, None, r.get("id", 1), "ეა-84 1111", r.get("buyer", ""),
            r.get("seller", ""), r.get("issued_at"), r.get("op_date"), "",
        ])
    df = pd.DataFrame(df_rows, columns=header)
    df.to_excel(path, index=False)


def test_parse_invoices_issued_filters_to_our_tax_id(tmp_path: Path) -> None:
    f = tmp_path / "report (1).xls"
    _write_invoices_excel(f, [
        {"seller": "(400333858-დღგ) შპს ჯეო ფუდთაიმი", "buyer": "შპს ფუდმარტი",
         "amount": 2299.63, "op_date": pd.Timestamp("2024-08-01")},
        {"seller": "(400333858-დღგ) შპს ჯეო ფუდთაიმი", "buyer": "შპს მასტერ თრეიდი",
         "amount": 1000.00, "op_date": pd.Timestamp("2024-08-15")},
        # Row where we are NOT the seller — must be ignored
        {"seller": "(999999999) სხვა კომპანია", "buyer": "შპს ვინმე",
         "amount": 5000.00, "op_date": pd.Timestamp("2024-08-20")},
        # Different month
        {"seller": "(400333858-დღგ) შპს ჯეო ფუდთაიმი", "buyer": "შპს ფუდმარტი",
         "amount": 3000.00, "op_date": pd.Timestamp("2024-09-05")},
    ])
    result = parse_invoices_issued(str(f), our_tax_id="400333858")
    assert "2024-08" in result
    assert "2024-09" in result
    assert result["2024-08"] == pytest.approx(2299.63 + 1000.00)
    assert result["2024-09"] == pytest.approx(3000.00)


def test_parse_invoices_issued_missing_file_returns_empty() -> None:
    assert parse_invoices_issued("/nonexistent.xls") == {}


def test_find_invoices_issued_excel_in_subfolder(tmp_path: Path) -> None:
    fa = tmp_path / "Financial_Analysis"
    subfolder = fa / "ანგარიშ ფაქტურები"
    subfolder.mkdir(parents=True)
    (subfolder / "report (1).xls").write_text("x")
    (subfolder / "ა.ფ რეესტრი.xls").write_text("x")  # must NOT be picked
    found = find_invoices_issued_excel(str(fa))
    assert found is not None
    assert Path(found).name.lower().startswith("report")


def test_find_invoices_issued_excel_searches_up_to_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project_fa = workspace / "project" / "Financial_Analysis"
    project_fa.mkdir(parents=True)
    # Only workspace-level has the subfolder
    ws_sub = workspace / "Financial_Analysis" / "ანგარიშ ფაქტურები"
    ws_sub.mkdir(parents=True)
    (ws_sub / "report.xlsx").write_text("x")
    found = find_invoices_issued_excel(str(project_fa))
    assert found is not None


def test_compute_vat_reconciliation_uses_invoices_from_report(tmp_path: Path) -> None:
    """When report.xls is provided, invoices_ge comes from it (bruto)."""
    fx = _vat_fixture()
    invoices_f = tmp_path / "report.xls"
    _write_invoices_excel(invoices_f, [
        {"seller": "(400333858-დღგ) შპს ჯეო ფუდთაიმი", "buyer": "შპს ფუდმარტი",
         "amount": 19591.98, "op_date": pd.Timestamp("2024-08-15")},
    ])
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
        invoices_issued_path=str(invoices_f),
    )
    row = bundle["by_month"][0]
    assert row["invoices_ge"] == pytest.approx(19591.98)
    # total_real = cashreg_in + bank_card + invoices
    assert row["total_real_ge"] == pytest.approx(
        row["cashreg_in_ge"] + row["bank_card_ge"] + 19591.98
    )


def test_compute_vat_reconciliation_fallback_to_audit_af_bruto(tmp_path: Path) -> None:
    """Without report.xls, invoices_ge = audit_af × 1.18 (approximate bruto)."""
    fx = _vat_fixture()
    audit_f = tmp_path / "გაანგარიშება.xlsx"
    _write_audit_excel(audit_f, [
        {"period": 202408, "declared": 139485, "af": 16603, "cashreg": 142413, "tbc": 6697, "bog": 71200},
    ])
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
        audit_excel_path=str(audit_f),
    )
    row = bundle["by_month"][0]
    # invoices_ge = 16603 × 1.18 = 19591.54
    assert row["invoices_ge"] == pytest.approx(16603 * 1.18)


# ---------------------------------------------------------------------------
# parse_cash_outflow_journal
# ---------------------------------------------------------------------------

def _write_journal_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = ["period", "amount", "purpose_ka", "category", "vat_applies", "notes", "entered_at"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def test_parse_cash_outflow_journal_basic(tmp_path: Path) -> None:
    f = tmp_path / "journal.csv"
    _write_journal_csv(f, [
        {"period": "2024-08", "amount": 15000, "purpose_ka": "ხელფასი",
         "category": "salary_cash", "vat_applies": "true", "notes": "", "entered_at": "2026-04-23"},
        {"period": "2024-08", "amount": 3500, "purpose_ka": "საკანცელარიო",
         "category": "business_expense", "vat_applies": "false", "notes": "", "entered_at": "2026-04-23"},
    ])
    entries = parse_cash_outflow_journal(str(f))
    assert len(entries) == 2
    assert entries[0]["amount_ge"] == 15000
    assert entries[0]["vat_applies"] is True
    assert entries[0]["category_label_ka"] == CATEGORY_LABELS_KA["salary_cash"]
    assert entries[1]["vat_applies"] is False


def test_parse_cash_outflow_journal_defaults_vat(tmp_path: Path) -> None:
    f = tmp_path / "journal.csv"
    _write_journal_csv(f, [
        {"period": "2024-08", "amount": 100, "purpose_ka": "X",
         "category": "personal_withdrawal", "vat_applies": "", "notes": "", "entered_at": ""},
    ])
    entries = parse_cash_outflow_journal(str(f))
    # personal_withdrawal default = True
    assert entries[0]["vat_applies"] is True


def test_parse_cash_outflow_journal_missing_returns_empty(tmp_path: Path) -> None:
    assert parse_cash_outflow_journal(str(tmp_path / "none.csv")) == []


def test_parse_cash_outflow_journal_rejects_bad_period(tmp_path: Path) -> None:
    f = tmp_path / "journal.csv"
    _write_journal_csv(f, [
        {"period": "bad-period", "amount": 100, "purpose_ka": "X",
         "category": "unknown", "vat_applies": "true", "notes": "", "entered_at": ""},
    ])
    assert parse_cash_outflow_journal(str(f)) == []


# ---------------------------------------------------------------------------
# append_cash_outflow_entry
# ---------------------------------------------------------------------------

def test_append_cash_outflow_entry_creates_file_with_header(tmp_path: Path) -> None:
    f = tmp_path / "journal.csv"
    entry = append_cash_outflow_entry(
        str(f),
        period="2024-08",
        amount_ge=5000,
        purpose_ka="ხელფასი",
        category="salary_cash",
    )
    assert f.exists()
    assert entry["period"] == "2024-08"
    assert entry["vat_applies"] is True  # salary_cash default
    assert entry["category_label_ka"] == CATEGORY_LABELS_KA["salary_cash"]

    # Re-read it
    entries = parse_cash_outflow_journal(str(f))
    assert len(entries) == 1
    assert entries[0]["amount_ge"] == 5000


def test_append_cash_outflow_entry_appends_without_duplicate_header(tmp_path: Path) -> None:
    f = tmp_path / "journal.csv"
    append_cash_outflow_entry(str(f), period="2024-08", amount_ge=1000, purpose_ka="a", category="unknown")
    append_cash_outflow_entry(str(f), period="2024-08", amount_ge=2000, purpose_ka="b", category="unknown")
    content = f.read_text(encoding="utf-8")
    # Header appears exactly once
    assert content.count("period,amount") == 1
    entries = parse_cash_outflow_journal(str(f))
    assert len(entries) == 2


def test_append_cash_outflow_entry_validates_period(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="period"):
        append_cash_outflow_entry(
            str(tmp_path / "j.csv"), period="bad", amount_ge=100, purpose_ka="x", category="unknown"
        )


def test_append_cash_outflow_entry_validates_amount(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="amount"):
        append_cash_outflow_entry(
            str(tmp_path / "j.csv"), period="2024-08", amount_ge=0, purpose_ka="x", category="unknown"
        )


def test_append_cash_outflow_entry_validates_category(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="category"):
        append_cash_outflow_entry(
            str(tmp_path / "j.csv"), period="2024-08", amount_ge=10, purpose_ka="x", category="alien"
        )


# ---------------------------------------------------------------------------
# _classify_status
# ---------------------------------------------------------------------------

def test_classify_status_green_yellow_red() -> None:
    # <= 5% gap, no unaccounted → green
    assert _classify_status(gap=1000, declared=100000, has_unaccounted=False) == "green"
    # 5-15% → yellow
    assert _classify_status(gap=10000, declared=100000, has_unaccounted=False) == "yellow"
    # > 15% → red
    assert _classify_status(gap=30000, declared=100000, has_unaccounted=False) == "red"


def test_classify_status_unaccounted_escalates_green_to_yellow() -> None:
    assert _classify_status(gap=1000, declared=100000, has_unaccounted=True) == "yellow"


def test_classify_status_no_declared() -> None:
    assert _classify_status(gap=None, declared=None, has_unaccounted=False) == "no_declared_data"
    assert _classify_status(gap=None, declared=0, has_unaccounted=False) == "no_declared_data"


# ---------------------------------------------------------------------------
# compute_vat_reconciliation — integration
# ---------------------------------------------------------------------------

def _vat_fixture() -> Dict[str, Any]:
    """Single-month synthetic fixture replicating 2024-08 audit evidence."""
    retail = {
        "by_month": [
            {"month": "2024-08", "revenue_ge": 282314.0, "cost_ge": 0, "profit_ge": 0},
        ],
    }
    tbc = {
        "lines": [
            {"თარიღი": "2024-08-05", "თანხა": 80000.0},
            {"თარიღი": "2024-08-20", "თანხა": 84903.0},
        ],
    }
    bog = {
        "lines": [
            {"თარიღი": "2024-08-10", "თანხა": 82481.0},
        ],
    }
    manual = [
        {"თარიღი": "2024-08-07", "თანხა": 12000.0},
    ]
    return {"retail": retail, "tbc": tbc, "bog": bog, "manual": manual}


def test_compute_vat_reconciliation_2024_08_identity() -> None:
    fx = _vat_fixture()
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
    )
    assert bundle["summary"]["months_total"] == 1
    row = bundle["by_month"][0]
    assert row["period"] == "2024-08"
    assert row["max_pos_ge"] == pytest.approx(282314.0)
    assert row["tbc_pos_ge"] == pytest.approx(164903.0)
    assert row["bog_pos_ge"] == pytest.approx(82481.0)
    assert row["bank_card_ge"] == pytest.approx(247384.0)
    # cashreg_in = MAX - bank_card
    assert row["cashreg_in_ge"] == pytest.approx(282314.0 - 247384.0)
    # cash_supplier from manual_payments
    assert row["cash_supplier_ge"] == pytest.approx(12000.0)
    # cash_unaccounted = cashreg_in - cash_supplier (no classified yet)
    expected_unacc = (282314.0 - 247384.0) - 12000.0
    assert row["cash_unaccounted_ge"] == pytest.approx(max(0, expected_unacc))
    assert row["data_quality"]["max_pos_available"] is True
    assert row["data_quality"]["banks_complete"] is True


def test_compute_vat_reconciliation_unaccounted_triggers_needs_input() -> None:
    fx = _vat_fixture()
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
    )
    row = bundle["by_month"][0]
    # With 35K - 12K = 23K unaccounted (above 5K threshold)
    assert row["needs_user_input"] is True
    assert row["vat_on_unaccounted_ge"] > 0


def test_compute_vat_reconciliation_bank_exceeds_max_flag() -> None:
    """Month where Bank POS > MAX POS → bank_exceeds_max=true."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2026-01", "revenue_ge": 107000}]},
        tbc_card_income_bundle={"lines": [{"თარიღი": "2026-01-10", "თანხა": 90000}]},
        bog_pos_income_bundle={"lines": [{"თარიღი": "2026-01-20", "თანხა": 50000}]},
        manual_journal_full=[],
    )
    row = bundle["by_month"][0]
    assert row["data_quality"]["bank_exceeds_max"] is True
    # cashreg_in floored at 0
    assert row["cashreg_in_ge"] == 0


def test_compute_vat_reconciliation_with_audit_excel(tmp_path: Path) -> None:
    fx = _vat_fixture()
    audit_f = tmp_path / "გაანგარიშება.xlsx"
    _write_audit_excel(audit_f, [
        {"period": 202408, "declared": 139485, "af": 16603, "cashreg": 142413, "tbc": 6697, "bog": 71200},
    ])
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
        audit_excel_path=str(audit_f),
    )
    row = bundle["by_month"][0]
    assert row["declared_ge"] == pytest.approx(139485)
    # gap = total_real - declared; total_real >> declared
    assert row["gap_vs_declared_ge"] > 100000
    assert row["status"] == "red"


def test_compute_vat_reconciliation_empty_inputs() -> None:
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": []},
        tbc_card_income_bundle={"lines": []},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    assert bundle["by_month"] == []
    assert bundle["summary"]["months_total"] == 0


# ---------------------------------------------------------------------------
# Sprint 5.8 — per-shop by_shop breakdown
# ---------------------------------------------------------------------------


def _vat_fixture_by_shop() -> Dict[str, Any]:
    """Synthetic 2024-08 fixture with per-shop retail_sales + per-line bank object tags."""
    retail = {
        "by_month": [
            {"month": "2024-08", "revenue_ge": 282314.0, "cost_ge": 0, "profit_ge": 0},
        ],
        "by_object_by_month": [
            {"object": "ოზურგეთი", "month": "2024-08", "revenue_ge": 180000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 5000, "total_quantity": 1000},
            {"object": "დვაბზუ", "month": "2024-08", "revenue_ge": 102314.0, "cost_ge": 0, "profit_ge": 0, "row_count": 3000, "total_quantity": 600},
        ],
    }
    tbc = {
        "lines": [
            {"თარიღი": "2024-08-05", "თანხა": 100000.0, "object": "ოზურგეთი"},
            {"თარიღი": "2024-08-20", "თანხა": 64903.0, "object": "დვაბზუ"},
        ],
    }
    bog = {
        "lines": [
            {"თარიღი": "2024-08-10", "თანხა": 50000.0, "object": "ოზურგეთი"},
            {"თარიღი": "2024-08-15", "თანხა": 32481.0, "object": "დვაბზუ"},
        ],
    }
    return {"retail": retail, "tbc": tbc, "bog": bog, "manual": []}


def test_by_shop_splits_max_per_shop() -> None:
    fx = _vat_fixture_by_shop()
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
    )
    row = bundle["by_month"][0]
    assert "by_shop" in row
    shops = row["by_shop"]
    assert set(shops.keys()) == {"ოზურგეთი", "დვაბზუ"}
    assert shops["ოზურგეთი"]["max_pos_ge"] == pytest.approx(180000.0)
    assert shops["დვაბზუ"]["max_pos_ge"] == pytest.approx(102314.0)


def test_by_shop_splits_bank_per_shop() -> None:
    fx = _vat_fixture_by_shop()
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
    )
    shops = bundle["by_month"][0]["by_shop"]
    assert shops["ოზურგეთი"]["tbc_pos_ge"] == pytest.approx(100000.0)
    assert shops["ოზურგეთი"]["bog_pos_ge"] == pytest.approx(50000.0)
    assert shops["ოზურგეთი"]["bank_card_ge"] == pytest.approx(150000.0)
    assert shops["დვაბზუ"]["tbc_pos_ge"] == pytest.approx(64903.0)
    assert shops["დვაბზუ"]["bog_pos_ge"] == pytest.approx(32481.0)
    assert shops["დვაბზუ"]["bank_card_ge"] == pytest.approx(97384.0)


def test_by_shop_cashreg_in_per_shop() -> None:
    fx = _vat_fixture_by_shop()
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
    )
    shops = bundle["by_month"][0]["by_shop"]
    # ოზურგეთი: MAX 180K - bank 150K = 30K cashreg
    assert shops["ოზურგეთი"]["cashreg_in_ge"] == pytest.approx(30000.0)
    # დვაბზუ: MAX 102,314 - bank 97,384 = 4,930 cashreg
    assert shops["დვაბზუ"]["cashreg_in_ge"] == pytest.approx(4930.0)
    assert shops["ოზურგეთი"]["bank_exceeds_max"] is False
    assert shops["დვაბზუ"]["bank_exceeds_max"] is False


def test_by_shop_bank_exceeds_max_flag_per_shop() -> None:
    """One shop has bank > MAX (anomaly) — only that shop's flag set."""
    retail = {
        "by_month": [{"month": "2025-03", "revenue_ge": 100000.0}],
        "by_object_by_month": [
            {"object": "ოზურგეთი", "month": "2025-03", "revenue_ge": 60000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
            {"object": "დვაბზუ", "month": "2025-03", "revenue_ge": 40000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
        ],
    }
    tbc = {
        "lines": [
            {"თარიღი": "2025-03-10", "თანხა": 50000.0, "object": "ოზურგეთი"},
            {"თარიღი": "2025-03-12", "თანხა": 60000.0, "object": "დვაბზუ"},  # bank > MAX for დვაბზუ
        ],
    }
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=retail,
        tbc_card_income_bundle=tbc,
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    shops = bundle["by_month"][0]["by_shop"]
    assert shops["ოზურგეთი"]["bank_exceeds_max"] is False
    assert shops["დვაბზუ"]["bank_exceeds_max"] is True
    assert shops["დვაბზუ"]["cashreg_in_ge"] == 0.0


def test_by_shop_skips_shops_with_no_activity() -> None:
    """A shop present in mapping but with 0 MAX and 0 bank for that month is omitted."""
    retail = {
        "by_month": [{"month": "2025-06", "revenue_ge": 50000.0}],
        "by_object_by_month": [
            {"object": "ოზურგეთი", "month": "2025-06", "revenue_ge": 50000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
            # No დვაბზუ row for this month
        ],
    }
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=retail,
        tbc_card_income_bundle={"lines": [{"თარიღი": "2025-06-01", "თანხა": 30000, "object": "ოზურგეთი"}]},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    shops = bundle["by_month"][0]["by_shop"]
    assert set(shops.keys()) == {"ოზურგეთი"}


def test_by_shop_tags_unallocated_when_no_object() -> None:
    """Bank line with no `object` tag falls to გაუნაწილებელი."""
    retail = {
        "by_month": [{"month": "2025-07", "revenue_ge": 100000.0}],
        "by_object_by_month": [
            {"object": "ოზურგეთი", "month": "2025-07", "revenue_ge": 100000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
        ],
    }
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=retail,
        tbc_card_income_bundle={"lines": [{"თარიღი": "2025-07-10", "თანხა": 20000}]},  # no object tag
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    shops = bundle["by_month"][0]["by_shop"]
    assert "გაუნაწილებელი" in shops
    assert shops["გაუნაწილებელი"]["tbc_pos_ge"] == pytest.approx(20000.0)
    # TBC reliability flag = False (20K attributed to "გაუნაწილებელი", 0 attributed to real shops)
    assert bundle["by_month"][0]["data_quality"]["tbc_per_shop_reliable"] is False


def test_by_shop_tbc_reliable_when_fully_attributed() -> None:
    fx = _vat_fixture_by_shop()
    bundle = compute_vat_reconciliation(
        retail_sales_bundle=fx["retail"],
        tbc_card_income_bundle=fx["tbc"],
        bog_pos_income_bundle=fx["bog"],
        manual_journal_full=fx["manual"],
    )
    assert bundle["by_month"][0]["data_quality"]["tbc_per_shop_reliable"] is True


def test_by_shop_absent_when_no_object_by_month() -> None:
    """Backward-compat: bundle without `by_object_by_month` → empty by_shop, no crash."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2024-08", "revenue_ge": 282314.0}]},  # no by_object_by_month
        tbc_card_income_bundle={"lines": [{"თარიღი": "2024-08-05", "თანხა": 164903.0}]},
        bog_pos_income_bundle={"lines": [{"თარიღი": "2024-08-10", "თანხა": 82481.0}]},
        manual_journal_full=[],
    )
    row = bundle["by_month"][0]
    # Top-level fields still populated normally.
    assert row["max_pos_ge"] == pytest.approx(282314.0)
    assert row["bank_card_ge"] == pytest.approx(247384.0)
    # Bank lines without object tags → everything falls to გაუნაწილებელი.
    # MAX side contributes nothing to by_shop (no by_object_by_month).
    shops = row["by_shop"]
    assert "გაუნაწილებელი" in shops
    assert shops["გაუნაწილებელი"]["max_pos_ge"] == 0


def test_by_shop_methodology_ka_documents_sprint_5_8() -> None:
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": []},
        tbc_card_income_bundle={"lines": []},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    meta = bundle["methodology_ka"]
    assert "by_shop" in meta
    assert "Sprint 5.8" in meta
    assert "tbc_per_shop_reliable" in meta


# ---------------------------------------------------------------------------
# AI tools — vat_tools
# ---------------------------------------------------------------------------

from dashboard_pipeline.ai.vat_tools import (
    explain_unaccounted_cash,
    get_vat_reconciliation_month,
    record_cash_outflow,
)


def _fake_data_loader(bundle: Dict[str, Any]):
    """Wrap a vat_reconciliation bundle as a data.json-shaped loader."""
    def _load() -> Dict[str, Any]:
        return {"vat_reconciliation": bundle}
    return _load


def _fixture_bundle() -> Dict[str, Any]:
    return compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2024-08", "revenue_ge": 282314.0}]},
        tbc_card_income_bundle={"lines": [{"თარიღი": "2024-08-05", "თანხა": 164903.0}]},
        bog_pos_income_bundle={"lines": [{"თარიღი": "2024-08-10", "თანხა": 82481.0}]},
        manual_journal_full=[{"თარიღი": "2024-08-07", "თანხა": 12000.0}],
    )


def test_get_vat_reconciliation_month_happy() -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = get_vat_reconciliation_month(loader, period="2024-08")
    assert out["period"] == "2024-08"
    assert "summary_ka" in out
    assert out["row"]["tbc_pos_ge"] == pytest.approx(164903.0)
    assert out["source"] == "data.json:vat_reconciliation"


def test_get_vat_reconciliation_month_rejects_bad_period() -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = get_vat_reconciliation_month(loader, period="August 2024")
    assert "error" in out


def test_get_vat_reconciliation_month_missing_period_lists_available() -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = get_vat_reconciliation_month(loader, period="2030-01")
    assert "error" in out
    assert "2024-08" in out["available_periods"]


def test_get_vat_reconciliation_month_summary_ka_surfaces_by_shop() -> None:
    """Sprint 5.8 — summary_ka must list per-shop MAX + cashreg when ≥2 shops material."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={
            "by_month": [{"month": "2024-08", "revenue_ge": 282314.0}],
            "by_object_by_month": [
                {"object": "ოზურგეთი", "month": "2024-08", "revenue_ge": 180000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
                {"object": "დვაბზუ", "month": "2024-08", "revenue_ge": 102314.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
            ],
        },
        tbc_card_income_bundle={"lines": [
            {"თარიღი": "2024-08-05", "თანხა": 100000.0, "object": "ოზურგეთი"},
            {"თარიღი": "2024-08-20", "თანხა": 64903.0, "object": "დვაბზუ"},
        ]},
        bog_pos_income_bundle={"lines": [
            {"თარიღი": "2024-08-10", "თანხა": 50000.0, "object": "ოზურგეთი"},
            {"თარიღი": "2024-08-15", "თანხა": 32481.0, "object": "დვაბზუ"},
        ]},
        manual_journal_full=[],
    )
    loader = _fake_data_loader(bundle)
    out = get_vat_reconciliation_month(loader, period="2024-08")
    summary = out["summary_ka"]
    assert "მაღაზიები" in summary
    assert "ოზურგეთი" in summary
    assert "დვაბზუ" in summary
    # Ordered by MAX desc → ოზურგეთი (180K) before დვაბზუ (102K)
    idx_ozurgeti = summary.index("ოზურგეთი")
    idx_dvabzu = summary.index("დვაბზუ")
    assert idx_ozurgeti < idx_dvabzu


def test_get_vat_reconciliation_month_summary_ka_skips_by_shop_for_single_shop() -> None:
    """When only one shop material, summary_ka stays compact without per-shop line."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={
            "by_month": [{"month": "2025-07", "revenue_ge": 100000.0}],
            "by_object_by_month": [
                {"object": "ოზურგეთი", "month": "2025-07", "revenue_ge": 100000.0, "cost_ge": 0, "profit_ge": 0, "row_count": 1, "total_quantity": 1},
            ],
        },
        tbc_card_income_bundle={"lines": [
            {"თარიღი": "2025-07-10", "თანხა": 80000.0, "object": "ოზურგეთი"},
        ]},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    loader = _fake_data_loader(bundle)
    out = get_vat_reconciliation_month(loader, period="2025-07")
    summary = out["summary_ka"]
    assert "მაღაზიები:" not in summary


def test_explain_unaccounted_cash_prompts_user_when_above_threshold() -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = explain_unaccounted_cash(loader, period="2024-08")
    assert out["needs_user_input"] is True
    assert out["potential_vat_liability_ge"] > 0
    # Prompt mentions VAT
    assert "დღგ" in out["prompt_ka"]
    assert "18%" in out["prompt_ka"] or "0.18" in out["prompt_ka"] or "18" in out["prompt_ka"]


def test_explain_unaccounted_cash_categories_listed() -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = explain_unaccounted_cash(loader, period="2024-08")
    cat_ids = {c["id"] for c in out["categories"]}
    assert "salary_cash" in cat_ids
    assert "personal_withdrawal" in cat_ids
    assert "unknown" in cat_ids


def test_explain_unaccounted_cash_below_threshold_no_input() -> None:
    # All cashreg consumed by supplier manual — below threshold
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2024-08", "revenue_ge": 250000.0}]},
        tbc_card_income_bundle={"lines": [{"თარიღი": "2024-08-05", "თანხა": 200000.0}]},
        bog_pos_income_bundle={"lines": [{"თარიღი": "2024-08-10", "თანხა": 49000.0}]},
        manual_journal_full=[{"თარიღი": "2024-08-07", "თანხა": 1000.0}],
    )
    loader = _fake_data_loader(bundle)
    out = explain_unaccounted_cash(loader, period="2024-08")
    assert out["needs_user_input"] is False


def test_record_cash_outflow_writes_and_previews(tmp_path: Path) -> None:
    fa_dir = tmp_path / "Financial_Analysis"
    fa_dir.mkdir()
    loader = _fake_data_loader(_fixture_bundle())
    out = record_cash_outflow(
        loader,
        project_root=str(tmp_path),
        period="2024-08",
        amount_ge=15000,
        purpose_ka="ხელფასი ხელზე",
        category="salary_cash",
    )
    assert out["status"] == "ok"
    assert out["entry"]["amount_ge"] == 15000
    assert out["requires_pipeline_rerun"] is True
    # preview_vat = remaining * 0.18
    expected_remaining = max(0.0, out["previous_unaccounted_ge"] - 15000)
    assert out["remaining_unaccounted_preview_ge"] == pytest.approx(expected_remaining)
    assert out["preview_vat_liability_ge"] == pytest.approx(expected_remaining * VAT_RATE)
    # File actually written
    journal = fa_dir / "cash_outflow_journal.csv"
    assert journal.exists()
    entries = parse_cash_outflow_journal(str(journal))
    assert len(entries) == 1


def test_record_cash_outflow_rejects_bad_category(tmp_path: Path) -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = record_cash_outflow(
        loader,
        project_root=str(tmp_path),
        period="2024-08",
        amount_ge=1000,
        purpose_ka="x",
        category="alien",
    )
    assert "error" in out
    assert "allowed_categories" in out


def test_record_cash_outflow_rejects_bad_period(tmp_path: Path) -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = record_cash_outflow(
        loader,
        project_root=str(tmp_path),
        period="08-2024",
        amount_ge=1000,
        purpose_ka="x",
        category="unknown",
    )
    assert "error" in out


def test_record_cash_outflow_rejects_zero_amount(tmp_path: Path) -> None:
    loader = _fake_data_loader(_fixture_bundle())
    out = record_cash_outflow(
        loader,
        project_root=str(tmp_path),
        period="2024-08",
        amount_ge=0,
        purpose_ka="x",
        category="unknown",
    )
    assert "error" in out


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def test_tool_schemas_register_vat_tools() -> None:
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    names = [t["name"] for t in TOOL_SCHEMAS]
    assert "get_vat_reconciliation_month" in names
    assert "explain_unaccounted_cash" in names
    assert "record_cash_outflow" in names


def test_tool_schemas_vat_month_requires_period() -> None:
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "get_vat_reconciliation_month")
    assert tool["input_schema"]["required"] == ["period"]
    assert tool["input_schema"]["properties"]["period"]["pattern"] == r"^\d{4}-\d{2}$"


def test_tool_schemas_record_outflow_category_enum() -> None:
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "record_cash_outflow")
    cat_enum = tool["input_schema"]["properties"]["category"]["enum"]
    assert "salary_cash" in cat_enum
    assert "personal_withdrawal" in cat_enum
    assert "unknown" in cat_enum
    assert set(cat_enum) == set(CATEGORY_VAT_DEFAULTS.keys())


def test_vat_reconciliation_in_allowed_sections() -> None:
    from dashboard_pipeline.ai.tools import ALLOWED_SECTIONS

    assert "vat_reconciliation" in ALLOWED_SECTIONS


# ---------------------------------------------------------------------------
# Sprint 5.9 — MAX data gap detection (correctness fix)
# ---------------------------------------------------------------------------


def test_max_data_gap_sets_insufficient_status_when_banks_active() -> None:
    """Missing MAX Excel but banks show activity → status 'insufficient_data',
    NOT a false red/yellow signal based on negative gap."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": []},  # no MAX file for this month
        tbc_card_income_bundle={"lines": [
            {"თარიღი": "2023-03-05", "თანხა": 15000.0},
        ]},
        bog_pos_income_bundle={"lines": [
            {"თარიღი": "2023-03-10", "თანხა": 25000.0},
        ]},
        manual_journal_full=[],
    )
    row = bundle["by_month"][0]
    assert row["period"] == "2023-03"
    assert row["status"] == "insufficient_data"
    assert row["data_quality"]["max_data_gap_suspected"] is True
    assert row["max_pos_ge"] == 0
    assert row["bank_card_ge"] == pytest.approx(40000.0)


def test_max_data_gap_suspected_when_declared_exists_but_max_missing(tmp_path: Path) -> None:
    """Audit Excel shows declared 150K but pipeline has no MAX → insufficient_data."""
    audit_f = tmp_path / "გაანგარიშება.xlsx"
    _write_audit_excel(audit_f, [
        {"period": 202303, "declared": 150000, "af": 20000, "cashreg": 80000, "tbc": 50000, "bog": 0},
    ])
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": []},  # MAX missing
        tbc_card_income_bundle={"lines": []},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
        audit_excel_path=str(audit_f),
    )
    row = bundle["by_month"][0]
    assert row["status"] == "insufficient_data"
    assert row["data_quality"]["max_data_gap_suspected"] is True
    # declared is preserved for transparency
    assert row["declared_ge"] == pytest.approx(150000.0)


def test_max_data_gap_not_flagged_when_both_max_and_banks_present() -> None:
    """Normal month — MAX present, banks present → max_data_gap_suspected=False."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2024-08", "revenue_ge": 282314.0}]},
        tbc_card_income_bundle={"lines": [{"თარიღი": "2024-08-05", "თანხა": 100000.0}]},
        bog_pos_income_bundle={"lines": [{"თარიღი": "2024-08-10", "თანხა": 50000.0}]},
        manual_journal_full=[],
    )
    row = bundle["by_month"][0]
    assert row["data_quality"]["max_data_gap_suspected"] is False
    assert row["status"] != "insufficient_data"


def test_max_data_gap_not_flagged_when_everything_empty() -> None:
    """Genuinely empty month (no MAX, no banks, no declared) → not a data gap
    worth flagging; stays as no_declared_data."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2024-08", "revenue_ge": 0}]},
        tbc_card_income_bundle={"lines": []},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[
            {"თარიღი": "2024-08-01", "თანხა": 0.0},  # keeps the period alive
        ],
    )
    if bundle["by_month"]:
        row = bundle["by_month"][0]
        # No banks + no declared → neither insufficient_data nor red. Likely
        # no_declared_data (if declared null). The point is NOT insufficient_data
        # since banks = 0 = MAX → no conflict.
        assert row["data_quality"]["max_data_gap_suspected"] is False
        assert row["status"] != "insufficient_data"


def test_summary_counts_insufficient_data_months() -> None:
    """summary.months_insufficient_data counter is present + correct."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": [{"month": "2024-08", "revenue_ge": 100000}]},
        tbc_card_income_bundle={"lines": [
            {"თარიღი": "2023-03-05", "თანხა": 15000.0},  # 2023-03 will be insufficient
            {"თარიღი": "2024-08-05", "თანხა": 50000.0},
        ]},
        bog_pos_income_bundle={"lines": [
            {"თარიღი": "2023-03-10", "თანხა": 25000.0},
        ]},
        manual_journal_full=[],
    )
    assert bundle["summary"]["months_insufficient_data"] == 1
    # 2024-08 is NOT insufficient (MAX available)
    m_2408 = next(r for r in bundle["by_month"] if r["period"] == "2024-08")
    assert m_2408["data_quality"]["max_data_gap_suspected"] is False


def test_methodology_documents_insufficient_data_rule() -> None:
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": []},
        tbc_card_income_bundle={"lines": []},
        bog_pos_income_bundle={"lines": []},
        manual_journal_full=[],
    )
    meta = bundle["methodology_ka"]
    assert "max_data_gap_suspected" in meta
    assert "Sprint 5.9" in meta
    assert "insufficient_data" in meta


def test_get_vat_month_summary_ka_warns_on_insufficient_data() -> None:
    """AI-facing summary_ka must carry a loud warning when MAX is missing —
    so AI does NOT interpret negative gap as over-declaration."""
    bundle = compute_vat_reconciliation(
        retail_sales_bundle={"by_month": []},
        tbc_card_income_bundle={"lines": [{"თარიღი": "2023-03-05", "თანხა": 15000.0}]},
        bog_pos_income_bundle={"lines": [{"თარიღი": "2023-03-10", "თანხა": 25000.0}]},
        manual_journal_full=[],
    )
    loader = _fake_data_loader(bundle)
    out = get_vat_reconciliation_month(loader, period="2023-03")
    summary = out["summary_ka"]
    assert "MAX retail_sales Excel ფაილი აკლია" in summary
    assert "data gap, არა over-declaration" in summary


def test_classify_status_insufficient_data_overrides_gap_direction() -> None:
    """_classify_status directly: max_data_gap_suspected=True overrides normal
    red/yellow/green classification, regardless of gap."""
    # Even a massive negative gap (declared >> real) returns insufficient_data
    assert _classify_status(
        gap=-200000, declared=150000, has_unaccounted=False, max_data_gap_suspected=True
    ) == "insufficient_data"
    # Massive positive gap (real >> declared) ALSO returns insufficient_data
    assert _classify_status(
        gap=200000, declared=150000, has_unaccounted=False, max_data_gap_suspected=True
    ) == "insufficient_data"
    # Without the flag, same inputs → red
    assert _classify_status(
        gap=-200000, declared=150000, has_unaccounted=False, max_data_gap_suspected=False
    ) == "red"


# ---------------------------------------------------------------------------
# Phase 4C.1 — Schema Poka-yoke markers for VAT tools (Sprint 5.8 audit)
# ---------------------------------------------------------------------------


def test_vat_month_schema_documents_by_shop() -> None:
    """Sprint 5.8 — `by_shop` dimension must be surfaced in the tool description
    so AI knows to reach for it on per-shop questions."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "get_vat_reconciliation_month")
    desc = tool["description"]
    assert "by_shop" in desc
    assert "Sprint 5.8" in desc
    assert "ოზურგეთი" in desc
    assert "დვაბზუ" in desc
    # Honesty flag must be referenced.
    assert "tbc_per_shop_reliable" in desc


def test_vat_month_schema_has_per_shop_trigger() -> None:
    """Per-shop question ('რომელ მაღაზიაშია ხარვეზი') must appear in triggers."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "get_vat_reconciliation_month")
    desc = tool["description"]
    assert "რომელ მაღაზიაშია ხარვეზი" in desc


def test_vat_month_schema_has_per_shop_anti_trigger() -> None:
    """Pure per-shop revenue comparison (no audit) should route to retail_sales,
    not vat_reconciliation. Anti-trigger must say so."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "get_vat_reconciliation_month")
    desc = tool["description"]
    assert "per-shop revenue comparison WITHOUT audit" in desc
    assert "retail_sales" in desc


def test_explain_unaccounted_has_below_threshold_anti_trigger() -> None:
    """Months with cash_unaccounted < threshold should not be interrogated."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "explain_unaccounted_cash")
    desc = tool["description"]
    assert "< threshold_ge" in desc
    assert "5,000 ₾" in desc
    assert "do NOT prompt the user unnecessarily" in desc


def test_record_cash_outflow_has_strict_dont_guess_rule() -> None:
    """User said 'accurate analysis' — record_cash_outflow must forbid AI from
    guessing amount/category when user input is ambiguous."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "record_cash_outflow")
    desc = tool["description"]
    assert "STRICT: do not guess" in desc
    # All 4 args must be covered by the strict block.
    for arg in ("amount_ge", "category", "purpose_ka", "vat_applies"):
        assert arg in desc
    # Range ambiguity anti-pattern.
    assert "10-15K" in desc
    # Category ambiguity anti-pattern.
    assert "ხელზე" in desc


def test_record_cash_outflow_has_append_only_anti_trigger() -> None:
    """CSV is append-only — modifying past entries requires explicit user confirmation."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "record_cash_outflow")
    desc = tool["description"]
    assert "append-only" in desc
    assert "modifying a past entry" in desc


def test_vat_month_schema_has_data_gap_guard() -> None:
    """Sprint 5.9 — AI must be warned about insufficient_data status so it
    doesn't misread negative gap as over-declaration."""
    from dashboard_pipeline.ai.tools import TOOL_SCHEMAS

    tool = next(t for t in TOOL_SCHEMAS if t["name"] == "get_vat_reconciliation_month")
    desc = tool["description"]
    assert "insufficient_data" in desc
    assert "max_data_gap_suspected" in desc
    assert "Sprint 5.9" in desc
    # AI is told explicitly NOT to conclude.
    assert "DO NOT assert any reconciliation conclusion" in desc


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT_KA presence
# ---------------------------------------------------------------------------

def test_system_prompt_has_vat_section() -> None:
    from dashboard_pipeline.ai.prompts import SYSTEM_PROMPT_KA

    assert "VAT / აუდიტის კონსულტაცია" in SYSTEM_PROMPT_KA
    assert "get_vat_reconciliation_month" in SYSTEM_PROMPT_KA
    assert "explain_unaccounted_cash" in SYSTEM_PROMPT_KA
    assert "record_cash_outflow" in SYSTEM_PROMPT_KA
    # 18% VAT reference
    assert "18%" in SYSTEM_PROMPT_KA or "18 %" in SYSTEM_PROMPT_KA
    # Trigger keywords
    assert "აუდიტი" in SYSTEM_PROMPT_KA
    assert "declared" in SYSTEM_PROMPT_KA
    assert "ბრუნვა" in SYSTEM_PROMPT_KA
