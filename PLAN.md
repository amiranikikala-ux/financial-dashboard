# გეგმა

## სტეკი
Python (pandas) + FastAPI (`server.py`) | React 19 + Vite (`rs-dashboard/`) | Excel → `data.json` → UI

## დასრულებული: ფაზა 1-2
აუდიტი, logging, DRY refactor, dead code cleanup, Cashflow.jsx გამოტანა.

## ფაზა 3: კოდის ხარისხი (დასრულებული)
- [x] `App.jsx` → Suppliers.jsx, Waybills.jsx build ტესტი OK
- [x] `run()` — 5 helper ამოღებული (1024→625 ხაზი)
- [x] `run()` — RS processing: +3 helper (625→211 ხაზი, ჯამი 8 helper)
- [x] CSS ორგანიზება: 4698 ხაზი → 7 ფაილი `src/styles/`-ში
- [x] 105 ახალი unit ტესტი (supplier_matching + bank_reconciliation)
- [x] API rate limiting (slowapi 60/min per IP)

## ფაზა 4: ახალი ფუნქციონალი (დასრულებული)
- [x] APScheduler 30წთ auto-refresh + /api/status + /api/refresh
- [x] RefreshButton + useDataStatus hook header-ში
- [x] ExportButton კომპონენტი + exportXlsx.js utility (11/14 ტაბზე)
- [x] მობილური bottom nav (4 quick tabs + "სხვა" sheet)
- [x] Touch: 44px targets, iOS zoom fix, viewport-fit=cover, safe-area

## ფაზა 5: ტესტირება და deploy (დასრულებული)
- [x] E2E ტესტები (Playwright) — 38 ტესტი 5 spec ფაილში
- [x] API auth — ApiKeyMiddleware (DASHBOARD_API_KEY env), X-API-Key header
- [x] PWA offline — manifest.json + sw.js (stale-while-revalidate + network-first API)

## ფაზა 6: Performance Optimization (დასრულებული)
- [x] PNG იკონები PWA-სთვის (192x192, 512x512) — session #30
- [x] Bundle size ანალიზი და ოპტიმიზაცია — session #31
  - manualChunks: vendor-react (190KB), vendor-recharts (432KB) ცალკე ჩანქებში
  - Build target: esnext (modern browsers)
  - Bundle analyzer: rollup-plugin-visualizer (`npm run build:analyze`)
  - App core: 199KB → 17KB (gzip 5.8KB)
  - საწყისი ჩატვირთვა (gzip): ~87KB

## ფაზა 7: დამატებითი E2E ტესტები (დასრულებული)
- [x] export.spec.js — 9 ტესტი: ExportButton 7 ტაბზე + CSV ბათონი — session #32
- [x] supplier-modal.spec.js — 16 ტესტი: open/close/content/keyboard/backdrop — session #32
- [x] mock-data.js განახლება: supplier ველები + retail_sales სტრუქტურა + imported_supplier_detail
- [x] 63/63 E2E, 125/125 unit, Vite build clean

## ფაზა 8: Calendar UX Upgrade (დასრულებული)
- [x] Packet F: custom კალენდრების შეცვლა `react-datepicker`-ით — session #33

## ფაზა 9: Unified date-range business logic (დასრულებული)
- [x] Packet G: `/api/data` date/time contract დაემატა `from_date`, `to_date`, `from_time`, `to_time`
- [x] `waybills` filtered backend პასუხები და summary იმავე canonical period-ზე გადავიდა
- [x] `retail_sales` filtered backend პასუხები იმავე canonical period-ზე გადავიდა
- [x] frontend request propagation დადასტურდა `waybills` და `retail_sales` ტაბებზე
- [x] live blocker fix: filtered `retail_sales` აღარ ჰანგდება single-worker backend-ზე
  - minimal/safe optimization მხოლოდ:
    - `dashboard_pipeline/retail_sales.py`
    - `dashboard_pipeline/api_contracts.py`
  - approach:
    - cached `retail_sales.files` metadata file-level date pruning-ისთვის
    - მხოლოდ საჭირო Excel columns-ის კითხვა
    - vectorized date filtering row-loop-მდე
    - aggregation მხოლოდ დარჩენილ rows-ზე
  - invariants:
    - ბიზნეს-ლოგიკა უცვლელია
    - response contract უცვლელია
- [x] დადასტურებული შედეგები
  - live API checks:
    - `/api/status` -> `200 OK`
    - filtered `waybills` -> `200 OK`
    - filtered `retail_sales` -> `200 OK`
  - business checks:
    - `waybills` (`2026-02-01` -> `2026-02-28`): `matched_rows=533`, `total_nominal_amount=136042.75`, `total_effective_amount=135631.35`
    - `retail_sales` (`2026-02-01` -> `2026-02-28`): `matched_rows=24980`, `revenue_ge=92316.83`, `profit_ge=14159.1941`
    - zero-match `2026-03-*`: valid empty filtered response
  - performance:
    - same filtered `retail_sales` path დაახლოებით `671.9s` -> დაახლოებით `25.7s`
    - test day-ზე `files_read_count = 1`
  - UI smoke:
    - `retail_sales`: `დამთხვეული: 24,980`
    - `waybills`: `ჩანაწერი: 533`

### Packet F — Calendar UX Upgrade

**პრობლემა:** custom-built კალენდრები უხერხულია გამოსაყენებლად.

**შესაცვლელი კომპონენტები (3 ცალი):**

1. **`DateTimeCalendarPicker.jsx`** — header-ის გლობალური თარიღი+დრო picker
   - გამოყენება: `App.jsx` (line ~259)
   - Props: `fromDate`, `fromTime`, `toDate`, `toTime` + onChange handlers
2. **`CalendarRangePicker.jsx`** — POS დღიური date range picker
   - გამოყენება: `Cashflow.jsx` (line ~680)
   - Props: `availableDays[]`, `from`, `to` + onChange handlers + `children`
3. **`DateRangePicker.jsx`** — თვის range picker (select dropdowns)
   - გამოყენება: `PnL.jsx` (line ~276), `Budget.jsx` (line ~383)
   - Props: `allMonths[]`, `from`, `to` + onChange handlers + `children`

**გეგმა:**
1. `npm install react-datepicker` (`rs-dashboard/`)
2. შექმნა ახალი wrapper კომპონენტები `react-datepicker`-ზე, იგივე prop interface-ით
3. CSS თემის მორგება dashboard-ის dark theme-ზე
4. ძველი custom კომპონენტების CSS-ის cleanup (crp-*, dtcp-* classes `components.css`-ში)
5. `npm run lint` + `npm run build` verification

**შენიშვნა:** `react-datepicker` მხარდაჭერს date range, time selection, locale, dark theme-ს.

## ფაზა 10: Dashboard-wide calendar propagation (დასრულებული — 2026-04-17)

**სტატუსი:** Packet H complete. Process 0-12 accepted (ყველა safe tab period-aware).  
**cashflow:** documented intentional exception — uses internal per-section calendars (POS daily via `CalendarRangePicker`), global header calendar ცნობიერად გამოტოვებულია (`cashflow_summary` არის management summary view, not transaction log).

### Accepted period-aware tabs (Process 0-12):
`suppliers`, `waybills`, `retail_sales`, `imported_products`, `working_capital`, `ratios`, `forecast`, `budget`, `valuation`, `executive`, `insights`, `pnl`, `analytics`

### Packet H history (reference)
- [x] Packet H: business page names ↔ რეალური tab keys / frontend components / backend builders mapping
- [x] ერთი canonical calendar window ყველა target page-ზე:
  - მომწოდებელი
  - ზედნადები ანალიტიკა
  - ბანკი
  - პროდუქცია
  - გაყიდვები
  - P&L
  - კაპიტალი
  - კოეფიციენტი
  - პროგნოზი
  - ბიუჯეტი
  - შეფასება
  - Executive Insights
- [ ] single-day behavior დაფიქსირდეს როგორც first-class rule:
  - თუ არჩეულია მხოლოდ ერთი დღე, მაგალითად `2026-02-05`, canonical period იყოს:
    - `from_date=2026-02-05`
    - `to_date=2026-02-05`
    - `from_time=00:00`
    - `to_time=23:59`
  - date filter იყოს explicit და inclusive
- [ ] frontend-ზე calendar visible + state propagation ყველა target page-ზე
- [ ] ყველა target request-ში გავიდეს:
  - `from_date`
  - `to_date`
  - `from_time`
  - `to_time`
- [ ] backend period-filter semantics დაემატოს ყველა target tab-ს minimal-change რეჟიმში
- [ ] თითო tab-ზე authoritative date semantics დადგინდეს:
  - transaction window
  - summary period
  - end-of-day snapshot
  - forecast anchor / derived analytics
- [ ] business logic უცვლელად დარჩეს
- [ ] response contract უცვლელად დარჩეს, თუ ცვლილება აბსოლუტურად აუცილებელი არ გახდა
- [ ] response meta / period label unify ყველა target page-ზე
- [ ] verification:
  - day scope
  - week scope
  - month scope
  - zero-match scope
  - tab switch persistence
  - request/network propagation
  - empty-state correctness

### Packet H — მკაცრი წესები
- [ ] ჯერ read-only state verification
- [ ] backend interpreter მხოლოდ:
  - `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`
- [ ] project-local `.venv` არ გამოიყენო backend სამუშაოზე
- [ ] ფართო refactor არ გააკეთო
- [ ] unrelated code არ შეცვალო
- [ ] უკვე დადასტურებული Packet G patch არ გადააკეთო ახალი დადასტურებული პრობლემის გარეშე

## ფაზა 11: AI Business Advisor (დაგეგმილი — დაწყება 2026-04-17)

**სამუშაო დოკუმენტი (ისტორიული):** `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md` (Phase 0-2 evidence only)
**Active roadmap (Phase 3+ supersedes):** `AI_GENIUS_PARTNER_PLAN.md` v2.1 (2026-04-18)
**მიზანი:** Financial Dashboard-ში სრულფასოვანი AI Business Advisor (Claude Sonnet 4.6 + Extended Thinking + ChromaDB + Web Search)
**სამუშაო:** 5.5-6 კვირა (v2.1; original 9 კვირა გეგმა v1.0-ში)
**Monthly cost:** $40-95 (heavy usage — Sonnet 4.6 + Extended Thinking)

### Phase 0 — Foundation (დასრულებული 2026-04-17)
- [x] Step 0.1: Packet H closed (cashflow documented exception)
- [x] Step 0.2: Data Quality Audit (10/10 structural, 9.8/10 overall)
- [x] Step 0.3: Code Hygiene (deprecated archived 1.09GB, deps pinned, `.env.example`, `.gitignore` hardened)
- [x] Step 0.4: External Setup (Anthropic + Telegram live pings passed)
- [x] Step 0.5: Phase 0 Sign-off (HANDOFF split, docs finalized)

### Phase 1 — MVP Chat (დასრულებული 2026-04-17)
- [x] Backend: `dashboard_pipeline/ai/` module (`config.py`, `tools.py`, `prompts.py`, `agent.py`)
- [x] API: `POST /api/chat` (slowapi 30/min, X-API-Key protected, lazy agent singleton)
- [x] Frontend: `ChatAssistant.jsx` (floating FAB + modal) + `ChatMessage.jsx` + `useAIChat.js` + `aiClient.js`
- [x] Styles: 400 ხაზიანი chat UI CSS `components.css`-ში (desktop + mobile safe-area)
- [x] Tests: 38 backend unit tests (`test_ai_tools.py` + `test_ai_agent.py`) + 7 Playwright E2E (`ai-chat.spec.js`)
- [x] Verification: 163/163 unit + 70/70 E2E + lint + build ✓; live `/api/chat` end-to-end OK
- [x] Live cost / latency snapshot:
  - text-only greeting: 3.6s, 1665+62 tokens ≈ $0.006
  - data query (270 suppliers): ~30s, 10K+74 tokens ≈ $0.031

