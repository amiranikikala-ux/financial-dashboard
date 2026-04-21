"""Phase 4A Part B — `/api/debt-plan` + `/api/debt-plan/save` endpoint tests.

Covers:
* Helper coercion (`_coerce_optional_int`, `_coerce_priority_list`) raises
  the right ``HTTPException(400)`` on bad input.
* `POST /api/debt-plan` routes to ``build_debt_repayment_plan`` with the
  exact coerced args and returns the plan JSON.
* `POST /api/debt-plan/save` routes to ``add_journal_entry(kind="repayment_plan")``.
* Error paths: bad body / bad types / upstream exceptions mapped to 500.

Uses FastAPI's ``TestClient`` with ``monkeypatch`` to stub the heavy
downstream helpers so tests run in milliseconds without ChromaDB or
data.json.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import server


# ---------------------------------------------------------------------------
# Helper coercion — direct unit tests
# ---------------------------------------------------------------------------


class TestCoerceOptionalInt:
    def test_none_returns_none(self):
        assert server._coerce_optional_int(None, field="x") is None

    def test_empty_string_returns_none(self):
        assert server._coerce_optional_int("", field="x") is None

    def test_int_passthrough(self):
        assert server._coerce_optional_int(4, field="x") == 4

    def test_numeric_string(self):
        assert server._coerce_optional_int("7", field="x") == 7

    def test_numeric_string_with_whitespace(self):
        assert server._coerce_optional_int("  3  ", field="x") == 3

    def test_bool_rejected(self):
        with pytest.raises(HTTPException) as exc:
            server._coerce_optional_int(True, field="max_priority_count")
        assert exc.value.status_code == 400
        assert "max_priority_count" in exc.value.detail

    def test_non_numeric_string_rejected(self):
        with pytest.raises(HTTPException) as exc:
            server._coerce_optional_int("abc", field="plan_duration_months")
        assert exc.value.status_code == 400
        assert "plan_duration_months" in exc.value.detail

    def test_weird_type_rejected(self):
        with pytest.raises(HTTPException) as exc:
            server._coerce_optional_int([1], field="plan_duration_months")
        assert exc.value.status_code == 400


class TestCoercePriorityList:
    def test_none_returns_none(self):
        assert server._coerce_priority_list(None) is None

    def test_empty_list_returns_none(self):
        # All entries stripped → nothing left → None
        assert server._coerce_priority_list([]) is None

    def test_whitespace_only_entries_skipped(self):
        assert server._coerce_priority_list(["  ", "", "\t"]) is None

    def test_happy_path(self):
        result = server._coerce_priority_list(["ვასაძე", "  კოკაკოლა  "])
        assert result == ["ვასაძე", "კოკაკოლა"]

    def test_mixed_token_strip(self):
        result = server._coerce_priority_list(["406181616", " ჯიდიაი "])
        assert result == ["406181616", "ჯიდიაი"]

    def test_non_list_rejected(self):
        with pytest.raises(HTTPException) as exc:
            server._coerce_priority_list("not a list")
        assert exc.value.status_code == 400
        assert "priority_suppliers" in exc.value.detail

    def test_non_string_element_rejected(self):
        with pytest.raises(HTTPException) as exc:
            server._coerce_priority_list(["ვასაძე", 123])
        assert exc.value.status_code == 400
        assert "strings" in exc.value.detail

    def test_too_many_entries_rejected(self):
        too_many = [f"supplier_{i}" for i in range(9)]
        with pytest.raises(HTTPException) as exc:
            server._coerce_priority_list(too_many)
        assert exc.value.status_code == 400
        assert "8" in exc.value.detail


# ---------------------------------------------------------------------------
# `/api/debt-plan` — happy paths + input validation
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_plan() -> Dict[str, Any]:
    """Minimal plan shape matching ``build_debt_repayment_plan`` output."""
    return {
        "as_of_date": "2026-04-21",
        "plan_duration_months": 2,
        "forecast": {
            "monthly_inflow_ge": 142_000,
            "low_ge": 128_000,
            "high_ge": 156_000,
            "trend": "stable",
            "method": "3-month moving average",
            "window_months": ["2026-01", "2026-02", "2026-03"],
        },
        "priority_suppliers": [
            {
                "tax_id": "406181616",
                "org": "შპს ჯიდიაი",
                "total_debt_ge": 313_000,
                "days_since_last": 6,
                "criticality_score": 0.78,
                "criticality_reasons": ["დიდი ვალი", "ხშირი მიწოდება"],
                "historical_monthly_paid_ge": 25_700,
                "recommended_monthly_payment_ge": 46_300,
                "recommended_weekly_payment_ge": 11_500,
                "days_to_clear_est": 42,
                "confidence_label": "🟢 მაღალი",
                "rationale_ka": "—",
            }
        ],
        "non_priority_summary": {
            "supplier_count": 265,
            "total_baseline_monthly_ge": 92_000,
            "average_per_supplier_ge": 347,
            "note_ka": "—",
        },
        "allocation_summary": {
            "priority_monthly_ge": 46_300,
            "non_priority_monthly_ge": 92_000,
            "buffer_ge": 3_700,
            "buffer_pct": 2.6,
            "forecast_ge": 142_000,
            "sustainable": True,
        },
        "risks": [],
        "summary_ka": "2-თვიანი გეგმა — 1 priority",
        "notes": [],
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(server.app)


@pytest.fixture
def patch_build_plan(monkeypatch: pytest.MonkeyPatch, fake_plan: Dict[str, Any]):
    """Patch the lazy-imported ``build_debt_repayment_plan`` symbol.

    ``server.post_debt_plan`` imports ``build_debt_repayment_plan`` from
    the module at call time, so we patch the module attribute rather
    than a bound reference in server.
    """
    captured: Dict[str, Any] = {}

    def _fake_plan(data_loader, *, priority_suppliers, plan_duration_months, max_priority_count):
        captured["data_loader"] = data_loader
        captured["priority_suppliers"] = priority_suppliers
        captured["plan_duration_months"] = plan_duration_months
        captured["max_priority_count"] = max_priority_count
        return fake_plan

    import dashboard_pipeline.ai.debt_plan as debt_plan_module

    monkeypatch.setattr(
        debt_plan_module, "build_debt_repayment_plan", _fake_plan,
    )
    return captured


class TestPostDebtPlan:
    def test_happy_path_empty_body(
        self, client, patch_build_plan, fake_plan,
    ):
        resp = client.post("/api/debt-plan", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_duration_months"] == 2
        assert body["priority_suppliers"][0]["org"] == "შპს ჯიდიაი"
        # No args passed → all None (so tool applies its own defaults)
        assert patch_build_plan["priority_suppliers"] is None
        assert patch_build_plan["plan_duration_months"] is None
        assert patch_build_plan["max_priority_count"] is None

    def test_happy_path_all_args(
        self, client, patch_build_plan, fake_plan,
    ):
        resp = client.post(
            "/api/debt-plan",
            json={
                "priority_suppliers": ["ვასაძე", " კოკაკოლა "],
                "plan_duration_months": 3,
                "max_priority_count": 4,
            },
        )
        assert resp.status_code == 200
        assert patch_build_plan["priority_suppliers"] == ["ვასაძე", "კოკაკოლა"]
        assert patch_build_plan["plan_duration_months"] == 3
        assert patch_build_plan["max_priority_count"] == 4

    def test_data_loader_wired_to_load_full_data(
        self, client, patch_build_plan,
    ):
        client.post("/api/debt-plan", json={})
        # Server wires the endpoint to ``load_full_data`` so the plan
        # builder has live data.json access.
        assert patch_build_plan["data_loader"] is server.load_full_data

    def test_numeric_string_coerced(
        self, client, patch_build_plan,
    ):
        client.post(
            "/api/debt-plan",
            json={"plan_duration_months": "3", "max_priority_count": "5"},
        )
        assert patch_build_plan["plan_duration_months"] == 3
        assert patch_build_plan["max_priority_count"] == 5

    def test_invalid_priority_suppliers_type(self, client, patch_build_plan):
        resp = client.post(
            "/api/debt-plan",
            json={"priority_suppliers": "not a list"},
        )
        assert resp.status_code == 400
        assert "priority_suppliers" in resp.json()["detail"]

    def test_invalid_priority_element_type(self, client, patch_build_plan):
        resp = client.post(
            "/api/debt-plan",
            json={"priority_suppliers": [1, 2, 3]},
        )
        assert resp.status_code == 400
        assert "strings" in resp.json()["detail"]

    def test_too_many_priorities(self, client, patch_build_plan):
        resp = client.post(
            "/api/debt-plan",
            json={"priority_suppliers": [f"s{i}" for i in range(9)]},
        )
        assert resp.status_code == 400
        assert "8" in resp.json()["detail"]

    def test_invalid_plan_duration_string(self, client, patch_build_plan):
        resp = client.post(
            "/api/debt-plan",
            json={"plan_duration_months": "xyz"},
        )
        assert resp.status_code == 400
        assert "plan_duration_months" in resp.json()["detail"]

    def test_invalid_plan_duration_bool(self, client, patch_build_plan):
        resp = client.post(
            "/api/debt-plan",
            json={"plan_duration_months": True},
        )
        assert resp.status_code == 400

    def test_upstream_failure_mapped_to_500(
        self, client, monkeypatch: pytest.MonkeyPatch,
    ):
        def _raiser(*args, **kwargs):
            raise RuntimeError("data.json corrupted")

        import dashboard_pipeline.ai.debt_plan as debt_plan_module

        monkeypatch.setattr(
            debt_plan_module, "build_debt_repayment_plan", _raiser,
        )
        resp = client.post("/api/debt-plan", json={})
        assert resp.status_code == 500
        assert "RuntimeError" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# `/api/debt-plan/save` — journal persistence
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_add_journal(monkeypatch: pytest.MonkeyPatch):
    """Patch ``add_journal_entry`` to avoid hitting ChromaDB."""
    captured: Dict[str, Any] = {}

    def _fake_add(*, title, kind, tags=None, **kwargs):
        captured["title"] = title
        captured["kind"] = kind
        captured["tags"] = tags
        return {
            "ok": True,
            "entry_id": "journal_abc123",
            "title": title,
            "kind": kind,
            "tags": tags or [],
        }

    import dashboard_pipeline.ai.journal as journal_module

    monkeypatch.setattr(journal_module, "add_journal_entry", _fake_add)
    return captured


class TestPostDebtPlanSave:
    def test_happy_path(self, client, patch_add_journal):
        resp = client.post(
            "/api/debt-plan/save",
            json={
                "title": "📋 ვალების გეგმა — 5 priority @ 28,400 ₾/თვე",
                "tags": ["phase4a", "duration:2mo", "priority_count:5"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["entry_id"] == "journal_abc123"
        assert patch_add_journal["kind"] == "repayment_plan"
        assert "priority" in patch_add_journal["title"]
        assert patch_add_journal["tags"] == ["phase4a", "duration:2mo", "priority_count:5"]

    def test_title_trimmed(self, client, patch_add_journal):
        resp = client.post(
            "/api/debt-plan/save",
            json={"title": "   📋 test title   "},
        )
        assert resp.status_code == 200
        assert patch_add_journal["title"] == "📋 test title"

    def test_tags_optional(self, client, patch_add_journal):
        resp = client.post(
            "/api/debt-plan/save",
            json={"title": "📋 minimal"},
        )
        assert resp.status_code == 200
        assert patch_add_journal["tags"] is None

    def test_missing_title(self, client, patch_add_journal):
        resp = client.post("/api/debt-plan/save", json={})
        assert resp.status_code == 400
        assert "title" in resp.json()["detail"]

    def test_empty_title(self, client, patch_add_journal):
        resp = client.post(
            "/api/debt-plan/save",
            json={"title": "   "},
        )
        assert resp.status_code == 400

    def test_non_string_title(self, client, patch_add_journal):
        resp = client.post("/api/debt-plan/save", json={"title": 123})
        assert resp.status_code == 400

    def test_non_list_tags(self, client, patch_add_journal):
        resp = client.post(
            "/api/debt-plan/save",
            json={"title": "t", "tags": "not a list"},
        )
        assert resp.status_code == 400
        assert "tags" in resp.json()["detail"]

    def test_journal_error_propagates_as_400(
        self, client, monkeypatch: pytest.MonkeyPatch,
    ):
        def _fake_add(*, title, kind, tags=None, **kwargs):
            return {"ok": False, "error": "title too short (min 3 chars)"}

        import dashboard_pipeline.ai.journal as journal_module

        monkeypatch.setattr(journal_module, "add_journal_entry", _fake_add)
        resp = client.post(
            "/api/debt-plan/save",
            json={"title": "📋 x"},
        )
        assert resp.status_code == 400
        assert "title too short" in resp.json()["detail"]

    def test_journal_raises_mapped_to_500(
        self, client, monkeypatch: pytest.MonkeyPatch,
    ):
        def _raiser(**kwargs):
            raise RuntimeError("chromadb connection lost")

        import dashboard_pipeline.ai.journal as journal_module

        monkeypatch.setattr(journal_module, "add_journal_entry", _raiser)
        resp = client.post(
            "/api/debt-plan/save",
            json={"title": "📋 test"},
        )
        assert resp.status_code == 500
        assert "RuntimeError" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Route registration — catches typos / accidental removals
# ---------------------------------------------------------------------------


class TestDebtPlanRoutesRegistered:
    def test_generate_route_registered_post(self):
        routes = [r for r in server.app.routes if getattr(r, "path", "") == "/api/debt-plan"]
        assert len(routes) == 1
        assert "POST" in routes[0].methods

    def test_save_route_registered_post(self):
        routes = [r for r in server.app.routes if getattr(r, "path", "") == "/api/debt-plan/save"]
        assert len(routes) == 1
        assert "POST" in routes[0].methods


class TestJournalKindRegistration:
    def test_repayment_plan_in_journal_kinds(self):
        from dashboard_pipeline.ai.journal import JOURNAL_KINDS

        assert "repayment_plan" in JOURNAL_KINDS

    def test_journal_kinds_length_is_six(self):
        from dashboard_pipeline.ai.journal import JOURNAL_KINDS

        # Phase 3.1 grew 4→5 (+proposal); Phase 4A grew 5→6 (+repayment_plan).
        assert len(JOURNAL_KINDS) == 6
