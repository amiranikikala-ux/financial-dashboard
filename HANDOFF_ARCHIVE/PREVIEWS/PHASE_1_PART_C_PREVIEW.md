# Phase 1 Part C — Multi-Store DNA — Preview

> **თარიღი:** 2026-04-20 | **სტატუსი:** ✅ **COMPLETE + LIVE VERIFIED** (2026-04-20 02:11)
> **ავტორი:** Cascade
> **ენა:** Plain ქართული (technical jargon გარეშე)
> **Scope:** `AI_GENIUS_PARTNER_PLAN.md` § 1.12 — Multi-Store DNA
> **წინაპირობა:** Phase 1 Part A ✅ + Part B ✅ (ორივე LIVE)
> **Approved:** user "გააგრძელე" (default 🔵 A Core DNA + 🔵 I Auto-journal + 🔵 α Soft seasonality)
> **Actual Dev time:** ~40 წუთი (prompt section + 54 tests + live dog-food + docs)
>
> **დახურვის შემაჯამებელი:**
> - Code: `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` new `🏪 მაღაზიების DNA` section (~700 ტოკენი)
> - Tests: 54 new cases in `tests/test_ai_prompts_phase1c.py` — pytest **914/914 green** (was 860; +54; 0 weakened)
> - Investigator prompt UNTOUCHED (6 do-not-touch tests)
> - Backend restart #8 — parent-venv PID **31176** live with 15 Part C markers verified in-process
> - Live Anthropic dog-food ✅ — AI emitted all 5 DNA markers (ოზურგეთი / დვაბზუ / elasticity / confidence / DNA-based hypothesis) on თამბაქოს ფასდაკლება cross-store question (49.84s earlier chat-mode run hit tool cap; redone with `think=True` → elapsed ~2 min, `stop_reason=end_turn`, 178,889 in + 5,607 out + **166,817 cache_read**; ≈$0.14)
> - Docs refresh — PLAN.md + CONTEXT_HANDOFF.md + HANDOFF.md

---

## 📖 რა არის ეს დოკუმენტი

**ეს არის გეგმა, არა კოდი.** შენს დადასტურებას ვიღებ — მერე ვწერ.

Phase 1-ის სამი ნაწილი ერთ სურათად:

| ნაწილი | რას ასწავლის AI-ს |
|---|---|
| **Part A** ✅ | **როგორ** ფიქრობდეს (5 ქუდი, პერსონა, confidence ნიშნები, skepticism) |
| **Part B** ✅ | **სად ცხოვრობს** (VAT, საპენსიო, RS.ge, ფრენჩაიზი royalty) |
| **Part C** 📝 | **რა ბიზნესია ზუსტად** (2 ცალკე მაღაზია, ცალკე DNA-თი — **არა ერთი ერთეული**) |

---

## 🧭 რატომ გჭირდება

**ახლანდელი AI ცნობს,** რომ "2 მაღაზია გაქვს":

> 🗺️ პროექტის რუკა → *"ოზურგეთი (3 POS, urban, tourist-ი, 12-საათიანი) + დვაბზუ (2 POS, rural, ლოკალი customer, shorter hours, weekend peak)"*

ერთი ხაზი — სულ ეს არის.

**ეს 1 ხაზი საკმარისია, რომ AI-მ გაიგოს "რომელი სტორი" შეიკითხო.** მაგრამ ცოტაა, რომ **სტრატეგიულად განასხვავოს რჩევა**.

მაგალითად, რომ ვკითხო:

> *"თამბაქოს ფასდაკლება გავაკეთო?"*

AI **ახლა** გიპასუხებს:

> "ფასდაკლების effect-ი დამოკიდებულია margin-ზე + volume elasticity-ზე. **შენი margin რამდენია?**..."

AI **Part C-ის შემდეგ** გიპასუხებს:

