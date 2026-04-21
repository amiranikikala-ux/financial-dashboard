# AI Genius Financial Partner — Master Plan

> **ვერსია:** 2.1 | **თარიღი:** 2026-04-18 | **სტატუსი:** Active
> **პროექტი:** იოლი მარკეტი ფრენჩაიზი — Financial Dashboard
> **Supersedes:** `AI_ADVISOR_ROADMAP.md` v1.0 (Phase 3+ deprecated), `AI_GENIUS_PARTNER_PLAN.md` v2.0

---

## 📝 რა შეიცვალა v2.0 → v2.1 (2026-04-18 საღამოს განახლება)

**დამატებული:**
- 🆕 **Phase 0A — Critical Foundation** (3 ფუნდამენტური ცვლილება): არითმეტიკის კალკულატორი, თვითკრიტიკის ციკლი, დღის პულსი
- 🆕 **Phase 1-ში** ქართული ბიზნეს-კონტექსტი (RS.ge + ფრენჩაიზი + Multi-Store DNA) expanded
- 🆕 **Phase 2-ში** Dead Stock Liquidation + Supplier Negotiation Prep
- 🆕 **Parking Lot** სექცია — ~40 დამატებითი feature მომავალი იტერაციებისთვის

**არ შეცვლილა:**
- ფილოსოფია, 6 სვეტი, user preferences
- Phase 3, Phase 4, 10 dashboard feature
- Cost ($40-95/თვე)

**Timeline:** 4.5-5 კვირა → **5.5-6 კვირა** (Phase 0A-ის დამატების გამო)

---

## 🧠 ფილოსოფია

AI არის **სტრატეგიული პარტნიორი**, არა database lookup robot. ის:
- ფიქრობს, აზრს გამოთქვამს, აკრიტიკებს
- შემოგთავაზებთ გადაწყვეტილებებს
- თვითონ სთავაზობს პროექტის გაფართოებას
- ადევნებს საკუთარ რჩევებს

**Read-only** — არასდროს ცვლის კოდს/data-ს/Excel-ს. მხოლოდ კითხვა, ანალიზი, რჩევა. User-ი action-taker.

---

## 🏛 6 სვეტი

| # | სვეტი | გულისხმა |
|---|---|---|
| 1 | 🧠 ცოდნა | დღევანდელი, ისტორიული, ბიზნესი, პროექტი |
| 2 | 💭 აზროვნება | კრიტიკული, სკეპტიკური, მკაცრი, ფაქტებით შებოჭილი |
| 3 | 📚 მეხსიერება | წინა საუბრები, decision-ები, outcome-ები |
| 4 | 🔬 ანალიტიკა | On-demand specialized tools |
| 5 | 🎨 Co-Designer | თავად სთავაზობს feature/page/report |
| 6 | ✅ პასუხისმგებლობა | საკუთარი რჩევის tracking + retrospective |

---

## 🎯 User Preferences (baseline — mandatory)

- ✅ Chat-on-demand (pull, not push)
- ✅ მკაცრი, მომთხოვი ტონი (არა soft, არა flattery)
- ✅ ღრმა აზროვნება (intelligence > cost)
- ✅ მეხსიერება + ბუნებრივი recall
- ✅ Co-designer behavior
- ❌ Push notifications / Daily briefing / Telegram push
- ❌ Technical jargon user-თან (plain ქართული ყოველთვის)
- ❌ Write access (NEVER, non-negotiable)
- ❌ Voice input (distraction)
- ❌ Multi-LLM routing (Sonnet 4.6 optimal)

---

## 🔴 Phase 0A — Critical Foundation (2-3 დღე) 🆕

**მიზანი:** 3 ფუნდამენტური დაცვა, რომელთა გარეშე ყველა დანარჩენი feature სუსტ ნიადაგზე დგას.

---

### 0A.1 🧮 არითმეტიკის კალკულატორი (Calculator Enforcement)

