# PRODUCTS Fragmentation — Evidence Preview

**თარიღი**: 2026-05-03 · **Phase 1 — Data Quality Sprint, deliverable (a)** · **READ-ONLY** · არც ერთი code edit, არც commit, არც push.

---

## 0. მოკლე ქართული რეზიუმე

ერთი ფიზიკური barcode (პროდუქტის შტრიხკოდი) ხშირად რეგისტრირებულია **მრავალი P_ID-ით ერთი მაღაზიის შიგნით** — Megaplus-ში ოპერატორმა იგივე პროდუქტი მეორედ შექმნა იმის მაგივრად რომ უკვე არსებული გამოეყენებინა. ამის გამო მონაცემთა აგრეგაციისას „ერთი პროდუქტი" სხვადასხვა P_ID-ზე იშლება — ფაქტურა ერთს ხვდება, გაყიდვა მეორეს, ცხრილი ფრაგმენტული გამოდის.

ცოცხალი მონაცემიდან (2026-05-03):

| Store | ფრაგმენტირებული barcode | სრული PRODUCTS row count |
|---|---|---|
| დვაბზუ (1329) | **1,525** | 100,746 |
| ოზურგეთი (1301) | **1,875** | 100,774 |
| ერთ მაღაზიაში მაინც | **2,210** | — |
| ორივე მაღაზიაში ერთდროულად | **1,190** | — |

20-row sample სპოტ-ჩეკი 10-ვე ხაზზე **10/10 დადასტურდა** ხელახლა მოთხოვნით ცოცხალ DB-ზე.

⚠️ **გუშინდელ ციფრებს არ ემთხვევა** — იხ. §6 cross-check footnote.

---

## 1. ფრაგმენტაციის definition (ცხადი არჩევანი)

**არჩეული definition:**

> ერთი მაღაზიის DB-ში (`MEGAPLUS_<storeID>`), `PRODUCTS` ცხრილში, ერთი და იმავე ფიზიკური barcode-ის (`P_BARCODE`, trailing whitespace მოჭრილი) **მრავალი ცალკე P_ID-ის** არსებობა.

**რატომ ეს definition:**

- ეს არის ის pattern რომელიც **მიყიდვა-ფაქტურის აგრეგაციას ფიზიკურად აზიანებს** ცალკე ერთი მაღაზიის შიგნით:
  - GET (ფაქტურის) ხაზი მიცურავს P_ID #1-ზე
  - ORDERS (გაყიდვის) ხაზი მიცურავს P_ID #2-ზე
  - per-product აგრეგატი (cost vs revenue, margin, inventory) **ფრაგმენტულ ცხრილს იძლევა**
- Cross-store (იხ. ალტერნატივა B ქვემოთ) თვითონ "different P_ID across stores" trivially TRUE-ია **ყველა საერთო barcode-ისთვის** (~95K), რადგან თითოეული მაღაზია ცალკე ID-სივრცეს იყენებს — ეს არ არის bug, ეს არის schema design

**Filter**: trailing whitespace TRIM-ით; ცარიელი barcode გამოვრიცხოთ; `0000%`-ით დაწყებული placeholder კოდები გამოვრიცხოთ.

### განხილული ალტერნატიული definition-ები (არ ავირჩიე)

| # | ალტერნატივა | რატომ არ ავირჩიე |
|---|---|---|
| A | ერთი ფიზიკური barcode → სხვადასხვა P_ID **ორ მაღაზიას შორის** (cross-store) | trivially TRUE 95,425 საერთო barcode-ისთვის — schema-ის design-ია, არა bug |
| B | A + სახელი/ჯგუფი განსხვავდება ორ მაღაზიას შორის (semantic mismatch) | მნიშვნელოვანია, მაგრამ უფრო რთული definition; უნდა ჯერ A-ს ფესვი დახურდეს |
| C | ერთი მაღაზიაში მრავალი P_ID **+** იქვე უნდა იყოს ცოცხალი GET ან ORDERS აქტივობა | უფრო ვიწრო, „ეფექტური" frag-ი — მაგრამ definition-ი მოცულობას ორმაგებს, ჯერ baseline-ი დაგვიდეს |
| D | მხოლოდ active rows (`P_ACTIVE = 1`) | ცოტა იცვლის count-ს (1,523 vs 1,524 დვაბზუ) — დიდი delta არ არის, ფარული „ჩაკეტილი" duplicates ცალკე ღირს |

---

## 2. ზუსტი SQL (ცოცხალ DB-ზე გაშვებული)

```sql
-- Per-store count of fragmented barcodes (run on each MEGAPLUS_<storeID>)
SELECT COUNT(*) AS fragmented_barcodes
FROM (
    SELECT LTRIM(RTRIM(P_BARCODE)) AS bc
    FROM PRODUCTS
    WHERE P_BARCODE IS NOT NULL
      AND LTRIM(RTRIM(P_BARCODE)) <> ''
      AND LTRIM(RTRIM(P_BARCODE)) NOT LIKE '0000%'
    GROUP BY LTRIM(RTRIM(P_BARCODE))
    HAVING COUNT(DISTINCT P_ID) > 1
) x;
```

```sql
-- Diagnostic: rows with trailing/leading whitespace in barcode
SELECT COUNT(*) FROM PRODUCTS
WHERE P_BARCODE IS NOT NULL
  AND P_BARCODE <> LTRIM(RTRIM(P_BARCODE));
-- Result: 14 rows in 1329, 14 rows in 1301
```

```sql
-- Per-barcode all rows (used for sample build)
SELECT
    LTRIM(RTRIM(P_BARCODE)) AS bc,
    P_ID, P_NAME, P_GROUP, P_ACTIVE, P_DAFAULTSUPPLIER
FROM PRODUCTS
WHERE P_BARCODE IS NOT NULL
  AND LTRIM(RTRIM(P_BARCODE)) <> ''
  AND LTRIM(RTRIM(P_BARCODE)) NOT LIKE '0000%';

-- Supplier name resolution
SELECT DIST_UUID, dasaxeleba FROM DISTRIBUTORS;
-- JOIN: PRODUCTS.P_DAFAULTSUPPLIER = DISTRIBUTORS.DIST_UUID
```

---

## 3. Live count

| Store | DB | რიგით (P_BARCODE) | distinct (P_BARCODE) | **ფრაგმენტირებული barcode** | ფრაგმ. რიგი |
|---|---|---|---|---|---|
| დვაბზუ | `MEGAPLUS_1329` | 100,430 | 98,905 | **1,525** | 3,049 |
| ოზურგეთი | `MEGAPLUS_1301` | 100,454 | 98,567 | **1,875** | 3,761 |

| აგრეგაციული | რაოდენობა |
|---|---|
| ერთ მაღაზიაში მაინც (union) | **2,210** |
| ორივე მაღაზიაში ერთდროულად (intersection) | **1,190** |
| საერთო barcode (ორივე მაღაზიაში) | 95,425 |

---

## 4. წარმომადგენლობითი sample (20 barcode)

10 ხაზი — ფრაგმენტირებული **ორივე** მაღაზიაში; 5 — მხოლოდ დვაბზუში; 5 — მხოლოდ ოზურგეთში. random.seed(20260503).

| # | barcode | სახელი (variants) | P_ID-დვაბზუ | P_ID-ოზურგეთი | მომწოდებელი | P_GROUP | P_ACTIVE დვ./ოზ. |
|---|---|---|---|---|---|---|---|
| 1 | 2601548000002 | "ასაწონი შოკოლადი /როშენი კრემონა" + "ხილი /ბერძნული ქლიავი" | 5774, 64800 | 35346, 81579 | ბიდი კომპანი · ბორა | კანფეტი · ნაყინი | 1/1 / 1/1 |
| 2 | 082184090442 | "ვისკი /ჯეკ დენიელსი/ 1ლ" | 40624, 94572 | 75207, 96117 | გდ ალკო | ვისკი | 1/1 / 1/1 |
| 3 | 2609658000004 | "ჭარხლის სალათი" + "ხორცი/კუპატი" | 19851, 92573 | 2265, 93294 | აჩი | ფეხსაცმელი · ხორცპროდ. | 1/1 / 1/1 |
| 4 | 8690624203394 | "დორიტოს SHOTS" (3 ვარიანტი) | 92207, 92356 | 92719, 92959 | იბერია რეფრეშმენტსი | ჩიფსი | 1/1 / 1/1 |
| 5 | 4869002039588 | "ცივი/ლობიო ნგვზ" + "ქათმის კოტლეტი" | 59999, 92759 | 85048, 93533 | ევროპული საცხობი | ლანჩ ბოქსი | 1/1 / 1/1 |
| 6 | 2506088000003 | "რძე 2.5%" + "საახალწლო განათება" | 12132, 41687 | 17359, 69366 | გნოცა · მახარაძე ბ. | რძე · საახალწლო | 1/1 / 1/1 |
| 7 | 2507519000005 | "ყავა ლატე-კარამელი" + "ერთჯერადი პარკი" | 34530, 51405 | 51210, 67343 | შანავა ე. | სახარჯი · ყავა | 1/1 / 1/1 |
| 8 | 2521912000004 | "სკოჩი პატარა /35მ" (FR-ით და გარეშე) | 17976, 62841 | 25760, 74336 | დისტრიბუტ2 | სკოჩი | 1/1 / 1/1 |
| 9 | 4860106232066 | "სუნელი/პაპრიკა" + "პაპრიკა დაფქვილი" | 64362, 96416 | 80422, 97318 | ოზნერა · რენეკო | წიწაკა სუნელი | 1/1 / 1/1 |
| 10 | 2502529000007 | "არაყი F ვოდკა" + "ნამცხვრის ასორტი" | 3424, 32557 | 4544, 65563 | მირიანაშვილი ბ. | არაყი · ნამცხვარი | 1/1 / 1/1 |
| 11 | 8690504036210 | "ულქერი_ალბენი" + "ბისკვიტი ალბენი" | 91591, 94820 | 95237 | დაფნა | ბისკვიტი | 1/1 / 1 |
| 12 | 2502796000007 | "დეკორაცია" + "სამკაული თმის სამაგრი" | 26910, 39194 | 57775 | ჯეირანაშვილი ქ. | სათამაშო · გაპასიურ. | 1/1 / 1 |
| 13 | 2508093000009 | "ნამცხვარი სნიკერსი" + "სააღდგომო წიწილა" | 1173, 62809 | — | დიდებული 2018 · ვერსალი | სააღდგომო · დამაგრძ. | 1/1 / — |
| 14 | 2509093000006 | "MP3 ფლეერი" + "მინდვრის ლობიო" | 27444, 62498 | — | მობიმარტი | ბოსტნ. · ტელ. აქს. | 1/1 / — |
| 15 | 2507429000003 | "კაპუჩინო ჩამოსასხმელი" + "RELX INFINITY წითელი" | 34452, 50855 | 66005 | რგ ტრეიდი | ელ. სიგარეტი · ყავა | 1/1 / 1 |
| 16 | 2602025000003 | "გამოსაცხობი მარწყვი" + "ქათმის ფილე" | 65032 | 10586, 82203 | ბესტ გრუპი · გაგრა+ | გამოსაცხ. · ქათამი | 1 / 1/1 |
| 17 | 47605770 | "Lincoln Compact Blue" (2 აკრეფა) | 86622 | 87710, 87811 | თ & რ დისტრიბუშენ | სიგარეტი | 1 / 1/1 |
| 18 | 2602280000008 | "შოკოლადის ფილა 2.25კგ" + "კაკაო D11S" | 44856 | 11520, 64522 | ჯეოსვითი · შვიდი | შოკოლადი · კაკაო | 1 / 1/1 |
| 19 | 2600704000009 | "ბასთურმა კაიზერი" + "ფრთის ძირები ურუშა" | 55651 | 32952, 80211 | სამეფო ფრთები · პარტნიორი | ფრთა · ძეხვი | 1 / 1/1 |
| 20 | 8690637805219 | "კეჩუპი კალვე ბარბექიუ" + "სოუსი კალვე" | 57329 | 29524, 76611 | BRAND BASKET · შარმ ტრეიდინგი | სოუსი | 1 / 1/1 |

### Sample-ის შეჩვია (qualitative)

ფრაგმენტაცია **ორი ფესვია**, sample-ზე ცხადია:

- **Type A — ოპერატორმა იგივე პროდუქტი ხელახლა შექმნა** (typing duplicate). მაგ: #2 ვისკი ჯეკ დენიელსი (ერთი სახელი, ორი P_ID); #4 დორიტოს SHOTS (3 ვარიანტი); #11 ულქერი_ალბენი vs ბისკვიტი ალბენი; #17 Lincoln (განსხვავებული capitalization)
- **Type B — სრულიად სხვა პროდუქტებს იგივე internal barcode-ი მიენიჭა** (barcode reuse). ეს ძირითადად ხდება Megaplus-ის ხელით-გენერირებულ შტრიხკოდებზე (`2502...`, `2506...`, `2509...`). მაგ: #1 შოკოლადი vs ქლიავი; #3 ჭარხლის სალათი vs კუპატი; #6 რძე vs საახალწლო განათება; #14 MP3 ფლეერი vs ლობიო

EAN-ის რეალური barcode-ები (8-13 ციფრი, არც ნულით დაწყებული) ძირითადად Type A-ში ხვდებიან. Megaplus-ის შიდა generated codes — Type B-ში.

**„(FR)" suffix** — ბევრ დუბლიკატ row-ზე გვხვდება. სავარაუდოდ "fresh"-ის აღმნიშვნელია (ყოველდღიური მზადება). ცოცხალი production items barcodes ცვალებადი ჩანს.

---

## 5. Spot-check (random 10/20)

random.seed(99). ყოველი არჩეული barcode-ისთვის — დამოუკიდებელი `SELECT P_ID FROM PRODUCTS WHERE LTRIM(RTRIM(P_BARCODE)) = ?` ცოცხალ DB-ზე, შედარება sample-ის expected-სთან.

| # | barcode | expected 1329 | got 1329 | expected 1301 | got 1301 | ✓ |
|---|---|---|---|---|---|---|
| 1 | 2508093000009 | [1173, 62809] | [1173, 62809] | [] | [] | ✓ |
| 2 | 8690637805219 | [57329] | [57329] | [29524, 76611] | [29524, 76611] | ✓ |
| 3 | 2507519000005 | [34530, 51405] | [34530, 51405] | [51210, 67343] | [51210, 67343] | ✓ |
| 4 | 2506088000003 | [12132, 41687] | [12132, 41687] | [17359, 69366] | [17359, 69366] | ✓ |
| 5 | 2521912000004 | [17976, 62841] | [17976, 62841] | [25760, 74336] | [25760, 74336] | ✓ |
| 6 | 8690624203394 | [92207, 92356] | [92207, 92356] | [92719, 92959] | [92719, 92959] | ✓ |
| 7 | 2609658000004 | [19851, 92573] | [19851, 92573] | [2265, 93294] | [2265, 93294] | ✓ |
| 8 | 2600704000009 | [55651] | [55651] | [32952, 80211] | [32952, 80211] | ✓ |
| 9 | 082184090442 | [40624, 94572] | [40624, 94572] | [75207, 96117] | [75207, 96117] | ✓ |
| 10 | 4869002039588 | [59999, 92759] | [59999, 92759] | [85048, 93533] | [85048, 93533] | ✓ |

