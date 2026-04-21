# AI ADVISOR ROADMAP (Legacy)

> ⚠️ **STATUS (2026-04-18):** Phase 1-2 completed & preserved below as evidence.
> **Phase 3+ DEPRECATED** → superseded by `AI_GENIUS_PARTNER_PLAN.md` (v2.0).
>
> User-ის explicit preferences 2026-04-18 session-ში:
> - ❌ Daily Briefing / Telegram push — rejected
> - ❌ Provider migration (Kimi/Gemini) — rejected
> - ❌ Voice input (Whisper) — rejected
> - ✅ ChromaDB + Extended Thinking + Web Search — upgraded to Phase 0 core
> - ✅ Co-Designer mode + Cash Runway widget + Monthly Strategy page — added
>
> **Read for**: Phase 1-2 historical evidence only.
> **Active plan**: `AI_GENIUS_PARTNER_PLAN.md`

---

# AI ADVISOR ROADMAP

> **ვერსია:** 1.0 | **თარიღი:** 2026-04-17 | **სტატუსი:** Superseded 2026-04-18
> **პროექტი:** იოლი მარკეტი ფრენჩაიზი — Financial Dashboard AI Integration
> **ავტორი:** Cascade (Windsurf AI Architect)

---

## 📋 მიმოხილვა (Executive Summary)

### მიზანი

Financial Dashboard-ში ჩავდოთ **სრულფასოვანი AI Business Advisor** რომელიც:
- ⚡ **აჩქარებს ყოველდღიურ ანალიზს** (საათები → წუთები)
- 🔍 **აფიქსირებს data quality issues** (Excel vs data.json შეუსაბამობები)
- 📊 **პროაქტიულად აფრთხილებს** ანომალიებზე (cash flow, POS, მომწოდებლები)
- 💡 **აძლევს სტრატეგიულ რჩევებს** (სცენარები, optimization, ზრდა)
- 📱 **მობილური წვდომით** (PWA + Telegram briefing)

### კონტექსტი

**ბიზნესი:** "იოლი მარკეტი" ფრენჩაიზი, 2 მაღაზია:
- ოზურგეთი (ქალაქი, 3 POS terminal)
- დვაბზუ (სოფელი, 2 POS terminal)

**მოცულობა:** 2023-2026 data, 110+ MB შემოტანილი პროდუქცია, 270+ მომწოდებელი, ~25,000 retail transaction/თვე

### სამუშაოს მოცულობა

- **ხანგრძლივობა:** 9 კვირა (5 phase)
- **თვიური operating cost:** $40-70 (Claude Sonnet 4.6 API)
- **Development:** 0$ (Cascade იმუშავებს Windsurf-ით)
- **One-time setup:** Anthropic API key + Telegram Bot (უფასო)

---

## 🎯 1. პროექტის ამჟამინდელი მდგომარეობა

### 1.1 AI-Readiness Score: **9/10** ⭐

| მიმართულება | ქულა | შეფასება |
|---|---|---|
| Infrastructure | 9/10 | FastAPI + APScheduler + Auth + PWA უკვე არის |
| Data Quality | 8/10 | Verified, 2 წლის history, 1 process pending (cashflow) |
| Code Quality | 7/10 | Modular (20 pipeline მოდული), მაგრამ 2 monolithic file |
| Documentation | 8/10 | კარგი (PLAN, HANDOFF, AGENTS), HANDOFF archival საჭიროა |
| Process Discipline | 9/10 | Outstanding systematic verification |

### 1.2 Tech Stack

**Backend:** Python 3 + FastAPI + pandas + openpyxl + APScheduler + slowapi
**Frontend:** React 19 + Vite 8 + recharts + react-datepicker + PWA
**Testing:** 125 unit + 63 E2E (Playwright)
**Data:** Excel → `generate_dashboard_data.py` → `data.json` → `/api/data` → React

### 1.3 Packet H Status

- ✅ **12 process accepted:** `suppliers`, `waybills`, `retail_sales`, `imported_products`, `working_capital`, `ratios`, `forecast`, `budget`, `valuation`, `executive`, `insights`, `pnl`, `analytics`
- ⏳ **1 process pending:** `cashflow` (last remaining)

### 1.4 ძლიერი მხარეები AI-სთვის

1. ✅ **Multi-location attribution** — `object_mapping.json` უკვე structured (ოზურგეთი/დვაბზუ/გაუნაწილებელი)
2. ✅ **Sector benchmarks** — `sector_benchmarks.json` უკვე populated (retail Georgia)
3. ✅ **Supplier registry** — 11KB matching registry
4. ✅ **TBC expense categorization** — 24KB კატეგორიზებული
5. ✅ **Multi-source reconciliation** — BOG + TBC + RS + Manual
6. ✅ **APScheduler** — daily briefing-ისთვის მზად
7. ✅ **PWA** — mobile-first ready
8. ✅ **API Auth** — X-API-Key layer უკვე ფუნქციონალური

### 1.5 Technical Debt (AI-ს წინ cleanup)

1. ⚠️ `cashflow` Process pending (Packet H)
2. ⚠️ `deprecated-root-copy/` clutter
3. ⚠️ `HANDOFF.md` — 862 ხაზი, archival საჭიროა
4. ⚠️ `requirements.txt` — loose version pinning (`pandas>=2.0`)
5. ⚠️ Monolithic files — `api_contracts.py` (85KB), `analytics_builders.py` (83KB)
6. ⚠️ No root `.env.example` (მხოლოდ rs-dashboard-ში)

