# PHASE 4B — AI Personality & Behavior Tuning (PREVIEW)

> **სტატუსი**: 📋 **PLANNED** (2026-04-21 04:57 UTC+04:00, updated)
> **წინადადებები**: **31 წესი** (29 prompt + 2 tool design), **5 sprint** (Phase 4B × 4 + Phase 4C × 1), ~5-6 დღე, ~$0.80
> **წყარო**: Anthropic docs (docs.anthropic.com + code.claude.com) + Anthropic "Building Effective Agents" (anthropic.com/engineering) + Claude Sonnet 4.5 / Opus 4.6 leaked prompts + **GPT-5 leaked prompt** (asgeirtj/system_prompts_leaks/OpenAI)

---

## 1. რას ვაკეთებთ — ერთი წინადადებით

AI-ის ქცევას ვასწორებთ **Anthropic-ის ოფიციალური რეკომენდაციებით**, რომელიც თავად Anthropic-მა Claude.ai-სთვის გამოიყენა, ჩვენ კი გამოგვეპარა.

---

## 2. რატომ — სამი ცხადი pain point

### 🎭 Pain 1 — AI "რობოტი" ტონი RAG-ის გამოყენებისას

ახლა AI ხშირად ამბობს:
- *"ჩემს მეხსიერებაში ვხედავ..."*
- *"ბოლო საუბრებიდან ვიპოვე..."*
- *"`recall_context`-ში აღმოაჩინა..."*

Anthropic-ი ცხადად ამბობს — ეს ფრაზები **აკრძალულია**. მეხსიერების ფაქტი "ბუნებრივად" უნდა იდოს პასუხში, **არა მიუთითო რომ იპოვე**.

### 🚨 Pain 2 — STOP-CHECK ზედმეტად ვფშლის

ახლა, თუ კითხვაში წელი ცხადად არ ჩანს, AI უარს ამბობს პასუხზე და 3 კითხვას სვამს (წელი + date-column + scope).

Anthropic-ი ცხადად ამბობს:
> "Claude does its best to address the person's query, **even if ambiguous, before** asking for clarification."

+ "Max 1 question per response."

ე.ი. **ჯერ ცადე პასუხი**, შემდეგ ერთ ყველაზე მთავარ კითხვაზე ჰკითხე.

### 📏 Pain 3 — Maximum formatting ყოველ პასუხზე

ახლა AI-ი *"რამდენი მომწოდებელია?"* კითხვაზეც კი ცხრილი + ქუდი + Confidence-ით წერს. Anthropic-ი:
> "Claude avoids over-formatting. Uses **minimum formatting** appropriate. For simple questions — prose, not lists."

---

## 3. რა ვიპოვე — 31 წესი პრიორიტეტით

### 🥇 TIER 1 — ფუნდამენტური (9 წესი) — **Phase 4B.1**

| # | წესი | წყარო | რას ცვლის |
|---|---|---|---|
| 1 | "ჯერ ცადე, მერე გადააკითხე" | Sonnet 4.5 | STOP-CHECK-ის ფილოსოფიას |
| 2 | მაქსიმუმ 1 კითხვა ერთ პასუხში | Claude 4 | STOP-CHECK cascade |
| 3 | User-ის premise-ი შეიძლება მცდარი | Sonnet 4.5 | ბრმა ეთანხმება |
| 4 | User-იც შეიძლება შეცდეს | Opus 4.6 | auto-apology |
| 16 | `<use_parallel_tool_calls>` XML | docs.anthropic | ~100% parallel success |
| 17 | `<investigate_before_answering>` XML | docs.anthropic | hallucination-ზე brake |
| 18 | "Commit to approach" | docs.anthropic | 180° pivots |
| **27** | **"Partial completion > clarification"** | **🆕 GPT-5** | **clarify-ის აკრძალვა non-critical-ზე** |
| **28** | **"No future promises" ban** | **🆕 GPT-5** | **"ვცდი და მოვახსენებ"-ის აკრძალვა** |