**რას აკეთებს:** AI-ს აეკრძალება რიცხვების ჯამი/საშუალო/%/ცვლილება "გონებაში". ყოველ ციფრულ ოპერაციას გადის ერთ უსაფრთხო კალკულატორში (Python sandbox, limited).

**რატომ გჭირდება:** 27 თებერვლის waybill-bug ზუსტად აქ მოხდა — AI-მ "გონებაში" დათვალა 20 რიცხვი და გამოუვიდა 7,246 ₾ (სწორი: 7,882.68). ერთი ცდომილება ერთ გადაწყვეტილებაში → რეალური ფული.

**შედეგი:** ყოველი ციფრი, რაც AI-მ გითხრათ, შეგიძლიათ ენდოთ როგორც Excel-ის ფორმულას. "დაახლოებით..." პასუხები ქრება.

---

### 0A.2 🪞 თვითკრიტიკის ციკლი (Self-Critique Loop)

**რას აკეთებს:** AI ჯერ ადგენს პასუხის draft-ს → შემდეგ თვითონ საკუთარ თავს სვამს 3 კითხვას:
1. რა დავუშვი? (რა ფაქტი არ გადავამოწმე)
2. რაში ვერ ვარ დარწმუნებული?
3. რა პრობლემა აქვს ჩემს ლოგიკას?

მხოლოდ ამის შემდეგ თქვენ ხედავთ პასუხს.

**რატომ გჭირდება:** დღევანდელი AI შეიძლება სრული დარწმუნებით ცდებოდეს. Self-critique არის "ფრთხილი მრჩეველის" ნიშანი. გეგმაში არსებული "Sub-agent Debate" (Phase 0.7) მხოლოდ "მნიშვნელოვან" კითხვებზე მუშაობს — Critical Foundation-ში ეს ხდება **ყოველი** პასუხისთვის (მოკლე version).

**შედეგი:** "შპს X რისკია" ხდება → "X-ის ვალი 18K ₾, 45 დღე ვადა გადაცილებული. მაგრამ `manual_payments.csv` 3 დღე ძველია — შეიძლება უკვე გადახდილია. გადაამოწმე."

---

### 0A.3 🌅 დღის პულსი (Today's Pulse — Automatic Preamble)

**რას აკეთებს:** ყოველი ახალი ჩატის დასაწყისში AI 2-3 წამში თვითონ კრებს:
- დღევანდელი თარიღი + დღის სახელი
- გუშინდელი POS ჯამი (ოზურგეთი + დვაბზუ ცალცალკე)
- 7-დღიანი cash-forecast (მიღებული vs გასაცემი)
- Top 3 საფრთხე (POS-ის ჩავარდნა, ვადამოსული გადახდა, უცნაური ნომერი)

ეს კონტექსტი ავტომატურად ემატება ყოველ თქვენს კითხვას.

**რატომ გჭირდება:** ახლა ყოველი ჩატი "ცარიელი ფურცლით" იწყება — AI-მ არ იცის გუშინ რა მოხდა. Phase 1.3 "today-awareness" არსებობს, მაგრამ მხოლოდ თარიღი. ნამდვილი მრჩეველი შეხვედრაზე "უკვე რიცხვებით ხელში მოდის".

**შედეგი:** პირველივე კითხვაზე — "რა ვაკეთო დღეს?" — AI პასუხობს კონტექსტში: "დღეს 18 აპრილი. გუშინდელი ოზურგეთი +14,200 ₾, დვაბზუ −18% (POS30BWH 0 ₾ — შეამოწმე ტერმინალი). მომდევნო 5 დღეში გადასახდელი 34K, მოსალოდნელი 28K. Top priority: ტერმინალი + Alpha-ს 23K მესამე დღეს."

---

## 📋 Phase 0B — Genius Core (4-5 დღე)

**მიზანი**: AI engine genius-level — 7 upgrade.