---

## 🎨 2. ვიზია და Scope

### 2.1 User Journey Example

**სცენარი 1: დილის 9:00 — Telegram Briefing**

> 🤖 *დილა მშვიდობისა! 2026-04-17 briefing:*
> 
> 📊 **გუშინდელი შედეგი (2026-04-16):**
> - ოზურგეთი: 14,200 ₾ (+5% vs 7-day avg)
> - დვაბზუ: 3,100 ₾ (−18% vs 7-day avg) ⚠️
> 
> 💰 **Cash Flow:**
> - Cash on hand: 180,400 ₾
> - მომდევნო 7 დღეში გადასახდელი: 95,300 ₾
> - Expected income: 112,000 ₾ (projection)
> - **Gap:** +16,700 ₾ ✅
> 
> ⚠️ **ყურადღების ღირსი:**
> - დვაბზუს POS30BWH-ის income გუშინ 0 ₾ — შეამოწმე ტერმინალი
> - შპს "Alpha"-ის გადახდის ვადა 3 დღეში (23,400 ₾)
> 
> 🎯 **დღევანდელი priorities:**
> 1. POS30BWH ტექნიკური შემოწმება
> 2. Alpha-ს გადახდის ავანსი/ფოსტი
> 3. შემოტანა მოვა ხვალ → cash-ი უნდა მოიმზადო

**სცენარი 2: კითხვაზე პასუხი (Chat)**

> 👤 *"2025-აგვისტოში რამდენი ლარის ზედნადები აითვირთა ოზურგეთისთვის?"*
> 
> 🤖 **👁️ წყარო:** `data.json → waybills` + `object_mapping`
> 
> 📊 **შედეგი:** 847,300 ₾ (56 ზედნადები)
> 
> **მთავარი მომწოდებლები:**
> 1. შპს "Alpha" — 234,500 ₾ (12 ზედნადები)
> 2. ი/მ "Beta" — 178,200 ₾ (8 ზედნადები)
> 3. შპს "Gamma" — 89,100 ₾ (15 ზედნადები)
> 
> 💡 **კომენტარი:** 2024-აგვისტოსთან შედარებით **+12%** ზრდა. შენი inventory turnover ასევე გაუმჯობესდა (28 → 22 დღე).

**სცენარი 3: Bug Detection**

> 👤 *"ბოლო კვირის ზედნადებები Excel-ში 14 ცალია, Dashboard-ში 12. რატომ?"*
> 
> 🤖 **⚠️ შეუსაბამობა დადასტურდა**
> 
> 📊 **შედარება:**
> - Excel: `Financial_Analysis/რს ზედნადები/` → 14 ფაილი, ჯამი 920,300 ₾
> - Dashboard: `data.json → waybills` → 12 ჩანაწერი, ჯამი 850,400 ₾
> 
> 🔍 **მიზეზი:**
> 2 ზედნადების TIN-ები `404123456` და `404789012` 9-ნიშნაა.
> `dashboard_pipeline/supplier_matching.py:142` regex `^\d{11}$` მხოლოდ 11-ნიშნა TIN-ს ცნობს.
> 
> 📋 **Cascade-ისთვის (copy-paste):**
> ```
> ფაილი: dashboard_pipeline/supplier_matching.py
> ხაზი: 142
> პრობლემა: regex გამოტოვებს 9-ნიშნა TIN-ებს
> გასწორება: r'^\d{11}$' → r'^\d{9}(\d{2})?$'
> ტესტი: tests/test_supplier_matching.py — ახალი case 9-ნიშნა TIN
> ```

**სცენარი 4: სტრატეგიული კითხვა**

> 👤 *"ვფიქრობ მე-3 მაღაზიის გახსნას. როგორ ფიქრობ?"*
> 
> 🤖 **🎯 სცენარის ანალიზი**
> 
> **📊 ამჟამინდელი მდგომარეობა:**
> - ოზურგეთი: ყოველთვიური 165K ₾ (net +18K)
> - დვაბზუ: ყოველთვიური 42K ₾ (net −2K) — უკვე რისკია
> - Combined net margin: 7.2% (industry median 5% ✅)
> 
> **⚠️ Red flags:**
> 1. **დვაბზუ ჯერ break-even-ს არ აღწევს** — ახალ მაღაზიამდე ჯერ ეს გადაჭრას
> 2. **Cash reserve: 180K ₾** — ახალი მაღაზიის launch 250-300K სჭირდება
> 3. **Franchise fee** — "იოლი მარკეტი" royalty terms? გადახედე ხელშეკრულებას
> 
> **🎯 ჩემი რეკომენდაცია:**
> **ჯერ არა.** 6 თვე ფოკუსი:
> 1. დვაბზუს stabilization (+15K/თვე მიზანი)
> 2. Cash reserve → 280K ₾
> 3. ოზურგეთში margin optimization (7.2% → 8.5%)
> 
> ამის შემდეგ ახალი განხილვა.

### 2.2 Scope Tiers

#### 🟢 Tier 1 — Core (Phase 1-2, 3 კვირა)
- Dashboard-ში Chat UI
- კითხვა-პასუხი data-ზე (source attribution)
- Bug detection (Excel vs data.json)
- Copy-paste format Cascade-ისთვის

