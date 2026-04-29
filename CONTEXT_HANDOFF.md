# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-04-29 — გრძელი წაკითხვა საჭირო **არ არის**. ეს ფაილი ცოცხალი state-ია. Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. Evidence → `HANDOFF.md` + `HANDOFF_ARCHIVE/`.
>
> **ახალი ჩატის read order**: ეს ფაილი → `docs/MASTER_PLAN.md` → `AGENTS.md`.
>
> 🚨 **ბოლო session დასრულდა language regression-ის მე-4 cross-session occurrence-ით** („მაგრამ" Latin-ად იწერებოდა). AGENTS.md Correction Escalation-ის მიხედვით → ეს handoff = restart-ი. ახალ ჩატში პირველი ნაბიჯი: წაიკითხე ეს ფაილი + AGENTS.md "მომხმარებელთან საუბრის ენა" სექცია სრულად, ვიდრე პირველ tool-ს გამოიყენებ.

---

## 1. ახლა სად ვართ

- **ბოლო session-ის ცვლილება** (`4deed3a`, 2026-04-29 commit landed): **docs/governance consolidation დასრულდა** — 7-ფაილოვანი governance → 4-ფაილოვანი + 1 archive. 5 critical contradictions გადაიჭრა. დეტალები ქვემოთ §6.
- **Active section** (Master Plan): §5 გაყიდვები — **CAL mini-sprint** გაჩერებულია Step 2-ის ბოლოზე.
- **CAL Step 1 (Scope agree)**: ✅ ifqli first, **3-button per-store toggle** (ჯამი / ოზურგეთი / დვაბზუ; თბილისი closed 2024-06 → 2026 retail window-ში 0 data), only-matched + partial-coverage warning banner
- **CAL Step 2 (Data inventory)**: ✅ pipeline-ში per-day aggregation **არ არსებობს** (only `by_month` / `by_category_by_month`). Source per-row datetime ცხადია (`დრო` სვეტი), ifqli matched products უკვე გამოთვლილია `supplier_profitability`-ში. **საჭიროა ახალი aggregation**: `supplier.profitability.daily_breakdown[]` sparse (per-day × per-store)
- **CAL Step 3-6**: spot-check + implement + verify + user review — ⏳ ვიდრე user-ის ცხადი „გადავიდეთ"

**ბოლო commit-ები** (`origin/main`-ზე 43 ahead, push არ გაკეთებულა):
```
4deed3a  docs(governance): consolidate to 4-file structure — MASTER_PLAN as single roadmap
f75dfd0  docs(handoff): Section 1 (Tbilisi) closure + stale-CONTEXT corrections
666edd3  feat(imported-products): add Tbilisi (closed store) to object_mapping
971c304  docs(handoff): flag ground-truth ELIZI mismatch
3a9df66  docs(handoff): pin a318a91 + 3d3ac07 SHAs
3d3ac07  feat(ai): data_quality_guard tool
a318a91  fix(imported-products): destination resolver + 3-tier safety net
020a555  fix(imported-products): cancelled-status filter
```

---

## 2. 🚨 ახალი finding — duplicate `Financial_Analysis` ფოლდერი

**Status: UNRESOLVED** — user-ის გადაწყვეტილებას ელოდება ვიდრე ცვლილება გაკეთდება.

ცხრილში ცხადი — ორი ფოლდერი არსებობს თითქმის ერთი და იგივე content-ით:

| ფოლდერი | ზომა | სტატუსი |
|---|---|---|
| `...\AI აგენტი\Financial_Analysis\` (workspace, გარეთ) | ~150 MB | 🔴 **orphan** — pipeline არ კითხულობს, არ აქვს ახალი ფაილები (`product_aliases.json`, `cash_outflow_journal.csv` აკლია) |
| `...\financial-dashboard\Financial_Analysis\` (project, შიგნით) | ~175 MB | 🟢 **canonical** — pipeline იყენებს, git tracked (18 ფაილი + .gitignored data dirs) |

**მტკიცებულება რომ project-inside არის ცოცხალი:**

`generate_dashboard_data.py:1367`:
```python
script_dir = os.path.dirname(os.path.abspath(__file__))  # = financial-dashboard/
```
ყველა loader (`config_loaders.py`, `retail_sales.py`, etc.) იყენებს `os.path.join(script_dir, "Financial_Analysis", ...)`.

**ცხადი bug**: AGENTS.md + CONTEXT_HANDOFF.md წერდნენ:
> Source canonical: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\Financial_Analysis`

**ეს არასწორია.** რეალური canonical = `...\financial-dashboard\Financial_Analysis`.

**წარმოშობა**: `666edd3` commit-ში წერია „project + workspace mirror" — Claude წინა session-ებში ცდილობდა ორივე ფოლდერი ცოცხლად ეჭიროს, მაგრამ რეალურად მხოლოდ JSON config-ი იყო manual-ად სინქი. Excel/CSV data არასოდეს არ სინქდებოდა.

### 3 ვარიანტი — user-მა უნდა აირჩიოს

| # | ვარიანტი | რისკი |
|---|---|---|
| **ა** (რეკომენდაცია) | Workspace-ი წაიშალოს — orphan-ი 150 MB ცარიელი ადგილი | 23 MB განსხვავება იმპორტი folder-ში (workspace 81 MB / project 104 MB) — ცხადი არ არის რა ცადო. spot-check საჭიროა ვიდრე delete |
| ბ | Workspace-ი დარჩეს როგორც „import staging" RS.ge-დან | manual sync-ის შრომა, drift-ი კვლავ წარმოიშვება |
| გ | Symbolic link (Windows junction) project-inside-ზე | OneDrive sync-ი junction-ებთან არასტაბილურია |

**პირველი ნაბიჯი ვიდრე ცვლილება**: spot-check-ი 23 MB განსხვავებაზე (`du`-ის output project-inside `შემოტანილი პროდუქცია/` 104 MB vs workspace 81 MB) — ცხადია workspace-ში ცარიელი დუპლიკატია თუ ცხადი წყარო-ფაილი.

**bug fix scope** (გადაწყვეტილების შემდეგ): AGENTS.md proof gate path + ამ ფაილის §6 path განახლდება.

---

## 3. Verified facts (cross-check ვიდრე action)

| მეტრიკა | მნიშვნელობა |
|---|---|
| pytest | 2,227/2,230 green (3 pre-existing phase4b3 doc baseline failures) |
| `SYSTEM_PROMPT_KA` | 1,163 ხაზი |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 15 |
| `data.json` | 110.88 MB, 26 sections, 259 supplier row, **4 store buckets**: ოზურგეთი 2,375K (146) / დვაბზუ 1,968K (123) / თბილისი 871K (129, closed) / გაუნაწილებელი −15K (148, returns) |
| Pipeline coverage | **42.0%** (2,182,576 / 5,200,734 ₾). ⚠️ წინა docs-ი 69.7%-ს წერდა — wrong, baseline regen verified 42% |
| `retail_sales` window | **3 თვე** (2026-01..03) — 96,464 line / 319K ₾ revenue / 50K ₾ profit / 15.84% margin |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |
| VAT cumulative gap | **+90K ₾ net / +107K ₾ gross** (pipeline). Audit ground-truth: **742K ₾**. Delta = ~652K within pipeline coverage gaps |

---

## 4. ღია სამუშაო (priority order)

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| **🚨 NEW** | duplicate `Financial_Analysis` ფოლდერი — user არჩევს 3 ვარიანტიდან (§2) | 5-30 წთ | LOW-MED | docs-ი არასწორ canonical path-ს წერდა; bug fix simple, მაგრამ user-მა strategy უნდა აირჩიოს |
| **🚨 0c** | dashboard „ანალიზდა" KPI ცრუობს partial-coverage სცენარში | 1 sprint | **HIGH** | ELIZI ground-truth: cost 297,685 / sales 313,456 / margin **+5.3%**. Dashboard: −2.13%. 4 ვარიანტი: (A) alias 35→80%; (B) UI banner; (C) ცალკე KPI „matched-only margin"; (D) ground-truth Excel pipeline-ში. user-ი არჩევს |
| **🚧 CAL** | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა | ~1 session | LOW | scope locked, data inventory done; საჭიროა new daily aggregation `supplier_profitability`-ში |
| 🧹 0a | `dashboard_pipeline/constants.py:468-502` + `684-718` — `detect_object` duplicate definition | 5 წთ | LOW | dead code line 468; live = line 684 |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) | 1-2 session | LOW | (a) `vulture` dead-code; (b) `jsonschema` config-ფაილებზე; (c) golden snapshot data.json-ისთვის; (d) reconcile_suppliers.py გავრცელება; (e) Pandera RS.ge CSV reader |
| 1 | Supplier Profitability Sprint C — alias UI mutation workflow | ~1 session | LOW | browser-ში „✓ დაადასტურე ალიასი" → POST → `product_aliases.json` write |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` | ~1 session | LOW | TOOL_SCHEMAS 29 → 30 |

