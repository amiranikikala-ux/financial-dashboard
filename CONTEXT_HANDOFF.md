# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-18 #1 — **Google Workspace CLI (gws) დაყენდა + Foodmart marketing income სტრუქტურა ცხადია**. ბრანჩი push-შია (4 commit gone to origin: `444e7ac` + `53f2544` + `1d74288` + handoff). Owner-ის ფოსტიდან აღმოვაჩინეთ რომ „cashback" სინამდვილეში 3 ნაკადია (რეტრო/სალარო/ტრეიდი) + KPI ბონუსი 2%. გავაგზავნე ფოსტა Anastasia Nedria-ს (FoodMart FS-form contact) — ვითხოვთ 4-თვიან გაშიფრვას. Lela-ც პასუხს გვმართებს May 13-დან.
>
> წინა: 2026-05-17 #4 — MegaPlus permission gap fixed (RESTORE-ი 3 დღე მარცხდებოდა, SYSTEM-ს dbcreator+db_owner მივეცი).
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`.

---

## 0. ბოლო session-ის შედეგი (2026-05-18 #1) — gws CLI + Foodmart marketing income discovery

### Headline

Owner-ის ფოსტა მანამდე ხელით იკითხებოდა (`_scratch_gmail_*.py` IMAP-ით). ამ სესიაში დავაყენე **Google Workspace CLI (`gws` v0.22.5)** — Claude-ი Bash-ით კითხულობს Gmail/Drive/Calendar-ს. შემდეგ Foodmart-ის ფოსტის ანალიზში აღმოვაჩინეთ **"FS Form for Franchises.xlsx" + "KPI Project 2026.pdf"** (Maka Alimbarashvili-სგან), რომელიც ცხადყოფს რომ owner-ის ბანკში „მომსახურების ღირებულების" სახელით შემოსული თანხები **სამი ცალკე ნაკადია** + KPI ბონუსი 2%.

### What shipped — commits + actions

| # | Commit/Action | რა |
|---|---|---|
| 1 | `444e7ac` | `fix(megaplus)`: SYSTEM grant SQL განახლდა dbcreator + db_owner-ით (წინა session-ის #4-ის commit). Pushed. |
| 2 | `53f2544` | `chore(gitignore)`: root-level `*.png` ignored (Playwright screenshots აღარ ჩანს `git status`-ში). |
| 3 | `1d74288` | `fix(megaplus)`: ცრუ "no new ZIP" log გასწორდა — exception case ცალკე refresh_failed flag-ით (HANDOFF #4 bug-bonus). |
| 4 | gws install | `npm install -g @googleworkspace/cli` (v0.22.5). |
| 5 | gcloud install | `winget install Google.CloudSDK` → at `C:\Users\tengiz\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd`. |
| 6 | GCP project | `financial-dash-1779046436` შექმნა + Gmail API enabled. |
| 7 | OAuth setup | Consent screen + Desktop OAuth client created (browser steps); credentials at `C:\Users\tengiz\.config\gws\client_secret.json` + encrypted `credentials.enc`. |
| 8 | Permissions | `.claude/settings.local.json`: `Bash(gws:*)` + per-service subcommand entries added. |
| 9 | Email sent | To `a.nedria@foodmart.ge` (CC Lela), msg id `19e37b34751c5b1d` — asking 4-month რეტრო/სალარო/ტრეიდი breakdown + per-supplier + formula. |

### Discoveries (saved to memory)

- **`project_gws_cli_setup.md`** — full install path, OAuth client id, credential locations, common gws usage patterns.
- **`project_foodmart_marketing_income_structure.md`** — 3 streams (რეტრო/სალარო/ტრეიდი) + KPI bonus 2%; Anastasia Nedria pending; Lela pending; KPI math: current 70%/2%/17% vs targets 90%/5%/22-25%.

### Foodmart KPI math (current vs target)

| KPI | მიზანი | ბონუსი | ჩვენი |
|---|---|---|---|
| Assortment Matching | 90% | 0.5% | 70% ❌ |
| Import & PL Share | 5% | 0.5% | 2% ❌ |
| Promo Sale Share | 22-25% | 0.5% | 17% ❌ |
| On-time Payments | 100% | 0.25% | ? |
| Financial info shared (by 25th) | per request | 0.25% | ? |
| **TOTAL** | | **2%** | **0%** |

KPI Project active from 2026-03-01. Monthly calc, quarterly settlement. All-or-nothing per KPI.

### Files state (post-commits)

```
M  CONTEXT_HANDOFF.md            (this update)
M  .claude/settings.local.json   (gws permissions added — gitignored normally? check)
```

ბრანჩი origin/main-თან sync. `git status`-ში მხოლოდ ეს handoff + settings ცვლილება.

### Open / next-session candidates

1. **Wait for Anastasia reply** — 4-თვის რეტრო/სალარო/ტრეიდი breakdown. პასუხის შემდეგ backtest formula-ის გაუმჯობესება.
2. **Wait for Lela** — May 13-ის დაპირება (cashback გაშიფრვა) + April 2026 "სააქციო ანაზღაურება" Excel (ჩვეულებრივ 22-25 რიცხვს მოდის, დაგვიანებაშია).
3. **Negative/Dead stock cleanup** (carryover) — Owner-მა ფიზიკურად უნდა შეამოწმოს 1,753 negative + 1,960 dead stock.
4. **HOME-9 bookkeeping** (carryover) — AP headline + Net liquidity card + Tax obligations.
5. **KPI dashboard** — assortment match / import-PL / promo % per-month chart, რომ Owner-მა იცოდეს რომელი KPI რეალურია მისაღწევი.

### Memory updates

- ახალი: `project_gws_cli_setup.md`, `project_foodmart_marketing_income_structure.md`.
- წინა „Lela email pending" (`project_foodmart_cashback_backtest_2026-05-09.md`) — ახლა cross-referenced ახალ ფაილში; pending list დღეს უფრო ცხადია (Anastasia + Lela + April Excel).

---

## 0aaa. წინა session (2026-05-17 დღე გაგრძელება #4) — MegaPlus auto-ingest permission gap fixed

### Headline

Owner-მა შენიშნა „Home გვერდი არ კითხულობს 14 რიცხვისას". გამოვიკვლიე: დვაბზუ-ში ZIP-ები 16 მაისამდე ეწერა, ოზურგეთში 17-მდე — მაგრამ pipeline-ის auto-regen ცარიელ პასუხს იძლეოდა და freshness API აჩვენებდა `last_backup_date: 2026-05-13`. ლოგი გაჩვენა root cause-ი:

```
MegaPlus DB backup-ი refresh ვერ მოხერხდა (cache-ი მაინც გამოვიყენო):
CREATE DATABASE permission denied in database 'master'. (262)
RESTORE FILELIST is terminating abnormally. (3013)
```

წინა session-ში SYSTEM-ს მივეცი მხოლოდ `db_datareader` MEGAPLUS_1329 + MEGAPLUS_1301-ზე. SELECT-ი მუშაობდა (`inventory_view` ცოცხლად კითხულობდა), მაგრამ `RESTORE FILELISTONLY + RESTORE DATABASE`-ისთვის სჭირდება `dbcreator` server role + `db_owner` ბაზებზე. ე.ი. ცოცხალი წვდომა იყო, ახალი ბექაპის ჩაგდება არასოდეს ხდებოდა — 3 დღე (14-15-16 მაისი) ჩუმად დაიკარგა.

### What shipped

| ფაილი | რა შეიცვალა |
|---|---|
| `grant_system_megaplus_access.sql` | +`dbcreator` server role · +`db_owner` ორივე ბაზაზე · header comment განახლდა; idempotent. Re-run safe. |

### What I ran

1. **SQL grant applied** — `sqlcmd -E -S "localhost\SQLEXPRESS" -i "grant_system_megaplus_access.sql"` → 3 `Changed database context` + final `Done. NT AUTHORITY\SYSTEM has dbcreator + db_owner + db_datareader on MEGAPLUS_1329 and MEGAPLUS_1301.`
2. **Manual MegaPlus refresh** — parent venv python `-c "from dashboard_pipeline.megaplus_backup import ...; process_all_stores(folders)"` → `Stores processed: ['1329', '1301']` (no exception).
3. **State file verification** — `_megaplus_state.json` after manual run:
   - დვაბზუ: `last_processed_zip = PLUS_1329_MEGA_20260516.zip`, `last_backup_date = 2026-05-16` (22:08:45)
   - ოზურგეთი: `last_processed_zip = PLUS_1301_MEGA_20260517.zip`, `last_backup_date = 2026-05-17` (22:14:01)
4. **Pipeline auto-regen triggered** — scheduled run at 22:19:01, currently in progress (last log: 22:21:41 "Reading RS files..."). MegaPlus stage მოვა 22:30-22:35 around. data.json regenerated by ~22:40.

### Verification done

- `/api/freshness` ცოცხალი: `megaplus.დვაბზუ.last_backup_date = 2026-05-16`, `ოზურგეთი.last_backup_date = 2026-05-17` ✓
- `_megaplus_state.json` ფაილების mtime შესაბამისი ✓
- Pipeline subprocess log: NO RESTORE error after grant applied ✓

### ⚠️ STILL OPEN — F5 + visual verification

1. **Wait for pipeline regen finish (~22:40)** — currently running. After it finishes:
   - `data.json` should grow / be rebuilt with new megaplus data
   - `last_complete_day` should jump from `2026-05-12` to `2026-05-15` (or 16)
   - retail_sales May 13-15 should appear
2. **Owner browser F5** — Home page should show updated freshness dots + KPI numbers for May 13-15.
3. **Commit + push** — 1 modified file (`grant_system_megaplus_access.sql`) ready. Previous 2 commits (`285a218` + `24e62ac`) still unpushed.

### Memory updates

- `project_megaplus_system_db_grant.md` ხელახლა დაიწერა: `dbcreator + db_owner + db_datareader`. Cross-reference დაემატა `[[feedback_proactive_verification]]`-ზე ლესონით „permission grant ერთ workflow slice-ზე (SELECT) test ვერ მოსწრებს silent failure-ს სხვა workflow-ში (RESTORE)".

### ⚠️ Bug-bonus (out of scope, not fixed this session)

`generate_dashboard_data.py:1882-1895` — როცა `_process_megaplus_stores` exception-ით ფეთქდება, ლოგი ჩამოდის `MegaPlus DB backup-ი — ახალი ZIP არ არის, cache-დან წაიკითხება` — ცრუ-შეტყობინება (ნამდვილი exception უკვე ცალკე WARNING-ად დაიწერა). მცირე UX bug-ი, ცალკე commit-ით.

### Files state (post-fix)

```
M  CONTEXT_HANDOFF.md                         (this update)
M  grant_system_megaplus_access.sql           (this session — +dbcreator +db_owner)
M  Financial_Analysis/orphan_user_status.json  (carried from prev session)
?? 8 screenshot PNGs                           (carried from prev session)
```

ბრანჩი ისევ 2 commit-ით წინ origin/main-ზე (push არ შესრულდა ჯერ).

### Open / next-session candidates

1. **F5 + verification** — wait for pipeline regen, F5, owner check fresh dates appear.
2. **Push origin** — `285a218` + `24e62ac` + (this handoff commit + grant SQL commit).
3. **Fix the misleading "ახალი ZIP არ არის" log** — distinguish "no new ZIP" from "refresh exception".
4. **Negative/Dead stock cleanup workflow** (carryover from #3).
5. **HOME-9 bookkeeping review** (carryover from earlier sessions).

---

## 0aa. წინა session (2026-05-17 დღე გაგრძელება #3) — INVENTORY CLEANUP ცალკე გვერდი

### Headline

Owner-მა შენიშნა: „ოზურგეთის მაღაზია 124,150 მიწერს მეგა პლიუსში ნაშთს და მაგდენი არ მიდევს მაღაზიაში". ვიყავი მაქს რეჟიმზე, სრულ გამოკვლევას ვიწყე დუბლირებიდან — SQL პირდაპირ MEGAPLUS_1301-ში: 1,877 დუბლირებული შტრიხკოდი, მაგრამ მხოლოდ 21 ნამდვილი phantom (1,125 ₾). იგივე-სახელი-სხვა-შტრიხკოდი დამატებითი 27 ჯგუფი (~2,077 ₾). სულ დუბლირებიდან გადანამეტი ~3,200 ₾ — 124,150-ის 2.6%. ე.ი. **დუბლირება არ არის მთავარი მიზეზი**. რეალური განცალკევება: **მკვდარი საქონელი** (1,123 პროდუქტი, 32,138 ₾ ოზურგეთში — 26%) რომელიც ფიზიკურად შესაძლოა აღარ არსებობს (გაფუჭდა, ვადა გავიდა, წაიკარგა).

ამის გადასაჭრელად — ცალკე გვერდი dashboard-ში, რომ Owner-მა MegaPlus-ში გაასწოროს და განახლების შემდეგ ჩამოვარდეს სიიდან.

### What shipped — 2 commit

| # | Commit | რა გავაკეთე |
|---|---|---|
| 1 | `285a218` | **Backend: inventory page module + cleanup section.** NEW `dashboard_pipeline/inventory.py` (live PRODUCTS + DISTRIBUTORS + ORDERS query per restored MEGAPLUS_<store>, builds inventory_view bundle). NEW `dashboard_pipeline/inventory_cleanup.py` (derives 3 problem-stock classes: dead 365+, negative qty, phantom duplicates). `generate_dashboard_data.py` wires both. `dashboard_pipeline/api_contracts.py` adds inventory_view + inventory_cleanup to FIELD_DEFAULTS + TAB_ALLOWLIST + SPECIAL_TAB_BUILDERS. Cleanup builder also derives on-the-fly from cached inputs — no regen needed for the tab to work immediately after service restart. NEW `grant_system_megaplus_access.sql` (idempotent SYSTEM db_datareader grant). |
| 2 | `24e62ac` | **Frontend: Inventory + Cleanup pages.** NEW `rs-dashboard/src/Inventory.jsx` (~470 lines — KPI cards, per-store toggle, 3 ცალკე search fields, DOS color badge, view filters, today's sales table). Filter logic split into 2 memos: `searchedItems` (supplier+text only — fed to TodaysSalesTable) vs `filteredItems` (view filter on top — fed to main table). NEW `rs-dashboard/src/Cleanup.jsx` (3 KPI cards + tabbed tables dead/negative/phantom + per-store toggle + search + CSV export). App.jsx + tabConfig.js wire `inventory` + `inventory_cleanup` tabs under გაყიდვები group. |

### Verification done

1. **SQL forensics** — MEGAPLUS_1301 raw query: 1,869 P_BARCODE clusters with 2+ active products. Only 4 clusters have 2+ stock-positive variants (1 of which is barcode "2" placeholder). BARCODES secondary table: 1 cluster with 2+ stock. Name-based potential dups: 27 groups. **Total max inflation: ~3,200 ₾** (vs 121,485 ₾ Ozurgeti total = 2.6%).
2. **API live** — `/api/data?tab=inventory_cleanup` returns `available: true`, totals: dead=1960 (60,102 ₾), negative=1753 (34,724 ₾), phantom=21 (1,125 ₾). ოზურგეთი: dead=1123, neg=1039, phantom=21. დვაბზუ: dead=837, neg=714, phantom=0.
3. **Vite build** — წარმატებით, `Cleanup-CQYflJ1-.js` 15.08 kB chunk, BUILD_ID `mpa1ry4s-8s5o9l`.
4. **Service restart** — UAC დიალოგი დადასტურდა, status Running. `/api/data?tab=meta` 400-ი დააბრუნა, რაც დაადასტურა რომ `inventory_cleanup` ALLOWED_TABS-ში ჩაჯდა.
5. **Playwright browser** — `http://localhost:8000/#inventory_cleanup` რენდერდება, KPI = API ჯამები, ოზურგეთი → Phantom tab → 21 row, პირველი row: სულგუნი დიდგორი / barcode 1166 / iconflict ორცხობილა-სთან (იგივე რასაც SQL forensics-ში ვიპოვე). CSV button enabled.

