# Sprint Preview — §8 Dead Stock (first-time analytics page)

**Status:** `PREVIEW · NO CODE CHANGE`
**Date:** 2026-05-10
**Target section:** Master Plan §8 — Dead Stock
**Predecessor closed:** §5 Retail Sales (Sprint 2 + period filter, 2026-05-10 დილა, 3 commits on origin/main)

---

## TL;DR

Megaplus DB ფლობს per-barcode per-store ნაშთის რეალურ snapshot-ს `PRODUCTS.P_QUANT` სვეტში — ცალკე "stock" ცხრილი არ გვჭირდება. Dead-stock სექცია აშენდება როგორც `PRODUCTS LEFT JOIN ORDERS` რომელიც პროდუქტს უწერს ბოლო გაყიდვის თარიღს და ბუჩქებში დაყოფს (>365d / 180-365d / 90-180d / never sold / negative qty). per-store ფილტრი მოყვება `per_object_view`-ის უკვე არსებულ პატერნს. ერთი sprint-ში ჩაეტევა — ერთი backend query, ერთი retail_sales sliding hook, ერთი front-end სექცია.

---

## Inventory

### წყაროები რომლებიც წავიკითხე

| ფაილი / DB ცხრილი | ხაზები გადახედული | რა მოვიპოვე |
|---|---|---|
| `dashboard_pipeline/megaplus_backup.py` | header + 200-300 + 1200-1301 | `_read_supplier_rollups()` ერთი DB-ის როლაპს აბრუნებს. Returns dict-ი ბოლოს ~30 key-ით (vat_*, shifts, discount_by_category, by_product, by_product_by_month, ...). Dead-stock query აქ უნდა დაემატოს როგორც სრულიად ახალი key. |
| `dashboard_pipeline/retail_sales.py` | 270-350 + 1140-1230 + 1820-1855 | `synthesize_from_megaplus(megaplus_live)` აერთიანებს ყველა მაღაზიის როლაპს `overall` + `by_object` + ~20 ცალკე ცხრილად. `per_object_view[store]` უკვე ფლობს per-store dataset-ს. Bundle-ის ბოლოს `dead_stock_*` key-ების დამატება სუფთად ჯდება. |
| `dashboard_pipeline/api_contracts.py` | 880-970 + 990-1060 | `_project_retail_sales_summary()` projection-ი ცხადად აპარკავს ყველა field-ს. ახალი key-ები აქ უნდა მოვიხსენიოთ ცხადად, თორემ `data.json` payload-ში არ გავა (verified earlier feedback memory: registry override needs explicit pipeline wiring). |
| `rs-dashboard/src/RetailSales.jsx` | structure scan only | სექციები აშენებულია `CollapsibleSection` + recharts + STORE_COLOR + InfoTip patterns-ით. `storeFilter` state უკვე exists. Period filter ($v3 commit `d1c566d`) ცოცხალია მაგრამ Dead Stock snapshot lifetime-ია (period filter ვერ გამოიყენება — ნაშთი "ახლა" snapshot-ია, ისტორიული by_month არ ვრცელდება). |
| MEGAPLUS_1301 / 1329 / LATEST DB | live SQL query | 53 ცხრილი per-DB. Dead-stock-ისთვის რელევანტურია: `PRODUCTS` (master), `ORDERS` (sales), `GET` (incoming), `CHAMOCERA` (write-off — 147 rows). |

### DB-დან verified ფაქტები

**`PRODUCTS` ცხრილის ნაშთის სვეტები:**
- `P_QUANT decimal` — მიმდინარე ნაშთის რაოდენობა (per-DB = per-store)
- `P_GETPRICE decimal` — ბოლო შესყიდვის ფასი
- `P_PRICE decimal` — გასაყიდი ფასი (free-stock ფილტრისთვის ⇒ `P_PRICE = 0`)
- `P_ACTIVE int` — `1` = აქტიური SKU
- `P_LIMIT decimal` — მინ. ნაშთის ლიმიტი (reorder threshold? — verify)
- `P_GROUP nvarchar` — კატეგორია
- `P_BARCODE varchar` — join key

**Per-store ნაშთის რაოდენობა (live snapshot):**

| DB | ✔ პოზიტიური ნაშთი | ❌ ნეგატიური ნაშთი | 0 ნაშთი | ნაშთის ღირებულება (P_QUANT × P_GETPRICE) |
|---|---|---|---|---|
| MEGAPLUS_1329 (დვაბზუ) | 3,431 SKU | 701 SKU (min `-34,295`) | 96,676 | ~128,563 ₾ |
| MEGAPLUS_1301 (ოზურგეთი) | 3,351 SKU | 1,025 SKU (min `-13,181`) | 96,448 | ~128,962 ₾ |
| MEGAPLUS_LATEST | 3,390 SKU | 715 SKU | 96,627 | ~131,744 ₾ |