### 🥈 TIER 2 — Personality & Agentic (7 წესი) — **Phase 4B.2 (nahevari)**

| # | წესი | წყარო | რას ცვლის |
|---|---|---|---|
| 5 | Seamless memory (forbidden phrases) | Opus 4.6 | RAG ბუნებრივობას |
| 6 | Overfamiliarity warning | Opus 4.6 | RAG-ის "მეგობრული" ტონი |
| 7 | Push back + Kindness balance | Sonnet 4.5 | მკაცრი ტონს ამცირებს |
| 19 | "Avoid over-engineering" | docs.anthropic | ზედმეტი "გაუმჯობესებები" |
| 20 | "State scope explicitly" | docs.anthropic | literal following |
| 21 | "Persistence directive" | docs.anthropic | early-stop bug |

### 🥉 TIER 3 — ფორმატი + Anti-sycophancy (9 წესი) — **Phase 4B.2 (nahevari)**

| # | წესი | წყარო | რას ცვლის |
|---|---|---|---|
| 8 | Minimum formatting | Sonnet 4.5 | ცხრილი მხოლოდ რთულზე |
| 9 | Anti-sycophancy 8-სიტყვიანი ქართული | Claude 4 | flattery openers |
| 10 | Asterisk actions ბანი | Sonnet 4.5 | `*"text"*` style |
| 11 | Emoji ზომიერება | Sonnet 4.5 | decoration emoji |
| 12 | Tool scaling ladder (0 / 2-4 / 5-9 / 10+) | Opus 4.6 | calibrated depth |
| 13 | Financial override — documented | Sonnet 4.5 default | "not advisor" disclaimer skip |
| 14 | ფაილი შეიძლება არ იყოს | Sonnet 4.5 | empty attachment |
| 15 | Metaphor/example usage | Sonnet 4.5 | რთული ცნების ახსნა |
| **26** | **Oververbosity 1-10 scale** (default 3) | **🆕 GPT-5** | **response length quantitative calibration** |

### 🏅 TIER 4 — Anti-patterns (4 წესი) — **Phase 4B.3**

| # | წესი | წყარო | რას ცვლის |
|---|---|---|---|
| 22 | ⚠ "Ruthlessly prune" | code.claude.com | 1,291-ხაზიანი prompt bloat |
| 23 | "Kitchen sink session" warning | code.claude.com | PLAN.md discipline |
| 24 | "General-purpose solution" | docs.anthropic | test hard-coding |
| 25 | "Correcting 2× → restart" rule | code.claude.com | workflow anti-pattern |

### ⚙ TIER 5 — Tool Design (2 წესი + 18 tool review) — **Phase 4C (ცალკე sprint)**

| # | წესი | წყარო | რას ცვლის |
|---|---|---|---|
| **29** | **"Poka-yoke your tools"** — 18 tool schema review | **🆕 Anthropic Agent Blog** | **argument ambiguity mistakes** |
| **30** | **"Tools should think out loud"** — natural language output | **🆕 Anthropic Agent Blog** | **silent JSON → narrative text** |

---

## 4. 🚨 CRITICAL DISCOVERY — ჩვენი Prompt გადატვირთულია

**Anthropic-ის ცხადი ფრაზა** (Claude Code best practices):
> "If your CLAUDE.md is too long, Claude **ignores half of it** because important rules get lost in the noise. **Fix: Ruthlessly prune.** If Claude already does something correctly without the instruction, delete it or convert it to a hook."

**ფაქტი:**

| მეტრიკა | ამჟამინდელი | Anthropic-ის რეკომენდაცია |
|---|---|---|
| `SYSTEM_PROMPT_KA` ხაზები | **1,291** | ≤ 900 (ჩვენი domain-ისთვის) |
| `AGENTS.md` ხაზები | ~60 | ≤ 60 ✅ |
| Duplicate patterns | **რამდენიმე** | 0 |

**ეფექტი:** თუ ახლავე 25 ახალ წესს დავამატებთ (~200 ხაზი), სულ იქნება **~1,500 ხაზი**. AI **ნახევარს ჩაიგდებს** — ე.ი. ახალი წესები "ცარიელზე" იქნება.

