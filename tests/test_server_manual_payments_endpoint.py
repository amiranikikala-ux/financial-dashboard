"""POST + GET + DELETE /api/manual-payments — owner cash-payments journal."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import server
from dashboard_pipeline import manual_payments_journal as mpj


@pytest.fixture
def isolated_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    journal = tmp_path / "manual_payments_journal.csv"
    monkeypatch.setattr(mpj, "journal_csv_path", lambda: str(journal))
    yield journal


@pytest.fixture
def client(isolated_journal: Path) -> Iterator[TestClient]:
    with TestClient(server.app) as c:
        yield c


def test_post_creates_entry(client: TestClient, isolated_journal: Path):
    response = client.post(
        "/api/manual-payments",
        json={"tax_id": "406181616", "amount": 72972, "comment": "ჯიდიაი ნაღდი"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["entry"]["tax_id"] == "406181616"
    assert body["entry"]["amount"] == 72972.0
    assert body["entry"]["id"]
    assert isolated_journal.exists()


def test_post_rejects_missing_tax_id(client: TestClient):
    response = client.post("/api/manual-payments", json={"amount": 100})
    assert response.status_code == 400
    assert "tax_id" in response.json()["detail"]


def test_post_rejects_non_numeric_amount(client: TestClient):
    response = client.post(
        "/api/manual-payments", json={"tax_id": "111", "amount": "abc"}
    )
    assert response.status_code == 400


def test_post_rejects_zero_or_negative_amount(client: TestClient):
    r1 = client.post("/api/manual-payments", json={"tax_id": "111", "amount": 0})
    r2 = client.post("/api/manual-payments", json={"tax_id": "111", "amount": -5})
    assert r1.status_code == 400
    assert r2.status_code == 400


def test_post_rejects_non_digit_tax_id(client: TestClient):
    response = client.post(
        "/api/manual-payments", json={"tax_id": "abc", "amount": 100}
    )
    assert response.status_code == 400


def test_get_lists_entries(client: TestClient):
    client.post("/api/manual-payments", json={"tax_id": "111", "amount": 100})
    client.post("/api/manual-payments", json={"tax_id": "222", "amount": 50})

    response = client.get("/api/manual-payments")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert len(body["entries"]) == 2


def test_get_filters_by_tax_id(client: TestClient):
    client.post("/api/manual-payments", json={"tax_id": "111", "amount": 100})
    client.post("/api/manual-payments", json={"tax_id": "222", "amount": 50})

    response = client.get("/api/manual-payments?tax_id=222")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["entries"][0]["tax_id"] == "222"


def test_delete_soft_removes_entry(client: TestClient):
    create = client.post(
        "/api/manual-payments", json={"tax_id": "111", "amount": 100}
    )
    entry_id = create.json()["entry"]["id"]

    response = client.delete(f"/api/manual-payments/{entry_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True

    listing = client.get("/api/manual-payments").json()
    assert listing["count"] == 0


def test_delete_unknown_id_returns_404(client: TestClient):
    response = client.delete("/api/manual-payments/nonexistent-id")
    assert response.status_code == 404


def test_delete_already_deleted_returns_404(client: TestClient):
    create = client.post(
        "/api/manual-payments", json={"tax_id": "111", "amount": 100}
    )
    entry_id = create.json()["entry"]["id"]
    client.delete(f"/api/manual-payments/{entry_id}")

    second = client.delete(f"/api/manual-payments/{entry_id}")
    assert second.status_code == 404


def test_post_then_get_then_delete_round_trip(client: TestClient):
    create = client.post(
        "/api/manual-payments",
        json={"tax_id": "406181616", "amount": 72972.50, "comment": "ჯიდიაი"},
    )
    eid = create.json()["entry"]["id"]

    listing = client.get("/api/manual-payments?tax_id=406181616").json()
    assert listing["count"] == 1
    assert listing["entries"][0]["amount"] == 72972.50
    assert listing["entries"][0]["comment"] == "ჯიდიაი"

    client.delete(f"/api/manual-payments/{eid}")

    after = client.get("/api/manual-payments?tax_id=406181616").json()
    assert after["count"] == 0
