# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-15 — **HOME-9: 10-ბაგ-batch + bookkeeping review.** 12 commit pushed (`1948676` ბოლო). სერვისი გადატვირთული, freshness API ცოცხალია.
>
> წინა: 2026-05-14 ღამე HOME-8 (bank balance + cash-till + freshness) `b85225c` + agent baseline `fee78c6` + handoff `a84f2fe`.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-15) — HOME-9: 10 ბაგი + bookkeeping review

### Headline

Owner-მა Home გვერდი თვალით გადახედა და მოგვცა 10 ცდის სია (8 confirmed + 2 verify). შემოწმდა → ცხრიდან 9 ნამდვილია, ერთს მცირე ნიუანსი ჰქონდა. დახურა მთლიანი batch ერთ სესიაში — 9 fix-commit + 1 gitignore commit + უკვე ლოკალურად მზადებული cash-till drill-down commit. push origin-ში გავიდა, სერვისი გადატვირთული. ბოლოს — bookkeeping perspective review: 60% აქვს, 10 ფუნდამენტური field აკლია.

### რა shipped — commit by commit

| # | Commit | რა გავაკეთე |
|---|---|---|
| — | `28e5966` | **Pre-existing cash-till drill-down** — წინა სესიის uncommitted work: per-store sales_lines / deposit_lines / cash_expense_lines + lag-shift (`_infer_sales_date`) + ოზურგეტი typo + supplier name_map. Home.jsx-ში CashTillRow component + expand/collapse tables. manual_payments_journal.csv: 2 ახალი backdated April row (TIN 206335223). |
| #1+#8 | `b4f520a` | **ფუტერი + freshness dot.** Home.jsx:2198 — წავშალე ძველი "HOME-2 placeholder" ბლოკი. Home.jsx:1056 — `Math.max` → `Math.min` ბანკის წერტილზე (ცარიელი ბანკი აღარ იმალება). |
| #7 | `7c627ef` | **freshness API partial flag.** `/api/freshness` ცარიელ მხოლოდ `last_backup_date`-ს აბრუნებდა; ახალი `last_complete_day` + `partial:bool` — cashier_hour_breakdown-დან hour ≥ 22 რულით. |
| #3 | `36d1e90` | **Unattributed cash deposits visible.** 2 ₾ Apr 8 row-ი totals.unattributed_deposit_lines-ში იყო მაგრამ Home-ში არ რენდერდებოდა. ახალი ⚠️ amber CashTillRow ცხრილით (date / bank / purpose / amount). |
| #4 | `16edee0` | **Unconditional lag-shift in daily_money_flow.** ძველი ვერსია 20% amount-match guard-ით → partial deposits unshifted რჩებოდა (e.g. Apr 1 ოზურგ 648.50 ₾ inflated April). ახლა cash_till.py-ის ანალოგია: დვაბზუ -1 day, ოზურგეთი Mon→Fri (-3 days), სხვა -1 day. |
| #5 | `b728d0c` | **Refund-in excluded from headline.** `REFUND_IN_PATTERN = r"შეცდომით ჩარიცხული\|უკან დაბრუნება\|დაბრუნებული თანხა"`. Detection-ი bank_in_total-ის accumulator-ის წინ ხდება; payload-ში refund_in / refund_in_tbc / refund_in_bog / refund_in_items გამოეცა. e.g. Apr 1 1,090.69 ₾ აღარ ჯდება "ბანკში შემოვიდა"-ში. |
| #6 | `6dfe2da` | **Return waybill store flip.** rs.ge return-ის "მიწოდების ადგილი" = მომწოდებლის სასაწყობო; "ტრანსპორტ. დაწყება" = ჩვენი. is_return → flip to origin. Updated: generate_dashboard_data.py (waybills_data + _build_supplier_waybill_lines) + api_contracts.py fallback. e.g. April 88/95 returns აღარ ვარდება "გაუნაწილებელი"-ში. |
| #2 | `3e45894` | **Cancelled waybill count.** `effective_amount` = 0 cancelled-ისთვის (sum სწორი), მაგრამ `len(wbs_regular)` cancelled რომ ითვლიდა. ფილტრი `status != "გაუქმებული"` დაემატა wbs_today-ის შემდეგ. April 2026 5 ცალი ნაკლები. |
| #9 | `0d7ef80` | **cash_till last_complete_day cap.** Window-ის ბოლო Megaplus-ის partial day-ს არ უნდა გადააცილებდეს — lag-shift-ი ცარიელ Megaplus-day-ზე ბანკის სრულ deposit-ს ხატავდა (e.g. May 13: sales 1,789, deposits 3,623 = -1,834 phantom). compute_cash_till(..., last_complete_day=) param, server.py-ში min across stores-ით კალკულირდება. |
| — | `1948676` | **.gitignore** — Playwright MCP home-*.yml snapshots (machine-local). |

