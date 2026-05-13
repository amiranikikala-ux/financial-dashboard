# Sprint HOME — მთავარი გვერდი (Owner's Daily Cockpit) — Preview

**Status:** `PREVIEW · NO CODE CHANGE`
**Date:** 2026-05-12
**Target sprint:** Sprint HOME — split into 3 phases (HOME-1 / HOME-2 / HOME-3)
**Author note:** Owner needs a single dashboard page that opens FIRST when he logs in. From it he must "see the real picture" of the business in seconds. Industry analog: Square's Home, Lightspeed dashboard, Shopify Overview.

---

## TL;DR

Owner wants the dashboard's first tab to be a daily-overview "cockpit" with 5 blocks:
**(1)** stores comparison (cash/card per store today + period),
**(2)** cash from till vs cash that hit the bank (variance alert),
**(3)** 3 headline KPIs at the top (today's revenue / today's profit / current bank balance),
**(4)** money in/out today (incoming vs outgoing),
**(5)** today's waybills list.

Pipeline data audit shows: **3 of 5 blocks ship with no new pipeline work** (blocks 1, 3 partial, 5). **2 blocks need pipeline additions** (block 2 = cash-deposit detection rule; block 4 = daily expense rollup). Bank-balance exposure is a 1-hour delta. Total pipeline work ~7-8 hours; frontend page ~6-8 hours. Recommendation: split into **3 sequential sprints**, each independently shippable, so owner gets value early and we don't bundle blast radius.

---

## Inventory — რა გვაქვს ხელთ (verified by file audit)

### Backend (pipeline / API)

| Source | რა აქვს | სად |
|---|---|---|
| `retail_sales.daily_trend[]` | per-day: `day`, `lines`, `receipts`, `revenue_ge`, `cost_ge`, `profit_ge`, `gross_margin_pct` ✅ | `dashboard_pipeline/retail_sales.py:752-866` |
| `retail_sales.cashier_day_breakdown[]` | per-day-per-store-per-cashier: cash, card, revenue, receipts ✅ | added 2026-05-11 ღამე session, exposed via `api_contracts.py` allowlist |
| `retail_sales.cashier_hour_breakdown[]` | per-day-per-hour, rolling 180 days ✅ | added 2026-05-12 session |
| `pos_terminal_income.daily_summary[]` | per-day TBC + BOG acquirer deposits (`day`, `tbc_total_ge`, `bog_total_ge`) ✅ | `dashboard_pipeline/bank_income.py:1325-1350` |
| `waybills[]` | per-waybill list with `delivery_date`, `full_amount`, `seller_name`, `seller_tin` ✅ | `dashboard_pipeline/rs_waybill_connector.py:66-94` + `api_contracts.py:2549-2654` |
| Bank category rules | `salary_payments`, `tax_and_budget`, `rs_budget_payments`, `cash_withdrawal` ✅ | `dashboard_pipeline/bank_unmatched.py:50-81` |
| `manual_payments_journal` | per-entry: `date`, `tax_id`, `amount` ✅ | `dashboard_pipeline/manual_payments_journal.py:44-57` |
| `supplier_payment_lines{tax_id: [{date, amount, source, purpose}]}` | indexed by supplier (NOT date) ⚠️ | `dashboard_pipeline/bank_reconciliation.py:687-759` |

### Frontend (React)

| File | რას აკეთებს | რა მაინტერესებს |
|---|---|---|
| `rs-dashboard/src/App.jsx` | tab router, 28 lazy imports, global header with `DateTimeCalendarPicker` | `useHashTab('suppliers')` default = first tab — need to change |
| `rs-dashboard/src/tabConfig.js` | 4 tab groups, 25 tabs total; group order: daily → sales → finance → strategy | new tab needs to be **before** `suppliers` (first slot in `daily` group) |
| `rs-dashboard/src/Executive.jsx` | 538 lines, closest existing analog (executive KPI rollup) | reusable pattern for KPI cards, period-aware |
| `rs-dashboard/src/Cashiers.jsx` | 831 lines, cash/card split table + hourly chart | reusable pattern for store breakdown |
| `SAFE_PERIOD_REQUEST_TABS` / `PERIOD_PICKER_TABS` (App.jsx:49,61) | period filter allowlists | new tab id must be added to both if period-aware |

---

## Ship-readiness per block

| Block | Ready? | Pipeline gap | Frontend effort |
|---|---|---|---|
| **1. Stores comparison (today + period)** | 90% | per-store-per-day already in `cashier_day_breakdown` ✅ | ~2h — aggregate by store, render table |
| **2. Cash till → bank variance** | 30% | **needs cash-deposit rule** (keywords: "ნაღდის შემოტანა" / "შემოტანა" / "გადათავსება" / "დეპოზიტი") + matching logic | ~3h pipeline + 2h frontend |
| **3. Daily KPIs (revenue / profit / bank balance)** | 70% | revenue+profit ready (`daily_trend[0]`). **Bank balance NOT exposed** — TBC/BOG statements have closing balance internally but not surfaced. | ~1h pipeline + 1h frontend |
| **4. Money in/out today** | 40% | per-month exists; **need daily rollup** of: supplier payments by date, expenses by category by date, manual journal by date | ~3h pipeline + 2h frontend |
| **5. Today's waybills** | 100% | none | ~1h frontend (filter `waybills[]` by `delivery_date == selectedDate`) |