| # | Feature | რას აკეთებს | რატომ |
|---|---|---|---|
| 0B.1 | 🧠 Extended Thinking | მნიშვნელოვან კითხვამდე 30-60 წმ ფარულად ფიქრობს | Depth radically up |
| 0B.2 | 🔎 Semantic Memory (ChromaDB) | Vector search keyword-ის ნაცვლად | Natural recall |
| 0B.3 | 🌐 Web Search | Currency, inflation, news, regulatory | External world awareness |
| 0B.4 | 📚 RAG full project | Excel + conversations + code indexed | AI-ს head-ში მთელი პროექტი |
| 0B.5 | 🧪 Multi-hypothesis | 3 alternative ყოველ მნიშვნელოვან კითხვაზე | Depth, not surface |
| 0B.6 | 🔮 Advanced Forecasting | Prophet + ARIMA + ensemble | Trend + seasonality |
| 0B.7 | 🤖 Sub-agent Debate | auditor + skeptic + creative internal | Decision quality up |

Cost: ~$30-80/თვე heavy. ROI: 1 good decision > $1,000.

---

## 📋 Phase 1 — Foundation (4 დღე)

| # | Feature |
|---|---|
| 1.1 | ფილოსოფიის shift (system prompt revolution) |
| 1.2 | 5 ქუდი (multi-role) |
| 1.3 | დღევანდელი მდგომარეობა (today-awareness pre-call) |
| 1.4 | პროექტის რუკა (business + architecture) |
| 1.5 | ფაქტი vs ფიქცია (anti-hallucination strict) |
| 1.6 | Confidence + assumption framework |
| 1.7 | სკეპტიკური data-ზე |
| 1.8 | მკაცრი/მომთხოვი ტონი |
| 1.9 | Tool limit 6 → 12 |
| 1.10 | Source-of-truth hierarchy (Excel > data.json) |
| 🆕 1.11 | **ქართული ბიზნეს-კონტექსტი (RS.ge + ფრენჩაიზი)** — VAT 18%, ყოველთვიური დეკლარაცია, e-ინვოისი, "იოლი მარკეტი" royalty + compliance rules |
| 🆕 1.12 | **Multi-Store DNA** — ოზურგეთი (urban, 3 POS, 12-საათიანი) vs დვაბზუ (rural, 2 POS, სხვა customer, სხვა პიკი) — AI ცნობს განსხვავებებს |

### 🆕 1.11 ქართული ბიზნეს-კონტექსტი (RS.ge + ფრენჩაიზი)

**რას აკეთებს:** AI-ს system prompt-ში ჩაწერილი ცოდნა საქართველოს ფინანსური რეალობის შესახებ:
- VAT 18%, ყოველთვიური დეკლარაცია RS.ge-ზე
- შემოსავლის გადასახადი, საპენსიო ფონდი, მცირე ბიზნესის სტატუსი
- ე-ინვოისი, ზედნადების წესები, გადაუხდელი საურავი
- "იოლი მარკეტი" ფრენჩაიზის ცნობილი rules (royalty %, sourcing obligations, brand standards)

**რატომ გჭირდება:** ბევრი AI დავალება ფინანსურ მრჩეველობაში ქართული რეალობის გარეშე fake-ია. "margin 7%"-ზე საუბარი VAT-ის და საპენსიო ფონდის გაუთვალისწინებლად არასწორია.

**შედეგი:** AI პასუხები ქართულ რეალობაში წერტილ-წერტილ ჯდება. "თვის გადასახდელი 4,200 ₾ VAT + 1,800 ₾ საპენსიო + 900 ₾ საშემოსავლო — ჯამში 6,900 ₾ მომდევნო 15-ში."

---

### 🆕 1.12 Multi-Store DNA

**რას აკეთებს:** AI-ს ცოდნაში ფიქსირებული განსხვავება ორ მაღაზიას შორის:
- ოზურგეთი — urban, 3 POS, 12-საათიანი რეჟიმი, მაღალი traffic, ტურისტი customer
- დვაბზუ — rural, 2 POS, 8-საათიანი, ადგილობრივი customer, შაბათ-კვირა პიკი
- product mix, seasonality, supplier preference განსხვავებული

