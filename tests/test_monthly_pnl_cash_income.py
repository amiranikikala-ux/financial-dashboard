"""Megaplus სალაროს wire-in — build_monthly_pnl + build_financial_ratios.

Pins the contract that monthly_pnl rows expose pos_income (bank card —
unchanged for UI compat), cash_income (Megaplus minus bank card), and
total_income (sum), and that build_financial_ratios reads the new
total_income field with fallback to pos_income for backward compat with
older monthly_pnl rows.

Formula mirrored from vat_reconciliation.py:524-525:
    cashreg_in = max(0, max_pos - bank_card)

Tests cover:
1. cash_income when MAX POS exceeds bank
2. cash_income clamps to 0 when bank exceeds MAX POS
3. per-(month, object) cash_income matches per-shop formula
4. invariant: total_income == pos_income + cash_income
5. pos_income field unchanged when retail bundle is missing (UI compat)
6. financial_ratios uses total_income when present
7. financial_ratios falls back to pos_income on legacy rows
8. period-filter callsite (api_contracts) threads retail bundle through
"""
from __future__ import annotations

from dashboard_pipeline.analytics_builders import (
    build_financial_ratios,
    build_monthly_pnl,
)


OBJECT_DVABZU = "დვაბზუ"
OBJECT_OZURGETI = "ოზურგეთი"


def _pos_line(date, obj, amount):
    # Pipeline POS rows always carry a full timestamp string; using just a date
    # falls into the dayfirst=True fallback in _month_key and flips the month.
    if len(str(date)) == 10:
        date = f"{date} 00:00:00"
    return {"თარიღი": date, "object": obj, "თანხა": amount}


def _make_pos_bundle(lines):
    return {"pnl_lines": lines}


def _make_retail_bundle(rows):
    """rows: list of (month, object, revenue_ge[, cost_ge]) tuples.

    cost_ge is optional; defaults to 0 when not supplied (legacy tests don't
    care about COGS).
    """
    bundle_rows = []
    for row in rows:
        month, obj, revenue = row[0], row[1], row[2]
        cost = row[3] if len(row) >= 4 else 0
        bundle_rows.append({
            "month": month,
            "object": obj,
            "revenue_ge": revenue,
            "cost_ge": cost,
        })
    return {"by_object_by_month": bundle_rows}


def _make_supplier_payment_lines(by_month):
    """by_month: dict {YYYY-MM: total_amount}. Builds a single fake tax_id
    line per month so the date→month aggregation in
    _supplier_payments_by_month can sum it up.
    """
    return {
        "999999999": [
            {"date": f"{m}-15", "amount": amt, "source": "TBC", "purpose": "test"}
            for m, amt in by_month.items()
        ]
    }


def _make_object_mapping():
    return {"default_object": "გაუნაწილებელი"}


# ---------------------------------------------------------------------------
# 1. cash_income when MAX POS > bank_card → cashreg_in = MAX − bank
# ---------------------------------------------------------------------------

def test_cash_income_when_max_exceeds_bank():
    pos = _make_pos_bundle(
        [_pos_line("2026-03-15", OBJECT_DVABZU, 50_000.0)]
    )
    retail = _make_retail_bundle(
        [("2026-03", OBJECT_DVABZU, 80_000.0)]
    )
    out = build_monthly_pnl(pos, None, _make_object_mapping(), retail_sales_bundle=retail)
    assert len(out) == 1
    row = out[0]
    assert row["month"] == "2026-03"
    obj = row["objects"][OBJECT_DVABZU]
    assert obj["pos_income"] == 50_000.0
    assert obj["cash_income"] == 30_000.0
    assert obj["total_income"] == 80_000.0
    assert row["total"]["pos_income"] == 50_000.0
    assert row["total"]["cash_income"] == 30_000.0
    assert row["total"]["total_income"] == 80_000.0


# ---------------------------------------------------------------------------
# 2. cash_income clamps to 0 when bank_card > MAX POS (data anomaly)
# ---------------------------------------------------------------------------

