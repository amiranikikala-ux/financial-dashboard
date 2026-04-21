# Phase 2.12 — Supplier Negotiation Brief (PREVIEW)

> სტატუსი: 🟡 **PREVIEW DRAFT** — user-ის approval მოლოდინში
> ენა: ქართული (user); კოდი + commit: ინგლისური
> Pattern: Phase 2.11-ის preview-first workflow-ს იცავს

---

## 🎯 TL;DR — სამ წინადადებად

1. **ფაქტი**: შენი 270 მომწოდებლიდან მხოლოდ 5 ფარავს შენი შესყიდვების 42%-ს — ეს ნიშნავს რომ სწორი 5 შეხვედრა შეიძლება იყოს **13-40K ₾ წლიური დაზოგვის** ტოლი.
2. AI-ს მიეცემა ერთი ახალი ხელსაწყო — **`prepare_supplier_brief`** — რომელიც ნებისმიერ მომწოდებელზე აწყობს "1-გვერდიან ცნობას": რამდენს ვყიდულობ, როგორ ვიხდი, რა ფასში ვარ ბაზართან შედარებით, 2-3 მზა შეთავაზება რომ ხვალ მოლაპარაკებაზე წაიღო.
3. SYSTEM_PROMPT-ში დაემატება ცალკე სექცია (`📞 Supplier Negotiation`), რომელიც AI-ს უკარნახებს როდის გამოიყენოს ეს ხელსაწყო — როცა user ჰკითხავს "ჯიდიაი-სთან მაქვს შეხვედრა" ან "ვის ფასდაკლება ვთხოვო".

---

## 🔍 რა აღმოვაჩინე ცოცხალ data-ზე probe-ში

**ცოცხალი ცვლადები `data.json`-დან:**

| ფაქტი | რიცხვი | რას ნიშნავს |
|---|---|---|
| სულ მომწოდებელი RS-ში | **270** | |
| Top 5 მომწოდებლის წილი | **41.9%** | კლასიკური Pareto — სწორი 5 შეხვედრა = მთლიანი portfolio-ის 42% |
| Top 10 წილი | 53.8% | |
| Top 20 წილი | 67.4% | 80/20 rule ცოცხლად აქ ჩანს |
| Dual-sourced პროდუქცია (ერთზე მეტი მომწოდებელი) | **304 SKU** | კონკრეტული price leverage signals |
| მათგან ფასის სხვაობა > 3% | **292** | უკვე "ვის გადავიდე" გადაწყვეტილებები |

### 🎯 კონკრეტული leverage მაგალითი (ცოცხალ data-დან)

ყველაზე გარკვეული სიგნალი — **Coca-Cola-ს პროდუქცია**:

| პროდუქტი | ჩემი მომწოდებელი | ჩემი ფასი | იაფი ალტერნატივა | alt ფასი | gap | ჩემი წლიური ხარჯი |
|---|---|---|---|---|---|---|
| 2ლ კოკა-კოლა (6ც.) | კოკა-კოლა გურია | 3.80 | კოკა-კოლა დისტრიბუცია | 3.56 | **+6.7%** | 106,874 ₾ |
| კაპი ფორთოხალი 0.5ლ | კოკა-კოლა გურია | 2.18 | კოკა-კოლა დისტრიბუცია | 1.97 | **+10.7%** | 20,257 ₾ |
| 1.5ლ კოკა-კოლა (6ც.) | კოკა-კოლა გურია | 3.10 | კოკა-კოლა დისტრიბუცია | 2.91 | **+6.5%** | 20,089 ₾ |
| 2ლ ფანტა (6ც.) | კოკა-კოლა გურია | 3.80 | კოკა-კოლა დისტრიბუცია | 3.56 | **+6.8%** | 19,333 ₾ |
| ბერნი (12ც.) | კოკა-კოლა გურია | 1.64 | კოკა-კოლა დისტრიბუცია | 1.57 | +4.2% | 24,093 ₾ |

**თუ ცოცხალი ფასდაკლებით მიხვალ "კოკა-კოლა გურია"-სთან** — ~190K ₾ annual spend-ზე 6.7% მოთხოვნა → **~13K ₾ წლიური დაზოგვა**.

