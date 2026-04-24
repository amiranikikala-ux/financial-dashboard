# Phase Status Matrix

> **განახლდა:** 2026-04-24 · **ცოცხალი სტატუსი** → `CONTEXT_HANDOFF.md` · **master roadmap** → `AI_GENIUS_PARTNER_PLAN.md` · **closed milestone log** → `PLAN.md` · **evidence** → `HANDOFF.md` + `HANDOFF_ARCHIVE/`.
>
> ეს ფაილი — "ყველა phase ერთი ცხრილით" დოკუმენტი. ახალ phase-ს რომ ვხურავთ, აქაც ვაახლებთ. Open work-ის ცხრილი აქ არ არის — `CONTEXT_HANDOFF.md:107-116` authoritative.

---

## Legend

- ✅ **COMPLETE** — code merged, tests green
- 🎬 **LIVE VERIFIED** — real Anthropic Sonnet 4.6 dog-food passed (scripted `/api/chat` or in-process)
- 📋 **PLANNED** — next open work
- 💤 **PARKED** — Parking Lot, not scheduled
- ❌ **DROPPED** — superseded or rejected

## Top-level metrics (2026-04-24)

| | |
|---|---|
| pytest | **2,087/2,087 green** (~75s full) |
| Tool surface | **26 tools** |
| Dashboard tabs | **15** (incl. Store Compare, 💀 Dead Stock, ⚠️ Supplier Concentration, 📋 Debt Plan, 🧾 VAT) |
| `SYSTEM_PROMPT_KA` | **1,163 lines** |
| Pipeline cache | `.pipeline_cache.json` — Sprint 2/3a/3b/3c extensions |
| `data.json` | **131.7 MB**, 26 sections, 21,233 waybills |

---

## Dashboard MVP — Phases 1–10 (pre-AI foundation, 2025 → 2026-Q1)

| | |
|---|---|
| Phases 1–10 | ✅ — audit/refactor, APScheduler, E2E, PWA, performance, react-datepicker, Packet G unified date-range, Packet H calendar propagation. Detail → `PLAN.md` ცხრილი. |

## AI Advisor original MVP (2026-04-17 / 18) — **superseded 2026-04-18**

| Phase | Status |
|---|---|
| AI Phase 0 Foundation, Phase 1 MVP Chat + Polish, Streaming SSE, Phase 2 Investigator Sprint 1–3, Waybill Fix | ✅ 🎬 |
| Phase 3+ of original roadmap (Daily Briefing / Telegram / Voice) | ❌ DROPPED — superseded by `AI_GENIUS_PARTNER_PLAN.md` v2.1 |

---

## AI Genius Financial Partner v2.1 — active roadmap

### Phase 0A — Critical Foundation (2026-04-18)

| Phase | Status |
|---|---|
| 0A.1 Calculator Enforcement (`compute` tool) · 0A.2 Self-Critique Loop · 0A.3 Today's Pulse | ✅ 🎬 |

### Phase 0B — Genius Core (2026-04-19)

| Sprint | Feature | Status |
|---|---|---|
| 1 | Extended Thinking + 🧠 Deep Think toggle + Multi-hypothesis | ✅ 🎬 |
| 2 | Prophet 1.3 + ARIMA ensemble (`forecast_revenue`) | ✅ 🎬 |
| 3 | ChromaDB semantic memory (`save_memory` / `recall_context`, 18,263 chunks) | ✅ 🎬 |
| 4 | Decision Journal CRUD + `MAX_TOOL_ITERATIONS_DEEP=10` | ✅ 🎬 |

### Phase 1 — AI Persona & Context (2026-04-20)