def test_cash_income_zero_when_bank_exceeds_max():
    pos = _make_pos_bundle(
        [_pos_line("2026-03-15", OBJECT_DVABZU, 100_000.0)]
    )
    retail = _make_retail_bundle(
        [("2026-03", OBJECT_DVABZU, 60_000.0)]  # MAX < bank
    )
    out = build_monthly_pnl(pos, None, _make_object_mapping(), retail_sales_bundle=retail)
    obj = out[0]["objects"][OBJECT_DVABZU]
    assert obj["pos_income"] == 100_000.0
    assert obj["cash_income"] == 0.0
    assert obj["total_income"] == 100_000.0


# ---------------------------------------------------------------------------
# 3. per-(month, object) parity — per-shop cashreg_in matches per-shop formula
# ---------------------------------------------------------------------------

def test_per_object_cash_income_matches_per_shop_formula():
    pos = _make_pos_bundle([
        _pos_line("2026-03-10", OBJECT_DVABZU, 40_000.0),
        _pos_line("2026-03-20", OBJECT_OZURGETI, 60_000.0),
    ])
    retail = _make_retail_bundle([
        ("2026-03", OBJECT_DVABZU, 70_000.0),     # cash = 30K
        ("2026-03", OBJECT_OZURGETI, 100_000.0),  # cash = 40K
    ])
    out = build_monthly_pnl(pos, None, _make_object_mapping(), retail_sales_bundle=retail)
    objs = out[0]["objects"]
    assert objs[OBJECT_DVABZU]["cash_income"] == 30_000.0
    assert objs[OBJECT_OZURGETI]["cash_income"] == 40_000.0
    assert out[0]["total"]["cash_income"] == 70_000.0


# ---------------------------------------------------------------------------
# 4. invariant — total_income == pos_income + cash_income at every level
# ---------------------------------------------------------------------------

def test_total_income_equals_pos_plus_cash():
    pos = _make_pos_bundle([
        _pos_line("2026-01-15", OBJECT_DVABZU, 10_000.0),
        _pos_line("2026-02-15", OBJECT_DVABZU, 20_000.0),
        _pos_line("2026-02-15", OBJECT_OZURGETI, 30_000.0),
    ])
    retail = _make_retail_bundle([
        ("2026-01", OBJECT_DVABZU, 25_000.0),
        ("2026-02", OBJECT_DVABZU, 50_000.0),
        ("2026-02", OBJECT_OZURGETI, 70_000.0),
    ])
    out = build_monthly_pnl(pos, None, _make_object_mapping(), retail_sales_bundle=retail)
    for row in out:
        total = row["total"]
        assert abs(total["total_income"] - (total["pos_income"] + total["cash_income"])) < 1e-6
        for obj_data in row["objects"].values():
            assert abs(
                obj_data["total_income"]
                - (obj_data["pos_income"] + obj_data["cash_income"])
            ) < 1e-6


# ---------------------------------------------------------------------------
# 5. UI-compat regression — pos_income unchanged when retail bundle is missing
# ---------------------------------------------------------------------------

def test_pos_income_field_unchanged_when_retail_bundle_missing():
    pos = _make_pos_bundle([
        _pos_line("2026-03-15", OBJECT_DVABZU, 50_000.0),
    ])
    out = build_monthly_pnl(pos, None, _make_object_mapping())
    assert len(out) == 1
    row = out[0]
    obj = row["objects"][OBJECT_DVABZU]
    assert obj["pos_income"] == 50_000.0
    assert obj["cash_income"] == 0.0
    assert obj["total_income"] == 50_000.0
    assert row["total"]["pos_income"] == 50_000.0


# ---------------------------------------------------------------------------
# 6. build_financial_ratios uses total_income when present
# ---------------------------------------------------------------------------