### ⚠️ მნიშვნელოვანი caveat

Unit price იზომება როგორც `total_amount_ge / total_quantity` — ეს ცოცხალი ფასი არის, მაგრამ **შეიძლება საფარგების (VAT), შეფუთვის ერთეულის ან პერიოდის განსხვავების გამო ცდომილება იყოს**. ამიტომ tool-ი აუცილებლად დააბრუნებს `matching_warning`-ს თუ:
- compared suppliers ცოცხალი სხვადასხვა თვეებში იყიდებოდნენ (ფასი დროში იცვლება)
- quantity < 5 ცალი (statistically შიშველი)
- unit mismatch (ცალი vs კგ)

---

## 💬 Before / After — როგორ ისაუბრებს AI

### Before (ამჟამად)

> **User:** "ხვალ ჯიდიაი-სთან მაქვს შეხვედრა. რა ვთხოვო?"
>
> **AI:** *(ცდება `read_data_json(section='suppliers')` — იღებს 270 row-ს, ცდილობს სუბიექტურად გარჩევას. Calculator Enforcement-ის გამო ვერ გაკეთდება arithmetic — ამიტომ დაბრუნდება სავარაუდოდ ზოგადი რჩევით "ფასდაკლება ჰკითხე").*

AI-ს **არ აქვს strategic lens-ი** მომწოდებელზე — არ იცის ჩემი share, ფასდაკლების potential, payment leverage, comparables.

### After (Phase 2.12-ის შემდეგ)

> **User:** "ხვალ ჯიდიაი-სთან მაქვს შეხვედრა. რა ვთხოვო?"
>
> **AI:** *🔍 ვხედავ — "შპს ჯიდიაი" (406181616) შენი #1 მომწოდებელია.*
>
> **📊 ჩემი leverage შენს სასარგებლოდ: 🟢 HIGH (78/100)**
>
> | ფაქტორი | რიცხვი | რას ნიშნავს |
> |---|---|---|
> | **ჩემი წილი მომწოდებლის სავარაუდო portfolio-ში** | 17% | შენ მისი ერთ-ერთი დიდი კლიენტი ხარ |
> | **ჩემი წლიური შესყიდვა** | 897,043 ₾ | 628 ზედნადები, 11 თვე ისტორიაში |
> | **გადახდის დისციპლინა** | ✅ სუფთა ბანკი | 583K გადახდილი, 314K დავალიანება (35% unpaid — leverage!) |
> | **ბოლო შესყიდვა** | 5 დღის წინ | relationship-ი ცოცხალია |
>
> **🎯 3 შესათავაზებელი formulation (პრიორიტეტის მიხედვით):**
>
> **#1 — Cash discount-ი payment speed-ზე** *(🟢 მაღალი შანსი)*
> > *"314K ₾ დავალიანება მაქვს. თუ 15 დღეში დავფარავ, მომეცი 4% ფასდაკლება მომდევნო 3 თვის შესყიდვაზე."*
>
> რატომ მუშაობს: მომწოდებელს cash flow problem უფრო ძვირი უჯდება ვიდრე 4% margin-ის დათმობა. კონკრეტული ცხადი ოფერი + deadline.
>
> **#2 — Volume commitment** *(🟡 საშუალო შანსი)*
> > *"მომავალ კვარტალში 250K ₾ ვარ მზად ერთი contract-ში შეხვედრაზე. თუ blanket order-ს ვაფორმებ, მინდა 3% volume discount + ბარკოდის ფასდასშენობა (Q3).*
>
> **#3 — Dual-source leverage** *(🟠 მხოლოდ საჭიროების შემთხვევაში)*
> > *"საქართველოს დისტრიბუცია და ლოგისტიკა-ც გვაქვს ხელში (ჩვენი #10 მომწოდებელი). იქ price/quality ცოცხალია, მაგრამ მე შენთან კომფორტი მიყვარს — თუ შენ გქონდეს კონკურენტული ცხრილი, მე მზადა ვარ volume გავზარდო."*
>
> ⚠️ **სად არ უნდა დააჭერო:**
> - მიწოდების სიხშირე (628 ზედნადები 11 თვეში = ~8 ზედნადები/კვირაში) — ეს მისთვის ოპერაციული ფასია, საჯარო არ არის.
> - 35% დავალიანების ზომა — ნაცვლად "ჩემი payment slow-ია"-ს, მას ლოგიკური მხრიდან წარადგინე ("cash timing opportunity").
>
> წყარო: `data.json → suppliers[ჯიდიაი] + imported_products.suppliers + supplier_aging[ჯიდიაი]`