> "**ეს კითხვა ორი სხვადასხვა ბიზნესია:**
>
> 🏪 **ოზურგეთი (YES, 🟢 საიმედო):** weekend + ტურისტული პიკი — თამბაქო high-frequency + price-inelastic segment (smokers habit-driven). 10-15% ფასდაკლება → volume +18-25% (pass-through >100%).
>
> 🏡 **დვაბზუ (NO, 🟢 საიმედო):** rural loyal customer, volume ფიქსი — ფასდაკლება margin-ს ჭამს, volume ~3-5% თუ გაიზრდება. Net: −1,500 ₾/თვე.
>
> **რჩევა:** ოზურგეთი-ში **კი** (3 კვირიანი test). დვაბზუ-ში **არა**."

ანუ AI ერთი კითხვიდან **ორ ცალკე ანალიზს** აწარმოებს — **სწორედ ისე, როგორც პარტნიორი იფიქრებდა**.

---

## 🎯 ახლა vs Part C-ის შემდეგ

| შენი კითხვა | ახლანდელი AI | Part C-ის შემდეგ AI |
|---|---|---|
| "ფასდაკლება თამბაქოზე" | "margin/volume trade-off" | "🏪 ოზურგეთი YES (tourist + evening rush — 🟢), 🏡 დვაბზუ NO (loyal habit-driven, elasticity low)" |
| "ახალი supplier-ის ტესტი სად?" | "ორივეში ცდა" | "ოზურგეთი — traffic high → ფიდბეკი 2 კვირაში; დვაბზუ — volume slow → 6+ კვირა. **ჯერ ოზურგეთი**" |
| "evening staff-ი ჭარბი მაქვს?" | "cost audit"  | "🏪 ოზურგეთი — 12-საათიანი evening rush (20:00-22:00 peak), staff CRITICAL; 🏡 დვაბზუ — 8-საათიანი, evening empty, staff შემცირდეს" |
| "ახალი კატეგორია რომელ სტორში?" | "inventory pressure" | "Premium drinks → 🏪 ოზურგეთი (tourist discretionary spend); Bulk/basics → 🏡 დვაბზუ (local recurring); Organic/health → 🏪 ოზურგეთი-ს test first" |
| "მარგინი 11% vs 2% — რატომ დვაბზუ?" | "supplier cost comparison" | "🏡 დვაბზუ DNA: rural inelastic customer → **სასტიკად ვერ ვფასდაკმარდები** → pricing tight; ოზურგეთი-ს margin bolster ხდება premium SKU-თი, დვაბზუ-ში იგივე SKU არ იყიდება" |
| "promotion-ის calendar?" | "მარტივი calendar" | "🏪 ოზურგეთი — Fri-Sat (pre-weekend tourist); 🏡 დვაბზუ — 9-ე, 24-ე (ხელფასის წინ + ქართული ortodox holidays); ორივე — 31 დეკემბერი" |

---

## 🧩 რას ჩავწერ AI-ის "თავში"

ახალი section `SYSTEM_PROMPT_KA`-ში — **`🏪 მაღაზიების DNA (CRITICAL — Phase 1 Part C)`** — ჩაიდება **`🇬🇪 ქართული რეგულაცია`-ს შემდეგ** და **`⚖️ წყაროების იერარქია`-ის წინ**. ე.ი. ბიზნეს-კონტექსტის cluster ერთად რჩება:

```
🌅 დღის პულსი
🗺️ პროექტის რუკა          ← უკვე 1 ხაზი "2 მაღაზია"
🇬🇪 ქართული რეგულაცია     ← Part B
🏪 მაღაზიების DNA          ← 🆕 Part C (ეს ჩაიდება აქ)
⚖️ წყაროების იერარქია
🕵 Data-ზე სკეპტიციზმი
🎭 5 ქუდი
...
```

---

### 🏪 ოზურგეთი — Urban Flagship