#### 🟡 Tier 2 — Proactive (Phase 3, 2 კვირა)
- Daily morning briefing (Telegram + PWA push)
- Anomaly detection (statistical)
- Cash flow projection
- Per-location performance alerts

#### 🔵 Tier 3 — Strategic (Phase 4-5, 4 კვირა)
- Scenario simulation ("რა თუ...")
- Pricing optimization
- Expansion analysis
- Long-term memory (business goals tracking)
- Industry benchmark comparison
- Valuation scenarios

---

## 🛠️ 3. Pre-AI Foundation (1 კვირა)

AI-ს აშენებას წინ სჭირდება foundation cleanup.

### 3.1 Packet H Completion

- [ ] **Process 13: cashflow** 
  - backend audit: `_build_cashflow_summary_response` period-awareness
  - if needed: extend builder to apply period filter
  - frontend wiring: `'cashflow'` to `PERIOD_PICKER_TABS`, `'cashflow_summary'` to `SAFE_PERIOD_REQUEST_TABS`
  - live HTTP + CLI Playwright verification
- [ ] HANDOFF.md + PLAN.md finalization: *"Packet H complete"*

### 3.2 Data Quality Audit

**10 spot-checks** data.json vs Excel:
- [ ] 2025-08 P&L totals (ოზურგეთი + დვაბზუ)
- [ ] 2025-12-15 რეზონალური waybills (minimum 5 ცალი)
- [ ] Top 3 supplier-ის ყოველწლიური ჯამი (3 წელი)
- [ ] 2026-02 retail sales (გადაამოწმე 2026-02-28-ის 24,980 rows)
- [ ] BOG POS terminal (POS30BOE) ყოველთვიური ჯამი
- [ ] Manual payments (`manual_payments.csv`) vs `data.json` reconciliation
- [ ] 2024 vs 2025 YoY gross margin
- [ ] Inventory turnover (top 10 product)
- [ ] Salary allocation (ოზურგეთი vs დვაბზუ)
- [ ] TBC expense categorization — top 5 category totals

**ქმედებები discrepancy-ს აღმოჩენისას:**
- Documentation-ში ცხადი note
- Pipeline bug fix (Cascade-ით)
- Re-verify after fix

### 3.3 Code Hygiene

- [ ] `deprecated-root-copy/root-cleanup-20260415-112311/` — archive გარე (backup drive-ზე)
- [ ] `HANDOFF.md` (862 lines) → `HANDOFF_ARCHIVE/2026-04-packet-h.md` + fresh HANDOFF
- [ ] `requirements.txt` — pinned versions:
  ```
  pandas==2.2.3
  openpyxl==3.1.5
  fastapi==0.115.4
  uvicorn==0.32.0
  slowapi==0.1.9
  apscheduler==3.10.4
  ```
- [ ] `package.json` — lockfile audit (`npm audit`)
- [ ] Create root `.env.example`:
  ```
  DASHBOARD_API_KEY=
  ANTHROPIC_API_KEY=
  TELEGRAM_BOT_TOKEN=
  TELEGRAM_CHAT_ID=
  AI_BUDGET_CAP_USD=100
  AI_MODEL=claude-sonnet-4-6
  ```

### 3.4 External Setup

- [ ] **Anthropic API Account:** https://console.anthropic.com
  - დარეგისტრირება
  - Credit card attach
  - Budget limit: $100/month
  - Generate API key → `.env` (never commit!)
- [ ] **Telegram Bot:**
  - BotFather-ში `/newbot` → bot name + username
  - Get token → `.env`
  - Create private chat with bot, get chat_id
- [ ] **Anthropic Claude Console usage tracking** — bookmark-ი

**⏱️ Timeline:** 5-7 დღე (ცალ-ცალკე სესიებში)

---

## 🏛️ 4. AI Architecture (State-of-the-art 2026)

### 4.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      USER INTERFACES                          │
├──────────────────────────────────────────────────────────────┤
│  📱 PWA Chat    │  📧 Telegram Bot  │  🎤 Voice (Whisper)    │
└────────┬─────────────────┬─────────────────┬─────────────────┘
         │                 │                 │
         └─────────────────┴─────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   AI AGENT LAYER (LangGraph)                  │
├──────────────────────────────────────────────────────────────┤
│  • Planning node (decide which tools to use)                  │
│  • Tool calling (structured function calls)                   │
│  • Reflection (validate output)                               │
│  • Response formatting (Georgian, markdown)                   │
└────────┬──────────────────────────────────────────────────────┘
         │
         ├──► Claude Sonnet 4.6 API
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│                      TOOL LAYER                               │
├──────────────────────────────────────────────────────────────┤
│  📄 read_data_json     📊 query_pnl        🔍 find_anomaly   │
│  📑 read_excel_source  📈 forecast_scenario  ⚠️ validate_vs_source │
│  💾 read_source_code   🎯 compare_to_benchmark  📝 log_insight  │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│                      DATA LAYER                               │
├──────────────────────────────────────────────────────────────┤
│  data.json  │  Excel files  │  source code  │  git history   │
│             │  (Financial_  │  (pipeline)   │                │
│             │   Analysis/)  │               │                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    MEMORY LAYER                               │
├──────────────────────────────────────────────────────────────┤
│  Conversation history  │  Vector DB (embeddings)              │
│  (SQLite)              │  (ChromaDB for semantic search)      │
│  Business goals        │  Past insights (learned patterns)    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                  SCHEDULING LAYER (existing APScheduler)      │
├──────────────────────────────────────────────────────────────┤
│  • Daily 9:00 briefing job                                    │
│  • Real-time anomaly scan (every 15 min)                      │
│  • Weekly deep analysis (Monday 9:00)                         │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Tech Stack Choices

