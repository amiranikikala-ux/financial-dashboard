"""Integration tests for `/api/banks/refresh` and `/api/status` extension.

Uses FastAPI TestClient. The orchestrator (`refresh_all_banks`) is patched
via the `bank_refresh` module reference so no SOAP/HTTP fires. The
`_run_pipeline` thread-target is also stubbed to a no-op so we don't kick
the heavy subprocess during tests.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

import server
from dashboard_pipeline import bank_refresh as bank_refresh_module


@pytest.fixture
def reset_bank_state():
    """Reset the in-memory `_bank_refresh_status` between tests."""
    saved = dict(server._bank_refresh_status)
    server._bank_refresh_status.update({
        "state": "idle",
        "started_at": None,
        "completed_at": None,
        "last_error": None,
        "last_result": None,
        "runs_total": 0,
    })
    yield
    server._bank_refresh_status.clear()
    server._bank_refresh_status.update(saved)


@pytest.fixture
def disable_rate_limit():
    """Disable slowapi rate limiting so the test suite can fire repeated POSTs."""
    prior = server.limiter.enabled
    server.limiter.enabled = False
    yield
    server.limiter.enabled = prior


@pytest.fixture
def client(reset_bank_state, disable_rate_limit):
    return TestClient(server.app)


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Replace `_run_pipeline` with a no-op so endpoint tests don't kick it."""
    monkeypatch.setattr(server, "_run_pipeline", lambda: None)


@pytest.fixture
def stub_orchestrator(monkeypatch):
    """Replace `refresh_all_banks` with a synchronous, instant success stub."""
    def _ok(_nonce: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "started_at": "2026-05-08T10:00:00+00:00",
            "ended_at": "2026-05-08T10:00:01+00:00",
            "today": "2026-05-08",
            "bog": {
                "ok": True, "added_total": 5, "updated_total": 0,
                "by_year": {2026: 5}, "duration_s": 0.1,
            },
            "rsge": {
                "ok": True, "added_total": 3, "updated_total": 1,
                "by_year": {2026: {"added": 3, "updated": 1}}, "duration_s": 0.2,
            },
            "tbc": {
                "ok": True, "added_total": 7, "updated_total": 0,
                "by_year": {2026: 7}, "duration_s": 0.3,
            },
        }
    monkeypatch.setattr(bank_refresh_module, "refresh_all_banks", _ok)
    return _ok


def _wait_for_state(target: str, timeout: float = 2.0) -> bool:
    """Poll `_bank_refresh_status['state']` until it matches `target`."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server._bank_refresh_status["state"] == target:
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------------------
# OTP shape validation (synchronous — no thread spawned)
# ---------------------------------------------------------------------------


def test_endpoint_rejects_missing_nonce(client, stub_pipeline):
    res = client.post("/api/banks/refresh", json={})
    assert res.status_code == 400
    assert "9 digits" in res.json()["detail"]


def test_endpoint_rejects_short_otp(client, stub_pipeline):
    res = client.post("/api/banks/refresh", json={"nonce": "12345"})
    assert res.status_code == 400


def test_endpoint_rejects_alpha_otp(client, stub_pipeline):
    res = client.post("/api/banks/refresh", json={"nonce": "abcdefghi"})
    assert res.status_code == 400


def test_endpoint_rejects_too_long_otp(client, stub_pipeline):
    res = client.post("/api/banks/refresh", json={"nonce": "1234567890"})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Happy path — orchestrator stubbed
# ---------------------------------------------------------------------------


def test_endpoint_starts_with_valid_otp(client, stub_pipeline, stub_orchestrator):
    res = client.post("/api/banks/refresh", json={"nonce": "123456789"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "started"

    # Wait until the background thread finishes (state goes idle).
    assert _wait_for_state("idle", timeout=3.0)
    assert server._bank_refresh_status["last_result"]["bog"]["ok"] is True


def test_status_payload_includes_bank_refresh_block(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.json()
    assert "bank_refresh" in body
    assert body["bank_refresh"]["state"] == "idle"


def test_already_running_short_circuits(client, stub_pipeline, monkeypatch):
    """If state is already 'running', the endpoint must not spawn a 2nd run."""
    server._bank_refresh_status["state"] = "running"
    invocations: list[str] = []

    def trip(*_a, **_kw):
        invocations.append("called")
        return {}

    monkeypatch.setattr(bank_refresh_module, "refresh_all_banks", trip)
    res = client.post("/api/banks/refresh", json={"nonce": "123456789"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "already_running"
    # Give any (incorrectly spawned) thread a moment to fire.
    time.sleep(0.1)
    assert invocations == []


def test_partial_failure_marks_state_error(client, stub_pipeline, monkeypatch):
    """When at least one bank fails, status state goes 'error' with detail."""
    def _partial(_nonce: str, **_kwargs: Any) -> dict[str, Any]:
        return {
            "started_at": "x", "ended_at": "y", "today": "2026-05-08",
            "bog": {
                "ok": True, "added_total": 1, "updated_total": 0,
                "by_year": {}, "duration_s": 0.1,
            },
            "rsge": {
                "ok": False, "error": "rs.ge timeout",
                "added_total": 0, "updated_total": 0, "duration_s": 0.2,
            },
            "tbc": {
                "ok": False, "error": "skipped — BOG or rs.ge failed",
                "added_total": 0, "updated_total": 0, "duration_s": 0.0,
                "skipped": True,
            },
        }
    monkeypatch.setattr(bank_refresh_module, "refresh_all_banks", _partial)
    res = client.post("/api/banks/refresh", json={"nonce": "123456789"})
    assert res.status_code == 200

    assert _wait_for_state("error", timeout=3.0)
    err = server._bank_refresh_status["last_error"]
    assert err is not None
    assert "rs.ge" in err
