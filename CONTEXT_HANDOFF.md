# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-06 (Sprint B: rs.ge pipeline wire-in PROOFED — Sprint B სრულად დახურულია). წინა → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-03_2026-05-04.md`. ადრე → `CONTEXT_HISTORY_2026-04_2026-05-02.md`.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-06) — Sprint B PROOFED · Sprint B CLOSED

🎉 **რს.ge-ის pipeline ექსკლუზიურად parquet cache-დან კითხულობს. Excel ფაილები აღარაა pipeline-ის dependency.**

| საკითხი | სტატუსი |
|---|---|
| `rsge_cache.py::list_rsge_waybill_paths()` + `read_waybill_file()` (auto-dispatch parquet/xls) + `append_rsge_cache()` | ✅ NEW |
| `_backfill_rsge.py` runner (calendar-month windows, append-only, error-stops) | ✅ NEW |
| Backfill 2022-05-01 → 2026-05-05 (4yr+) | ✅ 22,408 rows (2022:1,060 / 2023:5,716 / 2024:6,848 / 2025:6,537 / 2026:2,247) |
| Yearly cache vs XLSX 1:1 verification (2022/2023/2024/2025) | ✅ cent-perfect |
| 2026 cache vs XLSX delta = 70 rows / +9,109.42 ₾ (May 1-5 only, bonus depth) | ✅ ახსნილი |
| 7 surgical wire-in edits — production read sites | ✅ |
| `generate_dashboard_data.py::_read_and_parse_rs` (main RS reader — initially missed, found via POST log) | ✅ |
| `generate_dashboard_data.py` 3 path-list sites (manifest, line 1395, line 1746) → `list_rsge_waybill_paths()` | ✅ |
| `waybill_reconciliation.py::load_rs_waybills` (folder→paths signature change, uses `read_waybill_file`) | ✅ |
| `supplier_matching.py::build_supplier_master` | ✅ |
| `supplier_matching.py::_build_waybill_reference_index` | ✅ |
| `supplier_matching.py::collect_rs_tax_ids` | ✅ |
| `manual_payments.py::collect_rs_suppliers_by_tax_id` | ✅ |
| Pipeline run (~4 წუთი, 0 errors / 0 warnings, data.json 101.44 MB) | ✅ |
| Pre/post-swap data.json diff: 31 sections — 16 IDENTICAL, 15 DIFF | ✅ |

**Numeric verification — `data.json` actual delta (15 DIFF sections all derive from one root cause):**

| section | delta | მიზეზი |
|---|---|---|
| `waybills[]` (array) | +70 rows / +9,109.42 ₾ ↑ | bonus historical depth (May 1-5, 2026) |
| `waybill_reconciliation`, `suppliers`, `supplier_aging`, `ap_monthly_trend`, `aging_summary`, `supplier_concentration`, `bank_reconciliation_audit`, `bank_unmatched_analysis`, `financial_ratios`, `executive_summary`, `company_valuation`, `imported_products`, `meta`, `source_manifest` | derived deltas | all propagate from the same +70 May 2026 waybills |
| `bog_expenses`, `budget`, `category_anomalies`, `forecast`, `megaplus_live`, `monthly_pnl`, `pos_terminal_income`, `retail_sales`, `tax_flow`, `tbc_card_income`, `tbc_expenses`, `tbc_foodmart_cashback`, `tbc_samurneo`, `vat_reconciliation`, ... | **IDENTICAL** | swap არ შეცვალა |

**Spot-checked 5 only-POST waybill numbers** — ყველა `2026-05-xx` რიცხვი, მომწოდებლები შესაბამისი (იფქლი / ვასაძის პური / კოსტ-კასტლ).

**Source-level delta (cache - XLSX) = +70 rows / +9,109.42 ₾** = pipeline-level delta ✅ ცენტამდე.

**Commits**: `eba02cf` (cache infra) + `de55942` (pipeline wire-in) on `main`. Local branch is 6 commits ahead of `origin/main` (push pending — user-side).

**House-keeping**: `data.json.PRE_BOG_PARQUET_BACKUP` + `data.json.PRE_RSGE_PARQUET_BACKUP` (106 MB each) დაცულია repo-ფესვში — gitignored, წაშლის უფლება მომავალ session-ში. `_scratch_*.py` + `_scratch_*.log` — verification evidence, untracked.

---

## 1. წინა session-ის შედეგი (2026-05-05 ღამე) — Sprint A Step 4b PROOFED · Sprint A CLOSED

🎉 **ბოგ-ის pipeline ექსკლუზიურად parquet cache-დან კითხულობდა.** ანალოგიური სტრუქტურა, რასაც Sprint B-მა მიჰყვა (§0).