| ველი | ზოგადი პარამეტრი |
|---|---|
| **ტიპი** | Urban, ცენტრალური ლოკაცია |
| **POS** | 3 ტერმინალი (paralleled checkout) |
| **რეჟიმი** | 12-საათიანი (დილიდან დაგვიანებულ საღამომდე) |
| **Customer profile** | ტურისტი + ადგილობრივი (mixed) |
| **Daily traffic** | Higher (~2-3× დვაბზუ-ს) |
| **Peak times** | Evening 20:00-22:00 + შაბ/კვ + ზაფხული ტურისტული სეზონი |
| **Product mix tilt** | Premium drinks, snacks, tobacco, convenience |
| **Promotion response** | **Fast & high pass-through** — elastic segment |
| **Price elasticity** | Mixed (ტურისტი price-elastic; local regular inelastic) |
| **Typical basket** | Smaller, impulse-driven, higher frequency |

---

### 🏡 დვაბზუ — Rural Local

| ველი | ზოგადი პარამეტრი |
|---|---|
| **ტიპი** | Rural / სოფლური, ლოკალური community-იდან |
| **POS** | 2 ტერმინალი |
| **რეჟიმი** | 8-საათიანი (daytime + evening slow) |
| **Customer profile** | ადგილობრივი, regular, loyal |
| **Daily traffic** | Lower (~50-60% ოზურგეთი-ს) |
| **Peak times** | შაბ/კვ + ხელფასის დღეები (10, 25) + ოფიციალური დღესასწაულები |
| **Product mix tilt** | Basics, bulk, essentials, affordable |
| **Promotion response** | **Slow & low pass-through** — habitual segment |
| **Price elasticity** | **Low** (loyal, needs-based spend) |
| **Typical basket** | Larger, planned, recurring |

---

### 🌅 სეზონური რიტმი (soft hint — hardcoded calendar არა)

AI-ს ცოდნაში:

- 🏪 **ოზურგეთი peak:** **6-9 ზაფხული** (ტურისტი) + **დეკემბერი** (holidays)
- 🏡 **დვაბზუ peak:** **10, 25 — ხელფასი days** + **გაზაფხული (ortodox easter)** + **აგვ-სექტ moderate**
- 🎄 **ორივეს საერთო:** **31 დეკემბერი** (new year rush)

> **⚠️ წესი:** ზუსტი თვე/თარიღი **user-ზეა დამოკიდებული**. თუ precise seasonal recommendation საჭიროა, AI `forecast_revenue(store=...)`-ს გამოძახავს ფაქტობრივი seasonality-ის მისაღებად.

---

### 🎯 სტრატეგიული DNA — როდის რომელი მნიშვნელოვანია

AI-ს ცოდნა როგორ გამოიყენოს ეს DNA:

| კითხვის ტიპი | DNA-ს გავლენა |
|---|---|
| **Promotion / discount** | 🏪 ოზურგეთი: elastic → test first; 🏡 დვაბზუ: inelastic → skip ან limited SKU |
| **ახალი კატეგორია** | Premium/discretionary → ოზურგეთი; Basics/bulk → დვაბზუ |
| **Supplier strategy** | ოზურგეთი: larger pack + frequent delivery; დვაბზუ: smaller pack + bulk-buy |
| **Staffing** | ოზურგეთი: evening staff CRITICAL (20-22 peak); დვაბზუ: daytime focus |
| **Pricing** | ოზურგეთი: tolerance 2-3%; დვაბზუ: price rises risk churn |
| **Cash planning** | დვაბზუ payday spike (10, 25); ოზურგეთი steady + seasonal summer uplift |
| **Store comparison (margin drift)** | DNA-based hypothesis first (tourist drop, pay-day shift, category mix) |

---

## 📝 4 Baseline Fact User-იდან (Part B-ის pattern)

ზოგადი DNA საკმარისია **მიმართულების** სასაზღვრავად. მაგრამ **კონკრეტული ციფრები** (promotion pass-through, ტურისტული თვეები, supplier concentration) მხოლოდ შენ იცი. როდესაც AI-ს **ზუსტი** cross-store რეკომენდაცია დასჭირდება, გკითხავს + `journal_add_entry(kind=reminder, tags=["topic:store_dna"])`-ით შეინახავს:

| ფაქტი | რისთვის | როდის კითხვადება |
|---|---|---|
| **1. ტურისტული თვეების ზუსტი ფანჯარა (ოზურგეთი)** | Revenue forecasting + seasonal inventory | Forecast-ის / სეზონური promotion-ის კითხვაზე |
| **2. ხელფასი days (დვაბზუ ლოკალი customer)** | Cash planning + promotion timing | Cash-flow-ის / promotion calendar-ის კითხვაზე |
| **3. Top-3 supplier per store (concentration %)** | Supplier risk radar | Supplier-თემაზე ცხადი ოდიტი |
| **4. Evening : Daytime revenue ratio (ოზურგეთი 3 POS)** | Staffing + evening promo timing | Staff cost / evening rush კითხვაზე |

👉 ეს 4 ფაქტი journal-ში ერთხელ შეინახება, AI-ს ყოველი cross-store რჩევაში ცხადად გაუხსენდება.

---

## ⚙️ რა ეცვლება კოდში

| ფაილი | ცვლილება |
|---|---|
| `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` | ერთი ახალი section `🏪 მაღაზიების DNA (CRITICAL — Phase 1 Part C)` — ~400-600 ტოკენი |
| `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA_INVESTIGATOR` | **untouched** (mandatory do-not-touch rule Sprint 1/2/3/4 + Part A + Part B) |
| `tests/test_ai_prompts_phase1c.py` (ახალი) | ~30-40 ახალი ტესტი — ოზურგეთი DNA presence + დვაბზუ DNA presence + seasonality hint + baseline-fact placeholder mechanism + topological position + investigator untouched |
| ChromaDB / `today_context.py` / `agent.py` / `forecasting.py` / `journal.py` | **untouched** (არ საჭიროა) |

**Prompt-ის ზრდა:** ~400-600 tokens (caching-ით პირველი call-ის შემდეგ warm → ~$0.0001 per call). **Net cost impact:** ~$1-2/თვე.

---

## 🎯 ალტერნატივები (რომელს გაირჩევ)

### Scope ოფცია (რამდენი DNA-ს detail AI-ს head-ში)

- **🔵 A — Core DNA (რეკომენდაცია)** — ზემოთ მოცემული 2 ცხრილი (ტიპი / POS / რეჟიმი / customer / peak / mix / promotion / elasticity) + soft seasonal hint. ~500 tokens. **Coverage:** 90% realistic კითხვების.
- **B — Extended DNA** — A + ცხადი თვე-თვე seasonality calendar (ჯან-დეკ ofhe) + typical basket size per store + top-3 supplier placeholder. ~1000 tokens. **Cost:** +$2-3/თვე. **Risk:** ზუსტი ციფრები user-ის data-დან უნდა მოვიდეს — hardcoded cal შეიძლება დრო გადავიდეს.
- **C — Lean** — მხოლოდ urban vs rural labeling + 3 basic dimension. ~200 tokens. **Coverage:** 60%. **Risk:** "promotion timing", "supplier concentration", "evening staff" კითხვები DNA-free-ით იქნება.

### Baseline fact collection მექანიზმი

- **🔵 I — Auto-journal placeholders (Part B-ის pattern)** — AI პირველი relevant რჩევაზე გკითხავს + `journal_add_entry(kind=reminder, tags=["topic:store_dna"])` შეინახავს. User ცალკე ჩაწერს, მერე ყველა cross-store რჩევაში აფიცირდება.
- **II — Manual only** — user თვითონ ჩამატავს journal-ში; AI-ს არ ეიცის.
- **III — Skip** — baseline fact ცოდნა არ იწერება (AI ყოველ ჯერზე "დამიზუსტე" ეტყვის).

### Seasonality encoding

