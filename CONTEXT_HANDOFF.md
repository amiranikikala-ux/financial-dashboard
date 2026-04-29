# CONTEXT HANDOFF — ცოცხალი სტატუსი

> **განახლდა**: 2026-04-29 — გრძელი წაკითხვა საჭირო **არ არის**. ეს ფაილი ცოცხალი state-ია. Roadmap → `docs/MASTER_PLAN.md`. წესები → `AGENTS.md`. Evidence → `HANDOFF.md` + `HANDOFF_ARCHIVE/`.
>
> **ახალი ჩატის read order**: ეს ფაილი → `docs/MASTER_PLAN.md` → `AGENTS.md`.

---

## 1. ახლა სად ვართ

- **Active section**: §5 გაყიდვები (Master Plan) — **CAL mini-sprint** (calendar heatmap supplier modal-ში)
- **CAL Step 1 (Scope agree)**: ✅ scope confirmed — ifqli first, **3-button per-store toggle** (ჯამი / ოზურგეთი / დვაბზუ; თბილისი closed 2024-06 → 2026 retail window-ში 0 data), only-matched + partial-coverage warning banner
- **CAL Step 2 (Data inventory)**: ✅ pipeline-ში per-day aggregation **არ არსებობს** (only `by_month` / `by_category_by_month`). Source per-row datetime ცხადია (`დრო` სვეტი), ifqli matched products უკვე გამოთვლილია `supplier_profitability`-ში. **საჭიროა ახალი aggregation**: `supplier.profitability.daily_breakdown[]` sparse (per-day × per-store)
- **CAL Step 3-6**: spot-check + implement + verify + user review — ⏳ ვიდრე user-ის ცხადი „გადავიდეთ"
- **ბოლო session-ის ცვლილება (2026-04-29)**: docs/governance consolidation **დასრულდა** — 4-ფაილიანი სტრუქტურა (`MASTER_PLAN.md` + `CONTEXT_HANDOFF.md` + `AGENTS.md` + `HANDOFF.md`); `PHASE_STATUS_MATRIX.md` → archive (`HANDOFF_ARCHIVE/PHASE_STATUS_MATRIX_v2.1_superseded_2026-04-29.md`); `CLAUDE.md` GitNexus block-ის ზევით override note (AGENTS.md scope-ი ვრცელდება, არა CLAUDE.md-ის strict ცხადი). Commit-ად ჯერ არ შენახულა — user-ი გადაწყვეტს როდის

**ბოლო commit-ები** (`origin/main`):
```
f75dfd0  docs(handoff): Section 1 closure + stale-CONTEXT corrections
666edd3  feat(imported-products): add Tbilisi (closed store) to object_mapping
971c304  docs(handoff): flag ground-truth ELIZI mismatch (dashboard ანალიზდა KPI ცრუობს)
3a9df66  docs(handoff): pin a318a91 + 3d3ac07 SHAs
3d3ac07  feat(ai): data_quality_guard tool
a318a91  fix(imported-products): destination resolver + 3-tier safety net
020a555  fix(imported-products): cancelled-status filter
```

---

## 2. Verified facts (cross-check ვიდრე action)

| მეტრიკა | მნიშვნელობა |
|---|---|
| pytest | 2,227/2,230 green (3 pre-existing phase4b3 doc baseline failures) |
| `SYSTEM_PROMPT_KA` | 1,163 ხაზი |
| Tool surface | 29 (incl. `data_quality_guard`) |
| Dashboard tabs | 15 |
| `data.json` | 110.88 MB, 26 sections, 259 supplier row, **4 store buckets**: ოზურგეთი 2,375K (146 supplier) / დვაბზუ 1,968K (123) / თბილისი 871K (129, closed) / გაუნაწილებელი −15K (148, returns) |
| Pipeline coverage | **42.0%** (cost_matched 2,182,576 / cost_imported 5,200,734 ₾). ⚠️ პრევიოუს doc claimed 69.7% — wrong, baseline regen verified 42% before AND after Tbilisi mapping |
| `retail_sales` window | **3 თვე** (2026-01..03) — 96,464 line / 319K ₾ revenue / 50K ₾ profit / 15.84% margin |
| `data.db` (SQLite mirror) | `rs-dashboard/public/data.db` — suppliers/aging/pnl/retail_sales_category/imported_*/iban_taxid_conflicts/meta_kv. **MCP `sqlite` tool — ad-hoc data check-ისთვის Python subprocess-ზე სწრაფია** |
| MCP servers | gitnexus · playwright · filesystem · github · sqlite · sequential-thinking · memory · brave-search · time · fetch · context7 |
| VAT cumulative gap | **+90K ₾ net / +107K ₾ gross** (pipeline independently). Audit ground-truth: **742K ₾**. Delta = ~652K within pipeline coverage gaps (missing MAX/BOG/TBC for 11 months) |
| IBAN audit | 1 cross-ID conflict — `GE80TB1560000006156111` shared by 3 ფიზ.პირები (surfaced in `meta.iban_taxid_conflicts`) |
| Suppliers concentration | HHI=558 (🟡 ზომიერი) · Top-5=42.2% · Top-10=54.2% |

