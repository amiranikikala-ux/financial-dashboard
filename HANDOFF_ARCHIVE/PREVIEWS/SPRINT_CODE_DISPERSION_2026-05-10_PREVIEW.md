# Sprint — Code Dispersion Detection · Evidence Preview

**Status**: `PREVIEW · NO CODE CHANGE`
**Date**: 2026-05-10 (ღამე)
**Owner**: tengiz (financial-dashboard)
**Author session**: Claude Opus 4.7

---

## 0. TL;DR

ერთი ფიზიკური პროდუქტი (მაგ. ფეირი ლიმონი 21x450მლ) MegaPlus-ში 3 სხვადასხვა კოდით ცოცხლობს. ერთი კოდი უარყოფითში ჩავარდა (-350 ცალი), დანარჩენ ორზე იგივე საქონელი ნაშთად ზის (+336, +42). ნამდვილად შემოვიდა 492, გაიყიდა 464, ნამდვილი ნაშთი +28 — შეცდომა მხოლოდ კოდურია. პირველი ცდის ჰერისტიკამ 837 ჯგუფი იპოვა, მაგრამ **სატესტო შემთხვევა (ფეირი ლიმონი) ვერ აღმოაჩინა** ქართული ფორმის გამო, და ჰქონდა სერიოზული false positive-ები (მინერალური წყლის ბრენდები გადაერთიანდა, კოლა სხვადასხვა მოცულობით გაერთიანდა, სიგარეტის ვარიანტები გაერთიანდა). ეს sprint ცვლის ჰერისტიკას მრავალი-სიგნალის ანალიზზე და უწევს Excel review tool-ის გაშვებას — orphan_resolver.py-ის ანალოგიური შაბლონით (read-only, owner ხელით ცვლის MegaPlus-ში).

---

## 1. Inventory

### 1.1 ცოცხალი მონაცემიდან გადამოწმებული ფაქტები

ფეირი ლიმონის spot-check (`_scratch_dogfood_barcode_5413149798946.py` რეალურ DB-ზე):

| P_ID | ბარკოდი | სახელი | qty | IN (GET ACT=1) | OUT (ORDERS ACT=1) |
|---|---|---|---|---|---|
| 20754 | 5413149798946 | ფეირი ლიმონი 21x450მლ | -350 | 76 | 426 |
| 89755 | 8001090931191 | ფეირი (1) ლიმონი 0.450მლ ყ*21 | +336 | 374 | 38 |
| 93297 | 4038 | ფეირი ლიმონის 450 მლ 21ც | +42 | 42 | 0 |
| **ჯამი** | | | **+28** | **492** | **464** |

გარღვევის წერტილი: **2025-08** — 315 ცალი შემოვიდა 89755 კოდზე (zed 0917377733), იმავე თვეში 142 ცალი გაიყიდა 20754 კოდზე. ანუ შემოსული ბარკოდი ერთი იყო, სალაროს ბაზაში — სხვა.

### 1.2 პირველი ცდის ჰერისტიკის შედეგი

`_scratch_dispersed_codes_discovery.py` — token-overlap (≥3 shared discriminating tokens, ≥60% Jaccard ორმხრივ):

| მაჩვენებელი | დვაბზუ | ოზურგეთი | ჯამი |
|---|---|---|---|
| products with P_QUANT < 0 | 701 | 1,019 | 1,720 |
| candidate groups detected | 342 | 495 | 837 |
| groups where IN-OUT ≈ snapshot | 262 (77%) | 409 (83%) | 671 (80%) |

### 1.3 პირველი ცდის ცნობილი დეფექტები

**Defect A — false negative (test case missed):** ფეირი ლიმონის 3 კოდი ერთად ვერ შეიკრიბა, რადგან „ლიმონი" vs „ლიმონის" (ქართული ფორმა) როგორც ცალკე token განიხილება. ცხადი მტკიცებულება: anchor „ფეირი ლიმონი 21x450მლ"-ზე verify-ის სკრიპტმა „NOT FOUND" დააბრუნა (`_scratch_verify_dispersion_sample.py` output, 2026-05-10).