---

## 🛠️ Scope — რა შეიცვლება

### კოდის მხარე (2 ფაილი)

**1. ახალი მოდული `dashboard_pipeline/ai/supplier_brief.py` (~350 ხაზი)**

ფუნქცია `prepare_supplier_brief(data_loader, *, supplier_name=None, tax_id=None, lookback_months=12)`:

**Resolution logic:**
- თუ `tax_id` — direct match
- თუ `supplier_name` — fuzzy match via `normalize_name` (Georgian-aware)
- თუ ორივე არარის — `PortfolioConcentrationReport` (Pareto view)

**მთავარი output სექციები:**

```json
{
  "supplier": {
    "tax_id": "406181616",
    "resolved_name": "შპს ჯიდიაი",
    "match_confidence": "high",
    "match_source": "tax_id_exact"
  },
  "as_of_date": "2026-04-20",
  "lookback_months": 12,

  "volume_snapshot": {
    "total_spend_ge": 897043.21,
    "portfolio_share_pct": 17.2,
    "waybill_count": 628,
    "distinct_product_count": 87,
    "distinct_month_count": 11,
    "first_waybill_date": "2025-05-01",
    "last_waybill_date": "2026-04-15",
    "monthly_avg_ge": 81549.38,
    "ranking_among_suppliers": 1
  },

  "payment_profile": {
    "total_billed_ge": 897043.21,
    "total_paid_ge": 583121.00,
    "current_debt_ge": 313922.21,
    "payment_scope": "strict_bank_only",
    "days_since_last_activity": 5,
    "aging_bucket": "0-30",
    "reliability_label": "✅ clean",
    "reliability_note": "ბანკის ავტო-დადასტურებული ნაკადი; ცდომილება < 1%"
  },

  "price_benchmark": [
    {
      "product_code": "123456",
      "product_name": "2ლ კოკა-კოლა (6ც.)",
      "unit": "ცალი",
      "my_avg_unit_price_ge": 3.80,
      "market_alternatives": [
        {"supplier": "კოკა-კოლა დისტრიბუცია", "tax_id": "...", "unit_price_ge": 3.56, "quantity": 12000}
      ],
      "gap_pct_vs_cheapest": 6.7,
      "my_total_spend_ge": 106874.0,
      "quality_flag": "comparable"
    }
  ],

  "price_benchmark_summary": {
    "products_with_dual_source": 14,
    "products_where_i_am_cheapest": 7,
    "products_where_i_am_most_expensive": 4,
    "estimated_annual_savings_if_switch_cheapest_ge": 13200.0
  },

  "leverage_score": {
    "score": 78,
    "label": "🟢 HIGH",
    "components": [
      {"factor": "portfolio_share", "weight": 30, "score": 28, "note": "17.2% of total procurement"},
      {"factor": "payment_leverage", "weight": 20, "score": 18, "note": "35% unpaid — cash timing play"},
      {"factor": "dual_sourcing", "weight": 20, "score": 14, "note": "7 overlapping SKUs"},
      {"factor": "tenure", "weight": 15, "score": 12, "note": "11 months active"},
      {"factor": "relationship_health", "weight": 15, "score": 6, "note": "last wb 5d ago, clean"}
    ]
  },

  "negotiation_plays": [
    {
      "rank": 1,
      "confidence": "🟢 high",
      "type": "cash_discount_for_payment_speed",
      "ask": "4% ფასდაკლება მომდევნო 3 თვის შესყიდვაზე",
      "give": "314K ₾ დავალიანება 15 დღეში დაფარდება",
      "rationale_ka": "მომწოდებელს cash flow problem 4% margin-ზე ძვირი უჯდება",
      "evidence_refs": ["payment_profile.current_debt_ge", "volume_snapshot.monthly_avg_ge"]
    },
    {
      "rank": 2,
      "confidence": "🟡 medium",
      "type": "volume_commitment_discount",
      "ask": "3% volume discount + Q3 ფასდაფიქსირება",
      "give": "250K ₾ blanket order commitment 3 თვეში",
      "rationale_ka": "predictable volume = მომწოდებლის planning benefit",
      "evidence_refs": ["volume_snapshot.monthly_avg_ge"]
    },
    {
      "rank": 3,
      "confidence": "🟠 use_only_if_stalled",
      "type": "dual_source_leverage",
      "ask": "ფასების გათანაბრება კონკურენტი მომწოდებელთან",
      "give": "volume-ის 60% აქ ვტოვებ",
      "rationale_ka": "7 SKU-ზე alt supplier-ის ფასი 4-11% უფრო დაბალია",
      "evidence_refs": ["price_benchmark_summary.products_with_dual_source"],
      "warning_ka": "ეს last-resort, relationship-ი სასიცოცხლოა"
    }
  ],

  "risks_and_caveats": [
    "Unit price calc = amount / quantity — შეფუთვის ერთეულის განსხვავების რისკი აქვს",
    "quantity < 5 ცალი პროდუქტებზე price gap არ მიეცემა (statistically შიშველი)"
  ],

  "matching_warnings": []
}
```