**რატომ გჭირდება:** ერთიდაიგივე რჩევა ორივე მაღაზიას არ უხდება. დვაბზუში "discount promotion" ოზურგეთის style-ზე შეიძლება არ იმუშაოს. AI უნდა ფიქრობდეს ორ ცალკე ბიზნესზე.

**შედეგი:** "თამბაქოს ფასდაკლება" → "ოზურგეთში YES (18%+ traffic peak vs week), დვაბზუში NO (ლოკალ customer რბილი volume, margin compression won't recover)".

---

## 📋 Phase 2 — Deep Analytics (5 დღე)

| # | Feature | მაგალითი |
|---|---|---|
| 2.1 | 💰 Cash Flow Projection | "14-18 მაისში cash −15K რისკი" |
| 2.2 | 🧪 Scenario Simulator | "+5% ფასი → −8% volume, +2K profit" |
| 2.3 | 📊 Industry Benchmark | "Margin 7.2% vs median 5% — ahead" |
| 2.4 | ⚠️ Supplier Risk Radar | "ვასაძე 18K AP, delayed 3x, HIGH" |
| 2.5 | 📦 Product Profitability X-Ray | "12 product margin −2% — დაღუპვა" |
| 2.6 | 🎯 Promotion Candidate Finder | "5 candidate ოზურგეთისთვის" |
| 2.7 | 🔎 Supplier Deep-Dive | Full one-supplier profile |
| 2.8 | 🏪 Store Comparison | "Margin 11% vs 2%" |
| 2.9 | 📈 Trend Detector | "Category YoY +11% price, −4% volume" |
| 2.10 | 🔄 Multi-source Triangulation | "Excel vs data.json 6.6% diff" |
| 🆕 2.11 | 💀 **Dead Stock + Salvage Plan** — 90+ დღე გაუყიდავი პროდუქცია + ფასდაკლების/დაბრუნების გეგმა |
| 🆕 2.12 | 📞 **Supplier Negotiation Prep** — მომწოდებელთან შეხვედრის წინ 1-pager: ჩემი volume, payment reliability, comparables |

### 🆕 2.11 Dead Stock + Salvage Plan

**რას აკეთებს:** AI იდენტიფიცირებს პროდუქციას, რომელიც 90+ დღე დევს stock-ში გაუყიდავი. თითოეულისთვის ადგენს:
- რამდენი ფული იყინება ამ stock-ში
- რა ფასდაკლებით შეიძლება გაიყიდოს (ისე რომ cost covered)
- მომწოდებელთან დაბრუნება შესაძლებელია თუ არა
- გაყიდვის მოსალოდნელი დრო ფასდაკლების შემდეგ

**რატომ გჭირდება:** Dead stock არის "გაყინული ფული" — ფულის სურვილი არის, მაგრამ ფული stock-ში დგას. მცირე მაღაზიისთვის ეს შეიძლება იყოს 20-50K ₾ working capital.

**შედეგი:** "ამჟამად 34,500 ₾ dead stock-ია. გირჩევ: 12 SKU −30% ფასდაკლება → მოსალოდნელი liquidation 3 კვირაში, freed cash 24K ₾. 4 SKU მომწოდებელს დაუბრუნე (contractual return 100%). 2 SKU ვერ გაიყიდება — write-off."

---

### 🆕 2.12 Supplier Negotiation Prep

**რას აკეთებს:** მომწოდებელთან ფასის/ვადის ვაჭრობის წინ AI ამზადებს 1-გვერდიან ცნობას:
- ჩემი ჯამური volume (ამ მომწოდებლიდან წლის განმავლობაში)
- გადახდის ისტორია (ვადაში/ვადაგადაცილებული)
- იგივე პროდუქტზე სხვა მომწოდებლების ფასები (comparables)
- 2-3 შესათავაზებელი ფორმულირება ("7% ფასდაკლება 30-დღიანი payment-ს გადაცვლით")

**რატომ გჭირდება:** ვაჭრობა ძალაუფლების თამაშია. ცარიელი ხელით შესვლა ნიშნავს ცარიელი ხელით გამოსვლას. AI ამზადებს "leverage"-ს წინ.

