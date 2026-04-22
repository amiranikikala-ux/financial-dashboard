# CONTEXT HANDOFF — short brief

> **განახლდა**: 2026-04-22 (Phase 2.1 + 2.2 landed — 2 of 9 Phase 2 tools done)
> **სტატუსი**: Phase 4A **FULLY CLOSED** + Phase 4B **COMPLETE (3/3 sprints, 28 rules, 171 tests)** + Phase 4C.2 **FULLY CLOSED** (10 tools with summary_ka, 8 explicitly skipped) + Phase 4C.3 **LIVE VERIFIED** + **Phase 2.1 Cash Flow Projection LIVE VERIFIED** ($0.16) + **Phase 2.2 Scenario Simulator LIVE VERIFIED** ($0.45, 3/3 PASS).

---

## რომელი დოკუმენტი რისთვისაა

| ფაილი | გამოყენება |
|---|---|
| **`CONTEXT_HANDOFF.md`** (ეს) | ახალი ჩატის startup — verified facts + do-not-touch + next step |
| **`AI_GENIUS_PARTNER_PLAN.md`** | authoritative roadmap v2.1 (Phase 0A–4B done, 4C partial, 2-4 remaining) |
| **`PHASE_STATUS_MATRIX.md`** | ერთი ცხრილი ყველა phase-ის სტატუსით |
| **`PLAN.md`** | live status tracker + full technical plan |
| **`PHASE_4B_PROMPT_TUNING_PREVIEW.md`** | closed; remaining 4C scope documented inside |
| **`AGENTS.md`** | session-start checklist + GitNexus rules + Windows-venv caveats + Prompt Hygiene + Session Boundaries + Correction Escalation (all Phase 4B.3) |
| **`HANDOFF.md`** | full evidence log (open only for per-phase drill-down) |
| **`HANDOFF_ARCHIVE/`** | 12 per-phase preview drafts + legacy roadmap (historical only) |

**ახალი ჩატის read order**: ეს ფაილი → `AGENTS.md` → (თუ Phase-specific context) `PHASE_STATUS_MATRIX.md`.

---

## Canonical paths & services

- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard`
- **Python interpreter** (canonical, parent venv): `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`
- **Backend**: Windows Service **`FinancialDashboardBackend`** (NSSM, auto-start + auto-restart 2s after crash, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1` persisted, logs rotate 10MB/24h in `logs/backend_{stdout,stderr}.log`)
- **Service control**: `services.msc` → "Financial Dashboard Backend" OR `Restart-Service FinancialDashboardBackend` (requires admin/UAC) OR `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: Service runs off working-tree code but loads prompt at module-import time. After prompt changes, `Restart-Service` picks them up (admin required). For in-process AI tests, use `_scratch_dogfood_*.py` pattern (no service needed).
- **Tool surface**: **20 tools live** (Phase 2.1 + 2.2 added two; `compute_cash_flow_projection` @ 12, `simulate_scenario` @ 14). Index positions: `compute_cash_flow_projection` @ 12, `build_debt_repayment_plan` @ 13, `simulate_scenario` @ 14, `propose_feature` @ 19 (tail). Tools with `summary_ka` (12 total): `compute`, `compute_waybill_total`, `forecast_revenue`, `analyze_dead_stock`, `compute_cash_runway` (legacy `status_summary_ka`), `build_debt_repayment_plan`, `recall_context`, `propose_feature`, `validate_vs_source`, `prepare_supplier_brief` (focused + portfolio), `compute_cash_flow_projection`, `simulate_scenario`. 8 tools explicitly **skipped** (raw-data readers + CRUD confirms).

---

## Commit history (this session — 19 commits on `main`)

| commit | subject |
|---|---|
| `b7a8801` | feat(ai): Sprint 4C.2 remaining — summary_ka on 4 final AI-facing tools |
| `5bb1d5d` | chore(gitignore): exclude .claude/scheduled_tasks.lock |
| `3893a67` | feat(ai): Sprint 4C.2 partial — summary_ka on 4 headline tools |
| `a6f9ef4` | feat(workflow): Sprint 4B.3 Tier 4 — 4 workflow anti-patterns |
| `27c6f71` | feat(ai): Sprint 4B.2 Tier 2+3 — 15 personality & format rules |
| `334220b` | feat(ai): Sprint 4B.1 Tier 1 — 9 fundamental behavior rules + STOP-CHECK rebalance |
| `0b40fa6` | docs(context-handoff): rewrite as canonical short brief (866 → 97 lines) |
| `07780bf` | chore: keep 2 AI Advisor helper scripts + drop 26 scratch files |
| `5b60e75` | chore(config): MCP + Claude commands + gitignore refinements |
| `71db708` | docs: AI Advisor Phase 1-4A work log + master plan + phase matrix |
| `13e54e7` | chore(scripts): parent-venv path resolution + idempotent API launcher |
| `825af3b` | feat(frontend): Packet F react-datepicker migration + SW cache-bust build hook |
| `5922566` | fix(pipeline): add missing dashboard_pipeline/date_filters.py |
| `cc33b4e` | feat(frontend): propagate period-aware params to tab pages + Suppliers widget |
| `55045d6` | feat(pipeline): period-aware tab responses + AI analytics builders |
| `c0fd63d` | feat(frontend): AI chat UI + Phase 3.5/4A dashboard pages |
| `0f3793e` | feat(server): add AI endpoints + period-aware query params |
| `7ef3451` | feat(ai): add AI Advisor module + Sprint 4B.0 prompt prune |

All on `origin/main`. `git status` clean.

---

## Verified facts

| მეტრიკა | მნიშვნელობა |
|---|---|
| **pytest** | **1,743/1,743 green** (~18s; 1,652 baseline + 39 Phase 2.1 + 52 Phase 2.2) |
| **`SYSTEM_PROMPT_KA`** | 1,299 lines (Phase 2.1 + 2.2 added **no** prompt text — tool descriptions carry all guidance) |
| **new tests this session** | 4B 171 + 4C.2 38 + Phase 2.1 39 + Phase 2.2 52 = **300** |
| **`data.json`** | regenerated 2026-04-22 05:10, 133 MB, 26 sections, 21,233 waybills (was 76MB truncated pre-regen) |
| **Live dog-food** | 3 scenarios PASS on real Anthropic Sonnet 4.6 `think=true`, ~$0.18 total cost |

**Live dog-food evidence — Sprint 4B (2026-04-22 05:13)**:
- Rule 1 Attempt-first ✅ — AI defaulted to 2025 December for ambiguous "რა margin იყო დეკემბერში?"
- Rule 3 Premise correction ✅ — AI pushed back on "50% margin ოზურგეთში" with real data (Net −72,814 ₾ Jan / −58,893 ₾ Feb)
- Rule 2 Max 1 question ✅ — scenarios ended with single priority clarify
- Rule 20 State scope ✅ — every number came with object + date + metric + source
- Multi-hypothesis 3-version ✅ — 60%/30%/10% breakdown on premise correction
- Anti-markers ✅ — 0 "ვცდი და მოვახსენებ" / 0 "ჩემს მეხსიერებაში" / 0 "მშვენიერი კითხვაა"

**Live dog-food evidence — Sprint 4C.3 summary_ka (2026-04-22)**:
3/3 scenarios PASS on real Sonnet 4.6 `think=True` via in-process `_scratch_dogfood_phase4c3.py`. Total tokens: 37,901 in / 4,221 out / 341,734 cache read. Est. cost $0.28.
- **Scenario 1 — `prepare_supplier_brief` FOCUSED** (ვასაძე): summary_ka `"**შპს ვასაძის პური** · leverage **32/100** (🟠 LOW) · play-ი ვერ შემუშავდა"` triggered AI to triangulate data (called read_data_json ×5 after brief) and build its own plays — validates the "no plays" fallback branch works + AI reads summary.
- **Scenario 2 — `prepare_supplier_brief` PORTFOLIO**: summary_ka `"**270 მომწოდებელი**, სულ 5,201,362.18 ₾ · top-5 41.93% (moderate) · #1 call: **შპს ჯიდიაი** (leverage 71) · portfolio savings: **64,625.40 ₾/წელი**"` — AI reused verbatim in reply ("**270 მომწოდებელი**, სულ **5,201,362 ₾** შესყიდვა"), cleanest single-call flow.
- **Scenario 3 — `validate_vs_source` inspection**: summary_ka `"**suppliers**: 270 მწკრივი (საწყისი inspection ...)"` surfaced in AI reply alongside source_hint.
- Anti-markers ✅ — all 3 scenarios clean.

**Live dog-food evidence — Phase 2.1 `compute_cash_flow_projection` (2026-04-22)**:
3/3 scenarios PASS on real Sonnet 4.6 `think=True` via in-process `_scratch_dogfood_phase2_1.py`. Total tokens: 6,394 in / 5,646 out / 175,072 cache read. Est. cost $0.16.
- **Scenario 1 — 14-day forward trajectory** (BOG 28K + TBC 12.5K): summary_ka `"**14 დღის პროექცია** · საწყისი **40,500 ₾** · 🟢 0 წითელი დღე · მინ. **26,476 ₾** (6 მაი) · საბოლოო **26,476 ₾** · prophet+arima ensemble"` surfaced verbatim in AI reply with full daily table.
- **Scenario 2 — upcoming_payments overlay** (ქირა 4,500 on 3 მაი): AI correctly passed `upcoming_payments` arg; tool validated + dropped the date when AI mistyped year (2025-05-03 vs 2026-05-03); AI's reply acknowledged the drop and added payment manually to table — honesty rule held.
- **Scenario 3 — anti-trigger routing** (months-left question): AI routed to `compute_cash_runway` (✅) NOT `compute_cash_flow_projection` (✅) — schema description's anti-triggers successfully disambiguated the two runway tools.
- Anti-markers ✅ — all 3 scenarios clean. `usage.thinking=True` on all turns.

**Live dog-food evidence — Phase 2.2 `simulate_scenario` (2026-04-22)**:
3/3 scenarios PASS on real Sonnet 4.6 `think=True` via in-process `_scratch_dogfood_phase2_2.py`. Total tokens: 63,520 in / 5,916 out / 574,293 cache read. Est. cost $0.45.
- **Scenario 1 — price +5% with elasticity auto**: summary_ka `"**scenario** (2026-02, ორივე მაღაზია) · **ფასი +5% · elasticity −0.8** · net **-15,266 → -11,514 ₾** (+3,752) · margin **-12.4% → -9.3%** (+3.1 pp) · 🟢 PROFIT_IMPROVE · volume=elasticity"` — AI surfaced full table + verdict + "volume -4% ავტომატურად დავიანგარიშე" caveat verbatim.
- **Scenario 2 — wage +10%**: AI called `read_data_json` 6× first to check payroll share (Phase 4B Rule 20 "state scope" discipline), THEN called `simulate_scenario(expense_change_pct=10, cogs_share=...)`. summary_ka `"net **-15,266 → -29,101 ₾** (-13,835) · margin **-23.6%** (-11.2 pp) · 🔴 PROFIT_ERODE"` verbatim. AI added honest caveat: payroll is ~20% of total expenses, so simulating 10% of total is overstated — and flagged it to user. Good epistemic humility.
- **Scenario 3 — anti-trigger routing** (historical margin lookup): AI correctly called `read_data_json` + `compute`, NOT `simulate_scenario` (✅). Description anti-triggers successfully disambiguated scenario-simulator from historical-lookup.
- Anti-markers ✅ — all 3 scenarios clean. `usage.thinking=True` on all turns.

**Data caveat**: Old pinned ground truth `2026-02-27 = 7,882.68 ₾` (waybill `transport_start_date`) is **stale** post-regen. New data.json shows 0 under `transport_start_date` field; `date` field shows 17 valid rows / 7,004.06 ₾. If regression tests pin 7,882.68, they'll need updating OR the generate_dashboard_data.py pipeline changed date-field semantics between 2026-04-18 and 2026-04-22.

---

## Do-not-touch rules (carry forward)

1. **Backend interpreter = parent venv only** (`...\AI აგენტი\venv\Scripts\python.exe`). Never `.venv` / project-local / system Python. Windows Service targets this.
2. **Windows venv verification** = `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process <pid> | Select Path` — stub artifact always shows base interpreter).
3. **Env propagation** = verify `usage.thinking=true` in a real SSE call after any backend restart. CommandLine match alone is insufficient.
4. **Investigator prompt** (`SYSTEM_PROMPT_KA_INVESTIGATOR`) stays marker-free for chat-mode sections. Every Phase 4B rule has a do-not-touch investigator guard in `test_ai_prompts_phase4b{1,2,3}.py`.
5. **GitNexus index** may be stale (2026-04-14 snapshot). If any GitNexus tool warns stale, run `npx gitnexus analyze` first.
6. **ChromaDB 1.5.x `$lt`/`$gt`** don't work on string metadata. Python post-fetch filter mandatory.
7. **Excel Georgian path**: `tools.py::_resolve_safe_path` uses `Path.absolute()`, NOT `Path.resolve()`.
8. **Prompt editing**: 600+ grep-style assertions now pin `SYSTEM_PROMPT_KA` (was 432, +171 added for 4B). Before any edit, grep tests for asserted Georgian phrases.
9. **4B rule conflict resolution**: Phase 4B rules sit above phase-specific sections — if Phase 2/3/4 section contradicts a behavior principle, principle wins (Rule 1 attempt-first > old STOP-CHECK mandatory cascade).
10. **`.claude/scheduled_tasks.lock`** is gitignored (Claude Code ScheduleWakeup artifact, machine-specific).
11. **data.json regen caveat**: old ground-truth numbers pinned in docs/tests may be stale after a pipeline regen. Re-verify before trusting pinned values.

---

## Active packet — Phase 2 started (2 of 9 tools done)

Phase 4B ✅ **FULLY CLOSED**. Phase 4C.2 + 4C.3 ✅ **FULLY CLOSED**. **Phase 2.1 `compute_cash_flow_projection`** + **Phase 2.2 `simulate_scenario`** ✅ **LANDED + LIVE VERIFIED**.

**📋 Phase 2 remaining (7 tools after 2.1 + 2.2):**

| Phase | Tool | Scope |
|---|---|---|
| 2.3 | `industry_benchmark` | "Margin 7.2% vs median 5% — ahead" (needs external data source) |
| 2.4 | `supplier_risk_radar` | Portfolio risk scoring (may already be covered by `prepare_supplier_brief` PORTFOLIO — audit first) |
| 2.5 | `product_profitability_xray` | Per-product margin deep-dive from retail_sales |
| 2.6 | `promotion_candidate_finder` | "5 candidates for ოზურგეთი" from dead-stock + margin data |
| 2.8 | Store Comparison page (frontend) | "Margin 11% vs 2%" UI |
| 2.9 | `trend_detector` | "Category YoY +11% price / −4% volume" |
| 2.10 | `multi_source_triangulation` | Likely subsumed by existing `validate_vs_source` — audit first |

**📋 Phase 4C.1 still open (high-risk, fresh session recommended):**

| Sub-sprint | scope | size |
|---|---|---|
| 4C.1 Schema Poka-yoke audit | All 20 tools: review argument names for ambiguity, tighten type enums, rewrite descriptions as "junior-dev docstrings" | 1 day, high-risk (schema changes cascade to tests + frontend aiClient) |

---

## Next recommended steps

1. **Phase 2.5 `product_profitability_xray`** — per-product margin lens. Product list from `retail_sales`. Clear user value ("which SKU bleeds money?"). ~1 day.
2. **Phase 2.9 `trend_detector`** — YoY category trends (price vs volume decomposition). Builds on existing monthly_pnl. ~1 day.
3. **Audit Phase 2.4 + 2.10 for overlap** with existing `prepare_supplier_brief` PORTFOLIO + `validate_vs_source`. May be unnecessary additions.
4. **Sprint 4C.1 Schema Poka-yoke audit** (~1 day, high-risk, fresh session strongly recommended) — 20 tools' argument/description tightening.
5. **Phase 3 remaining** (4 features — conversation_summary_on_demand, margin_compression_radar, monthly_strategy_page, gap_analysis). ~1 week.
6. **Phase 4 Advanced** (9 features — monthly_strategy_generator, quarterly_review, long_term_goals, scenario_multi_variable, stress_test, financial_literacy_teacher, retrospective_loop, exec_summary_generator, viz_suggester, peer_comparison). ~2-3 weeks.
7. **Parking Lot** (~40 items documented in `AI_GENIUS_PARTNER_PLAN.md` v2.1).

---

## `მოამზადე ახალი ჩატისთვის` — rule

- განაახლე ეს ფაილი (verified facts + do-not-touch + next step only).
- **არ შეაყრო ისტორია** — ისტორია `HANDOFF.md`-ში, evidence `HANDOFF_ARCHIVE/`-ში, git log-ში.
- Short brief target: **≤200 lines**. Third "წინა-სტატუსი" block → stop → move to `HANDOFF.md`.
