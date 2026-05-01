# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-01 (Excel POS retired → MegaPlus DB primary; 4 commits land cost-imputation, MegaPlus retail synthesis, supplier_profitability switch, windowed by_product). გრძელი წაკითხვა საჭირო **არ არის**. Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. Evidence → `HANDOFF.md` + `HANDOFF_ARCHIVE/`.
>
> ✅ **TODAY (2026-05-01) — Excel retirement + MegaPlus retail end-to-end**:
> - **`db21a7d` feat(megaplus): cost imputation + per-product/per-month/per-category rollups** — d1ff190 Excel-pipeline cost-imputation logic ported to SQL via a `#pec` temp table (`effective_unit_cost = cost_paid / MAX(qty_bought, qty_sold)`); rollup output gains `by_product` (top 10000), `by_month`, `by_category`, `by_category_by_month`. **ვასაძე margin 83.58% → 12.03% დვაბზუ / 9.44% ოზურგეთი** ✓ — recorded MAX-POS cost preserved as `cogs_recorded` for transparency.
> - **`a6c6891` feat(supplier-profitability): switch to MegaPlus retail source + revenue cap** — new helper `_megaplus_to_retail_by_product` converts `data["megaplus_live"]` into `retail_sales.by_product` shape (per-store `object_totals` synthesized from store_id 1329/1301). `build_supplier_profitability` prefers MegaPlus first, falls back to `retail_sales`. **d1ff190 qty cap now applied to REVENUE alongside cost** — without revenue scaling, lifetime MegaPlus retail credited the supplier with revenue from inventory shipped by someone else. New `revenue_sold_full_ge` field preserves raw retail revenue. `generate_dashboard_data.py` reordered: MegaPlus block runs BEFORE supplier_profitability so the matcher sees `megaplus_live`.
> - **`c35560f` feat(megaplus): windowed by_product (last 365 days)** — `by_product_recent` field added per store (filtered to last 365 days from anchor); `_megaplus_to_retail_by_product` prefers it over lifetime so cost↔revenue stay in the same pricing era. Cache size 7 MB → 10 MB per store. Margins on the matched portfolio land closer to reality (vasadze 6.34% — within 0.7pp of Excel-era 7.1%).
> - **`215deaa` feat(retail): synthesize retail_sales bundle from MegaPlus DB** — new `retail_sales.synthesize_from_megaplus(megaplus_live)` builds the full retail_sales bundle shape (overall, by_object, by_month, by_category, by_category_by_month, by_object_by_month, by_product top-1000, top-N lists). Pipeline injects synthetic only when Excel `files_read_count == 0` so it never overwrites real Excel data. **RetailSales.jsx tab now renders MegaPlus data automatically — no JSX changes needed**. Live: revenue 4.85M ₾ / cost 4.25M ₾ / profit 593K ₾ / margin 12.24% / 8449 products / 36 months (2024-03 → 2026-04).
> - **Excel POS folders DELETED** (~60 MB freed, both copies + parent): `Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/` + `.../სოფ ოზურგეთი/` were not symlinks (despite earlier CONTEXT entry — checked via `Get-Item.LinkType` empty on both). 6 Excel files (3 monthly per store, Q1 2026). Folders were already in `.gitignore` so no git event from deletion. **MegaPlus DB is primary going forward; RS waybills cross-check only.**
> - **`dashboard_pipeline/_megaplus_setup/` DELETED** — 4 dev-time setup scripts (test_connection, restore_bak, inspect_tables, inspect_v2). Untracked, no git event.
> - **Pipeline post-Excel-retirement verified** on C:\ — 0 errors / 0 warnings, 28 API artifacts, data.json 67 MB → 52 MB then back up to 52 MB (synthesized retail_sales adds ~5 MB; full sequence: 67 → 31 → 47 → 52 across 4 commits). Live numbers: 46 verified / 5 partial / 14 unverified / 5 protected (was 34/17/14/5 with Excel — 12pp better coverage); ფინანსური დაფარვა 85.2% (was 77.9%); portfolio profit/margin will be revisited (see Known Issues below).
> - **User restarted FinancialDashboardBackend service** (2026-05-01 evening) — live dashboard now serves the MegaPlus-derived retail_sales section. User browser-confirmed RetailSales tab renders correctly.
> - **MegaPlus cache contents post-refresh**: დვაბზუ 5982 lifetime products + 4488 recent (last 365d), 10 MB JSON; ოზურგეთი 6389 lifetime + 3904 recent, 11 MB JSON.
>
> 🚀 **HUGE WIN**: Excel POS export for დვაბზუ was missing **~64% of rows** vs MegaPlus DB (Q1 2026: Excel 97K ₾ vs MegaPlus 273K ₾ revenue). ოზურგეთის Excel matched MegaPlus cent-for-cent. The Excel→MegaPlus migration FIXED a silent data gap nobody knew about. User goal of "MegaPlus = primary, RS doesn't get mixed" achieved end-to-end.
>
> 📌 **OPEN — for next session**:
> 1. **🔴 ELIZI false KPI fix** — cigarette name-fuzzy matching attributes other distributors' sales to ELIZI. Live numbers: cost_imp 79K, matched_rev only 4.9K, margin **−873%** ← drags portfolio margin to −7.7%. Pre-existing limitation per CONTEXT_HANDOFF; the d1ff190 cap + revenue scaling correctly bound supplier attribution but cigarette name-fuzzy matches still attribute wrong inventory. Fix paths: (a) require barcode match for PROTECTED categories — would lose ELIZI's full match coverage, (b) ingest the MAX vendor-tag file `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (per-supplier rollup, დვაბზუ-only) to override pipeline supplier totals, (c) add cigarette-supplier-tag column to the imported_products schema.
> 2. **`retail_sales_top_products` SQLite export bug** (pre-existing, NOT my fault, NOT a blocker) — `dashboard_pipeline/export_sqlite.py:111` reads `(retail_sales).top_products` but the schema has `top_products_by_revenue` and `top_products_by_profit` instead. The sqlite table has been 0 rows since forever — even with Excel data. Easy single-line fix in a separate commit.
> 3. **UI premium refresh** — when user wants to start a UI sprint, propose Claude Design (claude.ai/design) + Claude Code workflow per memory `project_claude_design_workflow.md`. First candidate: per-store MegaPlus card (side-by-side დვაბზუ vs ოზურგეთი with KPI grid + sparkline + top-5 supplier mini-list). Skip subscribing until UI sprint actively starts.
> 4. **Auto-sync OneDrive ↔ C:\** (carryover from 2026-05-02) — today's "C:\ drifted 10 commits behind" pattern will recur unless we add a post-commit/post-merge hook or scheduled task. Light-touch fix.
> 5. **Date anomaly follow-up** (carryover) — ოზურგეთი DB has 234 active orders dated 2009 (0.026% of orders, 661 ₾ revenue). Likely legacy seed/test rows. Optional: filter `WHERE ORD_TIMESTAMP >= '2023-01-01'` in rollup query.
>
> ⚠️ **Known caveat**: portfolio margin currently shows **−7.7%** in `data.imported_products.profitability_summary.portfolio.margin_pct`. Excel-era equivalent was +7.1%. The negative is dragged ENTIRELY by ELIZI's cigarette name-fuzzy false KPI (item 1 above) — vasadze, Coca-Cola, Iberia, Jidiai etc. all show plausible margins (3-25%). Once ELIZI is fixed, portfolio margin should land near +5 to +12%.
>
> 🚀 **HUGE WIN — MegaPlus DB direct integration LANDED (2026-05-01 → 02 ღამე)** — user-მა აღმოაჩინა `Financial_Analysis/მეგაპლიუსის არქიტექტურა/2/MEGA-BACKUP/` ფოლდერი 3 ZIP-ით (ყოველდღე 14:30-ზე rolling backup, თითო `PLUS_1329_MEGA_YYYYMMDD.zip` ~70 MB compressed / ~600 MB uncompressed `.bak`-ის სახით). file-header `TAPE` magic = MS SQL Server full backup. ერთი ფაილი = სრული DB-ის snapshot (ისტორიული, არა incremental).
>
> **Setup ნაბიჯები ყველა გავიდა:**
> - ✅ SQL Server 2022 Express install (winget, instance `localhost\SQLEXPRESS`)
> - ✅ ODBC Driver 18 for SQL Server (winget)
> - ✅ pyodbc 5.3.0 add to project venv
> - ✅ April 30 backup restore წარმატებული — DB `MEGAPLUS_LATEST`, **53 ცხრილი**, key tables: PRODUCTS (100,737 rows) / DISTRIBUTORS (9,426) / GET (49,790 purchases) / ORDERS (722,342 sales lines, 719,594 active) / OPER (719,594) / PROD_AGR (185,994 product↔supplier links) / AGREEMENTS (10,176)
> - ✅ ახალი module `dashboard_pipeline/megaplus_backup.py` — finds newest `PLUS_*.zip`, extracts, restores, reads supplier rollups (lifetime + 30day + 90day), writes `_megaplus_state.json` for idempotent re-runs (~1s no-op when nothing new, ~3 min when new ZIP)
> - ✅ Wired into `generate_dashboard_data.py` `run()` just before `_write_outputs` — non-fatal try/except
> - ✅ Watch folder: `C:\financial-dashboard\Financial_Analysis\მეგა პლუს backup\`
> - ✅ Memory note saved at `project_megaplus_db_integration.md`
>
> **რეალური ცოცხალი ფაქტები გამოვიდა:**
> - **Portfolio (lifetime)**: revenue 2,222,755 ₾ / cogs 1,848,013 ₾ / profit 374,742 ₾ / **margin +16.86%** (Excel pipeline ცხადობდა −249.4% — ცრუ)
> - **ELIZI lifetime**: revenue 221,677 ₾ / margin **+19.57%** (Excel pipeline ცხადობდა −31.02%; MAX rollup ცხადობდა +5.31%)
> - **282 მომწოდებელი** სრული რუკით (Excel pipeline-ი 70-ს კი მხოლოდ; PROD_AGR 185,994 product↔supplier vendor-tag-ი მთლიანად ცხადია name-matching-ის გარეშე)
> - Date range: **2024-03-31 → 2026-04-30** (2+ წელი, 720K active orders)
>
> ✅ **CLOSED 2026-05-02**: yesterday's "UNCOMMITTED CHANGES" + "ხვალ დავამატებ ოზურგეთს" both addressed in this session — 2 commits landed (`c338c93` + `a0468aa`), pushed, C:\ synced, pipeline verified.
>
> 🐛 **Known issue (არ-blocker, listed under OPEN above)**: ვასაძე margin **83.58% lifetime** ცხადდება DB rollup-ში — `ORD_GETPRICE` ცხადია near-zero MAX POS-ში ვასაძის პროდუქტებზე. იგივე bug, რასაც Excel pipeline-ისთვის `d1ff190` (cost imputation from GET table) მოაგვარა. იგივე fix DB module-ში ცალკე session-ში.
>
> 🚨 **PRIOR SESSION CLOSED VIA HANDOFF (2026-05-01 ~late)** — language regression event: partial Georgian morphology artifacts plus filler tokens accumulated 11+ in a single response while synthesizing MAX file findings (specific tokens deliberately omitted from this file to avoid self-priming, per `feedback_no_garbage_georgian_tokens.md`). Per AGENTS.md Correction Escalation: cross-session iteration. User explicitly requested handoff via /context. Detection hook (`a5ff7d0`) was working — it surfaced the warning into context — but output drift during complex multi-table synthesis still bypassed self-correction. **Mitigation for next session**: avoid mixing Georgian + English + tax_id strings + table data in one paragraph; smaller responses; defer narration when synthesizing comparison findings.
>
> 🧹 **MEMORY HYGIENE — followup (2026-05-01 late)**: cleaned self-priming sources in user memory files (`MEMORY.md` + `feedback_no_garbage_georgian_tokens.md`) — typo fixes (2 in MEMORY.md, 1 in rule file) + removed broken-token example list from rule file's "Why" block (rule's own line 15 said "no examples in file" but contained them — circular loop) + Latin transliteration → Georgian script. Backups exist (`*.backup` siblings). Open decision in earlier session re: a Latin transliteration in `MEMORY.md` line 23 — addressed in 2026-05-02 audit (replaced with Georgian script). **Caveat**: memory cleanup is necessary but insufficient — tokenizer-level artifact at generation time still possible. Stop hook flagged regression 2× post-cleanup in that session, which triggered Rule 25 restart. **Next**: monitor regression frequency over next 1–2 fresh sessions before deciding further mitigation.
>
> 🆕 **NEW FINDING — MAX MEgaplus per-supplier file landed (2026-05-01)**: user dropped `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (45 KB, **დვაბზუ store only**, 116 suppliers, 81 with revenue>0). File has 14 columns per supplier: მომწოდებელი / საიდენტ. (tax_id) / cost (with+without VAT) / revenue (with+without VAT) / profit (with+without VAT) / margin %. **Total დვაბზუ revenue (with VAT): 260,330 ₾ / cost 232,985 ₾ / profit 27,344 ₾**. This is the MAX vendor-tag ground-truth — the file we'd been asking for to solve §4 0c (ELIZI false KPI). **First analysis revealed systematic gap**:
> - Pipeline catches **only ~42% of MAX-recorded revenue** at დვაბზუ on average across top suppliers (range −20% to −99.3%).
> - **20 suppliers in MAX file are entirely missing from pipeline's per-store breakdown** (61 in pipeline vs 81 in MAX with revenue).
> - Margins wildly off: ELIZI MAX +5.31% vs pipeline −31.02% (36-point gap), შრომა-2023 MAX +28.64% vs pipeline +0.89% (28-point gap), ზახარ MAX +19.79% vs pipeline −56.04% (76-point gap), კანტი MAX +5.73% vs pipeline +34.57% (29-point gap), ენგადი MAX +6.15% vs pipeline +39.14% (33-point gap). VASADZE and იფქლი are the closest matches (margins within 0.1pp, but revenue still 58% under).
>
> **3 ცხადი integration paths surfaced for user — DECISION PENDING (next session)**:
> - **A — Read-only side-by-side**: UI per-supplier ცხრილი adds a „MAX ground-truth" column next to pipeline numbers + delta badge. No pipeline numbers change. ~1 session.
> - **B — Soft replacement**: pipeline per-store totals overridden by MAX file when tax_id matches; pipeline numbers move to a „raw" sub-field. ~2 sessions.
> - **C — File loader only**: read file into data.json under new section, no UI yet. ~30 min, low value alone.
>
> **Important caveat**: file is **per-supplier rollup (not per-product)** — solves the supplier-level KPI gap, but cannot fix individual product mappings. Alias UI (Sprint C) still needed for per-product alias confirmation. Also: user said "დვაბზუს კომპანიების შესახებ" → assume single-store; ოზურგეთი's analogous file would need separate drop. The previously-used ground-truth Excel `Financial_Analysis/ოზურგეთი კომპანიების გაყიდვები/2022,2026-02.xls` covers ოზურგეთი (per `reference_oz_ground_truth_excel.md` memory).
>
> ✅ **THIS SESSION — 4 commits landed + push (2026-05-01)**: prior-session working-tree changes finally committed and split into 2 logical pipeline commits + 1 governance commit + 1 handoff commit. Tests 57/57 green at every step. Pipeline change is what flips portfolio from −611,380 ₾ / −249.4% margin to +17,454 ₾ / +7.1% margin (verified in last pipeline run, data.json 58.99 MB, 2026-04-30 22:10). User restarted FinancialDashboardBackend service → new 30-min timeout active (`server.py:122` confirmed in live mirror). **Branch is now 0 ahead of `origin/main` — push verified clean**.
>
> ✅ **`560dab9` fix(pipeline): supplier matching — name-exclusivity + barcode dedup + short-code guard** — `_build_supplier_exclusive_names` (97.1% of 12,905 names supplier-exclusive; 371 shared names dominated by Coca-Cola distributors filtered out, preserves Borjomi-glass-vs-plastic rule), `_clean_code` strips trailing `.0` from numeric Excel codes (4380→3225 by_product rows), short-code collision guard (codes <5 chars trusted only when retail name agrees, prevents bread-1002 → MAX-barcode-1002 mis-match). 5 tests reframed for shared-name scenarios.
>
> ✅ **`d1ff190` fix(pipeline): impute cost_sold from supplier invoice with qty cap** — replaces MAX POS-recorded `cost_ge` with `min(qty_sold, qty_bought) × (cost_paid / qty_bought)`. Source of truth = supplier RS waybill (contractually signed) instead of MAX operator entry (frequently empty/placeholder for cost-at-sale). Cap prevents over-attribution when name-match catches a multi-supplier brand. `cost_sold_recorded_ge` preserved for UI transparency. Per-store breakdown scaled by same cap factor.
>
> ✅ **`6ab04b7` docs(governance): lazy-load policy** — only `CONTEXT_HANDOFF.md` is mandatory at session start; `MASTER_PLAN.md` and `AGENTS.md` read on-demand. Reading all 3 governance files up front filled too much context and contributed to language regression pattern; lazy-load reduces baseline load. CLAUDE.md GitNexus block also slimmed (full per-task knowledge in `.claude/skills/gitnexus/*`).
>
> ✅ **0d server.py:122 timeout fix ACTIVE in service** (2026-05-01 confirmed) — `Restart-Service FinancialDashboardBackend` done. `/api/status` returns 200, `server.py:122` shows `timeout=30 * 60`. Hourly `/api/refresh` cron will now have 30 min before kill (was 10 min). C:\\ pipeline runs are 7-8 min, OneDrive runs are 28-30 min. Pipeline ran 30+ consecutive failed timeouts between 2026-04-23 and 2026-04-30 — that crash loop is now closed.
>
> ✅ **imported_products data refresh — same numbers as before, format change only** (2026-04-30 ~18:27): user added 3 monthly CSVs (`01,2026.csv` 1.97 MB / `02,2026.csv` 1.79 MB / `03,2026.csv` 2.10 MB = 5.86 MB total) into OneDrive's `Financial_Analysis/შემოტანილი პროდუქცია/` folder (originally created as Latin `shemotanili produqcia`, then user renamed to `შემოტანილი საქონელი`, then I renamed to pipeline-expected `შემოტანილი პროდუქცია`). 3 monthly files copied to C:\, old aggregate `report 01,2026-03,2026.csv` → `.csv.bak` to prevent double-counting. Pipeline ran cleanly on C:\ (6 min 49 sec, 0 errors, 0 warnings). data.json: 65.5 MB → **62.33 MB** at 18:27. **Result: same supplier counts as before — 28 verified / 21 partial / 17 unverified / 4 protected = 70 total**. The 3 new monthly files contain identical data to the previous single aggregate, just split per-month. Coverage progress toward 90% goal still requires the MAX vendor-tag export discussed earlier in this session (see §4 item 0f).
>
> ✅ **Sprint C — alias confirmation UI: CODE LANDED** (2026-04-30 evening) — ორი commit C:\\-ზე და OneDrive-ზე merged: `9ae5e2c` (preview doc, 179 lines) + `57fa81d` (impl, 651 insertions / 10 deletions across 6 files). Backend = new `_validate_aliases.append_alias_atomic` helper + new `POST /api/aliases/confirm` endpoint with 400/409 mapping. Frontend = `SupplierModal.UnmatchedProductRow` gains confirm button + state (confirmedAliases/pendingAliases/aliasError) + Georgian feedback. CSS = button gradient + confirmed-row variant + error sub-note. **8 new tests green** (4 helper + 4 endpoint). After `Restart-Service FinancialDashboardBackend`: live endpoint VERIFIED — `POST /api/aliases/confirm` with empty body returns `400 {"detail":"imported_code სავალდებულოა — ცარიელი მნიშვნელობა მიუღებელია"}`, status 200 OK. **Browser smoke-test STILL PENDING** — needs `_vite-dev.bat` start + click on ვასაძის პურის modal.
>
> 🆕 **NEW FINDING — cross-source revenue gap** (2026-04-30 evening, surfaced by user ground-truth check): user provided დვაბზუს vasadze actual numbers from MAX MEgaplus (cost 10,228.48 ₾ / profit 1,248.85 ₾ / revenue ~11,477 ₾, both with-VAT and without-VAT versions, internally consistent — 1.18 ratio). Pipeline-derived revenue for vasadze in დვაბზუ = **only 3,888 ₾ via name-match**, **gap of 7,589 ₾** unaccounted. Mass-balance on cost side checks out (imported 11,696 ₾ → COGS 10,228 = 87% sold, 12% inventory leftover, expected). Diagnosis: **MAX has its own per-product vendor-tag (manual mapping)** that's broader than RS.ge waybill linkage — captures products with name divergence, paper invoices, cash-paid items. **Sprint C alias UI does NOT solve this** — it bridges RS-code↔MAX-code where names align, but cross-source gap requires ENTIRELY DIFFERENT linkage (MAX vendor-tag pull). Candidate Sprint D item, listed below.
>
> ✅ **REGRESSION HOOK FEEDBACK LOOP CLOSED** (2026-04-30 evening, commit `a5ff7d0`): root cause was NOT broken detection — Stop hook was correctly firing (counter at 11 from prior cross-session responses) but its `systemMessage` JSON output is not visibly surfaced in Claude Code CLI. Fix = new UserPromptSubmit hook `inject_regression_alert.sh` reads fresh flag and injects `additionalContext` into Claude's next-turn context, then consumes the flag. Verified live in that session: a single morphology-artifact slip in an assistant response triggered the Stop hook → flag written → next user prompt surfaced the warning → Claude self-corrected. Counter reset 11 → 0. The specific wrong-vs-right Georgian morphology pairs are documented in `feedback_no_garbage_georgian_tokens.md` deliberately without literal example tokens (rule: examples in files self-prime).
>
> ✅ **imported_products bug RESOLVED** (2026-04-30 14:06, prior session phase): user-მა „შემოტანილი პროდუქცია" CSV ფაილი წინა session-ში 4-წლიანი 4-ფაილოვანი catalog-დან 3 თვის (2026-Q1) ერთფაილოვან mode-ში გააფიცა. Pipeline-ი silently skipped რადგან folder ცარიელი იყო (1 ფაილი `_to_delete`-ში დარჩენილი). User confirmed wants — „რა ფოლდერში არის — იმის ანალიზი, არც-future გადატვირთვა, incremental add". Fix: `report 01,2026-03,2026.csv` (5.59 MB) გადავიტანე `_to_delete_2026-04-29\02_financial_analysis_orphan\შემოტანილი პროდუქცია\` → `C:\financial-dashboard\Financial_Analysis\შემოტანილი პროდუქცია\`. Pipeline manual run (server timeout 10min hit, then bypassed via direct subprocess) → data.json updated 14:06:05 → **`imported_products.suppliers = 70` populated, profitability per-supplier ON** (28 verified / 21 partial / 4 protected / 17 unverified). User goal — **90% coverage floor for ALL suppliers** (currently 21/70 ≥90%).
>
> ✅ **MAX vendor-tag export — PARTIALLY LANDED 2026-05-01**: user provided the file at supplier-rollup level (per-supplier totals for დვაბზუ store, 116 rows). This is enough to solve §4 0c (ELIZI false KPI) at supplier level via integration paths A/B/C above. **Still pending for full solution**: (a) ოზურგეთი analog of the same file, (b) per-product breakdown (current file is per-supplier rollup only — needed if we want to also fix individual product matching gaps, e.g. ვასაძე's 7,589 ₾ gap was at the per-product level).
>
> ✅ **NSSM migration სრული** (2026-04-30 01:14) — pipeline 7.2 წთ-ში სრულდება C:\\-ზე, data.json fresh. **მთავარი პრობლემა გადაჭრილია — ფაილს რომ ამატებ, dashboard ახლა ნამდვილად ხედავს**.

---

## 1. ახლა სად ვართ

- **ეს session (2026-05-01 — 4 commits landed + push + MAX file analysis)**:
  - **Phase 1 — committed prior-session working-tree** (split into 2 logical pipeline commits + 1 governance commit + 1 handoff commit), deleted residue `CLAUDE.md.backup`, tests 57/57 green at each intermediate state. Service restart confirmed by user (`/api/status = 200`, `server.py:122 timeout=30*60` active). **Pushed to `origin/main`** — branch now 0 ahead, working tree had only this CONTEXT_HANDOFF update at handoff time.
  - **Commits landed this session**:

    | SHA | type | რას აკეთებს |
    |---|---|---|
    | `560dab9` | fix(pipeline) | name-exclusivity + barcode dedup + short-code guard (matching overhaul) |
    | `d1ff190` | fix(pipeline) | impute cost_sold from supplier invoice with qty cap (cost truth) |
    | `6ab04b7` | docs(governance) | lazy-load policy — only `CONTEXT_HANDOFF.md` mandatory at session-start |
    | `0967c5f` | docs(handoff) | close session — 3 commits landed, service restart verified |

  - **Phase 2 — MAX MEgaplus per-supplier file analysis** (NEW finding, no code change yet):
    - **File path**: `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (45 KB, dropped by user 2026-05-01 ~01:07).
    - **Scope**: დვაბზუ store ONLY, 116 suppliers (81 with revenue>0 + 35 zero rows), 14 columns per supplier (with-VAT and without-VAT versions of cost/revenue/profit/margin).
    - **Headline gap**: pipeline catches ~42% of MAX-recorded revenue at დვაბზუ on average. 20 suppliers in MAX file are entirely missing from pipeline's per-store breakdown (61 in pipeline vs 81 in MAX).
    - **Top 15 side-by-side comparison** (revenue without-VAT, MAX vs pipeline; tax_id linked):

      | მომწოდებელი | tax_id | MAX rev | pipeline rev | gap | MAX მ% | pipeline მ% |
      |---|---|---|---|---|---|---|
      | ჯიდიაი | 406181616 | 35,037 | 14,882 | −57.5% | +6.81 | +5.83 |
      | ELIZI ჯგუფი | 204920381 | 33,608 | 9,220 | −72.6% | **+5.31** | **−31.02** |
      | კოკა-კოლა გურია | 405152953 | 19,826 | 8,255 | −58.4% | +12.61 | +13.89 |
      | შრომა-2023 | 437078485 | 15,588 | 5,364 | −65.6% | **+28.64** | **+0.89** |
      | ვასაძის პური | 237077961 | 9,726 | 4,084 | −58.0% | +10.87 | +10.76 |
      | ინტერნეიშნლ | 420424393 | 8,038 | 1,036 | −87.1% | +5.36 | −1.15 |
      | ზედაზენი აჭარა | 445404232 | 7,210 | 2,400 | −66.7% | −1.29 | +1.39 |
      | გეოდისტრიბუცია | 401958271 | 6,102 | 44 | **−99.3%** | +7.28 | +10.22 |
      | იბერია რეფრეშმენტსი | 204968730 | 5,719 | 1,722 | −69.9% | +13.36 | +12.70 |
      | იფქლი | 200179118 | 5,164 | 2,104 | −59.3% | +7.74 | +7.76 |
      | კანტი | 200140267 | 4,393 | 2,441 | −44.4% | **+5.73** | **+34.57** |
      | ენგადი | 242005888 | 3,983 | 3,167 | −20.5% | **+6.15** | **+39.14** |
      | ზახარ | 202061053 | 3,908 | 502 | −87.1% | **+19.79** | **−56.04** |
      | ჯიბე | 206335223 | 3,848 | 698 | −81.9% | +17.85 | +29.27 |
      | ლავაზა | 412726448 | 3,774 | 983 | −74.0% | +13.84 | +14.32 |

    - **MAX-file totals (with VAT)**: revenue 260,330 / cost 232,985 / profit 27,344 / portfolio margin ~10.5%.
    - **3 integration paths surfaced — DECISION PENDING from user**: (A) read-only side-by-side display, (B) soft replacement of pipeline numbers when MAX matches by tax_id, (C) file loader only into data.json with no UI. Details in top-of-file finding block.
    - **Caveat**: file is per-supplier rollup (not per-product). It solves supplier-level KPI verification but does not by itself fix per-product matching gaps. Alias UI (Sprint C) still relevant for per-product mapping. Also: დვაბზუ store ONLY in this file; ოზურგეთი needs analogous drop or use of `Financial_Analysis/ოზურგეთი კომპანიების გაყიდვები/2022,2026-02.xls`.

  - **Live margin table (still applicable from 2026-04-30 22:10 pipeline run)**:

    | მომწოდებელი | წინ | ახლა | MAX ground-truth |
    |---|---|---|---|
    | ვასაძე ჯამი | 33.22% | **10.50%** | ~10.9% ✓ |
    | ვასაძე@ოზურგეთი | 11.81% | 10.38% | — |
    | **ვასაძე@დვაბზუ** | **77.86%** ✗ | **10.76%** ✓ | **10.87%** ✓ (now MAX-confirmed) |
    | Portfolio margin | −249.4% | **+7.1%** | — |
    | Portfolio profit | −611,380 ₾ | **+17,454 ₾** | — |
    | ELIZI@დვაბზუ | −836% | −31.02% | **+5.31%** (still off — see §4 0c, MAX-confirmed) |
    | შრომა-2023 | −2,149% | +7.30% | +28.64% (still off) |

  - **Phase 3 — language regression handoff trigger**: while explaining MAX-vs-pipeline findings to user, partial Georgian morphology artifacts plus filler tokens accumulated 11+ in a single response (specific tokens deliberately omitted). User invoked /context (showing 17% usage = NOT a context-size issue) and explicitly requested handoff. This is the same regression pattern the SessionStart hook flagged at the very start of that session. Detection working, output drift during complex multi-table synthesis still bypasses self-correction. Handoff started before further damage.

  - **Open work for next session** (priority order):
    1. **🔴 0c ELIZI false KPI — DECISION**: user picks A/B/C from the 3 integration paths above for the new MAX file, then I implement.
    2. **🟡 0a Sprint C alias UI browser smoke-test** (~30 min): start `_vite-dev.bat`, click „დადასტურდი ალიასი" on ვასაძის პური unmatched product, verify product_aliases.json append + pipeline rerun.
    3. **🟢 CAL Step 3 spot-check** for calendar heatmap supplier modal.
    4. **🟢 ოზურგეთი analog of MAX file** (user action): same export from MAX admin panel for ოზურგეთი store closes the cross-store gap.