| Layer | ტექნოლოგია | რატომ |
|---|---|---|
| **Primary LLM** | Claude Sonnet 4.6 | Best financial reasoning, Georgian fluency (updated 2026-04-17) |
| **Fallback LLM** | Claude Haiku 4.5 | Cheaper + faster for simple queries (updated 2026-04-17) |
| **Agent Framework** | LangGraph (v0.2+) | Stateful multi-step reasoning, checkpointing |
| **Tool Calling** | Native Anthropic SDK | Clean function calling, no framework tax |
| **Vector DB** | ChromaDB (embedded) | Lightweight, no separate server |
| **Embeddings** | sentence-transformers (local) | Free, multilingual, no API cost |
| **Conversation Store** | SQLite | Simple, built-in, zero setup |
| **Telegram** | python-telegram-bot | Mature, async-friendly |
| **Voice** | Whisper API (OpenAI) | Only paid dependency for voice |
| **Frontend** | React (existing) + react-markdown | Reuse Vite build |

### 4.3 Prompt Engineering Strategy

**System Prompt Structure:**

```
<IDENTITY>
შენ ხარ ფინანსური მრჩეველი "იოლი მარკეტი" ფრენჩაიზისთვის.
2 მაღაზია: ოზურგეთი (3 POS) + დვაბზუ (2 POS).
ენა: ქართული (ბიზნეს-ფორმალური, მაგრამ ცოცხალი).
</IDENTITY>

<CAPABILITIES>
- Data კითხვა data.json-დან (ინსტრუმენტი: read_data_json)
- Excel source-ების შედარება (ინსტრუმენტი: read_excel_source)
- Source code ინსპექცია (ინსტრუმენტი: read_source_code)
- Anomaly detection (ინსტრუმენტი: find_anomaly)
- Benchmark comparison (ინსტრუმენტი: compare_to_benchmark)
</CAPABILITIES>

<RULES>
1. ყოველი ციფრთან — source attribution: "წყარო: {file} → {field}"
2. თუ data-ში არ არის — "ეს მონაცემი არ მაქვს" (არასოდეს გამოიგონო)
3. Unusual ციფრებს აფრთხილე: "გადამოწმე Excel-ში"
4. Bug-ის აღმოჩენისას — copy-paste format Cascade-ისთვის
5. Strategic რჩევისას — 3 perspective: სარგებელი, რისკი, ალტერნატივა
</RULES>

<BUSINESS_CONTEXT>
- Franchise: "იოლი მარკეტი"
- Revenue streams: POS + cash + bank transfer
- Key KPIs: gross margin, net margin, AP days, inventory turnover
- Industry benchmarks: {sector_benchmarks.json}
- Current locations: ოზურგეთი (urban), დვაბზუ (rural)
</BUSINESS_CONTEXT>

<OUTPUT_FORMAT>
- Markdown formatting
- Tables for comparisons
- Bullet points for actions
- Emoji for visual scan (📊 for data, ⚠️ for warnings, 🎯 for actions)
</OUTPUT_FORMAT>
```

### 4.4 Tool Definitions (OpenAPI-style)

```python
TOOLS = [
    {
        "name": "read_data_json",
        "description": "Read specific section of data.json",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "enum": ["suppliers", "waybills", "monthly_pnl", ...]},
                "filter": {"type": "object", "optional": True}
            }
        }
    },
    {
        "name": "read_excel_source",
        "description": "Read source Excel from Financial_Analysis/",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "sheet": {"type": "string", "optional": True},
                "date_range": {"type": "object", "optional": True}
            }
        }
    },
    # ... 8 more tools
]
```

---

## 📅 5. Phased Implementation Plan

### Phase 0 — Foundation (1 კვირა)

**მიზანი:** Packet H-ის დასრულება + cleanup

**Deliverables:**
- ✅ `cashflow` process accepted
- ✅ Data audit report (10 spot-checks)
- ✅ Clean `requirements.txt` + `package.json`
- ✅ `.env.example` (root)
- ✅ `deprecated-root-copy/` archived externally
- ✅ `HANDOFF.md` → archived, fresh start
- ✅ Anthropic API key acquired
- ✅ Telegram bot created
- ✅ Initial "hello" test: Claude API reachable from Python

**Verification:** `python -c "import anthropic; client = anthropic.Anthropic(); print(client.messages.create(...))"`

**Time:** 5-7 დღე

---

### Phase 1 — MVP Chat (1 კვირა)

**მიზანი:** Dashboard-ში Chat UI რომ კითხვაზე პასუხობდეს `data.json`-დან

**Backend:**
- ახალი ფაილი: `dashboard_pipeline/ai/__init__.py`
- ახალი ფაილი: `dashboard_pipeline/ai/agent.py` — basic agent
- ახალი ფაილი: `dashboard_pipeline/ai/prompts.py` — system prompt + few-shot
- ახალი ფაილი: `dashboard_pipeline/ai/tools.py` — `read_data_json` tool
- `server.py`: ახალი endpoint `POST /api/chat`
- Rate limit: 30/minute (expensive LLM calls)

