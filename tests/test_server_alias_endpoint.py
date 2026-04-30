"""Sprint C — `POST /api/aliases/confirm` endpoint tests.

The endpoint receives a single user-confirmed alias from
``SupplierModal``-ის „დადასტურდი ალიასი" button, validates it against the
live ``retail_sales.by_product`` index, and atomically appends it to
``Financial_Analysis/product_aliases.json``.

Tests use FastAPI's ``TestClient`` with two monkeypatches:

* ``server.load_full_data`` — return a fake data dict so we can control
  which retail keys exist without touching the real 65 MB ``data.json``.
* ``server._aliases_file_path`` — point at a ``tmp_path`` so each test
  runs in isolation and never mutates the repo-tracked file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import server


# ---------------------------------------------------------------------------
# Fixtures — lightweight fake data + isolated alias file path
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_data() -> Dict[str, Any]:
    """Minimal data.json shape — only retail_sales.by_product matters here.

    Two rows give us a non-trivial known-keys set ({2247377, 4860103230058,
    9999, 4860119260841}) so unknown-key tests have something to fail
    against.
    """
    return {
        "retail_sales": {
            "by_product": [
                {
                    "product_code": "2247377",
                    "barcode": "4860103230058",
                    "product_name": "შეფუთული აგურა რუხი",
                },
                {
                    "product_code": "9999",
                    "barcode": "4860119260841",
                    "product_name": "სხვა პროდუქტი",
                },
            ]
        }
    }


@pytest.fixture
def isolated_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the endpoint at a tmp file. Returns the path so tests can
    inspect what was written."""
    p = tmp_path / "product_aliases.json"
    monkeypatch.setattr(server, "_aliases_file_path", lambda: p)
    return p


@pytest.fixture
def client(
    isolated_aliases: Path,
    fake_data: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """TestClient with ``load_full_data`` patched to return our fake data."""
    monkeypatch.setattr(server, "load_full_data", lambda *a, **kw: fake_data)
    return TestClient(server.app)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_post_alias_confirm_happy_path(client: TestClient, isolated_aliases: Path):
    resp = client.post(
        "/api/aliases/confirm",
        json={
            "imported_code": "2006",
            "retail_code_or_barcode": "2247377",
            "imported_supplier_taxid": "400123456",
            "imported_name_sample": "შეფუთული აგურა რუხი",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["alias_count"] == 1
    assert body["alias"]["confirmed_by"] == "user"
    assert body["alias"]["imported_code"] == "2006"
    assert body["alias"]["retail_code_or_barcode"] == "2247377"
    assert "მომდევნო pipeline run-ი" in body["hint_ka"]

    # File on disk reflects the same canonical entry.
    on_disk = json.loads(isolated_aliases.read_text(encoding="utf-8"))
    assert len(on_disk["aliases"]) == 1
    assert on_disk["aliases"][0]["imported_code"] == "2006"


# ---------------------------------------------------------------------------
# Validation — unknown retail key → 400
# ---------------------------------------------------------------------------


def test_post_alias_confirm_unknown_retail_key_returns_400(
    client: TestClient, isolated_aliases: Path,
):
    resp = client.post(
        "/api/aliases/confirm",
        json={"imported_code": "2006", "retail_code_or_barcode": "GHOST"},
    )
    assert resp.status_code == 400
    body = resp.json()
    # Georgian error message — user-facing, not a stack trace.
    assert "GHOST" in body["detail"]
    assert "retail_sales" in body["detail"]
    assert not isolated_aliases.exists()


# ---------------------------------------------------------------------------
# Idempotency guard — duplicate confirm → 409
# ---------------------------------------------------------------------------


def test_post_alias_confirm_duplicate_returns_409(
    client: TestClient, isolated_aliases: Path,
):
    payload = {"imported_code": "2006", "retail_code_or_barcode": "2247377"}

    first = client.post("/api/aliases/confirm", json=payload)
    assert first.status_code == 200

    second = client.post("/api/aliases/confirm", json=payload)
    assert second.status_code == 409
    assert "უკვე დადასტურებულია" in second.json()["detail"]

    on_disk = json.loads(isolated_aliases.read_text(encoding="utf-8"))
    assert len(on_disk["aliases"]) == 1


# ---------------------------------------------------------------------------
# Bad-shape body — empty fields → 400
# ---------------------------------------------------------------------------


def test_post_alias_confirm_missing_fields_returns_400(
    client: TestClient, isolated_aliases: Path,
):
    resp = client.post(
        "/api/aliases/confirm",
        json={"imported_code": "  ", "retail_code_or_barcode": "2247377"},
    )
    assert resp.status_code == 400
    assert "imported_code" in resp.json()["detail"]
    assert not isolated_aliases.exists()
