# Suppliers page audit — 2026-05-08

> **Scope**: მომწოდებლების გვერდის (Suppliers.jsx) 9-ნაბიჯიანი source→formula→UI ვერიფიკაცია.
> **Owner request**: „რამდენი ხანიც და რა რესურსიც არ უნდა დაგვწირდეს" — სიზუსტის სრული შემოწმება.
> **Method**: live API → recompute from raw cache (parquet/CSV) → side-by-side compare → flag every diff.
> **Status legend**: ✅ verified · ⚠️ verified-with-nuance · 🔴 open gap (deferred) · 🟡 UI improvement

---

## Step 1 — Header KPIs

**Verified (live API, 2026-05-08 დღე):**

| KPI | UI ციფრი | წყარო | ფორმულა | სტატუსი |
|---|---:|---|---|---|
| მომწოდებლების რაოდენობა | 236 | API `suppliers[]` | 261 სულ − 25 archived − 0 non-RS | ✅ |
| პერიოდი | „ყველა პერიოდი" | API `meta.period` | label_ka or fallback | ✅ |
| სულ ვალი | 404,214.25 ₾ | API `total_debt` ჯამი | sum(debt) of realSuppliers | ✅ |
| ვალის მქონე | 212 | computed in JS | count(`abs(debt) >= 1`) | ⚠️ |

**Open findings:**

1. **🟡 KPI 4 ფორმულირება (212)** — ერთად ითვლის 178 ფირმას (გვმართებენ, debt>0) + 34 ფირმას (ჩვენ ზედმეტი მივეცით, debt<0). ბუღალტრის ვერიფიკაციისთვის ცალკე უნდა ჩანდეს — სხვადასხვა ფაქტი, სხვადასხვა მოქმედება.
   - **Defer to**: UI patch, owner approval needed → task #12.
   - **Why not now**: scope creep — სიზუსტის შემოწმებაა მისია, არა UI redesign.

2. **🔴 248,951 ₾ uxilavi orphan tax_id-ები** — 4 ფირმა ბანკით გადახდილი, მომწოდებლების გვერდზე საერთოდ არ ჩანან:

   | tax_id | თანხა | რიცხვი | რეალური კატეგორია |
   |---|---:|---:|---|
   | 400333858 ჯეო ფუდთაიმი | 84,826 ₾ | 196 | ჩვენი საკუთარი ფირმა — TBC↔BOG შიდა გადარიცხვა + საკომისიო |
   | 33001015189 | 69,375 ₾ | 33 | დვაბზუ landlord — იჯარა + 20% წყაროსთან |
   | 33001023234 | 64,650 ₾ | 31 | ოზურგეთი landlord — იჯარა |
   | 01025003711 | 30,100 ₾ | 15 | თბილისი landlord — იჯარა |

   - **Found in meta**: `bank_orphan_total_ge=164,125`, `bank_unmatched_total_ge=38,940` — მონაცემი არსებობს, UI არ აჩვენებს.
   - **„📌 RS-ის გარეშე გადახდები" სექცია** — ცარიელი unfiltered view-ზე (synthetic name pattern მხოლოდ period-filtered path-ში იქმნება, `api_contracts.py:1930`).
   - **Defer to**: Master Plan §7 sprint (მაღაზიები + ქირა/ფართი). Landlords → §7. Internal transfer → bank-internal section.
   - **Why not now**: Suppliers გვერდზე workaround = მცდარი მესიჯი (იჯარა ≠ მომწოდებელი). სწორი სახლი §7-ია.
   - **Tracked**: task #11.

---

## Step 2 — Main table columns (5-supplier spot-check)

**Verified suppliers**: საქ. დისტრიბუცია (205116088), ფუდმარტი (404460187), ჯიდიაი (406181616), heavy-returns auto-pick (ჯიდიაი), mid-size bank-only auto-pick (კუმისი XXI 204490390).

