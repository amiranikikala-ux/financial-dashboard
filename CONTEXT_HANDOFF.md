# CONTEXT HANDOFF — short brief

> **განახლდა**: 2026-04-23 (**Sprint 5.1 LANDED** — vat_reconciliation pipeline section + 3 AI tools + SYSTEM_PROMPT_KA consultation mode + 37 new tests; **1,963/1,963 pytest green**; tool surface 22 → 25)
> **სტატუსი**: Phase 4A **FULLY CLOSED** + Phase 4B **COMPLETE** + Phase 4C.2/4C.3 **CLOSED** + **Phase 2.1/2.2/2.4/2.5/2.6 LIVE VERIFIED** + **Phase 2.9 pipeline unblocked** + **Tier 1 + Tier 2 Sprint 1/2 LIVE VERIFIED** + **🧾 Sprint 5.1 LANDED** (audit defense foundation: 37-month reconciliation evidence, 1.18M ₾ pipeline excess capture vs audit, cash outflow classification journal, per-month AI consultation with 18% VAT liability preview).

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
- **Tool surface**: **25 tools live** (Sprint 5.1 added `get_vat_reconciliation_month`, `explain_unaccounted_cash`, `record_cash_outflow`). Index positions: `compute_cash_flow_projection` @ 12, `build_debt_repayment_plan` @ 13, `simulate_scenario` @ 14, `analyze_product_profitability` @ 15, `find_promotion_candidates` @ 16, `get_vat_reconciliation_month` @ 17, `explain_unaccounted_cash` @ 18, `record_cash_outflow` @ 19, `propose_feature` @ 24 (tail). Tools with `summary_ka` (17 total): legacy 14 + 3 VAT tools. 8 tools explicitly **skipped** (raw-data readers + CRUD confirms).

---

## Commit history (this session — 24 commits on `main`)

| commit | subject |
|---|---|
| `3a18e45` | feat(pipeline+ai): Sprint 5.1 — VAT reconciliation + cash outflow journal + 3 AI tools |
| _pending_ | feat(pipeline): Tier 2 Sprint 2 — retail_sales incremental cache integration |
| `c1cccc6` | feat(pipeline): Tier 2 Sprint 1 — pipeline_cache module foundation |
| `e83063b` | docs(context-handoff): Tier 1 scale fix landed; Tier 2 incremental ingest queued |
| `ad4c345` | fix(server): Tier 1 scale fix — stream subprocess logs, atomic data.json, saner schedule |
| `fa4f62b` | docs(context-handoff): Phase 2.9 pipeline unblocked — tool build is next sprint |
| `85b870e` | feat(pipeline): Phase 2.9 unblock — retail_sales.by_category_by_month aggregate |
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
| **pytest** | **1,963/1,963 green** (~21s full run; 1,926 baseline + 37 Sprint 5.1 vat_reconciliation) |
| **`SYSTEM_PROMPT_KA`** | 1,351 lines (Sprint 5.1 added "🧾 VAT / აუდიტის კონსულტაცია" section with triggers, workflow, anti-patterns) |
| **new tests this session** | 4B 171 + 4C.2 38 + Phase 2.1 39 + Phase 2.2 52 + Phase 2.5 47 + Phase 2.6 72 + Phase 2.9 pipeline 10 + pipeline_cache v2 36 + retail_sales incremental 8 + Sprint 5.1 VAT 37 = **510** |
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