**Defect B — false positives (verified samples):**
- მინერალური წყალი ერთად ჩაიყარა: "მინ წყალი /საირმე /2ლ" + "მინ წყალი /ნაბეღლავი/1ლ" + "მინ წყალი /ბორჯომი/0.5ლ" + "მინ წყალი /ბაკურიანი/1ლ პეტი" → 16-ნოდიანი ცრუ ჯგუფი (4-6 ბრენდი, 4 მოცულობა აერია)
- კოლის მოცულობები აერია: "0.150ლ კოკა-კოლა" + "0.250ლ" + "0.5ლ" + "0.33ლ ქილა" + "1ლ" → 15-ნოდიანი ცრუ ჯგუფი
- სიგარეტის ვარიანტები აერია: "ფილიპ მორისი ექსპერტ რედი" + "Compact Blue" + "Compact Mix" + "გოლდი" + "Slim Blue" → 10-ნოდიანი ცრუ ჯგუფი

ფესვი: token-overlap-ი ვერ ხედავს რომ „საირმე" vs „ნაბეღლავი" სხვადასხვა ბრენდია, ან „0.150" vs „0.250" სხვადასხვა მოცულობაა.

### 1.4 უკვე-არსებული ინფრასტრუქტურა (გამოვიყენებ)

| რესურსი | ფაილი | რასთან გამოვიყენებ |
|---|---|---|
| `_connect(db_name)` SQL helper | `dashboard_pipeline/megaplus_backup.py:106` | DB connection (Trusted, ODBC 18) |
| `parse_g_time(bigint)` G_TIME დეკოდერი | `dashboard_pipeline/waybill_reconciliation.py:108` | yymmddhhxx → Timestamp |
| `orphan_resolver.py` შაბლონი | `dashboard_pipeline/orphan_resolver.py` | Excel review pattern (read-only, owner ხელით ცვლის) |
| `cross_store_comparison` block | `dashboard_pipeline/retail_sales.py:1650` | API contract pattern (top-N + filter notes + sort variants) |
| `dead_stock_summary` UI | `rs-dashboard/src/RetailSales.jsx:356` + L2540+ | CollapsibleSection + KPI cards + bucket chips პატერნი |
| `tests/test_retail_sales_dead_stock.py` | tests | combinator-only test pattern (no DB) |
| `Financial_Analysis/product_aliases.json` | aliases | სქემა cross-system mapping-ისთვის — *არ იყენებს* intra-store dispersion-ისთვის, ცალკე ფაილი მინდა |

### 1.5 უკვე-დახურული ფრაგმენტაციის სამუშაო (განსხვავებული პრობლემა)

`HANDOFF_ARCHIVE/PREVIEWS/PRODUCTS_FRAGMENTATION_2026-05-03.md`:
- იქ პრობლემა: **იგივე ბარკოდი** რამდენიმე P_ID-ზე (Type A typing dup: 302 ცალი)
- აქ პრობლემა: **სხვადასხვა ბარკოდი** იგივე ფიზიკურ პროდუქტზე
- ეს ორი პრობლემა **დამოუკიდებელია** — გადაკვეთა მცირეა, ცალცალკე უნდა მოგვარდეს

---

## 2. ალგორითმი v2 — Multi-signal evidence

### 2.1 ცხადი ფილოსოფია

orphan_resolver-ის სტილი: **არ ვცადოთ 100% ავტომატური სიზუსტე**. ვაჩვენოთ კანდიდატები მთელი მტკიცებულებით (signals + numbers), owner გადაწყვიტოს. False negative > false positive (cleaner suggestions ცოტა, მაგრამ სანდო).

### 2.2 ეტაპები

