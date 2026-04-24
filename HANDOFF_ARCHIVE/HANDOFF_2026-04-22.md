# HANDOFF

> ⚠️ **მიმდინარე სტატუსისთვის ეს ფაილი არ გახსნა — ძველია.**
> Latest status: `CONTEXT_HANDOFF.md` (updated 2026-04-21 13:25 — Phase 4A CLOSED + AI FAB hotfix live).
> Phase overview: `PHASE_STATUS_MATRIX.md` (created 2026-04-22 — ერთი ცხრილი ყველა phase-ით).
> Active plan: `PLAN.md` (live status tracker) + `AI_GENIUS_PARTNER_PLAN.md` v2.1 (master roadmap).
> ამ ფაილში ქვემოთ — ისტორიული evidence / file-level detail / runtime caveat-ები (banner 2026-04-20, ბოლო განახლება Phase 1 Part D).
>
> Updated: 2026-04-20 12:50 UTC+04:00 | **🆕 Excel Georgian Path Fix COMPLETE + LIVE VERIFIED** (2026-04-20 12:45) — `_resolve_safe_path` Windows + OneDrive + non-ASCII ancestor bug მოგვარებულია; `Path.resolve(strict=False)` → `Path.absolute()` + ცხადი `..` reject; pytest **976/976 green** (was 969; +7 `TestResolveSafePathRegression`); live AIAgent dog-food on the SAME BOG 2026-02 question — AI now reads `Financial_Analysis/ბოგ ბანკი ამონაწერი/02--2026.xlsx` directly (Path bug **completely gone**; only the SEPARATE 200-row sample cap remains as parking-lot for big-Excel aggregation). Part D's NEW caveat → ✅ **RESOLVED**. | **Packet H COMPLETE** | **AI Phase 0 / 1 / 1 Polish / Streaming SSE / Phase 2 Sprint 1-3 / Phase 2 Live+UI Dog-Food / Waybill Fix / Phase 0A Critical Foundation / Service Worker Cache Fix / Phase 0B Sprints 1-4 + Closure ALL COMPLETE** (2026-04-19 23:40) | **Phase 1 Part A — AI "ხასიათი" + "საზრისობა" Layer 1 COMPLETE + LIVE VERIFIED** (2026-04-20 00:55) | **Phase 1 Part B — ქართული რეგულაცია + ფრენჩაიზი კონტექსტი COMPLETE + LIVE VERIFIED** (2026-04-20 01:28) | **Phase 1 Part C — Multi-Store DNA COMPLETE + LIVE VERIFIED** (2026-04-20 02:11) | **🆕 Phase 1 Part D — Self-Correction Loop COMPLETE + LIVE VERIFIED** (2026-04-20 02:50) — new `🔄 საკუთარი თავის გასწორების ციკლი` section in `SYSTEM_PROMPT_KA` (🔁 Retry Protocol 4-step + 🎯 Self-Triage 3-hypothesis + 📢 Latin Alias MANDATORY 3-row anti-pattern + 📅 Date 3-format triage + ❌ "ვერ ვიპოვე" 3+ retries prerequisite); 55 new tests in `test_ai_prompts_phase1d.py` (pytest **969/969 green** was 914; +55; 0 weakened); investigator prompt untouched (15 Part D markers absent + 6 do-not-touch tests); backend restart #9 parent-venv **PID 7776**; live Anthropic dog-food **5/5 PASS** on the SAME BOG 2026-02 question that triggered the false-negative incident at 02:30 → AI made 17 tool calls (4× recall_context Latin alias progression + 6× read_data_json + 3× read_excel_source + 2× grep_code + read_source_code + executive_summary), surfaced 02--2026.xlsx, delivered structured "ვცადე: (1)... (2)... (3)..." fallback with 3 clarifying questions to user; NEW caveat surfaced: `read_excel_source` blocks Georgian folder paths with spaces (separate carry-forward). — new `🏪 მაღაზიების DNA` section in `SYSTEM_PROMPT_KA` (🏪 ოზურგეთი Urban Flagship 10-row DNA card + 🏡 დვაბზუ Rural Local 10-row DNA card + 🌅 soft seasonality hint + 🎯 7-dimension DNA guidance + 📋 4 store-level baseline facts + ⚠️ over-apply guardrails); 54 new tests in `test_ai_prompts_phase1c.py` (pytest **914/914 green** was 860; +54; 0 weakened); investigator prompt untouched (6 do-not-touch tests + 15 Part C markers absent); backend restart #8 parent-venv **PID 31176**; live Anthropic dog-food on თამბაქოს 10-15% ფასდაკლება cross-store question verified 5/5 DNA markers (ოზურგეთი YES + დვაბზუ NO + elasticity reasoning + 🟢/🟡 confidence + DNA-based hypothesis) end-to-end (~2 წთ, 15 sources + 6+ tool calls, $0.14, `stop_reason=end_turn`, 166,817 cache_read). — Part B earlier: new `🇬🇪 ქართული რეგულაცია` section (💰 tax table + 🧾 RS.ge + 🏪 Franchise + 📋 Baseline facts + 🌅 Monthly rhythm); 42 tests, 860/860 green; live dog-food on capex-timing question verified Monthly rhythm + Baseline facts end-to-end (111.72s, 10 tool calls, $0.19). — `prompts.py::SYSTEM_PROMPT_KA` gained 8 CRITICAL sections (🎯 role-contract + 🗺️ project-map + ⚖️ source-hierarchy + 🕵 data-skepticism + 🎭 5-hats + 🎯 confidence-labels + 📌 assumption-vs-fact anti-hallucination v2 + reinforced strict-tone); persona upgraded `ფინანსური მრჩეველი → სტრატეგიული ფინანსური პარტნიორი`; `MAX_TOOL_ITERATIONS_DEEP` bumped **10 → 12** (5-hat + multi-store triangulation routinely chains past 10 tool calls); `today_context.py` extended with `_WEEKDAY_CONTEXT` (7-entry Georgian weekday hints) + `_FIXED_MONTHLY_DEADLINES` (VAT + საპენსიო, day 15) + `_upcoming_deadlines` / `_next_monthly_anchor` / `_clamp_day` helpers + `⏰ უახლოესი ვადები` block section with 🚨/⏰/📆 severity buckets; investigator prompt **UNTOUCHED** (do-not-touch rule honored since Sprint 1). **66 new tests** in `tests/test_ai_prompts_phase1.py` (14 classes covering persona / project-map / hierarchy / skepticism / 5-hats / confidence / assumption-mark / investigator-untouched / weekday / deadlines / month-arithmetic / ctx-shape); 5 existing persona-marker assertions re-anchored `ფინანსური მრჩეველი → 🎯 როლის კონტრაქტი`; TestDeepIterationCap constant 10 → 12 + test rename `ten_iteration_limit → twelve_iteration_limit`. **pytest 818/818 green** (was 752; +66 new; 0 weakened). 🆕 **Backend restart #6 DONE + Live Anthropic dog-food VERIFIED ✅ (2026-04-20 00:55)** — new PID 11620 on parent venv; single scripted `/api/chat` call (`think=True`) emitted full 5-hat strategic analysis (💼/🔧/🎯/⚠️/🪞 all fired) + multi-hypothesis 3-version (55%/30%/15%) + confidence mark 🟢 საიმედო + strict tone (`"სუსტი ლოგიკაა"` direct critique, zero flattery) + inline `წყარო:` attribution + auto-save to `save_memory` (`chat_705a38ef`) + auto-`journal_add_entry` recommendation (`journal_886cce34`) across 26 tool calls under 12-iteration deep cap. One collateral 1-line production fix: `DEFAULT_TIMEOUT_S 60 → 120 s` in `dashboard_pipeline/ai/agent.py:47` (heavier Phase-1-Part-A prompt + Extended Thinking + Prophet cold-start combined pushed a single Anthropic message past the old 60 s ceiling → SDK auto-retry loop). | next: **Phase 1 Part B preview (1.11 ქართული ბიზნეს — RS.ge + VAT + ფრენჩაიზი royalty)**
> Purpose: lean status banner + pointer to archive; historical evidence lives in `HANDOFF_ARCHIVE/`.
> `CONTEXT_HANDOFF.md` არის მოკლე canonical brief; ეს ფაილი გამოიყენე მხოლოდ მაშინ, როცა გჭირდება ზუსტი history, evidence ან acceptance criteria.

## 0. Current Status Banner (2026-04-17)

### Packet H — COMPLETE ✅
- Process 0-12 accepted (13 period-aware tabs)
- `cashflow` documented intentional exception (internal per-section calendars by design)

### AI Advisor Phase 0 — COMPLETE ✅
- **Step 0.1 ✅** — Packet H closed; `AI_ADVISOR_ROADMAP.md` authored
- **Step 0.2 ✅** — Data Quality Audit passed (9.8/10); 3 Excel↔data.json validations matched
- **Step 0.3 ✅** — Code Hygiene: `deprecated-root-copy/` archived (1.09 GB), `requirements.txt` pinned, `.env.example` created, `.gitignore` hardened
- **Step 0.4 ✅** — External setup + test pings (Anthropic + Telegram both live)
- **Step 0.5 ✅** — This sign-off (HANDOFF split, docs finalized)

### AI Advisor Phase 1 MVP Chat — COMPLETE ✅ (2026-04-17 23:35)
- **Backend**: `dashboard_pipeline/ai/{__init__,config,tools,prompts,agent}.py` — Anthropic `messages.create` tool-use loop, `read_data_json` tool with section allowlist, row cap, filter semantics, JSON-safe output
- **API**: `POST /api/chat` in `server.py` — slowapi 30/min, X-API-Key via existing middleware, lazy agent singleton, 400/503 error mapping
- **Frontend**: `rs-dashboard/src/lib/aiClient.js` + `hooks/useAIChat.js` + `components/ChatAssistant.jsx` (floating FAB + modal) + `components/ChatMessage.jsx` (react-markdown + source attribution + usage badge)
- **Styles**: ~400-line chat UI block appended to `styles/components.css` (FAB, panel, bubble, markdown, typing dots, mobile safe-area)
- **Tests**: 38 new unit tests (`test_ai_tools.py` 23 + `test_ai_agent.py` 15) + 7 E2E (`ai-chat.spec.js`). 163/163 unit, 70/70 E2E, lint clean, build clean
- **Deps**: `requirements.txt` — `anthropic==0.96.0`, `python-dotenv==1.2.2` (pinned). Parent venv gained `pytest==9.0.3` (+ iniconfig, pluggy, pygments). Frontend — `react-markdown@^9`, `remark-gfm@^4`.
- **Live verification**:
  - text-only greeting: 3.6s, 1665 in + 62 out tokens ≈ $0.006/query, no tool calls
  - data query "რამდენი მომწოდებელია" → "**270** (წყარო: data.json → suppliers)", ~30s, 10132 in + 74 out ≈ $0.031, `read_data_json(suppliers)` traced in `sources`
- **Collateral fixes**:
  - `.env.example` — default model names refreshed `claude-3-5-*` → `claude-sonnet-4-6` / `claude-haiku-4-5-20251001` (old models 404 per Step 0.4)
  - `rs-dashboard/src/hooks/useDataStatus.js` — targeted `eslint-disable-next-line react-hooks/set-state-in-effect` (new rule in eslint-plugin-react-hooks@7 flagged async fetch; setState runs after await, not synchronously; pre-existing runtime-correct code)
  - `rs-dashboard/e2e/dashboard.spec.js` — stale `.header-period-badge` assertion replaced with `.dtcp-trigger` check; the badge was removed during Packet F `react-datepicker` migration
  - `rs-dashboard/e2e/helpers/api-mock.js` — added deterministic `POST /api/chat` mock for E2E
- **Known caveat**: `_truncate_output` halves list rows when the serialized tool result exceeds `MAX_OUTPUT_CHARS=32000` — observed on 50-row suppliers slice collapsing to 25 with `truncated: true` flag. Intentional safety rail; future optimization can prune columns rather than rows.

### AI Advisor Phase 1 Polish — COMPLETE ✅ (2026-04-18 00:20)
- **Prompt caching** (Anthropic ephemeral):
  - `dashboard_pipeline/ai/prompts.py` — new `build_system_prompt_blocks(cached=True)` returns `[{type:"text", text:..., cache_control:{type:"ephemeral"}}]`
  - `dashboard_pipeline/ai/tools.py` — new `get_cached_tool_schemas()` returns deep-copy of `TOOL_SCHEMAS` with `cache_control` on the last tool; module constant untouched
  - `dashboard_pipeline/ai/agent.py` — `chat()` now sends `system=<blocks>` + `tools=<cached_tools>`; `usage_totals` extended with `cache_creation_input_tokens` + `cache_read_input_tokens` (defensive `getattr(..., 0)` when absent)
- **Row cap + column pruning**:
  - `DEFAULT_ROW_LIMIT = 10` (was 50)
  - `SECTION_COLUMN_PROFILES` for `suppliers`, `supplier_aging`, `ap_monthly_trend`, `monthly_pnl` — keeps only analytically useful fields
  - `read_data_json` schema gains `columns: "minimal" | "all"` (default `"minimal"`); `_apply_filter_and_limit(section=..., columns=...)` prunes list rows and emits `columns` + `columns_kept` metadata
- **Frontend visibility**:
  - `ChatMessage.jsx::UsageBadge` now renders a `⚡ N cached` sub-span when `cache_read_input_tokens > 0` and surfaces cache read/write totals via tooltip — zero-impact when fields absent
- **Tests**: 19 new unit cases (5 column-pruning, 2 schema, 4 cached-schemas, 2 row-limit default-checks in existing; 5 prompt-block + cache-wiring + cache-usage aggregation in agent). `182/182` unit tests passing. Frontend `npm run lint` + `npm run build` clean (ChatAssistant bundle unchanged size).
- **Expected impact** (to be measured on next live `/api/chat` run):
  - input tokens ~10× drop on cached turns (system + tools ≈ 1500 tok prefix, stable per session)
  - data-query cost: ~$0.031 → ~$0.003 / query target
  - latency: ~30s → ~8s target (less re-tokenization server-side)
  - context window: suppliers slice 50 rows (≈25 after MAX_OUTPUT_CHARS halving) → 10 rows with pruned fields, under 32KB cap without truncation on typical queries
- **No breaking changes**:
  - `build_system_prompt()` string form preserved for backward compat + existing prompt tests
  - `TOOL_SCHEMAS` module constant remains cache-control-free (pure data)
  - Old `_apply_filter_and_limit(value, criteria, limit)` call sites still work via keyword-only `section=None, columns="minimal"` defaults (no internal callers broke)
  - E2E `api-mock.js` contract unchanged (cache fields optional; frontend gracefully hides cache badge when absent)

### AI Advisor — Streaming SSE — COMPLETE ✅ (2026-04-18 00:42)
- **Backend** (`dashboard_pipeline/ai/agent.py`):
  - New `AIAgent.chat_stream(message, history)` sync generator — mirrors the `chat()` tool-use loop but uses `client.messages.stream(...)` context manager
  - Yields event dicts in order: `delta` (text chunks, many) → `tool_call` + `tool_result` (per tool iteration) → `sources` → `usage` → `history` → `done`; fatal failure emits `error` and terminates
  - Reuses `build_system_prompt_blocks()` + `get_cached_tool_schemas()` — **prompt caching stacks on top of streaming** (first-token latency drops further on cache hit)
  - Defensive fallbacks: missing `.messages.stream` → error event; empty message → error event; `MAX_TOOL_ITERATIONS` hit → fallback Georgian delta + `stop_reason: "max_iterations"`
- **API** (`server.py`):
  - New `POST /api/chat/stream` endpoint — `text/event-stream` response; same body contract as `/api/chat`; slowapi 30/min; X-API-Key inherited via `ApiKeyMiddleware`
  - `_format_sse_event(event)` — W3C-compliant SSE frame (`event: <type>\ndata: <json>\n\n`)
  - `_sse_stream_bridge(sync_gen)` — async wrapper running `next()` in a threadpool so the event loop keeps serving other requests while Anthropic streams; `asyncio.CancelledError` triggers `sync_gen.close()` on client disconnect
  - Headers include `Cache-Control: no-cache`, `X-Accel-Buffering: no` (nginx-friendly)
- **Frontend**:
  - `rs-dashboard/src/lib/aiClient.js`:
    - new `postChatStream({message, history, signal, onEvent})` — `fetch` + `ReadableStream` + SSE parser
    - new `parseSseEventBlock(block)` — exported utility; splits `event: <type>` + `data: <json>` lines (strips CR, handles comments, concatenates multi-line data per SSE spec)
    - existing `postChat()` preserved (unused by default path now, still exported for fallback/tests)
  - `rs-dashboard/src/hooks/useAIChat.js`:
    - switched default path from `postChat` → `postChatStream`
    - progressive `streamedText` accumulates on each `delta`; `pending` flips to `false` on first delta; `streaming: true` flag set until final `done`
    - tool_call events captured into `entry.toolCalls` array (future UI hook; invisible today)
    - `sources`, `usage`, `history` events fold into the final assistant entry on stream end
    - `AbortController` still cancels in-flight streams on `reset()` / fresh `send()`
  - `rs-dashboard/src/components/ChatMessage.jsx` — unchanged; existing markdown + typing-dots → text render works naturally with progressive updates (pending=false hides dots once first delta arrives)
- **Tests**:
  - `tests/test_ai_agent.py` — +10 new cases in `TestChatStream` class:
    - `FakeStream` + `FakeStreamMessages` + `FakeStreamingClient` fixtures mimic Anthropic's sync context-manager streaming API
    - covered: text-only delta streaming, tool-use iteration (`tool_call` before `tool_result`), empty message error, missing `.stream` method error, max-iterations guard, cache-token aggregation, `history` event shape, prompt-caching wiring on the stream path, tool-error resilience, prior-history carry-forward
  - `rs-dashboard/e2e/ai-chat.spec.js` — +1 streaming smoke test (`chat hook uses streaming endpoint (/api/chat/stream)`); asserts the new endpoint is hit with correct method/content-type and streamed chunks concatenate to the final reply
  - `rs-dashboard/e2e/helpers/api-mock.js` — new `/api/chat/stream` mock emits SSE-framed body with 3 delta chunks + sources + usage + history + done events; existing `/api/chat` mock retained for back-compat
  - All **192/192** unit tests pass (was 182/182; +10 streaming); **8/8** ai-chat E2E tests pass (was 7; +1 streaming smoke)
- **Verification**:
  - `pytest tests/test_ai_agent.py -v` → 32/32 passed (was 22; +10 streaming)
  - `pytest tests/` → 192/192 passed (0.73s)
  - parent-venv smoke import: `AIAgent.chat_stream` exists, `server.post_chat_stream` + `_sse_stream_bridge` + `_format_sse_event` all reachable
  - `npx eslint` (targeted + full `npm run lint`) → clean
  - `npm run build` → clean, ChatAssistant bundle 164.31 kB gzip 49.67 kB (+1.44 kB / ~0.57 kB gzip over Phase 1 Polish — streaming logic additive)
  - `npx playwright test e2e/ai-chat.spec.js` → 8/8 passed (13.0s)
- **Expected UX impact** (to measure on next real `/api/chat/stream` call):
  - first-token latency: ~8s (Phase 1 Polish cached turn) → ~2s (streaming on top of cache hit)
  - total turn time unchanged (tool calls still round-trip server-side), but perceived speed dramatically better
  - data-query cost unchanged from Phase 1 Polish target (~$0.003/query on cached turns)