- **🔵 α — Soft context (რეკომენდაცია)** — "🏪 ოზურგეთი peak: ზაფხული ტურისტული + დეკემბერი holidays" — **hint**, არა hard rule. AI ცხადი ციფრებისთვის `forecast_revenue`-ს გამოიყენებს.
- **β — Hardcoded calendar** — ზუსტი თვეები/თარიღები prompt-ში ჩაფიქსირდება. **Risk:** ტურისტული სეზონი 2026-ში შეიძლება გადაინაცვლოს (ახალი flight route, კურორტის გახსნა, external event), ხოლო prompt stale-ად დარჩება.
- **γ — Skip seasonality** — DNA მხოლოდ structural (POS/customer/elasticity), seasonal context გამოიტანება.

### Investigator prompt

- **🔵 (mandatory carry-over)** — Investigator **untouched** (Sprint 1-4 + Part A + Part B-ის იდენტური do-not-touch წესი).

---

## 🧪 Verification (code-ის შემდეგ)

### 1. pytest
- 30-40 ახალი cases in `tests/test_ai_prompts_phase1c.py`
- 8 test class:
  - `TestStoreDnaSection` (5) — section present + header
  - `TestOzurgeti` (6) — urban/3 POS/12h/tourist/evening peak/premium tilt
  - `TestDvabzu` (6) — rural/2 POS/8h/local/payday/basics tilt
  - `TestSeasonality` (4) — tourist summer + payday days + holidays + soft-hint disclaimer
  - `TestBaselineFacts` (4) — 4 placeholders + journal pattern
  - `TestBuildSystemPromptWiring` (3) — topological position + chat contains + investigator absent
  - `TestInvestigatorPromptUntouched` (4) — 15 markers all absent from investigator
  - `TestStrategicGuidance` (3) — "when to apply DNA" table present
- 0 weakened; Phase 1 Part A + Part B markers **all** retained

### 2. Backend restart #8
- Kill old PID; start parent-venv with `AI_ENABLE_THINKING=true`
- Verify via `Win32_Process.CommandLine` + in-process 15-marker probe
- `/api/status` 200 OK

### 3. Live Anthropic dog-food (1-2 scripted call)

- **Q1** (high-confidence scenario): *"თამბაქოს ფასდაკლება — სად გავაკეთო?"*
  - Expect: ცხადი `🏪 ოზურგეთი YES` + `🏡 დვაბზუ NO` differentiation + DNA-based reasoning (elastic vs inelastic) + 🟢 საიმედო confidence + cross-store cost estimate
- **Q2** (baseline-fact probe): *"შეადარე margin-ი ორ მაღაზიას შორის"*
  - Expect: pulls `data.json → pnl_summary` per store + DNA-based hypothesis (basket size, customer loyalty, category mix) + 📌 ვარაუდი on baseline-fact gap + optional `journal_add_entry(kind=reminder)` placeholder prompt
- **Q3** (optional — strategic expansion): *"ქობულეთში მე-3 მაღაზია გავხსნა — DNA რომელი ემთხვევა?"*
  - Expect: DNA-based hypothesis (urban tourist + seasonal peak → closer to ოზურგეთი profile) + franchise royalty / opening fee from Part B + cash planning context + 🟡 ვარაუდი due to limited data on ქობულეთი specifics

---

## 🚫 Part C-ის ფარგლებში **არა**

- Dashboard UI changes — არა (მხოლოდ AI prompt ცვლილება)
- Store-level dedicated page / widget — არა (Phase 3.6 Supplier Concentration Widget + Phase 2.8 Store Comparison Page ცალკე scope-ია)
- ახალი `data.json` ველი — არა (data layer უკვე ცნობს store-ებს — `forecast_revenue(store=...)` + `pnl_summary.objects["ოზურგეთი"]`)
- Per-store forecasting accuracy improvements — არა (Phase 0B Sprint 2-ში ცოცხლად მუშაობს)
- Automated store-DNA refresh — არა (user manually updates via journal)
- Customer segmentation (Phase 4 Advanced) — არა
- Multi-store ABC analysis (parking lot) — არა

---

## ⏱ Timeline + Cost

| რა | ღირებულება |
|---|---|
| ერთჯერადი სამუშაო (prompt section + 30-40 ტესტი + regression + live dog-food + docs) | **0.5-1 დღე** |
| თვიური ხარჯი (default scope A) | **+$1-2/თვე** (caching-ის შემდეგ) |
| latency | **±0** (cache warm hit) |
| AI ხარისხი | **↑↑↑** — strategic cross-store differentiation live |