def test_financial_ratios_uses_total_income_when_present():
    pos = _make_pos_bundle([
        _pos_line("2026-03-15", OBJECT_DVABZU, 100_000.0),
    ])
    retail = _make_retail_bundle([
        ("2026-03", OBJECT_DVABZU, 250_000.0),
    ])
    monthly_pnl = build_monthly_pnl(
        pos, None, _make_object_mapping(), retail_sales_bundle=retail
    )
    ratios = build_financial_ratios(monthly_pnl, [], [])
    # total_income at company level should match retail revenue (pos + cash)
    assert ratios["company"]["total_income"] == 250_000.0


# ---------------------------------------------------------------------------
# 7. build_financial_ratios falls back to pos_income on legacy monthly rows
# ---------------------------------------------------------------------------

def test_financial_ratios_falls_back_to_pos_income():
    legacy_monthly = [
        {
            "month": "2026-03",
            "objects": {
                OBJECT_DVABZU: {"pos_income": 100_000.0, "expenses": 0.0, "net": 100_000.0},
            },
            "total": {"pos_income": 100_000.0, "expenses": 0.0, "net": 100_000.0},
        }
    ]
    ratios = build_financial_ratios(legacy_monthly, [], [])
    assert ratios["company"]["total_income"] == 100_000.0


# ---------------------------------------------------------------------------
# 8. period-filter callsite — retail bundle threaded through
# ---------------------------------------------------------------------------

def test_period_filter_response_includes_cash_income():
    from dashboard_pipeline.api_contracts import (
        _build_pnl_summary_response,
        _filter_retail_sales_bundle_by_months,
    )
    from dashboard_pipeline.date_filters import build_period_filter

    cache = {
        "object_mapping": _make_object_mapping(),
        "pos_terminal_income": {
            "pnl_lines": [
                _pos_line("2026-03-15", OBJECT_DVABZU, 50_000.0),
                _pos_line("2026-04-15", OBJECT_DVABZU, 60_000.0),
            ],
        },
        "tbc_expenses": {"categories": []},
        "bog_expenses": {"categories": []},
        "retail_sales": _make_retail_bundle([
            ("2026-03", OBJECT_DVABZU, 80_000.0),
            ("2026-04", OBJECT_DVABZU, 90_000.0),
        ]),
        "monthly_pnl": [],
    }

    period_filter = build_period_filter(
        from_date="2026-03-01", to_date="2026-03-31"
    )
    resp = _build_pnl_summary_response(cache, period_filter=period_filter)
    rows = resp["monthly_pnl"]
    march_rows = [r for r in rows if r["month"] == "2026-03"]
    assert len(march_rows) == 1
    march_total = march_rows[0]["total"]
    assert march_total["pos_income"] == 50_000.0
    assert march_total["cash_income"] == 30_000.0
    assert march_total["total_income"] == 80_000.0
    # April outside the filter — must NOT appear in the filtered response.
    april_rows = [r for r in rows if r["month"] == "2026-04"]
    assert april_rows == []

    # Helper test: slicing produces a thin bundle.
    sliced = _filter_retail_sales_bundle_by_months(cache["retail_sales"], {"2026-03"})
    assert sliced is not None
    assert len(sliced["by_object_by_month"]) == 1
    assert sliced["by_object_by_month"][0]["month"] == "2026-03"


# ---------------------------------------------------------------------------
# 9. cogs surfaces from retail_sales.cost_ge per (object, month)
# ---------------------------------------------------------------------------

def test_cogs_per_object_from_retail_bundle():
    pos = _make_pos_bundle([
        _pos_line("2026-03-15", OBJECT_DVABZU, 50_000.0),
    ])
    retail = _make_retail_bundle([
        ("2026-03", OBJECT_DVABZU, 80_000.0, 65_000.0),  # cogs = 65K
    ])
    out = build_monthly_pnl(
        pos, None, _make_object_mapping(), retail_sales_bundle=retail
    )
    obj = out[0]["objects"][OBJECT_DVABZU]
    assert obj["cogs"] == 65_000.0
    assert obj["gross_margin"] == 80_000.0 - 65_000.0
    assert out[0]["total"]["cogs"] == 65_000.0
    assert out[0]["total"]["gross_margin"] == 15_000.0