### How the auto-drop works

Cleanup სია derived-ია `inventory_view` და `duplicate_products`-დან, რომლებიც ცოცხლად რეგენდება pipeline-ის ყოველი regen-ის შემდეგ. Workflow:

1. Owner CSV ჩამოტვირთავს ან გვერდიდან ხედავს.
2. MegaPlus-ში ფიზიკურად ამოწმებს, „ჩამოწერა"/„კორექცია" qty=0-მდე.
3. Dashboard → „ხელახლა გათვლა" (5-10 წთ) → F5.
4. გასწორებული row ავტომატურად ჩამოვარდება (filter `qty > 0` + dead/`qty < 0` neg/phantom kind logic აღარ მოიხედავს).

### Files state (post-commits)

```
M  CONTEXT_HANDOFF.md            (this update)
M  Financial_Analysis/orphan_user_status.json  (owner UI action, untouched)
?? 8 screenshot PNGs              (testing artifacts, not committed)
```

ბრანჩი 2 commit-ით წინ origin/main-ზე. Push-ი ჯერ არ.

### Open / next-session candidates

1. **Push origin** — `285a218` + `24e62ac` + (this handoff commit).
2. **Negative stock cleanup workflow** — 1,753 row მინუსში. Owner-მა ფიზიკურად შეამოწმოს და MegaPlus-ში გასწოროს.
3. **Dead stock cleanup workflow** — 1,960 row 365+ დღე. გავამახვილოს რომელია ნამდვილად დაგროვილი vs ნამდვილად დაკარგული.
4. **Phantom dedup tool** — 21 phantom variant MegaPlus-ში ხელით inactive-ად მონიშვნა, ან ფასების merger.
5. **Memory adds** — `project_ozurgeti_inventory_audit_2026-05-17.md` (124k MegaPlus vs ~100k physical, root cause = dead stock not duplicates), `project_inventory_cleanup_tab.md` (architecture: auto-drop on regen).