**შედეგი:** "Alpha-სთან შეხვედრის წინ: შენი volume 2025 — 234,500 ₾ (#1 მომწოდებელი), payment reliability 94% (6/96 ვადა გადაცილებული). Comparable supplier (Beta) იგივე კატეგორიაზე 4-7% უფრო იაფი. შენი leverage: ან ფასი ჩამოწიოს 5%, ან გადაცი 14 → 30-დღიან payment term-ზე."

---

## 📋 Phase 3 — Co-Designer + Memory (4 დღე)

| # | Feature |
|---|---|
| 3.1 | 🎨 Co-Designer Mode (structured proposals) |
| 3.2 | 🧠 Persistent Memory (SQLite + ChromaDB) |
| 3.3 | 📋 Conversation Summary on-demand ("ვაჯამებდეთ") |
| 3.4 | ✅ Decision Journal (rec → action → outcome) |
| 3.5 | 💰 Cash Runway Widget (Dashboard) |
| 3.6 | ⚠️ Supplier Concentration Widget |
| 3.7 | 💀 Product Death Row page |
| 3.8 | 📉 Margin Compression Radar |
| 3.9 | 🗓 Monthly Strategy Page (user's idea) |
| 3.10 | 🎯 Gap Analysis |

---

## 📋 Phase 4 — Advanced Strategy (5 დღე)

| # | Feature |
|---|---|
| 4.1 | 📅 Monthly Strategy Generator (auto-draft) |
| 4.2 | 📊 Quarterly Strategic Review |
| 4.3 | 🎯 Long-term Goals Tracker |
| 4.4 | 🧪 Advanced Multi-variable Scenario |
| 4.5 | 💥 Stress Test (worst-case + mitigation) |
| 4.6 | 🎓 Financial Literacy Teacher |
| 4.7 | 🔄 Retrospective / Learning Loop |
| 4.8 | 🎁 Executive Summary Generator |
| 4.9 | 📊 Visualization Suggester |
| 4.10 | 🌐 Peer Comparison Extended |

---

## 🎁 10 ახალი Dashboard Feature (user-facing)

1. 🎯 თვიური სტრატეგიის Tab (Phase 3.9, 4.1)
2. 💰 Cash Runway Widget (Phase 3.5)
3. ⚠️ Supplier Concentration Widget (Phase 3.6)
4. 💀 Product Death Row page (Phase 3.7)
5. 📉 Margin Compression Dashboard (Phase 3.8)
6. 📋 Decision Journal Tab (Phase 3.4)
7. 🏪 Store Comparison Page (Phase 2.8)
8. 🧪 Scenario Simulator Page (Phase 4.4)
9. 🎓 Financial Coach Widget (Phase 4.6)
10. 🎁 Quarterly Review Tab (Phase 4.2)

---

## 🅿️ Parking Lot — მომავალი იტერაციებისთვის (v2.1 არ მოიცავს)

ქვემოთ ჩამოთვლილი ~40 feature **პროფესიული** AI advisor-ის სრულ arsenal-ს ქმნის, მაგრამ v2.1-ში არ შედის — execution focus-ის გამო. როცა Phase 0A + Phase 0B + Phase 1 + Phase 2 მზადაა, ვუბრუნდებით სიას და ვირჩევთ მომდევნო batch-ს.

### Phase 0 Advanced (8 feature)
- 🎯 Confidence Calibration (ნამდვილი % — არა ცრუ "95%")
- 📝 Reasoning Trace (AI-ს ფიქრი საჯარო)
- ⚡ Parallel Tool Calls (სიჩქარე 5x)
- 🗜 Context Compression (გრძელი ჩატი იკუმშება, recall რჩება)
- 🛡 Fallback Mode (Anthropic API down → local minimum)
- 🎚 Prompt Version Control + A/B testing
- 🔐 Advanced Hallucination Detector (3-layer filter)
- 📊 Per-call Cost Dashboard

### Phase 1 Advanced (10 feature)
- 🇬🇪 ქართული ფინანსური ლექსიკა ("შავი/თეთრი", "ფრთხილი ხარჯი", "ქუდი")
- 💵 ვალუტა/ერთეულის ნორმალიზება (USD/GEL/EUR, კგ/ლიტრი/ცალი)
- ⏰ რთული დროის ლოგიკა ("წინა სამშაბათიდან ახლავე")
- 🎄 Georgian Holidays + Seasonality (ახალი წელი, აღდგომა, 9 აპრილი, ტურისტული სეზონი)
- ⚖ Source-of-truth Conflict Protocol (Excel vs data.json vs manual vs bank)
- 🕳 "არ ვიცი" Awareness (data gap-ების აქტიური იდენტიფიცირება)
- 🕘 Data Freshness Tracker (ფაილი ძველია — AI იცის)
- 🚨 Data Quality Guardrails (feb 30, negative sales → AI ეჭვი)
- 🎭 User Communication Preferences Memory
- 🧠 Mode Adaptation (stress signals → ტონი რბილდება)

### Phase 2 Advanced (13 feature)
- 🔤 ABC Analysis (80/20 ფოკუსი)
- 🛒 Customer Basket Analysis (POS co-occurrence)
- 💸 Supplier Payment Term Optimizer
- 🎰 POS-level Anomaly (ოზ.POS1 vs POS2 vs POS3)
- 🏷 Discount Effectiveness Measurement
- 🍴 Category Cannibalization Detector
- 📐 Price Elasticity per-SKU
- 💰 Working Capital Cycle Optimizer (cash-to-cash days)
- 🦹 Fraud / Cash Discrepancy Radar (Z-report vs drawer vs bank)
- 👷 Employee/Shift Performance (POS-attributable)
- 📉 Shrinkage Quantification (inventory vs sales loss)
- 🗓 Reorder Point + Stockout Prediction
- 🏭 Vendor Contract Review (terms vs market)

### Phase 3 Advanced (10 feature)
- 📋 Action Item Extractor (ჩატი → todo)
- 🎬 Decision Replay ("X თვის წინ რა გადავწყვიტე, შედეგი?")
- 🧬 Hypothesis Tracker (AI-ს რჩევები vs რეალური outcome)
- 🧠 Multi-Level Memory (short/medium/long + declarative/episodic/procedural)
- 🎓 Teaching Moments (ახსნა inline)
- 📊 Risk Register (ყველა რისკი ერთ ადგილას)
- 🌱 Growth Opportunities Board
- 📚 Learning Log ("რა ვიცი შენი ბიზნესის შესახებ")
- 🏆 Success Log (რომელმა რჩევამ იმუშავა)
- 🧾 Audit Log

### Phase 4 Advanced (12 feature)
- 🕵 Competitor Surveillance (web-monitored)
- 🗺 Location Scoring (მე-3 მაღაზიის adres)
- 📉 Macro Tracker (GEL/USD, ინფლაცია)
- 🏛 Regulatory Calendar + Deadline Alerts
- 🧑‍🤝‍🧑 Customer Segmentation (თუ ID data)
- 🎁 Loyalty Program Designer
- 📆 Seasonal Staffing Plan
- 🤝 M&A Scenario (ყიდვა vs გახსნა)
- 🚪 Exit Strategy (3-წლიანი valuation)
- 📈 Long-term Trend Detection (3-წლიანი)
- 🏥 Business Health Score (1-10)
- 🎯 Goal Progress Tracker

### Dashboard Advanced (5 feature)
- 🌅 Today's Pulse Widget (header-permanent)
- 🔔 Smart Notification Center
- 📱 Mobile Quick-View Card
- 📄 AI-Generated Weekly PDF
- 🕐 Regulatory Deadline Banner

---

## 📅 Timeline — 5.5-6 კვირა

```
კვირა 1       Phase 0A —  Critical Foundation (3 ფუნდამენტური) 🆕
კვირა 1-2     Phase 0B —  Genius Core
კვირა 2       Phase 1  —  Foundation (12 feature, 2 new)
კვირა 2-3     Phase 2  —  Deep Analytics (12 feature, 2 new)
კვირა 3-4     Phase 3  —  Co-Designer + Memory
კვირა 4-5     Phase 4  —  Advanced Strategy
```

Approval gate ყოველ Phase-ზე — user-ს შეუძლია stop/iterate.

---

## 💸 Cost

| Layer | თვიური |
|---|---|
| Anthropic API (Sonnet 4.6) | $20-50 |
| Extended Thinking | $10-20 |
| Web Search | $5-15 |
| ChromaDB + embeddings | $5-10 |
| **სულ heavy** | **$40-95/თვე** |

ROI: 1 good decision > $1,000. No-brainer.

**შენიშვნა v2.1:** Phase 0A (Critical Foundation) extra cost ≈ $0 — calculator sandbox-ი local, self-critique იყენებს იმავე API call-ს (inner reflection), today's pulse იყენებს ერთ extra call/day.

---

## ❌ Don't-Do List

- ❌ Daily/weekly push notifications
- ❌ Telegram push bot
- ❌ Automatic email/SMS alerts
- ❌ Voice input (Whisper)
- ❌ Provider migration (Kimi/Gemini)
- ❌ LangGraph migration
- ❌ **Write access** — NEVER (absolute)

---

## 📦 რა დარჩა ძველი plan-იდან

### ✅ Preserved
- Dashboard Phase 1-10 — all done
- AI Phase 1 (Chat MVP) — done
- AI Phase 2 Sprint 1-3 (Investigator + waybill fix) — done
- Handoff workflow + PLAN/HANDOFF/CONTEXT_HANDOFF system — untouched

### ⏳ Pending (prerequisite to Phase 0A)
- Backend restart (user action) — Waybill fix live activation
- Waybill live verify — Feb 27 (7,882.68 ₾), Feb 28 (2,675.86 ₾), ambiguous, contradictory prompts

### 🗑 Deprecated / removed
- Old Phase 3 (Daily Briefing + Telegram push) — user rejected
- Old Phase 4-5 (Scenarios, Full Advisor) — merged into new Phase 2+4
- Provider migration POC — rejected
- Voice input — rejected

---

## 🔄 Current Status (2026-04-18)

**Active**: Pre-Phase 0A (approval + prerequisites).

**Blockers**:
1. Backend restart needed for Waybill live verify (user action)
2. Phase 0A + 0B + Phase 1 (1.11, 1.12) + Phase 2 (2.11, 2.12) prompt text preview pending user review BEFORE code

**Next step**: 
1. User approves v2.1 → ✅ DONE (2026-04-18 საღამოს)
2. Cascade drafts Phase 0A Critical Foundation prompt text preview in plain Georgian
3. User reviews + approves
4. Phase 0A code implementation (2-3 დღე)
5. Phase 0B Genius Core kickoff

---

## 📌 Authoritative Documents

| File | Purpose |
|---|---|
| `AI_GENIUS_PARTNER_PLAN.md` (this, v2.1) | Master plan — authoritative |
| `PLAN.md` | High-level status + pointer here |
| `CONTEXT_HANDOFF.md` | Active packet + copy/paste brief |
| `HANDOFF.md` | Slim banner + packet evidence |
| `HANDOFF_ARCHIVE/` | Historical evidence |
| `AGENTS.md` | Project rules (incl. plain Georgian rule) |
| `AI_ADVISOR_ROADMAP.md` | Legacy — Phase 1-2 evidence, Phase 3+ deprecated |

---

## 📞 კომუნიკაციის წესი (built-in)

`AGENTS.md`-ში გადაწერილი rule — AI Chat Assistant system prompt (Phase 1.1) მოიცავს:

- ქართული plain language
- "რას აკეთებს + რატომ გჭირდება + შედეგი რა იქნება"
- ფაილის სახელი მხოლოდ user-ის ცალკე ნახსენები
- ტექნიკური ცნება: ჯერ მაგალითი, მერე სახელი (optional)
- Self-check: "პროგრამისტი რომ არ ყოფილიყო, გაიგებდა?"