---

## Risks / pitfalls

1. **Bank-balance accuracy** — TBC/BOG statements show running balance per row but cache is append-only (`Sprint A/B/C` parquet wire-in). "Current balance" needs latest-row resolution per account, not sum. Watch out for ანაბარი (deposit) account vs main: API gives only main per memory `project_bog_two_accounts`. Display label must say "მთავარი ანგარიში" if we exclude deposit.

2. **Cash-deposit detection ambiguity** — Owner deposits cash with various memo strings. No canonical keyword. Risk: false-positives (e.g., POS settlement also has "შემოტანა" in some descriptions). Mitigation: require BOTH (a) keyword match in purpose AND (b) own-account → own-account transfer pattern (no external counterparty TIN). Need 5 spot-checks against real bank rows before pinning.

3. **"Today" definition** — Megaplus uses calendar-day cutoff (cross-midnight shifts carry into next day's hour 00:01). Bank uses statement-date (midnight cut). Inconsistency means "Today" on the page can show 11:50 PM shift sales but NOT the matching 11:55 PM cash drawer close. Decision needed: do we use Megaplus calendar-day OR bank-statement-day OR a unified "operational day" boundary?

4. **Period picker coexistence with "today"** — Page has a global period picker (header). If user picks "Last 30 days", do KPIs at the top become "30-day total" or stay "Today"? Owner phrased it as "real picture" — meaning today-anchored. Recommend: **top KPIs always Today**, table sections honor picker.

5. **Cost data freshness** — `profit_ge` in `daily_trend` depends on `cost_ge` which depends on the barcode JOIN to imported price. If a barcode is unmatched (orphan_products has ~4,925 items), its cost = 0 → profit inflated. Need to surface "incomplete cost coverage" badge if today's revenue includes orphan-product sales.

6. **First-tab default change risk** — `useHashTab('suppliers')` is the entry point. Changing default breaks any bookmark / muscle memory that lands on `#suppliers`. Mitigation: new tab id `home`, default becomes `home`, but `#suppliers` URL still works (no rename of suppliers tab).

---

## Scope recommendation — 3-sprint split

### **HOME-1: Quick-win shippable cockpit (~1 session)**
**Ships blocks 1, 3-partial, 5 with no pipeline changes.**

- New tab `home` registered first in `tabConfig.js` (`daily` group, position 0)
- New `Home.jsx` page with 3 zones:
  - **Top KPI strip:** today's revenue / today's profit (both from `daily_trend[0]`) + placeholder "ბანკში ნაშთი — მზადდება" (HOME-2 fills this in)
  - **Stores table:** per-store today + period from `cashier_day_breakdown` (cash / card / revenue / receipts / AOV)
  - **Today's waybills:** filtered `waybills[]` by `delivery_date`
- App.jsx routing + lazy import added
- Default tab changes from `suppliers` → `home`
- Both `SAFE_PERIOD_REQUEST_TABS` and `PERIOD_PICKER_TABS` updated to include `home`
- Mobile nav (`MobileNav.jsx`) updated

**Owner sees:** real numbers, first day, no waiting for pipeline.

### **HOME-2: Bank balance + cash-to-bank variance (~1-2 sessions)**
**Ships block 3-complete + block 2.**

- Pipeline: add `cash_position` top-level field — latest closing balance per account from TBC/BOG parquet, exclude `project_bog_two_accounts` ანაბარი
- Pipeline: add `cash_deposit` category rule to `bank_unmatched.py` with verified keywords (require 5 spot-check rows before pinning rule)
- Pipeline: new `cash_till_vs_bank[]` per-day series — `{day, till_cash_ge, bank_cash_in_ge, variance_ge, alert_days_overdue}`
- API contract: expose both fields via `_build_home_response` builder OR add to `data.json` top-level
- Frontend: fill in placeholder KPI + add variance card with red badge when 3+ days lag

### **HOME-3: Money in/out today (~2 sessions)**
**Ships block 4.**

- Pipeline: new `daily_money_flow[]` per-day breakdown — `{day, incoming: {pos_cash, pos_card, bank_in_other, ...}, outgoing: {suppliers, taxes, salary, manual, ...}}`
- Build by aggregating: `supplier_payment_lines` group-by date, `bank_unmatched` expense categories group-by date, `manual_payments_journal` group-by date
- Frontend: 2-column layout (incoming | outgoing) with totals + clickable rows that open detail modal

---

## Test plan (HOME-1)

Unit / integration patterns to add (under `tests/`):

1. `test_home_default_tab.py` — assert `useHashTab` default in App.jsx is `home`, and `tabConfig.js` first entry id is `home`.
2. `test_home_kpi_revenue_matches_daily_trend.py` — pipeline test: `home.today_revenue == retail_sales.daily_trend[0].revenue_ge` exactly.
3. `test_home_kpi_profit_matches_daily_trend.py` — same for profit.
4. `test_home_store_table_matches_cashier_day_breakdown.py` — sum of `home.stores[].revenue_today` per store == sum of `cashier_day_breakdown` rows where `day == today AND object == store`.
5. `test_home_waybills_filter_by_date.py` — `home.todays_waybills[*].delivery_date` all equal selected date.
6. `test_home_period_picker_propagates.py` — assert `home` is in both `SAFE_PERIOD_REQUEST_TABS` and `PERIOD_PICKER_TABS`.
7. `test_home_orphan_cost_warning.py` — when `daily_trend[0]` contains products with cost=0, page surfaces an "incomplete cost coverage" indicator (asserted via response_meta flag).

Patterns to mirror: `tests/test_retail_sales_revenue_formula.py` for revenue invariants; `tests/test_supplier_data_invariants.py` for shape validation.

---

## Files expected to change (HOME-1 only)

**Frontend (new + modified):**
- `rs-dashboard/src/Home.jsx` — NEW (~300-400 lines)
- `rs-dashboard/src/tabConfig.js` — add `home` entry at position 0 of `daily` group
- `rs-dashboard/src/App.jsx` — lazy import + routing case + `useHashTab` default + `SAFE_PERIOD_REQUEST_TABS` + `PERIOD_PICKER_TABS`
- `rs-dashboard/src/components/MobileNav.jsx` — likely needs `home` added (verify when implementing)

**Backend (HOME-1 only — minimal):**
- `dashboard_pipeline/api_contracts.py` — likely a thin `_build_home_response` builder that re-bundles existing fields (or HOME-1 can ship by reading from existing tab responses if owner accepts the latency)

**Tests (new):**
- `tests/test_home_*.py` — 7 files per test plan above

**Config / governance:**
- `CONTEXT_HANDOFF.md` — only at session close (handoff step), not during implementation
- `docs/MASTER_PLAN.md` — only after Step 6 user review (sprint closure)

**Untouched (do-not-edit during HOME-1):**
- `dashboard_pipeline/retail_sales.py`, `bank_income.py`, `bank_reconciliation.py`, `bank_unmatched.py` — all stable for HOME-1
- `manual_payments_journal.py`, `megaplus_backup.py` — stable
- All other `.jsx` page files

---

## Self-check checklist (HOME-1 pre-commit)

- [ ] `home` is first tab in `tabConfig.js` `daily` group
- [ ] `useHashTab` default is `home`
- [ ] `home` added to `SAFE_PERIOD_REQUEST_TABS` and `PERIOD_PICKER_TABS`
- [ ] `home` routing case present in App.jsx (after `activeTab === 'suppliers'` check)
- [ ] Lazy import line added next to existing 28 imports
- [ ] Bookmarks to `#suppliers` still work (no rename of suppliers tab)
- [ ] All 3 home zones render: KPI strip, stores table, today's waybills
- [ ] Period picker visible + changes propagate to home
- [ ] Today's revenue matches `daily_trend[0].revenue_ge` (visual spot-check)
- [ ] Per-store cash+card sums match `cashier_day_breakdown` for selected day
- [ ] Empty-state UI: when no data for "today" yet (early morning), show "ჯერ მონაცემი არ შემოსულა" not zeroes
- [ ] `npm run build` passes (per memory `feedback_single_url_workflow` — single-URL workflow)
- [ ] All 7 new tests pass under parent venv pytest
- [ ] Existing test suite still green (39/39 waybill + 50/50 supplier + others)
- [ ] No regression on first-load: `#home` loads under 2s on cold cache
- [ ] MobileNav shows new tab (manual check)
- [ ] CONTEXT_HANDOFF.md update deferred to session-close handoff step

---

## Evidence sources

- Inventory audit: 2026-05-12 (this preview session)
- Current CONTEXT_HANDOFF.md state: lines 1-273 (post-cleanup, same session)
- Related memories: `project_bog_two_accounts.md`, `project_api_response_paths.md`, `feedback_single_url_workflow.md`
- Files read for evidence (no edits):
  - `rs-dashboard/src/App.jsx` (615 lines, full)
  - `rs-dashboard/src/tabConfig.js` (58 lines, full)
  - File-line citations in inventory table above, gathered via Explore subagent audit (Block-by-block ship-readiness report)
- Industry references (used for layout convention): Square Home, Shopify Overview, Lightspeed Retail dashboard — three-zone pattern (KPI strip → breakdown table → flow detail)