**ORDERS join verified:** `ORDERS.ORD_P_ID = PRODUCTS.P_ID` work-ს — `ORD_TIMESTAMP` უკვე `datetime` ტიპია (არა epoch bigint), ისე რომ `MAX(ORD_TIMESTAMP) WHERE ORD_ACT = 1` უშუალოდ იძლევა last_sale_ts-ს Python-ში conversion-ის გარეშე.

**Spot-check შედეგი — რეალური dead-stock კანდიდატები (top 5 per store, sorted by stock_value DESC):**

ოზურგეთი (1301):
| barcode | name | qty | last_sale | stock_value |
|---|---|---|---|---|
| 4860001601776 | სიგარეტი/პირველი პრემიუმი ლურჯი | 1024 | 2025-07-11 (10 თვე) | 5,151 ₾ |
| 5449000185259 | კაპი ატამი 0.5ლ FR | 1596 | **never** | 3,425 ₾ |
| 1700 | აგარის შაქარი 50 კგ | 550 | 2024-07-23 (22 თვე) | 1,427 ₾ |
| 5900951027307 | სნიკერსი სუპერი 80გრ | 435 | 2024-05-28 (24 თვე) | 1,130 ₾ |
| 5449000146748 | კაპი ატამი პალპი 1ლ | 228 | **never** | 860 ₾ |

დვაბზუ (1329):
| barcode | name | qty | last_sale | stock_value |
|---|---|---|---|---|
| 8001090931191 | ფეირი ლიმონი 450მლ | 336 | 2025-04-02 (13 თვე) | 894 ₾ |
| 2226097 | უფასო პარკი ასაწონებში 400ც | 59 | **never** | 799 ₾ ⚠ free-stock |
| 5000159459228 | ბატონჩიკი ტვიქსი 58გრ | 486 | 2024-05-27 (24 თვე) | 759 ₾ |

⚠️ **Edge case found in spot-check:** "უფასო პარკი" (free shopping bag) — მაღაზია უფასოდ აძლევს მყიდველებს, ASUS-ი არასოდეს გაიყიდება ცხადია. `P_PRICE = 0` ფილტრი გადაარჩევს ამ თქვენს cases-ს ცალკე "operational/free-stock" სიად, dead-stock-ში არ შეერევა.

---

## Bucket definition (proposed)

| ბუჩქი | წესი | UI ფერი |
|---|---|---|
| 🔴 `dead_365d_plus` | qty > 0 AND (last_sale IS NULL OR last_sale < 365d ago) AND P_PRICE > 0 | red |
| 🟠 `dead_180_365d` | qty > 0 AND last_sale 180-365d ago AND P_PRICE > 0 | orange |
| 🟡 `slow_90_180d` | qty > 0 AND last_sale 90-180d ago AND P_PRICE > 0 | amber |
| 🟢 `active_<90d` | qty > 0 AND last_sale < 90d ago | green (not surfaced — context only) |
| 💸 `free_stock` | qty > 0 AND P_PRICE = 0 | grey (separate panel — not real dead stock) |
| ⚠ `negative_stock` | qty < 0 (data quality) | amber warning panel |

**`never_sold`** ცალკე ბუჩქი არ არის — `last_sale IS NULL` ხვდება `dead_365d_plus`-ში (ცხადად ცარიელი slot). UI-ში ცალკე `never_sold_count` ცვლადი per ბუჩქი — owner-მა იცოდეს რამდენი მათ არასოდეს გაყიდულა vs რამდენმა გაყიდული მაგრამ მიტოვებული.

---

## Scope recommendation

**Do this sprint:**
1. Backend SQL — ერთი ახალი query `_read_dead_stock(cur)` + ორი ახალი key როლაპში: `dead_stock_summary` + `dead_stock_items` (top 200 per store).
2. retail_sales.py — `synthesize_from_megaplus`-ში combined-view aggregation + `per_object_view[store].dead_stock_*` per-store breakdown.
3. api_contracts.py — `_project_retail_sales_summary()`-ში 2 ახალი projection block.
4. RetailSales.jsx — ერთი ახალი `CollapsibleSection` ("მკვდარი მარაგი / Dead Stock") 4 KPI ბარათით + 4-bucket bar chart + top-50 table per bucket. `storeFilter`-ს მიყვება.