**Frontend:**
- ახალი კომპონენტი: `rs-dashboard/src/components/ChatAssistant.jsx`
- Floating button (bottom-right, mobile-friendly)
- Chat modal overlay (full-screen mobile, side-panel desktop)
- `react-markdown` dependency
- `useAIChat` hook: state management + API calls
- Source attribution rendering (collapsible expandable sections)

**Tests:**
- Unit: prompt template rendering
- Integration: `/api/chat` endpoint (mocked LLM)
- E2E: Playwright test chat button + message flow

**Success Criteria:**
- [ ] Chat button ჩანს ყველა page-ზე
- [ ] კითხვა → პასუხი < 5 წამში
- [ ] Source attribution 100% of responses
- [ ] ქართული ენა fluent
- [ ] Mobile-friendly (iPhone Safari + Android Chrome)

**Time:** 4-6 დღე

**Cost:** $0-5 (development testing)

---

### Phase 2 — Investigator (2 კვირა)

**მიზანი:** Bug detection + Cascade-ისთვის copy-paste output

**New Tools:**
- `read_excel_source(file_path, sheet, date_range)` — pandas-ით
- `read_source_code(file_path, line_range)` — კოდის ფრაგმენტების კითხვა
- `validate_vs_source(tab, date_range)` — ავტომატური cross-check
- `grep_code(pattern)` — regex search პროექტში

**New Prompts:**
- "Investigator mode" system prompt
- Few-shot examples (Excel vs data.json discrepancy)
- Copy-paste output template for Cascade

**Backend:**
- `dashboard_pipeline/ai/investigator.py` — specialized agent
- `/api/chat` extends: `mode: "chat" | "investigate"`
- Caching for Excel reads (24-hour TTL)

**Frontend:**
- "🔍 Investigate" button in ChatAssistant
- Collapsible "Copy for Cascade" section
- Source comparison table UI

**Success Criteria:**
- [ ] ერთი real bug აღმოაჩინოს data.json-ში
- [ ] Copy-paste format works end-to-end with Cascade
- [ ] Excel read < 3 წამი (cache hit)
- [ ] Georgian business vocabulary accurate

**Time:** 8-10 დღე

**Cost:** $3-8/month (Investigator uses more tokens)

---

### Phase 3 — Proactive Anomaly + Daily Briefing (1 კვირა)

**მიზანი:** ყოველდღე 9:00 Telegram briefing + real-time alerts

**Backend:**
- ახალი ფაილი: `dashboard_pipeline/ai/anomaly.py`
  - Statistical methods: 3-sigma, IQR, rolling average
  - Per-location analysis (ოზურგეთი vs დვაბზუ)
  - POS terminal health check
  - Cash flow projection (7-day rolling)
- ახალი ფაილი: `dashboard_pipeline/ai/scheduler.py`
  - Daily 9:00 job
  - Briefing template generation
- ახალი ფაილი: `dashboard_pipeline/ai/telegram_bot.py`
  - Send formatted message
  - Handle /commands (/details, /query, /mute)

**APScheduler Integration:**
- Existing scheduler-ს ემატება 2 ახალი job:
  - `daily_briefing_9am` — cron ('0 9 * * *')
  - `anomaly_scan_15min` — interval (15 min)

**Briefing Template:**
```
დილა მშვიდობისა! [date] briefing:

📊 გუშინდელი შედეგი:
- ოზურგეთი: {amount} ₾ ({trend} vs week avg)
- დვაბზუ: {amount} ₾ ({trend} vs week avg)

💰 Cash Flow (7-day):
- Cash on hand: {balance}
- გადასახდელი: {outflow}
- Expected income: {projection}
- Gap: {net}

⚠️ ყურადღება:
{anomalies_list}

🎯 დღევანდელი priorities:
{top_3_actions}
```

**Success Criteria:**
- [ ] Daily briefing delivers at 9:00 ± 5 წთ
- [ ] False positive rate < 20%
- [ ] Telegram message render-ი clean
- [ ] User can `/mute` briefing
- [ ] PWA push notification fallback

**Time:** 5-7 დღე

**Cost:** $5-10/month (daily queries accumulate)

---

### Phase 4 — Scenario Simulation (2 კვირა)

**მიზანი:** "რა თუ..." scenarios + gradual decision support

**New Tools:**
- `forecast_scenario(params)` — price change, cost change, volume change
- `cash_flow_projection(days, scenario)` — what-if cash flow
- `break_even_analysis(fixed_costs, variable_costs, price)` — BE calculator
- `pricing_optimization(product_category)` — margin suggestion
- `expansion_analysis(new_location_params)` — 3-ე მაღაზიის სცენარი

**New Prompts:**
- "Strategic advisor mode"
- 3-perspective framework (სარგებელი / რისკი / ალტერნატივა)
- Industry benchmark comparison template

**Backend:**
- `dashboard_pipeline/ai/simulator.py` — pandas-based calculations
- `/api/chat` extends: `mode: "strategize" | "simulate"`

**Frontend:**
- "🎯 Scenario" mode toggle
- Parameter input form (price, cost, volume sliders)
- Result visualization (recharts — existing!)