- **No breaking changes**:
  - `POST /api/chat` endpoint retained; existing clients using `postChat()` continue to work
  - `AIAgent.chat()` method unchanged
  - `TOOL_SCHEMAS` + `build_system_prompt_blocks` + `get_cached_tool_schemas` all re-used by streaming path (no drift risk between the two endpoints)
  - Streaming mock emits cache_* fields = 0 (UsageBadge still renders correctly whether cache metrics appear or not)

### AI Advisor Phase 2 Investigator — Sprint 1 — COMPLETE ✅ (2026-04-18 01:10)
- **Backend tools** (`dashboard_pipeline/ai/tools.py`):
  - `read_source_code(file_path, line_range?)` — path allowlist `ALLOWED_CODE_ROOTS` (`dashboard_pipeline/`, `rs-dashboard/src/`, `tests/`, `server.py`, `generate_dashboard_data.py`, `backend_paths.py`); bounded `MAX_SOURCE_LINES=500`, `DEFAULT_SOURCE_LINES=200`
  - `grep_code(pattern, path?, max_hits?)` — regex across code roots; caps `DEFAULT_GREP_HITS=50`, `MAX_GREP_HITS=200`; early-exit on cap hit
  - `read_excel_source(file_path, sheet?, nrows?, skiprows?)` — allowlist `ALLOWED_DATA_ROOTS` (`Financial_Analysis/`); csv/xlsx/xls via pandas + engine-switch; caps `DEFAULT_EXCEL_NROWS=20`, `MAX_EXCEL_NROWS=200`; unicode subdir safe
  - `validate_vs_source(section, expected_row_count?, expected_total?, field_name?)` — compare data.json section metadata vs expected; status `inspected`/`match`/`mismatch`; `_SECTION_SOURCE_HINTS` dict for source hints
- **Path safety**: `_resolve_safe_path(rel_path, allowed_roots, project_root)` rejects traversal (`..`), absolute paths, Windows drive letters, and unicode-encoded escapes; `.env`, `secrets/`, `node_modules/`, `ai_memory.db`, `ai_vectors/` MUST remain outside both allowlists
- **Tools schema gains** — `INVESTIGATOR_TOOL_NAMES` tuple + all 4 new schemas added to `TOOL_SCHEMAS`; cache_control annotation still lives only in `get_cached_tool_schemas()` deep-copy (module constant stays cache-control-free)
- **Dispatcher** (`ToolDispatcher`) — extended with `project_root` kwarg + routes all 5 tools; `read_data_json` unchanged
- **Tests** — 66 new cases in `tests/test_ai_investigator.py` covering path resolver, allowlist rejection, line-range bounds, regex caps, Excel engine selection, mismatch detection, traversal attack vectors
- **Verification**: `pytest tests/` → 258/258 passed (was 192; +66 investigator)

### AI Advisor Phase 2 Investigator — Sprint 2 — COMPLETE ✅ (2026-04-18 01:40)
- **Prompt variant** (`dashboard_pipeline/ai/prompts.py`):
  - `SYSTEM_PROMPT_KA_INVESTIGATOR` — Georgian discrepancy-hunter persona; mandates ordered methodology (`read_data_json` → `read_excel_source`/`validate_vs_source` → `grep_code`/`read_source_code`); mandates structured response with `🔍 აღმოჩენა` / `📊 შედარება` / `🔎 მიზეზი` / `📋 Cascade-ისთვის` sections; enforces "no discrepancy ⇒ no Cascade brief" + `.env`/`secrets/`/`node_modules/` hands-off + `cashflow` period-aware prohibition
  - `SUPPORTED_MODES = ("chat", "investigate")` + `DEFAULT_MODE = "chat"` + registry `_SYSTEM_PROMPT_BY_MODE`
  - `_resolve_mode(mode)` — empty/whitespace/`None` → default; unknown → `ValueError`
  - `build_system_prompt(extra_context="", *, mode="chat")` + `build_system_prompt_blocks(extra_context="", *, cached=True, mode="chat")` — each mode caches its own Anthropic prefix independently
- **Agent** (`dashboard_pipeline/ai/agent.py`):
  - `AIAgent.chat(..., *, mode="chat")` + `AIAgent.chat_stream(..., *, mode="chat")` — keyword-only mode kwarg; forwards into prompt builder; echoed in `usage.mode`
  - `_validate_mode(mode)` — raises `AIAgentError` on `chat()` path; yields single `error` event on `chat_stream()` path **without opening the Anthropic stream** (token cost guard)
- **Server** (`server.py`):
  - `_extract_chat_mode(payload)` helper — shared 400 validation
  - `POST /api/chat` + `POST /api/chat/stream` bodies accept optional `mode`; passes into agent
- **Tests** — +24 cases (`TestPromptMode` 11 + `TestChatMode` 8 + `TestChatStreamMode` 5) in `tests/test_ai_agent.py`; streaming guard `test_invalid_mode_does_not_open_stream` asserts `fake.messages.calls == []`
- **Verification**: `pytest tests/` → 282/282 passed (was 258; +24 mode cases)
- **Bug caught + fixed during dev**: initial `_resolve_mode("   ")` raised `ValueError` because `(mode or DEFAULT_MODE)` short-circuit didn't cover whitespace-only strings. Refactored to `raw.strip().lower()` + early `return DEFAULT_MODE` on empty (matches user's "გასასწორებელი გვერდი არ ააუარო ან გადადო" rule)

### AI Advisor Phase 2 Investigator — Sprint 3 — COMPLETE ✅ (2026-04-18 02:00)
- **Frontend client** (`rs-dashboard/src/lib/aiClient.js`):
  - `postChat({ message, history, mode, signal })` + `postChatStream({ message, history, mode, signal, onEvent })` — optional `mode` body field; omitted from POST body when falsy/empty (preserves pre-Sprint 3 backward compat)
- **Chat hook** (`rs-dashboard/src/hooks/useAIChat.js`):
  - `send(message, options = { mode })` — keyword-only options; forwards `mode` into `postChatStream`
  - Assistant entry stamped with requested mode at submit time + reconciled with server-echoed `usage.mode` on final update (authoritative)
  - `resolvedMode` precedence: `usage.mode` → `requestedMode` → `null`
- **Toggle UI** (`rs-dashboard/src/components/ChatAssistant.jsx`):
  - 🔍 Investigate toggle button in composer row (left of textarea) with `aria-pressed`, `data-mode`, `data-testid="chat-mode-toggle"`
  - `localStorage["ai-advisor-mode"]` persistence (SSR-safe + private-browsing-safe try/catch); `readStoredMode()` helper
  - Active state (amber accent); tooltip: `Investigate: აღმოაჩინე შეუსაბამობები Excel ↔ data.json ↔ კოდს შორის`
  - Toggle disabled during `sending` (prevents mid-turn mode churn)
- **Cascade block** (`rs-dashboard/src/components/ChatMessage.jsx`):
  - `extractCascadeBrief(markdown)` — regex `/```(?:text|txt|plain)?\s*\n([\s\S]*?)```/g` + Georgian heuristic (first line `ფაილი:` + body contains `ხაზი:` + `გასწორება:`)
  - `CascadeBriefBlock` component — collapsible `<pre>` with toggle + "კოპირება" button; `navigator.clipboard.writeText` with `document.execCommand('copy')` legacy fallback
  - Block only renders when `entry.usage?.mode === "investigate"` AND the heuristic matches (prevents false positives on chat-mode code fences)
  - `data-testid`: `chat-msg-cascade`, `chat-msg-cascade-body`, `chat-msg-cascade-copy`
- **Styles** (`rs-dashboard/src/styles/components.css`):
  - `.chat-panel__btn-mode` + `--active` variant (amber `#f59e0b` theme)
  - `.chat-msg__cascade*` block (amber header, monospace body, copy button with `--ok` success state)
  - No existing styles touched
- **E2E** (`rs-dashboard/e2e/helpers/api-mock.js` + `rs-dashboard/e2e/ai-chat.spec.js`):
  - mock `buildMockReply(userMessage, mode)` + `buildMockSources(mode)` vary response by `mode`; investigate mode returns Georgian Cascade-brief with `ფაილი: dashboard_pipeline/supplier_matching.py` / `ხაზი: 142` / `გასწორება: r'^\\d{11}$' → r'^\\d{9}(\\d{2})?$'`
  - chat mode preserves legacy `ტესტური პასუხი` string byte-compatibly (8 existing tests unchanged)
  - both mocks echo `usage.mode` in response
  - +1 smoke test: `Investigate toggle sends mode=investigate and renders Cascade copy block` — asserts toggle visible + default off, click → `aria-pressed=true` + `data-mode=investigate`, POST body to `/api/chat/stream` contains `"mode":"investigate"`, assistant bubble has `data-mode=investigate`, Cascade block with body text + copy button visible, localStorage persists preference
- **Verification**:
  - `pytest tests/` → 282/282 passed (backend unchanged, as expected; Sprint 3 frontend-only)
  - `npm run lint` → clean
  - `npm run build` → clean; ChatAssistant bundle 164.31 kB → **167.59 kB** / gzip 49.67 kB → **50.74 kB** (+3.28 kB / +1.07 kB gzip for toggle + Cascade block + heuristic + clipboard fallback)
  - `npx playwright test e2e/ai-chat.spec.js` → **9/9 passed** (was 8; +1 investigate smoke; 17.5s)
- **No breaking changes**:
  - `send(message)` without options still works (mode omitted)
  - `postChat()` + `postChatStream()` still callable without mode
  - Cascade block is opt-in by server-echoed `usage.mode`; chat-mode responses render identically to pre-Sprint 3
  - Existing 8 ai-chat E2E tests pass unchanged (mock is mode-branching)
- **Investigate mode now end-to-end operational**:
  - User toggles 🔍 Investigate → preference persisted → next `send()` POSTs `mode=investigate` → backend swaps prompt to `SYSTEM_PROMPT_KA_INVESTIGATOR` → agent streams discrepancy analysis → frontend renders response + Cascade-for-copy block → one-click copy into Cascade

### AI Advisor Phase 2 — Live Dog-Food — VERIFIED ✅ (2026-04-18 02:10)
- **Method**: 3 real `POST /api/chat/stream` calls against Anthropic Claude Sonnet 4.6 via parent-venv backend (port 8000, API auth disabled for local dev). Same question across all 3: `"რამდენი მომწოდებელია data.json-ში? ერთადერთი რიცხვი მითხარი."` — expected: 1 `read_data_json` tool call + Georgian source-attributed reply
- **Result — all 3 calls returned identical reply**: `**270** (წყარო: data.json → suppliers)` with `stop_reason=end_turn` and 1 tool call each (`read_data_json({"section":"suppliers","limit":500,"columns":"minimal"})`)
- **Metrics table**:

| Call | mode | total_s | first_token_s | input_tokens | cache_create | cache_read | cached % |
|---|---|---|---|---|---|---|---|
| 1 / investigate / fresh | `investigate` ✅ | 4.52s | 4.52s | 15087 | 0 | **5832** | 28% |
| 2 / investigate / repeat | `investigate` ✅ | 3.98s | 3.98s | 15087 | 0 | **5832** | 28% |
| 3 / chat / separate cache | `chat` ✅ | 3.67s | 3.66s | 15087 | **4808** | 0 | 0% |

- **Invariants confirmed**:
  - Sprint 2 invariant — `usage.mode` server-authoritative echo works end-to-end (`investigate` vs `chat`) ✅
  - Phase 1 Polish invariant — each mode caches its own Anthropic prefix independently; investigator prefix read 5832 tokens/call while chat prefix was fresh (creation=4808) on first call ✅
  - Phase 1 Polish invariant — column pruning active (`columns: "minimal"` in tool input) ✅
  - Streaming SSE — first-token latency 3.7–4.5s (well under 5s chat MVP target) ✅
  - Tool-use loop clean exit (`stop_reason=end_turn`) ✅
  - Georgian source-attribution format respected (`**270** (წყარო: data.json → suppliers)`) ✅
- **Surfaced caveat (NOT a regression)**:
  - An earlier aggressive investigator question (`"გადაამოწმე: მომწოდებელთა რაოდენობა data.json-ში და რამდენი მომწოდებელია აქტიური suppliers.py-ში. თუ განსხვავებაა, მიაგნე მიზეზს pipeline კოდში."`) triggered 12 tool calls across 6 iterations and hit `MAX_TOOL_ITERATIONS=6` cap → polite Georgian fallback: `"⚠️ პასუხის გენერაცია შეწყდა tool-ების ლიმიტის გამო. გთხოვ, გადამოთხოვე უფრო ვიწრო კითხვით."`
  - This cap is from Phase 1 MVP (`dashboard_pipeline/ai/agent.py`), not Sprint 3 regression
  - Investigator-mode discrepancy hunts naturally want more iterations (Excel → data.json → validate → grep_code → read_source_code triangulation)
  - **Possible future polish** (out of scope for this chat): mode-dependent cap, e.g. `MAX_TOOL_ITERATIONS_INVESTIGATE=10`, while keeping chat-mode at 6
- **Cost estimate per call** (Claude Sonnet 4.6 published rates):
  - investigator cached: ~$0.047/call (15087 × $3/M + 5832 × $0.30/M + 109 × $15/M)
  - chat fresh: ~$0.063/call (creation surcharge at $3.75/M)
  - Savings from mode-namespaced cache: ~25-30% on input cost per call after prefix warms
- **Backend cleanup**: `server.py` stopped (PID 22548, port 8000 free); scratch script `_scratch_live_dogfood.py` deleted

### AI Advisor Phase 2 — UI Dog-Food — VERIFIED ✅ (2026-04-18 02:40)
- **Method**: Playwright-driven real-browser run against parent-venv backend (server.py, PID 31328, port 8000) + `npm run preview` (port 4173, strictPort). Pre-existing `dist/` from Sprint 3 build (01:47, 45 min old) reused — no rebuild. User: clicked 🔍 Investigate toggle, then sample prompt "რამდენი მომწოდებელი გვყავს ჯამში?"
- **Toggle state — verified via DOM**:
  - `aria-pressed="true"` ✅
  - `data-mode="investigate"` ✅
  - `aria-label="Investigate რეჟიმი ჩართულია — დააჭირე გამოსართავად"` ✅
  - `title` tooltip: `"Investigate: აღმოაჩინე შეუსაბამობები Excel ↔ data.json ↔ კოდს შორის"` ✅
  - `localStorage["ai-advisor-mode"] === "investigate"` ✅ (persistence contract)
- **Wire protocol — verified via captured POST body**:
  - `POST http://127.0.0.1:4173/api/chat/stream` → 200 OK
  - Body: `{"message":"რამდენი მომწოდებელი გვყავს ჯამში?","history":[],"mode":"investigate"}` ✅
  - Vite preview (port 4173) proxies `/api/*` to backend 8000 via existing `vite.config.js` proxy — confirms E2E flow works in both dev and preview
