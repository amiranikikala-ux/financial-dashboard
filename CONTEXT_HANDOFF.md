# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-13 დღე — **HOME-5 sprint SHIPPED: Bank money correctness deep-dive.** ვამოწმებდით აპრილს — Owner-მა იპოვა, რომ headline "ბანკში შემოვიდა 86,361 ₾" სრულიად არასწორი იყო (რეალურად 163,918 ₾, 90% სხვაობა). ეს გადაიშალა მთლიანი დაყაჩაღება. გასწორებები: (1) **Bank headline silent drift fixed** — `daily_money_flow.py:bank_in/bank_out` ცარიელ category subset-ს ითვლიდა; ახლა raw `bank_in_total`/`bank_out_total` accumulator-ი (loop-ში += უპირობოდ). + reconciliation sanity check ყოველ დღეს: categorized sum ≠ raw → red badge UI-ში + log error. (2) **სამეურნეო BOG↔TBC netting** — owner ფიზიკურად BOG-დან იღებს ნაღდს, TBC-ში შეიტანს „სამეურნეო" სახელით. იმავე თვეში დაბრუნებული = შიდა გადარიცხვა, არა ხარჯი. Home.jsx აგრეგაცია calendar-month bucketing-ით ნეთებს. აპრილი: 4,850 ₾ internal, real owner expense 2,900 ₾ (was 7,750). (3) **Supplier matching 15,893→0 ₾** — `daily_money_flow.py` extended: (a) `suppliers_list` parameter — known_supplier_tins ფაქტურა-based suppliers-ით expand, (b) quote stripping (ASCII "/' + HTML `&apos;`/`&quot;`), (c) hyphen ↔ space + `&` whitespace collapse, (d) cross-bank TIN inference (TBC empty + BOG TIN → propagate), (e) prefix-of-known-supplier match (single-candidate only), (f) `LEGACY_KNOWN_ALIASES` from supplier_matching.py integrated. (4) **AP delta = TOTAL not active-only** — was 250,467→227,073 (-23,394, misleading) showing 59 active suppliers; now 325,430→326,459 (+1,029, real) across all 261. New per-day fields `total_ap_before`/`total_ap_after`. (5) **TBC ნავაჭრი regex broader** — `TBC_CASH_DEPOSIT_PURPOSE_RE` ცნობს ახლა „დვაბზუ"/„ოზურგეთი"/„დუვაბზუ" + ნავაჭრი (was only ნავაჭრი). აპრილი: 72,706→74,279 ₾ correctly identified. (6) **Comprehensive financial summary on Home** — replaced compact summary with full IN↗ / OUT↘ side-by-side breakdown: sales (cash+card) + other; bank OUT (suppliers + other) + cash journal + cash expenses; true_net (no double-count) + AP change + verdict. `agg.true_in/true_out` formulas in Home.jsx. (7) **Cash expense entry** — POST'd 3,200 ₾ Dvabzu salary (date 2026-04-13, comment "მაისის ხელფასი წინასწარ"). Owner had paid by hand April 10-17. (8) **Cash deposit lag pattern documented** — დვაბზუ 1-day lag, ოზურგეთი weekend (Fri+Sat+Sun) bundles to Monday. Verified: დვაბზუ 30 აპრ 1,964.53 ↔ 1 მაი TBC 2,023.50; ოზურგეთი 1-3 მაი 4,347.80 ↔ 4 მაი 4,423.55. Memory: `project_cash_deposit_lag_pattern.md`. (9) **CLAUDE.md new 🔴 CRITICAL rule** — „Aggregate ციფრი ცოცხალ წყაროს უნდა ემთხვეოდეს" (with the 90%-drift incident as example). Plus memory `feedback_aggregate_vs_source_verification.md`. **APRIL FINAL NUMBERS (after all fixes)**: ნავაჭრი 191,909; ბანკში შემოვიდა 159,068 (after samurneo netting); ბანკიდან გავიდა 159,682; true_net +8,250 ₾ (or +433 if missing 7,817 ₾ unknown cash entered); AP change +1,029. Verdict 🟡 ფაქტობრივად ნულზე — ფული მცირედით მეტი, ვალი მცირედით გაიზარდა. **OPEN — next session**: enter remaining 7,817 ₾ unknown cash (ოზურგეთის ხელფასი + ბენზინი + წვრილი) via Home page modal so April reconciliation goes to ~0. The 1,091 ₾ TBC "შეცდომით ჩარიცხული თანხის უკან დაბრუნება" (1 აპრ.) still in "სხვა" bucket — ეს TBC-ის თვითონ შესწორებაა, არ არის owner-ის შემოსავალი. Memories saved: `project_cash_deposit_lag_pattern`, `project_samurneo_internal_transfer`, `feedback_aggregate_vs_source_verification`. All uncommitted on local main. Owner did NOT authorize commit.
>
> **წინა session-ის შედეგი (2026-05-13 ღამე)** — **HOME-4 sprint SHIPPED: Bank Money rewrite + cash reconciliation.** Major session — owner asked "did I make progress this period?" and we built a complete cash-flow understanding. Key pieces: (1) **Bank IN per-bank** — TBC/BOG expand with ბარათით გადახდა (per-tx net) + გროსი/საკომისიო subdetail + Wallet swap; (2) **TBC „ნავაჭრი" reclassified as cash deposit** — owner physically deposits cash and bank labels it as "ნავაჭრი თანხა" via transit account. Pipeline `_is_tbc_cash_via_terminal()` routes these to `cash_deposit` field (April: 72,706 ₾ across both stores). Was misclassified as POS card before. (3) **Bank OUT full categorization** — salary / rent / owner_withdraw / service / refund / unmatched_suppliers / other. Each row expandable with item list (partner + bank badge). Detection patterns added in `daily_money_flow.py`. (4) **Supplier list with TBC/BOG bank badge** — `amount_bank_tbc`/`amount_bank_bog` per supplier shows which bank paid; both shown if mixed. (5) **ჯიდიაი cash-on-receipt flow** — 372,690 ₾ lump on May 8 soft-deleted; 533 backfill manual entries created (scaled by monthly gap, sums to 376,187 = total_wb − total_bank, debt now ≈ 0). SupplierModal has ✅ ვეთანხმები button on each pending ჯიდიაი waybill (POST /api/manual-payments, 5% amount tolerance for past matches). `CASH_ON_RECEIPT_TAX_IDS` constant in SupplierModal.jsx. (6) **Financial summary block** — replaced misleading yellow "ჯერ არ ბანკშია" with smart block for past periods: net cash flow + AP delta + 1-line verdict (✅ წახვედი წინ / ⚠️ წახვედი უკან). Owner's primary question per memory `project_owner_main_question.md`. (7) **Cash expenses journal** — new `cash_expenses_journal.csv` + module `dashboard_pipeline/cash_expenses_journal.py` + endpoints GET/POST/DELETE `/api/cash-expenses`. Categories: salary/rent/owner/service/supplier_cash/other. Wired into daily_money_flow OUT buckets. Home page "➕ ნაღდი ხარჯი ჩამიწერე" button + modal on bank-flow section header. **OPEN — tomorrow's task**: owner will determine exact cash salary figures (April: 3,200 Dvabzu + 3,200 Ozurgeti = 6,400 known so far, +rest TBD) and enter via modal. After that April reconciliation: cash remaining 4,616 ₾ minus actual cash expenses → 0. Service restart required (`Restart-Service FinancialDashboardBackend`) once before testing — owner confirmed done. Two big things: (1) **Waybill date semantics fix** — pipeline `safe_cols` mapping changed from `გააქტიურების თარ.` (ACTIVATE_DATE) to `ტრანსპ. დაწყება` (BEGIN_DATE). Owner's MegaPlus tool groups by transport start date, not activation date — so our dashboard now exactly matches his MegaPlus view (May 8: 16 regulars, 7,561.87 ₾, 2 returns -14.92 ₾). Open ambiguity from previous session RESOLVED. (2) **Daily Money Flow section** — new collapsible zone on Home page: `🏦 ბანკის ფული — შემოვიდა / გავიდა`. Pipeline `daily_money_flow.py` aggregates last 90 days per-day money flow with categories. Headline shows bank-only IN/OUT/NET. Per-bank breakdown (TBC, BOG) expandable to show ნავაჭრის შემოტანა + სამეურნეო + სხვა categories. Suppliers list shows AP balance change (იყო → დარჩა) per supplier with bank-vs-manual payment split. Cash + card revenue displayed separately in yellow block ("ჯერ არ ბანკშია"). Manual journal cash payments (e.g., ჯიდიაი 372,690 ₾ on May 8 — owner pays this supplier cash on receipt) shown separately. Today's waybills section made collapsible (default collapsed). **Pending UX restart**: 3 successive UI restructures this session as owner clarified intent — would benefit from a fresh session to evaluate the final HOME-3 shape with clear mind. **Service restart cycle**: every API contract change required user-side `Restart-Service FinancialDashboardBackend` (admin) — 3x this session.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-13) — HOME-3: Daily Money Flow + rs.ge waybill date fix

