# SPRINT — Megaplus სალაროს wire-in (cash income → P&L)

> **Status**: PREVIEW · NO CODE CHANGE
> **Date**: 2026-05-08
> **Target sprint**: სექცია 5 (გაყიდვები) cross-cutting + სექცია 9 (P&L) Source-first
> **Trigger**: 2026-05-07 ღამე AI strategic interview-ში გამოჩნდა `net_margin_pct = -178.06%`. Root cause-ის ანალიზი (CONTEXT_HANDOFF.md §0) ცხადია: `total_income` ბანკის card-only ცი- ფრს კითხულობს, ნაღდი ფული P&L income მხარეს არ ჩანს.

---

## TL;DR

`monthly_pnl[].total.pos_income`-ს ახლა მხოლოდ **POS ტერმინალის ბანკის ფული** აყრის — 2,037,224 ₾. ნაღდი ფულის გაყიდვა (Megaplus სალარო) საერთოდ არ ითვლება. გასასწორებელია `build_monthly_pnl`, რომელიც დამატებით retail_sales bundle-ს წაიკითხავს და თვეში ნაღდი ფულის შემოსავალს (cashreg_in = max(0, MAX_POS − bank_card)) მიამატებს. ფორმულა უკვე არსებობს `vat_reconciliation.py:524-525`-ში — გამოცდილია 2026 Q1-ზე — მისი ხელმეორედ გამოყენება და რიცხვების P&L-ში გადატანა-ღაა საჭირო. UI-ის surgical-edit ცალკე ნაბიჯია.

---

## Inventory — რა წავიკითხე და რა ვიპოვე

### წყარო (data flow)

| ფენა | ფაილი | ნაპოვნი |
|---|---|---|
| Pipeline orchestrator | `generate_dashboard_data.py:539-544` | `build_monthly_pnl(pos_terminal_pnl_bundle, tbc_expenses, mapping, bog_expenses)` — retail_sales bundle არ ეძლევა |
| Period-filter callsite | `dashboard_pipeline/api_contracts.py:1385-1390` | მეორე callsite — `_build_pnl_summary_response` |
| P&L builder | `dashboard_pipeline/analytics_builders.py:42-116` | `month_income[month][obj] += pnl_lines.თანხა`. სხვა income წყარო არ აქვს |
| Ratio builder | `dashboard_pipeline/analytics_builders.py:417-419` | `total_income = sum(monthly_pnl[i].total.pos_income)` |
| **Cash formula (already exists)** | `dashboard_pipeline/vat_reconciliation.py:524-525` | `raw_gap = max_pos − bank_card; cashreg_in = max(0.0, raw_gap)` |
| Cash per-shop formula | `dashboard_pipeline/vat_reconciliation.py:540-558` | `by_shop` per-month per-object — Sprint 5.8-ში PROOFED |
| Retail per-month source | `dashboard_pipeline/vat_reconciliation.py:117-128` | `_retail_sales_by_month()` reads `retail_sales_bundle.by_month[].revenue_ge` |
| Retail per-shop-month source | `dashboard_pipeline/vat_reconciliation.py:131-155` | `_retail_sales_by_object_month()` reads `retail_sales_bundle.by_object_by_month` |

### Frontend dependency

`rs-dashboard/src/PnL.jsx`: `m.total?.pos_income` — **15 callsite** (line 89, 92, 93, 141, 145, 156, 210, 218, 228, 323, 463, 504, 530, 544 +1). სხვა რენდერერები (`Forecast.jsx`, `Executive.jsx`, `Insights.jsx`, `DebtPlan.jsx`, `App.jsx`) — იგივე field-ს კითხულობენ. ახალი field-ის დამატება უფრო უსაფრთხოა, ვიდრე `pos_income`-ს გადარქმევა.

### Existing data shape — ვერიფიცირებული 2026-05-07