### Phase 1 — Polish (დასრულებული 2026-04-18)
- [x] Anthropic prompt caching: `build_system_prompt_blocks(cached=True)` + `get_cached_tool_schemas()` with ephemeral `cache_control` on last block of `system` and last tool in `tools`
- [x] Agent tracks `cache_creation_input_tokens` + `cache_read_input_tokens` and surfaces them in `usage`
- [x] `DEFAULT_ROW_LIMIT` 50 → 10; new `SECTION_COLUMN_PROFILES` for `suppliers`, `supplier_aging`, `ap_monthly_trend`, `monthly_pnl`
- [x] Tool schema gains `columns: "minimal" | "all"` (default `"minimal"`); list rows projected via `_project_row()`
- [x] Frontend `UsageBadge` renders `⚡ N cached` sub-span when API reports cache reads
- [x] Tests: +19 unit cases (182/182 green, was 163); `FakeMessages` extended with optional cache tokens
- [x] No API contract breakage: old `_apply_filter_and_limit(value, criteria, limit)` signature preserved via keyword-only `section=None, columns="minimal"` defaults
- [x] Live cache-hit measurement (2026-04-18 02:10 dog-food: investigator cache_read=5832 stable across repeated calls; chat cache_create=4808 on fresh first call — mode-namespaced cache isolation confirmed)

### Streaming SSE (დასრულებული 2026-04-18)
- [x] `AIAgent.chat_stream(message, history)` sync generator — uses `client.messages.stream(...)` with the same tool-use loop; yields `delta` / `tool_call` / `tool_result` / `sources` / `usage` / `history` / `done` / `error` events
- [x] `POST /api/chat/stream` endpoint in `server.py` — `text/event-stream`; same body contract as `/api/chat`; slowapi 30/min; X-API-Key inherited; async bridge (`_sse_stream_bridge`) runs `next()` in threadpool and closes generator on client disconnect
- [x] Frontend `postChatStream({message, history, signal, onEvent})` + `parseSseEventBlock()` in `rs-dashboard/src/lib/aiClient.js` — `fetch` + `ReadableStream` parser
- [x] `useAIChat.js` switched to streaming by default: progressive text accumulation, tool_call → `entry.toolCalls`, final `sources`/`usage`/`history` fold in
- [x] `api-mock.js` + `ai-chat.spec.js` — new `/api/chat/stream` mock (SSE body with 3 delta chunks + final events) + 1 new smoke test; existing 7 ai-chat E2E tests continue to pass unchanged
- [x] Tests: +10 unit cases in `TestChatStream` (`FakeStream`/`FakeStreamMessages`/`FakeStreamingClient` fixtures) — 192/192 unit green (was 182); 8/8 ai-chat E2E green (was 7)
- [x] Prompt caching re-used on the streaming path (`system=<blocks>` + `tools=<cached_tools>` — same helpers as `chat()`)
- [x] No breaking changes: `POST /api/chat` retained; `AIAgent.chat()` unchanged; `postChat()` still exported for tests/fallback
- [x] Live `/api/chat/stream` first-token latency measurement (2026-04-18 02:10 dog-food: 3.66-4.52s across chat + investigate modes; well under 5s MVP target on cached turns with 1 tool call)

### Phase 2 — Investigator (დასრულებული 2026-04-18)

#### Sprint 1 — Backend tools (2026-04-18 01:10)
- [x] `dashboard_pipeline/ai/tools.py` extended with 4 new tools:
  - `read_source_code(file_path, line_range?)` — allowlist `ALLOWED_CODE_ROOTS`; caps `MAX_SOURCE_LINES=500` / `DEFAULT_SOURCE_LINES=200`
  - `grep_code(pattern, path?, max_hits?)` — regex across code roots; caps `DEFAULT_GREP_HITS=50` / `MAX_GREP_HITS=200`
  - `read_excel_source(file_path, sheet?, nrows?, skiprows?)` — allowlist `Financial_Analysis/`; caps `DEFAULT_EXCEL_NROWS=20` / `MAX_EXCEL_NROWS=200`; unicode-safe
  - `validate_vs_source(section, expected_row_count?, expected_total?, field_name?)` — data.json vs expected cross-check
- [x] `_resolve_safe_path()` helper rejects traversal, absolute paths, Windows drive letters; secrets (`.env`, `secrets/`, `node_modules/`, `ai_memory.db`, `ai_vectors/`) hard-excluded
- [x] `ToolDispatcher` extended with `project_root` kwarg; routes all 5 tools; `TOOL_SCHEMAS` module constant stays cache-control-free
- [x] 66 new unit tests (`tests/test_ai_investigator.py`); suite 258/258 passing

#### Sprint 2 — Prompt variant + mode param (2026-04-18 01:40)
- [x] `dashboard_pipeline/ai/prompts.py` — `SYSTEM_PROMPT_KA_INVESTIGATOR` (Georgian discrepancy-hunter persona); `SUPPORTED_MODES = ("chat", "investigate")` + `DEFAULT_MODE = "chat"` + `_resolve_mode()` + `_SYSTEM_PROMPT_BY_MODE` registry
- [x] `build_system_prompt(extra_context="", *, mode="chat")` + `build_system_prompt_blocks(extra_context="", *, cached=True, mode="chat")` — each mode caches its own Anthropic prefix
- [x] `dashboard_pipeline/ai/agent.py` — `AIAgent.chat(..., *, mode="chat")` + `AIAgent.chat_stream(..., *, mode="chat")`; `_validate_mode()` raises `AIAgentError` on `chat()`, yields single `error` event on `chat_stream()` **without opening Anthropic stream** (token cost guard)
- [x] `server.py` — `_extract_chat_mode()` shared helper; `POST /api/chat` + `POST /api/chat/stream` accept optional `mode` body field; 400 on non-string/unknown; `usage.mode` echoed in response
- [x] 24 new unit tests (`TestPromptMode` 11 + `TestChatMode` 8 + `TestChatStreamMode` 5); suite 282/282 passing

#### Sprint 3 — Frontend toggle + Cascade block + E2E (2026-04-18 02:00)
- [x] `rs-dashboard/src/lib/aiClient.js` — `postChat` + `postChatStream` accept optional `mode` body field; omitted when falsy (backward-compat)
- [x] `rs-dashboard/src/hooks/useAIChat.js` — `send(message, options = { mode })`; server-echoed `usage.mode` authoritative; `resolvedMode` stamped on final entry
- [x] `rs-dashboard/src/components/ChatAssistant.jsx` — 🔍 Investigate toggle button + `localStorage["ai-advisor-mode"]` persistence + SSR/private-browsing-safe storage guards + tooltip; disabled during `sending`
- [x] `rs-dashboard/src/components/ChatMessage.jsx` — `extractCascadeBrief()` regex + Georgian heuristic (`ფაილი:` + `ხაზი:` + `გასწორება:`); `CascadeBriefBlock` collapsible `<pre>` + "კოპირება" button; `navigator.clipboard.writeText` + `document.execCommand('copy')` fallback; mode-gated rendering
- [x] CSS (`components.css`) — `.chat-panel__btn-mode` + `.chat-msg__cascade*` (amber theme, amber→green on copy success)
- [x] E2E — `api-mock.js` mode-branching (`buildMockReply` / `buildMockSources`); +1 smoke test asserts toggle + POST body + Cascade block + copy button + localStorage
- [x] Verification: `pytest tests/` → 282/282 backend unchanged; `npm run lint` clean; `npm run build` clean (ChatAssistant 167.59 kB / gzip 50.74 kB, +3.28/+1.07 kB over Streaming SSE); `npx playwright test e2e/ai-chat.spec.js` → 9/9 (was 8; +1 investigate smoke)
- [x] End-to-end operational: user toggles 🔍 Investigate → preference persisted → next `send()` POSTs `mode=investigate` → backend swaps to `SYSTEM_PROMPT_KA_INVESTIGATOR` → frontend renders Cascade copy-paste block

### Phase 3-5 — SUPERSEDED
Original plan: `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md` → Phase 3 (Daily Briefing) → Phase 4 (Scenarios) → Phase 5 (Full Advisor)
User rejected Daily Briefing / Telegram push / Provider migration / Voice on 2026-04-18. New Phase 3+ scope in `AI_GENIUS_PARTNER_PLAN.md` v2.1.

### Next queue (user pre-approved all 3 on 2026-04-17 23:39)
- [x] Option 1 — Phase 1 Polish (done 2026-04-18)
- [x] Option 3 — Streaming SSE (done 2026-04-18; picked before Option 2 for smaller scope + cached-prefix synergy)
- [x] Option 2 — Phase 2 Investigator (done 2026-04-18; Sprint 1 + 2 + 3 complete)
- [x] Live dog-food of `mode="investigate"` on real Anthropic API (done 2026-04-18 02:10; 3 calls verified Sprint 1/2/3 invariants end-to-end; see HANDOFF.md Phase 2 Live Dog-Food section)
- [x] UI dog-food of `mode="investigate"` on real Playwright browser + production preview (done 2026-04-18 02:40; toggle + POST body + UsageBadge `⚡ 5832 cached` + Cascade gating all verified live; see HANDOFF.md Phase 2 UI Dog-Food section)
- [x] 🆕 Waybill Arithmetic Bug-Fix (done 2026-04-18 04:00; pipeline + `compute_waybill_total` tool + prompt semantics + 26 regression tests + data.json regen; 308/308 green; ground truth Feb 27 = 7,882.68, Feb 28 = 2,675.86 verified; backend restart PENDING; see HANDOFF.md Waybill Arithmetic Bug-Fix section)
- [ ] Backend restart + live Waybill-fix verification prompts (Priority 0)
- [ ] Strategy-AI capability probe (user-priority) — test current AI's ability to generate actionable strategy from existing data.json sections before committing to any new infra

### Phase 2 Live Dog-Food — COMPLETE (2026-04-18 02:10)
- 3 real `POST /api/chat/stream` calls against Anthropic Claude Sonnet 4.6 (parent venv backend, port 8000):
  - Call 1 / investigate / warm: 4.52s total, 15087 in + 5832 cache_read + 109 out
  - Call 2 / investigate / repeat: 3.98s total, identical cache (stable hit)
  - Call 3 / chat / fresh: 3.67s total, 15087 in + 4808 cache_create + 109 out
- All 3 produced identical Georgian source-attributed reply `**270** (წყარო: data.json → suppliers)` with `stop_reason=end_turn` and single `read_data_json(columns="minimal")` tool call
- Invariants verified: Sprint 2 `usage.mode` echo ✅ | Phase 1 Polish mode-namespaced cache ✅ | column pruning ✅ | first-token <5s ✅ | Georgian source attribution ✅
- Caveat surfaced (NOT regression): `MAX_TOOL_ITERATIONS=6` (Phase 1 MVP) tight for investigator discrepancy hunts (12 tool calls on aggressive question → polite fallback); optional future polish: mode-dependent cap (6 chat / 10 investigate)

### Phase 2 UI Dog-Food — COMPLETE (2026-04-18 02:40)
- Real Playwright browser run on production preview (Vite preview port 4173) + parent-venv backend (PID 31328, port 8000) — no code changes, docs-only chat
- Browser flow: navigate `#suppliers` → click chat FAB → click 🔍 Investigate toggle → click sample prompt "რამდენი მომწოდებელი გვყავს ჯამში?" → wait for `(წყარო: data.json` text → inspect DOM + network
- Verified live in real UI:
  - Toggle: `aria-pressed=true` + `data-mode=investigate` + `localStorage["ai-advisor-mode"]=investigate` ✅
  - POST body to `/api/chat/stream`: `{"mode":"investigate"}` ✅
  - Assistant bubble root `<div data-mode="investigate">` (server-echoed `usage.mode`) ✅
  - Investigator prompt signature `"🔍 შედეგი"` in response + Georgian source attribution `"(წყარო: data.json → suppliers)"` ✅
  - UsageBadge: `"29891in / 564out tok · ⚡ 5832 cached"` — `⚡ cached` sub-span rendered (Phase 1 Polish cache indicator live) ✅
  - 2 sources in sources list (data.json + Excel triangulation) ✅
  - Cascade block correctly suppressed (no discrepancy found — gating contract respected) ✅
