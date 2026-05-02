# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-03 (cleanup + MegaPlus layout migration). 2 commits ჩავარდა local main-ზე ამ session-ში: `61ffe93` (workspace cleanup) + `e8dc73f` (MegaPlus discovery — new layout). ორივე end-to-end verified, data.json fresh (106 MB, 2026-05-03 02:36).
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. სრული ისტორია (აპრილი 18 → მაისი 2) → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`.

---

## 1. ბოლო სამუშაო session-ი (2026-05-03 ღამე)

**🧹 `61ffe93` chore(cleanup): trim CONTEXT_HANDOFF + remove obsolete archives + scratch artifacts**

- CONTEXT_HANDOFF.md — 110 KB / 576 ხაზი → **12 KB / 88 ხაზი**; სრული ისტორია არქივში გადავიდა (`HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`).
- HANDOFF_ARCHIVE — 18 ფაილი წაიშალა: 3 superseded planning doc (AI_ADVISOR_ROADMAP v1.0, AI_GENIUS_PARTNER_PLAN v2.1, PHASE_STATUS_MATRIX v2.1) + 15 pre-MASTER_PLAN preview (PHASE 0/1/2/3/4A/3B era). HANDOFF.md-ის pointer block განახლდა.
- 47 `_scratch_*.py / .json` root-ში წაიშალა — 8 tracked გიტში, 39 untracked (gitignored). __pycache__ წაიშალა.
- **`_to_delete_2026-04-29\` ფოლდერი parent-ში permanent წაიშალა** (994 MB / 16,021 ფაილი) — dashboard ცოცხალი დარჩა, HTTP 200, disk free 259 GB.

**🟢 `e8dc73f` feat(megaplus): discover backup folders under მეგაპლიუსის არქიტექტურა layout**

- User-მა PLUS_*.zip backup-ები ძველი `მეგა პლუს backup*` sibling ფოლდერებიდან ახალ `Financial_Analysis/მეგაპლიუსის არქიტექტურა/<store>/` სტრუქტურაში გადააწყო (per store: დვაბზუ + ოზურგეთი).
- Pipeline-ი ძველ ფოლდერს ეძებდა → 3 successive run-ში „watch folder-ი არ არის, ნაბიჯი გამოტოვდა" → MegaPlus data ცარიელი/stale data.json-ში.
- **Fix**: `megaplus_backup._discover_watch_folders` ახლა ორივე layout-ს პოულობს (legacy glob + ახალი arch parent + PLUS_*.zip presence check). `generate_dashboard_data.py` inline glob შეიცვალა helper-ის import-ით (single source of truth).
- 5+5 ZIP backup აპრილი 28 → მაისი 2 (`PLUS_1329_*.zip` დვაბზუ, `PLUS_1301_*.zip` ოზურგეთი). უახლესი ორივე restore-ი → SQL Server Express → `_megaplus_live.json` ფოლდერთან.
- Pipeline run end-to-end: 18.6 წთ / 0 errors / 0 warnings / 30 API artifacts. data.json 106 MB, fresh.
- **Live numbers**: Store 1329 (დვაბზუ) 282 supplier / 2,229,889 ₾ revenue / **12.34% margin**; Store 1301 (ოზურგეთი) 308 supplier / 2,631,008 ₾ revenue / **12.17% margin**. ჯამი 4.86 მლნ ₾ revenue / 595K ₾ profit / 8,456 პროდუქტი / 37 თვე (2024-03 → 2026-04).
- **ხვალინდელი backup**: PLUS_*_MEGA_20260503.zip ჩავარდნისთანავე pipeline ავტომატურად აიღებს (no manual step).

---

## 2. ჯერ-ჯერობით წინა session-ი (2026-05-02 evening)

**`e5ee7ea` feat(waybill-reconciliation): wrong-store category** — ზედნადებების შედარებაში ცალკე გამოჩნდა „🔄 არასწორი მაღაზია" ჯგუფი (4-წლიან 3,978 active rs.ge-ზე: 28 wrong_store / ₾13,237). Spot-check-ით 26 false-positive class დაიჭირა — fix `ACTIVE_STORE_KEYWORDS["1329"]` `"დვაბზუ"` → prefix `"დვაბზ"`.

**`6d45dd7` feat(pwa): soft update banner** — საიტი მუშაობის შუაში თვითონ აღარ რეფრეშდება. ახლა მარცხნივ-ქვემოთ მწვანე ბანერი „განახლება" ღილაკით. **One-time activation cost**: ძველი sw.js-ით გახსნილი tab-ებს ერთხელ ავტო-რეფრეში მოუვათ, მერე ბანერი ცოცხლდება.

---

## 3. შემდეგი session-ის OPEN list (priority order)

1. **🟢 MegaPlus cleanup workflow გაგრძელდება** — user აქტიურად იყენებს ტაბს, pattern-ი ცოცხლდება: „MegaPlus-ში ერთი batch ჩავასწორებ, ხვალ PLUS_*.zip backup ჩამოვწერ, pipeline ცვლილებას აიღებს, რიგი ცხრილიდან გაქრება". **არაპროაქტიულად კონკრეტულ რიგებზე ხელი არ გავიწიოთ**; user თვითონ გამოიტანს. როცა გამოიტანს — D&L / Partnyori / Lactalis-ისებური line-by-line drill-down (GET vs rs.ge xls diff, plain-ქართული explanation).
2. **🟢 Browser smoke-check pending** — `6d45dd7` (PWA banner) GitHub-ზეა მაგრამ user-ს ჯერ არ გადაუხედავს. პირველი F5-ი ერთხელ ავტო-რეფრეშს გამოიწვევს (ძველი sw.js cache-ში); მერე ბანერი ცოცხლდება. პრობლემის შემთხვევაში: dist bundle hash უნდა იყოს `index-hfmLnxUb.js`.
3. **🟢 ცვლილებების push origin/main-ზე** — `61ffe93` + `e8dc73f` ჯერ origin-ზე არ აიტვირთა (local main 2 ahead). user-მა „push" როცა მოითხოვოს — ერთად აიგზავნება.
4. **🟢 Carryover (არა-blocking)**:
   - RS_CODES-based product matching (189,015 rs.ge↔Megaplus mappings MegaPlus DB-ში — name-fuzzy-ის ჩანაცვლება exact JOIN-ით; ~1 sprint).
   - Auto-sync OneDrive↔C:\ — drift-ი მეორდება; post-commit/post-merge hook ან scheduled task.
   - `retail_sales_top_products` SQLite export bug (`dashboard_pipeline/export_sqlite.py:111` reads `top_products`, schema-ში `top_products_by_revenue` / `_by_profit`).
   - ოზურგეთი DB 234 orders dated 2009 (0.026% / 661 ₾, optional date filter).
   - rs.ge automation deferred — user-მა manual download აირჩია.
5. **🟢 Category-anomalies UI follow-ups (deferred)** — deep-link / severity scoring / Excel export — **მხოლოდ user-ის მოთხოვნით**.

---

## 4. Verified facts (cross-check ვიდრე action)

| მაჩვენებელი | მნიშვნელობა |
|---|---|
| pytest (key suites) | **39/39** waybill_reconciliation + 50/50 supplier_profitability + retail_sales_revenue_formula |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 16 (waybill_reconciliation tab-ში "🔄 არასწორი მაღაზია" group) |
| `data.json` | **106 MB** (post-MegaPlus-rediscovery, 2026-05-03 02:36) |
| Local branch | `main` 2 ahead of `origin/main` (`61ffe93` + `e8dc73f` — push pending) |
| MegaPlus DB integration | LIVE — 53 tables / 282+308 suppliers across 2 stores / 720K active orders / 2024-03 → 2026-04 |
| MegaPlus watch folder layout | `Financial_Analysis/მეგაპლიუსის არქიტექტურა/{დვაბზუ,ოზურგეთი}/` (legacy `მეგა პლუს backup*` glob still supported) |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |

---

## 5. Active open work

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

## 6. Canonical paths & services (do-not-touch)

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

## 7. Workspace cleanup status

| რა | status |
|---|---|
| `_to_delete_2026-04-29\` (994 MB / 16,021 ფაილი parent root-დან) | ✅ permanent წაიშალა 2026-05-03 |
| OneDrive `financial-dashboard\` copy | NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ი ცოცხალი მაგრამ divergence იზრდება |
| **2026-05-03 cleanup** | 47 `_scratch_*` ფაილი + `__pycache__\` წაიშალა · CONTEXT_HANDOFF.md ისტორია არქივში · 18 obsolete archive ფაილი წაიშალა · MegaPlus discovery layout ახალი |