### Files touched (delta from `a84f2fe`)

```
.gitignore                              | + 4
dashboard_pipeline/api_contracts.py     | + 14 / - 3
dashboard_pipeline/cash_till.py         | + 144 / - 38  (drill-down + last_complete_day)
dashboard_pipeline/daily_money_flow.py  | + 65 / - 30   (#4 + #5 + #2)
generate_dashboard_data.py              | + 19 / - 9    (#6 origin flip)
rs-dashboard/src/Home.jsx               | + 240 / - 16  (CashTillRow + unattributed + freshness)
server.py                               | + 60 / - 1    (cash-till name_map + freshness + last_complete_day)
Financial_Analysis/manual_payments_journal.csv  | + 2 rows (owner backdated)
```

### Verification done

- service restart via `/restart-service` skill — HTTP 200 ✓
- `/api/freshness` ცოცხალი: ორივე მაღაზია `partial: true`, `last_complete_day: 2026-05-12`, `last_backup_date: 2026-05-13` ✓
- cash_till cap smoke test: window May 1-15 no-cap till=12,115; cap=2026-05-12 till=12,150 ✓
- syntax check: 3 .py ფაილზე `ast.parse` ✓
- Home browser render: page loads, all sections present ✓

### ⚠️ STILL OPEN — Pipeline regen საჭიროა

ცვლილებები #2, #4, #5, #6 **data.json-ს ცვლის**, მაგრამ pipeline regen ჯერ არ გავუშვი. ბრაუზერი ცარიელ data.json-ს ხედავს. user-ისთვის step:

```
Home → "ხელახლა გათვლა" ღილაკი (5-10 წთ) → F5 ბრაუზერში
```

### Bookkeeping review (post-fixes) — 10 ფუნდამენტური ხარვეზი

Owner-მა მოითხოვა Home გვერდის ბუღალტრული შეფასება. ვერდიქტი: **60% აქვს**.

**კარგად ცოცხალია:** ნავაჭრი, COGS, ბრუტო მოგება, ხელფასი, ბანკის საკომისიო, სალაროს მოძრაობა per-store, ბანკის ნაშთები, ნაღდი მომწოდებლისთვის, ზედნადებები (in/return).

**ცარიელია (next-session candidates):**