**გადაწყვეტა:** **ჯერ prune, მერე add**.

---

## 5. 5 Sprint Breakdown (Phase 4B + Phase 4C)

### Sprint 4B.0 — 🔥 Ruthlessly Prune (2-3 საათი)

**მიზანი:** 1,291 ხაზი → ~900 ხაზი (~30% reduction).

**რას ვაკეთებთ:**
- Duplicate section-ების გაერთიანება (მაგ. "ენა და ფორმატი" განმეორდება 3-ჯერ)
- Verbose ახსნების მოკლე ფორმად ჩამოყვანა
- Redundant anti-pattern-ების მოცილება (თუ AI უკვე სწორად იქცევა, წესი ზედმეტია)
- 5 ქუდი section — 150 → 80 ხაზი (ცხრილი საკმარისია)
- 📌 ვარაუდი vs ფაქტი — 70 → 40 ხაზი
- STOP-CHECK — 130 → 70 ხაზი (რადგან Sprint 4B.1 ცვლის ფილოსოფიას)

**Verification:**
- `grep "ფრაზა"` — ყოველი ძირითადი ფრაზა რამდენჯერ ფიგურირებს
- Regression tests — 1443/1443 უნდა დარჩეს green (pytest)
- Live dog-food (1 scripted `/api/chat/stream`) — ყოფილი behavior უნდა შენარჩუნდეს

**Deliverable:** `prompts.py` ~900 ხაზი, pytest green.

---

### Sprint 4B.1 — TIER 1 ფუნდამენტური (1 დღე)

**მიზანი:** AI ქცევის ძირითადი ცვლილება — 7 წესის დამატება.

**რას ვამატებთ:**
1. **"Attempt first, clarify second"** → STOP-CHECK-ი **მხოლოდ** critical decisions-ზე (ფული, ვალი, გადაწყვეტილება)
2. **Max 1 question** → STOP-CHECK 3 gate → ერთი priority cascade
3. **False premise detection** → ახალი სექცია "🕵 premise-ის შემოწმება"
4. **User-იც შეიძლება შეცდეს** → "შეცდომა დაუშვი"-ზე reaction პატერნი
5. **`<use_parallel_tool_calls>` XML** → Anthropic-ის ზუსტი wording
6. **`<investigate_before_answering>` XML** → Georgian financial-domain adapted version
7. **"Commit to approach"** → anti-overthinking section

**Tests:** ~40-60 new regression tests `test_ai_prompts_phase4b1.py`.

**Verification:** Live dog-food 3 scenarios (ambiguous question → AI attempts first; premise correction; parallel tool call burst).

---

### Sprint 4B.2 — TIER 2 + TIER 3 (1 დღე)

**მიზანი:** Personality + formatting სისუფთავე — 15 წესი.

**რას ვამატებთ:**
- **Seamless memory** — `<forbidden_memory_phrases>` ბლოკი ქართული adapted
- **Overfamiliarity** warning — ChromaDB 18K chunks context-ისთვის
- **Push back + kindness** — მკაცრ ტონს empathy-ს ვამატებთ
- **Avoid over-engineering** — Cascade-ისთვის (არა chat AI), მაგრამ principle-ი ზიარდება
- **State scope explicitly** — "ყოველ ციფრს, ყოველ ცხრილში..."
- **Persistence directive** — long-horizon tasks
- **Minimum formatting matrix** — 4 question type → 4 response format
- **Anti-sycophancy** — ქართული 8-სიტყვიანი სია
- **Asterisk ban** — `*"..."*` style აიკრძალოს
- **Emoji calibration** — functional only (🟢/🟡/🟠/⚪/⚠), decoration minimal
- **Tool scaling ladder** — 0/2-4/5-9/10+ triggers
- **Financial override** — ცხადი justification კომენტარი prompt-ში
- **File-might-not-exist** — attachment verification
- **Metaphor usage** — ცხადი encouragement მარტივი ცნებებისთვის