---

## 5. წინა session-ის carry-forward findings

**ELIZI ground-truth** (2026-04-28): user-მა გააზიარა Excel `Financial_Analysis/ოზურგეთი კომპანიების გაყიდვები/2022,2026-02.xls`. რეალური cost 297,685 / sales 313,456 / **profit +15,771 / margin +5.3%**. Dashboard აჩვენებს: cost 322K / sold 61.7K / **profit −1,314 / margin −2.13%**. — Item §0c-ში.

**🚨 ენობრივი regression — RESTART TRIGGERED**: filler-words / partial Georgian tokens — **4 session-ის occurrence** (2026-04-27 + 04-28 + 04-29 morning + 04-29 evening). AGENTS.md Correction Escalation-ის მიხედვით ეს handoff = restart. ახალ ჩატში პირველი ნაბიჯი: წაიკითხე ეს ფაილი + AGENTS.md "მომხმარებელთან საუბრის ენა" სრულად.

---

## 6. Governance consolidation — `4deed3a` (2026-04-29)

ცხადი 4-ფაილოვანი სტრუქტურა (იყო 7 ფაილი + parallel duplicates):

| ფაილი | ხაზი | რას ემსახურება |
|---|---|---|
| `CONTEXT_HANDOFF.md` (ეს) | ~110 | ცოცხალი state — current section + open work + verified facts |
| `docs/MASTER_PLAN.md` | 232 | ერთადერთი 18-სექციის roadmap (A→F sequence, 6-step sprint cycle, data inventory, VAT cross-cutting) |
| `AGENTS.md` | 89 | Session rules — consolidated 3-layer proof gate, scoped GitNexus rule (shared functions only, JSON/docs/constants EXEMPT), cross-session language regression flag |
| `HANDOFF.md` | 81 | Commit SHA → archive evidence index, Master Plan §-ის ნომერი binding |
| `CLAUDE.md` (project) | 114 | GitNexus tools (override note + auto-block + governance pointer table) |

