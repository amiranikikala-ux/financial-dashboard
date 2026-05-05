# Sprint C step 6 — Bank-tab "განახლება" button + DigiPass modal + bank-cache refresh endpoint

**Status**: PREVIEW · NO CODE CHANGE · Scope finalized 2026-05-08 (interactive Q&A — see "Final scope" block below)
**Date**: 2026-05-08
**Target sprint**: Sprint C step 6 — split into Phase 1 (backend) + Phase 2 (UI), two sessions
**Reference decisions**: `CONTEXT_HANDOFF.md` §1b (#6, #7) and §4

---

## TL;DR

Two distinct refresh actions, two buttons, no UI overlap:

- **Existing global header button** — recalculates `data.json` from already-cached parquet/Excel. Renamed `განახლება` → `ხელახლა გათვლა`. Auto-runs every hour via APScheduler. No DigiPass needed. ~7–8 min.
- **NEW Bank-tab button** — fetches fresh data from BOG + rs.ge + TBC into parquet caches, then triggers the same pipeline regen. Needs DigiPass (TBC only). Smart incremental window per source (see Final scope).

**Critical bug discovered during scoping**: `append_rsge_cache` uses dedup-by-ID. When a waybill changes status (active → cancelled) or amount on rs.ge, our cache silently drops the update — the existing reconciliation page (`WaybillReconciliation.jsx`) cannot fire `ghost_ap` / `amount_mismatch` flags because the cache shows stale state. **Fix**: rs.ge cache moves from append-only to upsert-by-ID. BOG/TBC stay append-only (banks don't retroactively edit posted transactions). This re-opens locked decision §1b #10 ("retroactive corrections deferred") **only for rs.ge**, with the user's explicit consent.

---

## Final scope (locked 2026-05-08)

### 2-button design
- **Header button** (existing `RefreshButton.jsx`) — label: `ხელახლა გათვლა`. Behavior unchanged, only the label changes. Stays on every tab in the header.
- **Bank-tab button** (new) — label: `ბანკიდან ახალი მონაცემის ჩამოტანა`. Lives at the top of `Cashflow.jsx`. Click → DigiPass modal.

### Smart incremental refresh window
| Source | Window | Reason |
|---|---|---|
| BOG | `start = last_refresh_at - 2 days`, `end = today` (default 7 days back if never refreshed) | Banks rarely amend; 2-day overlap catches late-arriving entries |
| TBC | same as BOG | same |
| **rs.ge** | **`start = today - 30 days`, `end = today` (always)** | Suppliers DO amend within ~weeks; 30-day re-fetch + upsert catches status/amount changes |

State file: `Financial_Analysis/cache/.last_refresh.json` — `{"bog": "ISO_TS", "tbc": "ISO_TS", "rsge": "ISO_TS"}`. Updated only on per-source success.

### rs.ge cache: append-only → upsert-by-ID
- `append_rsge_cache(waybills)` becomes `upsert_rsge_cache(waybills)` (or new function alongside; see implementation).
- When an incoming waybill ID already exists in the year file: **REPLACE** the row, not skip.
- BOG/TBC caches: unchanged (append-only-by-ID).
- Returns split metrics: `{year: {"added": N, "updated": M}}`.

### OTP pre-flight: NO
Don't add a pre-validation SOAP call. Per memory `feedback_one_shot_token_validation.md`: validate everything that can be validated offline (regex 9-digit, env vars present, connector class instantiates) **before** the user-supplied OTP touches `fetch_movements`. Accept the residual risk: if a runtime error fires inside `fetch_movements`, one OTP is consumed. The orchestrator runs BOG + rs.ge first; only if both succeed does TBC use the OTP.

---

## Two-phase split

### Phase 1 — Backend foundation (this session)
1. `dashboard_pipeline/rsge_cache.py` — refactor `append_rsge_cache` → upsert-by-ID. Update return shape to `{year: {"added": N, "updated": M}}`.
2. `tests/test_rsge_cache_upsert.py` — 7 unit tests (no SOAP).
3. `dashboard_pipeline/bank_refresh.py` — orchestrator + state-file management.
4. `tests/test_bank_refresh_orchestrator.py` — unit tests with patched `run_backfill` funcs.
5. `server.py` — add `POST /api/banks/refresh`, extend `/api/status`.
6. `tests/test_bank_refresh_endpoint.py` — endpoint tests via FastAPI TestClient.
7. Run full `pytest`, commit.

### Phase 2 — Frontend UI (next session)
8. `rs-dashboard/src/components/BankRefreshModal.jsx` — DigiPass OTP input + per-bank progress.
9. `rs-dashboard/src/hooks/useBankRefresh.js` — start + poll + reload data.
10. `rs-dashboard/src/Cashflow.jsx` — top-of-tab button + modal mount.
11. `rs-dashboard/src/components/RefreshButton.jsx` — relabel `განახლება` → `ხელახლა გათვლა`.
12. Vite dev smoke-test (real OTP, 3 progress lines, success).

---

## Inventory — what already exists

### Backend

| Symbol | Path | Shape | Reuse plan |
|---|---|---|---|
| `_run_pipeline()` | `server.py:86` | thread-safe pipeline regen, sets `_pipeline_status` | call after bank-cache step finishes ok |
| `_pipeline_status` dict | `server.py:77` | `state` / `last_run` / `last_error` / `runs_total` | existing `/api/status` already exposes this — frontend polls it |
| `/api/refresh` | `server.py:429` | kicks `_run_pipeline` only (no bank fetch) | DO NOT repurpose — stays as-is for global "regen-only" |
| `/api/status` | `server.py:406` | reports pipeline state + data age | reuse, extend payload with `bank_refresh: {...}` |
| `bog_bank_connector.BOGBankConnector` | `dashboard_pipeline/bog_bank_connector.py:146,180` | `check_auth() / fetch_statement(start, end, max_window_days)` | already used by `_backfill_bog.run_backfill` |
| `rs_waybill_connector.RSWaybillConnector` | `dashboard_pipeline/rs_waybill_connector.py:176,183` | `check_auth() / fetch_buyer_waybills(ws, we)` | already used by `_backfill_rsge.run_backfill` |
| `tbc_bank_connector.TBCBankConnector` | `dashboard_pipeline/tbc_bank_connector.py:291` | `fetch_movements(start, end, nonce=...)` | already used by `_backfill_tbc.run_backfill` |
| `_backfill_{bog,rsge,tbc}.run_backfill(start, end, ...)` | `dashboard_pipeline/_backfill_*.py` | append-only, returns `{year: rows_added}` | **direct reuse** — same shape across the 3 |
| `bank_cache.append_bog_cache` / `rsge_cache.append_rsge_cache` / `tbc_cache.append_tbc_cache` | `dashboard_pipeline/*_cache.py` | append-only, dedup, parquet | already invoked by `run_backfill` — no direct call needed |

### Frontend

| Symbol | Path | Shape | Reuse plan |
|---|---|---|---|
| `Cashflow.jsx` | `rs-dashboard/src/Cashflow.jsx:79` | the actual Bank tab (`💳 ბანკი`, id `cashflow` — `tabConfig.js:9`) | insert button at very top of the returned JSX; no logic shift |
| `useDataStatus.js` | `rs-dashboard/src/hooks/useDataStatus.js` | polls `/api/status` every 15 s, exposes `triggerRefresh()` for `/api/refresh` | leave global hook alone; add new `useBankRefresh.js` for the bank-tab button |
| `RefreshButton.jsx` | `rs-dashboard/src/components/RefreshButton.jsx` | global header refresh button (regen only) | unchanged |
| Modal precedent | `SupplierModal.jsx` is a side panel, not a true centered modal | — | DigiPass modal is a fresh component (no exact pattern to mirror) |

### Tabs / routing

- `tabConfig.js:9` defines the Bank tab as `{ id: 'cashflow', label: '💳 ბანკი' }`. Hash routing via `useHashTab('suppliers')` in `App.jsx:76`.

---

## What changes (new files + edits)

### NEW backend files

1. `dashboard_pipeline/bank_refresh.py` — orchestrator function `refresh_all_banks(nonce: str, start: date, end: date) -> dict`. Internally runs the 3 `run_backfill()` calls in a `concurrent.futures.ThreadPoolExecutor(max_workers=3)`. Returns:
   ```
   {
     "bog":  {"ok": True,  "added": {2026: 42}, "duration_s": 12.4},
     "rsge": {"ok": True,  "added": {2026: 8},  "duration_s": 18.1},
     "tbc":  {"ok": False, "error": "...",      "duration_s": 4.0},
     "started_at": "2026-05-08T..", "ended_at": "..."
   }
   ```

### Backend EDITS

2. `server.py` — add `_bank_refresh_status` dict and `/api/banks/refresh` POST endpoint. Endpoint reads `{nonce: "123456789"}` from body, validates 9-digit format **server-side**, calls `bank_refresh.refresh_all_banks(...)` in a daemon thread (not blocking the request), returns `{"status": "started", "request_id": <uuid>}` immediately. The endpoint does **not** start `_run_pipeline()` directly; the orchestrator does it itself if all 3 banks succeed.

3. `server.py` — extend `/api/status` payload: add a `bank_refresh` key with the latest `_bank_refresh_status` snapshot. Frontend modal polls this for per-bank progress (BOG ✅ / RSGE ✅ / TBC running…).

### NEW frontend files

4. `rs-dashboard/src/components/BankRefreshModal.jsx` — DigiPass OTP input field (digits-only, exactly 9 chars), client-side validation **before** POST (regex `^\d{9}$`), submit button, per-bank progress rows (BOG / rs.ge / TBC), final summary or error message, "დახურვა" button when finished.

5. `rs-dashboard/src/hooks/useBankRefresh.js` — exposes `{ start(nonce), state, perBank, error }`. Calls POST `/api/banks/refresh`, then polls `/api/status` every 2 s until `bank_refresh.state` is `idle` or `error`. On success, **also** triggers global `triggerRefresh()` (or relies on the orchestrator having kicked the pipeline) so dashboard data reloads.

### Frontend EDITS

6. `rs-dashboard/src/Cashflow.jsx:79+` — top of the returned JSX: a "ბანკის მონაცემების განახლება" button + age indicator ("ბოლო განახლება: N წთ წინ" — derived from `data.meta.bank_refresh.last_run`). Click sets `setShowBankModal(true)`. Render `<BankRefreshModal open={showBankModal} onClose={...} />` at the top.

7. `dashboard_pipeline/api_contracts.py` — if `cashflow` tab response builder needs the bank-refresh metadata, add the key. (TO BE CONFIRMED in implementation — may be unnecessary.)

### Tests

8. `tests/test_bank_refresh_endpoint.py` (new) — 7 tests, see test plan below.

---

## Output-shape audit

Not a serialization refactor — the new endpoint returns a fresh response shape (`{status, request_id}`) and the orchestrator writes a fresh `_bank_refresh_status` dict. No existing JSON contracts change. ✅

The 3 `run_backfill()` functions already return JSON-safe `dict[int, int]` (year → rows added). ✅

---

## Risks / pitfalls

1. **OTP burn on validation error.** `feedback_one_shot_token_validation.md` (memory) — burned a TBC DigiPass code on AttributeError. **Mitigation:** orchestrator runs **BOG + rs.ge first** (no OTP needed). If either fails, return error **before** the TBC SOAP call. Validate the 9-digit shape both client- and server-side. Connector exceptions before `fetch_movements` (e.g., env-var missing) must be caught and reported without consuming the OTP. Add a tiny pre-flight: try a `TBCBankConnector()` constructor + a fast no-op SOAP call (StatementService aggregate call for "today" — already known to work) **OR** simply rely on connector lazy-init and accept that an env-var miss costs an OTP. Decision needed at implementation time — see "Open question 1".

2. **Concurrency vs single-OTP semantics.** TBC pagination reuses one nonce, so concurrent BOG + rs.ge + TBC is safe. But if we run them in 3 threads and TBC fails halfway, we still wrote BOG + rs.ge cache entries. **Mitigation:** that is acceptable — the caches are append-only and idempotent, so retrying with a new OTP just re-adds 0 BOG/rs.ge rows + finishes TBC. Document this in the modal copy: "თუ TBC ვერ მოხერხდა, გაიმეორე ახალი კოდით — ბანკი/rs.ge უკვე განახლდა."

3. **Pipeline trigger race.** The orchestrator calls `_run_pipeline()` after the bank step. If the user is **also** clicking the global `RefreshButton` simultaneously, `_pipeline_lock.acquire(blocking=False)` already returns False and the second call is a no-op (`server.py:96-99`). ✅ — no fix needed, but document for the modal: while bank refresh is running, the global header button visually "is also running" because they share `_pipeline_status`.

4. **Thread vs FastAPI async.** `_run_pipeline` is sync + thread-based. Our orchestrator must also be sync + thread-based, **not** an async coroutine, to match the existing pattern. Use `Thread(target=...)` exactly like `trigger_refresh` does (`server.py:435`). ✅

5. **Date window.** What `start..end` does the orchestrator use? Locked decision in §1b is "append-only refresh, no retroactive". Pragmatic default: `start = today - 7 days`, `end = today` — overlap is harmless (append-only dedup). Edge case: TBC nonce window is ~5–15 min, so 7 days is well within bandwidth. **Open question 2** — confirm the default with user.

6. **Rate limits.** `/api/refresh` is `2/minute`. New `/api/banks/refresh` should be `1/minute` (more expensive). slowapi `@limiter.limit("1/minute")`.

7. **Auth-key pass-through.** If `DASHBOARD_API_KEY` is set, the new endpoint requires `X-API-Key` (already enforced by `ApiKeyMiddleware`). The frontend `fetchApiJson` helper handles this — make sure `useBankRefresh.js` uses it, not raw `fetch`.

8. **Backend service restart needed.** New code in `server.py` requires `Restart-Service FinancialDashboardBackend` (admin/UAC) per `CLAUDE.md` Stack rule. Pipeline subprocess auto-picks up new code; no service restart needed for changes inside `dashboard_pipeline/`. Frontend Vite picks up changes via HMR.

---

## Scope recommendation — DO NOT split

This is a single self-contained sprint step:
- 1 new orchestrator file, ~100 LOC.
- 1 endpoint addition, ~30 LOC.
- 1 status-payload extension, ~10 LOC.
- 1 new modal component, ~150 LOC.
- 1 new hook, ~60 LOC.
- 1 Cashflow.jsx insertion, ~20 LOC.
- 7 tests, ~200 LOC.

Total ~570 LOC. Comfortably one session. Splitting (e.g., backend-first / frontend-second) would cost a full extra session for re-loading context with no risk reduction.

**Recommendation: do in one session.**

---

## Test plan (7 tests, follow `tests/test_samurneo_incremental.py` pattern)

`tests/test_bank_refresh_endpoint.py`:

1. `test_endpoint_rejects_invalid_otp_shape` — POST with `nonce="abc"` → 400, no orchestrator invoked, no OTP consumed.
2. `test_endpoint_rejects_short_otp` — POST with `nonce="12345"` → 400.
3. `test_endpoint_returns_started_with_valid_otp` — POST with `nonce="123456789"` → 200, `{"status":"started"}`. Mock orchestrator at the boundary (don't hit real banks).
4. `test_endpoint_rate_limited` — 2nd call within 60s → 429.
5. `test_status_includes_bank_refresh_when_active` — start refresh → `/api/status` payload has `bank_refresh.state == "running"`.
6. `test_orchestrator_runs_bog_and_rsge_before_tbc` — patch the 3 `run_backfill` funcs, assert call ordering. Why this matters: see Risk 1.
7. `test_orchestrator_returns_per_bank_status` — patch one of the 3 to raise; assert orchestrator returns `{"ok": False, "error": ...}` for that bank and continues with the others (does NOT raise globally).

Frontend: smoke-test by user (Vite dev → click button → enter test OTP → see modal progress → success). No automated frontend tests in the sprint scope.

---

## Files expected to change

### NEW
- `dashboard_pipeline/bank_refresh.py`
- `rs-dashboard/src/components/BankRefreshModal.jsx`
- `rs-dashboard/src/hooks/useBankRefresh.js`
- `tests/test_bank_refresh_endpoint.py`
- `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_C6_BANK_REFRESH_BUTTON_PREVIEW.md` (this file)

### EDIT
- `server.py` (add endpoint + status extension; ~50 LOC added)
- `rs-dashboard/src/Cashflow.jsx` (top-of-tab button + modal mount; ~20 LOC added)

### POSSIBLY EDIT
- `dashboard_pipeline/api_contracts.py` (only if cashflow response needs to expose bank_refresh metadata — defer decision to implementation)

### NO TOUCH
- `RefreshButton.jsx`, `useDataStatus.js`, `App.jsx`, `tabConfig.js` — existing global refresh chain stays intact.
- Cache modules (`bank_cache.py`, `rsge_cache.py`, `tbc_cache.py`) and connector classes — read-only reuse.
- `_run_pipeline` — invoked, not modified.

---

## Self-check checklist (pre-commit)

- [ ] 9-digit OTP regex enforced both client- AND server-side
- [ ] BOG + rs.ge run **before** TBC; if either fails, abort before SOAP (no OTP burn)
- [ ] Orchestrator catches per-bank exceptions, never raises globally
- [ ] Endpoint rate-limited `1/minute`
- [ ] `/api/status` payload extended with `bank_refresh` block, frontend polls it
- [ ] `_run_pipeline()` called only after all 3 banks finish; pipeline lock makes second-call race-safe
- [ ] Modal copy mentions "BOG/rs.ge already updated, retry TBC with new code" on TBC-only failure
- [ ] `Restart-Service FinancialDashboardBackend` (admin) noted in commit message for backend changes
- [ ] All 7 tests green (mocked — no real bank API hits in CI)
- [ ] Manual smoke: Vite dev → click → modal → real OTP → 3 progress lines → pipeline kicks → dashboard reloads

---

## Open questions for user (before implementation)

1. **OTP pre-flight**: should we add a fast no-op TBC SOAP call to validate auth before consuming the user's OTP for the actual `fetch_movements`, or accept the small risk of burning one OTP if env vars are mis-set? Pre-flight adds ~3s and one additional SOAP request per refresh.
2. **Default refresh window**: 7 days back? 30 days? Custom (modal field)?
3. **Modal mount location**: top of `Cashflow.jsx` (Bank tab only — locked decision) — confirm it does **not** also render on the Suppliers / Waybills tabs.

---

## Evidence sources

- `CONTEXT_HANDOFF.md` §1b (decisions 1-10) and §4 (Sprint C step 6 scope) — at commit `975209e` (current `main` head).
- `server.py:86-147` (`_run_pipeline` + lock pattern) and `server.py:429-437` (`/api/refresh` shape).
- `dashboard_pipeline/_backfill_bog.py`, `_backfill_rsge.py`, `_backfill_tbc.py` — `run_backfill` shape inventory.
- `dashboard_pipeline/{bank_cache,rsge_cache,tbc_cache}.py` — `append_*` signatures.
- `dashboard_pipeline/{bog,tbc}_bank_connector.py` and `rs_waybill_connector.py` — connector class signatures.
- `rs-dashboard/src/{Cashflow.jsx,App.jsx,tabConfig.js,components/RefreshButton.jsx,hooks/useDataStatus.js,components/UpdateBanner.jsx,SupplierModal.jsx}` — frontend insertion points and existing modal-ish patterns.
- Memory `feedback_one_shot_token_validation.md` — DigiPass burn lesson.
