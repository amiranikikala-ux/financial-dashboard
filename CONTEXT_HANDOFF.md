# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-04 ღამე. 2026-05-03 / 2026-05-04 morning ისტორია → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-03_2026-05-04.md`. წინა → `CONTEXT_HISTORY_2026-04_2026-05-02.md`.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 1. ბოლო session-ის შედეგი (2026-05-04 ღამე)

🎉 **3 ბანკის connector კოდი მზადაა** + დღევანდელი governance cleanup დამთავრდა.

| ბანკი | Connector | Live verify | Commit |
|---|---|---|---|
| **rs.ge** | ✅ committed earlier | ✅ PROOFED | `52de7ba`/`bf8d204`/`dc2f9de` |
| **BOG** | ✅ committed | ✅ **PROOFED** (453 records / 3,891.84 dbt / 5,336.42 crd, 100% parity 2026-03-01..03) | `4c14920` |
| **TBC DBI** | ✅ committed | ⏳ **PENDING** (account blocked — too many wrong-action probes during URI discovery) | `3c80236` |
| **Governance** | ✅ short-language rule + doc cleanup + CONTEXT_HANDOFF trim 656→143 lines | n/a | `a5b88c8` |

**Local branch**: `main` is **3 commits ahead of origin/main** (`a5b88c8` + `4c14920` + `3c80236`). Push pending — user-controlled.

⚠️ **TBC account temporary block** (Stage 3 verify blocker):
- Cause: SDK SOAPAction URI was undocumented in available materials → discovered via probing (`http://www.mygemini.com/schemas/mygemini/GetAccountMovements` confirmed correct, body wrapper `GetAccountMovementsRequestIo`, body field `accountMovementFilterIo` with `pager`/`accountNumber`/`accountCurrencyCode`/`periodFrom`/`periodTo`)
- Wrong-attempts triggered TBC auto-block ("User is currently blocked")
- Auto-unblock typically 15-30 min, OR call TBC support
- After unblock: fresh DigiPass code → run `conn.fetch_movements(date(2026,3,1), date(2026,3,3), nonce='<9-digit OTP>')` → verify 104 records / 9,641.40 dbt / 9,994.94 crd / per-ID match vs `2026.xlsx` sheet `GE90TB7793336020100005-GEL`

**Pipeline integration (BOG + TBC + rs.ge) NOT yet wired in** — connectors standalone, ready when user approves wire-in strategy.

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

## 4. ღია სამუშაო — შემდეგი session (priority order)

1. **TBC Stage 3 verification** (BLOCKED until TBC account auto-unblocks, 15-30 min):
   - Wait for auto-unblock OR user calls TBC support
   - Get fresh DigiPass nonce from user (PIN 0777 → 9-digit OTP, ~5-15 min validity)
   - Run: `from dashboard_pipeline.tbc_bank_connector import TBCBankConnector; from datetime import date; conn = TBCBankConnector(); movs = conn.fetch_movements(date(2026,3,1), date(2026,3,3), nonce='<OTP>')`
   - Verify: 104 records, debit 9,641.40, credit 9,994.94 — per-ID match vs `2026.xlsx`
   - **DO NOT** retry-storm the TBC SOAP if first attempt fails — investigate offline first to avoid re-block
   - SDK URI confirmed: `http://www.mygemini.com/schemas/mygemini/GetAccountMovements`, wrapper `GetAccountMovementsRequestIo`

2. **Wire-in strategy decision** (user picks): live SOAP only / SOAP+XLSX augment / SOAP-current+XLSX-history (recommended — analog rs.ge Sprint A)

3. **Pipeline wire-in** (separate sprint, user approval): replace `Financial_Analysis/{bank}/*.xlsx` consumption in `bank_reconciliation.py` with live API fetch — TBC + BOG + rs.ge all share the same `to_xls_dataframe()` drop-in pattern

4. **rs.ge Sprint A follow-ups** (carryover from morning):
   - SOAP run for 26 SOAP_PENDING orphan TINs (~5 min) → updates `Financial_Analysis/orphan_resolver_review_2026-05-04.xlsx`
   - User reviews orphan Excel and applies 4,647 mappings via MegaPlus UI
   - Pipeline integration of `rs_waybill_connector` (separate Sprint, user approval)

5. **Push** — 3 local commits ahead of origin/main (`a5b88c8`, `4c14920`, `3c80236`)

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
