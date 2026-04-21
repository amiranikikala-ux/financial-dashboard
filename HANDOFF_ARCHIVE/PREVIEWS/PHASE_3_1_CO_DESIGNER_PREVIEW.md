# Phase 3.1 — Co-Designer Mode — ✅ COMPLETE + LIVE VERIFIED

> **სტატუსი:** ✅ COMPLETE + LIVE VERIFIED (2026-04-20 17:50) — Backend #11 PID 29400, 3/3 dog-food PASS, 0 failures
> **მიღების თარიღი:** 2026-04-20 16:20 → **დასრულების თარიღი:** 2026-04-20 17:50
> **წინაპირობა:** Phase 1 A+B+C+D ✅ + Phase 2.11 + 2.12 ✅ (ცოცხლად დამოწმებული)
> **ფაქტობრივი ვადა:** ~1.5 სთ (კოდი + 79 ტესტი + ცოცხალი გამოცდა)

---

## ✅ მიღების მტკიცებულებები (LIVE VERIFIED 2026-04-20 17:50)

### Code changes
- `dashboard_pipeline/ai/journal.py`: `JOURNAL_KINDS` გაფართოვდა — `proposal` (5→6); 6 proposal_* metadata key; `cleanup_stale_proposals()` 30-დღიანი auto-cleanup
- `dashboard_pipeline/ai/tools.py`: `TOOL_SCHEMAS` 15→**16**; ახალი `propose_feature` tool (index 15); dispatcher route
- `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA`: 🎨 Co-Designer section (PULL-ONLY + 6 trigger phrases + anti-trigger + 6-field format + 🪞 critic mandate + ID citation + 3-proposal cap)
- `SYSTEM_PROMPT_KA_INVESTIGATOR`: **UNTOUCHED** (0/6 Co-Designer markers — do-not-touch rule ✅)

### Tests: 1242/1242 green (+79 net, 78 new + 1 renamed)
- `tests/test_ai_co_designer.py` — NEW, 78 cases (proposal kind / metadata / add/list/update / cleanup / tool schema / dispatch / prompt wiring / anti-trigger / investigator untouched)
- 6 existing tests updated: `test_ai_journal.py`, `test_ai_tools.py`, `test_ai_memory.py`, `test_ai_forecasting.py`, `test_ai_investigator.py`, `test_ai_supplier_brief.py` (TOOL_SCHEMAS=16 + JOURNAL_KINDS +proposal)
- `test_ai_agent.py::test_investigate_mode_preserves_tool_surface` — expected set bumped to include `propose_feature`
- `test_ai_journal.py::test_every_kind_registers` — teaches iteration to pass 6 proposal fields when `kind=='proposal'`

### Backend restart #11 (PID 29400)
- `$env:AI_ENABLE_THINKING="true"` + `Start-Process ...\venv\Scripts\python.exe -u server.py` → PID 29400 listening on 127.0.0.1:8000
- `/api/status` → 200 OK ✅
- `Get-CimInstance Win32_Process -Filter "ProcessId=29400"` → CommandLine = `...\venv\Scripts\python.exe -u server.py` (parent-venv ✅)
- In-process probe: `TOOL_SCHEMAS=16` ✅ / `TOOL_SCHEMAS[-1]=propose_feature` ✅ / `AIConfig.enable_thinking=True` ✅ / chat markers 6/6 ✅ / investigator 0/6 ✅

### Live dog-food 3/3 PASS (real Anthropic Sonnet 4.6, `/api/chat/stream` `think=true`)
| # | Scenario | Question | Expected | Actual | Result |
|---|---|---|---|---|---|
| A | TRIGGER | *"რას შემომთავაზებდი Dashboard-ზე? 2-3 იდეა მომეცი."* | 1-3 propose_feature calls | **3** calls (+ journal_list_entries + recall_context first) | ✅ 146.1s |
| B | ANTI-TRIGGER strategic | *"რატომ არის ოზურგეთის margin −80%?"* | 0 propose_feature calls | **0** calls (used compute + 5× read_data_json) | ✅ 75.4s |
| C | ANTI-TRIGGER data | *"რამდენი მომწოდებელი გვყავს?"* | 0 propose_feature calls | **0** calls (1× read_data_json) | ✅ 9.5s |

Every scenario: `stop_reason=end_turn` ✅ + `usage.thinking=true` ✅.

