# Phase Status Matrix

> **განახლდა:** 2026-04-22
> **მიზანი:** ერთი ცხრილი — ყველა phase-ის ცხადი მდგომარეობა. ფართო narrative `PLAN.md`-ში, ისტორიული evidence `HANDOFF.md`-ში, საწყისი preview-ები `HANDOFF_ARCHIVE/PREVIEWS/`-ში.
>
> **Authoritative docs:**
> - Master roadmap (active): `AI_GENIUS_PARTNER_PLAN.md` v2.1 (2026-04-18)
> - Live status tracker: `PLAN.md`
> - Short chat brief: `CONTEXT_HANDOFF.md`
> - Full evidence log: `HANDOFF.md`
> - Legacy (Phase 1-2 AI evidence only): `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md`

---

## Legend

- ✅ **COMPLETE** — code merged, tests green
- 🎬 **LIVE VERIFIED** — scripted `/api/chat` or UI dog-food passed on real backend
- 📋 **PLANNED** — scope drafted, awaits approval/start
- 💤 **PARKED** — in Parking Lot, not scheduled
- ⚠️ **DRIFT** — preview file's internal status doesn't match merged code (archived copy reflects pre-merge draft)

---

## Pre-AI foundation (ფაზა 1 – 10)

| Phase | Status | Date | Notes |
|---|---|---|---|
| 1–2: Audit / logging / DRY refactor | ✅ | early 2026 | `PLAN.md` top section |
| 3: Code quality (`run()` helpers, CSS split, 105 tests, rate-limit) | ✅ | — | `PLAN.md` §ფაზა 3 |
| 4: APScheduler auto-refresh + ExportButton + mobile nav | ✅ | — | `PLAN.md` §ფაზა 4 |
| 5: Testing + deploy (38 E2E, API auth, PWA offline) | ✅ | — | `PLAN.md` §ფაზა 5 |
| 6: Performance (bundle 87 KB gzip, manualChunks) | ✅ | session #31 | `PLAN.md` §ფაზა 6 |
| 7: Extra E2E (export + supplier-modal) — 63/63 E2E | ✅ | session #32 | — |
| 8: Calendar UX (`react-datepicker` migration) | ✅ | session #33 | — |
| 9: Unified date-range business logic (Packet G) | ✅ | — | retail_sales 671.9s → 25.7s |
| 10: Dashboard-wide calendar propagation (Packet H) | ✅ | 2026-04-17 | Process 0-12 accepted; `cashflow` documented exception |

---

## AI Advisor — original roadmap (legacy path, 2026-04-17 / 18)

| Phase | Status | Date | Notes |
|---|---|---|---|
| AI Phase 0 Foundation | ✅ | 2026-04-17 | Data Quality 9.8/10, deps pinned, Anthropic + Telegram pings |
| AI Phase 1 MVP Chat | ✅ 🎬 | 2026-04-17 23:35 | `/api/chat` live, 163/163 unit + 70/70 E2E |
| AI Phase 1 Polish (prompt caching + column pruning) | ✅ 🎬 | 2026-04-18 00:20 | cache_read stable across repeats |
| AI Streaming SSE (`/api/chat/stream`) | ✅ 🎬 | 2026-04-18 00:42 | first-token 3.66–4.52s |
| AI Phase 2 Investigator (Sprint 1 backend / 2 prompt+mode / 3 frontend) | ✅ 🎬 | 2026-04-18 01:10 – 02:40 | 🔍 toggle + Cascade block + 9/9 E2E |
| Waybill Arithmetic Bug-Fix (`compute_waybill_total`) | ✅ | 2026-04-18 04:00 | Feb 27 = 7,882.68 ₾ / Feb 28 = 2,675.86 ₾ pinned |

**Note:** Phase 3+ of the original roadmap (Daily Briefing / Telegram push / Provider migration / Voice) was **rejected** by user on 2026-04-18 and superseded by `AI_GENIUS_PARTNER_PLAN.md` v2.1.