**შედარება Part A / Part B-თან:**
- Part A = AI-ის **ხასიათი** (როგორ ფიქრობდეს)
- Part B = AI-ის **გარე სამყაროს კონტექსტი** (რეგულაცია + ფრენჩაიზი)
- Part C = AI-ის **ბიზნესის შიდა ანატომია** (ერთი ბიზნესი სინამდვილეში **ორი ცალკე**)

ერთად სამივე — **Phase 1 Foundation სრული**.

---

## ⚠️ შეზღუდვების სია (გულწრფელი)

1. **DNA-ს ცხადი ციფრები ("45% tourist share") AI-ს არ გააჩნია.** Core DNA კატეგორიული: "mixed customer", "evening peak", "price-inelastic". ზუსტი ციფრი `journal_add_entry` placeholder-ებით დროში დაგროვდება.

2. **Seasonal calendar — generic hint.** ტურისტული ზაფხული 2024-2025-ის data-ზეა ნასაზრდოები. თუ 2026-ში ქობულეთი-ს flight route გახსნა → AI-ს prompt უნდა განახლდეს, ან user-ის journal-ში დააფიქსირებს.

3. **AI-ს შეუძლია DNA over-apply.** კითხვა "რა იყიდე ოზურგეთში?" — ზოგადი ფაქტის კითხვაა, არა strategic. prompt-ში წესი: **DNA გამოიყენე მხოლოდ სტრატეგიულ/რეკომენდაციულ კითხვებზე**, არა simple data lookup-ზე.

4. **Cross-store data შედარებისას DNA-ს პრიმატი.** თუ ოზურგეთი-ს margin 11%, დვაბზუ-ს 2% — AI ჯერ DNA-based hypothesis-ს წარუდგენს (category mix, pricing elasticity, customer type). მაგრამ **გადამოწმებული ფაქტი data.json-იდან მოდის**. DNA არის "რატომ", data არის "რა".

5. **Part C +2-3K tokens უფრო არ ხდის.** Core DNA ~500 tokens; Extended DNA ~1000 tokens. caching-ის შემდეგ cost impact ~$1-2/თვე.

---

## ✅ შემდეგი ნაბიჯი (შენი დადასტურების შემდეგ)

1. user იტყვის "**გააგრძელე**" (default 🔵 A + 🔵 I + 🔵 α) ან ცალკე scope-ი აირჩევს
2. ვწერ კოდს:
   - `prompts.py::SYSTEM_PROMPT_KA` — ერთი ახალი section `🏪 მაღაზიების DNA`
   - `tests/test_ai_prompts_phase1c.py` — ~30-40 ცდა
3. pytest regression → expect **890-900/890-900 green** (860 baseline + 30-40 new)
4. Backend restart #8 + live Anthropic dog-food (1-2 call — promotion + margin comparison)
5. Docs refresh (PLAN, CONTEXT_HANDOFF, HANDOFF, Part C preview promoted DRAFT → ✅ COMPLETE)
6. **Phase 1 სრული** (Part A ✅ + Part B ✅ + Part C ✅) → Phase 2 kickoff (2.11 Dead Stock + 2.12 Supplier Negotiation Prep)

---

## 🔑 Copy/paste user-ისთვის

**default-ით გავაგრძელო?**

- Scope: **🔵 A** (Core DNA — 7-8 dimension per store + soft seasonal hint)
- Baseline collection: **🔵 I** (Auto-journal placeholders)
- Seasonality: **🔵 α** (Soft context, არა hardcoded calendar)
- Investigator: **untouched** (mandatory)

**შენი პასუხი:** "**default**" / "**A + I + α**" / "**B + I + α**" / სხვა ცხადი რჩევა

---

> **შენი პასუხს ვცდები.** თუ `default` მოგწონს, ერთი სიტყვა საკმარისია.
