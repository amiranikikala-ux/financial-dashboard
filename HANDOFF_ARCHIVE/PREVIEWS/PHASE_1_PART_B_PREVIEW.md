# Phase 1 Part B — ქართული ბიზნეს-კონტექსტი — Preview

> **თარიღი:** 2026-04-20 | **სტატუსი:** ✅ **COMPLETE + LIVE VERIFIED** (2026-04-20 01:28)
> **ავტორი:** Cascade
> **ენა:** Plain ქართული (technical jargon გარეშე)
> **Scope:** AI_GENIUS_PARTNER_PLAN.md § 1.11
> **Approved:** user "კი" (default 🔵 A Narrow + 🔵 I Auto-journal + 🔵 α Journal placeholder)
> **Actual Dev time:** ~1 hour (prompt section + 42 tests + live dog-food + docs)
>
> **დახურვის შემაჯამებელი:**
> - Code: `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` new `🇬🇪 ქართული რეგულაცია` section
> - Tests: 42 new cases in `tests/test_ai_prompts_phase1b.py` — pytest **860/860 green** (was 818; +42; 0 weakened)
> - Investigator prompt UNTOUCHED (4 do-not-touch tests)
> - Backend restart #7 — parent-venv PID **36460** live with 15 Part B markers verified in-process
> - Live Anthropic dog-food ✅ — AI used Monthly rhythm rule + Baseline facts mechanism + auto journal on ოზურგეთი POS 20K ₾ capex question (111.72s, $0.19, stop_reason=end_turn)
> - Docs refresh — PLAN.md + CONTEXT_HANDOFF.md + HANDOFF.md
>
> იხილე ქვემოთ გეგმის სრული დეტალი — თავდაპირველი draft დოკუმენტი რჩება archive-ისთვის.

---

## 📖 რა არის ეს დოკუმენტი

**ეს არის გეგმა, არა კოდი.** შენს დადასტურებას ვიღებ — მერე ვწერ.

Phase 1 Part A-ში AI-მ ისწავლა **როგორ** ფიქრობდეს (5 ქუდი, პერსონა, confidence ნიშნები). Phase 1 Part B-ში ისწავლის **სად ცხოვრობს**:

- 🇬🇪 საქართველოს ფინანსური რეალობა (VAT, საპენსიო, შემოსავლის გადასახადი)
- 🏢 RS.ge-ის წესები (ე-ინვოისი, ზედნადები, გადაუხდელი საურავი)
- 🏪 ფრენჩაიზის კონტექსტი (royalty, sourcing, brand standards)

---

## 🧭 რატომ გჭირდება

ახლანდელი AI საქართველოს კონკრეტულ რეგულაციებს "**არ ფიქრობს**". მაგალითად — ვკითხო:

> *"Alpha-ს ვალი გადაცილდება 15 დღეში. რა ვქნა?"*

AI **ახლა** მიპასუხებს:
> "ეს HIGH რისკია: cash-buffer შემცირდება, supply interruption შესაძლოა..."

AI **Part B-ის შემდეგ** მიპასუხებს:
> "ეს HIGH რისკია. **ამას ემატება:**
> - 🇬🇪 VAT დეკლარაცია 15 მაისს — საშუალოდ თვის revenue-ის ~15-18% cash-ად უნდა დევდეს
> - 🏪 ფრენჩაიზი royalty საშუალოდ 5-7% revenue-ის — ეს რიცხვი ცხადად გაქვს?
> - 📄 ე-ინვოისი 30 დღეზე მეტი "გადაუხდელი" სტატუსი RS.ge-ზე შენს reputation-ს აფუჭებს
> - 💡 **რჩევა:** ვაჭრე 10-14 დღის ვადაზე + 5% ფასდაკლებისთვის, არა 30 დღე"

ანუ AI არ გიპასუხებს "ზოგად" რჩევას — **ქართული რეალობის კონტექსტში** გიპასუხებს.

