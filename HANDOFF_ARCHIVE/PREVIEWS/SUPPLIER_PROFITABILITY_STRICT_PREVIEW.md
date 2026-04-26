# Supplier Profitability — STRICT MODE — PREVIEW

**Status**: `PREVIEW · NO CODE CHANGE`
**Date**: 2026-04-26
**Trigger**: User screenshots of SupplierModal (შპს ტკბილი ქვეყანა, შპს სუნელი) + request: „რამდენ ლარის პროდუქცია გაყიდა, % მოგება, რომელი იყიდება დაბალი %-ით"
**Foundational rules** (saved to memory 2026-04-26):
- `feedback_perfect_or_silent.md` — UI ციფრები ან 100% verified ან ცარიელი „ჯერ არ ვიცი" status
- `project_product_match_barcode_only.md` — JOIN მხოლოდ barcode/code-ით; name-fuzzy აკრძალულია (ბორჯომი მინისა ≠ პლასტმასი)

---

## TL;DR

User-მა მთხოვა: „SupplierModal-ში დაამატე ანალიზი — ამ მომწოდებლისგან რა ვიყიდე, რა გავყიდე, რა მარჟით, სად ვკარგავ". პირველი მცდელობა (name-fuzzy match) **მცდარი** იყო — user-მა ცხადად მითხრა „ბორჯომი მინისა ≠ პლასტმასი, თუნდაც სახელი ერთი ჰქონდეს". მეორე მცდელობა (barcode-strict) — **64% product / 75% cost-coverage** ცოცხალ data-ზე, top suppliers (კოკა-კოლა/ჯიდიაი/ზედაზენი) 100%.

User-მა შემდეგ მითხრა: **„სრულყოფილი ანალიზი მინდა, არ უნდა ტყუვდებოდეს".** ე.ი. 75%-ი UI-ში არ კმარა — partial confidence badge-ი ნდობას შლის.

ფიჩერი ამ ფესვი-დონის წესით ხელახლა იწერება: **strict mode**. ყოველი row Modal-ში — ან 100% verified barcode-match, ან ცარიელი ცელი ცხადი „ჯერ უცნობია" ნიშნით. Coverage % — ცალკე admin გვერდზე, არა მთავარ UI-ში.

შედეგი: **top-12 supplier-ზე (75% ყველა შესყიდვის) ფიჩერი ეშვება დღეს, 100% სანდო ანალიზით**. ცარიელ supplier-ებზე (ფუდმარტი 76K, ელიზი 559K) — ცხადი „გასარკვევი" status + ხელით vetted alias workflow კვირების განმავლობაში coverage გაზრდისთვის.

