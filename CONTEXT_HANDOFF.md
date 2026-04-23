# CONTEXT HANDOFF — short brief

> **განახლდა**: 2026-04-24 (**Sprint 5.10 evidence-only** — VAT gap unit-error diagnosed; **906K claim WITHDRAWN**; real gap aligns with audit's **742K (net)**, pipeline data-gaps prevent full independent reproduction of 652K; production code NOT changed this session — fix queued as Sprint 5.11)
> **სტატუსი**: Phase 4A/4B/4C.2/4C.3 CLOSED · **Phase 2.1/2.2/2.4/2.5/2.6/2.8/2.9 COMPLETE** · Tier 1 + Tier 2 Sprint 1/2/3a COMPLETE · **🧾 Sprint 5.1 → 5.9 COMPLETE** · Phase 4C.1 VAT-tools-scoped ✅ · **Sprint 5.10 🚨 CRITICAL DISCOVERY** (906K inflated by unit error — see `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_10_UNIT_ERROR_PREVIEW.md`) — **Sprint 5.11 PENDING: fix `gap_vs_declared_ge` across 6 production files + tests + AI prompts + live dog-food**.

---

## რომელი დოკუმენტი რისთვისაა

| ფაილი | გამოყენება |
|---|---|
| **`CONTEXT_HANDOFF.md`** (ეს) | ახალი ჩატის startup — verified facts + do-not-touch + next step |
| **`PHASE_STATUS_MATRIX.md`** | ერთი ცხრილი ყველა phase-ის სტატუსით (live) |
| **`AI_GENIUS_PARTNER_PLAN.md`** | authoritative roadmap v2.1 (predates Phase 5) |
| **`PLAN.md`** | live status tracker (mixed narrative) |
| **`AGENTS.md`** | session-start checklist + GitNexus rules + Windows-venv caveats + Prompt Hygiene + Session Boundaries + Correction Escalation |
| **`HANDOFF.md`** | full evidence log (archival) |

**ახალი ჩატის read order**: ეს ფაილი → `AGENTS.md` → (phase-specific drill) `PHASE_STATUS_MATRIX.md`.

---

## Canonical paths & services

- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard`
- **Python interpreter** (canonical, parent venv): `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`
- **Backend**: Windows Service **`FinancialDashboardBackend`** (NSSM, auto-start + auto-restart 2s, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`, logs rotate 10MB/24h in `logs/backend_{stdout,stderr}.log`)
- **Service control**: `services.msc` · `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: service loads prompt at module-import time. After prompt changes, `Restart-Service` picks them up. For in-process AI tests, use `_scratch_dogfood_*.py` pattern (no service needed).
- **Tool surface (26)**: `read_data_json`(1), `compute_waybill_total`(2), `compute`(3), `forecast_revenue`(4), `recall_context`(5), `save_memory`(6), `journal_{add,list,update}_entry`(7-9), `analyze_dead_stock`(10), `prepare_supplier_brief`(11), `compute_cash_runway`(12), `compute_cash_flow_projection`(13), `build_debt_repayment_plan`(14), `simulate_scenario`(15), `analyze_product_profitability`(16), `find_promotion_candidates`(17), `detect_trends`(18), `get_vat_reconciliation_month`(19), `explain_unaccounted_cash`(20), `record_cash_outflow`(21), `read_source_code`(22), `grep_code`(23), `read_excel_source`(24), `validate_vs_source`(25), `propose_feature`(26).

---

## Verified facts

| მეტრიკა | მნიშვნელობა |
|---|---|
| **pytest** | **2,068/2,068 green** (~79s full run) |
| **`SYSTEM_PROMPT_KA`** | 1,163 lines |
| **Tool surface** | 26 |
| **Dashboard tabs** | 15 (incl. Store Compare, 💀 Dead Stock, ⚠️ Supplier Concentration, 📋 Debt Plan, 🧾 VAT) |
| **Pipeline cache** | 207 MB (was 864 MB — Sprint 3a slim-down) |
| **`data.json`** | 131.7 MB, 26 sections, 21,233 waybills |
| **VAT cumulative gap** | ⚠️ **906K ₾ headline is UNIT-WRONG** (Sprint 5.10 discovery: gross pipeline − net declared). Unit-corrected: **+90K pipeline independently** / **+742K audit-matched** (remaining 652K within pipeline coverage gaps). **Sprint 5.11 will fix.** |

---

## Commit history — Sprint 5.x (state audit response, 2026-04-23 → 2026-04-24)

| commit | sprint | summary |
|---|---|---|
| *pending* | **5.10** | **evidence-only session** — diagnosed unit error in `gap_vs_declared_ge` (gross − net mismatch inflating gap by +702K); identified 98.5/94 cross-match as hardcoded string, not computed; mapped fix blast radius (6 production files + tests + prompts). **No production code changed.** See `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_10_UNIT_ERROR_PREVIEW.md` + `_scratch_sprint5_10_*.json` evidence. |
| `6a4ee1b` | 5.9 | MAX-data-gap vs over-declaration: `insufficient_data` status for max=0 & (bank>0 \| declared>0); AI-facing warning prepended to summary_ka |
| `354ffe7` | 4C.1 scoped | VAT 3 tools schema Poka-yoke audit (by_shop docs, anti-triggers, STRICT do-not-guess) |
| `6e5118d` | 5.8 | per-shop by_shop breakdown (ოზურგეთი vs დვაბზუ); `tbc_per_shop_reliable` honesty flag; 22 new tests |
| `efcc79a` | 3a | cache slim-down 864→207 MB (cap retail_sales preview_rows per file) |
| `84faa43` | Phase 2.9 | `detect_trends` tool (MoM/YoY price×volume decomposition) |
| `5f94ded` | Phase 2.8 | Store Comparison page frontend |
| `e962857` | 5.6 | VAT AI live dog-food 3/3 PASS on Sonnet 4.6 |
| `cf39cd3` | 5.5 | **revenue = price × quantity fix** (9% drift → 612K cumulative revenue drop → 689K gap drop) |
| `46afd00` | 5.4 | Excel export for auditor/bookkeeper |
| `974f2db` | 5.3 | Dashboard 🧾 VAT & აუდიტი tab + cash classification UI |
| `5d45e9e` | 5.2 | TBC POS terminal-ID matching (5 physical terminals; transit-IBAN double-count eliminated) |
| `e866aa3` | 5.1.1 | `invoices_ge` ingest from RS.ge ა/ფ report (42 months, 491K ₾) + TBC overcount investigation |
| `3a18e45` | 5.1 | VAT reconciliation module + 3 AI tools + cash_outflow_journal.csv + SYSTEM_PROMPT_KA `🧾 VAT / აუდიტის კონსულტაცია` section |

All on `origin/main`. Older commits → `git log`.

---

## Live dog-food evidence (cumulative, real Sonnet 4.6 `think=True`)

- **Sprint 4B** (behavior rules), **4C.3** (summary_ka), **Phase 2.1/2.2/2.4/2.5/2.6** (tools), **5.6** (VAT trio): all **3/3 PASS** per phase. Total cost across phases ≈ $1.65.
- **Sprint 5.9** (2026-04-23) — **3/3 PASS** · 72.4s · ~$0.16. Pipeline regen activated 8 `insufficient_data` months (2022-10..12 + 2023-01..05). Scenarios:
  - (1) `2023-03 data-gap ask` — AI surfaced "MAX retail_sales Excel ფაილი აკლია" warning verbatim + explicitly said "დასკვნა «ბუღალტერს ხარვეზი აქვს» ამ ციფრებზე დამყარებით მცდარი იქნება" + prescribed upload + regen steps.
  - (2) `loaded over-declaration framing rejection` — AI refused to confirm premise, surfaced audit cross-check showing declared 49,379 ₾ ≈ audit 49,762 ₾, offered multi-hypothesis (50%/35%) and flagged MAX file absence as root cause.
  - (3) `2024-08 real month control` — AI correctly did NOT emit the data-gap warning (no false positive); routed to `get_vat_reconciliation_month` + `explain_unaccounted_cash` chain for the real 139K gap + 168K unaccounted cash + 30K VAT liability preview.
- **Phase 4C.1 Parts A+B routing** (2026-04-24) — **4/4 PASS** · ~109s · ~$0.25. Confirms 8-tool schema tightening (eacc59b + 3d13e8b) actually changes routing on real turns:
  - (1) `"2026-02-27-ში რამდენი ზედნადები?"` → `compute_waybill_total` (Part B Triggers block fired)
  - (2) `"რა პროდუქცია მაქვს 120+ დღე გაუყიდავი?"` → `analyze_dead_stock` ONLY (Part B anti-trigger kept analyze_product_profitability + find_promotion_candidates out — distinction between frozen vs live SKUs held)
  - (3) `"ფუდმარტს რამდენი ვალი?"` (no date) → `read_data_json(supplier_aging)` + `compute`, NOT `compute_waybill_total` (Part B anti-trigger for undated debt questions held)
  - (4) `"2024-08-ში declared vs რეალური?"` → `get_vat_reconciliation_month` (Part A anti-trigger away from read_data_json held).

---

## Do-not-touch rules (carry forward)

1. **Backend interpreter = parent venv only** (`...\AI აგენტი\venv\Scripts\python.exe`). Never `.venv` / project-local / system Python.
2. **Windows venv verification** = `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process <pid> | Select Path` — stub artifact always shows base interpreter).
3. **Env propagation** = verify `usage.thinking=true` in a real SSE call after any backend restart.
4. **Investigator prompt** (`SYSTEM_PROMPT_KA_INVESTIGATOR`) stays marker-free for chat-mode sections. Every Phase 4B rule has a do-not-touch investigator guard.
5. **GitNexus index** may be stale. If any GitNexus tool warns stale, run `npx gitnexus analyze` first.
6. **ChromaDB 1.5.x `$lt`/`$gt`** don't work on string metadata — Python post-fetch filter mandatory.
7. **Excel Georgian path**: `tools.py::_resolve_safe_path` uses `Path.absolute()`, NOT `Path.resolve()`.
8. **Prompt editing**: 600+ grep-style assertions pin `SYSTEM_PROMPT_KA`. Before any edit, grep tests for asserted Georgian phrases.
9. **4B rule conflict resolution**: Phase 4B rules sit above phase-specific sections. If conflict, principle wins.
10. **`.claude/scheduled_tasks.lock`** gitignored (Claude Code ScheduleWakeup artifact, machine-specific).
11. **data.json regen**: Sprint 5.9 requires pipeline regen to activate `insufficient_data` status on months 2022-10/11/12 + 2023-01..05. If data.json is older than commit `6a4ee1b`, rerun `python generate_dashboard_data.py` before any VAT drill-down.
12. **retail_sales revenue (Sprint 5.5)**: formula is `unit_price × quantity` per row. Pinned in `tests/test_retail_sales_revenue_formula.py`. Never regress to summing unit_price alone.

---

## Still-open work (priority order, fresh-session recommended for high-risk)

| # | item | size | risk | რატომ |
|---|---|---|---|---|
| **0** | **🚨 Sprint 5.11 — VAT gap unit-error fix** | ~1-2 sessions | **MED** | **URGENT**: `gap_vs_declared_ge` is unit-wrong across UI + AI + Excel. Blueprint + blast radius in `SPRINT_5_10_UNIT_ERROR_PREVIEW.md`. Single biggest audit-defense integrity fix. |
| 1 | **Phase 4C.1 Part C (if gaps appear)** | evidence-driven | LOW | Parts A+B covered 8 tools with real Triggers/Anti-triggers gaps. The remaining tools (forecast/math six + save_memory/recall_context/journal_add/journal_list + prepare_supplier_brief + analyze_product_profitability + find_promotion_candidates + build_debt_repayment_plan + propose_feature) were SKIPPED per evidence-based survey — they already carry Triggers + Anti-triggers + Returns + Honesty-rule blocks. Only open new schema-audit work if a live dog-food surfaces an actual routing miss. |
| 2 | **Tier 2 Sprint 3b — cache extension to bank / supplier / waybills** | ~1 session each | MED | applies Sprint 2/3a pattern per `project_pipeline_cache_pattern.md` memory; audit all-rows fields before caching |
| 3 | **Phase 2.3 `industry_benchmark`** | ~1 day | LOW | blocked on external data source decision (hardcoded retail medians? Excel import? public dataset?) — ask user |
| 4 | **Phase 3 remaining (4 features)** | ~1 week | LOW | conversation_summary_on_demand · margin_compression_radar · monthly_strategy_page · gap_analysis |
| 5 | **Phase 4 Advanced (9 features)** | ~2-3 weeks | MED | in `AI_GENIUS_PARTNER_PLAN.md` v2.1 |
| 6 | **Parking Lot** | — | — | ~40 items in v2.1 plan |

**Audit defense view** (rewritten 2026-04-24 after Sprint 5.10 evidence):

- **Real gap (net, audit-matched): 742K ₾.** Audit's Excel "სხვაობა ბრუნვაში" = 4,645,366 (net sum) − 3,903,150 (declared net) = **742,217 ₾** — reproduces exactly from the audit file.
- **Pipeline independently verifies 90K ₾** of this directly. Per-month check (2024-08, 2025-08, 2025-12): pipeline_gross ≈ audit_net × 1.18 within **0.3%** when data is complete.
- **Remaining ~652K is within pipeline coverage gaps** — not a disagreement with audit:
  - missing MAX POS Excel files: 2022-10..12 + 2023-01..05 (8 months, `status=insufficient_data`)
  - missing BOG bank statements: 2023-Q1 (3 months, pipe_bog=0, audit has ~34K)
  - TBC shortage 2023-08..2024-03 (8 months, pipeline captures 27–81% less TBC than audit — root cause unknown, needs separate investigation)
- **Previously reported "98.5% TBC / 94% BOG match"** (hardcoded in `vat_reconciliation_export.py:68-69`) — **WITHDRAWN**: actual cumulative match ratios are 95.7% / 88.7%, and that naive comparison mixes gross/net units. Meaningful cross-check requires unit normalization (which shows <0.3% per-month residual).
- **Previously reported "906K ₾ real gap"** — **WITHDRAWN as headline**: this number was produced by `total_real_ge (gross) − declared_ge (net)` which is a unit error. The 906 decomposes to **742 audit-true + 703 unit inflation − 652 coverage deficit** (approximate).
- **Sprint 5.11 (next session) will land the code fix.** Until then, 🧾 VAT dashboard tab + AI VAT tool + Excel export all still show the unit-wrong numbers. Do NOT share the 906K figure with the auditor; if the 742K audit figure is already what they have, that number is correct.

---

## `მოამზადე ახალი ჩატისთვის` — rule

- განაახლე ეს ფაილი (verified facts + do-not-touch + next step only).
- **არ შეაყრო ისტორია** — ისტორია `HANDOFF.md`-ში, evidence `HANDOFF_ARCHIVE/`-ში, git log-ში.
- Short brief target: **≤200 lines**. ისტორიული "წინა-სტატუსი" სექციები აკრძალულია.
