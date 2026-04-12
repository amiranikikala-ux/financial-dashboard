# მიმდინარე PLAN — Manager / Router რეჟიმი

## მიზანი

- ეს არის ერთადერთი აქტიური plan.
- ახალი სესია იწყება `PLAN.md` -> `AGENTS.md`.
- ძველი archive/handoff სექციები აქ არ გროვდება.
- მთავარი პრინციპი: correctness > coverage > convenience.

## ოპერაციული მოდელი

### როლები

- `Router` — მომხმარებელი; აკოპირებს prompt-ს შესაბამის worker-თან და აბრუნებს შედეგს.
- `Manager` — Lead Architect; აანალიზებს კოდს, არჩევს worker-ს და წერს მხოლოდ ერთ prompt-ს ერთ ჯერზე.
- `Codex` — backend/data worker; მუშაობს Python/API/data contract-ზე.
- `Gemini` — frontend/UI worker; მუშაობს React/CSS/UI-ზე.

### workflow

1. `Router` აძლევს ამოცანას `Manager`-ს.
2. `Manager` აბრუნებს მხოლოდ ერთ prompt-ს, მხოლოდ ერთ worker-ზე, fenced code block-ში.
3. `Manager` ჩერდება და ელოდება worker-ის შედეგს.
4. `Router` უშვებს prompt-ს შესაბამის worker მოდელში.
5. worker აბრუნებს მხოლოდ raw code-ს ან ზუსტად მოთხოვნილ patch-ს.
6. `Router` worker-ის შედეგს აბრუნებს ისევ `Manager`-თან.
7. მხოლოდ ამის შემდეგ მზადდება შემდეგი prompt.

### მკაცრი წესები

- ერთდროულად ორი worker არა.
- scope drift არა.
- fake certainty არა.
- silent error არა.
- `Manager` დიდი კოდური პაკეტის თვითონ წერაზე არ გადადის, თუ workflow prompt-routing რეჟიმშია.

## პროექტის მოკლე რუკა

### ბიზნესი

- ერთი კომპანია; ობიექტები: `ოზურგეთი`, `დვაბზუ`.

### წყაროები

- `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx`
- `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx`
- `Financial_Analysis/რს ზედნადები/*.xlsx`
- `Financial_Analysis/რს ზედნადები/*.xls`
- `Financial_Analysis/შემოტანილი პროდუქცია/*.csv` preferred; fallback `*.xls` / `*.xlsx`

### ტექნიკური flow

- `generate_dashboard_data.py` -> `data.json` + export-ები
- `server.py` -> tab-based API slices
- `rs-dashboard/` -> React + Vite frontend

## Truth boundary

- `imported_products` არის მხოლოდ `reference-only`.
- `imported_products` არ ერთვება:
  - supplier debt
  - AP logic
  - RS truth totals
  - bank reconciliation
- reconciliation წესები:
  - `ambiguous = 0`
  - `0 silent error`
  - `0 fake certainty`
- `supplier_matching_registry.json` ივსება მხოლოდ explicit evidence-ით.

## Reconciliation baseline

- `matched_high = 7009` / `4,525,012.97 ₾`
- `ambiguous = 0` / `0.00 ₾`
- `unmatched = 949` / `291,646.79 ₾`
- `non_supplier = 3513` / `570,121.10 ₾`

## მიმდინარე სტატუსი — 2026-04-12

- ბოლო დადასტურებული checks:
  - `python -m py_compile generate_dashboard_data.py server.py backend_paths.py dashboard_pipeline/api_contracts.py dashboard_pipeline/config_validation.py dashboard_pipeline/sources.py`
  - `python generate_dashboard_data.py`
  - `npm run lint`
  - `npm run build`
- `Packet E` (API Usage Optimization & Dashboard Polling Tuning) დასრულებულია:
  - `App.jsx`-ში დაემატა 600ms debounce `waybills` ძებნისთვის.
  - `api.js`-ში დაემატა Request Deduplication.
  - `App.jsx`-ში დაემატა Intelligent Polling (5 წუთიანი ინტერვალით, მხოლოდ ხილულ ტაბზე).
  - `api.js`-ში დაემატა API Usage Metrics (`window.__apiMetrics`).
- `Packet C` (launcher/runtime cleanup) დასრულებულია:
  - ყველა `.bat` ფაილში (`Run_Dashboard.bat`, `Run_Dashboard_Quick.bat`, `Run_Dashboard_With_Check.bat`, `Run_Dashboard_With_API.bat`) დაემატა `taskkill` ბრძანებები ძველი "Dashboard API" და "Dashboard Server" ფანჯრების დასახურად.
  - PowerShell-ის პორტების გამათავისუფლებელ სკრიპტებში `Stop-Process` შეიცვალა უფრო აგრესიული `taskkill.exe /F /PID`-ით, რათა თავიდან ავიცილოთ stale backend listeners.