**მთავარი დიზაინ რჩევა:**
- `leverage_score` ცხადი კომპონენტების decomposition — AI-მ ცხადად დაინახოს რატომ (არა black box)
- `evidence_refs` — ყოველი ცოცხალი cifram-ი ცხადი data.json path-ით (AI-მ "ფაბრიკაცია" არ გააკეთოს)
- `negotiation_plays` — რეალური rank-ოლი ცხრილი, არა LLM generative
- Portfolio mode (`supplier_name=None`) — Pareto concentration view ("top 5 ფარავს 42%, რომელ 5 შეხვედრას გირჩევ?")

**2. `dashboard_pipeline/ai/tools.py`**

- `PREPARE_SUPPLIER_BRIEF_TOOL` schema
- `ToolDispatcher` route-ი
- TOOL_SCHEMAS length: **14 → 15**

### Prompt-ის მხარე (1 ფაილი)

**3. `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA`**

ახალი სექცია `📞 Supplier Negotiation Prep (CRITICAL — Phase 2.12)`:

განთავსება: `💀 Dead Stock Detection`-ის შემდეგ, `🔄 Self-Correction Loop`-ის წინ.

შინაარსი:
- **Trigger list** (როდის გამოიყენე `prepare_supplier_brief`):
  - "ხვალ X-თან მაქვს შეხვედრა"
  - "ფასდაკლება ვთხოვო" / "ვაჭრობის წინ"
  - "რა ვსთხოვო X-ს" / "negotiation strategy"
  - "ჩემი leverage რა არის"
  - "ვის გადავიდე" / "alternative supplier"
- **Anti-trigger** (როდის *არ* გამოიყენო):
  - "რამდენს ვალი მაქვს X-თან?" → `read_data_json(section='supplier_aging', filter=X)`
  - "X-ს რამდენი გადავუხადე?" → `read_data_json(section='suppliers', filter=X)`
  - "X-ის ბოლო ზედნადები" → `read_data_json(section='waybills', filter=X)`
- **Output format** — სავალდებულო ცხრილი + 3 plays + evidence citation + 🟢/🟡/🟠 confidence
- **Identity confidence** — თუ `match_confidence=low` ან `medium`, AI-მ **მოითხოვოს user-ის დადასტურება** ვიდრე brief-ს დაიწყებს ("ჩემი ვარაუდი: 'ჯიდიაი'-ს ქვეშ დავხედე 406181616 tax_id — ეს გჭირდება?")
- **Portfolio mode routing** — თუ user ზოგადია ("ვის უნდა ვესაუბრო"), AI-მ იცოდეს რომ `prepare_supplier_brief()` (ცალკე `supplier_name` / `tax_id`) portfolio-wide Pareto-ს აბრუნებს — ეს ცალკე UX-ია
- **Relationship caution** — ყოველი negotiation play-ს მოყვება `warning_ka` — AI არ უნდა "push" მისგან უფრო მკვეთრი, ვიდრე data ცოცხალია