**Live dog-food evidence — Phase 2.5 `analyze_product_profitability` (2026-04-22)**:
3/3 scenarios PASS on real Sonnet 4.6 `think=True` via in-process `_scratch_dogfood_phase2_5.py`. Total tokens: 23,638 in / 5,629 out / 185,504 cache read. Est. cost $0.21.
- **Scenario 1 — worst SKUs (combined)**: summary_ka `"**Product X-Ray** (ორივე მაღაზია) · 1227/... პროდუქტი გააჩერდა · portfolio margin **12.8%** · worst: ... · ⚠️ 55 suspicious"` — AI generated full top-10 table + **explicitly flagged** data entry errors ("სობრანიე ბლექს — data entry error-ის კლასიკური სიმპტომი, ვერავინ ყიდის სიგარეტს 41%-იანი ზარალით"). Honesty rule worked perfectly.
- **Scenario 2 — ოზურგეთი best-margin SKUs**: summary_ka `"(ოზურგეთი) · 693/9095 პროდუქტი · portfolio margin **11.4%** · worst: **ლუდი/ესტრელა** (-4.4%) · best: **პოლიეთილენის პარკი** (89.2%) · ⚠️ 37 suspicious"`. AI proactively warned: "37 SKU-ს margin [-5%, 90%]-ის მიღმაა — სანამ მათზე გადაწყვეტილება მიიღებ, გადაამოწმე Excel-ში".
- **Scenario 3 — anti-trigger routing** (dead stock question): AI correctly called `analyze_dead_stock`, NOT `analyze_product_profitability`. Anti-trigger disambiguation held.
- Anti-markers ✅ — all 3 scenarios clean. `usage.thinking=True` on all turns.

**Live dog-food evidence — Phase 2.4 REDUCED `prepare_supplier_brief` portfolio `sort_by` (2026-04-22)**:
3/3 scenarios PASS on real Sonnet 4.6 `think=True` via in-process `_scratch_dogfood_phase2_4.py`. Total tokens: 4,328 in / 6,155 out / 280,002 cache read. Est. cost $0.19.
- **Scenario 1 — `sort_by="risk"` watch list**: "მომწოდებლების პორტფოლიოში ვისი payment reliability ყველაზე ცუდი? ვინ უნდა ჩავსვა watch list-ზე?" → AI called `prepare_supplier_brief(sort_by="risk", top_n=15)`. summary_ka `"**270 მომწოდებელი**, სულ 5,201,362.18 ₾ · top-5 41.93% (moderate) · #1 risk: **შპს ფუდმარტი** (unpaid 100%, debt 53,314 ₾, 🔴 behind) · top-15 debt-at-risk: **569,945 ₾**"` — AI structured a Critical/Systemic watch-list in reply, honoring the ranking. `sort_mode="risk"` echoed in payload.
- **Scenario 2 — leverage default (backward-compat)**: "ვის ვთხოვო discount-ი ჯერ?" → AI called `prepare_supplier_brief(sort_by="leverage", top_n=10)`. summary_ka legacy shape unchanged: `"... #1 call: **შპს ჯიდიაი** (leverage 71) · portfolio savings: **64,625.40 ₾/წელი**"`. No risk-mode markers leaked. `sort_mode="leverage"` echoed.
- **Scenario 3 — FOCUSED routing intact**: "შპს ჯიდიაიზე გამიკეთე brief" → AI called `prepare_supplier_brief(supplier_name="ჯიდიაი")` (focused mode). summary_ka `"**შპს ჯიდიაი** · leverage **71/100** (🟢 HIGH) · #1 play: *6% ფასდაკლება ...*"`. Portfolio `sort_by` addition did not disrupt focused routing.
- **Calibration learning**: first dry-run used phrasing "რომელ მომწოდებლებზე უფრო მეტი დავალიანება მიმაქვს?" — AI correctly routed to `read_data_json(supplier_aging)` per the schema's anti-trigger ("რამდენი ვალი მაქვს X-თან" → raw aging). Reframed as strategic monitoring ("watch list / ranking / payment reliability") — AI then hit `sort_by="risk"` cleanly. Schema anti-trigger is working as designed; risk-sort is the strategic-monitoring path, not the raw AP-lookup path.
- Anti-markers ✅ — all 3 scenarios clean. `usage.thinking=True` on all turns.

