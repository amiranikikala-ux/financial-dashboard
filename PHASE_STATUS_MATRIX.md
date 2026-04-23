# Phase Status Matrix

> **განახლდა:** 2026-04-23
> **მიზანი:** ერთი ცხრილი — ყველა phase-ის ცხადი მდგომარეობა. ფართო narrative `PLAN.md`-ში, ისტორიული evidence `HANDOFF.md`-ში, საწყისი preview-ები `HANDOFF_ARCHIVE/PREVIEWS/`-ში.
>
> **Authoritative docs:**
> - Short chat brief (**canonical live status**): `CONTEXT_HANDOFF.md`
> - Master roadmap (historical v2.1, 2026-04-18 — **predates Phase 5**): `AI_GENIUS_PARTNER_PLAN.md`
> - Live status tracker (mixed narrative + addenda): `PLAN.md`
> - Full evidence log: `HANDOFF.md`
> - Legacy (Phase 1-2 AI evidence only): `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md`

---

## Legend

- ✅ **COMPLETE** — code merged, tests green
- 🎬 **LIVE VERIFIED** — scripted `/api/chat` or in-process dog-food passed on real Anthropic Sonnet 4.6
- 📋 **PLANNED** — scope drafted, awaits approval/start
- 💤 **PARKED** — in Parking Lot, not scheduled
- ❌ **DROPPED** — scope rejected or superseded
- ⚠️ **DRIFT** — preview file's internal status doesn't match merged code (archived copy reflects pre-merge draft)

---

## Verified top-level metrics (2026-04-23)

| მეტრიკა | მნიშვნელობა |
|---|---|
| pytest | **2,045/2,045 green** (~77s full run) |
| Tool surface | **26 tools** (`detect_trends` @ 17; Sprint 5.1 VAT trio @ 18-20) |
| Dashboard tabs | **15** (incl. Store Compare + 💀 Dead Stock + ⚠️ Supplier Concentration + 📋 Debt Plan + 🧾 VAT) |
| `SYSTEM_PROMPT_KA` | **1,351 lines** |
| Pipeline cache | **207 MB** (was 864 MB — Sprint 3a slim-down) |
| `data.json` | **133 MB**, 26 sections, 21,233 waybills |

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

## AI Advisor — original MVP (2026-04-17 / 18)

| Phase | Status | Date | Notes |
|---|---|---|---|
| AI Phase 0 Foundation | ✅ | 2026-04-17 | Data Quality 9.8/10, deps pinned, Anthropic + Telegram pings |
| AI Phase 1 MVP Chat | ✅ 🎬 | 2026-04-17 | `/api/chat` live, 163/163 unit + 70/70 E2E |
| AI Phase 1 Polish (prompt caching + column pruning) | ✅ 🎬 | 2026-04-18 | cache_read stable across repeats |
| AI Streaming SSE (`/api/chat/stream`) | ✅ 🎬 | 2026-04-18 | first-token 3.66–4.52s |
| AI Phase 2 Investigator (Sprint 1-3) | ✅ 🎬 | 2026-04-18 | 🔍 toggle + Cascade block + 9/9 E2E |
| Waybill Arithmetic Bug-Fix (`compute_waybill_total`) | ✅ | 2026-04-18 | Feb 27 = 7,882.68 ₾ / Feb 28 = 2,675.86 ₾ pinned (**⚠️ stale post-regen**, see CONTEXT_HANDOFF data caveat) |

**Note:** Phase 3+ of the original roadmap (Daily Briefing / Telegram push / Provider migration / Voice) was **rejected** by user on 2026-04-18 and superseded by `AI_GENIUS_PARTNER_PLAN.md` v2.1.

---

## AI Genius Financial Partner v2.1 — active roadmap

### Phase 0A — Critical Foundation

| Phase | Status | Date | Preview |
|---|---|---|---|
| 0A.1 Calculator Enforcement (generic `compute` tool) | ✅ 🎬 | 2026-04-18 | `HANDOFF_ARCHIVE/PREVIEWS/PHASE_0A_PREVIEW.md` ⚠️ DRIFT |
| 0A.2 Self-Critique Loop (📊 / ⚠️ / 🎯) | ✅ 🎬 | 2026-04-18 | same |
| 0A.3 Today's Pulse (`today_context.py`) | ✅ 🎬 | 2026-04-18 | same |

### Phase 0B — Genius Core

| Sprint | Feature | Status | Date |
|---|---|---|---|
| 1 | Extended Thinking + Multi-hypothesis + 🧠 Deep Think | ✅ 🎬 | 2026-04-19 |
| 2 | Prophet + ARIMA ensemble (`forecast_revenue`) | ✅ 🎬 | 2026-04-19 |
| 3 | ChromaDB Semantic Memory (`save_memory` / `recall_context`) | ✅ 🎬 | 2026-04-19 |
| 4 | Decision Journal (CRUD + journal kinds) | ✅ 🎬 | 2026-04-19 |