**შედეგი: 10/10 confirmed.**

### Methodology bug რომელიც გაიჭერა და გაიწორა

პირველ run-ში spot-check-მა **4/10 discrepancy** აჩვენა. ფესვი: 14 row-ს თითოეულ DB-ში P_BARCODE-ში trailing whitespace ჰქონდა. SQL Server-ის `=` operator ასწორებს trailing space-ს, მაგრამ Python-ის dict key-ი არა — შედეგად ერთი ფიზიკური barcode-ის რიგები ცალცალკე bucket-ებად იყოფოდა, sample display არასწორ P_ID სიას აჩვენებდა. გასწორება: `LTRIM(RTRIM(P_BARCODE))` ყველგან (SQL და Python სამივე ეტაპზე — count, sample build, spot-check). Re-run → 10/10. Final count-ი ამის შემდეგ შეიცვალა (1,524 → 1,525 დვაბზუ; 1,874 → 1,875 ოზურგეთი) — მცირე delta, მაგრამ რეალური.

---

## 6. Cross-check vs გუშინდელი ციფრები (footnote, არა anchor)

`CONTEXT_HANDOFF.md` §1a-ში გუშინდელი chat-დან გადასული ციფრები:

| გუშინ chat | ჩემი დღევანდელი | ემთხვევა? |
|---|---|---|
| **„1,299 barcode ერთდროულად ფიქსირდება ორივე მაღაზიის უარყოფით სიაში"** | 1,190 (intersection — ორივე მაღაზიის intra-frag) | ❌ **არა** — გუშინდელი 1,299 იყო *negative-balance* intersection (Detector #21), არა pure fragmentation. ციფრი ახლოა შემთხვევით |
| **„252 dual-store P_ID ფრაგმენტი"** | 2,210 (union) ან 1,190 (both) — არცერთი 252-ს არ ემთხვევა | ❌ **არა** — გუშინდელი 252 უფრო ვიწრო filter-ით აიგო (სავარაუდოდ active + with sales/receipts), დღევანდელი ბაზელაინ definition-ი არ მოიცავს ამ filter-ს |

გუშინდელი ფაილური SQL უკვე არ არის (cleanup-ში წაიშალა, `CONTEXT_HANDOFF §1a` ცხადყოფს), ამიტომ ცხრილს შესადარებლად არ მაქვს. დღევანდელი ციფრები **ნულიდან წერილი SQL-ის შედეგია** (§2), არ არიან gestalt-ებული გუშინდელი მეხსიერებიდან.

---

## 7. ცხადი open question (next-step decision — fix-ი არ ვთავაზობ)

Definition (intra-store fragmentation) ცხადია. Count ცხადია. Sample ცხადია. Spot-check ცხადია.

**შენ უნდა გადაწყვიტო შემდეგი ნაბიჯი:**

1. **ხედვის გაფართოება (recommended ჯერ Phase B-მდე):** ფრაგმენტაცია ცოცხალი ბიზნესისთვის რა სიფართოვის problem-ია? რამდენი ფრაგმენტ. barcode-ი მოდის **ცოცხალ აქტივობას** (last 12-month GET ან ORDERS) — vs რამდენი არის „ჩაკეტილი" duplicates რომ ცხრილი ბინძურდება მაგრამ ფინანსურად აღარ ცოცხლდება? ეს ცალკე SQL run-ია (~30 წთ).

2. **Type A / Type B-ის ცალკე დაყოფა:** sample-ი აჩვენებს ორ ძალიან განსხვავებულ ფესვს. Type A (typing dup) ერთი ფიქს-ს ითხოვს. Type B (internal-code reuse) მთლად სხვა ლოგიკას. გინდა ცალკე count + sample თითოეული ტიპისთვის?

3. **გადახვევა Phase 1 (b)-ზე** — PRODUCTS orphan resolution (3,046 product / `P_DAFAULTSUPPLIER` ცარიელი) — ხელახლა გამოვიკვლიოთ live ციფრით?

4. **სხვა მიმართულება** — შენ მითხარი.

---

**Generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — read-only preview, no fix proposed**

---

# Section 8 — Type A vs Type B classification (1,190 dual-frag barcodes)

**დამატებულია**: 2026-05-03 (იგივე session-ში) · **Phase 1, deliverable (a) extension** · **STRICT SCOPE — read-only**

## 8.0 მოკლე ქართული რეზიუმე

1,190 barcode რომელიც ფრაგმენტირებულია **ორივე მაღაზიაში ერთდროულად** დავყავი ორ კატეგორიად:

- **Type A** = იგივე ფიზიკური პროდუქტი, ოპერატორმა ხელახლა აკრიფა (typing duplicate)
- **Type B** = სრულიად სხვა პროდუქტებს იგივე barcode მიენიჭა (internal code reuse)
- **Ambiguous** = საზღვრული შემთხვევები (კლასიფიკატორმა ცხადად ვერ გადაწყვიტა)

| ტიპი | რაოდენობა | წილი |
|---|---|---|
| **Type B** (different products, same barcode) | **769** | **64.6%** |
| **Type A** (typing duplicate, same product) | **302** | 25.4% |
| **Ambiguous** (border case — needs human judgment) | **119** | 10.0% |
| **სულ** | 1,190 | 100% |

**მთავარი finding**: **Type B-ი დომინირებს** (~2/3). თითქმის ყველა Type B-ი არის Megaplus-ის ხელით-გენერირებული შიდა კოდი (`2503...`, `2604...`, `2605...`, `2607...`-ით დაწყებული). EAN-ის რეალური barcode-ები დიდი უმრავლესობით Type A-ში ხვდება (operator typing dup).

Spot-check 10/30 ხაზზე — **10/10 confirmed**.

---

## 8.1 ცხადი definition (criterion)

**ერთეული მონაცემი per barcode**:
- ყველა distinct `P_NAME` — დვაბზუ + ოზურგეთი — combined set
- ყველა distinct `P_GROUP` — დვაბზუ + ოზურგეთი — combined set

**ნორმალიზაცია**:
- `P_NAME`: lowercase, NFC normalize, ჩამოშლა `(FR)` / `(G)` / `(BP)` / `(II)` / `D` суффიქს · პუნქტუაცია → space · მრავალი space → ერთი
- `P_GROUP`: ჩამოშლა leading `"NNNN | "` numeric prefix (e.g. `"1103 | სახარჯი მასალები"` → `"სახარჯი მასალები"`) · lowercase

**მეტრიკები**:
- `min_sim` = MIN pairwise `difflib.SequenceMatcher.ratio()` ყველა distinct ნორმალიზებულ სახელს შორის (1.0 თუ ერთი ან ნული სახელია)
- `group_overlap` = ცხადია ერთი მაინც ≥4-სიმბოლოიანი content-token (არა stopword) საერთო ყველა distinct group-ის ნორმალიზებულ token-ებში

**კლასიფიკაცია**:

| პირობა | კლასი | რას ნიშნავს |
|---|---|---|
| `min_sim ≥ 0.60` | **Type A** | სახელები ცხადად მსგავსია — typing variant |
| `0.40 ≤ min_sim < 0.60` AND `group_overlap = TRUE` | **Type A** | სახელი საშუალო მსგავსი + იმავე ჯგუფში → იგივე პროდუქტი |
| `min_sim < 0.40` AND `group_overlap = FALSE` | **Type B** | სახელი + ჯგუფი ორივე განსხვავდება → სხვადასხვა პროდუქტი |
| ყველა დანარჩენი | **Ambiguous** | (weak name + no group) ან (weak name + group match) — საზღვრული |

**Stopwords გამოვრიცხე**: „სხვა", „სხვადასხვა", „სხვ", „ჯგუფის", „გარეშე", „გრ", „კგ", „მლ", „ცალი" — ეს tokens ყველგან გვხვდება, ცრუ overlap-ს შექმნიდა.