### 3 real proposals that AI generated in scenario A (later cancelled post-verification):
1. **"ხარჯების გაუნაწილებელი vs მაღაზიის Split — Live Dashboard Widget"** — allocation-gap visibility
2. **"Dead Stock — Salvage Tracker: SKU-ების სტატუსის ცხოველი მონიტორინგი"** — Phase 2.11 follow-through
3. **"Cash Runway Widget — 'რამდენი დღე ვძლებ?' real-time indicator"** — liquidity anchor

ყველას ჰქონდა: problem / benefit / mvp_scope / data_needed / time_estimate / risk_critique + journal ID + 🪞 კრიტიკოსის თვით-კრიტიკა.

### Carry-forward do-not-touch rules (Phase 3.1)
- `JOURNAL_KINDS` tuple order: `("promise", "ai_commitment", "recommendation", "reminder", "proposal")` — NEVER reorder
- `TOOL_SCHEMAS` pinned index 15 = `propose_feature` — new tools go to index 16+
- `SYSTEM_PROMPT_KA_INVESTIGATOR` must stay 0 Co-Designer markers (pin: `test_investigator_prompt_has_no_codesigner_markers`)
- `PROPOSAL_AUTO_CLEANUP_DAYS = 30` — never reduce without user consent
- 6 proposal_* metadata keys — fixed names: `proposal_problem`, `proposal_benefit`, `proposal_mvp`, `proposal_data_needed`, `proposal_time_estimate`, `proposal_risk_critique`
- PULL-ONLY policy — 6 trigger phrases in prompt are the only activation path; anti-trigger list must stay explicit
- Critic mandate 🪞 — risk_critique field MUST be filled by AI (prompt forces it); never drop from schema

---

## 📋 ორიგინალური PREVIEW (approved 2026-04-20 16:20)

---

## 1. 🎯 რას ცვლის — ერთი წინადადებით

> AI მიიღებს უნარს, **მხოლოდ თქვენი პირდაპირი თხოვნით**, სტრუქტურირებული შემოთავაზება გააკეთოს Dashboard-ის ახალი feature-ისთვის. **პროაქტიულობა — გამორიცხული.**

---

## 2. 💡 რატომ გჭირდებათ

თქვენი მაგალითი: *"მინდა ცალკე გვერდი dead stock-ისთვის"*.

**დღეს:** ეს იდეა თქვენგან უნდა წამოვიდეს — მერე **მე** (Cascade) ვდებ preview-ს.

**ხვალ (ამ ცვლილების შემდეგ):** თქვენ უბრალოდ AI-ს ჰკითხავთ *"რას შემომთავაზებდი Dashboard-ზე?"* — AI გადაავლებს თვალს თქვენს **ბოლო 7 დღის კითხვებს** + **Dashboard-ის მდგომარეობას** + **Phase 2.11/2.12 აღმოჩენებს**, და მოგცემთ **3 რანჟირებულ, სტრუქტურირებულ შემოთავაზებას** 6 ველით:

- **პრობლემა** — რას ვერ აგვარდებს ახლანდელი UI?
- **სარგებელი** — რას დააფიქსირებს user-ი? (დრო/ფული/ზუსტობა)
- **MVP ფარგლები** — მინიმალური რაც ღირებულია
- **რა მონაცემი** — უკვე არსებული? ახალი?
- **ვადა** — რამდენი დღე ჭირდება
- **რისკი** — AI-მ **თავად** გააკრიტიკოს თავისი შემოთავაზება (🪞 კრიტიკოსი ქუდი)

---

## 3. 🎭 როგორ იმუშავებს — 2 სცენარი

### 🅰 სცენარი 1 — თქვენ ითხოვთ შემოთავაზებას

თქვენ AI-ს ჰკითხავთ რომელიმე triger-ფრაზით:

| თქვენი კითხვა | AI-ს ქცევა |
|---|---|
| *"რას შემომთავაზებდი?"* | ✅ 3 რანჟირებული შემოთავაზება |
| *"რა ახალი feature გვინდა Dashboard-ზე?"* | ✅ 3 რანჟირებული შემოთავაზება |
| *"რა იდეები გაქვს?"* | ✅ 3 რანჟირებული შემოთავაზება |
| *"შემომთავაზე რამე"* | ✅ შემოთავაზება |
| *"co-designer"* (ცხადი სიტყვა) | ✅ შემოთავაზება |
| *"AI, იყავი შენ co-designer"* | ✅ შემოთავაზება |