---

## AI Genius Financial Partner v2.1 — active roadmap

### Phase 0A — Critical Foundation

| Phase | Status | Date | Preview |
|---|---|---|---|
| 0A.1 Calculator Enforcement (generic `compute` tool, 8 ops) | ✅ 🎬 | 2026-04-18 23:00 | `HANDOFF_ARCHIVE/PREVIEWS/PHASE_0A_PREVIEW.md` ⚠️ DRIFT (header says Draft, code merged) |
| 0A.2 Self-Critique Loop (📊 / ⚠️ / 🎯 structure) | ✅ 🎬 | 2026-04-18 23:00 | same file |
| 0A.3 Today's Pulse (`today_context.py`) | ✅ 🎬 | 2026-04-18 23:00 | same file |

**Verification:** 73 new tests, pytest 381/381 green.

### Phase 0B — Genius Core (4 sprints)

| Sprint | Feature | Status | Date | Preview |
|---|---|---|---|---|
| 1 | Extended Thinking + Multi-hypothesis + 🧠 Deep Think toggle | ✅ 🎬 | 2026-04-19 | `PHASE_0B_PREVIEW.md` ⚠️ DRIFT |
| 2 | Prophet Forecasting + ARIMA ensemble (`forecast_revenue`) | ✅ 🎬 | 2026-04-19 18:42 | `PHASE_0B_SPRINT2_PREVIEW.md` ⚠️ DRIFT |
| 3 | ChromaDB Semantic Memory (`save_memory` / `recall_context`) | ✅ 🎬 | 2026-04-19 | `PHASE_0B_SPRINT3_PREVIEW.md` ⚠️ DRIFT |
| 4 | Decision Journal (CRUD + journal kinds) | ✅ 🎬 | 2026-04-19 23:40 | `PHASE_0B_SPRINT4_PREVIEW.md` |

**Verification:** Phase 0B FULLY CLOSED 2026-04-19 23:40; 7 features (0B.1–0B.7) landed across 4 sprints. 2 bug-fixes en-route (Windows venv Path caveat + ChromaDB `$lt`/`$gt` string-range caveat).

### Phase 1 — AI Persona & Context (4 parts)

| Part | Feature | Status | Date | Preview |
|---|---|---|---|---|
| A | "ხასიათი" + "საზრისობა" Layer 1 (5 ქუდი, persona, strict tone) | ✅ 🎬 | 2026-04-20 00:55 | `PHASE_1_PART_A_PREVIEW.md` |
| B | ქართული რეგულაცია + ფრენჩაიზი კონტექსტი (RS.ge, VAT, royalty) | ✅ 🎬 | 2026-04-20 01:28 | `PHASE_1_PART_B_PREVIEW.md` |
| C | Multi-Store DNA (ოზურგეთი urban vs დვაბზუ rural) | ✅ 🎬 | 2026-04-20 02:11 | `PHASE_1_PART_C_PREVIEW.md` |
| D | Self-Correction Loop (Retry / Latin alias / Self-triage) | ✅ 🎬 | 2026-04-20 02:50 | `PHASE_1_PART_D_PREVIEW.md` |

**Verification:** pytest 969/969 green at Part D close. 4 parts released on same night.

### Phase 2 — Specialized Tools

| Phase | Feature | Status | Date | Preview |
|---|---|---|---|---|
| 2.11 | Dead Stock Liquidation (`analyze_dead_stock`) | ✅ 🎬 | 2026-04-20 15:30 | `PHASE_2_11_DEAD_STOCK_PREVIEW.md` ⚠️ DRIFT |
| 2.12 | Supplier Negotiation Prep (`prepare_supplier_brief`, 5-factor leverage) | ✅ 🎬 | 2026-04-20 15:30 | `PHASE_2_12_SUPPLIER_NEGOTIATION_PREVIEW.md` ⚠️ DRIFT |

