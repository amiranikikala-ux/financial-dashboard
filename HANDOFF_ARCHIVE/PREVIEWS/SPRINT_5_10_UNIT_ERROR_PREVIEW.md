# Sprint 5.10 — VAT Gap Unit Error Discovery (evidence only, no code change)

> **თარიღი:** 2026-04-24
> **სტატუსი:** 🚨 **CRITICAL FINDING — production numbers are wrong. Code fix pending.**
> **სესია:** 1/1 — evidence gathered, NO production code touched. Fix deferred to next session.
> **Evidence files:** `_scratch_sprint5_10_*.py` + `.json` (4 files, uncommitted)

---

## 🎯 ერთი წინადადებით

CONTEXT_HANDOFF-ის "906K ₾ real gap" ციფრი **მცდარია unit-ზე** (gross pipeline vs net declared). აუდიტის 742K-ს ჩვენი pipeline რეპროდუცირებს, მაგრამ UI / AI / Excel-ზე ნაჩვენებ 906K-ში **+702K unit inflation** დგას და **−652K coverage deficit** ირევა. ორივე რაოდენობრივად გამოცნობილია, მაგრამ fix-ი **HIGH impact** არის (7 ფაილი, 4 ტესტი) — გადატანილია შემდეგ სესიაზე.

---

## 📊 სამი მთავარი აღმოჩენა

### 1. "98.5% TBC / 94% BOG match" — hardcoded string, არა computed

**File:** `vat_reconciliation_export.py:68-69`
**პრობლემა:** ეს სტრინგი Excel export-ში წერია როგორც cross-validation evidence, მაგრამ რეალურად არაა გამოთვლილი. CONTEXT_HANDOFF.md-მ ამ claim-ს ენდობოდა.
**რეალური რიცხვები** (pipeline vs audit-ის own BOG/TBC columns, 37 თვე):

| მეტრიკა | Claim | Actual |
|---|---|---|
| TBC match ratio | 98.5% | **95.7%** (+4.3% inflation in pipeline when compared naive) |
| BOG match ratio | 94% | **88.7%** (+12.7% inflation) |

### 2. Pipeline vs audit ratio = **1.1581 ± 0.001** (34 თვე) — არ არის bug, არის unit + commission

**File:** `_scratch_sprint5_10_bog_ratio_probe.py` output
**Math:** `1.1581 ≈ 1.18 × (1 − 0.019)` → **VAT-gross ÷ VAT-net × (1 − BOG_commission)**
**ვერიფიკაცია** (5 sample months):

| period | pipe_bog | audit_bog × 1.18 | implied commission |
|---|---|---|---|
| 2023-06 | 17,702 | 18,042 | 1.88% |
| 2024-04 | 23,248 | 23,746 | 2.10% |
| 2024-08 | 82,481 | 84,016 | 1.83% |
| 2025-08 | 95,113 | 96,795 | 1.74% |
| 2025-12 | 54,215 | 55,166 | 1.72% |

**დასკვნა:** audit-ის ყველა ციფრი **NET of VAT** (gross ÷ 1.18), ხოლო pipeline **GROSS** (bank deposit after commission). ორიდან არცერთი არ არის bug — ორივე სწორია თავის სისტემაში. **პრობლემა არის pipeline-ის gap calc:** audit-ის declared_ge-ს (net) აკლებს pipeline-ის total_real_ge-ს (gross). **Unit error.**

### 3. 906K-ის component decomposition

```
906K (current "gap" headline)
 = 742K audit's real gap (net)           ← TRUE, aligns with audit
 + 703K unit error (declared × 0.18)     ← UNITS BUG, inflates artificially
 − 652K pipeline measurement deficit     ← COVERAGE GAP (see §4)
 − 113K rounding / other                  ← residual
```

**Unit-corrected reconciliation:**

