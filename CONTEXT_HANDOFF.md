# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-05-03 (cleanup session — workspace tidied) — წინა session-ის ბოლო რეალური სამუშაო commit-ები: `e5ee7ea` (wrong_store category) + `6d45dd7` (PWA soft update banner). ორივე end-to-end verified, origin/main-ზე.
>
> Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. სრული ისტორია (აპრილი 18 → მაისი 2) → `HANDOFF_ARCHIVE/CONTEXT_HISTORY_2026-04_2026-05-02.md`.

---

## 1. ბოლო სამუშაო session-ი (2026-05-02 evening)

**`e5ee7ea` feat(waybill-reconciliation): wrong-store category** — ზედნადებების შედარებაში ცალკე გამოჩნდა „🔄 არასწორი მაღაზია" ჯგუფი — შემთხვევები, როცა MegaPlus-ში ზედნადები არასწორ მაღაზიაში მიიღეს (`only_other`) ან ორივე მაღაზიაში დააფიქსირეს (`duplicate`, Lactalis-ის pattern). 4-წლიან 3,978 active rs.ge-ზე: 28 wrong_store / ₾13,237. Spot-check-ით 26 false-positive class დაიჭირა (დვაბზუ vs დვაბზა/დვაბზეე dest-spelling) ვიდრე user-ი ნახავდა — fix `ACTIVE_STORE_KEYWORDS["1329"]` `"დვაბზუ"` → prefix `"დვაბზ"`. Tests 39/39. data.json ~100 MB.

**`6d45dd7` feat(pwa): soft update banner** — საიტი მუშაობის შუაში თვითონ აღარ რეფრეშდება. ახლა მარცხნივ-ქვემოთ მწვანე ბანერი „განახლება" ღილაკით — user თვითონ წყვეტს როდის გადახვიდეს ახალ ვერსიაზე (Gmail / GitHub-ის pattern). `<UpdateBanner />` 53 ხაზი, sw.js-ის `skipWaiting()` მოშორდა, `rs-update-available` / `rs-apply-update` CustomEvent-ის მეშვეობით. **One-time activation cost**: ძველი sw.js-ით გახსნილი tab-ებს ერთხელ ავტო-რეფრეში მოუვათ, მერე ბანერი ცოცხლდება.

---

## 2. შემდეგი session-ის OPEN list (priority order)

1. **🟢 MegaPlus cleanup workflow გაგრძელდება** — user აქტიურად იყენებს ტაბს, როგორც pattern-ი ცოცხლდება: „MegaPlus-ში ერთი batch ჩავასწორებ, ხვალ PLUS_*.zip backup ჩამოვწერ, pipeline ცვლილებას აიღებს, რიგი ცხრილიდან გაქრება". Wrong_store რიგებიც იგივე გზით — როცა user-ი address-ს ჩაასწორებს. **არაპროაქტიულად კონკრეტულ რიგებზე ხელი არ გავიწიოთ**; user თვითონ გამოიტანს. როცა გამოიტანს — D&L / Partnyori / Lactalis-ისებური line-by-line drill-down (GET vs rs.ge xls diff, plain-ქართული explanation).
2. **🟢 Browser smoke-check** — `6d45dd7` GitHub-ზეა მაგრამ user-ს ჯერ არ გადაუხედავს. პირველი F5-ი ერთხელ ავტო-რეფრეშს გამოიწვევს (ძველი sw.js cache-ში); მერე ბანერი ცოცხლდება. პრობლემის შემთხვევაში: dist bundle hash უნდა იყოს `index-hfmLnxUb.js`.
3. **🟢 Carryover (არა-blocking)**:
   - RS_CODES-based product matching (189,015 rs.ge↔Megaplus mappings MegaPlus DB-ში — name-fuzzy-ის ჩანაცვლება exact JOIN-ით; ~1 sprint).
   - Auto-sync OneDrive↔C:\ — drift-ი მეორდება; post-commit/post-merge hook ან scheduled task.
   - `retail_sales_top_products` SQLite export bug (`dashboard_pipeline/export_sqlite.py:111` reads `top_products`, schema-ში `top_products_by_revenue` / `_by_profit`).
   - ოზურგეთი DB 234 orders dated 2009 (0.026% / 661 ₾, optional date filter).
   - rs.ge automation deferred — user-მა manual download აირჩია.
4. **🟢 Category-anomalies UI follow-ups (deferred)** — deep-link / severity scoring / Excel export — **მხოლოდ user-ის მოთხოვნით**.

---

## 3. Verified facts (cross-check ვიდრე action)

| მაჩვენებელი | მნიშვნელობა |
|---|---|
| pytest (key suites) | **39/39** waybill_reconciliation + 50/50 supplier_profitability + retail_sales_revenue_formula |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 16 (waybill_reconciliation tab gained "🔄 არასწორი მაღაზია" group) |
| `data.json` | ~100 MB (post-wrong_store-category, 2026-05-02 evening) |
| Branch state | clean — `e5ee7ea` + `6d45dd7` pushed to origin/main |
| MegaPlus DB integration | LIVE — 53 tables / 282 suppliers / 720K active orders / 2024-03 → 2026-04 |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |

---

## 4. Active open work

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| **🟡 0a CODE COMPLETE — smoke-test pending** | **Sprint C alias UI** browser smoke-test — endpoint LIVE post-restart, 8 tests green, just need user-side click. Steps: (1) `_vite-dev.bat` → http://127.0.0.1:5173, (2) მომწოდებლები ტაბი → ვასაძის პური → modal → ალიასის კანდიდატები, (3) „✓ დადასტურდი ალიასი" → toast + product_aliases.json write + pipeline rerun. | ~30 წთ | LOW |
| **🚨 0c — DECISION READY** | **MAX vendor-tag file integration** (ELIZI / შრომა / etc. KPI gaps) — file landed at `Financial_Analysis/მეგა პლუს/კომპანიების გაყიდვა მოგება.xls` (45 KB, 116 suppliers, **დვაბზუ store only**). 3 paths: **(A)** read-only side-by-side (~1 session, low risk); **(B)** soft replacement when MAX matches by tax_id (~2 sessions, medium); **(C)** file loader only (~30 წთ, low value alone). User picks A/B/C. ოზურგეთი analog file ⏳. | A=1 / B=2 / C=0.5 sessions | **HIGH** |
| **🚧 CAL** | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა. `supplier.profitability.daily_breakdown[]` sparse aggregation საჭიროა. | ~1 session | LOW |
| **🆕 0f Sprint D candidate** | **Cross-source revenue gap** — MAX vendor-tag vs RS waybill (ვასაძე@დვაბზუ Q1 2026: pipeline 3,888 ₾ vs MAX 11,477 ₾ ground-truth, 7,589 ₾ gap). Sprint C alias UI არ წყვეტს. Investigation paths: (1) MAX-ის per-supplier sales report direct export, (2) MAX-vendor-tag column retail_sales pipeline-ში, (3) KPI banner caveat. | 2-3 investigation + 1-2 impl | MEDIUM |
| 1 | Supplier Profitability Sprint C UI extensions — render `ambiguous_preview` (46 invisible candidates) + bulk-confirm + DELETE endpoint | ~1 session | LOW |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` (TOOL_SCHEMAS 29 → 30) | ~1 session | LOW |
| **🧹 1-week-pending** | `_to_delete_2026-04-29\` permanent delete (863 MB staging-ში 5+ დღე; dashboard ცოცხალი) | 1 წთ | LOW |
| **🧹 1-week-pending** | OneDrive `financial-dashboard\` copy retire (NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ში divergence-ი იზრდება) | ~30-45 წთ mini-sprint | MEDIUM |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) — vulture dead-code, jsonschema config, golden snapshot, reconcile_suppliers spread, Pandera RS.ge CSV reader | 1-2 sessions | LOW |

---

## 5. Canonical paths & services (do-not-touch)

⚠️ **Source ფაილების canonical path — symlink სტრუქტურა (2026-04-29 verified):**
- **pipeline view**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis\`
  - 15 JSON config (real, canonical) — `cash_outflow_journal.csv`, `product_aliases.json`, etc.
  - 5 symlink target ფოლდერი → `..\Financial_Analysis\` (parent):
    - `ბოგ ბანკი ამონაწერი`, `გაყიდული პროდუქტები სოფ დვაბზუ`, `გაყიდული პროდუქტები სოფ ოზურგეთი`, `თბს ბანკი ამონაწერი`, `რს ზედნადები`
  - ⚠️ **`შემოტანილი პროდუქცია\` ფოლდერი** — pipeline 0 errors-ით სრულდება, მაგრამ folder absent verified (2026-04-30 evening). შემდეგ session-ში გადასამოწმებელი — `dashboard_pipeline/imported_products.py` რომელ path-ს კითხულობს და რა ხდება როცა აკლია.
- **parent's `Financial_Analysis\`**: 5 ცოცხალი data ფოლდერი (symlink target — **NEVER touch**); top-level JSON-ები + ძველი `შემოტანილი პროდუქცია\` `_to_delete_2026-04-29\02_financial_analysis_orphan\`-ში გადატანილი.

ცხრილი:
- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `...\financial-dashboard`
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / project-local / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)

---

## 6. Workspace cleanup status

| რა | status |
|---|---|
| `_to_delete_2026-04-29\` (863 MB / 16,021 ფაილი parent root-დან) | STAGED 2026-04-29; permanent delete pending (5+ დღე ცოცხალი dashboard-ით) |
| OneDrive `financial-dashboard\` copy | NSSM service mirror მხოლოდ C:\\-ზე; OneDrive working-tree-ი ცოცხალი მაგრამ divergence იზრდება |
| **2026-05-03 cleanup** | 47 `_scratch_*` ფაილი + `__pycache__\` წაიშალა (gitignored, no code reference); CONTEXT_HANDOFF.md ისტორია არქივში გადავიდა |
