# Phase 2.11 — Dead Stock + Salvage Plan (PREVIEW)

> სტატუსი: 🟡 **PREVIEW DRAFT** (2026-04-20 12:55) — user-ის approval მოლოდინში
> ენა: ქართული (user); კოდი + commit: ინგლისური
> Pattern: Phase 1 Part A/B/C/D-ის preview-first workflow-ს იცავს

---

## 🎯 TL;DR — სამ წინადადებად

1. **შენს მაღაზიებში 7.1M ₾ კანდიდატი "გაყინული ფული" გვაქვს** — შემოტანილი პროდუქცია, რომელიც 90+ დღე დაუყიდველია (ან საერთოდ არასოდეს გაყიდულა).
2. AI-ს მიეცემა ერთი ახალი tool — `analyze_dead_stock` — რომელიც `imported_products` ⊕ `retail_sales`-ს triangulate-ს და თითო-თითო SKU-ზე ფასდაკლების / დაბრუნების / write-off-ის რეკომენდაციას იძლევა.
3. SYSTEM_PROMPT_KA-ში დაემატება ცალკე სექცია (`💀 Dead Stock Detection`), რომელიც AI-ს უკარნახებს როდის და როგორ გამოიყენოს ეს tool — strategic question-ებისთვის, არა ცარიელი data lookup-ისთვის.

---

## 🔍 რა აღმოვაჩინე ცოცხალი probe-ში (2026-04-20 12:50)

ციფრები ფაქტობრივი data.json-დან (44 თვე ისტორია, 13,344 imported პროდუქტი, 8,286 retail_sales პროდუქტი):

| ფაქტი | ციფრი | რას ნიშნავს |
|---|---|---|
| Imported, ფაქტობრივად გაყიდული პროდუქცია | **3,533** | მხოლოდ 26%-ის sell-through |
| Imported, **არასოდეს არ გაყიდული** | **9,811** | 74% ფაქტობრივად სუფთა "frozen" |
| ბოლო გაყიდვა < 30 დღე | 0 | (ეს უცნაურია — შეიძლება data quality) |
| ბოლო გაყიდვა 31-90 დღე | 742 | "ცოცხალი" tail |
| ბოლო გაყიდვა 91-180 დღე | **918** | "stale" zone — 1-ლი ფასდაკლების კანდიდატი |
| ბოლო გაყიდვა 181-365 დღე | **886** | "deeply stale" — მძიმე ფასდაკლება / დაბრუნება |
| ბოლო გაყიდვა 365+ დღე | **987** | "dead" — write-off / liquidation |
| **TOTAL frozen cash (zero-sale + 90+d)** | **GEL 7,105,031.73** | ⚠️ ზედა შეფასება (იხ. ქვემოთ) |

### ⚠️ მნიშვნელოვანი caveat — ციფრი ზუსტი არ არის

Top 10 "Never sold" SKU-ში პირველ ხუთიანში არიან:
- **შეფუთული ქვის პური** (178K ₾) — ცხადია ცხელი პურია, ფაქტობრივად ყოველდღე იყიდება
- **2ლ კოკა-კოლა** (122K ₾) — basics
- **5 სიგარეტი ბრენდი** (კომპაქტი + ქემელი + პარლამენტი + Vip Blue + Black Tip)

ეს არ არის dead stock — ეს არის **product_code matching ბუგი**: `imported_products`-ში SKU-ს ერთი code-ი აქვს, `retail_sales`-ში სხვა (`barcode` vs `product_code`). რეალური dead stock სავარაუდოდ ბევრად ნაკლებია — შეფასებით **300K – 1.5M ₾** მერყეობა, არა 7.1M.

ე.ი. **Phase 2.11 უნდა ემსახურებოდეს ორ მიზანს:**
1. **(პირველი)** დავამატოს product matching layer — barcode + name fuzzy match კოდის გვერდით
2. **(მეორე)** ცხადი dead stock რეკომენდაცია მხოლოდ matched products-ზე

---

## 💬 Before / After — როგორ ისაუბრებს AI

### Before (ამჟამად)

> **User:** "რა SKU-ები მაქვს stock-ში დიდი ხანია? რა გავაკეთო?"
>
> **AI (Phase 1 Part D):** "გავიქცე — `read_data_json(section='imported_products', limit=10)`, `read_data_json(section='retail_sales', limit=10)` — ვხედავ 13K imported და 8K sold. ცხადი dead stock view-ი data.json-ში არ არსებობს. შეიძლება Excel-ში პირდაპირ ვცადო… ☹️ ვერ ვიპოვე ცხადი მონაცემი."