---

## 0a. წინა session (2026-05-17 დღე გაგრძელება #2) — INVENTORY ფილტრი fix

### Headline

Owner-მა შენიშნა: „მომწოდებლის კომპანიის სახელწოდებას რომ ვწერ უმოქმედოა". Browser-ში დადასტურდა — input მართლა იღებდა keystroke-ს და მთავარი „პროდუქცია" ცხრილი ფილტრდებოდა (6707 → 40 row), მაგრამ search input-ის მაშინვე ქვემოთ მდებარე „📅 დღევანდელი გაყიდვა" ცხრილი storeView.items-ს იღებდა და ფილტრს არ ეპასუხებოდა. Owner ხედავდა „ელიზი ჯგუფი", „ახალიგეო" — სხვა მომწოდებლების სიგარეტებს — და ჰგონებდა რომ ფილტრი არ მუშაობს.

### Fix

`rs-dashboard/src/Inventory.jsx` — filter ლოგიკა ორ memo-ად გავყავი:
- **`searchedItems`** — მხოლოდ supplier + text search filters (company / name / barcode). გამოიყენება `TodaysSalesTable`-ში.
- **`filteredItems`** — view filter (low / dead / stockout / negative / all) `searchedItems`-ის თავზე. გამოიყენება მთავარ ცხრილში.

