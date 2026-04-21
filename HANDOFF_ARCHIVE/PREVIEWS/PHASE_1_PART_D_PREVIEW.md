# Phase 1 Part D — საკუთარი თავის გასწორების ციკლი — Preview

> **თარიღი:** 2026-04-20 | **სტატუსი:** ✅ **COMPLETE + LIVE VERIFIED** (2026-04-20 02:50)
> **ავტორი:** Cascade
> **ენა:** Plain ქართული (technical jargon გარეშე)
> **Scope:** AI-ს ქცევის დონის გაუმჯობესება — retrieval resilience + self-correction
> **წინაპირობა:** Phase 1 Part A ✅ + Part B ✅ + Part C ✅ (ყველა LIVE)
> **Trigger:** 2026-04-20 02:30 BOG 2026-02 false-negative — AI-მ 1 ცუდი query-ით დაასკვნა "ფაილი არ მაქვს", მაშინ როცა ფაილი ინდექსშიც და Excel-შიც იყო
> **Actual Dev time:** ~30 წუთი (prompt section + 55 tests + live dog-food + cleanup)
>
> **დახურვის შემაჯამებელი:**
> - Code: `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` new `🔄 საკუთარი თავის გასწორების ციკლი` section (~600 ტოკენი)
> - Tests: **55** new cases in `tests/test_ai_prompts_phase1d.py` — pytest **969/969 green** (was 914; +55; 0 weakened)
> - Investigator prompt UNTOUCHED (6 do-not-touch tests + 15-marker leak guard)
> - Backend restart #9 — parent-venv PID **7776** live with 15 Part D markers verified
> - Live Anthropic dog-food **5/5 PASS** ✅ — same BOG 2026-02 question that failed at 02:30 → AI made **17 tool calls** including 4× recall_context with progressive Latin alias enrichment + structured "ვცადე" fallback
> - **NEW bug surfaced** during dog-food: `read_excel_source` blocks Georgian folder names with spaces (e.g. `ბოგ ბანკი ამონაწერი/`) — separate carry-forward concern, NOT a Part D regression

---

## 📖 რა არის ეს დოკუმენტი

**ეს არის გეგმა, არა კოდი.** შენს დადასტურებას ვიღებ — მერე ვწერ.

Phase 1-ის ოთხი ნაწილი ერთ სურათად:

| ნაწილი | რას ასწავლის AI-ს |
|---|---|
| **Part A** ✅ | **როგორ** ფიქრობდეს (5 ქუდი, პერსონა, confidence, skepticism) |
| **Part B** ✅ | **სად ცხოვრობს** (VAT, საპენსიო, RS.ge, ფრენჩაიზი) |
| **Part C** ✅ | **რა ბიზნესია ზუსტად** (2 მაღაზია, ცალკე DNA) |
| **Part D** 📝 | **როცა ვერ ვპოვებ — რა უნდა გავაკეთო** (retry / self-correct, არ დაასკვნა "არ მაქვს" პირველ ცდაზე) |

---

## 🧭 რატომ გჭირდება — 2026-04-20 02:30 real incident

შენ იკითხე:

> *"საქართველოს ბანკიდან რამდენი ლარის ჩარიცხვა მოხდა კომპანიებზე 2026 თებერვალში"*

AI-მ გიპასუხა:

> *"⚠️ მონაცემი არ მაქვს — ვერ ვიპოვე. 2026 წლის BOG ფაილი ინდექსში არ ჩანს. ატვირთე ფაილი..."*

### სინამდვილე

| AI-ს ნათქვამი | რეალობა |
|---|---|
| "2026 წლის BOG ფაილი ინდექსში არ ჩანს" | ❌ **ფაილი იყო** — `Financial_Analysis/ბოგ ბანკი ამონაწერი/02--2026.xlsx` (1.5 MB) |
| "ChromaDB-ში მხოლოდ 2025.xlsx ფაილია" | ❌ **ოთხი ფაილი** იყო (2023, 2024, 2025, 02--2026) |
| "ატვირთე ფაილი pipeline-ში" | ❌ **ატვირთვა აღარ საჭირო იყო** — ფაილი უკვე ინდექსირებული იყო (2026-04-19 21:35) |