1. **AP headline** — რამდენი გვმართებს ჯამში დღეს (ბუღალტრის #1 კითხვა). data.json-ში არსებობს `supplier_aging`, მაგრამ Home-ზე ცარიელია.
2. **Inventory value** — საქონლის ნაშთის ფასი თარეშოზე. Megaplus DB-ში ცოცხალია, Home არ ცდის.
3. **Tax obligations** — დღგ/საშემოსავლო/საქონლის: რა გვერიცხება + რა გადავიხადეთ. VAT tab არსებობს, Home headline ცარიელია.
4. **Rent (იჯარა)** — თვის ფიქსირებული. daily_money_flow აქ `rent_out` ცდის, Home-ის Real Profit-ში drill-down გვაქვს, magrამ თვის ჯამის headline ცარიელია.
5. **Utilities (კომუნალურები)** — დენი/წყალი/ინტერნეტი თვის ჯამი. იგივე — drill-down გვაქვს, headline არა.
6. **Owner withdraw** — დივიდენდი ან მფლობელის გატანა თვის ცხრილი.
7. **Net liquidity** — ბანკი + სალარო + AP (−) = რეალური ფინანსური მდგომარეობა ერთ ციფრად. ცარიელია.
8. **MTD ცხრილი** — დღევანდელი vs თვის ციკლი. ბუღალტერი თვის ჩარჩოს ცდის; Home "დღევანდელ"-ს ცდის.
9. **Margin %** — ბრუტო/წმინდა მარჟა ფარდობით, არა მხოლოდ ლარით.
10. **Refund-in display** — #5 commit-ი payload-ში გადმოაქცია `refund_in_items`, Home-ში არ რენდერდება.

**Plus:** დროის კონტექსტი ერევა — Home ცდის ერთდროულად: დღევანდელ ნავაჭარს, 1-12 მაი სალაროს, ცოცხალ ბანკის ნაშთს, დღევანდელ ზედნადებებს. ბუღალტერი ვერ ცდის „მაისში როგორ მივდივართ?"-ს ერთი ხედვით.

### User's state

- Owner თქვა: „დღეს მეყო ძალიან გადავიტვირთე". სესია დახურა.
- Bookkeeping review-ის გაგრძელება მომდევნო სესიაში.

### Next-session candidates

1. **Pipeline regen + browser verify** — user step, არ მოითხოვს ჩემს ჩარევას.
2. **AP headline + Net liquidity card** — ბუღალტრის #1 + #7. ერთ KPI ცხრილში: ბანკი + სალარო + AP. ~1-2 ჰ.
3. **MTD layout რეფაქტორი** — Home time-context unification. დიდი UI ცვლილება.
4. **Tax + Inventory headlines** — VAT-tab/Megaplus DB-დან headline-ის ამოღება.
5. **Refund-in display** — payload უკვე გადმოაქცია, UI რენდერი მცირე.

---

## 0a. წინა session (2026-05-14 ღამე) — HOME-8: bank balance + cash-till + freshness + agent quality

### Headline

Owner asked "ჩემ პროექტის მთავარ გვერდზე როგორი სიზუსტეა და რა დასამატებელია". 4 verification agents (bank-reconciler, megaplus-verifier, waybill-auditor, spot-checker) ran on May 1-12 — all 4 Home KPIs verified 1:1 against live sources (revenue 76,764.55 ₾, COGS 63,939.75, cashback 7,300.23, real_net_profit 8,865.76 ₾). Then shipped 3 new Home additions + cleaned up data quality issue.

### What shipped — commit `b85225c`

**1) Bank balance KPI (TBC + BOG)** — replaces "HOME-2" placeholder on Home top.
- **BOG**: REST `GET /api/accounts/{account}/{currency}` → `{AvailableBalance, CurrentBalance}`. No OTP. Already tested live: 781.28 ₾.
- **TBC**: SOAP `GetAccountStatement` (NEW envelope, separate from existing `GetAccountMovements`). Critical gotcha discovered during debugging: filter element name is `<filter>`, NOT `<accountStatementFilterIo>` (confirmed against TBCBank/TBC.OpenAPI.SDK.DBI source: `IStatementAdapter.cs` shows `public ... filter;` field name). Uses same DigiPass OTP that the movements fetch consumes — nonce reuse works within validity window. Verified live 2026-05-14: 215.20 ₾ closing balance, 230.95 ₾ opening.
- New module `dashboard_pipeline/bank_balance.py` — orchestrator + JSON cache at `Financial_Analysis/cache/bank_balance.json`. Called as "Phase C" of `_run_bank_refresh` after BOG/TBC runners succeed. Failures logged but don't fail the refresh.
- New endpoint `GET /api/bank-balance`. Home.jsx fetches on mount + `reloadKey`.