---

## 🎯 ახლა vs Phase 1 Part B-ის შემდეგ

| შენი კითხვა | ახლანდელი AI | Part B-ის შემდეგ AI |
|---|---|---|
| "თვის დასაწყისი — რა cash-ი გამოვყო?" | "depends on your expenses" | "15-მდე გადასახდელები: VAT ~18% revenue-ის, საპენსიო 2%+2% payroll-ის, საშემოსავლო ~1% (მცირე ბიზნესი). **30% revenue-ის dry-powder-ად დატოვე**." |
| "Alpha-ს 5% ფასდაკლება 30 დღე ვადის ნაცვლად" | "შეგიძლია მიიღო" | "30 დღე = ე-ინვოისი "გადაუხდელი" RS.ge-ზე ფაქტობრივად გადავადებად ფიქსირდება. **შეხვდი 14 დღისთვის ნახევარ ფასდაკლებაზე** — RS.ge reputation clean, cash buffer still healthy." |
| "რატომ ძვირია brand-ის პროდუქცია 12%-ით?" | "მაღალი cost" | "ეს **ფრენჩაიზი sourcing obligation**-ის ნიშანია — ჩვეულებრივ 60-75% პროდუქცია brand warehouse-იდან. ალტერნატივა = contract violation, royalty freeze. **შენი კონკრეტული % მითხარი**, ცხადად გადავიანგარიშო net cost." |
| "ახალი მაღაზიის გახსნა ღირს?" | ზოგადი ROI | "🇬🇪 საქართველოში ახალი ობიექტის გახსნა = RS.ge რეგისტრაცია + 18% VAT-ის ახალი cycle + საპენსიო fund დამატება + franchise opening fee (5K-15K USD ჩვეულებრივ). **Break-even გამოანგარიშდება ~6-9 თვე — იცი შენი royalty schedule?**" |

---

## 🧩 რას ჩავწერ AI-ის "თავში"

ყველაფერი ერთ ახალ სექციად `SYSTEM_PROMPT_KA`-ში — `🇬🇪 ქართული რეგულაცია (CRITICAL — Phase 1 Part B)`:

### 🇬🇪 საჯარო საქართველოს რეგულაცია (ყველაზე კომპანიისთვის ერთი)

- **VAT 18%** — ყოველთვიური დეკლარაცია RS.ge-ზე, deadline **15-ე**
- **საპენსიო ფონდი** — 2% დამსაქმებელი + 2% თანამშრომელი, ერიცხება payroll-ს, deadline **15-ე**
- **შემოსავლის გადასახადი** — 15% standard / 1% მცირე ბიზნესი სტატუსით (< 500K ₾ წლიური)
- **ე-ინვოისი** — RS.ge electronic invoice; "გადაუხდელი" სტატუსი 30 დღეზე მეტი = საურავი + reputation hit
- **ზედნადები** — რეგისტრაცია RS.ge-ზე სავალდებულოა; "გააქტიურება" vs "ტრანსპ. დაწყება" vs "ჩაბარება" სამი სხვადასხვა თარიღია (waybill fix-ში უკვე გადაჭრილია)
- **გადაუხდელი საურავი** — CB-ის discount rate + 1% (წელიწადში) ვადაგადაცილებულ გადასახადზე

### 🏪 ფრენჩაიზი კონტექსტი (user-სპეციფიკური, ცხადი მითითებით)

- **Royalty %** — ჩვეულებრივი retail ფრენჩაიზის პარამეტრი 4-7% monthly revenue-ის (AI placeholder-ად ამას იყენებს, მაგრამ user-ს ცხადად ჰკითხავს პირველ ინვესტიციულ რჩევაზე)
- **Sourcing obligation** — brand warehouse-დან შესყიდვის ვალდებულება (ჩვეულებრივ 60-75%); violation = contract breach
- **Brand standards** — მაღაზიის იერსახე, product mix, pricing tier (violation = royalty freeze ან termination)
- **Opening fee** — ახალი ობიექტი = ერთჯერადი franchise fee (ჩვეულებრივ 5-20K USD retail-ში)

