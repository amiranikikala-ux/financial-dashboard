# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-03 (afternoon — Phase 1 (a) PRODUCTS fragmentation closure as phantom + supplier_profitability false alarm). **NO COMMITS, READ-ONLY**. ადრინდელი დღის 3 commit (`61ffe93` + `e8dc73f` + `aef42c9`) ისევ local main-ზე — push pending. data.json fresh (106 MB, 2026-05-03 02:36).
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. სრული ისტორია (აპრილი 18 → მაისი 2) → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`.

---

## 1. ბოლო სამუშაო session-ი (2026-05-03)

### 1a. ღამე-მერე — Phase A + Phase B exploratory research (READ-ONLY)

**Scope:** ბუღალტრული ცდომილებების catalog-ი (Phase A) + 4 detector-ის შემოწმება მონაცემზე (Phase B). **არცერთი production კოდი არ შეცვლილა, არცერთი commit, არცერთი push.** მთლიანი work in-process scratch-ფაილებში — ყველა წაშლილი ფინალურ რეპორტთან ერთად. რეპორტები chat-ში დარჩა.

**Phase A — 34-ცდომილების catalog (chat-ში, no .md per scope):**
- 6 ბლოკში დაიყო: დოკუმენტური · VAT · cross-source · რაოდენობა/ნაშთი · ფასი/მარჟა · სპეციფიკური
- 6 უკვე ვიჭერთ (waybill_reconciliation tab — missing/wrong_store/amount_mismatch/ghost_ap/returns/stale)
- 25 ახალი detector კანდიდატი + 3 ნახევრად ღია
- წყაროები: `SHPS_RETAIL_TAX_GUIDE_KA.md` · საგ. კოდექსი მუხ. 286 · #84/#86/#996 ბრძანებები · eaudit.ge · matsne #5389341

**Phase B — 4 detector შემოწმდა:**

| # | detector | ვერდიქტი | რა აღმოჩნდა |
|---|---|---|---|
| 5  | ფაქტურის გვიანი გამოწერა (>2 დღე) | ❌ NO VALUE | 99.6% ხაზი ±2 დღეში; MegaPlus G_TIME თითქოს ფაქტურის ქაღალდიდან კრეფს — ვერ აკონტროლებს |
| 20 | არააღრიცხული პროდუქცია | ⚠️ DATA QUALITY FIRST | 6,656 candidate / 572K ₾ — დომინირებს PRODUCTS ფრაგმენტაცია + ობოლი მომწოდებლები |
| 21 | უარყოფითი ნაშთი | ⚠️ DATA QUALITY FIRST | 2,408 product / 149K ცალი deficit — დომინირებს consumables (პარკი/ჭიქა/რეზინი) + 38% trivial timing |
| 25 | უარყოფითი მარჟა | 🚨 ცხადი სიგნალი + ახალი ცოდნა | 57,048 row (4.13% with-cost) / **95,682 ₾ loss** 4 წელში — დომინირებს packaging-unit cost confusion |

**🆕 ახალი ცოდნა — 3 ფესვიანი findings (Phase B-ის მთავარი ღირებულება):**

**1. Packaging-unit cost confusion** (Detector #25) — ოპერატორები POS-ში cost-ად აკრეფენ **ბლოკის ფასს**, მაგრამ ცალი იყიდება ცალკე-ცალკე. შედეგი: სისტემა ცრუ-უარყოფით მარჟას აჩვენებს. ცნობილი მომწოდებლები:
   - **ELIZI ჯგუფი** (Sobranie/Vinston: cost 72-89 ₾ per pack while sale 7-9 ₾) — 290 row / 15,913 ₾
   - **ჯიდიაი** (Marlboro: იგივე pattern)
   - **კრიკეტ სანთებელა** (cost 30 ₾ per piece while sale 0.25 ₾) — 95 row / 2,709 ₾
   - **ჰიგიენური საფენი ბენგული** (cost 10 ₾ vs sale 0.30 ₾) — 74 row / 2,056 ₾
   - **ზედაზენი 2012 ლუდი** (highest row count — 6,502 row / 14,101 ₾ false-loss)
   - **ეს განამტკიცებს `AGENTS.md`-ის PROTECTED cigarette წესს** — არა მხოლოდ მარჟისთვის. ცალკე workflow აშკარად საჭიროა (POS cost-entry validation, ან known packaging-factor table per supplier+category).

**2. PRODUCTS table ფრაგმენტაცია** (Detectors #20/#21) — **1,299 barcode** ერთდროულად ფიქსირდება ორივე მაღაზიის "უარყოფით" სიაში; **252 dual-store P_ID ფრაგმენტი**. იგივე ფიზიკური barcode სხვადასხვა P_ID-ს ეძახიან per-store. შედეგი: receipt ერთ P_ID-ს მიენიჭება, sale მეორეს, აგრეგატი არასწორი.

**3. ობოლი მომწოდებლები** (Detector #20) — **3,046 product** (~24% სრული catalog-ის) PRODUCTS ცხრილში default supplier-ის გარეშე (`P_DAFAULTSUPPLIER` ცარიელი). 4-წლიანი revenue 231K ₾. ბევრს რეალურად აქვს მომწოდებელი rs.ge-ზე, უბრალოდ PRODUCTS-ში ცარიელადაა.

**Phase B გადაწყვეტილება:** **ვაჩერებთ #25-ზე**. ❌ არ ვაშენებთ ცალკე ტაბებს — სამივე detector (#20/#21/#25) იმავე ფესვის გამო ცრუ-დადებითს იჭერს, ცალ-ცალკე ფილტრების კასკადი ცხადობას არ მოცემს. ✅ ჯერ data quality unified sprint (იხ. §3.4 ქვემოთ), მერე detector-ების ხელახლა აშენება უფრო ცხადი ნიადაგზე.

**6 detector ცხრილში გადადგმული** (Phase A-დან, არ შემოწმდა — ხელმისაწვდომია მომავალი sprint-ისთვის post-cleanup):
- #23 — ერთი პროდუქტი, რამდენიმე barcode (overlap with PRODUCTS cleanup)
- #24 — duplicate ფაქტურის ნომერი (rs.ge same zed_base, multiple active rows)
- #26 — ფასის უცაბედი ცვლილება (>30% jump per-product per-month)
- #28 — 0 ფასი ან 0 რაოდენობა per-line
- #32 — დაბრუნების შებრუნებული თარიღი (GACERA date < GET date)
- #34 — ერთი თანხა, ორი მომწოდებელი (split fraud, წარმ. 1% ლიმიტის გვერდის ავლა)

### 1b. ღამე-ადრე — cleanup + MegaPlus layout migration (`61ffe93` + `e8dc73f`)

**🧹 `61ffe93` chore(cleanup): trim CONTEXT_HANDOFF + remove obsolete archives + scratch artifacts**

- CONTEXT_HANDOFF.md — 110 KB / 576 ხაზი → **12 KB / 88 ხაზი**; სრული ისტორია არქივში გადავიდა (`HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`).
- HANDOFF_ARCHIVE — 18 ფაილი წაიშალა: 3 superseded planning doc + 15 pre-MASTER_PLAN preview. HANDOFF.md-ის pointer block განახლდა.
- 47 `_scratch_*.py / .json` root-ში წაიშალა · `__pycache__` წაიშალა.
- **`_to_delete_2026-04-29\` ფოლდერი parent-ში permanent წაიშალა** (994 MB / 16,021 ფაილი) — dashboard ცოცხალი დარჩა, disk free 259 GB.

**🟢 `e8dc73f` feat(megaplus): discover backup folders under მეგაპლიუსის არქიტექტურა layout**

- User-მა PLUS_*.zip backup-ები ძველი `მეგა პლუს backup*` sibling ფოლდერებიდან ახალ `Financial_Analysis/მეგაპლიუსის არქიტექტურა/<store>/` სტრუქტურაში გადააწყო.
- **Fix**: `megaplus_backup._discover_watch_folders` ახლა ორივე layout-ს პოულობს (legacy glob + ახალი arch parent + PLUS_*.zip presence check). `generate_dashboard_data.py` inline glob შეიცვალა helper-ის import-ით.
- Pipeline run end-to-end: 18.6 წთ / 0 errors / 0 warnings. data.json 106 MB.
- **Live numbers**: დვაბზუ 282 supplier / 2,229,889 ₾ rev / 12.34% margin; ოზურგეთი 308 supplier / 2,631,008 ₾ rev / 12.17% margin. ჯამი 4.86 მლნ ₾ rev / 595K ₾ profit / 8,456 პროდუქტი / 37 თვე.
- **ხვალინდელი backup**: PLUS_*_MEGA_20260503.zip ჩავარდნისთანავე pipeline ავტომატურად აიღებს.

---

## 2. დღის შუა session-ი (2026-05-03 afternoon — research-only)

**Scope:** research-only session, **არც code change, არც commit, არც push.** Phase 1 (a) PRODUCTS fragmentation deliverable-ის source-first re-derivation + Type A subtype split + pipeline aggregation trace + supplier_profitability false-alarm diagnostic. 2 preview ფაილი დაიწერა, არც ერთი commit-ში არ შესულა.

### 2a. Phase 1 (a) PRODUCTS fragmentation — CLOSED as phantom

- გუშინდელი chat-ის anchor numbers (**1,299 / 252**) **არ გადარჩა** fresh source-first re-derivation-ს — გუშინდელი exact SQL ფაილზე არ შენახულა (cleanup-ში წაიშალა, §1a documents), მხოლოდ chat-ში დარჩა
- რეალური fragmentation (TRIMMED for trailing whitespace): **2,210 union dual-store barcode** (intra-store P_BARCODE → multiple P_ID), **1,190 ორივე მაღაზიაში ერთდროულად**
- Subtype split (1,190-დან): **TYPING_DUP 12** (~3,325 ₾, real cosmetic damage) + **SKU_VARIANT 33** (~20,097 ₾ revenue but pipeline handles correctly per-P_ID — false damage) + **BORDERLINE 4** (~4,731 ₾) + Type B 769 (catalog noise, **0.80 ₾ active in 12 months** — virtually dead)
- Pipeline aggregation traced ცოცხალ კოდში:
  - **Per-P_ID** at source rollup: `dashboard_pipeline/megaplus_backup.py:417-418` — `GROUP BY p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_UNIT, p.P_GROUP, ...`
  - **Per-barcode** at retail_sales cross-store merge: `dashboard_pipeline/retail_sales.py:451-462` — `key = barcode or code or pid_*`
  - **Cosmetic name-pick only** (line 461-465 `setdefault` never updates name; first-encountered variant wins display)
  - **Sums correct linearly** (lines 478-482 — revenue/cost/profit/qty)
  - **`object_totals` preserves per-store-per-P_ID granularity** (lines 484-492 — multi-entry per store)
- ფინალური fix scope: **~3,325 ₾ TYPING_DUP cosmetic merge**, low priority, შეიძლება existing category_anomalies tab pattern-ით ჩავახვიოთ მისი შემდეგი sprint-ის დროს

### 2b. supplier_profitability "absent" surprise finding — FALSE ALARM

- §12-ში მისრიდი: top-level `data.json["supplier_profitability"]` key-ი ვეძებდი → ვერ ვიპოვე → claim "section არ ცოცხლდება data.json-ში"
- რეალობა: ცოცხალი მონაცემი **nested location-ში** — `imported_products.suppliers[*].profitability` (**220/220 supplier**) + `imported_products.profitability_summary` (overall: **4.86M ₾ cost / 300K ₾ profit / 13.86% margin / 64.88% coverage**)
- Active usage: `rs-dashboard/src/SupplierModal.jsx:405-740+` — UI არ არის broken, არ არის regression, არ არის stale
- Pattern intentional ორიგინალური wire-up-დან (commit `8455486`, **2026-04-26**) — never was top-level key. Verified via git blame `generate_dashboard_data.py:1849-1857` და `git log -S 'data["supplier_profitability"]'` (empty result)

### 2c. Two preview files written this session (no commit)

- `HANDOFF_ARCHIVE/PREVIEWS/PRODUCTS_FRAGMENTATION_2026-05-03.md` — **1,348 ხაზი**, §4–§12 (definition + count + Type A/B/Ambig + 12mo activity + Type A drill-down + subtype split + pipeline trace clarification)
- `HANDOFF_ARCHIVE/PREVIEWS/SUPPLIER_PROFITABILITY_ABSENCE_2026-05-03.md` — **247 ხაზი**, diagnostic only

### 2d. Lesson logged

როცა Claude (terminal) ანონსირებს „surprise out-of-scope finding" — **ერთი fresh query-თ verify-ი მანამდე სანამ actionable-ად მოვექცე**. დღევანდელი supplier_profitability detour ~30 წთ false alarm იყო, რადგან misread fact-ად გადავაქციე და ცალკე diagnostic-ზე ენერგია წავიდა.

### 2e. Open for next session (priority order)

1. **Phase 1 (b) PRODUCTS orphans** — გუშინდელი chat-ის claim **3,046 product / 231K ₾** **NOT verified in source**. შემდეგი session-ი source-first scratch-დან უნდა derive-ს, **არა გუშინდელი ციფრს დაუბრუნდეს** (per Phase 1 (a) lesson — anchor numbers from chat are unverified)
2. **Phase 1 (c) packaging-unit cost confusion** — გუშინდელი **95,682 ₾** claim same caveat. ELIZI/ჯიდიაი/სიგარეტი/სანთებელა/საფენი/ლუდი pattern — fresh source-first re-derivation needed
3. **TYPING_DUP cosmetic merge** (~3,325 ₾, 12 barcode) — low priority, შეიძლება existing `category_anomalies` tab pattern-ით ჩავახვიოთ category_anomalies-ის შემდეგი sprint-ის დროს
4. **Type B catalog cleanup** (769 dormant SKUs, 0.80 ₾ active in 12 months) — preventive only (zero current financial signal), ცალკე sprint, MegaPlus-side POS uniqueness-check workflow

### 2f. Pending push state (2026-05-03 afternoon)

- **3 local-only commits** (origin/main-დან 3 ahead): `61ffe93` (cleanup) + `e8dc73f` (MegaPlus layout migration) + `aef42c9` (yesterday's handoff close from morning session)
- ⚠️ Note: მომხმარებლის დღის initial assumption-ში 2 commit იყო ნახსენები; მე-3 (`aef42c9`) დაემატა გუშინდელი მორნინგ session-ის handoff close-ით — ჯერ ისევ local
- `CONTEXT_HANDOFF.md` modified (today's update — uncommitted)
- 2 ახალი preview ფაილი untracked (`HANDOFF_ARCHIVE/PREVIEWS/PRODUCTS_FRAGMENTATION_2026-05-03.md` + `SUPPLIER_PROFITABILITY_ABSENCE_2026-05-03.md`)
- 1 untracked folder: `Financial_Analysis/მეგაპლიუსის არქიტექტურა/` (MegaPlus backup folder structure — see §1b)
- **Push არ მოხდა — user-ის ნება**

---

## 3. ჯერ-ჯერობით წინა session-ი (2026-05-02 evening)

**`e5ee7ea` feat(waybill-reconciliation): wrong-store category** — ზედნადებების შედარებაში ცალკე გამოჩნდა „🔄 არასწორი მაღაზია" ჯგუფი (4-წლიან 3,978 active rs.ge-ზე: 28 wrong_store / ₾13,237). Spot-check-ით 26 false-positive class დაიჭირა — fix `ACTIVE_STORE_KEYWORDS["1329"]` `"დვაბზუ"` → prefix `"დვაბზ"`.

**`6d45dd7` feat(pwa): soft update banner** — საიტი მუშაობის შუაში თვითონ აღარ რეფრეშდება. ახლა მარცხნივ-ქვემოთ მწვანე ბანერი „განახლება" ღილაკით. **One-time activation cost**: ძველი sw.js-ით გახსნილი tab-ებს ერთხელ ავტო-რეფრეში მოუვათ, მერე ბანერი ცოცხლდება.

---

## 4. შემდეგი session-ის OPEN list (priority order)

1. **🟢 MegaPlus cleanup workflow გაგრძელდება** — user აქტიურად იყენებს ტაბს, pattern-ი ცოცხლდება: „MegaPlus-ში ერთი batch ჩავასწორებ, ხვალ PLUS_*.zip backup ჩამოვწერ, pipeline ცვლილებას აიღებს, რიგი ცხრილიდან გაქრება". **არაპროაქტიულად კონკრეტულ რიგებზე ხელი არ გავიწიოთ**; user თვითონ გამოიტანს. როცა გამოიტანს — D&L / Partnyori / Lactalis-ისებური line-by-line drill-down (GET vs rs.ge xls diff, plain-ქართული explanation).
2. **🟢 Browser smoke-check pending** — `6d45dd7` (PWA banner) GitHub-ზეა მაგრამ user-ს ჯერ არ გადაუხედავს. პირველი F5-ი ერთხელ ავტო-რეფრეშს გამოიწვევს (ძველი sw.js cache-ში); მერე ბანერი ცოცხლდება. პრობლემის შემთხვევაში: dist bundle hash უნდა იყოს `index-hfmLnxUb.js`.
3. **🟢 ცვლილებების push origin/main-ზე** — `61ffe93` + `e8dc73f` ჯერ origin-ზე არ აიტვირთა (local main 2 ahead). user-მა „push" როცა მოითხოვოს — ერთად აიგზავნება.
4. **🚨 Data Quality Unified Sprint — DECISION READY (post-Phase-B)** — Phase B-ის (2026-05-03) მთავარი დასკვნა: **3 detector ერთი ფესვს ეჯახება**. ფუნდამენტი 3 ნაწილია:
   - **(a) PRODUCTS orphan resolution** — 3,046 product (~24% catalog) / 231K ₾ revenue / `P_DAFAULTSUPPLIER` ცარიელი. ბევრს რეალურად აქვს მომწოდებელი rs.ge-ზე.
   - **(b) P_ID dual-store fragmentation** — 252 barcode / per-store სხვადასხვა P_ID. Receipt ერთს, sale მეორეს, აგრეგატი ფრაგმენტული. Manual mapping ან automated barcode-based unification.
   - **(c) Packaging-unit cost-entry workflow** — POS-ში cost ბლოკის ფასით იწერება, ცალით იყიდება. სისტემური ELIZI/ჯიდიაი/სიგარეტი/სანთებელა/საფენი/ლუდი მიმართულებით (იხ. §1a finding #1). საჭიროა: cost validation rule, ან known packaging-factor table per supplier+category, ან POS workflow change.
   - **Blocks**: detectors #19, #20, #21, #22, #24, #26 — ყველა საჭიროებს ცხად per-product per-store მონაცემს.
   - **Path forward**: user-ის გადაწყვეტილება — (1) data quality cleanup ერთიანი sprint-ით (1-2 კვირა, ფესვი იხსნება ერთხელ), ან (2) #25-ის ფილტრიანი detector-ი ცალკე (~1 sprint, partial signal), ან (3) სხვა მიმართულება.
5. **🟢 Carryover (არა-blocking)**:
   - RS_CODES-based product matching (189,015 rs.ge↔Megaplus mappings MegaPlus DB-ში — name-fuzzy-ის ჩანაცვლება exact JOIN-ით; ~1 sprint). შესაძლოა (a)/(b) cleanup-ის ფარგლებში გადაიჭრას.
   - Auto-sync OneDrive↔C:\ — drift-ი მეორდება; post-commit/post-merge hook ან scheduled task.
   - `retail_sales_top_products` SQLite export bug (`dashboard_pipeline/export_sqlite.py:111` reads `top_products`, schema-ში `top_products_by_revenue` / `_by_profit`).
   - ოზურგეთი DB 234 orders dated 2009 (0.026% / 661 ₾, optional date filter) — Phase B-ში დადასტურდა (#21-ში 117 product first_neg_year=2009).
   - rs.ge automation deferred — user-მა manual download აირჩია.
6. **🟢 Category-anomalies UI follow-ups (deferred)** — deep-link / severity scoring / Excel export — **მხოლოდ user-ის მოთხოვნით**.

---

## 5. Verified facts (cross-check ვიდრე action)

| მაჩვენებელი | მნიშვნელობა |
|---|---|
| pytest (key suites) | **39/39** waybill_reconciliation + 50/50 supplier_profitability + retail_sales_revenue_formula |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 16 (waybill_reconciliation tab-ში "🔄 არასწორი მაღაზია" group) |
| `data.json` | **106 MB** (post-MegaPlus-rediscovery, 2026-05-03 02:36) |
| Local branch | `main` 2 ahead of `origin/main` (`61ffe93` + `e8dc73f` — push pending) |
| MegaPlus DB integration | LIVE — 53 tables / 282+308 suppliers across 2 stores / 720K active orders / 2024-03 → 2026-04 |
| MegaPlus watch folder layout | `Financial_Analysis/მეგაპლიუსის არქიტექტურა/{დვაბზუ,ოზურგეთი}/` (legacy `მეგა პლუს backup*` glob still supported) |
| **Phase B exploratory data (2026-05-03)** | POS active rows 1,552,457 (4yr); with-cost 89.1%; **negative-margin 4.13% / 95,682 ₾ loss** (dom. by packaging-unit confusion); negative-inventory 2,408 product / 149K unit deficit; unrecorded products 6,656 / 572K ₾; PRODUCTS orphans 3,046 / 231K ₾; dual-store P_ID fragments 252 |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |

---

## 6. Active open work

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| **🟡 0a CODE COMPLETE — smoke-test pending** | **Sprint C alias UI** browser smoke-test — endpoint LIVE post-restart, 8 tests green, just need user-side click. Steps: (1) `_vite-dev.bat` → http://127.0.0.1:5173, (2) მომწოდებლები ტაბი → ვასაძის პური → modal → ალიასის კანდიდატები, (3) „✓ დადასტურდი ალიასი" → toast + product_aliases.json write + pipeline rerun. | ~30 წთ | LOW |
| **🚨 0c — DECISION READY** | **MAX vendor-tag file integration** (ELIZI / შრომა / etc. KPI gaps) — file landed at `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (45 KB, 116 suppliers, **დვაბზუ store only**). 3 paths: **(A)** read-only side-by-side (~1 session, low risk); **(B)** soft replacement when MAX matches by tax_id (~2 sessions, medium); **(C)** file loader only (~30 წთ, low value alone). User picks A/B/C. ოზურგეთი analog file ⏳. | A=1 / B=2 / C=0.5 sessions | **HIGH** |
| **🚧 CAL** | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა. `supplier.profitability.daily_breakdown[]` sparse aggregation საჭიროა. | ~1 session | LOW |
| **🆕 0f Sprint D candidate** | **Cross-source revenue gap** — MAX vendor-tag vs RS waybill (ვასაძე@დვაბზუ Q1 2026: pipeline 3,888 ₾ vs MAX 11,477 ₾ ground-truth, 7,589 ₾ gap). Sprint C alias UI არ წყვეტს. Investigation paths: (1) MAX-ის per-supplier sales report direct export, (2) MAX-vendor-tag column retail_sales pipeline-ში, (3) KPI banner caveat. | 2-3 investigation + 1-2 impl | MEDIUM |
| 1 | Supplier Profitability Sprint C UI extensions — render `ambiguous_preview` (46 invisible candidates) + bulk-confirm + DELETE endpoint | ~1 session | LOW |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` (TOOL_SCHEMAS 29 → 30) | ~1 session | LOW |
| **🧹 1-week-pending** | OneDrive `financial-dashboard\` copy retire (NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ში divergence იზრდება) | ~30-45 წთ mini-sprint | MEDIUM |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) — vulture dead-code, jsonschema config, golden snapshot, reconcile_suppliers spread, Pandera RS.ge CSV reader | 1-2 sessions | LOW |

---

## 7. Canonical paths & services (do-not-touch)

⚠️ **Source ფაილების canonical path — symlink სტრუქტურა (2026-04-29 verified):**
- **pipeline view**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis\`
  - 15 JSON config (real, canonical) — `cash_outflow_journal.csv`, `product_aliases.json`, etc.
  - 5 symlink target ფოლდერი → `..\Financial_Analysis\` (parent):
    - `ბოგ ბანკი ამონაწერი`, `გაყიდული პროდუქტები სოფ დვაბზუ`, `გაყიდული პროდუქტები სოფ ოზურგეთი`, `თბს ბანკი ამონაწერი`, `რს ზედნადები`
  - **`მეგაპლიუსის არქიტექტურა/`** — MegaPlus daily backup ZIPs (per-store sub-folder); pipeline auto-discovers.
  - ⚠️ **`შემოტანილი პროდუქცია\` ფოლდერი** — pipeline 0 errors-ით სრულდება, მაგრამ folder absent verified (2026-04-30 evening). შემდეგ session-ში გადასამოწმებელი — `dashboard_pipeline/imported_products.py` რომელ path-ს კითხულობს და რა ხდება როცა აკლია.
- **parent's `Financial_Analysis\`**: 5 ცოცხალი data ფოლდერი (symlink target — **NEVER touch**); top-level JSON-ები ძველად parent-ში იყო, ახლა გასუფთავდა (`_to_delete_2026-04-29\` permanent წაშლილია 2026-05-03-ზე).

ცხრილი:
- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `...\financial-dashboard`
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / project-local / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. Pipeline subprocess-ი ცალკე იქმნება, კოდის ცვლილებას ავტომატურად აიღებს. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)
- **SQL Server Express**: `localhost\SQLEXPRESS` (instance), `MEGAPLUS_<storeID>` databases — restore via `megaplus_backup._restore` from PLUS_*.bak

---

## 8. Workspace cleanup status

| რა | status |
|---|---|
| `_to_delete_2026-04-29\` (994 MB / 16,021 ფაილი parent root-დან) | ✅ permanent წაიშალა 2026-05-03 |
| OneDrive `financial-dashboard\` copy | NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ი ცოცხალი მაგრამ divergence იზრდება |
| **2026-05-03 cleanup** | 47 `_scratch_*` ფაილი + `__pycache__\` წაიშალა · CONTEXT_HANDOFF.md ისტორია არქივში · 18 obsolete archive ფაილი წაიშალა · MegaPlus discovery layout ახალი |
