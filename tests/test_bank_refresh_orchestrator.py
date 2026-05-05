"""Unit tests for `dashboard_pipeline.bank_refresh.refresh_all_banks`.

Patches the BOG / rs.ge / TBC backfill runners so no SOAP / HTTP traffic
fires. Covers the contract that:

- OTP shape is validated up front; malformed OTP raises ValueError before
  any runner is touched (memory: protect the user's DigiPass OTP).
- BOG + rs.ge run before TBC; if either fails, TBC is skipped without
  consuming the OTP.
- Per-runner exceptions are captured into the per-bank result block
  (`ok=False, error=..., duration_s=...`); they never propagate.
- Smart windows: BOG/TBC use `last_refresh - 2 days` (or `today - 7d` on
  first run); rs.ge always uses `today - 30 days`.
- State file persists per-source `last_completed_at`, but only for
  sources that succeeded in this run.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from dashboard_pipeline import bank_refresh


@pytest.fixture
def state_path(tmp_path):
    return tmp_path / ".last_refresh.json"


def _ok_int_runner(*args, **kwargs):
    """Stand-in for BOG/TBC backfill — returns `dict[int, int]`."""
    return {2026: 5}


def _ok_dict_runner(*args, **kwargs):
    """Stand-in for rs.ge backfill — returns `dict[int, dict]`."""
    return {2026: {"added": 3, "updated": 1}}


def _raising_runner(message: str):
    def _inner(*args, **kwargs):
        raise RuntimeError(message)

    return _inner


def test_otp_shape_rejected_before_runners(state_path):
    """Malformed OTP must raise ValueError without invoking any runner."""
    calls: list[str] = []

    def trip(*_args, **_kwargs):
        calls.append("ran")
        return {}

    with pytest.raises(ValueError, match="9 digits"):
        bank_refresh.refresh_all_banks(
            "12345",
            today=date(2026, 5, 8),
            bog_runner=trip,
            rsge_runner=trip,
            tbc_runner=trip,
            state_path=state_path,
        )
    assert calls == []


def test_happy_path_all_three_succeed(state_path):
    bog_calls: list[tuple[date, date]] = []
    rsge_calls: list[tuple[date, date]] = []
    tbc_calls: list[tuple[date, date, str]] = []

    def bog(start, end, **_):
        bog_calls.append((start, end))
        return {2026: 7}

    def rsge(start, end, **_):
        rsge_calls.append((start, end))
        return {2026: {"added": 4, "updated": 2}}

    def tbc(start, end, nonce, **_):
        tbc_calls.append((start, end, nonce))
        return {2026: 11}

    today = date(2026, 5, 8)
    result = bank_refresh.refresh_all_banks(
        "123456789",
        today=today,
        bog_runner=bog,
        rsge_runner=rsge,
        tbc_runner=tbc,
        state_path=state_path,
    )

    assert result["bog"]["ok"] is True
    assert result["rsge"]["ok"] is True
    assert result["tbc"]["ok"] is True
    assert result["bog"]["added_total"] == 7
    assert result["rsge"]["added_total"] == 4
    assert result["rsge"]["updated_total"] == 2
    assert result["tbc"]["added_total"] == 11

    # First-run windows: BOG/TBC = 7 days back; rs.ge = 30 days back.
    assert bog_calls == [(today - timedelta(days=7), today)]
    assert rsge_calls == [(today - timedelta(days=30), today)]
    assert tbc_calls == [(today - timedelta(days=7), today, "123456789")]

    # State file persisted with all 3 sources.
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(saved.keys()) == {"bog", "rsge", "tbc"}


def test_tbc_skipped_when_bog_fails(state_path):
    """If BOG fails in Phase A, TBC is NOT invoked — OTP must not be burned."""
    tbc_invocations: list[str] = []

    def tbc(*_args, **_kwargs):
        tbc_invocations.append("called")
        return {2026: 1}

    today = date(2026, 5, 8)
    result = bank_refresh.refresh_all_banks(
        "123456789",
        today=today,
        bog_runner=_raising_runner("BOG auth failed"),
        rsge_runner=_ok_dict_runner,
        tbc_runner=tbc,
        state_path=state_path,
    )

    assert tbc_invocations == []
    assert result["bog"]["ok"] is False
    assert "BOG auth failed" in result["bog"]["error"]
    assert result["rsge"]["ok"] is True
    assert result["tbc"]["ok"] is False
    assert result["tbc"].get("skipped") is True
    assert "OTP not consumed" in result["tbc"]["error"]


def test_tbc_skipped_when_rsge_fails(state_path):
    tbc_invocations: list[str] = []

    def tbc(*_args, **_kwargs):
        tbc_invocations.append("called")
        return {2026: 1}

    result = bank_refresh.refresh_all_banks(
        "123456789",
        today=date(2026, 5, 8),
        bog_runner=_ok_int_runner,
        rsge_runner=_raising_runner("rs.ge timeout"),
        tbc_runner=tbc,
        state_path=state_path,
    )

    assert tbc_invocations == []
    assert result["rsge"]["ok"] is False
    assert result["tbc"].get("skipped") is True


def test_state_only_updated_for_successes(state_path):
    """A failed source must not have its `last_completed_at` advanced."""
    # Seed prior state with an old BOG entry.
    state_path.parent.mkdir(parents=True, exist_ok=True)
    old_iso = "2025-01-01T00:00:00+00:00"
    state_path.write_text(
        json.dumps(
            {
                "bog": {
                    "last_completed_at": old_iso,
                    "last_window": ["2024-12-25", "2025-01-01"],
                    "last_added": 0,
                    "last_updated": 0,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = bank_refresh.refresh_all_banks(
        "123456789",
        today=date(2026, 5, 8),
        bog_runner=_raising_runner("BOG auth failed"),
        rsge_runner=_ok_dict_runner,
        tbc_runner=_ok_int_runner,
        state_path=state_path,
    )

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    # BOG kept its old entry untouched (failure must not advance state).
    assert saved["bog"]["last_completed_at"] == old_iso
    # rs.ge succeeded → fresh entry.
    assert saved["rsge"]["last_completed_at"] != old_iso
    # TBC was skipped (no OTP burn) → no entry created.
    assert "tbc" not in saved
    # Sanity: result reflects the same outcome.
    assert result["bog"]["ok"] is False
    assert result["rsge"]["ok"] is True
    assert result["tbc"]["ok"] is False


def test_smart_window_uses_last_refresh_minus_overlap(state_path):
    """When prior state exists, BOG window = last_refresh - 2 days."""
    last_iso = "2026-05-06T10:00:00+00:00"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "bog": {
                    "last_completed_at": last_iso,
                    "last_window": ["2026-04-29", "2026-05-06"],
                    "last_added": 12,
                    "last_updated": 0,
                },
                "tbc": {
                    "last_completed_at": last_iso,
                    "last_window": ["2026-04-29", "2026-05-06"],
                    "last_added": 9,
                    "last_updated": 0,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bog_calls: list[tuple[date, date]] = []
    tbc_calls: list[tuple[date, date, str]] = []
    rsge_calls: list[tuple[date, date]] = []

    def bog(start, end, **_):
        bog_calls.append((start, end))
        return {}

    def rsge(start, end, **_):
        rsge_calls.append((start, end))
        return {}

    def tbc(start, end, nonce, **_):
        tbc_calls.append((start, end, nonce))
        return {}

    today = date(2026, 5, 8)
    bank_refresh.refresh_all_banks(
        "123456789",
        today=today,
        bog_runner=bog,
        rsge_runner=rsge,
        tbc_runner=tbc,
        state_path=state_path,
    )

    # Prior BOG completion 2026-05-06; overlap 2 days → start = 2026-05-04.
    assert bog_calls == [(date(2026, 5, 4), today)]
    assert tbc_calls == [(date(2026, 5, 4), today, "123456789")]
    # rs.ge always 30 days back regardless of state.
    assert rsge_calls == [(today - timedelta(days=30), today)]


def test_added_total_aggregates_both_shapes(state_path):
    """`_sum_added` must handle BOG `dict[int, int]` and rs.ge nested shape."""

    def bog(start, end, **_):
        return {2025: 3, 2026: 4}  # dict[int, int]

    def rsge(start, end, **_):
        return {
            2025: {"added": 2, "updated": 1},
            2026: {"added": 5, "updated": 3},
        }

    def tbc(start, end, nonce, **_):
        return {2026: 8}

    result = bank_refresh.refresh_all_banks(
        "123456789",
        today=date(2026, 5, 8),
        bog_runner=bog,
        rsge_runner=rsge,
        tbc_runner=tbc,
        state_path=state_path,
    )

    assert result["bog"]["added_total"] == 7
    assert result["bog"]["updated_total"] == 0
    assert result["rsge"]["added_total"] == 7
    assert result["rsge"]["updated_total"] == 4
    assert result["tbc"]["added_total"] == 8