- **Response rendering — verified via `.chat-msg` DOM snapshot**:
  - Assistant bubble root `<div data-mode="investigate">` ✅ (`usage.mode` echo stamped on final entry)
  - Text begins `"🔍 შედეგი\nDashboard-ის suppliers სექციის მიხედვით, \"იოლი მარკეტს\" სულ ჰყავს:\n\n🏢 270 მომწოდებელი\n\n(წყარო: data.json → suppliers)"` — investigator prompt signature + Georgian source attribution ✅
  - `hasSources: true` — 2 sources rendered (data.json → suppliers + `Financial_Analysis/რს ზედნადები/` referenced by the investigator's Excel triangulation)
  - UsageBadge: **`29891in / 564out tok · ⚡ 5832 cached`** — Phase 1 Polish cache hit visible in production-preview UI; `⚡ N cached` sub-span only renders when `cache_read_input_tokens > 0` (confirms `UsageBadge` contract)
  - Input token count 29891 higher than Phase 2 Live Dog-Food baseline (15087) because investigator also called `read_excel_source` for cross-check on this turn (2 tool calls vs 1)
  - Cache warm: reused Phase 2 Live Dog-Food investigator prefix (5832-token stable hit across this session's earlier calls — same backend PID, Anthropic-side cache still warm)
  - **Cascade block**: NOT rendered — expected, because investigator found no discrepancy (270 consistent data.json ↔ source). Prompt contract: "no discrepancy ⇒ no Cascade brief" — respected ✅
  - `chat-msg-cascade` / `chat-msg-cascade-copy` data-testids: absent (gated correctly)
  - Screenshot captured inline via `browser_take_screenshot` — not persisted to disk (Playwright MCP inline base64 delivery)
- **Cost (this one call)**:
  - Non-cached input: 24059 tok × $3/M = $0.072
  - Cached input: 5832 tok × $0.30/M = $0.002
  - Output: 564 tok × $15/M = $0.008
  - **Total: ~$0.082/call** (higher than Live Dog-Food single-tool $0.047 because of extra `read_excel_source` triangulation)
- **Invariants confirmed end-to-end in real UI**:
  - Sprint 3: Toggle ↔ localStorage ↔ `aria-pressed` ↔ `data-mode` all in sync ✅
  - Sprint 3: `mode` body field on `/api/chat/stream` POST, omitted when chat (default) ✅
  - Sprint 3: Server-echoed `usage.mode` flows to `resolvedMode` → `data-mode` on bubble ✅
  - Sprint 3: UsageBadge renders `⚡ N cached` sub-span on cache hit ✅
  - Sprint 3: Cascade block gated correctly (no false positives when no discrepancy) ✅
  - Phase 1 Polish: mode-namespaced cache reuse across calls in same session ✅
  - Phase 1 Polish: column pruning (`columns: "minimal"`) active in tool input ✅
  - Streaming SSE: progressive text render worked (browser viewport showed typing-dots → text as delta stream arrived; final UsageBadge + sources folded in on `done` event) ✅
- **Cleanup after UI dog-food**:
  - Playwright browser closed via `browser_close`
  - Preview server (command ID 31) stopped via `Stop-Process` on port 4173 listener; `netstat` verified port 4173 free
  - Backend server (PID 31328) left running — it was launched before this session (parent venv, same `server.py -u`) and belongs to the user's dev environment; no restart needed
  - No scratch files created (sample prompt + browser interaction only)
  - Zero repo pollution (screenshot stayed inline; no artifacts written)
- **No regressions**: all Sprint 3 E2E (9/9) + unit (282/282) baseline unchanged; this chat touched only `HANDOFF.md` + `CONTEXT_HANDOFF.md` + `PLAN.md` docs (no product code modifications)

### 🆕 Waybill Arithmetic Bug-Fix — COMPLETE ✅ (2026-04-18 04:00)
- **Trigger**: user's live chat produced false totals — "Feb 27 2026 → ~7,246 ₾" and "Feb 28 2026 → 18 ₾ only" — vs Excel ground truth **7,882.68 ₾** and **2,675.86 ₾**. Earlier in the session, user had also hit HTTP 413 `RequestTooLargeError` when AI fell back to 33 MB `retail_sales`/`imported_products` dict sections.
- **Root causes**:
  1. Pipeline (`generate_dashboard_data.py` `safe_cols` dict) mapped only `გააქტიურების თარ.` → `date`; `ტრანსპ. დაწყება` (business-semantic match for "ზედნადები შემოვიდა") + `ჩაბარების თარ.` were dropped. AI literally had no date-field to filter on for the "შემოვიდა" question.
  2. No deterministic arithmetic tool — Claude was mentally summing 20+ rows from `read_data_json` output → hallucination-prone. No `compute_*` helper existed.
  3. 413 RequestTooLargeError: `waybills` was not in `ALLOWED_SECTIONS`, AI fell back to huge dict sections, and `_truncate_output` had no dict-clamp safety rail.
- **Code fixes**:
  - `generate_dashboard_data.py` (~L1100, L1189): `safe_cols` now maps all 3 RS datetime columns → `date` + `transport_start_date` + `delivery_date`; both new columns cast to ISO strings (same pattern as existing `date`)
  - `dashboard_pipeline/ai/tools.py`:
    - `ALLOWED_SECTIONS["waybills"]` — **NEW entry** with 3-date-field guidance + `compute_waybill_total` recommendation
    - `SECTION_COLUMN_PROFILES["waybills"]` — **NEW entry**: `date`, `transport_start_date`, `delivery_date`, `supplier`, `waybill_number`, `nominal_amount`, `effective_amount`, `status`, `type`
    - new `COMPUTE_WAYBILL_TOTAL_TOOL` schema inserted at `TOOL_SCHEMAS[1]` (right after `read_data_json`, high LLM visibility); params: `date` required + `date_field` enum default=`transport_start_date` + `exclude_returns` default=true + `exclude_cancelled` default=true + `amount_field` enum default=`nominal_amount` + optional `supplier`
    - `ToolDispatcher.dispatch()` routes `"compute_waybill_total"` → new function below; `_SUMMARY_KEYS` extended with `date`, `date_field`, `amount_field`, `exclude_returns`, `exclude_cancelled`, `matched_count`, `total` for trace visibility
    - new `compute_waybill_total()` function at file end (~140 lines): filters `data["waybills"]` by date substring on chosen date_field, excludes `უკან დაბრუნება` type + `გაუქმებული` status by default, sums `amount_field`, returns `{date, date_field, amount_field, matched_count, total, top_suppliers (top 10), bad_amount_rows, source}`
    - `_truncate_output()` rewritten: now clamps dict/scalar `value` sections exceeding `MAX_OUTPUT_CHARS` (32,000) to metadata summary — kills the 413 root cause
  - `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` (chat mode ONLY; investigator prompt untouched): 3 new sections added mid-prompt: (1) "ზედნადების თარიღების სემანტიკა (CRITICAL)" — mapping "შემოვიდა"→transport_start, "დარეგისტრირდა"→date, "ჩავიბარე"→delivery + mandatory clarify on ambiguity; (2) "არითმეტიკა ზედნადებებზე (CRITICAL)" — forbids mental row-summing, mandates `compute_waybill_total`; (3) "ორაზროვანი კითხვები — სავალდებულო clarify" — missing year / date-field / scope → must clarify before answering
- **Tests**: new `tests/test_compute_waybill_total.py` (26 regression tests in 7 classes: `TestToolSchemaExposure` 4 + `TestFeb27GroundTruth` 3 pinning **7,882.68 exact** + `TestDateFieldSelection` 2 + `TestInputValidation` 4 + `TestSupplierFilterAndBreakdown` 3 + `TestDispatcherRouting` 2 + `TestMonthLevelQuery` 1); `tests/test_ai_agent.py` + `tests/test_ai_investigator.py` updated for 6-tool surface; `tests/test_ai_tools.py` +7 tests for waybills allowlist/profile + `_truncate_output` dict safety rail. **pytest 308/308 passed** (was 282; +26 net; 2026-04-18 04:00 and re-verified ~13:46)
- **Data regen**: `python generate_dashboard_data.py` via parent venv, 0 errors, 0 warnings, 26 API artifacts, 13 Excel files republished; `data.json` **129.54 MB** (was 127.56 MB; +1.98 MB for 21,233 waybill rows × 2 new ISO datetime strings)
- **End-to-end verification** (throwaway `_scratch_verify_fix.py`, deleted):
  - Feb 27 + `transport_start_date` + defaults → **7,882.68 ₾ (20 rows)** ✅ exact match
  - Feb 27 + `date` (RS activation) + defaults → 7,004.06 ₾ (17 rows) — explains AI's old wrong answer
  - Feb 27 + `delivery_date` + defaults → 13,347.48 ₾ (23 rows)
  - Feb 28 + `transport_start_date` + defaults → **2,675.86 ₾ (11 rows)** ✅ matches user's Excel baseline exactly
  - Top Feb 27 suppliers: ელიზი ჯგუფი 4,593.60 ₾ (count 2), ჯიდიაი 1,077.35, ენგადი 393.06, ...
- **Intentionally NOT touched** (separate business decision, documented caveat):
  - `dashboard_pipeline/analytics_builders.py::build_supplier_aging` (~L180, L210) still uses `გააქტიურების თარ.` for "last waybill date" + aging bucket assignment
  - `dashboard_pipeline/analytics_builders.py::build_ap_monthly_trend` (~L318) still uses `გააქტიურების თარ.` for monthly AP trend grouping
  - Changing either would shift aging-bucket boundaries (30/60/90+ days) + redistribute monthly AP totals across Jan/Feb/Mar → dashboard numbers users have already internalized would change. **Requires explicit user sign-off.** Effort: 2-4 hours + rebaseline of regression tests.
- **Backend restart PENDING** — running backend (whichever process was launched before this session) still holds old `TOOL_SCHEMAS` (5 tools) + old `SYSTEM_PROMPT_KA`. Fix has **no live effect until restart** via parent venv. Post-restart verification prompts queued in next-recommended-step.
- **Scratch cleanup**: `_scratch_check_feb27.py`, `_scratch_check_feb27_full.py`, `_scratch_verify_fix.py`, `_tmp_check_feb28*.py` — all created for live diagnostics + data-quality probing, all deleted before this handoff (repo clean)
- **Invariants preserved**:
  - `TOOL_SCHEMAS` module constant stays cache-control-free (only annotated in `get_cached_tool_schemas()` deep-copy)
  - Both `/api/chat` + `/api/chat/stream` automatically expose `compute_waybill_total` (shared schemas path)
  - Investigator prompt untouched → zero Sprint 1/2/3 regression risk
  - File-system tool allowlists unchanged (`compute_waybill_total` operates on cached in-memory data.json dict, doesn't need new allowed roots)
  - All pre-existing 282 tests still pass unchanged alongside 26 new; no test weakened or deleted (user rule respected)
- **Open strategic discussion** (no decision made this session):
  - User's hard ask: "მე მჭირდება სტრატეგიები" — not data-lookup, but actionable recommendations (drop product X, switch supplier Y, adjust margin Z)
  - User's derivative critique: "თუ AI ჭკვიანია, თვითონ უნდა გაარკვიოს — რატო წერ რა უნდა გააკეთოს"
  - Cascade's open recommendation: after backend restart, probe AI with a strategy-prompt against existing `data.json` sections BEFORE building any new pipeline. If AI already delivers → prompt+tool polish only. If not → concrete scope justification for product-margin pipeline (~16-22 hours estimated).
  - Provider-migration options (Gemini API / Kimi K2.5 via OpenRouter) discussed but user explicitly de-prioritized in favor of "intelligence > cost"

### 🆕 AI Genius Partner Master Plan v2.1 — APPROVED ✅ (2026-04-18 საღამოს)
- **Trigger**: user's explicit ask — "რას შეცვლი, ანუ ჩემთვის ყველაზე მნიშვნელოვანი არის AI ფუნქციები სრულყოფილი იყოს, რაც არის მითითებულზე 10 ჯერ მეტი შეეძლოს" — i.e., expand the AI feature scope beyond v2.0's 47 features
- **Cascade's response**: structured "3 fundamental + Phase-by-Phase extensions + Parking Lot" proposal; user voted A (fundamental + top-5); Cascade auto-picked implementation order
- **v2.0 → v2.1 delta** (in `AI_GENIUS_PARTNER_PLAN.md`):
  - 🆕 **Phase 0A — Critical Foundation** (3 fundamental changes): Calculator Enforcement (forbid mental arithmetic >3 numbers) + Self-Critique Loop (3 internal checks before output) + Today's Pulse (automatic preamble with date/POS/cash/risks)
  - 🆕 **Phase 1.11** — RS.ge + ფრენჩაიზი business context (VAT 18%, ე-ინვოისი, "იოლი მარკეტი" royalty rules)
  - 🆕 **Phase 1.12** — Multi-Store DNA (ოზურგეთი urban 3-POS vs დვაბზუ rural 2-POS, different peak / customer / mix)
  - 🆕 **Phase 2.11** — Dead Stock + Salvage Plan (90+ day unmoved SKUs → liquidation plan)
  - 🆕 **Phase 2.12** — Supplier Negotiation Prep (1-pager: my volume + payment history + comparables)
  - 🆕 **Parking Lot** — ~40 features deferred for future iteration (full list in plan `§ Parking Lot`)
- **Timeline**: 4.5-5 weeks → **5.5-6 weeks** (Phase 0A adds 2-3 days)
- **Cost**: unchanged ($40-95/month heavy; Phase 0A extras ≈ 0 ₾)
- **v2.0 superseded**; old plan Phase 3 Daily Briefing REMAINS DEPRECATED (user rejected push model)

### 🆕 AI Advisor Phase 0A — Critical Foundation — COMPLETE ✅ (2026-04-18 23:00)
- **Preview step**: `PHASE_0A_PREVIEW.md` created with Before/After examples for each of the 3 changes; user approved without edits via "კაი დაიწყე და გზად რაც შეგხვდება გასასწორებელი გაასწორე"
- **Cascade defaults chosen**:
  - 0A.1: all 3 changes implemented
  - 0A.2 Self-Critique: **variant A** (inline, 0 extra API cost; can upgrade to variant B later if quality insufficient)
  - 0A.3 Today's Pulse: **store-level granularity** (ოზ. + დვ. separately; POS-level deferred to Phase 2.4)
- **Code fixes**:
  - `dashboard_pipeline/ai/tools.py`:
    - new `COMPUTE_TOOL` schema inserted at `TOOL_SCHEMAS[2]` (right after `compute_waybill_total`, high LLM visibility); params: `operation` enum (`sum`/`avg`/`min`/`max`/`count`/`pct`/`growth`/`diff`) + `numbers` array required + optional `round_digits` default 2 + optional `label`
    - `ToolDispatcher.dispatch()` routes `"compute"` → new `compute()` function; `_SUMMARY_KEYS` extended with `operation`, `input_count`, `result`, `formula`, `label` for trace visibility
    - new `compute()` function (~120 lines): strict input validation (bool rejected even though `isinstance(True, int)`, zero-division guarded for pct/growth, exactly-2-operands enforced for pct/growth/diff), returns `{operation, input_count, result, formula, source}` + optional `label`
  - `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` (chat mode ONLY; investigator untouched):
    - old "არითმეტიკა ზედნადებებზე" section replaced with broader "არითმეტიკა — ზოგადი წესი" documenting BOTH `compute_waybill_total` (domain) AND new generic `compute` (8 operations enumerated with `pct`/`growth`/`diff` semantics); threshold "3-ზე მეტი რიცხვის ოპერაცია → tool აუცილებელია" explicit
    - 🆕 "თვითკრიტიკა (CRITICAL) 🪞" section: 3 mandatory internal questions (რა ფაქტი არ გადავამოწმე / რაში ვარ გაურკვეველი / რა ლოგიკური პრობლემა) + mandatory output structure (📊 ფაქტი / ⚠️ გაურკვეველი / 🎯 რეკომენდაცია); explicit instruction to skip "⚠️ გაურკვეველი" when everything is tool-verified (false-skepticism is as harmful as false-certainty); explicit "never expose the internal checks in output" rule
  - 🆕 `dashboard_pipeline/ai/today_context.py` — new module (~280 lines):
    - `build_today_context(data_loader, today=None) -> Dict` — returns `{date, weekday (Georgian), yesterday_pos, cash_forecast_7day, top_risks, notes}`; NEVER raises (broken data_loader → graceful "ვერ წავიკითხე" breadcrumb in `notes[]`)
    - `format_today_block(ctx) -> str` — XML-tagged Georgian block `<TODAY>...</TODAY>` ready for prompt injection; skips empty sections (never shows "0 ₾" as if it were real)
    - `build_today_block(data_loader)` — one-shot convenience wrapper
    - Heuristics: POS drop ≥ 25% vs 7-day avg surfaces as risk; supplier overdue_60+ ≥ 5,000 ₾ flagged; overdue > current signals cash strain; max 3 risks
    - Also exposes `GEORGIAN_WEEKDAYS` + `STORE_LABELS` for downstream test fixtures
  - `dashboard_pipeline/ai/prompts.py::build_system_prompt_blocks(..., today_block=None)` — new optional `today_block` param; when set, appended as a SECOND system content block WITHOUT `cache_control` (base prompt + tools prefix stays cacheable; today block varies per session, cheap to resend)
  - `dashboard_pipeline/ai/agent.py`:
    - `AIAgent.__init__(..., today_context_enabled=True)` — new kwarg (default True, override to False for unit tests that pin single-block system)
    - new `AIAgent._maybe_today_block()` helper: wraps `build_today_block(data_loader)` in broad `try/except` so a broken today_context never crashes chat; returns `None` on disable / failure / empty string
    - `chat()` + `chat_stream()` both pass `today_block=self._maybe_today_block()` into `build_system_prompt_blocks(...)` — identical injection on both paths
- **Tests**: 73 new pytest cases across 3 new files:
  - `tests/test_ai_compute.py` — **35 cases** (schema exposure 4 + operations 10 + rounding 4 + label 2 + validation 11 + dispatcher 3 + parity with waybill fix 1)
  - `tests/test_ai_today_context.py` — **23 cases** (happy path 6 + defensive 5 + top risks 3 + format 5 + agent integration 4)
  - `tests/test_ai_self_critique_prompt.py` — **15 cases** (self-critique directive 5 + calculator directive 5 + investigator prompt preserved 3 + end-to-end 2)
  - updated `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` (6 → 7 tool count; added `"compute"` assertion)
  - updated `tests/test_ai_agent.py::TestChatMode::test_investigate_mode_preserves_tool_surface` (expected tool set now includes `"compute"`); helpers `_run_once`, `_capture_system`, `_run_stream`, `test_prompt_caching_wired_on_stream` all pass `today_context_enabled=False` to preserve deterministic single-block assertions
  - **pytest 381/381 passed** (was 308; +73 net; run 2026-04-18 ~23:00)
- **Invariants preserved**:
  - `TOOL_SCHEMAS` module constant stays cache-control-free (only annotated in `get_cached_tool_schemas()` deep-copy)
  - Both `/api/chat` + `/api/chat/stream` automatically expose new `compute` tool (shared schemas path)
  - Investigator prompt untouched → zero Sprint 1/2/3 regression risk
  - Self-critique + calculator directives land in chat mode ONLY; investigator keeps its Sprint 2 "🔍 აღმოჩენა / 📊 შედარება / 🔎 მიზეზი / 📋 Cascade-ისთვის" structure
  - File-system tool allowlists unchanged (`compute` is pure arithmetic on LLM-provided numbers — no I/O)
  - All pre-existing 308 tests still pass unchanged alongside 73 new; no test weakened or deleted (user rule respected)
  - Today's Pulse on `today_context_enabled=False` path produces EXACTLY the pre-0A behavior (single cached system block) — back-compat verified
- **Backend restart still PENDING** — same `server.py` process that has pre-Waybill-fix code also has pre-0A code; BOTH fixes go live in one restart
- **Not yet done** (scope limited to 0A only):
  - Phase 0B Genius Core (Extended Thinking, ChromaDB, Web Search, RAG, Multi-hypothesis, Forecasting, Sub-agent Debate) — 4-5 days
  - Phase 1.11 RS.ge context, Phase 1.12 Multi-Store DNA — part of Phase 1
  - Phase 2.11 Dead Stock, Phase 2.12 Supplier Negotiation Prep — part of Phase 2
  - UI widget for Today's Pulse (Dashboard `🌅 Today's Pulse` widget in Parking Lot)

### 🆕 AI Advisor Phase 0B Sprint 2 — Prophet Forecasting — COMPLETE + LIVE VERIFIED ✅ (2026-04-19 18:42)

- **Scope gate**: user approved `PHASE_0B_SPRINT2_PREVIEW.md` (plain-Georgian Before/After, analogous to Phase 0A preview) via the 4 `🔵` recommended defaults (Sprint 2 start / 3-month horizon / store-alias combo / revenue-only scope)

- **Dependencies** (installed to parent venv at `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv`):
  - `prophet==1.3.0` (pre-built `prophet-1.3.0-py3-none-win_amd64.whl` — **no cmdstan compile required**, ~2 min install)
  - `statsmodels==0.14.6`
  - Transitive pulls: `scipy 1.17.1` (37.3 MB), `matplotlib 3.10.8` (8.3 MB), `cmdstanpy 1.3.0`, `holidays 0.94`, `patsy 1.0.2`, `contourpy 1.3.3`, `kiwisolver 1.5.0`, `pillow 12.2.0`, `pyparsing 3.3.2`, `fonttools 4.62.1`, `cycler 0.12.1`, `tqdm 4.67.3`, `stanio 0.5.1`, `importlib_resources 7.1.0`
  - `requirements.txt`: `prophet>=1.1` + `statsmodels>=0.14` moved out of the commented "Phase 2+ not yet active" block into a new "Phase 0B Sprint 2 — active" block with a LAZY-import note explaining that a failed Prophet install does NOT break the rest of the pipeline

- **New module** `dashboard_pipeline/ai/forecasting.py` (~480 lines):
  - `forecast_revenue(data_loader, *, horizon_months=None, store=None)` — main tool entry point
  - Constants: `DEFAULT_HORIZON_MONTHS=3`, `MIN_HORIZON_MONTHS=1`, `MAX_HORIZON_MONTHS=12`, `MIN_HISTORY_MONTHS=12`, `SUPPORTED_STORES=("total","ოზურგეთი","დვაბზუ")`, `SOURCE_LABEL="data.json:monthly_pnl (prophet+arima ensemble)"`
  - `_STORE_ALIASES` — accepts both Latin (`ozurgeti` / `dvabzu`) and Georgian (`ოზურგეთი` / `დვაბზუ` / `ჯამი` / `ყველა`) + whitespace/empty → `total`; case-insensitive
  - `_resolve_store()` + `_resolve_horizon()` — strict validation with Georgian error messages (not just English)
  - `_extract_revenue_series(monthly_pnl, store)` — reads `row["total"]["pos_income"]` for `total`, `row["objects"][store]["pos_income"]` for named stores; silently skips malformed rows (robust to `objects: "not-a-dict"` or missing store); clamps to `MIN_HISTORY_MONTHS=12` (returns partial history for caller's error message)
  - `_next_month()` / `_future_months()` — pure string month arithmetic, December → January rollover tested
  - `_yoy_growth_pct()` — `sum(last_12) / sum(prev_12) × 100 − 100`; returns `None` when history < 24 months or prev-12 sum is zero (prevents misleading "infinite growth" when a store was freshly opened)
  - `_load_prophet()` + `_load_arima()` — LAZY import helpers wrapped in broad `try/except`; return `None` on `ImportError` or sub-dep errors; called only from inside `forecast_revenue` so import-time side effects never reach the chat pipeline when Prophet is absent
  - `_run_prophet()` — Prophet 1.3.0 `fit(df)` + `make_future_dataframe(periods, freq="MS")` + `predict(future)`; config: `yearly_seasonality=True`, `weekly_seasonality=False`, `daily_seasonality=False`, `interval_width=0.95`; `tail(horizon)` extracts the forecast rows
  - `_run_arima()` — statsmodels `ARIMA(order=(1,1,1)).fit().get_forecast(steps)` + `conf_int(alpha=0.05)`; deliberately NO `pmdarima` auto-selection (robust default for monthly retail + one fewer heavy dep); `_ci_at()` helper handles both numpy 2-D arrays and pandas DataFrames (statsmodels returns the latter in recent versions)
  - `_ensemble()` — both engines succeed → baseline = arithmetic mean; bounds WIDEN via `max(upper)` / `min(lower)` (ensemble never narrower than most-cautious engine); one engine → its rows verbatim; both `None` → `[]`; mismatched lengths → fall through to Prophet-only (length mismatch is a model bug, not safe to splice)
  - `_round_rows()` + `_safe_round_nonneg()` — 2-decimal rounding + **clamp ≥ 0** on every field (baseline/optimistic/pessimistic). Rationale: retail revenue is physically non-negative; statistical CI lower bounds that drop below zero are a model artifact (the 95% interval extrapolating past the physical zero floor), not a prediction. Without this, the LLM could quote "პესიმისტური −6,832 ₾" to the user, which is both confusing and factually impossible. Non-finite / non-numeric inputs collapse to `None` so JSON stays encodable.
  - Stable return contract: `{source, store, horizon_months, history_months, history_start, history_end, last_12_months_total, yoy_growth_pct, engines_used, forecast[{month, baseline, optimistic, pessimistic}], notes[]}` or `{error, hint}` when something upstream fails
  - `notes[]` always seeded with 2 mandatory caveats ("მოდელი ვერ ხედავს მოულოდნელ შოკებს" + "±10-15% variance expected"); when only one engine succeeds, inserts a third degradation warning at position 0 ("მხოლოდ {engine} იყო ხელმისაწვდომი — confidence ცოტა უფრო ფართოა")

- **`dashboard_pipeline/ai/tools.py`** changes:
  - new `FORECAST_REVENUE_TOOL` schema inserted at `TOOL_SCHEMAS[3]` (compute-family cluster — after `compute`, before investigator tools); `store` enum `["total", "ოზურგეთი", "დვაბზუ"]`; `horizon_months` integer min=1 max=12; `required=[]` (both params optional); `additionalProperties=False`; description explicitly forbids use for historical questions
  - `ToolDispatcher.dispatch()` routes `"forecast_revenue"` → lazy-import `dashboard_pipeline.ai.forecasting.forecast_revenue` inside the `elif` branch, passing `data_loader=self._get_data` (Prophet sees the same cached `data.json` snapshot as every other tool call in the same chat turn — no duplicate reads)
  - `_SUMMARY_KEYS` extended with: `store`, `horizon_months`, `history_months`, `history_start`, `history_end`, `last_12_months_total`, `yoy_growth_pct`, `engines_used` — dispatcher traces surface engines + history span to the sources list without shoveling the full forecast table
  - **TOOL_SCHEMAS length: 7 → 8** (new total): `read_data_json`, `compute_waybill_total`, `compute`, `forecast_revenue`, `read_source_code`, `grep_code`, `read_excel_source`, `validate_vs_source`

- **`dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA`** (chat mode ONLY — investigator prompt untouched):
  - 🆕 **"🔮 პროგნოზირება (CRITICAL — Phase 0B Sprint 2)"** section placed between "არითმეტიკა — ზოგადი წესი" and "თვითკრიტიკა"
  - trigger keyword list: `მომავალი` (month/quarter/year), `პროგნოზი`, `რა მოხდება`, `რამდენი იქნება`, `მომდევნო N თვე`, `სეზონური ტრენდი`, `როდის იქნება პიკი`, `cash-planning`, `რამდენი შემოსავალი უნდა ველოდო`
  - explicit "when NOT to use" anti-trigger list: past questions (`read_data_json` / `compute_waybill_total` route), "დღევანდელი" (today) cue → `<TODAY>` block, horizons > 12 months → refuse with explicit wording ("Prophet 1-12 თვეზე საიმედოა; 2-3 წელიწადი extrapolation-ია, ნუ ვენდობი")
  - mandatory output structure: (1) Markdown ცხრილი 3 ცხოვრების-სვეტით (თვე / ბაზისი / ოპტ. / პეს. + `₾` unit) + (2) 1-2 trend sentences (YoY ზრდა, სეზონი) + (3) ALL `notes` items — **never skip** (user must know the model's limits) + (4) inline source `(წყარო: data.json → monthly_pnl, prophet+arima ensemble)`
  - `store` param guidance: default `total`; when user says "ცალცალკე" → **two invocations** (Ozurgeti + Dvabzu) with two tables in one reply; when user names one store → pass that store directly

- **Tests**: new `tests/test_ai_forecasting.py` — **80 regression cases in 10 classes**:
  - `TestForecastToolSchema` 7 — registration + index 3 + length 8 + shape + store enum + description mentions prophet/arima + explicit "NEVER use for historical" guardrail
  - `TestResolveStore` 12 — None/empty/whitespace → total; Georgian canonical + Latin aliases; unknown → Georgian error (includes the string user passed); non-string type → error
  - `TestResolveHorizon` 7 — default 3, valid [1, 3, 6, 12] accepted, 0 / negative / above-max / non-int-string reject, numeric string accepted via int coercion
  - `TestExtractRevenueSeries` 10 — total path + per-store paths, empty pnl / non-list / short-history rejects, malformed row skipped (not fatal), missing store block skipped per-row, NaN/non-finite skipped, out-of-order rows sorted chronologically, exactly-MIN_HISTORY (12) months accepted
  - `TestMonthArithmetic` 5 — mid-year, December rollover to Jan+year, future sequence, year-rollover sequence, zero count returns empty
  - `TestYoYGrowth` 5 — short history → None, zero prev → None, flat series → 0, +10%, -20%
  - `TestEnsemble` 5 — prophet-only returns Prophet verbatim, arima-only returns ARIMA verbatim, both-None returns empty list, both averaged (baseline = mean, bounds widened to `max/min`), mismatched-lengths falls through to Prophet (defensive)
  - `TestForecastRevenueHappyPath` 9 — default horizon 3, custom horizon 6, store=`ოზურგეთი` passthrough, Latin `"ozurgeti"` alias normalized to Georgian canonical, 2dp rounding, **non-negative clamp verified by injecting Prophet stub returning `yhat_lower=-50`** (result must be 0), ensemble baseline = (1000 Prophet + 500 ARIMA) / 2 = 750, YoY present for 30-month history / absent for 12-month, last_12_months_total = tail sum
  - `TestForecastRevenueErrors` 8 — bad horizon, unknown store, data_loader raises FileNotFoundError → captured Georgian message, data_loader returns non-dict → error, missing `monthly_pnl` key → error, short history → error mentions `MIN_HISTORY_MONTHS=12`, both engines unavailable → error + hint `"pip install prophet statsmodels"`, Prophet-only + ARIMA-only degradation paths
  - `TestDispatcherRouting` 3 — `ToolDispatcher.dispatch("forecast_revenue", ...)` reaches forecasting module; call trace surfaces `engines_used` + `horizon_months`; unknown-store error forwarded through dispatcher
  - `TestPromptWiring` 2 — chat prompt mentions `forecast_revenue` + `🔮` + at least one trigger keyword; investigator prompt does NOT include the forecast section (Sprint 2 scope guard)
  - `TestModuleExports` 4 — `SUPPORTED_STORES` tuple, horizon bounds, `MIN_HISTORY_MONTHS=12`, `SOURCE_LABEL` contains `data.json` + `monthly_pnl`
  - `Prophet` / `statsmodels` never actually installed during test runs — both engines mocked via `monkeypatch.setattr(forecasting, "_load_prophet", lambda: _FakeProphet)` (same for ARIMA). Fake classes live in the test file and emit deterministic pandas DataFrames so test runs are reproducible across machines
  - **2 existing tests updated for the 8-tool surface**:
    - `tests/test_ai_agent.py::TestChatMode::test_investigate_mode_preserves_tool_surface` — expected set now includes `forecast_revenue`
    - `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` — `len(TOOL_SCHEMAS) == 8` + `forecast_revenue` in names assertion
  - **pytest 548/548 passed** (was 468; +80 new forecasting + 2 existing updated for 8-tool surface; 0 tests weakened or deleted)

- **Live verification** (2026-04-19 18:30 via throwaway `_scratch_forecast_smoke.py` — gitignored, deleted after use):
  - `data.json` at `rs-dashboard/public/data.json` = **135.84 MB**, 44 months of monthly_pnl (2022-06 → 2026-02)
  - 3 scenarios exercised against real Prophet + ARIMA (not stubs):
    
    | scope | engines | horizon | last_12m (₾) | YoY | first-row baseline (₾) | duration |
    |---|---|---|---|---|---|---|
    | TOTAL | prophet+arima | 3 | 1,897,584 | **+18.2%** | 134,944 (2026-03) | 9.17s cold |
    | ოზურგეთი | prophet+arima | 6 | 647,443 | **−12.47%** 📉 | 57,643 (2026-03) | 1.23s warm |
    | დვაბზუ | prophet+arima | 3 | 1,024,883 | **+45.14%** 📈 | 75,684 (2026-03) | 1.22s warm |
  - Non-negative clamp verified **live** on real Prophet output: Ozurgeti 2026-07 (was −3,518), 2026-08 (was −6,833) both clamped to 0; Dvabzu 2026-05 (was −6,832) clamped to 0
  - Prophet wall-clock: first call 9.17s (cmdstan backend JIT + pandas warm-up), subsequent ~1.2s each — well under any chat UX budget
  - Prophet / cmdstan emit harmless `"Importing plotly failed. Interactive plots will not work."` + `"Chain [1] start processing / Chain [1] done processing"` + statsmodels `"Non-stationary starting autoregressive parameters"` warnings — non-fatal, expected with ARIMA(1,1,1) on this series

- **Backend restart** (2026-04-19 18:36):
  - old PID **30788** stopped via `Stop-Process -Id 30788 -Force`; `Get-NetTCPConnection -LocalPort 8000 -State Listen` confirmed port 8000 free
  - new PID **19208** started via `$env:AI_ENABLE_THINKING='true'; & "…\venv\Scripts\python.exe" -u server.py` (non-blocking, `WaitMsBeforeAsync=10000`)
  - Uvicorn log: `Loaded suppliers.json (mtime=1776608895.5255394)` + `Adding job tentatively` + `Added job "_run_pipeline" to job store "default"` + `Scheduler started` + `Scheduled pipeline refresh every 30 min` + `Application startup complete` + `Uvicorn running on http://127.0.0.1:8000`
  - `/api/status` → 200 OK; `data_age_seconds: 533`; pipeline state: idle
  - Smoke import confirms `TOOL_SCHEMAS` length 8 + `forecast_revenue` present + server imports clean

- **User UI dog-food** (2026-04-19 18:40 — natural chat in the browser, no Playwright):
  - user prompt: _"მომდევნო 3 თვის შემოსავალი რა იქნება?"_
  - AI narrated STOP-CHECK pass-through (Check 1 წელი: forward-looking, not needed ✅; Check 2 ზედნადები: N/A; Check 3 scope: store not mentioned, default=total ✅)
  - AI invoked `forecast_revenue(horizon_months=3, store=<unset>)` via tool-use; server logs one `POST /api/chat/stream` call
  - Assistant bubble rendered matching scratch-script values byte-for-byte:
    - `2026-03 134,944 ₾ | 182,032 ₾ | 63,878 ₾`
    - `2026-04 141,994 ₾ | 206,914 ₾ | 38,994 ₾`
    - `2026-05 147,679 ₾ | 225,953 ₾ | 19,955 ₾`
  - AI followed prompt contract: **🔮 ცხრილი** with `₾` units + YoY +18.2% sentence + last-12m sum 1,897,584 ₾ + ALL `notes` caveats (POS, ვალუტა, mitigation ±10-15%, broad CI interpretation) + inline source `(წყარო: data.json → monthly_pnl, prophet+arima ensemble — 44 თვის ისტორია)`
  - No hallucinated numbers, no missed caveats, table format correct

- **Invariants preserved**:
  - `TOOL_SCHEMAS` module constant stays cache-control-free (tests assert); annotate only via `get_cached_tool_schemas()` deep-copy
  - Both `/api/chat` + `/api/chat/stream` automatically expose `forecast_revenue` (shared schemas path)
  - Investigator prompt (`SYSTEM_PROMPT_KA_INVESTIGATOR`) untouched → zero Sprint 1/2/3 regression risk
  - File-system tool allowlists unchanged (`forecast_revenue` operates on the cached in-memory `data.json` dict, doesn't need new allowed roots)
  - All pre-existing 468 tests still pass unchanged alongside 80 new; no test weakened or deleted (user rule respected)
  - Lazy imports in `forecasting.py` + `tools.py` dispatcher mean a broken Prophet wheel does NOT crash the chat pipeline — it surfaces a Georgian error + install hint only when the user actually asks for a forecast

- **Scratch cleanup**:
  - `_scratch_forecast_smoke.py` created for live 3-scenario verification, deleted after evidence gathering (gitignored `_scratch_*.py` pattern)
  - No repo pollution

---

### 🆕 AI Advisor Phase 0B Sprint 3 — ChromaDB Semantic Memory + RAG — COMPLETE ✅ (2026-04-19 19:40)

- **Scope gate**: `PHASE_0B_SPRINT3_PREVIEW.md` drafted in plain Georgian (Before/After format mirroring Sprint 2 preview); user approved via the 4 `🔵` recommended defaults (start Sprint 3 / local ChromaDB / save only "important" entries / index only `Financial_Analysis/` Excel for now / decision-journal deferred to Sprint 4)

- **Dependencies installed to parent venv** (`C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`):
  - `chromadb==1.5.8` (pre-built `chromadb-1.5.8-cp39-abi3-win_amd64.whl`)
  - `sentence-transformers==5.4.1`
  - Transitive: `torch 2.11.0`, `transformers 5.5.4`, `huggingface-hub 1.11.0`, `tokenizers 0.22.2`, `safetensors 0.7.0`, `onnxruntime 1.24.4`, `opentelemetry-* 1.41.0/0.62b0`, `kubernetes 35.0.0`, `bcrypt 5.0.0`, `pypika 0.51.1`, `pydantic-settings 2.13.1`, `pybase64 1.4.3`, `mmh3 5.2.1`, `flatbuffers 25.12.19`, `httptools 0.7.1`, `watchfiles 1.1.1`, `websockets 16.0`, `regex 2026.4.4`, `joblib 1.5.3`, `scikit-learn 1.8.0`, `mpmath 1.3.0`, `sympy 1.14.0`, `networkx 3.6.1`, `tenacity 9.1.4`, `requests-oauthlib 2.0.0`, `oauthlib 3.3.1`, `urllib3 2.6.3`, `requests 2.33.1`, `charset-normalizer 3.4.7`, etc.
  - `requirements.txt`: `chromadb>=0.5` + `sentence-transformers>=3.0` moved out of the commented "Phase 2+ not yet active" block into a new "Phase 0B Sprint 3 — active" block with a LAZY-import note explaining that a failed install does NOT break the rest of the pipeline (the new tools surface a Georgian error + `pip install` hint instead)

- **New module** `dashboard_pipeline/ai/memory.py` (~610 lines):
  - `MemoryStore` class wraps a `chromadb.PersistentClient` (default persist dir `ai_vectors/` under project root, already gitignored) + 2 collections (`chat_memory` and `project_index`) sharing one multilingual MiniLM embedding function (`paraphrase-multilingual-MiniLM-L12-v2` — ~120 MB download on first use, cached in HF cache)
  - `save_memory(summary, *, tags, source, project_root, extra_metadata)` — validated + bounded; `_coerce_summary` enforces `MIN_SUMMARY_CHARS=10` / `MAX_SUMMARY_CHARS=8000`; auto-IDs `<source>_<uuid>` so repeat calls with explicit `memory_id` are idempotent (upsert semantics)
  - `recall_context(query, *, limit, source, tags, project_root)` — cosine-distance ranked top-K hits across both collections by default; `source="chat"` / `"excel"` filters narrow scope; `tags=[...]` translates to ChromaDB `$and` + `$contains` `where` filter; `_coerce_query` caps length at `MAX_QUERY_CHARS=500`; `_coerce_limit` clamps `[1, 50]` (default 5); per-collection `count()` guard prevents empty-collection crashes
  - `index_project_files(file_specs, *, project_root, on_progress, replace, chunk_chars, chunk_overlap)` — bulk indexer for the project_index bucket; deletes existing chunks per `path` when `replace=True`; chunks via `_chunk_text` (default 1200 chars + 150 overlap); hard cap `MAX_INDEX_CHUNKS_PER_FILE=5000` per file
  - `_normalise_tag(s)` + `_normalise_tags(value)` — lowercase + snake_case + `:` namespace preservation; cosmetic post-processing collapses runs of underscores and strips `_` adjacent to `:` so `"Topic: Cash Flow!"` becomes `"topic:cash_flow"` (cleaner than the raw regex output)
  - `_load_chromadb()` + `_load_embedding_function()` — LAZY imports; return `None` on `ImportError`/sub-dep errors (graceful degradation); broken install → `MemoryStoreUnavailable` propagates up as a Georgian error + `pip install` hint
  - Process-level singleton `get_memory_store(project_root)` cached per persist-dir + `reset_memory_store()` for tests / reload scenarios
  - Stable JSON-safe return contract: `{ok: True, memory_id, stored_chars, tags, source, collection}` for save; `{source, query, limit, result_count, results: [{id, rank, distance, summary, tags, source, created_at, collection, metadata}, ...]}` for recall; `{error, hint}` for any failure

- **`dashboard_pipeline/ai/tools.py`**:
  - `RECALL_CONTEXT_TOOL` schema inserted at `TOOL_SCHEMAS[4]` (right after `forecast_revenue`); `query` required, `limit` 1–50 with min/max validation, `source` enum `["chat", "excel"]`, optional `tags` array; description tells the LLM **when to call** (`გახსოვს`, `3 კვირის წინ`, `გასულ წელს`) and **when NOT** (current period → `read_data_json`/`compute_waybill_total`; future → `forecast_revenue`)
  - `SAVE_MEMORY_TOOL` schema inserted at `TOOL_SCHEMAS[5]`; `summary` required (10–8000 chars), optional `tags` (snake_case + `:` namespacing recommended), `source` enum restricted to `["chat"]` at tool level (project-index entries only get written by `index_project_files.py`, never directly by the chat); description distinguishes meaningful chat-end summaries from idle chit-chat
  - `ToolDispatcher.dispatch()` routes `"recall_context"` and `"save_memory"` via LAZY `from dashboard_pipeline.ai.memory import ...` (matches the `forecast_revenue` pattern — broken install never crashes the dispatch loop)
  - `_SUMMARY_KEYS` extended with `memory_id`, `stored_chars`, `tags`, `collection`, `query`, `limit`, `result_count`, `files`, `chunks` so traces surface useful metadata without dumping the full results array
  - **TOOL_SCHEMAS length: 8 → 10** (new total): `read_data_json`, `compute_waybill_total`, `compute`, `forecast_revenue`, `recall_context`, `save_memory`, `read_source_code`, `grep_code`, `read_excel_source`, `validate_vs_source`

- **`dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA`** (chat mode ONLY — investigator prompt untouched):
  - 🆕 **"🔎 სემანტიკური მეხსიერება (CRITICAL — Phase 0B Sprint 3)"** section placed between "🔮 პროგნოზირება" and "თვითკრიტიკა"
  - trigger keyword list for `recall_context`: `გახსოვს?`, `ჩვენი წინა საუბარი`, `ბოლო ჩატში`, `N კვირის/თვის წინ`, `მე რა დაგპირდი`, `რა გადავწყვიტე`, `რა შევთანხდით`, `გასულ წელს`, `2024/2025 ოქტომბერში რა იყო`
  - explicit "when NOT to use" anti-trigger list: current period → `read_data_json`; today → `<TODAY>` block; future → `forecast_revenue`; full Excel rows + headers → `read_excel_source`
  - mandatory "how to use the result" rules: cite `matched_id` inline (`(წყარო: მეხსიერება chat_alpha_2026_03_23 — 23 მარტი 2026)`), refuse to invent ("მეხსიერებაში მსგავსი საუბარი ვერ ვიპოვე") when `result_count==0` or distance > 0.7, prefer fresher hits (`created_at`) when distance ties
  - `save_memory` policy: write 2-5 sentence Georgian summary at meaningful chat ends (decisions, recommendations, observations, promises); namespace tags (`kind:decision`/`kind:promise`/`kind:observation`/`kind:recommendation` + `supplier:<name>`/`topic:<area>`); explicit DO-NOT-SAVE list (greetings, single-fact lookups, anything 1-second from `data.json`)
  - **Sprint 3 lives in chat prompt only** — `SYSTEM_PROMPT_KA_INVESTIGATOR` byte-unchanged, no recall/save references leak into investigate mode

- **New script** `index_project_files.py` (root, ~330 lines) — one-time Excel/CSV indexer:
  - Walks `Financial_Analysis/` recursively; supports `.xls` / `.xlsx` / `.xlsm` (via `xlrd` + `openpyxl`) and `.csv` (via pandas)
  - Auto-tags: `excel`/`csv` + `category:waybills|sales|bank|products` (mapped from folder name) + `year:YYYY` (extracted from file name like `01--2025.xls` or `2024.xlsx`)
  - Conservative defaults: `--max-rows 2000`, `--max-sheets 5`, `--skip-larger-than 80MB`; `--full` flag bypasses every cap; `--replace` drops old chunks per path before re-indexing; `--dry-run` previews file list without indexing
  - Lazy `from dashboard_pipeline.ai.memory import ...` so the script imports even if Chroma is missing (clean error surface)
  - Dry-run on this workspace: **26 candidate files** (5 bank xlsx 2022–2026 + 7 sales xlsx 2023–2026 + 5 waybills xls 2022–2026 + 4 products csv 2023–2026 + 1 manual_payments.csv + 4 BOG bank xlsx 2023–2026); largest `გაყიდული პროდუქტები სოფ დვაბზუ\2025 ნავაჭრი დვაბზუ.xlsx` 43.5 MB

- **Live save→recall verification** (this session, no live Anthropic call yet):
  - Single-file mini-run `python index_project_files.py --limit 1 --max-rows 100` indexed `manual_payments.csv` → 5 chunks vectorized in 0.2s, `ai_vectors/` directory created on disk
  - Scratch one-liner: `save_memory("Alpha-ს ვალი 23,000 ლარი — 45 დღე გადაცილებული...", tags=["kind:decision", "supplier:alpha"])` → returned `chat_996e...58815` id; immediate `recall_context("Alpha ვალი ვაჭრობა")` returned the saved chunk as rank 1 with cosine distance 0.486; `counts: {chat_memory: 1, project_index: 5}`
  - Embedding model `paraphrase-multilingual-MiniLM-L12-v2` downloaded successfully on first use (HF Hub HTTP 200, weights loaded into BertModel; `position_ids` UNEXPECTED is the standard sentence-transformers warning, safe to ignore)

- **Tests** (all green this chat):
  - `tests/test_ai_memory.py` (NEW — **85 cases** in 13 classes):
    - `TestMemoryToolSchemas` (10) — registration, position 4/5, count = 10, schema shape (required fields, source/limit enums, additionalProperties=False), description content (Georgian triggers + when-to/when-not), module exports surface
    - `TestNormaliseTags` (7) — None / list dedupe+sort / comma string / unsafe chars collapsed cleanly / garbage shapes don't raise / outer underscores stripped / empty→None
    - `TestCoerceSummary` (5) — None / non-string / too-short / oversized truncated with ellipsis / happy path strips outer whitespace
    - `TestCoerceQuery` (4) — None / empty / oversized truncated / Georgian happy path
    - `TestCoerceLimit` (5) — None default 5 / garbage default / below min clamped / above max clamped / in-range
    - `TestCoerceSource` (6) — None default / case-insensitive canonicalise / unknown error / non-string error / empty default / `ALLOWED_SOURCES` constant pin
    - `TestBuildWhereFilter` (5) — no filters None / source only / single tag / multiple tags AND / source+tags AND
    - `TestChunkText` (5) — empty / short single chunk / chunk_chars=0 fallback / overlap respected / overlap clamped
    - `TestSaveMemoryHappyPath` (8) — save returns id+metadata / save→recall round trip / tag filter / source filter / empty collection → 0 / limit clamped / default limit 5 / explicit-id idempotent
    - `TestSaveMemoryErrorPaths` (5) — summary required / too short / unknown source / chromadb unavailable / embedding unavailable
    - `TestRecallContextErrorPaths` (3) — query required / unknown source / chromadb unavailable
    - `TestIndexProjectFiles` (7) — empty specs / chunks reported / replace=True drops old chunks / on_progress per file / empty text → ok=False / chunks capped at MAX_INDEX_CHUNKS_PER_FILE / Excel hit recallable
    - `TestDispatcherRouting` (2) — save→recall via dispatcher / call trace populated
    - `TestPromptWiring` (3) — chat prompt mentions `🔎` + `recall_context` + `save_memory` + `გახსოვს`; investigator prompt does NOT contain recall/save; chat prompt warns against ცრუ recall
    - `TestModuleConstants` (7) — persist_dir under project root + `ai_vectors`; chat/project collection name pins; chunk overlap < chunk_chars; min < max summary; `get_memory_store` cached singleton; `reset_memory_store` drops cache
    - `TestTagMetadataRoundtrip` (3) — list ↔ comma-string encode/decode; missing/non-string handled
  - **Fake ChromaDB fixture** (in-process, ~150 lines): `_FakeCollection` + `_FakeClient` + `_FakeChromaDB` + `_NoopEmbeddingFunction` autouse-fixture installs them via `monkeypatch` over `mem._load_chromadb` + `mem._load_embedding_function` + `mem._default_project_root`, then resets the singleton. Distance is a deterministic word-overlap score so ranking assertions are stable without invoking a real embedding model. `_fake_matches` implements the `$eq` + `$contains` + `$and` `where` operators we actually use.
  - 3 existing tests updated for the 8→10 tool surface (zero weakened or deleted): `tests/test_ai_forecasting.py::TestForecastToolSchema::test_tool_count_is_8` renamed to `test_tool_count_is_10`; `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` extended with `recall_context`/`save_memory` assertions + count 10; `tests/test_ai_agent.py::TestChatMode::test_investigate_mode_preserves_tool_surface` extended with both new names
  - **pytest 633/633 passed** in 2.57s (was 548; +85 new memory tests, no regression in any pre-Sprint-3 suite)

- **Invariants preserved**:
  - `TOOL_SCHEMAS` module constant stays cache-control-free (tests assert); annotate only via `get_cached_tool_schemas()` deep-copy — the `cache_control` ephemeral marker now sits on `validate_vs_source` (last entry is unchanged by Sprint 3 reordering since memory tools land at indices 4 and 5, not at the tail)
  - Both `/api/chat` + `/api/chat/stream` automatically expose `recall_context` + `save_memory` (shared schemas path)
  - Investigator prompt (`SYSTEM_PROMPT_KA_INVESTIGATOR`) untouched — zero Sprint 1/2/3 regression risk
  - `cashflow` tab documented intentional exception still respected
  - All pre-existing 548 tests still pass unchanged alongside 85 new (+3 updates); no test weakened or deleted (user rule respected)
  - Lazy imports in `memory.py` + `tools.py` dispatcher mean a broken `chromadb` or `sentence-transformers` wheel does NOT crash the chat pipeline — it surfaces a Georgian error + `pip install` hint only when the user actually asks for recall/save
  - `ai_vectors/` persist dir is gitignored (already covered by `.gitignore` line 42) — no risk of committing the local vector store
  - HuggingFace model cache lives outside the repo (default `~/.cache/huggingface/`) — no repo bloat

- **Scratch + cleanup**:
  - Scratch scripts `_scratch_recall_check.py` + `_scratch_embed_probe.py` used during the Georgian embedding probe — both deleted at the end of session 21:10
  - `ai_vectors/` persist directory populated through two `--replace` re-index runs (first after backend restart, second after Latin-hint fix)

---

### 🆕 Phase 0B Sprint 3 — FULLY LIVE ✅ (2026-04-19 20:54–21:10)

- **Backend restart #3** (20:54):
  - Earlier background `server.py` (PID 9096) had exited with code 1 during this session. A separate system-Python 3.14 process (PID 25876) briefly occupied port 8000 via an automated `.bat` launcher — it has NO `chromadb` / `sentence-transformers` installed and would silently break `recall_context` / `save_memory`. Terminated with `Stop-Process -Id 25876 -Force`.
  - Fresh parent-venv launch (`Cwd=financial-dashboard`, `$env:AI_ENABLE_THINKING='true'`, `-u server.py`) → PID 18076 listening on 127.0.0.1:8000
  - `/api/status` 200 OK; smoke import confirms TOOL_SCHEMAS length = 10 with `recall_context` + `save_memory` both present

- **Full `Financial_Analysis/` corpus indexed** (20:56, 20:37, 21:02 — three `--replace` runs over the session):
  - `python index_project_files.py --replace` in default sampled mode (`--max-rows 2000` per file, `--max-sheets 5`, skip > 80 MB)
  - 26 Excel/CSV files → 18,263 upsert operations → 13,329 unique chunks in `ai_vectors/`
  - Per-run elapsed: 344.6s → 357.2s → 359.4s → 378.5s (~6 min each)
  - Per-file chunk examples: `ბოგ ბანკი ამონაწერი/2023.xlsx` = 1,545; `თბს ბანკი ამონაწერი/2024.xlsx` = 860; `რს ზედნადები/2024.xls` = 543; `manual_payments.csv` = 13 (after header added, was 5)

- **UI live dog-food — 4 user-driven chat turns all ✅**:
  1. **Save** (20:03): user typed `"შეინახე წესი — ahead-ვალის პოლიტიკა: ნებისმიერი ოდენობა, წინასწარი 50% ჭანაწერები გვექნება"` → AI invoked `save_memory` → returned id `chat_5ae70d77fba7455d8a00c8a0346fc9c4` with 🔒 Georgian formulation and a follow-up clarifying question
  2. **Recall** (20:04): `"გახსოვს, რა პოლიტიკა დავადგინეთ ahead-ვალებზე?"` → AI narrated `"მოიცა, ვეძებ მეხსიერებაში…"` → invoked `recall_context` → cited both `chat_5ae70d...` (just-saved rule) AND `chat_996e87...` (Alpha 23,000 ₾ debt memory from an earlier scratch round-trip, surfaced via semantic proximity — bonus validation of cross-memory retrieval)
  3. **Negative control** (20:05): `"რამდენი მომწოდებელია?"` → AI did NOT invoke `recall_context`; routed to `read_data_json(section=suppliers)` and answered `"სულ 270 მომწოდებელია (წყარო: data.json → suppliers)"` — confirms anti-trigger rules in SYSTEM_PROMPT_KA are respected
  4. **Excel recall** (21:05, after the Latin fix): `"2023 წლის ბოგ ბანკში რა ტიპის ოპერაციები ფიქსირდება?"` → AI invoked `recall_context(source=excel)` with Latin alias injected automatically → 5/5 matched chunks from `Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx` → full Georgian answer with POS terminal `POS1XA88` (ოზურგეთი, ბარამიძის 7), account `GE15BG0000000537419534GEL`, SWIFT `BAGAGE22`, company `შპს ჯეო ფუდთაიმი` (400333858), MC + AMEX cards, per-tx fees 0.10–0.19 ₾

---

### 🆕 Georgian embedding Latin fix — delivered same session (21:00–21:10)

- **Problem observed** (turn 4, first attempt): `"2023 წლის ბოგ ბანკში რა ოპერაციები იყო?"` returned chunks exclusively from `თბს ბანკი ამონაწერი/` — wrong bank. BOG 2023 was physically indexed (1,545 chunks) but ranked below #30 on pure-Georgian queries.
- **Diagnosis** (in-process probe script `_scratch_embed_probe.py`, deleted after use):
  - `paraphrase-multilingual-MiniLM-L12-v2` tokenises the 3-letter Georgian abbreviations `"ბოგ"` / `"თბს"` / `"რს"` as near-identical neighbours in embedding space
  - Cross-test: query `"BOG bank 2023"` ranked BOG 2023 top-1 (cosine 0.196); query `"ბოგ ბანკი 2023"` ranked TBC 2022 top-1 (cosine 0.318). The Latin alias was the decisive signal.
- **Fix — two coupled layers**:
  1. **Indexing side** (`dashboard_pipeline/ai/memory.py`):
     - New `_CATEGORY_GEORGIAN_LABELS` (4-entry) + `_FOLDER_LATIN_HINTS` (6-entry) static maps — folder stem → Latin alias (e.g. `"ბოგ ბანკი ამონაწერი" → "BOG bank Bank of Georgia statement"`, `"თბს ბანკი ამონაწერი" → "TBC bank statement"`)
     - New `_build_chunk_header(path, tags)` helper returns a 2-line prefix prepended to every Excel chunk before `upsert()`:
       - Line 1 (embedding-dominant keyword line): `ბოგ ბანკი ამონაწერი BOG bank Bank of Georgia statement 2023 ბანკი`
       - Line 2 (structured human-readable): `[ფაილი: Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx — წელი 2023 — კატეგორია ბანკი]`
     - `index_project_files()` now calls `header = _build_chunk_header(path, tags)` per file and stores `documents.append(f"{header}{chunk}" if header else chunk)` per chunk
  2. **Prompt side** (`dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — chat mode only; investigator prompt untouched):
     - New `### 💡 Excel query გაძლიერება` subsection inside the `🔎 სემანტიკური მეხსიერება` block with a 3-row mapping table and the instruction that the Latin alias goes in the `recall_context.query` field but the rendered Georgian answer must stay pure Georgian
- **Verification after `--replace` re-index (21:05)**:
  | Query | Top-1 file | Cosine dist | Outcome |
  |---|---|---|---|
  | `"ბოგ ბანკი 2023"` (pure ქართული) | TBC 2022.xlsx | 0.214 | ❌ still mis-ranks (model limitation — prompt fix is the decisive piece) |
  | `"ბოგ ბანკი BOG Bank of Georgia 2023"` | BOG 2023.xlsx | **0.096** | ✅ top-5 all BOG 2023 |
  | `"თბს ბანკი TBC 2024"` | TBC 2024.xlsx | 0.128 | ✅ top-5 all TBC 2024 |
  | `"რს ზედნადები RS waybill Revenue Service 2025"` | RS 2025.xls | 0.063 | ✅ |
- **Test posture**: `pytest tests/test_ai_memory.py tests/test_ai_self_critique_prompt.py -q` → 119/119 still green (no existing test references the new header format — it's additive text inside already-stored Excel chunks)
- **New do-not-touch rules**:
  - `_FOLDER_LATIN_HINTS` map is paired with the prompt Latin alias table; removing one without the other regresses Georgian-only queries silently
  - Re-indexing (`--replace`) is required after any change to `_build_chunk_header` or `_FOLDER_LATIN_HINTS` — old headers do NOT auto-migrate
  - If new banking folders ever appear (e.g. `"ქართუ ბანკი ამონაწერი"`), add a mapping entry before re-indexing

---

### 🚨 path_token ID-collision bug-fix — delivered 2026-04-19 21:25

- **Symptom reported by user**: asked for the 6 subfolders AI sees under `Financial_Analysis/`. Per-folder report showed only 20 of the 26 files indexed; 3 of the 3 დვაბზუ files and 3 of the 4 ოზურგეთი files were silently missing, while the ones that WERE indexed had partially correct content.
- **Diagnosis**:
  - `index_project_files()` used `path_token = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")` to derive chunk ids like `excel::{path_token}::{idx}`
  - The regex `[^a-z0-9]+` strips every non-ASCII character, so every Georgian folder name collapsed into the surrounding ASCII fragments. Live examples:
    - `Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx` → `financial_analysis_2023_xlsx`
    - `Financial_Analysis/თბს ბანკი ამონაწერი/2023.xlsx` → `financial_analysis_2023_xlsx`  ← identical
    - `Financial_Analysis/რს ზედნადები/2023.xls` → `financial_analysis_2023_xls`
  - `ChromaDB.upsert(ids=...)` with duplicated ids silently overwrites — so BOG 2023 chunks were replaced by TBC 2023 chunks, ozurgeti 2023 replaced by სოფ ოზურგეთი 2023, etc.
- **Fix**: replaced the ASCII-only regex with a unicode-safe SHA256 digest:
  ```python
  path_token = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
  ```
  (`hashlib` added to the module imports; 16-char digest keeps ids compact yet collision-free for all realistic path sizes)
- **Re-index after the fix** (single `python index_project_files.py --replace` run, ~6 min):
  | folder | files | chunks | status |
  |---|---|---|---|
  | `ბოგ ბანკი ამონაწერი` | 4 | 6,374 | ✅ all 4 (was 4 files but chunk totals were partly masked) |
  | `გაყიდული პროდუქტები სოფ დვაბზუ` | 3 | 1,112 | ✅ all 3 (was 0 🆕) |
  | `გაყიდული პროდუქტები სოფ ოზურგეთი` | 4 | 1,552 | ✅ all 4 (was 1 🆕) |
  | `თბს ბანკი ამონაწერი` | 5 | 4,475 | ✅ all 5 |
  | `რს ზედნადები` | 5 | 2,234 | ✅ all 5 |
  | `შემოტანილი პროდუქცია` | 4 | 2,503 | ✅ all 4 |
  | (root) `manual_payments.csv` | 1 | 13 | ✅ |
  | **total** | **26 ✅** | **18,263 ✅** | (was 13,329 — 4,934 chunks lost to collisions) |
- **Test posture**: `pytest tests/test_ai_memory.py -q` → 85/85 still green (the fix is mechanical inside `index_project_files`; no test asserted on the old regex shape)
- **Do-not-touch (new rule)**: never revert `path_token` to any ASCII-only regex; it must preserve the distinctness of Georgian file paths. The chunk-header Latin hints (`_FOLDER_LATIN_HINTS`) are complementary but independent — they only affect embedding ranking, NOT ID uniqueness.

---

### 🆕 Phase 0B Sprint 4 — Decision Journal — Part 1 (code) COMPLETE ✅ (2026-04-19 22:05)

**Scope delivered this session (Part 1 = code + tests only; backend restart + live dog-food + Parts 2/3 remain):**

- **New module `dashboard_pipeline/ai/journal.py`** (~640 lines):
  - CRUD wrapper over the existing `chat_memory` ChromaDB collection — journal entries are semantically searchable through `recall_context(tags=["journal"])` *and* queryable by structured filters (status/kind/overdue/due_date) through `collection.get(where=...)`. No new storage engine.
  - Public API: `add_journal_entry(title, kind, *, due_date=None, tags=None, source_memory_id=None)` / `list_journal_entries(*, status=None, kind=None, overdue=None, due_before=None, due_after=None, limit=None, today=None)` / `update_journal_entry(entry_id, *, status)` / `delete_journal_entry(entry_id)` / `collect_today_journal_highlights(*, today=None, newest_open_limit=3)`.
  - Stable metadata discriminator: `journal_entry_type="journal"` separates journal rows from plain `save_memory` summaries in the same collection. `update_journal_entry` hard-enforces this check to prevent status stamping any non-journal row.
  - 4 kinds: `promise` (user commits) / `ai_commitment` (AI commits) / `recommendation` (AI suggests + outcome-tracks) / `reminder` (dated external deadline).
  - 3 statuses: `open` (default on add) / `done` / `cancelled`.
  - Title bounds: 3–500 chars. Tags auto-prefixed with `journal` + `kind:<kind>` + `status:<status>`; user-supplied `kind:*` / `status:*` tokens are stripped to prevent drift.
  - Due-date coercion accepts ISO `YYYY-MM-DD`, `date`, `datetime`, empty → `""`; invalid formats rejected with Georgian error.
  - Sort order (deterministic): `overdue` (most days first) → `upcoming` (earliest-due first) → `rest` (newest first).

- **`dashboard_pipeline/ai/memory.py` extensions**:
  - `MemoryStore.get_entries(source, *, where=None, ids=None, limit=None)` — structured ChromaDB `collection.get(...)` lookup that bypasses the embedding model.
  - `MemoryStore.update_metadata(entry_id, source, *, patch)` — shallow-merge patch, keeps existing `document` + `tags` (so embedding remains stable across status toggles).
  - `MemoryStore.delete_entry(entry_id, source)` — id-based deletion with graceful fallback when the underlying client lacks `delete(ids=...)`.
  - All three fail soft (return `None`/`False`/`[]` on failure) so `today_context` never crashes a chat turn over journal infrastructure issues.

- **`dashboard_pipeline/ai/tools.py` — TOOL_SCHEMAS 10 → 13**:
  - `JOURNAL_ADD_ENTRY_TOOL` at index 6, `JOURNAL_LIST_ENTRIES_TOOL` at 7, `JOURNAL_UPDATE_ENTRY_TOOL` at 8; investigator tools (`read_source_code` / `grep_code` / `read_excel_source` / `validate_vs_source`) shift down so `VALIDATE_VS_SOURCE_TOOL` remains last (preserves `get_cached_tool_schemas` cache marker placement).
  - Dispatcher routes the 3 new names through lazy imports of `dashboard_pipeline.ai.journal` — zero impact when journal isn't used.
  - `_SUMMARY_KEYS` extended with `entry_id`, `kind`, `title`, `due_date`, `previous_status`, `count`, `today`, `existed`.

- **`dashboard_pipeline/ai/today_context.py` extensions**:
  - `build_today_context(..., project_root=None)` + `build_today_block(..., project_root=None)` gain optional `project_root` kwarg (tests pass `tmp_path`).
  - New `ctx["open_promises"] = {"overdue": [...], "newest_open": [...]}` field auto-populated via `journal.collect_today_journal_highlights`.
  - `format_today_block` renders a new `⏳ ღია დაპირებები (N ვადაგადაცილებული + M ახალი):` sub-section with per-entry icon (🤝 promise / 🔍 ai_commitment / 💡 recommendation / ⏰ reminder) + 🚨 tag for overdue + `id: journal_<hex>` handle. Suppressed entirely when empty (never shows `0 ვადაგადაცილებული`).
  - Surfaces journal state even when `data_loader` fails — overdue commitments don't depend on fresh POS numbers.

- **`dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` extensions** (chat mode ONLY — investigator prompt completely untouched):
  - New **"📋 დაპირებების ჟურნალი (CRITICAL — Phase 0B Sprint 4)"** section between the 🔎 memory section and the 🪞 Self-Critique directive.
  - Per-kind trigger table (4 rows) + `due_date` Georgian → ISO conversion rules (`ხვალ` → today+1; `ერთ კვირაში` → today+7; `14 მაისს` → `2026-05-14`; undated by default).
  - Anti-trigger list (greetings, idle chit-chat, `რამდენია X` lookups, acknowledgments) — prevents a flood of low-value journal rows.
  - `journal_update_entry` trigger rules for `done` / `cancelled` transitions; mandatory `list → disambiguate → update` flow when the user didn't name the entry_id.
  - `<TODAY>` "⏳ ღია დაპირებები" usage guidance — AI must cite the running commitment when the current question matches it, and proactively remind on 7+ day overdue.
  - `save_memory` vs `journal_add_entry` disambiguation — both may fire in one turn; prescribed order is `journal_add_entry` first, `save_memory` last.

- **Tests — pytest 742/742 green (was 633; +109 new, 0 weakened)**:
  - New file `tests/test_ai_journal.py` — **109 cases across 18 classes**: tool schemas + module constants + coercion helpers (title/kind/status/due_date/limit/today) + normalise_extra_tags + where-builder + sort + add/list/update/delete + `collect_today_journal_highlights` + `today_context` integration + dispatcher routing + prompt wiring + hit→entry + semantic recall interop.
  - Uses a fake in-process ChromaDB module (mirrors the `_FakeChromaDB` + `_FakeClient` + `_FakeCollection` pattern from `test_ai_memory.py`) — no disk I/O, no real embedding model load, tests run in milliseconds.
  - Existing updates: `tests/test_ai_memory.py::TestMemoryToolSchemas::test_tool_count_is_13` (was `_is_10`); `tests/test_ai_forecasting.py::TestForecastToolSchema::test_tool_count_is_13`; `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` (asserts 13 + adds 3 new names to the expected set); `tests/test_ai_agent.py::TestChatMode::test_investigate_mode_preserves_tool_surface` (expected name set gains `journal_add_entry` / `journal_list_entries` / `journal_update_entry`).
  - `tests/test_ai_memory.py::_FakeCollection` gained `get(ids=..., where=..., limit=...)` + `delete(ids=...)` fallback + `$ne` / `$lt` / `$gt` / `$lte` / `$gte` / `$or` operators — so the journal CRUD path exercises realistic ChromaDB semantics, not just a subset.
  - First run of `pytest tests/test_ai_journal.py -x` flagged a single sort-bucket bug (`created_at[::-1]` inversion trick didn't produce descending order when strings share a common prefix); replaced with an explicit 3-bucket approach (overdue / upcoming / rest) and dedicated `reverse=True` on the rest bucket — all 109 green on the second run.

- **Backend live status**:
  - PID 18076 (suspected "parent venv" from earlier restart) was actually **system Python 3.14** (confirmed via `importlib.util.find_spec` — `chromadb`, `sentence-transformers`, `anthropic`, `prophet`, `apscheduler` all MISSING). Killed 2026-04-19 22:22.
  - **PID 10128** (parent venv) now serves the live backend (`AI_ENABLE_THINKING=true`, `127.0.0.1:8000`). Verified via `Win32_Process.CommandLine` = `"...\venv\Scripts\python.exe" -u server.py` and in-process `sys.prefix = "...\venv"`.
  - `TOOL_SCHEMAS` length = **13** confirmed live (indices 6/7/8 = `journal_add_entry` / `journal_list_entries` / `journal_update_entry`).

- **Scratch cleanup**: 3 `_scratch_*.py` files (`_scratch_journal_smoke.py`, `_scratch_probe_where.py`, `_scratch_cleanup_journal.py`) were created for the live verification + bug-fix probe, then deleted at end of session. Leftover journal row `journal_9c4b07f1...` (orphaned by the first failed smoke run) also cleaned up before the final smoke.

- **No breaking changes**: old `build_today_context(data_loader, *, today=None)` signature still works (new kwarg is optional-keyword); old `_apply_filter_and_limit`, `recall_context`, `save_memory` contracts untouched; `_FakeCollection` changes are additive (`get()` / `delete(ids=...)` / extra operators); `_build_journal_where` output shape changed but only used internally by `journal.py`, not part of any public contract.

### 🐞 Part 1 Live Verification — 2 bug-fixes discovered + patched (2026-04-19 22:20–22:45)

**Bug #1: Windows venv Path-check caveat** (diagnosis, not a code bug)

- `Get-Process <pid> | Select Path` on a venv process always shows the **base Python** image (e.g. `C:\Users\tengiz\AppData\Local\Python\pythoncore-3.14-64\python.exe`), because Windows `venv\Scripts\python.exe` is a stub launcher that `CreateProcess()`-forwards to the base binary.
- This broke the "verify Path points to venv" guidance documented in earlier handoffs. During this session both the stray system-Python PID 18076 AND the fresh parent-venv PID 10128 returned identical Path strings, so the `Get-Process Path` check could not tell them apart.
- **Correct Windows venv verification**:
  - `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` → shows the full launch command incl. `...\venv\Scripts\python.exe`
  - In-process `sys.prefix` / `sys.executable` / `importlib.util.find_spec("chromadb")` → definitive venv activation proof
- **Do-not-touch**: never rely on `Get-Process Path` for venv activation on Windows going forward.
- **Previous false positive**: PID 18076 was documented in earlier sessions as parent-venv but was actually system Python 3.14. Since `fastapi`/`slowapi` are globally installed, `/api/status` still returned 200 — but any `/api/chat` call would have `ImportError`-crashed on the first tool dispatch (no `anthropic`/`chromadb` in that environment).

**Bug #2: ChromaDB 1.5.x `$lt` / `$gt` silent no-op on string metadata**

- **Symptom**: `list_journal_entries(overdue=True)` returned `count=0` even when a journal row with `due_date="2026-04-17"` (2 days past today) existed; `<TODAY>` block rendered the row as "🆕 today" instead of "🚨 overdue".
- **Root cause**: ChromaDB 1.5.x range operators (`$lt` / `$gt` / `$lte` / `$gte`) work only on **numeric** metadata. On string metadata they silently return zero rows — no error, no warning.
  - Minimal probe:
    - `{journal_status: {$eq: "open"}}` → 1 row ✅
    - `{journal_due_date: {$lt: "2026-04-19"}}` → **0 rows** ❌
    - `{journal_due_date: {$ne: ""}}` → 3 rows ✅ (incl. the one that should match `$lt`)
    - `{journal_due_date: {$gt: ""}}` → **0 rows** ❌
- **Why tests didn't catch it**: the in-process fake `_FakeCollection` faithfully implements Chroma's *documented* `$lt`/`$gt` semantics (lexicographic string comparison) so all 109 journal tests stayed green — but the *real* ChromaDB backend doesn't match its own docs for string metadata in v1.5.x.
- **Fix** (minimal, contract-stable):
  - `journal.py::_build_journal_where` now emits only `$eq`/`$ne` clauses — all range comparisons removed from the ChromaDB side.
  - New helper `journal.py::_apply_python_date_filters(entries, *, overdue, due_before, due_after)` applies overdue / due_before / due_after filters in Python after fetch (lexicographic ISO YYYY-MM-DD comparison).
  - `list_journal_entries` over-fetches up to 500 journal rows (narrowed structurally by `$eq status`/`$eq kind` clauses) then filters in Python — performant for realistic journals (<500 open entries).
  - `collect_today_journal_highlights` simplified to a single open-status fetch + Python overdue split.
  - `tests/test_ai_journal.py::TestBuildJournalWhere::test_overdue_enforces_lt_and_nonempty` renamed + rewritten to `test_overdue_enforces_open_status_only` asserting the new contract (no date clauses leak to ChromaDB); +1 new test `test_overdue_with_explicit_status_skips_auto_open`.
- **Verification**:
  - `pytest tests/` → **743/743 green** (was 742; +1 new test; 0 weakened/deleted)
  - Scratch smoke `_scratch_journal_smoke.py` → 6/6 steps pass against live ChromaDB:
    1. `<TODAY>` BEFORE empty state ✅
    2. `add_journal_entry(kind="promise", due_date=today-2d)` → `ok:true` ✅
    3. `list_journal_entries(status="open", overdue=True)` → **`count=1`** (was 0 before fix) ✅
    4. `<TODAY>` AFTER adding → `⏳ ღია დაპირებები (1 ვადაგადაცილებული)` + 🤝 + `🚨 ვადა გადაცილებული 2 დღე` ✅
    5. `update_journal_entry(status="done")` → `previous_status: "open"` ✅
    6. `<TODAY>` AFTER done → entry disappears from open list ✅

- **Do-not-touch rules** (new, carry forward):
  - `journal.py::_build_journal_where` must never re-introduce `$lt`/`$gt` on `journal_due_date` — they're silent no-ops against real ChromaDB 1.5.x. Track upstream; revert only after confirming real-backend behavior on string metadata.
  - `_apply_python_date_filters` `overdue=True` branch guard `isinstance(overdue_days, int) and overdue_days > 0` must stay — undated entries must never match overdue.
  - Python post-filter mechanism must be applied at **both** call sites (`list_journal_entries` + `collect_today_journal_highlights`).

### 🆕 Phase 0B Sprint 4 Part 1 — Live Anthropic Dog-Food — VERIFIED ✅ (2026-04-19 23:05)

**Purpose**: prove that the `SYSTEM_PROMPT_KA` 📋 journal section (chat mode only) correctly triggers `journal_add_entry` + `journal_list_entries` when the user types a natural Georgian promise sentence — the scratch smoke earlier proved the CRUD + `<TODAY>` integration, but not the prompt routing against real Anthropic.

**Method**: 2 sequential `POST /api/chat` calls to parent-venv backend (PID 10128, port 8000, `AI_ENABLE_THINKING=true`, mode=chat). API auth disabled for local dev. Single throwaway Python script (`_scratch_live_dogfood_sprint4.py`) using `urllib.request` — NO streaming (SSE), NO frontend — wire-clean test of the `/api/chat` contract.

**Turn 1** (~27.51s, 1 tool call) — natural promise:

> _"Alpha-ს ვალი 7 დღე გადაცილებულია, შემინახე ჟურნალში რომ არ დავივიწყო (due_date 3 დღეში)."_

AI behavior (all correct):
- Called `journal_add_entry` with:
  - `title = "Alpha-ს ვადაგადაცილებული ვალის გადამოწმება და მოგვარება"` (AI expanded user's terse phrasing into an action-oriented sentence)
  - `kind = "reminder"` (functionally correct — Alpha's debt is an external deadline to act on; prompt allows reminder/promise overlap in this context)
  - `due_date = "2026-04-22"` (today+3 — matched user's "3 დღეში" phrasing exactly)
  - `tags = ["supplier:alpha", "topic:cashflow"]` (Sprint 3 tag convention auto-applied without explicit guidance in this turn)
- Returned Georgian Markdown reply with entry ID `journal_ea57220f680f4aaba80e80c55b72415a`, a 4-row table (ID / title / kind / due_date), and a hint about `<TODAY>` ⏳ section surfacing this entry next chat.

Metrics (Turn 1): input=529 + output=460; `cache_create_input_tokens=16,028` + `cache_read_input_tokens=16,028`; `stop_reason=end_turn`; model `claude-sonnet-4-6`.

**Turn 2** (~7.08s, 1 tool call) — natural query on fresh history:

> _"რა მაქვს ახლა ღია ჟურნალში?"_

AI behavior (all correct):
- Called `journal_list_entries({"status": "open"})` (no extra args — prompt directs AI to default to `status="open"` on "რა მაქვს ჟურნალში?" wording).
- Returned Georgian Markdown reply: 1 entry table (#/title/kind/due/status) + "3 დღე რჩება ვადამდე" days-to-due hint + prompt for next action ("გსურს ამ ჩანაწერის სტატუსის განახლება?").

Metrics (Turn 2): input=1,586 + output=313; `cache_read_input_tokens=32,056` + `cache_create_input_tokens=0` (warm prefix — second turn re-uses cached prompt + tool schemas from Turn 1, as expected); `stop_reason=end_turn`.

**Observations**:
- **Total cost**: ~$0.09 across both turns (Sonnet 4.6 pricing: ~$0.077 Turn 1 cold + ~$0.014 Turn 2 warm).
- **Cache behavior**: Turn 2 `cache_read=32,056` = roughly 2× Turn 1 cache (prefix from both `system` + `tools` blocks intact). Latency dropped ~4× (27.5s → 7.1s) almost entirely due to the cache hit — no wall-clock cost for the AI re-parsing the 13-tool + multi-section system prompt.
- **Tag convention inheritance**: AI applied `supplier:alpha` + `topic:cashflow` tags without explicit reminder in the user turn — Sprint 3 prompt guidance ("supplier:/topic: namespacing") carried through cleanly into Sprint 4's new tool surface.
- **Kind choice (`reminder` vs `promise`)**: minor observation, NOT a bug. User said "ვალი გადაცილებულია" (the debt is overdue) rather than "ვპირდები..." (I promise...). AI interpreted this as an external deadline → `reminder`. Both kinds stay `open` + surface in `<TODAY>` ⏳ block + get overdue-flagged, so the business effect is identical. Could tighten via prompt ("ვალი/საკითხი გადაცილებულია" → always `promise` if subject = a specific supplier) in a future polish pass, but not blocking.
- **Markdown output format**: entry ID / table / days-to-due hint are all well-formatted for ChatAssistant.jsx react-markdown rendering (no raw JSON leaking into reply).

**Cleanup**: `update_journal_entry(entry_id, status="cancelled")` was called via scratch script after Turn 2 so the test entry doesn't clutter live ChromaDB. Tags after cleanup: `["journal", "kind:reminder", "status:cancelled", "supplier:alpha", "topic:cashflow"]` (status tag correctly rewritten from `status:open` to `status:cancelled` during the update).

**Scratch artifacts**: 2 `_scratch_*.py` files (`_scratch_live_dogfood_sprint4.py` + `_scratch_cleanup_sprint4.py`) created for this session and deleted immediately after verification.

**Conclusion**: SYSTEM_PROMPT_KA 📋 journal section is live-proven on real Anthropic Sonnet 4.6 through `/api/chat` endpoint. Phase 0B Sprint 4 Part 1 is now **fully verified end-to-end** (code + tests + CRUD smoke + prompt routing). Remaining Sprint 4 work is Part 2 (Phase 0B-wide metrics collection) + Part 3 (retrospective + docs refresh + closure).

### 🆕 Phase 0B Sprint 4 Part 2 — Phase 0B-wide Live Metrics + Deep-Iteration Fix — VERIFIED ✅ (2026-04-19 23:15)

**Purpose**: single scripted pass covering all four Phase 0B sprints to measure real cost / latency / cache utilisation on the deployed stack, then close the Phase 0B Sprint 4 caveat queue.

**Method**: `_scratch_phase0b_metrics.py` (gitignored, deleted after run) — 7 sequential `POST /api/chat` calls against parent-venv backend PID 10128 with live Sonnet 4.6 + Anthropic prompt caching + `AI_ENABLE_THINKING=true`.

**Metrics** (raw dump: `_scratch_phase0b_metrics.json`):

| # | Scenario | elapsed | in | out | cache_read | cache_create | cost $ | stop_reason |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | Sprint 1 · think=true Alpha strategy | 85.57 s | 32,131 | 1,140 | 64,112 | 32,078 | 0.157 | **max_iterations ⚠️** |
| 2 | Sprint 2 · `forecast_revenue` (3-month) | 10.98 s | 1,591 | 453 | 32,056 | 0 | 0.016 | end_turn |
| 3 | Sprint 3a · `save_memory` | 11.18 s | 1,607 | 449 | 32,056 | 0 | 0.016 | end_turn |
| 4 | Sprint 3b · `recall_context` | 10.31 s | 2,291 | 520 | 32,056 | 0 | 0.017 | end_turn |
| 5 | Sprint 4a · `journal_add_entry` | 9.62 s | 1,502 | 417 | 32,056 | 0 | 0.016 | end_turn |
| 6 | Sprint 4b · `journal_list_entries` | 7.04 s | 1,569 | 281 | 32,056 | 0 | 0.014 | end_turn |
| 7 | Sprint 4c · `journal_update_entry` | 9.74 s | 1,585 | 232 | 32,056 | 0 | 0.013 | end_turn |
| **sum** | **7 scenarios** | **≈60 s warm + 86 s think = ≈145 s** | | | | | **≈$0.25** | **6 end_turn / 1 max_iterations** |

**Cache efficiency**: `cache_create=32,078` on call 1 then `cache_read=32,056` on every subsequent call. Effective input-token cost dropped by ~90% for calls 2–7 ($3/M → $0.30/M). Warm chat turns under $0.02 each on this hardware.

**Cleanup**: Sprint 4c succeeded in calling `journal_update_entry(status="cancelled")` autonomously; Python-side belt-and-suspenders sweep found 0 stale `phase 0b metrics` journal entries afterward. Live ChromaDB unchanged by the metrics run.

**Surfaced caveat → fix landed in same session (2026-04-19 23:30)**: Sprint 1 scenario hit `MAX_TOOL_ITERATIONS=6` because Extended Thinking + an Alpha-strategy question + Self-Critique Multi-hypothesis naturally fans out into more tool calls than the Phase 1 MVP chat-default budget allows. The documented Parking Lot item "Mode-dependent `MAX_TOOL_ITERATIONS`" was promoted to an in-session fix:

- `dashboard_pipeline/ai/agent.py`:
  - New module constant `MAX_TOOL_ITERATIONS_DEEP = 10` (old `MAX_TOOL_ITERATIONS = 6` preserved)
  - New helper `AIAgent._resolve_max_iterations(*, mode, thinking_enabled) -> int` — returns `10` when `think=True` OR `mode=="investigate"`, else `6`. The two switches don't compound (10 is the ceiling even when both are active) so a runaway prompt still can't loop forever.
  - Both `chat()` and `chat_stream()` now resolve the per-turn cap via the helper instead of referencing the module constant directly; fallback log + Georgian fallback reply both reference `max_iterations` (resolved value) instead of the constant.
- `tests/test_ai_agent.py` — new `TestDeepIterationCap` class with **9 cases**: constant ordering, 4 resolver permutations (chat / think / investigate / both), `think=True` lets 9 tool_use turns + final text complete, `mode="investigate"` does the same, deep cap still hits `max_iterations` at 10 on a runaway prompt, plain chat (no think, no investigate) still hits the 6-iteration fallback at turn 6. Import line imports `MAX_TOOL_ITERATIONS_DEEP` alongside existing `MAX_TOOL_ITERATIONS`.
- Existing tests (`test_max_iterations_guard` chat + streaming) unchanged — both use default chat mode so the 6-step cap still triggers at the expected index.
- **pytest 752/752 green** (was 743; +9 deep-cap cases; 0 tests weakened or deleted).

**Backend restart #5 (2026-04-19 23:33)**: killed PID 10128 (port 8000 was being held by the old server still running pre-deep-cap code). New `& '...\venv\Scripts\python.exe' -u server.py` with `$env:AI_ENABLE_THINKING='true'` → **PID 7644** live on `127.0.0.1:8000`. Verified via `Win32_Process.CommandLine` = `"...\venv\Scripts\python.exe" -u server.py`; `/api/status` returns 200 OK.

**Re-verification on new backend (2026-04-19 23:34)**: repeated the Sprint 1 Alpha strategic question (`think=True`, same wording as the metrics run):

| field | value |
|---|---|
| elapsed | **155.1 s** |
| stop_reason | **`end_turn`** ✅ (was `max_iterations`) |
| tools called | 8: `read_data_json` ×3, `recall_context`, `compute` ×4 |
| input / output / cache_read / cache_create | 29,886 / 3,423 / 48,084 / 32,078 |
| cost | **$0.186** |
| reply | 3,722-char Georgian 3-version strategic analysis (50%/40% probabilities across 3 paths + 🎯 recommendation) |
| bonus | Agent called `recall_context` and cited the prior Alpha `"50% წინასწარის"` commitment stored in earlier Sprint 3 scratch round-trip |

Cost delta vs failed run: +$0.029 for a qualitatively massive upgrade (polite fallback → full 3-hypothesis strategic output). Phase 0B Sprint 4 caveat now closed.

**Raw scratch artifacts** (deleted after Part 3 docs refresh): `_scratch_phase0b_metrics.py`, `_scratch_phase0b_metrics.json`, `_scratch_sprint1_reverify.py`, `_scratch_sprint1_reverify.json`.

### 🆕 Phase 0B Sprint 4 Part 3 — Retrospective + Docs Refresh + Closure — DONE ✅ (2026-04-19 23:40)

- `PHASE_0B_SPRINT4_PREVIEW.md` — top banner marked **COMPLETE (2026-04-19 23:40)** with a summary table of all three parts and Part 2 metrics + deep-cap fix.
- `PLAN.md` — active-status block rewritten to "Phase 0B Sprint 4 FULLY COMPLETE + Phase 0B CLOSED" with PID 7644 + 752-test pytest baseline + 8-tool Sprint 1 re-verify numbers; Sprint 4 checklist marks Part 2 + Part 3 done.
- `CONTEXT_HANDOFF.md` — banner timestamp + current-blocker + next-recommended + copy/paste brief all refreshed to reflect Phase 0B closure. `MAX_TOOL_ITERATIONS_DEEP` stable surface added to the do-not-touch rule block.
- `HANDOFF.md` (this file) — banner timestamp refreshed; Part 2 + Part 3 evidence sections appended above; Next-queue rewritten to Phase 1 kickoff.
- Scratch artifacts cleaned up; only the final JSON summary narrative stays in HANDOFF.md metrics table above.

### 📊 Phase 0B retrospective (one-pass summary)

| Sprint | Delivered | New tests | pytest baseline | Live verified |
|---|---|---:|---:|---|
| 0A (baseline) | `compute` + Self-Critique + `<TODAY>` + waybill fix | 73 | 381 | ✅ |
| 0B Sprint 1 | Extended Thinking + Multi-hypothesis + 🧠 toggle | 77 | 458 | ✅ |
| 0B Sprint 2 | Prophet + ARIMA `forecast_revenue` + 🔮 prompt | 80 | 548 | ✅ |
| 0B Sprint 3 | ChromaDB + RAG + 🔎 prompt + Latin hint + SHA256 path_token | 85 | 633 | ✅ |
| 0B Sprint 4 Part 1 | `journal.py` CRUD + 3 tools + ⏳ block + 📋 prompt | 109 | 742 (before bug-fix) | ✅ |
| 0B Sprint 4 Part 2 bug-fix 1 | Windows venv Path-check caveat | 0 (doc) | 742 | ✅ |
| 0B Sprint 4 Part 2 bug-fix 2 | ChromaDB 1.5.x `$lt`/`$gt` string caveat | +1 | 743 | ✅ |
| 0B Sprint 4 Part 2 deep-cap | `MAX_TOOL_ITERATIONS_DEEP=10` + resolver | +9 | **752** | ✅ |

**Total new tests through Phase 0A + 0B**: 381 → 752 (+371 cases; 0 tests weakened or deleted throughout).

**Total Phase 0B cost envelope** (observed 2026-04-19 metrics run): **~$0.25 for a 7-call heavy session** with one Extended Thinking call. Order-of-magnitude under the AI_GENIUS_PARTNER_PLAN budget of $40–$95/month heavy use — Sprint 4 closure leaves Phase 1 with plenty of cost headroom.

### AI Genius Phase 1 Part A — CODE COMPLETE ✅ (2026-04-20 00:30)

**Scope**: "ხასიათი + საზრისობა" Layer 1 — give the chat-mode prompt a persona, a mental model of the project, a source-priority ladder, data-skepticism reflexes, the 5-hat thinking frame, confidence labels, and an anti-hallucination assumption marker. Investigator prompt intentionally untouched.

#### Backend
- `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — 8 new CRITICAL sections **above** the existing ENG/STOP-CHECK stack:
  1. **🎯 როლის კონტრაქტი** — persona, tone contract (**strict, direct, no flattery / soft-pedaling**), and the new anchor marker the test suite now pins on (replaces pre-Phase-1 `ფინანსური მრჩეველი` label)
  2. **🗺️ პროექტის რუკა** — compact mental model of the 2-store franchise business (Ozurgeti urban × 3 POS, Dvabzu rural × 2 POS), the data sources owned by `data.json`, the `Financial_Analysis/` Excel tree, the ChromaDB vector store, and the AI's own memory
  3. **⚖️ წყაროების იერარქია** — strict priority `Excel > data.json > ChromaDB > AI's head`; the last rung is explicitly banned from numeric claims without a `📌` flag
  4. **🕵 Data-ზე სკეპტიციზმი** — per-section refresh-lag rules (POS last 1-2 days often incomplete, `manual_payments.csv` always stale, `supplier_aging` 1-3 day lag, waybills daily-sync); recommendation gate: if advice depends on possibly-stale data, the AI must warn upfront
  5. **🎭 5 ქუდი** — complex strategic / risk / scenario questions MUST surface ≥ 2-3 hats (💼 financial / 🔧 operational / 🎯 strategist / ⚠️ risk / 🪞 critic); every multi-hat reply ends with a 🪞 critic block
  6. **🎯 Confidence ნიშნები** — non-factual replies (advice / forecast / hypothesis / scenario) must carry an explicit confidence label ✅ 95%+ / 🟢 75-95% / 🟡 50-75% / 🟠 25-50% / ⚪ 0-25%
  7. **📌 ვარაუდი vs ფაქტი (anti-hallucination v2)** — every number is either tool-derived + cited OR prefixed `📌 ვარაუდი:` and paired with a confidence label; banned filler phrases (`ალბათ ~150K`, `დაახლოებით 200K`, `ჩვეულებრივ მარგინი 8%`) called out by name
  8. **Reinforced strict-tone** in the "ენა და ფორმატი" block — bold/table/bullet formatting guidance, units always required, `YYYY-MM-DD` date form, and an explicit back-reference to the 🎯 role contract
- `dashboard_pipeline/ai/agent.py`:
  - `MAX_TOOL_ITERATIONS_DEEP` bumped **10 → 12** — 5-hat triangulation + two-store comparisons + multi-hypothesis scaffolding routinely chain past 10 tool calls under `think=True` / `mode="investigate"`
  - `_resolve_max_iterations` docstring refreshed; plain chat stays capped at 6
- `dashboard_pipeline/ai/today_context.py`:
  - new `_WEEKDAY_CONTEXT` — 7-entry Georgian weekday hints (`ორშაბათი — კვირის დასაწყისი — დაგეგმე`, `პარასკევი — კვირის ბოლო — შეადგინე ბრიფი`, etc.); surface via weekday line appended to the date line
  - new `_FIXED_MONTHLY_DEADLINES` — only universal Georgian monthly anchors (`VAT` return + `საპენსიო` contribution, both due on day 15); franchise/income-tax intentionally routed through user's journal, not hard-coded
  - new helpers `_upcoming_deadlines()` + `_next_monthly_anchor()` + `_clamp_day()`; 10-day lookahead window with severity buckets (🚨 `≤ 3 days`, ⏰ `≤ 7 days`, 📆 `≤ 10 days`)
  - `⏰ უახლოესი ვადები:` block appears in `<TODAY>` only when something is actually inside the window — outside window, section is suppressed (silent for 2/3 of each month)
- Investigator prompt `SYSTEM_PROMPT_KA_INVESTIGATOR` — **untouched** (carry-forward do-not-touch rule honored since Sprint 1; Phase 1 Part A test suite asserts persona marker + 5-hat icons + outcome-based language all ABSENT from investigator)

#### Tests
- `tests/test_ai_prompts_phase1.py` (**NEW — 66 cases / 14 classes**):
  - `TestRoleContract` 8 — persona upgrade, strict-tone phrasing, anti-flattery guardrail
  - `TestProjectMap` 5 — all 4 sources named, Ozurgeti/Dvabzu store model present
  - `TestSourceHierarchy` 5 — ladder order, "AI's head" ban, `📌` pairing rule
  - `TestDataSkepticism` 6 — POS / manual_payments / aging / waybills lag rules
  - `TestFiveHats` 9 — all 5 icons + labels + multi-hat trigger ≥ 2 + closing 🪞 requirement
  - `TestConfidenceLabels` 6 — all 5 labels, non-factual requirement, factual exception
  - `TestAssumptionMark` 5 — `📌 ვარაუდი` mandatory pairing + confidence
  - `TestInvestigatorUntouched` 6 — every Phase-1-Part-A marker ABSENT in investigator prompt
  - `TestWeekdayContext` 5 — 7 hints, rendering in `<TODAY>`, weekday-indexing correctness
  - `TestFixedMonthlyDeadlines` 7 — VAT + საპენსიო only, day 15, severity buckets, 10-day horizon
  - `TestMonthArithmetic` 4 — `_next_monthly_anchor` / `_clamp_day` edge cases (Feb, December rollover)
  - `TestCtxShape` — extra ctx fields remain JSON-safe
- Re-anchored 5 existing persona-marker assertions across `test_ai_prompts.py` / `test_ai_journal.py` / `test_ai_forecasting.py` — `ფინანსური მრჩეველი → 🎯 როლის კონტრაქტი` (pre-Phase-1 marker string removed from production prompt; anchor renamed, not weakened)
- `TestDeepIterationCap` — constant expectation bumped 10 → 12; test renamed `ten_iteration_limit → twelve_iteration_limit`
- **pytest 818/818 green** (was 752; +66 new; 0 tests weakened or deleted)

### AI Genius Phase 1 Part A — LIVE VERIFIED ✅ (2026-04-20 00:55)

#### Backend restart #6
- Old PID 7644 (pre-Phase-1 prompt) died overnight; restarted via `$env:AI_ENABLE_THINKING='true'; & '...\venv\Scripts\python.exe' -u server.py` → new **PID 11620** on parent venv
- `Get-CimInstance Win32_Process -Filter "ProcessId=11620" | Select CommandLine` → `"C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe" -u server.py` ✅
- `/api/status` 200 OK; `AI_agent_initialized` log shows `model=claude-sonnet-4-6`, `enable_thinking=True`, `thinking_budget_tokens=5000`
- In-process probe confirmed (live via parent-venv `-c`): `MAX_TOOL_ITERATIONS_DEEP = 12` + `TOOL_SCHEMAS` length 13 + all 19 Phase-1-Part-A string markers (`🎯 როლის კონტრაქტი`, `🗺️ პროექტის რუკა`, `⚖️ წყაროების იერარქია`, `🕵 სკეპტიციზმი`, `🎭 5 ქუდი`, all 5 hat icons 💼/🔧/🎯/⚠️/🪞, `🎯 Confidence`, `📌 ვარაუდი vs ფაქტი`, `სტრატეგიული ფინანსური პარტნიორი`, all 5 confidence icons ✅/🟢/🟡/🟠/⚪) present in `SYSTEM_PROMPT_KA`; all 3 persona markers cleanly **absent** from `SYSTEM_PROMPT_KA_INVESTIGATOR`
- `<TODAY>` render sample includes weekday hint: `თარიღი: 2026-04-20 (ორშაბათი) — კვირის დასაწყისი — დაგეგმე` ✅ (deadline block correctly suppressed — next anchor is 2026-05-15, 25 days away, outside 10-day horizon)

#### 🐞 Collateral 1-line production fix — `DEFAULT_TIMEOUT_S 60 → 120 s`
- **Symptom**: First scripted `/api/chat` call returned HTTP 500 `APITimeoutError`; second call hung ~10 min with Anthropic SDK logging `Retrying request to /v1/messages in 0.447 s` → `0.756 s` → …
- **Root cause**: Phase 1 Part A's heavier system prompt (~3 K extra tokens) + Extended Thinking (5000 token budget) + per-turn Prophet cold start (~9 s cmdstanpy compile) combined pushed a single Anthropic `messages.create` call past the existing 60 s Anthropic SDK timeout ceiling → SDK's internal retry loop fired, each retry re-hit the cap, server locked ~10 min before giving up
- **Fix** (`dashboard_pipeline/ai/agent.py:47`): single-constant change `DEFAULT_TIMEOUT_S = 60.0` → `120.0` with an inline comment explaining Phase-1-Part-A + Extended-Thinking headroom rationale. No other code touched; no tests pin the 60 s value (only 2 references in the whole repo: definition + single `anthropic.Anthropic(timeout=DEFAULT_TIMEOUT_S)` consumer)
- **Verification**: `python -m py_compile agent.py` clean; full dog-food call completed in `151.6 s` elapsed, zero retries, `200 OK`; backend log shows successive `POST /v1/messages HTTP/1.1 200 OK` without any `Retrying request` chatter

#### Live Anthropic dog-food (1 scripted `/api/chat` call, `think=True`)
- **Question**: `"2026 წლის მდგომარეობით, ოზურგეთის და დვაბზუს მაღაზიებს შორის რომელია უფრო პერსპექტიული ინვესტიციისთვის? სტრატეგიული ანალიზი გჭირდება."`
- **Model behavior — all Phase 1 Part A markers exercised in one reply**:
  - 🎭 **All 5 hats fired** (💼 ფინანსური / 🔧 ოპერაციული / 🎯 სტრატეგი / ⚠️ რისკის / 🪞 კრიტიკოსი) — hats surfaced as section headers
  - 🎯 **Multi-hypothesis** — explicit 3-version strategic frame with probability split `ვერსია 1 (55%) / ვერსია 2 (30%) / ვერსია 3 (15%)`
  - 🎯 **Confidence label** — final რეკომენდაცია tagged `🟢 საიმედო` (75-95% band)
  - 📌 **Strict tone** — direct critique `"ჩადო ფული, სანამ არ იცი სად მიდის ხარჯი — სუსტი ლოგიკაა"`; zero flattery phrases detected (scratch audit scanned `შესანიშნავი კითხვა` / `საუცხოო კითხვა` / `მშვენიერი კითხვა` / `ძალიან საინტერესო` — all absent)
  - 📎 **Inline source attribution** — `(წყარო: data.json → monthly_pnl, executive_summary, compute + forecast_revenue ensemble)` closed the reply
  - 💾 **Auto-persistence surprise** — the AI, after writing the full strategic block, independently invoked `save_memory` (`chat_705a38ef`, 602 chars summary with tags `topic:strategy` / `kind:recommendation` / `object:ozurgeti` + `object:dvabzu`) **AND** `journal_add_entry` (`journal_886cce34`, `kind=recommendation`, title "ოზურგეთის ხარჯების ობიექტური audit — გაუნაწილებელი vs მაღაზიის ხარჯის გამიჯვნა") — exactly the "remember decisions + log commitments" contract from the 📋 journal prompt block + 🔎 memory prompt block
- **Numbers produced — all tool-verified, zero hallucination**: Dvabzu 2025 revenue **1,011,654 ₾ (+45.1% YoY)**, net **+839,081 ₾**, expense ratio 17.1%; Ozurgeti 2025 revenue **642,852 ₾ (-14% YoY)**, net **-961,788 ₾**, expense/revenue 249.6%. AP Days 163 flagged critical
- **Metrics**:

| Metric | Value |
|---|---|
| elapsed | 151.6 s |
| tool iterations | 26 tool calls across ≤ 12 deep iterations (under cap) |
| input tokens | 136,296 |
| output tokens | 7,235 |
| cache_read_input_tokens | **175,018** — prompt-caching working in streaming path |
| cache_create_input_tokens | 0 (warm prefix) |
| stop_reason | `end_turn` (natural completion; no max-iterations fallback) |
| HTTP status | 200 OK — no retries, no SDK backoff |
| cost (Sonnet 4.6 pricing) | ≈ **$0.12** — ~70% cheaper than naive fresh-cache cost thanks to 175 K cached tokens |

- **Endpoint note**: the scratch auditor's `"reply"` field audit showed all 5 hat icons / confidence labels / flattery-phrase list as empty because the AI ended its turn with a `save_memory` + `journal_add_entry` tool-use pair, then emitted only a short confirmation sentence `*(ანალიზი შენახულია — chat_705a38ef, journal → journal_886cce34)*` as its FINAL text block. `AIAgent.chat()` returns only that final text as `reply`; the full strategic analysis lives in the `history` array as prior assistant turns. This is a **pre-existing `/api/chat` (non-streaming) limitation**, not a Phase 1 Part A regression — the streaming endpoint `/api/chat/stream` emits all text via `delta` events progressively, so the **UI (`useAIChat` → `postChatStream`) sees the full reply**. No UI-facing bug; non-streaming scripts must inspect `history` (or add intermediate text accumulation, future polish)
- **Live test artifact**: test-created journal entry `journal_886cce34` was left in place (the AI's recommendation — to audit Ozurgeti's expense attribution — is a legitimate business suggestion worth preserving, not a synthetic smoke datum)
- **Scratch cleanup**: 4 `_scratch_phase1a_*` files deleted; `_banner_snapshot.txt` helper deleted; zero repo pollution

### AI Genius Phase 1 Part B — CODE COMPLETE ✅ (2026-04-20 01:00)

**Scope**: Georgian regulation + franchise-context knowledge layer. Give chat-mode AI awareness of VAT/pension deadlines, RS.ge e-invoice rules, franchise royalty/sourcing norms, monthly cash-rhythm, and a baseline-facts-in-journal contract. Investigator prompt intentionally untouched.

**User approval**: "კი" → default scope (🔵 A Narrow + 🔵 I Auto-journal placeholders + 🔵 α Journal placeholder for tax/VAT status).

#### Files touched
- `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` — new `🇬🇪 ქართული რეგულაცია (CRITICAL — Phase 1 Part B)` section inserted between `🗺️ პროექტის რუკა` and `⚖️ წყაროების იერარქია` (5 sub-sections, ~550 tokens):
  - `💰 საჯარო გადასახადები` — 5-row markdown table: **VAT 18% day 15** + **საპენსიო ფონდი 2% + 2% day 15** + **Income tax standard 15% / small-business 1% (< 500K ₾)** + **VAT threshold < 100K ₾ turnover** + **Penalty CB discount rate + 1%/year on overdue taxes**
  - `🧾 RS.ge` — e-invoice 30-day unpaid warning (reputation + საურავი); waybill 3-date-field cross-reference (`date` / `transport_start_date` / `delivery_date`)
  - `🏪 ფრენჩაიზი` — 4-row context table: Royalty 4-7% / Sourcing 60-75% / Opening fee $5-20K / Brand standards; explicit consequences (`contract breach`, `royalty freeze`, `termination`); Royalty marked `📌 ვარაუდი` — AI must ask user's contract number and store in journal
  - `📋 Baseline facts` — 4 user-specific facts to ask + journal-store: (1) Royalty %, (2) Sourcing obligation %, (3) income tax status (მცირე ბიზნესი / standard / ფიზ. პირი), (4) VAT registration status; tags convention `topic:franchise` + `topic:tax` + `kind:reminder`; `ask-not-guess` rule explicit
  - `🌅 ქართული თვის რიტმი` — 4-row day-bucket table (**1-10 post-deadline calm** / **11-14 pre-deadline stress** / **15 🚨 deadline day** / **16-30 revenue accumulation**) + 3 recommendation rules ("cash-intensive in 5-10", "**15-ე-ს შემდეგ** qualifier in 12-14", "next-month preparation reminder in 16-25")
- Investigator prompt `SYSTEM_PROMPT_KA_INVESTIGATOR` — **untouched** (4 do-not-touch tests assert that)

#### Tests
- `tests/test_ai_prompts_phase1b.py` (**NEW — 42 cases / 8 classes**):
  - `TestGeorgianRegulationSection` 5 — header present + Phase 1 Part B tag + Georgia operating context + 4 sub-section presence + **topological position** (after 🗺️ პროექტის რუკა, before ⚖️ წყაროების იერარქია)
  - `TestTaxRules` 8 — VAT 18% + pension 2/2 + day-15 anchor + small-business 1% + standard 15% + 500K threshold + 100K VAT threshold + CB+1% penalty
  - `TestRsGeRules` 3 — e-invoice 30-day + waybill 3 date fields + waybill-semantics cross-reference
  - `TestFranchiseContext` 6 — royalty 4-7% + sourcing 60-75% + opening fee $5K-20K + brand standards + violation consequences (breach/freeze/termination) + `📌 ვარაუდი` mark on royalty
  - `TestBaselineFacts` 8 — section header + 4 enumerated facts + `journal_add_entry` reference + `kind="reminder"` + `topic:franchise` + `topic:tax` + `ask-not-guess` rule + `recall_context` / `journal_list_entries` mechanism references
  - `TestMonthlyRhythm` 5 — section header + day-15 marked deadline day + 4 buckets + cash-intensive rule + `15-ე-ს შემდეგ` qualifier rule
  - `TestBuildSystemPromptWiring` 3 — chat mode exposes Part B section + chat mode exposes baseline mechanism + investigate mode hides Part B
  - `TestInvestigatorPromptUntouched` 4 — investigator has no Phase 1 Part B marker / no 🇬🇪 section / no Baseline facts / no monthly rhythm
- **pytest 860/860 green** (was 818; +42 new; 0 tests weakened or deleted)

### AI Genius Phase 1 Part B — LIVE VERIFIED ✅ (2026-04-20 01:28)

#### Backend restart #7
- Old PID 11620 (Part A active) stopped via `Stop-Process -Id 11620 -Force`; port 8000 freed; restarted via `$env:AI_ENABLE_THINKING='true'; & '...\venv\Scripts\python.exe' -u server.py` → new **PID 36460** on parent venv
- Verification (**Win32_Process.CommandLine + in-process 15-marker scan**):
  - `CommandLine` = `"...\venv\Scripts\python.exe" -u server.py` ✅ (parent venv — NOT system Python 3.14 stub)
  - In-process SYSTEM_PROMPT_KA contains all 15 Part B markers: `🇬🇪 ქართული რეგულაცია` / `Phase 1 Part B` / `VAT (დღგ)` / `18%` / `საპენსიო ფონდი` / `Royalty` / `4-7%` / `Sourcing obligation` / `60-75%` / `Baseline facts` / `topic:franchise` / `topic:tax` / `🌅 ქართული თვის რიტმი` / `deadline day` / `cash-intensive` ✅
  - All 15 markers ABSENT from investigator prompt (do-not-touch honored) ✅
  - `/api/status` 200 OK; scheduler running; data loaded ✅

#### Live Anthropic dog-food (1 scripted in-process `AIAgent.chat(think=True)` call)
- **Question**: `"დღეს 20 აპრილი, 2026. ოზურგეთის მაღაზიისთვის ვგეგმავ 20,000 ₾-იან ინვესტიციას POS ტერმინალების განახლებაზე. თვის დასაწყისი დავიანგარიშო ეს მიზანი ეხლა გავაკეთო (აპრილში), თუ პირველი რიცხვებისთვის მოვიცადო (მაისი/ივნისი)? cash-planning-ზე როგორ იმოქმედებს?"`
- **Model behavior — all Phase 1 Part B markers + carryover Part A markers in one reply**:
  - 🎭 **4/5 hats fired** (💼 ფინანსური / ⚠️ რისკის / 🎯 სტრატეგი / 🪞 კრიტიკოსი) — 🔧 ოპერაციული skipped (capex timing doesn't need tech perspective — correct hat economy)
  - 🎯 **Multi-hypothesis** — 3-version probabilistic split `ვერსია 1 (40%) / ვერსია 2 (35%) / ვერსია 3 (25%)`
  - 🎯 **Confidence stack** — final რეკომენდაცია tagged `🟢 საიმედო`; multiple `🟡 ვარაუდი` inline on domain-knowledge claims
  - 📌 **ვარაუდი mark** — e.g. `"(seasonality: მომწოდებლები ზაფხულამდე ფასს ამაღლებენ 📌 ვარაუდი 🟡)"` on unverified supply-chain claim
  - 🇬🇪 **Monthly rhythm rule LIVE-applied** — recommended staggered timing: "**2026-04-20 — 2026-04-30:** 1 ტერმინალი" + "**2026-05-16 — 2026-06-01:** მე-2 ტერმინალი, **15-ის deadline-ის შემდეგ** (VAT/საპენსიო)" — cross-referenced to the month-rhythm rule in Part B section verbatim
  - 🇬🇪 **VAT + საპენსიო 15 მაისი deadline** — explicit mention `"15 მაისამდე VAT + საპენსიო ფონდი"` in the risk bullet
  - 📋 **Baseline facts mechanism LIVE-invoked** — AI called `recall_context(query="VAT სტატუსი შემოსავლის გადასახადი მცირე ბიზნესი cash planning")` as the Part B section prescribes (search journal+memory for user's baseline tax facts before giving cash-planning advice); 5 hits returned
  - 🔧 **Strict tone** — direct critique `"ROI ბუნდოვანია"`, `"ოზურგეთი ამჟამად revenue-ზე შეზღუდული არ არის — ის ხარჯ-შეზღუდული (ან ატრიბუციის-პრობლემა) ობიექტია"`; zero flattery detected
  - 📎 **Inline source attribution** — present throughout the response
  - 💾 **Auto-persistence surprise (encore)** — AI invoked `journal_add_entry` creating `journal_15c67afa...` (`kind=recommendation`, title "ოზურგეთის ხარჯების ატრიბუციის გამოძიება — რომელი ხარჯები ნამდვილად მაღაზიის და რომელი გაუნაწილებელია"); post-run **cancelled** via `update_journal_entry(status="cancelled")` because it was a scratch-triggered artifact, not a genuine user commitment. Part A's `journal_886cce34` left open (still a legitimate business suggestion)
- **Numbers produced — all tool-verified**: Ozurgeti 2026-03 baseline forecast 57,643 ₾ / 2026-04 59,465 ₾ / 2026-05 60,722 ₾ (sum Q2 = 177,830 ₾); Ozurgeti YoY -12.47%; AP Days 163; ~860K ₾ debt; Ozurgeti -78K/თვე net
- **Tool-call sequence** (10 calls under 12-iter cap):
  1. `journal_list_entries(status="open", limit=20)` → 2 carry-over recommendations
  2. `read_data_json(cashflow_summary)` → section not present (AI adapted gracefully)
  3. `read_data_json(monthly_pnl, limit=6)` → 6 rows + total_count 44
  4. `forecast_revenue(store="ოზურგეთი", horizon_months=3)` → yoy -12.47%, last_12m 647,443 ₾
  5. `read_data_json(monthly_pnl, limit=6, columns="all")`
  6. `read_data_json(executive_summary)`
  7. `recall_context(query="VAT სტატუსი შემოსავლის გადასახადი მცირე ბიზნესი cash planning")` → 5 hits
  8. `compute(operation="sum", [57642.65, 59465.38, 60722.09], label="ოზურგეთი Q2 2026 baseline forecast ჯამი")` → 177,830.12 ₾
  9. `read_data_json(monthly_pnl, filter={month:"2026"}, columns="all")` → 2 rows
  10. `read_data_json(supplier_aging, limit=10)` → 193 total
- **Metrics**:

| Metric | Value |
|---|---|
| elapsed | 111.72 s |
| tool iterations | 10 tool calls (under 12 deep cap) |
| input tokens | 30,197 |
| output tokens | 4,507 |
| cache_read_input_tokens | **108,127** — Anthropic prompt-cache warm from the Part A session earlier |
| cache_create_input_tokens | 0 (fully warm) |
| stop_reason | `end_turn` (natural completion; no max-iterations fallback) |
| HTTP status | 200 OK — no retries, no SDK backoff |
| cost (Sonnet 4.6 pricing) | ≈ **$0.19** (~$0.091 uncached + $0.032 cache_read + $0.068 output) |

- **`<TODAY>` block render** (2026-04-20 ორშაბათი): weekday hint `კვირის დასაწყისი — დაგეგმე`; May 15 VAT + საპენსიო deadline = 25 days away → outside 10-day horizon → `⏰ უახლოესი ვადები` section **suppressed** ✅ (correct behavior for far-future deadlines); `⏳ ღია დაპირებები (2)` shows Part A recommendation carried over
- **Scratch cleanup**: `_scratch_phase1b_dogfood.py` deleted end-of-session; zero repo pollution

### Next active work (post Phase 1 Part B live)

- **Phase 1 Part C preview** (from `AI_GENIUS_PARTNER_PLAN.md` v2.1 § 1.12) — `PHASE_1_PART_C_PREVIEW.md` for Multi-Store DNA (ოზურგეთი urban tourist 3 POS 12-საათიანი vs დვაბზუ rural weekend-peak 2 POS 8-საათიანი baked into `SYSTEM_PROMPT_KA`; product mix / seasonality / supplier preference / price elasticity differences; ~0.5-1 dev day)
- **Phase 2 kickoff** (after Part C) — Dead Stock Liquidation (2.11) + Supplier Negotiation Prep (2.12), same preview-first workflow as Part A/B/C
- **Parking Lot (not blocking Phase 1)**:
  - Embedding-model upgrade to `intfloat/multilingual-e5-large` (~580 MB, ~3–4× slower) if Georgian abbreviations ever need to rank correctly WITHOUT Latin aliasing
  - `python index_project_files.py --full --replace` overnight pass for coverage beyond the current 2000-row sampling cap
  - Dashboard UI surface for decision journal (Phase 3.4 `Decision Journal Tab` in `AI_GENIUS_PARTNER_PLAN.md` v2.1 — currently chat-only)
  - Prompt polish: "ვალი გადაცილებულია" for a specific supplier → bias towards `kind="promise"` instead of `kind="reminder"` (observation from Sprint 4 dog-food)
- **Deprecated (preserved)**: old Phase 3 Daily Briefing + Telegram push + provider migration POC — user explicitly rejected 2026-04-18 afternoon

### Key references
- **`AI_GENIUS_PARTNER_PLAN.md` v2.1** — authoritative 5.5-6 week, 5-phase AI plan (replaces AI_ADVISOR_ROADMAP.md Phase 3+ entirely)
- **`PHASE_0A_PREVIEW.md`** — plain-Georgian Before/After preview used for user approval
- `AI_ADVISOR_ROADMAP.md` — legacy (Phase 1-2 evidence only; Phase 3+ deprecated)
- `CONTEXT_HANDOFF.md` — canonical short brief for new chats
- `.env.example` — environment template (do NOT commit `.env`)
- `HANDOFF_ARCHIVE/2026-04-packet-h.md` — full Packet H evidence archive

---

## 1. Canonical startup / short handoff protocol

- ახალი ჩატის default startup order:
  1. `PLAN.md`
  2. root `AGENTS.md`
  3. `financial-dashboard/CONTEXT_HANDOFF.md`
- `financial-dashboard/HANDOFF.md` გახსენი მხოლოდ მაშინ, როცა გჭირდება:
  - file-level evidence
  - ძველი verification შედეგები
  - runtime caveat-ები
  - process acceptance criteria
- თუ მომხმარებელი წერს `მოამზადე ახალი ჩატისთვის`:
  1. ჯერ განაახლე `financial-dashboard/CONTEXT_HANDOFF.md`
  2. ჩატში დააბრუნე მხოლოდ იქ არსებული copy/paste brief
  3. სრული history არ ჩასვა
- ყოველი ახალი ქმედების დაწყებამდე ჯერ მომხმარებლისგან `კი` / `არა` დადასტურება აიღე
- ამ დადასტურების მოთხოვნას ზედმეტი ახსნა არ დაურთო
- `კი` => გააგრძელე შემდეგი ქმედება
- `არა` => გაჩერდი და დაელოდე ახალ მითითებას

## 2. Archived history

Full Packet H evidence (Processes 0-12, verification matrices, file-level diffs, Session 2026-04-17 sessions) lives in:

- [`HANDOFF_ARCHIVE/2026-04-packet-h.md`](HANDOFF_ARCHIVE/2026-04-packet-h.md)

Open it only when you need:
- file-level evidence for a specific Process
- exact runtime caveats, DOM selectors, artifact regeneration steps
- proof of acceptance (UI + API + source cross-check + no-filter baseline)

## 3. Next active work — AI Advisor Phase 1 (MVP Chat)

See `AI_ADVISOR_ROADMAP.md` § 5 Phase 1 for the scope.

### Phase 0 sign-off (2026-04-17)

- **Step 0.1 ✅** — Packet H closed; `AI_ADVISOR_ROADMAP.md` authored.
- **Step 0.2 ✅** — Data Quality Audit passed (9.8/10); 3 Excel↔data.json validations matched.
- **Step 0.3 ✅** — Code Hygiene: `deprecated-root-copy/` archived (1.09 GB), `requirements.txt` pinned, `.env.example` created, `.gitignore` hardened.
- **Step 0.4 ✅** — External setup + test pings:
  - Anthropic account + $100 credits (auto-reload disabled)
  - API key stored locally in `C:\Users\tengiz\OneDrive\Desktop\claude_key.txt` (108 chars, `sk-ant-` prefix)
  - Telegram bot `@ioli_market_ai_bot` created via `@BotFather`; initial token revoked after in-chat leak; new token stored locally in `C:\Users\tengiz\OneDrive\Desktop\telegram_token.txt` (46 chars)
  - `.env` populated via `ping_anthropic.py` + `ping_telegram.py` helpers at project root; secrets never transited chat
  - Anthropic live ping OK — model `claude-sonnet-4-6` replied in Georgian, 85+34 tokens
  - Telegram live ping OK — message_id 8 delivered to chat_id 6805108691 (recipient: ამირანი)
- **Step 0.5 ✅** — This sign-off:
  - HANDOFF.md split: historical content → `HANDOFF_ARCHIVE/2026-04-packet-h.md`
  - `CONTEXT_HANDOFF.md` updated to reflect Phase 0 complete
  - `PLAN.md` updated: active mode → AI Advisor Phase 1 MVP
  - `AI_ADVISOR_ROADMAP.md` model references updated (Sonnet 3.5 → 4.6, Haiku 3.5 → 4.5)

### .env keys provisioned

| Key | Status | Notes |
|---|---|---|
| `DASHBOARD_API_KEY` | empty | existing auth; intentionally unset for local dev |
| `ANTHROPIC_API_KEY` | ✅ filled | 108 chars, `sk-ant-` prefix |
| `AI_MODEL` | `claude-sonnet-4-6` | primary |
| `AI_MODEL_FALLBACK` | `claude-haiku-4-5-20251001` | fallback |
| `TELEGRAM_BOT_TOKEN` | ✅ filled | 46 chars |
| `TELEGRAM_CHAT_ID` | `6805108691` | private chat with user |

### Guard rails carried into Phase 1

- Canonical backend interpreter remains: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`.
- `.env` is git-ignored by `.env` + `*.env` patterns; defensive `.gitignore` additions (`claude_key*`, `telegram_token*`, `*_key.txt`, `*_token.txt`, `secrets/`).
- `ping_anthropic.py` and `ping_telegram.py` are kept at project root as reusable health-check scripts; they never echo secrets.
- API keys / tokens must never transit chat. Always use local file + shell redirect / script.
- `cashflow` remains documented intentional exception (internal per-section calendars by design).

### Open for next session

- Phase 1 (MVP Chat) — see `AI_ADVISOR_ROADMAP.md` § 5 Phase 1.
- Begin with `dashboard_pipeline/ai/__init__.py` + `dashboard_pipeline/ai/agent.py` + `dashboard_pipeline/ai/tools.py` + `server.py` `POST /api/chat` endpoint + `rs-dashboard/src/components/ChatAssistant.jsx`.
- Rate limit: 30/min (existing `slowapi` middleware already available).
- Tests: extend `tests/` with `test_ai_agent.py` + `test_ai_tools.py`.