- 8 surgical edits — `bank_reconciliation.py::get_bank_payments`, 5 × `bank_income.py` (samurneo, POS, expense_categories, tax_flow, tax_flow path-list), `file_utils.py::_bank_positive_debit_total_ge`, `supplier_matching.py::infer_bog_receiver_id_to_rs_tax_id`, `generate_dashboard_data.py` source-manifest.
- Numeric delta: `pos_terminal_income.bog` +11,312 lines / +109,086.96 ₾ (bonus historical depth — 2023 Jan-Mar + 2026 Apr-May); `tax_flow.out (BOG)` +6 lines / +10,338.83 ₾; `vat_reconciliation` +109,086.96 ₾ gross / +92,446.58 ₾ net (mirrors POS ÷ 1.18). 27/30 numeric sub-sections IDENTICAL.
- **Commit**: `c4fd1c6` on `main`.
- Earlier (TBC + BOG + rs.ge connectors PROOFED): commits `52de7ba`/`bf8d204`/`dc2f9de` (rs.ge), `4c14920`+`a7f4ea9` (BOG), `3c80236`+`ace7d9f` (TBC), `a5b88c8` (governance). Two bug fixes: TBC `debitCredit` 0/1 not 1/2; BOG ID-float trailing `.0` (`_g_str()` `float.is_integer()` check).

---

## 1b. Wire-in architecture — DECIDED 2026-05-05 ღამე (Variant 1, 10 locked decisions)

| # | გადაწყვეტილება | მნიშვნელობა |
|---|---|---|
| 1 | Source | API only — no XLSX in pipeline |
| 2 | Cache path | `C:\financial-dashboard\Financial_Analysis\cache\{bog,tbc,rsge}\` |
| 3 | Cache format | parquet (one file per bank per year) |
| 4 | Data model | **Append-only** — old records never mutate, refreshes only ADD new entries |
| 5 | Trigger | Manual button only — NO background scheduler |
| 6 | Button location | Top of bank tab, single "განახლება" button refreshes all 3 banks together |
| 7 | Refresh flow | Button click → modal asks for DigiPass OTP → fetch BOG + rs.ge + TBC concurrently → cache append → dashboard reload, ~30-60s wait |
| 8 | Backfill | One-time manual script, 2023-01-01 → today, runs via parent venv. Error → STOP + ask user |
| 9 | Phase order | A. BOG (simplest, fully automated) → B. rs.ge → C. TBC + UI button. Each phase fully closed before next. |
| 10 | Retroactive corrections | **DEFERRED** — user knowingly accepts that bank-side mutations to old records will be missed. If later observed to matter, add 30-day re-fetch + changes log feature. |

**User-side note (2026-05-05 ღამე):** sessions ended on user fatigue + "თავიდან დავიწყოთ" framing. New chat is preferred for sprint A. This handoff carries the locked scope forward — **do not relitigate decisions 1-10 unless user reopens them explicitly**.

**Pipeline integration (BOG + TBC + rs.ge) NOT yet wired in** — connectors standalone, parity verified. Sprint A = BOG read-site swap.

---

## 2. TBC DBI verified facts (Stage 3 prep)

**Status**: ✅ Stage 0/1a/1b/2 PROOFED. Stage 3 (production connector) ღია.

| ფაქტი | მნიშვნელობა |
|---|---|
| Production endpoint | `https://dbi.tbconline.ge/dbi/dbiService` (Standard tier, NO certificate) |
| Standard+ production | `https://secdbi.tbconline.ge/dbi/dbiService` (requires .pfx client cert) |
| Username | `FOODTIME_TBC` |
| IBAN | `GE90TB7793336020100005` (GEL) |
| Auth scheme | WS-Security `UsernameToken` — plain text Username + Password + Nonce (NO PasswordDigest) |
| Nonce | DigiPass-generated 9-digit OTP (PIN: 0777) — ~5-15 min window |
| 5 services | StatementService · MovementService · PaymentService · PostboxService · ChangePasswordService |
| Statement vs Movement | StatementService = aggregates only · MovementService = per-transaction (40+ fields, paged 700 max) |
| DateTime format | `yyyy-MM-dd'T'HH:mm:ss.SSS` (milliseconds REQUIRED) |
| Response wrapping | `<accountMovement>` per-row · `<result><pager><totalCount>` |
| XLSX naming gotcha | `03.2026.xlsx` contains 12 months (2025-03 → 2026-03), 19,919 rows |

