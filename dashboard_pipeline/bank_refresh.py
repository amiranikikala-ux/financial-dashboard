"""Bank refresh orchestrator — Sprint C step 6 Phase 1 backend.

Runs BOG / rs.ge / TBC connectors with smart incremental windows, persists
last-completed-at state to a JSON file, and returns a structured per-bank
result. Designed to run inside a daemon thread launched by the
`/api/banks/refresh` endpoint — never blocks the FastAPI event loop.

Window strategy (locked 2026-05-08, see SPRINT_C6_BANK_REFRESH_BUTTON_PREVIEW):
- BOG: ``start = last_refresh - 2 days`` (or ``today - 7 days`` if never run).
- TBC: same as BOG.
- rs.ge: **always** ``today - 30 days``, regardless of last refresh.
  Reason: rs.ge SOAP queries by ``create_date``; supplier amendments target
  waybills that were created weeks earlier, so we re-fetch a wide window
  and rely on `rsge_cache.upsert_rsge_cache` to overwrite changed rows.

OTP discipline (memory ``feedback_one_shot_token_validation.md``):
- Phase A: BOG + rs.ge concurrently — neither needs an OTP.
- Phase B: TBC — only fires if Phase A both succeeded. Otherwise the
  user's OTP is preserved and they can retry without burning it.
- The 9-digit shape is regex-validated up front so a malformed OTP cannot
  reach `fetch_movements`.

State file: ``Financial_Analysis/cache/.last_refresh.json``. Updated only
for sources that succeed in this run; failed sources keep their previous
state untouched.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from dashboard_pipeline._backfill_bog import run_backfill as _default_bog_runner
from dashboard_pipeline._backfill_rsge import run_backfill as _default_rsge_runner
from dashboard_pipeline._backfill_tbc import run_backfill as _default_tbc_runner

CACHE_ROOT = Path(__file__).resolve().parent.parent / "Financial_Analysis" / "cache"
STATE_FILE = CACHE_ROOT / ".last_refresh.json"

OTP_RE = re.compile(r"^\d{9}$")

BOG_OVERLAP_DAYS = 2
TBC_OVERLAP_DAYS = 2
DEFAULT_FIRST_RUN_DAYS = 7
RSGE_WINDOW_DAYS = 30

_state_lock = threading.Lock()


# ---------------------------------------------------------------------------
# State file
# ---------------------------------------------------------------------------


def _read_state() -> dict[str, dict]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(new: dict[str, dict]) -> None:
    with _state_lock:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _last_refresh_date(state: dict, source: str) -> date | None:
    iso = (state.get(source) or {}).get("last_completed_at")
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Window computation
# ---------------------------------------------------------------------------


def _bank_window(state: dict, source: str, today: date, overlap: int) -> tuple[date, date]:
    last = _last_refresh_date(state, source)
    if last is None:
        return today - timedelta(days=DEFAULT_FIRST_RUN_DAYS), today
    return last - timedelta(days=overlap), today


def _rsge_window(today: date) -> tuple[date, date]:
    return today - timedelta(days=RSGE_WINDOW_DAYS), today


# ---------------------------------------------------------------------------
# Per-source result normalization
# ---------------------------------------------------------------------------


def _sum_added(payload: Any) -> int:
    """Accept both `dict[int, int]` (BOG/TBC) and `dict[int, dict]` (rs.ge)."""
    if not isinstance(payload, dict):
        return 0
    total = 0
    for v in payload.values():
        if isinstance(v, dict):
            total += int(v.get("added", 0))
        else:
            try:
                total += int(v)
            except (TypeError, ValueError):
                continue
    return total


def _sum_updated(payload: Any) -> int:
    """rs.ge is the only source with updates; others always return 0."""
    if not isinstance(payload, dict):
        return 0
    total = 0
    for v in payload.values():
        if isinstance(v, dict):
            total += int(v.get("updated", 0))
    return total


def _run_one(
    label: str,
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Wrap a backfill call with timing + ok/error normalization."""
    t0 = time.time()
    try:
        added = fn(*args, **kwargs)
        return {
            "ok": True,
            "added_total": _sum_added(added),
            "updated_total": _sum_updated(added),
            "by_year": added,
            "duration_s": round(time.time() - t0, 2),
        }
    except Exception as exc:  # noqa: BLE001 — we want every error normalized
        return {
            "ok": False,
            "error": str(exc)[:500],
            "added_total": 0,
            "updated_total": 0,
            "duration_s": round(time.time() - t0, 2),
        }


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def refresh_all_banks(
    nonce: str,
    *,
    today: date | None = None,
    bog_runner: Callable[..., Any] = _default_bog_runner,
    rsge_runner: Callable[..., Any] = _default_rsge_runner,
    tbc_runner: Callable[..., Any] = _default_tbc_runner,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Run BOG + rs.ge concurrently, then TBC if both succeeded.

    Parameters
    ----------
    nonce : str
        9-digit DigiPass OTP. Validated up front; ``ValueError`` if malformed.
    today : date | None
        Override "today" for tests. Defaults to ``date.today()``.
    bog_runner / rsge_runner / tbc_runner : Callable
        Injectable backfill functions for tests. Default to the production
        ``run_backfill`` helpers in ``_backfill_*`` modules.
    state_path : Path | None
        Override state-file location for tests.

    Returns
    -------
    dict
        Top-level keys: ``started_at``, ``ended_at``, ``bog``, ``rsge``,
        ``tbc``. Each per-bank value is a dict with ``ok`` plus either
        ``added_total`` / ``updated_total`` / ``by_year`` / ``duration_s``
        (success) or ``error`` / ``duration_s`` (failure).
    """
    if not OTP_RE.match(nonce or ""):
        raise ValueError(
            "nonce must be exactly 9 digits (DigiPass OTP); got "
            f"{nonce!r}"
        )

    today = today or date.today()
    sf = state_path or STATE_FILE
    state = _read_state_at(sf)

    bog_start, bog_end = _bank_window(state, "bog", today, BOG_OVERLAP_DAYS)
    tbc_start, tbc_end = _bank_window(state, "tbc", today, TBC_OVERLAP_DAYS)
    rsge_start, rsge_end = _rsge_window(today)

    started_at = datetime.now(timezone.utc).isoformat()

    # Phase A — BOG + rs.ge concurrently. Neither uses an OTP.
    with ThreadPoolExecutor(max_workers=2) as ex:
        bog_fut = ex.submit(_run_one, "bog", bog_runner, bog_start, bog_end)
        rsge_fut = ex.submit(_run_one, "rsge", rsge_runner, rsge_start, rsge_end)
        bog_result = bog_fut.result()
        rsge_result = rsge_fut.result()

    # Phase B — TBC, only if both Phase A banks succeeded. Protects the OTP.
    if bog_result["ok"] and rsge_result["ok"]:
        tbc_result = _run_one("tbc", tbc_runner, tbc_start, tbc_end, nonce)
    else:
        tbc_result = {
            "ok": False,
            "error": "skipped — BOG or rs.ge failed; OTP not consumed",
            "added_total": 0,
            "updated_total": 0,
            "duration_s": 0.0,
            "skipped": True,
        }

    _persist_state(
        sf,
        state,
        bog_result=bog_result,
        bog_window=(bog_start, bog_end),
        rsge_result=rsge_result,
        rsge_window=(rsge_start, rsge_end),
        tbc_result=tbc_result,
        tbc_window=(tbc_start, tbc_end),
    )

    return {
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "today": today.isoformat(),
        "bog": bog_result,
        "rsge": rsge_result,
        "tbc": tbc_result,
    }


def refresh_bog_and_rsge_only(
    *,
    today: date | None = None,
    bog_runner: Callable[..., Any] = _default_bog_runner,
    rsge_runner: Callable[..., Any] = _default_rsge_runner,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """Refresh BOG + rs.ge caches without an OTP.

    TBC requires a 9-digit DigiPass OTP that only the owner can supply,
    so the auto-scheduler can keep BOG + rs.ge fresh every cycle while
    TBC stays a manual button click. Output schema mirrors
    ``refresh_all_banks`` for caller reuse — TBC slot is an explicit
    ``skipped`` placeholder.
    """
    today = today or date.today()
    sf = state_path or STATE_FILE
    state = _read_state_at(sf)

    bog_start, bog_end = _bank_window(state, "bog", today, BOG_OVERLAP_DAYS)
    rsge_start, rsge_end = _rsge_window(today)

    started_at = datetime.now(timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=2) as ex:
        bog_fut = ex.submit(_run_one, "bog", bog_runner, bog_start, bog_end)
        rsge_fut = ex.submit(_run_one, "rsge", rsge_runner, rsge_start, rsge_end)
        bog_result = bog_fut.result()
        rsge_result = rsge_fut.result()

    tbc_result = {
        "ok": False,
        "error": "skipped — auto-refresh does not consume OTP; TBC stays manual",
        "added_total": 0,
        "updated_total": 0,
        "duration_s": 0.0,
        "skipped": True,
    }

    # Persist windows we actually ran (TBC unchanged).
    tbc_window = _bank_window(state, "tbc", today, TBC_OVERLAP_DAYS)
    _persist_state(
        sf,
        state,
        bog_result=bog_result,
        bog_window=(bog_start, bog_end),
        rsge_result=rsge_result,
        rsge_window=(rsge_start, rsge_end),
        tbc_result=tbc_result,
        tbc_window=tbc_window,
    )

    return {
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "today": today.isoformat(),
        "bog": bog_result,
        "rsge": rsge_result,
        "tbc": tbc_result,
    }


# ---------------------------------------------------------------------------
# State helpers (parameterized so tests can inject a tmp_path)
# ---------------------------------------------------------------------------


def _read_state_at(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _persist_state(
    path: Path,
    prior: dict[str, dict],
    *,
    bog_result: dict,
    bog_window: tuple[date, date],
    rsge_result: dict,
    rsge_window: tuple[date, date],
    tbc_result: dict,
    tbc_window: tuple[date, date],
) -> None:
    new = dict(prior)
    now_iso = datetime.now(timezone.utc).isoformat()

    if bog_result["ok"]:
        new["bog"] = {
            "last_completed_at": now_iso,
            "last_window": [bog_window[0].isoformat(), bog_window[1].isoformat()],
            "last_added": int(bog_result.get("added_total", 0)),
            "last_updated": int(bog_result.get("updated_total", 0)),
        }
    if rsge_result["ok"]:
        new["rsge"] = {
            "last_completed_at": now_iso,
            "last_window": [
                rsge_window[0].isoformat(),
                rsge_window[1].isoformat(),
            ],
            "last_added": int(rsge_result.get("added_total", 0)),
            "last_updated": int(rsge_result.get("updated_total", 0)),
        }
    if tbc_result["ok"]:
        new["tbc"] = {
            "last_completed_at": now_iso,
            "last_window": [tbc_window[0].isoformat(), tbc_window[1].isoformat()],
            "last_added": int(tbc_result.get("added_total", 0)),
            "last_updated": int(tbc_result.get("updated_total", 0)),
        }

    with _state_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8"
        )


__all__ = [
    "refresh_all_banks",
    "STATE_FILE",
    "OTP_RE",
    "BOG_OVERLAP_DAYS",
    "TBC_OVERLAP_DAYS",
    "RSGE_WINDOW_DAYS",
    "DEFAULT_FIRST_RUN_DAYS",
]