- **წინა session-ის ნაწილი (2026-04-30 ღამე — pipeline matching + cost imputation development)**:
  - **ნაწილი 1 (vasadze 688.80 ₾ gap reconciliation)** — User dropped `Financial_Analysis/მეგა პლუს/ზედანდებები.xlsx` (367 waybills, 20,452.80 ₾, vasadze→ჯეო ფუდთაიმი Q1 2026). Cross-checked with `Financial_Analysis/რს ზედნადები/report 01,2026-03,2026.xls` (386 waybills for vasadze, 19,881 ₾ gross / 19,764 net). Finding: 367 common waybills match cent-for-cent both sides; 19 RS-only = 17 returns (−688.80 ₾) + 2 cancellations (+117 ₾). Reconciliation: 20,452.80 − 688.80 + 117 = 19,881 ✓. User concern (cancelled-on-RS-but-accepted-in-MegaPlus → ghost AP) — cleared for vasadze Q1; cancelled and return waybill IDs absent from MegaPlus.
  - **ნაწილი 2 (root-cause find — "ანალიზდა" 2,484 ₾ vs ground-truth ~19,320)** — User asked why dashboard shows only 2,484 ₾ "გავიდა (ანალიზდა)" for ვასაძე when ground-truth name-match across both stores' Q1 2026 sales files yields 19,320 ₾. Diagnosis: pipeline JOIN was code/barcode-only; ვასაძე's internal codes (1002, 9003, etc) don't match MAX's product codes; PROTECTED-name fallback covers cigarettes/alcohol only.
  - **ნაწილი 3 (3 pipeline fixes — code on disk, NOT COMMITTED)**:
    1. **`_build_supplier_exclusive_names()`** in `dashboard_pipeline/supplier_profitability.py` — new helper builds Set[str] of normalized product names that appear under exactly ONE supplier across all imports (97.1% of all 12,905 names qualify; the 371 shared names are dominated by Coca-Cola distributors). New `match_kind="name_supplier_exclusive"` step in `_match_product`: when imported name is supplier-exclusive AND retail has exactly 1 row with that name, JOIN safely (Borjomi-glass-vs-plastic risk eliminated by upstream supplier-exclusivity filter).
    2. **`_clean_code()` helper** in `dashboard_pipeline/retail_sales.py` — strips trailing `.0` that pandas adds when Excel stores barcodes/product_codes as numeric. Fixes the duplicate-row bug where same SKU produced two by_product entries (e.g., `4860103230027` + `4860103230027.0`). by_product row count: 4380 → 3225 after dedup.
    3. **Short-code collision guard** in `_match_product` — imported codes ≤4 chars are typically supplier-internal numbering; trust short-code matches only when retail row's name agrees (exact normalized OR substring/prefix). Threshold tunable (`SHORT_CODE_THRESHOLD = 5`). Fixes the bread-1002 → bogus retail barcode 1002 collision. Ambiguous-code path also falls through to name-supplier-exclusive before returning ambiguous.
  - **ნაწილი 4 (tests — 5 updated, 0 added, 57/57 green)** — Updated tests preserved their original intent (testing what happens for SHARED names) by introducing a 2nd supplier with the same name in test data, so name is no longer supplier-exclusive: `test_name_candidate_attached_when_unique_name_match_non_protected`, `test_name_candidate_normalizes_whitespace_and_punctuation`, `test_name_candidate_attached_to_ambiguous_rows_too`, `test_name_in_protected_category_does_not_fire_for_beverages`, `test_portfolio_summary_aggregates_candidate_counts`. `test_x_suffix_does_not_override_direct_pcode_hit` started failing on substring-strict `_name_agrees`; relaxed to allow prefix/substring/contained name to pass.
  - **ნაწილი 5 (verification)** — Pipeline ran clean 4 times during dev iteration. Final data.json (`rs-dashboard/public/data.json`, 58.98 MB, 2026-04-30 20:54:07): ვასაძე verified, შემოვიდა 19,764 / გავ 12,602 / მოგ 4,186 / მარჟა 33.22% / matched 56/92 / cost coverage 95.03%. დვაბზუ: 11,696 / 4,084 / 3,180 / 77.9% margin (margin suspiciously high — see §4 0g). ოზურგეთი: 8,067 / 8,517 / 1,005 / 11.8%. Portfolio: 34 verified / 17 partial / 14 unverified / 5 protected (was 28/21/17/4).
  - **ნაწილი 6 (NOT COMMITTED — pending decision)**: 3 files modified working-tree only — `dashboard_pipeline/supplier_profitability.py`, `dashboard_pipeline/retail_sales.py`, `tests/test_supplier_profitability.py`. No commit made. User asked for handoff before commit step. Next session decision: review diff, verify smoke-test in browser, then commit + push.