### 🌅 ქართული თვის რიტმი (`<TODAY>` block უკვე ფლობს 15-ე deadline-ს)

AI-ს ახსოვს:
- თვის **1-10**: პოსტ-deadline, relative calm, გასახდელი transactions აქტიური
- **11-14**: pre-deadline stress, cash preparation
- **15**: deadline day (VAT + საპენსიო)
- **16-30/31**: revenue accumulation, გადახდების შემზადება

ამ რიტმში AI მართავს recommendation-ებს.

---

## 📝 User-ის ცალსახა საჭირო ცოდნა (4 baseline fact)

ზოგიერთი რამე მე/AI ვერ ვიცით — მხოლოდ შენ ხარ კომპანიის მფლობელი. 4 baseline fact:

| ფაქტი | რა-სჭირდება | როგორ ვგროვებთ |
|---|---|---|
| **1. Royalty %** — მთლიან revenue-ზე | ცხადი % rough estimate-ის ნაცვლად | AI პირველი **ინვესტიციის / ფრენჩაიზი-თემაზე** რჩევაზე გკითხავს + `journal_add_entry(kind=reminder)`-ით შეინახავს |
| **2. Sourcing obligation %** — brand warehouse-დან | ცხადი % rough-ის ნაცვლად | იმავე კითხვას გაერთიანებს |
| **3. შემოსავლის გადასახადის სტატუსი** — მცირე ბიზნესი (1%) / standard (15%) / ფიზ. პირი | cash planning-ში სწორი რიცხვი | AI პირველი **cash planning** რჩევაზე გკითხავს |
| **4. VAT registration სტატუსი** — registered (18% დეკლარაცია) / not registered (< 100K ₾ turnover) | cash planning + pricing-ში | იმავე კითხვას გაერთიანებს |

👉 ამ 4 ფაქტი journal-ში შეინახება (ერთხელ), ყველა ახალ რჩევაში AI-ს დასახელებულ ცხადად გაუხსენდება.

---

## ⚙️ რა ეცვლება კოდში

| ფაილი | ცვლილება |
|---|---|
| `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` | ერთი ახალი სექცია `🇬🇪 ქართული რეგულაცია (CRITICAL — Phase 1 Part B)` — ~500-700 ტოკენი |
| `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA_INVESTIGATOR` | **untouched** (კარგავს კარტოთეკული do-not-touch წესი) |
| `tests/test_ai_prompts_phase1b.py` (ახალი) | ~15-20 ახალი ტესტი — ყველა ცნების presence + investigator-in-absence |
| ChromaDB / `today_context.py` / `agent.py` | **untouched** (არ საჭიროა) |

**ერთი ზემოქმედება input cost-ზე:** prompt +3-5K ტოკენი (cached გახდება პირველი call-ის შემდეგ, რე-expense არ გაიწევს).

---

## 🎯 ალტერნატივები (რომელს გაირჩევ)

### Scope ოფცია (რომელი რეგულაციები ჩავწერო AI-ის "თავში")

- **🔵 A — Narrow (რეკომენდაცია)** — საჯარო საქართველოს რეგულაცია + franchise conventions ზოგადი (4-7% royalty, 60-75% sourcing). User-სპეციფიკური რიცხვები — journal-ში.
- **B — Wide** — A + კონკრეტული franchise-ის rules წინასწარ (user-ს მომცემ კონტრაქტის კითხვარს 10-15 detail-ზე). **შედარებით**: უფრო მდიდარი რჩევები, **მაგრამ** +5K tokens input-ს = ~20-30% cost increase ყოველ ჩატზე.
- **C — Basic** — მხოლოდ VAT + საპენსიო + RS.ge (franchise context-ი გამოტოვებული). **შედარებით**: ყველაზე იაფი, მაგრამ Alpha-ს ვალი / ახალი მაღაზია რჩევები ცალკე კონტექსტს დაკარგავენ.

