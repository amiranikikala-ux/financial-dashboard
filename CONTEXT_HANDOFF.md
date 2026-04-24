# CONTEXT HANDOFF — short brief

> **განახლდა**: 2026-04-24 (**Sprint 3f LANDED** — TBC foodmart cashback per-file cache — **completes the per-file cache series** (retail_sales + samurneo + expense_categories + tax_flow + POS terminal income + foodmart cashback). Cold→hot 335x speedup. 7 new regression tests. Totals display-identical (313,725.75 ₾).)
> **სტატუსი**: Phase 4A/4B/4C.2/4C.3 CLOSED · **Phase 2.1/2.2/2.4/2.5/2.6/2.8/2.9 COMPLETE** · Tier 1 + Tier 2 Sprint 1/2/3a/**3b/3c/3d/3e/3f** COMPLETE (per-file cache series DONE) · **🧾 Sprint 5.1-5.6, 5.8-5.11 COMPLETE · 5.7 DROPPED (retail-only) · 5.12 evidence-only** · Phase 4C.1 VAT-tools-scoped ✅ · **Sprint 3f foodmart cache (pending commit)**.

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
| **pytest** | **2,114/2,114 green** (~124s full run; +41 regression pins Sprint 3b/3c/3d/3e/3f incremental cache) |
| **`SYSTEM_PROMPT_KA`** | 1,163 lines |
| **Tool surface** | 26 |
| **Dashboard tabs** | 15 (incl. Store Compare, 💀 Dead Stock, ⚠️ Supplier Concentration, 📋 Debt Plan, 🧾 VAT) |
| **Pipeline cache** | 207 MB (was 864 MB — Sprint 3a slim-down) |
| **`data.json`** | 131.7 MB, 26 sections, 21,233 waybills |
| **VAT cumulative gap** | **+90K ₾ net / +107K ₾ gross** (pipeline independently, Sprint 5.11 unit-fix landed). Audit's own figure: **742K ₾** (reproduces exactly from audit Excel). Pipeline-vs-audit delta = ~652K in pipeline coverage gaps (missing MAX/BOG/TBC for 11 months). Per-month match ≈0.3% where data is complete. |

---

## Commit history — Sprint 5.x (state audit response, 2026-04-23 → 2026-04-24)

| commit | sprint | summary |
|---|---|---|
| _pending_ | **3f** | **TBC foodmart cashback per-file cache — completes per-file cache series.** Extends the Sprint 3b/3c/3d/3e template to `collect_tbc_foodmart_cashback` (smallest collector — TBC-only, no config file on disk, no object_mapping dependency). Adds module constants `FOODMART_CASHBACK_DEFAULT_PATTERNS` + `FOODMART_CASHBACK_LABEL_KA`, `_content_fingerprint_foodmart_cashback` (sha1 over sorted patterns + default pattern tuple — future code-level edits to the hardcoded list invalidate stale caches automatically), `_empty_foodmart_cashback_payload`, `_process_tbc_foodmart_cashback_file`, `_merge_foodmart_cashback_payloads`. Collector now accepts `use_cache`/`cache_path`; wired at `_collect_income_bundles`. Same `sum()`-based total convention as Sprint 3e — display total unchanged (313,725.75 ₾ / 33 lines). **Live-verify**: cold 6.51s → hot 0.019s (335x speedup). 7 new integration tests (`tests/test_foodmart_cashback_incremental.py`). 2,114/2,114 pytest green. **Per-file cache series complete** — all six income/expense collectors (retail_sales Sprint 2, samurneo 3b, expense_categories 3c, tax_flow 3d, POS terminal 3e, foodmart 3f) now read through incremental per-file cache. |
| `89338e4` | **3e** | **POS terminal income per-file cache + precision fix.** Extends the Sprint 3b/3c/3d template to `collect_tbc_card_income` + `collect_bog_pos_terminal_income` (both in `_collect_income_bundles`). Adds `_load_bog_pos_patterns`, `_load_tbc_card_income_config`, `_content_fingerprint_bog_pos`, `_content_fingerprint_tbc_card_income` (covers patterns/terminal_ids/label_ka/object_mapping — `object_mapping` must be in fingerprint because per-line `object` field depends on it), `_process_bog_pos_terminal_income_file`, `_process_tbc_card_income_file`, `_merge_bog_pos_payloads`, `_merge_tbc_card_income_payloads`. Both collectors now accept `use_cache`/`cache_path`; wired at `_collect_income_bundles:352-357`. **Behavior change (user-approved)**: merge-level totals now computed via Python `sum()` instead of iterative `total += x`, eliminating ~1e-8 floating-point drift (TBC 378,734.76000001247 → 378,734.76; BOG 1,481,042.880000011 → 1,481,042.88; same rows/line_count, cleaner accumulator). No hardcoded values in tests or production docs reference the old drift values, so no downstream regressions. **Live-verify on real corpus**: TBC 7.44s → 0.50s (14.9x), BOG 29.69s → 2.13s (13.9x); digests byte-identical across no-cache/cold/hot after rebaseline. 12 new integration tests (`tests/test_pos_terminal_income_incremental.py`) including Sprint 5.2 terminal-ID filter round-trip + terminal_ids change invalidation. 2,107/2,107 pytest green. Unblocks Sprint 3f (foodmart cashback). |
| `7404af6` | **3d** | **Cross-bank tax_flow per-file cache landed.** Extends the samurneo/expense_categories template to the only cross-bank collector (`collect_tax_flow` iterates BOTH BOG AND TBC xlsx corpora, tags rows with `ბანკი: "BOG"\|"TBC"`). Adds `_load_tax_flow_config`, `_content_fingerprint_tax_flow` (sha1 over sorted patterns + treasury_in_markers + `TAX_TREASURY_CLUSTER_NOTE_KA` + default_patterns), `_process_{bog,tbc}_tax_flow_file`, `_merge_tax_flow_file_payloads`. Single combined `_run_cached_per_file` call with a path-dispatching processor (calling the helper twice would wipe the first bank's entries as "stale" on the second pass — BOG/TBC paths are disjoint so a single call is correct). Collector now accepts `use_cache`/`cache_path`; wired at `_collect_income_bundles:412`. **Live-verify on real corpus: 31.13s → 0.055s cold→hot (561x speedup); digest byte-identical across baseline/cold/hot** (out=112,675.41 ₾ / 543 lines, in=46,071.98 ₾ / 12 lines, treasury_in=46,071.98 ₾ / 12 lines). 8 new integration tests (`tests/test_tax_flow_incremental.py`) including cross-bank treasury-marker round-trip. 2,095/2,095 pytest green. Unblocks Sprint 3e (POS terminal income) and 3f (foodmart cashback). |
| `0a81b86` | **3c** | **Bank expense_categories per-file cache landed.** Extends the samurneo template to `collect_tbc_expense_categories` + `collect_bog_expense_categories`. Renames `_run_cached_samurneo` → `_run_cached_per_file` (generic, shared by both sprints). Adds `_load_expense_categories_config`, `_content_fingerprint_expense_categories` (sha1 over full 630-line cfg blob + object_mapping + bank + other_id), `_process_{tbc,bog}_expense_categories_file`, `_merge_expense_file_payloads`. Both collectors now accept `use_cache`/`cache_path`; wired at `_collect_income_bundles:378,390`. **Live-verify: TBC 7.65s→0.12s (62x), BOG 18.11s→0.07s (246x); digests byte-identical** (TBC grand 3,758,916.09 ₾ / 7,572 lines / 52 categories; BOG 1,608,164.77 ₾ / 3,880 lines). 7 new integration tests (`tests/test_expense_categories_incremental.py`). 2,087/2,087 pytest green. Sprint 5.12 TBC numbers unchanged. |
| `8bd01e8` | **3b** | **Bank samurneo per-file cache landed.** Extends Sprint 2 retail_sales cache template to `collect_tbc_samurneo_flow` + `collect_bog_samurneo_flow`. Adds `_load_samurneo_patterns`, `_content_fingerprint_samurneo` (bank-scoped SHA1 over patterns + include_all), `_process_{tbc,bog}_samurneo_file`, `_merge_samurneo_file_payloads`, `_run_cached_samurneo`. Both collectors now accept `use_cache`/`cache_path`; wired `use_cache=True` at `_collect_income_bundles:409-410`. **Live-verify on real corpus: TBC 6.66s→0.03s (200x), BOG 23.22s→0.03s (748x); digests byte-identical with no-cache run (TBC exp 77,270/ret 168,010, BOG exp 120,703.95/ret 76,390).** 7 new integration tests (`tests/test_samurneo_incremental.py`) mirror retail_sales incremental pattern. 2,080/2,080 pytest green. Sprint 5.12 TBC shortage numbers unchanged. Unblocks Sprint 3c/3d/3e (tax_flow, TBC card_income + BOG POS, expense_categories, foodmart cashback). |
| `684eab8` | **5.12** | **TBC shortage diagnosis — evidence-only.** Per-row forensics on 2023-08..2024-03 + RS.ge source-of-truth + 8-bucket classification reveal TBC bank statement format changed in 2024-04: before the change, SH046092 and SH034467 terminal transactions were posted to transit-IBAN `GE69TB0000000251140006` with merchant-ID tags (`33001022152`, `33001023234`, `01301132349`) but no physical terminal ID embedded; after 2024-04 TBC started embedding terminal IDs in rollup rows. Sprint 5.2's terminal-ID filter correctly excludes merchant-ID rows (which would double-count in post-change months) but incidentally loses ~52K ₾ of real per-transaction income in the 8 pre-change months. No safe auto-fix: same row signature represents "real income" in pre-change months and "double-count aggregates" in post-change months. Audit's TBC figure (computed from RS.ge × 1/1.18) correctly captures all these transactions — pipeline's +90K independent gap verification is unaffected. See `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_12_TBC_SHORTAGE_EVIDENCE.md`. |
| `3d41819` | **5.11** | **unit-error fix landed end-to-end** — `vat_reconciliation.py` now computes `gap_vs_declared_ge` = total_real_net − declared (NET basis, matches audit); adds `gap_gross_ge` + `total_real_net_ge` as explicit alternatives; removes hardcoded 98.5/94 claim from methodology; also fixes declared=0 placeholder case (was polluting gap sum by ~82K). Export + AI tools + frontend + tests (+5 new regression pins) + SYSTEM_PROMPT_KA all updated. `generate_dashboard_data.py` output log now exposes gross vs net. **2,073/2,073 pytest green.** data.json regenerated — UI/AI/Excel now show unit-correct numbers. |
| `f876012` | **5.10** | **evidence-only session** — diagnosed unit error in `gap_vs_declared_ge` (gross − net mismatch inflating gap by +702K); identified 98.5/94 cross-match as hardcoded string, not computed; mapped fix blast radius (6 production files + tests + prompts). **No production code changed.** See `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_10_UNIT_ERROR_PREVIEW.md` + `_scratch_sprint5_10_*.json` evidence. |
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
- **Sprint 5.11 unit-fix** (2026-04-24, post-commit bfeeee5) — **1/1 PASS** · 27.7s · ~$0.05 · in-process Sonnet 4.6 `think=True`. Scenario: `"2024 აგვისტოში declared vs რეალური ბრუნვა — რა არის გაპი?"` → AI called `get_vat_reconciliation_month` + `explain_unaccounted_cash`, emitted explicit "NET საფუძველი (პირველადი, audit-matched)" table with declared 139,485 / total_real_net 236,169 / gap_net +96,684 / gap_gross +114,087 labeled as alternative. Verified: "ნეტო" surfaced, no trace of old 906K headline, thinking=True, no anti-markers. In-process test — confirms production AI will behave correctly once `FinancialDashboardBackend` service restarts (admin/UAC required) to pick up the new prompt + tools cache.

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
| **1** | **Tier 2 Sprint 3f — foodmart cashback** | **~1 session** | LOW | `collect_tbc_foodmart_cashback` — smallest collector, last in the per-file cache series. |
| 4 | **Phase 4C.1 Part C (if gaps appear)** | evidence-driven | LOW | Parts A+B covered 8 tools. Remaining tools already carry Triggers + Anti-triggers + Returns + Honesty-rule blocks per evidence survey. Only open new schema-audit work if a live dog-food surfaces an actual routing miss. |
| 2 | **Phase 2.3 `industry_benchmark`** | ~1 day | LOW | blocked on external data source decision (hardcoded retail medians? Excel import? public dataset?) — ask user |
| 3 | **Phase 3 remaining (4 features)** | ~1 week | LOW | conversation_summary_on_demand · margin_compression_radar · monthly_strategy_page · gap_analysis |
| 4 | **Phase 4 Advanced (9 features)** | ~2-3 weeks | MED | in `AI_GENIUS_PARTNER_PLAN.md` v2.1 |
| 5 | **Parking Lot** | — | — | ~40 items in v2.1 plan |

**Recently CLOSED** (drill into commit/evidence if needed, not open work):
- Sprint 3f (_pending commit_) — foodmart cashback per-file cache; 335x hot speedup; 7 new tests (2,114/2,114 green); **per-file cache series COMPLETE** across all 6 income/expense collectors
- Sprint 3e (`89338e4`) — POS terminal income per-file cache + precision fix; TBC 14.9x / BOG 13.9x hot speedup; 12 new tests; user-approved `sum()` total convention (removes ~1e-8 fp drift)
- Sprint 3d (`7404af6`) — cross-bank tax_flow per-file cache landed, 561x hot speedup on real corpus (31.13s → 0.055s), 8 new tests; single combined `_run_cached_per_file` call with path-dispatching processor (BOG/TBC paths disjoint)
- Sprint 3c (`0a81b86`) — expense_categories per-file cache landed, 62x TBC / 246x BOG speedup, 7 new tests; `_run_cached_samurneo` generalized to `_run_cached_per_file`
- Sprint 3b (`8bd01e8`) — samurneo per-file cache landed, 200x TBC / 748x BOG speedup, 7 new tests
- Sprint 5.12 (`684eab8`) — TBC shortage 2023-08→2024-03 diagnosed, no safe auto-fix, audit-defense unaffected (see `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_5_12_TBC_SHORTAGE_EVIDENCE.md`)
- Sprint 5.11 (`bfeeee5` + `3d41819`) — VAT gap unit-error fixed end-to-end, live AI 1/1 PASS

**Audit defense view** (rewritten 2026-04-24 after Sprint 5.11 unit-fix landed, TBC line sharpened by Sprint 5.12 diagnosis):

- **Real gap (net, audit-matched): 742K ₾.** Audit's Excel "სხვაობა ბრუნვაში" = 4,645,366 (net sum) − 3,903,150 (declared net) = **742,217 ₾** — reproduces exactly from the audit file.
- **Pipeline independently verifies 90K ₾ (net) / 107K ₾ (gross)** directly. Per-month check (2024-08, 2025-08, 2025-12): pipeline_gross ≈ audit_net × 1.18 within **0.3%** when data is complete.
- **Remaining ~652K is within pipeline coverage gaps** — not a disagreement with audit:
  - missing MAX POS Excel files: 2022-10..12 + 2023-01..05 (8 months, `status=insufficient_data`)
  - missing BOG bank statements: 2023-Q1 (3 months, pipe_bog=0, audit has ~34K)
  - **TBC statement format pre-2024-04** (Sprint 5.12): 8 months (2023-08..2024-03), ~52K ₾ of SH046092/SH034467 per-transaction income posted to transit-IBAN with merchant-ID tags only (no physical terminal ID in text). Sprint 5.2's terminal-ID filter correctly excludes them to prevent double-counting in post-change months; audit's figure (RS.ge × 1/1.18) captures them independently. No safe auto-fix.
- **Old "98.5% TBC / 94% BOG match"** (hardcoded) and **"906K real gap"** (unit error) — both WITHDRAWN in Sprint 5.10 evidence + Sprint 5.11 code fix. UI/AI/Excel now reflect correct numbers.
- **For the auditor**: audit's 742K figure is correct. Pipeline agrees unit-for-unit where data is complete. Any discussion of "real gap" should cite 742K (net, audit-matched), optionally qualified with "pipeline-independent verification is +90K due to coverage gaps in months X, Y, Z — not a methodological disagreement."

---

## `მოამზადე ახალი ჩატისთვის` — rule

- განაახლე ეს ფაილი (verified facts + do-not-touch + next step only).
- **არ შეაყრო ისტორია** — git commit log = authoritative, `HANDOFF_ARCHIVE/` = preview-ები/evidence, `HANDOFF.md` = commit SHA → archive index.
- Short brief target: **≤200 lines**. ისტორიული "წინა-სტატუსი" სექციები აკრძალულია.