**Success Criteria:**
- [ ] User runs 3+ scenarios per week
- [ ] Decision support rating 4/5+
- [ ] Calculations validate against manual Excel

**Time:** 8-10 დღე

**Cost:** $10-20/month (heavy reasoning)

---

### Phase 5 — Full Business Advisor (2 კვირა)

**მიზანი:** Long-term memory + strategic partnership

**New Components:**
- **Long-term Memory (ChromaDB):**
  - User's business goals (quarterly)
  - Past insights (confirmed + rejected)
  - Decision history (what was done, outcome)
  - Preferences (risk tolerance, priority areas)
- **Metacognition:**
  - "რა data-ც აკლია ზუსტი რჩევისთვის"
  - "შემომიტანე ეს ფაილი" requests
  - Confidence scoring (high / medium / low)
- **Weekly Strategic Review:**
  - Every Monday 9:00 deeper analysis
  - YoY comparison
  - Trend identification
  - Goal progress tracking

**Backend:**
- `dashboard_pipeline/ai/memory.py` — ChromaDB wrapper
- `dashboard_pipeline/ai/strategist.py` — weekly review generation
- Embedding model: `paraphrase-multilingual-MiniLM-L12-v2` (ქართული support)

**Frontend:**
- "🎯 ჩემი მიზნები" tab — goal tracker
- "📊 ჩემი insights" tab — confirmed AI recommendations
- Weekly review UI (email-style digest)

**Success Criteria:**
- [ ] Daily usage 5+ interactions
- [ ] User satisfaction 8/10+
- [ ] ROI: 5+ saved hours/week (self-report)
- [ ] Memory recall accurate 90%+

**Time:** 8-10 დღე

**Cost:** $15-35/month (full system)

---

## 📁 6. Technical Specifications

### 6.1 New Files

```
financial-dashboard/
├── AI_ADVISOR_ROADMAP.md (this file)
├── .env.example (root)
├── dashboard_pipeline/
│   └── ai/
│       ├── __init__.py
│       ├── agent.py              # Main LangGraph agent
│       ├── investigator.py       # Phase 2: Bug detection
│       ├── anomaly.py            # Phase 3: Statistical anomaly
│       ├── scheduler.py          # Phase 3: Daily briefing jobs
│       ├── telegram_bot.py       # Phase 3: Telegram integration
│       ├── simulator.py          # Phase 4: Scenario calculations
│       ├── strategist.py         # Phase 5: Weekly review
│       ├── memory.py             # Phase 5: ChromaDB wrapper
│       ├── prompts.py            # All system prompts
│       ├── tools.py              # All tool definitions
│       └── config.py             # AI-specific config
├── rs-dashboard/
│   └── src/
│       ├── components/
│       │   ├── ChatAssistant.jsx     # Phase 1
│       │   ├── ChatMessage.jsx       # Phase 1
│       │   ├── ScenarioInput.jsx     # Phase 4
│       │   └── AIInsights.jsx        # Phase 5
│       ├── hooks/
│       │   ├── useAIChat.js          # Phase 1
│       │   └── useVoiceInput.js      # Optional
│       └── lib/
│           └── aiClient.js           # API wrapper
└── tests/
    ├── test_ai_agent.py              # Phase 1
    ├── test_ai_tools.py              # Phase 1-2
    ├── test_ai_anomaly.py            # Phase 3
    └── test_ai_simulator.py          # Phase 4
```

### 6.2 Dependencies (Additional)

**Python (`requirements.txt` additions):**
```
anthropic>=0.40.0
langgraph>=0.2.0
langchain-anthropic>=0.2.0
chromadb>=0.5.0
sentence-transformers>=3.0.0
python-telegram-bot>=21.0
pydantic>=2.0.0
httpx>=0.27.0
```

**Frontend (`rs-dashboard/package.json` additions):**
```json
{
  "dependencies": {
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "react-syntax-highlighter": "^15.5.0"
  }
}
```

### 6.3 Environment Variables

```bash
# LLM Configuration
ANTHROPIC_API_KEY=sk-ant-api03-...
AI_MODEL=claude-sonnet-4-6
AI_MODEL_FALLBACK=claude-haiku-4-5-20251001
AI_MAX_TOKENS=4096
AI_TEMPERATURE=0.3

# Budget & Limits
AI_BUDGET_CAP_USD=100
AI_BUDGET_WARN_PCT=80
AI_RATE_LIMIT_PER_HOUR=60

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_MUTE_UNTIL=

# Feature Flags
AI_FEATURE_DAILY_BRIEFING=true
AI_FEATURE_ANOMALY_ALERTS=true
AI_FEATURE_VOICE=false
AI_FEATURE_WEEKLY_REVIEW=true

# Paths
AI_MEMORY_DB_PATH=./ai_memory.db
AI_VECTOR_DB_PATH=./ai_vectors/
AI_LOG_PATH=./logs/ai.log
```

### 6.4 API Endpoints (New)

| Endpoint | Method | Purpose | Rate Limit |
|---|---|---|---|
| `/api/chat` | POST | Main chat interface | 30/min |
| `/api/chat/stream` | POST | Streaming responses (SSE) | 30/min |
| `/api/chat/history` | GET | Conversation history | 60/min |
| `/api/chat/clear` | POST | Reset conversation | 10/min |
| `/api/ai/investigate` | POST | Bug detection mode | 10/min |
| `/api/ai/simulate` | POST | Scenario simulation | 20/min |
| `/api/ai/goals` | GET/POST | Business goals CRUD | 60/min |
| `/api/ai/insights` | GET | Past insights list | 60/min |
| `/api/ai/briefing` | GET | Manual briefing trigger | 5/min |
| `/api/ai/status` | GET | AI system health + budget | 60/min |