**რამ კონკრეტულ შემთხვევებში criterion-ი ცხადად არ ჯდება** (და ამიტომ Ambiguous bucket არსებობს):
- სახელი ძალიან მოკლეა (e.g. „აჯიკა" vs სხვა) — SequenceMatcher მცირე ტექსტზე არასტაბილურია
- ჯგუფი ცრუდ ემთხვევა (e.g. ორივე row-ის ჯგუფი „ფეხსაცმელი", მაგრამ ეს Megaplus-ის უცნაური taxonomy-ის placeholder-ია)
- ერთი row English text-ში, მეორე ქართული — character similarity დაბალი, მაგრამ შინაარსით იგივე

ეს ambiguous bucket **სანდოა მხოლოდ თუ ცალკე ხელით განვხილავთ** — automatic classifier-ი მათზე გადაწყვეტილებას არ იღებს.

---

## 8.2 ზუსტი SQL + Python კლასიფიკატორი

SQL-ი ცოცხალი DB-დან მონაცემს იღებს, კლასიფიკაცია Python-ში ხდება (SequenceMatcher საჭიროებს char-level comparison-ს, რაც T-SQL-ში პრაქტიკული არ არის):

```sql
-- Same per-store query as §2, run on each MEGAPLUS_<storeID>:
SELECT
    LTRIM(RTRIM(P_BARCODE)) AS bc,
    P_ID, P_NAME, P_GROUP, P_ACTIVE, P_DAFAULTSUPPLIER
FROM PRODUCTS
WHERE P_BARCODE IS NOT NULL
  AND LTRIM(RTRIM(P_BARCODE)) <> ''
  AND LTRIM(RTRIM(P_BARCODE)) NOT LIKE '0000%';

SELECT DIST_UUID, dasaxeleba FROM DISTRIBUTORS;
```

```python
# Python classification (run after merging both stores' rows per barcode):
NORM_STRIP = re.compile(r'\s*\((?:FR|G|BP|II)\)\s*|\s*\bD\b\s*$|^\s*\d{3,4}\s*\|\s*|\s+', re.IGNORECASE)
PUNCT      = re.compile(r"[/\\\-_,.\"\'()]+")
STOPWORDS  = {"სხვა", "სხვადასხვა", "სხვ", "ჯგუფის", "გარეშე", "გრ", "კგ", "მლ", "ცალი"}
GROUP_PFX  = re.compile(r"^\s*\d{3,4}\s*\|\s*")

def normalize_name(s):
    s = unicodedata.normalize("NFC", (s or "").strip().lower())
    s = NORM_STRIP.sub(" ", s)
    s = PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()

def group_tokens(g):
    g = GROUP_PFX.sub("", (g or "")).strip().lower()
    return {t for t in re.split(r"[\s/.,\-]+", g) if len(t) >= 4 and t not in STOPWORDS}

def min_pairwise_sim(names):
    uniq = sorted({normalize_name(n) for n in names if n})
    uniq = [n for n in uniq if n]
    if len(uniq) <= 1: return 1.0
    sims = [SequenceMatcher(None, uniq[i], uniq[j]).ratio()
            for i in range(len(uniq)) for j in range(i+1, len(uniq))]
    return min(sims)

def groups_share_token(groups):
    sets = [s for s in (group_tokens(g) for g in groups if g) if s]
    if len(sets) <= 1: return True
    common = sets[0]
    for s in sets[1:]: common &= s
    return bool(common)

def classify(min_sim, group_overlap):
    if min_sim >= 0.60: return "A"
    if min_sim >= 0.40 and group_overlap: return "A"
    if min_sim < 0.40 and not group_overlap: return "B"
    return "AMBIG"
```

---

## 8.3 Live count (1,190 dual-frag barcode → A / B / Ambiguous)

| კლასი | რაოდენობა | წილი | რას ნიშნავს |
|---|---|---|---|
| **Type A** | **302** | 25.4% | ერთი პროდუქტი, ხელახლა შექმნილი (typing dup) |
| **Type B** | **769** | 64.6% | სხვადასხვა პროდუქტები, იგივე barcode (internal-code reuse) |
| **Ambiguous** | **119** | 10.0% | საზღვრული, ხელით განხილვა საჭიროა |
| **ჯამი** | **1,190** | 100% | (sanity check ✓) |

---

## 8.4 Sample (10 + 10 + 10 = 30 row)

random.seed(20260503).

### Type A (10 ხაზი) — typing duplicate (იგივე პროდუქტი)

| # | barcode | min_sim | grp_ovl | სახელ(ებ)ი | P_ID-დვ. | P_ID-ოზ. | მომწოდებელი | P_GROUP |
|---|---|---|---|---|---|---|---|---|
| 1 | 4823097808900 | 0.76 | ✓ | ესკიმო მილენიუმ შავი/ჩორნი შოკოლად-სიც. (3 vars) | 40991, 61944 | 56928, 62499 | აის ლენდ ჯორჯია | ნაყინი იმპ. სხვა |
| 2 | 025616042138 | 0.96 | ✓ | ცივი ყავა მისტერ ბრაუნი ვანილით (240მლ ≈ 0.240ლ) | 21654, 94576 | 58461, 96124 | ქართული სადისტრიბ. | ცივი ყავა |
| 3 | 4860113900187 | 0.51 | ✓ | წინდა კაცის ჰეიდეი / წინდა მამაკაცის კლასიკური | 29038, 97164 | 14426, 98198 | ბელ-ჯი · იმპორტიორი | წინდა |
| 4 | 8690637905896 | 0.50 | ✓ | კალვე კეტჩუპი ცხარე 600გრ (2 აკრეფა) | 47266, 55308 | 71740, 74623 | V.T DlSTICARET · შარმ | კეტჩუპი |
| 5 | 8034042190759 | 1.00 | ✓ | TOSTI Prosecco DOC Extra dry 0.75L (FR / non-FR) | 65729, 96345 | 83938, 97206 | კანტი | ღვინო ცქრიალა |
| 6 | 3107872600394 | 1.00 | ✗ | ტეკილა სან ხოსე სილვერ 35% 0.7ლ (FR / non-FR) | 91789, 96321 | 92347, 97203 | კანტი | ბრენდი / ტეკილა |
| 7 | 4607072710620 | 0.52 | ✓ | სიმინდის ბურღული აგრო ალიანსი კლასიკი 800გრ | 23390, 48556 | 6971, 62850 | გეო ფუდს · შაბა | სიმინდის ღერღილი |
| 8 | 4770190055871 | 0.71 | ✓ | სამეფო კრევეტები ვიჩი 30/40 500გრ | 36114, 99378 | 53368, 100101 | კანტი · პარტნიორი | გაყინული ზღვის დელ. |
| 9 | 6970212512834 | 0.65 | ✓ | სანთებელა 3KF001 / GL&Co | 86516, 98911 | 87685, 99452 | ევრო ჰაუს | სანთებელა |
| 10 | 100062 | 0.70 | ✗ | TENE USB FOR LIGHTNING 1M (English / Georgian) | 90838, 98567 | 86324, 99089 | ჯინვენტორი | ტელეფ. აქს. |

### Type B (10 ხაზი) — სხვადასხვა პროდუქტი, იგივე barcode (highlighted divergence)

| # | barcode | min_sim | სახელი #1 | სახელი #2 | P_ID-დვ. | P_ID-ოზ. | P_GROUP divergence |
|---|---|---|---|---|---|---|---|
| 1 | 2608757000007 | 0.32 | **ბალი /ქართული/ 1კგ** | **ყველი /სენე სულგუნი/ წონის** | 8843, 96688 | 39844, 97550 | ბალი ↔ ყველი ქართული |
| 2 | 2503280000008 | 0.25 | **ტარტი მარწყვის** | **ყუთი/პიცის და ხაჭაპურის** | 7603, 40776 | 10894, 24597 | შესაფუთი ↔ თევზი მარინადში |
| 3 | 2610389000003 | 0.21 | **ეკლერი** | **ცომი ფენოვანი რერა 1კგ** | 47515, 57658 | 68355, 83317 | ცომეული ↔ ნამცხვარი |
| 4 | 2503278000003 | 0.23 | **ყუთი ტორტის 30-30-16სმ** | **ყურსასმენი 8133** | 7566, 29871 | 10811, 71457 | შესაფუთი ↔ ტელეფ. აქს. |
| 5 | 2509039000008 | 0.32 | **ზეთი კახური წისქვილი 250გრ** | **ლიტვური ქადა** | 27355, 62827 | 40162, 74984 | ზეთი ↔ მარკეტინგული |
| 6 | 2510121000004 | 0.15 | **მეტალის სტატუეტი** | **სასაჩუქრე დიდი კვერცხი ხელნაკეთი** | 1204, 54111 | 27356, 77346 | სათამაშო ↔ საოჯახო ინვ. |
| 7 | 2609679000007 | 0.37 | **ნუშის ნამცხვარი ეკო ფუდი 1კგ** | **ქათმის შნიცელი** | 69623, 95692 | 28839, 96305 | მურაბა ↔ ნამცხვარი სხვა |
| 8 | 2507844000008 | 0.22 | **კერამიკის თებში (ვერსალი)** | **ჩამოსასხმელი ყავა კაპუჩინო** | 46958, 62296 | 27223, 73218 | საოჯახო ↔ ყავა ხსნადი |
| 9 | 2603461000008 | 0.20 | **Kommunarka შოკოლადის კანფეტი** | **კომბოსტოს ხვეულა** | 50158, 60662 | 64643, 87431 | კანფეტი ↔ მურაბა |
| 10 | 2605200000003 | 0.29 | **სალათა კრაბის მაიონეზში LK** | **შეფუთული ქათამი 1კგ** | 32972, 91856 | 48557, 92414 | გაყინული ქათამი ↔ სალათები |

### Ambiguous (10 ხაზი) — საზღვრული შემთხვევები

| # | barcode | min_sim | grp_ovl | სახელ(ებ)ი | რატომ ambiguous |
|---|---|---|---|---|---|
| 1 | 2606230000001 | 0.40 | ✗ | ვაშლი გოლდენი / სალათის ფოთლები | სახელი borderline, group disjoint, ორივე produce |
| 2 | 2604041000008 | 0.41 | ✗ | ზეთისხილის ასორტი / ყველი ძროხის გუდა | სახელი borderline, ერთი group "ვადაგასული I" placeholder |
| 3 | 4820023366152 | 0.49 | ✗ | შიკი მყარი საპონი 140გრ / შიკი საბავშვო 150გრ | „შიკი" საერთო, sim მაღალი მაგრამ groups განცალკ. |
| 4 | 2600434000003 | 0.45 | ✗ | მწვანილი ქინძი ქართული / შაშხი ვაკე გვერდის | sim borderline, groups სრულიად სხვა |
| 5 | 2504156000003 | 0.45 | ✗ | ადაპტერი / ვაშლის დესერტი | sim borderline, groups სრულიად სხვა (ლიკურდ ე. ვადაგასული) |
| 6 | 2604853000002 | 0.28 | **✓** | ქათმის სალათი / ცივი კერძი ქაშაყი წისქვილი | groups ცრუდ ემთხვევა „ფეხსაცმელი" placeholder-ით |
| 7 | 2600256000007 | 0.53 | ✗ | სოსისი რძიანი / ხილი მანდარინი ქარ. წონა | sim borderline, groups disjoint |
| 8 | 2600389000004 | 0.52 | ✗ | ბარკალი ტაისონი ქათმის / ბოსტნეული გოგრა ქართული | sim borderline, groups (ბოსტნეული + გაყინული ბარკალი) — partial |
| 9 | 2507519000005 | 0.40 | ✗ | ერთჯერადი პარკი 100ც (501-514) / ყავა ლატე-კარამელი 501 | „501" suffix → internal-code reuse, ცხადად Type B-ს ჰგავს მაგრამ sim ზუსტად threshold-ზე |
| 10 | 2600328000003 | 0.46 | ✗ | ბოსტნეული კომბოსტო ყვავილოვანი / თევზი მოივა გაყინული | sim borderline, groups disjoint |

---

## 8.5 Spot-check (random 10/30)

random.seed(99). ყოველი არჩეული ხაზისთვის — დამოუკიდებელი re-fetch DB-დან + classifier-ის ხელახალი run. შემოწმდა classification + min_sim + group_overlap სამივე.

| # | barcode | expected | got | ✓ |
|---|---|---|---|---|
| 1 | 2610389000003 | B sim=0.21 grp=False | B sim=0.21 grp=False | ✓ |
| 2 | 2600328000003 | AMBIG sim=0.46 grp=False | AMBIG sim=0.46 grp=False | ✓ |
| 3 | 4607072710620 | A sim=0.52 grp=True | A sim=0.52 grp=True | ✓ |
| 4 | 2605200000003 | B sim=0.29 grp=False | B sim=0.29 grp=False | ✓ |
| 5 | 3107872600394 | A sim=1.0 grp=False | A sim=1.0 grp=False | ✓ |
| 6 | 4770190055871 | A sim=0.71 grp=True | A sim=0.71 grp=True | ✓ |
| 7 | 2504156000003 | AMBIG sim=0.45 grp=False | AMBIG sim=0.45 grp=False | ✓ |
| 8 | 8034042190759 | A sim=1.0 grp=True | A sim=1.0 grp=True | ✓ |
| 9 | 4860113900187 | A sim=0.51 grp=True | A sim=0.51 grp=True | ✓ |
| 10 | 6970212512834 | A sim=0.65 grp=True | A sim=0.65 grp=True | ✓ |

**შედეგი: 10/10 confirmed.**

---

## 8.6 ცხრება (plain Georgian summary)

**1) Type B-ი დომინირებს (~2/3, 769 barcode).**

ყველა Type B-ის sample მთლიანად Megaplus-ის ხელით-გენერირებული შიდა კოდია (`2503...`, `2604...`, `2605...`, `2607...`, `2509...`, `2510...`, `2606...`). ეს არ არის ნამდვილი EAN — ეს Megaplus-ის auto-numbering-ია „ისეთი პროდუქტისთვის რომელსაც EAN არ აქვს" (in-house კერძები, weighed produce, packaging, ხელნაკეთი, marketing items). pattern-ი ცხადია: **POS-ი იძლევა operator-ს უფლებას ხელახლა გენერირდეს უკვე-დაკავებული შიდა კოდი** — uniqueness check-ი არ ეშვება ან ადვილად შეიცვლება.

**2) Type A მცირეა (1/4, 302 barcode), მაგრამ ცოცხალია.**

Type A სუფთა typing duplicate — ნამდვილი EAN barcode-ის (8-13 ციფრი, ცნობილი formatting) მქონე პროდუქტი ოპერატორმა მეორედ შექმნა იმის ნაცვლად რომ უკვე-არსებული გამოეყენებინა. სამივე ნიშანი თანხვდება: იგივე სახელი (slight variation), იგივე ჯგუფი, ხშირად იგივე მომწოდებელი. ხელით merge ლოგიკურია — risk დაბალი (იგივე პროდუქტია, აგრეგატი უბრალოდ აერთიანებს).

**3) Ambiguous (~10%, 119 barcode) — საზღვრული.**

