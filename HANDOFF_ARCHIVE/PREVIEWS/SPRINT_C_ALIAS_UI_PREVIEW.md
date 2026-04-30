# Sprint C — Supplier Coverage 90% Floor (Alias Confirmation UI)

**Status**: PREVIEW · NO CODE CHANGE
**Date**: 2026-04-30
**Target sprint**: §2 Suppliers (MASTER_PLAN.md) — Profitability Sprint C
**Handoff parent**: `CONTEXT_HANDOFF.md` row 137 (item `🚨 0a NEW`)

---

## TL;DR

Pipeline-ი უკვე გამოაქვს `name_candidate` payload-ს ყოველი unmatched/ambiguous პროდუქტისთვის, სადაც MAX-ში ერთი retail row ემთხვევა სახელით. ამ payload-ს რენდერავს `SupplierModal.jsx`-ც (💡 ბადჯი, „MAX-ის შესაძლო შესაბამისობა" ღია ფანჯარა). რჩება მხოლოდ **საბოლოო ერთი ხიდი**: button „დადასტურდი ალიასი" → POST `/api/aliases/confirm` → `Financial_Analysis/product_aliases.json` atomic append → toast „დადასტურდა, მომდევნო pipeline run-ი ანალიზში დაამატებს". Backend validation უკვე სრულია (`_validate_aliases.py` 138 ხაზი — `confirmed_by="user"` enforce, retail key existence, dedup). Sprint = ~1 session, additive code (zero modification of profitability/match logic).

**Reality check**: Sprint C-ით **ვერ ავიყვანთ ყველა 70 მომწოდებელს ≥90%-მდე**. მხოლოდ 21 მომწოდებელს აქვს რომელიმე candidate (top-10 preview-ში), მათ შორის ვასაძის პური 9 candidate-ით — ერთი session-ში 21-მდე mover. დანარჩენი 28 below-90 მომწოდებლისთვის (ELIZI, ინტერნეიშნლ, გეოდისტრიბუცია — tobacco renumbering) candidate არ არსებობს — მათი 90%-ისკენ მისვლას ცალკე path სჭირდება (Sprint D — `unmatched_preview` cap-ის გაზრდა / eANGARISH cross-ref / ground-truth Excel).

---

## Inventory — რა წავიკითხე, რა ვიპოვე

### Backend — pipeline payload (უკვე არის)

| ფაილი | ხაზი | რას შეიცავს |
|---|---|---|
| `dashboard_pipeline/supplier_profitability.py` | 321-344 | `_name_candidate_for(imported_name, name_index)` — თუ ერთი retail row-ის normalized name ემთხვევა, returns `{retail_barcode, retail_product_code, retail_name, retail_category}` |
| `dashboard_pipeline/supplier_profitability.py` | 396-417 | unmatched/ambiguous loop — ყოველ row-ს ერთვება `"name_candidate": candidate` |
| `dashboard_pipeline/supplier_profitability.py` | 624-625 | output: `unmatched_preview` (top 10 priciest) + `ambiguous_preview` (top 10) |
| `dashboard_pipeline/_validate_aliases.py` | 138 ხაზი სრული | `load_aliases_file()` + `validate_aliases(parsed, retail_known_keys)` + `load_and_validate(path, keys)`. Validation rules: (a) `confirmed_by == "user"`, (b) `imported_code` და `retail_code_or_barcode` non-empty, (c) `retail_code_or_barcode` ცოცხალ retail index-ში, (d) `imported_code` no-duplicate. Pipeline ცარიელ/გატეხილ alias-ებზე არ ეშვება — silently drop + log warning |
| `generate_dashboard_data.py` | 257, 1665-1670 | `_load_aliases(aliases_path, retail_known_keys)` → `safe_aliases` → `build_supplier_profitability(data, aliases=safe_aliases)`. ე.ი. სრული პიპელაინი უკვე იცის რომ alias-ფაილი წაიკითხოს |
| `Financial_Analysis/product_aliases.json` | 14 ხაზი (`aliases: []`) | ცარიელია, schema fixed (version 1, comment_ka, schema, aliases array) |

### Frontend — UI payload renderer (უკვე არის)

| ფაილი | ხაზი | რას შეიცავს |
|---|---|---|
| `rs-dashboard/src/SupplierModal.jsx` | 172-231 | `UnmatchedProductRow` — შეიცავს `candidate = product?.name_candidate \|\| null` ცვლადს, რენდერავს 💡 ტეგს და „MAX-ის შესაძლო შესაბამისობა" sub-card-ს |
| `rs-dashboard/src/SupplierModal.jsx` | 652-670 | `unmatched_preview.map(...)` სექცია სათაურით „ალიასის კანდიდატები". ბოლოში static note: **„ალიასების დადასტურება — დაამატე ხელით `Financial_Analysis/product_aliases.json`-ში და გაუშვი pipeline-ი ხელახლა (ბრაუზერის ალიასის ფლოუ მომდევნო ეტაპზე ჩაშენდება)."** ← ეს note Sprint C-ის TODO-ს ცხადად აფიქსირებს |

### Server — endpoint patterns (უკვე არის)

| ფაილი | ხაზი | რას შეიცავს |
|---|---|---|
| `server.py` | 670-715 | `@app.post("/api/vat-reconciliation/cash-outflow")` — Body validation pattern + HTTPException 400 + atomic CSV append. იგივე pattern alias confirm-ისთვის სრულდება |
| `server.py` | 422 | `@app.post("/api/refresh")` — pipeline regen trigger (timeout 10 min, ცალკე ტასკია §0d) |
| `server.py` | 41 | `_PUBLIC_PATHS` — ახალი endpoint default mode (auth ცალკე გადასაწყვეტია) |

### data.json spot-check (2026-04-30 14:06 baseline)

| მომწოდებელი | სტატუსი | cov% | imp ₾ | unmatched ₾ | candidates (unmatched+ambiguous) |
|---|---|---|---|---|---|
| შპს **ვასაძის პური** | verified | 82.4 | 19,764 | 3,470 | **9** ← ყველაზე საინტერესო quick win |
| შპს ლავაზა | unverified | 1.1 | 6,249 | 6,179 | 4 |
| შპს თისო | unverified | 2.8 | 3,148 | 3,059 | 4 |
| შპს შრომა-2023 | partial | 57.6 | 25,318 | 10,740 | 4 |
| შპს ჯიბე | partial | 30.2 | 5,869 | 4,098 | 3 |
| შპს **ELIZI ჯგუფი** | unverified | 0.8 | 79,634 | 78,967 | **0** ← Sprint C-ის რადარს მიღმა |
| შპს ინტერნეიშნლ | protected | 44.2 | 19,848 | 11,069 | **0** |
| შპს გეოდისტრიბუცია | unverified | 5.0 | 11,511 | 10,939 | **0** |

ვასაძე spot-check candidate (1-ლი unmatched): `imp_code=2006`, `imp_name="შეფუთული აგურა რუხი"` → MAX `product_code=2247377`, `barcode=4860103230058`, `category="პური შავი აგური"`. ერთი click → 158.7 ₾ matched-ში გადადის, კიდევ 8 ambiguous candidate ეროდება — total 9 confirm = სავარაუდო coverage 82% → 95%+.

### Global candidate inventory

- 70 მომწოდებელი (28 verified / 21 partial / 4 protected / 17 unverified)
- 49 below 90% coverage
- 471 candidate-row-ი visible preview-ში (347 unmatched + 124 ambiguous)
- **66 row-ი** გვაქვს `name_candidate` payload-ით (20 unmatched + 46 ambiguous) — Sprint C-ის სრული addressable scope
- 21 supplier (below-90)-ს აქვს ერთი მაინც candidate visible top-10-ში
- **28 supplier (below-90)-ს არ აქვს ვერც ერთი candidate** → Sprint D-ის სამუშაო

---

## Risks / Pitfalls

| # | რისკი | რას ვაკეთებ |
|---|---|---|
| 1 | **`unmatched_preview` cap = 10** (top by cost) — UI-ს მხოლოდ 10 ცალს აჩვენებს. თუ მომწოდებელს 200 unmatched აქვს, რეალური candidate-ები (11-ე, 12-ე...) აღარ ჩანს. | Sprint C უძლებს ამ cap-ს როგორც data-driven scope-ს. Sprint D-ის candidate (cap → ALL with-candidate, თვითნებური zero-padding-ის გარეშე) ცალკე item-ად მოვამზადებ |
| 2 | **JSON file race condition** — pipeline ერთდროულად კითხულობს, frontend კი append-ს ცდილობს. | Atomic write pattern: `path.with_suffix(".tmp")` write → `os.replace(tmp, target)` (POSIX/Windows atomic). Lock არ სჭირდება — pipeline read-only / endpoint write-only |
| 3 | **Validation duplicate** — endpoint-მა უნდა შეამოწმოს `confirmed_by="user"`, `retail_code_or_barcode` exists, no duplicate `imported_code`. Pipeline-ს ცალკე validation აქვს `_validate_aliases.py`-ში. | Endpoint-ი იგივე helper-ს იყენებს (`load_and_validate(path, retail_known_keys)`) NEW alias hypothetical insertion-ის შემდეგ — single source of truth |
| 4 | **Retail index საჭიროა confirm-დროს** — endpoint-ს უნდა გადაამოწმოს რომ `retail_code_or_barcode` რეალურ retail row-ს ემთხვევა. `data.json` ცალკე loader-ი რომ შევქმნა → 65 MB read-ი ყოველ POST-ზე — slow. | `retail_known_keys` cache server-ზე module-import time / first-request time-ზე. ან უფრო მარტივი — confirm payload უკვე იცის MAX product_code/barcode-ს (frontend-ი იღებს pipeline-დან როგორც candidate). Endpoint trust: სანამ frontend-ი payload-ს pipeline-მ შემოგვთავაზა, validate-ის გადატანა სტატიკურ check-ზე (frontend რომ candidate.retail_product_code-ს არ შეცვლის) დასაშვებია |
| 5 | **Pipeline rerun timing** — alias confirm-ი effective გახდება მხოლოდ შემდეგ pipeline run-ზე. user ხედავს რომ click გააკეთა, მაგრამ მნიშვნელობები immediate-ად არ იცვლება. | UI feedback ცხადი: „დადასტურდა — მომდევნო pipeline run-ი ანალიზში დაამატებს (~5 წუთში automatic ან ხელით „განაახლე")". confusion-ის გარეშე explicit message |
| 6 | **Confirm-ის reverse / „თქვი არა"** — user-მა შეცდომით click გააკეთა. | v1-ში — manual JSON edit-ი (file path UI-ში ცხადია). v2 — `DELETE /api/aliases/{imported_code}`. Out-of-scope Sprint C-დან, მაგრამ note-ი UI-ში |
| 7 | **Auth / CSRF** — ეს endpoint state-ს ცვლის (file write), მაგრამ data.json-ს უშუალოდ არ აკეთებს — შემდეგი pipeline run-ი მისგან წერს. Public/internal? | რჩება როგორც სხვა endpoint-ები (`/api/refresh`, `/api/vat-reconciliation/cash-outflow`) — `_PUBLIC_PATHS`-ს მიღმა, რეგულარული flow. CSRF არ სჭირდება (LAN-only) |

---

## Files expected to change

| ფაილი | ცვლილების ტიპი | მიახლოებითი diff |
|---|---|---|
| `server.py` | NEW endpoint `@app.post("/api/aliases/confirm")` | +60-80 ხაზი |
| `dashboard_pipeline/_validate_aliases.py` | NEW helper `append_alias_atomic(path, entry, retail_known_keys)` | +30-40 ხაზი |
| `rs-dashboard/src/SupplierModal.jsx` | UnmatchedProductRow → ცვლილება (button + click handler + state); section note replacement | +50-70 ხაზი, -10 ხაზი (static note) |
| `rs-dashboard/src/SupplierModal.css` (or scoped CSS) | new button styles + confirmed-badge styles | +20-30 ხაზი |
| `tests/test_validate_aliases.py` | NEW tests for `append_alias_atomic` (success, duplicate, invalid retail key, JSON corruption recovery) | +80-120 ხაზი |
| `tests/test_server_alias_endpoint.py` | NEW integration test (FastAPI TestClient) — POST happy path, validation 400s, idempotency | +100-150 ხაზი |

**Untouched** (zero modification):
- `dashboard_pipeline/supplier_profitability.py` — name_candidate emission უცვლელი
- `dashboard_pipeline/supplier_matching.py` — match logic უცვლელი
- `generate_dashboard_data.py` — alias loading უცვლელი
- `Financial_Analysis/product_aliases.json` schema — append-only

---

## Test plan (7 tests, mirror existing pattern)

`tests/test_validate_aliases.py` (existing) + new tests:

1. `test_append_alias_atomic_appends_valid_entry` — ცარიელი ფაილზე append → 1 entry, `confirmed_by="user"`, `confirmed_at` ISO timestamp
2. `test_append_alias_rejects_unknown_retail_key` — `retail_code_or_barcode="XXXNOTREAL"` → ValueError, ფაილი უცვლელი
3. `test_append_alias_rejects_duplicate_imported_code` — იგივე `imported_code` 2-ჯერ → second call raises, ფაილი 1 entry-ით
4. `test_append_alias_atomic_recovers_from_partial_write` — `.tmp` ფაილი წინასწარ არსებული → cleanup + success

`tests/test_server_alias_endpoint.py` (new):

5. `test_post_alias_confirm_happy_path` — valid payload → 200, JSON file 1 entry-ით
6. `test_post_alias_confirm_invalid_retail_key_returns_400` — unknown key → 400 + Georgian error message
7. `test_post_alias_confirm_idempotent_duplicate_returns_409` — second identical confirm → 409 (not 500)

ერთად, `tests/test_supplier_profitability.py`-ის უკვე-არსებული 50+ test-ი untouched. გავუშვი:
```
"...venv\\Scripts\\python.exe" -m pytest tests/test_validate_aliases.py tests/test_server_alias_endpoint.py tests/test_supplier_profitability.py -v
```

Frontend ცარიელი — manual smoke-test browser-ში (Sprint cycle Step 6 user review):
- Open ვასაძის პური modal → 9 candidate visible → click „დადასტურდი" 1-ზე → toast „დადასტურდა" → reload pipeline → coverage 82.4% → ~95%+

---

## Scope recommendation

**Do in single session** — Sprint cycle Step 4-6:
- Backend endpoint + helper: ~1.5 საათი
- Frontend button + state + toast: ~1.5 საათი
- Tests (7 ცალი): ~1 საათი
- Manual browser smoke-test ვასაძის პურით: ~30 წთ
- Pipeline rerun + before/after coverage diff verify: ~30 წთ

**Total: ~5 საათი ერთ session-ში**. context budget healthy (Opus 4.7, 1M context window).

**Defer to Sprint D**:
- `unmatched_preview` cap-ის გაზრდა (top 10 → all-with-candidate)
- ELIZI/tobacco renumbering — ცალკე investigation (eANGARISH cross-ref ან ground-truth Excel რომ user მოგვცეს)
- Bulk confirm UI („ერთბაშად ყველა დაადასტურე") — სავარაუდოდ არ სჭირდება, candidate-ები <100 ცალია

---

## Self-check checklist (pre-commit)

- [ ] `gitnexus_impact({target: "build_supplier_profitability"})` — verify alias-loading code path untouched (zero modification expected)
- [ ] Atomic write უნდა იყოს — partial-write-ის პრობლემა არ შემოვიდეს
- [ ] Endpoint validation — frontend-ის-მიერ-შეცვლილ candidate-ს არ ვენდობი, retail_known_keys ცად-ცარიელი
- [ ] Toast Georgian — plain language, ჟარგონის გარეშე
- [ ] tests green: 50+ supplier_profitability + 4 _validate_aliases (existing) + 7 new = 61+ green
- [ ] `gitnexus_detect_changes` — confirm scope match
- [ ] CONTEXT_HANDOFF.md update post-merge: row 137 status `🚨 0a NEW` → `✅ DONE 2026-04-30 (commit XXX)`, coverage delta documented (e.g., 21/70 → 25-30/70 ≥90%)
- [ ] HANDOFF.md row update with commit SHA → archive pointer
- [ ] User review Step 6 — ცხადი „გადავიდეთ" ან „ჩავასწოროთ"

---

## Evidence sources

| რესურსი | რისთვის გამოვიყენე |
|---|---|
| `dashboard_pipeline/supplier_profitability.py` (HEAD `b3e2b41`) | name_candidate emission, output shape |
| `dashboard_pipeline/_validate_aliases.py` (HEAD `b3e2b41`) | validation rules, return shape |
| `dashboard_pipeline/__init__.py` import surface | `build_supplier_profitability` re-export |
| `generate_dashboard_data.py:1665` | wiring of alias loader into pipeline |
| `rs-dashboard/src/SupplierModal.jsx` lines 172-231, 652-670 | current UnmatchedProductRow + section structure |
| `server.py:670-715` | POST endpoint pattern (`/api/vat-reconciliation/cash-outflow`) |
| `Financial_Analysis/product_aliases.json` | empty schema fixed |
| `C:\financial-dashboard\rs-dashboard\public\data.json` (2026-04-30 14:06, 65 MB) | live supplier coverage state, candidate distribution |
| `CONTEXT_HANDOFF.md:137` | Sprint C original scope agreement |
| `docs/MASTER_PLAN.md` §3 sprint cycle | 6-step verification framework |

---

**ვერსია:** v1 · 2026-04-30 · NO CODE CHANGE