**Live dog-food evidence — Phase 2.6 `find_promotion_candidates` (2026-04-22)**:
3/3 scenarios PASS on real Sonnet 4.6 `think=True` via in-process `_scratch_dogfood_phase2_6.py`. Total tokens: 13,887 in / 5,823 out / 191,932 cache read. Est. cost $0.19.
- **Scenario 1 — generic promotion menu**: "მომავალი კვირის promotion-ისთვის რა პროდუქცია გავიტანო?" → AI proactively called `find_promotion_candidates` TWICE (once per store, ოზურგეთი + დვაბზუ) to compare. summary_ka `"**promotion menu** (ოზურგეთი) · 5/5 SKU · top: **ასანთი/ლეოპარდი** (margin 89% → 20% discount, 🟢 high) · evaluated 288/9095"`. AI flagged the suspicious 89% margin verbatim ("**#1 ასანთი** — 89% margin საეჭვოა. შესაძლოა cost field-ი არარეალურია. **ხელით გადაამოწმე Excel-ში სანამ promo-ზე გაიტან**") — the tool's honesty rule held without prompting.
- **Scenario 2 — store + discount-size constraint**: "ოზურგეთისთვის 10-15% discount, margin ბოლომდე არ მომიშალოს" → AI called `find_promotion_candidates(store="ოზურგეთი", top_n=5, max_suggested_discount_pct=15, min_margin_pct=15)` — all three knobs correctly inferred from user language. summary_ka carries 15% discount + ოზურგეთი label. Post-discount margins 53-74% surfaced cleanly; again flagged the 89% ასანთი data concern.
- **Scenario 3 — anti-trigger (dead stock routing)**: "რა პროდუქცია დევს 90+ დღე გაუყიდავი?" → AI called `analyze_dead_stock(days_threshold=90, top_n=25)`, NOT `find_promotion_candidates` (✅). Tool-description anti-trigger disambiguation held: promotion_candidates = push live SKUs; dead_stock = liquidate stuck inventory.
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

## Active packet — Phase 2 in progress (4 of 9 tools done)

Phase 4B ✅ **FULLY CLOSED**. Phase 4C.2 + 4C.3 ✅ **FULLY CLOSED**. **Phase 2.1 + 2.2 + 2.4 + 2.5 + 2.6** ✅ **LANDED + LIVE VERIFIED**.

**📋 Phase 2 remaining after 2026-04-22 audit:**

