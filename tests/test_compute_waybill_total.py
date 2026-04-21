"""Regression tests for compute_waybill_total.

Root-cause evidence (captured 2026-04-18):
- User asked "how much waybills came in on 2026-02-27".
- Chat AI answered "7,246 ₾" — WRONG (no combination of date column + filter
  rule actually produces 7,246 from the Excel source; pure LLM hallucination).
- Excel ground truth: `ტრანსპ. დაწყება == 2026-02-27` + exclude `უკან დაბრუნება`
  yields exactly 7,882.68 ₾ across 23 rows (nominal_amount sum).
- Root cause #1: pipeline only exposed `გააქტიურების თარ.` as `date`, losing
  transport-start semantics that actually matter for "ზედნადები შემოვიდა".
- Root cause #2: chat AI had no arithmetic tool — mentally summing rows from
  a truncated list routinely hallucinates.

Fix shipped:
- generate_dashboard_data.py: waybills now include `date` +
  `transport_start_date` + `delivery_date`.
- tools.py: `compute_waybill_total` tool (server-side sum).
- prompts.py: chat-mode prompt mandates the tool + clarifying questions.

These tests pin the exact 7,882.68 baseline and the date-field selection
behavior so this class of bug cannot silently regress.
"""

from __future__ import annotations

import pytest

from dashboard_pipeline.ai.tools import (
    TOOL_SCHEMAS,
    ToolDispatcher,
    compute_waybill_total,
)


# ---------------------------------------------------------------------------
# Synthetic data mirroring the real Feb 27, 2026 waybill pattern
# ---------------------------------------------------------------------------

def _feb27_2026_fixture():
    """Minimal synthetic data.json that reproduces the 7,882.68 ground truth.

    Mixes rows that match Feb 27 on different date fields so tests can
    distinguish `date` vs `transport_start_date` vs `delivery_date`.
    """
    return {
        "waybills": [
            # Regular active row — transport_start_date = 2026-02-27.
            {
                "date": "2026-02-26 18:00:00",
                "transport_start_date": "2026-02-27 09:00:00",
                "delivery_date": "2026-02-28 12:00:00",
                "supplier": "(204920381-დღგ) შპს ელიზი ჯგუფი",
                "waybill_number": "WB-A",
                "nominal_amount": 5000.00,
                "effective_amount": 5000.00,
                "status": "დასრულებული",
                "type": "ქვე-ზედნადები",
            },
            # Active row — transport_start_date = 2026-02-27, same-day activation.
            {
                "date": "2026-02-27 08:00:00",
                "transport_start_date": "2026-02-27 10:00:00",
                "delivery_date": "2026-02-27 20:00:00",
                "supplier": "(237077961-დღგ) შპს ვასაძის პური",
                "waybill_number": "WB-B",
                "nominal_amount": 2882.68,
                "effective_amount": 2882.68,
                "status": "დასრულებული",
                "type": "ქვე-ზედნადები",
            },
            # Return — transport_start_date = 2026-02-27 BUT must be excluded.
            {
                "date": "2026-02-27 11:00:00",
                "transport_start_date": "2026-02-27 11:00:00",
                "delivery_date": "2026-02-27 15:00:00",
                "supplier": "(237077961-დღგ) შპს ვასაძის პური",
                "waybill_number": "WB-C",
                "nominal_amount": -20.00,
                "effective_amount": -20.00,
                "status": "აქტიური",
                "type": "უკან დაბრუნება",
            },
            # Cancelled — should also be excluded.
            {
                "date": "2026-02-27 12:00:00",
                "transport_start_date": "2026-02-27 12:00:00",
                "delivery_date": "2026-02-27 18:00:00",
                "supplier": "(111111111-დღგ) შპს X",
                "waybill_number": "WB-D",
                "nominal_amount": 999.00,
                "effective_amount": 0.0,
                "status": "გაუქმებული",
                "type": "ქვე-ზედნადები",
            },
            # Neighboring day — must NOT be picked up when filtering Feb 27.
            {
                "date": "2026-02-26 09:00:00",
                "transport_start_date": "2026-02-26 12:00:00",
                "delivery_date": "2026-02-26 18:00:00",
                "supplier": "(999999999-დღგ) შპს Y",
                "waybill_number": "WB-E",
                "nominal_amount": 1000.00,
                "effective_amount": 1000.00,
                "status": "დასრულებული",
                "type": "ქვე-ზედნადები",
            },
        ],
    }


def _loader():
    return _feb27_2026_fixture()


# ---------------------------------------------------------------------------
# Tool schema exposure
# ---------------------------------------------------------------------------

class TestToolSchemaExposure:
    def test_compute_waybill_total_in_tool_schemas(self):
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert "compute_waybill_total" in names

    def test_schema_declares_date_required(self):
        schema = next(t for t in TOOL_SCHEMAS if t["name"] == "compute_waybill_total")
        assert schema["input_schema"]["required"] == ["date"]

    def test_schema_date_field_enum(self):
        schema = next(t for t in TOOL_SCHEMAS if t["name"] == "compute_waybill_total")
        props = schema["input_schema"]["properties"]
        assert set(props["date_field"]["enum"]) == {
            "date",
            "transport_start_date",
            "delivery_date",
        }

    def test_schema_amount_field_enum(self):
        schema = next(t for t in TOOL_SCHEMAS if t["name"] == "compute_waybill_total")
        props = schema["input_schema"]["properties"]
        assert set(props["amount_field"]["enum"]) == {
            "nominal_amount",
            "effective_amount",
        }


# ---------------------------------------------------------------------------
# Primary regression — 7,882.68 baseline
# ---------------------------------------------------------------------------

