# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-14 — **HOME-7 SHIPPED + COMMITTED** (`e64ea2e`). Owner-led Home page audit + 3 bugs fixed + Real Net Profit expandable rows. April bank OUT reconciliation verified: headline 159,682.38 ₾ = category sum 159,682.38 ₾ (DIFF 0.00 ₾).
>
> **წინა session** (2026-05-13 ღამე): HOME-6 — Real Net Profit + lag-fix v2 + cash journal in P&L → commit `d4ae56b`. Full HOME-1 / HOME-3 / Cashiers detail → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-12_2026-05-13.md`.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-14) — HOME-7: Home page audit + 3 bugs + Real Net Profit drill-down

### Headline

Owner asked for thorough review of Home page since "ყოველ დღე მასზე ვარ დამოკიდებული". Audit found 5,700 ₾ silent drift (headline 159,682 ≠ category sum 165,382 in April bank OUT). Identified 8 findings (3 bugs + 5 UX). All 3 bugs fixed + 3 UX improvements + 1 new feature shipped in commit `e64ea2e`. Memory: `project_home_page_audit_2026-05-14.md`.

### What shipped

**Bug 1 — bank vs cash split in OUT categories.** Pipeline `daily_money_flow.py` exposes `salary_bank` / `rent_bank` / `owner_withdraw_bank` / `service_bank` / `refund_bank` / `unmatched_suppliers_bank` (computed already since HOME-5, not exposed before). Home.jsx bank OUT section now uses `*_bank` totals + filters items by `bank !== 'ნაღდი'`. Real Net Profit keeps full `op_salary` etc. (label clarified: "ბანკი + ნაღდი"). `owner_withdraw_bank` further reduced by samurneoInternal in JS. Reconciliation verified live: April headline 159,682.38 = UI category sum 159,682.38 (DIFF 0.00 ₾).

**Bug 2 — stale "~2,500 ₾" hardcoded warning replaced with live cash residual.** New `agg.cash_residual = cash_megaplus − (tbc.cash_deposit + bog.cash_deposit) − cash_journal_total − true_out_cash_expenses`. April: +5.45 ₾ → page shows "✓ ნაშთს ემთხვევა". If |residual| > 50 ₾, shows actual unrecorded/over-logged amount. Only displayed in multi-day period mode.

**Bug 3 — owner_withdraw items reconciled with headline via expandedNote.** New `expandedNote` prop on `OutItemsExpandableRow` renders amber note above items table when samurneo netting applies. April: "ცხრილში ჯამი 7,750 გამოვა — აქედან 4,850 შიდა გადარიცხვაა (BOG → TBC სამეურნეო), რეალურად შენ მიიღე 2,900". Same note added to Real Net Profit owner row.

**UX 5 — "სხვა" row now expandable** in bank OUT section.

**UX 8 — Foodmart cashback now inside BOG expand.** `BankExpandableRow` accepts new `cashback` prop, header total includes it (62,002 POS + 5,605 cashback = 67,608 BOG total). Top-level standalone cashback row removed.

**NEW: Real Net Profit expandable rows.** Owner asked "შეგვიძლია ჩანართები რომ გავუკეთოთ ხელფასები ვისთან გავეცი". New `ProfitExpenseRow` component — clickable, shows partner + bank badge + amount on expand. Categories: salary / rent / owner / service / refund. Tax + bank fees stay non-clickable (no items). Owner row includes samurneo netting explanation.

**Auto-resolved + deferred:** UX 4 + UX 7 became moot after Bug 1 (cash items filtered out of bank section). UX 6 (per-bank OUT split TBC/BOG) deferred — can add later if owner asks.

### Files changed (committed in `e64ea2e`)

- `dashboard_pipeline/daily_money_flow.py` (+6 lines — `*_bank` field exposure)
- `rs-dashboard/src/Home.jsx` (+208 / -43 lines — Bug 1/2/3 + `ProfitExpenseRow` + `BankExpandableRow.cashback` prop + `OutItemsExpandableRow.expandedNote` prop)

### Open / next-session candidates

Owner's recommendation request for future sessions — I proposed top 3 next-priority additions:

1. **HOME-2 bank balance KPI** — parquet has ნარჩენი column; extract last line per account → real-time bank position on Home top.
2. **Cash-till balance per store** — cash sales − bank deposits − cash journal → physical cash on hand per shop.
3. **Due-payments next 7 days widget** — upcoming AP from waybill terms.

Lower priority (deferred): margin warning, missing-waybill alerts, year-over-year comparison, mfl_owner running total, break-even mid-month indicator. UX 6 per-bank OUT split.

Other candidates: May reconciliation analogous to April (partial month, mid-month). March reconciliation (likely more discrepancies).

### Verification commands (next session)

```powershell
# HOME-7 audit verify — April category sum matches headline (DIFF must be 0.00 ₾)
"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -c "
import urllib.request, json
api = json.loads(urllib.request.urlopen('http://localhost:8000/api/data?tab=daily_money_flow', timeout=60).read())
idx = api['daily_money_flow_index']
days = [d for d in idx if d.startswith('2026-04')]
out_total = sum(idx[d]['out']['bank_total'] for d in days)
salary_bank = sum(idx[d]['out'].get('salary_bank', 0) for d in days)
owner_bank = sum(idx[d]['out'].get('owner_withdraw_bank', 0) for d in days)
print(f'April OUT headline: {out_total:.2f} GEL')
print(f'  salary_bank: {salary_bank:.2f}')
print(f'  owner_withdraw_bank: {owner_bank:.2f}')
# Expected: headline 159,682.38; *_bank fields present alongside full bank+cash totals.
"
```

---

## ისტორიული session-ები — გადატანილია არქივში

- 2026-05-12 → 2026-05-13 (HOME-1 / HOME-3 / Cashiers detail) → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-12_2026-05-13.md`
- 2026-05-05 → 2026-05-11 → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-05_2026-05-11.md`
- წინა ისტორია: `CONTEXT_HISTORY_2026-04_2026-05-02.md` + `CONTEXT_HISTORY_2026-05-03_2026-05-04.md`

---


## 1. წინა Sprints — დახურული (commit pointers only, full evidence in git log)

| Sprint | რა | Commit(s) |
|---|---|---|
| **A — BOG pipeline wire-in** (2026-05-05 ღამე) | 8 surgical edits, BOG cache exclusive read; +11,312 POS lines / +109k ₾ bonus depth | `c4fd1c6` |
| **B — rs.ge pipeline wire-in** (2026-05-06) | 7 surgical edits, RSGE cache exclusive read; +70 May 2026 waybills / +9,109.42 ₾ bonus depth | `eba02cf` (cache) + `de55942` (wire-in) |
| **Earlier** — TBC/BOG/rs.ge connectors PROOFED + 2 bug fixes | TBC `debitCredit` 0/1 (not 1/2); BOG ID-float trailing `.0` `_g_str()` fix | `52de7ba` / `bf8d204` / `dc2f9de` (rs.ge), `4c14920`+`a7f4ea9` (BOG), `3c80236`+`ace7d9f` (TBC), `a5b88c8` (governance) |

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

## 2. TBC DBI verified facts (Stage 3 PROOFED 2026-05-07)

**Status**: ✅ Stage 0/1a/1b/2/3 PROOFED. Pipeline wire-in CLOSED — see §0.

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

## 4. ღია სამუშაო — შემდეგი session

**All bank-refresh sprints CLOSED:**
- Sprint A (BOG wire-in) `c4fd1c6` · Sprint B (rs.ge wire-in) `eba02cf` + `de55942` · Sprint C ცენტრი (TBC wire-in) `c8aea4b` + `0e8c816` · Sprint C step 6 Phase 1 (backend orchestrator) `31bb1ab` · Sprint C step 6 Phase 2 (UI) `b9f44ba`.

**MegaPlus mapping Sprint — Part 1 CLOSED (2026-05-05 დღე გაგრძელება):**
- ✅ Live MegaPlus DB query architecture — `f318cad` · `0ab6000` · `e75643b`
- ✅ BONUS „დუბლიკატები" tab — `abb41dd`
- 🔴 **Part 2 — Alias UI redesign STILL OPEN** (scope: `HANDOFF_ARCHIVE/PREVIEWS/SUPPLIER_ALIAS_REDESIGN_2026-05-05.md`).

### Next-session candidates

1. 🔴 **Alias UI redesign** (Part 2 of MegaPlus mapping Sprint) — top priority.
   Decouple `/api/aliases/confirm` validation from `data.json.retail_sales.by_product` truncation. Reduce dashboard top-line to 20-30 best sellers. Move alias confirmation into per-supplier drill-down. Estimate 1-2 sessions.

2. 🆕 More MegaPlus data-quality tabs (continuing the pattern). User noticed phantom-stock issue mid-session — there may be more (e.g., price-change history anomalies, fictitious stock on closed accounts, etc.). Ask user explicitly.

3. 🚨 0c — MAX vendor-tag file integration (`Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls`, 116 suppliers, დვაბზუ only). 3 paths still on the table.

**rs.ge Sprint A carryover (non-blocking, USER-ONLY work — agent-side complete):**
- ✅ SOAP for 26 SOAP_PENDING orphan TINs — DONE.
- 🟡 User-only: apply 4,647 RS_CODES mappings + remaining SOAP mappings via MegaPlus UI. As of 2026-05-05 დღე live count: ოზურგეთი 23 SOAP-products already cleared (vs xlsx 2026-05-04 baseline), დვაბზუ 3 still pending. „შეუსაბამო პროდუქცია" ჩანართი now shows the live remaining list.

---

## 5. Active open work (carryover from earlier sprints)

| # | task | size | risk |
|---|---|---|---|
| 🟡 **Megaplus სალარო Session 2 (frontend) — Session 1 backend DONE 2026-05-08 ღამე** | PnL.jsx-ში 15 callsite-ი `m.total?.pos_income`-ზე — გადასვლა `total_income`-ზე + ცალკე row „ნაღდი ფული". სხვა ფაილები: Forecast.jsx, Executive.jsx, Insights.jsx, DebtPlan.jsx, App.jsx. Backend რიცხვები სწორია (cash 5.48M, parity 15/15). | 0.5–1 session | LOW |
| 🟡 **COGS detachment (followup of Megaplus wire-in)** | `total_expenses` ისევ შეიცავს supplier payments-ს, ამიტომ net_margin −3.36%-ია. რეალურ P&L-ში supplier payment = COGS, არა ცალკე ხარჯი. გამოყოფა: (a) `bank_reconciliation.matched_high` lines-ის expense ბუნდლიდან გამორიცხვა, (b) financial_ratios-ში `cogs` ცალკე ფიგურა. | 1-2 sessions | MEDIUM |
| 🟡 **vat_reconciliation pre-synthesis bug (NEW 2026-05-08 ღამე)** | `vat_reconciliation.by_month[].max_pos_ge = 0` ყველა თვისთვის, რადგან `compute_vat_reconciliation` ცარიელ `retail_sales_bundle`-ს იღებს — synthesis მოგვიანებით ხდება (`generate_dashboard_data.py:1645` რბის `:1842`-მდე). გამოსავალი: ან synthesis ადრე გადავიტანოთ, ან vat-ი ხელახლა გადავთვალოთ. | ~30 წთ | LOW |
| 🟡 **AI strategic interview answers (NEW 2026-05-07 ღამე)** | User უპასუხებს AI-ს 10 კითხვას (ნაღდი ფული, decision-maker, ჯიდიაი ხასიათი, AP days სტრატეგია, სეზონი, ვასაძე dependency, customer base, წითელი ხაზი). შემდეგ პასუხები სტრუქტურდება ფაილში (TBD: `Financial_Analysis/MY_BUSINESS.md` ან `dashboard_pipeline/ai/business_context.py` module). Inject system prompt-ში. სრული ლისტი → §0 above. | ~1 session | LOW |
| 🟡 **Telegram bot ფონური სერვისი (NEW 2026-05-07 ღამე)** | Currently runs as standalone Python process (`telegram_bot.py`). Process restart needed after each reboot. NSSM second service ან systemd unit. ⚠️ Bash on Windows quirk spawned 2 instances ერთდროულად — race-ის თავიდან ასარიდებლად single-instance enforcement (lock file ან existing-process check) | ~30-60 წთ | LOW |
| 🟡 **xfail-cleanup carryover (NEW 2026-05-08)** | 26 incremental-cache tests xfail-marked because Sprint A/B/C parquet wire-in broke their fixtures. `collect_*` funcs (bank_income / pos_terminal / tax_flow / samurneo) now read from `Financial_Analysis/cache/` parquet, but fixtures only redirect XLSX. Real fix = parametrize cache root in `bank_income`, then unmark. Files: `test_pos_terminal_income_incremental.py` (9), `test_samurneo_incremental.py` (7, file-level), `test_tax_flow_incremental.py` (7), `test_tbc_pos_terminal_matching.py` (3). | ~1-2 sessions | LOW (ფარავს რეალურ regression-ს) |
| 🔴 **alias UI redesign — STILL OPEN (Part 2 of MegaPlus mapping Sprint)** | Smoke-test 2026-05-05 exposed: `retail_sales.by_product` truncated to top 1000 of 8 460; `/api/aliases/confirm` validates against this slice, so candidates outside top-1000 are rejected. Fix path: (a) decouple alias-confirm validation from the truncated dashboard slice (consult full retail universe), (b) reduce dashboard top-line to 20-30 best sellers, (c) move alias confirmation into per-supplier drill-down. 5 known smoke-test targets: კორიდა / აროშიძე / თისო / ექსტრამითი / გი-შო+ — only თისო (codes 1050, 1066) validates today. | 1-2 sessions | LOW |
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
| Dashboard tabs | 18 (16 + ⚠️ შეუსაბამო პროდუქცია + 👥 დუბლიკატები — both added 2026-05-05 დღე) |
| `data.json` | 116.00 MB (2026-05-08 build, public · dist not mirrored — pre-Session-1 stale) |
| Local branch | `main`, working tree clean post-HOME-7 commit `e64ea2e` |
| Cache state | BOG: 171,869 rows (2023-2026) · rs.ge: 22,408 rows (2022-2026, last refresh 2026-05-05 14:52, no 2026-05-06 yet) · TBC: 50,924 rows (2023-2026, dedup by `ტრანზაქციის ID`) |
| MegaPlus DB integration | LIVE — 53 tables / 282+308 suppliers across 2 stores / 720K active orders / 2024-03 → 2026-04 |
| MegaPlus watch folder layout | `Financial_Analysis/მეგაპლიუსის არქიტექტურა/{დვაბზუ,ოზურგეთი}/` (legacy `მეგა პლუს backup*` glob still supported) |
| MegaPlus orphan products (live 2026-05-05) | 4 925 ცალი / 685 805 ₾ · დვაბზუ 2 480 (97.9% resolved) · ოზურგეთი 2 445 (91.9% resolved) |
| MegaPlus duplicate barcodes (live 2026-05-05) | 3 401 დუბლიკატი (1 525 დვაბზუ + 1 876 ოზურგეთი) · 36 phantom-stock = 6 787 ცრუ ერთეული = 8 899 ₾ sell-basis |
| Margin status (2026-05-08 ღამე) | `total_income=5.48M` (ბანკის ბარათით 2.04M + Megaplus ნაღდი 3.44M) vs `total_expenses=5.66M` (still incl. supplier payments) → `net_margin=−3.36%`. სრული გამოსასწორებლად საჭიროა COGS detachment (იხ. §5). |
| Live API endpoints (post-2026-05-07) | `/api/data?tab=orphan_products` · `/api/data?tab=duplicate_products` · `POST /api/orphan-products/status` · `POST /api/suppliers/archive` · `POST /api/chat` · `POST /api/banks/refresh` (all rate-limited) |
| Persistent state files | `Financial_Analysis/orphan_soap_cache.json` (TIN→name, ~2 entries) · `Financial_Analysis/orphan_user_status.json` (ignored map, currently empty) · `Financial_Analysis/supplier_archive.json` (archived suppliers, currently empty — NEW 2026-05-07) |
| Telegram bot | `@ioli_market_ai_bot` (id=8724250734), allowed_chat_id=6805108691, runs via `python telegram_bot.py`, offset cursor `.telegram_bot_offset.json` (gitignored). Standalone process — needs manual start after reboot. NSSM service deferred (see §5) |
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