**2) Cash-till per store** — new section on Home (below KPI cards, above Real Net Profit).
- New module `dashboard_pipeline/cash_till.py`. Period-aware (uses Home picker; defaults last 14 days).
- Per-store: `cash_sales` (Megaplus cashier_day_breakdown) − `cash_deposits` (bank parquet rows where `დანიშნულება` contains "ნავაჭრი" + store name). NB: my first regex `ნავაჭრის ჩარიცხვა` matched nothing; actual text is bare stem `ნავაჭრი` — fixed.
- Total row also subtracts `cash_supplier_paid` (manual_payments_journal.csv, active rows in window) — surfaced as separate line because no per-store attribution available.
- New endpoint `GET /api/cash-till?from=YYYY-MM-DD&to=YYYY-MM-DD`. `from` is read off `request.query_params` directly (Python reserved word).
- Live May 1-12: დვაბზუ +2,912.98 ₾, ოზურგეთი +5,208.08 ₾, supplier_paid 30,516.90 ₾ post-cleanup, real_till_change −22,395.84 ₾.

**3) Data freshness badge** — small line under Home title with bank/Megaplus dot+timestamp.
- New endpoint `GET /api/freshness` — reads `cache/.last_refresh.json` + per-store `_megaplus_state.json`. Returns `{banks, megaplus}` with timestamps.
- Frontend renders color dot per source: green <6h, amber 6-24h, red >24h.

**4) Manual payment date picker** — `SupplierModal.jsx` + `Suppliers.jsx`.
- Old code hardcoded `date: new Date().toISOString().slice(0, 10)` (always today). Now `payDate` state with default = today, `max` = today, sent in POST body.
- This stops future bulk-entries from defaulting to "today" instead of actual payment date — root cause of the cleanup below.

**5) Data cleanup — 68 backfill rows re-dated.** `manual_payments_journal.csv`: bulk entries from 2026-05-08 with comment="ბრაუზერიდან" (48,889 ₾ across 68 suppliers, entered by owner in one ~30-minute session on May 8) re-dated to 2025-12-31. Comment updated to "ბრაუზერიდან · backfill (იყო 2026-05-08, რეალური თარიღი უცნობია)". Backup at `Financial_Analysis/_backups/manual_payments_journal_pre_redate_20260514_173918.csv`. These were silently inflating cash-till `supplier_paid` to 79,406 ₾ (~−71k real till change).

### What shipped — commit `fee78c6` (earlier same session)

**spot-checker agent — Step 2 (project-context awareness).** First-ever comprehensive test of all 7 sub-agents launched 4+4 in parallel on April 2026 verification tasks. 6 agents ⭐⭐⭐⭐⭐, spot-checker ⭐⭐⭐ — math correct but called the documented samurneo BOG↔TBC netting (`Home.jsx:783-790`, 4,850 ₾ in April) a "stale claim" because it never read project memory or the JSX UI logic. Fix: added explicit "Step 2 — Project context awareness" + forbidden-behavior bullet that blocks drift/FAILED verdicts before searching memory + `.jsx`. Re-tested same claim → now returns ✅ PROOFED with explicit citation of `project_samurneo_internal_transfer.md` + `Home.jsx:789-790`. Memory: `project_agent_quality_baseline_2026-05-14.md`.

### Files changed today (both commits)

`fee78c6`:
- `.claude/agents/spot-checker.md` (+25 / -6)

`b85225c`:
- `dashboard_pipeline/bank_balance.py` (NEW, 122 lines)
- `dashboard_pipeline/cash_till.py` (NEW, 175 lines)
- `dashboard_pipeline/bog_bank_connector.py` (+24 — `fetch_balance` method)
- `dashboard_pipeline/tbc_bank_connector.py` (+101 — `fetch_balance` + `_build_balance_envelope` + `_parse_balance`, plus `_post` accepts `soap_action` param)
- `server.py` (+106 — 3 new endpoints + balance fetch in Phase C of refresh)
- `rs-dashboard/src/Home.jsx` (+181 — bank-balance KPIs, freshness badge, cash-till section, 3 new state hooks + effects)
- `rs-dashboard/src/SupplierModal.jsx` (+13 — date picker)
- `rs-dashboard/src/Suppliers.jsx` (+14 — date picker)
- `Financial_Analysis/manual_payments_journal.csv` (68 rows re-dated)