ამჟამად AI-ს არ აქვს tool რომელიც მზად dead-stock-ის ცხრილს ბრუნებს. `read_data_json`-ი ნედლი მონაცემია, AI ცდილობს გონებაში გადააკეთოს — Calculator Enforcement-ის გამო ფაქტობრივად ვერ გადააკეთებს.

### After (Phase 2.11-ის შემდეგ)

> **User:** "რა SKU-ები მაქვს stock-ში დიდი ხანია? რა გავაკეთო?"
>
> **AI:**
> *🔍 ვხედავ: შენი მონაცემები 90+ დღე stock-ში მყოფი 374 SKU-ის შესახებ.*
> *📊 frozen cash: 467,820 ₾ (matched products only — არ ვითვლი ცრუ "Never sold" კატეგორიაში მოხვედრილ ყოველდღიურ პროდუქტს).*
>
> **🟢 საიმედო რეკომენდაცია:**
>
> | მოქმედება | SKU-ები | Freed cash | სავარაუდო timeline |
> |---|---|---|---|
> | **−15% ფასდაკლება** (91-180d zone) | 142 | 187K ₾ | 3 კვირაში |
> | **−30% ფასდაკლება** (181-365d zone) | 119 | 156K ₾ | 4-6 კვირა |
> | **მომწოდებელს დაუბრუნე** (365+d, contractual) | 38 | 89K ₾ | მომდევნო შეხვედრამდე |
> | **Write-off** (365+d, expired) | 75 | 35K ₾ | მიმდინარე თვე |
>
> **🎯 პრიორიტეტი #1:** ბოლო თვის ფონდი 467K-ს რომ მოვუფერებთ, "ცოცხალი" inventory turnover-ი 3.2 → 4.8 გაიზრდება (45% improvement).
>
> 💡 *რჩევა:* ერთიანად ნუ გაშვებ — დაიწყე ოზურგეთის top-30 stale-ით, შემდეგ დვაბზუ. წყარო: `data.json → imported_products + retail_sales (matched 3,533 SKUs, 90d cutoff 2026-01-20)*

---

## 🛠️ Scope — რა შეიცვლება

### კოდის მხარე (2 ფაილი)

**1. ახალი მოდული `dashboard_pipeline/ai/dead_stock.py` (~250 ხაზი)**

ფუნქცია `analyze_dead_stock(data_loader, *, days_threshold=90, store=None, top_n=20)`:

ბრუნებს stable JSON-safe contract:

```json
{
  "as_of_date": "2026-04-20",
  "days_threshold": 90,
  "store_filter": "ჯამი",
  "summary": {
    "matched_products": 3533,
    "matched_total_imported_amount": 1007683.80,
    "active_count": 742,
    "stale_91_180d_count": 918,
    "stale_181_365d_count": 886,
    "dead_365d_plus_count": 987,
    "frozen_cash_estimate": 467820.00,
    "matching_warning": "9811 imported SKUs unmatched in retail_sales — barcode/code drift, see /data quality"
  },
  "top_stale_skus": [
    {
      "product_code": "1234",
      "product_name": "...",
      "imported_amount": 25000.00,
      "imported_quantity": 120,
      "last_sold_date": "2025-08-15",
      "days_since_last_sale": 248,
      "top_supplier": "შპს ...",
      "recommended_action": "discount_30",
      "expected_freed_cash": 17500.00
    },
    ...
  ],
  "by_action_summary": {
    "discount_15_pct": {"sku_count": 142, "freed_cash_estimate": 187000.00},
    "discount_30_pct": {"sku_count": 119, "freed_cash_estimate": 156000.00},
    "supplier_return": {"sku_count": 38, "freed_cash_estimate": 89000.00},
    "write_off": {"sku_count": 75, "freed_cash_estimate": 35000.00}
  }
}
```

**მთავარი დიზაინ რჩევა:**
- product_code matching ⊕ barcode fallback ⊕ ფუძი normalize (lowercase, trim, remove punctuation)
- ფასდაკლების ლიმიტი (15% / 30% / 45%) — ცხადი rule, არა AI guess (`gross_margin_pct`-ის მიხედვით)
- "expected freed cash" = `imported_amount × discount_factor × historical_velocity_factor`
- "matching_warning" — explicit caveat რომ AI-ს ცხადად აცნობოს მონაცემთა ხარისხი

**2. `dashboard_pipeline/ai/tools.py`**

- `ANALYZE_DEAD_STOCK_TOOL` schema — `TOOL_SCHEMAS[9]` (journal-ის შემდეგ, investigator-ის წინ)
- `ToolDispatcher` route-ი
- TOOL_SCHEMAS length: **13 → 14**

### Prompt-ის მხარე (1 ფაილი)

**3. `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA`**

ახალი სექცია `💀 Dead Stock-ის გამოვლენა (CRITICAL — Phase 2.11)`:

განთავსება: `🏪 მაღაზიების DNA`-ს შემდეგ, `🔄 საკუთარი თავის გასწორების ციკლი`-ს წინ (logical flow: ჯერ ვიცნო მაღაზიის DNA, შემდეგ ცარიელი inventory-ის ანალიზი, მერე retry/fallback discipline).

შინაარსი:
- **Trigger list** (როდის გამოიყენე `analyze_dead_stock`):
  - "რა დიდი ხანია stock-ში?" / "რა SKU-ები არ იყიდება?"
  - "გაყინული ფული" / "frozen cash" / "working capital ანალიზი"
  - "მომწოდებელს რა დავუბრუნო?" / "ფასდაკლების კანდიდატები"
- **Anti-trigger** (როდის *არ* გამოიყენო):
  - "რა მაქვს stock-ში სულ?" → `read_data_json(section='imported_products')` (ცარიელი count, არა dead stock)
  - "ბოლო გაყიდვები" → `read_data_json(section='retail_sales')`
  - "მომწოდებელთან ვალი" → `read_data_json(section='supplier_aging')`
- **Output format** — სავალდებულო ცხრილი (action / SKU count / freed cash / timeline) + 🟢/🟡/🟠 confidence
- **Matching warning awareness** — თუ `matching_warning` დაბრუნდა, AI-მ უნდა ცხადად ახსენოს user-ს რომ ციფრი "ზედა შეფასებაა"
- **Multi-store guidance** — ცალკე ანალიზი ოზურგეთი vs დვაბზუ (Part C DNA-ს საფუძველზე)

### ტესტები (1 ახალი + 4 update)

**ახალი:** `tests/test_ai_dead_stock.py` — დაახლოებით 35 ცდა:
- `TestAnalyzeDeadStockMatching` (8) — code/barcode/name match precedence
- `TestStaleBucketSplit` (5) — 91-180 / 181-365 / 365+ buckets
- `TestRecommendedAction` (6) — margin × age decision tree
- `TestFrozenCashCalculation` (4) — discount factor × velocity
- `TestStoreFilter` (3) — total / ოზურგეთი / დვაბზუ
- `TestMatchingWarning` (3) — when emitted, when suppressed
- `TestEdgeCases` (6) — empty data, no imported, no sales, missing dates

**Updates** (tool count 13 → 14):
- `test_ai_memory.py::test_tool_count_is_14`
- `test_ai_forecasting.py::test_tool_count_is_14`
- `test_ai_journal.py::test_tool_count_is_14`
- `test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed`

ჯამში pytest: **976 → ~1011 green** (+35 new dead_stock + 4 updates with same count).

---

## 🚫 NOT in scope (parking-lot)

- ❌ მომწოდებელთან რეალური negotiation tool — Phase 2.12 (Supplier Negotiation Prep)
- ❌ Dashboard UI tab (Dead Stock Liquidation page) — Phase 3.4 / 3.7 (UI-layer Roadmap-ში)
- ❌ Auto-execute discount actions — AI არ იწვევს რაიმე mutation-ს, მხოლოდ რეკომენდაციას იძლევა
- ❌ ცხადი product matching ML model — barcode/code fuzzy match დაინერგება, მაგრამ semantic embedding match (ChromaDB-ით) parking-lot-ში გადადის
- ❌ Aggregator tool დიდი Excel-ისთვის (1000+ row) — Excel-Path Fix-ის separate-კონცერნი, ცალკე iteration

---

## ⚠️ რისკები + caveats

| რისკი | მიტიგაცია |
|---|---|
| **Product code mismatch** (74% imported არ არის retail_sales-ში) | AI-მ ცხადად მიუთითოს `matching_warning`; ციფრი "ზედა შეფასებაა" კი არა "ზუსტი დიაგნოზი" |
| **Discount factor heuristic** (15/30/45%) მცდარი იქნება ზოგ კატეგორიაზე | AI-ს ცხადი instructions, რომ ციფრი "first-cut", მაღაზიის ცოცხალი ცოდნა > AI rule |
| **Velocity assumption** (3 კვირა / 4-6 კვირა liquidation) — სავარაუდო, არა ცოცხალი | AI-მ უნდა მიუთითოს როგორც 🟡 ვარაუდი, არა 🟢 ფაქტი |
| **Store-level breakdown** — retail_sales-ის object_breakdown-ი ხელმისაწვდომია, მაგრამ imported_products store-ის გარეშეა (ერთი pool) | Phase 2.11 v1: მხოლოდ "total" + per-SKU object hint via retail_sales; per-store imported allocation parking-lot |

---

## 🎬 ცოცხალი dog-food-ის გეგმა (post-code)

Backend restart-ის შემდეგ ცოცხლად დავუსვამ AI-ს ორ კითხვას:

**1. Direct dead stock query:**
> "რა SKU-ები გვაქვს stock-ში 90+ დღე გაუყიდველი? რა მოვიმოქმედო?"

ვამოწმებ:
- ✅ AI იძახებს `analyze_dead_stock(days_threshold=90)`
- ✅ Output ცხრილია (4 action × SKU count × freed cash)
- ✅ Matching warning ცხადად მიუთითებს
- ✅ Confidence labels ცხადია (🟢 / 🟡 / 🟠)
- ✅ Recommendation actionable (კონკრეტული ნაბიჯი + timeline)
- ✅ Store-level differentiation (ოზურგეთი vs დვაბზუ — Part C DNA)

**2. Multi-hop strategic query (5-hat):**
> "750K ₾ working capital გვაქვს. გადავწყვიტო — ახალი მაღაზია ვიყიდო 200K-ით თუ inventory liquidation გავაკეთო? რა გავაკეთო?"

ვამოწმებ:
- ✅ 5 ქუდი (💼 / 🔧 / 🎯 / ⚠️ / 🪞)
- ✅ Multi-hypothesis (3 ვერსია: liquidation-only / capex-only / mixed)
- ✅ `analyze_dead_stock` + `read_data_json(financial_ratios)` + `forecast_revenue` triangulation
- ✅ Phase 1 Part C DNA-ის გამოყენება (capex timing — Part B Monthly rhythm)
- ✅ `journal_add_entry` recommendation auto-stamped

---

## ✅ Acceptance criteria

- [ ] `dashboard_pipeline/ai/dead_stock.py` მზადაა + lazy imports (Path-Fix-ის ფიქსი არ ფუჭდება)
- [ ] `tools.py` TOOL_SCHEMAS = 14, dispatcher route-ი მუშაობს
- [ ] `prompts.py::SYSTEM_PROMPT_KA` ახალი 💀 Dead Stock სექცია, investigator prompt **untouched** (15+ marker leak guard)
- [ ] `tests/test_ai_dead_stock.py` ~35 cases green
- [ ] 4 existing test files updated for tool count 13 → 14
- [ ] pytest **~1011/1011 green** (was 976; +35; 0 weakened)
- [ ] Backend restart #10 + in-process 3-5 marker probe (chat present, investigator absent)
- [ ] ცოცხალი Anthropic dog-food: 2 კითხვა, ორივე pass

---

## 🔗 Carry-forward dependencies

- **Excel-Path Fix** ✅ COMPLETE (2026-04-20 12:45) — `read_excel_source` ქართულ ფოლდერებზე მუშაობს, ცალკე triangulation tool dead_stock-ში სავალდებულოა
- **Phase 1 Part C — Multi-Store DNA** ✅ COMPLETE (2026-04-20 02:11) — store-level guidance იცის DNA-ის საფუძველზე
- **Phase 1 Part D — Self-Correction Loop** ✅ COMPLETE (2026-04-20 02:50) — AI ცხადად იცის, რომ "0 hits ≠ არ არსებობს", retry protocol მუშაობს
- **Phase 0A Calculator Enforcement** ✅ COMPLETE — AI ვერ ცდილობს row-by-row გონებაში სუმირებას, `analyze_dead_stock`-ის output ფაქტობრივად ცხადია

---

## 🚦 Estimated dev time

- კოდი (`dead_stock.py` + tools/prompts): **3-4 საათი**
- ტესტები (35 ახალი): **1.5 საათი**
- Backend restart + verification: **30 წუთი**
- ცოცხალი dog-food + journal + summary: **30 წუთი**
- **TOTAL: ~6 საათი** (1 dev day)

---

## 📋 user-ის გადასაწყვეტი

1. **დავიწყოთ კოდი ახლა?** (`კი`)
2. **მინდა ცვლილება scope-ში** (აღწერე — რა დაუმატო/მოვაკლო)
3. **საერთოდ სხვა მიდგომა გირჩევნია** (მაგ: ჯერ data quality issue გავასწოროთ — product matching layer ცალკე pre-Phase 2)