---

## 💰 7. Cost & Timeline

### 7.1 Development Timeline

```
კვირა 1:   [Phase 0] Foundation ████████
კვირა 2-3: [Phase 1] MVP Chat   ████████████████
კვირა 4-5: [Phase 2] Investigator ████████████████
კვირა 6:   [Phase 3] Daily Brief ████████
კვირა 7-8: [Phase 4] Scenarios  ████████████████
კვირა 9:   [Phase 5] Advisor    ████████
```

**სულ: 9 კვირა** (~2.25 თვე)

### 7.2 Monthly Cost Breakdown

| Phase | Claude API | Telegram | ChromaDB | Whisper (opt) | **Total** |
|---|---|---|---|---|---|
| Phase 1 (MVP) | $3-8 | $0 | $0 | $0 | **$3-8** |
| Phase 2 (Invest.) | $8-15 | $0 | $0 | $0 | **$8-15** |
| Phase 3 (Briefing) | $15-25 | $0 | $0 | $0 | **$15-25** |
| Phase 4 (Scenario) | $25-40 | $0 | $0 | $0-5 | **$25-45** |
| Phase 5 (Full) | $40-60 | $0 | $0 | $0-10 | **$40-70** |

**Target:** $80/თვე — **fits** Phase 5 full system

### 7.3 Development Cost

**Cascade (via Windsurf):** $0 (გადახდილი subscription-ით)
**External developer equivalent:** $3,000-5,000 (80-100 hours × $40-60/hr)

### 7.4 ROI Calculation

**დროის ეკონომია:** 5-10 საათი/კვირა = 20-40 საათი/თვე
- თუ შენი საათი $10/hr → $200-400/თვე value
- თუ შენი საათი $20/hr → $400-800/თვე value

**Cost:** $40-80/თვე
**ROI:** **5-10x**

+ **Decision quality improvement** (non-measurable, but potentially highest value)

---

## ⚠️ 8. Risk Management

### 8.1 Technical Risks

| რისკი | მავნე გავლენა | Mitigation |
|---|---|---|
| **LLM Hallucination** | არასწორი ციფრი → wrong decision | ❶ Source attribution on every claim ❷ "Don't know" fallback ❸ Post-hoc validation tool |
| **API Cost Overrun** | Budget > $100 | ❶ Monthly cap in Anthropic Console ❷ In-app budget tracking ❸ Haiku 4.5 fallback for simple queries |
| **Rate Limit Hit** | AI unavailable | ❶ Client-side queuing ❷ Local cache for repeat queries ❸ Graceful degradation messaging |
| **Telegram Bot Down** | No morning briefing | ❶ PWA push fallback ❷ Email fallback (future) ❸ In-app dashboard widget |
| **Pipeline Failure** | Stale data for AI | ❶ Existing `/api/status` freshness check ❷ AI refuses to answer if data > 24h old |

### 8.2 Business Risks

| რისკი | გავლენა | Mitigation |
|---|---|---|
| **Over-reliance on AI** | Atrophying judgment | AI რჩევები ყოველთვის marked "suggestion", user-ი decision maker |
| **False Anomaly Alerts** | Alert fatigue | Tunable sensitivity, "mark as not-anomaly" feedback loop |
| **Data Privacy Concern** | Sensitive data leak | Anthropic terms review, no PII in prompts (TIN masking optional Phase 6) |
| **User Adoption Lag** | $80/თვე wasted | Phase 1 MVP-ი fast launch, iterate on feedback |

### 8.3 Failure Modes & Recovery

**თუ Phase 1 MVP უხერხულია:** Pause, iterate on prompts (1 week), don't go Phase 2
**თუ Claude API ცუდად მოქმედებს:** Switch to GPT-4o (provider-agnostic design)
**თუ ღირებულება ასცდა budget-ს:** Haiku 4.5-only mode ($5-10/month), still functional

---

## 📊 9. Success Metrics

### 9.1 Phase-level Metrics

#### Phase 1 (MVP)
- Response time median: < 5 წამი
- Source attribution: 100%
- User satisfaction: ≥ 4/5
- Georgian fluency (subjective): ≥ 4/5

#### Phase 2 (Investigator)
- Real bugs found: ≥ 1 in first month
- Copy-paste success rate: ≥ 95%
- Cross-validation accuracy: ≥ 98%

#### Phase 3 (Briefing)
- Delivery reliability: ≥ 98% daily
- False positive rate: < 20%
- User reads briefing: ≥ 80% of days (self-report)

#### Phase 4 (Scenarios)
- Scenarios run/week: ≥ 3
- Calculation accuracy (vs manual Excel): ≥ 99%
- Decision support rating: ≥ 4/5

#### Phase 5 (Advisor)
- Daily active usage: ≥ 5 interactions
- Memory recall accuracy: ≥ 90%
- User satisfaction: ≥ 8/10
- Self-reported time savings: ≥ 5 hrs/week

### 9.2 Business Impact (Quarterly Review)