**Tests:** ~80-100 new regression tests.

---

### Sprint 4B.3 — TIER 4 Anti-patterns (0.5 დღე)

**მიზანი:** Workflow discipline (PLAN.md + AGENTS.md + /restart-session).

**რას ვამატებთ:**
- **"Ruthlessly prune"** — AGENTS.md-ში ახალი სექცია "Prompt Hygiene"
- **"Kitchen sink session"** — AGENTS.md-ში "Session Boundaries" წესი
- **"General-purpose solution"** — prompts.py-ში "🎯 საერთო გადაწყვეტა" section
- **"2× correction → restart"** — `.windsurf/workflows/restart-session.md` ახალი workflow

**Tests:** workflow validation only, unit tests ~10 new.

---

### 🆕 Sprint 4C — Tool Design Review (2-3 დღე) — **ცალკე Phase**

**მიზანი:** 18 ინსტრუმენტის Anthropic "Poka-yoke" + "think out loud" review.

**რას ვამატებთ:**

**4C.1 — Schema audit (1 დღე):**
- ყოველი tool-ის schema review "junior developer docstring" ოპტიკით:
  - რომელი parameter-ი ამოცანოვანია? (მაგ. `store` vs `store_name` vs `store_id`)
  - რომელი parameter-ი ორაზროვანია? (მაგ. `date_field` — `date` / `transport_start_date` / `delivery_date`-იდან რომელი?)
  - რომელი default გაუგებარია? (მაგ. `lookback_months=6` vs user-ი ფიქრობს "მთელი წელი")
- **Poka-yoke transformations**: fragile args → self-describing args (მაგ. `store="ozurgeti"` → `store_alias="ozurgeti_urban"`)
- **Tests:** ~30 new schema validation tests per tool

**4C.2 — Tool output redesign (1 დღე):**
- Current: ყველა tool JSON-ს აბრუნებს (`{"total": 270, "breakdown": {...}}`)
- Target: hybrid — structured JSON **+** human-readable `summary_ka` ველი
  - მაგ: `{"total": 270, "summary_ka": "270 მომწოდებელი. Top-3 კრიტიკული: ვასაძე 313K / კოკაკოლა 87K / ჯიდიაი 62K. ⚠ 2 inactive-ი 6 თვეა"}`
- AI იყენებს `summary_ka`-ს, მაგრამ raw data-ც ხელმისაწვდომია
- **Tests:** ~20 new output format tests

**4C.3 — Live dog-food verification (0.5 დღე):**
- 3-5 scripted `/api/chat/stream` scenarios
- Metric: AI-ის tool call error rate უკვე (before/after)
- Expected: fewer wrong-argument retries, richer Georgian reply quality

**Deliverable:** `tools.py` refactored, ~50 new tests, backend restart verified.

**რატომ ცალკე Phase:** Prompt tuning (4B) **prompts.py only**-ია. Tool redesign (4C) **tools.py + ~20 tool implementations**-ია — სრულიად განსხვავებული scope. Phase 4B წინ უნდა წავიდეს, რადგან new prompt rules + old tools → new baseline-ია. მერე Phase 4C tool-ებს upgrade-ს შეაფასებს ცხადი აპრიორი prompt-ით.

---

## 6. Before / After მაგალითები

### მაგალითი 1 — Seamless Memory

**ახლა (Before):**
> User: "Alpha-ს რამდენი ვალი აქვს?"
>
> AI: *"მოვიძიე ChromaDB მეხსიერებაში — ვხედავ რომ 4 კვირის წინ ჩავწერე 23,000 ₾ ვალი Alpha-ზე. ამჟამინდელი `data.json`-ში supplier_aging-იდან ვპოვე 31,450 ₾. ჩემი მეხსიერებიდან ცხადად ჩანს, რომ..."*

**Sprint 4B.2-ის შემდეგ (After):**
> User: "Alpha-ს რამდენი ვალი აქვს?"
>
> AI: *"Alpha-ს ვალი **31,450 ₾** (წყარო: data.json → supplier_aging). 4 კვირის წინ 23,000 ₾ იყო — ნელი ზრდა."*