| Part | Feature | Status |
|---|---|---|
| A | Strategic Partner persona + 5-hat + source hierarchy + 📌 anti-hallucination v2; deep cap 10→12 | ✅ 🎬 |
| B | Georgian regulation (VAT, საპენსიო, RS.ge, franchise royalty) + monthly rhythm | ✅ 🎬 |
| C | Multi-Store DNA (ოზურგეთი urban vs დვაბზუ rural) | ✅ 🎬 |
| D | Self-Correction Loop (retry / Latin alias MANDATE / self-triage) | ✅ 🎬 |

### Phase 2 — Specialized Tools

| Phase | Feature | Tool | Status | თარიღი |
|---|---|---|---|---|
| 2.1 | Cash Flow Projection | `compute_cash_flow_projection` | ✅ 🎬 | 2026-04-22 |
| 2.2 | Scenario Simulator | `simulate_scenario` | ✅ 🎬 | 2026-04-22 |
| 2.3 | Category Mix Analyzer (reframed from Industry Benchmark) | `mix_analyzer` | ✅ 🎬 | 2026-04-25 (`533c02f`) |
| 2.4 | Supplier Risk Radar (REDUCED) | `prepare_supplier_brief` portfolio | ✅ 🎬 | 2026-04-22 |
| 2.5 | Product Profitability X-Ray | `analyze_product_profitability` | ✅ 🎬 | 2026-04-22 |
| 2.6 | Promotion Candidate Finder | `find_promotion_candidates` | ✅ 🎬 | 2026-04-22 |
| 2.8 | Store Comparison page | — | ✅ | 2026-04-23 (`5f94ded`) |
| 2.9 | Trend Detector | `detect_trends` | ✅ | 2026-04-23 (`84faa43`) |
| 2.10 | Multi-Source Triangulation | — | ❌ DROPPED | covered by `read_excel_source` + `validate_vs_source` |
| 2.11 | Dead Stock Liquidation | `analyze_dead_stock` | ✅ 🎬 | 2026-04-20 |
| 2.12 | Supplier Negotiation Prep | `prepare_supplier_brief` | ✅ 🎬 | 2026-04-20 |

### Phase 3 — Co-Designer + Widgets + AI Tools

| Phase | Feature | Status | თარიღი |
|---|---|---|---|
| 3.1 | Co-Designer Mode (PULL-ONLY, `propose_feature`) | ✅ 🎬 | 2026-04-20 |
| 3.5 | Dead Stock page + Supplier Concentration widget | ✅ 🎬 | 2026-04-20 |
| 3.7 | `compute_cash_runway` AI tool | ✅ 🎬 | 2026-04-20 |
| 3.8 | `margin_radar` (time-series GM compression tracker, pin `5dfbf19`) | ✅ 🎬 | 2026-04-25 |
| 3.* | conversation_summary_on_demand · monthly_strategy_page · gap_analysis | 📋 PLANNED | ~1 week |

### Phase 4 — Autonomous Strategist

| Phase | Feature | Status | თარიღი |
|---|---|---|---|
| 4A Part A + B | Debt Repayment Plan + React page + journal mirror | ✅ 🎬 | 2026-04-21 |
| 4A Windows Service (NSSM `FinancialDashboardBackend`) | ✅ | 2026-04-21 — retired "backend restart #N" counter |
| 4B.0 Prune `SYSTEM_PROMPT_KA` 1,290→1,100 | ✅ | 2026-04-22 (`7ef3451`) |
| 4B.1–4B.3 Personality tuning (28 rules, 171 tests, 4 tiers) | ✅ 🎬 | 2026-04-22 (`334220b`/`27c6f71`/`a6f9ef4`) |
| 4C.1 Parts A + B Schema Poka-yoke (8 tools covered) | ✅ 🎬 | 2026-04-24 (`eacc59b`/`3d13e8b`) — 4/4 PASS live |
| 4C.1 Part C (evidence-driven) | 📋 PLANNED | only if live dog-food routing miss surfaces |
| 4C.2 `summary_ka` on 4 headline tools | ✅ | 2026-04-22 (`3893a67`) |
| 4C.3 Full-stack live dog-food | ✅ 🎬 | 2026-04-22 |
| Phase 4 Advanced (9 features) | 💤 PARKED | ~2-3 weeks — in v2.1 roadmap |