### Phase 1 — AI Persona & Context

| Part | Feature | Status | Date |
|---|---|---|---|
| A | "ხასიათი" + "საზრისობა" Layer 1 (5 ქუდი, persona) | ✅ 🎬 | 2026-04-20 |
| B | ქართული რეგულაცია + ფრენჩაიზი (RS.ge, VAT, royalty) | ✅ 🎬 | 2026-04-20 |
| C | Multi-Store DNA (ოზურგეთი urban vs დვაბზუ rural) | ✅ 🎬 | 2026-04-20 |
| D | Self-Correction Loop (Retry / Latin alias MANDATE / Self-triage) | ✅ 🎬 | 2026-04-20 |

### Phase 2 — Specialized Tools

| Phase | Feature | Tool | Status | Date |
|---|---|---|---|---|
| 2.1 | Cash Flow Projection | `compute_cash_flow_projection` | ✅ 🎬 | 2026-04-22 |
| 2.2 | Scenario Simulator | `simulate_scenario` | ✅ 🎬 | 2026-04-22 |
| 2.3 | Industry Benchmark | `industry_benchmark` | 📋 PLANNED | — — needs external data source decision |
| 2.4 | Supplier Risk Radar (REDUCED) | `prepare_supplier_brief` portfolio `sort_by` | ✅ 🎬 | 2026-04-22 |
| 2.5 | Product Profitability X-Ray | `analyze_product_profitability` | ✅ 🎬 | 2026-04-22 |
| 2.6 | Promotion Candidate Finder | `find_promotion_candidates` | ✅ 🎬 | 2026-04-22 |
| 2.8 | Store Comparison page (frontend) | — | ✅ | 2026-04-23 (commit `5f94ded`) |
| 2.9 | Trend Detector (MoM/YoY price×volume) | `detect_trends` | ✅ | 2026-04-23 (commit `84faa43`) |
| 2.10 | Multi-Source Triangulation | — | ❌ DROPPED | composition of `read_excel_source` + `validate_vs_source` covers it |
| 2.11 | Dead Stock Liquidation | `analyze_dead_stock` | ✅ 🎬 | 2026-04-20 |
| 2.12 | Supplier Negotiation Prep | `prepare_supplier_brief` | ✅ 🎬 | 2026-04-20 |

### Phase 3 — Co-Designer + Widgets + AI Tools

| Phase | Feature | Status | Date |
|---|---|---|---|
| 3.1 | Co-Designer Mode (PULL-ONLY, `propose_feature`) | ✅ 🎬 | 2026-04-20 |
| 3.5 | Dead Stock page + Supplier Concentration widget | ✅ 🎬 | 2026-04-20 |
| 3.7 | `compute_cash_runway` AI tool (PULL-ONLY workflow) | ✅ 🎬 | 2026-04-20 |

**Phase 3 remaining (not yet started):** conversation_summary_on_demand, margin_compression_radar, monthly_strategy_page, gap_analysis. ~1 week budget.

### Phase 4 — Autonomous Strategist

| Phase | Feature | Status | Date |
|---|---|---|---|
| 4A Part A + B | Debt Repayment Plan + React page + journal mirror | ✅ 🎬 | 2026-04-21 |
| 4A Windows Service install (NSSM `FinancialDashboardBackend`) | ✅ | 2026-04-21 | retired "backend restart #N" counter |
| 4B.0 Prune `SYSTEM_PROMPT_KA` 1,290→1,100 | ✅ | 2026-04-22 (commit `7ef3451`) |
| 4B.1 Tier 1 Fundamental (9 rules, 68 tests) | ✅ | 2026-04-22 (commit `334220b`) |
| 4B.2 Tier 2+3 Personality+Format (15 rules, 79 tests) | ✅ | 2026-04-22 (commit `27c6f71`) |
| 4B.3 Tier 4 Workflow Anti-patterns (4 rules, 24 tests) | ✅ 🎬 | 2026-04-22 (commit `a6f9ef4`) |
| 4C.1 Schema Poka-yoke audit (26 tools) | 📋 PLANNED | ~1 day, **high-risk** — schema changes cascade to tests + frontend aiClient |
| 4C.2 `summary_ka` on headline tools (4 + 4) | ✅ | 2026-04-22 (commits `3893a67`, `b7a8801`) |
| 4C.3 Full-stack live dog-food (3/3 PASS) | ✅ 🎬 | 2026-04-22 |

**Phase 4 Advanced (Parking Lot):** 9 features documented in `AI_GENIUS_PARTNER_PLAN.md`. ~2-3 weeks. Not scheduled.

### 🧾 Phase 5 — Tax Audit System (NEW since v2.1 plan — HIGHEST PRIORITY)

**Trigger (2026-04-22):** state audit received for **შპს ჯეო ფუდთაიმი**; bookkeeper errors caused 742,217 ₾ undeclared turnover (real gap **1,595,306 ₾** per post-fix pipeline). User wants SYSTEM so bookkeeper cannot hide anything again.