### Headline

Owner asked for daily bank-money picture: "8 მაისს სად მოხდა გადახდები, ერთი სიტყვით ყველა თანხის მიმოსვლა სად მოხდა და სად გავიდა". Built `🏦 ბანკის ფული` collapsible section on Home page — bank-only IN/OUT/NET with per-bank category expansion. Separately fixed rs.ge waybill date semantics to match owner's MegaPlus tool (previous session's open ambiguity).

### Part 1 — rs.ge waybill date fix

**Root cause found:** `safe_cols` in `generate_dashboard_data.py:1251` was mapping `გააქტიურების თარ.` (ACTIVATE_DATE) → `date`. Owner's MegaPlus rs.ge UI groups by `დაწყ. თარიღი` (BEGIN_DATE = when transport starts). Many waybills activated late evening (e.g., 05-07 21:48) have BEGIN_DATE next day (05-08). MegaPlus shows them under 05-08, our dashboard showed them under 05-07.

**Fix:** Changed mapping to `ტრანსპ. დაწყება` → `date`. Verified May 8: 16 regular waybills / 7,561.87 ₾ + 2 returns / -14.92 ₾ — matches owner's MegaPlus tool exactly. The 4 "extras" that we previously had on May 8 (კოკა-კოლა 2 + სტარდი + ზედაზენი) correctly moved to May 9 (their BEGIN_DATE).