### 🧾 Phase 5 — Tax Audit System (NEW since v2.1, 2026-04-23 → 04-24)

Trigger: state audit for შპს ჯეო ფუდთაიმი; bookkeeper hid 742,217 ₾ undeclared turnover. User wants SYSTEM so this cannot recur.

| Sprint | Feature | Status | Commit |
|---|---|---|---|
| 5.1 | VAT reconciliation module + 3 AI tools + `cash_outflow_journal.csv` + SYSTEM_PROMPT_KA section | ✅ 🎬 | `3a18e45` |
| 5.1.1 | `invoices_ge` ingest from RS.ge ა/ფ report | ✅ | `e866aa3` |
| 5.2 | TBC POS terminal-ID matching (5 physical terminals; transit-IBAN double-count eliminated) | ✅ | `5d45e9e` |
| 5.3 | Dashboard 🧾 VAT & აუდიტი tab | ✅ | `974f2db` |
| 5.4 | Excel export for auditor | ✅ | `46afd00` |
| 5.5 | Revenue formula fix (`unit_price × quantity`) | ✅ | `cf39cd3` |
| 5.6 | VAT AI live dog-food 3/3 PASS | ✅ 🎬 | `e962857` |
| 5.7 | RS outgoing waybill ingest → populate `invoices_ge` | ❌ DROPPED | 2026-04-24 — retail-only business, no B2B / wholesale / inter-store volume worth tracking. `invoices_ge` already populated via Sprint 5.1.1. Audit defense unaffected. |
| 5.8 | Per-shop `by_shop` breakdown | ✅ | `6e5118d` |
| 5.9 | MAX-data-gap `insufficient_data` status | ✅ 🎬 | `6a4ee1b` — 3/3 PASS live |
| 5.10 | Unit error diagnosis (evidence-only, 906K claim withdrawn) | ✅ | `f876012` |
| 5.11 | Unit-fix landed end-to-end (NET basis primary) | ✅ 🎬 | `bfeeee5` + `3d41819` — 1/1 PASS live |
| 5.12 | TBC shortage 2023-08→2024-03 diagnosis (statement format change; no safe auto-fix) | ✅ | `684eab8` |

### Tier 2 — Pipeline cache scalability

| Phase | Feature | Status | Commit |
|---|---|---|---|
| Tier 1 | Stream subprocess logs + atomic `data.json` + schedule | ✅ | `ad4c345` |
| Sprint 1 | `pipeline_cache` module foundation | ✅ | `c1cccc6` |
| Sprint 2 | retail_sales per-file cache integration | ✅ | 2026-04-22 |
| Sprint 3a | Cap retail_sales preview_rows (cache 864→207 MB) | ✅ | `efcc79a` |
| Sprint 3b | Bank samurneo per-file cache (TBC 200× / BOG 748×) | ✅ | `8bd01e8` |
| Sprint 3c | Bank expense_categories per-file cache (TBC 62× / BOG 246×) | ✅ | `0a81b86` |
| Sprint 3d | tax_flow cache (cross-bank) | 📋 PLANNED | next recommended |
| Sprint 3e | POS terminal income cache (Sprint 5.12-sensitive) | 📋 PLANNED | needs pin test first |
| Sprint 3f | foodmart cashback cache | 📋 PLANNED | smallest, easy follow-up |

### Hotfixes & collateral (2026-04-19 → 04-21)

| Fix | Status |
|---|---|
| Excel Georgian Path Fix (`_resolve_safe_path` OneDrive + non-ASCII ancestor) | ✅ |
| Service Worker Cache Bug-Fix (route strategies + BUILD_ID) | ✅ |
| AI FAB Stability Hotfix (eager import + SW cleanup + idempotent launch) | ✅ 🎬 |