**Archived**: `PHASE_STATUS_MATRIX.md` (Phase 0A...5 paradigm) → `HANDOFF_ARCHIVE/PHASE_STATUS_MATRIX_v2.1_superseded_2026-04-29.md`

**5 critical contradictions resolved**:
1. CLAUDE.md strict GitNexus rule vs AGENTS.md scoped relaxation → CLAUDE.md ზევით override note
2. PHASE_STATUS_MATRIX Phase 0A...5 vs MASTER_PLAN §1...18 → PHASE archived
3. Proof gates duplicate CLAUDE.md+AGENTS.md → only AGENTS.md
4. MASTER_PLAN ცხრილი vs §5.1 numbering → table reordered (1=ზედნადები)
5. ✅ ნაწილობრივ ambiguity → ⏳ ნაწილობრივ + ახსნა

---

## 7. Canonical paths & services (do-not-touch)

⚠️ **Source ფაილები — bug აღმოჩენილი §2-ში. ვიდრე user არჩევს — ცხრილ-ცხრილ:**
- **რეალური canonical (pipeline იყენებს)**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard\Financial_Analysis`
- **ცარიელი orphan (docs შეცდომით ცხადყოფს)**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\Financial_Analysis` — 🔴 NOT used by pipeline

ცხრილი:
- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `...\financial-dashboard`
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / project-local / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)
