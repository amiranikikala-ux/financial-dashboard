# CONTEXT HANDOFF — short brief

> **განახლდა**: 2026-04-23 (**Sprint 5.9 LANDED** — MAX-data-gap vs over-declaration გარჩევა; **2,068/2,068 pytest green** ~73s; tool surface **26**; dashboard tabs **15**; SYSTEM_PROMPT_KA **1,163 lines**; cache **207 MB**; data.json **131.7 MB**; real gap **906K ₾** vs audit 742K)
> **სტატუსი**: Phase 4A/4B/4C.2/4C.3 CLOSED · **Phase 2.1/2.2/2.4/2.5/2.6/2.8/2.9 COMPLETE** · Tier 1 + Tier 2 Sprint 1/2/3a COMPLETE · **🧾 Sprint 5.1 → 5.9 COMPLETE** (full VAT audit system: reconciliation forensics · TBC POS terminal-ID fix · Dashboard 🧾 tab · Excel export · retail_sales revenue=price×qty fix · 3/3 live dog-food · per-shop by_shop breakdown · MAX data gap distinction). Phase 4C.1 VAT-tools-scoped ✅.

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
| **VAT cumulative gap** | **906K ₾** (post-Sprint-5.5 revenue fix; was 1.6M pre-fix) |

---

## Commit history — Sprint 5.x (state audit response, 2026-04-23)

| commit | sprint | summary |
|---|---|---|
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
| 1 | **Phase 4C.1 Part C (if gaps appear)** | evidence-driven | LOW | Parts A+B covered 8 tools with real Triggers/Anti-triggers gaps. The remaining tools (forecast/math six + save_memory/recall_context/journal_add/journal_list + prepare_supplier_brief + analyze_product_profitability + find_promotion_candidates + build_debt_repayment_plan + propose_feature) were SKIPPED per evidence-based survey — they already carry Triggers + Anti-triggers + Returns + Honesty-rule blocks. Only open new schema-audit work if a live dog-food surfaces an actual routing miss. |
| 2 | **Tier 2 Sprint 3b — cache extension to bank / supplier / waybills** | ~1 session each | MED | applies Sprint 2/3a pattern per `project_pipeline_cache_pattern.md` memory; audit all-rows fields before caching |
| 3 | **Phase 2.3 `industry_benchmark`** | ~1 day | LOW | blocked on external data source decision (hardcoded retail medians? Excel import? public dataset?) — ask user |
| 4 | **Phase 3 remaining (4 features)** | ~1 week | LOW | conversation_summary_on_demand · margin_compression_radar · monthly_strategy_page · gap_analysis |
| 5 | **Phase 4 Advanced (9 features)** | ~2-3 weeks | MED | in `AI_GENIUS_PARTNER_PLAN.md` v2.1 |
| 6 | **Parking Lot** | — | — | ~40 items in v2.1 plan |

**Audit defense view**: real gap is **906K ₾** (not 1.6M as pre-Sprint-5.5; not audit's 742K). Pipeline is cross-validated against RS.ge POS terminal export (98.5% TBC / 94% BOG match). Ready for voluntary-disclosure conversation OR audit defense — user decides.

---

## `მოამზადე ახალი ჩატისთვის` — rule

- განაახლე ეს ფაილი (verified facts + do-not-touch + next step only).
- **არ შეაყრო ისტორია** — ისტორია `HANDOFF.md`-ში, evidence `HANDOFF_ARCHIVE/`-ში, git log-ში.
- Short brief target: **≤200 lines**. ისტორიული "წინა-სტატუსი" სექციები აკრძალულია.