**Risk**: MED. არც mechanical refactor, არც pure UI — ფიჩერი strategic decision-ებს მხარდაჭერს („რომელი პროდუქცია არ ღირს ამ supplier-დან"). სიგარეტი/PROTECTED handling უნდა იყოს მოპირდაპირე-მოპირდაპირე — სხვაგვარად ჯიდიაი-სთვის (100% სიგარეტი, 7.5% margin) ფიჩერი შესთავაზებს „ამ supplier-დან ნაკლები შემოიტანე", რაც ცრუ რჩევაა.

---

## 1. ცოცხალი data — რა გვაქვს დღეს

### 1.1 imported_products vs retail_sales — ფესვი-დონის ფაქტი

```
imported_products (RS.ge ზედნადებები):  13,683 უნიკალური პროდუქცია, 5,310,478 ₾ cost
retail_sales.by_product (MAX POS):        8,579 უნიკალური პროდუქცია (gross_margin_pct მზადაა)
```

**barcode-strict JOIN coverage:**

| | რიცხვი | % |
|---|---:|---:|
| imported პროდუქცია (ჯამი) | 13,683 | 100% |
| ↳ EAN-13 ბარკოდით (სანდო) | 10,475 | 77% |
| ↳ შიდა MAX-კოდით | 3,190 | 23% |
| **match retail_sales-ში (barcode-strict)** | **8,816** | **64%** |
| ვერ მოვიძიე | 4,867 | 36% |

**ფინანსურად (cost-weighted):**

| | ₾ | % |
|---|---:|---:|
| ჯამური cost imported | 5,310,478 | 100% |
| **match-ით დაფარული** | **4,004,039** | **75.4%** |

### 1.2 Top-12 supplier — verified-only ანალიზი (real numbers)

```
supplier                                        ver/tot  cost(₾)     rev(₾)     profit    margin
─────────────────────────────────────────────  ────────  ─────────  ─────────  ────────  ──────
შპს ჯეო ფუდთაიმი                                936/1288   25,298  1,155,933  137,718    11.9%
შპს ჯიდიაი                                       95/103   905,489    864,287   64,556     7.5% 🔒
შპს კოკა-კოლა დისტრიბუცია                        72/75     45,365    509,212   75,162    14.8%
შპს კოკა-კოლა გურია                              84/84    402,641    428,331   59,683    13.9%
სს კოკა-კოლა ბოთლერს ჯორჯია                      60/61     18,047    409,332   56,540    13.8%
შპს ზედაზენი აჭარა                               60/60    160,548    152,129   10,473     6.9%
შპს შრომა - 2023                               1112/1381   94,696    139,518   34,532    24.8% ⭐
შპს ინტერნეიშნლ მარკეტინგ ენდ თრეიდინგ            9/10    181,420    128,330   11,022     8.6%
შპს პარტნიორი 2010                              117/124    59,592    113,265   16,034    14.2%
შპს იფქლი                                        33/37    135,556    112,284   15,524    13.8%
შპს ლაქტალის ჯორჯია                              79/135    47,344    111,658    2,948     2.6% ⚠️
სს იბერია რეფრეშმენტსი                          132/157   130,825    110,611   14,711    13.3%
```

**🔒 ჯიდიაი** — 100% სიგარეტი (Marlboro/Philip Morris/L&M); PROTECTED handling კრიტიკულია
**⭐ შრომა - 2023** — 24.8% margin, ყველაზე მომგებიანი
**⚠️ ლაქტალის ჯორჯია** — 2.6% margin, შესაძლო audit candidate (რა შემოვიდა, რა გაიყიდა, რატომ ასე დაბალი)

### 1.3 0% match suppliers — ცხადი „გასარკვევი" status

| supplier | cost | რატომ 0% |
|---|---:|---|
| **შპს ელიზი ჯგუფი** | 559,372 ₾ | სიგარეტის დისტრიბუტორი, RS.ge-ში MAX-ის შიდა 4-ციფრიანი კოდით (`[2165]`, `[2126]`); არც EAN, არც MAX-ში match. 🔒 PROTECTED ისედაც. |
| **შპს ფუდმარტი** | 76,614 ₾ | საცხობი/ფუდსერვის დისტრიბუტორი, RS.ge-ში საკუთარი შიდა SKU-ით (`[00-00049243]`, `[01-00008088]`). სახელი ემთხვევა MAX-ში — მაგრამ name-მიდგომა აკრძალულია (პერ წესი). საჭიროა ხელით vetted ალიასი. |

---

## 2. წესები (memory-დან გადმოცემული, აქ explicit)

### 2.1 Match logic — strict barcode/code

```python
# pseudocode — NO name fuzzy ever
def match(imp_product, rs_index_by_bc, rs_index_by_pcode, alias_table):
    code = imp_product["product_code"].strip()
    if not code:
        return None  # უცნობი

    # 1. ცდა ცხადი match-ი
    if code in rs_index_by_bc:
        return ("verified_barcode", rs_index_by_bc[code])
    if code in rs_index_by_pcode:
        return ("verified_pcode", rs_index_by_pcode[code])

    # 2. ცდა ხელით vetted ალიასი
    if code in alias_table:
        target = alias_table[code]["retail_code_or_barcode"]
        if target in rs_index_by_bc:
            return ("verified_alias", rs_index_by_bc[target])
        if target in rs_index_by_pcode:
            return ("verified_alias", rs_index_by_pcode[target])

    # 3. სხვა შემთხვევაში — None. NO fuzzy. NO name match. NEVER.
    return None
```

### 2.2 Modal display — perfect or silent

| supplier-ის coverage | Modal-ში რას ვაჩვენო |
|---|---|
| **100%** ფინანსურად | სრული ანალიზი: KPI ცხრილი, top-3 best margin, bottom-3 worst margin, dead-stock list |
| **80-99%** | სრული ანალიზი (verified rows-ისთვის) + footer: „📋 X პროდუქცია (Y ₾) ჯერ ვერ ანალიზდება — [იხ. data quality]" |
| **< 80%** ფინანსურად | KPI ცარიელი (`—`) + ცხადი ბანერი: „📋 ანალიზი ჯერ ვერ ხდება. [N] პროდუქცია ([X ₾]) ვერ მოიძებნა retail_sales-ში." + ღილაკი „[ალიასების კონსოლი →]" |
| **PROTECTED კატეგორია** (cigarettes, alcohol if added) | ცხადი badge: „🔒 PROTECTED — ცხელი ანალიზი არ მოქმედებს ამ კატეგორიაზე" + minimal info (cost, count of products) |

### 2.3 Coverage % — admin only, არა მთავარ UI-ში

ცარიელი ცელი UI-ში ცხადია — user-ი იცის „ეს ჯერ არ ვიცი". „75% სანდო" ბეჯი ქმნის ცრუ ნდობას მე-25%-ზე → **იკრძალება**.

Coverage analytics ცხალკე გვერდზე **„📊 მონაცემთა ხარისხი"** (admin/data-quality view) — როცა შენ გინდა ნახო რომელ supplier-ებზე უნდა ვიმუშაო ალიასებზე.

---

## 3. ფიჩერის სრული ფორმა

### 3.1 SupplierModal — ახალი სექცია (slot: line 374-376 შორის, pay form-ის წინ)

**Mock — შპს კოკა-კოლა გურია (100% verified):**
```
┌─────────────────────────────────────────────────────────┐
│ 📊 პროდუქციული მოგება                                   │
├─────────────────────────────────────────────────────────┤
│ შემოვიდა cost     გავიდა revenue    მოგება    მარჟა    │
│   402,641 ₾       428,331 ₾         59,683 ₾   13.9%   │
│                                                          │
│ ─── ⭐ ყველაზე მომგებიანი (top 3) ───                  │
│   კოკა-კოლა 1.5ლ ფეტი               18.5% (rev 89K)    │
│   სპრაიტ 1.5ლ ფეტი                  17.8% (rev 32K)    │
│   ფანტა ფორთოხალი 0.5ლ              16.2% (rev 14K)    │
│                                                          │
│ ─── ⚠️ დაბალი მარჟით იყიდება (bottom 3) ───            │
│   კოკა-კოლა 0.33ლ ქილა              4.2% (rev 8K)      │
│   ⤷ ფასდაკლება? ცარელი ფასი?                            │
│   კოკა ზერო 0.5ლ                    6.1% (rev 12K)     │
│   ფანტა მსხალი 0.5ლ                 7.8% (rev 5K)      │
│                                                          │
│ ─── 🐌 dead stock (ბოლო 120 დღე — 0 გაყიდვა) ───       │
│   ცარიელია — ყველაფერი იყიდება ✓                       │
└─────────────────────────────────────────────────────────┘
```

**Mock — შპს ჯიდიაი (100% PROTECTED):**
```
┌─────────────────────────────────────────────────────────┐
│ 📊 პროდუქციული მოგება                                   │
├─────────────────────────────────────────────────────────┤
│ 🔒 PROTECTED — სიგარეტის დისტრიბუტორი                  │
│ ცხელი ოპტიმიზაცია (margin shift, drop) არ მოქმედებს.   │
│                                                          │
│ ინფორმაციული:                                            │
│   95 პროდუქცია · 905,489 ₾ შემოვიდა                   │
│   864,287 ₾ გავიდა · 7.5% blended margin               │
│                                                          │
│ [📋 სრული სია →] (ცალკე გვერდი)                         │
└─────────────────────────────────────────────────────────┘
```

**Mock — შპს ფუდმარტი (0% — ცარიელი status):**
```
┌─────────────────────────────────────────────────────────┐
│ 📊 პროდუქციული მოგება                                   │
├─────────────────────────────────────────────────────────┤
│ 📋 ანალიზი ჯერ ვერ ხდება                                │
│                                                          │
│ ფუდმარტი იყენებს საკუთარ შიდა SKU-კოდს (`00-00049243`),│
│ რომელიც არც RS.ge ბარკოდია, არც MAX-ში არსებული კოდი.  │
│                                                          │
│ შესყიდვა: 33 პროდუქცია · 76,614 ₾                      │
│                                                          │
│ [🔧 ალიასების კონსოლი →] — დაამატე ხელით vetted        │
│                              barcode-mapping             │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Pipeline — ახალი მოდული `supplier_profitability.py`

**ფაილი**: `dashboard_pipeline/supplier_profitability.py` (ახალი, ~250 line)

**პასუხისმგებლობა:**
1. დატვირთოს `data.json:imported_products.suppliers` + `retail_sales.by_product` + `data/product_aliases.json`
2. აკეთოს strict barcode JOIN
3. გამოთვალოს per-supplier:
   - `cost_imported_ge` — ჯამური შესყიდვა
   - `revenue_sold_ge` — ჯამური გაყიდვა (მხოლოდ verified რიცხვებზე)
   - `profit_ge`, `margin_pct`
   - `verified_count`, `total_count`, `coverage_cost_pct`, `coverage_product_pct`
   - `top_margin[]` (top 3 best, revenue-filtered ≥ 100 ₾)
   - `bottom_margin[]` (bottom 3 worst, same filter)
   - `dead_stock[]` (imported but 0 retail rev OR last sale > 120 days)
   - `status`: `"verified"` / `"partial"` / `"unverified"` / `"protected"`
4. ჩაწეროს `data.json:imported_products.suppliers[].profitability` (per-supplier object)

**გამოძახება**: pipeline `run()`-ში, `build_supplier_concentration()` შემდეგ, `_write_outputs()` წინ.

### 3.3 alias workflow — `data/product_aliases.json`

**ფაილი**: ახალი, ცარიელი დასაწყისიდან.

**Schema:**
```json
{
  "version": 1,
  "aliases": [
    {
      "imported_code": "01-00008088",
      "imported_supplier_taxid": "405000000",
      "imported_name_sample": "ენერგეტიკული სასმელი/ S /450 მლ",
      "retail_code_or_barcode": "4860119260841",
      "confirmed_by": "user",
      "confirmed_at": "2026-04-26",
      "note": "ფუდმარტის შიდა SKU = MAX-ში EAN-13"
    }
  ]
}
```

**Validator** (`dashboard_pipeline/_validate_aliases.py`):
- ყოველი ალიასი უნდა იყოს `confirmed_by: "user"` (აგენტს არ შეიძლება ცარიელი match-ი დამატოს)
- `retail_code_or_barcode` უნდა არსებობდეს `retail_sales.by_product`-ში (განცალკევებული retail-side სიის მიხედვით)
- duplicate `imported_code` → error
- pipeline-ში warning + skip თუ ალიასი ცდუნებული (target ცარიელი)

### 3.4 Admin გვერდი — „📊 მონაცემთა ხარისხი"

**ფაილი**: `rs-dashboard/src/DataQualityPage.jsx` (ახალი) + tab DashboardTabs-ში

**ფუნქციონალური:**
- ცხრილი: supplier × coverage_cost_pct × verified_count / total_count
- sort: coverage ascending (worst first → ის სჭირდება ალიასი)
- ყოველი supplier-ის row-დან: drill-in „რა პროდუქცია არ მოიძიე" ცხრილი
- per unmatched product: AI-suggested alias candidate (ცარიელად დასაწყისიდან, AI tool ცალკე sprint-ზე) + „დადასტურება" ღილაკი
- დადასტურება → `product_aliases.json`-ში ახალი row → next pipeline regen-ი ფარავს

### 3.5 AI tool (optional, defer to follow-up sprint)

`analyze_supplier_profitability(tax_id: str)` — AI-ს შეუძლია ჰკითხოს „ფუდმარტიდან რომელი პროდუქცია არ ღირს?" → ცარიელი status returned + alias-action recommendation.

**Out of scope ამ sprint-ში**. ფოკუსი UI + pipeline. AI tool — Phase 2.X follow-up.

---

## 4. „თუ რამე გამომრჩა — დაამატე" — extra signals

User-მა მითხრა „რამე გამომრჩა — დაამატე". ჩემი proposal:

| signal | რას აჩვენებს | სად |
|---|---|---|
| 🐌 **dead stock per supplier** | imported, ბოლო 120+ დღე გაყიდვა 0 → არ შემოიყვანო მეტი | bottom section, ცალკე list |
| 🎯 **fast movers per supplier** | top-3 best-selling units → potential ფასდაკლების მოლაპარაკება მოცულობაზე | top-3 ჩამონათვალში inline tag |
| ⚖️ **portfolio profit-share** | ამ supplier-ის წილი ჩემი მთლიანი მოგებიდან (არა მხოლოდ ბრუნვიდან) | KPI ცხრილში, თვითონ portfolio-share-ის გვერდით |
| 📈 **margin trend** (3-month MoM) | ამ supplier-ის blended margin იზრდება/ეცემა → წითელი arrow ↓ თუ −2pp | KPI ცხრილში |

**Confirm თითოეულზე ცალკე** — არ ვაკეთებ ყველაფერს თუ შენ ცალკე არ ადასტურებ. დასაწყისში დავამატებ მხოლოდ **dead stock** + **fast movers**, დანარჩენი — შენი არჩევანი.

---

## 5. ფაილები რომელიც შეიცვლება

| ფაილი | ცვლილება | size |
|---|---|---|
| `dashboard_pipeline/supplier_profitability.py` | NEW — strict JOIN + per-supplier aggregate | ~250 line |
| `dashboard_pipeline/_validate_aliases.py` | NEW — alias schema validator | ~80 line |
| `dashboard_pipeline/generate_dashboard_data.py` | wire up в `run()` | +5 line |
| `data/product_aliases.json` | NEW (empty seed) | ~10 line |
| `rs-dashboard/src/SupplierModal.jsx` | new section after line 374 | +120 line |
| `rs-dashboard/src/SupplierModal.css` (or inline) | new section styles | +60 line |
| `rs-dashboard/src/DataQualityPage.jsx` | NEW — admin coverage page | ~200 line |
| `rs-dashboard/src/DashboardTabs.jsx` | new tab „📊 მონაცემთა ხარისხი" | +5 line |
| `tests/test_supplier_profitability.py` | NEW — strict match, alias, protected, edge cases | ~300 line |
| `tests/test_alias_validator.py` | NEW — schema, dedup, missing target | ~80 line |
| `CONTEXT_HANDOFF.md` | new sprint entry | +5 line |
| `PHASE_STATUS_MATRIX.md` | new row | +1 line |

**ჯამი**: ~1,100 line code + ~380 line test. ერთ session-ში ვერ მოთავსდება — **2 session** რეალისტურია (Sprint A: pipeline + tests + AGENTS.md edit; Sprint B: SupplierModal + DataQuality + dog-food).

---

## 6. რას ვერ ვაკეთებ ამ sprint-ში

- ❌ **AI tool** (`analyze_supplier_profitability`) — defer Phase 2.X
- ❌ **MEGA Plus integration** — შენი ხვალის ზარი MEGA support-ზე ცალკე არქია
- ❌ **upstream RS.ge enrichment** (barcode dataset purchase, RS.ge API) — strategic level, ცალკე
- ❌ **automatic alias suggestion** (AI scan unmatched → suggest top-N likely matches) — ცალკე sprint, საფუძველი ალიას-ფაილი ჯერ უნდა იყოს მუშა

---

## 7. რისკი და do-not-touch

### Risks
1. **PROTECTED detection bug** — თუ ჯიდიაი/ელიზი არ მონიშნავ PROTECTED-ად, ფიჩერი შესთავაზებს „shrink ჯიდიაი" → ცრუ რჩევა, user-ის ნდობა შლის. **Mitigation**: per-supplier PROTECTED detection = თუ ≥80% top_products ფარდა PROTECTED კატეგორიას (`mix_analyzer._canonicalize_protected` reuse), supplier მონიშნულია 🔒
2. **Alias file მცდარი mapping** — user-მა ვერ შეცდომით ჩაწეროს „X = Y" თუ Y სხვა პროდუქციაა → ციფრები გადასცდება. **Mitigation**: validator + admin-page-ში ცხადი preview „X (cost 100 ₾) → Y (rev 200 ₾, gm 15%)" დადასტურების წინ
3. **data.json ზრდა** — per-supplier `profitability` object შესაძლოა ~1-2 KB × 258 supplier = ~500 KB extra (132 MB → 132.5 MB) — acceptable
4. **pytest რეგრესიული** — დიდი ცვლილება data.json-ის სქემაში; existing prompt tests (432 grep assertions) რომელიმე შეიძლება გადაგონდეს. **Mitigation**: pre-flight grep run სქემა-ცვლილების სცენარისთვის

### Do-not-touch
- `mix_analyzer._canonicalize_protected` — reuse, NOT duplicate
- `imported_products.py` dedup logic (Sprint Suppliers UX/DI 9 `ae91710`) — **არ შეცვალო**, ფესვი-დონის ფიქსია
- `same-tax-id collapse` (`d7a45a7`) — **არ შეცვალო**, საფუძველი ფიქსია
- `Sprint 5.5 revenue formula` (`unit_price × quantity`) — **არ შეცვალო**, რეგრესიული ტესტი ცოცხალია

---

## 8. ღია კითხვები შენთვის (preview-ის შემდეგ პირდაპირ)

1. **PROTECTED-ის გაფართოება** — სიგარეტი ისედაც PROTECTED. **ალკოჰოლი** (ლუდი/ღვინო/არაყი) PROTECTED-ად ჩავთვალო? რეალური სიტუაცია: ზედაზენი (ლუდი/ალკ) — 6.9% margin. თუ არ მონიშნავ PROTECTED-ად, AI შესთავაზებს „shrink ზედაზენი".
2. **dead-stock წინდი ფანჯარა**: 120 დღე default-ად კარგია? (ეს არის უკვე `analyze_dead_stock`-ის default) ან 90/180?
3. **„margin trend" signal** — დავამატო ახლავე თუ მოგვიანებით? (extra ცოცხალი, MoM direction arrow)
4. **admin გვერდი — სად?** ცალკე tab DashboardTabs-ში ('🔧 მონაცემთა ხარისხი') თუ Settings/Profile იკონის ქვეშ?
5. **alias UI** — დადასტურების ფლოუ ბრაუზერშიდან (form + POST → ფაილში write) თუ მხოლოდ JSON ხელით ედიტი + pipeline regen?
6. **მცირე supplier-ები (<5 product)** — ანალიზი ღირს თუ minimal-display („3 product, 500 ₾")?

---

## 9. ქმედების გეგმა (sequence)

1. ✅ **Memory + AGENTS.md commit (now)** — სრულად ჩაიწერა + უკომიტო AGENTS.md-ის edit დაიკომიტება
2. ✅ **Preview commit (now)** — ეს ფაილი
3. ⏳ **Sprint A** (~1 session): `supplier_profitability.py` + alias validator + pipeline wiring + tests + data.json regen + verify ცხრილი ცოცხალ ციფრებზე
4. ⏳ **Sprint B** (~1 session): SupplierModal new section + DataQualityPage + DashboardTabs tab + visual polish + browser smoke
5. ⏳ **Optional Sprint C**: AI tool wrapper + dog-food (Sonnet 4.6 think=True, 3 scenarios)

**Risk-aware**: Sprint A-ის შემდეგ, სანამ Sprint B იწყება, **ცოცხალ data.json-ზე ვცადი** რომ top-12 supplier-ის ციფრები შეესაბამება ხელით კალკულაციას. თუ რომელიმე supplier-ის profit ან margin ხელით ვერ ვადასტურებ → STOP, blast radius გადავრცე.

---

## 10. რას არ მოდის ამ preview-სთან

- კონკრეტული CSS რეიტინგ + დიზაინი (Sprint B-ში, შენი Linear/Stripe-tier preference-ზე დაყრდნობით — მემორი `feedback_design_ambition.md`)
- კონკრეტული dog-food scenarios (Sprint C-ში)
- AI tool schema (Phase 2.X — defer)
- MEGA Plus / pos export (ცალკე)

---

## End of preview

User-ის გადაწყვეტა preview-ის შემდეგ — ერთი წერილი:
- ✅ approve → იწყება Sprint A
- 🟡 changes requested → revise (კითხვებზე პასუხი + scope ცვლა)
- ❌ defer → არქივი + წავიდე სხვა task-ზე