class TestFeb27GroundTruth:
    """Pin the exact ground-truth baseline that the AI hallucinated away."""

    def test_transport_start_date_default_matches_7882_68(self):
        """Default path: transport_start_date + exclude returns & cancelled."""
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
        )
        assert "error" not in result, result
        # 5000.00 (WB-A) + 2882.68 (WB-B) = 7882.68
        # WB-C (return) excluded; WB-D (cancelled) excluded; WB-E (wrong date) excluded.
        assert result["matched_count"] == 2
        assert result["total"] == 7882.68
        assert result["date_field"] == "transport_start_date"
        assert result["amount_field"] == "nominal_amount"
        assert result["exclude_returns"] is True
        assert result["exclude_cancelled"] is True

    def test_including_returns_drops_by_return_amount(self):
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            exclude_returns=False,
        )
        # 7882.68 + (-20.00 from WB-C) = 7862.68
        assert result["matched_count"] == 3
        assert result["total"] == 7862.68

    def test_including_cancelled_adds_cancelled_nominal(self):
        """WB-D has nominal_amount=999.00 but status=გაუქმებული."""
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            exclude_cancelled=False,
        )
        # 7882.68 + 999.00 = 8881.68
        assert result["matched_count"] == 3
        assert result["total"] == 8881.68


# ---------------------------------------------------------------------------
# date_field selection
# ---------------------------------------------------------------------------

class TestDateFieldSelection:
    def test_date_field_date_filters_by_activation_only(self):
        """`date` field picks up WB-B (activated Feb 27) but not WB-A (activated Feb 26)."""
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            date_field="date",
        )
        # Only WB-B passes (activated Feb 27, not a return, not cancelled).
        assert result["matched_count"] == 1
        assert result["total"] == 2882.68

    def test_date_field_delivery_date(self):
        """`delivery_date` filter: WB-B + WB-E's neighbors — here WB-B only."""
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            date_field="delivery_date",
        )
        # WB-B (delivered Feb 27) passes. WB-A delivered Feb 28. WB-C return excluded.
        # WB-D cancelled excluded. WB-E delivered Feb 26.
        assert result["matched_count"] == 1
        assert result["total"] == 2882.68


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_missing_date_errors(self):
        result = compute_waybill_total(data_loader=_loader, date="")
        assert "error" in result
        assert "date" in result["error"].lower()

    def test_invalid_date_field_errors(self):
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            date_field="bogus_field",
        )
        assert "error" in result
        assert "date_field" in result["error"]

    def test_invalid_amount_field_errors(self):
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            amount_field="not_a_field",
        )
        assert "error" in result
        assert "amount_field" in result["error"]

    def test_missing_waybills_section_errors(self):
        result = compute_waybill_total(
            data_loader=lambda: {"other_section": []},
            date="2026-02-27",
        )
        assert "error" in result
        assert "waybills" in result["error"]


# ---------------------------------------------------------------------------
# Supplier filter + top_suppliers breakdown
# ---------------------------------------------------------------------------

class TestSupplierFilterAndBreakdown:
    def test_supplier_filter_substring(self):
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
            supplier="ვასაძის",
        )
        # Only WB-B (WB-C is a return, excluded by default).
        assert result["matched_count"] == 1
        assert result["total"] == 2882.68

    def test_top_suppliers_ordered_by_total_desc(self):
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02-27",
        )
        top = result.get("top_suppliers") or []
        assert len(top) == 2
        totals = [float(s["total"]) for s in top]
        assert totals == sorted(totals, reverse=True)
        # ელიზი ჯგუფი is larger (5000.00) than ვასაძის პური (2882.68).
        assert "ელიზი" in top[0]["supplier"]
        assert top[0]["total"] == 5000.00

    def test_top_suppliers_contains_count(self):
        result = compute_waybill_total(data_loader=_loader, date="2026-02-27")
        for s in result["top_suppliers"]:
            assert "count" in s
            assert isinstance(s["count"], int)


# ---------------------------------------------------------------------------
# ToolDispatcher integration
# ---------------------------------------------------------------------------

class TestDispatcherRouting:
    def test_dispatch_compute_waybill_total(self):
        disp = ToolDispatcher(_loader)
        result = disp.dispatch(
            "compute_waybill_total",
            {"date": "2026-02-27"},
        )
        assert "error" not in result
        assert result["total"] == 7882.68

    def test_dispatch_records_call_trace(self):
        disp = ToolDispatcher(_loader)
        disp.dispatch("compute_waybill_total", {"date": "2026-02-27"})
        assert len(disp.calls) == 1
        call = disp.calls[0]
        assert call["tool"] == "compute_waybill_total"
        assert call["arguments"]["date"] == "2026-02-27"
        # Summary exposes compute_waybill_total-specific keys.
        summary = call["result_summary"]
        assert summary["ok"] is True
        assert summary["matched_count"] == 2
        assert summary["total"] == 7882.68
        assert summary["date_field"] == "transport_start_date"


# ---------------------------------------------------------------------------
# Month-level query (substring match on YYYY-MM)
# ---------------------------------------------------------------------------

class TestMonthLevelQuery:
    def test_whole_month_2026_02_sums_both_active(self):
        """Feb 2026 total (excl. returns/cancelled) = WB-A + WB-B + WB-E."""
        result = compute_waybill_total(
            data_loader=_loader,
            date="2026-02",
        )
        # WB-A (Feb 27 transport) + WB-B (Feb 27 transport) + WB-E (Feb 26 transport).
        # WB-C return excluded; WB-D cancelled excluded.
        assert result["matched_count"] == 3
        assert result["total"] == 5000.00 + 2882.68 + 1000.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