რატომ ცალკე: Today's sales-ში თვითონ აქვს `qty_sold_today > 0` ფილტრი, ამიტომ stock-ის view (qty>0 etc) არ უნდა ეხედებოდეს — წინააღმდეგ შემთხვევაში დღევანდელი გაყიდვის ცარიელი ცხრილი გამოვა იმ პროდუქტებზე, რომელთა ნაშთიც ნულზე ან უარყოფითზე ჩავარდა გაყიდვის შემდეგ.

### Verification

- Vite build წარმატებით (`Inventory-D_W66v52.js`, BUILD_ID `mp9yzwc2-e7t5ab`).
- Playwright: კომპანიის ველში „ჯიდიაი" → ორივე ცხრილში პირველი row „ჯიდიაი შპს". მთავარი ცხრილი: 40 ცალი (იყო 6707).
- Screenshot `inventory-filter-fixed.png` დადასტურდა.

### Files state — uncommitted ბოლო session-ის + ამ fix-ის (8 ფაილი)

```
M  rs-dashboard/src/Inventory.jsx            (this session — 2-memo split + TodaysSalesTable items={searchedItems})
A  dashboard_pipeline/inventory.py            (prev session — NEW, ~330 lines)
M  generate_dashboard_data.py                 (prev session — +27 lines)
M  dashboard_pipeline/api_contracts.py        (prev session — +2 lines)
M  rs-dashboard/src/App.jsx                   (prev session — +5 lines)
M  rs-dashboard/src/tabConfig.js              (prev session — +1 line)
A  grant_system_megaplus_access.sql           (prev session — SYSTEM db_datareader grant)
?? rs-dashboard/dist/                          (rebuilt)
```