| Method | Gap |
|---|---|
| **Current code (gross − net):** | **+906,283 ₾** ❌ wrong |
| Method A (net terms, pipeline ÷ 1.18 vs declared): | +90,368 ₾ |
| Method B (gross terms, pipeline vs declared × 1.18): | +106,635 ₾ |
| **Audit's own gap (net):** | **+742,217 ₾** |

### 4. რატომ ვხედავთ მხოლოდ 90K-ს, როცა აუდიტი 742K-ს ამბობს?

**"652K measurement deficit" = pipeline coverage gaps:**

- **2022-10/11/12 + 2023-01..05** → `status: insufficient_data` (Sprint 5.9 added) — **missing MAX POS Excel files**. pipeline `max_pos_ge = 0`. Audit has figures.
- **2023-Q1 (Jan/Feb/Mar)** → `pipe_bog = 0` but audit has ~34,370 ₾. **Missing BOG bank statements** for 3 months.
- **2023-08 → 2024-03 (8 consecutive months)** → `pipe_tbc` is −27% to −81% below `audit_tbc`. Pipeline captures much less TBC than audit. **Cumulative TBC shortage ≈ 43K net ≈ 51K gross.** Root cause: unknown (possibly missing bank statement rows, terminal-ID matching gap, or audit used different source).

ყოველ აუდიტის თვეზე სადაც ჩვენ სრული data გვაქვს (2024-08, 2025-08, 2025-12 — ცხრილი §2-ში), pipeline-ის gross ≈ audit-ის net × 1.18 **0.3% დონეზე**. ანუ როცა data სრულია, **pipeline ზუსტად რეპროდუცირებს აუდიტის რიცხვებს**.

---

## 🚨 Blast radius (Variant 2 "proper fix"-ისთვის)

Production consumers of `gap_vs_declared_ge` / `total_gap_ge` (grep-ით დადასტურებული):

| file | role | change needed |
|---|---|---|
| `dashboard_pipeline/vat_reconciliation.py:576,605,632,655,691` | definition | add `gap_net_ge` + `gap_gross_ge`, deprecate old field |
| `dashboard_pipeline/vat_reconciliation_export.py:36,114,131,132,146,157` | Excel export (auditor) | update column, aggregates, summary |
| `dashboard_pipeline/ai/vat_tools.py:53` | AI tool returning gap | return net gap as primary |
| `dashboard_pipeline/ai/tools.py:238,2199` | AI tool prompts | update description to clarify net |
| `rs-dashboard/src/VATAudit.jsx:99,401,561` | Frontend 🧾 VAT tab | display net (primary) + gross (secondary) |
| `generate_dashboard_data.py:1422` | pipeline regen console | switch to net |
| `tests/test_vat_reconciliation.py:463` | `assert gap > 100000` | update to net-based threshold |
| `tests/test_vat_reconciliation_export.py:44,67,86,136` | fixture assertions | update to new field names |
| `SYSTEM_PROMPT_KA` (VAT section) | AI tone + math documentation | `dashboard_pipeline/ai/prompts.py` — clarify declared=net, total_real=gross |

**Count:** 6 production files + 2 test files + prompt. AI live dog-food required after.

---

## 🔄 Fix options (next session decision)

### Option A — **Full proper fix** (2-3 sessions)
1. Add `gap_net_ge` + `gap_gross_ge` to `by_month`; deprecate `gap_vs_declared_ge`.
2. Compute `summary.total_gap_net_ge` + `summary.total_gap_gross_ge`.
3. Update Excel export to show both with clear labels.
4. Update AI tools to return net as primary (gross as annotation).
5. Update frontend to render net prominently, gross in subtotal.
6. Update SYSTEM_PROMPT_KA VAT section: "დეკლარირებული ბრუნვა = net of VAT; pipeline-ის total_real = gross; gap არის net basis".
7. Update 4 test assertions + add 3-5 new tests pinning unit correctness.
8. Live dog-food on Sonnet 4.6 (3 scenarios: "რამდენია gap?", "declared vs real", "რატომ შეიცვალა ციფრი?").
9. Update CONTEXT_HANDOFF.md: "906K withdrawn → net gap 742K (audit-matched, data gaps for 11 months prevent independent reproduction of 652K)".