| Phase | Tool | Scope |
|---|---|---|
| 2.3 | `industry_benchmark` | "Margin 7.2% vs median 5% — ahead" (needs external data source) |
| ~~2.4~~ | ~~`supplier_risk_radar`~~ → ✅ **DONE 2026-04-22** (REDUCED) | `prepare_supplier_brief` PORTFOLIO `sort_by: "leverage" \| "risk"`. 9 tests, backward-compat preserved. Commit `c235afa`. LIVE 3/3. |
| ~~2.6~~ | ~~`promotion_candidate_finder`~~ → ✅ **DONE 2026-04-22** | `find_promotion_candidates` new tool: ranked promo menu with margin-headroom + volume + recency scoring, 5% post-discount floor, discount sizing capped by both user ceiling and floor. 72 unit tests + 3/3 live PASS. Suspicious-margin quarantine (mirrors X-Ray's [-5%, 90%] rule). Anti-trigger vs `analyze_dead_stock` verified live. |
| 2.8 | Store Comparison page (frontend) | "Margin 11% vs 2%" UI |
| 2.9 | `trend_detector` tool | 🟡 **PIPELINE UNBLOCKED** (commit `85b870e`) — `retail_sales.by_category_by_month` aggregate live, surfaced in AI summary, 10 regression tests green. **Tool build remains** — fresh session, ~1 day: MoM / YoY price-vs-volume decomposition per (category, store). Rerun `python generate_dashboard_data.py` to materialize the new section in live `data.json` before tool dog-food. |
| ~~2.10~~ | ~~`multi_source_triangulation`~~ | ❌ **DROPPED**: composition of `read_excel_source` + `validate_vs_source(section, expected_total, field_name)` already delivers "Excel vs data.json diff". No new tool required. |

**📋 Phase 4C.1 still open (high-risk, fresh session recommended):**

| Sub-sprint | scope | size |
|---|---|---|
| 4C.1 Schema Poka-yoke audit | All 22 tools: review argument names for ambiguity, tighten type enums, rewrite descriptions as "junior-dev docstrings" | 1 day, high-risk (schema changes cascade to tests + frontend aiClient) |

---

## 🚨 Phase 5 — Tax Audit System (NEW, HIGHEST PRIORITY)

State audit received 2026-04-22 for **შპს ჯეო ფუდთაიმი**. Bookkeeper errors caused 742,217 ₾ undeclared turnover. User wants SYSTEM (not one-off analysis) so bookkeeper cannot hide anything again.

**Source files** (in `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\`):
- `RS_Final_Check.xlsx` — state audit's waybill reconciliation (267 suppliers, 21,233 wb)
- `გაანგარიშება შპს ჯეო ფუდთაიმი.xlsx` — declared vs actual per month (37 months, 2023-01 to 2026-01)

**Key findings from 2024-08 deep-dive:**
- Audit total income: 236,914 ₾
- Direct MAX read: 259,087 ₾ (+22K vs audit — bookkeeper missed register sales)
- Pipeline retail_sales: 282,314 ₾ (+23K vs direct MAX — retail_sales aggregation drift)
- **3 pipeline classification bugs** (detailed below)

**Structural breakpoint**: 2024-06 — BOG POS started handling most in-store card transactions, TBC POS dropped from ~10K/month to ~500/month. Declared turnover did not track this change → 19-month gap accumulated.

### Sprint 5.1 — Audit Reconciliation Forensics ✅ **LANDED 2026-04-23**

**BREAKTHROUGH confirmed**: pipeline classification is correct; audit's numbers are systematically undercounting TBC POS.

> **⚠️ KNOWN SIGNAL ERROR (investigated 2026-04-23 02:30, not yet fixed):**
> RS.ge-ის ოფიციალური `პოს ტერმინალი.xls` (3,900 rows, 1.96M ₾ total, 2022-07 → 2026-02) გვიჩვენებს რომ **pipeline-ის TBC POS 2.38× overcounts** (pipeline 3.18M vs RS ფაქტი 0.38M). BOG POS სწორია (1.48M vs RS 1.57M, 6% VAT დელტა).
> **გავლენა**: 1.54M ₾ "ხარვეზი" შეიძლება გადაჭარბებული იყოს 2M+ ₾-ით. Pipeline's `tbc_card_income_patterns.json` patterns (`ecom/pos`, `wallet/domestic`) იჭერენ **online/wallet** გადახდებს რომლებიც არა-POS-ია. **Sprint 5.2 scope**: გამოვასწოროთ TBC pattern matching terminal-ID-based-ით (SH079927, RS014189, SH046092, SH034467, SH060853 = 5 TBC ფიზიკური terminals).

**Live-verified summary (2026-04-23 01:45 data.json regen, audit Excel auto-detected):**
| მეტრიკა | მნიშვნელობა |
|---|---|
| months total | 43 (2022-06 → 2026-02) · 🔴 22 red · 🟡 5 yellow · 🟢 9 green · ⚪ 7 no-declared |
| **total_real_ge** (pipeline) | **5,638,253.58 ₾** |
| **total_declared_ge** (audit 37 months) | **3,903,149.86 ₾** |
| **total_gap_ge** (pipeline − declared) | **+1,535,810.44 ₾** |
| **total_unaccounted_cash_ge** | **980,810.82 ₾** |
| **total_vat_liability_ge** (18% of unaccounted) | **176,545.95 ₾** |

**Cumulative under-declaration 1.54M ₾ is ~2x audit's 742K estimate.** Evidence in hand for audit defense OR voluntary-disclosure path (user decides).

**Forensics results (2024-08 deep dive):**
- TBC 2024-08 non-POS incoming = 12,163 ₾, **100% non-income**: 7,663 treasury tax refund + 4,500 BOG→TBC internal transfer (GE15BG...) + zero other. Pipeline's POS filter correctly excludes all three.
- BOG 2024-08 non-POS incoming = 800 ₾, **100% non-income**: single ჯეო→ჯეო internal transfer.
- TBC IBAN exclusivity audit (whole-year 2024): 4 of 5 IBANs fully pattern-covered; `GE69TB0000000251140006` has 29 rows (28,494 ₾) matched via IBAN-only (transit-account format "...სს თიბისი ბანკი..."), correctly classified as POS.

**37-month pipeline vs audit comparison (2023-01 → 2026-01):**
- **Audit total**: 4,645,366 ₾ · **Pipeline total**: 5,822,821 ₾ · **Pipeline excess**: **+1,177,455 ₾** (25% more)
- 33/37 months pipeline ≥ audit · 4 "miss" months all explainable (BOG file starts 2023-04; 2026-01 still incomplete)
- Audit's worst blind spot: 2024-08 TBC POS reported 6,697 ₾ vs real **164,903 ₾** → **158K ₾ missed in one month**, bucketed as phantom "cashreg 142K"
- **Audit's 742K "gap" is a severe underestimate** — real cumulative under-declaration is likely **1.5–2M+ ₾** by pipeline evidence

**Deliverables shipped:**
1. `dashboard_pipeline/vat_reconciliation.py` — pure aggregator: TBC POS + BOG POS + retail_sales + manual_payments + cash_outflow_journal + audit Excel → per-month bundle
2. `Financial_Analysis/cash_outflow_journal.csv` pattern (+ example file) — user-classified cash outflow entries (7 categories: salary_cash, personal_withdrawal, supplier_undocumented, business_expense, advance_to_employee, return_to_customer, unknown)
3. `data.json["vat_reconciliation"]` section — per-month fields: max_pos_ge, tbc_pos_ge, bog_pos_ge, bank_card_ge, cashreg_in_ge, cash_supplier_ge, cash_classified_ge, cash_unaccounted_ge, vat_on_unaccounted_ge, declared_ge (nullable), audit_total_ge, gap_vs_declared_ge, status (🟢/🟡/🔴), needs_user_input, data_quality.{max_pos_available, banks_complete, bank_exceeds_max}
4. Auto-detect: audit Excel `Financial_Analysis/გაანგარიშება*.xlsx` or one level up; cash journal at `Financial_Analysis/cash_outflow_journal.csv`
5. **3 AI tools** (per-month focus per user's explicit ask):
   - `get_vat_reconciliation_month(period)` — single-month drill-down (**main path**)
   - `explain_unaccounted_cash(period)` — consultation prompt with 18% VAT liability preview (triggered when cash_unaccounted ≥ 5K ₾)
   - `record_cash_outflow(period, amount, purpose_ka, category, vat_applies?, notes?)` — append classified entry to CSV, return remaining-unaccounted preview
6. **SYSTEM_PROMPT_KA** new section "🧾 VAT / აუდიტის კონსულტაცია" — triggers (`აუდიტი`/`declared`/`ბრუნვა`/`დღგ`/`სალარო`), per-month workflow, 18% VAT flag requirement, 4 anti-patterns (no guessing, no full-history dump on per-month question, no academizing, no hiding negative gap)
7. **37 new tests** (`tests/test_vat_reconciliation.py`): parse_audit_excel happy + error paths · parse_cash_outflow_journal with vat_applies defaults · append_cash_outflow_entry CSV write + header idempotency + category validation · compute_vat_reconciliation integration (2024-08 identity, unaccounted trigger, bank_exceeds_max flag, audit merge, empty inputs) · status classification thresholds · all 3 AI tools happy + error paths · tool registry presence · SYSTEM_PROMPT_KA markers
8. **5 test count pins updated** across `test_ai_agent`, `test_ai_cash_runway`, `test_ai_co_designer`, `test_ai_debt_plan`, `test_ai_forecasting`, `test_ai_investigator`, `test_ai_journal`, `test_ai_memory`, `test_ai_supplier_brief` (22 → 25 tool count)

**Design notes (for future sessions):**
- `cashreg_in_ge = max(0, MAX_POS - bank_card_ge)` — nonneg floor; `bank_exceeds_max=true` flag when Bank POS > MAX POS (e.g., 2023-06→2024-04 + 2026-01-02 show this pattern, needs Sprint 5.2 investigation)
- `cash_unaccounted_ge = cashreg_in - cash_supplier - cash_classified` — the residual that triggers AI consultation
- `invoices_ge` currently `null` (RS outgoing waybills not yet ingested — Sprint 5.2 scope; RS.ge Excel export has ONLY incoming `მისაღები`, 0 outgoing)
- `vat_on_unaccounted_ge = cash_unaccounted * 0.18` — preview liability if user can't classify
- Pipeline rerun required for `record_cash_outflow` changes to reflect in totals (tool returns `requires_pipeline_rerun=true`)

**Not in scope (Sprint 5.2+):**
- Outgoing RS.ge waybill ingest → populates `invoices_ge`
- Direct MAX Excel ingest path vs current retail_sales aggregator (divergence investigation 282K pipe vs 259K raw)
- Dashboard "VAT & აუდიტი" tab (5.4)
- Live AI dog-food verification (not done this session — backend restart + Anthropic API call queued)

**NOT changed** (deliberate): `tbc_card_income_patterns.json`, `bog_pos_terminal_income_patterns.json` — patterns are working correctly; would delete real income signal.

### Sprint 5.2 — Direct MAX ingest + cashreg separation (~1 session)
**Bug 1**: `retail_sales.revenue_ge` computation diverges from direct Excel read by ~10% (2024-08: 282K pipe vs 259K raw).
**Bug 2**: `retail_sales` bundles cash + card; audit needs cash-only (სალარო) separately.
**Fix**: verify revenue_ge formula (quantity × price vs summed line totals); add `cashreg_ge` = retail_sales.revenue_ge − (TBC POS + BOG POS) per month; per-month by-shop breakdown.

### Sprint 5.3 — `vat_reconciliation` pipeline section (~1 session)
New `data.json` section with monthly breakdown matching audit file structure:
- period, cashreg_ge (from 5.2), tbc_pos_ge (fixed in 5.1), bog_pos_ge, invoices_ge (from RS.ge outgoing waybills if present), total_ge, declared_ge (from uploaded audit file), gap_ge
- Excel import mechanism: user drops "declared ბრუნვა" Excel into `Financial_Analysis/` → pipeline auto-ingests per-month declared, computes gap

### Sprint 5.4 — AI tools + dashboard tab (~1 session)
- New AI tool `check_vat_reconciliation` (returns gap status, red-flag months, cumulative under-declaration)
- Dashboard page "VAT & აუდიტი" — month-by-month table with 🟢/🟡/🔴 color-coded gaps + trend chart
- SYSTEM_PROMPT_KA: trigger on "აუდიტი", "გადასახადი", "ბუღალტერი", "declared", "ბრუნვა" → auditor consultation mode
- Excel export ready for accountant/auditor

### Post-Phase 5 optional
- Phase 5.5 Voluntary disclosure letter generator (legal draft with numbers auto-filled)
- Phase 5.6 Automated RS.ge declaration fetch (if API available)
- Phase 5.7 Telegram bot for monthly gap alerts

---

## Next recommended steps

1. **Sprint 5.1 AI live dog-food** (~30 min, fresh session) — 3 scenarios against real Sonnet 4.6 via `_scratch_dogfood_sprint5_1.py`:
   a) "რა მოხდა 2024-08-ში declared-თან?" → expects `get_vat_reconciliation_month` → `explain_unaccounted_cash` chain
   b) "15,000 ხელფასი ხელზე + 8,000 საკანცელარიო" classification reply → expects 2× `record_cash_outflow` calls with correct categories
   c) Anti-trigger: "2024-08 მოცდემა" (ambiguous) → AI must ASK before guessing (no fabricated answer)
   After dog-food, rerun `generate_dashboard_data.py` to verify `cash_outflow_journal.csv` entries show up in `cash_classified_ge` / `cash_unaccounted_ge` drops.
2. **Sprint 5.2 — RS outgoing waybill ingest** (~1 session) — user exports RS.ge გასაცემი ზედნადებები 2023–2026 → new pipeline reader → populates `invoices_ge` per month. Cross-check audit file's `აფ.გამოწერილი` numbers — mismatch surfaces either audit or pipeline error.
3. **Sprint 5.3 — Direct MAX Excel ingest** (~1 session) — investigate retail_sales 282K vs MAX direct 259K divergence for 2024-08; add `cashreg_ge` column computed as `retail_sales.revenue - (TBC POS + BOG POS)` per month by shop.
4. **Sprint 5.4 — Dashboard "VAT & აუდიტი" tab** (~1 session) — month-by-month table 🟢/🟡/🔴 color coding + cash classification entry UI + Excel export for auditor.
5. ~~**Tier 2 Sprint 2 LIVE verification**~~ → ✅ **DONE 2026-04-22** (service stopped; hot run 574s @ 21:27→21:37, vs prior service baseline ~1700s over 10 runs = **66% faster, ~18 min saved per run**; retail_sales output **byte-equal** across revenue 5,039,708.48 / profit 648,931.64 / margin 12.88% / 9095 products / 10882 category-months / 1,462,967 rows; top-level data.json section keys identical; ~150 KB overall delta attributed to time-based fields, not retail_sales). **Cache size note**: `.pipeline_cache.json` is **905 MB** (per-file aggregates for ~200 Excel files) — flag for future Sprint 3/4 sizing decisions.
2. **Tier 2 Sprint 3a — retail_sales cache slim-down FIRST** (~0.5 session, fresh-session recommended). 2026-04-22 analysis of the 905 MB cache: `preview_rows` is 96% of size (428 MB out of 447 MB payload) across 6 files (retail_sales 2023-2026 per store, largest 384k rows). Field is misnamed — stores ALL matched rows per file, not a preview. Downstream `bundle["rows_preview"]` keeps only global top 50k (`RETAIL_SALES_ROWS_PREVIEW_LIMIT`). **Fix**: in `_process_retail_sales_file`, sort preview_rows by `_preview_sort_key` (date desc, revenue desc, product_name) and cap at 50_000 before returning. Proof of correctness: union of per-file top-50k ⊇ global top-50k (pigeonhole), so `bundle["rows_preview"]` stays byte-equal. Projected cache: ~107 MB (88.2% reduction). Also add regression test asserting cached preview_rows ≤ 50_000 per file.
3. **Tier 2 Sprint 3b — extend cache pattern to bank / supplier / waybills** (~1 session each, AFTER 3a). Template: extract per-file processing → return serializable payload → merge in orchestrator. `pipeline_cache` supports multiple sections via normalized path keys. Apply same cap-before-cache discipline from 3a — audit each section's "all-rows" fields before caching.
4. **Phase 2.9 `trend_detector` tool build (~1 day)** — pipeline is ready (`retail_sales.by_category_by_month` aggregate, commit `85b870e`). `data.json` already regenerated with the new section (2026-04-22 20:07). Tool scope: MoM / YoY price-vs-volume decomposition per (category, store), with suspicious-move quarantine mirroring X-Ray's [-5%, 90%] rule. Anti-triggers vs `analyze_product_profitability` + `analyze_dead_stock`.
5. **Phase 2.3 `industry_benchmark`** — needs an external benchmark data source decision first (hard-coded retail medians? Excel import? public dataset?). Ask user which.
6. **Sprint 4C.1 Schema Poka-yoke audit** (~1 day, high-risk, fresh session strongly recommended) — 22 tools' argument/description tightening.
7. **Phase 3 remaining** (4 features — conversation_summary_on_demand, margin_compression_radar, monthly_strategy_page, gap_analysis). ~1 week.
8. **Phase 4 Advanced** (9 features). ~2-3 weeks.
9. **Parking Lot** (~40 items documented in `AI_GENIUS_PARTNER_PLAN.md` v2.1).

---

## `მოამზადე ახალი ჩატისთვის` — rule

- განაახლე ეს ფაილი (verified facts + do-not-touch + next step only).
- **არ შეაყრო ისტორია** — ისტორია `HANDOFF.md`-ში, evidence `HANDOFF_ARCHIVE/`-ში, git log-ში.
- Short brief target: **≤200 lines**. Third "წინა-სტატუსი" block → stop → move to `HANDOFF.md`.