# ---------------------------------------------------------------------------
# 10. supplier_payments aggregate from supplier_payment_lines per month
# ---------------------------------------------------------------------------

def test_supplier_payments_aggregated_by_month():
    pos = _make_pos_bundle([
        _pos_line("2026-03-15", OBJECT_DVABZU, 50_000.0),
    ])
    retail = _make_retail_bundle([
        ("2026-03", OBJECT_DVABZU, 80_000.0, 65_000.0),
    ])
    spl = _make_supplier_payment_lines({"2026-03": 40_000.0})
    out = build_monthly_pnl(
        pos, None, _make_object_mapping(),
        retail_sales_bundle=retail, supplier_payment_lines=spl,
    )
    total = out[0]["total"]
    assert total["supplier_payments"] == 40_000.0
    # operating_expenses = expenses (0 here) − supplier_payments → −40K
    # (expenses bucket is empty in this fixture; the formula still applies)
    assert total["operating_expenses"] == 0.0 - 40_000.0
    # net_profit = gross_margin − operating_expenses
    assert total["net_profit"] == 15_000.0 - (0.0 - 40_000.0)


# ---------------------------------------------------------------------------
# 11. real P&L identity: net_profit == gross_margin − operating_expenses
# ---------------------------------------------------------------------------

def test_real_pnl_identity_holds():
    """End-to-end: realistic numbers, all four accrual fields consistent."""
    pos = _make_pos_bundle([
        _pos_line("2026-03-15", OBJECT_DVABZU, 100_000.0),
    ])
    retail = _make_retail_bundle([
        ("2026-03", OBJECT_DVABZU, 250_000.0, 200_000.0),  # 250K rev, 200K cogs
    ])
    # Mock expenses: 180K total bank outflow
    tbc_bundle = {
        "categories": [
            {
                "lines": [
                    {"თარიღი": "2026-03-15 00:00:00", "object": OBJECT_DVABZU,
                     "თანხა": 180_000.0},
                ],
            },
        ],
    }
    spl = _make_supplier_payment_lines({"2026-03": 150_000.0})  # 150K to suppliers
    out = build_monthly_pnl(
        pos, tbc_bundle, _make_object_mapping(),
        retail_sales_bundle=retail, supplier_payment_lines=spl,
    )
    total = out[0]["total"]
    # Sanity
    assert total["total_income"] == 250_000.0
    assert total["cogs"] == 200_000.0
    assert total["gross_margin"] == 50_000.0
    assert total["expenses"] == 180_000.0
    assert total["supplier_payments"] == 150_000.0
    assert total["operating_expenses"] == 30_000.0  # 180K − 150K
    assert total["net_profit"] == 20_000.0  # 50K − 30K
    # Margin percentages
    assert total["gross_margin_pct"] == 20.0
    assert total["net_margin_pct"] == 8.0


# ---------------------------------------------------------------------------
# 12. backward-compat: when supplier_payment_lines is None,
#     operating_expenses == expenses (legacy behaviour for old fixtures)
# ---------------------------------------------------------------------------

def test_operating_expenses_falls_back_when_no_supplier_lines():
    pos = _make_pos_bundle([
        _pos_line("2026-03-15", OBJECT_DVABZU, 100_000.0),
    ])
    tbc_bundle = {
        "categories": [
            {
                "lines": [
                    {"თარიღი": "2026-03-15 00:00:00", "object": OBJECT_DVABZU,
                     "თანხა": 70_000.0},
                ],
            },
        ],
    }
    out = build_monthly_pnl(pos, tbc_bundle, _make_object_mapping())
    total = out[0]["total"]
    assert total["expenses"] == 70_000.0
    assert total["supplier_payments"] == 0.0
    assert total["operating_expenses"] == 70_000.0  # no subtraction
