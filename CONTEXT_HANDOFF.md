# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-04 ღამე (Sprint A Step 4-5: cache infrastructure built + verified). წინა → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-03_2026-05-04.md`. ადრე → `CONTEXT_HISTORY_2026-04_2026-05-02.md`.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-04 ღამე) — Sprint A Step 4-5 PROOFED

🎉 **BOG cache infrastructure built + full backfill verified 1:1 vs XLSX across 4 years.**

| საკითხი | სტატუსი |
|---|---|
| `dashboard_pipeline/bank_cache.py` (read/write/append parquet) | ✅ NEW |
| `dashboard_pipeline/_backfill_bog.py` (one-time CLI runner) | ✅ NEW |
| `requirements.txt` (+pyarrow==24.0.0) | ✅ |
| `Financial_Analysis/cache/bog/{2023,2024,2025,2026}.parquet` | ✅ 171,869 rows total (gitignored) |
| Q1 2025 parity proof (XLSX vs API) | ✅ 11,912=11,912 / debit 139,708.09 / credit 138,965.08 / 5/5 spot-checks |
| 2023 Apr-Dec parity (XLSX-covered window) | ✅ 26,892=26,892 / 0.00 ₾ diff / all 26,892 EntryIds match |
| 2024 full-year parity | ✅ 53,935=53,935 / 0.00 ₾ diff |
| 2025 full-year parity | ✅ 65,116=65,116 / 0.00 ₾ diff |
| 2026 Feb parity | ✅ 4,644=4,644 / 0.00 ₾ diff |
| 2026 Mar parity | ✅ (already PROOFED 2026-05-05 prior; 5,075 rows) |
| Append-only idempotency | ✅ re-running on overlap window adds 0 rows |

**Two new facts surfaced:**
1. **2023 Jan-Mar — bonus history.** XLSX `2023.xlsx` only covers `01.04.2023-31.12.2023` (period stamped in metadata row 6). API gave us **4,705 extra rows** for Jan-Mar 2023 — dashboard's historical depth will extend 3 months further once cache is wired in.
2. **Second BOG account (`GE66BG0000000603627033GEL`)** — savings/deposit, NOT registered in API. Money never leaves company directly from it (always returns to main first). User-confirmed: don't register it. Saved as memory `project_bog_two_accounts.md`. XLSX/API "diff" rows in 2024 (8 rows = 690 ₾ in/out) and 2025 (3 rows = 500 ₾ in/out) are exclusively this account; net P&L impact = 0.

**Local branch**: `main` in sync with `origin/main` at session start; this session adds 1 NEW commit (cache infra + handoff). Push pending.

---

## 0a. ღია — Sprint A Step 4 (continuation): pipeline wire-in (6 sites, not 5)

**არ დაწყებულა.** ფრთხილ სუფთა სესიას იმსახურებს — touches 6 production read sites in 3 files:

| # | ფაილი : ფუნქცია | ხაზი | რას აკეთებს |
|---|---|---|---|
| 1 | `bank_reconciliation.py::get_bank_payments` | 1014 | BOG მიერ-XLSX iteration → reconcile lines |
| 2 | `bank_income.py::_process_bog_samurneo_file` | 252 | per-file სამურნეო expense aggregates |
| 3 | `bank_income.py::_process_bog_pos_terminal_income_file` | 1060 | POS-income aggregates |
| 4 | `bank_income.py::_process_bog_expense_categories_file` | 1532 | expense-category aggregates |
| 5 | `bank_income.py::tax_flow` BOG branch | 809 | **NEW — was missed in earlier handoff.** BOG part of `_run_cached_per_file` dispatcher (BOG+TBC mixed). |
| 6 | `file_utils.py::_bank_positive_debit_total_ge` | 266 | reconciliation total cross-check |

**Strategy** (agreed but not yet executed): add to `bank_cache.py`:
- `list_bog_statement_paths()` → returns `Financial_Analysis/cache/bog/*.parquet` paths
- `read_bank_statement(path)` → auto-dispatch by extension (parquet → `pd.read_parquet`; xlsx → `find_header_row` + `pd.read_excel`). TBC sites can use this verbatim — they keep XLSX paths until Sprint C.

Then 6 surgical edits, each replacing `for f in list_bog_bank_statement_xlsx(): … find_header_row(f) … pd.read_excel(f, …)` with `for f in list_bog_statement_paths(): … read_bank_statement(f)`.

**Risk:** caches in `_run_cached_per_file` use file fingerprint; switching from XLSX paths to parquet paths invalidates them all → first pipeline run after the swap is full-rebuild (slow but correct). Subsequent runs cache normally.

**Verify after swap:**
- Backup current `data.json` → run pipeline → diff numerically.
- BOG-related figures **may legitimately rise** because of bonus 2023 Jan-Mar 4,705 rows (3 extra months of debit/credit feeding through samurneo / POS / expense categories / reconciliation totals). NOT a regression — historical depth gain.
- Spot-check: per-month bank reconciliation totals 2024 onwards (where cache and XLSX are identical) must match 1:1 with prior data.json byte-for-byte for those months.

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

## 4. ღია სამუშაო — შემდეგი session (Sprint A = BOG pipeline wire-in)

**Sprint A status (2026-05-04 ღამე):**
- ✅ Step 2 (data inventory): 6 read sites identified — see §0a above (5 from earlier handoff + 1 missed: `bank_income.py::tax_flow` BOG branch line 809).
- ✅ Step 3 (spot-check): Q1 2025 + full-year 2024/2025 + 2026 Feb verified 1:1 vs XLSX (see §0).
- ✅ Step 4a (cache infra): `bank_cache.py` + `_backfill_bog.py` built; backfill 2023-01-01 → 2026-05-04 done (171,869 rows).
- 🚧 **Step 4b (pipeline wire-in)** — **THIS is next session's primary task.** 6-site surgical refactor; details + risk in §0a.
- ⏳ Step 5 (verify pipeline data.json): blocked on 4b.
- ⏳ Step 6 (user review): blocked on 5.

**Then Sprint B (rs.ge), Sprint C (TBC + UI button + DigiPass modal).** Total 4-7 sessions estimated (Sprint A reduced because Step 4a is done).

**rs.ge Sprint A carryover (non-blocking, side task):**
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
| `data.json` | 106 MB (post-MegaPlus-rediscovery, 2026-05-03) |
| Local branch | `main` 3 commits ahead of `origin/main` (push pending) |
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