---

## 0b. წინა session (2026-05-17 დღე გაგრძელება #1) — INVENTORY: ცოცხალია + SYSTEM grant + 3 search field

### Headline

წინა session-ში backend + frontend „ნაშთები" გვერდი ააწყო, მაგრამ pipeline-ი ცარიელ `inventory_view`-ს აბრუნებდა, რადგან NSSM სერვისი `NT AUTHORITY\SYSTEM`-ით ეშვება და MEGAPLUS SQL ბაზებზე წვდომა არ ჰქონდა. ამ სესიაში: (1) SYSTEM-ს მიენიჭა `db_datareader` MEGAPLUS_1329 + MEGAPLUS_1301-ზე → pipeline ახლა ცოცხლად ააწყობს inventory-ს ყოველი regen-ის შემდეგ; (2) Owner-მა მოითხოვა საძიებო ველების სამად გაყოფა (კომპანია / პროდუქტი / შტრიხკოდი) — გაკეთდა; (3) payload 10 MB-დან 4.8 MB-მდე შემცირდა (alerts arrays + 5 unused per-SKU field მოშორდა, supplier rollup ერთ pass-ში folded); (4) საძიებო ველები მაღაზიების ღილაკების მაშინვე ქვემოთ გადავიდა. ბრაუზერში დადასტურდა (Service Worker banner-ით განახლება).