### ტესტები (1 ახალი + 4 update)

**ახალი:** `tests/test_ai_supplier_brief.py` — დაახლოებით 40 ცდა:
- `TestSupplierResolution` (8) — tax_id / name / fuzzy / ambiguous / missing
- `TestVolumeSnapshot` (5) — totals, month count, ranking
- `TestPaymentProfile` (6) — scope labels, aging bucket, reliability logic
- `TestPriceBenchmark` (6) — dual-source detection, unit price calc, quantity threshold
- `TestLeverageScore` (5) — component weights, edge cases (new supplier, concentrated)
- `TestNegotiationPlays` (5) — rank logic, confidence tiers, evidence_refs integrity
- `TestPortfolioMode` (3) — Pareto concentration, no-focus mode
- `TestMatchingWarnings` (2) — emitted when quality_flag ambiguous

**Updates** (tool count 14 → 15):
- `test_ai_memory.py::test_tool_count_is_15`
- `test_ai_forecasting.py::test_tool_count_is_15`
- `test_ai_journal.py::test_tool_count_is_15`
- `test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed`
- `test_ai_agent.py::test_investigate_mode_preserves_tool_surface`
- `test_ai_dead_stock.py`-შიც tool surface-ის pin-ი ცოცხლად განახლდება

ჯამში pytest: **1033 → ~1073 green** (+40 new + 5-6 updates with same count).

---

## 🚫 NOT in scope (parking-lot)

- ❌ რეალური contract export (PDF/Word) — UI-layer feature (Phase 3.x)
- ❌ Email/message auto-compose — separate integration track
- ❌ Alt-supplier price crawl external (bazar.ge etc) — data-sovereignty scope
- ❌ Auto-trigger alerts ("X mounth supplier concentration spike") — Phase 4 proactive alerts
- ❌ Dashboard UI "Supplier Brief" page — Phase 3.6 (Supplier Concentration Widget)-ის გაფართოება
- ❌ Historical price trend chart (time-series) — data surface უკვე საკმარისი, მაგრამ v1-ში static snapshot

---

## ⚠️ რისკები + caveats