---

## 3. ღია სამუშაო (priority order)

| # | task | size | risk | რატომ |
|---|---|---|---|---|
| 🚧 CAL | calendar heatmap supplier modal-ში — Step 3 (spot-check) ღიაა | ~1 session | LOW | scope locked, data inventory done; საჭიროა new daily aggregation `supplier_profitability`-ში |
| 🚨 0c | dashboard „ანალიზდა" KPI ცრუობს partial-coverage სცენარში | 1 sprint | **HIGH** | ELIZI ground-truth Excel: cost 297,685 / sales 313,456 / margin **+5.3%**. Dashboard: −2.13%. `(PP)*` deprecated variant-ები matched 35.5%-ში დომინირებენ + loss sample ქმნიან. 4 ვარიანტი: (A) alias 35→80%; (B) UI banner; (C) ცალკე KPI „matched-only margin"; (D) ground-truth Excel pipeline-ში — user-ი არჩევს |
| 🧹 0a | `dashboard_pipeline/constants.py:468-502` + `684-718` — `detect_object` duplicate definition | 5 წთ | LOW | dead code line 468; live = line 684 |
| 🛡 0b | Safety net follow-ups (Pandera ანალიზის შემდეგ) | 1-2 session | LOW | (a) `vulture` dead-code; (b) `jsonschema` config-ფაილებზე; (c) golden snapshot data.json-ისთვის; (d) reconcile_suppliers.py-ის გავრცელება retail_sales/monthly_pnl-ზე; (e) Pandera RS.ge CSV reader-ისთვის |
| 1 | Supplier Profitability Sprint C — alias UI mutation workflow | ~1 session | LOW | browser-ში „✓ დაადასტურე ალიასი" → POST → `product_aliases.json` write |
| 2 | AI tool wrapper `analyze_supplier_profitability(tax_id)` | ~1 session | LOW | TOOL_SCHEMAS 29 → 30 |

**📌 §0c-ის გადაწყვეტამდე** — partial-coverage მომწოდებლების KPI-ს ციფრი მცდარი ბიზნეს ისტორიას ჰყვება (ELIZI loss-ში არ არის რეალურად).

---

## 4. წინა session-ის ღია finding (carry forward)

User-მა გააზიარა ground-truth Excel `Financial_Analysis/ოზურგეთი კომპანიების გაყიდვები/2022,2026-02.xls`. ELIZI ოზურგეთი რეალური: cost 297,685 / sales 313,456 / **profit +15,771 / margin +5.3%**. Dashboard აჩვენებს: cost 322K / sold 61.7K / **profit −1,314 / margin −2.13%**. Item §0c-ში.

**🚨 ენობრივი regression flag**: filler-words / partial Georgian tokens — 3 session-ის ოკურენცია (2026-04-27 + 04-28 + 04-29). მე-4 cross-session occurrence = სასწრაფო restart (AGENTS.md Correction Escalation).

---

## 5. Canonical paths & services (do-not-touch)

- **Workspace root**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- **Project**: `...\financial-dashboard`
- **Source ფაილები**: `...\Financial_Analysis` (canonical მისამართი proof gate-ისთვის)
- **Python interpreter**: `...\AI აგენტი\venv\Scripts\python.exe` (parent venv only — NEVER `.venv` / project-local / system Python)
- **Backend**: Windows Service `FinancialDashboardBackend` (NSSM, auto-start + auto-restart, `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1`)
- **Service control**: `Restart-Service FinancialDashboardBackend` (admin/UAC) · `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit}`
- **⚠️ Service-restart-for-new-code**: prompt module-import time-ზე იტვირთება. Prompt change-ის შემდეგ — `Restart-Service`. In-process AI test = `_scratch_dogfood_*.py` pattern (no service)
- **Backend interpreter verification**: `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` (NOT `Get-Process`)