**Memory saved:** `project_rsge_waybill_date_semantics.md`.

**Files:** `generate_dashboard_data.py` (1 line change in safe_cols).

### Part 2 — Daily Money Flow section (HOME-3)

#### New pipeline module — `dashboard_pipeline/daily_money_flow.py` (~370 lines)

Reads TBC + BOG parquet caches directly, joins with waybills + supplier_payment_lines, and categorizes every bank line for the last 90 days. Output: `data["daily_money_flow_index"][YYYY-MM-DD] = { in, out, internal, info, bank_net, net }`.

Categorization logic:
- **IN (bank)**: `pos_deposit` (Wallet/domestic + ნავაჭრი + per-customer card payment patterns), `samurneo_in` (purpose contains "სამეურნეო"), `foodmart_cashback` (TIN 404460187), `other`. Tracked per-bank (TBC/BOG).
- **OUT (bank)**: `suppliers` (partner_tin matches known supplier TIN from waybills; name fallback for empty TIN), `tax_treasury` (TIN 200122900 / "სახაზინო" / TRESGE22), `bank_fees` (op=COM, not treasury), `other`.
- **Internal**: partner = own TIN 400333858 → not counted as IN/OUT.
- **Per-supplier AP roll**: cumulative sum of waybill amounts minus all payments (bank + manual) through date — gives `ap_before` (end of prior day) and `ap_after` (end of this day) per supplier.

Bank-vs-manual payment split:
- Bank payments derived from raw bank-line scan (authoritative — independent of bank_reconciliation match status).
- Manual payments derived from `supplier_payment_lines` entries where `source.contains("manual")`.

#### Wire-in

- `generate_dashboard_data.py::_build_analytics` end — calls `compute_daily_money_flow(days_back=90)` after executive_summary, stores result on `data["daily_money_flow_index"]`.
- `api_contracts.py` — added `"daily_money_flow_index": {}` to `FIELD_DEFAULTS` and `"daily_money_flow": ["daily_money_flow_index"]` to `TAB_ALLOWLIST`.

#### Frontend — `rs-dashboard/src/Home.jsx`

New collapsible zone (Zone 4) below today's waybills. Components added:
- `BankExpandableRow` — header `{bank} ბანკი — {total} ₾`, click reveals subcategories (ნავაჭრის შემოტანა, სამეურნეო, სხვა). Used twice (TBC + BOG).
- `PosExpandableRow` — kept in code (unused after final refactor) — could render per-customer card-transaction table with time/brand/amount. Owner initially asked for it, then changed direction.
- `FlowRow` — simple label + value row, supports `bold`/`hint`/`danger`/`size`.

Layout:
- **Headline** (collapsed default): "🏦 ბანკის ფული — შემოვიდა / გავიდა" + ↗ ბანკში შემოვიდა X / ↘ ბანკიდან გავიდა Y / წმინდა Z.
- **Expanded — IN column (green)**: TBC ბანკი row (expandable) → BOG ბანკი row (expandable) → ფუდმარტი ქეშბექი → სხვა → სულ ბანკში.
- **Expanded — OUT column (red)**: მომწოდებლები + გადასახადი/ხაზინა + საკომისიო + სხვა + სულ ბანკიდან.
- **Expandable suppliers list** (▶): per-supplier rows with bank/manual/returns/იყო/დარჩა columns. Top 50.
- **Yellow context block**: "💰 დღევანდელი გაყიდვა (ჯერ არ ბანკშია)" — სალარო ნაღდი + ბარათით (Megaplus). Plus "📝 ნაღდი გადახდები (ჟურნალი)" — manual journal cash supplier payments.
- **Bottom info row**: 🔁 შიდა მოძრაობა (own-bank transfers) + 📦 დღის ზედნადებები (waybill receipts info).

#### May 8 verified output

| metric | value |
|---|---|
| ბანკში შემოვიდა | 5,388.26 ₾ (TBC 3,025.45 + BOG 2,362.81) |
| ბანკიდან გავიდა | 8,060.38 ₾ (მომწოდებლები 8,055.80 + tax 2.98 + fees 1.60) |
| ბანკის წმინდა | -2,672.12 ₾ |
| ნაღდი გადახდები (ჟურნალი) | 421,579 ₾ (ჯიდიაი 372,690 + others) |
| სალარო ნაღდი (Megaplus) | 4,439.81 ₾ |
| ბარათით (Megaplus) | 2,956.65 ₾ |