### 🅱 სცენარი 2 — ისტორიის დათვალიერება

თქვენ ჰკითხავთ: *"რა შემოთავაზებები მაქვს ღიად?"*

AI წაიკითხავს გადაწყვეტილების ჟურნალს, **ფილტრი: `kind="proposal", status="open"`** → გაჩვენებთ ცხრილს: თარიღი + სათაური + სარგებელი + სტატუსი.

### ❌ რა **არ** ხდება (მკაცრი წესი)

- ❌ AI **არასოდეს** არ დაამატებს შემოთავაზებას ბოლოს ჩვეულებრივი კითხვის შემდეგ
- ❌ AI **არასოდეს** არ შემოგთავაზებთ "მინდა რამე განვავითარო..."
- ❌ 3+ ერთნაირი კითხვა ერთ თემაზე **არ** აამოქმედებს auto-trigger-ს
- ❌ კრიზისული მდგომარეობა (margin −80% და მსგავსი) **არ** გამოიწვევს უცხო შემოთავაზებას
- ❌ ყოველდღიური briefing / weekly summary / push — არ არსებობს

---

## 4. 🛠 ტექნიკური ცვლილებები (მოკლედ)

| კომპონენტი | ცვლილება |
|---|---|
| AI-ს tool-ების კრებული | **+1 ახალი** `propose_feature` tool (6-ველიანი სტრუქტურა) |
| გადაწყვეტილების ჟურნალი | **+1 ახალი ტიპი** `kind="proposal"` (დღეს: promise + recommendation + reminder + ai_commitment → ხდება 5) |
| AI-ის system prompt | **+1 ახალი სექცია** 🎨 Co-Designer — trigger-ფრაზების სია + anti-trigger წესები + structured format |
| Investigator prompt | **არ იცვლება** (do-not-touch წესი) |
| Dashboard UI | **არ იცვლება ამ ფაზაში** — შემოთავაზება AI ჩატში ჩანს |
| API / endpoint | **არ იცვლება** |
| ახალი dependency | **არცერთი** |

---

## 5. ✅ Default-ები — დამოწმებული

| Q | კითხვა | გადაწყვეტილება |
|---|---|---|
| Q1 | **როდის შესთავაზოს AI?** | ✅ **მხოლოდ თქვენი პირდაპირი თხოვნით** (pull-only) |
| Q2 | **სადაც შეინახოს?** | ✅ **გადაწყვეტილების ჟურნალში** (არსებული სისტემა) |
| Q3 | **როგორ "დააფიქსიროს" AI რა თემებია ხშირი?** | ✅ **ბოლო 7 დღის ChromaDB მეხსიერებიდან კითხვის დროს** (არსებული `recall_context` tool) |
| Q4 | **რამდენი შემოთავაზება ერთ ჩათში?** | ✅ **მაქსიმუმ 3 რანჟირებული** ერთ "რას შემომთავაზებდი?" კითხვაზე |

---

## 6. 🛡️ Anti-Trigger წესები — prompt-ში მკაცრად ჩაწერილი

AI-ის 🎨 Co-Designer სექციაში ჩაიწერება **კრძალული ქცევა**:

```
❌ არასდროს არ შესთავაზო feature ჩვეულებრივი კითხვის შემდეგ
❌ არასდროს არ დაამატო "შემოგთავაზებდი..." უცხოდ
❌ არასდროს არ გააკეთო auto-trigger 3+ კითხვისგან — ეს მანქანურია, არა პარტნიორული
❌ არასდროს არ აქციო კრიზის შემოთავაზების მოტივად — კრიზის შემდეგ მოდის **ფაქტი**, არა "რა გვქონდეს"
❌ მხოლოდ 6-ფრაზიანი trigger-სიტყვიდან ერთი გამოცანია ("რას შემომთავაზებდი" / "შემომთავაზე" / ...)
```

ეს ანტი-წესები **ცალკე ტესტებით** დაცულია — 10+ test რომ ამოწმოთ, რომ AI *არ* აკეთებს შემოთავაზებას.

---

## 7. 🧪 ტესტირება