**Defer to next sprint:**
- Inventory turnover ratio (cost_of_goods_sold ÷ avg_inventory) — საჭიროებს ისტორიულ inventory snapshot-ებს, რომლებიც ამჟამად არ ვინახავთ.
- Re-order recommendation per-product (P_LIMIT-ზე დაყრდნობით) — owner-ს ჯერ უნდა დავხატოთ რასაც გვიჩვენებს P_LIMIT.
- Cross-store transfer suggestion ("ეს SKU 1329-ში დასამარხია, 1301-ში გასაყიდი ჯერ კიდევ აქტიურია — გადაიტანე") — ცალკე feature, ცალკე UI.
- Dead-stock trend over time (snapshot history) — ვერც კი დავიწყებთ, თუ snapshot history არ ვინახავთ.

---

## Risks / pitfalls

| # | რისკი | მიტიგაცია |
|---|---|---|
| 1 | **MEGAPLUS_LATEST დუბლირებულია 1329-თან.** რომელ DB-ს ვუსმინოთ რეალური live snapshot-ისთვის? | `process_all_stores()` უკვე resolve-ს შესაბამისს — ვემხრობით მის გადაწყვეტილებას. cross-check spot-checks შემდგომ. |
| 2 | **P_QUANT ნეგატიურია 700-1000 SKU-ზე.** Naïve sum stock_value-ს დაცემს ცარიელ ნულამდე. | `WHERE P_QUANT > 0` filter dead-stock-ისთვის; ნეგატივი ცალკე "data quality" panel-ში surface-ს უკეთებს, არ ერევა totals-ში. |
| 3 | **Free-stock items (P_PRICE=0) რომლებიც განზრახ უფასოდ გაიცემა.** "უფასო პარკი" ჩაერევა dead-stock-ში მცდარი alarm-ით. | `WHERE P_PRICE > 0` ფილტრი dead-stock buckets-ში; free-stock ცალკე "ოპერაციული/უფასო მარაგი" panel-ში. |
| 4 | **never_sold rows** (last_sale IS NULL) — JOIN-ი მისცემს NULL-ს, წესის გარეშე ცარიელ ბუჩქში ჩავარდება. | LEFT JOIN explicit; bucket logic აშკარად მიჰყავს `last_sale IS NULL` → `dead_365d_plus` (most-conservative). UI ცალკე chip-ით "ვერასოდეს გაიყიდა". |
| 5 | **PRODUCTS.P_QUANT უმდევრი snapshot-ია — დღევანდელი ღამის backup-ის როდისიდან.** Owner-მა შეიძლება დარეკოს „რატომ ჩანს `qty=10` როცა საკავო ნაშთია 7?" | UI-ზე ცხადი წარწერა: "ნაშთი = ბოლო backup-ის (\<date\>) მდგომარეობით". `data_range.max_timestamp` უკვე გადმოდის retail_sales bundle-ში — გამოვიყენოთ `dead_stock_summary.snapshot_date`-ად. |
| 6 | **Combined view (ორი მაღაზიის ერთიანი)** — ერთი SKU ორ მაღაზიაშიც დევს. Stock_value SUM კორექტულია, last_sale უნდა იყოს max ორი მაღაზიის სასურსათოს. | per-store rollup-ში ცალცალკე ცხრილი + UI combined-mode-ში მოპოვებული `qty_total = qty_1329 + qty_1301`, `last_sale = max(...)`, store_breakdown chip ცხადი. |
| 7 | **Performance** — PRODUCTS 100k row × ORDERS 720k row LEFT JOIN per store. | `ORDERS.ORD_TIMESTAMP` already indexed; query plan უნდა შემოწმდეს `SET STATISTICS IO ON`. Top-200 per store + summary + buckets — გამოყავს ~5-10MB max სრულ data.json-ზე (≤7%). |
| 8 | **api_contracts projection silent drop** (Memory `feedback_pipeline_registry_override`) | new field-ები ცხადად დავამატოთ `_project_retail_sales_summary()` და `per_object_view` projection-ში; in-memory verify ვიდრე commit-ი. |

---

## Test plan

7 ცალი integration test, არსებული `tests/test_retail_sales_*` pattern-ით:

| # | test ფაილი / სახელი | რას ამოწმებს |
|---|---|---|
| 1 | `test_dead_stock_buckets_basic` | bundle-ში `dead_stock_summary` და `dead_stock_items` ფლობს მოსალოდნელ ფორმას; bucket count = 5 (incl. free + negative); rev counts > 0 (live data). |
| 2 | `test_dead_stock_join_correctness` | top-3 spot-check barcode-ები (პირველი პრემიუმი ლურჯი / აგარის შაქარი / ტვიქსი 58გრ) ცხადად ხვდებიან მათ მოსალოდნელ ბუჩქში. |
| 3 | `test_dead_stock_negative_isolation` | `WHERE qty > 0` filter — ნეგატიური qty არ ერევა stock_value totals-ში; ცალკე `negative_stock_alert` blob რეპორტავს min/max/count. |
| 4 | `test_dead_stock_free_stock_separation` | `P_PRICE = 0` SKU-ები ("უფასო პარკი") არ ჩანს dead_365d_plus-ში; ცალკე `free_stock_items` სიაში. |
| 5 | `test_dead_stock_per_store_split` | combined `dead_stock_items` SUM-ი = 1329 + 1301 per-store ჯამები (modulo qty_total reconciliation for shared SKUs). |
| 6 | `test_dead_stock_snapshot_date` | `dead_stock_summary.snapshot_date` = `data_range.max_timestamp` (latest backup). |
| 7 | `test_dead_stock_api_projection` | `data.json["retail_sales"]["dead_stock_summary"]` populated; per_object_view-ც გადადის (verified `urllib.request` to live `:8000`). |

**Reference test pattern:** `tests/test_retail_sales_revenue_formula.py` (already pinned in `AGENTS.md`).

---

## Files expected to change

| ფაილი | ცვლილების ტიპი | სავარაუდო ხაზები |
|---|---|---|
| `dashboard_pipeline/megaplus_backup.py` | add — new SQL block + return dict 2 new keys | +60 |
| `dashboard_pipeline/retail_sales.py` | add — combined aggregator + per_object_view block | +90 |
| `dashboard_pipeline/api_contracts.py` | add — 2 new projection blocks (combined + per_store) | +50 |
| `rs-dashboard/src/RetailSales.jsx` | add — new CollapsibleSection ("მკვდარი მარაგი") | +180 |
| `tests/test_retail_sales_dead_stock.py` | new file — 7 integration tests | +220 |
| `data.json` | regenerated by pipeline | ~+2-3 MB (top-200 SKU per store + summary buckets) |

**No-touch (verify integrity):**
- `dashboard_pipeline/category_anomalies.py` — orthogonal, არ გადაიკვეთება
- ბოლო Sprint 2 commit-ის shifts/vat/returns/discount blocks — უცვლელი
- period filter (commit `d1c566d`) — არ ვრცელდება dead-stock-ზე (snapshot-ია, არა flow)

---

## Self-check checklist (pre-commit)

- [ ] `dead_stock_summary` snapshot_date populated and matches latest backup
- [ ] free-stock items (P_PRICE=0) ცალკე surface; არ შეერევა dead bucket-ებში
- [ ] negative_stock_alert ცალკე panel; არ ერევა stock_value SUM-ში
- [ ] api_contracts.py projection ცხადად აპარკავს 2 ახალი key-ს (`dead_stock_summary`, `dead_stock_items`); in-memory test გვიჩვენებს რომ `/api/data?tab=retail_sales` დასახელებულ key-ებს აბრუნებს
- [ ] `per_object_view[store].dead_stock_*` populated for both stores
- [ ] storeFilter combined ↔ per-store toggle UI-ში live ცვლის dead-stock data-ს
- [ ] 7 integration tests passing
- [ ] proof-gate 3-layer checklist:
   - source: live SQL query reproduces same numbers per spot-check barcode
   - derived: bucket assignment logic single-source-of-truth in retail_sales.py
   - unverified: explicit "ეს ციფრი ჯერ არ შემოწმდა" ცარიელი slot-ისთვის

---

## Evidence sources

- `dashboard_pipeline/retail_sales.py:278` — `synthesize_from_megaplus(megaplus_live)` entry-point
- `dashboard_pipeline/retail_sales.py:1150` — `per_object_view` per-store dataset block
- `dashboard_pipeline/retail_sales.py:1820` — bundle return assembly (where new `dead_stock_*` keys land)
- `dashboard_pipeline/megaplus_backup.py:1258` — `_read_supplier_rollups()` return dict (where new SQL block joins)
- `dashboard_pipeline/api_contracts.py:881` — `_project_retail_sales_summary()` (where projections must explicitly mention dead-stock keys per `feedback_pipeline_registry_override.md`)
- `MEMORY.md → feedback_no_silent_data_drops.md` — negative-qty / free-stock / never-sold edges must be surfaced loudly, not silenced
- `MEMORY.md → feedback_proactive_verification.md` — spot-check live SQL before claiming any number "PROOFED"
- Live DB queries (this session): MEGAPLUS_1301 / 1329 / LATEST stock counts, top-stock spot-checks for dvabzu + ozurgeti — all reproducible via `pyodbc` + queries embedded above

**Last ancestor commit on `main`:** `d1c566d` (period filter v3, 2026-05-10 დილა).