Top bank-paid suppliers May 8: ელიზი ჯგუფი 2,665.80 ₾ (იყო 10,088 → დარჩა 7,794), საქართველოს დისტრიბუცია 2,000 ₾, აიდიეს ბორჯომი 990, კოკა-კოლა გურია 900, იფქლი 500 (returns -14.92), ვასაძის პური 400, კინგ ჯგუფი 300, ენგადი 300.

#### Owner's iterative feedback during session (3 restructures)

1. Initial build: aggregated bank IN included `cash_megaplus` + `card_megaplus` + `pos_bank_deposit` together. Owner asked: "12,712.45 ₾ — is this in bank?" — pointed out cash + card aren't in bank yet. Refactor: bank-only headline; cash/card moved to yellow context block.
2. Owner wanted POS deposit rows clickable for per-transaction detail. Built `PosExpandableRow` with per-line table (time/card-brand/amount).
3. Owner: "მყიდველის გადახდები ჯამი აჩვენე, არ არის საჭირო ცალკე" — wants aggregated total, not per-line. Removed expand.
4. Owner: "TBC-ში დაჭერით უნდა გამოჩნდეს ნავაჭრის შემოტანა, სამეურნეო, სხვა" — wanted category breakdown on click. Built `BankExpandableRow` with category subrows. Final shape.

#### Memory saved

- `project_supplier_cash_payment_patterns.md` — ჯიდიაი + others are paid CASH on waybill receipt; large manual entries are normal (owner confirmed 372,690 single-day entry).
- `project_rsge_waybill_date_semantics.md` (from Part 1).

### Files changed this session — **all uncommitted on local main**

- `dashboard_pipeline/daily_money_flow.py` (NEW, ~370 lines)
- `dashboard_pipeline/api_contracts.py` (FIELD_DEFAULTS + TAB_ALLOWLIST entries)
- `generate_dashboard_data.py` (waybill date column + daily_money_flow wire-in)
- `rs-dashboard/src/Home.jsx` (Zone 4 + waybills collapsible + state/components)

Joins earlier uncommitted Home-1 work + Cashiers work (now 5+ sessions accumulated without commit/push authorization).

### Open / next-session candidates

1. **3-restructure restart marker** — owner pivoted UI 3 times this session as scope clarified. Final HOME-3 shape works, but a fresh session would be useful for a clean review pass.
2. **Service-restart automation** — every API contract change requires user-side admin `Restart-Service`. NSSM has `nssm restart FinancialDashboardBackend` — consider adding a `/restart-service` skill or a hook that prompts user during pipeline regen.
3. **Per-bank OUT split** — currently OUT column aggregates across TBC+BOG. Same per-bank treatment as IN side would make symmetry clean.
4. **More OUT categories** — currently: suppliers / tax / fees / other. Owner may want salary / rent / utilities / accountant / cash-withdrawal as named categories. `tbc_expenses_bundle` already has these; need to wire categorization rules into `daily_money_flow.py`.
5. **POS deposit per-customer drill-down** — `PosExpandableRow` is built but unused; can be re-enabled later if owner asks.
6. **Sales context inside TBC/BOG expand** — owner mentioned "გაყიდვების ჯამი" alongside "ნავაჭრის შემოტანა". Currently shown in yellow block (top-level). Could add Megaplus card revenue context line inside each bank expand for direct comparison.
7. **HOME-2 sprint** — bank balance (top-level `cash_position` field) + cash-till vs bank-deposit variance with red-badge alert. Pipeline ~3h + frontend ~2h.

### Verification commands (next session)

```powershell
# Daily money flow endpoint
"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -c "
import urllib.request, json
api = json.loads(urllib.request.urlopen('http://localhost:8000/api/data?tab=daily_money_flow', timeout=60).read())
idx = api['daily_money_flow_index']
print(f'days: {len(idx)}')
m8 = idx.get('2026-05-08', {})
print(f'May 8 bank IN: {m8[\"in\"][\"bank_total\"]:.2f}')
print(f'  TBC: pos={m8[\"in\"][\"tbc\"][\"pos\"]} samurneo={m8[\"in\"][\"tbc\"][\"samurneo\"]} other={m8[\"in\"][\"tbc\"][\"other_total\"]}')
print(f'  BOG: pos={m8[\"in\"][\"bog\"][\"pos\"]} samurneo={m8[\"in\"][\"bog\"][\"samurneo\"]} other={m8[\"in\"][\"bog\"][\"other_total\"]}')
print(f'May 8 bank OUT: {m8[\"out\"][\"bank_total\"]:.2f}')
print(f'  suppliers_bank={m8[\"out\"][\"suppliers_total_bank\"]} suppliers_manual={m8[\"out\"][\"suppliers_total_manual\"]} tax={m8[\"out\"][\"tax_treasury\"]}')
# Expected: bank IN 5388.26, bank OUT 8060.38, suppliers_manual 421579
"

# rs.ge date fix verification (May 8 regulars must match owner's MegaPlus 7,561.87)
"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -c "
import urllib.request, json
api = json.loads(urllib.request.urlopen('http://localhost:8000/api/data?tab=waybills', timeout=60).read())
m8 = [w for w in api['waybills'] if w['date'].startswith('2026-05-08')]
regs = [w for w in m8 if not w['is_return']]
print(f'May 8: {len(regs)} regulars, {sum(w[\"effective_amount\"] for w in regs):.2f} ₾')
# Expected: 16 / 7561.87 ₾
"
```