| ტესტის ტიპი | რაოდენობა | მიზანი |
|---|---|---|
| 🟢 Positive path | ~12 | trigger-ფრაზა → AI აკეთებს შემოთავაზებას სწორი ფორმატით |
| 🔴 Anti-proactive | ~15 | სტრატეგიული კითხვა + კრიზის + 3x ერთნაირი კითხვა → AI **არ** აკეთებს შემოთავაზებას |
| 📊 Journal integration | ~10 | `kind="proposal"` CRUD + ფილტრი + lifecycle |
| 🔧 Investigator untouched | ~5 | investigator prompt-ი 0 Co-Designer marker-ით |
| 🎭 Structured output | ~8 | 6 ველი ყოველთვის არსებობს + კრიტიკოსი სვეტი |

**Baseline:** 1163/1163 green (დღევანდელი)
**მოსალოდნელი:** ~1213/1213 green (~+50 ახალი)

---

## 8. ⚠️ რისკები (pull-only რეჟიმის შემდეგ)

| რისკი | ალბათობა | დაცვა |
|---|---|---|
| 1. AI ზედმეტად შემოგვთავაზებს | 🟢 **ძალიან დაბალი** (pull-only + 15 anti-test) | anti-trigger სია + ტესტები |
| 2. ცუდი შემოთავაზება | 🟡 ზომიერი | 6-ველიანი სტრუქტურა + 🪞 კრიტიკოსი + "არა" ღილაკი |
| 3. ჟურნალის გადატვირთვა | 🟢 დაბალი | Default ფილტრი + 30d auto-cleanup |
| 4. Investigator-ის გატეხვა | 🟢 ძალიან დაბალი | do-not-touch + 5 ტესტი |
| 5. გამორთვა გართულდეს | 🟢 დაბალი | 1 prompt section — ადვილი წაშლა |

**ყველაზე მაღალი რისკი:** #2 — *ცუდი შემოთავაზება*. **გადამწყვეტი მექანიზმი:** `🪞 კრიტიკოსი ქუდი` — AI-ს ვალდებულია საკუთარი შემოთავაზების სუსტი მხარე თვითონ მოძებნოს. დღევანდელ გაყიდვების dog-food-ზე ეს ქცევა ცოცხლად **იმუშავა**.

---

## 9. 💰 ფასი / დრო

| რესურსი | შეფასება |
|---|---|
| სამუშაო დრო | ~1-1.5 დღე |
| ცოცხალი ტესტის Anthropic API | ~$0.50-1.00 |
| თვიური API-ს ცვლილება | **~$0** |
| ახალი dependency | **არცერთი** |

---

## 10. 🎯 MVP vs მომდევნო ნაბიჯები

### 🅰 ამ ფაზაში (Phase 3.1 — MVP)

- `propose_feature` tool
- 🎨 Co-Designer სექცია prompt-ში (trigger + anti-trigger + format)
- journal-ში `kind="proposal"` + 30d auto-cleanup
- 50 ტესტი
- ცოცხალი dog-food

### 🅱 Phase 3.2-3.10 (მომდევნო ფაზები)

- Phase 3.2 — Persistent Memory upgrade
- Phase 3.3 — Conversation Summary
- Phase 3.4 — Decision Journal Dashboard Tab (ყველა kind — შემოთავაზებების ვიზუალიზაცია)
- Phase 3.5 — Cash Runway Widget
- Phase 3.6 — Supplier Concentration Widget
- Phase 3.7 — Product Death Row Page (**თქვენი dead stock იდეა აქ ხორცს ისხამს!**)
- Phase 3.8 — Margin Compression Radar
- Phase 3.9 — Monthly Strategy Page
- Phase 3.10 — Gap Analysis

---

## 11. ✅ ნაბიჯების გეგმა (კოდი)

1. `dashboard_pipeline/ai/journal.py` — `kind="proposal"` + 6-ველიანი payload + 30d cleanup
2. `dashboard_pipeline/ai/tools.py` — ახალი `propose_feature` tool (TOOL_SCHEMAS=15 → 16)
3. `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — 🎨 Co-Designer სექცია (trigger + anti-trigger + format + 🪞 კრიტიკოსი)
4. **Investigator prompt** — **0 cascade change** (do-not-touch)
5. ~50 pytest
6. **Backend restart #11** + ცოცხალი dog-food (2-3 კითხვა)
7. `CONTEXT_HANDOFF.md` + `PLAN.md` განახლება
8. Scratch cleanup