| სვეტი | წყარო | ფორმულა | 5/5 ემთხვევა? |
|---|---|---|---|
| რაოდენობა | RS.ge cache parquet | აქტიური + დასრულებული (გაუქმებული გამოკლ.) | ✅ |
| ნომინალი | RS.ge cache parquet | sum(`თანხა`) | ✅ |
| გაუქმებული | RS.ge cache parquet | sum where `სტატუსი contains "გაუქმებული"` | ✅ |
| დაბრუნება | RS.ge cache parquet | sum where `ტიპი contains "უკან დაბრუნება"` & not cancelled | ✅ |
| ბრუნვა (effective) | derived | nominal − cancelled − returned (per `waybill_amounts.py`) | ✅ |
| ბანკი (strict) | TBC+BOG cache parquet | `supplier_matching` reconciliation map | ✅ |
| ნაღდი (manual) | manual_payments.csv + journal.csv | legacy + journal active (`deleted_at` empty) | ✅ |
| სულ გადახდილი | derived | bank + manual (გარდა bilateral) | ✅ |
| ვალი | derived | effective − total_paid | ✅ |

**Verification gotchas (ჩემი სკრიპტის ბაგი, არა აპის):**

- ჟურნალის CSV-ში `status` სვეტი არ არის — `deleted_at` წაშლის დროა. პროდუქცია სწორად ფილტრავს `deleted_at == ""`. ჩემი პირველი draft სკრიპტი წაშლილ entry-ებსაც ითვლიდა, ბაგი გავასწორე.
- რაოდენობის სვეტი გაუქმებულ ხაზებს გამორიცხავს — სწორი ლოგიკაა (გაუქმებული მოვლენა არ მომხდარა).

**Open findings:**

3. **🟡 Bilateral netting transparency** — ფუდმარტი ცხრილში ჩანს:
   - ბანკი = 0 ₾, ნაღდი = 0 ₾, სულ გადახდილი = **53,774 ₾**, ვალი = 0
   - არითმეტიკულად 0+0 ≠ 53,774. რიცხვი სწორია (bilateral_netting cashback-ით ფარავს), მაგრამ მფლობელი ცხრილზე ვერ ხედავს „რატომ 53,774".
   - **Suggested fix**: `payment_scope=bilateral_netted` რიგზე ცალკე badge ან tooltip „⇄ ფაქტურა-კაშბექით ჩაითვალა". კოდი არ შეიცვლება, მხოლოდ UI hint.
   - **Defer to**: small UI tweak — owner approval pending.

---

## Step 3 — Payment scope colored dot

**Verified (live API, 261 suppliers):**

| scope | რიცხვი | წესი (backend) | UI label მუშაობს? | CSS ფერი მუშაობს? |
|---|---:|---|---|---|
| strict_bank_only | 189 | ბანკი>0, ნაღდი=0 | ✅ „ბანკით დადასტურებული" | ✅ |
| unpaid_or_unmatched | 62 | ორივე=0 | ✅ „გადაუხდელი / დაუდგენელი" | ✅ |
| manual_only | 6 | ბანკი=0, ნაღდი>0 | ✅ „მხოლოდ ნაღდით / ჟურნალით" | ✅ |
| strict_bank_plus_manual | 2 | ბანკი>0, ნაღდი>0 | ❌ ნედლი English | ❌ no rule |
| bilateral_netted | 1 (ფუდმარტი) | post-process override | ❌ ნედლი English | ❌ no rule |
| excluded_from_analysis | 1 (სევენთისევენ) | sup.excluded=true | ❌ ნედლი English | ❌ no rule |

**Logic check**: ✅ 261/261 — backend rule (`describe_supplier_payment_scope`) მონაცემს ემთხვევა, შეცდომა არ აღმოჩნდა.

**Open findings:**

4. **❌ Frontend label key mismatch + missing entries** — 4 მომწოდებელი (ჯიდიაი + 1 strict+manual, ფუდმარტი, სევენთისევენ) იღებენ ცრუ tooltip-ს და default ფერის წერტილს:
   - `Suppliers.jsx:14` ცხრილში key `strict_and_manual` ↔ backend აგზავნის `strict_bank_plus_manual` (ცხრილი ვერ პოულობს)
   - `bilateral_netted` ლეიბლი არ არის — frontend label map-ში დაამატე
   - `excluded_from_analysis` ლეიბლი არ არის
   - `components.css:3769` CSS class `sup-row-dot--strict_and_manual` (არასწორი key) — ფერი ვერ ინიჭება
   - **Fix**: ~6 ხაზი — `Suppliers.jsx` PAYMENT_SCOPE_LABEL_KA + `components.css` 3 ახალი rule
   - **Defer to**: small UI patch, owner approval pending.