**Stage 0 — სქემის გადამოწმება**: `INFORMATION_SCHEMA.COLUMNS` PRODUCTS-ისთვის ორივე DB-ში — დაფიქსირდა რომ P_GROUP არ არსებობდა MEGAPLUS_1329-ში v1 spotcheck-ში. P_GROUP, P_DAFAULTSUPPLIER, ნებისმიერი category column უნდა გადამოწმდეს.

**Stage 1 — anchor + candidate filter (cheap):**
- anchor = P_ID where P_QUANT < 0 AND has ORDERS history (lifetime out > 0)
- candidate pool = P_ID with positive qty in same store
- pre-filter by **stem-of-first-significant-token match** (drop punctuation + parens + size first; first 4 chars of first ≥4-char content token must equal anchor's)
- ეს დიდად ამცირებს pair-ების რაოდენობას O(N×M) → O(N×k)

**Stage 2 — per-pair signals (each computed and stored separately):**

| signal | range | description |
|---|---|---|
| `score_brand` | 0/1 | first 1-2 content tokens stems match (≥4-char prefix) |
| `score_size` | 0/1 | extracted unit-size matches (after normalization "0.450ლ" = "450მლ"; package counts "21x", "(12ც)" stripped) |
| `score_variant` | 0/1 | post-brand/size content tokens overlap ≥ 2 OR Jaccard ≥ 0.5 |
| `score_supplier` | 0/1 | same `P_DAFAULTSUPPLIER` UUID, OR ≥1 shared GET supplier |
| `score_temporal` | 0-1 | Pearson correlation between anchor's monthly sales decay and candidate's intake/sales rise (smoothed, only over months where both are nonzero) |
| `score_economic` | 0-1 | when group is taken as closed: `1 - min(1, |Σ_in − Σ_out − Σ_qty_now| / max(Σ_in, Σ_out, 1))` |

**Stage 3 — pair → group (greedy clustering):**
1. Start with anchor (negative-qty product).
2. Find candidates with `brand AND size AND variant` all = 1 → "tier-1" siblings.
3. Greedily expand the group: add a candidate if `brand AND size AND variant` AND adding it improves `score_economic` (the group's math closes better with it included).
4. STOP when no candidate improves the closure.

**Stage 4 — confidence tiering:**
- **HIGH** (auto-suggest): `brand=1 AND size=1 AND variant=1 AND (supplier=1 OR temporal≥0.5 OR economic≥0.9)`
- **MEDIUM** (review carefully): hard signals OK but no soft signal → flag for review
- **LOW** (manual judgement): brand+variant only without size → display, no suggestion

### 2.3 ცხადი validation cases

| case | expected | rationale |
|---|---|---|
| ფეირი ლიმონი {20754, 89755, 93297} | HIGH-merge group of 3 | brand=ფეირ stem; size=450მლ unified; variant=ლიმონ stem; economic=0.99 |
| საირმე 2ლ vs ნაბეღლავი 1ლ | NO group | brand="საირმე" vs "ნაბეღლავი" (sub-brand differs) ✗; size 2ლ vs 1ლ ✗ |
| კოკა-კოლა 0.150 vs 0.250 vs 0.5 | NO group | brand same, size differs |
| ფილიპ მორისი ექსპერტ რედი vs Compact Blue | NO group | variant differs ("ექსპერტ რედი" vs "Compact Blue") |

თითოეული spot-check live DB-ზე გავუშვათ verify-script-ში (Stage 5).

### 2.4 ბრენდის ექსტრაქცია (ცხადი წესი)

ნორმალიზაცია → split → strip stopwords → strip pure-size tokens → take **first ≥4-char content token's stem (length-4 prefix)**. ორი ბრენდის შემთხვევა (e.g. "მინ წყალი /საირმე") — ვიყენებ **მე-2 content token-ს** ბრენდად, თუ პირველი 1-3 ცარიელი generic-ია (lookup table: {"მინ", "წყალი", "გაზ", "სასმელი", "შ/მ", "შიდა", "სიგარეტი"} → skip → next).

### 2.5 ზომის ექსტრაქცია (ცხადი წესი)

regex: `(\d+([.,]\d+)?)\s*(მლ|ლ|გ|კგ|ml|l|g|kg)`. ყველა match-ი → ფილტრი:
- ფასადი package count: skip if preceded by `x` ან followed by `ც` ან `ცალი` ან `*\d`
- value < 1 + unit მლ → operator typo, ვაკონვერტირებ (0.450მლ → 450მლ)
- value ≥ 1 + unit ლ → convert to მლ (0.5ლ → 500მლ)
- კანონიკური ფორმა: `{value_in_ml}მლ`

ერთიდან მეტი ზომის შემთხვევაში — ვიღებ უდიდეს ერთად-სალოგიკოდ ბრენდის შემდგომ მდებარე token-ს.

---

## 3. Risks / Pitfalls

| # | რისკი | სავარაუდოობა | mitigation |
|---|---|---|---|
| 1 | Georgian inflection ცდუნება ჯერ კიდევ — „ლიმონი/ლიმონის/ლიმონის-" | მაღალი | length-4 prefix stem („ლიმონ") უნდა ფარავდეს ყველაზე გავრცელებულ ფორმებს. Test case ცხადია. |
| 2 | Brand extraction-ის ცდუნება generic პრეფიქსებზე („მინ წყალი" / „გაზ.სასმელი" / „შ/მ") | მაღალი | explicit skip-list § 2.4. Spot-check ყველა generic-ზე. |
| 3 | Size normalization-ის edge cases (ერთი ცალი, ცამხრივი შეფუთვა) | საშუალო | ცხადი regex § 2.5 + `score_size = 0` თუ ვერ ვცნობ — fallback დიდი ზომის რეცეპტებზე |
| 4 | Temporal correlation noise short-lived პროდუქტებზე | საშუალო | min-data threshold (≥6 ორ-სიდე-ზრდის თვე) — სხვაგვარად score_temporal = NA, არ ვიყენებ |
| 5 | Economic completeness ცრუ-პოზიტივი თუ მართლაც აკლდა საქონელი (ქურდობა/აღსოფლი) | დაბალი | ცალკე flag — `economic ≥ 0.9 ✓` vs `<0.9 ⚠` ცხრილში. Owner ხედავს და გადაწყვეტს. |
| 6 | API/UI scope — დიდი feature, ერთ session-ში ვერ ჩაეტევა | მაღალი | **split**: Phase 1 = backend + Excel review tool (ეს sprint); Phase 2 = dashboard UI section (separate sprint) |
| 7 | PRODUCTS row count 100K+ × 100K+ → O(N²) ფეთქდება | საშუალო | Stage 1 stem-prefix filter ამცირებს pair count-ს ≤10K-მდე |
| 8 | Schema column-name სხვაობა DB-ებს შორის (P_GROUP არ ეგზისტირებს?) | დაბალი | Stage 0 schema audit — fall back მხოლოდ available columns-ზე |

---

## 4. Scope recommendation

**ორ-ფაზიანი sprint, ერთად ვერ ჩატევდება საუკეთესო session-ში:**

### Phase 1 — backend logic + Excel review tool (ეს session)
- ✅ Stage 0 schema audit
- ✅ Algorithm v2 implementation in `dashboard_pipeline/code_dispersion.py` (new file, mirrors `orphan_resolver.py`)
- ✅ Stage 5 spot-check script: ფეირი ლიმონი HIGH-merged ✓, საირმე NO-group ✓, კოლა sizes NO-group ✓, სიგარეტი NO-group ✓
- ✅ Excel output to `Desktop\code_dispersion_review_2026-05-XX.xlsx`:
  - Sheet `summary` — confidence-ranked groups (HIGH/MEDIUM/LOW)
  - Sheet `groups_detail` — per-group rows + all 6 signals + manual `verdict` column for owner
  - Sheet `accepted_aliases` — initially empty; owner fills, then we read back next session
- ✅ Tests: `tests/test_code_dispersion.py` — pure-Python tests on synthetic PRODUCTS+GET+ORDERS samples (4 validation cases from § 2.3)
- ❌ NO dashboard UI yet
- ❌ NO API contract change yet
- ❌ NO data.json regeneration

### Phase 2 — Dashboard integration (next session)
- Read accepted_aliases (verified by owner in Phase 1 Excel)
- Add `code_dispersion_groups` block to `synthesize_from_megaplus`
- Project through `api_contracts.py` (per `feedback_pipeline_registry_override.md`)
- New `RetailSales.jsx` CollapsibleSection: 3 KPI cards + group browser
- Tests for combinator + projection

**რატომ split:** Phase 1-ის ხარისხი (algorithm correctness + owner approval flow) უნდა მტკიცდეს ფიქსირდეს ვიდრე UI surface-ი დაიხატოს. UI-მდე owner უნდა დაამოწმოს რომ tool-ი მართლაც სწორ ჯგუფებს იპოვნის.

---

## 5. Test plan (Phase 1)

`tests/test_code_dispersion.py` (pattern: `test_retail_sales_dead_stock.py`):

| # | test name | რას ამოწმებს |
|---|---|---|
| 1 | `test_brand_stem_extracts_first_content_token` | "ფეირი ლიმონი 21x450მლ" → brand="ფეირ"; "მინ წყალი /საირმე" → brand="საირ" (skip "მინ", "წყალი") |
| 2 | `test_size_normalization_handles_decimal_typo` | "0.450მლ" → 450; "0.5ლ" → 500; "21x450მლ" → 450; "(12ც) 0.150ლ" → 150 |
| 3 | `test_size_strips_package_counts` | "ფეირი 21x450მლ" → 450 only; not 21 |
| 4 | `test_fairy_lemon_group_detected_high` | synthetic 3-row PRODUCTS + GET + ORDERS → HIGH-merge group of all 3 |
| 5 | `test_mineral_water_brands_not_merged` | "საირმე 2ლ" + "ნაბეღლავი 1ლ" + "ბორჯომი 0.5ლ" → 3 separate (no group) |
| 6 | `test_cola_sizes_not_merged` | "0.150ლ" + "0.250ლ" + "0.5ლ" კოკა-კოლა → 3 separate (size=0) |
| 7 | `test_economic_score_closes_when_complete` | anchor -350 + sibling +336 + sibling +42, IN total 492 OUT total 464 → economic ≥ 0.99 |
| 8 | `test_temporal_correlation_inverse_signal` | anchor sales drop 2024-Q4 + candidate sales rise 2025-Q1 → score_temporal ≥ 0.5 |
| 9 | `test_low_tier_when_size_mismatch_only` | brand+variant match but size differs → LOW (display, no merge suggest) |

ყველა pure-Python, არც ერთი DB connection — სქემის verification ცალკე live spot-check-ში.

---

## 6. Files expected to change (Phase 1)

| ფაილი | ტიპი | რა იცვლება |
|---|---|---|
| `dashboard_pipeline/code_dispersion.py` | NEW | core algorithm (≈400 lines) — mirrors orphan_resolver.py shape |
| `tests/test_code_dispersion.py` | NEW | 9 tests (≈350 lines) |
| `_scratch_verify_dispersion_v2.py` | NEW (`_scratch_*` per AGENTS.md) | live DB spot-check on 4 validation cases |
| `Desktop\code_dispersion_review_2026-05-XX.xlsx` | OUTPUT (not in repo) | owner review file |

**არ ეცვლება:**
- `dashboard_pipeline/retail_sales.py`
- `dashboard_pipeline/api_contracts.py`
- `rs-dashboard/src/RetailSales.jsx`
- `rs-dashboard/public/data.json`
- `Financial_Analysis/product_aliases.json` (existing schema is for cross-system, not intra-store)

**Phase 2-ისას მხოლოდ ეცვლება**: ზედა 4 ფაილი + ახალი `Financial_Analysis/code_dispersion_aliases.json` (separate schema; owner-confirmed groups).

---

## 7. Self-check checklist (pre-implementation)

- [ ] schema audit რეალურ DB-ზე გაშვებულია, ცნობილი columns ცხადი (P_GROUP existence verified)
- [ ] brand stoplist § 2.4-ში ცხადია, owner-მა დაადასტურა (ან ცხადად მითხრა "skip-list ფინალურია")
- [ ] size regex § 2.5-ში ცხადია, edge cases ცნობილია
- [ ] 4 validation cases § 2.3-ში live DB-ზე verifiable (და უარი ან დადასტურება ცხადია vidრე implementation)
- [ ] confidence tier definition § 2.4-ში owner-მა დაამოწმა — HIGH/MEDIUM/LOW border ცხადია
- [ ] Excel review file format owner-ს მოსწონს (orphan_resolver-ის ანალოგია)

---

## 8. Evidence sources (for next session re-entry)

| რესურსი | ბილიკი | ვერსია/SHA |
|---|---|---|
| ფეირი ლიმონის spot-check სრული output | `_scratch_dogfood_barcode_5413149798946.py` | branch main, uncommitted |
| v1 discovery output | `Desktop\dispersed_codes_review_2026-05-10.xlsx` | run @ 2026-05-10 ღამე |
| v1 verification output | `_scratch_verify_dispersion_sample.py` | console output captured in this preview §1.3 |
| Existing fragmentation analysis | `HANDOFF_ARCHIVE/PREVIEWS/PRODUCTS_FRAGMENTATION_2026-05-03.md` | Type A 302 / Type B 769 / Ambiguous 119 |
| Existing alias schema | `Financial_Analysis/product_aliases.json` | empty aliases array; cross-system schema, not reusable for intra-store |
| Pattern reference (read-only Excel review) | `dashboard_pipeline/orphan_resolver.py` | last touched commit `42d2e98` |
| Pattern reference (combine block) | `dashboard_pipeline/retail_sales.py:1650` (cross_store_comparison) | commit `345072e` (Dead Stock §8) |

---

## 9. Open questions for owner before implementation

1. **Brand skip-list საბოლოო?** დღეს `{"მინ", "წყალი", "გაზ", "სასმელი", "შ/მ", "შიდა", "სიგარეტი"}` — ცხადია გენერიკული პრეფიქსები. სხვა generic-ები გავრცელდება? (e.g. "ნამცხვარი", "ხორცი", "რძე")

2. **Confidence tier-ის გადახარისხება მისაღებია?** HIGH = auto-suggest merge; MEDIUM = review; LOW = display-only. Phase 1 Excel-ში owner ცხრილს მოწერს `verdict` სვეტს — გნებავს `[merge / keep_separate / unsure]` სამოპციანი, თუ უფრო დეტალური?

3. **Phase 2 ალიასების სქემა — ცალკე ფაილი თუ MegaPlus-ში canonical-ის ჩაწერა?**
   - **ვარიანტი A**: `Financial_Analysis/code_dispersion_aliases.json` ცალკე (orphan_resolver style, owner ვიწრო control); MegaPlus უცვლელი; dashboard ფარავს.
   - **ვარიანტი B**: owner თვითონ აკეთებს merge-ს MegaPlus-ში; dashboard auto-detect-ი ამოწმებს.
   - **A-ს ვარჩევ** რადგან: (1) safer (no MegaPlus write); (2) reversible; (3) owner workflow უცვლელი.

---

**Generated**: 2026-05-10 ღამე (Claude Opus 4.7) · **STRICT SCOPE — read-only preview, no code change**