### Baseline fact collection მექანიზმი

- **🔵 I — Auto-journal baseline placeholders** — AI პირველი relevant რჩევაზე იკითხავს + `journal_add_entry(kind=reminder)` შეინახავს. User ცალკე ჩაწერს, მერე ყველა რჩევაში აფიცირდება.
- **II — Manual only** — user თვითონ შეიძლება ჩამატოს journal-ში ზოგადი prompt-ით; AI-ს არ ეიცისs.
- **III — Skip** — baseline fact ცოდნა არ იწერება (AI ყოველ ჯერზე "დამიზუსტე" ეტყვის).

### Income tax / VAT status

- **🔵 α — Journal placeholder** (recommended) — baseline fact-ებს კატეგორიად შეინახავს.
- **β — Hard-code in prompt** — user ცხადად მომცემს. **პრობლემა:** AI ცდილობს "მცირე ბიზნესი"-ს ვარაუდს ყოველთვის; თუ user-ის სტატუსი შეიცვალა, prompt უნდა განახლდეს.

### Investigator prompt

- **🔵 (mandatory carry-over)** — Investigator **untouched** (იგივე Sprint 1-4 + Phase 1 Part A-ს do-not-touch წესი).

---

## 🧪 Verification (code-ის შემდეგ)

1. **pytest** — 15-20 ახალი cases + 0 weakened; ფაზი 1-ის persona marker-ი ისევ present; investigator untouched (absent)
2. **Backend restart #7** — parent venv, `AI_ENABLE_THINKING=true`
3. **Live Anthropic dog-food** — 1-2 სკრიპტული `/api/chat` call:
   - Q1: "თვის დასაწყისი — cash-ის გამოყოფა" → expect 15-ე deadline + VAT/pension/income math, confidence mark
   - Q2: "ფრენჩაიზი royalty რა ვიცით?" → expect 4-7% assumption + journal-prompt for user-ს ცხადი %
   - Q3 (optional): "ე-ინვოისი 30 დღე გადაცილდა Alpha-სთვის" → expect 30-day საურავი + RS.ge reputation warning

---

## 🚫 Part B-ის ფარგლებში **არა**

- Dashboard UI changes — არა (მარტო AI prompt)
- RS.ge API integration — არა (Phase 4+ ოპცია, user-ს ცხადი request არ გაუკეთებია)
- E-invoice auto-parse — არა (manual for now)
- Tax category automation — არა (manual-data.json sync)
- Payroll automation — არა (parking-lot)

---

## ✅ შემდეგი ნაბიჯი (შენი დადასტურების შემდეგ)

1. user იტყვის "**გააგრძელე**" (default რეკომენდაციებით: 🔵 A + 🔵 I + 🔵 α) ან ცალკე scope-ი აირჩევს
2. ვწერ კოდს: `prompts.py` ერთი ახალი section + `tests/test_ai_prompts_phase1b.py` ~15-20 ცდა
3. pytest regression
4. Backend restart #7 + live Anthropic dog-food (1-2 call)
5. Docs refresh (PLAN, CONTEXT_HANDOFF, HANDOFF)
6. Phase 1 Part C preview (1.12 Multi-Store DNA)

---

## 🔑 Copy/paste user-ისთვის

**default-ით გავაგრძელო?**
- Scope: 🔵 A (Narrow — საჯარო რეგულაცია + franchise conventions)
- Baseline collection: 🔵 I (Auto-journal placeholders)
- Tax/VAT status: 🔵 α (Journal placeholder, არა hardcoded)

**შენი პასუხი:** "**default**" / "**A + I + α**" / "**B + I + α**" / სხვა ცხადი რჩევა