- `Packet B` (reconciliation evidence review) დასრულებულია:
  - `generate_dashboard_data.py`-ში `NON_SUPPLIER_CATEGORY_IDS` სია განახლდა, რათა სრულად ასახავდეს `tbc_expense_categories.json`-ში არსებულ კატეგორიებს.
  - `tbc_expense_categories.json`-ში დაემატა explicit evidence (IBAN-ები) მსხვილი unmatched ტრანზაქციებისთვის (ამირან კიკალიშვილი, შპს მეგა პლიუს, მესხი ფიქრია, შპს სთრით ფუდ 125).
  - ახალი reconciliation totals:
    - `matched_high = 7036` / `4,516,386.97 ₾`
    - `ambiguous = 0` / `0.00 ₾`
    - `unmatched = 238` / `13,109.98 ₾` (ჩამოვიდა 252,365.68 ₾-დან)
    - `non_supplier = 4197` / `857,283.91 ₾`
- `Packet E` (Secondary Backlog) დასრულებულია:
  - `Valuation.jsx`-ში `AP Days` unit rendering გასწორდა (ემატება  `დღე`).
  - `Executive.jsx`-ში timeline key collision risk მოგვარდა (composite keys).
- `Packet D` (retail sales source onboarding) დასრულებულია:
  - backend/data pass და frontend/UI pass ორივე დახურულია.
  - `retail_sales` ტაბი დაემატა tabConfig/App-ში.
  - ახალი `RetailSales.jsx` summary view ჩაირთო.
  - `index.css`-ში retail-sales styles დაემატა.
  - duplicate policy შენარჩუნებულია (`ოზურგეთი/2026-01-02.xlsx` excluded).
  - truth boundary შენარჩუნებულია (`retail_sales` არ ერთვება supplier/AP/bank truth-ში).
- imported-products code state:
  - სრული bundle ისევ იგება `generate_dashboard_data.py`-ში
  - `Packet A` backend pass დახურულია: `imported_products_product_detail` უკვე დგას მიმდინარე backend-ში; ამ run-ში დამატებითი backend edit აღარ გახდა საჭირო
  - default `tab=imported_products` summary projection-ით ბრუნდება და მძიმე product-detail payload-ს აღარ აყოლებს
  - targeted tabs დგას:
    - `imported_products_full`
    - `imported_products_supplier_detail`
    - `imported_products_product_detail`
  - frontend fallback დგას ძველი backend-ისთვის
- imported-products metrics:
  - `source_format = csv`
  - `truncation_suspected_any = false`
  - `row_count = 176535`
  - `distinct_supplier_count = 267`
  - `distinct_product_count = 13344`
  - `date_range = 2022-05-18 .. 2026-02-28`
  - `products = 250`
  - `top_supplier_product_pairs_total_count = 13683`
- payload measurements:
  - full response დაახლოებით `887,332 bytes`
  - default summary response დაახლოებით `135,541 bytes`
  - summary bundle დაახლოებით `132,748 bytes`
  - supplier detail response დაახლოებით `5,819 bytes`
- runtime caveat:
  - თუ live backend ძველი პროცესით მუშაობს, ახალ detail tab-ზე UI შეიძლება `HTTP 400` აჩვენებდეს
  - ასეთ დროს საჭიროა backend restart
- frontend/runtime notes:
  - `SupplierModal` title cleanup fix უკვე დგას და runtime-ით დადასტურდა: `(406181616-დღგ) შპს  ჯიდიაი` -> title `შპს ჯიდიაი`, `ID: 406181616`
  - trust/split UI baseline verified-ად ითვლება; თავიდან browser verification საჭიროა მხოლოდ change/regression/anomaly/user-request-ზე
  - duplicate-key warning clean-room runtime recheck დასრულდა: `#working_capital` + `#ratios` fresh target-ზე warning no-reproduce დადასტურდა; `Packet C` დახურულია როგორც stale evidence case
- reconciliation/runtime notes:
  - `Packet B`-ში დახურულია რამდენიმე high-impact case strict evidence-ით: `ACCOUNT:101001000`, known landlord IBAN-ები (`GE81...`, `GE60...`), `415117929 / შპს ოლდენ ვესთ`, `GE90TB7436136060100004 / შპს ქართული სადისტრიბუციო-მარკეტინგული კომპანია`, `GE81TB7125136060100002 / შპს ლიდერი-ფუდი`, `GE35BG0000000499465014 / შპს ელიტ ფუდი 2`
  - მიმდინარე reconciliation snapshot:
    - `matched_high = 7030` / `4,512,486.97 ₾`
    - `ambiguous = 0` / `0.00 ₾`
    - `unmatched = 662` / `252,365.68 ₾`
    - `non_supplier = 3779` / `621,928.21 ₾`