ტრიგერი — ან მცირე name length (SequenceMatcher არასტაბილური), ან Megaplus-ის placeholder ჯგუფი („3000 | მეორადი ვადაგასული I", „1102 | შესაფუთი მასალა (ქვეჯგუფი)", „ფეხსაცმელი" — ამ ბოლო placeholder-ი food items-ზე გვხვდება!), ან English↔Georgian sample mismatch.

**ბიზნეს რისკი per type:**

| ტიპი | რისკი | რატომ |
|---|---|---|
| **Type A** | LOW (აგრეგატი ერთობდეს, ფინანსურად სწორი) | იგივე პროდუქტი — ფაქტურა, გაყიდვა, მარჟა ცხრილში გაბნეულია, მაგრამ summed-აპ თანხა ნამდვილია |
| **Type B** | **HIGH** (cross-contamination ცრუ ერთიანდება) | ერთი fizიკური კოდი, სრულიად სხვა პროდუქტები — ფაქტურა „ბალი 100ც"-ისა შეიძლება მიენიჭოს „ყველი სულგუნი"-ს, მარჟა ცრუდ გამოვიდეს, dead-stock ანალიზი ცრუ-პროდუქტს მიჰყვეს |
| **Ambiguous** | UNKNOWN | ცალკე ხელით განხილვის გარეშე ვერ ვიტყვი |

**Type B-ის ფესვი** (ცხადია sample-დან): Megaplus-ის auto-barcode-generation-ი არ ცვლის უნიკალურობას მთელი catalog-ის მასშტაბით. ოპერატორი ქმნის ახალ პროდუქტს („ცომი ფენოვანი რერა 1კგ"), სისტემა ენიჭება შიდა კოდს `2610389000003`, რომელიც წინა წელს უკვე მინიჭებული იყო „ეკლერი"-ს. ფაქტურა-გაყიდვა-cost-ი ერთიდაიგივე barcode-ით ცურავს ხან ერთ პროდუქტს, ხან მეორეს.

---

## 8.7 ცხადი open question (next-step decision — fix-ი არ ვთავაზობ)

Type A / Type B / Ambiguous ცხადია. Counts ცხადია. Sample ცხადია. Spot-check ცხადია.

**შენ უნდა გადაწყვიტო შემდეგი ნაბიჯი:**

1. **Type B-ის ცოცხალი აქტივობა გავზომოთ** — რამდენი 769 Type B barcode-დან მოდის ცოცხალ GET (ფაქტურა) ან ORDERS (გაყიდვა) მოძრაობას ბოლო 12 თვეში? რა ფინანსური ღირებულება ხდება affected? (~30 წთ ცალკე SQL).

2. **Ambiguous-ის ხელით განხილვა** — 119 barcode-ის სრული სია გადავცეთ ხელით review-სთვის (~1-2 საათი)? ან ამბიგუს კატეგორია სრულად ჩავყაროთ Type B-ში conservative defaults-ით?

3. **Type A merge candidate-ების გაშლა** — 302 Type A-ში რამდენი არის absolutely safe-merge (იგივე name post-normalize + იგივე supplier + იგივე group)?

4. **გადახვევა Phase 1 (b)-ზე** — PRODUCTS orphan resolution (3,046 product / `P_DAFAULTSUPPLIER` ცარიელი) — ხელახლა გამოვიკვლიოთ live ციფრით?

5. **სხვა მიმართულება** — შენ მითხარი.

---

**Section 8 generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — read-only preview, no fix proposed, no detector code touched**

---

# Section 9 — Type B live-activity overlay (12-month POS window)

**დამატებულია**: 2026-05-03 (იგივე session-ში) · **Phase 1, deliverable (a) extension #2** · **STRICT SCOPE — read-only**

## 9.0 მოკლე ქართული რეზიუმე — ⚠️ §8-ის risk-ის შეფასება ფიზიკურად შებრუნდა

§8.6-ში ვწერდი რომ Type B = HIGH risk (cross-contamination) და Type A = LOW risk. **ცოცხალი 12-თვიანი მონაცემი ცხადყოფს საპირისპიროს**:

| ტიპი | სრული | აქტიური 12თ | cross-contam 12თ | revenue 12თ |
|---|---|---|---|---|
| **Type A** (typing dup) | 302 | **68** (23%) | **49** | **29,434.08 ₾** |
| **Type B** (sxva პროდუქტი) | **769** | **2** (0.3%) | **0** | **0.80 ₾** |
| Ambiguous | 119 | 20 (17%) | 16 | 11,970.40 ₾ |

**ცხადია:**
- **Type B = catalog ნაგავი, არა ცოცხალი ფინანსური საფრთხე.** 769-დან მხოლოდ 2 barcode-ი აქტიურია 12 თვეში, ერთად 0.80 ₾ revenue.
- **Type A — სად არის რეალური ცოცხალი fragmentation:** 68 აქტიური barcode, 49 cross-contam, 29,434 ₾ revenue 12 თვეში.
- **Ambiguous-ის ცოცხალი ნაწილი არც ცარიელია** — 16 cross-contam, 11,970 ₾.

ცოცხალი financial damage from fragmentation = **Type A + Ambiguous active subset = ~88 cross-contam barcode, ~41,000 ₾ revenue 12 თვეში**, **არა Type B**.

Spot-check 2/2 confirmed (sample-ში მხოლოდ 2 active Type B იყო).

---

## 9.1 ცხადი definition

**Anchor**: per-store `MAX(ORD_TIMESTAMP)` (active orders).
- 1329 (დვაბზუ): `2026-05-02 13:57:36`
- 1301 (ოზურგეთი): `2026-05-02 16:16:22`

**Window**: anchor − 365 დღე.
- 1329 cutoff: `2025-05-02 13:57:36`
- 1301 cutoff: `2025-05-02 16:16:22`

**Per-P_ID metrics** (`ORDERS` JOIN `P_ID`):
- `qty_12m` = `SUM(ORD_quant)`
- `revenue_12m` = `SUM(ORD_itemprice * ORD_quant)`
- `cost_12m` = `SUM(ORD_GETPRICE * ORD_quant)`
- `lines_12m` = `COUNT(*)`

**Per-barcode classification (last 12mo)**:
- **Active** = ≥1 sale on **at least one** P_ID for that barcode (across both stores combined)
- **Cross-contaminated** = ≥1 sale on **2 or more distinct** P_IDs (could be within one store or across stores) — i.e., barcode actively splits attribution
- **Inactive** = zero sales on every P_ID

შენიშვნა: cross-contam ⊆ active. Active count = cross-contam + single-P_ID-active.

---

## 9.2 ზუსტი SQL (per store, with temp table for safety)

```sql
-- 1. Anchor + cutoff
SELECT MAX(ORD_TIMESTAMP) FROM ORDERS WHERE ORD_ACT = 1;
-- (Python: cutoff = anchor - timedelta(days=365))

-- 2. Stage all Type B P_IDs into a temp table
--    (safer than IN-list with 1500+ params; pyodbc parameter-cap risk avoided)
CREATE TABLE #typeb_pids (p_id BIGINT PRIMARY KEY);
-- bulk INSERT ... VALUES (?), (?), ...   ← all Type B P_IDs for this store

-- 3. Aggregate ORDERS for those P_IDs in last 12 months
SELECT o.ORD_P_ID,
       SUM(o.ORD_quant)                       AS qty_12m,
       SUM(o.ORD_itemprice * o.ORD_quant)     AS revenue_12m,
       SUM(o.ORD_GETPRICE  * o.ORD_quant)     AS cost_12m,
       COUNT(*)                               AS lines_12m
FROM ORDERS o
INNER JOIN #typeb_pids t ON o.ORD_P_ID = t.p_id
WHERE o.ORD_ACT = 1
  AND o.ORD_TIMESTAMP >= ?                    -- per-store cutoff
GROUP BY o.ORD_P_ID;

DROP TABLE #typeb_pids;
```

**Methodology note**: ჯერ ცადე `WHERE ORD_P_ID IN (1500+ params)` სტრატეგია — დაბრუნდა მოცულობით ანომალია (suspicious 2 active out of 3,077 P_IDs). გადავამოწმე:
1. ID space-ი ემთხვევა (`ORD_P_ID` = `PRODUCTS.P_ID`)
2. სრული lifetime check — Type B P_IDs ცოცხალი ORDERS-ში: 1 in 1329, 6 in 1301 = **7 P_ID სულ რომელიც ოდესმე გაყიდულა** (3,077-დან)
3. ე.ი. IN-list query დაბრუნდა სწორი — Type B P_IDs **ფაქტობრივად არ მოძრაობს POS-ში**

ე.ი. ცარიელი შედეგი არ იყო bug — ეს იყო ფაქტი. Temp-table approach ფინალში მაინც ვიყენე იმისთვის რომ pyodbc-ის parameter-cap იშოცი არ გამეჭიროს.

---

## 9.3 Live counts — Type B (769 barcodes, last 12 months)

| კატეგორია | რაოდენობა | წილი | რას ნიშნავს |
|---|---|---|---|
| **Active** | **2** | 0.3% | ≥1 sale ნებისმიერ P_ID-ზე |
| **Cross-contaminated** | **0** | 0.0% | ≥1 sale 2+ განსხვავებულ P_ID-ზე |
| **Inactive** | **767** | 99.7% | ნული გაყიდვა ყველა P_ID-ზე |
| **სულ** | **769** | 100% | (sanity ✓) |

**Type B P_IDs სულ catalog-ში**: 1,539 (1329) + 1,538 (1301) = **3,077 P_ID**
**Type B P_IDs ცოცხალი 12 თვეში**: მხოლოდ **2 P_ID** (ორივე ოზურგეთში, ყველა ცალცალკე barcode-ზე)
**Type B P_IDs ცოცხალი lifetime**: 7 P_ID (1 in 1329 + 6 in 1301) — სხვები არასოდეს გაყიდულა

---

## 9.4 Financial scope — active subset (2 barcode)

(Cross-contaminated subset ცარიელია, ამიტომ active subset-ის ციფრებს ვაჩვენებ.)

| მეტრიკა | მნიშვნელობა |
|---|---|
| revenue 12m | **0.80 ₾** |
| cost 12m | 0.00 ₾ |
| margin 12m | 0.80 ₾ |
| qty 12m | 1.00 ცალი |
| total order lines | 2 |
| sign-mismatched per-P_ID margins | 0 |

**Type B-ის ცოცხალი ფინანსური მასშტაბი ფაქტიურად ნულია.**

---

## 9.5 Sample (Type B active subset — 2 barcode + 4 P_ID-ის breakdown)

(Cross-contam = 0, ამიტომ sample იღებს active-ისგან.)

### Barcode #1: `2508653000005` — საფენი ბავშვის პამპერსი 6 ზომა (de-კომპლექტ.)

| store | P_ID | სახელი | group | მომწოდებელი | qty 12m | rev 12m | lines |
|---|---|---|---|---|---|---|---|
| დვაბზუ | 11254 | საფენი ბავშვის /პამპერსი/ 6 ზომა /11-25 კგ /36ც - 1ც (де-კომპლ.) | საფენი ბავშვის | დიპლომატ ჯორჯია | 0.00 | 0.00 | 0 |
| დვაბზუ | 62626 | ჩურჩხელა/ნიგვზის, რქაწითელის ბადაგში/1ც (FR) | კიტრი | ? | 0.00 | 0.00 | 0 |
| ოზურგეთი | 46813 | საფენი ბავშვის /პამპერსი/ 6 ზომა /11-25 კგ /36ც - 1ც (де-კომპლ.) | საფენი ბავშვის | დიპლომატ ჯორჯია | **1.00** | **0.80** | **1** |
| ოზურგეთი | 74747 | ჩურჩხელა/ნიგვზის, რქაწითელის ბადაგში/1ც (FR) | კიტრი | ? | 0.00 | 0.00 | 0 |

**ფესვი ცხადია**: ერთი ფიზიკური barcode (`2508653000005`) ორ სრულიად სხვადასხვა პროდუქტს ჰყავს მინიჭებული — საფენი + ჩურჩხელა (Type B = ✓). Active P_ID მხოლოდ ოზურგეთის საფენი (1 ცალი / 0.80 ₾). სხვა 3 P_ID-ი ცარიელი catalog-entry-ია.

### Barcode #2: `2602255000002` — მაფინი თაფლით + სულგუნი

| store | P_ID | სახელი | group | მომწოდებელი | qty 12m | rev 12m | lines |
|---|---|---|---|---|---|---|---|
| დვაბზუ | 7899 | მაფინი თაფლით | 3000 \| მეორადი ვადაგასული I | ? | 0.00 | 0.00 | 0 |
| დვაბზუ | 59191 | შებოლილი სულგუნი/Smoked Sulguni (FR) | ყველი ქართული | გეო-ინდუსტრია | 0.00 | 0.00 | 0 |
| ოზურგეთი | 11491 | მაფინი თაფლით | 3000 \| მეორადი ვადაგასული I | ? | 0.00 | 0.00 | **1** |
| ოზურგეთი | 86405 | შებოლილი სულგუნი/Smoked Sulguni (FR) | ყველი ქართული | გეო-ინდუსტრია | 0.00 | 0.00 | 0 |

**ფესვი**: barcode-ი ორ სრულიად სხვა პროდუქტს ჰყავს (მაფინი + სულგუნი). Active = ერთი line ოზურგეთში მაფინზე, **მაგრამ revenue/cost = 0** (Group "მეორადი ვადაგასული" — discount-ით ნულოვან ფასად ჩამოწერილი ალბათ).

---

## 9.6 Spot-check (2/2 — sample-ის ზომა)

| # | barcode | exp_rev | got_rev | exp_cost | got_cost | exp_lines | got_lines | ✓ |
|---|---|---|---|---|---|---|---|---|
| 1 | 2602255000002 | 0.00 | 0.00 | 0.00 | 0.00 | 1 | 1 | ✓ |
| 2 | 2508653000005 | 0.80 | 0.80 | 0.00 | 0.00 | 1 | 1 | ✓ |

**Result: 2/2 confirmed.** (10/10 ვერ მოხერხდა — sample-ში სულ 2 active barcode იყო.)

---

## 9.7 Comparison footnote — Type A vs B vs Ambiguous (12mo activity)

ეს ცხრილი **§8.6-ის risk-ის შეფასებას ცვლის**:

| ტიპი | სულ | active 12თ | cross-contam 12თ | revenue 12თ | რეალური ცოცხალი fragmentation? |
|---|---|---|---|---|---|
| Type A | 302 | 68 (22.5%) | **49** | **29,434.08 ₾** | ✅ კი |
| **Type B** | 769 | 2 (0.3%) | **0** | 0.80 ₾ | ❌ არა |
| Ambiguous | 119 | 20 (16.8%) | **16** | 11,970.40 ₾ | ✅ ნაწილი |
| **ჯამი (active+cc)** | 1,190 | **90** | **65** | **41,405.28 ₾** | — |

**ცოცხალი მონაცემიდან რეალური ფრაგმენტაცია (cross-contam 12mo):**
- 65 barcode (Type A: 49 + Ambig: 16)
- ერთად 12 თვეში ~41K ₾ revenue გადის ფრაგმენტული P_IDs-ით
- ბუღალტრულად: per-product margin ცრუა, dead-stock ანალიზი ცრუ, supplier-level cost ცრუ

---

## 9.8 ცხრება (plain Georgian summary)

**ფინანსურად ცრუა ცხრილებში — ფრაგმენტაციის ცოცხალი მასშტაბი:**

| რა | მნიშვნელობა |
|---|---|
| Type B (1,190 dual-frag-დან 769) ცოცხალი financial scope | **~0.80 ₾ / 12 თვე — ფაქტიურად ნული** |
| Type A ცოცხალი fragmentation revenue (49 cross-contam barcode) | **~29,434 ₾ / 12 თვე** |
| Ambiguous ცოცხალი fragmentation revenue (16 cross-contam barcode) | **~11,970 ₾ / 12 თვე** |
| **ჯამი — რეალური ცოცხალი ცრუობის მასშტაბი** | **~41,405 ₾ / 12 თვე (65 barcode)** |

**ინტერპრეტაცია:**

§8-ის გადახედვა **საჭიროა**. Type B-ის HIGH risk classification იყო hypothesis — ცოცხალმა მონაცემმა შეცვალა. რეალური სურათი:

1. **Type B = catalog ჰიგიენის problem** (768 dormant duplicate row + ~3K dead P_ID) — ბინძური catalog, მაგრამ ფინანსურად ცარიელი. Risk = დაბალი / cosmetic. POS workflow-ის გასწორება (uniqueness check internal-code-ისთვის) ხელმძღვანელობს მომავლის prevention-ს, არა ისტორიული ფინანსური damage-ის repair-ს.

2. **Type A + Ambiguous active subset = რეალური ცოცხალი damage** (65 cross-contam barcode, ~41K ₾/year). აქ შეიძლება pipeline aggregation per-P_ID მართლაც ცრუობდეს per-product margin/cost-ს. ხელით merge ან automated dedup აქ უფრო ფინანსური value-ით ვრცელდება.

3. **Risk-ის სიძლიერის-მიხედვით rank-ი (ცოცხალი 12-თვიანი მონაცემი):**
   - 🔥 Type A active + cross-contam (49 barcode, 29K ₾): ცხადი fix candidate
   - 🟡 Ambiguous active + cross-contam (16 barcode, 12K ₾): ცალკე ხელით review-ის შემდეგ
   - 🟢 Type B (769 barcode, 0.80 ₾): catalog cleanup, financial signal არ აქვს

---

## 9.9 ცხადი open question (next-step decision — fix-ი არ ვთავაზობ)

ცოცხალი ფინანსური სურათი ცხადია. §8-ის risk-ი ცოცხალმა მონაცემმა შეცვალა. შენ უნდა გადაწყვიტო:

1. **Type A active subset-ის drill-down** (49 cross-contam barcode, 29K ₾/year): რომელი მომწოდებელი/ჯგუფი დომინირებს? რომელი barcode-ს უმაღლესი individual revenue-ი აქვს? (~30 წთ ცალკე SQL)

2. **Ambiguous active subset-ის ხელით review** (16 cross-contam barcode, 12K ₾/year): ცხრილით გადავცეთ შენთვის ხელით სწორი class-ის ასარჩევად?

3. **Type B catalog cleanup-ის separate plan** — financial damage არ არის, მაგრამ catalog hygiene problem-ი ცოცხალია. POS-ის uniqueness check-ის თემა (preventive) — ცალკე sprint?

4. **გადახვევა Phase 1 (b)-ზე** — PRODUCTS orphan resolution (3,046 product / `P_DAFAULTSUPPLIER` ცარიელი) — ხელახლა გამოვიკვლიოთ live ციფრით?

5. **სხვა მიმართულება** — შენ მითხარი.

---

**Section 9 generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — read-only, no fix proposed, no detector code touched. §8.6 risk assessment overturned by §9 live data — see §9.0 / §9.7 / §9.8.**

---

# Section 10 — Type A active cross-contamination drill-down

**დამატებულია**: 2026-05-03 (იგივე session-ში) · **Phase 1, deliverable (a) extension #3** · **STRICT SCOPE — read-only**

## 10.0 მოკლე ქართული რეზიუმე

49 Type A cross-contaminated barcode (≥2 active P_ID 12 თვეში) **კონცენტრირებულია**:

- **Top-1 supplier (კოკა-კოლა ბოთლერს ჯორჯია)** = 26% revenue (7,333 ₾, 6 barcode)
- **Top-3 supplier** = 57% revenue (16,018 ₾)
- **Top-5 supplier** = 71% revenue
- **Top-10 supplier** = 92% revenue
- სულ 20 distinct supplier (ე.ი. ფარული long-tail არ არის)

**Top-3 group root** (ჩიფსი / წყალი / გაყინული) = **41% revenue**.

ეს **არ არის გაბნეული ოპერატორ-pattern** მთელი catalog-ის მასშტაბით. ეს არის **specific-supplier pattern** — high-volume bottler-ები + snack distributor-ები (ცვალებადი SKU variants, season/promo rollout-ის შემდეგ ოპერატორი თვითონ ცვლის variant-ს catalog-ში არსებულის გამოყენების ნაცვლად).

**Spot-check 10/10 confirmed.**

**Reconciliation footnote**: §9.7-ში ვნახე "Type A revenue 12m = 29,434.08 ₾" — ეს იყო **ყველა 68 active Type A barcode**, არა მხოლოდ cross-contam subset. ეს Section-ი მუშაობს **49 cross-contam subset-ზე** = **28,153.43 ₾**. სხვაობა (1,281 ₾) იყო 19 singleton-active barcode (ერთ P_ID-ზე გაყიდვით, fragmentation ცოცხლად არ ცრუობს).

---

## 10.1 Scope + methodology

**Scope**: 49 barcode რომლებიც:
- §8-ის Type A კლასიფიკაციაში მოხდნენ (typing duplicate, იგივე product)
- §9-ის 12mo activity overlay-ში cross-contaminated-ად მოინიშნენ (≥2 P_ID-ი ცოცხალი)

**12mo window**: per-store anchor `MAX(ORD_TIMESTAMP)` − 365 დღე (იხ. §9.1).

**Per-barcode metric**: combined revenue/qty/cost ყველა P_ID-დან (ორივე მაღაზია).

**Total live revenue**: 28,153.43 ₾ / 12 თვე (49 barcode).

---

## 10.2 Per-barcode breakdown (49 ხაზი, sorted by combined revenue desc)

| # | barcode | სახელი (canonical) | მომწოდებელი | group root | P_ID 1329 | rev 1329 | qty 1329 | P_ID 1301 | rev 1301 | qty 1301 | **სულ rev** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4860101980320 | პილმენი დიდგორი ციმბირული 800 გრ | შავნაბადა | ნახევარფაბრ. | (multi) | 2,038.80 | 229 | (multi) | 966.20 | 106 | **3,005.00** |
| 2 | 54492790 | გაზ.სასმელი კოკა კოლა ალუბალი 0.5ლ პეტი | კოკა-კოლა | გაზ | (multi) | 1,443.60 | 802 | (multi) | 1,085.40 | 603 | **2,529.00** |
| 3 | 5449000329738 | 5ლ მინერ. წყალი მთის (2ც) | კოკა-კოლა | წყალი | (multi) | 1,583.40 | 377 | (multi) | 756.00 | 168 | **2,339.40** |
| 4 | 4690388123635 | ლეისი რიბეის სტეიკი წიწაკის სოუსის გემოთი 140გრ | ქართული სადისტრ. | ჩიფსი | (multi) | 804.00 | 134 | (multi) | 691.60 | 118 | **1,495.60** |
| 5 | 4850021590068 | არაყი რადუგა ხლებნაია 1ლ | 3G-Georgian Global | არაყი | (multi) | 825.60 | 32 | (multi) | 442.00 | 17 | **1,267.60** |
| 6 | 4650054710552 | ზეთი მზესუმზირის რუსკოე მასლო 1ლ | ჯიბე | ზეთი | (multi) | 787.65 | 156 | (multi) | 312.00 | 60 | **1,099.65** |
| 7 | 5449000329721 | 3ლ მინერ. წყალი მთის (4ც) | კოკა-კოლა | წყალი | (multi) | 642.00 | 214 | (multi) | 387.00 | 129 | **1,029.00** |
| 8 | 4860101980245 | ვარენიკი იმერული სახაჭაპურე გულსართით 800 გრ | შავნაბადა | გაყინული | (multi) | 727.60 | 68 | (multi) | 286.20 | 27 | **1,013.80** |
| 9 | 4690388119157 | ლეისი ნატურალური კარტოფილ ჩიფსი არაჟანი მწვანილი | იბერია რეფრეშმ. | ჩიფსი | (multi) | 584.10 | 177 | (multi) | 422.40 | 128 | **1,006.50** |
| 10 | 5449000331496 | ცივი ჩაი Fuse Tea დრაკონის და ვნების ხილი 0.5ლ | კოკა-კოლა | ცივი | (multi) | 483.75 | 215 | (multi) | 479.15 | 231 | **962.90** |
| 11 | 8690624203950 | სიმინდის ჩიფსი დორიტოს შოთსი ფლემინ ჰოთი 23გ | იბერია რეფრეშმ. | ჩიფსი | (multi) | 447.15 | 390 | (multi) | 507.40 | 496 | **954.55** |
| 12 | 8690624203394 | სიმინდის ჩიფსი დორიტოს შოთსი მექსიკანო ცხარე 23გ | იბერია რეფრეშმ. | ჩიფსი | (multi) | 497.75 | 434 | (multi) | 436.05 | 426 | **933.80** |
| 13 | 4690388116125 | ლეისი ნატურალური კარტოფილის ჩიფსი არაჟან-მწვანილი | იბერია რეფრეშმ. | ჩიფსი | (multi) | 388.80 | 216 | (multi) | 410.40 | 228 | **799.20** |
| 14 | 4620017454847 | კამფეტი გლეისი შოკოლადესი გემთ 500გ (FR) | კადევე საქართველო | კანფეტი | (multi) | 420.60 | 62 | (multi) | 225.75 | 16.5 | **646.35** |
| 15 | 4860101980153 | კატლეტი დიდგორი 600გრ | შავნაბადა | ნახევარფაბრ. | (multi) | 533.20 | 62 | (multi) | 104.40 | 12 | **637.60** |
| 16 | 4670161190894 | პრიანიკი მინი იაშკინო ჟოლოს შიგთავსით 300გრ | დეილი | ორცხობილა | (multi) | 249.00 | 60 | (multi) | 332.40 | 77 | **581.40** |
| 17 | 4607109844731 | დაფასოებული შოკოლადი იარჩე არაქისით 500გრ | კადევე საქართველო | კანფეტი | (multi) | 422.80 | 59 | (multi) | 152.00 | 9.5 | **574.80** |
| 18 | 4860103352088 | ლიმონათი ზედაზენი ფეიხო 2 ლ პეტი | ზედაზენი 2012 | გაზ | (multi) | 456.00 | 96 | (multi) | 58.80 | 12 | **514.80** |
| 19 | 4670161190900 | თაფლაკვერი მინი იაშკინო მოხარშული სგუშონით 300გრ | დეილი | ორცხობილა | (multi) | 192.25 | 47 | (multi) | 242.40 | 59 | **434.65** |
| 20 | 4850033431205 | არაყი ხლებნაია რადუგა 0.500 | 3G-Georgian Global | არაყი | (multi) | 246.50 | 17 | (multi) | 188.15 | 14 | **434.65** |
| 21 | 5449000314987 | 0.500ლ ფანტა შაქრის გარეშე მანგოს არომატით | კოკა-კოლა | გაზ | (multi) | 145.00 | 81 | (multi) | 216.00 | 120 | **361.00** |
| 22 | 8904206202379 | ასანთი ლეოპარდი 100ბლ 10ც | დაკო ტრეიდ | 0720 | (multi) | 305.50 | 3,055 | (multi) | 33.00 | 33 | **338.50** |
| 23 | 4690388123734 | ხრუსტიმ ბაგეტი ხბოს ხორცისა და სანელებლების 60გრ | იბერია რეფრეშმ. | სუხარი | (multi) | 159.60 | 84 | (multi) | 174.80 | 92 | **334.40** |
| 24 | 4860009627716 | მოხარშული ძეხვი ქათმის 400 გრ ±10 გრ კორიდა (FR) | კორიდა | ძეხვი | (multi) | 206.55 | 51 | (multi) | 125.20 | 32 | **331.75** |
| 25 | 4690388122829 | ორცხობილა ხრუსტიმი ბარის კოლექცია ყველის ჩხირები | ქართული სადისტრ. | სუხარი | (multi) | 180.00 | 90 | (multi) | 140.00 | 70 | **320.00** |
| 26 | 4690388122843 | ორცხობილა ხრუსტიმი ბარის კოლექცია სტეიკის და შაშხის | ქართული სადისტრ. | სუხარი | (multi) | 190.00 | 95 | (multi) | 130.00 | 65 | **320.00** |
| 27 | 082184090442 | ვისკი ჯეკ დენიელსი 1ლ | გდ ალკო | ვისკი | 40624,94572 | 179.90 | 2 | 75207,96117 | 99.95 | 1 | **279.85** |
| 28 | 4850015370218 | ARPA ნატ. წვ. ალუბლის 1.5ლ (6ც)(FR) | ვივა | გაპასიურ. | (multi) | 259.95 | 63 | (multi) | 9.00 | 2 | **268.95** |
| 29 | 3585550030709 | მინიონი საშუალო გოგო (12ც)(FR) | ვივა | საახალწლო | (multi) | 222.00 | 37 | (multi) | 39.20 | 7 | **261.20** |
| 30 | 4630024630653 | LBP ბიზნეს ლანჩი 45გრ*100 საქონლის ბულიონი კვერცხ. | დეილი | სწრაფი | (multi) | 193.05 | 297 | (multi) | 54.40 | 68 | **247.45** |
| 31 | 4850015370225 | ARPA ნატ. წვ. მულტიფრუტი 1.5ლ (6ც)(FR) | ვივა | გაპასიურ. | (multi) | 209.15 | 51 | (multi) | 29.80 | 7 | **238.95** |
| 32 | 4760164790570 | ნამცხვარი ბონიტა კენკრის ნარევით (0.260 X 12) | გრეიდი | ტორტი | (multi) | 183.75 | 35 | (multi) | 46.80 | 9 | **230.55** |
| 33 | 4607001776512 | ყავა იაკობს მონარქი ინტენზა ხსნადი (შუშა) 95 გრ | მეგაკო | ყავა | (multi) | 159.50 | 10 | (multi) | 67.20 | 4 | **226.70** |
| 34 | 4620017454939 | შოკოლადის კანფეტი ჯეთსი ორცხობილით 500 გრ | კადევე საქართველო | კანფეტი | (multi) | 194.10 | 32 | (multi) | 27.20 | 2 | **221.30** |
| 35 | 4630024630684 | ლაფშა ბიზნეს ლანჩი ქათმის ლაფშა კვერცხით თეფში 90გრ | დეილი | სწრაფი | (multi) | 184.80 | 77 | (multi) | 14.00 | 5 | **198.80** |
| 36 | 025616042138 | ცივი ყავა მისტერ ბრაუნი ვანილით 0.240ლ | ქართული სადისტრ. | ცივი | 21654,94576 | 59.88 | 12 | 58461,96124 | 123.60 | 24 | **183.48** |
| 37 | 4630024630691 | ლაფშა ბიზნეს ლანჩი საქონლის ლაფშა კვერცხით თეფში 90გრ | დეილი | სწრაფი | (multi) | 161.60 | 65 | (multi) | 19.80 | 9 | **181.40** |
| 38 | 8690879425831 | გუდბეიბი საბავშვო სველი სახოცი პლასტიკური სახურით 120ც | დ&ლ სერვისი | სველი | (multi) | 120.00 | 48 | (multi) | 58.85 | 22 | **178.85** |
| 39 | 4850015370249 | ARPA ნატ. წვ. ფორთოხლის 1.5ლ (6ც)(FR) | ვივა | გაპასიურ. | (multi) | 149.90 | 34 | (multi) | 17.10 | 4 | **167.00** |
| 40 | 4820182061684 | მიწის თხილი ბიგ ბობი საქონლის ხორცით + აჯიკის არომატით | პარტნიორი (400132192) | მიწის | (multi) | 34.50 | 10 | (multi) | 128.70 | 39 | **163.20** |
| 41 | 4710487017038 | ცივი ყავა MOON WALKER კაპუჩინო 0.240მლ (FR) | კანტი | ცივი | (multi) | 81.70 | 19 | (multi) | 54.00 | 12 | **135.70** |
| 42 | 4710487017021 | ცივი ყავა MOON WALKER ამერიკანო+რძე 0.240მლ (FR) | კანტი | ცივი | (multi) | 73.10 | 17 | (multi) | 58.10 | 13 | **131.20** |
| 43 | 4850015370584 | ARPA ნატ. წვ. ვაშლის 1.5ლ (6ც)(FR) | ვივა | გაპასიურ. | (multi) | 112.20 | 24 | (multi) | 12.60 | 3 | **124.80** |
| 44 | 4860020002424 | 0.5ლ შუშა წყალი გაზიანი მთის (12ც) | კოკა-კოლა | მინერალური | (multi) | 86.00 | 43 | (multi) | 25.50 | 17 | **111.50** |
| 45 | 5901069000442 | შპროტი შებოლილი LOSOS ზეთით 170გ შ*16 | ფიგარო | თევზის | (multi) | 78.75 | 15 | (multi) | 24.25 | 5 | **103.00** |
| 46 | 4680021887758 | ორცხობილა ფხვიერი ბონფეტი ფერადი დრაჟეთი 200გრ | კადევე საქართველო | ორცხობილა | (multi) | 29.70 | 9 | (multi) | 62.20 | 19 | **91.90** |
| 47 | 4607109844762 | შოკოლადის კანფეტი ჯაზი მიწის თხილი + კარამელი 500გრ | კადევე საქართველო | კანფეტი | (multi) | 53.05 | 9 | (multi) | 12.90 | 1 | **65.95** |
| 48 | 4607109844755 | შოკოლადის კანფეტი ჯაზი 500გრ | კადევე საქართველო | შოკოლადის | (multi) | 43.80 | 8 | (multi) | 12.50 | 1 | **56.30** |
| 49 | 8008970055831 | შამუპუნი ვოშენდ-გოუ დაზიანებული თმის 180მლ | შაბა | შამპუნი | (multi) | 12.50 | 2 | (multi) | 7.00 | 1 | **19.50** |
| **ჯამი** | | | | | | **17,891.78** | **8,425** | | **10,261.65** | **3,909** | **28,153.43** |

შენიშვნა: "(multi)" ნიშნავს ერთი მაღაზიის შიგნით 2+ P_ID-ი — სრული P_ID სია სიგრძის გამო ცხრილს არ ვტვირთავ. სრული breakdown ცოცხალი DB-დან რეპროდუცირებადია §9.2-ის SQL-ით.

---

## 10.3 Rollup A — by supplier (revenue equally split if multi-supplier per barcode)

| # | მომწოდებელი | barcode-ები | revenue 12m | qty 12m | წილი |
|---|---|---|---|---|---|
| 1 | **კოკა-კოლა ბოთლერს ჯორჯია შპს** | 6 | **7,332.80** | 3,000 | **26.0%** |
| 2 | **შავნაბადა შპს** | 3 | **4,656.40** | 504 | **16.5%** |
| 3 | **იბერია რეფრეშმენტსი სს** | 5 | **4,028.45** | 2,671 | **14.3%** |
| 4 | ქართული სადისტრიბუციო-მარკეტინგული კომპანია | 4 | 2,319.08 | 608 | 8.2% |
| 5 | 3G-Georgian Global Group შპს | 2 | 1,702.25 | 80 | 6.0% |
| 6 | კადევე საქართველო შპს | 6 | 1,656.60 | 228 | 5.9% |
| 7 | დეილი შპს | 5 | 1,643.70 | 764 | 5.8% |
| 8 | ჯიბე შპს | 1 | 1,099.65 | 216 | 3.9% |
| 9 | ვივა (VIVA შპს) | 5 | 1,060.90 | 232 | 3.8% |
| 10 | ზედაზენი 2012 შპს | 1 | 514.80 | 108 | 1.8% |
| 11 | დაკო ტრეიდ შპს | 1 | 338.50 | 3,088 | 1.2% |
| 12 | კორიდა შპს | 1 | 331.75 | 83 | 1.2% |
| 13 | გდ ალკო შპს | 1 | 279.85 | 3 | 1.0% |
| 14 | კანტი შპს | 2 | 266.90 | 61 | 0.9% |
| 15 | გრეიდი შპს | 1 | 230.55 | 44 | 0.8% |
| 16 | მეგაკო შპს | 1 | 226.70 | 14 | 0.8% |
| 17 | დ&ლ სერვისი შპს | 1 | 178.85 | 70 | 0.6% |
| 18 | პარტნიორი შპს (400132192) | 1 | 163.20 | 49 | 0.6% |
| 19 | ფიგარო შპს | 1 | 103.00 | 20 | 0.4% |
| 20 | შაბა შპს | 1 | 19.50 | 3 | 0.1% |
| **სულ** | | **20** distinct | **28,153.43** | — | 100% |

---

## 10.4 Rollup B — by P_GROUP root (revenue equally split if multi-group)

| # | P_GROUP root | barcode-ები | revenue 12m | qty 12m | წილი |
|---|---|---|---|---|---|
| 1 | **ჩიფსი** | 6 | **5,356.85** | 2,835 | **19.0%** |
| 2 | **წყალი** | 3 | **3,424.15** | 918 | **12.2%** |
| 3 | **გაყინული** | 3 | **2,835.10** | 299.5 | **10.1%** |
| 4 | ნახევარფაბრიკატები | 2 | 1,821.30 | 204.5 | 6.5% |
| 5 | გაზ | 3 | 1,702.40 | 857 | 6.0% |
| 6 | არაყი | 2 | 1,702.25 | 80 | 6.0% |
| 7 | კანფეტი | 6 | 1,623.62 | 210.2 | 5.8% |
| 8 | კოლა | 2 | 1,445.00 | 803 | 5.1% |
| 9 | ცივი (coffee/tea) | 4 | 1,413.28 | 543 | 5.0% |
| 10 | ორცხობილა | 3 | 1,107.95 | 271 | 3.9% |
| 11 | ზეთი | 1 | 1,099.65 | 216 | 3.9% |
| 12 | სუხარი | 3 | 807.20 | 408 | 2.9% |
| 13 | გაპასიურებულები | 4 | 399.85 | 94 | 1.4% |
| 14 | წვენი (juice) | 4 | 399.85 | 94 | 1.4% |
| 15 | ძეხვი | 1 | 331.75 | 83 | 1.2% |
| ... | (ბოლო 21 ჯგუფი) | | 1,432.54 | | 5.1% |
| **სულ** | | **36** distinct | **28,153.43** | — | 100% |

---

## 10.5 Rollup C — concentration metrics

| მეტრიკა | მნიშვნელობა |
|---|---|
| **სრული revenue 12mo** | **28,153.43 ₾** |
| Distinct მომწოდებლები | **20** |
| Distinct group root-ები | **36** |
| Top-1 supplier (კოკა-კოლა) | 7,332.80 ₾ — **26.0%** |
| **Top-3 supplier total** | **16,017.65 ₾** — **56.9%** |
| Top-5 supplier total | 20,038.98 ₾ — 71.2% |
| Top-10 supplier total | 26,014.63 ₾ — 92.4% |
| Top-1 group (ჩიფსი) | 5,356.85 ₾ — 19.0% |
| **Top-3 group total** | **11,616.10 ₾** — **41.3%** |
| Top-5 group total | 15,139.80 ₾ — 53.8% |

---

## 10.6 Spot-check (10/49 random)

random.seed(99). ყოველი ხაზისთვის — independent re-fetch DB-დან, აქტიური P_ID count + revenue + cost + lines შემოწმება.

| # | barcode | exp_rev | got_rev | exp_active_pids | got | exp_lines | got | ✓ |
|---|---|---|---|---|---|---|---|---|
| 1 | 4820182061684 | 163.20 | 163.20 | 2 | 2 | 63 | 63 | ✓ |
| 2 | 4760164790570 | 230.55 | 230.55 | 2 | 2 | 47 | 47 | ✓ |
| 3 | 4650054710552 | 1,099.65 | 1,099.65 | 2 | 2 | 225 | 225 | ✓ |
| 4 | 5449000314987 | 361.00 | 361.00 | 2 | 2 | 205 | 205 | ✓ |
| 5 | 4630024630691 | 181.40 | 181.40 | 2 | 2 | 76 | 76 | ✓ |
| 6 | 4670161190900 | 434.65 | 434.65 | 2 | 2 | 107 | 107 | ✓ |
| 7 | 4680021887758 | 91.90 | 91.90 | 2 | 2 | 29 | 29 | ✓ |
| 8 | 4620017454939 | 221.30 | 221.30 | 2 | 2 | 37 | 37 | ✓ |
| 9 | 4607109844755 | 56.30 | 56.30 | 2 | 2 | 12 | 12 | ✓ |
| 10 | 4690388116125 | 799.20 | 799.20 | 2 | 2 | 446 | 446 | ✓ |

**Result: 10/10 confirmed.**

---

## 10.7 ცხრება — pattern observation

**კონცენტრაცია მაღალია, არა გაბნეული.**

| signal | მნიშვნელობა | ინტერპრეტაცია |
|---|---|---|
| Top-3 supplier-ის წილი | **57%** | concentrated, არა long-tail |
| Top-5 supplier-ის წილი | 71% | მცირე ბირთვი დომინირებს |
| Top-10 supplier-ის წილი | 92% | "ფარული" გაბნეული მომწოდებლები არ არსებობს |
| Distinct supplier-ები | 20 | ვიწრო — fix-ი ფოკუსირებადია |
| Distinct group root-ები | 36 | უფრო გაბნეული, მაგრამ Top-3 ჯგუფი (ჩიფსი/წყალი/გაყინული) = 41% |

**ცხადი pattern (sample-დან):**

1. **High-volume bottlers** (კოკა-კოლა 26% / 6 barcode) — Coca-Cola line-ი ცვლის variant-ებს ხშირად (Fuse Tea ვარიანტები, Fanta ცვლადი არომატები, წყლის ცვლადი მოცულობები). ოპერატორი ხშირად ქმნის ახალ entry-ს ნაცვლად არსებული barcode-ის reuse-ისა.

2. **Snack distributor-ები** (იბერია რეფრეშმენტსი 14% / 5 barcode + ქართული სადისტრიბ. 8% / 4 barcode = 22%) — Lays, Doritos, ხრუსტიმი — flavor-ის ცვლა promo cycle-ით. Pattern-ი იგივე.

3. **Frozen pre-prepared** (შავნაბადა 17% / 3 barcode) — დიდგორის პელმენი/ვარენიკი/კატლეტი — packaging-ის რესტ-ი ცვლის barcode-მდე entry duplicate-ს ცხადყოფს.

**ფინანსური damage per category:**
- **ჩიფსი** (19%, 5,357 ₾) — ცალკე rich subset, აშკარად მიზანმიმართული fix
- **წყალი** (12%, 3,424 ₾) — Coca-Cola-ს მიერ
- **გაყინული** (10%, 2,835 ₾) — შავნაბადა-ს მიერ

3 ეს ჯგუფი ერთად = **41%**, 12 barcode.

**მნიშვნელოვანი observation:** ფრაგმენტაცია არ არის "ოპერატორ-ერორი generic", ეს არის **specific-supplier რეცეპტი** — ცვალებადი variant-ების კატალოგ-მენეჯმენტი ცუდად სრულდება გარკვეული მომწოდებლების SKU-ებზე. ფიქს-ი per-supplier უფრო მცირე scope-ში ფიქსდება ვიდრე mass-merge.

---

## 10.8 ცხადი open question (next-step decision — fix-ი არ ვთავაზობ)

49 cross-contam barcode-ის full breakdown ცხადია. Concentration ცხრილი ცხრილში. Spot-check 10/10. შენ უნდა გადაწყვიტო:

1. **Top-3 supplier-ზე (Coca-Cola + შავნაბადა + იბერია = 57%) ცალკე გადახედვა** — ფიქს-ი ფინანსურად კონცენტრირებული; ერთჯერადი per-supplier merge რა აშორებს ცრუობას?

2. **გადახდა-შესაფუთი დონეზე analysis** — არის თუ არა ფრაგმენტაცია ფიზიკური SKU-ის variation-ის გამო (e.g. 0.5ლ vs 0.330ლ კოკა-კოლა) თუ წმინდა typing duplicate?

3. **Ambiguous (16 cross-contam, 12K ₾) ცალკე drill-down**, იგივე format-ით?

4. **გადახვევა Phase 1 (b)-ზე** — PRODUCTS orphan resolution (3,046 product / `P_DAFAULTSUPPLIER` ცარიელი) — ხელახლა გამოვიკვლიოთ live ციფრით?

5. **სხვა მიმართულება** — შენ მითხარი.

---

**Section 10 generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — read-only, no fix proposed, no detector code touched**

---

# Section 11 — Type A subtype split: typing-dup vs SKU variant

**დამატებულია**: 2026-05-03 (იგივე session-ში) · **Phase 1, deliverable (a) extension #4 — research-CLOSED step** · **STRICT SCOPE — read-only**

## 11.0 მოკლე ქართული რეზიუმე

49 Type A cross-contam barcode-ი უფრო ღრმად დავყავი ორ ფესვ-კატეგორიად + საზღვრული:

| Subtype | Barcodes | % count | Revenue 12m | % rev | რას ნიშნავს fix-isthvis |
|---|---|---|---|---|---|
| **TYPING_DUP** | 12 | 24% | 3,325 ₾ | 12% | ერთიდაიგივე პროდუქტი — **მარტივი merge**-ის კანდიდატი |
| **SKU_VARIANT** | **33** | **67%** | **20,097 ₾** | **71%** | სხვადასხვა SKU ერთი barcode-ით — **ნაივი merge შეუძლებელია** |
| BORDERLINE | 4 | 8% | 4,731 ₾ | 17% | ხელით განხილვა საჭირო (ხშირად supplier-side error) |
| **სულ** | 49 | 100% | 28,153 ₾ | 100% | |

**მთავარი finding (fix-strategy-ს ცვლის):** Type A cross-contam-ის უმრავლესობა (67% count, 71% revenue) არ არის typing-dup, არიან **SKU variants** — ერთი ფიზიკური barcode ცოცხალი სხვადასხვა SKU-ზე (განსხვავებული მოცულობა, packaging, შემავსებელი). naive merge ფინანსურად დააზიანებდა — ეს რეალურად სხვა პროდუქტებია.

**Spot-check 10/10 confirmed.**

**Methodology note**: ჯერ ცადე aggressive-normalize-ი (lowercase + dot-strip) numeric token extraction-ისთვის — ცარიელი dot აშორებდა "0.240ლ"-ს ცალცალკე "0" + "240ლ"-ად, false numeric divergence. **გასწორდა** — numeric extraction ახლა მხოლოდ NFC + casefold-ით (dot შენარჩუნებული). გასწორების შემდეგ TYPING_DUP 11 → 12, SKU_VARIANT 34 → 33 (1 barcode გადაინაცვლა — `025616042138` ცივი ყავა მისტერ ბრაუნი 240მლ ≡ 0.240ლ).

---

## 11.1 ცხადი definition (subtype criterion)

**გამოყენებული ნორმალიზაცია:**

```
AGGRESSIVE-canonical name (for similarity comparison):
  NFC + casefold + drop (FR)/(G)/(BP)/(II) tags + drop punctuation + collapse whitespace

NUMERIC tokens (for SKU divergence detection):
  Run on RAW name (NFC + casefold ONLY — keep dots/commas)
  Match: \d+([.,]\d+)? + optional unit (ლ, მლ, გრ, კგ, გ, ც, ბლ, x/×)
  Cross-unit normalization:
    240მლ ≡ 0.240ლ ≡ ('vol_ml', 240) ≡ ('vol_l', 0.24)  ← canonical equality
    500გრ ≡ 0.5კგ ≡ ('mass_g', 500)
  "bare" numbers (no unit) — not used for divergence (likely codes/IDs, not SKU markers)
  Multiplier (108X, 16X) — NOT excluded; can indicate package count
```

**Subtype rules:**

| AGG_SIM | NUM_DIVERGENCE | → Subtype |
|---|---|---|
| ≥ 0.85 | False | **TYPING_DUP** |
| 0.83 ≤ sim < 0.87 | False | **BORDERLINE** (right at edge) |
| 0.60 ≤ sim < 0.85 | False | **SKU_VARIANT** |
| any sim | True | **SKU_VARIANT** (volume/mass/count differs) |
| sim < 0.60 | False | **BORDERLINE** (low sim shouldn't happen for Type A — guard) |

შენიშვნა: კრიტერიუმი deterministic + reproducible (10/10 spot-check confirmed re-classification consistency).

**კრიტერიუმის ცნობილი limitation-ები** (ცხადობისთვის):

- **სიმოკლე-ეფექტი**: მოკლე სახელებზე (e.g., "ARPA 1.5ლ") SequenceMatcher-ის ratio არასტაბილურია მცირე ცვლილებაზე
- **მრავალი variant**: ერთი barcode 3+ name variant-ით, min-pairwise sim ხდება ყველაზე-დიფერენციულ წყვილზე (conservative — bumps to SKU_VARIANT or BORDERLINE)
- **Multiplier ambiguity**: "108X" ხშირად package-count descriptor-ია (case quantity), არა SKU differentiator — ჩემი class-ი მაინც divergence-ად მიიღებს
- **Long supplier strings inside name**: e.g., "5182647560 ორცხობილა..." — bare number-ი filter-ით გავიცანი, არ ცრუდებს

---

## 11.2 ზუსტი ლოგიკა (Python კლასიფიკატორი)

```python
import re, unicodedata
from difflib import SequenceMatcher

PAREN_TAGS = re.compile(r'\((?:FR|G|BP|II|FR\)|R)\)?\s*', re.IGNORECASE)
PUNCT_AGG  = re.compile(r"[/\\\-_,.\"\'()*\[\]&+]+")
WHITESPACE = re.compile(r"\s+")
NUM_UNIT_RE = re.compile(
    r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>ლ|მლ|გრ|კგ|გ|ც|ბლ|x|х|×)?",
    re.IGNORECASE,
)

def normalize_aggressive(s):
    s = unicodedata.normalize("NFC", s or "").casefold()
    s = PAREN_TAGS.sub(" ", s); s = PUNCT_AGG.sub(" ", s)
    return WHITESPACE.sub(" ", s).strip()

def to_canonical_volume(num_str, unit):
    val = float(num_str.replace(",", "."))
    out = set()
    if unit in ("ლ",):    out |= {("vol_ml", round(val*1000)), ("vol_l", round(val,3))}
    elif unit in ("მლ",): out |= {("vol_ml", round(val)),       ("vol_l", round(val/1000,3))}
    elif unit in ("კგ",): out |= {("mass_g", round(val*1000)),  ("mass_kg", round(val,3))}
    elif unit in ("გრ","გ"): out |= {("mass_g", round(val)),    ("mass_kg", round(val/1000,3))}
    elif unit in ("ც",):  out.add(("count_pcs", round(val)))
    elif unit in ("ბლ",): out.add(("count_blocks", round(val)))
    elif unit in ("x","х","×"): out.add(("multiplier", round(val)))
    else:                  out.add(("bare", round(val,3)))
    return out

def extract_volume_set(name):
    # CRITICAL: run on RAW name (NFC + casefold), NOT aggressive-normalized
    s = unicodedata.normalize("NFC", name or "").casefold()
    out = set()
    for m in NUM_UNIT_RE.finditer(s):
        out |= to_canonical_volume(m.group("num"), m.group("unit") or "")
    return out

def num_token_divergence(names):
    sets = {n: {t for t in extract_volume_set(n) if t[0] != "bare"} for n in names}
    nonempty = [s for s in sets.values() if s]
    if len(nonempty) <= 1: return False
    common = nonempty[0].copy()
    for s in nonempty[1:]: common &= s
    union = set().union(*nonempty)
    # canonical equality across unit pairs (240ml ≡ 0.240l)
    def canon(t):
        kind, v = t
        if kind == "vol_ml": return ("vol", v)
        if kind == "vol_l":  return ("vol", round(v*1000))
        if kind == "mass_g": return ("mass", v)
        if kind == "mass_kg":return ("mass", round(v*1000))
        return (kind, v)
    return len({canon(t) for t in (union - common)}) > 0

def agg_sim(names):
    uniq = sorted({normalize_aggressive(n) for n in names if n})
    uniq = [n for n in uniq if n]
    if len(uniq) <= 1: return 1.0
    return min(SequenceMatcher(None, uniq[i], uniq[j]).ratio()
               for i in range(len(uniq)) for j in range(i+1, len(uniq)))

def classify_subtype(names):
    s, div = agg_sim(names), num_token_divergence(names)
    if 0.83 <= s < 0.87 and not div: return "BORDERLINE", s, div
    if s >= 0.85 and not div:        return "TYPING_DUP", s, div
    if (0.60 <= s < 0.85) or div:    return "SKU_VARIANT", s, div
    return "BORDERLINE", s, div
```

---

## 11.3 Live counts

| Subtype | Barcodes | წილი count | Revenue 12m | წილი rev |
|---|---|---|---|---|
| TYPING_DUP | 12 | 24.5% | 3,324.93 ₾ | 11.8% |
| **SKU_VARIANT** | **33** | **67.3%** | **20,097.40 ₾** | **71.4%** |
| BORDERLINE | 4 | 8.2% | 4,731.10 ₾ | 16.8% |
| **სულ** | **49** | 100% | **28,153.43 ₾** | 100% |

---

## 11.4 Supplier × subtype matrix (revenue 12m / barcode count)

| # | მომწოდებელი | TYPING_DUP | SKU_VARIANT | BORDERLINE | მთლიანი |
|---|---|---|---|---|---|
| 1 | კოკა-კოლა ბოთლერს ჯორჯია შპს | 361.00 / 1b | 6,971.80 / 5b | 0 | **7,332.80** |
| 2 | შავნაბადა შპს | 0 | 637.60 / 1b | 4,018.80 / 2b | **4,656.40** |
| 3 | იბერია რეფრეშმენტსი სს | 0 | 4,028.45 / 5b | 0 | **4,028.45** |
| 4 | ქართული სადისტრიბუციო-მარკეტ. | 183.48 / 1b | 2,135.60 / 3b | 0 | **2,319.08** |
| 5 | 3G-Georgian Global Group | 0 | 1,702.25 / 2b | 0 | **1,702.25** |
| 6 | კადევე საქართველო | 91.90 / 1b | 852.40 / 3b | 712.30 / 2b | **1,656.60** |
| 7 | დეილი | 1,016.05 / 2b | 627.65 / 3b | 0 | **1,643.70** |
| 8 | ჯიბე | 0 | 1,099.65 / 1b | 0 | **1,099.65** |
| 9 | **ვივა (VIVA)** | **1,060.90 / 5b** | 0 | 0 | **1,060.90** |
| 10 | ზედაზენი 2012 | 0 | 514.80 / 1b | 0 | **514.80** |
| 11 | დაკო ტრეიდ | 0 | 338.50 / 1b | 0 | **338.50** |
| 12 | კორიდა | 331.75 / 1b | 0 | 0 | **331.75** |
| 13 | გდ ალკო | 279.85 / 1b | 0 | 0 | **279.85** |
| 14 | კანტი | 0 | 266.90 / 2b | 0 | **266.90** |
| 15-20 | (sub-200 ₾ suppliers, 6 entries) | 0 | 922.10 / 6b | 0 | **922.10** |

**მნიშვნელოვანი per-supplier pattern-ები:**

- **ვივა (ARPA juices) — 5/5 = TYPING_DUP**, 1,061 ₾ → ხშირი (FR)-suffix variant + spacing dups, **სუფთა typing duplicate**
- **იბერია რეფრეშმენტსი — 5/5 = SKU_VARIANT**, 4,028 ₾ → Doritos/Lays packaging-format differences (case-count, box notation)
- **შავნაბადა (Didgori frozen) — 1 SKU + 2 BORDERLINE**, 4,656 ₾ → ხშირად სხვა შემავსებელი ერთ barcode-ზე (ვარენიკი ყველით vs სახაჭაპურე გულსართით) — **supplier-side error**
- **კოკა-კოლა — 1 TYPING + 5 SKU**, 7,333 ₾ → ცვალებადი size variants (3L vs 5L) catalog-ში დუბლიკატით
- **დეილი — 2 TYPING + 3 SKU**, 1,644 ₾ → mixed (LBP ბიზნეს ლანჩი variants — naming convention drift)

---

## 11.5 Sample 5+5+5

### TYPING_DUP (5 of 12) — სუფთა typing dup, იგივე პროდუქტი

| barcode | sim | num_div | rev | მომწოდებელი | სახელი variants |
|---|---|---|---|---|---|
| 4670161190894 | 1.000 | F | 581.40 | დეილი | ერთი სახელი ყველგან: "პრიანიკი მინი იაშკინო ჟოლოს შიგთავსით 300გრ" |
| **025616042138** | **0.960** | **F** | 183.48 | ქართ. სადისტრ. | "ცივი ყავა მისტერ ბრაუნი ვანილით 0.240ლ" vs "240მლ" — **ერთი მოცულობა, სხვა ერთეული** ✓ ფიქსის შემდეგ TYPING_DUP-ში გადაინაცვლა |
| 4850015370218 | 1.000 | F | 268.95 | ვივა | "ARPA ნატ. წვ. ალუბლის 1,5 ლ (6ც)" — 3 typing variant (FR-suffix, double space, etc.) |
| 4850015370249 | 1.000 | F | 167.00 | ვივა | "ARPA ნატ. წვ. ფორთოხლის 1,5 ლ (6ც)" + (FR) variant |
| 4860009627716 | 1.000 | F | 331.75 | კორიდა | ერთი სახელი: "მოხარშული ძეხვი ქათმის 400 გრ ±10 გრ კორიდა" |

→ ყველა შემთხვევაში: **იდენტური product, formatting/whitespace/(FR)-tag-ის ცვალებადობა**.

### SKU_VARIANT (5 of 33) — სხვადასხვა SKU ერთი barcode-ით

| barcode | sim | num_div | rev | მომწოდებელი | სახელი variants | რა განსხვავდება |
|---|---|---|---|---|---|---|
| 4630024630684 | 0.626 | F | 198.80 | დეილი | "LBP ბიზნეს ლანჩი 90გრ*24" vs "ლაფშა ბიზნეს ლანჩი თეფში 90გრ" | სავარაუდოდ packaging variant — case (24 ც.) vs single (თეფში) |
| 4690388122843 | 0.726 | T | 320.00 | ქართ. სადისტრ. | "ორცხობილა ხრუსტიმი 70გ" vs "ხრუსტიმი 70გ 16X" vs "სუხარიკი 70გ" | "16X" multiplier divergence + naming style |
| 8690879425831 | 0.714 | F | 178.85 | დ&ლ სერვისი | "გუდბეიბი სველი სახოცი" vs "გუდბეიბი სველი სახოცი პლასტიკური სახურით 120ც" | one variant with package count detail (120ც) |
| 4607001776512 | 0.632 | F | 226.70 | მეგაკო | "ყავა იაკობს მონარქი ინტე" vs "...ინტენზა ხსნადი (შუშა) 95 გრ" vs "...95 გრ (776512)" | partial truncated name + barcode-in-name suffix |
| 4607109844755 | 0.711 | F | 56.30 | კადევე | "კამფეტი ჯაზი 500გ (FR)" vs "შოკოლადის კანფეტი ჯაზი 500გრ" | naming convention only (კამფეტი vs შოკოლადის კანფეტი) — ეს თითქოს სუფთა typing-dup, მაგრამ sim 0.71 ≤ 0.85 → SKU_VARIANT |

→ აქ ცხადია classifier-ის შეზღუდვა: მაღალი ფიზიკური მსგავსების ზოგი case (e.g. last row) sim 0.85-ის ქვემოთ ხვდება Georgian-ის character variation-ის გამო. **classifier conservative-ია TYPING_DUP-ისკენ**.

### BORDERLINE (4 of 4 — სრული)

| barcode | sim | num_div | rev | მომწოდებელი | სახელი variants | რატომ borderline |
|---|---|---|---|---|---|---|
| 4607109844762 | 0.525 | F | 65.95 | კადევე | "კამფეტი ჯაზი ნუგა კარამელი ნუგა არახისი 0.500" vs "კანფეტი ჯაზი 500გრ" vs "შოკოლადის კანფეტი ჯაზი მიწის თხილით კარამელით 500გრ" | sim=0.52 (<0.60) — ცხადი threshold-ს ქვემოთ; სავარაუდოდ TYPING_DUP-ის long-name variant-ი, მაგრამ classifier conservative |
| 4620017454847 | 0.545 | F | 646.35 | კადევე | "კამფეტი გლეისი შოკოლადესი გემთ 500გ" vs "შოკოლადის კანფეტი გლეისი 500 გრ" | იგივე pattern — long-name vs short-name typing variant, sim conservative |
| **4860101980245** | 0.545 | F | 1,013.80 | შავნაბადა | **"ვარენიკი დიდგორი ყველით 800 გრ"** vs **"ვარენიკი იმერული სახაჭაპურე გულსართით 800 გრ"** | **სხვა შემავსებელი! Cheese ვარენიკი vs khachapuri ვარენიკი — supplier-side data error** |
| 4860101980320 | 0.836 | F | 3,005.00 | შავნაბადა | "პილმენი დიდგორი ციმბირული 800 გრ" vs "პილმენი ციმბირული 800გრ" | sim 0.84 — ზუსტად borderline-ის ქვედა ზღვარზე; brand "დიდგორი" with/without — typing variant |

→ Borderline ჯგუფი mixed: **2 conservative-classified (კადევე)** რომლებიც სავარაუდოდ TYPING_DUP, **1 supplier-error (შავნაბადა ვარენიკი)** რომელიც სრულიად სხვა-პროდუქტური case-ია, **1 brand-suffix typing var (შავნაბადა პილმენი)**.

---

## 11.6 Spot-check (10/49 random — classification reproducibility)

random.seed(99). Each barcode: independent re-fetch names from BOTH stores, re-run classifier, compare exp/got triple (subtype, sim, div).

| # | barcode | exp subtype | got subtype | exp sim | got sim | exp div | got div | ✓ |
|---|---|---|---|---|---|---|---|---|
| 1 | 4820182061684 | SKU_VARIANT | SKU_VARIANT | 0.735 | 0.735 | F | F | ✓ |
| 2 | 4760164790570 | SKU_VARIANT | SKU_VARIANT | 0.630 | 0.630 | T | T | ✓ |
| 3 | 4650054710552 | SKU_VARIANT | SKU_VARIANT | 0.512 | 0.512 | T | T | ✓ |
| 4 | 5449000314987 | TYPING_DUP | TYPING_DUP | 1.000 | 1.000 | F | F | ✓ |
| 5 | 4630024630691 | SKU_VARIANT | SKU_VARIANT | 0.647 | 0.647 | F | F | ✓ |
| 6 | 4670161190900 | TYPING_DUP | TYPING_DUP | 0.872 | 0.872 | F | F | ✓ |
| 7 | 4680021887758 | TYPING_DUP | TYPING_DUP | 0.955 | 0.955 | F | F | ✓ |
| 8 | 4620017454939 | SKU_VARIANT | SKU_VARIANT | 0.694 | 0.694 | F | F | ✓ |
| 9 | 4607109844755 | SKU_VARIANT | SKU_VARIANT | 0.711 | 0.711 | F | F | ✓ |
| 10 | 4690388116125 | SKU_VARIANT | SKU_VARIANT | 0.655 | 0.655 | T | T | ✓ |

**Result: 10/10 confirmed.**

---

## 11.7 ცხრება — რა ნიშნავს fix-strategy-ისთვის

**ცხრილში დომინირებს SKU_VARIANT (67%) — ეს fix-ის approach-ს ცვლის.**

| Subtype | რეალობა | რა fix-ს ითხოვს |
|---|---|---|
| **TYPING_DUP** (12 barcode, 3,325 ₾) | იგივე product, ოპერატორმა მეორედ აკრიფა | **მარტივი merge** — combine P_IDs, accept aggregated history. LOW risk |
| **SKU_VARIANT** (33 barcode, 20,097 ₾) | სხვადასხვა SKU ერთი barcode-ით (size, package, ზოგ შემთხვევაში flavor/filling) | **ნაივი merge ფინანსურად ცრუობს** — სხვა პროდუქტებს აერთიანებს. ვარიანტები: (a) supplier-side fix რომ ცალკე barcode-ი მიენიჭოს თითოეულ SKU-ს, (b) catalog-level reorganization, (c) accept that per-barcode aggregation gives package-line summary not per-SKU |
| **BORDERLINE** (4 barcode, 4,731 ₾) | mixed — 1 supplier-side error (შავნაბადა ვარენიკი), 2 conservative-classification (კადევე) რომლებიც სავარაუდოდ TYPING_DUP, 1 brand-suffix typing var | **ხელით review per-barcode** |

**მნიშვნელოვანი ინტერპრეტაცია:**

§9-ის "Type A active fragmentation = ~29K ₾ live damage" ციფრი ცოცხალი იყო, მაგრამ §11 ცხადყოფს რომ:
- მხოლოდ ~3,325 ₾ (12%) არის სუფთა "merge საკმარისია" damage
- 20,097 ₾ (71%) რეალური SKU-divergence-ია — ეს არ არის ცრუობა dashboard-ის pipeline-ის გამო, ეს არის catalog-system limitation რომელიც ცხადობს რომ ერთ barcode-ზე რამდენიმე SKU-ის არსებობა → per-product analysis ხდება approximate
- 4,731 ₾ (17%) საზღვრული — დეტალური review

**Cocnentration per-supplier (subtype-aware):**

- **ცხადი TYPING_DUP fix candidates** (per-supplier): ვივა (ARPA juices, 5b/1,061 ₾) + დეილი (LBP, 2b/1,016 ₾) + კოკა-კოლა (1b/361 ₾) + ქართ. სადისტრ. (1b/183 ₾) + კადევე (1b/92 ₾) + კორიდა (1b/332 ₾) + გდ ალკო (1b/280 ₾) = **~3,325 ₾ across 12 barcodes**
- **SKU_VARIANT, supplier coordination needed**: კოკა-კოლა (5b/6,972), იბერია რეფრეშმენტსი (5b/4,028), ქართ. სადისტრ. (3b/2,136), 3G-Georgian (2b/1,702), ჯიბე (1b/1,100) — დიდი 5 supplier = ~16K ₾
- **Supplier-side error**: შავნაბადა ვარენიკი ყველით vs სახაჭაპურე at same barcode — 1,014 ₾, requires supplier dialogue

---

## 11.8 🛑 Research closed for deliverable (a)

**ეს არის Phase 1 — Data Quality Sprint, deliverable (a) — PRODUCTS fragmentation-ის ცოდნის ფესვებამდე ჩასვლის ბოლო ნაბიჯი.** მონაცემთა მხარე ცხადია:

- **§4–§7**: definition + count (1,525 / 1,875 / 2,210 union / 1,190 both stores)
- **§8**: Type A / B / Ambiguous classification (302 / 769 / 119)
- **§9**: live 12mo activity overlay — Type B virtually dead, Type A + Ambig actively cross-contaminated
- **§10**: Type A cross-contam drill-down — 49 barcode / 28K ₾ / Top-3 supplier 57%
- **§11**: subtype split — only 12 are simple typing-dups, 33 are real SKU variants, 4 borderline

**შემდეგი ბუნებრივი ნაბიჯი = fix-path discussion (არა მეტი drill-down).** კონკრეტული გადაწყვეტილებები რომელიც user-მა უნდა მიიღოს fix-strategy-სთვის:

1. TYPING_DUP merge (12 barcode) — მარტივად fix-დება; supplier-coordination არ სჭირდება. ფინანსური მცირე scope (3,325 ₾), მაგრამ catalog clean.
2. SKU_VARIANT (33 barcode) — გადაწყვეტილება ფესვის შესახებ: catalog-level reorganization, supplier dialogue, ან accept-and-document?
3. BORDERLINE (4 barcode) — manual review scope.
4. Type B (769 barcode) — preventive POS uniqueness-check workflow (catalog hygiene).
5. Ambiguous active (16 barcode, 12K ₾) — შეიძლება იგივე subtype split საჭიროა?

⚠️ **არცერთი fix-path proposal preview-ში არ არის.** Research-ი დახურულია, fix-path discussion ცალკე ცოცხალდება — user-ის ნებაზე.

**No more drill-downs without explicit user approval.**

---

**Section 11 generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — read-only, no fix proposed, no detector code touched, deliverable (a) research CLOSED**

---

# Section 12 — SKU_VARIANT damage clarification: real or false alarm?

**დამატებულია**: 2026-05-03 (იგივე session-ში) · **Phase 1 deliverable (a) follow-up — verdict only** · **STRICT SCOPE — read-only**

## 12.0 ცხრება (one-liner verdict)

**ფინანსურ ციფრებს — false alarm.** ჯამური revenue/cost/profit მათემატიკურად სწორია. **Identity-level — real damage** (UI ერთი name-ს აჩვენებს 2-name-იან barcode-ზე), მაგრამ **per-store breakdown preserves per-P_ID granularity** ციფრობრივად. §11-ის "20K ₾ live damage" claim **overstated** — რეალური financial damage scope = **მცირე**, ძირითადად TYPING_DUP-ზე ზის (3K ₾), არა SKU_VARIANT-ზე.

---

## 12.1 Pipeline aggregation paths — exact code locations

| Path | ფაილი:ხაზი | GROUP BY / merge key | რა ემართება SKU_VARIANT-ს |
|---|---|---|---|
| **Source-side POS rollup** | `dashboard_pipeline/megaplus_backup.py:417-418` | `GROUP BY p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_UNIT, p.P_GROUP, d.DIST_UUID, d.dasaxeleba` | **Per-P_ID** — ცალკე row-ი თითოეული P_ID-ისთვის. **არანაირი blurring source-ზე.** |
| **Cross-store merge (retail_sales)** | `dashboard_pipeline/retail_sales.py:451-462` | `key = barcode or code or f"pid_{product_id}"` — **per-barcode** | **REAL merge** — SKU_VARIANT row-ები სხვადასხვა stores-ში ერთ row-ში ერთიანდება key-ით=barcode |
| **Name handling on merge** | `retail_sales.py:461-465` (`setdefault`) | `product_name = first encountered` — never updated | **Name = first P_ID's name** (highest-revenue from first store iterated). სხვა variant-ები **ქრება row-summary-ში** |
| **Numeric sum on merge** | `retail_sales.py:478-482` | `cur["revenue_ge"] += rev`, `cost_ge`, `profit_ge`, `total_quantity` (linear sum) | **Revenue/cost/profit/qty = correct sum.** ფინანსური ცრუობა **არ არის** |
| **Per-store breakdown preservation** | `retail_sales.py:484-492` | `object_totals.append({...})` — MULTIPLE entries per store allowed | **Per-store-per-P_ID granularity preserved** as separate entries inside object_totals — UI can drill down |
| **Supplier profitability** | `dashboard_pipeline/supplier_profitability.py:158-182` | Built ON `retail_sales.by_product`, indexed by_barcode + by_product_code (both already-merged) | ⚠️ **Section არ არსებობს current data.json-ში** (not produced) — code would inherit barcode-merge if it ran |
| **Category anomalies** | `dashboard_pipeline/category_anomalies.py:73-84` | Direct `SELECT p.P_ID, p.P_CODE, p.P_BARCODE, p.P_NAME, p.P_GROUP FROM PRODUCTS` per-P_ID query | **No barcode merge — per-P_ID throughout.** |
| **Waybill reconciliation** | `dashboard_pipeline/waybill_reconciliation.py` | rs.ge waybill data only — barcode not used as merge key | **No barcode-level damage** |

ე.ი. fragmenting blur **მხოლოდ ერთ ადგილას ხდება**: `retail_sales.by_product` cross-store merge-ში. სხვა pipeline path-ებში damage არ არის (ან section არ ცოცხლდება data.json-ში).

---

## 12.2 ცოცხალი trace — 5 SKU_VARIANT/BORDERLINE barcodes data.json-ში

`retail_sales.by_product` truncated 1,000 row-ით (`PRODUCT_LIMIT=1000`, `retail_sales.py:514`). სამიდან 4 SKU_VARIANT barcode top-1000-ში არ მოყვა (revenue დაბალი). ცოცხალი ცხრილში ხილული 5 barcode-ის trace:

### Trace 1: `8690624203394` — Doritos მექსიკანო ცხარე (SKU_VARIANT, 1,039.45 ₾ lifetime)

| ფენა | რა ცხადია |
|---|---|
| `megaplus_live.stores[1329].by_product` (source per-P_ID) | **2 row**: P_ID=92356 "სიმინდის ჩიფსი დორიტოს" rev=286.35; P_ID=92207 "დორიტოს SHOTS 108X" rev=279.70 |
| `megaplus_live.stores[1301].by_product` | **2 row**: P_ID=92719 "დორიტოს SHOTS 108X" rev=386.00; P_ID=92959 "სიმინდის ჩიფსი დორიტოს" rev=87.40 |
| `retail_sales.by_product` (cross-store merge) | **1 row**: name="სიმინდის ჩიფსი /დორიტოს შოთსი / მექსიკანო ცხარე / 23გ", revenue=1,039.45, cost=534.24, profit=505.21 |
| Sum check | 286.35 + 279.70 + 386.00 + 87.40 = **1,039.45** ✓ |
| `object_totals` field | **4 entries** (preserves per-store-per-P_ID granularity, but P_ID identity not labeled) |

### Trace 2: `4860101980320` — პელმენი დიდგორი ციმბირული (BORDERLINE, 5,194.60 ₾ lifetime)

| ფენა | რა ცხადია |
|---|---|
| `megaplus_live.stores[1329].by_product` | 1 row: P_ID=87819 "პილმენი ციმბირული 800გრ" rev=3,135.90 |
| `megaplus_live.stores[1301].by_product` | 1 row: P_ID=88739 "პილმენი ციმბირული 800გრ" rev=2,058.70 |
| `retail_sales.by_product` | 1 row: name="პილმენი ციმბირული 800გრ", revenue=5,194.60 (sum ✓), 2 object_totals |
| **comment** | PRODUCTS catalog-ში 2 P_ID აქვს ("დიდგორი" with/without brand), მაგრამ მეორე P_ID **არ მუშაობს ORDERS-ში** — 12mo/lifetime activity მხოლოდ ერთ P_ID-ზე per-store. ცარიელი variant ცარიელია → blur არ ხდება. |

### Trace 3: `54492790` — კოკა-კოლა ალუბალი 0.5ლ (SKU_VARIANT, 2,527.20 ₾)

| ფენა | რა ცხადია |
|---|---|
| `megaplus_live.stores[*].by_product` | 1 row each store: P_ID=97549 "0.500ლ კოკა-კოლა ალუბალი (12ც)" 1329; P_ID=97954 "0.500ლ კოკა-კოლა ალუბალი " 1301 (trailing space) |
| `retail_sales.by_product` | 1 row, sum correct, 2 object_totals |
| **comment** | SKU_VARIANT classifier-მა divergence დაიჭირა (one name with "(12ც)" case-count, other without). რეალურად — იგივე product, იგივე SKU. **classifier-ის false-positive SKU_VARIANT** (typing variation, not real SKU divergence). |

### Trace 4: `5449000329738` — 5ლ მინერალური წყალი (SKU_VARIANT, 3,297.80 ₾)

| ფენა | რა ცხადია |
|---|---|
| `megaplus_live.stores[*].by_product` | 1 row per store, identical name "5 ლ მინერ. წყალი მთის (2ც)" |
| `retail_sales.by_product` | 1 row, sum correct, 2 object_totals |
| **comment** | სხვადასხვა P_ID-ები PRODUCTS-ში არსებობს, მაგრამ ცოცხალი ORDERS-ი მხოლოდ ერთ P_ID-ზე per store. **No blur in current state.** |

### Trace 5: `4860101980245` — ვარენიკი (BORDERLINE — შემავსებელი divergence)

| ფენა | რა ცხადია |
|---|---|
| `megaplus_live.stores[1329]` | 1 row: P_ID=69271 "ვარენიკი იმერული სახაჭაპურე გულსართით 800 გრ" rev=1,116.10 |
| `megaplus_live.stores[1301]` | 1 row: P_ID=58408 same name, rev=699.60 |
| `retail_sales.by_product` | 1 row: სახაჭაპურე variant, sum=1,815.70 |
| **comment** | PRODUCTS-ში 2 sharply-different name ("ყველით 800 გრ" vs "სახაჭაპურე გულსართით 800 გრ"), მაგრამ ცოცხალი ORDERS-ი მხოლოდ "სახაჭაპურე გულსართით"-ზე. ე.ი. `ვარენიკი ყველით` — dormant catalog ghost. **Real-time aggregation არ ცრუობს.** |

---

## 12.3 ფინალური verdict per question type

| დაკითხვა | პასუხი |
|---|---|
| Pipeline merges per-barcode (correct) თუ per-P_ID? | **Per-barcode** in `retail_sales.by_product` (after cross-store merge). Per-P_ID at source. |
| ფინანსური damage არსებობს? | **არა.** Revenue/cost/profit linearly summed, mathematically correct. |
| Identity damage არსებობს? | **კი** — top-level row carries one name (first-seen variant). For Doritos (true SKU_VARIANT), 1 name out of 4 ცხადია. |
| Per-store breakdown damage? | **არა** — `object_totals` preserves multi-entry per-store granularity. |
| რეალური SKU divergence (e.g. ვარენიკი ყველით vs სახაჭაპურე) ცრუობს? | **მხოლოდ თუ ორივე ცოცხალია 12mo-ში.** §11 BORDERLINE ვარენიკი — only one variant ცოცხალი → no current blur. |
| supplier_profitability damage? | **N/A** — section არ არის current data.json-ში. Code would inherit barcode-merge if ცოცხლდებოდა. |
| category_anomalies damage? | **არა** — per-P_ID query throughout. |
| waybill_reconciliation damage? | **არა** — barcode not merge key. |

---

## 12.4 §11-ის "20K ₾ live damage" claim revisited

§11-ში ვწერდი: "SKU_VARIANT (33 barcode, 20,097 ₾) — naive merge ფინანსურად ცრუობს". **ეს overstated იყო.** ცოცხალი pipeline trace-ი ცხადყოფს:

| Damage type | რეალური scope |
|---|---|
| Financial number distortion | **0 ₾** (sums are correct) |
| Per-store breakdown loss | **0 ₾** (object_totals preserved) |
| Identity/UI label collapse (cosmetic) | up to ~20K ₾ revenue ხილულია მხოლოდ ერთი name-ით — **არა numeric ცრუობა, label-ის accuracy** |
| Genuine SKU divergence at single barcode (worst case — fundamentally different products) | ცოცხალი მონაცემიდან **0 ₾** for §11's BORDERLINE შავნაბადა ვარენიკი (only one variant active in 12mo); **must re-check per barcode** if more cases hide |

**რეალური ცოცხალი financial damage scope (revised):**

- TYPING_DUP merge candidates: **3,325 ₾** (12 barcode) — სიწმინდის merge fix-ით identity გაუმჯობესდება, ფინანსური ცრუობა არ არის
- SKU_VARIANT identity blur: **20,097 ₾** label-level only — financial sums correct
- BORDERLINE (4 barcode, 4,731 ₾) — ცოცხალი მონაცემი ცხადყოფს რომ 1 variant-ი per-barcode active per store. Genuine identity damage მცირე ან ნული

ე.ი. ხელშეკრულებისთვის ღირებული scope = **3,325 ₾ TYPING_DUP merge** (financial impact ≈ 0, catalog hygiene + name accuracy improves) + **specific BORDERLINE manual review** (≤ 1K ₾).

SKU_VARIANT-ი არ არის financially harmful — pipeline-ი მართებულად ეპყრობა (revenue/cost სწორად ეჯამება, per-store breakdown დეტალურია, მხოლოდ row-summary name-ი ცალკეული name-ია).

---

## 12.5 ცხრება — fix-strategy implication

**§11-ის conclusion-ი (SKU_VARIANT requires supplier coordination / catalog reorg / accept-and-document) გადასახედია:**

- **Financial accuracy: NO fix needed.** Pipeline-ი ფინანსურად სწორად მუშაობს per-barcode merge-ით.
- **Identity/UX accuracy: optional cosmetic fix** — UI-ში per-barcode multi-name display (e.g., "Doritos მექსიკანო ცხარე / SHOTS 108X"). Code change in `retail_sales.py:461-465` could collect ALL distinct names instead of just first.
- **Real fix priority** (per actual damage):
  1. **Supplier_profitability section არ ცოცხლდება data.json-ში** — ეს უფრო კრიტიკული issue-ია ვიდრე SKU_VARIANT-ის blurring. ცალკე investigation საჭიროა (out of (a) scope).
  2. **TYPING_DUP merge** (12 barcode, 3,325 ₾) — catalog cleanup + per-supplier coordination (e.g., ვივა ARPA juices). LOW risk.
  3. **Type B catalog cleanup** (preventive, no current financial signal — POS uniqueness check workflow).

---

## 12.6 ცხადი ღია question (no fix proposal)

§11-ის "20K SKU_VARIANT damage" claim was **overstated based on hypothesis**. §12-ის ცოცხალი trace ცხადყოფს რომ pipeline ფინანსურად მართებულად ექცევა cross-store merge-ს. Real fix scope ბევრად მცირეა.

**შენი გადაწყვეტილება:**

1. **TYPING_DUP merge fix** (12 barcode, ~3K ₾) — ცოცხლდე ეს fix-path discussion ცალკე? (catalog cleanup mostly, financial impact minimal)
2. **`supplier_profitability` section absent from data.json** — ეს ცალკე issue-ი არის, ღირს investigation-ის prioritization?
3. **Type B preventive workflow** (POS uniqueness check) — long-term catalog hygiene (no current financial signal)
4. **Phase 1 (b) — PRODUCTS orphans** (3,046 product / `P_DAFAULTSUPPLIER` empty)
5. **სხვა მიმართულება** — შენი არჩევანი

⚠️ **Research is fully closed for deliverable (a)**. §12 ცხრება — fix-strategy decision **must be made before any further code-level work**.

---

**Section 12 generated**: 2026-05-03 (Claude Code, Opus 4.7) · **STRICT SCOPE — read-only verification, no fix proposed. §11's 20K ₾ claim re-evaluated as identity-only, not financial. Pipeline behaves correctly for cross-store revenue/cost aggregation.**