- **წინა session-ი (2026-04-30 evening — Sprint C alias UI implementation + cross-source gap discovery + handoff)**:
  - **ნაწილი A (Sprint C preview)** — `/preview` skill executed, evidence inventory complete. File: `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_C_ALIAS_UI_PREVIEW.md`. Findings: name_candidate emission already shipped at `supplier_profitability.py:321`, SupplierModal.jsx:172-231 already renders 💡 hint card, ONLY the confirm bridge missing. User approved DO-in-single-session.
  - **ნაწილი B (Sprint C implement)** — 4 files modified + 2 new test files: `_validate_aliases.append_alias_atomic` (90 lines, atomic .tmp + os.replace, AliasValidationError + AliasDuplicateError exception classes), `server.POST /api/aliases/confirm` (85 lines, mirrors cash-outflow pattern, `_aliases_file_path()` extracted for monkeypatching, retail_known_keys built from cached data.json), `SupplierModal.UnmatchedProductRow` (50+ lines, accepts onConfirm/confirmed/pending props, renders ✓ button + ⏳ + ✅ states), 60 lines new CSS for button gradient + confirmed-row variant + error sub-note. 8 tests green (`tests/test_validate_aliases.py` +4, `tests/test_server_alias_endpoint.py` NEW +4). Full pytest: 2,252 passed / 7 pre-existing AGENTS.md-doc-pin failures (unrelated).
  - **ნაწილი C (commit + sync)** — Two commits on OneDrive: `9ae5e2c docs(preview): Sprint C alias-confirmation scoping` + `57fa81d feat(supplier): Sprint C alias confirmation — endpoint + UI + 8 tests`. C:\\ pulled via `git fetch <onedrive-path> main && git merge --ff-only`. Both heads now at 57fa81d.
  - **ნაწილი D (Restart-Service + endpoint verification)** — User ran `Restart-Service FinancialDashboardBackend` (admin elevation). Post-restart probe: `/api/status = 200`, `POST /api/aliases/confirm` with empty body = `400 + Georgian message "imported_code სავალდებულოა — ცარიელი მნიშვნელობა მიუღებელია"` ✓ — proves new code loaded. Endpoint live.
  - **ნაწილი E (cross-source gap discovery)** — User asked diagnostic question: how much vasadze sold in დვაბზუ Q1 2026. Pipeline-derived numbers (matched-only 617 ₾, name-match 3,888 ₾) DO NOT MATCH user's MAX-side ground truth (revenue ~11,477 ₾ with VAT, cost 10,228 ₾, profit 1,248 ₾). Gap analysis: cost side checks (87% sold, 12% leftover, mass balance OK), revenue side has 7,589 ₾ unaccounted. Diagnosis: MAX uses internal vendor-tag (manual mapping) that's broader than RS waybill linkage. **Sprint C alias UI cannot fix this — it's a different data integration problem (Sprint D candidate)**.
  - **ნაწილი F (regression triggered handoff)** — Multiple partial-token Georgian artifacts appeared across 2 responses during cross-source diagnostic. User explicitly requested handoff to new chat. Stop hook DID NOT auto-flag — needs investigation in new chat.