**რა შეიცვალა:** "ვხედავ", "მოვიძიე", "ჩემი მეხსიერება" — ყველა წაშლილი. ფაქტი ბუნებრივად ჩადგა.

---

### მაგალითი 2 — STOP-CHECK Rebalancing

**ახლა (Before):**
> User: "რა margin იყო დეკემბერში?"
>
> AI: *"STOP-CHECK: (ა) რომელი წელი 2024/2025/2026? (ბ) რომელი ობიექტი ოზურგეთი/დვაბზუ? (გ) რა ტიპის margin gross/net?"*

**Sprint 4B.1-ის შემდეგ (After):**
> User: "რა margin იყო დეკემბერში?"
>
> AI: *"**2025 დეკემბერში total margin = 18.7%** (gross, წყარო: data.json → monthly_pnl).
>
> თუ **სხვა წლის** დეკემბერი გაინტერესებს ან **ცალკე ობიექტი** (ოზურგეთი/დვაბზუ) — მითხარი."*

**რა შეიცვალა:** AI-მ ცადა მოსალოდნელი პასუხი (2025 — ბოლო სრული წელი), მერე ერთი clarify-ით გაფართოვება შესთავაზა.

---

### მაგალითი 3 — Anti-sycophancy

**ახლა (Before):**
> User: "როგორ შევამცირო AP?"
>
> AI: *"**მშვენიერი კითხვაა!** AP-ის შემცირება **ფუნდამენტური** საკითხია. **გულწრფელად რომ გითხრა**, ეს **საინტერესო** პრობლემაა..."*

**Sprint 4B.2-ის შემდეგ (After):**
> User: "როგორ შევამცირო AP?"
>
> AI: *"AP 854,230 ₾-ია (წყარო: pnl_summary). 3 მიდგომა შესაძლოა:
> 1. Top-5 leverage supplier-ების მოლაპარაკება..."*

**რა შეიცვალა:** 4 flattery სიტყვა წაშლილი, AI პირდაპირ პასუხს იწყებს.

---

### მაგალითი 4 — Minimum Formatting

**ახლა (Before), მარტივი კითხვაზე:**
> User: "რამდენი მომწოდებელია?"
>
> AI:
> ```
> 💼 **ფინანსური ქუდი:**
>
> | მეტრიკა | მნიშვნელობა |
> |---|---|
> | სულ მომწოდებელი | 270 |
> | წყარო | data.json → suppliers |
>
> 🟢 **საიმედო** — tool-ით გადამოწმებული.
> ```

**Sprint 4B.2-ის შემდეგ (After):**
> User: "რამდენი მომწოდებელია?"
>
> AI: *"**270** (წყარო: data.json → suppliers)."*

**რა შეიცვალა:** ცხრილი + ქუდი + Confidence წაშლილი — საჭირო არ იყო. ერთი წინადადება.

### მაგალითი 5 — GPT-5 Oververbosity 1-10 Scale (Rule #26)

**ახლა (Before):** ყველა კითხვაზე იგივე სტრუქტურა (ცხრილი + ქუდი + 🪞 კრიტიკოსი).

**Sprint 4B.2-ის შემდეგ (After):**

| კითხვის ტიპი | Oververbosity | ფორმატი | მაგალითი |
|---|---|---|---|
| **ფაქტობრივი** | **2** | ერთი წინადადება | *"**270 მომწოდებელი** (წყარო: data.json → suppliers)."* |
| **რთული ფაქტი** | **3** (default) | ფაქტი + context | *"Alpha-ს ვალი **31,450 ₾**. 4 კვირის წინ 23,000 ₾ იყო — ნელი ზრდა."* |
| **სტრატეგია** | **7** | სრული structure | ქუდი + ცხრილი + multi-hypothesis + კრიტიკოსი |
| **კრიზისი** | **2** | Top-3 action პირველ წამს | *"🚨 ჯერ: (1) Alpha-ს დარეკე, (2) 60%-ის offer, (3) BOG ანგარიში დახურე. დეტალები მერე."* |