- `pos_terminal_income.total_ge` = 2,037,224.49 ₾ (POS ტერმინალი, TBC + BOG, card-only) — `data.json`
- `retail_sales.overall.revenue_ge` = (Megaplus სრული გაყიდვა, ცაიდიდება ცარდ + ნაღდი ერთად)
- formula: `cashreg_in = max(0, retail_sales.by_month[m].revenue_ge − tbc_pos[m] − bog_pos[m])` per თვე
- per-object: იმავე formula-ს იყენებ `retail_sales.by_object_by_month` წყაროდ; bank side = `tbc_card_income_bundle.lines` filter-ი object-ით

---

## Output-shape audit (additive — UI უცვლელი დარჩება)

| ველი | სტატუსი | კომენტარი |
|---|---|---|
| `monthly_pnl[i].total.pos_income` | unchanged | UI-ის dependency, არ ვცვლი semantics-ს |
| `monthly_pnl[i].total.cash_income` | **NEW** | ახალი ნაღდი ფული per month per object aggregate |
| `monthly_pnl[i].total.total_income` | **NEW** | `pos_income + cash_income` — ნამდვილი income line |
| `monthly_pnl[i].total.net` | semantics shift | `net = total_income − expenses` (იყო `pos_income − expenses`) |
| `monthly_pnl[i].objects[obj].cash_income` | **NEW** | per-object ნაღდი ფული |
| `monthly_pnl[i].objects[obj].total_income` | **NEW** | per-object pos + cash |
| `financial_ratios.company.total_income` | semantics shift | `sum(total.total_income)` instead of `sum(total.pos_income)` |
| `financial_ratios.company.total_expenses` | unchanged | supplier payments-ი ისევ "expense"-ში ითვლება (იხ. Risk #4) |
| `financial_ratios.company.net_margin_pct` | recalculates | ცარდ-ი + ნაღდი / expenses → -178%-ი ბევრად შემცირდება |
| `financial_ratios.company.gross_margin_pct` | currently aliased | `== net_margin_pct`. ცალკე COGS detach-ი არაა scope-ში |

---

## Fingerprint inputs

ცაცე-ხე გავლენა: `build_monthly_pnl`-ი caching-ის ნაწილი არ არის (in-memory call). მაგრამ retail_sales bundle-ს თავისი caching აქვს (`pipeline_cache.json`). ცაცე-ის invalidation დამოკიდებულია retail_sales-ის source ფაილების fingerprint-ზე. ცვლილება არ ცვლის cache contract-ს.

---

## Risks / pitfalls

1. **Double-counting (HIGH if naive)** — თუ `total_income = pos_terminal + retail_sales.revenue` უბრალოდ შევაგროვოთ, card payments ორჯერ ჩაითვლება (Megaplus სრულ გაყიდვაშიც წერია, ბანკის POS-შიც). `vat_reconciliation.py`-ის formula (`max_pos − bank_card`) ამას უკვე აგვარებს. **ვალდებულება: იგივე formula გამოვიყენო, არა sum.**

2. **`bank_exceeds_max` anomaly (MED)** — როცა bank_card > MAX_POS (data-quality issue, ნახეს Sprint 5.8-ში), `cashreg_in` clamp-ი 0-ზე. ეს ნიშნავს რომ ცარდ-ი არ შეიცვლება, მაგრამ ნაღდი ფული underestimated-ია. Surface-ი — `data_quality.bank_exceeds_max[]` ფლეგი per problematic month.

3. **Per-object alignment (MED)** — TBC POS per-shop attribution არასრულია (`tbc_per_shop_reliable` flag, vat_reconciliation.py:566-568). თვეებში სადაც TBC <98% attributed, per-object cash_income-ი არ უნდა იყოს გარანტირებული — ან საერთო `OBJECT_UNALLOCATED`-ში გადადის, ან `data_quality.tbc_per_shop_reliable=false` flag-ით უნდა გამოიყოფა.

4. **Supplier payments still in expenses (HIGH for მარჟის ინტერპრეტაცია)** — root cause-ის მეორე ნაწილია. დამოუკიდებელი sprint. ამ wire-in-ის შემდეგ მარჟა ისევ შესაძლოა negative-ი იყოს (cash + card − supplier_payments − operating). User-ს უნდა ავუხსნა: "ეს pass 1 — ნაღდი ფული შემოვა. Pass 2 — supplier payments expense-დან COGS-ში გადავა."

5. **Period-filter callsite (LOW)** — `api_contracts.py:1385` `build_monthly_pnl`-ს period-filtered POS lines-ით ეძახის. retail_sales bundle აქ caching-დან უნდა მოვაშოო. signature change ან bundle-ის thread-ი — `_build_pnl_summary_response` ცალცალკე გასასწორებელი.

6. **Test fixture compat (LOW)** — `tests/test_ai_forecasting.py:11` `build_monthly_pnl` row shape-ს mock-ავს. Test-მა ახალი field-ები უნდა ცნოს ან საერთოდ არ მოეთხოვოს — additive change-ის გამო, არსებული ტესტები არ უნდა გატყდეს.

7. **Frontend ცარიელი მიგრაცია (LOW)** — UI ჯერ ისევ `pos_income`-ს კითხულობს, ანუ ახალ ციფრებს არ აჩვენებს. ცალკე ნაბიჯი: PnL.jsx-ში `total_income`-ის გადასვლა + cash_income separate row. ⚠️ wire-in-ის შემდეგ preview screenshot აუცილებელია, რომ UI არც ერთ ციფრს არ კარგავდეს.

---

## Scope recommendation — split

ერთ session-ში ცდის ცდუნება მაგარია, მაგრამ recommend-ია **2 session split**:

### Session 1 (TOP priority — wire-in backend) ~1 session
1. `build_monthly_pnl` — retail_sales_bundle parameter დამატება, per-object per-month cashreg_in computation, ახალი fields (`cash_income`, `total_income`).
2. ორი callsite update — `generate_dashboard_data.py:539` + `api_contracts.py:1385`.
3. `build_financial_ratios` — `total_income` სვეტს დამატებითი fallback (თუ `total_income` არსებობს — ის წაიკითხე; თუ არა — `pos_income` როგორც ადრე).
4. 5+ spot-check on real data.json (ყოველთვიური per-object: pos_income + cash_income vs MAX POS revenue-ს ცდის ცდის).
5. ერთი test file — `tests/test_monthly_pnl_cash_income.py` (8-10 ცდის).

### Session 2 (UI surface) ~0.5-1 session
1. PnL.jsx — `total_income`-ის გადასვლა + ცალკე "ნაღდი ფული" row (lines 89/210/218/228/463/504/530/544).
2. Forecast / Executive / Insights / DebtPlan — დანარჩენი 4 callsite.
3. Smoke-test browser-ში; per-tab ციფრები.

### Deferred (not this sprint)
- COGS detachment (supplier payments expense-დან COGS-ში გადატანა) — სრულიად ცალკე sprint.
- gross_margin_pct vs net_margin_pct deduplication — same.
- rs.ge ცაცური აპარატის API verification — handoff §0-ში deferred.

---

## Test plan (Session 1) — 8 ცდის pattern after `tests/test_samurneo_incremental.py`

| # | ცდის name | ფიქსავს |
|---|---|---|
| 1 | `test_cash_income_when_max_exceeds_bank` | `cashreg_in = max_pos − bank_card` შეფასება |
| 2 | `test_cash_income_zero_when_bank_exceeds_max` | clamp 0-ზე + flag |
| 3 | `test_per_object_cash_income_matches_per_shop_formula` | object-by-month parity vat_reconciliation by_shop-თან |
| 4 | `test_total_income_equals_pos_plus_cash` | invariant: `total_income = pos_income + cash_income` |
| 5 | `test_pos_income_field_unchanged_for_ui_compat` | regression guard: `pos_income` არ იცვლება |
| 6 | `test_financial_ratios_uses_total_income_when_present` | `build_financial_ratios` ახალი field-ს კითხულობს |
| 7 | `test_financial_ratios_falls_back_to_pos_income` | backward compat: ძველი data.json-ის format |
| 8 | `test_period_filter_response_includes_cash_income` | `_build_pnl_summary_response` callsite |

ცდილობა: in-process tests, არ ვამოწმებ ცაცე-ის I/O-ს; fixture-ად 2-3 month-ის synthetic retail_sales bundle + 2-3 month-ის synthetic POS bundle.

---

## Files expected to change

| ფაილი | ცვლილების ტიპი | ხაზი (განახ.) |
|---|---|---|
| `dashboard_pipeline/analytics_builders.py` | edit | `build_monthly_pnl` სიგნატურა + body, `build_financial_ratios` fallback (~30 ხაზი) |
| `generate_dashboard_data.py` | edit | line 539 callsite — retail_sales_bundle pass-through (~3 ხაზი) |
| `dashboard_pipeline/api_contracts.py` | edit | line 1385 callsite — cache-დან retail_sales bundle მოპოვება (~5 ხაზი) |
| `tests/test_monthly_pnl_cash_income.py` | NEW | ~150 ხაზი, 8 ცდის |
| `tests/test_ai_forecasting.py` | maybe edit | მხოლოდ თუ row-shape mock იშლება |
| `CONTEXT_HANDOFF.md` | append | session closure-ში — § new section |

**Frontend (Session 2 ცალკე):**
- `rs-dashboard/src/PnL.jsx` — 15 callsite `pos_income` → `total_income`, plus new "ნაღდი ფული" row.
- `rs-dashboard/src/{Forecast,Executive,Insights,DebtPlan,App}.jsx` — minor callsite updates.

---

## Self-check checklist (pre-commit Session 1)

- [ ] `build_monthly_pnl` pure function — retail_sales_bundle parameter optional (default None) რათა test fixtures არ გატყდეს
- [ ] cashreg_in formula = identical to `vat_reconciliation.py:524-525` (copy, არა divergent re-implementation)
- [ ] per-object split — TBC `tbc_per_shop_reliable` flag respected (UNALLOCATED bucket)
- [ ] backward-compatible: `monthly_pnl[i].total.pos_income` არსებობს, semantic-ი იგივეა
- [ ] `pytest tests/test_monthly_pnl_cash_income.py -v` — 8/8 პასიერი
- [ ] `pytest tests/` — წინა ტესტებიდან არც ერთი არ გატყდა (target: regression-free)
- [ ] real `data.json` regen → `financial_ratios.company.total_income` 2.04M-ის ნაცვლად ~2.6-3.0M (Megaplus 2026 Q1 ~600K cash)
- [ ] 5+ spot-check: per-month per-object cashreg_in vs vat_reconciliation by_shop[month][object].cashreg_in_ge — IDENTICAL
- [ ] UI smoke-test (PnL ჩანართი) — `pos_income` ცარდ-ის ციფრი იგივე რჩება (UI-ის regression guard)

---

## Evidence sources

- **Files**: `dashboard_pipeline/analytics_builders.py:42-116, 395-481` · `dashboard_pipeline/vat_reconciliation.py:117-155, 490-610` · `generate_dashboard_data.py:255-257, 539-549, 1456-1490` · `dashboard_pipeline/api_contracts.py:1378-1392` · `dashboard_pipeline/retail_sales.py:278-398` · `rs-dashboard/src/PnL.jsx` (15 callsite)
- **Verified facts**: `CONTEXT_HANDOFF.md §0` (margin -178% root cause) · `CONTEXT_HANDOFF.md §6` (`total_income=2.04M` (bank-only), `total_expenses=5.66M`)
- **Existing PROOFED formula**: `vat_reconciliation.py` Sprint 5.8 (commit history) — per-shop `cashreg_in` per month, audit-tested
- **Git head**: branch `main` at `b91587e` (2026-05-07 ღამე)
- **Index status**: GitNexus indexed `financial-dashboard` (5654 symbols) — fresh

---

**End of preview · NO CODE CHANGE made**