| რისკი | მიტიგაცია |
|---|---|
| **Unit mismatch** (ცალი vs კგ vs ცალი-ყუთში) | tool შეაფასებს `unit` string-ის normalize-ს; თუ differs — `quality_flag: unit_mismatch` და gap არ ითვლება |
| **Short-history supplier** (< 2 თვე) | leverage score ცხრ reliability-ზე penalty; ceremonial brief მხოლოდ აფრთხილებს user-ს რომ ცოცხალი data არაა |
| **Tax_id ambiguity** (სახელი ემთხვევა 2 კომპანიას) | `match_confidence: "medium"` → AI prompt-ი user-ს გადაუკითხავს ვიდრე brief-ს იტყვის |
| **Price gap false positive** (ერთი მომწოდებელი promo-ზე იყო) | `quality_flag: "temporal_mismatch"` თუ date range-ები სხვადასხვა კვარტალშია |
| **Relationship harm** (AI "push"-ს overdrives) | negotiation_plays ცოცხალი rank-ით (#3 `warning_ka: last-resort, relationship-ი სასიცოცხლოა`); prompt-ი AI-ს უკარნახებს "relationship > margin" საფუძვლიანობას |

---

## 🎬 ცოცხალი dog-food გეგმა (post-code)

Backend restart-ის შემდეგ ცოცხლად დავუსვამ AI-ს ორ კითხვას:

**1. Direct negotiation query:**
> "ხვალ 'ჯიდიაი'-სთან მაქვს შეხვედრა. რა ვთხოვო?"

ვამოწმებ:
- ✅ AI ცდის `prepare_supplier_brief(supplier_name="ჯიდიაი")`
- ✅ Resolution match_confidence = high (tax_id resolved)
- ✅ Volume snapshot ცოცხალი (897K ₾, 628 wb, 17.2% share)
- ✅ Payment profile ცხადი (debt 314K, clean scope)
- ✅ 3 negotiation plays + confidence labels + rationale + evidence_refs
- ✅ ⚠️ რისკის warning ჩართული
- ✅ Relationship discipline ("relationship > margin")

**2. Portfolio-scale query:**
> "ვის უნდა ვესაუბრო ფასდაკლებისთვის? ვის მომიმზადებ?"

ვამოწმებ:
- ✅ AI გარჩევს user-ის intent-ს (portfolio, არა single)
- ✅ `prepare_supplier_brief()` call-ი უცოცხალო supplier args-ით
- ✅ Pareto ცხრ Top 5 concentration + annual potential savings
- ✅ Rank by `leverage_score`, არა total spend
- ✅ AI რეკომენდაცია — "დაიწყე #1-ით, გელოდება ~13K ₾ savings"

---

## ✅ Acceptance criteria

- [ ] `dashboard_pipeline/ai/supplier_brief.py` მზადაა (Pareto + single-supplier modes)
- [ ] `tools.py` TOOL_SCHEMAS = 15, dispatcher route-ი მუშაობს
- [ ] `prompts.py::SYSTEM_PROMPT_KA` ახალი 📞 Supplier Negotiation სექცია, investigator prompt **untouched**
- [ ] `tests/test_ai_supplier_brief.py` ~40 cases green
- [ ] 5-6 existing test files updated for tool count 14 → 15
- [ ] pytest **~1073/1073 green** (was 1033; +40; 0 weakened)
- [ ] Backend restart + in-process marker probe
- [ ] ცოცხალი Anthropic dog-food: 2 კითხვა, ორივე pass

---

## 🔗 Carry-forward dependencies

- **Phase 2.11 — Dead Stock** ✅ COMPLETE (2026-04-20) — ამავე pattern-ის triangulation სკელეტი
- **Excel-Path Fix** ✅ COMPLETE — ქართული მომწოდებლის სახელების Excel read არ ფუჭდება
- **Phase 1 Part C — Multi-Store DNA** ✅ COMPLETE — store-level supplier breakdown Part C awareness-ი გამოიყენოს
- **Phase 1 Part D — Self-Correction Loop** ✅ COMPLETE — ambiguous match-ზე AI-მ retry ცოცხალი ცხრ user clarify-ით გამოიტანოს
- **Phase 0A Calculator Enforcement** ✅ COMPLETE — არც ერთი arithmetic AI გონებაში; ყველაფერი tool-ში calcul

---

## 🚦 Estimated dev time

- კოდი (`supplier_brief.py` + tools/prompts): **4-5 საათი**
- ტესტები (40 ახალი): **2 საათი**
- Backend restart + verification: **30 წუთი**
- ცოცხალი dog-food + journal + summary: **45 წუთი**
- **TOTAL: ~7-8 საათი** (1 dev day)

---

## 📋 user-ის გადასაწყვეტი

1. **დავიწყოთ კოდი ახლა?** (`კი`)
2. **მინდა ცვლილება scope-ში** (აღწერე — რა დაუმატო/მოვაკლო)
3. **საერთოდ სხვა მიდგომა გირჩევნია** (მაგ: ჯერ Phase 2.13 Cash Runway, მერე 2.12)

---

## 💡 გადახედე — რა ღირს ეს feature შენთვის?

**Concrete cifram-ით:**

| მომხმარებლის სცენარი | Phase 2.12-ის გარეშე | Phase 2.12-ით | დაზოგვა |
|---|---|---|---|
| "ჯიდიაი-სთან შეხვედრა" | 2-3 საათი Excel-ში ძიება | 30 წამში 1-pager | **~2.5 სთ + უფრო სრული leverage** |
| "ვის ფასდაკლება ვთხოვო" | გრძნობით/ინტუიციით | Top-5 ranked list + cifram-ი | **gut-feel → data-backed** |
| "Coca-Cola-ზე ფასდაკლება" | არც იცი რომ alt supplier 6.7% იაფად ცხრ | "დისტრიბუცია-ს ცხრ 13K/წლ. საქმე გქვია" | **~13K ₾/წლ savings opportunity ცხადია** |

**Bottom line:** Phase 2.11-მა dead stock-ი გამოავლინა (**გაყინული ფული**). Phase 2.12-ი იმავე ფულს ცოცხალ ნაკადში აბრუნებს — **მომწოდებლებთან უკეთესი პირობები**.