### რა მოხდა ტექნიკურად (მოკლედ, არა-პროგრამისტული)

AI-მ ერთი სუსტი ფრაზა სცადა (`ბოგ 2026`). AI-ს მეხსიერების ძიებამ **სხვა ბანკი** დააბრუნა (თბს) — რადგან "ბოგ" და "თბს" 3-ასოიანი ქართული აბრევიატურები ძალიან ჰგავს ერთმანეთს embedding-ში. AI-მ ეს არასწორი შედეგი დაინახა, **პირდაპირ დაასკვნა** "ფაილი არ მაქვს", და **აღარ სცადა** სხვა ფრაზა.

ცხადი მაგალითი: ფრაზა `"საქართველოს ბანკი BOG Bank of Georgia 2026-02 ჩარიცხვა"` **ცოცხლივ მოგცემდა** 5/5 chunk-ს `02--2026.xlsx`-იდან, distance 0.12 (ზუსტი match).

### შედეგი შენთვის

- შენ დაინახე "ფაილი უნდა ატვირთო" — **რაც არასწორი მითითება იყო**
- დრო იკარგება — ამ ტიპის ცდომილებას ყოველდღე შესაძლოა შეხვდე
- AI-ს "საკუთარი" გონი ვერ გიშველის — შენ ხდები "AI-ს მასწავლებელი"

---

## 🎯 რას ემატება — **საკუთარი თავის გასწორების ციკლი**

SYSTEM_PROMPT_KA-ში (chat-mode) ახალი სექცია დაემატება, რომელიც **3 წესს** აკისრებს AI-ს.

### წესი 1: **Retry Protocol — ცდა ცდაზე**

> **"ცარიელი ან ცუდი პასუხი" ≠ "არ არსებობს".**
> სანამ ვიტყვი "ვერ ვიპოვე", **3-ჯერ** ვცდი სხვადასხვა ფრაზით.

| ცდის ნაბიჯი | რას ვცვლი | მაგალითი — user-ის კითხვა: "BOG 2026-02 ჩარიცხვა" |
|---|---|---|
| **1-ელი ცდა** | User-ის ფრაზა 1-1-ზე | `"ბოგ 2026 თებერვალი ჩარიცხვა"` |
| **2-ე ცდა** | + **სრული Latin alias** | `"ბოგ ბანკი BOG Bank of Georgia 2026-02"` |
| **3-ე ცდა** | + **თარიღი 3 ფორმატით** | `"Bank of Georgia February 2026 company transfers"` |
| **4-ე ცდა** (fallback) | **ფაილის სახელი** პირდაპირ | `"02--2026.xlsx ბოგ"` ან ფოლდერი `"ბოგ ბანკი ამონაწერი"` |

### წესი 2: **Confidence Gate — პასუხის წინ**

პასუხის გაცემამდე AI-მ თავის თავი უნდა შეიკითხოს:

- ✅ **თუ მცადა 3+ ფრაზა** → შეიძლება "ვერ ვიპოვე"-ს თქმა, **ოღონდ** უნდა ჩამოაყალიბოს რა ფრაზები სცადა
- ❌ **თუ მცადა 1 ფრაზა** → **აკრძალულია** "ვერ ვიპოვე"-ს თქმა. ჯერ სხვა ვარიანტები.

### წესი 3: **Self-Triage — რა ჰიპოთეზა ავიღო**

თუ query-ი მოდის მაგრამ "შედეგი უცნაურია", AI-მ უნდა **გამოიცნოს** რა პრობლემაა:

| სიმპტომი | ჰიპოთეზა | გადასაჭრელი ნაბიჯი |
|---|---|---|
| **0 hit / ცარიელი პასუხი** | "Query ძალიან ვიწროა" | ფრაზის გაფართოება: ფოლდერი, წელი, კატეგორია |
| **5+ hit, მაგრამ სხვა ბანკი / სხვა წელი** | "Latin alias სუსტია" | **სრული** ინგლისური ფრაზა დაამატე (`Bank of Georgia`, არა "BOG") |
| **Off-topic შინაარსი** | "Embedding ურევს მსგავს აბრევიატურებს" | Domain-anchor keyword: `ამონაწერი`, `ანგარიში`, `POS`, `ტერმინალი` |

---

## 🔍 Before / After — 2 კონკრეტული სცენარი

### სცენარი 1 — დღევანდელი BOG incident

**Before (დღეს):**
> User: "BOG 2026-02 რამდენი ჩარიცხვა?"
> AI → `recall_context("ბოგ 2026")` → 5/5 თბს ბანკი → "⚠️ არ მაქვს, ატვირთე ფაილი"
> **რეალობა:** ფაილი იყო. AI-ს ცდომილება.

**After (Part D-ს შემდეგ):**
> User: "BOG 2026-02 რამდენი ჩარიცხვა?"
> AI → `recall_context("ბოგ 2026")` → 5/5 **თბს** — 🚨 self-triage: "Latin alias სუსტი"
> AI → `recall_context("ბოგ ბანკი BOG Bank of Georgia 2026-02")` → 5/5 **ბოგ 02--2026** ✅
> AI → იკითხავს chunk-ებს → გათვლის → პასუხი

### სცენარი 2 — ახალი მომწოდებლის ძიება

**Before:**
> User: "Alpha-ს 2026 მარტიდან რა ვალი აქვს?"
> AI → `read_data_json(suppliers, filter=Alpha)` → 0 hit → "Alpha არ ჩანს მონაცემებში"

**After:**
> AI → 1-ელი ცდა: 0 hit → self-triage: "name variant?" → 2-ე ცდა: `filter=alp` partial match → 1 hit (`Alpha LLC`) ✅
> → "ალფა (Alpha LLC) ვალი: 23,000 ₾ (წყარო: suppliers)"

---

## 🧪 Tests — ~45 new cases in `tests/test_ai_prompts_phase1d.py`

| Test class | Cases | რას ამოწმებს |
|---|---|---|
| `TestSelfCorrectionSection` | 5 | Section header + Phase 1 Part D tag + 3 ქვე-წესი + topological position |
| `TestRetryProtocol` | 8 | 4-ცდიანი ცხრილი + Latin alias წესი + თარიღი 3 ფორმატით + ფაილი-სახელი fallback |
| `TestConfidenceGate` | 5 | "3+ ცდა MANDATORY" + "ვერ ვიპოვე" ფრაზის აკრძალვა 1-ცდაზე + ცდების ჩამოყალიბება პასუხში |
| `TestSelfTriage` | 6 | 3 hypothesis + each with symptom → action mapping |
| `TestLatinAliasMandate` | 5 | "Bank of Georgia" MANDATORY (არა optional) + "TBC" + "Revenue Service" + anti-pattern examples |
| `TestBuildSystemPromptWiring` | 4 | chat-ს გააჩნია + investigator-ს არ გააჩნია |
| `TestInvestigatorPromptUntouched` | 6 | 15 Part D marker-ის ყველა absent კიდევ ერთხელ |
| `TestPhase1PriorPartsStillPresent` | 6 | Part A (პერსონა + 5 ქუდი) + Part B (რეგულაცია + რიტმი) + Part C (DNA + Seasonality + Baseline ×2) ცოცხალი |

**pytest baseline:** 914 → ~**959** (+45)

---

## 📐 სადაც ემატება — topology

**ამჟამინდელი rend:**
```
🎯 როლის კონტრაქტი (Part A)
🎭 5 ქუდი (Part A)
🗺️ პროექტის რუკა
🇬🇪 ქართული რეგულაცია (Part B)
🌅 ქართული თვის რიტმი (Part B)
🏪 მაღაზიების DNA (Part C)
⚖️ წყაროების იერარქია
🕵 Data-ზე სკეპტიციზმი
...
```