- sales-source notes:
  - აღმოჩენილია ორი ახალი retail sales source:
    - `Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/*.xlsx`
    - `Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/*.xlsx`
  - line-level sales schema დადასტურდა: `P_ID`, `კოდი`, `შტრიხკოდი`, `დასახელება`, `ერთეული`, `რაოდენობა`, `ფასი`, `თვითღირებულება`, `დრო`, `ობიექტი`, `მოგება`, `ქვეჯგუფი`, `ცვლა`
  - `openpyxl` `read_only`/dimension ამ წყაროზე არასანდოა; parsing-სთვის გამოიყენე `pandas.read_excel()`
  - anomaly: `გაყიდული პროდუქტები სოფ ოზურგეთი/2026-01-02.xlsx` data-level-ით ზუსტად ტოლია `2025.xlsx`-ის; duplicate-suspected fileა, სანამ explicit policy არ დადგება
  - dedup-safe sales view (თუ `ოზურგეთი/2026-01-02.xlsx` დროებით არ ითვლება ცალკე პერიოდად):
    - `net_revenue_ge = 4,336,425.65`
    - `net_cost_ge = 3,687,489.14`
    - `net_profit_ge = 648,931.64`
    - `gross_margin_pct = 14.97`

## აქტიური coding packet

### მიმდინარე ამოცანები დასრულებულია

ყველა აქტიური Packet და Secondary backlog დასრულებულია.
ველით ახალ დავალებას მომხმარებლისგან.

## Worker scopes

### Manager

- ერთ worker-ზე ერთი prompt
- პასუხობს analysis + routing-ით
- არ უშვებს ორ parallel prompt-ს

### Codex

- backend/data only
- აბრუნებს:
  - exact contract change
  - validation result
  - payload before/after
  - runtime note
  - remaining caveat

### Gemini

- frontend/UI only
- უნდა ჩაირთოს მხოლოდ თუ Codex-ის შედეგი რეალურად მოითხოვს frontend ცვლილებას
- აბრუნებს:
  - changed UI
  - backend keys used
  - lint/build result
  - UX caveat

## Secondary backlog

- (ცარიელია)

## შემდეგი ზუსტი ნაბიჯი

1. ახალი ჩათი დაიწყოს `PLAN.md` -> `AGENTS.md`.
2. ყველა აქტიური ამოცანა და Secondary backlog დასრულებულია. მომხმარებელმა უნდა განსაზღვროს ახალი Packet.

## სესიის დახურვის წესი

- სესიის ბოლოს შეიძლება დაემატოს მხოლოდ ერთი მოკლე `Handoff` ბლოკი.
- ამ ფაილში ძველი handoff-ები და არქივი არ უნდა დაგროვდეს.
- `Handoff` უნდა შეიცავდეს მხოლოდ:
  - რა შეიცვალა
  - რომელი ფაილები შეიცვალა
  - რომელი checks გავიდა
  - რომელი prompt გაიცა
  - შემდეგი ზუსტი ნაბიჯი

## Handoff

- რა შეიცვალა:
  - `Packet E` (API Usage Optimization & Dashboard Polling Tuning) სრულად დასრულდა.
  - `App.jsx`-ში დაემატა **Intelligent Polling** მექანიზმი: 5-წუთიანი ინტერვალით მონაცემები ავტომატურად ახლდება, მაგრამ მხოლოდ მაშინ, როცა დოკუმენტი ხილულია (`document.visibilityState === 'visible'`).
  - `App.jsx`-ში დაემატა `visibilitychange` ივენთი, რომელიც მაშინვე აახლებს მონაცემებს, თუ მომხმარებელი დაბრუნდა ტაბზე და ბოლო განახლებიდან 5 წუთზე მეტია გასული.
  - `api.js`-ში დაემატა **API Usage Metrics** ტრეკერი: `window.__apiMetrics` აგროვებს სტატისტიკას თითოეულ ენდპოინტზე (წარმატებული და ჩავარდნილი მოთხოვნების რაოდენობა).
- რომელი ფაილები შეიცვალა:
  - `rs-dashboard/src/App.jsx`
  - `rs-dashboard/src/lib/api.js`
  - `PLAN.md`
- რომელი checks გავიდა:
  - `npm run lint` (`rs-dashboard`) -> pass
  - `npm run build` (`rs-dashboard`) -> pass
- რომელი prompt გაიცა:
  - `Gemini` (Subagent): `Packet E` (E2) Intelligent polling triggers & API usage metrics.
- შემდეგი ზუსტი ნაბიჯი:
  - ახალი ჩათი დაიწყოს `PLAN.md` -> `AGENTS.md`.
  - ყველა მიმდინარე Packet და Secondary backlog დასრულებულია. მომხმარებელმა უნდა განსაზღვროს ახალი მიზანი/ამოცანა.