- Cash flow forecast accuracy improvement: +20%
- Data quality issues caught early: +5/quarter
- Decision confidence (self-report): 1-10 scale, +2 points
- Strategic options considered: +30%

---

## 🚀 10. Next Actions

### 10.1 Immediate (ეს კვირა)

- [ ] **User approval** of this roadmap (← თქვენ ახლა)
- [ ] Anthropic API account creation
- [ ] Telegram bot creation via BotFather
- [ ] `.env.example` (root) creation
- [ ] Start Phase 0: cashflow process

### 10.2 Phase 0 Kickoff (მომდევნო კვირა)

1. `cashflow` process (backend + frontend wiring + verification)
2. Data audit spot-checks (10 items)
3. `deprecated-root-copy/` archival
4. `HANDOFF.md` split (archive + fresh)
5. `requirements.txt` version pinning
6. Initial Claude API connection test

### 10.3 Approval Points (Milestones)

- **M1:** After Phase 1 MVP → "მოგწონს? Phase 2-ს ვიწყებთ?"
- **M2:** After Phase 3 Briefing → "Daily briefing-ი სასარგებლოა? Phase 4?"
- **M3:** After Phase 5 → Full review, future roadmap

თითოეული milestone-ს აქვს **exit point** — შეგიძლია შეაჩერო ყოველთვის.

---

## 📌 Appendix A: LLM Model Comparison

| მოდელი | Input $/1M | Output $/1M | Context | Georgian | Reasoning | რჩევა |
|---|---|---|---|---|---|---|
| **Claude Sonnet 4.6** | $3 | $15 | 200K | 🥇 | 🥇 | ⭐ **Primary** (2026) |
| Claude Haiku 4.5 | $1 | $5 | 200K | 🥈 | 🥈 | **Fallback** for simple (2026) |
| Claude 3 Opus | $15 | $75 | 200K | 🥇 | 🥇 | Too expensive |
| GPT-4o | $2.50 | $10 | 128K | 🥈 | 🥈 | Alternative |
| GPT-4o-mini | $0.15 | $0.60 | 128K | 🥉 | 🥉 | Too weak |
| Gemini 1.5 Pro | $1.25 | $5 | 2M | 🥉 | 🥈 | Unclear ქართული |

## 📌 Appendix B: File-level Reading List for Phase 0

Pre-AI discovery reading:
- `dashboard_pipeline/api_contracts.py` (2163 lines) — API contract
- `dashboard_pipeline/analytics_builders.py` (~2000 lines) — KPI calculations
- `generate_dashboard_data.py` (1456 lines) — Pipeline entry
- `dashboard_pipeline/supplier_matching.py` (30KB) — Matching logic
- `dashboard_pipeline/bank_reconciliation.py` (60KB) — Banking logic
- `Financial_Analysis/sector_benchmarks.json` — AI context source
- `Financial_Analysis/object_mapping.json` — Location resolution

## 📌 Appendix C: Prompt Library Preview

Few-shot examples-ი AI-ისთვის (Phase 1+):

**Example 1: Simple query**
```
Q: რა იყო ოზურგეთის შემოსავალი 2025-დეკემბერში?
A: 📊 ოზურგეთის შემოსავალი (2025-12): 185,400 ₾
   წყარო: data.json → monthly_pnl → 2025-12 → ოზურგეთი
   Breakdown: POS 142K + bank transfer 28K + cash 15K
```

**Example 2: Bug detection**
```
Q: ბოლო 7 დღის waybills-ები Excel-ში 14-ია, dashboard-ში 12
A: ⚠️ შეუსაბამობა დადასტურდა
   წყარო 1 (Excel): 14 ფაილი, ჯამი 920,300 ₾
   წყარო 2 (data.json): 12 ჩანაწერი, ჯამი 850,400 ₾
   
   🔍 მიზეზი: 2 ზედნადების TIN 9-ნიშნაა, regex 11-ნიშნაზეა
   📋 Cascade-ისთვის: [copy-paste block]
```

**Example 3: Strategic advice**
```
Q: ფასი ავწიო 5%-ით top-5 პროდუქტზე?
A: 🎯 ანალიზი ამ კითხვაზე
   📊 მიმდინარე: top-5 გვაძლევს 32% ჯამური margin-ის
   სცენარი: +5% ფასი
     ოპტიმისტური (elasticity -0.5): +2.5% revenue, +8% profit
     რეალისტური (elasticity -1.0): 0% revenue, +5% profit
     პესიმისტური (elasticity -1.5): -2.5% revenue, +2% profit
   
   ⚠️ რისკი: კონკურენტების ფასების შემოწმება აუცილებელია
   🎯 რეკომენდაცია: A/B test 1 პროდუქტზე, 2 კვირა
```

---

## 🎬 Closing Note

ეს roadmap არის **working document** — შენი feedback-ით განახლდება.

**ღია კითხვები:**
1. ქართული voice input (Whisper) — ღირს $5-10/თვე-ის დამატებითი ხარჯი?
2. TIN masking/anonymization — Phase 6-ზე გადავდოთ?
3. Multi-location benchmarking — ოზურგეთი vs industry averages?

**მომდევნო ნაბიჯი:**
გადახედე ეს document. თუ OK-ია, **Phase 0-ს დავიწყებ** (`cashflow` process + cleanup).

---

*Document version: 1.0 | Authored: 2026-04-17 | Status: Draft, awaiting approval*