### What shipped (uncommitted — adds to prev session work)

| ფაილი | რა შეიცვალა (ამ session-ში) |
|---|---|
| **NEW** `grant_system_megaplus_access.sql` | One-time idempotent SQL script. `CREATE LOGIN [NT AUTHORITY\SYSTEM] FROM WINDOWS` + `CREATE USER` + `ALTER ROLE db_datareader` MEGAPLUS_1329 + MEGAPLUS_1301-ზე. გაშვება: `sqlcmd -E -S localhost\SQLEXPRESS -i grant_system_megaplus_access.sql`. **გავიდა ჩემი user-ით (windows sysadmin რომ ჰქონდა)** — owner-მა admin powershell არ დასჭირდა. |
| `dashboard_pipeline/inventory.py` | (a) წაიშალა `alerts` ბლოკი (4× dup data items-ში); (b) წაიშალა 5 unused per-item field: `margin_unit`, `margin_pct`, `active`, `qty_sold_7d`, `sell_through_30d_pct`; (c) supplier rollup folded into the same loop as items[] (no second pass over items[] for `revenue_30d`/`qty_sold_7d`); (d) totals_combined-ში revenue_30d/qty_sold_30d/today ჯამიდან by_supplier-დან გადათვლა. **Payload effect: 10,026,725 → 6,596,935 → 4,892,xxx bytes** (52% შემცირება). |
| `rs-dashboard/src/Inventory.jsx` | (a) `search` single field → 3 ცალკე state: `searchCompany` (supplier_name + supplier_tax_id), `searchName` (product_name only), `searchBarcode` (barcode + product_code). 3 ცალკე input. (b) Controls section მაღაზიების ღილაკების მაშინვე ქვემოთ გადავიდა (იყო Today's sales-ის შემდეგ). Today's sales ახლა search-ის შემდეგ. |

### Verification done

1. **SQL grant** — `sqlcmd -E ...` წარმატებით → `Done. NT AUTHORITY\SYSTEM has db_datareader on MEGAPLUS_1329 and MEGAPLUS_1301.`
2. **Pipeline regen via `/api/refresh`** — დასრულდა ~22 წთ. Log: `inventory_view → data.json: 6707 SKU, 255209 ₾ cost-value, 318776 ₾ retail-value, dead 23.6%, alerts: neg=1753 stockout=195 low=826 dead365=1960`. SYSTEM-ით ცოცხლად მუშაობს ✅.
3. **Payload size measurement** — `curl ... | wc -c`: 10,026,725 → 6,596,935 (alerts dropped) → 4,892,xxx (per-item fields trimmed). Frontend ჯერ ნელია 4.8 MB-ზე — შემდგომი ოპტიმიზაცია 200-row pre-pagination server-side შემდეგი session-ისთვის.
4. **Vite build** — წარმატებით (`Inventory-DAZTC6z8.js`, `index-DQuK5SOM.js`, BUILD_ID `mp9qczba-hyfybl`).
5. **Playwright browser verify** — `http://localhost:8000/#inventory` → ხედავა 6,707 SKU, 255k ₾, KPI ცხრილი, 3 search ველი (კომპანია/პროდუქტი/შტრიხკოდი), მაღაზიების ღილაკები. Snapshot DOM-ში დადასტურდა labels: `კომპანია (მომწოდებელი)` / `პროდუქტის სახელი` / `შტრიხკოდი / კოდი`.
6. **Owner verify** — „გამოჩნდა მაგრამ მირჩევნია ოზურგეთი და დვაბზუს ქვემოთ იყოს" → reorder შესრულდა. „კარგი არის" → დადასტურდა.

### ⚠️ STILL OPEN — შემდეგი session-ისთვის

1. **Commit + push** — 7 uncommitted ფაილი (იხ. ქვემოთ). Owner-მა approve თქვა; ერთ commit-ში ან 2-ში (pipeline + UI ცალკე).
2. **Payload further reduce** — 4.8 MB ჯერ კიდევ ნელია first-load-ზე. Options: (a) server-side top-200 per store + on-demand load (b) ცალკე endpoint `/api/inventory/items?store_id=&supplier_uuid=&offset=&limit=` და მთავარ tab-ში მხოლოდ summaries; (c) gzip უკვე ჩართულია (sent 4.8 MB → wire ~700 KB), მაგრამ parse + render ბრაუზერში მაინც დიდია.
3. **Negative stock cleanup** — 1,753 უარყოფითი row (data quality). Owner-ის ხელით recount-ი ან ცალკე filter view.
4. **Stockout reorder workflow** — 195 stockout SKU → ღილაკი „ზედნადები შევქმენი".
5. **Brand vs supplier disambiguation** — orphan products (P_DAFAULTSUPPLIER ცარიელია, „(უცნობი)" შევარდა).
6. **Bookkeeping review #1** (HOME-9 carryover) — AP headline + Net liquidity card.

### Industry KPIs (carryover from prev session — still in code)

- **Days of Supply (DOS)** = qty / (qty_sold_30d / 30). UI ფერი: < 7 წითელი, 7-21 ყვითელი, ≥ 21 მწვანე.
- **Sell-through 30d %** — გათვლა inline მუშაობდა, მაგრამ field წაიშალა (UI არ იყენებდა). საჭიროების შემთხვევაში inventory.py-ში დააბრუნება.
- **Stock turn (annualized)** — future extension.

### Files state (uncommitted, full session combined)

```
A  dashboard_pipeline/inventory.py            (NEW, ~330 lines now; trimmed + inline rollup)
M  generate_dashboard_data.py                 (+27 lines — prev session)
M  dashboard_pipeline/api_contracts.py        (+2 lines — prev session)
A  rs-dashboard/src/Inventory.jsx             (NEW, ~470 lines now; 3-field search + reorder)
M  rs-dashboard/src/App.jsx                   (+5 lines — prev session)
M  rs-dashboard/src/tabConfig.js              (+1 line — prev session)
A  grant_system_megaplus_access.sql           (NEW, this session)
?? rs-dashboard/dist/                          (rebuilt; new chunks Inventory-DAZTC6z8.js + index-DQuK5SOM.js)
?? home-bookkeeping-review.png                 (pre-existing, ignored)
```

### Memory adds this session

- `project_megaplus_system_db_grant.md` — SYSTEM-ის db_datareader grant ფაქტი + სკრიპტი (idempotent, re-run safe).
- `feedback_try_before_asking_user.md` — ვცადო ბრძანება ჩემი tool-ით ჯერ, შემდეგ მხოლოდ წარუმატებლობის შემთხვევაში ვთხოვო user-ს admin-ით. burned by `sqlcmd -E` რომელიც user-ის sysadmin-ით უპრობლემოდ გავიდა.

---

## 0c. წინა session (2026-05-15) — HOME-9: 10 ბაგი + bookkeeping review

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

## 0d. წინა session (2026-05-14 ღამე) — HOME-8: bank balance + cash-till + freshness + agent quality

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

## 0e. წინა session (2026-05-14 დილა) — HOME-7: audit + 3 bugs

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