| Sprint | Feature | Status | Date |
|---|---|---|---|
| 5.1 | Audit Reconciliation Forensics — `vat_reconciliation.py` + 3 AI tools + `cash_outflow_journal.csv` + SYSTEM_PROMPT_KA section | ✅ | 2026-04-23 (commit `3a18e45`) |
| 5.1.1 | Live dog-food 3/3 PASS | ✅ 🎬 | 2026-04-23 |
| 5.2 | TBC POS terminal-ID fix (5 physical terminals; transit IBAN double-count eliminated) | ✅ | 2026-04-23 |
| 5.3 | Dashboard 🧾 VAT tab + Excel export | ✅ | 2026-04-23 |
| 5.4 | Retail_sales preview cap + revenue formula fix | ✅ | 2026-04-23 |
| 5.5 | Terminal-ID POS rewire | ✅ | 2026-04-23 |
| 5.6 | VAT AI dog-food 3/3 PASS | ✅ 🎬 | 2026-04-23 (commit `e962857`) |
| 5.7 | RS outgoing waybill ingest → populate `invoices_ge` | 📋 PLANNED | ~1 session — user exports RS.ge გასაცემი ზედნადებები; cross-check `აფ.გამოწერილი` |
| 5.8 | Per-shop `by_shop` breakdown in vat_reconciliation | ✅ | 2026-04-23 — MAX POS/TBC/BOG/cashreg_in per ოზურგეთი/დვაბზუ; retail_sales `by_object_by_month` aggregation; `tbc_per_shop_reliable` honesty flag; summary_ka surfaces per-shop when ≥2 shops material. +22 tests (12 by_object_by_month + 10 by_shop). Revenue formula 282K vs 259K divergence already fixed in Sprint 5.5. |

### Scalability — Tier 1 + Tier 2

| Phase | Feature | Status | Date |
|---|---|---|---|
| Tier 1 | Stream subprocess logs + atomic `data.json` + saner schedule | ✅ | 2026-04-22 (commit `ad4c345`) |
| Tier 2 Sprint 1 | `pipeline_cache` module foundation | ✅ | 2026-04-22 (commit `c1cccc6`) |
| Tier 2 Sprint 2 | retail_sales incremental cache integration | ✅ | 2026-04-22 |
| Tier 2 Sprint 3a | Cap retail_sales preview_rows per file (cache 864→207 MB) | ✅ | 2026-04-23 (commit `efcc79a`) |
| Tier 2 Sprint 3b | Extend cache pattern to bank / supplier / waybills | 📋 PLANNED | ~1 session each, AFTER 3a. See `project_pipeline_cache_pattern.md` memory. |

### Hotfixes & collateral

| Fix | Status | Date |
|---|---|---|
| Excel Georgian Path Fix (`_resolve_safe_path` OneDrive) | ✅ | 2026-04-20 |
| Service Worker Cache Bug-Fix (route strategies + BUILD_ID) | ✅ | 2026-04-19 |
| AI FAB Stability Hotfix (eager import + SW cleanup + idempotent launch) | ✅ 🎬 | 2026-04-21 |

---

## Still-open work (in priority order)

1. **Sprint 5.7 — RS outgoing waybill ingest** (state audit scope) — ~1 session
2. **Sprint 5.8 — Direct MAX ingest + cashreg separation** (state audit scope) — ~1 session
3. **Tier 2 Sprint 3b — cache extension to bank/supplier/waybills** — ~1 session each
4. **Phase 2.3 `industry_benchmark`** — needs external data source decision first (hard-coded retail medians? Excel import? public dataset?)
5. **Sprint 4C.1 Schema Poka-yoke audit** (~1 day, high-risk, fresh session strongly recommended) — 26 tools' argument/description tightening
6. **Phase 3 remaining** (4 features). ~1 week.
7. **Phase 4 Advanced** (9 features). ~2-3 weeks.
8. **Parking Lot** (~40 items in `AI_GENIUS_PARTNER_PLAN.md` v2.1)

---

## Docs hygiene notes

- ⚠️ 6 PREVIEW files were archived with internal header still saying "Draft — თქვენი დასამტკიცებლად" even though the corresponding code had already merged. Marked `DRIFT` above. Accept as historical artifacts — do NOT edit retrospectively.
- `AI_GENIUS_PARTNER_PLAN.md` v2.1 predates Phase 5 (Tax Audit System). Phase 5 lives in `CONTEXT_HANDOFF.md` + this matrix; v2.1 roadmap master does NOT mention it.
- `PLAN.md` main body narrative stops at Phase 1 Part D; Phase 2 / 4B / 4C / 5 status lives as `Active:` / `წინა-სტატუსი` blob in lines 287-327. Use `CONTEXT_HANDOFF.md` for current state.
- `HANDOFF.md` (2026-04-22 02:24) is archival; not kept in sync with recent commits.