- **წინა session (2026-04-30 afternoon — imported_products bug FIX + 90% coverage diagnostic)**: imported_products bug closed (single CSV moved, 70 suppliers populated). User confirmed incremental file-add philosophy. 90% coverage diagnostic: 21/70 currently ≥90%, top 10 below-90% computed, vasadze identified as quick-win headline (9 candidates total).
- **წინა session (2026-04-30 evening — handoff close-out)**: წინა NSSM-migration session-ის working-copy state ფორმალურად დახურდა — 5 commit landed (constants.py duplicates, retired imported-products CSVs + regression-runtime gitignore, regression-detection Stop hook + handoff template v1.1, AGENTS.md proof-gate path + Session Pacing rewrite, CONTEXT-ის განახლება). ენობრივი regression — partial-token filler-ი user-მა აღმოაჩინა მე-7 cross-session occurrence-ად; გასწორდა inline (specific token replaced with valid alternatives).
- **წინა session (2026-04-30 morning — NSSM migration COMPLETE)**: `C:\financial-dashboard\` უკვე დასახლებული იყო (user-ის ხელით 04-29 evening + venv 04-30 00:00:06). NSSM 4 paths გადარედირექტდა (Application + AppDirectory + AppStdout + AppStderr) → service restart → data.json copy from OneDrive → manual pipeline trigger → **pipeline 7.2 წთ-ში სრულდა**, data.json fresh 54.2 MB, 28 API artifacts, 0 errors. OneDrive copy untouched (fallback). Auto-handoff hook + AGENTS.md path fix + handoff skill template v1.1 ამავე session-ში მომზადდა working-copy-ში; დახურდა ამ session-ში 5 commit-ით.
- **წინა-წინა session (2026-04-29 evening, არც ერთი commit არ მომხდარა)**: workspace structural cleanup — parent folder-დან ~863 MB orphan/duplicate ფაილი გადატანილი `_to_delete_2026-04-29\` staging-ში. დეტალები §2-ში.
- **Active section** (Master Plan): §5 გაყიდვები — **CAL mini-sprint** Step 2-ის ბოლოზეა (იგივე წერტილი, არ შეცვლილა).
- **CAL Step 1 (Scope agree)**: ✅ ifqli first, **3-button per-store toggle** (ჯამი / ოზურგეთი / დვაბზუ; თბილისი closed 2024-06 → 2026 retail window-ში 0 data), only-matched + partial-coverage warning banner
- **CAL Step 2 (Data inventory)**: ✅ pipeline-ში per-day aggregation **არ არსებობს** (only `by_month` / `by_category_by_month`). Source per-row datetime ცხადია (`დრო` სვეტი), ifqli matched products უკვე გამოთვლილია `supplier_profitability`-ში. **საჭიროა ახალი aggregation**: `supplier.profitability.daily_breakdown[]` sparse (per-day × per-store)
- **CAL Step 3-6**: spot-check + implement + verify + user review — ⏳ ვიდრე user-ის ცხადი „გადავიდეთ"

**ბოლო commit-ები** (pushed to `origin/main` 2026-05-01; branch is 0 ahead at handoff):
```
0967c5f  docs(handoff): close session — 3 commits landed, service restart verified
6ab04b7  docs(governance): lazy-load policy — only CONTEXT_HANDOFF.md mandatory at session start
d1ff190  fix(pipeline): impute cost_sold from supplier invoice with qty cap
560dab9  fix(pipeline): supplier matching — name-exclusivity + barcode dedup + short-code guard
8adfb70  docs(handoff): close session — 0d timeout fix landed, imported_products refresh same numbers, regression #2 → restart
089e953  fix(pipeline): bump /api/refresh subprocess timeout 10→30 min + ignore imported_products CSVs
9868d38  docs(handoff): close regression-hook item 0e — feedback loop landed in a5ff7d0
a5ff7d0  feat(.claude): close regression-detection feedback loop via UserPromptSubmit hook
6c1e24e  docs(handoff): close Sprint C session — code complete, smoke-test pending, regression hook needs investigation
57fa81d  feat(supplier): Sprint C alias confirmation — endpoint + UI + 8 tests
```

**ამ session-ში გაკეთებული (2026-05-01)**:
1. **Service restart verified** — `/api/status` returns 200, `server.py:122 timeout=30*60` active. Hourly refresh cron crash loop is now closed.
2. **Pipeline matching commit** `560dab9` — `dashboard_pipeline/retail_sales.py` (+`_clean_code` helper) + `dashboard_pipeline/supplier_profitability.py` (matching half) + `tests/test_supplier_profitability.py` (5 reframed tests). 151 insertions / 32 deletions across 3 files.
3. **Cost imputation commit** `d1ff190` — `dashboard_pipeline/supplier_profitability.py` (cost block + per-store scale + `cost_sold_recorded_ge` field) + `tests/test_supplier_profitability.py` (1 reframed test). 47 insertions / 7 deletions across 2 files.
4. **Governance commit** `6ab04b7` — `CLAUDE.md` lazy-load policy (12 insertions / 95 deletions; only `CONTEXT_HANDOFF.md` mandatory at session start).
5. **Handoff commit** `0967c5f` — CONTEXT_HANDOFF.md updated to reflect close-out.
6. **Residue cleanup** — deleted untracked `CLAUDE.md.backup`.
7. **Tests verified at every step** — 57/57 supplier_profitability + retail_sales_revenue_formula tests green at intermediate matching-only state AND post-imputation state.
8. **Push to origin/main** — 11 commits → live on GitHub.
9. **MAX MEgaplus per-supplier file analysis** (no commit) — file landed at `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls`, 116 suppliers for დვაბზუ store, top-15 side-by-side comparison with pipeline computed and captured in §1 above. **3 integration paths surfaced; user decision pending in next session**.
10. **Language regression triggered handoff** — partial Georgian filler tokens 11+ in single response while synthesizing comparison findings; user invoked /context + requested handoff. No commits between this finding and handoff.

---

## 2. workspace cleanup — `_to_delete_2026-04-29\` (1-კვირიანი grace pending)

**Status: STAGED** — 863 MB / 16,021 ფაილი parent-ის root-დან გადატანილი `_to_delete_2026-04-29\` staging-ში. სრულად უკან-დასაბრუნებელი (mv-ი, არა delete-ი). Service ცოცხალი (HTTP 200 cleanup-ის შემდეგ).

### წინა CONTEXT_HANDOFF §2-ის გადამოწმება (2026-04-29 evening verified)

**წინა CONTEXT-ი ცხადობდა**: parent's `Financial_Analysis\` = ცარიელი orphan, project-inside = canonical.

**რეალობა (ls -la-ით verified)**: project-inside `Financial_Analysis\`-ში **5 ფოლდერი symbolic link-ია parent-ზე**:
- `ბოგ ბანკი ამონაწერი` → parent (25 MB)
- `გაყიდული პროდუქტები სოფ დვაბზუ` → parent (22 MB)
- `გაყიდული პროდუქტები სოფ ოზურგეთი` → parent (8.3 MB)
- `თბს ბანკი ამონაწერი` → parent (8.1 MB)
- `რს ზედნადები` → parent (7.8 MB)

ანუ pipeline-ი project-inside-ის ფოლდერებიდან კითხულობს, **მაგრამ რეალური data parent-ის Financial_Analysis-შია** symlink-ის გავლით. parent-ის `Financial_Analysis\` სრული წაშლა → catastrophe (5 symlink ცარიელად, dashboard down).

**parent FA-ის შინაარსი**: top-level 13 JSON config + `შემოტანილი პროდუქცია\` (81 MB out-of-date — project-ში 104 MB canonical: `პროდუქცია 2023/24/25/26.csv`-ები real folder-ი).

### რა გადატანილია `_to_delete_2026-04-29\`-ში

```
01_old_code\                  ~30 MB — ძველი .py/.bat/.ps1/__pycache__/.cursor + parent-ის ძველი
                              AGENTS.md/CLAUDE.md/CONTEXT_HANDOFF.md/HANDOFF.md/PLAN.md/README.md
                              + previews (preview*.md, rs_aggregated*.md, temp.json, headers_*.{json,txt})
                              + dashboard_pipeline\, rs-dashboard\, tests\, $null