---

## Step 4 — Selected supplier card + payment record form

**4a — Static consistency:** ბარათი და ცხრილის ხაზი ერთსა და იმავე `getDisplay(sup)` JS ფუნქციას იყენებს. ციფრები იდენტურია definition-ით — drift შეუძლებელია. ✅

**4b — Journal active cross-check (16 row → 8 tax_ids):**

| tax_id | active sum | deleted sum | API manual_paid | legacy implied |
|---|---:|---:|---:|---:|
| 406181616 ჯიდიაი | 56,788 | 157,388 | 370,710 | 313,922 ✅ |
| 448382633 ანთბილდი | 410 | 0 | 410 | 0 ✅ |
| 33001035254 | 398 | 0 | 398 | 0 ✅ |
| 415082760 | 380 | 0 | 380 | 0 ✅ |
| 412757994 | 345 | 0 | 345 | 0 ✅ |
| 33001051786 | 318 | 0 | 318 | 0 ✅ |
| 33001021729 | 310 | 0 | 310 | 0 ✅ |
| 404460187 ფუდმარტი | 0 | 100 | 0 | 0 ✅ |

8/8 — ყველა აქტიური journal entry სწორად აისახება API-ში.

**4c — POST/DELETE round-trip (test entry):**
- `POST /api/manual-payments {tax_id: 999999999, amount: 0.01}` → 200 OK, CSV row added ✅
- `DELETE /api/manual-payments/{id}` → 200 OK, `deleted_at` populated ✅
- Soft-delete semantics preserved (row stays in CSV, falls out of active reads).

**Open findings**: none. Step 4 fully verified.

---

## Step 5 — Archive feature (📥)

**5a — File schema:** ✅ `supplier_archive.json` — 25 entries (24 archived_at + 1 excluded_from_analysis). Schema v2 supports both flags orthogonally.

**5b — API annotation:** ✅ all 25 archive.json tax_ids correctly tagged `archived=true` in `/api/data?tab=suppliers`.

**5c — KPI subtitle vs code (CONTRADICTION):**
- Subtitle: „დაარქივებული ფირმები — მთავარ ცხრილში არ ჩანან, მაგრამ თანხები იჯამება ჩვეულებრივ."
- `supplier_archive.py` docstring (design intent): „archived — display-only flag. Hidden from main table but **KPIs/totals/concentration analytics still include it**."
- `Suppliers.jsx:220-228` (actual code): `totalRealDebt` and `suppliersWithDebt` use **only `realSuppliers`** — **archived excluded.**
- Current archived sums: `total_debt=0.68 ₾`, `total_paid=136,317.80 ₾`, `total_effective=136,318.48 ₾`. Owner archived suppliers near zero debt, so KPI impact is currently negligible. **Bug becomes visible if owner archives a supplier with non-zero debt.**

**5d — Live POST/restore round-trip:**
- `supplier_archive.load()` direct call: shows new entry IMMEDIATELY after POST ✓
- `/api/data?tab=suppliers` after POST: still shows `archived=False` — **bug** ✗
- Cause: `server.py:361-365` returns pre-built static artifact (`STATIC_RESPONSE_TABS`) when no dynamic input present, bypassing `_annotate_archive_flag` altogether.
- Owner-facing impact: archive flag updates in static artifact only on pipeline regen (~60 min) or service restart. Frontend `archiveOverrides` local state masks the issue per-session, but page reload before regen → archived suppliers reappear in main table.

**Open findings:**