---

## 0. ბოლო session-ის შედეგი (2026-05-12 ღამე) — HOME-1: Owner's daily cockpit + governance cleanup

### Headline

Owner asked for "მთავარი გვერდი — დილით ჯერ ეს ვხსნა, რეალურ სახეს ვხედავ". Built `🏠 მთავარი` as the new default-first tab. 3 zones: top KPI strip (today's revenue + profit, bank balance placeholder for HOME-2), per-store comparison table (cash/card/total/receipts/AOV), today's waybills (returns in red, separated total). All 3 zones honour the global header date-picker — pick any date/range and entire page reflows. Sprint preview document at `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_HOME_PAGE_PREVIEW.md`.

### Frontend changes

- **NEW** `rs-dashboard/src/Home.jsx` (~530 lines) — KPI cards + stores table + waybills table. Self-fetches waybills via `/api/data?tab=waybills` (parallel to App.jsx's retail_sales fetch).
- `rs-dashboard/src/tabConfig.js` — added `{ id: 'home', label: '🏠 მთავარი' }` as **first** entry in `daily` group.
- `rs-dashboard/src/App.jsx` — 6 edits:
  - lazy import `Home`
  - `useHashTab('home')` (was `'suppliers'`) — new default tab
  - `PERIOD_PICKER_TABS` += `'home'`
  - `SAFE_PERIOD_REQUEST_TABS` deliberately **excludes** `'home'` (see bug-fix below)
  - `requestTab` mapping: home → `retail_sales`
  - routing case `activeTab === 'home'` renders `<Home />` with retail_sales + period props
  - **Critical bug-fix**: `appendCanonicalPeriodParams(params, activeTab === 'home' ? 'home' : requestTab)` — without this, picker triggered a filtered `tab=retail_sales&from_date=...` request which strips `daily_trend` and `cashier_day_breakdown` from the response → Home spun on "იტვირთება" forever.
- `rs-dashboard/src/components/MobileNav.jsx` — `home` replaces `executive` in `QUICK_TABS` (first slot).

### Date-handling logic — "last complete day"

The MegaPlus backup ZIP is created mid-day (~14:30 Dvabzu, ~16:30 Ozurgeti), so the **latest** day in `cashier_day_breakdown` is always partial. Home walks back through days and picks the latest day where every store's max hour reaches **≥22**. As of this session: data has May 9 (Dvabzu max hour 13, Ozurgeti max hour 16 — incomplete) → home anchors to **May 8** (both stores reached hour 23).

Implementation: `lastCompleteDay(retailSales)` in `Home.jsx`. Fallback to latest available day if none complete.

### Returns surfaced separately

Owner: "დაბრუნება ცალკეა ორივეს ითვლის. ჩვენი დაბრუნება ცალკე წითელ ფერში გამოყავი ჯამის გვერდით". Implemented:
- Waybills split into `regularWaybills` (filter `!w.is_return`) and `returnWaybills` (filter `w.is_return`)
- Header shows: `14 ცალი · ჯამი 8,601.34 ₾` (regulars) AND `დაბრუნება: -14.92 ₾ (2)` in red.
- Return rows in the table get red text + red-tinted background + ↩ arrow prefix.

### Global picker — dark theme + sizing fixes

The `DateTimeCalendarPicker` component had legacy Windows-classic light styles that didn't match the dark dashboard. Multiple iterations:

1. **Dark theme overrides** appended to `rs-dashboard/src/styles/components.css` (~150 lines, end of file). Repaints `.dtcp-popup--classic` and the inline react-datepicker grid to dark using CSS vars (`--bg-secondary`, `--accent`, etc.).
2. **Popup width**: was `min(100%, 31rem)` constrained by `dtcp-wrapper` parent width → way too narrow on the centered header trigger. Changed to fixed `38rem` + `left: 50%; transform: translateX(-50%)` for center positioning under the trigger. No longer clips off-screen.
3. **Day-name overflow**: `კვირა / ორშ. / სამშ. / ოთხშ. / ხუთშ.` (mix of 3-5 chars with dots) overflowed the day cells. Shortened to 3-char consistent labels (`კვი ორშ სამ ოთხ ხუთ პარ შაბ`) in `DateTimeCalendarPicker.jsx::WEEKDAYS_KA`. Also: font-size 0.95→0.78rem, `overflow: hidden`, `white-space: nowrap`, `min-width: 0`.

### Verification — numbers match source

May 8 (last complete day, default anchor):

| store | cash | card | revenue | receipts | AOV |
|---|---|---|---|---|---|
| დვაბზუ | 2,268.58 | 1,746.47 | **4,015.05 ₾** | 399 | 10.06 |
| ოზურგეთი | 2,171.23 | 1,210.18 | **3,381.41 ₾** | 487 | 6.94 |
| ჯამი | 4,439.81 | 2,956.65 | **7,396.46 ₾** | 886 | — |

Cross-checked against `retail_sales.daily_trend[]` and `cashier_day_breakdown[]` row-by-row — all exact. May 8 ლია (Dvabzu): cash 95.48 + card 31.39 = 126.87 ₾ / 9 receipts ✅ (matches earlier Cashiers verification).

### Open data ambiguity — RESOLVE FIRST in next session

Owner's rs.ge `RS კაბინი` UI shows May 8 Dvabzu (filter 1329) total **7,561.87 ₾**. Our home page shows 8,586.42 ₾ (all stores, net of returns).

Diagnostic findings:
- Our rs.ge LIVE fetch via `fetch_buyer_waybills('2026-05-08 → 2026-05-08')` returns **16 waybills = 8,616.26 ₾** (raw, all amounts positive in the API).
- Pipeline applies negative sign to 2 იფქლი returns (3.40 + 11.52 = 14.92) → net 8,586.42 ₾ in `data.json.waybills`.
- Dvabzu only (5 rows): 2,208.13 ₾. Ozurgeti only (9 rows): 6,393.21 ₾. Neither matches owner's 7,561.87.
- Diff 8,616.26 − 7,561.87 = 1,054.39 ₾ — no single waybill matches, no obvious subset sums to it.
- **Smoking gun**: waybill `0976826734` from owner's screenshot (შპს კავკას სატრან., TIN 405159180, type **ექსპორ.**, 284.79 ₾, May 7 18:12) is **NOT** in our SOAP response across May 6–10. This is a transport-service waybill, not a goods-purchase waybill.

Hypothesis: `fetch_buyer_waybills` only returns goods-purchase waybills where the requesting party is the buyer. rs.ge UI shows additional types (ექსპორი / ტრანსპორი / ვერსიული / etc.) — we don't fetch them. Owner's 7,561.87 may be a slice using different filters in the UI (status filter? date column? type filter?).

**Action required next session:**
1. Ask owner to scroll to bottom of `RS კაბინი` and screenshot the SUM row + visible row count.
2. Ask owner what date column the filter is on (`თარიღი` vs `ფაქტ. თარიღი` vs `მიღების`).
3. Decide whether to extend our connector to fetch other waybill types (export/transport) or keep "goods only" scope.

### Pre-existing 2026-05-12 Cashiers ambiguity — STILL UNRESOLVED

From earlier 2026-05-12 session (now §0a): owner said "მაღაზიების შედარება ეს არ გვჭირდება" but never clarified which element of the Cashiers page he meant. Open question still pending. Owner moved on to home-page work in this session.

### Governance cleanup

- **35 debug PNGs deleted** from project root (cashiers-*, drilldown-*, deadstock-*, retail-*, kpi-*, daily-spike-alert).
- **CONTEXT_HANDOFF.md trimmed**: 2372 → 273 lines before this update. Sessions 2026-05-05 → 2026-05-11 (23 entries) moved to `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-05_2026-05-11.md`.
- **Memory audit**: 18 files in `C:\Users\tengiz\.claude\projects\C--financial-dashboard\memory\` — all still valid (rs.ge SOAP facts, BOG dual-account, no-silent-data-drops, single-URL workflow, etc.). None deleted.

### Files changed this session — **all uncommitted on local main**

This session (HOME-1 + governance + picker):
- `rs-dashboard/src/Home.jsx` (NEW)
- `rs-dashboard/src/App.jsx`
- `rs-dashboard/src/tabConfig.js`
- `rs-dashboard/src/components/MobileNav.jsx`
- `rs-dashboard/src/components/DateTimeCalendarPicker.jsx` (3-char weekday labels)
- `rs-dashboard/src/styles/components.css` (dark theme + popup width + day-name CSS)
- `CONTEXT_HANDOFF.md` (this update + earlier trim)
- `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-05_2026-05-11.md` (NEW — archive)
- `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_HOME_PAGE_PREVIEW.md` (NEW — preview doc)

Still uncommitted from earlier 2026-05-12 (§0a — Cashiers analysis):
- `dashboard_pipeline/megaplus_backup.py`
- `dashboard_pipeline/retail_sales.py`
- `dashboard_pipeline/api_contracts.py`
- `rs-dashboard/src/Cashiers.jsx`

Still uncommitted from 2026-05-11 ღამე (Cashiers/Salaro rebuild) — included above except for `Financial_Analysis/cashier_names.json` (still needs deletion). Plus commits `f9a78e2` + `d0b924f` (retail_sales period-filter) local main, not pushed.

### Next-session candidates

1. **Resolve rs.ge waybill type ambiguity** (open data issue above) — clarify with owner what 7,561.87 represents.
2. **HOME-2 sprint** — bank balance (top-level `cash_position` field) + cash-till vs bank-deposit variance with red-badge alert. Pipeline work ~3h + frontend ~2h.
3. **HOME-3 sprint** — daily money in/out (incoming vs outgoing). Pipeline daily aggregations + frontend 2-column. ~2 sessions.
4. **Commit/push pending changes** — owner has not authorized commit on Cashiers, Salaro rebuild, OR home page yet. 4 + 5 + 6 + 2 changes accumulated across 4 sessions.
5. **Delete obsolete `Financial_Analysis/cashier_names.json`** — still pending from 2026-05-11.

### Verification commands (next session)

```powershell
# Home page numbers should match these exactly for May 8 (default anchor)
"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -c "
import urllib.request, json
api = json.loads(urllib.request.urlopen('http://localhost:8000/api/data?tab=retail_sales', timeout=30).read())
rs = api['retail_sales']
dt = [r for r in rs['daily_trend'] if r['day'] == '2026-05-08'][0]
print('May 8 revenue:', dt['revenue_ge'], 'profit:', dt['profit_ge'])
# expect revenue=7396.46, profit=1241.05
cdb = [r for r in rs['cashier_day_breakdown'] if r['day']=='2026-05-08']
by_store = {}
for r in cdb:
    s = r['object']
    by_store[s] = by_store.get(s,{'cash':0,'card':0,'rev':0,'rcpt':0})
    by_store[s]['cash'] += r['cash']
    by_store[s]['card'] += r['card']
    by_store[s]['rev']  += r['revenue']
    by_store[s]['rcpt'] += r['receipts']
for s,v in by_store.items():
    print(f'{s}: cash={v[\"cash\"]:.2f} card={v[\"card\"]:.2f} rev={v[\"rev\"]:.2f}')
# expect: დვაბზუ 2268.58/1746.47/4015.05; ოზურგეთი 2171.23/1210.18/3381.41
"

# rs.ge LIVE waybill fetch — reproduces the open ambiguity
"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -c "
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from dashboard_pipeline.rs_waybill_connector import RSWaybillConnector
c = RSWaybillConnector(os.environ['RS_USER'], os.environ['RS_PASS'])
wbs = c.fetch_buyer_waybills(datetime(2026,5,8,0,0,0), datetime(2026,5,8,23,59,59))
total = sum(float(w.full_amount or 0) for w in wbs)
print(f'{len(wbs)} waybills, total = {total:.2f}')
# expect 16 / 8616.26 (raw positive). Owner sees 7,561.87 in his tool — diff = 1054.39.
"
```

---

## 0a. წინა session-ის შედეგი (2026-05-12 დღე) — Cashiers/Salaro analysis section

### Headline

Owner asked for "ანალიზები რაც ამ გვერდს უკავშირდება. მოიძიე ისეთი კომპანიიდან რომელიც უმაღლეს დონეს წარმოადგენს". Agent researched NCR Voyix / Lightspeed / KORONA / Logile via Brave search and presented 8 candidate analyses split into three top-tier buckets: loss-prevention (discount/refund/voids), performance (AOV/TPH/UPT/hourly), comparison (period-over-period/leaderboard/cash-share). Owner rejected #1 and #2 (discount + refunds per cashier) and authorized the remaining 6. Agent built all 6, then owner rejected the period-over-period column. Final shipped state: 4 of original 8 (#3 AOV, #4 receipts/hour, #5 hourly distribution, #6 cash-share %, #8 rank). #7 (week-over-week) built then removed. #1/#2 never built.

### Backend changes — `dashboard_pipeline/megaplus_backup.py`

- **New SQL `cashier_hour_breakdown`** — per-day-per-hour-per-cashier rolling 180-day window. Window: `DATEADD(day, -180, CAST(GETDATE() AS DATE))`. Per-row: day, hour (0-23), user_id, cashier_name (USERS JOIN), receipts (COUNT DISTINCT ORD_N), cash (SUM where ORD_PAY_TYP=0), card (SUM where ORD_PAY_TYP=1), revenue (SUM ORD_jamjam).
- Returns 7,464 rows total (3,208 დვაბზუ + 4,256 ოზურგეთი) at last refresh.
- Added to return dict next to `cashier_day_breakdown`.

### Pipeline + API contracts

- `dashboard_pipeline/retail_sales.py` — combined accumulator `combined_cashier_hour_breakdown` across stores, each row tagged with `object` (store label). Sort by (day desc, hour). Added to return dict.
- `dashboard_pipeline/api_contracts.py` — `cashier_hour_breakdown` added to retail_sales pass-through allowlist (line ~1050, next to `cashier_day_breakdown`).

### Frontend changes — `rs-dashboard/src/Cashiers.jsx`

Added two new sections BELOW the existing MegaPlus-mirroring table + KPI strip:

**Section 1 — „მოლარეების ანალიზი" table:**
- 5 columns: # (rank with gold/silver/bronze color for #1/#2/#3) · მოლარე · საშუალო კალათა (AOV) · ჩეკი/საათში (TPH) · ნაღდის წილი (% + progress bar)
- TPH = receipts_in_period / distinct_active_hours_in_period (from `cashier_hour_breakdown`). Falls back to "—" or "პერიოდი მონიშნე" when no period selected or out of 180-day window.
- Cash share % = `cash / (cash + card) * 100`. Renders as numeric + visual bar.

**Section 2 — „საათობრივი აქტივობა" 24-bar chart:**
- 24 vertical bars showing revenue per hour-of-day, aggregated across the period+store+cashier filter.
- Hover tooltip: `HH:00 — {revenue} ₾ / {receipts} ჩეკი`.
- Empty bars rendered as faint placeholders when no activity. Whole chart hidden behind "პერიოდი მონიშნე" prompt when no period selected.

**Removed (built then reverted in same session):**
- `prevRange` / `prevRevByKey` useMemos and the "წინა პერიოდთან" column. Owner rejected.

### Verification — May 8 ლია (დვაბზუ), exact match

| metric | expected (from cashier_day_breakdown) | derived (new analyses) |
|---|---|---|
| receipts | 9 | 9 ✅ |
| revenue | 126.87 ₾ | 126.87 ₾ ✅ |
| cash | 95.48 | 95.48 ✅ |
| card | 31.39 | 31.39 ✅ |
| **AOV** | — | **14.10 ₾** ✅ |
| **cash share** | — | **75.26%** ✅ |
| **TPH** | — | **4.50** (9 receipts / 2 active hours) ✅ |
| hourly | — | hour 0: 8 receipts / 113.87 ₾ · hour 1: 1 receipt / 13.00 ₾ ✅ |

Cross-midnight shift visible: ლია's "May 8" is actually 7 May late-night carried into 00:xx and 01:xx — MegaPlus-consistent calendar-day cutoff.

### Files changed this session — **uncommitted on local main**

- `dashboard_pipeline/megaplus_backup.py` (new SQL + return-dict entry)
- `dashboard_pipeline/retail_sales.py` (combined accumulator + dict entry)
- `dashboard_pipeline/api_contracts.py` (allowlist entry)
- `rs-dashboard/src/Cashiers.jsx` (analysis table + hourly chart; styles block extended; previous-period code removed mid-session)

### Open ambiguity — RESOLVE FIRST in next session

Owner's final message before handoff: "დღეების შედარება მაღაზიების შედარება ეს არ გვჭირდება". Agent removed period-over-period column (covers "დღეების შედარება") but could NOT identify what "მაღაზიების შედარება" referred to. Possible interpretations agent asked owner (no answer):

1. „· დვაბზუ / · ოზურგეთი" suffix next to each cashier name (in BOTH the existing main table AND the new analysis table)
2. The unified leaderboard rank that mixes cashiers from both stores when "ყველა მაღაზია" filter active
3. Hourly chart aggregating across both stores
4. The new analysis table altogether (since it shows the same cashier × store pairing as the main table)
5. Something else entirely

**Action required:** ask owner explicitly „გვერდის რომელ ადგილს გულისხმობდი როცა თქვი 'მაღაზიების შედარება ეს არ გვჭირდება'?" Show concrete examples (e.g., screenshot crops). Do NOT guess.

### Pending — other items

- Owner did NOT authorize commit/push (per pattern). Local main has 4 + 5 + 2 changes accumulated across three sessions, none pushed.
- Delete obsolete `Financial_Analysis/cashier_names.json` (from 2026-05-11 ღამე session — still unresolved).

### Verification commands (next session)

```powershell
# AOV / cash% / TPH for May 8 ლია — should match table above
"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -c "
import urllib.request, json
api = json.loads(urllib.request.urlopen('http://localhost:8000/api/data?tab=retail_sales', timeout=30).read())
rs = api['retail_sales']
chb = [r for r in rs['cashier_hour_breakdown'] if r['day']=='2026-05-08' and r['object']=='დვაბზუ' and r.get('cashier_name')=='ლია შკუბულიანი']
for r in sorted(chb, key=lambda x: x['hour']):
    print(f\"  hr={r['hour']:>2} rcp={r['receipts']:>3} rev={r['revenue']:>7.2f}\")
# expect hour 0: 8 receipts / 113.87 · hour 1: 1 receipt / 13.00
"
```

---

## ისტორიული session-ები — გადატანილია არქივში

2026-05-05 → 2026-05-11 session-ების ანგარიშები → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-05-05_2026-05-11.md`

წინა ისტორია: `CONTEXT_HISTORY_2026-04_2026-05-02.md` + `CONTEXT_HISTORY_2026-05-03_2026-05-04.md`

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
| Local branch | `main`, 3 modified + 2 untracked (Megaplus Session 1 not yet pushed): `analytics_builders.py`, `api_contracts.py`, `generate_dashboard_data.py`, `tests/test_monthly_pnl_cash_income.py`, `HANDOFF_ARCHIVE/PREVIEWS/SPRINT_MEGAPLUS_CASH_INCOME_PREVIEW.md` |
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