**რა შეიცვალა:** ცხადი numerical dial — AI "იცის" რამდენად მოკლე/გრძელი უნდა იყოს პასუხი.

### მაგალითი 6 — No Future Promises (Rule #28)

**ახლა (Before):**
> User: "ჯიდიაის ვალი რამდენია?"
>
> AI: *"მე ვცდი `supplier_aging` data-ში ძიებას, **რამდენიმე წამში ვიპოვებ** და მოგახსენებ..."*

**Sprint 4B.1-ის შემდეგ (After):**
> User: "ჯიდიაის ვალი რამდენია?"
>
> [AI-მ tool call-ი გააკეთა — user არ ხედავს]
>
> AI: *"**313,922 ₾** (წყარო: supplier_aging)."*

**რა შეიცვალა:** *"ვცდი... რამდენიმე წამში ვიპოვებ..."* წაშლილი. Tool call synchronous-ია — illusion არ საჭიროა.

---

## 7. რისკი + Mitigation

| რისკი | ალბათობა | Mitigation |
|---|---|---|
| Prune-ი ცხადი behavior-ს გააფუჭებს | 🟡 საშუალო | regression tests 1443/1443 + live dog-food 3 scenarios |
| 25 ახალი წესი პირიქით მოიქცევა | 🟠 მცირე | Sprint-ზე თანმიმდევრობით, სპრინტს შორის live verify |
| Financial override-ი Anthropic-ის default-ს გატეხავს | ⚪ დაბალი | override-ი უკვე არსებობს Phase 1 Part A, ახალ ვერსიაში ცხადად დავასაბუთებთ |
| `<investigate_before_answering>` XML + existing STOP-CHECK კონფლიქტი | 🟡 საშუალო | STOP-CHECK-ი ცხადად მიიღებს "only financial-critical" scope-ს |
| Backend restart-ი ყოველ Sprint-ს | 🟢 დაბალი | Windows Service-ი უკვე installed, hot-reload საკმარისია |

---

## 8. დრო + Cost Estimate

| Sprint | ძალისხმევა | AI cost (dev) | Impact |
|---|---|---|---|
| 4B.0 Prune | 2-3 სთ | $0 (offline) | 🔥🔥🔥 foundation |
| 4B.1 Tier 1 (9 წესი) | **1.5 დღე** | ~$0.25 (4 live dog-foods) | 🔥🔥🔥 highest |
| 4B.2 Tier 2+3 (16 წესი) | 1 დღე | ~$0.30 (5 live dog-foods) | 🔥🔥 medium |
| 4B.3 Tier 4 (4 წესი) | 0.5 დღე | $0 (workflow only) | 🔥 low |
| **Phase 4B ჯამი** | **~3-3.5 დღე** | **~$0.55** | **Prompt tuning** |
| 4C.1 Schema audit | 1 დღე | ~$0.10 | 🔥🔥 high |
| 4C.2 Output redesign | 1 დღე | ~$0.15 | 🔥🔥 high |
| 4C.3 Dog-food | 0.5 დღე | ~$0.15 (5 scenarios) | 🔥 verify |
| **Phase 4C ჯამი** | **~2.5 დღე** | **~$0.40** | **Tool design** |
| **სულ (4B + 4C)** | **~5.5-6 დღე** | **~$0.95** | **ფუნდამენტური + tool quality** |

---

## 9. Verification Plan (per sprint)

ყოველ Sprint-ის დასრულებისას:

1. **Static checks**:
   - `pytest` → ყველა regression green
   - `grep "აკრძალული-ფრაზა"` → 0 hits
   - Line count verification (4B.0 = ≤ 900, 4B.1-3 = ≤ 1,100)

2. **Live dog-food** (scripted `/api/chat/stream`):
   - Ambiguous date question → AI attempts first
   - Memory recall question → no "ვხედავ/ვიპოვე" leak
   - Simple factual → minimum formatting
   - Strategic question → full structure preserved

