# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-04-30 evening (Sprint C alias UI **CODE COMPLETE & ENDPOINT LIVE**, browser smoke-test ჯერ არ ჩატარებულა; user-მა restart მოითხოვა language regression-ის გამო). გრძელი წაკითხვა საჭირო **არ არის**. ეს ფაილი ცოცხალი state-ია. Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. Evidence → `HANDOFF.md` + `HANDOFF_ARCHIVE/`.
>
> ✅ **Sprint C — alias confirmation UI: CODE LANDED** (2026-04-30 evening) — ორი commit C:\\-ზე და OneDrive-ზე merged: `9ae5e2c` (preview doc, 179 lines) + `57fa81d` (impl, 651 insertions / 10 deletions across 6 files). Backend = new `_validate_aliases.append_alias_atomic` helper + new `POST /api/aliases/confirm` endpoint with 400/409 mapping. Frontend = `SupplierModal.UnmatchedProductRow` gains confirm button + state (confirmedAliases/pendingAliases/aliasError) + Georgian feedback. CSS = button gradient + confirmed-row variant + error sub-note. **8 new tests green** (4 helper + 4 endpoint). After `Restart-Service FinancialDashboardBackend`: live endpoint VERIFIED — `POST /api/aliases/confirm` with empty body returns `400 {"detail":"imported_code სავალდებულოა — ცარიელი მნიშვნელობა მიუღებელია"}`, status 200 OK. **Browser smoke-test STILL PENDING** — needs `_vite-dev.bat` start + click on ვასაძის პურის modal.
>
> 🆕 **NEW FINDING — cross-source revenue gap** (2026-04-30 evening, surfaced by user ground-truth check): user provided დვაბზუს vasadze actual numbers from MAX MEgaplus (cost 10,228.48 ₾ / profit 1,248.85 ₾ / revenue ~11,477 ₾, both with-VAT and without-VAT versions, internally consistent — 1.18 ratio). Pipeline-derived revenue for vasadze in დვაბზუ = **only 3,888 ₾ via name-match**, **gap of 7,589 ₾** unaccounted. Mass-balance on cost side checks out (imported 11,696 ₾ → COGS 10,228 = 87% sold, 12% inventory leftover, expected). Diagnosis: **MAX has its own per-product vendor-tag (manual mapping)** that's broader than RS.ge waybill linkage — captures products with name divergence, paper invoices, cash-paid items. **Sprint C alias UI does NOT solve this** — it bridges RS-code↔MAX-code where names align, but cross-source gap requires ENTIRELY DIFFERENT linkage (MAX vendor-tag pull). Candidate Sprint D item, listed below.
>
> ✅ **REGRESSION HOOK FEEDBACK LOOP CLOSED** (2026-04-30 evening, commit `a5ff7d0`): root cause was NOT broken detection — Stop hook was correctly firing (counter at 11 from prior cross-session responses) but its `systemMessage` JSON output is not visibly surfaced in Claude Code CLI. Fix = new UserPromptSubmit hook `inject_regression_alert.sh` reads fresh flag and injects `additionalContext` into Claude's next-turn context, then consumes the flag. Verified live in this session: a single ცადობდი slip in an assistant response triggered the Stop hook → flag written → next user prompt surfaced the warning → Claude self-corrected. Counter reset 11 → 0. **Clarification on the regression itself**: the wrong forms are „ცადობს / ცადობდი / ცადობდა" (NOT real Georgian morphology) — correct forms use stem `ცდილ-` → ცდილობს / ცდილობდი / ცდილობდა, or noun ცდა / მცდელობა.
>
> ✅ **imported_products bug RESOLVED** (2026-04-30 14:06, prior session phase): user-მა „შემოტანილი პროდუქცია" CSV ფაილი წინა session-ში 4-წლიანი 4-ფაილოვანი catalog-დან 3 თვის (2026-Q1) ერთფაილოვან mode-ში გააფიცა. Pipeline-ი silently skipped რადგან folder ცარიელი იყო (1 ფაილი `_to_delete`-ში დარჩენილი). User confirmed wants — „რა ფოლდერში არის — იმის ანალიზი, არც-future გადატვირთვა, incremental add". Fix: `report 01,2026-03,2026.csv` (5.59 MB) გადავიტანე `_to_delete_2026-04-29\02_financial_analysis_orphan\შემოტანილი პროდუქცია\` → `C:\financial-dashboard\Financial_Analysis\შემოტანილი პროდუქცია\`. Pipeline manual run (server timeout 10min hit, then bypassed via direct subprocess) → data.json updated 14:06:05 → **`imported_products.suppliers = 70` populated, profitability per-supplier ON** (28 verified / 21 partial / 4 protected / 17 unverified). User goal — **90% coverage floor for ALL suppliers** (currently 21/70 ≥90%).
>
> 🚨 **CRITICAL — server pipeline timeout = 10min hardcoded** (`server.py:116`) → §4 entry. Original `/api/refresh` failed at exact 10min before supplier_profitability step. Direct subprocess bypass took ~8min total. Fix: bump to 30min (`30 * 60`) — small `git diff`, requires service restart.
>
> ✅ **NSSM migration სრული** (2026-04-30 01:14) — pipeline 7.2 წთ-ში სრულდება C:\\-ზე, data.json fresh. **მთავარი პრობლემა გადაჭრილია — ფაილს რომ ამატებ, dashboard ახლა ნამდვილად ხედავს**.

---

## 1. ახლა სად ვართ

- **ეს session (2026-04-30 evening — Sprint C alias UI implementation + cross-source gap discovery + handoff)**:
  - **ნაწილი A (Sprint C preview)** — `/preview` skill executed, evidence inventory complete. File: `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_C_ALIAS_UI_PREVIEW.md`. Findings: name_candidate emission already shipped at `supplier_profitability.py:321`, SupplierModal.jsx:172-231 already renders 💡 hint card, ONLY the confirm bridge missing. User approved DO-in-single-session.
  - **ნაწილი B (Sprint C implement)** — 4 files modified + 2 new test files: `_validate_aliases.append_alias_atomic` (90 lines, atomic .tmp + os.replace, AliasValidationError + AliasDuplicateError exception classes), `server.POST /api/aliases/confirm` (85 lines, mirrors cash-outflow pattern, `_aliases_file_path()` extracted for monkeypatching, retail_known_keys built from cached data.json), `SupplierModal.UnmatchedProductRow` (50+ lines, accepts onConfirm/confirmed/pending props, renders ✓ button + ⏳ + ✅ states), 60 lines new CSS for button gradient + confirmed-row variant + error sub-note. 8 tests green (`tests/test_validate_aliases.py` +4, `tests/test_server_alias_endpoint.py` NEW +4). Full pytest: 2,252 passed / 7 pre-existing AGENTS.md-doc-pin failures (unrelated).
  - **ნაწილი C (commit + sync)** — Two commits on OneDrive: `9ae5e2c docs(preview): Sprint C alias-confirmation scoping` + `57fa81d feat(supplier): Sprint C alias confirmation — endpoint + UI + 8 tests`. C:\\ pulled via `git fetch <onedrive-path> main && git merge --ff-only`. Both heads now at 57fa81d.
  - **ნაწილი D (Restart-Service + endpoint verification)** — User ran `Restart-Service FinancialDashboardBackend` (admin elevation). Post-restart probe: `/api/status = 200`, `POST /api/aliases/confirm` with empty body = `400 + Georgian message "imported_code სავალდებულოა — ცარიელი მნიშვნელობა მიუღებელია"` ✓ — proves new code loaded. Endpoint live.
  - **ნაწილი E (cross-source gap discovery)** — User asked diagnostic question: how much vasadze sold in დვაბზუ Q1 2026. Pipeline-derived numbers (matched-only 617 ₾, name-match 3,888 ₾) DO NOT MATCH user's MAX-side ground truth (revenue ~11,477 ₾ with VAT, cost 10,228 ₾, profit 1,248 ₾). Gap analysis: cost side checks (87% sold, 12% leftover, mass balance OK), revenue side has 7,589 ₾ unaccounted. Diagnosis: MAX uses internal vendor-tag (manual mapping) that's broader than RS waybill linkage. **Sprint C alias UI cannot fix this — it's a different data integration problem (Sprint D candidate)**.
  - **ნაწილი F (regression triggered handoff)** — Multiple „ცადო"/„ცადო-ცადო" filler tokens appeared in 2 responses during cross-source diagnostic. User explicitly requested handoff to new chat. Stop hook DID NOT auto-flag — needs investigation in new chat.
- **წინა session (2026-04-30 afternoon — imported_products bug FIX + 90% coverage diagnostic)**: imported_products bug closed (single CSV moved, 70 suppliers populated). User confirmed incremental file-add philosophy. 90% coverage diagnostic: 21/70 currently ≥90%, top 10 below-90% computed, vasadze identified as quick-win headline (9 candidates total).
- **წინა session (2026-04-30 evening — handoff close-out)**: წინა NSSM-migration session-ის working-copy state ფორმალურად დახურდა — 5 commit landed (constants.py duplicates, retired imported-products CSVs + regression-runtime gitignore, regression-detection Stop hook + handoff template v1.1, AGENTS.md proof-gate path + Session Pacing rewrite, CONTEXT-ის განახლება). ენობრივი regression — „ცადო" filler-ი user-მა გამოაცადა მე-7 cross-session occurrence-ად; გასწორდა inline (filler → „გავაკეთო/მოკლე/შემოწმება").
- **წინა session (2026-04-30 morning — NSSM migration COMPLETE)**: `C:\financial-dashboard\` უკვე დასახლებული იყო (user-ის ხელით 04-29 evening + venv 04-30 00:00:06). NSSM 4 paths გადარედირექტდა (Application + AppDirectory + AppStdout + AppStderr) → service restart → data.json copy from OneDrive → manual pipeline trigger → **pipeline 7.2 წთ-ში სრულდა**, data.json fresh 54.2 MB, 28 API artifacts, 0 errors. OneDrive copy untouched (fallback). Auto-handoff hook + AGENTS.md path fix + handoff skill template v1.1 ამავე session-ში მომზადდა working-copy-ში; დახურდა ამ session-ში 5 commit-ით.
- **წინა-წინა session (2026-04-29 evening, არც ერთი commit არ მომხდარა)**: workspace structural cleanup — parent folder-დან ~863 MB orphan/duplicate ფაილი გადატანილი `_to_delete_2026-04-29\` staging-ში. დეტალები §2-ში.
- **Active section** (Master Plan): §5 გაყიდვები — **CAL mini-sprint** Step 2-ის ბოლოზეა (იგივე წერტილი, არ შეცვლილა).
- **CAL Step 1 (Scope agree)**: ✅ ifqli first, **3-button per-store toggle** (ჯამი / ოზურგეთი / დვაბზუ; თბილისი closed 2024-06 → 2026 retail window-ში 0 data), only-matched + partial-coverage warning banner
- **CAL Step 2 (Data inventory)**: ✅ pipeline-ში per-day aggregation **არ არსებობს** (only `by_month` / `by_category_by_month`). Source per-row datetime ცხადია (`დრო` სვეტი), ifqli matched products უკვე გამოთვლილია `supplier_profitability`-ში. **საჭიროა ახალი aggregation**: `supplier.profitability.daily_breakdown[]` sparse (per-day × per-store)
- **CAL Step 3-6**: spot-check + implement + verify + user review — ⏳ ვიდრე user-ის ცხადი „გადავიდეთ"

**ბოლო commit-ები** (`origin/main`-ზე 9 ahead, push არ გაკეთებულა; ამ session-ში **2 commit + 1 pending CONTEXT_HANDOFF.md**):
```
57fa81d  feat(supplier): Sprint C alias confirmation — endpoint + UI + 8 tests
9ae5e2c  docs(preview): Sprint C alias-confirmation scoping + evidence inventory
b3e2b41  docs(handoff): close imported_products bug + capture 90% coverage Sprint C input
f95e85f  docs(handoff): capture migration Phase 1 + imported_products bug
57cf383  docs(handoff): close _parse_rs_datetime task — pin SHA 2ab4a05
2ab4a05  chore(pipeline): drop dead _parse_rs_datetime first def + unused Georgian-month constant
45c6bb6  docs(handoff): correct ahead-of-main count (48 → 5)
3c54aab  docs(handoff): close NSSM-migration session — 5 commits landed, file rotated
8dd1637  docs(governance): correct AGENTS.md proof-gate path + flesh out Session Pacing
f11439b  feat(.claude): regression-detection Stop hook + handoff template fix
```

**ამ session-ში გაკეთებული**:
1. **Sprint C preview** committed (`9ae5e2c`) — `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_C_ALIAS_UI_PREVIEW.md`, 179 lines.
2. **Sprint C implementation** committed (`57fa81d`) — 6 files, 651 insertions / 10 deletions: `_validate_aliases.py` (+90 lines, atomic helper + 2 exception classes), `server.py` (+105 lines, new endpoint + `_aliases_file_path` + `_build_retail_known_keys`), `SupplierModal.jsx` (+124 lines, button + state + handleConfirmAlias), `components.css` (+65 lines, button + badge + error styles), `tests/test_validate_aliases.py` (+90 lines, 4 new tests), `tests/test_server_alias_endpoint.py` (NEW, 4 tests, 164 lines).
3. **C:\\ git pull** (fast-forward from local OneDrive remote) — both commits now on C:\\ working tree.
4. **`Restart-Service FinancialDashboardBackend`** by user (admin) — verified via `/api/status` 200 + `POST /api/aliases/confirm` empty body returns 400 + Georgian message.
5. **Cross-source revenue gap diagnostic** — uncommitted analysis (Python in shell), no file written. Findings captured in §5.
6. **Language regression triggered handoff** — no commits.

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
| pytest | **2,252/2,259 green** (Sprint C +8 new tests; 7 fail = pre-existing AGENTS.md doc-pin drift after `8dd1637`) |
| `SYSTEM_PROMPT_KA` | 1,163 ხაზი |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 15 |
| `data.json` | 65.5 MB (C:\\), 26 sections, **4 store buckets** supplier-side / **2 active store buckets** retail-side (ოზურგეთი 222K / დვაბზუ 97K Q1 2026) |
| Pipeline coverage | **42.0%** (2,182,576 / 5,200,734 ₾). ⚠️ წინა docs-ი 69.7%-ს წერდა — wrong, baseline regen verified 42% |
| `retail_sales` window | **3 თვე** (2026-01..03) — 96,464 line / 319K ₾ revenue / 50K ₾ profit / 15.84% margin |
| `imported_products` window | **1 file** (Q1 2026), 70 suppliers, profitability ON. NB: `distinct_month_count: 0` + `date_range: {min: None, max: None}` — pipeline doesn't extract month metadata for imports (separate bug) |
| Sprint C scope | **66 candidates total** (20 unmatched_preview + 46 ambiguous_preview); only 21 of 49 below-90% suppliers have ANY visible candidate; ვასაძე leads with 9 candidates |
| `/api/aliases/confirm` | **LIVE** post-restart 2026-04-30 evening — empty body → 400 + Georgian message; happy-path verified by 4 endpoint tests |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |
| VAT cumulative gap | **+90K ₾ net / +107K ₾ gross** (pipeline). Audit ground-truth: **742K ₾**. Delta = ~652K within pipeline coverage gaps |

---

## 4. ღია სამუშაო (priority order)

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| **✅ DONE 2026-04-30** | ~~imported_products bug — supplier modal ცარიელია~~ — File moved (single 3-month CSV), pipeline manual run, 70 supplier-ი profitability-ით. User-ის incremental philosophy captured. | — | — | მთავარი user pain — supplier modal cross-check ცხრილი ცოცხალი |
| **🟡 0a CODE COMPLETE — smoke-test pending** | **Sprint C alias UI** — code landed (commits `9ae5e2c` preview + `57fa81d` impl). Backend endpoint `POST /api/aliases/confirm` LIVE post-restart, returns 400/409/200 with Georgian messages, 8 tests green. Frontend UnmatchedProductRow gains ✓ button + ⏳/✅ states + error sub-note. **REMAINING — browser smoke-test**: (1) start `_vite-dev.bat` in `C:\financial-dashboard\rs-dashboard\`, (2) browser → `http://127.0.0.1:5173`, (3) მომწოდებლები ტაბი → ვასაძის პური → modal → ალიასის კანდიდატები section, (4) click „✓ დადასტურდი ალიასი" on first candidate (imp_code 2006 „შეფუთული აგურა რუხი" → MAX 2247377), (5) verify toast + product_aliases.json write, (6) trigger pipeline rerun + verify coverage delta. Sprint C addressable scope = 66 candidates total but only 20 unmatched + 46 ambiguous visible; pipeline only renders unmatched_preview in UI right now (ambiguous_preview unrendered — Sprint D extension candidate). | ~30-45 წთ | LOW | code on disk, endpoint live, just need user-side click |
| **🚨 0d NEW** | **server.py:116 timeout 10→30 min** — `subprocess.run(timeout=10*60)` killed pipeline at exact 10min. Direct subprocess bypass took ~8min total but Pipeline architecture timing means scheduled hourly run will keep failing. Edit: `timeout=30 * 60`, restart service. Tiny `git diff`, requires UAC for `Restart-Service`. | 5 min | LOW | მომავალი hourly auto-runs ცადობდა keep crashing |
| **✅ DONE 2026-04-30** | ~~NSSM service redirect to `C:\financial-dashboard\`~~ — Migration COMPLETE. data.json fresh, 28 API artifacts, 0 errors. OneDrive copy untouched (1-week retire pending). | — | — | RESOLVED |
| **✅ DONE 2026-04-30 evening** | ~~Regression hook feedback loop broken~~ — **Root cause identified + closed in commit `a5ff7d0`**. Investigation: Stop hook (`check_regression.sh`) IS firing correctly (counter was at 11, fresh flag from prior responses with „ცადო"-stem morphology errors). Bug = Stop hook's `systemMessage` JSON output is not visibly surfaced in Claude Code CLI, so neither user nor Claude saw the alerts. Fix = added new UserPromptSubmit hook (`inject_regression_alert.sh`) that reads `.claude/regression_detected.flag` if fresh (<10min old) and emits `hookSpecificOutput.additionalContext` into Claude's next-turn context, then consumes the flag (moves to `regression_history/`). Verified live: synthetic flag → JSON output → flag moved to history. Real-world demo same session — count incremented to 1 after a ცადობდი slip in prior assistant response, the warning surfaced into next turn's context, Claude self-corrected. Counter reset 11 → 0. `.gitignore` updated for `regression_history/`. |
| **🧹 1-week-pending** | **OneDrive `financial-dashboard\` copy retire — NOT a 5-minute mv** (2026-04-30 verification, session #2). Migration ნაწილობრივია: C:\\ = service mirror only (data.json fresh Apr 30 01:14, მაგრამ კოდი + `.git` Apr 29 22:16 stale — copy migration-ზე გაკეთდა). OneDrive = **ცოცხალი working tree** (governance edits Apr 30 00:36-01:16: CONTEXT_HANDOFF/AGENTS; .git working tree 48 commits ahead არ-push-ებული; .claude config; **Claude Code სესიის cwd**). უბრალო `mv` → working tree-ი დაიკარგება. **სწორი retire sequence**: (1) OneDrive uncommitted ცვლილებები git-ში commit (✅ ამ session-ში გაკეთდა); (2) C:\\-ზე `git pull` ან ხელით governance ფაილების sync; (3) Claude Code-ი C:\\-დან გავუშვა (cwd ცვლილება, შესაძლოა .claude config-იც კოპირდეს); (4) **მხოლოდ ამის შემდეგ** OneDrive → `_to_delete_2026-04-30_onedrive\` staging. | ~30-45 წთ mini-sprint | MEDIUM | divergence-ი ყოველ დღე იზრდება (governance edit-ები მხოლოდ OneDrive-ზე, data.json მხოლოდ C:\\-ზე) — საჭიროა migration plan |
| **🧹 1-week-pending** | `_to_delete_2026-04-29\` permanent delete (863 MB) — 5-7 დღე dashboard ცოცხალი → permanent rm. თუ user-მა რამე surprise აღმოაჩინა → უკან გადატანა (§2) | 1 წთ | LOW | grace period აქტიური; cleanup უკვე გაკეთდა, მხოლოდ permanent rm-ი დარჩა |
| **✅ DONE 2026-04-30** | ~~`AGENTS.md:35` proof gate path~~ — workspace canonical → project canonical, symlink note added pointing to §7 for full structure. | — | — | proof-ფრაზა ახლა შეესაბამება რეალურ symlink სტრუქტურას |
| **🚨 0c** | dashboard „ანალიზდა" KPI ცრუობს partial-coverage სცენარში | 1 sprint | **HIGH** | ELIZI ground-truth: cost 297,685 / sales 313,456 / margin **+5.3%**. Dashboard: −2.13%. 4 ვარიანტი: (A) alias 35→80%; (B) UI banner; (C) ცალკე KPI „matched-only margin"; (D) ground-truth Excel pipeline-ში. user-ი არჩევს |
| **🚧 CAL** | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა | ~1 session | LOW | scope locked, data inventory done; საჭიროა new daily aggregation `supplier_profitability`-ში |
| **✅ DONE 2026-04-30** | ~~`dashboard_pipeline/constants.py` duplicate functions~~ — **REAL SCOPE WAS 10 FUNCTIONS, NOT 1**. Verified: 9 character-identical (`_object_order_for_pos`, `_object_order_for_monthly_pnl`, `_month_sort_key`, `_match_text_to_object`, `detect_object`, `_extract_tax_id_from_org`, `_pick_aging_bucket`, `_empty_aging_summary`, `_to_waybills_df`) → first copies deleted (lines 434-541, 109 lines removed, file 797→688). 50 targeted tests green, syntax OK, all 10 names still callable. | — | — | dead code removed |
| **✅ DONE 2026-04-30** | ~~`_parse_rs_datetime` — TWO DIVERGENT versions~~ — Spot-check across 5 RS waybill files (2022-2026) + 3 retail sales files (01-03.2026) confirmed ALL datetime values use ISO `%Y-%m-%d %H:%M[:%S]` format. No Georgian month tokens anywhere. Dead first def (L434-463) + dead `IMPORTED_PRODUCTS_MONTH_TOKEN_TO_MM` constant + unused import in `generate_dashboard_data.py` removed (commit `2ab4a05`, 48 lines deleted). 21 targeted tests green. Live behavior unchanged (L657 was already overriding L434). | — | — | divergent dead code resolved; only one canonical `_parse_rs_datetime` remains |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) | 1-2 session | LOW | (a) `vulture` dead-code; (b) `jsonschema` config-ფაილებზე; (c) golden snapshot data.json-ისთვის; (d) reconcile_suppliers.py გავრცელება; (e) Pandera RS.ge CSV reader |
| **🆕 0f Sprint D candidate** | **Cross-source revenue gap — MAX vendor-tag vs RS waybill** (NEW 2026-04-30 evening) — User provided ground-truth from MAX MEgaplus for vasadze@დვაბზუ Q1 2026: cost 10,228.48 ₾ / profit 1,248.85 ₾ / revenue ~11,477 ₾ (with VAT). Pipeline-derived = 3,888 ₾ name-match (gap 7,589 ₾). Cost-side mass balance OK (87% sold). **Diagnosis**: MAX uses internal manual vendor-tag mapping per product (broader than RS waybill). Sprint C alias UI bridges RS-code↔MAX-code where names align — does NOT bridge "MAX-tagged-as-vasadze but no RS waybill linkage". Possible root causes: (a) name divergence beyond name-match threshold, (b) cash-paid invoices not on RS, (c) MAX's manual vendor-tag includes products vasadze never officially shipped per RS. **Investigation paths**: (1) ask user to export MAX's per-supplier sales report (CSV/Excel) to bypass RS waybill entirely; (2) add MAX-vendor-tag column to retail_sales pipeline if available in source data; (3) document this as a structural caveat in supplier_profitability output (KPI banner: „რეალურ-ცადო შეიცავს მხოლოდ RS-ით ცნობილ პროდუქტებს"). **Defer until user decides**: extend Sprint C with this OR run as separate Sprint D. | 2-3 sessions investigation + 1-2 sessions impl | MEDIUM | **structural caveat — pipeline-ით ვერ ვცადობ რომ ვასაძის სრული სცენა შემოგვცე** |
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

**🚨 ენობრივი regression — pattern history (8 cross-session occurrences)**: filler-words / partial Georgian tokens (2026-04-27 + 04-28 + 04-29 morning + 04-29 evening ×2 + 04-30 morning + 04-30 afternoon + **2026-04-30 evening — THIS SESSION**). Trigger: complex tool output → cognitive load → degraded Georgian generation. **2026-04-30 evening NEW**: this session had 4-5 instances of „ცადო"/„ცადო-ცადო" across 2 responses during cross-source diagnostic. Stop hook from `f11439b` did NOT visibly flag — see §4 item `0e` for debug path. User caught manually + triggered restart. **The 2-correction-rule for restart is now hardened: this is iteration #2 in this session and user explicitly requested handoff**.

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