5. **🔴 Static-artifact bypass for archive flag** — `server.py` static-fallback path (line 361-365) skips `_annotate_archive_flag`. Fix options:
   - (A) wrap `load_artifact("suppliers")` to re-run `_annotate_archive_flag` post-load (cheap, ~10 lines)
   - (B) exclude `suppliers` tab from STATIC_RESPONSE_TABS (slower /api/data?tab=suppliers, may impact other call sites)
   - **Defer**: requires owner approval — affects /api/data hot path.

6. **🔴 KPI subtitle / code contradiction** — fix decision required:
   - (A) Match design intent: include archived in `totalRealDebt`/`suppliersWithDebt` (frontend code change, 4 lines)
   - (B) Match code: rewrite subtitle „ცხრილიდან მოხსნილი + KPI-დან გამოკლდება"
   - Per docstring + 2026-05-08 ღამე CONTEXT_HANDOFF („📥 Archive: მხოლოდ ცხრილიდან მალავს, ციფრები KPI-ში ჩანს"), design intent = (A).
   - **Defer**: small UI patch, owner approval pending.

---

## Step 6 — Excluded-from-analysis (🚫) + bilateral_netting

**6A — Excluded (🚫) მექანიზმი:** ✅

სევენთისევენი (405623204) live test:
- `excluded_from_analysis: true` ✅
- `payment_scope: 'excluded_from_analysis'` ✅
- `total_debt: 0` (was 50,526 ₾, forced to 0) ✅
- `exclusion_reason` populated ✅
- Belt-and-suspenders: frontend `getDisplay` (Suppliers.jsx:174) ALSO forces debt→0 when excluded.

**6B — Bilateral netting (ფუდმარტი) ✅ — math matches CONTEXT_HANDOFF exactly:**

| component | API value | source | ✓ |
|---|---:|---|---|
| our seller invoices (we → foodmart) | 508,573.38 ₾ (46) | `our_seller_invoices[]` filter customer_tax_id | ✅ |
| their supplier invoices (foodmart → us) | 163,082.25 ₾ (60) | `supplier_invoices[404460187]` | ✅ |
| TBC cashback total | 335,202.36 ₾ | `tbc_foodmart_cashback.total_ge` | ✅ |
| **net = our − their − cashback** | **10,288.77 ₾** | computed | ✅ matches CONTEXT_HANDOFF "10,289 ₾ მისაცემი" |
| net ≥ 0 → debt = 0 | 0.00 ₾ | per `bilateral_netting.py:92` | ✅ |
| netted_paid = total_effective | 53,774.50 ₾ | total_effective override | ✅ |
| payment_scope | `bilateral_netted` | post-process tag | ✅ |

Bilateral logic is correct and matches the documented business rule end-to-end.

**Open findings:**

7. **🟡 `_annotate_archive_flag` over-tags excluded-only suppliers** — `api_contracts.py:2046` uses `tid in archived_map` (key presence) instead of `entry.get("archived_at")` (proper archive flag). სევენთისევენი has ONLY `excluded_at` in archive.json, no `archived_at`, but API still returns `archived=true`. Result: excluded-only supplier appears in 📦 archive list instead of main table with 🚫 badge. Two-flag orthogonality (per CONTEXT_HANDOFF design) silently breaks.
   - **Fix**: 1-line change — `sup["archived"] = bool(tid and archived_map.get(tid, {}).get("archived_at"))`.
   - **Defer**: confirm with owner that this is the intended display behavior before changing.

---

## Step 7 — RS-without-payments rows („📌 RS-ის გარეშე გადახდები")

**Verified — section is dead in all 3 view modes:**

| view | total suppliers | non-RS rows |
|---|---:|---:|
| Unfiltered | 261 | 0 |
| Period 2023..today | 261 | 0 |
| Period last 30 days | 261 | 0 |

**Why dead:** frontend regex `/არა.?\s*RS\s+ზედნადებ/i` matches the synthetic stub name set in `api_contracts.py:1930` ONLY when no name hint resolves. All 4 documented orphans have name hints from bank purpose strings (ჯეო ფუდთაიმი, იჯარა, etc.) → real names assigned → regex misses them.

**Reconciliation with Step 1 finding #2:** the 248,951 ₾ orphan total is hidden in unfiltered view (not in cache.suppliers at all) and in period-filtered view would land in main table with real names (tested above shows still 0 — likely because period filter doesn't merge synthetic recompute under current data state).

**No new finding.** Section behaviour is consistent with the documented orphan gap (task #11). Section becomes useful only after task #11 design change (move orphans to dedicated sections in §7 sprint).

---

## Step 7b — Cache refresh schedule (interim finding)

Verified directly during step 7:

- `Pipeline` (data.json rebuild from cache) — schedule 30 min, last 28 min ago, 11 runs today, no errors. ✅
- `Bank refresh` (cache parquet rewrite from rs.ge / TBC / BOG APIs) — `runs_total: 0` (no auto-schedule), last via `.last_refresh.json` 6.5 hours ago. ⚠️
- Means: any rs.ge waybill / bank movement created after 12:15 today is invisible to the dashboard until owner manually triggers refresh or restarts the service. Pipeline rebuild on stale cache produces stale answers.

**Open finding:**

8. **🔴 No automatic schedule for cache refresh from external APIs.** Pipeline regenerates data.json on cron (30 min) but the underlying cache parquets aren't auto-refreshed. `bank_refresh` endpoint exists but is `runs_total: 0`. Today's RS+TBC+BOG cache last refreshed 12:15 Tbilisi, ~6.5 h ago. Currently mitigated by service restart cadence; long-term needs APScheduler trigger for `bank_refresh` (e.g. every 60 min) parallel to the pipeline scheduler.
   - **Defer**: scheduler change, owner approval pending.

---

## Step 8 — Excel download matches UI

**Field-by-field consistency:** ✅ same `getDisplay()` function feeds Excel and table cells; values guaranteed identical.

**Column mapping:**

| ცხრილი (UI) | Excel |
|---|---|
| # (index) | (not in Excel — correct, ordinal only) |
| ორგანიზაცია | ორგანიზაცია |
| რაოდ. | რაოდენობა |
| ბრუნვა | რეალური ჯამი |
| — | ნომინალური (Excel-only, useful for accountant) |
| ბანკი | strict ბანკით გადახდა |
| ნაღდი | ნაღდით გადახდა |
| სულ გადახდ. | სულ გადახდილი |
| ვალი | დავალიანება |
| (color dot) | გადახდის scope (text) |

**Open findings:**

9. **🟡 Excel includes archived suppliers not on screen** — Excel = filteredSuppliers (261); main table = realSuppliers (236). Owner downloads thinking they get „what I see" but actually gets 25 archived rows too. Button title „ცხრილის Excel-ად ჩამოტვირთვა" implies table-equivalent.
   - **Fix options**: (A) export only `realSuppliers` (match table), (B) split into 2 sheets (Active / Archived), (C) keep as-is and rename button „სრული სია — Excel".
   - **Defer**: small UI decision, owner approval pending.

10. **🟡 Excluded supplier shows misleading „სულ გადახდილი" in Excel** — სევენთისევენი row: ბანკი=0, ნაღდი=0, but „სულ გადახდილი=50,526 ₾" because `getDisplay` overrides `paid = total_effective` for excluded suppliers (to force debt=0). On-screen this is masked by colored dot + tooltip; in Excel it looks like the amount was actually paid. Accountant reviewing the Excel would be confused.
   - **Fix**: when exporting an excluded row, set „სულ გადახდილი=0" + „გადახდის scope='excluded_from_analysis'" already in scope column tells the truth. Or annotate the row with reason.
   - **Defer**: small UI patch, owner approval pending.

---

## Step 9 — Supplier concentration widget (HHI + Top-N)

**Math 100% verified — recompute matches API exactly:**

| metric | API | recompute | diff |
|---|---:|---:|---:|
| total_suppliers | 261 | 261 | 0 |
| total_spend_ge | 5,520,842 ₾ | 5,520,842 ₾ | 0 |
| HHI index | 571.6 | 571.6 | 0 |
| Top-5 share | 43.13% | 43.13% | 0 |
| Top-10 share | 55.16% | 55.16% | 0 |
| Top-20 share | 68.52% | 68.52% | 0 |

HHI = 571 → 🟡 moderate band (500–1500), correct label.

**Inclusion scope:** widget includes ALL 261 suppliers (archived + excluded too) for HHI / Top-N — analytics-view rather than main-table view. archived (25) sum = 136K, excluded (1) sum = 50K, both contribute to denominator.

**Top-3 negotiation candidates:**
| # | supplier | share | leverage | est. savings |
|---|---|---:|---:|---:|
| 1 | კოკა-კოლა გურია | 7.94% | 67 | 17,253 ₾ |
| 2 | პარტნიორი | 1.44% | 62 | 558 ₾ |
| 3 | ჯიდიაი | **17.34%** (largest!) | 60 | **0 ₾** |

**Open finding:**

11. **🟡 ჯიდიაი = 17% portfolio share but „savings=0" puts it #3 not #1.** Algorithm sorts by `leverage_score × savings × spend`; ჯიდიაი's `estimated_annual_savings_ge=0` likely means category benchmark missing (Master Plan §4.1 area). This may be a SILENT GAP — the biggest concentration risk has zero negotiation guidance because we lack benchmark data for cigarette / fast-moving consumer category. Worth confirming with owner whether this is by-design or missing-data.

12. **🟡 Widget total „5.52M ₾" vs main-table sum „5.33M ₾"** — 187K ₾ (3.4%) discrepancy because widget includes archived + excluded. Not labelled to owner. Recommend: caption „სულ ხარჯი (archived/excluded ჩათვლით)" or split.

---

## Final summary — 9 steps · 12 open findings

**Verified accurate ✅:**
- Header KPIs (count, period, total debt, with-debt count) — math correct
- Main table columns (5-supplier spot-check) — all values trace to raw cache
- Payment scope rules — 261/261 suppliers correctly classified by backend
- Selected card + payment record form — round-trip POST/DELETE works
- Excluded mechanism (🚫) — total_debt forced to 0 correctly
- Bilateral netting (foodmart) — math matches owner's 10,289 ₾ misacemi exactly
- Concentration widget (HHI 571, Top-5/10/20) — math 100%

**Open findings (deferred — not fixed in this audit):**

| # | finding | severity | task | სად მოგვარდება |
|---|---|---|---|---|
| 1 | KPI 4 (212) mixes 178 owe-us + 34 we-overpaid | 🟡 | #12 | UI patch, owner approval |
| 2 | 248,951 ₾ orphan tax_ids invisible (3 landlords + 1 own) | 🔴 | #11 | Master Plan §7 sprint |
| 3 | Bilateral netting needs row badge/tooltip | 🟡 | — | small UI tweak |
| 4 | 4 payment_scope keys missing in frontend label map | 🟡 | #13 | 6-line JS+CSS fix |
| 5 | Static artifact bypasses archive flag refresh | 🔴 | #14 | server.py fix |
| 6 | KPI subtitle „თანხები იჯამება" contradicts code | 🔴 | #15 | 4-line frontend fix |
| 7 | _annotate_archive_flag uses key presence not archived_at | 🟡 | #16 | 1-line backend fix |
| 8 | No auto-schedule for cache parquet refresh from APIs | 🔴 | #17 | APScheduler job |
| 9 | Excel includes archived + excluded rows (label mismatch) | 🟡 | #18 | UI decision |
| 10 | Excluded supplier shows misleading „სულ გადახდილი" in Excel | 🟡 | #18 | UI fix |
| 11 | ჯიდიაი (17% portfolio) savings=0 → ranked #3 not #1 | 🟡 | #19 | benchmark data gap |
| 12 | Widget total 5.52M ₾ vs main table 5.33M ₾ unlabelled | 🟡 | #19 | caption clarification |

**Severity legend**: 🔴 = data correctness or owner-facing inconsistency · 🟡 = UI / cosmetic / minor.

**Audit method note**: ყველა ციფრი დადასტურდა live API-სა და raw cache (parquet/CSV) parallel რეცხვით; სკრიპტები `_scratch_verify_suppliers_step{1..9}.py` უტოვებენ reproducible evidence-ს. ცარიელი slot ერთი არ დარჩა.