3. **UI smoke** (Playwright):
   - Chat FAB → 3 sample questions → visible improvement in response

4. **Commit** with verified metrics in message.

---

## 10. Out of Scope (Parking Lot)

- **Tool call analytics** (რომელი tool ხშირად გამოიყენება?) — Phase 5-ისთვის
- **A/B testing framework** (old prompt vs new prompt) — future
- **User-configurable prompt style** (formal vs casual) — Phase 5+
- **Dashboard-internal prompt editor** — never (prompts.py-ი code-ში უნდა დარჩეს)

---

## 11. Success Criteria

### Phase 4B complete **თუ**:
- `SYSTEM_PROMPT_KA` ≤ 1,100 ხაზი (Anthropic recommendation)
- 29 prompt წესიდან **minimum 24** ცხადი evidence prompt-ში (grep verification)
- pytest **1443+ green** (არცერთი weakened)
- Live dog-food 5/5 scenarios PASS
- Before/After visual diff 3+ real user questions-ზე

### Phase 4C complete **თუ**:
- 18 tool-დან **ყველა** schema აუდიტ-passed (Poka-yoke checklist)
- Tool outputs გადაკეთილი — JSON-only → JSON+`summary_ka`-ი **ყველა** tool-ზე
- Tool error rate ↓ 50%+ (before/after scripted scenarios)
- ~50 new schema + output tests green
- pytest **1490+ green**

---

## 12. Open Questions (user-ს ვუტოვებ)

1. **Emoji policy**: Anthropic ამბობს "judicious use". ჩვენი 🟢/🟡/🟠/⚪ Confidence labels დავტოვოთ? (ვფიქრობ **კი** — functional, არა decoration).

2. **Financial override**: ცხადი disclaimer პასუხის ბოლოს ("**Note:** I am AI, not a licensed financial advisor") დავამატოთ? (ვფიქრობ **არა** — user-ი მფლობელია, იცის).

3. **XML vs Markdown**: ახალი წესების ჩანაწერი XML ბლოკებით (`<commit_to_approach>`) თუ Markdown headers-ით? (Anthropic იყენებს XML-ს ცხადი ბლოკებისთვის — ვცადოთ hybrid).

4. **Sprint order**: Sprint 4B.0 (prune) **ყოველთვის ჯერ**, თუ პარალელურად 4B.1-იც? (ვფიქრობ **ჯერ prune** — სხვაგვარად ახალი წესები "ცარიელზე").

5. **🆕 GPT-5 Oververbosity default**: ჩვენი default-ი **3** (OpenAI-ის default), თუ **4** (ცოტა უფრო verbose financial context-ისთვის)? (ვფიქრობ **3 default + strategic 7**).

6. **🆕 STOP-CHECK vs Partial completion** (Rule #27): Rule #1 ("attempt first") **ნაკლებად მკაცრი**, Rule #27 ("NEVER clarify") **ცხადი ბანი**. ჩვენი balance: financial-critical decisions (ფული/ვალი/გადაწყვეტილება) → clarify ok; ყველაფერი სხვა → **NEVER clarify + partial completion**. კი?

7. **🆕 Phase 4C vs Phase 4B priority**: ჯერ Phase 4B (prompt tuning) ბოლოსანამდე, მერე Phase 4C (tools)? ან პარალელურად? (ვფიქრობ **თანმიმდევრულად** — 4B baseline-ი 4C-ს აფასებს).

---

> **მომდევნო ნაბიჯი (ხვალინდელი session)**:
> 1. User-მა წაიკითხოს ეს Preview 12 სექცია
> 2. 7 Open Question-ზე გადაწყვიტოს (ან დეფაულტი აიღოს)
> 3. ვიწყებთ **Sprint 4B.0 Prune** (2-3 საათი) — offline, კოდი არ ცვლის, მხოლოდ `prompts.py`-ი
> 4. pytest regression (1443/1443) ვერიფიცირდება
> 5. მერე Sprint 4B.1 (Tier 1 ფუნდამენტური, 9 წესი) — ცხადი live dog-food-ით