**Part D-ს შემდეგ:**
```
...
🏪 მაღაზიების DNA (Part C)
🔄 საკუთარი თავის გასწორების ციკლი (Part D)  ← NEW
⚖️ წყაროების იერარქია
...
```

**რატომ აქ:** Part D ადგენს **ქცევას** წყაროების ძიებისას. ლოგიკურია იყოს **უშუალოდ** წყაროების იერარქიის წინ — ჯერ "როგორ ვეძებ" → შემდეგ "რომელი წყარო ჯობია".

---

## ⚠️ Do-not-touch rules (Part D-ს შემდეგ)

- **Retry minimum = 3** — AI-მ **მინიმუმ** 3 განსხვავებული ფრაზა უნდა სცადოს, სანამ "ვერ ვიპოვე"-ს იტყვის. Ci-ს **არასოდეს** ვამცირებთ 2-მდე.
- **Latin alias MANDATORY** — Sprint 3-ის "hint" → Part D "MANDATE". 3-ასოიანი ქართული აბრევიატურა ყოველთვის ინგლისური ეკვივალენტით.
- **"ვერ ვიპოვე" ფრაზა** ცხადად უნდა ჩამოთვალოს რა ცდები გააკეთა (user-ს ვუჩვენებთ **ცდების შრომას**, არა მხოლოდ **დასკვნას**)
- **Investigator prompt** — UNTOUCHED (Sprint 1/2/3/4 + Part A/B/C/**D** do-not-touch rule გრძელდება)

---

## 📊 Scope — რა შედის ძირითად Part D-ში

| Tier | რა | ჩართო? |
|---|---|---|
| 🔵 **A (Core)** | Retry protocol 4 ნაბიჯი + Confidence gate + Self-triage 3 hypothesis | ✅ default |
| 🔵 **B (Latin MANDATE)** | Sprint 3-ის Latin alias "hint" → "MANDATORY" სიძლიერის გაძლიერება + anti-pattern examples | ✅ default |
| 🔵 **C (Date triage)** | 3-formatian date retry (`YYYY-MM` / `Month YYYY` / `ქართული თვე YYYY`) | ✅ default |
| ⚪ **D (Suppler-name fuzzy retry)** | "Alpha" ↔ "ალფა" ↔ "Alpha LLC" partial match ცხრილი | ⚠️ optional — თუ გინდა |
| ⚪ **E (ChromaDB distance threshold)** | "distance > 0.25 → retry MANDATORY" numeric gate | ⚠️ optional — მცდელობაა, მოცულობა იზრდება |

**Default = 🔵 A + 🔵 B + 🔵 C** (Part C-ს მსგავსად — ბირთვი + 2 სიძლიერე)

---

## 🕐 Timeline estimate

| ეტაპი | დრო |
|---|---|
| Prompt section წერა | ~15 წთ |
| 45 tests წერა + debug | ~25 წთ |
| pytest regression | ~1 წთ |
| Live Anthropic dog-food (იგივე BOG 2026-02 query) | ~3-5 წთ |
| Backend restart #9 + verification | ~3 წთ |
| Docs refresh (PLAN + CONTEXT_HANDOFF + HANDOFF + preview → COMPLETE) | ~15 წთ |
| **ჯამში** | **~1 საათი** |

---

## 🎬 ცოცხალი ტესტი (live dog-food) — რას დავრწმუნდები

Backend restart-ის შემდეგ ცოცხლივ დავსვამ **იგივე** BOG კითხვას:

> *"საქართველოს ბანკიდან რამდენი ლარის ჩარიცხვა მოხდა კომპანიებზე 2026 თებერვალში?"*

**წარმატების კრიტერიუმი (5/5 marker-ი):**

1. ✅ AI **აღარ თქვა** "ფაილი არ მაქვს" 1-ელ ცდაზე
2. ✅ AI ცოცხლად სცადა `recall_context` **მინიმუმ 2-ჯერ** სხვადასხვა ფრაზით (ლოგიდან)
3. ✅ ერთ-ერთი ცდა **აუცილებლად** შეიცავდა `Bank of Georgia` full phrase-ს
4. ✅ AI იპოვა `02--2026.xlsx` chunk-ები
5. ✅ AI გამოთვალა **რეალური რიცხვი** ან დეტალურად ახსნა რა scope-ია (POS vs wire transfer)

თუ 5-დან 5 ✅ → Part D COMPLETE.
თუ 5-დან <4 ✅ → preview-ს ვუბრუნდები, fix-ს ვამზადებ, თავიდან ვცდი.

---

## ❓ გააგრძელო? (კი / არა)

- **"კი"** → ვიწყებ კოდს (`SYSTEM_PROMPT_KA` + ~45 tests + live dog-food + backend restart #9 + docs)
- **"არა"** → რაიმე ცალკე მიდგომა გინდა (scope-ი ცვლი, ოპციურ tier-ს დაამატებ, სხვა გზა)

---

## 📎 Appendix — ზუსტი ფრაზა რაც SYSTEM_PROMPT_KA-ში დაემატება (draft)

```text
## 🔄 საკუთარი თავის გასწორების ციკლი (CRITICAL — Phase 1 Part D)

**"ცარიელი პასუხი" ან "უცნაური პასუხი" ≠ "არ არსებობს".**

სანამ ვიტყვი "ვერ ვიპოვე" — **მინიმუმ 3-ჯერ** ვცდი სხვადასხვა ფრაზით.
1-ცდაზე "არ მაქვს"-ის თქმა **აკრძალულია**.

### 🔁 Retry Protocol (4 ნაბიჯი)

| ცდა | რას ვცვლი |
|---|---|
| **1** | User-ის ფრაზა 1-1-ზე |
| **2** | + სრული Latin alias (`Bank of Georgia`, არა მხოლოდ "BOG") |
| **3** | + თარიღი 3 ფორმატით (`YYYY-MM` / `Month YYYY` / `ქართული თვე YYYY`) |
| **4** | + ფაილის სახელი / ფოლდერი პირდაპირ (ბოლო fallback) |

### 🎯 Self-Triage — რა ჰიპოთეზა ავიღო

| სიმპტომი | ჰიპოთეზა | ნაბიჯი |
|---|---|---|
| 0 hit | Query ძალიან ვიწროა | გააფართოვე (ფოლდერი/წელი/კატეგორია) |
| 5+ hit, მაგრამ სხვა ბანკი / სხვა წელი | Latin alias სუსტია | **სრული** ინგლისური ფრაზა დაამატე |
| Off-topic შინაარსი | Embedding ურევს მსგავს აბრევიატურებს | Domain-anchor keyword (ამონაწერი / ანგარიში / POS / ტერმინალი) |

### 📢 Latin Alias — MANDATORY

3-ასოიანი ქართული აბრევიატურები **ყოველთვის** სრული ინგლისურით:
- **ბოგ** → `Bank of Georgia` (არა "BOG" alone)
- **თბს** → `TBC` (OK — 3 letter Latin ერთმნიშვნელოვანია)
- **რს** → `Revenue Service` (არა "RS" alone)

### ❌ "ვერ ვიპოვე" — მხოლოდ ცდების შემდეგ

თუ 3 ცდის შემდეგ ცარიელი ან არასწორი — **ცხადად ჩამოაყალიბე** რა ცდები გააკეთე:
> "ვცადე: (1) `ბოგ 2026 თებერვალი`, (2) `ბოგ ბანკი BOG Bank of Georgia 2026-02`, (3) `Bank of Georgia February 2026 company transfers`. არცერთი არ დაემთხვა. დააზუსტე: ..."
```

---

**მზად ვარ.** ვუცდი "კი"-ს.