**Verification:** Real Anthropic dog-food PASS — Focused (ჯიდიაი) 9/9, Portfolio 10/10, Dead Stock 9/9. Session cost ~$0.48.

### Phase 3 — Co-Designer + Widgets + AI Tools

| Phase | Feature | Status | Date | Preview |
|---|---|---|---|---|
| 3.1 | Co-Designer Mode (PULL-ONLY, `propose_feature`) | ✅ 🎬 | 2026-04-20 17:50 | `PHASE_3_1_CO_DESIGNER_PREVIEW.md` |
| 3.5 | Dead Stock page + Supplier Concentration widget | ✅ 🎬 | 2026-04-20 23:50 | `PHASE_3_5_7_PREVIEW.md` |
| 3.7 | `compute_cash_runway` AI tool (PULL-ONLY workflow) | ✅ 🎬 | 2026-04-20 23:50 | `PHASE_3_5_7_PREVIEW.md` |

### Phase 4 — Autonomous Strategist

| Phase | Feature | Status | Date | Preview |
|---|---|---|---|---|
| 4A Part A | Debt Repayment Plan tool (`build_debt_repayment_plan`) | ✅ 🎬 | 2026-04-21 00:50 | `PHASE_4A_DEBT_PLAN_PREVIEW.md` |
| 4A Part B | React page + `/api/debt-plan` + journal mirror (2 bug-fixes en-route) | ✅ 🎬 | 2026-04-21 04:02 | same file |
| 4A Windows Service install (NSSM `FinancialDashboardBackend`) | ✅ | 2026-04-21 04:15 | — retired "backend restart #N" counter |
| 4B + 4C | AI Personality & Tool Design Tuning — 31 rules / 5 sprints | 📋 PLANNED | 2026-04-21 | `PHASE_4B_PROMPT_TUNING_PREVIEW.md` (root — only active preview) |

**Prerequisite for 4B:** Sprint 4B.0 Prune `SYSTEM_PROMPT_KA` 1,291 → ~900 lines before adding new rules.

### Hotfixes & collateral

| Fix | Status | Date |
|---|---|---|
| Excel Georgian Path Fix (`_resolve_safe_path` OneDrive) | ✅ | 2026-04-20 12:45 |
| Service Worker Cache Bug-Fix (route strategies + BUILD_ID) | ✅ | 2026-04-19 00:20 |
| AI FAB Stability Hotfix (eager import + SW cleanup + idempotent launch) | ✅ 🎬 | 2026-04-21 13:25 |

---

## Future work — Parking Lot (not scheduled)

From `AI_GENIUS_PARTNER_PLAN.md` v2.1 "10 ახალი Dashboard Features" + ~40 Parking Lot items. Not started. 10 dashboard widgets (Cash Runway widget done, others pending): Dead Stock (done), Supplier Concentration (done), plus 7 unscheduled (e.g. Daily Plan page, Monthly Strategy page). Exact list in `AI_GENIUS_PARTNER_PLAN.md`.

---

## Docs hygiene notes

- ⚠️ 6 PREVIEW files were archived with internal header still saying "Draft — თქვენი დასამტკიცებლად" even though the corresponding code had already merged. Marked `DRIFT` above. Accept as historical artifacts — do NOT edit retrospectively.
- `HANDOFF.md` banner (as of 2026-04-20 12:50) names Phase 1 Part D as latest; actual latest is Phase 4A + AI FAB hotfix per `CONTEXT_HANDOFF.md` (2026-04-21 13:25). Use `CONTEXT_HANDOFF.md` for current state, `HANDOFF.md` for archived evidence.
- Only one active PREVIEW remains in root: `PHASE_4B_PROMPT_TUNING_PREVIEW.md`. All other PHASE previews are under `HANDOFF_ARCHIVE/PREVIEWS/`.