**Risk:** MED (non-trivial but bounded). **Outcome:** ყველა surface (UI/AI/Excel) ერთ unit-ში, auditor-ready.

### Option B — **Minimal cosmetic fix** (1 session)
- `gap_vs_declared_ge` ველში ვინარჩუნებთ `gross − net` ფორმულას (unchanged), მაგრამ ვამატებთ `gap_net_ge` + `gap_gross_ge` ველებს როგორც **supplemental**. UI / AI გადააქვთ new field-ზე. Tests updated but NOT breaking.

**Risk:** LOW. **Outcome:** გაორმაგებული ველები (confusion risk). Not audit-ready unless all 3 surfaces migrate.

### Option C — **Defer all code fixes, document in user docs only**
- CONTEXT_HANDOFF.md flag the issue, leave production numbers as-is, add user-facing warning in 🧾 VAT tab UI ("ციფრი Mixed-unit-ია, იხ. handoff").

**Risk:** NONE (no production change). **Outcome:** auditor still sees wrong number. Not recommended if audit defense is active.

---

## 📁 Evidence files (uncommitted, current session)

| file | purpose |
|---|---|
| `_scratch_sprint5_10_tbc_bog_crossmatch.py` + `.json` | per-month TBC/BOG diff table, coverage gap identification |
| `_scratch_sprint5_10_bog_ratio_probe.py` | 1.1581 ratio distribution (stdev=0.001 over 34 months) |
| `_scratch_sprint5_10_audit_excel_probe.py` | audit Excel raw column inspection, commission hypothesis test |
| `_scratch_sprint5_10_unit_reconciliation.py` | final 906K component decomposition |

**Recommendation:** keep these files as evidence until fix lands. Then move to `_ARCHIVE/`.

---

## 🔑 Key pre-known rules (still apply)

- `AUDIT_XLSX` path: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\გაანგარიშება შპს ჯეო ფუდთაიმი.xlsx` (workspace root, 2 levels above project).
- data.json at `rs-dashboard/public/data.json` (138 MB, last regen 2026-04-23).
- 2,068 pytest green as of Sprint 5.9. This sprint did NOT run pytest (no code changes).
- `insufficient_data` status (Sprint 5.9) correctly covers 8 months where MAX POS files are missing — do NOT change that status logic, it is fine.

---

## ⚠️ URGENT user-facing claim to withdraw

**CONTEXT_HANDOFF.md line 4:**
> "real gap **906K ₾**"

**Line 114:**
> "real gap is **906K ₾** (not 1.6M as pre-Sprint-5.5; not audit's 742K). Pipeline is cross-validated against RS.ge POS terminal export (98.5% TBC / 94% BOG match). Ready for voluntary-disclosure conversation OR audit defense — user decides."

**Replace with:**
> "real gap (net, audit-matched): **742K ₾**. Pipeline independently verifies 90K of this directly; **remaining ~652K is within pipeline coverage gaps** (missing MAX POS files for 5 months, BOG bank statements for Q1 2023, TBC shortage 2023-08..2024-03). Pipeline per-month numbers match audit within 0.3% where data is complete. **The previously reported 98.5/94 cross-match figures were hardcoded strings, not live computations** — withdrawn. Audit-defense claim of '906K real gap' was based on a unit error (gross pipeline − net declared) inflating the gap by +702K. Fix pending (Sprint 5.11)."

---

## 🚀 Next session startup

1. Read this PREVIEW + CONTEXT_HANDOFF (updated).
2. Pick fix option (A recommended if audit is live).
3. `gitnexus_impact compute_vat_reconciliation upstream` after re-running `npx gitnexus analyze`.
4. Fix in this order: define new fields → update tests → update Excel export → update AI tools → update frontend → prompt section → live dog-food.
5. Target scope: **one sprint (5.11) = code fix only**. If AI prompts + dog-food overrun, split to Sprint 5.12.