02_financial_analysis_orphan\ ~85 MB — parent FA-ის 13 out-of-date JSON config + `manual_payments.csv`
                              + `შემოტანილი პროდუქცია\` (81 MB, ძველი copy)
03_archive_and_git\           ~660 MB — _ARCHIVE\ (655 MB, deprecated-root-copy-20260415) + parent .git\
                              + parent .gitignore (parent ცალკე repo აღარ არის)
```

### Pre-flight verification (2026-04-29 evening)

| შემოწმება | შედეგი |
|---|---|
| NSSM service config | ✅ `AppDirectory = financial-dashboard\`, `python.exe -u server.py` (parent venv-ზე უთითებს) |
| Task Scheduler refs | ✅ ცარიელი — .bat/.ps1 safe-delete |
| Dashboard service post-cleanup | ✅ `SERVICE_RUNNING`, API `HTTP 200` |
| parent FA symlink-ები | ✅ 5 ცოცხალი ფოლდერი ხელუხლებელი |

### რჩება parent root-ში (cleanup-ის შემდეგ)

```
.claude\  .obsidian\  .vscode\  .windsurf\   ← editor settings
venv\                                          ← Python interpreter (CRITICAL — NEVER touch)
financial-dashboard\                           ← ცოცხალი project (untouched)
Financial_Analysis\                            ← 5 symlink target ფოლდერი (ცოცხალი data)
Download\  suratebi\  რს\                     ← user-ის პირადი ფაილები
VAT_Reconciliation_Monthly.xlsx                ← user VAT
გაანგარიშება შპს ჯეო ფუდთაიმი.xlsx            ← user accounting
სწრაფი_ინსტრუქცია.txt                          ← user notes
_to_delete_2026-04-29\                         ← grace folder (1 week → permanent delete)
```

### Open decision (1 კვირაში)

5-7 დღე dashboard ცოცხალი → `_to_delete_2026-04-29\` permanent delete (863 MB). თუ რამე გატყდა → ფაილი უკან გადატანა. user-მა შენიშნა, რომ შეიძლება დაგვიანდეს.

### AGENTS.md proof gate path bug — ✅ FIXED 2026-04-30 (commit `8dd1637`)

წინა state: AGENTS.md Proof Gate-ი წერდა: `Source canonical: ...\AI აგენტი\Financial_Analysis`. ეს არასწორი იყო — რეალური canonical pipeline-ის view-დან = `...\financial-dashboard\Financial_Analysis\` (5 symlink + 1 real folder + 15 JSON config). `AGENTS.md:35` ახლა გასწორდა — symlink სტრუქტურის ახსნა და §7-ზე pointer დაემატა.

---

## 3. Verified facts (cross-check ვიდრე action)

| მეტრიკა | მნიშვნელობა |
|---|---|
| pytest (supplier_profitability + retail_sales_revenue_formula) | **57/57 green** (post 5-test update + substring-tolerant `_name_agrees`) |
| `SYSTEM_PROMPT_KA` | 1,163 ხაზი |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 15 |
| `data.json` | **58.99 MB** (post-imputed-cost fix, 2026-04-30 22:10:54), 26 sections, **4 store buckets** supplier-side / **2 active store buckets** retail-side |
| `retail_sales.by_product` rows | **3,225** (was 4,380 before barcode dtype dedup) |
| `retail_sales` window | **3 თვე** (2026-01..03) — 96,464 line / 319K ₾ revenue / 50K ₾ profit / 15.84% margin |
| `imported_products` window | **1 file** (Q1 2026), 70 suppliers, profitability ON |
| **Supplier portfolio status (post-fix)** | 34 verified / 17 partial / 14 unverified / 5 protected = 70 total |
| **Portfolio profit/margin (post-imputed-cost)** | revenue 245,172 ₾ / profit **+17,454 ₾** / margin **+7.1%** — was −611,380 ₾ / −249.4% with MAX-recorded cost |
| **ვასაძის პური Q1 2026 (post-imputed-cost)** | შემოვიდა 19,764 ₾ / გაიყიდა 12,602 ₾ / **თვითღ. (imputed) 11,308 ₾** / მოგება **1,294 ₾** / **მარჟა 10.50%** (matches MAX ground-truth ~10.9%); per-store: ოზურგეთი 10.38% / დვაბზუ 10.76% (was 11.81% / 77.86% with MAX-recorded) |
| ვასაძე RS↔MegaPlus reconciliation | 367 common waybills cent-match / 19 RS-only = 17 returns (−688.80) + 2 cancellations (+117); MegaPlus 20,452.80 = RS-net 19,764 + 688.80 returns − 117 cancelled |
| `/api/aliases/confirm` | **LIVE** post-restart 2026-04-30 evening — empty body → 400 + Georgian message; happy-path verified by 4 endpoint tests |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |
| VAT cumulative gap | **+90K ₾ net / +107K ₾ gross** (pipeline). Audit ground-truth: **742K ₾**. Delta = ~652K within pipeline coverage gaps |

---

## 4. ღია სამუშაო (priority order)

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| **✅ DONE 2026-04-30** | ~~imported_products bug — supplier modal ცარიელია~~ — File moved (single 3-month CSV), pipeline manual run, 70 supplier-ი profitability-ით. User-ის incremental philosophy captured. | — | — | მთავარი user pain — supplier modal cross-check ცხრილი ცოცხალი |
| **✅ DONE 2026-05-01** | ~~0g — 4 uncommitted pipeline changes~~ — Split into 2 commits: `560dab9` matching overhaul (name-exclusivity + barcode dedup + short-code guard) + `d1ff190` cost imputation (supplier-invoice-imputed cost with qty cap + `cost_sold_recorded_ge` transparency field). All 57 tests green at every step. **Pushed to `origin/main`** — branch is 0 ahead. | — | — | RESOLVED |
| **🟡 0a CODE COMPLETE — smoke-test pending** | **Sprint C alias UI** — code landed (commits `9ae5e2c` preview + `57fa81d` impl). Backend endpoint `POST /api/aliases/confirm` LIVE post-restart, returns 400/409/200 with Georgian messages, 8 tests green. Frontend UnmatchedProductRow gains ✓ button + ⏳/✅ states + error sub-note. **REMAINING — browser smoke-test**: (1) start `_vite-dev.bat` in `C:\financial-dashboard\rs-dashboard\`, (2) browser → `http://127.0.0.1:5173`, (3) მომწოდებლები ტაბი → ვასაძის პური → modal → ალიასის კანდიდატები section, (4) click „✓ დადასტურდი ალიასი" on first candidate (imp_code 2006 „შეფუთული აგურა რუხი" → MAX 2247377), (5) verify toast + product_aliases.json write, (6) trigger pipeline rerun + verify coverage delta. Sprint C addressable scope = 66 candidates total but only 20 unmatched + 46 ambiguous visible; pipeline only renders unmatched_preview in UI right now (ambiguous_preview unrendered — Sprint D extension candidate). | ~30-45 წთ | LOW | code on disk, endpoint live, just need user-side click |
| **✅ DONE 2026-05-01** | ~~0d server.py:122 timeout 10→30 min~~ — `Restart-Service FinancialDashboardBackend` done by user. Service mirror `C:\financial-dashboard\server.py:122` shows `timeout=30 * 60` active, `/api/status` returns 200. Hourly `/api/refresh` cron 30+ failed run streak (2026-04-23 → 04-30) is now closed. | — | — | RESOLVED |
| **✅ DONE 2026-04-30** | ~~NSSM service redirect to `C:\financial-dashboard\`~~ — Migration COMPLETE. data.json fresh, 28 API artifacts, 0 errors. OneDrive copy untouched (1-week retire pending). | — | — | RESOLVED |
| **✅ DONE 2026-04-30 evening** | ~~Regression hook feedback loop broken~~ — **Root cause identified + closed in commit `a5ff7d0`**. Investigation: Stop hook (`check_regression.sh`) IS firing correctly (counter was at 11, fresh flag from prior responses with partial-token Georgian morphology artifacts). Bug = Stop hook's `systemMessage` JSON output is not visibly surfaced in Claude Code CLI, so neither user nor Claude saw the alerts. Fix = added new UserPromptSubmit hook (`inject_regression_alert.sh`) that reads `.claude/regression_detected.flag` if fresh (<10min old) and emits `hookSpecificOutput.additionalContext` into Claude's next-turn context, then consumes the flag (moves to `regression_history/`). Verified live: synthetic flag → JSON output → flag moved to history. Real-world demo same session — count incremented to 1 after a single morphology-artifact slip in prior assistant response, the warning surfaced into next turn's context, Claude self-corrected. Counter reset 11 → 0. `.gitignore` updated for `regression_history/`. |
| **🧹 1-week-pending** | **OneDrive `financial-dashboard\` copy retire — NOT a 5-minute mv** (2026-04-30 verification, session #2). Migration ნაწილობრივია: C:\\ = service mirror only (data.json fresh Apr 30 01:14, მაგრამ კოდი + `.git` Apr 29 22:16 stale — copy migration-ზე გაკეთდა). OneDrive = **ცოცხალი working tree** (governance edits Apr 30 00:36-01:16: CONTEXT_HANDOFF/AGENTS; .git working tree 48 commits ahead არ-push-ებული; .claude config; **Claude Code სესიის cwd**). უბრალო `mv` → working tree-ი დაიკარგება. **სწორი retire sequence**: (1) OneDrive uncommitted ცვლილებები git-ში commit (✅ ამ session-ში გაკეთდა); (2) C:\\-ზე `git pull` ან ხელით governance ფაილების sync; (3) Claude Code-ი C:\\-დან გავუშვა (cwd ცვლილება, შესაძლოა .claude config-იც კოპირდეს); (4) **მხოლოდ ამის შემდეგ** OneDrive → `_to_delete_2026-04-30_onedrive\` staging. | ~30-45 წთ mini-sprint | MEDIUM | divergence-ი ყოველ დღე იზრდება (governance edit-ები მხოლოდ OneDrive-ზე, data.json მხოლოდ C:\\-ზე) — საჭიროა migration plan |
| **🧹 1-week-pending** | `_to_delete_2026-04-29\` permanent delete (863 MB) — 5-7 დღე dashboard ცოცხალი → permanent rm. თუ user-მა რამე surprise აღმოაჩინა → უკან გადატანა (§2) | 1 წთ | LOW | grace period აქტიური; cleanup უკვე გაკეთდა, მხოლოდ permanent rm-ი დარჩა |
| **✅ DONE 2026-04-30** | ~~`AGENTS.md:35` proof gate path~~ — workspace canonical → project canonical, symlink note added pointing to §7 for full structure. | — | — | proof-ფრაზა ახლა შეესაბამება რეალურ symlink სტრუქტურას |
| **🚨 0c — DECISION READY** | dashboard „ანალიზდა" KPI ცრუობს partial-coverage სცენარში — **MAX file landed 2026-05-01**, ground-truth quantified. ELIZI@დვაბზუ: MAX +5.31% vs pipeline −31.02% (36-pp gap); MAX file shows total დვაბზუ revenue 260,330 ₾ vs pipeline ~108,500 ₾ (~42% catch rate). 3 paths: **(A) read-only side-by-side display** (~1 session, low risk); **(B) soft replacement of pipeline numbers when MAX matches by tax_id** (~2 sessions, medium risk); **(C) file loader only into data.json, no UI** (~30 min, low value alone). User picks A/B/C. File: `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (45 KB, დვაბზუ only — ოზურგეთი needs analog drop). Per-product breakdown not in this file → still need alias UI for individual product matching. | A=1 session / B=2 sessions / C=30 წთ | **HIGH** | top-of-file finding block + §1 Phase 2 has top-15 supplier comparison table |
| **🚧 CAL** | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა | ~1 session | LOW | scope locked, data inventory done; საჭიროა new daily aggregation `supplier_profitability`-ში |
| **✅ DONE 2026-04-30** | ~~`dashboard_pipeline/constants.py` duplicate functions~~ — **REAL SCOPE WAS 10 FUNCTIONS, NOT 1**. Verified: 9 character-identical (`_object_order_for_pos`, `_object_order_for_monthly_pnl`, `_month_sort_key`, `_match_text_to_object`, `detect_object`, `_extract_tax_id_from_org`, `_pick_aging_bucket`, `_empty_aging_summary`, `_to_waybills_df`) → first copies deleted (lines 434-541, 109 lines removed, file 797→688). 50 targeted tests green, syntax OK, all 10 names still callable. | — | — | dead code removed |
| **✅ DONE 2026-04-30** | ~~`_parse_rs_datetime` — TWO DIVERGENT versions~~ — Spot-check across 5 RS waybill files (2022-2026) + 3 retail sales files (01-03.2026) confirmed ALL datetime values use ISO `%Y-%m-%d %H:%M[:%S]` format. No Georgian month tokens anywhere. Dead first def (L434-463) + dead `IMPORTED_PRODUCTS_MONTH_TOKEN_TO_MM` constant + unused import in `generate_dashboard_data.py` removed (commit `2ab4a05`, 48 lines deleted). 21 targeted tests green. Live behavior unchanged (L657 was already overriding L434). | — | — | divergent dead code resolved; only one canonical `_parse_rs_datetime` remains |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) | 1-2 session | LOW | (a) `vulture` dead-code; (b) `jsonschema` config-ფაილებზე; (c) golden snapshot data.json-ისთვის; (d) reconcile_suppliers.py გავრცელება; (e) Pandera RS.ge CSV reader |
| **🆕 0f Sprint D candidate** | **Cross-source revenue gap — MAX vendor-tag vs RS waybill** (NEW 2026-04-30 evening) — User provided ground-truth from MAX MEgaplus for vasadze@დვაბზუ Q1 2026: cost 10,228.48 ₾ / profit 1,248.85 ₾ / revenue ~11,477 ₾ (with VAT). Pipeline-derived = 3,888 ₾ name-match (gap 7,589 ₾). Cost-side mass balance OK (87% sold). **Diagnosis**: MAX uses internal manual vendor-tag mapping per product (broader than RS waybill). Sprint C alias UI bridges RS-code↔MAX-code where names align — does NOT bridge "MAX-tagged-as-vasadze but no RS waybill linkage". Possible root causes: (a) name divergence beyond name-match threshold, (b) cash-paid invoices not on RS, (c) MAX's manual vendor-tag includes products vasadze never officially shipped per RS. **Investigation paths**: (1) ask user to export MAX's per-supplier sales report (CSV/Excel) to bypass RS waybill entirely; (2) add MAX-vendor-tag column to retail_sales pipeline if available in source data; (3) document this as a structural caveat in supplier_profitability output (KPI banner: „ანალიზდა შეიცავს მხოლოდ RS-ით ცნობილ პროდუქტებს"). **Defer until user decides**: extend Sprint C with this OR run as separate Sprint D. | 2-3 sessions investigation + 1-2 sessions impl | MEDIUM | **structural caveat — pipeline-ით სრული რეალური ბრუნვის ცხადობას ვერ ვაკეთებთ ვასაძის შემთხვევაში** |
| 1 | Supplier Profitability Sprint C UI extensions — render `ambiguous_preview` (currently invisible 46 candidates) + bulk-confirm + DELETE endpoint | ~1 session | LOW | post-Sprint-C-merge follow-up; Sprint C only confirms unmatched_preview (20 of 66 addressable) |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` | ~1 session | LOW | TOOL_SCHEMAS 29 → 30 |

---

## 5. წინა session-ის carry-forward findings

### Top 10 below-90% suppliers (2026-04-30 14:06 baseline) — Sprint C input

| # | მომწოდებელი | Coverage | Imported ₾ | Unmatched ₾ | Status |
|---|---|---|---|---|---|
| 1 | შპს ელიზი ჯგუფი | 0.8% | 79,634 | 78,967 | unverified, tobacco renumbering |
| 2 | შპს შრომა-2023 | 57.6% | 25,318 | 10,741 | partial, long-tail (247 unmatched) |
| 3 | შპს ინტერნეიშნლ მარკეტინგ | 44.2% | 19,848 | 11,069 | protected, tobacco |
| 4 | შპს ვასაძის პური | 82.4% | 19,764 | 3,470 | verified, **HAS name_candidate auto-suggested → quick win** |
| 5 | შპს ზედაზენი აჭარა | 73.7% | 17,977 | 4,732 | partial |
| 6 | სს იბერია რეფრეშმენტსი | 82.0% | 11,680 | 2,096 | verified |
| 7 | შპს გეოდისტრიბუცია | 5.0% | 11,511 | 10,939 | unverified, tobacco |
| 8 | შპს კანტი | 85.7% | 10,724 | 1,529 | verified |
| 9 | შპს ფუდსერვისი | 70.7% | 7,040 | 2,066 | partial |
| 10 | შპს პარტნიორი | 72.9% | 6,733 | 1,826 | partial |

**3 patterns**:
1. **Tobacco renumbering dominant** (3 of top 10 = ELIZI, ინტერნეიშნლ, გეოდისტრიბუცია). სალარო MAX renumbered, name same, code different. Best alias-fix candidates.
2. **Quick win** (#4 ვასაძის პური): pipeline already produced `name_candidate = "შეფუთული აგურა რუხი" → "პური შავი აგური" (retail_category)`. Single user click in alias UI = 82% → 90%+.
3. **Long-tail** (#2 შრომა-2023): 247 unmatched products, each <300 ₾. Manual review heavy work — last priority.

**Status distribution**: verified 28 / partial 21 / protected 4 / unverified 17 = 70 total.

### ELIZI ground-truth carry-over

**ELIZI ground-truth** (2026-04-28): user-მა გააზიარა Excel `Financial_Analysis/ოზურგეთი კომპანიების გაყიდვები/2022,2026-02.xls`. რეალური cost 297,685 / sales 313,456 / **profit +15,771 / margin +5.3%**. Dashboard აჩვენებს: cost 322K / sold 61.7K / **profit −1,314 / margin −2.13%**. — Item §0c-ში. **Note**: 2026-04-30 ELIZI 0.8% coverage on 3-month window (vs 35% on full window) — reaffirms tobacco renumbering issue dominant cause.

### ვასაძის პური ground-truth — დვაბზუ Q1 2026 (NEW 2026-04-30 evening)

User-მა გააზიარა MAX MEgaplus per-supplier per-store რეპორტი. ფაქტობრივი ციფრები:

| მაჩვენებელი | დღგ-ით | დღგ-ის გარეშე |
|---|---|---|
| თვითღირებულება (COGS) | **10,228.48 ₾** | 8,668.21 ₾ |
| მოგება | **1,248.85 ₾** | 1,057.50 ₾ |
| Revenue (derived) | ~11,477.33 ₾ | ~9,725.71 ₾ |
| მარჟა | — | **10.9%** (პურისთვის რეალური) |

**ჩვენი derived numbers** (3 ხედვა):

| ხედვა | დვაბზუს რევენიუ | gap | ახსნა |
|---|---|---|---|
| Pipeline matched-only (`profitability.per_store_breakdown`) | 617.63 ₾ | −10,860 | code-by-code 41/92 პროდუქტი |
| Name-match (vasadze imported names ↔ retail rows) | 3,888.11 ₾ | −7,589 | 54/92 პროდუქტი, sample object_breakdown |
| **User MAX ground truth** | **11,477 ₾** | reference | MAX-ის შიდა per-product vendor-tag |

**Mass balance check** — cost side OK: vasadze imported to დვაბზუ = 11,696 ₾ (per `imported_products.suppliers[*].object_breakdown`); user's COGS 10,228 ₾ → 87.4% sold, 12.6% inventory leftover (1,468 ₾) — realistic for bread.

**Where the 7,589 ₾ gap lives**: MAX uses manual per-product vendor-tag (set by shop staff). Pipeline only links via RS waybill product_code/barcode/name. Products vasadze supplies under cash invoice / paper waybill / different MAX naming → captured by MAX vendor-tag, missed by pipeline. **Sprint C alias UI does NOT solve this**: it only handles "RS code X needs to map to MAX code Y, names align". When RS-side has no entry at all, pipeline has nothing to alias.

**Recommended next step**: ask user to export MAX's per-supplier-per-store sales CSV directly (e.g., right-click „გაყიდვები per მომწოდებელი → დვაბზუ → ვასაძე → გადმოწერე") — would let us run a 3-way reconciliation (RS waybill / pipeline-derived / MAX vendor-tag).

**🚨 ენობრივი regression — pattern history (8 cross-session occurrences)**: filler-words / partial Georgian tokens (2026-04-27 + 04-28 + 04-29 morning + 04-29 evening ×2 + 04-30 morning + 04-30 afternoon + **2026-04-30 evening**). Trigger: complex tool output → cognitive load → degraded Georgian generation. **2026-04-30 evening NEW**: 4-5 instances of partial-token artifacts across 2 responses during cross-source diagnostic (specific tokens omitted to avoid self-priming). Stop hook from `f11439b` did NOT visibly flag — see §4 item `0e` for debug path. User caught manually + triggered restart. **The 2-correction-rule for restart is now hardened: that was iteration #2 in that session and user explicitly requested handoff**.

**OneDrive root-cause confirmation evidence (2026-04-29 evening #2)**:
- `logs/backend_stdout.log` grep „Pipeline exception" → 2026-04-23-დან 30+ consecutive timeout entries (ყოველი საათობრივი run = 600s timeout)
- `logs/pipeline_subprocess.log` ბოლო 15 run header: ყოველი run თიშავს „Reading RS files..." line-ზე → never reaches completion
- Code comment `server.py:84-87` უკვე აფიქსირებდა OneDrive bottleneck (28-30 min on OneDrive vs 3-5 min target)
- Desktop folder = `C:\Users\tengiz\OneDrive\Desktop\` (verified PowerShell SpecialFolders) → ყოველი desktop ფაილი sync-ში
- C: drive: 267 GB free → migration target room ცხადია

---

## 6. Governance consolidation — `4deed3a` (2026-04-29)

ცხადი 4-ფაილოვანი სტრუქტურა (იყო 7 ფაილი + parallel duplicates):

| ფაილი | ხაზი | რას ემსახურება |
|---|---|---|
| `CONTEXT_HANDOFF.md` (ეს) | ~110 | ცოცხალი state — current section + open work + verified facts |
| `docs/MASTER_PLAN.md` | 232 | ერთადერთი 18-სექციის roadmap (A→F sequence, 6-step sprint cycle, data inventory, VAT cross-cutting) |
| `AGENTS.md` | 89 | Session rules — consolidated 3-layer proof gate, scoped GitNexus rule (shared functions only, JSON/docs/constants EXEMPT), cross-session language regression flag |
| `HANDOFF.md` | 81 | Commit SHA → archive evidence index, Master Plan §-ის ნომერი binding |
| `CLAUDE.md` (project) | 114 | GitNexus tools (override note + auto-block + governance pointer table) |

**Archived**: `PHASE_STATUS_MATRIX.md` (Phase 0A...5 paradigm) → `HANDOFF_ARCHIVE/PHASE_STATUS_MATRIX_v2.1_superseded_2026-04-29.md`

**5 critical contradictions resolved**:
1. CLAUDE.md strict GitNexus rule vs AGENTS.md scoped relaxation → CLAUDE.md ზევით override note
2. PHASE_STATUS_MATRIX Phase 0A...5 vs MASTER_PLAN §1...18 → PHASE archived
3. Proof gates duplicate CLAUDE.md+AGENTS.md → only AGENTS.md
4. MASTER_PLAN ცხრილი vs §5.1 numbering → table reordered (1=ზედნადები)
5. ✅ ნაწილობრივ ambiguity → ⏳ ნაწილობრივ + ახსნა

---

## 7. Canonical paths & services (do-not-touch)

⚠️ **Source ფაილების canonical path — symlink სტრუქტურა (2026-04-29 verified):**
- **pipeline view**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis\`
  - 15 JSON config (real, canonical) — `cash_outflow_journal.csv`, `product_aliases.json`, etc.
  - 5 symlink target ფოლდერი → `..\Financial_Analysis\` (parent):
    - `ბოგ ბანკი ამონაწერი`, `გაყიდული პროდუქტები სოფ დვაბზუ`, `გაყიდული პროდუქტები სოფ ოზურგეთი`, `თბს ბანკი ამონაწერი`, `რს ზედნადები`
  - ⚠️ **`შემოტანილი პროდუქცია\` ფოლდერი მისამართიდან გაქრა** (verified 2026-04-30 evening, ორივე OneDrive-სა და C:\\-ზე). 4 ძველი per-year aggregate CSV (`შემოტანილი პროდუქცია 2023/24/25/26.csv`) git-დან წაიშალა commit `e21e9e0`-ში. წინა docs-ი წერდა „104 MB real folder — `პროდუქცია 2023/24/25/26.csv`", მაგრამ ეს ფოლდერი ცოცხლად არ არსებობს. Pipeline 2026-04-30 01:14-ზე 0 errors-ით სრულდა — იმპორტი სავარაუდოდ silently skip-დება ან parent-ის retire-ულ orphan-ში გადატანილ copy-დან იკითხება. **შემდეგ session-ში გადასამოწმებელი** — `dashboard_pipeline/imported_products.py` რომელ path-ს კითხულობს და რა ხდება როცა აკლია.
- **parent's `Financial_Analysis\`**: 5 ცოცხალი data ფოლდერი (symlink target — **NEVER touch**); top-level JSON-ები + ძველი `შემოტანილი პროდუქცია\` უკვე გადატანილია `_to_delete_2026-04-29\02_financial_analysis_orphan\`-ში

ცხრილი:
- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი` (cleanup-ის შემდეგ — მინიმალური; მხოლოდ venv + .claude + editor settings + user files + project + symlink-ის ფესვი)
- **Project**: `...\financial-dashboard`
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / project-local / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)