- Cost this call: ~$0.082 (investigator triangulated with `read_excel_source` in addition to `read_data_json` — 2 tool calls vs Live Dog-Food's 1)
- Cleanup: browser closed, preview server stopped, backend left alive (not launched by this session), zero repo artifacts

## Active: AI Genius Financial Partner v2.1 (2026-04-18 საღამოს)

→ Authoritative plan: **`AI_GENIUS_PARTNER_PLAN.md` v2.1**
→ Supersedes `AI_ADVISOR_ROADMAP.md` Phase 3+ (user rejected push/daily briefing/Telegram/provider migration/voice)
→ Supersedes `AI_GENIUS_PARTNER_PLAN.md` v2.0 (expanded with Phase 0A Critical Foundation + 4 new Phase 1-2 features + Parking Lot)

**სტატუსი**: **🏁🏁 Phase 4A FULLY CLOSED + Backend Perma-Up via Windows Service (2026-04-21 04:15)** — ამ სესიის ორი milestone: **(A) Phase 4A FULLY CLOSED (04:02)** Part A + Part B end-to-end live verified; **(B) Windows Service installed (04:15)** — `FinancialDashboardBackend` (NSSM 2.24 wrapper at `C:\tools\nssm\nssm.exe`) auto-starts on boot, auto-restarts 2s after crash, env `AI_ENABLE_THINKING=true`+`PYTHONUTF8=1` persisted, logs rotate 10MB/24h in `logs/backend_*.log`. Verified `Status=Running, StartType=Automatic` + PID 24364 LISTEN 8000 + `/api/status` 200 + `/api/chat` `usage.thinking=True`. **Backend-restart-#N counter retired.** Control: services.msc "Financial Dashboard Backend" OR `Restart-Service FinancialDashboardBackend` OR `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit} FinancialDashboardBackend`.

**წინა-სტატუსი**: **🏁 Phase 4A Debt Repayment Plan — FULLY CLOSED (2026-04-21 04:02)** — Part A + Part B ორივე end-to-end ცოცხლად ვერიფიცირებული. Backend restart #17 PID **5388**, `TOOL_SCHEMAS=18`, pytest **1443/1443 green**. ამ სესიაში ყველა mid-session pending item დასრულდა: (1) **Scripted `/api/chat/stream` dog-food** *"შემიდგინე ვალების გეგმა"* with `think=True` → AI autonomously invoked `build_debt_repayment_plan` (49.7s), `usage.thinking=true` ✅, `stop_reason=end_turn` ✅, 91.2s elapsed; Georgian 5-section brief (ჯიდიაი #1 313,922 ₾, 2-თვიანი arithmetically unsustainable 246K > 140K forecast, 4-6 თვე recommended horizon). (2) **UI regenerate click-through** (Vite 5173 + Playwright MCP): `#debt_plan` auto-mount → 2→6 თვე duration → `🔄 ახალი გეგმა` → 246K/თვე → 85.7K/თვე priority total, buffer −139.2% → −25.0%. (3) **UI approve click-through**: `✅ ვეთანხმები — შენახვა` → `POST /api/debt-plan/save` 200 OK → journal entry `journal_816295fd222b495199c30599510d8d7f` title *"ვალების გეგმა — 5 priority @ GEL 85,700/თვე (6-თვიანი)"* status `🟡 open` — cross-verified via `/api/chat` → `journal_list_entries`. (4) **`PHASE_4A_DEBT_PLAN_PREVIEW.md`** — Part B LIVE VERIFIED section + closure banner added. **🐞 3rd bug-fix en-route**: `rs-dashboard/src/App.jsx:307` — `showGlobalLoading` exclusion list lacked `debt_plan`; `loading` state default `true` never flipped (main `/api/data` useEffect early-returns for debt_plan) → UI stuck on "იტვირთება მონაცემები..." forever; 1-line fix adds `&& activeTab !== 'debt_plan'` guard matching the existing 3-tab pattern. This is the most likely root cause of last session's "UI approve/save + regenerate crash interrupted" note; both actions now fully verified working. Phase 4A ოფიციალურად დახურულია; შემდეგი recommended: Phase 4B / Phase 5 kickoff per v2.1 roadmap, ან parking-lot polish.

**წინა-სტატუსი**: **🎉 Phase 2.11 + 2.12 FULLY LIVE VERIFIED (2026-04-20 15:30)** — Backend restart #10 + 3 scripted `/api/chat/stream` dog-foods all PASS on real Anthropic Sonnet 4.6. PID 29332 with `AI_ENABLE_THINKING=true`. **Phase 2.12 Focused** (ჯიდიაი) 9/9 PASS, 49.8s, Leverage 🟢 71/100, 3 plays. **Phase 2.12 Portfolio** 10/10 PASS, 49.1s, HHI 551, Top-10 ranked, "დაიწყე ჯიდიაი-დან" steering, `usage.thinking=true` ✅. **Phase 2.11 Dead Stock** 9/9 PASS, 65.9s, ~1.49M ₾ frozen-cash, 3-action salvage plan, 30.3% unmatched warning live, `usage.thinking=true` ✅. Session cost ~$0.48. Cross-link: AI paired SKU `პარლამენტი აქვა ბლუ 87,850 ₾ → ჯიდიაი` (Phase 2.11) with the #1 leverage supplier from Phase 2.12 portfolio — end-to-end strategic composition works. AI-მ ისწავლა საკუთარი თავის გასწორება (Part D). `SYSTEM_PROMPT_KA`-ში ახალი `🔄 საკუთარი თავის გასწორების ციკლი` სექცია (🔁 Retry Protocol 4 ნაბიჯი + 🎯 Self-Triage 3 hypothesis + 📢 Latin Alias MANDATORY 3-row anti-pattern table + 📅 თარიღის 3 ფორმატი + ❌ "ვერ ვიპოვე" 3+ ცდის prerequisite). 55 new tests in `test_ai_prompts_phase1d.py`. Investigator prompt untouched (15-marker leak guard + 6 do-not-touch tests). pytest **969/969 green** (was 914; +55 new; 0 weakened). **LIVE** ცოცხალი dog-food 5/5 PASS — იგივე BOG 2026-02 კითხვა (რომელმაც 02:30-ზე false-negative დააფიქსირა) → AI-მ 17 tool call გააკეთო (4× recall_context Latin alias progression-ით + 6× read_data_json + 3× read_excel_source + 2× grep_code + read_source_code + executive_summary), 02--2026.xlsx surface-ი მოიპოვა, structured "ვცადე: (1)... (2)... (3)..." fallback გასცა და user-ს დააზუსტებინა. NEW caveat: `read_excel_source` ქართულ ფოლდერ-სახელებს ვერ ხსნის (separate carry-forward, NOT Part D regression).

**Previous**: **Phase 1 Part C COMPLETE + LIVE VERIFIED (2026-04-20 02:11)** — AI-ს ცოცხლად დაემატა Multi-Store DNA layer. `SYSTEM_PROMPT_KA`-ში ახალი `🏪 მაღაზიების DNA` სექცია (🏪 ოზურგეთი Urban Flagship 10-ველიანი DNA + 🏡 დვაბზუ Rural Local 10-ველიანი DNA + 🌅 soft seasonality hint + 🎯 DNA გამოყენების guidance ცხრილი 7 dimension-ით + 📋 4 store-level baseline facts auto-journal placeholder + ⚠️ over-apply guardrails). 54 new tests in `test_ai_prompts_phase1c.py`. Investigator prompt untouched (6 do-not-touch tests). pytest **914/914 green** (was 860; +54 new; 0 weakened). **LIVE** ცოცხალი dog-food (1 strategic in-process `AIAgent.chat(think=True)` call, თამბაქოს 10-15% ფასდაკლება cross-store question) — AI-მ ცოცხლად გამოიყენა: (a) ცხადი ოზურგეთი YES vs დვაბზუ NO differentiation; (b) elasticity reasoning (ტურისტი + loyal habit); (c) 🟢 საიმედო + 🟡 ვარაუდი confidence labels; (d) DNA-based hypothesis (peak / mix / POS რეჟიმი); (e) `stop_reason=end_turn`; 15 sources + 6+ tool calls under 12-iteration cap. ~2 წთ, 178,889 in + 5,607 out + 166,817 cache_read; ≈$0.14.

**Earlier**: **Phase 1 Part B COMPLETE + LIVE VERIFIED (2026-04-20 01:28)** — AI-ს ცოცხლად დაემატა ქართული რეგულაციისა და ფრენჩაიზი-კონტექსტის შრე. `SYSTEM_PROMPT_KA`-ში ახალი `🇬🇪 ქართული რეგულაცია` სექცია (💰 VAT/საპენსიო/1%-მცირე ბიზნესი/CB+1% საურავი + 🧾 RS.ge ე-ინვოისი 30-day + 🏪 Franchise 4-7% royalty / 60-75% sourcing / $5-20K opening fee / Brand standards + 📋 4 baseline facts auto-journal placeholder + 🌅 ქართული თვის რიტმი 4 bucket). 42 new tests in `test_ai_prompts_phase1b.py`. Investigator prompt untouched (4 do-not-touch tests). pytest **860/860 green** (was 818; +42 new; 0 weakened). **LIVE** ცოცხალი dog-food (1 strategic `/api/chat` call, think=True, ოზურგეთი POS 20K ₾ capex timing question) — AI-მ ცოცხლად გამოიყენა: (a) `recall_context("VAT სტატუსი ... მცირე ბიზნესი cash planning")` baseline tax facts-ის საძებნელად; (b) 5-ის ნაცვლად 4/5 ქუდი (💼/⚠️/🎯/🪞, 🔧 skip — capex timing-ს არ ესაჭიროება); (c) multi-hypothesis 40/35/25; (d) 🟢 საიმედო + 🟡 ვარაუდი; (e) Monthly rhythm rule — ცხადად შესთავაზა "2026-05-16 — 2026-06-01 მე-2 ტერმინალი **15-ის deadline-ის შემდეგ**" (Part B-ს ცოცხალი გამოყენება); (f) VAT + საპენსიო 15 მაისი deadline mention; (g) auto-journal `recommendation` entry დაემატა (post-run cancelled for clean data). 111.72s, 10 tool calls, ~$0.19 (108K cache_read; 30K in + 4.5K out), `stop_reason=end_turn`.

**Earlier+1**: Phase 1 Part A COMPLETE + LIVE VERIFIED (2026-04-20 00:55) — AI-ის ხასიათი + საზრისობა Layer 1 ცოცხალად დამოწმდა. 5 ქუდი + სტრატეგიული პარტნიორის პერსონა + პროექტის რუკა + წყაროების იერარქია + Data-ზე სკეპტიციზმი + Confidence ნიშნები (✅/🟢/🟡/🟠/⚪) + 📌 ვარაუდი vs ფაქტი anti-hallucination v2 + მკაცრი ტონი. `MAX_TOOL_ITERATIONS_DEEP` 10 → 12. `<TODAY>` block-ი გამდიდრდა weekday hint-ით + VAT/საპენსიო regulatory deadlines-ით (15-ე, 10-დღიანი severity ფანჯარა). LIVE dog-food (2-store comparison, think=True) — 5 ქუდი + 3-version multi-hypothesis + 🟢 საიმედო + strict tone + auto-journal. 151.6s, 26 tool calls, ~$0.12 (175K cache_read).

**Backend live**: **Windows Service `FinancialDashboardBackend`** (NSSM-wrapped parent-venv) running PID **24364**, `AI_ENABLE_THINKING=true`+`PYTHONUTF8=1` persisted via `AppEnvironmentExtra`, `MAX_TOOL_ITERATIONS_DEEP=12`, `DEFAULT_TIMEOUT_S=120`, **18 tools live** (Phase 3.1 `propose_feature` + Phase 3.7 `compute_cash_runway` + Phase 4A `build_debt_repayment_plan` added), 18,263 indexed Excel chunks. Phase 1 Part A + Part B + Part C + Part D + Phase 2.11 + Phase 2.12 + Phase 3.1 + Phase 3.5/3.7 + Phase 4A Part A + Part B **FULLY CLOSED** all LIVE. Verified via `Get-Service FinancialDashboardBackend` (Status=Running, StartType=Automatic) + `/api/status` 200 OK + scripted `/api/chat` returned `usage.thinking=True` ✅. 🏁 **Recurring pain resolved**: backend never dies between sessions. Auto-start on Windows boot + auto-restart 2s after crash + logs in `logs/backend_{stdout,stderr}.log` (rotate 10MB/24h). Control via services.msc / `Restart-Service FinancialDashboardBackend` / `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit} FinancialDashboardBackend`.
**Timeline**: 5.5-6 კვირა (Phase 0A → Phase 0B Sprint 1 → Sprint 2 Prophet → Sprint 3 ChromaDB → Sprint 4 integration → Phase 1/2)
**Cost**: $40-95/თვე (heavy usage — Sonnet 4.6 + Extended Thinking + ChromaDB + Web Search); Sprint 3 adds $0 (ChromaDB + sentence-transformers run locally)

**v2.1 დამატებები (2026-04-18 საღამოს)**:
- Phase 0A — Critical Foundation: 3 ფუნდამენტური ცვლილება **COMPLETE** (Calculator Enforcement + Self-Critique Loop + Today's Pulse) — 73 new tests, 381/381 green
- Phase 1 Part A — AI "ხასიათი" + "საზრისობა" **COMPLETE + LIVE** (2026-04-20 00:55)
- Phase 1 Part B — ქართული რეგულაცია + ფრენჩაიზი კონტექსტი **COMPLETE + LIVE** (2026-04-20 01:28)
- Phase 1 Part C — Multi-Store DNA (1.12, ოზურგეთი urban vs დვაბზუ rural) **COMPLETE + LIVE** (2026-04-20 02:11)
- Phase 1 Part D — Self-Correction Loop (retry / Latin alias MANDATE / self-triage) **COMPLETE + LIVE** (2026-04-20 02:50)
- Phase 2.11: Dead Stock Liquidation — **COMPLETE + LIVE VERIFIED** (2026-04-20 15:30) — real Anthropic Sonnet 4.6 dog-food (65.9s, 9/9 PASS, `usage.thinking=true`): `analyze_dead_stock(days_threshold=180, top_n=30, store="total")` + 3 `compute` aggregations → 3964-char Georgian brief with 30.3% unmatched warning live, 3-bucket breakdown (181–365d 452K ₾ / 365d+ 1,040K ₾ / unmatched), 3-action salvage plan, Top-10 products; ~1.49M ₾ frozen-cash estimate; ~$0.11
- Phase 2.12: Supplier Negotiation Prep — **COMPLETE + LIVE VERIFIED** (2026-04-20 15:30) — `prepare_supplier_brief` tool + 📞 prompt section + 130 new tests (76 module + 54 prompt-guard); pytest **1163/1163 green**. Real Anthropic dog-food 2 scenarios PASS: **Focused (ჯიდიაი)** 9/9 PASS, 49.8s, tax_id 406181616 auto-resolved, Leverage 🟢 HIGH 71/100, 3 plays ranked, ~$0.10. **Portfolio** 10/10 PASS including `usage.thinking=true`, 49.1s, 270 suppliers / HHI 551 / Top-5 41.9% / steering "დაიწყე ჯიდიაი-დან", ~$0.27
- Phase 3.1: Co-Designer Mode (PULL-ONLY feature proposals) — **COMPLETE + LIVE VERIFIED** (2026-04-20 17:50) — `JOURNAL_KINDS` +`proposal` + 6 metadata keys + `cleanup_stale_proposals(30d)`; `TOOL_SCHEMAS` 15→**16** with new `propose_feature(title, problem, benefit, mvp_scope, data_needed, time_estimate, risk_critique)`; `SYSTEM_PROMPT_KA` � Co-Designer section (PULL-ONLY + 6 trigger phrases + anti-trigger list + 🪞 critic mandate + 3-proposal cap); investigator prompt UNTOUCHED (0/6 markers). pytest **1242/1242 green** (was 1163; +79 net: 78 new in `test_ai_co_designer.py` + 1 renamed; 0 weakened). Live dog-food 3/3 PASS on Backend #11 PID 29400: (A) TRIGGER `"რას შემომთავაზებდი?"` 146.1s → 3 structured proposals (ხარჯების Split Widget / Dead Stock Salvage Tracker / Cash Runway Widget); (B) ANTI-TRIGGER strategic `"რატომ margin −80%?"` 75.4s → 0 `propose_feature` calls; (C) ANTI-TRIGGER data `"რამდენი მომწოდებელი?"` 9.5s → 0 `propose_feature` calls. All `stop_reason=end_turn` + `usage.thinking=true` ✅. 3 test proposals cancelled post-verification (journal clean).
- **�� Backend restart #10** — **DONE** (2026-04-20 15:25) — parent-venv PID **29332** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'`; verified 15/15 📞 markers chat + 0/15 investigator + `TOOL_SCHEMAS=15` + live `usage.thinking=true` on 2 subsequent dog-foods. **New do-not-touch rule**: after any backend restart, verify env propagation via real `usage.thinking=true` SSE call, not just `Win32_Process.CommandLine` — intermediate PID 27700 had parent-venv CommandLine but missing `AI_ENABLE_THINKING` env (silent degrade).
- **🆕 Backend restart #11** — **DONE** (2026-04-20 17:35) — old PID 29332 stopped; fresh parent-venv PID **29400** via same pattern; verified 6/6 🎨 Phase 3.1 markers chat + 0/6 investigator + `TOOL_SCHEMAS=16` + `propose_feature` at index 15 + live `usage.thinking=true` on all 3 subsequent dog-foods.
- Phase 3.5 + 3.7 + Cash Runway — Dashboard Widgets + AI Tool — **COMPLETE + LIVE VERIFIED** (2026-04-20 23:50) — 3 ახალი ნაწილი: `💀 Dead Stock` გვერდი (analytical tab-group, donut + Top-30 + 4-action salvage + 30%+ unmatched warning) + `⚠️ Supplier Concentration` widget (embedded top of `🏢 მომწოდებლები` tab — HHI gauge + Top-5/10/20 bars + Top-3 leverage-ranked candidates + `#1 priority` steering) + `compute_cash_runway` AI tool (PULL-ONLY user-balance-required workflow + burn rate + runway label 🟢/🟡/🔴 + burn_trend honesty). Pipeline `_build_analytics()` gained `build_dead_stock_summary` + `build_supplier_concentration`; `api_contracts.py` got 2 new static tabs + `_build_suppliers_response` passthrough; `TOOL_SCHEMAS` **16 → 17** with `compute_cash_runway` at index 11; `SYSTEM_PROMPT_KA` gained 💰 Cash Runway section with trigger/anti-trigger/3-step mandatory workflow/honesty rule/guardrail. pytest **1303/1303 green** (was 1242; +61 new `test_ai_cash_runway.py`; 6 existing pins bumped 16→17). Live `/api/data?tab=dead_stock` available=True / frozen 1.49M ₾ / Top-30 SKUs ✅; `/api/data?tab=supplier_concentration` available=True / 270 suppliers / HHI 551 / Top-5 41.9% ✅; live `/api/chat/stream` dog-food 6/6 PASS (57.1s, `usage.thinking=true`, user provided BOG 52K + TBC 28K → `compute_cash_runway` called → **3.2-თვე runway / 25,054 ₾/თვე burn stable / multi-hypothesis / Multi-Store DNA / 🪞 critic self-critique**).
- **🆕 Backend restart #12** — **DONE** (2026-04-20 23:35) — old PIDs 13960 + 29400 stopped; fresh parent-venv PID **20876** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'`; verified 9/9 💰 Cash Runway markers chat + 0/9 investigator + `TOOL_SCHEMAS=17` + `compute_cash_runway` at index 11 + live `usage.thinking=true` on post-restart dog-food.
- Phase 4A Part A — Debt Repayment Plan (AUTONOMOUS STRATEGIST) — **COMPLETE + LIVE VERIFIED** (2026-04-21 00:50) — **Phase 4 ფილოსოფიის ძვრა** user-ის ცხადი critique-ს საპასუხოდ (dashboard AI → Cascade-ივით თავისუფალი / აზრების მომცემი, არა Q&A bot). ახალი `dashboard_pipeline/ai/debt_plan.py` module (~600 lines) — `build_debt_repayment_plan` tool კომპონებს 1-2-თვიან ვალის შემცირების გეგმას data-only-დან: 4-ფაქტორიანი criticality score (ვალი 30 + ასაკი 25 + სიხშირე 25 + dysfunction 20), 3-თვიანი moving-average inflow forecast ±10%, per-supplier recommended monthly/weekly + days-to-clear, non-priority baseline (historical × 90%), allocation summary + sustainable bool, risks + 🪞 critic. `TOOL_SCHEMAS` 17 → **18** (build_debt_repayment_plan at index 12; propose_feature shifts 16→17). `SYSTEM_PROMPT_KA` gained 📋 ვალების გეგმა section — "AUTONOMOUS STRATEGIST" / BROAD triggers / IMMEDIATELY call / 5-part response format / critic mandate / anti-triggers / cross-tool chains. Investigator UNTOUCHED (0/7 markers). pytest **1393/1393 green** (was 1303; +90 new `test_ai_debt_plan.py` + 7 pin bumps 17→18; 0 weakened). Live `/api/chat/stream` dog-food **12/12 smoke PASS** on backend #13 PID 10800 across 3 scenarios: (A) BROAD *"მინდა ვალების გეგმა"* → tool called with empty priority_suppliers, auto-detected; (B) NAMED *"ვასაძე + კოკაკოლა 2 თვეში"* → FIRST tool call = `build_debt_repayment_plan(priority_suppliers=..., plan_duration_months=2)`, then 13 verifying tools, **detected user vs data.json discrepancy and surfaced honestly**; (C) ANTI-TRIGGER *"ჯიდიაი leverage"* → correctly routed to `prepare_supplier_brief`. All `usage.thinking=true` + `stop_reason=end_turn`. Part B deferred (React page + dedicated /api/debt-plan + journal kind + daily tracker) — Part A already usable via chat.
- **🆕 Backend restart #13** — **DONE** (2026-04-21 00:35) — fresh parent-venv PID **10800** via standard pattern; verified `TOOL_SCHEMAS=18` + new 📋 ვალების გეგმა prompt section + 3/3 live dog-foods all `usage.thinking=true`. Confirms Phase 4 philosophy shift lands cleanly on top of existing Phases 0A-3.5.
- Phase 4A Part B — React page + journal mirror sync + endpoint tests — **CODE COMPLETE** (2026-04-21 01:55) — backend, tests, frontend wired: (1) `server.py` — `from typing import Any` import fix (helper signatures საჭიროებდა); POST `/api/debt-plan` + POST `/api/debt-plan/save` endpoints route-introspection-ით ვერიფიცირდა. (2) `dashboard_pipeline/ai/tools.py::JOURNAL_KINDS` mirror-tuple synced with `journal.py` 5→6 (`repayment_plan` დამატებული). (3) **NEW 39 cases** `tests/test_api_debt_plan.py` — helper coercion (`_coerce_optional_int` 8 + `_coerce_priority_list` 9) + `TestClient`-based endpoint tests (9 happy/validation paths per endpoint) + 2 route-registration guards + 2 JOURNAL_KINDS guards. (4) `tests/test_ai_journal.py::TestJournalConstants::test_kinds_tuple` — 5→6 tuple update. (5) `rs-dashboard/src/tabConfig.js` — `debt_plan` tab added to `ანალიტიკური` group label `📋 ვალების გეგმა`. (6) `rs-dashboard/src/DebtPlan.jsx` **NEW ~600 lines** — auto-generate on mount via POST `/api/debt-plan`; 3-card strip (ForecastCard burn-trend / AllocationCard sustainable bool / NonPriorityCard baseline); PriorityTable with expandable rows (criticality reasons + rationale_ka); RisksBox; duration/priority dropdowns; Approve → `/api/debt-plan/save`; 🔄 Retry; inline-styled dark theme matching DeadStock pattern. (7) `rs-dashboard/src/App.jsx` — lazy-imported `DebtPlan`, excluded `debt_plan` from generic `/api/data` fetch. pytest **1433/1433 green** (was 1393 → +40; 0 weakened); eslint 0 warnings; `npm run build` clean (`DebtPlan-BEEdSF67.js 16.26 kB / 4.43 kB gzip`); Backend restart #14 PID 21408 + `/api/status` 200 OK.
- Phase 4A Part B — LIVE VERIFIED + **2 BUG-FIX** — **COMPLETE** (2026-04-21 02:35) — (1) **Schema bug**: `debt_plan.py::_active_debt_suppliers` expected `supplier_aging` as `{"suppliers": [...]}` dict; production `data.json` is a **list** directly (193 rows). First POST smoke returned `{"error": "ვალი არ აქვთ"}` 285B. Fix: `_active_debt_suppliers` gained list+dict tolerance + 4 new regression tests `TestSupplierAgingListSchema`. (2) **Ranking bug**: Top-5 priority ranked 1,434-დღიანი zombies (Bau-Tech 435 ₾ #1) while real 313K ₾ active debtor (ჯიდიაი) sat at #30. Formula dominant weight was "ასაკი". Fix: (a) `ACTIVE_CUTOFF_DAYS=365` — dormant suppliers auto-quarantined from priority pool (user-named priorities exempt); (b) weight rebalance: debt **0.30→0.50**, aging 0.25→0.15, freq 0.25→0.20, dysfunc 0.20→0.15 — **ჯიდიაი #1 score 0.585** (was #30 score 0.412). 6 new regression tests `TestDormantSupplierQuarantine`. pytest **1443/1443 green** (was 1433; +10). Live POST smoke: 2-თვე unsustainable (246K/თვე > 140K inflow — realistic); 6-თვე უკეთესი (priority 85,700 ₾ = 61% forecast) but baseline exceeds — business cash deficit ~35K ₾/თვე cleanly surfaced. **UI click-through** via Playwright navigate `#debt_plan` → 3 cards + risks + 5 priority rows + approve/regen buttons render; row expansion click → "💡 რატომ კრიტიკული" + analysis visible. **Backend crashed mid-session** (unknown cause); **Backend restart #16 PID 18960** restored. **⚠️ Pending**: approve/save + regenerate button clicks UI-test; `/api/debt-plan/save` journal smoke; `/api/chat/stream` dog-food ("შემიდგინე ვალების გეგმა" → AI calls `build_debt_repayment_plan`).
- **🆕 Backend restart #14** — **DONE** (2026-04-21 01:55) — post Part-B-code PID **21408** via standard pattern; `/api/status` 200 OK.
- **🆕 Backend restart #16** — **DONE** (2026-04-21 02:30-ის შემდგომ) — after mid-session crash, parent-venv PID **18960** via standard pattern; restored live service for Part B UI click-through completion.
- 🏁 **Phase 4A — FULLY CLOSED** — **DONE** (2026-04-21 04:02) — all 3 pending mid-session items completed + 3rd bug-fix in `rs-dashboard/src/App.jsx:307` (`showGlobalLoading` missed `debt_plan` exclusion, blocking UI render); `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B LIVE VERIFIED banner added; Windows Service setup queued as next planned improvement to eliminate recurring backend-death-between-sessions friction.
- **🆕 Backend restart #17** — **DONE** (2026-04-21 03:43) — after PID 18960 crashed between sessions, fresh parent-venv PID **5388** via standard pattern; `/api/status` 200 OK + `TOOL_SCHEMAS=18` + scripted `/api/chat/stream` `usage.thinking=true` ✅ (env propagation double-checked — not just CommandLine match).
- 🏁 **Phase 4B — AI Personality Tuning FULLY CLOSED** — **DONE + LIVE VERIFIED** (2026-04-22 05:13) — all 3 sprints shipped in one session: **4B.0 Prune** (`SYSTEM_PROMPT_KA` 1,290→1,100 lines, Anthropic ≤1,100 target hit, commit `7ef3451`), **4B.1 Tier 1 Fundamental** (9 rules + 68 tests, commit `334220b`), **4B.2 Tier 2+3 Personality+Format** (15 rules + 79 tests, commit `27c6f71`), **4B.3 Tier 4 Workflow Anti-patterns** (4 rules across AGENTS.md + prompts.py + new `.claude/commands/restart-session.md` + 24 tests, commit `a6f9ef4`). Total **28 new rules, 171 new tests, pytest 1,614/1,614 green** (was 1,443). Live dog-food 3 scenarios PASS on real Anthropic Sonnet 4.6 `think=true` (~$0.18): Rule 1 Attempt-first (ambiguous "რა margin იყო დეკემბერში?" → AI defaulted to 2025 + single clarify), Rule 3 Premise correction ("50% margin ოზურგეთში" → AI pushed back with real data −72K/−59K net, 3-version multi-hypothesis), Rule 2 Max-1-question honored throughout. Anti-markers swept clean — 0 "ვცდი და მოვახსენებ" / 0 "ჩემს მეხსიერებაში" / 0 "მშვენიერი კითხვაა". Sprint 4C partial: **4C.2** shipped `summary_ka` to 4 headline tools (compute / compute_waybill_total / forecast_revenue / analyze_dead_stock, commit `3893a67`, +20 tests → pytest **1,634/1,634**). Phase 4C remaining: 4C.1 Schema Poka-yoke audit (18 tools, high-risk) + 4C.3 Full-stack live dog-food (budget ~$0.25).
- 📋 **Phase 4C.1 + 4C.3 — Tool Design Review + Full-stack dog-food** — **PLANNED**, full scope documented in `PHASE_4B_PROMPT_TUNING_PREVIEW.md`.
- 🆕 **data.json regenerated** — **DONE** (2026-04-22 05:10) — previous file was corrupt (JSONDecodeError line 1,950,510, truncated mid-write at 76MB). Fresh pipeline run: 133 MB, 26 sections, 21,233 waybills, ~14 min runtime. **⚠️ Caveat**: pinned ground-truth `2026-02-27 = 7,882.68 ₾` (waybill `transport_start_date`) is **stale** post-regen — new data.json shows 0 under that field; `date` field shows 17 valid rows / 7,004.06 ₾. If regression tests pin 7,882.68 they need updating or pipeline date-field semantics changed between 04-18 and 04-22.
- 📋 **Phase 4B + 4C — AI Personality & Tool Design Tuning** — ~~**PLANNED**~~ **SUPERSEDED by above** — full Preview: `PHASE_4B_PROMPT_TUNING_PREVIEW.md`. **31 წესი** 5 tier-ად (9 fundamental + 7 personality/agentic + 9 format/anti-sycophancy + 4 workflow anti-patterns + **2 tool design**), **5 sprints ~5.5-6 days / ~$0.95 AI cost**. **Source hierarchy** (4 tier): (1) **Anthropic official docs** — `docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices` + `code.claude.com/docs/en/best-practices`; (2) **Anthropic "Building Effective Agents"** (Dec 2024 foundational blog, `anthropic.com/engineering/building-effective-agents`) — 5 workflow patterns (prompt-chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer) + Appendix 2 "Prompt Engineering Your Tools" (Poka-yoke + think-out-loud); (3) **Leaked system prompts** — Claude Sonnet 4.5 (2025-11-19 `jujumilk3/leaked-system-prompts`) + Claude Opus 4.6 (`asgeirtj/system_prompts_leaks`) + Simon Willison's Claude 4 analysis (simonwillison.net, May 2025); (4) **🆕 GPT-5 leaked prompt** (Aug 2025 `asgeirtj/system_prompts_leaks/OpenAI`) — 3 orig. concepts absent in Claude: Oververbosity 1-10 scale (default 3), "Partial completion > clarification" ban, "No future promises" ban. **🚨 CRITICAL finding**: `SYSTEM_PROMPT_KA` = **1,291 lines** currently — Anthropic explicitly warns "over-specified CLAUDE.md gets half-ignored because important rules get lost in the noise" (verbatim from `code.claude.com/docs/en/best-practices` failure-patterns section) → **Sprint 4B.0 (Ruthlessly Prune, 1,291 → ~900 lines) is prerequisite** before adding any new rules, otherwise new rules land "on dead air". Sprints: **4B.0 Prune (2-3h)** consolidate duplicates + trim verbose sections (5 ქუდი 150→80 / 📌 ვარაუდი 70→40 / STOP-CHECK 130→70) → **4B.1 Tier 1 Fundamental (1d)** attempt-first-clarify-second / max-1-question-per-turn / false-premise-detection / user-can-be-wrong / `<use_parallel_tool_calls>` XML (Anthropic's verbatim wording ~100% parallel success) / `<investigate_before_answering>` XML (anti-hallucination) / commit-to-approach (anti-180°-pivot) → **4B.2 Tier 2+3 Personality+Format (1d)** seamless-memory forbidden-phrases (bans "ვხედავ / ვიპოვე / ჩემს მეხსიერებაში") / overfamiliarity-warning (ChromaDB 18K chunks) / push-back+kindness balance / avoid-over-engineering / state-scope-explicitly / persistence-directive / minimum-formatting matrix / Georgian 8-word anti-sycophancy list (მშვენიერი/შესანიშნავი/საინტერესო/ფუნდამენტური/გულწრფელად/პირდაპირ/ცხადია/მარტივად) / asterisk-actions ban / emoji-calibration (functional only) / tool-scaling-ladder (0 / 2-4 / 5-9 / 10+) / financial-override documented (justifies Phase 1 Part A deliberate override of Anthropic's default "not a financial advisor" disclaimer) / file-might-not-exist / metaphor-usage → **4B.3 Tier 4 Workflow Anti-Patterns (0.5d)** kitchen-sink-session / general-purpose-solution / 2×-correction-restart (new `/restart-session` workflow + AGENTS.md "Prompt Hygiene" + "Session Boundaries" sections). **Success criteria**: ≤1,100 lines final, 20+/25 rules grep-verifiable, pytest 1443+ green, 5/5 live dog-food scenarios PASS. **Awaits user approval to start Sprint 4B.0**.
- Parking Lot — ~40 feature მომავალი იტერაციებისთვის

**Phase 0B Sprint 1 — COMPLETE ✅ (2026-04-19)**:
- [x] Backend restart: PID 30788 live on 127.0.0.1:8000 with `AI_ENABLE_THINKING=true`
- [x] Waybill live verify: Feb 27 = 7,882.68 ₾ + Feb 28 = 2,675.86 ₾ via `compute_waybill_total`
- [x] Phase 0A live verify: generic `compute` + `<TODAY>` block + Self-Critique 📊 / ⚠️ / 🎯 structure all live
- [x] STOP-CHECK clarify + Contradictory correction + Multi-hypothesis strategic output all live-verified
- [x] Extended Thinking config/agent/server/frontend wiring + 🧠 Deep Think toggle + 77 new tests

**Phase 0B Sprint 2 — Prophet Forecasting — COMPLETE ✅ (2026-04-19 18:42)**:
- [x] `PHASE_0B_SPRINT2_PREVIEW.md` drafted in plain ქართული (Before/After format) + user approved via `🔵` recommended defaults (3-month horizon / store aliases / revenue-only scope)
- [x] `requirements.txt`: `prophet>=1.1` + `statsmodels>=0.14` moved into active block
- [x] Parent-venv install: **prophet 1.3.0** (pre-built win_amd64 wheel, no cmdstan compile) + **statsmodels 0.14.6** + transitive deps (scipy, matplotlib, cmdstanpy, holidays, patsy, etc.)
- [x] New module `dashboard_pipeline/ai/forecasting.py` (~480 lines): `forecast_revenue(data_loader, *, horizon_months, store)`; Prophet (yearly_seasonality, 95% CI) + ARIMA(1,1,1) ensemble; lazy imports with graceful degradation; `_safe_round_nonneg` clamps output ≥ 0; stable return contract
- [x] `tools.py`: `FORECAST_REVENUE_TOOL` at `TOOL_SCHEMAS[3]`; dispatcher routes `"forecast_revenue"` (lazy import); `_SUMMARY_KEYS` extended; **TOOL_SCHEMAS length 7→8**
- [x] `prompts.py::SYSTEM_PROMPT_KA`: new "🔮 პროგნოზირება (CRITICAL — Phase 0B Sprint 2)" section with trigger list, 12-month horizon guard, historical-use prohibition, mandatory output structure; investigator prompt UNTOUCHED
- [x] Tests: 80 new cases in `tests/test_ai_forecasting.py` (10 classes); 2 existing tests updated for 8-tool surface; **548/548 pytest green** (was 468)
- [x] Live verification on real `data.json` (135.84 MB, 44 months 2022-06→2026-02): Total YoY +18.2%, Ozurgeti YoY -12.47% 📉, Dvabzu YoY +45.14% 📈; Prophet cold 9.17s, warm ~1.2s
- [x] Non-negative clamp verified live: Ozurgeti 2026-07/08 (was -3,518/-6,833) + Dvabzu 2026-05 (was -6,832) all clamped to 0
- [x] Backend restart #2: old PID 30788 stopped, new **PID 19208** started with AI_ENABLE_THINKING=true; `/api/status` 200 OK
- [x] User UI dog-food: "მომდევნო 3 თვის შემოსავალი" → AI passed STOP-CHECK, called `forecast_revenue`, rendered ცხრილი matching scratch-script byte-for-byte (134,944 / 141,994 / 147,679 ₾) with YoY + caveats + inline source

**Phase 0B Sprint 3 — ChromaDB Semantic Memory + RAG — COMPLETE ✅ (2026-04-19 19:40)**:
- [x] `PHASE_0B_SPRINT3_PREVIEW.md` drafted in plain ქართული (Before/After format mirroring Sprint 2 preview); user approved via 4 `🔵` recommended defaults (start Sprint 3 / local ChromaDB / save only "important" entries / index only `Financial_Analysis/` Excel)
- [x] `requirements.txt`: `chromadb>=0.5` + `sentence-transformers>=3.0` moved out of "Phase 2+ not yet active" block into new "Phase 0B Sprint 3 — active" block with LAZY-import note
- [x] Parent-venv install: **chromadb 1.5.8** (pre-built `cp39-abi3-win_amd64` wheel) + **sentence-transformers 5.4.1** + transitive (`torch 2.11.0`, `transformers 5.5.4`, `huggingface-hub 1.11.0`, `tokenizers 0.22.2`, `safetensors 0.7.0`, `onnxruntime 1.24.4`, `opentelemetry-* 1.41.0/0.62b0`, `kubernetes 35.0.0`, `bcrypt 5.0.0`, `pypika 0.51.1`, `pydantic-settings 2.13.1`, `mmh3 5.2.1`, `flatbuffers 25.12.19`, `httptools 0.7.1`, `watchfiles 1.1.1`, `websockets 16.0`, `regex 2026.4.4`, `joblib 1.5.3`, `scikit-learn 1.8.0`, etc.)
- [x] New module `dashboard_pipeline/ai/memory.py` (~610 lines): `MemoryStore` class wraps `chromadb.PersistentClient` + 2 collections (`chat_memory` + `project_index`); shared multilingual MiniLM embedding (`paraphrase-multilingual-MiniLM-L12-v2`); `save_memory` + `recall_context` + `index_project_files` public API; LAZY `_load_chromadb` + `_load_embedding_function` (graceful degradation → Georgian error + `pip install` hint); persist dir `ai_vectors/` (gitignored); process-level singleton via `get_memory_store` + `reset_memory_store` for tests; stable JSON-safe return contracts
- [x] `tools.py`: `RECALL_CONTEXT_TOOL` at `TOOL_SCHEMAS[4]` + `SAVE_MEMORY_TOOL` at `TOOL_SCHEMAS[5]`; `query` required + `limit` 1–50 + `source` enum `["chat","excel"]` for recall; `summary` required (10–8000 chars) + tags + `source` enum `["chat"]` only at tool level for save; dispatcher routes both with LAZY imports; `_SUMMARY_KEYS` extended; **TOOL_SCHEMAS length 8→10**
- [x] `prompts.py::SYSTEM_PROMPT_KA`: new "🔎 სემანტიკური მეხსიერება (CRITICAL — Phase 0B Sprint 3)" section between "🔮 პროგნოზირება" and "თვითკრიტიკა"; trigger list (`გახსოვს?`, `N კვირის/თვის წინ`, `გასულ წელს`, `მე რა დაგპირდი`, `რა შევთანხდით`, `2024/2025 ოქტ-ში რა იყო`); anti-trigger list (current period → `read_data_json`; today → `<TODAY>` block; future → `forecast_revenue`); cite matched_id rule + refuse to invent on `result_count==0` or `distance>0.7`; save policy with `kind:decision/promise/observation/recommendation` tags + `supplier:`/`topic:` namespacing; **investigator prompt UNTOUCHED**
- [x] New script `index_project_files.py` (root, ~330 lines): walks `Financial_Analysis/` recursively (`.xls`/`.xlsx`/`.xlsm` + `.csv`); auto-tags `excel`/`csv` + `category:waybills|sales|bank|products` + `year:YYYY`; `--max-rows 2000` + `--max-sheets 5` + `--skip-larger-than 80MB` defaults; `--full` / `--replace` / `--dry-run` / `--limit N` flags
- [x] Tests: 85 new cases in `tests/test_ai_memory.py` (13 classes); 3 existing tests updated for 8→10 tool surface (`test_ai_forecasting`, `test_ai_investigator`, `test_ai_agent`); **633/633 pytest green** (was 548); fake in-process ChromaDB fixture mocks `chromadb` + embedding function so tests run in milliseconds
- [x] Live verified this session (no Anthropic call yet — backend restart pending):
  - Smoke import: `chromadb 1.5.8` + `sentence-transformers 5.4.1` + memory module + TOOL_SCHEMAS length 10 with `recall_context` + `save_memory` present
  - `python index_project_files.py --dry-run` → 26 candidate files discovered
  - `python index_project_files.py --limit 1 --max-rows 100` → `manual_payments.csv` indexed → 5 vectorized chunks in 0.2s; `ai_vectors/` created
  - Scratch round-trip: `save_memory("Alpha-ს ვალი 23,000 ლარი — 45 დღე გადაცილებული...", tags=["kind:decision","supplier:alpha"])` → `chat_996e...58815`; `recall_context("Alpha ვალი ვაჭრობა")` returned that exact memory as rank 1 (cosine distance 0.486)
  - Embedding model `paraphrase-multilingual-MiniLM-L12-v2` downloaded successfully on first use (HF cache, ~120 MB)

**Phase 0B Sprint 4 — Decision Journal + Metrics + Closure (IN PROGRESS)**:
- [x] **Part 1 — Decision Journal code** ✅ (2026-04-19 22:05)
- [x] **Part 1 — Live CRUD verification** ✅ (2026-04-19 22:45) — backend restart on parent venv (killed stray system-Python PID 18076 → new PID 10128; TOOL_SCHEMAS=13 live) + scratch smoke 6/6 pass (add overdue promise → list returns 1 → `<TODAY>` shows ⏳ 2d overdue → update done → entry disappears)
  - **Bug fix #1**: Windows venv Path-check caveat — `Get-Process <pid> | Select Path` unreliable (stub forwards image); use `Win32_Process.CommandLine` or in-process `sys.prefix` instead
  - **Bug fix #2**: ChromaDB 1.5.x `$lt`/`$gt` silent no-op on string metadata — date filters moved to Python `_apply_python_date_filters`; `_build_journal_where` emits only `$eq`/`$ne`; pytest 743/743 green (+1 new test `test_overdue_with_explicit_status_skips_auto_open`)
- [x] **Part 1 live Anthropic dog-food** ✅ (2026-04-19 23:05) — 2 `/api/chat` turns against real Sonnet 4.6 prove SYSTEM_PROMPT_KA 📋 section end-to-end:
  - Turn 1 (27.5s, natural promise "Alpha-ს ვალი 7 დღე გადაცილებულია..."): AI called `journal_add_entry` with correct kind + due_date (today+3) + Sprint 3 `supplier:alpha` / `topic:cashflow` tag convention; entry `journal_ea57220f...72415a` stored
  - Turn 2 (7.1s, natural query "რა მაქვს ახლა ღია ჟურნალში?"): AI called `journal_list_entries(status="open")`; returned Alpha row + days-to-due hint
  - Cache: Turn 1 `cache_create=16028 + cache_read=16028`; Turn 2 `cache_read=32056 + cache_create=0` (warm prefix, ~4× speedup)
  - Cost: ~$0.09 total for both turns
  - Cleanup: test entry cancelled via `update_journal_entry(status="cancelled")` so live data stays clean
- [x] **Part 2 — Phase 0B-wide live metrics + deep-iteration fix** ✅ (2026-04-19 23:15)
  - 7 scripted `/api/chat` calls on Sonnet 4.6: Sprint 1 `think=true` + Sprint 2 `forecast_revenue` + Sprint 3 `save_memory`/`recall_context` + Sprint 4 `journal_add/list/update` — total ~$0.25 / ~2.4 min / 6-of-7 clean end_turn
  - Cache hit rate after first call: 32,056 tokens cache_read on every follow-up turn → ~10× input-cost drop
  - Surfaced caveat → **fix landed in same session**: Sprint 1 Alpha strategic question hit `MAX_TOOL_ITERATIONS=6` under Extended Thinking. Added `MAX_TOOL_ITERATIONS_DEEP = 10` + `AIAgent._resolve_max_iterations(mode, thinking_enabled)` helper; plain chat still capped at 6, `think=True` OR `mode=investigate` unlock 10. 9 new `TestDeepIterationCap` cases; pytest 752/752 green.
  - Backend restart #5: killed PID 10128, started PID 7644 on parent venv with new deep cap live
  - Re-verified Sprint 1 Alpha question on new backend — 8 tool calls (`read_data_json` ×3 + `recall_context` + `compute` ×4), `stop_reason=end_turn`, full Georgian 3-version strategic analysis (3,722 chars), ~$0.186
- [x] **Part 3 — Phase 0B retrospective + docs refresh + final closure** ✅ (2026-04-19 23:40)
  - `PHASE_0B_SPRINT4_PREVIEW.md` marked COMPLETE with Part 2 + Part 3 summary banner
  - `PLAN.md`, `CONTEXT_HANDOFF.md`, `HANDOFF.md` all refreshed with Phase 0B closure status
  - Scratch artifacts cleaned up

**Sprint 3 (reference, all ✅)**:
- [x] Backend restart #3 — fresh parent-venv PID 18076 (2026-04-19 20:54) exposes the 10-tool surface live
- [x] Live Anthropic dog-food for `recall_context` + `save_memory` — 4 user-driven UI turns all ✅
- [x] Full RAG project indexing — 26 files → 18,263 unique chunks (after path_token fix)
- [x] Georgian embedding Latin fix (21:10) — `_FOLDER_LATIN_HINTS` + prompt guidance; BOG 2023 recall cosine 0.385 → 0.096
- [x] path_token ID-collision bug-fix (21:25) — SHA256 replaces ASCII-only regex; 26 files indexed cleanly (was 20 with collisions)

**Phase 1 Part A — AI-ის "ხასიათი" + "საზრისობა" — COMPLETE ✅ (2026-04-20 00:30)**:
- [x] `PHASE_1_PART_A_PREVIEW.md` drafted in plain ქართული (Before/After + 4-cluster format) + user approved via "გააკეთე როგორც საჭიროდ ჩათვლი" (default scope: all 10 features + auto-hat + non-factual confidence + strict-but-political tone)
- [x] `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — persona upgrade to "სტრატეგიული ფინანსური პარტნიორი" + 8 new CRITICAL sections inserted BEFORE the existing ENG/STOP-CHECK stack:
  - `🎯 როლის კონტრაქტი` — outcome-based focus, flattery/soft-pedaling forbidden, risks in opening paragraph
  - `🗺️ პროექტის რუკა` — ოზურგეთი (3 POS urban tourist) + დვაბზუ (2 POS rural weekend peak) + RS.ge + VAT 18% + ფრენჩაიზი + data.json / Financial_Analysis / ChromaDB / <TODAY> layer breakdown
  - `⚖️ წყაროების იერარქია` — Excel > data.json > ChromaDB > AI's head (❌ no numbers from memory)
  - `🕵 Data-ზე სკეპტიციზმი` — manual_payments.csv freshness, rows_preview lag, supplier_aging refresh cadence + mandatory bank-statement cross-check rule
  - `🎭 5 ქუდი (Multi-Role)` — 💼 ფინანსური / 🔧 ოპერაციული / 🎯 სტრატეგი / ⚠️ რისკის / 🪞 კრიტიკოსი; hats skipped on factual queries, 2-3 mandatory on complex ones
  - `🎯 Confidence ნიშნები` — ✅ (95%+) / 🟢 (75-95%) / 🟡 (50-75%) / 🟠 (25-50%) / ⚪ (0-25%) with factual-carve-out
  - `📌 ვარაუდი vs ფაქტი` (Anti-Hallucination v2) — "ალბათ"/"დაახლოებით"/"ჩვეულებრივ" forbidden; tool-less numbers MUST carry 📌 mark + confidence label
  - Strict-tone reinforcement in "ენა და ფორმატი" section
- [x] `dashboard_pipeline/ai/agent.py` — `MAX_TOOL_ITERATIONS_DEEP` bumped **10 → 12** (5-hat + multi-store triangulation + multi-hypothesis routinely chain past 10 tool calls); `_resolve_max_iterations` docstring refreshed
- [x] `dashboard_pipeline/ai/today_context.py` — 3 additions:
  - `_WEEKDAY_CONTEXT` — 7-entry Georgian weekday hint table (Monday "კვირის დასაწყისი" → Saturday/Sunday "weekend — retail peak"); rendered inline on the ISO-date header line
  - `_FIXED_MONTHLY_DEADLINES` — 2-entry Georgian regulatory calendar (VAT declaration RS.ge + საპენსიო ფონდი, monthly day 15); franchise/income tax intentionally left to user journal
  - `_upcoming_deadlines(today)` + `_next_monthly_anchor` + `_clamp_day` helpers — severity buckets (🚨 urgent ≤3d / ⏰ approaching ≤7d / 📆 normal ≤10d horizon); rendered as "⏰ უახლოესი ვადები" section between top_risks and ⏳ open_promises
- [x] Tests: **66 new cases** in `tests/test_ai_prompts_phase1.py` (14 classes: TestStrategicPartnerPersona 5 + TestStrictToneContract 5 + TestProjectMap 5 + TestSourceHierarchy 4 + TestDataSkepticism 4 + TestFiveHats 8 + TestConfidenceLabels 4 + TestAssumptionMark 3 + TestInvestigatorPromptUntouched 3 + TestBuildSystemPromptWiring 2 + TestWeekdayContext 5 + TestUpcomingDeadlines 8 + TestMonthArithmetic 6 + TestTodayContextCtxShape 4); 5 existing tests re-anchored from "ფინანსური მრჩეველი" → "🎯 როლის კონტრაქტი" (Phase 1 Part A-durable chat-only marker); `TestDeepIterationCap::test_constants_order` updated 10 → 12; `test_deep_cap_still_enforces_ten_iteration_limit` renamed `twelve`
- [x] **pytest 818/818 passed** (was 752; +66 new; 0 weakened or deleted); investigator prompt untouched (do-not-touch rule honored — Sprint 1/2/3/4 **AND** Phase 1 Part A)
- [x] **Backend restart #6** ✅ (2026-04-20 00:47) — parent-venv PID 11620, Phase 1 Part A SYSTEM_PROMPT_KA + deep cap=12 + timeout=120s all LIVE; `Win32_Process.CommandLine` + in-process string-marker probe verified
- [x] **Live Anthropic dog-food** ✅ (2026-04-20 00:55) — 1 scripted `/api/chat` (think=True) with 2-store comparison → AI emitted all 5 hats + 3-version multi-hypothesis + 🟢 საიმედო confidence + strict tone + inline `წყარო:` + auto-invoked `save_memory` (`chat_705a38ef`) + `journal_add_entry` (`journal_886cce34`); 26 tool calls under 12-iteration cap; 151.6s elapsed; 175K cache-read tokens (~$0.12 per strategic turn); `stop_reason=end_turn`; `<TODAY>` render confirms Monday weekday hint `კვირის დასაწყისი — დაგეგმე` (VAT/საპენსიო deadline დღეისთვის გამორცხული — შემდეგი anchor 15 მაისია, 25 დღე — 10-დღიანი ფანჯრიდან გარეთ)
- [x] **Collateral 1-line production fix** ✅ (2026-04-20 00:47) — `DEFAULT_TIMEOUT_S` 60s → 120s in `dashboard_pipeline/ai/agent.py:47` (Phase 1 Part A + Extended Thinking + Prophet cold-start-მ ერთად 60s-ის ნაცვლად 40-80s დახარჯა — Anthropic SDK retry ლუპს ჩართო; no tests pinned 60s value; behavior unchanged for fast chats)

**Phase 1 Part B — ქართული რეგულაცია + ფრენჩაიზი კონტექსტი — COMPLETE ✅ (2026-04-20 01:28)**:
- [x] `PHASE_1_PART_B_PREVIEW.md` drafted in plain ქართული (Before/After + 3-option scope format) + user approved "კი" → default (🔵 A Narrow + 🔵 I Auto-journal placeholders + 🔵 α Journal placeholder for tax/VAT status)
- [x] `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — new `🇬🇪 ქართული რეგულაცია (CRITICAL — Phase 1 Part B)` section inserted after `🗺️ პროექტის რუკა` and before `⚖️ წყაროების იერარქია`:
  - `💰 საჯარო გადასახადები` — VAT 18% (day 15) + საპენსიო 2% + 2% (day 15) + შემოსავლის გადასახადი standard 15% / small-business 1% (< 500K ₾) / VAT threshold 100K + CB+1% penalty
  - `🧾 RS.ge` — ე-ინვოისი 30-day unpaid warning + waybill 3-date-fields cross-reference + მცირე ბიზნესის თრეშოლდი
  - `🏪 ფრენჩაიზი` — Royalty 4-7% + Sourcing obligation 60-75% + Opening fee $5K-20K + Brand standards (contract breach / royalty freeze / termination warnings); Royalty marked as 📌 ვარაუდი, user's concrete % to be asked + journal-saved
  - `📋 Baseline facts` — 4 user-specific facts (Royalty % / Sourcing obligation % / income tax status / VAT registration status) → AI asks on first relevant topic + `journal_add_entry(kind="reminder", tags=["topic:franchise"|"topic:tax"])` auto-invocation; `ask-not-guess` rule explicit
  - `🌅 ქართული თვის რიტმი` — 4 buckets (1-10 calm / 11-14 pre-deadline / **15 deadline day** / 16-30 accumulation) + recommendation rules ("cash-intensive in 5-10", "**15-ე-ს შემდეგ** qualifier in 12-14", "next-month preparation in 16-25")
  - Investigator prompt **untouched** (do-not-touch rule: Sprint 1/2/3/4 + Phase 1 Part A + Part B)
- [x] Tests: **42 new cases** in `tests/test_ai_prompts_phase1b.py` (8 classes: TestGeorgianRegulationSection 5 + TestTaxRules 8 + TestRsGeRules 3 + TestFranchiseContext 6 + TestBaselineFacts 8 + TestMonthlyRhythm 5 + TestBuildSystemPromptWiring 3 + TestInvestigatorPromptUntouched 4)
- [x] **pytest 860/860 passed** (was 818; +42 new; 0 weakened or deleted); investigator prompt untouched (do-not-touch rule honored)
- [x] **Backend restart #7** ✅ (2026-04-20 01:24) — parent-venv PID 36460, Phase 1 Part B `🇬🇪 ქართული რეგულაცია` live; `Win32_Process.CommandLine` + in-process 15-marker scan (`VAT (დღგ)` / `18%` / `საპენსიო ფონდი` / `Royalty` / `4-7%` / `Sourcing obligation` / `60-75%` / `Baseline facts` / `topic:franchise` / `topic:tax` / `🌅 ქართული თვის რიტმი` / `deadline day` / `cash-intensive`) all present in chat prompt, all 15 absent from investigator prompt; `/api/status` 200 OK
- [x] **Live Anthropic dog-food** ✅ (2026-04-20 01:28) — 1 scripted in-process `AIAgent.chat(think=True)` call with ოზურგეთი POS 20K ₾ capex timing question (2026-04-20 context) → AI reply verified:
  - 4/5 hats (💼 ფინანსური + ⚠️ რისკის + 🎯 სტრატეგი + 🪞 კრიტიკოსი; 🔧 ოპერაციული skipped — capex timing doesn't need tech perspective)
  - Multi-hypothesis 3 versions (40% / 35% / 25%, sum 100%)
  - Confidence stack: 🟢 საიმედო on recommendation + multiple 🟡 ვარაუდი markers
  - **Monthly rhythm rule LIVE-applied** — recommended "2026-05-16 — 2026-06-01 მე-2 ტერმინალი **15-ის deadline-ის შემდეგ**" ⚠️ (Part B `<TODAY>` + monthly-rhythm synergy confirmed end-to-end)
  - VAT + საპენსიო 15 მაისი deadline explicitly mentioned
  - **Baseline facts mechanism LIVE-invoked** — AI called `recall_context(query="VAT სტატუსი შემოსავლის გადასახადი მცირე ბიზნესი cash planning")` as Part B prescribes
  - 10 tool calls under 12-iteration cap: `journal_list_entries` → `read_data_json(monthly_pnl / executive_summary / supplier_aging)` ×4 → `forecast_revenue(ოზურგეთი, 3)` yoy=-12.47% → `recall_context` baseline facts → `compute(sum Q2 forecast)` 177,830 ₾
  - Auto-invoked `journal_add_entry` (`journal_15c67afa...` recommendation "ოზურგეთის ხარჯების ატრიბუციის გამოძიება"; post-run cancelled for clean data)
  - 111.72s elapsed; 30,197 in + 4,507 out + **108,127 cache_read** (Anthropic cache warm from Part A session); `stop_reason=end_turn`; ~$0.19 per strategic turn
  - `<TODAY>` render confirms ორშაბათი weekday hint, May 15 deadline outside 10-day horizon (25 days away), 1 open journal carry-over

**Phase 1 Part C — Multi-Store DNA — COMPLETE ✅ (2026-04-20 02:11)**:
- [x] `PHASE_1_PART_C_PREVIEW.md` drafted in plain ქართული (Before/After + 3-option scope format) + user approved "გააგრძელე" → default (🔵 A Core DNA + 🔵 I Auto-journal placeholders + 🔵 α Soft seasonality hint)
- [x] `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — new `🏪 მაღაზიების DNA (CRITICAL — Phase 1 Part C)` section inserted after `🌅 ქართული თვის რიტმი` and before `⚖️ წყაროების იერარქია`:
  - `🏪 ოზურგეთი — Urban Flagship` — 10-row DNA card (ტიპი / 3 POS / 12-საათიანი / tourist-local mix / higher traffic 2-3× / evening 20-22 peak + weekend + tourist summer / premium mix tilt / fast high-pass-through promotion / mixed elasticity / smaller impulse basket)
  - `🏡 დვაბზუ — Rural Local` — 10-row DNA card (Rural / 2 POS / 8-საათიანი / local loyal regular / lower traffic ~50-60% / weekend + payday 10/25 + ortodox holidays peak / basics bulk tilt / slow low-pass-through promotion / low elasticity / larger planned recurring basket)
  - `🌅 სეზონური რიტმი` — soft-hint (ოზურგეთი 6-9 ზაფხული + დეკემბერი; დვაბზუ 10/25 payday + Easter + აგვ-სექტ moderate; ორივეს 31 დეკემბერი); precise numbers via `forecast_revenue(store=...)`
  - `🎯 DNA-ს გამოყენება` — 7-dimension guidance table (Promotion / ახალი კატეგორია / Supplier / Staffing / Pricing / Cash planning / Store comparison) — DNA impact per question type
  - `📋 Baseline facts — store-level` — 4 user-specific placeholders (ტურისტული თვეების ფანჯარა / ხელფასი days / Top-3 supplier concentration / Evening:Daytime revenue ratio) with `topic:store_dna` + `kind:reminder` tags + `journal_add_entry` pattern; generic DNA numbers stay 📌 ვარაუდი until user supplies concrete data
  - `⚠️ DNA-ს over-apply-ის წინააღმდეგ` — explicit rule: DNA used only on strategic/recommendation questions, NOT on simple data lookups (`რამდენი მომწოდებელია?` → `read_data_json`, არა DNA essay)
  - Investigator prompt **untouched** (do-not-touch rule: Sprint 1/2/3/4 + Phase 1 Part A + Part B + Part C)
- [x] Tests: **54 new cases** in `tests/test_ai_prompts_phase1c.py` (9 classes: TestMultiStoreDnaSection 6 + TestOzurgetiDna 7 + TestDvabzuDna 7 + TestSeasonality 4 + TestStrategicGuidance 6 + TestBaselineFactsPartC 6 + TestOverApplyGuardrails 3 + TestBuildSystemPromptWiring 4 + TestInvestigatorPromptUntouched 6 + TestPhase1PriorPartsStillPresent 5)
- [x] **pytest 914/914 passed** (was 860; +54 new; 0 weakened or deleted); investigator prompt untouched (15 Part C markers absent)
- [x] **Backend restart #8** ✅ (2026-04-20 02:11) — old PID 36460 stopped, fresh parent-venv PID **31176** started via `& '...\venv\Scripts\python.exe' -u server.py` with `$env:AI_ENABLE_THINKING='true'`; verified via `Get-CimInstance Win32_Process -Filter "ProcessId=31176" | Select CommandLine` = `"...\venv\Scripts\python.exe" -u server.py` + in-process 15-marker probe (chat 15/15, investigator 0/15) + `/api/status` 200 OK
- [x] **Live Anthropic dog-food** ✅ (2026-04-20 02:11) — 1 scripted in-process `AIAgent.chat(think=True, mode="chat")` call with თამბაქოს 10-15% ფასდაკლება cross-store question → AI reply verified with all 5 DNA markers:
  - ოზურგეთი explicit mention ✅ + დვაბზუ explicit mention ✅
  - elasticity reasoning (tourist + loyal + habit-driven terms) ✅
  - Confidence tags (🟢 საიმედო / 🟡 ვარაუდი) ✅
  - DNA-based hypothesis (peak / mix / POS / რეჟიმი) ✅
  - `stop_reason=end_turn` ✅
  - 15 sources + 6+ tool calls (`read_data_json` ×4 + `recall_context` excel + `read_excel_source`) under 12-iteration cap
  - ~2 წთ elapsed, 178,889 in + 5,607 out + **166,817 cache_read** (warm from Part A/B sessions); ≈$0.14 per strategic turn
  - First dog-food attempt (pre env flag) hit `MAX_TOOL_ITERATIONS=6` — `AI_ENABLE_THINKING=true` set in launch env on second attempt → deep cap 12 activated → clean end_turn

**Phase 1 Part D — Self-Correction Loop — COMPLETE ✅ (2026-04-20 02:50)**:
- [x] **Trigger**: 2026-04-20 02:30 BOG 2026-02 incident — AI answered "ფაილი არ მაქვს" after 1 weak query against ChromaDB; `02--2026.xlsx` was actually indexed (6,374 chunks) and present in `Financial_Analysis/ბოგ ბანკი ამონაწერი/`. Investigation confirmed query "ბოგ 2026" returns θბს ბანკი (3-letter Georgian abbreviation embedding conflation); query `"საქართველოს ბანკი BOG Bank of Georgia 2026-02"` returns 5/5 BOG 02--2026 (cosine 0.116). Sprint 3 had a "Latin alias hint" but AI was not forced to use the FULL phrase.
- [x] `PHASE_1_PART_D_PREVIEW.md` drafted in plain ქართული (real-incident retrospective + Before/After + 3-tier scope) + user approved "კი" → default (🔵 A Core retry + 🔵 B Latin MANDATE + 🔵 C Date triage)
- [x] `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — new `🔄 საკუთარი თავის გასწორების ციკლი (CRITICAL — Phase 1 Part D)` section inserted after `🏪 მაღაზიების DNA` and before `⚖️ წყაროების იერარქია`:
  - **Intro contract**: `"ცარიელი ან ცუდი პასუხი" ≠ "არ არსებობს"` + `მინიმუმ 3-ჯერ` retry + first-attempt "არ მაქვს" forbidden
  - **🔁 Retry Protocol** — 4-step table with concrete BOG 2026-02 example progression: (1) user-phrase verbatim → (2) + Latin alias `Bank of Georgia` → (3) + 3 date formats → (4) + file/folder fallback
  - **🎯 Self-Triage** — 3-hypothesis table: 0 hit → "Query ძალიან ვიწროა" + 5+ hit wrong bank → "Latin alias სუსტია" + Off-topic → "Embedding ურევს მსგავს აბრევიატურებს" with domain-anchor keywords (ამონაწერი / ანგარიში / POS / ტერმინალი)
  - **📢 Latin Alias MANDATORY** — Sprint 3 "hint" → "MANDATE": ბოგ → `Bank of Georgia` (BOG alone forbidden) / თბს → `TBC` / რს → `Revenue Service` (RS alone forbidden) + ANTI-PATTERN column with explicit do-not examples
  - **📅 თარიღის 3 ფორმატი** — `YYYY-MM` + `Month YYYY` + `ქართული თვე YYYY` (activate on 2nd retry)
  - **❌ "ვერ ვიპოვე" only after 3+ attempts** — explicit rule: list attempts to user (`ვცადე: (1)... (2)... (3)...`), invite clarification (`დააზუსტე: ...`), show attempt-work not just conclusion
  - Investigator prompt **untouched** (do-not-touch rule: Sprint 1/2/3/4 + Phase 1 Part A + Part B + Part C + Part D)
- [x] Tests: **55 new cases** in `tests/test_ai_prompts_phase1d.py` (8 classes: TestSelfCorrectionSection 6 + TestRetryProtocol 8 + TestSelfTriage 6 + TestLatinAliasMandate 7 + TestDateTriage 5 + TestCannotFindGate 6 + TestBuildSystemPromptWiring 4 + TestInvestigatorPromptUntouched 6 + TestPhase1PriorPartsStillPresent 7)
- [x] **pytest 969/969 passed** (was 914; +55 new; 0 weakened or deleted); investigator prompt untouched (15 Part D markers absent)
- [x] **Backend restart #9** ✅ (2026-04-20 02:50) — old PID 31176 stopped, fresh parent-venv PID **7776** started via `Start-Process` with `$env:AI_ENABLE_THINKING="true"`; verified via `Get-CimInstance Win32_Process -Filter "ProcessId=7776" | Select CommandLine` = `"...\venv\Scripts\python.exe" -u server.py` + in-process 15-marker probe (chat 15/15, investigator 0/15) + `/api/status` 200 OK + AIConfig.enable_thinking=True
- [x] **Live Anthropic dog-food** ✅ (2026-04-20 02:50) — 1 in-process `AIAgent.chat(think=True, mode="chat")` call with **identical** 02:30 BOG 2026-02 question that previously failed → AI behavior verified across all 5 success criteria:
  - ✅ AI did NOT immediately give up (made 17 tool calls vs. previous failure's <5)
  - ✅ recall_context invoked **4 times** with progressive Latin alias enrichment
  - ✅ "Bank of Georgia" full phrase appeared in retry queries
  - ✅ 02--2026.xlsx surfaced in reply (AI recognized file existed in `Financial_Analysis/ბოგ ბანკი ამონაწერი/`)
  - ✅ Structured "ვცადე: (1)... (2)... (3)..." fallback delivered with attempt enumeration + 3 clarifying questions to user (POS/AP debit/external transfer disambiguation)
  - 17 tool calls breakdown: 4× `recall_context` (Latin alias progression) + 6× `read_data_json` (cashflow_summary, monthly_pnl, ap_monthly_trend, executive_summary, imported_products) + 3× `read_excel_source` (Georgian path attempts) + 2× `grep_code` + 1× `read_source_code` + 1× `read_data_json` (executive_summary)
  - **NEW caveat surfaced**: `read_excel_source` blocks Georgian folder names with spaces (e.g. `ბოგ ბანკი ამონაწერი/`) — AI explicitly noted this as a tool limitation, not a data-availability problem; SEPARATE carry-forward concern, NOT a Part D regression

**Next (pending)**:
- Phase 2 kickoff — 2.11 Dead Stock Liquidation + 2.12 Supplier Negotiation Prep (preview-first workflow, same as Phase 1 A/B/C/D)
- Optional Part D-adjacent: `read_excel_source` Georgian-path support (parking-lot — surfaced during Part D dog-food)

**User explicit preferences (locked 2026-04-18)**:
- ✅ Chat-on-demand pull (არა push)
- ✅ მკაცრი/მომთხოვი ტონი, intelligence > cost
- ✅ plain ქართული communication (see `AGENTS.md` CRITICAL section)
- ❌ Daily briefing / Telegram push / auto-alerts
- ❌ Voice input, provider migration, write access

## შემდეგი (არასავალდებულო)
- [ ] Production deploy

## წესი: სესიის ბოლოს HANDOFF.md განახლება