### Open / next-session candidates

1. **Push to origin** — branch is 2 commits ahead (`fee78c6` + `b85225c`). User has not explicitly authorized push yet.
2. **Verify HOME-8 in browser** — owner needs to refresh, see KPI cards + cash-till + freshness badge, sanity-check the numbers.
3. **3 remaining May cash payments** to investigate:
   - 2026-05-09 TIN 400029036 → 14,065 ₾ (largest, possibly real)
   - 2026-05-09 TIN 420424393 → 5,028 ₾
   - 2026-05-10 TIN 204920381 (ELIZI) → 1,605.40 ₾
   These were NOT re-dated; user should confirm they're real same-day payments or also backfill.
4. **Per-store attribution for cash supplier payments** — currently the supplier_paid total is "shared" because journal has no store column. Feature gap acknowledged in UI footer.
5. **#3 of original 3 recommendations (Due-payments next 7 days widget)** — deferred to ზედნადებები page per owner's instruction ("რთულია, ცალკე გადავდოთ").
6. **Max effort persistence on new terminal** — `env.CLAUDE_EFFORT=max` added to `~/.claude/settings.json` but user reported it still shows "xHigh effort (default)" on new terminals. Memory `user_max_effort_preference.md` updated with what was tried; needs more investigation if owner asks again. The owner said "აღარ ვიწვალოთ" — deferred.

### Verification commands (next session)

```powershell
# HOME-8 verify — live bank balances + cash-till
curl -s http://localhost:8000/api/bank-balance | python -m json.tool
curl -s "http://localhost:8000/api/cash-till?from=2026-05-01&to=2026-05-12" | python -m json.tool
curl -s http://localhost:8000/api/freshness | python -m json.tool

# Expected (as of 2026-05-14 ღამე):
#   /api/bank-balance: bog.current=781.28 GEL, tbc.closing_balance=215.20 GEL
#   /api/cash-till: real_till_change -22395.84, supplier_paid 30516.90
#   /api/freshness: banks.{bog,tbc,rsge}.last_completed_at ~ 2026-05-14 12:59 UTC,
#                   megaplus.{დვაბზუ,ოზურგეთი}.last_backup_date = "2026-05-12"
```

---

## 0b-prev. წინა session (2026-05-14 დილა) — HOME-7: audit + 3 bugs

5,700 ₾ silent drift in April bank OUT (headline 159,682 ≠ category sum 165,382). 8 findings (3 bugs + 5 UX); all 3 bugs fixed + 3 UX + Real Net Profit expandable rows. Commit `e64ea2e`. Memory: `project_home_page_audit_2026-05-14.md`.

Key fixes:
- Bug 1: `daily_money_flow.py` now exposes `salary_bank` / `rent_bank` / etc. so Home.jsx bank OUT section uses bank-only totals (was bank+cash mixed).
- Bug 2: hardcoded "~2,500 ₾ აღურიცხავი" replaced with live `agg.cash_residual` calc. April result: +5.45 ₾ → "✓ ნაშთს ემთხვევა".
- Bug 3: `expandedNote` prop on `OutItemsExpandableRow` for samurneo netting clarification on owner_withdraw items.
- NEW: `ProfitExpenseRow` component in Real Net Profit section — expandable salary/rent/owner/service/refund rows showing partner + bank badge.

Deferred: UX 6 (per-bank OUT TBC/BOG split completeness). Open candidates as proposed → 3 of them got built in HOME-8 above (bank balance, cash-till, freshness).

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
