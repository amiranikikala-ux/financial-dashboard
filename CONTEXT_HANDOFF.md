# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-05 ღამე (Sprint A Step 4b: BOG pipeline wire-in PROOFED — Sprint A სრულად დახურულია). წინა → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-03_2026-05-04.md`. ადრე → `CONTEXT_HISTORY_2026-04_2026-05-02.md`.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-05 ღამე) — Sprint A Step 4b PROOFED · Sprint A CLOSED

🎉 **ბოგ-ის pipeline ექსკლუზიურად parquet cache-დან კითხულობს. Excel ფაილები აღარაა pipeline-ის dependency.**

| საკითხი | სტატუსი |
|---|---|
| `bank_cache.py::list_bog_statement_paths()` + `read_bank_statement()` (auto-dispatch parquet/xlsx) | ✅ NEW |
| 8 surgical edits (handoff-ში 6 + ნაპოვნი 2 დამატებითი ad hoc) | ✅ |
| `bank_reconciliation.py::get_bank_payments` (BOG read loop) | ✅ |
| `bank_income.py::_process_bog_samurneo_file` | ✅ |
| `bank_income.py::_process_bog_pos_terminal_income_file` | ✅ |
| `bank_income.py::_process_bog_expense_categories_file` | ✅ |
| `bank_income.py::_process_bog_tax_flow_file` (helper called from tax_flow dispatcher) | ✅ |
| `bank_income.py::tax_flow` path-list site | ✅ |
| `file_utils.py::_bank_positive_debit_total_ge` (debit cross-check) | ✅ |
| `supplier_matching.py::infer_bog_receiver_id_to_rs_tax_id` (NEW — handoff missed) | ✅ |
| `generate_dashboard_data.py` source-manifest path list (NEW — handoff missed) | ✅ |
| Pipeline run (12 წუთი, 0 errors / 0 warnings, data.json 101.36 MB) | ✅ |
| Diff vs pre-swap baseline (27/30 numeric sub-sections IDENTICAL) | ✅ |

**Numeric verification — `data.json` actual delta:**

| section | delta | მიზეზი |
|---|---|---|
| `pos_terminal_income.bog` | +11,312 lines / +109,086.96 ₾ ↑ | bonus historical depth |
| `tax_flow.out` (BOG) | +6 lines / +10,338.83 ₾ ↑ | bonus historical depth |
| `vat_reconciliation` | +109,086.96 ₾ gross / +92,446.58 ₾ net ↑ | mirrors POS rise (÷ 1.18) |
| `bank_reconciliation`, `samurneo_movement`, `monthly_pnl`, `supplier_aging`, ე.ი. დანარჩენი | **IDENTICAL** | swap არ შეცვალა |

**Bonus historical depth (cent-perfect explanation of ↑):**
- 2023 Jan-Mar (XLSX `2023.xlsx` covered Apr-Dec only): +4,652 POS rows / +40,173.28 ₾
- 2026 Apr-May (newer than `03.2026.xlsx` cutoff): +6,660 POS rows / +68,913.68 ₾
- **Sum: +11,312 rows / +109,086.96 ₾** = data.json delta ✅ ცენტამდე

**Commit**: `c4fd1c6` on `main`. Local branch is 3 commits ahead of `origin/main` (push pending — user-side).

**House-keeping**: `data.json.PRE_BOG_PARQUET_BACKUP` (106 MB) დაცულია repo-ფესვში შესადარებელ შეფერხებად — gitignored, წავშლი/წაშლის უფლება მომავალ session-ში.

---

## 1. წინა session-ის შედეგი (2026-05-05) — TBC + BOG connectors PROOFED

🎉 **TBC Stage 3 PROOFED** + **BOG 1-month parity PROOFED** + **Variant 1 wire-in scope locked**.

| ბანკი | Connector | Live verify | Commit |
|---|---|---|---|
| **rs.ge** | ✅ | ✅ PROOFED | `52de7ba`/`bf8d204`/`dc2f9de` |
| **BOG** | ✅ + ID-float fix | ✅ **PROOFED** 3 days + **1 full month** (March 2026: 5,075=5,075 records, debit 52,521.36 = 52,521.36, credit 53,521.33 = 53,521.33, 31 days exact, 5/5 ID spot-checks 1:1) | `4c14920` + `a7f4ea9` |
| **TBC DBI** | ✅ + dc-convention fix | ✅ **PROOFED** (104=104, 9,641.40 / 9,994.94 exact, 4/5 unique 1:1) | `3c80236` + `ace7d9f` |
| **Governance** | ✅ | n/a | `a5b88c8` |

**Two bugs found + fixed this session:**
1. **TBC** `debitCredit` was `0/1`, not `1/2` — 12 outgoing records had been misclassified.
2. **BOG** numeric IDs were returned as floats with trailing `.0` — broke per-row spot-checks against XLSX (e.g. `"112251085657.0"` vs `"112251085657"`). Fixed in `_g_str()` via `float.is_integer()` check.

**Local branch**: `main` is 5 commits ahead of `origin/main` — **all pushed** (latest: `a7f4ea9`).

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

## 4. ღია სამუშაო — შემდეგი session (Sprint B = rs.ge pipeline wire-in)

**Sprint A status: ✅ CLOSED** (commit `c4fd1c6`). All 6 steps done — scope agreed, data inventory complete (8 read sites, not 6), spot-check 1:1, cache infra (`bank_cache.py` + `_backfill_bog.py`, 171,869 rows), wire-in surgical refactor, pipeline verify (cent-perfect diff), see §0.

**Sprint B (rs.ge) — has not started.** Mirror Sprint A structure:

| Step | რა |
|---|---|
| 1. Scope agree | რს.ge connector უკვე PROOFED (§1). Repeat Sprint A's 6-step pattern: cache infra → wire-in → verify. |
| 2. Data inventory | რს.ge XLSX read sites (not yet enumerated — find via `grep "list_rs_waybill_files"` and similar). |
| 3. Spot-check | Compare connector output vs current XLSX outputs row-by-row, 5+ representative samples. |
| 4. Cache infra | `bank_cache.py` extension or new `rsge_cache.py` — parquet store, append-only, per-year. Backfill runner. Schema = SOAP response shape. |
| 5. Wire-in | Surgical refactor — replace `pd.read_excel(rs_xlsx)` sites with cache reads. |
| 6. Verify | Pre-/post-swap data.json diff; bonus historical depth expected (similar to BOG). |

**Then Sprint C** = TBC + UI ღილაკი + DigiPass modal (last sprint).

**rs.ge Sprint A carryover (non-blocking, parallel side task):**
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
| `data.json` | 101.36 MB (post-BOG-parquet-wire-in, 2026-05-05) |
| Local branch | `main` 3 commits ahead of `origin/main` (push pending — user-side) |
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