**Stage 2 parity (window 2026-03-01 → 2026-03-03):** XLSX 104 = SOAP 104, debit 9,641.40 = 9,641.40, credit 9,994.94 = 9,994.94. 4/5 random documentNumber spot-checks exact; 1 documentNumber-collision (`1772438632`) artifact — production join must use composite key (docNum + amount + counterparty), not docNum alone.

**.env (gitignored):** `TBC_DBI_ENDPOINT` · `TBC_USERNAME` · `TBC_PASSWORD` · `TBC_ACCOUNT_NUMBER=GE90TB7793336020100005` · `TBC_ACCOUNT_CURRENCY=GEL`. Nonce = runtime input (DigiPass cannot be automated — bank confirmed).

---

## 3. BOG API verified facts (wire-in prep)

**Status**: ✅ Stage 1-3 PROOFED. Production connector ღია.

| ფაქტი | მნიშვნელობა |
|---|---|
| Account | `GE15BG0000000537419534GEL` (READ-ONLY, GEL only) |
| App name | `GeoFoodTime bog` (Client Credentials flow) |
| Token endpoint | `https://account.bog.ge/auth/realms/bog/protocol/openid-connect/token` |
| Production API host | `https://api.businessonline.ge` (NOT `api.bog.ge` — that's docs site) |
| Statement endpoint | `GET /api/statement/{account}/{currency}/{startDate}/{endDate}` |
| Auth | Bearer token, expires 1800s (30 min) |
| Date format | `YYYY-MM-DD` |
| Per-call limit | 1000 records — date-window slicing required (March 2026 had 5,075 rows) |
| Field mapping | `EntryDate↔თარიღი` · `EntryId↔ოპერაციის იდ` · `EntryAmountDebit↔დებეტი` · `EntryAmountCredit↔კრედიტი` · `EntryComment↔ოპერაციის შინაარსი` · `BeneficiaryDetails.Name↔მიმღების დასახელება` |

**Open gaps:** max historical range untested (try 2023+); rate limits untested; USD/EUR/POS accounts need separate registration; pagination strategy = date-window slicing.

**.env (gitignored):** `BOG_CLIENT_ID` · `BOG_CLIENT_SECRET`.

---

## 4. ღია სამუშაო — შემდეგი session (Sprint C = TBC pipeline wire-in + UI ღილაკი)

**Sprint A status: ✅ CLOSED** (commit `c4fd1c6`) — BOG.
**Sprint B status: ✅ CLOSED** (commits `eba02cf` + `de55942`) — rs.ge.

**Sprint C (TBC + UI) — has not started.** ბოლო ფაზაა Variant 1-დან (§1b decision #9).

| Step | რა |
|---|---|
| 1. Scope agree | TBC DBI connector უკვე PROOFED (§3). 6-step pattern კვლავ: cache infra → wire-in → verify. დამატებით: UI ღილაკი + DigiPass OTP modal. |
| 2. Data inventory | TBC XLSX read sites — `bank_income.py` (5 TBC site: samurneo, POS, foodmart cashback, card income, expense categories) + `bank_reconciliation.py::get_bank_payments` TBC ნაწილი + `file_utils.py` find_header_row + `supplier_matching.py` (TBC IBAN/partner index). Enumerate before edits. |
| 3. Spot-check | TBC connector output (`MovementService`) vs `03.2026.xlsx` — 1 თვე row-by-row, 5+ representative samples. ⚠️ Composite key required (docNum + amount + counterparty), არა docNum-ი მარტო — `1772438632` collision-i გამოვლინდა. |
| 4. Cache infra | New `tbc_cache.py` — parquet store, append-only, per-year. Schema = TBC `accountMovement` 40+ fields → mapping to existing TBC XLSX columns. Backfill runner `_backfill_tbc.py`. **DigiPass OTP** required — runner asks user-ისგან nonce-ს ერთხელ window-ის დასაწყისში; ~5-15 min window for full backfill. Plan windows accordingly. |
| 5. Wire-in | Surgical refactor — replace `pd.read_excel(tbc_xlsx)` sites with cache reads. ~6-8 sites expected. |
| 6. UI ღილაკი + DigiPass modal | Bank tab top — single „განახლება" button. Click → modal asks DigiPass OTP → fetch BOG + rs.ge + TBC concurrently → cache append → dashboard reload. ~30-60s. (§1b decision #6, #7) |
| 7. Verify | Pre-/post-swap data.json diff; bonus historical depth expected (similar to BOG + rs.ge). |

**rs.ge Sprint A carryover (non-blocking, parallel side task — still open):**
- SOAP run for 26 SOAP_PENDING orphan TINs → updates `Financial_Analysis/orphan_resolver_review_2026-05-04.xlsx`
- User reviews orphan Excel and applies 4,647 mappings via MegaPlus UI

---

## 5. Active open work (carryover from earlier sprints)

| # | task | size | risk |
|---|---|---|---|
| 🟡 0a CODE COMPLETE — smoke-test pending | Sprint C alias UI browser smoke-test (endpoint LIVE, 8 tests green, just need user-side click via `_vite-dev.bat` → modal → ალიასის კანდიდატები → დადასტურდი). | ~30 წთ | LOW |
| 🚨 0c — DECISION READY | MAX vendor-tag file integration (`Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls`, 116 suppliers, დვაბზუ only). 3 paths: (A) read-only side-by-side, (B) soft replacement on tax_id match, (C) loader only. ოზურგეთი analog ⏳. | A=1 / B=2 / C=0.5 sessions | HIGH |
| 🚧 CAL | calendar heatmap supplier modal-ში — Step 3 spot-check ღიაა. `supplier.profitability.daily_breakdown[]` sparse aggregation. | ~1 session | LOW |
| 🆕 0f Sprint D candidate | Cross-source revenue gap (MAX vs RS waybill: ვასაძე@დვაბზუ Q1 2026: pipeline 3,888 ₾ vs MAX 11,477 ₾, gap 7,589 ₾). | 2-3 inv + 1-2 impl | MEDIUM |
| 1 | Supplier Profitability Sprint C UI extensions — render `ambiguous_preview` + bulk-confirm + DELETE endpoint | ~1 session | LOW |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` (TOOL_SCHEMAS 29 → 30) | ~1 session | LOW |
| 🧹 1-week-pending | OneDrive `financial-dashboard\` copy retire (NSSM service mirror C:\\-only) | ~30-45 წთ | MEDIUM |
| 🛡 0b | Safety net follow-ups — vulture dead-code, jsonschema config, golden snapshot, Pandera RS.ge CSV reader | 1-2 sessions | LOW |

---

## 6. Verified facts (cross-check before action)

| მაჩვენებელი | მნიშვნელობა |
|---|---|
| pytest (key suites) | 39/39 waybill_reconciliation + 50/50 supplier_profitability + retail_sales_revenue_formula |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 16 |
| `data.json` | 101.44 MB (post-rs.ge-parquet-wire-in, 2026-05-06) |
| Local branch | `main` 6 commits ahead of `origin/main` (push pending — user-side) |
| Cache state | BOG: 171,869 rows (2023-2026) · rs.ge: 22,408 rows (2022-2026) · TBC: not yet built |
| MegaPlus DB integration | LIVE — 53 tables / 282+308 suppliers across 2 stores / 720K active orders / 2024-03 → 2026-04 |
| MegaPlus watch folder layout | `Financial_Analysis/მეგაპლიუსის არქიტექტურა/{დვაბზუ,ოზურგეთი}/` (legacy `მეგა პლუს backup*` glob still supported) |
| Phase B exploratory data | POS active rows 1,552,457 (4yr); negative-margin 4.13% / 95,682 ₾ loss; PRODUCTS orphans 4,918 / 685,804 ₾ (verified 2026-05-04, 2x larger than chat-history claim) |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |

---

## 7. Canonical paths & services (do-not-touch)

⚠️ **Source ფაილების canonical path — symlink სტრუქტურა (2026-04-29 verified):**

- **pipeline view**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis\`
  - 15 JSON config (real, canonical) — `cash_outflow_journal.csv`, `product_aliases.json`, etc.
  - 5 symlink target ფოლდერი → `..\Financial_Analysis\` (parent):
    - `ბოგ ბანკი ამონაწერი`, `გაყიდული პროდუქტები სოფ დვაბზუ`, `გაყიდული პროდუქტები სოფ ოზურგეთი`, `თბს ბანკი ამონაწერი`, `რს ზედნადები`
  - `მეგაპლიუსის არქიტექტურა/` — MegaPlus daily backup ZIPs (per-store sub-folder); pipeline auto-discovers
  - ⚠️ `შემოტანილი პროდუქცია\` ფოლდერი — pipeline 0 errors, მაგრამ folder absent verified (2026-04-30). შემდეგ session-ში გადასამოწმებელი — `dashboard_pipeline/imported_products.py` რომელ path-ს კითხულობს
- **parent's `Financial_Analysis\`**: 5 ცოცხალი data ფოლდერი (symlink target — NEVER touch)

**ცხრილი:**
- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `...\financial-dashboard`
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. Pipeline subprocess-ი ცალკე იქმნება, კოდის ცვლილებას ავტომატურად აიღებს. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)
- **SQL Server Express**: `localhost\SQLEXPRESS` (instance), `MEGAPLUS_<storeID>` databases — restore via `megaplus_backup._restore` from PLUS_*.bak
