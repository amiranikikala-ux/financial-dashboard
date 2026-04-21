# CONTEXT HANDOFF — ახალი ჩატისთვის

> განახლდა: 2026-04-21 13:25 UTC+04:00 (AI FAB disappearance hotfix + launch-script idempotency)
> სტატუსი: **🔧 AI FAB stability hotfix — LIVE VERIFIED ✅** (2026-04-21 13:25) — user-მა იწვია "AI chat ღილაკი ხშირად ქრება #suppliers tab-ზე", 2-3 ცდაში root-cause-ი აღმოჩნდა **სამ-ფენიანი**: (1) `rs-dashboard/src/App.jsx` — `ChatAssistant` `React.lazy()`-ით იყო + `<Suspense fallback={null}>`, ე.ი. slow chunk fetch → fallback რენდერდა სრული ცარიელი (no FAB); (2) `rs-dashboard/src/main.jsx` — dev-mode Service Worker cleanup `window.addEventListener('load', …)`-ში იყო, ანუ React უკვე დამონტაჟდებოდა SW-cache-ული `index.html`-იდან; (3) canonical vs duplicate — OneDrive-ის გამო `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\rs-dashboard\` (OUTER) იდგა, პარალელურად `financial-dashboard\rs-dashboard\` (INNER, git-tracked); (4) `Run_Dashboard_Quick.bat` ერთხელ-ხოცავდა port 8000-ზე listening process-ს → Phase 4A Windows Service `FinancialDashboardBackend`-საც ხოცავდა. **ფიქსები მიღებული**: (A) `App.jsx` — `ChatAssistant` **eager import** (lazy + Suspense მოვშალე) + ახსნა-კომენტარი; (B) `main.jsx` — SW cleanup **synchronously before React mount**, active-controller detection + single-shot auto-reload via `sessionStorage['rs-sw-reset-done']`; (C) OUTER `rs-dashboard/` — 73 ფაილი, 0 უნიკალური (INNER-ში ყველაფერი არის, verified via `HashSet`-based diff of 127 vs 73 files); rename to `_ARCHIVE\rs-dashboard_OLD_2026-04-21_pre_ai_fab_fix\` ცდა → **EBUSY** (OneDrive sync lock — **არა destructive**, მხოლოდ cleanup, skip); (D) `Run_Dashboard_Quick.bat` — **idempotent mode**: `:8000` health-check პირველ რიგში → if healthy `goto vite_check`; `:5173` health-check → if healthy `goto open_browser`; მკვდარი Windows Service აღარ ხოცავს (Phase 4A work რესპექტდება). **E2E regression guard**: `rs-dashboard/e2e/ai-chat.spec.js` +2 new tests (`FAB stays visible across all tab hash routes` 17 hashes + `FAB remains visible while global loading spinner is showing`). **Live verification**: `curl -sI http://127.0.0.1:5173/` → HTTP 200; `curl -s .../src/App.jsx | findstr ChatAssistant` → `import ChatAssistant from "/src/components/ChatAssistant.jsx"` + `_jsxDEV(ChatAssistant,…)` no Suspense; `curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/api/data?tab=suppliers` → HTTP 200 (Windows Service PID 24364 untouched). **User action required**: Chrome-ში გახსენი `http://127.0.0.1:5173/#suppliers` (ჩემი diagnostic-ის დროს Chrome tab-ი შემთხვევით taskkill /T-ში გაქრა — ბოდიში). **Known limitation**: OUTER rs-dashboard rename EBUSY-ია → შემდეგ სესიაში, OneDrive sync pause-ის შემდეგ, ხელახლა ვცადოთ (ახლა harmless, 0 tooling references OUTER — INNER-ია canonical).
>
> წინა-სტატუსი: **📋 Phase 4B + 4C — AI Personality & Tool Design Tuning — PLANNED** (2026-04-21 04:57) — ამ სესიაში **code არ შეცვლილა** (research-only). ჩატარდა **ღრმა 4-tier წყაროს კვლევა** Anthropic-ის ოფიციალური best practices + leaked system prompt-ებისთვის: (1) `docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices` + `code.claude.com/docs/en/best-practices`; (2) `anthropic.com/engineering/building-effective-agents` (Dec 2024 foundational blog — 5 workflow patterns + Appendix 2 Poka-yoke tools); (3) leaked prompts — Claude Sonnet 4.5 (2025-11-19 `jujumilk3/leaked-system-prompts`) + Claude Opus 4.6 (`asgeirtj/system_prompts_leaks`) + Simon Willison May 2025 analysis; (4) **🆕 GPT-5 leaked prompt** (Aug 2025 `asgeirtj/OpenAI`) — 3 orig. concepts. **შედეგი**: **31 წესი** 5 tier-ად (9 fundamental + 7 personality + 9 format + 4 anti-pattern + 2 tool design), **5 sprints ~5.5-6 days / ~$0.95 AI cost**. **🚨 CRITICAL finding**: `SYSTEM_PROMPT_KA` = **1,291 lines** currently — Anthropic explicitly warns ">1000-line CLAUDE.md gets half-ignored", ergo **Sprint 4B.0 (Ruthlessly Prune, 1,291 → ~900 lines) is prerequisite** before adding new rules. **ამ სესიაში შეიქმნა/განახლდა 3 ფაილი**: (A) `PHASE_4B_PROMPT_TUNING_PREVIEW.md` NEW (~470 lines, 12 sections — scope/pain-points/31-rule table/CRITICAL-discovery/5-sprint-breakdown/6 Before-After examples/risk/cost/verification/out-of-scope/success-criteria/7 Open-Questions); (B) `PLAN.md` — Phase 4B+4C bullet added between "Backend restart #17" and "Parking Lot" (v2.1 additions list); (C) `CONTEXT_HANDOFF.md` — this update. **ხვალინდელი session-ის workflow**: (1) user reviews Preview 12 sections + 7 Open Questions decisions; (2) Sprint 4B.0 Prune starts — offline, prompts.py only, ~2-3 hours, verify pytest 1443/1443 green; (3) Sprint 4B.1 Tier-1 fundamental (9 rules) — 1.5 days with live dog-food; (4) Sprints 4B.2-4B.3 and 4C.x thereafter. **Backend live**: Windows Service `FinancialDashboardBackend` PID 24364 (unchanged this session). **No code, tests, or backend state was modified**.
>
> წინა-სტატუსი: **🏁🏁 Phase 4A FULLY CLOSED + Backend Perma-Up via Windows Service ✅** (2026-04-21 04:15) — ამ სესიის ორი დასრულებული milestone: **(A) Phase 4A FULLY CLOSED** (Part A + Part B end-to-end live verified — AI autonomous tool call + UI regenerate + UI approve + journal entry + 3rd bug-fix `App.jsx:307` `showGlobalLoading` exclusion for `debt_plan`); **(B) Windows Service installed** — NSSM 2.24 downloaded + `FinancialDashboardBackend` service registered (auto-start on boot, auto-restart 2s after crash, env `AI_ENABLE_THINKING=true`+`PYTHONUTF8=1` persisted, log rotation 10MB/24h in `logs/backend_stdout.log`+`backend_stderr.log`), verified `Status=Running, StartType=Automatic` + PID 24364 LISTEN 8000 + `/api/status` 200 + `/api/chat` `thinking=True`. **Backend never dies again** — control via services.msc "Financial Dashboard Backend" Start/Stop/Restart OR `Restart-Service FinancialDashboardBackend` OR `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit} FinancialDashboardBackend`. **"Backend restart #N" counter retired.**
>
> წინა-სტატუსი: **🏁 Phase 4A Debt Repayment Plan — FULLY CLOSED ✅** (2026-04-21 04:02) — Part A + Part B ორივე ცოცხლად დადასტურებულია. ამ სესიაში დამთავრდა ყველა pending item: (1) `/api/chat/stream` dog-food "შემიდგინე ვალების გეგმა" → AI-მ თავისით გამოიძახა `build_debt_repayment_plan` 49.7s-ზე, `usage.thinking=true`, `stop_reason=end_turn`, 91.2s elapsed, Georgian 5-section brief (ჯიდიაი #1 313,922 ₾, 2-თვიანი arithmetically unsustainable 246K/თვე vs 140K forecast); (2) UI regenerate click-through (Vite 5173 + Playwright MCP): `#debt_plan` auto-load → 2→6 თვე ხანგრძლივობის ცვლილება → `🔄 ახალი გეგმა` → re-render (246K/თვე → 85.7K/თვე, buffer −139.2% → −25.0%); (3) UI approve click-through: `✅ ვეთანხმები — შენახვა` → `POST /api/debt-plan/save` 200 OK → journal entry `journal_816295fd222b495199c30599510d8d7f` title *"ვალების გეგმა — 5 priority @ GEL 85,700/თვე (6-თვიანი)"* status `🟡 open` — cross-verified via `/api/chat` query + `journal_list_entries` AI tool call; (4) `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B section + LIVE VERIFIED ბანერით განახლებულია. **🐞 3rd bug-fix en-route**: `rs-dashboard/src/App.jsx:307` — `showGlobalLoading` exclusion list-ში `debt_plan` არ იყო (იყო მხოლოდ `insights`/`imported_products`/`waybills`). `loading` state default-ით `true`-ია, flip-ს მხოლოდ მთავარი `/api/data` useEffect აკეთებს, რომელიც debt_plan-ზე early-returns → UI მუდმივად "იტვირთება მონაცემები..." ეკრანზე რჩებოდა. **Fix**: `activeTab !== 'debt_plan'` guard დამატება (1-line root-cause, იგივე pattern insights/imported_products/waybills-სთვის). Backend **restart #17** PID **5388** parent-venv, `/api/status` 200 OK, `TOOL_SCHEMAS=18`, `AI_ENABLE_THINKING=true`. ყველა დარჩენილი verification-pending item ამ სესიაში დაიხურა. Phase 4A ოფიციალურად დახურულია.
>
> წინა-სტატუსი: **🎉 Phase 4A Debt Repayment Plan — Part B LIVE VERIFIED + 2 BUG-FIX ✅** (2026-04-21 02:35) — Part B ცოცხლად გადამოწმდა და ორი root-cause ბუგი დაფიქსირდა. **(1) Schema bug**: `debt_plan.py::_active_debt_suppliers` მოელოდა `supplier_aging`-ს როგორც `{"suppliers": [...]}` dict, მაგრამ production `data.json`-ში ის პირდაპირ **list**-ია (193 row). პირველი POST smoke აბრუნებდა `{"error": "ვალი არ აქვთ"}` 285B — root cause იდენტიფიცირდა, `_active_debt_suppliers` გაუფართოვდა list+dict abatements-ით, 4 new regression test (`TestSupplierAgingListSchema`). **(2) Ranking bug**: top-5 priority-ში 1,434-დღიანი zombie მომწოდებლები (Bau-Tech 435 ₾ #1) იდგნენ, რეალური 313K ₾ active debtor (ჯიდიაი) #30 პოზიციაზე იყო. Formula dominant weight "ასაკი"-ს ჰქონდა. **Fix**: (a) `ACTIVE_CUTOFF_DAYS=365` — dormant supplier auto-detect priority pool-იდან გამოირიცხოს (user-named priorities exempt); (b) weight rebalance: debt 0.30→**0.50**, aging 0.25→0.15, freq 0.25→0.20, dysfunc 0.20→0.15 — ჯიდიაი ახლა **#1 score 0.585** (was #30 score 0.412). 6 new regression tests (`TestDormantSupplierQuarantine`). **Live POST smoke**: 2-თვე → unsustainable (246K/თვე > 140K inflow — realistic); 6-თვე → უკეთესი (priority 85,700 ₾ = 61% forecast) მაგრამ baseline still exceeds — business cash deficit 35K ₾/თვე ცხადად. **UI click-through**: Playwright navigate `#debt_plan` → auto-gen render OK (3 cards + risks list + 5 priority table rows + approve/regen buttons); row expansion click → "💡 რატომ კრიტიკული" + analysis text visible; backend crashed once mid-session (unknown cause, restart #16 PID 18960 restored). pytest **1443/1443 green** (was 1433, +10 new: 4 schema + 6 ranking; 0 weakened). `DebtPlan.jsx` (~600 lines) unchanged — behaves correctly now that API returns real data. **⚠️ Approve/save + regenerate button clicks not UI-tested yet** (backend crash interrupted); journal endpoint `/api/debt-plan/save` smoke also deferred. **ამ სესიაში landed**: (1) `server.py` — `from typing import Any` import-ი დაემატა ახალი helper signatures-ისთვის (Part A-ში ეს ჩატერიალდა, მაგრამ import აკლდა — ბარიერად იდგა); endpoints POST `/api/debt-plan` + POST `/api/debt-plan/save` **რეგისტრირებულია**-დადასტურებული `import server` + route introspection-ით. (2) `dashboard_pipeline/ai/tools.py::JOURNAL_KINDS` mirror-tuple სინქრონიზებულია `journal.py`-სთან — 5 → 6 (`repayment_plan` ბოლო; Phase 3.1 proposal + Phase 4A repayment_plan). (3) `tests/test_api_debt_plan.py` **NEW 39 cases** — helper coercion (8 `_coerce_optional_int` + 9 `_coerce_priority_list`) + `/api/debt-plan` endpoint (9 happy/validation via `TestClient` + monkeypatched `build_debt_repayment_plan`) + `/api/debt-plan/save` endpoint (9 happy/validation via monkeypatched `add_journal_entry`) + 2 route-registration guards + 2 `JOURNAL_KINDS` length/membership guards. (4) `tests/test_ai_journal.py::TestJournalConstants::test_kinds_tuple` — 5-tuple → 6-tuple assertion update (added `repayment_plan`). (5) Frontend: `rs-dashboard/src/tabConfig.js` — `debt_plan` tab დამატებული `ანალიტიკური` ჯგუფში `dead_stock`-ის შემდეგ label `📋 ვალების გეგმა`. (6) `rs-dashboard/src/DebtPlan.jsx` **NEW ~600 lines** — auto-generate on mount via POST `/api/debt-plan`; 3-card strip (ForecastCard burn-trend color / AllocationCard sustainable boolean / NonPriorityCard baseline); PriorityTable with expandable rows (criticality reasons + rationale_ka + days_since_last + criticality_score); RisksBox; duration/priority dropdowns (1/2/3/4/6 თვე × Top-3/4/5/6/8); Approve → `/api/debt-plan/save` with structured tags (`phase4a` / `duration:Xmo` / `priority_count:N` / `sustainable:bool`); 🔄 Retry button; inline-styled dark theme matching DeadStock pattern. (7) `rs-dashboard/src/App.jsx` — lazy-imported `DebtPlan`, excluded `debt_plan` from generic `/api/data` fetch useEffect (page manages own POST), added route block `activeTab === 'debt_plan'`. **Verified ამ სესიაში**: pytest **1433/1433 green** (was 1393 → +40 new/adjusted; 0 weakened); `npx eslint src/DebtPlan.jsx src/App.jsx src/tabConfig.js` → 0 warnings; `npm run build` → clean, `DebtPlan-BEEdSF67.js 16.26 kB / 4.43 kB gzip`; **Backend restart #14** PID **21408** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'` → `/api/status` 200 OK. **Pending (მომდევნო ჩატს)**: (a) ცოცხალი POST smoke `Invoke-WebRequest /api/debt-plan` ნამდვილი `data.json`-ით (priority_count + sustainable + forecast validation); (b) rs-dashboard dev server (`npm run dev` 5173) + Playwright main-app click-through `#debt_plan` tab → auto-generate loading state → priority table renders → expand row → regenerate → approve → journal `entry_id` returned; (c) optional end-to-end `/api/chat/stream` dog-food ("შემიდგინე ვალების გეგმა" → AI calls `build_debt_repayment_plan` tool + summarises to user); (d) docs — `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B section + PLAN.md v2.1 update.
>
> წინა-სტატუსი: **🎉 Phase 4A Debt Repayment Plan — Autonomous Strategist Part A COMPLETE + LIVE VERIFIED ✅** (2026-04-21 00:50) — **Phase 4 ფილოსოფიის ძვრა**: user-ის ცხადი critique-ს საპასუხოდ ("მინდა იყოს შენნაირი — თავისუფალი და ჭკვიანი, არ ჩაკეტილი; აზრებს მეუბნებოდეს, გეგმებს მისახავდეს და არა ვეუბნებოდე"), dashboard AI გადადის reactive Q&A → **autonomous strategic advisor**-ზე. ახალი `build_debt_repayment_plan` tool კომპონებს 1-2-თვიან ვალის შემცირების გეგმას **user input-ის გარეშე**: 4-ფაქტორიანი criticality score (ვალი 30% + ასაკი 25% + სიხშირე 25% + dysfunction 20%), 3-თვიანი moving-average inflow forecast ±10% bracket-ით, per-supplier recommended monthly/weekly + days-to-clear, non-priority baseline (historical × 90%), allocation summary (sustainable boolean), risks + 🪞 critic-ქუდი. `TOOL_SCHEMAS=18` (პლუსი build_debt_repayment_plan index 12-ზე). `SYSTEM_PROMPT_KA` gained 📋 ვალების გეგმა section ("AUTONOMOUS STRATEGIST" label, **BROAD triggers**, **IMMEDIATELY call** workflow, 5-part response format, critic mandate, anti-triggers route to `prepare_supplier_brief`/`compute_cash_runway`/`forecast_revenue`, cross-tool chain suggestions). Investigator prompt UNTOUCHED (0/7 markers). pytest **1393/1393 green** (was 1303, +90 new in `test_ai_debt_plan.py` + 7 existing pin bumps 17→18; 0 weakened). Backend **restart #13** PID **10800** + `AI_ENABLE_THINKING=true`. Live `/api/chat/stream` dog-food **12/12 PASS** across 3 scenarios: (A) BROAD trigger *"მინდა ვალების გეგმა"* → AI called tool with empty priority_suppliers + auto-detected top-5; (B) NAMED priorities *"ვასაძე + კოკაკოლა 2 თვეში"* → AI's FIRST call = `build_debt_repayment_plan(priority_suppliers=["ვასაძე", "კოკაკოლა"], plan_duration_months=2)`, then 13 more verifying tools, detected discrepancy between user-stated (12K/18K) vs data.json (10,977/13,825) and surfaced honestly; (C) ANTI-TRIGGER single-supplier *"ჯიდიაი leverage deep-dive"* → correctly routed to `prepare_supplier_brief`, NOT debt plan. All scenarios `usage.thinking=true` + `stop_reason=end_turn`. **Part B (React page + `/api/debt-plan` endpoint + journal kind `repayment_plan` + daily tracker) deferred** — current Part A is already usable via chat.
>
> წინა-სტატუსი: **🎉 Phase 3.5 + 3.7 + Cash Runway COMPLETE + LIVE VERIFIED ✅** (2026-04-20 23:50) — 3 ახალი ნაწილი: (1) `/api/data?tab=dead_stock` tab + React `DeadStock.jsx` გვერდი ("ანალიტიკური" ტაბ-ჯგუფი, `💀 Dead Stock`) — 3-bucket donut + 4-action salvage plan + Top-30 SKU table + 30%+ unmatched warning; (2) `/api/data?tab=supplier_concentration` tab + React `SupplierConcentrationWidget.jsx` ჩანერგილი `🏢 მომწოდებლები` ტაბის თავზე — HHI gauge + Top-5/10/20 share bars + Top-3 candidates table with leverage label + `#1 priority` steering; (3) `compute_cash_runway` AI tool — PULL-ONLY user-balance-required (mandatory "Ask first → Wait → Call tool with live numbers" workflow) + burn rate over last N months + runway label (🟢 SAFE ≥6mo / 🟡 WATCH 2-6mo / 🔴 CRITICAL <2mo / 🟢 PROFIT) + burn_trend honesty (stable/accelerating/decelerating/insufficient_history). **Backend pipeline:** `build_dead_stock_summary` + `build_supplier_concentration` pre-computed in `_build_analytics()`. Backend **restart #12** PID **20876** + `TOOL_SCHEMAS=17` + `AI_ENABLE_THINKING=true`. pytest **1303/1303 green** (was 1242, +61 new in `test_ai_cash_runway.py`; 6 existing pin tests bumped 16→17). Live verify: `/api/data?tab=dead_stock` returns available=True / frozen 1,492,970 ₾ / 2,003 stale-181-365 + 2,799 dead-365+ + 4,049 unmatched + Top-30 SKUs; `/api/data?tab=supplier_concentration` returns available=True / 270 suppliers / HHI 551 moderate / Top-5 41.93% + 10 candidates. Live `/api/chat/stream` dog-food 6/6 PASS (57.1s, `usage.thinking=true`, `compute_cash_runway(bog=52000, tbc=28000)` called → AI delivered full strategic brief: 3.2-თვე runway / 25,054 ₾/თვე burn stable / multi-hypothesis 3-version / Multi-Store DNA (ოზურგეთი vs დვაბზუ) / 🪞 critic self-critique ("3.2 თვე ოპტიმისტურია — სალაროს ნაღდი ამონაგები სისტემაში არ ჩანს") / cross-linked journal_886cce34 + `analyze_dead_stock` next-step). Investigator prompt UNTOUCHED (0/9 Cash Runway markers — do-not-touch rule holds).
>
> წინა-სტატუსი: **🎉 Phase 3.1 Co-Designer COMPLETE + LIVE VERIFIED ✅** (2026-04-20 17:50) — PULL-ONLY feature-proposal mode. Backend restart #11 PID **29400** + `TOOL_SCHEMAS=16` + new `propose_feature` tool + 🎨 Co-Designer prompt section. pytest **1242/1242 green** (was 1163, +79 net: 78 new in `test_ai_co_designer.py` + 1 renamed). Live `/api/chat/stream` dog-food **3/3 PASS, 0 failures**: (A) TRIGGER *"რას შემომთავაზებდი?"* → 3 structured proposals with 6 fields each + 🪞 critic self-critique + AI first checked existing proposals via `journal_list_entries` + `recall_context`, 146.1s, `usage.thinking=true` ✅; (B) ANTI-TRIGGER strategic *"რატომ margin −80%?"* → 0 `propose_feature` calls, analyzed via `compute` + 5× `read_data_json`, 75.4s ✅; (C) ANTI-TRIGGER data *"რამდენი მომწოდებელი?"* → 0 `propose_feature` calls, quick `read_data_json` lookup (270), 9.5s ✅. 3 real proposals AI generated during (A): "ხარჯების გაუნაწილებელი vs მაღაზიის Split — Live Dashboard Widget" / "Dead Stock — Salvage Tracker" / "Cash Runway Widget" — all with problem / benefit / mvp_scope / data_needed / time_estimate / risk_critique + journal ID + critic self-review; cancelled post-verification to keep journal clean. Investigator prompt **UNTOUCHED** (0/6 Co-Designer markers — do-not-touch rule holds).
>
> წინა-სტატუსი: **🎉 Phase 2.11 + 2.12 FULLY LIVE VERIFIED ✅** (2026-04-20 15:30) — Backend restart #10 + 3 ცოცხალი Anthropic dog-food ყველა PASS. Target state (`AI_ENABLE_THINKING=true` + `TOOL_SCHEMAS=15` + `MAX_TOOL_ITERATIONS_DEEP=12` + `DEFAULT_TIMEOUT_S=120`) სრულდება **PID 29332**-ზე. **Phase 2.12 Focused ჯიდიაი**: 9/9 PASS, 49.8s, tax_id `406181616` auto-resolved, match_confidence 🟢 HIGH, Leverage 🟢 HIGH 71/100, 17.2% portfolio share, 313K ₾ debt → 3 plays ranked (6% ფასდაკლება vs 313K ₾ 15-day payment / 3% volume discount + 61K blanket / price alignment fallback). **Phase 2.12 Portfolio (no identifier)**: 10/10 PASS, 49.1s, 270 suppliers / 5.2M ₾ spend / HHI 551 (moderate) / Top-5 41.9%; AI returned ranked Top-10 with leverage labels + Top-3 candidates with annual savings (ჯიდიაი 39.8K ₾ + კოკა-კოლა 27.1K ₾ + პარტნიორი 0.9K ₾) + `დაიწყე აქ` steering; `usage.thinking=true` ✅. **Phase 2.11 Dead Stock**: 9/9 PASS, 65.9s, `analyze_dead_stock(days_threshold=180, top_n=30, store="total")` + 3 `compute` aggregations; AI surfaced 30.3% unmatched warning (4,049 / 13,344 SKU barcode drift), 3-bucket breakdown (181–365d 2,003 SKU / 365d+ 2,799 SKU / unmatched 4,049 SKU), ~1,492,970 ₾ გაყინული ფული ზედა შეფასება, 3-action salvage plan (−30% discount → 452K ₾ | supplier return → 1,040K ₾ | write-off/audit for unmatched) + Top-10 specific products with last-sale date + recommended action. Session cost ≈ $0.48 for 3 dog-foods (fresh cache on portfolio, warm cache on dead_stock).
>
> წინა-სტატუსი: **🆕 Phase 2.12 — Supplier Negotiation Prep COMPLETE ✅** (2026-04-20 14:40) — AI-ს ცოცხლად დაემატა მომწოდებლის-მოლაპარაკების 1-გვერდიანი brief-ის გენერაცია. ახალი `prepare_supplier_brief(supplier_name|tax_id, lookback_months, top_n, benchmark_n)` tool triangulates `suppliers` × `imported_products` × `supplier_aging` into: **supplier identity + match_confidence** (high/medium/low) / **volume_snapshot** (spend, share, tenure, monthly_avg) / **payment_profile** (billed/paid/debt + unpaid % + reliability label) / **price_benchmark** (dual-source comparison rows + cheapest alternative + gap %) / **leverage_score 0-100** (5 weighted factors: portfolio_share 30 + payment_leverage 20 + dual_sourcing 20 + tenure 15 + relationship_health 15) / **1-3 ranked negotiation_plays** with `ask_ka` + `give_ka` + `rationale_ka` + `evidence_refs` + `warning_ka`. Portfolio mode (no identifier) returns HHI concentration + top_candidates ranked by `leverage × savings`. New `SYSTEM_PROMPT_KA` section `📞 მომწოდებელთან მოლაპარაკების მომზადება` between 💀 Dead Stock and 🔄 Self-Correction with triggers / anti-triggers / identity-confidence protocol / relationship discipline / portfolio-mode example. New module `dashboard_pipeline/ai/supplier_brief.py` (~1280 lines). `tools.py` grew to **TOOL_SCHEMAS=15** (was 14). Tool-count pins bumped 14→15 in 6 existing test files. 130 new tests (76 module `test_ai_supplier_brief.py` + 54 prompt-guard `test_ai_prompts_phase2_12.py`) — pytest **1163/1163 green** (was 1033 / wait: was 1109 after 2.11; +54 prompt-guard = 1163). One bug caught en-route: `_normalize_name` regex ordering — `( 123-დღგ ) შპს X` parenthetical cleanup left leading space that blocked `^შპს` anchor; fix = `lstrip()` before prefix regex. Zero backend regressions. **Backend restart + live Anthropic dog-food PENDING.**
>
> წინა-სტატუსი: **🆕 Excel Georgian Path Fix COMPLETE + LIVE VERIFIED ✅** (2026-04-20 12:45) — Phase 1 Part D dog-food-ში დაფიქსირებული `read_excel_source` Georgian folder ბუგი მოგვარებულია. ROOT CAUSE: Windows + OneDrive-ზე `Path.resolve(strict=False)` მიჰყვება OS-დონის junction-ებს / reparse points-ებს და როცა project root სიდის non-ASCII ancestor-ში (`AI აგენტი`), `resolve` ცარიელად ცვლიდა მდებარეობას `project_root`-ს გარეთ ხუთი Georgian subfolder-ისთვის (`ბოგ/თბს ბანკი ამონაწერი/`, `რს ზედნადები/`, ორი `გაყიდული პროდუქტები სოფ ...`/) — მხოლოდ `შემოტანილი პროდუქცია/` მუშაობდა. FIX: `dashboard_pipeline/ai/tools.py::_resolve_safe_path` — `.resolve(strict=False)` → `.absolute()` (lexical join + drive normalisation; symlink follow აღარ ხდება) + ცხადი `..` segment reject (traversal protection შენარჩუნებული). pytest **976/976 green** (was 969; +7 `TestResolveSafePathRegression`; 0 weakened). Live dog-food (იგივე BOG 2026-02 კითხვა, in-process AIAgent.chat(think=True), 120.1s, 9 sources): AI-მ პირდაპირ გახსნა `Financial_Analysis/ბოგ ბანკი ამონაწერი/02--2026.xlsx`, წაიკითხა მონაცემი (აიდიეს ბორჯომი თბილისი მომწოდებელი + PMD ტრანზაქცია), ცხადად აღნიშნა მხოლოდ ცალკე ლიმიტი (`read_excel_source` 200 row sample 1618-chunk ფაილისთვის — `parking-lot`-ი). Path-ბუგი აღარაა.
>
> წინა-სტატუსი: **Phase 1 Part D COMPLETE + LIVE VERIFIED ✅** (2026-04-20 02:50) — AI-მ ისწავლა საკუთარი თავის გასწორება. ცარიელი/ცუდი ცდა ≠ "არ არსებობს". `SYSTEM_PROMPT_KA`-ში ახალი `🔄 საკუთარი თავის გასწორების ციკლი` section (🔁 Retry Protocol 4 ნაბიჯი + 🎯 Self-Triage 3 hypothesis + 📢 Latin Alias MANDATORY 3-row anti-pattern table + 📅 თარიღის 3 ფორმატი + ❌ "ვერ ვიპოვე" 3+ ცდის prerequisite). pytest **969/969 green** (was 914; +55 `test_ai_prompts_phase1d.py`; 0 weakened). Investigator prompt **untouched** (do-not-touch rule — Sprint 1-4 + Part A + Part B + Part C + Part D; 15 Part D markers absent). ✅ Live dog-food **5/5 PASS** — იგივე BOG 2026-02 კითხვა (02:30-ზე false-negative დააფიქსირა) → AI-მ 17 tool call გააკეთო (4× recall_context Latin alias progression + 6× read_data_json + 3× read_excel_source + grep/read_source), 02--2026.xlsx მოიპოვა, structured "ვცადე: (1)... (2)... (3)..." fallback გასცა და user-ს 3 clarifying კითხვა დაუსვა. 🎉 **Phase 1 სრულად დასრულდა** (Part A + B + C + D).
>
> ✅ **Backend restart #9 DONE** — old PID 31176 stopped, parent-venv PID **7776** on 127.0.0.1:8000 with `AI_ENABLE_THINKING=true`. **Note (2026-04-20 12:45)**: PID 7776 ცოცხალი dog-food-ის დროს გამორთული აღმოჩნდა (port 8000 თავისუფალია); Excel-Path Fix in-process pattern-ით ვერიფიცირდა (AIAgent.chat პირდაპირ Anthropic-თან). მომდევნო backend launch-ი ავტომატურად ჩათვლის ფიქსს — code-ი მხოლოდ `tools.py`-ში შეიცვალა (no schema/contract change).
>
> ⚠️ Part D-ში გამოჩენილი caveat → ✅ **RESOLVED** (იყო `read_excel_source` blocks Georgian folder paths) — ფიქსი მოგვარდა ნამდვილ დროში; `parking-lot`-ში გადადის მხოლოდ ცალკე საკითხი: `read_excel_source` 200 row sample cap დიდი (1000+ row) Excel ფაილებისთვის არის შეზღუდული — მომავალში შეიძლება aggregation tool-ი დაემატოს (`compute_bank_total` / `compute_excel_aggregate` Phase 2.11-მდე ან ცალკე iteration-ად).
>
> 🐞 **Collateral from Part B — Backend restart pattern**: `Stop-Process -Id <old>; Start-Sleep 2; Get-NetTCPConnection -LocalPort 8000` verify empty; then `$env:AI_ENABLE_THINKING="true"; & '...\venv\Scripts\python.exe' -u server.py` non-blocking — გამოყენებით მთლიანი Part A/B/C cycle-ში.
>
> 🐞 **Windows venv caveat reinforced**: `Get-Process <pid> | Select Path` unreliable — always use `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` to confirm parent-venv activation. Verified PID 7776 = `"...\venv\Scripts\python.exe" -u server.py` via CommandLine + in-process 15-marker probe.
>
> 🐞 **Carried from Part A — Collateral 1-line production fix**: `DEFAULT_TIMEOUT_S` 60 s → **120 s** in `dashboard_pipeline/ai/agent.py:47` (stays; Phase 1 Part A + Part B heavier prompts + Extended Thinking keep this ceiling necessary).
>
> წინა-ისტორია (Phase 0B CLOSED — 2026-04-19 23:40): Sprint 4 Part 1 (Decision Journal code + LIVE CRUD + Anthropic dog-food) ✅ + Part 2 (Phase 0B-wide metrics ≈$0.25/7-call + ღრმა ფიქრის ლიმიტი 6→10) ✅ + Part 3 (docs refresh) ✅. 2 bug-fixes en-route ✅ (Windows venv Path-check caveat + ChromaDB 1.5.x `$lt`/`$gt` string-range caveat). დეტალური evidence HANDOFF.md-ში ნახე.
> 🐞 **2 bug fix this session**:
> (a) **Windows venv Path-check caveat** — `Get-Process <pid> | Select Path` Windows venv-ზე **ყოველთვის** base Python-ს აჩვენებს (venv stub პროცესის image-ად base-ს ირჩევს), მაგრამ ამას არ ნიშნავს რომ venv არ არის აქტიური. საიმედო verification: `Get-CimInstance Win32_Process | Select CommandLine` (ნახე venv\Scripts\python.exe path-ი command-line-ში). ასევე: პროცესიდან `sys.prefix` / `sys.executable` → venv-ზე მიუთითებს. PID 18076 **ნამდვილად** system Python 3.14 იყო (importlib-ით დადასტურდა რომ chromadb/anthropic MISSING — ე.ი. live AI ფუნქციები ფაქტობრივად გატეხილი).
> (b) **ChromaDB 1.5.x `$lt`/`$gt` string-ზე არ მუშაობს** — `journal_due_date` ISO string-ად იწერება, მაგრამ ChromaDB range operator-ები მხოლოდ numeric metadata-ზე არის მხარდაჭერილი. fix: date-range ფილტრაცია გადავიტანე Python-ის მხარეს (`_apply_python_date_filters`). Fake ChromaDB ტესტებში ამას სწორად ამუშავებდა — ამიტომ 109 ტესტი მწვანე იყო, მაგრამ ცოცხალ ChromaDB-ზე entry overdue bucket-ში არ ხვდებოდა. pytest 743/743 green (was 742 — +1 ახალი test `test_overdue_with_explicit_status_skips_auto_open`).
> მთლიანი წინა-ისტორია: Packet H ✅ | AI Phase 0 ✅ | Phase 1 MVP + Polish ✅ | Streaming SSE ✅ | Phase 2 Sprint 1/2/3 + Live + UI Dog-Food ✅ | Waybill Fix ✅ | Phase 0A ✅ | SW Cache Fix ✅ | **Phase 0B FULLY CLOSED ✅** (2026-04-19 23:40) | **Phase 1 Part A ✅** (2026-04-20 00:55) | **Phase 1 Part B ✅** (2026-04-20 01:28) | **Phase 1 Part C ✅** (2026-04-20 02:11) | **Phase 1 Part D ✅** (2026-04-20 02:50)

> ეს ფაილი არის **canonical short brief**. ახალი ჩატის startup order:
> `PLAN.md` → root `AGENTS.md` → `financial-dashboard/CONTEXT_HANDOFF.md`
> `HANDOFF.md` გახსენი **მხოლოდ მაშინ**, როცა გჭირდება file-level evidence, runtime caveat, ან ძველი sprint-ის ზუსტი ისტორია.

## `მოამზადე ახალი ჩატისთვის` — ზუსტი წესი

- ჯერ განაახლე ეს ფაილი.
- მერე ჩატში დააბრუნე ქვემოთ არსებული `Copy/paste brief`.
- ბრიფში დატოვე მხოლოდ:
  - verified facts
  - active do-not-touch rules
  - next recommended step
- სრული ისტორია, evidence, long narrative ამ ფაილში დატოვე, ბრიფში არა.

## canonical context snapshot

- workspace root: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი`
- project path: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard`
- backend interpreter (canonical): `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`
- backend server: **registered as Windows Service `FinancialDashboardBackend`** (NSSM-wrapped, 2026-04-21 04:15) running parent-venv `python.exe -u server.py` as **PID 24364**, `127.0.0.1:8000`, `AI_ENABLE_THINKING=true` — Phase 1 Part A + Part B + Part C + Part D + Phase 2.11 + Phase 2.12 + Phase 3.1 + Phase 3.5/3.7 Cash Runway + **Phase 4A Part A + Part B FULLY CLOSED** SYSTEM_PROMPT_KA + `MAX_TOOL_ITERATIONS_DEEP=12` + `DEFAULT_TIMEOUT_S=120` + **18-tool surface** (`build_debt_repayment_plan` at index 12, `propose_feature` at index 17) all LIVE. **Verified**: `Get-Service FinancialDashboardBackend` → `Status=Running, StartType=Automatic` + `/api/status` 200 OK + scripted `/api/chat` call returned `usage.thinking=True` (env propagation through NSSM confirmed). 🏁 **Recurring pain point RESOLVED**: no more manual restart. Service auto-starts on Windows boot; auto-restarts 2s after any crash; logs rotate at 10MB or 24h in `financial-dashboard/logs/backend_stdout.log` + `backend_stderr.log`. Control via **services.msc** ("Financial Dashboard Backend" → Start/Stop/Restart) or PowerShell (`Start-Service` / `Stop-Service` / `Restart-Service FinancialDashboardBackend`) or `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit} FinancialDashboardBackend`. **No more env-var-missing silent-degrade risk**: `AppEnvironmentExtra` persists `AI_ENABLE_THINKING=true` + `PYTHONUTF8=1` forever. **⚠️ Windows venv caveat**: `Get-Process <pid> | Select Path` is UNRELIABLE — venv's `python.exe` stub forwards to the base interpreter image, so Path always shows the base. Always use `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` instead. **⚠️ env propagation caveat**: after any backend restart, verify env via real `usage.thinking=true` SSE call, not just `Win32_Process.CommandLine` match.
- authoritative roadmap: **`AI_GENIUS_PARTNER_PLAN.md` v2.1** (2026-04-18) — 5.5-6 week, 5-phase, $40-95/month, Claude Sonnet 4.6 + Extended Thinking + ChromaDB + Web Search + RAG + Multi-hypothesis + Sub-agent Debate
- legacy (Phase 1-2 evidence only): `HANDOFF_ARCHIVE/AI_ADVISOR_ROADMAP_v1.0_superseded_2026-04-18.md`

## active packet / completion timeline

- `Packet H` — **COMPLETE** (2026-04-17) — Process 0-12 accepted, cashflow documented intentional exception
- `AI Phase 0` — **COMPLETE** (2026-04-17)
- `AI Phase 1 MVP Chat` — **COMPLETE** (2026-04-17)
- `AI Phase 1 Polish` — **COMPLETE** (2026-04-18) — prompt caching + row limit 10 + column pruning
- `AI Streaming SSE` — **COMPLETE** (2026-04-18) — `/api/chat/stream` + progressive UI
- `AI Phase 2 Investigator Sprint 1/2/3` — **COMPLETE** (2026-04-18 01:10–02:00)
- `AI Phase 2 Live + UI Dog-Food` — **VERIFIED** (2026-04-18 02:10 + 02:40)
- `Waybill Arithmetic Bug-Fix` — **COMPLETE** (2026-04-18 04:00) — `compute_waybill_total` + 3-date-field pipeline + 26 regression tests; ground truth pinned (Feb 27 = 7,882.68 ₾, Feb 28 = 2,675.86 ₾)
- `Phase 0A Critical Foundation` — **COMPLETE** (2026-04-18 23:00) — generic `compute` tool (8 ops) + Self-Critique directive + `today_context.py` + 73 new tests (381 total green)
- `Service Worker Cache Bug-Fix` — **COMPLETE** (2026-04-19 00:20) — route-specific SW strategies + `BUILD_ID_TOKEN` cache busting + auto-update flow
- `Backend restart` — **DONE** (2026-04-18 23:40 → 2026-04-19 morning) — fresh `server.py` with Phase 0A + Waybill + Phase 0B Sprint 1 live
- `Phase 0B Sprint 1 (Extended Thinking + Multi-hypothesis)` — **COMPLETE** (2026-04-19)
- `Phase 0B Sprint 2 (Prophet Forecasting)` — **COMPLETE + LIVE VERIFIED** (2026-04-19 18:42)
- `Backend restart #2` — **DONE** (2026-04-19 18:36) — fresh PID 19208 with Sprint 2 `forecast_revenue` tool live
- `Phase 0B Sprint 3 (ChromaDB Semantic Memory + RAG)` — **COMPLETE** (2026-04-19 19:40)
- `Backend restart #3` — **DONE** (2026-04-19 20:54) — PID 18076; later discovered to be stray system Python 3.14 (see 2026-04-19 22:22 restart below)
- `🆕 Full RAG project indexing` — **DONE** (2026-04-19 20:56) — 26 Excel/CSV files → 13,329 chunks in `ai_vectors/` (sampled mode: `--max-rows 2000` per file, `--max-sheets 5`, skip > 80 MB)
- `🆕 Georgian embedding Latin fix` — **DONE** (2026-04-19 21:05) — `_FOLDER_LATIN_HINTS` + keyword-first chunk header + prompt-side Latin alias guidance; verified BOG 2023 recall now returns correct file with cosine dist 0.096 (vs 0.385 pre-fix)
- `🆕 Phase 0B Sprint 3 UI live dog-food` — **VERIFIED** (2026-04-19 21:05) — 4 user-driven chat turns
- 🆕 `path_token ID-collision bug-fix` — **DONE** (2026-04-19 21:25) — SHA256 hash replacement; 26/26 files indexed cleanly (18,263 chunks; was 13,329 with silent collisions)
- 🆕 `Phase 0B Sprint 4 Part 1 — Decision Journal (code)` — **COMPLETE** (2026-04-19 22:05) — `journal.py` CRUD + 3 tools + `<TODAY>` integration + prompt section + 109 tests; pytest 742/742 green
- 🆕 `Backend restart #4 (Sprint 4 live)` — **DONE** (2026-04-19 22:22) — killed stray system-Python PID 18076, started parent-venv PID 10128; TOOL_SCHEMAS=13 LIVE; Win32_Process CommandLine verification method adopted
- 🆕 `ChromaDB 1.5.x string-range bug-fix` — **DONE** (2026-04-19 22:35) — `$lt`/`$gt` on string `journal_due_date` silently returned 0 rows; moved date filters to Python post-fetch (`_apply_python_date_filters`); pytest 743/743 green (+1 new test)
- 🆕 `Phase 0B Sprint 4 Part 1 scratch smoke` — **VERIFIED** (2026-04-19 22:40) — 6/6 steps: add promise (due=today-2d) → list(overdue=True) returns count=1 → `<TODAY>` shows `🚨 ვადა გადაცილებული 2 დღე` → update done → entry disappears from open list
- 🆕 `Phase 0B Sprint 4 Part 1 — Live Anthropic dog-food` — **VERIFIED** (2026-04-19 23:05) — 2 sequential `/api/chat` calls on real Sonnet 4.6 via parent-venv PID 10128; Turn 1 natural promise ("Alpha-ს ვალი 7 დღე გადაცილებულია...") → `journal_add_entry` with Sprint 3 `supplier:alpha`/`topic:cashflow` tag convention auto-applied + due_date today+3; Turn 2 natural query ("რა მაქვს ახლა ღია ჟურნალში?") → `journal_list_entries(status="open")` + Georgian table reply; ~$0.09 total; cache warm on Turn 2 (`cache_read=32056 + cache_create=0`) → latency 27.5s → 7.1s; scratch entry cancelled via `update_journal_entry(status="cancelled")` so live ChromaDB stays clean
- 🆕 `Phase 1 Part A — AI "ხასიათი" + "საზრისობა" Layer 1` — **CODE COMPLETE** (2026-04-20 00:30) — `SYSTEM_PROMPT_KA` gained 8 CRITICAL sections (🎯 role-contract + 🗺️ project-map + ⚖️ source-hierarchy + 🕵 data-skepticism + 🎭 5-hats + 🎯 confidence-labels + 📌 assumption-vs-fact + strict-tone); persona `ფინანსური მრჩეველი → სტრატეგიული ფინანსური პარტნიორი`; `MAX_TOOL_ITERATIONS_DEEP` 10 → 12; `today_context.py` extended with `_WEEKDAY_CONTEXT` + `_FIXED_MONTHLY_DEADLINES` (VAT + საპენსიო day 15) + `⏰ უახლოესი ვადები` 10-day severity block; 66 new tests in `test_ai_prompts_phase1.py`; pytest 818/818 green (was 752); investigator prompt untouched
- 🆕 `Backend restart #6` — **DONE** (2026-04-20 00:47) — new parent-venv PID 11620 on 127.0.0.1:8000 with `AI_ENABLE_THINKING=true`; verified via `Win32_Process.CommandLine` + in-process markers probe (all 19 Phase-1-Part-A strings present in `SYSTEM_PROMPT_KA`, all 3 investigator-prompt persona markers still absent, `MAX_TOOL_ITERATIONS_DEEP=12`, `TOOL_SCHEMAS=13`)
- 🆕 `DEFAULT_TIMEOUT_S 60→120 production fix` — **DONE** (2026-04-20 00:47) — Phase 1 Part A's heavier prompt + Extended Thinking + Prophet cold-start pushed single Anthropic messages past 60 s ceiling → SDK retry loop → server lock; minimal 1-line change in `dashboard_pipeline/ai/agent.py:47` (no tests pin the 60 s value; behavior unchanged for fast chats)
- 🆕 `Phase 1 Part A — Live Anthropic dog-food` — **VERIFIED** (2026-04-20 00:55) — 1 scripted `/api/chat` call (`think=True`) with 2-store comparison question; AI returned full 5-hat strategic block (💼/🔧/🎯/⚠️/🪞), 3-version multi-hypothesis (55%/30%/15%), `🟢 საიმედო` confidence, inline `წყარო:` attribution, strict tone ("სუსტი ლოგიკაა"), **auto-invoked** `save_memory` (`chat_705a38ef`) + `journal_add_entry` (`journal_886cce34`, kind=recommendation, title "ოზურგეთის ხარჯების ობიექტური audit"); 26 tool calls under 12-iteration cap; elapsed 151.6s; 136,296 in + 7,235 out + **175,018 cache_read**; cost ≈ $0.12; `stop_reason=end_turn`; no retries
- 🆕 `Phase 1 Part B — AI ქართული რეგულაცია + ფრენჩაიზი კონტექსტი` — **CODE COMPLETE** (2026-04-20 01:00) — `SYSTEM_PROMPT_KA` gained new `🇬🇪 ქართული რეგულაცია` section between 🗺️ პროექტის რუკა and ⚖️ წყაროების იერარქია (💰 tax table + 🧾 RS.ge + 🏪 Franchise + 📋 Baseline facts + 🌅 Monthly rhythm); 42 new cases in `test_ai_prompts_phase1b.py` (8 classes); pytest 860/860 green (was 818); investigator prompt untouched (4 do-not-touch tests)
- 🆕 `Backend restart #7` — **DONE** (2026-04-20 01:24) — parent-venv PID 36460 via `& '...\venv\Scripts\python.exe' -u server.py` with `$env:AI_ENABLE_THINKING='true'`; verified via `Get-CimInstance Win32_Process` CommandLine + in-process 15 Phase-1-Part-B markers present in chat prompt + absent from investigator prompt
- 🆕 `Phase 1 Part B — Live Anthropic dog-food` — **VERIFIED** (2026-04-20 01:28) — 1 scripted in-process `AIAgent.chat(think=True)` call with ოზურგეთი POS 20K ₾ capex timing question (2026-04-20 weekday=ორშაბათი); AI emitted: 4/5 hats (💼/⚠️/🎯/�, 🔧 skip), 3-version multi-hypothesis (40%/35%/25%), `🟢 საიმედო` + multiple `🟡 ვარაუდი`, VAT + საპენსიო 15 მაისი deadline mention, inline `წყარო:`, **Monthly rhythm rule LIVE-applied** ("2026-05-16 — 2026-06-01 მე-2 ტერმინალი **15-ის deadline-ის შემდეგ**"), **Baseline facts mechanism LIVE-invoked** (`recall_context(query="VAT სტატუსი შემოსავლის გადასახადი მცირე ბიზნესი cash planning")`), auto `journal_add_entry` (`journal_15c67afa...` recommendation "ოზურგეთის ხარჯების ატრიბუციის გამოძიება"; post-run cancelled for clean data); 10 tool calls under 12-iteration cap; elapsed 111.72s; 30,197 in + 4,507 out + **108,127 cache_read**; cost ≈ $0.19; `stop_reason=end_turn`
- 🆕 `Phase 1 Part C — Multi-Store DNA` — **CODE COMPLETE** (2026-04-20 02:00) — `SYSTEM_PROMPT_KA` gained new `🏪 მაღაზიების DNA` section between 🌅 ქართული თვის რიტმი and ⚖️ წყაროების იერარქია (🏪 ოზურგეთი Urban Flagship DNA card + 🏡 დვაბზუ Rural Local DNA card + 🌅 სეზონური რიტმი + 🎯 DNA გამოყენების guidance + 📋 store-level Baseline facts + ⚠️ over-apply guardrails); 54 new cases in `test_ai_prompts_phase1c.py` (10 classes); pytest 914/914 green (was 860); investigator prompt untouched (6 do-not-touch tests + 15 Part C markers absent)
- 🆕 `Backend restart #8` — **DONE** (2026-04-20 02:11) — parent-venv PID 31176 via `& '...\venv\Scripts\python.exe' -u server.py` with `$env:AI_ENABLE_THINKING='true'`; verified via `Get-CimInstance Win32_Process` CommandLine + in-process 15 Phase-1-Part-C markers present in chat prompt + absent from investigator prompt
- 🆕 `Backend restart #9` — **DONE** (2026-04-20 02:50) — parent-venv PID **7776** via `Start-Process` with `$env:AI_ENABLE_THINKING='true'`; verified via `Get-CimInstance Win32_Process` CommandLine + in-process 15 Phase-1-Part-D markers present in chat prompt + absent from investigator prompt
- 🆕 `Phase 1 Part C — Live Anthropic dog-food` — **VERIFIED** (2026-04-20 02:11) — 1 scripted in-process `AIAgent.chat(think=True, mode="chat")` call with თამბაქოს 10-15% ფასდაკლება cross-store question → AI reply verified with 5/5 DNA markers: ოზურგეთი YES + დვაბზუ NO differentiation + elasticity reasoning (tourist + loyal + habit-driven) + 🟢 საიმედო + 🟡 ვარაუდი confidence + DNA-based hypothesis (peak / mix / POS / რეჟიმი); 15 sources + 6+ tool calls (`read_data_json` ×4 + `recall_context` excel + `read_excel_source`) under 12-iteration cap; ~2 წთ elapsed, 178,889 in + 5,607 out + **166,817 cache_read** (warm from Part A/B sessions); cost ≈ $0.14; `stop_reason=end_turn`. ⚠️ First attempt without env flag hit `MAX_TOOL_ITERATIONS=6` — launched with `$env:AI_ENABLE_THINKING="true"` on second attempt → deep cap 12 activated
- 🆕 `Phase 2.11 — Dead Stock Liquidation` — **COMPLETE** (earlier session) — `analyze_dead_stock(days_threshold, store, top_n)` tool + bucket classification (active / 91-180d / 181-365d / 365d+) + recommended action (discount_15 / discount_30 / supplier_return / write_off) + frozen_cash_estimate + 30 % unmatched warning threshold; TOOL_SCHEMAS 13→14; `SYSTEM_PROMPT_KA` 💀 Dead Stock section added
- 🆕 `Phase 2.12 — Supplier Negotiation Prep` — **CODE COMPLETE** (2026-04-20 14:40) — new module `dashboard_pipeline/ai/supplier_brief.py` (~1280 lines): `prepare_supplier_brief(data_loader, supplier_name|tax_id, lookback_months, top_n, benchmark_n)` triangulates `suppliers` × `imported_products.suppliers` × `imported_products.products` × `supplier_aging` into 1-page negotiation deck. Match precedence: `tax_id_exact` (high) → `name_exact` (high) → `name_substring` (medium) → `name_partial` (low). Date-range fallback chain: imported.date_range → supplier_aging first/last → zero. Leverage score 0-100 with 5 weighted components (portfolio_share 30 + payment_leverage 20 + dual_sourcing 20 + tenure 15 + relationship_health 15) + 🟢 HIGH ≥70 / 🟡 MEDIUM ≥40 / 🟠 LOW. 3 ranked plays: `cash_discount_for_payment_speed` (🟢 high, fires when unpaid ≥10%) / `volume_commitment_discount` (🟡 medium, share ≥3% + monthly_avg ≥20K) / `dual_source_leverage` (🟠 use_only_if_stalled, requires dual-source + more-expensive + comparable-row). Portfolio mode: Pareto top-5/10/20 shares + HHI concentration + top_candidates ranked by `leverage_score × savings × spend`. `TOOL_SCHEMAS=15` (was 14); dispatcher routes new tool via LAZY import. `SYSTEM_PROMPT_KA` gains 📞 section between 💀 Dead Stock and 🔄 Self-Correction with trigger / anti-trigger / identity-confidence protocol / relationship discipline / portfolio example. 130 new tests (76 `test_ai_supplier_brief.py` + 54 `test_ai_prompts_phase2_12.py`); 6 existing tool-count pins bumped 14→15 (`test_ai_memory.py`, `test_ai_journal.py`, `test_ai_forecasting.py`, `test_ai_investigator.py`, `test_ai_agent.py`, new 2.12 module). One bug en-route: `_normalize_name` regex ordering — `lstrip()` added before `^შპს|^სს|^ი.მ` anchor so parenthetical cleanup doesn't orphan the legal-prefix rule. Smoke-scripted against real `data.json`: 5 scenarios pass (focused via tax_id → rank #1 / share 17.25 % / leverage 71 🟢 HIGH / 3 plays / warning count 0; focused via fuzzy name → high-confidence exact match; Coca-Cola Guria → 34 dual-source rows, 27K ₾ savings; portfolio mode → 270 suppliers, HHI 551 moderate, top-5 41.9 %; unknown supplier → Georgian error). pytest **1163/1163 green** (was 1033 → 1109 after 2.12 module/prompt wiring → 1163 after prompt-guard). Zero backend regressions. **Backend restart + live Anthropic dog-food PENDING** (previous PID 7776 was already stopped at Excel Path Fix time — next `server.py -u` launch picks up both Phase 2.11 + 2.12 tool surface automatically; no schema/contract break)
- 🆕 `Excel Georgian Path Fix` — **CODE COMPLETE + LIVE VERIFIED** (2026-04-20 12:45) — `dashboard_pipeline/ai/tools.py::_resolve_safe_path` fix: replaced `Path.resolve(strict=False)` (which followed Windows OneDrive junctions across non-ASCII ancestor `AI აგენტი` and silently relocated the candidate outside `project_root` for 5 of 6 Georgian Excel folders) with `Path.absolute()` (lexical join + drive normalisation, no symlink follow) + explicit `..` segment reject (traversal protection preserved). 7 new regression tests in `TestResolveSafePathRegression` class (`test_ai_investigator.py`): rejects `..` at start / mid / inside subdir / backslash-dotdot, normal paths still resolve, Georgian subfolder under non-ASCII ancestor works, backslash form under non-ASCII ancestor works. pytest **976/976 green** (was 969; +7; 0 weakened). Live in-process `AIAgent.chat(think=True)` dog-food on the SAME BOG 2026-02 question that hit the bug at Part D's 02:50 dog-food → AI now opens `Financial_Analysis/ბოგ ბანკი ამონაწერი/02--2026.xlsx` directly via `read_excel_source` and reads real data (PMD transactions, "აიდიეს ბორჯომი თბილისი" supplier); explicit acknowledgement of the SEPARATE 200-row sample cap limitation (1618-chunk file > 200-row cap → recommended Excel-side filter). Path bug **completely gone**. Investigator prompt + chat prompt + journal + memory layers untouched. Backend PID 7776 found stopped at probe time (port 8000 free) — code change in `tools.py` only (no schema/contract change), next launch picks up the fix automatically.
- 🆕 `Backend restart #10` — **DONE** (2026-04-20 15:25) — old PID 27700 (parent-venv but started without `AI_ENABLE_THINKING`) stopped; fresh PID **29332** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'`; verified via `Get-CimInstance Win32_Process` CommandLine + live `/api/status` 200 + in-process 15-marker 📞 Phase 2.12 probe (chat 15/15 / investigator 0/15) + `TOOL_SCHEMAS=15` confirmed. Intermediate PID 27700 caveat: focused dog-food had `usage.thinking=false` despite request `think=True` — the proximate env-var was missing in the launching shell even though CommandLine matched parent-venv; restart #10 fixed this. **Do-not-touch rule**: always confirm env propagation via `usage.thinking=true` in first live call after a restart, not just CommandLine match.
- 🆕 `Phase 2.12 — Focused Live Anthropic dog-food` — **VERIFIED** (2026-04-20 15:15) — 1 scripted `/api/chat/stream` call with `think=True`, question `"ხვალ შპს ჯიდიაი-სთან მაქვს შეხვედრა, რა ვთხოვო?"` → AI called `prepare_supplier_brief(supplier_name="ჯიდიაი")` + `recall_context` bonus; returned 2661-char Georgian brief with tax_id `406181616` auto-resolved, `match_confidence 🟢 HIGH (exact name match)`, Ranking #1, `Leverage: 🟢 HIGH (71/100)`, 5-row factor table (897,043 ₾ / 17.25% / 313,922 ₾ debt / 51d inactivity / 44mo tenure), 3 ranked plays with ask/give columns + probability, critical signal callout (`313K ₾ debt = strongest bargaining chip`), `stop_reason=end_turn`, inline `წყარო:` attribution; 49.8s elapsed, 8186 in + 1891 out + 31189 cache_create + 31189 cache_read (this call ran on PID 27700 **before** restart #10; `usage.thinking=false` due to pre-restart env gap, but 9/9 PASS on feature-layer criteria — the brief rendered in full; thinking-activated evidence captured on subsequent portfolio + dead-stock calls instead). Cost ≈ $0.10.
- 🆕 `Phase 2.12 — Portfolio Live Anthropic dog-food` — **VERIFIED** (2026-04-20 15:27) — 1 scripted `/api/chat/stream` call with `think=True`, question `"ვის უნდა ვესაუბრო პირველად ფასდაკლებისთვის?"` → AI called `prepare_supplier_brief()` (no identifier = portfolio mode) → returned 2248-char Georgian ranking deck: `270 მომწოდებელი / 5,201,362 ₾ / Top-5 41.9% / HHI 551 (moderate)`; Top-3 candidates table (`#1 ჯიდიაი 17.25% 🟢 HIGH 71 ~39,800 ₾ savings / #2 კოკა-კოლა გურია 7.72% 🟡 MEDIUM 57 ~27,091 ₾ / #3 პარტნიორი 1.41% 🟡 MEDIUM 55 ~903 ₾`); full Top-10 table with leverage labels; `🎯 სტრატეგია` section with `1. ჯიდიაი — დაიწყე აქ, ეს ყველაზე მომგებიანია` steering + `#1 priority`; `stop_reason=end_turn`; **10/10 PASS** including `usage.thinking=true` ✅; 49.1s elapsed, 3104 in + 1569 out + 62400 cache_create + 0 cache_read (fresh post-restart cache). Cost ≈ $0.27.
- 🆕 `Phase 2.11 — Dead Stock Live Anthropic dog-food` — **VERIFIED** (2026-04-20 15:30) — 1 scripted `/api/chat/stream` call with `think=True`, question about 6+ month unsold products → AI called `analyze_dead_stock(days_threshold=180, top_n=30, store="total")` + 3 `compute` aggregations; returned 3964-char Georgian strategic brief opening with mandatory 30.3% unmatched warning (`4,049 / 13,344 imported SKU ვერ დავამთხვიე retail_sales-ს — barcode/code drift`), 3-bucket breakdown table (181–365d 2,003 SKU ~452,634 ₾ / 365d+ 2,799 SKU ~1,040,336 ₾ / Unmatched 4,049 SKU ?); 3-action Salvage Plan table (`−30% ფასდაკლება` 452K ₾ 🟡 / `მომწოდებელს დაბრუნება` 1,040K ₾ 🟢 / `write-off + manual audit` 🟠); Top-10 specific products with product name + supplier + frozen ₾ + last-sale-date + recommended action (e.g. `პარლამენტი აქვა ბლუ → ჯიდიაი, 87,850 ₾, last sold 2025-03-29 (387d), 🟢 დაუბრუნე ჯიდიაი-ს`); total frozen-cash estimate `~1,492,970 ₾ (🟡 ზედა შეფასება)`; `stop_reason=end_turn`; **9/9 PASS** including `usage.thinking=true` ✅; 65.9s elapsed, 13684 in + 3198 out + 93589 cache_read (warm from portfolio). Cost ≈ $0.11. **Cross-link evidence**: Dead Stock + Negotiation Prep composition works — AI paired specific SKU (`პარლამენტი აქვა ბლუ`) with specific supplier (`ჯიდიაი`) and recommended `supplier return` — the same supplier Phase 2.12 focused flagged as #1 leverage target.
- 🆕 `Phase 3.1 — Co-Designer Mode` — **COMPLETE + LIVE VERIFIED** (2026-04-20 17:50) — PULL-ONLY feature-proposal capability. `JOURNAL_KINDS` gained `proposal` (5→6) + 6 metadata keys (`proposal_problem` / `_benefit` / `_mvp` / `_data_needed` / `_time_estimate` / `_risk_critique`) + `cleanup_stale_proposals(days=30)` auto-janitor. `tools.py::TOOL_SCHEMAS` 15→16 — new `propose_feature(title, problem, benefit, mvp_scope, data_needed, time_estimate, risk_critique)` tool at index 15 (last). `SYSTEM_PROMPT_KA` gained 🎨 Co-Designer section between Phase 2.12 📞 and 🔄 Self-Correction: PULL-ONLY policy + 6 explicit trigger phrases (`"რას შემომთავაზებდი"`, `"რა ახალი feature"`, `"რა იდეები გაქვს"`, `"შემომთავაზე რამე"`, `"co-designer"`, `"AI, იყავი შენ co-designer"`) + anti-trigger list (never propose on strategic/data/debug questions) + mandatory 6-field format + 🪞 critic mandate (AI must self-critique `risk_critique`) + ID citation (journal_xxx) + 3-proposal cap per query. Investigator prompt UNTOUCHED (0/6 markers, do-not-touch). Tests: 78 new in `test_ai_co_designer.py` (proposal kind / metadata / add/list/update / cleanup / tool schema / dispatch / prompt wiring / anti-trigger / investigator untouched) + 6 existing tool-count pins bumped 15→16 (`test_ai_journal.py`, `test_ai_tools.py`, `test_ai_memory.py`, `test_ai_forecasting.py`, `test_ai_investigator.py`, `test_ai_supplier_brief.py`) + 2 regression fixes (`test_ai_agent.py::test_investigate_mode_preserves_tool_surface` set bumped to include `propose_feature`; `test_ai_journal.py::test_every_kind_registers` teaches iteration to pass 6 proposal fields for `kind=='proposal'`). pytest **1242/1242 green** (was 1163; +79 net: 78 new + 1 renamed; 0 weakened). Live `/api/chat/stream` dog-food **3/3 PASS, 0 failures** on PID 29400: (A) trigger 146.1s → 3 structured proposals with all 6 fields + critic self-review + AI first checked via `journal_list_entries` + `recall_context`; (B) strategic anti-trigger 75.4s → 0 `propose_feature`, analyzed via `compute` + 5× `read_data_json`; (C) data anti-trigger 9.5s → 0 `propose_feature`, single `read_data_json`. All scenarios `stop_reason=end_turn` + `usage.thinking=true` ✅. 3 proposals post-verified: "ხარჯების გაუნაწილებელი vs მაღაზიის Split — Live Dashboard Widget" / "Dead Stock — Salvage Tracker" / "Cash Runway Widget — რამდენი დღე ვძლებ?" — cancelled via `update_journal_entry(status='cancelled')` to keep journal clean. **Carry-forward do-not-touch**: `JOURNAL_KINDS` order fixed; `TOOL_SCHEMAS[15]=propose_feature` pinned; `PROPOSAL_AUTO_CLEANUP_DAYS=30`; PULL-ONLY policy + 6 trigger phrases + anti-trigger list + 🪞 critic mandate + ID citation must stay in prompt; investigator prompt must stay 0/6 markers.
- 🆕 `Backend restart #11` — **DONE** (2026-04-20 17:35) — old PID 29332 stopped; fresh parent-venv PID **29400** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'`; verified via `Get-CimInstance Win32_Process -Filter "ProcessId=29400"` CommandLine = `"...\venv\Scripts\python.exe" -u server.py` + `/api/status` 200 OK + in-process 6-marker Phase 3.1 probe (chat 6/6 / investigator 0/6) + `TOOL_SCHEMAS=16` / `TOOL_SCHEMAS[-1]=propose_feature` / `AIConfig.enable_thinking=True` / `AI_ENABLE_THINKING` env confirmed. Live `usage.thinking=true` verified on all 3 subsequent dog-food calls.
- 🆕 `Phase 4A — Debt Repayment Plan Part A (backend tool + prompt + endpoints)` — **COMPLETE + LIVE VERIFIED** (2026-04-21 00:50) — new `dashboard_pipeline/ai/debt_plan.py::build_debt_repayment_plan(data_loader, *, priority_suppliers, plan_duration_months, max_priority_count)` (~620 lines) computing 4-factor criticality score (debt 30% + aging 25% + frequency 25% + dysfunction 20%) + 3-month moving-average inflow forecast with ±10% bracket + per-supplier `recommended_monthly_payment_ge` / `_weekly_payment_ge` / `days_to_clear_est` / `confidence_label` (🟢🟡🔴) / `rationale_ka` + `non_priority_summary` (historical × 90% baseline) + `allocation_summary` with `sustainable: bool` + `risks[]` + `summary_ka` + `notes[]`. `tools.py::TOOL_SCHEMAS` 17→18 with `BUILD_DEBT_PLAN_TOOL` at index 12 (before `propose_feature` which shifted 16→17). `SYSTEM_PROMPT_KA` gained 📋 ვალების გეგმა section (AUTONOMOUS STRATEGIST label, broad triggers, IMMEDIATELY-call workflow, 5-part response format, critic mandate, anti-triggers → `prepare_supplier_brief`/`compute_cash_runway`). `JOURNAL_KINDS` 5→6 (`repayment_plan` added in `journal.py`). `server.py` gained POST `/api/debt-plan` + POST `/api/debt-plan/save` endpoints with `_coerce_optional_int` + `_coerce_priority_list` helpers. pytest **1393/1393 green** (was 1303; +90 new `test_ai_debt_plan.py`; 7 existing tool-count pins bumped 17→18). Live `/api/chat/stream` dog-food **12/12 PASS** across 3 scenarios (BROAD trigger / focused priority list / anti-trigger `compute_cash_runway` route).
- 🆕 `Phase 4A — Part B (React page + journal mirror sync + endpoint tests)` — **CODE COMPLETE** (2026-04-21 01:55) — **ამ სესიის დელიბერებლი**: (1) `server.py` — `from typing import Any` import ფიქსი (ახალი helper signatures საჭიროებდა); endpoints `/api/debt-plan` + `/api/debt-plan/save` POST რეგისტრაცია დადასტურდა `import server` + route introspection-ით. (2) `dashboard_pipeline/ai/tools.py::JOURNAL_KINDS` mirror-tuple 5→6 (`repayment_plan` დამატებული — ადრე მხოლოდ `journal.py`-ში იყო, schema enums `JOURNAL_ADD_ENTRY_TOOL` + `JOURNAL_LIST_ENTRIES_TOOL` ამ tuple-ს იყენებენ). (3) `tests/test_api_debt_plan.py` **NEW 39 cases**: `TestCoerceOptionalInt` 8 (None/empty/int/numeric-string/whitespace/bool-reject/non-numeric-reject/weird-type) + `TestCoercePriorityList` 8 (None/empty/whitespace/happy/mixed-strip/non-list-reject/non-string-elem-reject/too-many-reject) + `TestPostDebtPlan` 10 via FastAPI `TestClient` + monkeypatched `build_debt_repayment_plan` (happy empty body / all args / data_loader wired to `load_full_data` / numeric-string coerced / 4× invalid body shapes / upstream exception → 500) + `TestPostDebtPlanSave` 9 via monkeypatched `add_journal_entry` (happy / title-trimmed / tags-optional / 3× missing-bad-title / non-list-tags / journal-error → 400 / journal-raise → 500) + `TestDebtPlanRoutesRegistered` 2 + `TestJournalKindRegistration` 2. (4) `tests/test_ai_journal.py::TestJournalConstants::test_kinds_tuple` 5-tuple → 6-tuple (added `repayment_plan`). (5) `rs-dashboard/src/tabConfig.js` — `debt_plan` tab დამატებული `ანალიტიკური` ჯგუფში `dead_stock`-ის შემდეგ label `📋 ვალების გეგმა`. (6) `rs-dashboard/src/DebtPlan.jsx` **NEW ~600 lines** — auto-generate on mount via POST `/api/debt-plan`; 3-card strip (Forecast burn-trend color / Allocation sustainable boolean / NonPriority baseline); PriorityTable with expandable rows; RisksBox; duration/priority dropdowns (1/2/3/4/6 × Top-3/4/5/6/8); Approve → `/api/debt-plan/save` with structured tags. (7) `rs-dashboard/src/App.jsx` 3 edits: lazy import `DebtPlan`, excluded `debt_plan` from generic fetch useEffect, added `activeTab === 'debt_plan'` route block. pytest **1433/1433 green** (was 1393; +40 new/adjusted; 0 weakened). `npx eslint src/DebtPlan.jsx src/App.jsx src/tabConfig.js` → 0 warnings. `npm run build` → clean, `DebtPlan-BEEdSF67.js 16.26 kB / 4.43 kB gzip`. **Backend restart #14** PID **21408** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'` → `/api/status` 200 OK. **User cancelled the live POST smoke step** — next chat must run: (a) `Invoke-WebRequest /api/debt-plan` real `data.json` smoke; (b) rs-dashboard `npm run dev 5173` + Playwright click-through on `#debt_plan` (auto-gen → priority table → expand row → regenerate → approve → journal entry_id); (c) optional `/api/chat/stream` dog-food ("შემიდგინე ვალების გეგმა" trigger); (d) docs `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B + `PLAN.md` v2.1 update.
- 🆕 `Phase 4A — Part B LIVE VERIFIED + 2 BUG-FIX` — **COMPLETE** (2026-04-21 02:35) — UI `#debt_plan` tab ცოცხლად მუშაობს. Two root-cause bugs fixed this session: **(1) Schema bug** in `debt_plan.py::_active_debt_suppliers` — expected `supplier_aging` as `{"suppliers": [...]}` dict, but production `data.json` is a **list** directly (193 rows). First POST smoke returned `{"error": "ვალი არ აქვთ"}` 285B. Fix: list+dict tolerance + 4 new regression tests (`TestSupplierAgingListSchema`). **(2) Ranking bug** — Top-5 priority showed 1,434-day-old zombie suppliers (Bau-Tech 435 ₾ #1) while the real 313K ₾ active debtor (ჯიდიაი) sat at #30 because the formula's dominant weight was "ასაკი". Fix: (a) `ACTIVE_CUTOFF_DAYS=365` auto-quarantines dormant suppliers from the priority pool (user-named priorities exempt); (b) weight rebalance: debt **0.30→0.50**, aging 0.25→0.15, freq 0.25→0.20, dysfunc 0.20→0.15 — **ჯიდიაი #1 score 0.585** (was #30 score 0.412). 6 new regression tests (`TestDormantSupplierQuarantine`). pytest **1443/1443 green** (was 1433; +10 new: 4 schema + 6 ranking; 0 weakened). Live POST smoke realistic: 2-თვე unsustainable (246K/თვე > 140K inflow); 6-თვე უკეთესი (priority 85,700 ₾ = 61% forecast) but baseline still exceeds — business cash deficit ~35K ₾/თვე cleanly surfaced. Playwright main-app click-through on `#debt_plan` → 3 cards + risks + 5 priority rows render correctly; row expansion click → "💡 რატომ კრიტიკული" + analysis visible. **⚠️ Pending**: approve/save + regenerate button clicks UI-test (backend crashed mid-session); `/api/debt-plan/save` journal smoke; optional `/api/chat/stream` dog-food ("შემიდგინე ვალების გეგმა" → AI calls `build_debt_repayment_plan`).
- 🆕 `Backend restart #14` — **DONE** (2026-04-21 01:55) — post Part-B-code PID **21408** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'`; `/api/status` 200 OK.
- 🆕 `Backend restart #16` — **DONE** (2026-04-21 02:30-ის შემდგომ) — after mid-session crash (cause unknown), fresh parent-venv PID **18960** via standard pattern; restored live service for Part B UI click-through completion; `/api/status` 200 OK.
- 🏁 `Phase 4A — FULLY CLOSED (Part A + Part B LIVE VERIFIED end-to-end)` — **COMPLETE** (2026-04-21 04:02) — all mid-session pending items finished this session: (1) scripted `/api/chat/stream` dog-food `"შემიდგინე ვალების გეგმა"` with `think=True` → AI autonomously called `build_debt_repayment_plan` at 49.7s with empty `priority_suppliers` (auto-detection), `usage.thinking=true` ✅, `stop_reason=end_turn` ✅, 91.2s elapsed, 3,946 in + 2,887 out + 81,046 cache_create; Georgian 5-section reply (ჯიდიაი #1 313,922 ₾, 2-თვიანი arithmetically unsustainable 246K/თვე > 140K forecast, 4-6 თვე horizon recommendation, relationship-risk flags for 314/264/161-day missed-delivery suppliers); (2) UI regenerate click-through (Vite dev 5173 + Playwright MCP): initial `#debt_plan` mount → 🐞 **3rd bug-fix surfaced** (see below) → post-fix reload → 3-card strip + 6-risk list + 5-row priority table rendered in <3s → 2→6 თვე duration change + `🔄 ახალი გეგმა` click → re-render with 246,000→85,700 ₾/თვე priority total, buffer −139.2%→−25.0%; (3) UI approve click-through: `✅ ვეთანხმები — შენახვა` click → `POST /api/debt-plan/save` 200 OK → button morphed to `✅ შენახულია ჟურნალში` [disabled] → journal entry `journal_816295fd222b495199c30599510d8d7f` title *"ვალების გეგმა — 5 priority @ GEL 85,700/თვე (6-თვიანი)"* status `🟡 open` persisted; cross-verified via `/api/chat` "ვნახე ბოლო repayment_plan journal entry" query → AI invoked `journal_list_entries` → returned exact same entry ID/title/status. `PHASE_4A_DEBT_PLAN_PREVIEW.md` updated with Part B LIVE VERIFIED section + 🎉 closure banner. Scratch cleanup: `_scratch_dogfood_phase4a.py` + log deleted.
- 🐞 `App.jsx showGlobalLoading bug-fix (3rd Phase 4A bug)` — **DONE** (2026-04-21 03:58) — `rs-dashboard/src/App.jsx:307` — `showGlobalLoading` exclusion list contained `imported_products` / `waybills` / `insights` but not `debt_plan`; the `loading` state defaults to `true` and is only flipped to `false` by the main `/api/data` useEffect which early-returns for `debt_plan` (page manages its own POST lifecycle). Without `debt_plan` in the render-gate exclusion, UI was stuck on `"იტვირთება მონაცემები..."` forever, blocking all UI click-through verification. **Fix**: 1-line change adding `&& activeTab !== 'debt_plan'` — same pattern as the three existing exclusions. This bug is the most likely cause of last session's "UI approve/save + regenerate button crash interrupted" note; both actions now work cleanly.
- 🆕 `Backend restart #17` — **DONE** (2026-04-21 03:43) — after previous PID 18960 crashed between sessions (port 8000 free + `/api/status` connection refused); fresh parent-venv PID **5388** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py' -WindowStyle Hidden`; verified via `Win32_Process.CommandLine` = `"...\venv\Scripts\python.exe" -u server.py` ✅ + `/api/status` 200 OK ✅ + in-process `TOOL_SCHEMAS=18` probe (idx 12=build_debt_repayment_plan, idx 17=propose_feature) ✅ + subsequent scripted `/api/chat/stream` call returned `usage.thinking=true` ✅ (env propagation confirmed — not just CommandLine match).
- 🏁 `Windows Service installation — backend perma-up` — **DONE** (2026-04-21 04:15) — ends the recurring manual-restart pain permanently. NSSM 2.24 downloaded from `nssm.cc` to `C:\tools\nssm\nssm.exe`. Existing PID 5388 stopped (port 8000 freed). Service registered with name `FinancialDashboardBackend` / display `Financial Dashboard Backend` via elevated `_scratch_install_service.ps1` (one-time UAC prompt). Configuration: `AppPath=venv\Scripts\python.exe`, `AppParameters=-u server.py`, `AppDirectory=financial-dashboard`, `AppEnvironmentExtra=AI_ENABLE_THINKING=true PYTHONUTF8=1`, `Start=SERVICE_AUTO_START`, `AppExit=Default Restart`, `AppRestartDelay=2000`, `AppThrottle=1500`, `AppStdout=logs\backend_stdout.log` + `AppStderr=logs\backend_stderr.log` with rotation (10 MB OR 24 h). Stop method: graceful (Ctrl+C → window close → thread terminate → kill, each 1.5 s). Post-install verification: `Get-Service FinancialDashboardBackend` → `Running, Automatic` ✅; port 8000 LISTENING on PID **24364** ✅; `/api/status` 200 OK ✅; TOOL_SCHEMAS=18 ✅; `/api/chat` scripted call with `think=True` returned `usage.thinking=True` ✅ (env propagation through NSSM validated). Install script `_scratch_install_service.ps1` deleted post-run. **Control surface for user**: services.msc → "Financial Dashboard Backend" → Start/Stop/Restart buttons; or PowerShell `Restart-Service FinancialDashboardBackend`; or `C:\tools\nssm\nssm.exe {start|stop|restart|status|edit} FinancialDashboardBackend` for advanced reconfig. **Backend restart #N counter retired** — future backend changes triggered via `Restart-Service` (no PID tracking needed).
- 🆕 `Real-user dog-food (Phase 2.11 + 2.12 + Phase 1 stack)` — **VERIFIED** (2026-04-20 15:54) — 1 `/api/chat/stream` call with `think=True` on **genuine user-phrased Georgian strategic question** (not scripted): `"რას შეცვლიდი გაყიდვებიდა და როგორ გააუჯობესებდი გაყიდვების პრობლემას და შედეგიანობა"`. AI **reframed the question** ("პრობლემა გაყიდვებში არ არის — შემოსავალი +18.2% YoY, მაგრამ ხარჯი უფრო სწრაფად იზრდება → წლიური ზარალი −193,538 ₾"), opened with factual KPI table (revenue 1,270,212 ₾ / cost 1,463,749 ₾ / net margin −15.2% / AP Days 163 / 859,953 ₾ supplier debt); applied **Multi-Store DNA** (ოზურგეთი margin −80% flagged as cost-attribution bug, not real loss; recommended separate bank accounts + proportional allocation); delivered **5-priority roadmap** (#1 ოზურგეთი cost audit 2 weeks / #2 Dead Stock 4-SKU return to ჯიდიაი ~329,201 ₾ freed / #3 AP 163 → <60 in 3mo / #4 daily Z-report / #5 seasonal stocking for აგვისტო peak); **cross-linked Phase 2.11 + 2.12** (Dead Stock freed cash → partial AP paydown → stronger negotiation position with ჯიდიაი); used **🪞 კრიტიკოსი hat** (acknowledged weakest assumption: "ოზურგეთი −80% სავარაუდოდ attribution bug, არა ნამდვილი ზარალი"); asked **clarifying question** at end ("ქირა/royalty/ხელფასი ცალ-ცალკე ობიექტზე მიბმული გაქვს?"); inline `წყარო:` attribution throughout; `stop_reason=end_turn`; **all quality markers PASS**: multi-store ✅ / 5-hats ✅ / cross-link 2.11+2.12 ✅ / self-critique ✅ / source attribution ✅ / reframing ✅ / clarifying Q ✅. 88.7s elapsed (21.6s first-token after extended thinking), 7 tool calls (`read_data_json` ×5 `monthly_pnl`+`executive_summary`+`retail_sales`+`monthly_pnl full`+`financial_ratios` + `forecast_revenue(horizon=6, store=total)` + `analyze_dead_stock(days_threshold=90, store=total, top_n=10)`), 39,757 in + 4,047 out + 85,929 cache_create + 38,849 cache_read, `usage.thinking=true` ✅. Cost ≈ $0.20. **This is the first non-scripted, user-phrased dog-food** — end-to-end composition (Phase 1 A/B/C/D persona + Phase 2.11 Dead Stock + Phase 2.12 Supplier Negotiation) works under genuine open-ended strategic questioning.

## 🆕 Phase 0B Sprint 4 Part 1 — Decision Journal — delivered surface

### Backend

- `dashboard_pipeline/ai/journal.py` (**NEW** — ~640 ხაზი):
  - `add_journal_entry(title, kind, *, due_date=None, tags=None, source_memory_id=None)`
  - `list_journal_entries(*, status=None, kind=None, overdue=None, due_before=None, due_after=None, limit=None, today=None)`
  - `update_journal_entry(entry_id, *, status)`
  - `delete_journal_entry(entry_id)` — not exposed as LLM tool (internal CRUD)
  - `collect_today_journal_highlights(*, today=None, newest_open_limit=3)` — `<TODAY>` block helper
  - `JOURNAL_KINDS = ("promise", "ai_commitment", "recommendation", "reminder")`
  - `JOURNAL_STATUSES = ("open", "done", "cancelled")`
  - `MIN_TITLE_CHARS=3` / `MAX_TITLE_CHARS=500` / `DEFAULT_LIST_LIMIT=20` / `MAX_LIST_LIMIT=100`
  - Stable return contracts — `{ok, entry_id, title, kind, status, due_date, created_at, tags}` / `{count, entries, today}` / `{ok, entry_id, status, previous_status, tags}` / `{error, hint}`
  - Metadata keys live under `journal_entry_type="journal"` discriminator so journal entries never collide with plain `save_memory` rows in the same `chat_memory` collection
  - Sort order: overdue bucket (most days overdue first) → upcoming bucket (earliest due first) → rest bucket (newest first)

- `dashboard_pipeline/ai/memory.py` (extended):
  - `MemoryStore.get_entries(source, *, where=None, ids=None, limit=None)` — structured lookup bypassing the embedding model (ChromaDB `collection.get(...)`)
  - `MemoryStore.update_metadata(entry_id, source, *, patch)` — shallow-merge patch; reuses existing doc + tags so embedding stays stable
  - `MemoryStore.delete_entry(entry_id, source)` — id-based deletion with fallback for fake clients that lack `delete(ids=...)`
  - All three fail softly (return `None`/`False`) on ChromaDB errors so the chat path keeps working

- `dashboard_pipeline/ai/tools.py`:
  - 3 new schemas: `JOURNAL_ADD_ENTRY_TOOL` / `JOURNAL_LIST_ENTRIES_TOOL` / `JOURNAL_UPDATE_ENTRY_TOOL` inserted between `SAVE_MEMORY_TOOL` (index 5) and the investigator tools
  - `TOOL_SCHEMAS` length **10 → 13**; last tool still `VALIDATE_VS_SOURCE_TOOL` so `get_cached_tool_schemas` cache marker placement is unchanged
  - Dispatcher routes `journal_add_entry` / `journal_list_entries` / `journal_update_entry` through LAZY imports of `dashboard_pipeline.ai.journal`
  - `_SUMMARY_KEYS` extended with `entry_id`, `kind`, `title`, `due_date`, `previous_status`, `count`, `today`, `existed`

- `dashboard_pipeline/ai/today_context.py`:
  - `build_today_context(..., project_root=None)` and `build_today_block(..., project_root=None)` gain optional `project_root` kwarg
  - New `ctx["open_promises"] = {"overdue": [...], "newest_open": [...]}` field
  - `format_today_block` renders `⏳ ღია დაპირებები (N ვადაგადაცილებული + M ახალი):` with per-entry icon (🤝 promise, 🔍 ai_commitment, 💡 recommendation, ⏰ reminder) + 🚨 tag for overdue + `journal_<id>` handle
  - Runs even if `data_loader` fails — journal surfaces regardless of data.json freshness
  - Lazy-imports `journal` so the module has no hard ChromaDB dependency at import time

- `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` (chat mode ONLY — investigator prompt untouched):
  - 🆕 **"📋 დაპირებების ჟურნალი (CRITICAL — Phase 0B Sprint 4)"** section between the memory section and the Self-Critique directive
  - Per-kind trigger table (promise / ai_commitment / recommendation / reminder)
  - `due_date` conversion rules (`ხვალ` → today+1; `ერთ კვირაში` → today+7; `14 მაისს` → `2026-05-14`; undated by default)
  - Anti-trigger list (greetings, idle chit-chat, data lookups, acknowledgments)
  - `<TODAY>` "ღია დაპირებები" guidance — AI must cite the running commitment when context matches + proactively remind on 7+ day overdue
  - `save_memory` vs `journal_add_entry` disambiguation — both may fire; journal first, save_memory last

### Tests

- `tests/test_ai_journal.py` (**NEW** — **109 cases** across 18 classes):
  - `TestJournalToolSchemas` 8 — 3 new tool entries, positions (6/7/8), investigator tools still last, total = 13, schema shape, enums, required fields, descriptions
  - `TestJournalConstants` 5 — kinds tuple, statuses tuple, DEFAULT_STATUS, limit bounds, title bounds
  - `TestCoerceTitle` 5 — None/non-string/too-short errors, strip, oversized truncation
  - `TestCoerceKind` 4 — None/unknown errors, every enum roundtrips, case-insensitive
  - `TestCoerceStatus` 4 — same pattern as kind
  - `TestCoerceDueDate` 8 — None/empty → `""`, valid ISO, invalid format, impossible date, non-string, datetime coerced, date coerced
  - `TestCoerceListLimit` 5 — default, garbage, below-min clamp, above-max clamp, passthrough
  - `TestCoerceToday` 4 — None → today, date passthrough, ISO string parsed, garbage falls back
  - `TestNormaliseExtraTags` 4 — structural tags first, user tags preserved, user-supplied kind/status stripped, dedup
  - `TestBuildJournalWhere` 3 — base filter always includes `journal_entry_type`, status filter ANDed, overdue enforces both `$lt` and `$gt ""`
  - `TestSortEntries` 3 — overdue before future, most-overdue first, done bucket newest first
  - `TestAddEntry` 6 — happy path, ai_commitment without due_date, bad title/kind/due_date, every kind registers
  - `TestListEntries` 12 — seed helper produces 4 entries (overdue / future / undated / due-today); all statuses returned by default, overdue filter, status filter, kind filter, sort puts overdue first, limit respected + clamped, non-boolean overdue rejected, bad status rejected, empty when nothing added, overdue_days correct per bucket, today echoed
  - `TestUpdateEntry` 8 — transition to done/cancelled, rollback to open, unknown id errors, bad entry_id type, bad status, persistence across list query, save_memory rows rejected (discriminator guard)
  - `TestDeleteEntry` 3 — delete removes, unknown returns existed=False, bad id errors
  - `TestCollectTodayHighlights` 4 — overdue bucket populated, newest_open excludes overdue + done, newest_open limit respected, non-failing when empty
  - `TestTodayContextIntegration` 4 — open_promises present in ctx, format block renders ⏳ header + overdue tag + title, today-due tag, empty journal skips header entirely
  - `TestDispatcherRouting` 4 — add/list/update routed, call trace carries journal keys
  - `TestPromptWiring` 4 — chat prompt has 📋 section + all 3 tool names + all 4 kinds + anti-triggers; investigator prompt completely untouched
  - `TestHitToEntry` 3 — overdue_days computed, undated → None, bad due_date string → None
  - `TestSemanticRecallInterop` 2 — journal entries surface via `recall_context(tags=["journal"])`; filter excludes plain save_memory rows

- Existing test updates (tool-count pin 10 → 13):
  - `tests/test_ai_memory.py::TestMemoryToolSchemas::test_tool_count_is_13`
  - `tests/test_ai_forecasting.py::TestForecastToolSchema::test_tool_count_is_13`
  - `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` (asserts 13 + adds 3 new names to expected set)
  - `tests/test_ai_agent.py::TestChatMode::test_investigate_mode_preserves_tool_surface` (expected name set includes `journal_add_entry` / `journal_list_entries` / `journal_update_entry`)
  - `tests/test_ai_memory.py::_FakeCollection` — gained `get(ids=..., where=..., limit=...)` + `delete(ids=...)` fallback + `$ne`/`$lt`/`$gt`/`$lte`/`$gte`/`$or` operators so the journal CRUD path exercises realistic ChromaDB contracts

- **pytest 742/742 passed** (was 633; +109 new journal cases; 4 existing tests updated for the 10 → 13 tool surface; 0 tests weakened or deleted)

### Live verification — DONE (2026-04-19 22:45)

- **Backend restarted on parent venv** — PID 18076 (stray system Python 3.14) killed; PID **10128** started via `& '...\venv\Scripts\python.exe' -u server.py` with `$env:AI_ENABLE_THINKING='true'`
- **Win32_Process CommandLine** proved venv activation despite `Get-Process Path` showing base Python (Windows venv stub artifact — now a documented caveat)
- **TOOL_SCHEMAS length = 13** confirmed in-process: indices 6/7/8 = `journal_add_entry` / `journal_list_entries` / `journal_update_entry`
- **scratch smoke** (no Anthropic call, pure CRUD + `<TODAY>` integration against live ChromaDB):
  1. `<TODAY>` BEFORE adding anything — no `⏳ ღია დაპირებები` section (empty state suppressed) ✅
  2. `add_journal_entry(title="smoke...Alpha 50%...", kind="promise", due_date=today-2d)` → `{ok:true, entry_id: "journal_973c8a22...", status: "open"}` ✅
  3. `list_journal_entries(status="open", overdue=True, limit=5)` → **count=1** (after bug-fix; was 0 before) ✅
  4. `<TODAY>` AFTER adding → renders `⏳ ღია დაპირებები (1 ვადაგადაცილებული)` + icon 🤝 + `🚨 ვადა გადაცილებული 2 დღე` + `id: journal_973c8a22...` ✅
  5. `update_journal_entry(entry_id, status="done")` → `{ok:true, previous_status: "open"}` ✅
  6. `<TODAY>` AFTER done → entry removed from open list (⏳ section suppressed again) ✅
- **Remaining**: live Anthropic `/api/chat` dog-food (to prove the prompt triggers `journal_add_entry` end-to-end) + Part 2 (Phase 0B-wide metrics) + Part 3 (retrospective/closure) — next recommended steps

### 🐞 Bug-fix: ChromaDB 1.5.x string-range filter (2026-04-19 22:35)

**Symptom**: `list_journal_entries(overdue=True)` on real ChromaDB returned 0 rows, even though a journal entry with `due_date="2026-04-17"` (2 days past) existed in the store. `<TODAY>` block showed the entry as "🆕 today" instead of "🚨 overdue". 109 existing journal tests all passed because the in-process fake ChromaDB correctly implemented `$lt`/`$gt` on strings.

**Root cause**: ChromaDB 1.5.x (real) supports `$lt` / `$gt` / `$lte` / `$gte` only on **numeric** metadata; on strings these operators silently return zero matches. Minimal probe:

| filter | real ChromaDB | fake (tests) |
|---|---|---|
| `{journal_status: {$eq: "open"}}` | 1 row ✅ | 1 row ✅ |
| `{journal_due_date: {$lt: "2026-04-19"}}` | **0 rows** ❌ | 1 row ✅ |
| `{journal_due_date: {$ne: ""}}` | 3 rows ✅ | matches all |
| `{journal_due_date: {$gt: ""}}` | **0 rows** ❌ | 1 row |

**Fix** (minimal, contract-stable):
- `journal.py::_build_journal_where` now emits only `$eq` / `$ne` clauses; date comparisons were removed from the ChromaDB side
- New helper `journal.py::_apply_python_date_filters(entries, *, overdue, due_before, due_after)` applies overdue / due_before / due_after filters in Python after fetch (lexicographic ISO comparison)
- `list_journal_entries` over-fetches up to 500 journal rows (structurally narrowed by `$eq status/kind` clauses) then filters in Python — performant for realistic journals (< 500 open entries)
- `collect_today_journal_highlights` simplified to a single open-status fetch + Python overdue split
- `tests/test_ai_journal.py::TestBuildJournalWhere::test_overdue_enforces_lt_and_nonempty` renamed + rewritten to `test_overdue_enforces_open_status_only` asserting the new contract (NO date clauses leak to ChromaDB); +1 new test `test_overdue_with_explicit_status_skips_auto_open`

**Verification**: **pytest 743/743 green** (was 742; +1 new test; 0 weakened/deleted); scratch smoke 6/6 ✅

**Do-not-touch** (new rule — carry forward):
- `journal.py` must never re-introduce `$lt`/`$gt` clauses on `journal_due_date` until ChromaDB gains string-range support (open upstream issue: https://github.com/chroma-core/chromadb/issues — check before reverting)
- If `_apply_python_date_filters` is ever refactored, preserve the `bool(isinstance(overdue_days, int) and overdue_days > 0)` guard — undated entries must never match `overdue=True`
- `_build_journal_where` returns the dict used by BOTH `list_journal_entries` AND `collect_today_journal_highlights`; the Python post-filter mechanism must be applied at BOTH call sites

### 🐞 Caveat: Windows venv Path-check is unreliable (2026-04-19 22:20)

**Symptom**: `Get-Process <pid> | Select Path` returned the BASE Python (`C:\Users\...\pythoncore-3.14-64\python.exe`) for the new parent-venv process (PID 10128) — identical to what it returned for the stray system-Python process (PID 18076). This created a false "PID 10128 is still stray" alarm.

**Root cause**: On Windows, `venv\Scripts\python.exe` is a stub launcher that `CreateProcess()`-forwards to the base interpreter binary. The OS records the IMAGE path (base), not the stub path, in the process's `Win32_Process.ExecutablePath`. The stub still sets `sys.prefix` / `sys.executable` / `sys.path` to point at the venv, so the process DOES load the venv's `site-packages`. But external tools like `Get-Process Path` can't tell the difference.

**Reliable venv verification on Windows**:

| method | reliable? |
|---|---|
| `Get-Process <pid> \| Select Path` | ❌ always base |
| `Get-CimInstance Win32_Process -Filter "ProcessId=X" \| Select CommandLine` | ✅ shows full launch command incl. venv path |
| `importlib.util.find_spec("chromadb")` from within the process | ✅ definitive |
| `sys.prefix` / `sys.executable` in the running process | ✅ definitive |

**Previous false alarm**: PID 18076 was documented in earlier sessions as "fresh parent-venv process" based solely on the `Get-Process Path` check — but when we probed its actual environment via `importlib.util.find_spec` this session, `chromadb`, `sentence-transformers`, `anthropic`, `prophet`, `apscheduler` all returned MISSING. The server only stayed up because `fastapi` + `slowapi` are installed globally; any `/api/chat` call would have ImportError-crashed on first tool dispatch.

**Do-not-touch** (new rule — carry forward):
- Any future "verify backend is on parent venv" check MUST use `Win32_Process.CommandLine` or in-process `sys.prefix`, NOT `Get-Process Path`
- The older memory/docs text "verify `Get-Process <pid> | Select Path` points to `...\venv\Scripts\python.exe`" is WRONG on Windows and should be ignored if encountered in older handoffs

---

## 🆕 Phase 0B Sprint 2 — Prophet Forecasting — delivered surface

### Dependencies (installed to parent venv 2026-04-19 18:32)

- `prophet==1.3.0` (pre-built win_amd64 wheel — cmdstan compile bypassed, ~2 min install)
- `statsmodels==0.14.6`
- Transitive: `scipy 1.17.1`, `matplotlib 3.10.8`, `cmdstanpy 1.3.0`, `holidays 0.94`, `patsy 1.0.2`, `contourpy 1.3.3`, `kiwisolver 1.5.0`, `pillow 12.2.0`, `pyparsing 3.3.2`, `fonttools 4.62.1`, `cycler 0.12.1`, `tqdm 4.67.3`, `stanio 0.5.1`, `importlib_resources 7.1.0`
- `requirements.txt` updated — deps moved out of "Phase 2+ not yet active" block into a new "Phase 0B Sprint 2 — active" block with a LAZY-import note

### Backend

- `dashboard_pipeline/ai/forecasting.py` (**NEW** — ~480 lines):
  - `forecast_revenue(data_loader, *, horizon_months=None, store=None)` — main tool entry point
  - `SUPPORTED_STORES = ("total", "ოზურგეთი", "დვაბზუ")`; `_STORE_ALIASES` map accepts Latin `"ozurgeti"` / `"dvabzu"` / Georgian `"ჯამი"` / empty/whitespace → `"total"`
  - `_resolve_store()` + `_resolve_horizon()` — strict validation; Georgian error messages
  - `_extract_revenue_series(monthly_pnl, store)` — reads `row["total"]["pos_income"]` for `total`, `row["objects"][store]["pos_income"]` for named stores; silently skips malformed rows; requires `MIN_HISTORY_MONTHS=12`
  - `_next_month()` + `_future_months()` — month arithmetic with December → January rollover
  - `_yoy_growth_pct()` — `sum(last_12) / sum(prev_12) × 100 − 100`; `None` when history < 24 months or prev-12 sum is zero
  - `_load_prophet()` + `_load_arima()` — LAZY import helpers; return `None` on `ImportError`/sub-dep errors (graceful degradation)
  - `_run_prophet()` — Prophet 1.3.0 fit/predict; yearly_seasonality=True, weekly=False, daily=False, interval_width=0.95
  - `_run_arima()` — statsmodels ARIMA(1,1,1) fit + `get_forecast(steps)` + `conf_int(alpha=0.05)`; no pmdarima auto-selection (robust default for monthly retail)
  - `_ensemble()` — both engines succeed → baseline = arithmetic mean; bounds WIDEN via `max(upper)` / `min(lower)` (ensemble never narrower than most-cautious engine); one engine only → its rows verbatim
  - `_round_rows()` + `_safe_round_nonneg()` — 2-decimal rounding + **clamp ≥ 0** (revenue can't be negative; CI lower bounds going negative are statistical artifact, never shown to user as "პესიმისტური −6,832 ₾")
  - Stable return contract: `{source, store, horizon_months, history_months, history_start, history_end, last_12_months_total, yoy_growth_pct, engines_used, forecast[...], notes[...]}` or `{error, hint}`
  - `notes[]` always seeded with two mandatory caveats (POS/ვალუტა shock + ±10-15% variance); single-engine degradation inserts a third warning note at position 0

- `dashboard_pipeline/ai/tools.py`:
  - new `FORECAST_REVENUE_TOOL` schema inserted at `TOOL_SCHEMAS[3]` (compute-family cluster — after `compute`, before investigator tools); store enum `["total", "ოზურგეთი", "დვაბზუ"]`; horizon min=1 max=12; `required=[]`; `additionalProperties=False`
  - `ToolDispatcher.dispatch()` routes `"forecast_revenue"` → `forecast_revenue(data_loader=self._get_data, ...)`; import is LAZY (inside the `elif`) so callers who never touch forecasting skip the Prophet/statsmodels scientific stack at import time
  - `_SUMMARY_KEYS` extended with: `store`, `horizon_months`, `history_months`, `history_start`, `history_end`, `last_12_months_total`, `yoy_growth_pct`, `engines_used` — traces surface engines + history span to sources list without shoveling the full forecast table
  - Total tool count: **8** (was 7): `read_data_json`, `compute_waybill_total`, `compute`, `forecast_revenue`, `read_source_code`, `grep_code`, `read_excel_source`, `validate_vs_source`

- `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` (chat mode ONLY — investigator prompt untouched):
  - 🆕 **"🔮 პროგნოზირება (CRITICAL — Phase 0B Sprint 2)"** section — placed between general arithmetic (`compute`) and self-critique
  - trigger list: `მომავალი`, `პროგნოზი`, `რა მოხდება`, `რამდენი იქნება`, `მომდევნო N თვე` (N=1-12), `სეზონური ტრენდი`, `როდის იქნება პიკი`, `cash-planning`
  - refuses extrapolation beyond 12 months with explicit wording: "Prophet 1-12 თვეზე საიმედოა; 2-3 წელიწადი extrapolation-ია"
  - forbids historical use — past questions route through `read_data_json` / `compute_waybill_total`
  - mandatory output structure: Markdown ცხრილი (თვე/ბაზისი/ოპტ./პეს. + ₾) + trend sentence + ALL `notes` items + inline source `(წყარო: data.json → monthly_pnl, prophet+arima ensemble)`
  - `store` param guidance: default `total`; "ცალცალკე" → two invocations (Ozurgeti + Dvabzu) with two tables

### Tests (all green after Sprint 2)

- `tests/test_ai_forecasting.py` (**NEW** — **80 cases** in 10 classes):
  - `TestForecastToolSchema` 7 — registration, index 3, length 8, shape, store enum, description (prophet/arima mention, NEVER-historical guard)
  - `TestResolveStore` 12 — None/empty/whitespace → total; Georgian + Latin aliases; unknown → Georgian error; non-string → error
  - `TestResolveHorizon` 7 — default 3, valid [1,3,6,12], 0/negative/above-max/non-int/string all reject; numeric string accepted
  - `TestExtractRevenueSeries` 10 — total + per-store paths, empty/non-list/short-history rejects, malformed row skipped, missing store block skipped, NaN skipped, out-of-order sorted, exactly-min accepted
  - `TestMonthArithmetic` 5 — mid-year, December rollover, zero count, future month sequence
  - `TestYoYGrowth` 5 — short history → None, zero prev → None, flat → 0, +10%, -20%
  - `TestEnsemble` 5 — prophet-only, arima-only, both-none-empty, both-averaged-widen-bounds, mismatched-lengths-falls-through
  - `TestForecastRevenueHappyPath` 9 — total default 3, custom horizon 6, store passthrough, Latin alias, 2dp rounding, **non-negative clamp**, baseline = (prophet+arima)/2 = 750, YoY present/absent, last_12_months_total tail sum
  - `TestForecastRevenueErrors` 8 — bad horizon, unknown store, data_loader raises, non-dict data, missing key, short history, both engines unavailable (hint: "pip install"), single-engine degrades
  - `TestDispatcherRouting` 3 — dispatcher reaches forecast_revenue, call trace surfaces engines_used + horizon_months, store error forwarded
  - `TestPromptWiring` 2 — chat prompt mentions `forecast_revenue` + `🔮` + trigger keyword; investigator prompt does NOT include forecast section
  - `TestModuleExports` 4 — SUPPORTED_STORES tuple, horizon bounds, MIN_HISTORY_MONTHS=12, source label validity

- `tests/test_ai_agent.py::TestChatMode::test_investigate_mode_preserves_tool_surface` — updated expected tool set to include `forecast_revenue` (both chat + investigate modes surface it)

- `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` — updated `len(TOOL_SCHEMAS) == 8` and added `forecast_revenue` to the visible-names assertion

- **pytest 548/548 passed** (was 468; +80 new forecasting tests; 2 existing tests updated for 8-tool surface; 0 tests weakened or deleted)

### Live verification (2026-04-19 18:30 — scratch script against real `data.json` 135.84 MB, 44 months history 2022-06 → 2026-02)

| scope | engines | horizon | last 12m (₾) | YoY | first-row baseline (₾) | duration |
|---|---|---|---|---|---|---|
| TOTAL | prophet+arima | 3 | 1,897,584 | **+18.2%** | 134,944 (2026-03) | 9.17s (cold) |
| ოზურგეთი | prophet+arima | 6 | 647,443 | **−12.47%** 📉 | 57,643 (2026-03) | 1.23s |
| დვაბზუ | prophet+arima | 3 | 1,024,883 | **+45.14%** 📈 | 75,684 (2026-03) | 1.22s |

- **Non-negative clamp verified live**: Ozurgeti 2026-07/08 pessimistic went from −3,518/−6,833 → `0` after clamp; Dvabzu 2026-05 pessimistic from −6,832 → `0`
- **Warm-cache performance**: first Prophet call = 9.17s cold start (cmdstan compile), subsequent calls ~1.2s each — well under any chat UX budget

### Backend restart (2026-04-19 18:36)

- old PID **30788** stopped via `Stop-Process -Id 30788 -Force`; port 8000 freed
- new PID **19208** started via `$env:AI_ENABLE_THINKING='true'; python -u server.py`
- Uvicorn log shows `Application startup complete` + `Loaded suppliers.json` + `Scheduler started`
- `/api/status` → 200 OK; `data_age_seconds: 533`
- smoke import confirms tool list = 8 (`forecast_revenue` present)

### User UI live dog-food (2026-04-19 18:40)

- User chat with Sprint 2 prompt: _"მომდევნო 3 თვის შემოსავალი რა იქნება?"_
- AI delivered STOP-CHECK pass-through narrative + correct trigger detection + `forecast_revenue` tool call (default store=total, horizon=3)
- Output matched scratch-script values byte-for-byte: 134,944 / 141,994 / 147,679 ₾
- AI followed prompt contract: **🔮 ცხრილი** (3 columns ₾) + trend paragraph (YoY +18.2% + sum 1,897,584) + all `notes` caveats + inline source `(წყარო: data.json → monthly_pnl, prophet+arima ensemble — 44 თვის ისტორია)`
- No hallucinated numbers; no missed caveats; table format correct

---

## Phase 0B Sprint 1 — delivered surface

### Backend

- `dashboard_pipeline/ai/config.py`:
  - `AIConfig.enable_thinking: bool` (default `False`) — deployment-level feature flag
  - `AIConfig.thinking_budget_tokens: int` (default 5000, floor 1024 — Anthropic minimum)
  - `load_ai_config()` reads `AI_ENABLE_THINKING` + `AI_THINKING_BUDGET` env vars
  - `_parse_bool()` accepts `1/true/yes/on` + `0/false/no/off` (case-insensitive); invalid → default
  - `_parse_thinking_budget()` clamps below 1024 up to `_MIN_THINKING_BUDGET=1024`
  - `redacted()` surfaces both new fields safely

- `dashboard_pipeline/ai/agent.py`:
  - `_THINKING_TEMPERATURE = 1.0` + `_THINKING_OUTPUT_HEADROOM = 1024` constants (Anthropic contract)
  - `AIAgent._resolve_thinking(think)` — returns `False` unless BOTH `think=True` AND `config.enable_thinking=True` (deployment flag is authoritative)
  - `AIAgent._build_llm_call_kwargs(..., thinking_enabled)` — factored shared request builder; when `thinking_enabled=True` adds `thinking={"type":"enabled","budget_tokens":...}`, forces `temperature=1.0`, bumps `max_tokens` to `budget + 1024` headroom
  - `AIAgent.chat(..., *, mode="chat", think=False)` — new keyword-only `think` kwarg
  - `AIAgent.chat_stream(..., *, mode="chat", think=False)` — same
  - `usage.thinking` echoed in both chat response + stream `usage` event (server-authoritative)

- `dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA` (chat mode ONLY — investigator prompt untouched):
  - 🆕 **STOP-CHECK section** (Check 1 წელი / Check 2 date-column / Check 3 scope) — mandatory clarify on ambiguous year/date-field/scope queries; overrides "მოკლე პასუხი" / "მხოლოდ ციფრი" user phrasings
  - 🆕 **⚠️ Override-ის არარსებობა** subsection — explicit rule that STOP-CHECK cannot be bypassed by user phrasing
  - 🆕 **🧪 Multi-hypothesis section** — strategic/causal/decision/scenario/risk questions MUST produce 3 alternative hypotheses (X% + Y% + Z% ≈ 100%) + 🎯 რეკომენდაცია; factual questions stay single-answer; coexists with 📊/⚠️/🎯 Self-Critique structure

- `server.py`:
  - `_extract_think_flag(payload)` — validates boolean shape; missing/`None` → `False`; non-boolean → HTTP 400
  - `/api/chat` + `/api/chat/stream` both extract + forward `think` to agent; deployment gate enforced downstream

### Frontend

- `rs-dashboard/src/lib/aiClient.js`:
  - `postChat({ message, history, mode, think, signal })` + `postChatStream({ ..., think, onEvent })` — optional `think` body field; omitted when not a boolean (backward-compat)

- `rs-dashboard/src/hooks/useAIChat.js`:
  - `send(message, options = { mode, think })` — keyword-only options
  - Assistant entry stamped with `requestedThink` at submit (optimistic UI)
  - After stream ends, `resolvedThinking = usage.thinking` (server-authoritative) stamped on final entry

- `rs-dashboard/src/components/ChatAssistant.jsx`:
  - `THINK_STORAGE_KEY = "ai-advisor-think"` + SSR/private-browsing-safe `readStoredThink()`
  - New 🧠 Deep Think toggle button in composer row (next to 🔍 Investigate); `aria-pressed` + `data-think` + `data-testid="chat-think-toggle"`; tooltip `"ღრმა ფიქრი: AI 30-60 წამი ფარულად ფიქრობს, უფრო ღრმა პასუხი (+$0.01-0.05/კითხვა)"`
  - `localStorage["ai-advisor-think"]` persistence ("true" / "false" literal); try/catch guarded
  - Disabled during `sending`; `onSubmit` + `onSamplePromptClick` pass `{ mode, think }` to `send()`

- `rs-dashboard/src/styles/components.css`:
  - `.chat-panel__btn-think` + `--active` variant (violet theme, distinct from amber investigate toggle)
  - No existing styles touched

### Tests (all green after Sprint 1)

- `tests/test_ai_config_thinking.py` — **43 cases**: defaults, env var parsing, boolean parsing (1/true/yes/on vs 0/false/no/off vs garbage), budget clamping to 1024 floor, `redacted()` safety, load_ai_config integration
- `tests/test_ai_agent.py` **+13 cases** (Extended Thinking passthrough): `_resolve_thinking` truth table (4 permutations of deployment × per-turn flag), kwargs builder when enabled vs disabled, chat + chat_stream forward `think` into LLM call, `usage.thinking` echo, legacy callers without `think` kwarg still work, max_tokens bumped correctly
- `tests/test_ai_self_critique_prompt.py` **+9 cases** (Multi-hypothesis): STOP-CHECK directive presence, Multi-hypothesis trigger keywords (მიზეზი/რატომ/გადაწყვეტილება/სცენარი/რისკი), probability % pattern, 3-version structure, 🎯 რეკომენდაცია presence, coexistence with Self-Critique 📊/⚠️/🎯, investigator prompt absence of hypothesis directive, `build_system_prompt(mode="chat")` vs `mode="investigate"` differentiation
- `tests/test_server_think_flag.py` — **12 cases**: `_extract_think_flag` bool shape, missing/`None` → False, True → True, False → False, non-bool (string/int/dict/list) → 400, coexistence with `mode` field

### Live-verified by user this session

1. **Multi-hypothesis deep analysis** — strategic question "2026 deficit" → 3-version output with percentages + 🎯 რეკომენდაცია
2. **STOP-CHECK clarify** — ambiguous "December" query → AI refused single-year guess, requested year clarification
3. **Contradictory correction** — user asserted "10,000 ₾ feb 27" → AI corrected to 7,882.68 ₾ via `compute_waybill_total`
4. **Today's Pulse block** — `<TODAY>` section visible in first reply of new chat (date + yesterday POS context)
5. **Alpha supplier scenario analysis** — rich multi-section structured output with recommendations

## known caveats / do-not-touch

- `.env` populated with `ANTHROPIC_API_KEY` + `AI_ENABLE_THINKING=true` + `AI_THINKING_BUDGET=5000` + Telegram tokens + model names; **never commit, never overwrite, never echo values**
- backend interpreter MUST be parent venv (`C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`); project-local `.venv` for backend is prohibited
- `cashflow` tab: documented intentional exception (internal per-section calendars); never propose period-aware refactor
- `TOOL_SCHEMAS` module constant stays cache-control-free (tests assert); annotate only via `get_cached_tool_schemas()` deep-copy
- `SYSTEM_PROMPT_KA_INVESTIGATOR` (investigator prompt) — NOT modified through Sprint 1, 2, OR 3; all changes live in `SYSTEM_PROMPT_KA` (chat mode) only
- `today_context` block injected as NON-cached second system block — do NOT annotate with `cache_control` (would bust base prefix cache every session)
- localStorage keys: `"ai-advisor-mode"` (chat/investigate) + `"ai-advisor-think"` (true/false) — canonical; do not rename without migration
- `analytics_builders.py::build_supplier_aging` + `build_ap_monthly_trend` still use `გააქტიურების თარ.` (activation date); changing would redistribute AP buckets → requires explicit user sign-off
- broad refactor / unrelated code edits: forbidden
- 🆕 **Sprint 4 Part 2**: `MAX_TOOL_ITERATIONS` (=6) + `MAX_TOOL_ITERATIONS_DEEP` (=10) + `_resolve_max_iterations` helper form the stable deep-cap surface; never tighten plain chat below 6 (would break existing regression tests) and never raise deep cap above ~12 without re-validating Anthropic tool-use loop cost (10 observed ~$0.19 per Alpha strategic turn; 15+ would push >$0.30).
- API keys / tokens: NEVER accept from chat paste, NEVER print, use local file redirect only
- tests: never delete or weaken without explicit user direction
- `ping_anthropic.py` + `ping_telegram.py`: keep at root (reusable health-checks)
- 🆕 **Sprint 4** — `journal.py` `JOURNAL_KINDS` / `JOURNAL_STATUSES` / metadata keys (`journal_entry_type` / `journal_kind` / `journal_status` / `journal_due_date` / `journal_title`) are part of the stored contract; renaming them would orphan every existing journal row
- 🆕 **Sprint 4** — `MemoryStore.get_entries` + `update_metadata` + `delete_entry` must stay defensive (return `None`/`False`/`[]` on failure, never raise) — `today_context._collect_open_promises` counts on the silent-fail contract to avoid crashing the chat turn
- 🆕 **Sprint 4** — discriminator metadata `journal_entry_type="journal"` is REQUIRED on every journal row; without it `list_journal_entries` would surface plain `save_memory` rows and `update_journal_entry` would let status be stamped on any chat memory; the explicit `META_ENTRY_TYPE_KEY` check in `update_journal_entry` is what enforces this separation
- Stable agent surface (extend only, don't rewrite):
  - `AIConfig.enable_thinking` + `thinking_budget_tokens`
  - `AIAgent.chat(..., *, mode, think)` + `chat_stream(..., *, mode, think)` + `_resolve_thinking` + `_build_llm_call_kwargs`
  - `_extract_think_flag()` on server
  - `TOOL_SCHEMAS` length = **13** (Sprint 4 added `journal_add_entry` / `journal_list_entries` / `journal_update_entry` at indices 6/7/8 right after `save_memory`): `read_data_json`, `compute_waybill_total`, `compute`, `forecast_revenue`, `recall_context`, `save_memory`, `journal_add_entry`, `journal_list_entries`, `journal_update_entry`, `read_source_code`, `grep_code`, `read_excel_source`, `validate_vs_source`
  - `SUPPORTED_MODES = ("chat", "investigate")` + `DEFAULT_MODE = "chat"`
  - `forecast_revenue(horizon_months: 1-12, store: "total"|"ოზურგეთი"|"დვაბზუ")` contract: `{source, store, horizon_months, history_months, history_start, history_end, last_12_months_total, yoy_growth_pct, engines_used, forecast[...], notes[...]}` or `{error, hint}` — stable
  - `SUPPORTED_STORES = ("total", "ოზურგეთი", "დვაბზუ")` in `forecasting.py`
  - `recall_context` + `save_memory` contracts (Sprint 3) — see verified facts section above; both stable
- Prophet + statsmodels lazy-imported in `forecasting.py`; if either install breaks, `forecast_revenue` returns Georgian error + `pip install` hint instead of crashing the chat pipeline
- `chromadb` + `sentence-transformers` lazy-imported in `memory.py`; if either install breaks, `recall_context` / `save_memory` return Georgian error + `pip install` hint, rest of chat pipeline keeps working
- `_safe_round_nonneg` clamps forecast rows to ≥ 0 — revenue cannot be negative; never revert to `_safe_round` without re-adding clamp (tests pin it)
- ChromaDB persist dir = `ai_vectors/` (covered by `.gitignore` line 42); HuggingFace embedding cache lives outside repo (`~/.cache/huggingface/`) — no risk of vector store / model bloat in git

## verified facts (carry forward)

- Packet H: 13 period-aware tabs accepted, cashflow exception documented
- Waybill arithmetic ground truth (pinned by regression tests):
  - Feb 27 2026 `transport_start_date` + default exclusions + `nominal_amount` = **7,882.68 ₾ (20 rows)**
  - Feb 28 2026 same filter = **2,675.86 ₾ (11 rows)**
  - Feb 27 `date` (RS activation) = 7,004.06 ₾ (17 rows) — distinct by design
  - Feb 27 `delivery_date` = 13,347.48 ₾ (23 rows) — distinct by design
- `waybills[]` row shape: `date` + `transport_start_date` + `delivery_date` + `supplier` + `waybill_number` + `nominal_amount` + `status` + `type` + `effective_amount`
- `data.json` size: ~135.84 MB (latest measurement 2026-04-19 — 26 API artifacts, waybills ~21,233 rows)
- `TOOL_SCHEMAS` length = **13** (Sprint 4 added `journal_add_entry` / `journal_list_entries` / `journal_update_entry` at indices 6, 7, 8; was 10 after Sprint 3)
- pytest baseline progression: 381 (Phase 0A) → 458 (+77 Sprint 1) → 548 (+80 Sprint 2 + 2 updates) → 633 (+85 Sprint 3 with 3 existing test updates) → 742 (+109 Sprint 4 Part 1 with 4 existing test updates for tool count 10→13) → 743 (+1 Sprint 4 Part 2 ChromaDB range-filter fix test) → **752 green** (+9 Sprint 4 Part 2 `TestDeepIterationCap` cases; 0 tests weakened or deleted at any point)
- 🆕 **Sprint 4 Part 2 deep-iteration resolver (stable agent surface)**: `MAX_TOOL_ITERATIONS = 6` (default chat cap, unchanged) + new `MAX_TOOL_ITERATIONS_DEEP = 10` + new `AIAgent._resolve_max_iterations(*, mode, thinking_enabled) -> int` helper. Returns 10 when `think=True` OR `mode=="investigate"`, else 6. Both `chat()` and `chat_stream()` consume the resolved value per turn; fallback message unchanged; the existing `test_max_iterations_guard` tests still trigger at index 6 for default chat turns.
- 🆕 **Sprint 4** journal contracts (stable):
  - `add_journal_entry(title: str(3–500), kind: "promise"|"ai_commitment"|"recommendation"|"reminder", *, due_date: "YYYY-MM-DD"|None, tags: [str])` → `{ok, entry_id, title, kind, status, due_date, created_at, tags}` or `{error, hint}`
  - `list_journal_entries(*, status?, kind?, overdue?, due_before?, due_after?, limit: 1–100=20, today?)` → `{count, entries: [...], today}` or `{error, hint}` — entries sorted overdue→upcoming→rest
  - `update_journal_entry(entry_id, *, status: "open"|"done"|"cancelled")` → `{ok, entry_id, status, previous_status, tags}` or `{error, hint}`
  - `<TODAY>` block gains `⏳ ღია დაპირებები` sub-section when ChromaDB has journal rows; header suppressed when empty (never shows `0 ვადაგადაცილებული`)
- `monthly_pnl` shape (what `forecast_revenue` reads): list of `{month, objects: {ოზურგეთი: {pos_income, expenses, net}, დვაბზუ: {...}, საერთო: {...}, გაუნაწილებელი: {...}}, total: {pos_income, expenses, net}}` — 44 rows (2022-06 → 2026-02)
- Live forecast baselines (2026-04-19 scratch script) — treat as smoke-test expectations, NOT ground truth:
  - Total last 12m = 1,897,583.90 ₾; YoY **+18.2%**; 2026-03 baseline = 134,944 ₾
  - Ozurgeti last 12m = 647,443 ₾; YoY **−12.47%** 📉; 2026-03 baseline = 57,643 ₾
  - Dvabzu last 12m = 1,024,882.76 ₾; YoY **+45.14%** 📈; 2026-03 baseline = 75,684 ₾
- Prophet wall-clock: cold start **9.17s** (cmdstan compile); warm ~**1.2s** per call (single-engine or ensemble)
- Anthropic: Claude Sonnet 4.6 primary, `claude-haiku-4-5-20251001` fallback; prompt caching active on both `system` + `tools` prefix
- Extended Thinking contract: `temperature=1.0` forced + `max_tokens >= budget + 1024` + `thinking={"type":"enabled", "budget_tokens": N}`; deployment gate (`enable_thinking`) overrides per-turn `think=True`
- Live dog-food metrics (Phase 2, 2026-04-18 02:10 — baseline): investigator cached ~$0.047/call, chat fresh ~$0.063/call, first-token 3.66-4.52s, 5832-tok investigator prefix + 4808-tok chat prefix cached independently
- ChatAssistant bundle (pre-Sprint-1): 167.59 kB / gzip 50.74 kB; Sprint 1 adds small think toggle (expected +1-2 kB gzip)
- **Sprint 3 contract**: `recall_context(query: str, *, limit: 1–50=5, source: "chat"|"excel"=both, tags: [str])` + `save_memory(summary: str(10–8000), *, tags: [str], source: "chat")`; both return JSON-safe dicts; both gracefully degrade with Georgian error + `pip install` hint when chromadb / sentence-transformers wheels are broken; ChromaDB persist dir = `ai_vectors/` (gitignored); embedding model = `paraphrase-multilingual-MiniLM-L12-v2` (HF cached)

## current blocker

- active hard blocker: **არ არის**
- Phase 0B **fully closed** (Sprint 1 + 2 + 3 + 4 Parts 1+2+3) as of 2026-04-19 23:40; next canonical active work is Phase 1 kickoff (AI_GENIUS_PARTNER_PLAN v2.1 § Phase 1)

## 🆕 Georgian embedding Latin fix — delivered this session (2026-04-19 21:00–21:10)

### Problem

`paraphrase-multilingual-MiniLM-L12-v2` tokenises short Georgian abbreviations (`"ბოგ"` / `"თბს"` / `"რს"`) as near-identical neighbours in embedding space, so a user query like `"ბოგ ბანკი 2023"` ranked **TBC 2022.xlsx** as top-5 (cosine dist 0.21) while the correct **BOG 2023.xlsx** fell below rank 30. File names being Georgian was NOT the root cause — the multilingual model simply lacks sharp Georgian subword distinction.

### Fix (both layers together)

1. **Indexing side** (`dashboard_pipeline/ai/memory.py`):
   - New `_CATEGORY_GEORGIAN_LABELS = {"bank":"ბანკი","waybills":"ზედნადები","sales":"გაყიდვები","products":"პროდუქცია"}`
   - New `_FOLDER_LATIN_HINTS` map — Georgian folder → Latin alias, e.g. `"ბოგ ბანკი ამონაწერი" → "BOG bank Bank of Georgia statement"`, `"თბს ბანკი ამონაწერი" → "TBC bank statement"`, `"რს ზედნადები" → "RS waybill Revenue Service invoice"`
   - New `_build_chunk_header(path, tags)` helper returns 2-line prefix prepended to **every** Excel chunk before upsert:
     1. Keyword line (embedding-dominant): `ბოგ ბანკი ამონაწერი BOG bank Bank of Georgia statement 2023 ბანკი`
     2. Structured line (human-readable): `[ფაილი: Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx — წელი 2023 — კატეგორია ბანკი]`
   - `index_project_files()` loop now calls `header = _build_chunk_header(path, tags)` once and does `documents.append(f"{header}{chunk}" if header else chunk)` per chunk.

2. **Prompt side** (`dashboard_pipeline/ai/prompts.py::SYSTEM_PROMPT_KA`):
   - New `### 💡 Excel query გაძლიერება` subsection inside the `🔎 სემანტიკური მეხსიერება` block
   - Instructs the AI that when the user mentions `ბოგ` / `თბს` / `რს` in Georgian, the `recall_context.query` field must include the Latin alias as well (`"ბოგ ბანკი BOG Bank of Georgia"`), **but the rendered chat answer stays Georgian**.
   - Investigator prompt (`SYSTEM_PROMPT_KA_INVESTIGATOR`) remains untouched — memory section lives in chat mode only.

### Verification (in-process `_scratch_*.py` runs — scripts deleted after)

| Query | Top-1 file | Cosine distance | Status |
|---|---|---|---|
| `"ბოგ ბანკი 2023"` (pure Georgian) | TBC 2022.xlsx | 0.21 | ❌ (pre-fix behaviour — model limitation, not a bug) |
| `"ბოგ ბანკი BOG Bank of Georgia 2023"` | **BOG 2023.xlsx** ✅ | **0.096** | ✅ top-5 all BOG 2023 |
| `"თბს ბანკი TBC 2024"` | **TBC 2024.xlsx** ✅ | 0.128 | ✅ top-5 all TBC 2024 |
| `"რს ზედნადები RS waybill Revenue Service 2025"` | **RS 2025.xls** ✅ | 0.063 | ✅ |

### UI live dog-food (real Anthropic call through restarted parent-venv backend PID 18076)

User typed: _"2023 წლის ბოგ ბანკში რა ტიპის ოპერაციები ფიქსირდება?"_

AI response pulled:
- `recall_context(query="<ქართული + BOG/Bank of Georgia>" , source="excel")` (Latin injected automatically per prompt guidance)
- 5 matched chunks, **all from** `Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx`
- Full Georgian answer: POS terminal `POS1XA88` (ოზურგეთი, ბარამიძის 7), account `GE15BG...GEL`, SWIFT `BAGAGE22`, company `შპს ჯეო ფუდთაიმი` (400333858), MC + AMEX cards, per-tx fees 0.10–0.19 ₾
- Inline source: `(წყარო: მეხსიერება excel::financial_analysis_2023_xlsx — Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx)`

### Caveats / do-not-touch

- Pure Georgian abbreviations alone will STILL mis-rank at the embedding level — the prompt fix is the decisive piece. Any future query rewrite / pre-processing stripping the Latin alias will regress the behaviour.
- `_FOLDER_LATIN_HINTS` is a static 6-entry map covering the current `Financial_Analysis/` folder structure. If new bank folders appear (e.g. a "ქართუ ბანკი" folder), add a mapping there before re-indexing — otherwise the keyword line reduces to the folder stem only and the Latin token advantage disappears.
- Re-indexing triggered only by `--replace`; editing `_build_chunk_header` changes but forgetting `--replace` leaves old headers in place with no error.

## next recommended step

**Phase 1 Part D LIVE VERIFIED (2026-04-20 02:50).** Backend restart #9 + live Anthropic dog-food (5/5 PASS — same BOG 2026-02 question that previously failed) both done. **🎉 Phase 1 fully COMPLETE** (Part A + Part B + Part C + Part D). Canonical next action is **Phase 2 kickoff** (Dead Stock + Supplier Negotiation).

**Priority 0 — Phase 2 preview** (from `AI_GENIUS_PARTNER_PLAN.md` v2.1 § 2.11 + 2.12):
- Draft `PHASE_2_PREVIEW.md` covering both 2.11 + 2.12 (or two separate previews, user's call)
- **2.11 Dead Stock Liquidation** — identify 90+ day slow-moving SKU-s + freeze-cost estimate + discount/return salvage plan
- **2.12 Supplier Negotiation Prep** — per-supplier 1-pager (volume, payment history, comparables, 2-3 negotiation formulations)
- Each scope = preview-first, same A/B/C workflow
- ~1-2 dev days total

**Optional polish queue** (not blocking Phase 1):
- Upgrade embedding model to `intfloat/multilingual-e5-large` if Georgian abbreviation distinction ever matters without Latin aliasing (~580 MB; ~3–4× slower; not urgent)
- `--full` indexing pass (overnight) for complete historical coverage beyond the 2000-row sampled mode
- Dashboard UI surface for decision journal (Phase 3.4 `Decision Journal Tab` in `AI_GENIUS_PARTNER_PLAN.md` — currently chat-only)
- Prompt polish: "ვალი გადაცილებულია" for a specific supplier → bias towards `kind="promise"` instead of `kind="reminder"` (observation from Sprint 4 dog-food)

## authoritative files

- `PLAN.md`
- root `AGENTS.md` (plain ქართული communication rule — CRITICAL)
- `CONTEXT_HANDOFF.md` (this file)
- `AI_GENIUS_PARTNER_PLAN.md` v2.1 (active master plan)
- `HANDOFF.md` (slim banner + Phase 2 Sprint 1/2/3 + Waybill + Phase 0A + Service Worker + Phase 0B Sprint 1 + 🆕 Sprint 2 evidence)
- `HANDOFF_ARCHIVE/2026-04-packet-h.md` (Packet H archive)
- `PHASE_0A_PREVIEW.md` (Phase 0A Before/After preview — template for Sprint 2+ previews)
- `PHASE_0B_SPRINT2_PREVIEW.md` (Sprint 2 Before/After preview — approved)
- `PHASE_0B_SPRINT3_PREVIEW.md` (Sprint 3 Before/After preview — approved)
- `PHASE_0B_SPRINT4_PREVIEW.md` (Sprint 4 — ✅ COMPLETE banner)
- 🆕 `PHASE_1_PART_A_PREVIEW.md` (Phase 1 Part A — ✅ COMPLETE banner; full Before/After + 4-cluster breakdown)
- `PHASE_0B_PREVIEW.md` (meta-plan covering all 7 Phase 0B features)
- `.env.example`, `requirements.txt` (🆕 now includes `prophet>=1.1` + `statsmodels>=0.14` active)
- `ping_anthropic.py`, `ping_telegram.py`
- Backend AI module:
  - `dashboard_pipeline/ai/config.py` (Sprint 1 — thinking config)
  - `dashboard_pipeline/ai/agent.py` (Sprint 1 — `_resolve_thinking` + `_build_llm_call_kwargs` + `think` kwarg; Sprint 4 Part 2 — `_resolve_max_iterations` + `MAX_TOOL_ITERATIONS_DEEP`; 🆕 Phase 1 Part A — deep cap **10 → 12**)
  - `dashboard_pipeline/ai/prompts.py` (Sprint 1 — STOP-CHECK + Multi-hypothesis; Sprint 2 — 🔮 forecasting; Sprint 3 — 🔎 semantic memory; Sprint 4 — 📋 journal; 🆕 Phase 1 Part A — 🎯 role-contract + 🗺️ project-map + ⚖️ source-hierarchy + 🕵 data-skepticism + 🎭 5-hats + 🎯 confidence-labels + 📌 assumption-vs-fact anti-hallucination v2 + reinforced strict-tone; persona upgraded to "სტრატეგიული ფინანსური პარტნიორი"; investigator prompt **UNTOUCHED**)
  - `dashboard_pipeline/ai/tools.py` (Phase 0A `compute` + Waybill + Phase 2 investigator + Sprint 2 `FORECAST_REVENUE_TOOL` + 🆕 Sprint 3 `RECALL_CONTEXT_TOOL` + `SAVE_MEMORY_TOOL` at indices 4, 5 + dispatcher routes + `_SUMMARY_KEYS` memory fields)
  - `dashboard_pipeline/ai/forecasting.py` (Sprint 2 — Prophet + ARIMA ensemble, ~480 lines, lazy imports, non-negative clamp)
  - `dashboard_pipeline/ai/memory.py` (Sprint 3 — ChromaDB local store, ~1,012 lines incl. Sprint 4 `get_entries`/`update_metadata`/`delete_entry` helpers; lazy imports, multilingual MiniLM embedding, save/recall/index public API + `MemoryStore` class + singleton + `MemoryStoreUnavailable` exception)
  - `dashboard_pipeline/ai/today_context.py` (Phase 0A — daily snapshot builder; Sprint 4 extended with `open_promises` block + `project_root` kwarg + `_format_journal_entry` helper; 🆕 Phase 1 Part A — `_WEEKDAY_CONTEXT` 7-entry Georgian weekday hints + `_FIXED_MONTHLY_DEADLINES` (VAT + საპენსიო day 15) + `_upcoming_deadlines` / `_next_monthly_anchor` / `_clamp_day` helpers + `⏰ უახლოესი ვადები` block section with 🚨/⏰/📆 severity buckets)
  - 🆕 `dashboard_pipeline/ai/journal.py` (Sprint 4 — ~640 lines, CRUD wrapper over `chat_memory` collection with structured metadata discriminator; `add`/`list`/`update`/`delete` + `collect_today_journal_highlights` + full Georgian error messages)
- Project root scripts:
  - 🆕 `index_project_files.py` (Sprint 3 — ~330 lines, one-time Excel/CSV indexer; `--full` / `--replace` / `--dry-run` / `--max-rows N` / `--limit N` flags)
- Server:
  - `server.py` (Sprint 1 — `_extract_think_flag`)
- Frontend:
  - `rs-dashboard/src/lib/aiClient.js` (Sprint 1 — `think` body field)
  - `rs-dashboard/src/hooks/useAIChat.js` (Sprint 1 — `think` passthrough + `resolvedThinking`)
  - `rs-dashboard/src/components/ChatAssistant.jsx` (Sprint 1 — 🧠 Deep Think toggle + localStorage)
  - `rs-dashboard/src/components/ChatMessage.jsx` (Phase 2 Sprint 3 — CascadeBriefBlock)
  - `rs-dashboard/src/styles/components.css` (Sprint 1 — `.chat-panel__btn-think` violet theme)
  - `rs-dashboard/public/sw.js` + `rs-dashboard/vite.config.js` + `rs-dashboard/src/main.jsx` (SW cache-fix)
- Tests:
  - `tests/test_ai_config_thinking.py` (Sprint 1 — 43 cases)
  - `tests/test_ai_agent.py` (Sprint 1 — +13 Extended Thinking cases; Sprint 3 — +recall/save in `test_investigate_mode_preserves_tool_surface`)
  - `tests/test_ai_self_critique_prompt.py` (Sprint 1 — +9 Multi-hypothesis cases on top of pre-existing Phase 0A cases)
  - `tests/test_server_think_flag.py` (Sprint 1 — 12 cases)
  - `tests/test_ai_compute.py` (Phase 0A — 35 cases)
  - `tests/test_ai_today_context.py` (Phase 0A — 23 cases)
  - `tests/test_compute_waybill_total.py` (Waybill fix — 26 regression cases)
  - `tests/test_ai_investigator.py` (Phase 2 Sprint 1 — 66 cases; Sprint 3 — `TestExtendedToolSchemas::test_all_tools_exposed` updated for tool count 10)
  - `tests/test_ai_tools.py` (Phase 1 Polish + Waybill + Phase 0A — 35 cases)
  - `tests/test_ai_forecasting.py` (Sprint 2 — 80 cases; Sprint 3 — `test_tool_count_is_8` renamed to `test_tool_count_is_10`)
  - `tests/test_ai_memory.py` (Sprint 3 — 85 cases; Sprint 4 extended `_FakeCollection` with `get()` + range operators + `delete(ids=...)` fallback; `test_tool_count_is_13` updated; 85/85 still green)
- 🆕 `tests/test_ai_journal.py` (Sprint 4 — **109 cases** in 18 classes: tool schemas + constants + coercion (title/kind/status/due_date/limit/today) + normalise_extra_tags + where-builder + sort + add/list/update/delete + today highlights + today_context integration + dispatcher routing + prompt wiring + hit→entry + semantic recall interop; fake in-process ChromaDB fixture identical to test_ai_memory.py)
- 🆕 `tests/test_ai_prompts_phase1.py` (Phase 1 Part A — **66 cases** in 14 classes: TestStrategicPartnerPersona 5 + TestStrictToneContract 5 + TestProjectMap 5 + TestSourceHierarchy 4 + TestDataSkepticism 4 + TestFiveHats 8 + TestConfidenceLabels 4 + TestAssumptionMark 3 + TestInvestigatorPromptUntouched 3 + TestBuildSystemPromptWiring 2 + TestWeekdayContext 5 + TestUpcomingDeadlines 8 + TestMonthArithmetic 6 + TestTodayContextCtxShape 4)
- 5 existing tests re-anchored from `"ფინანსური მრჩეველი"` → `"🎯 როლის კონტრაქტი"` (chat-only persona marker in `test_ai_agent.py` + `test_ai_today_context.py`); `TestDeepIterationCap::test_constants_order` 10 → 12; `test_deep_cap_still_enforces_ten_iteration_limit` → `..._twelve_iteration_limit`

## verification pending / not run this session

- ✅ **Sprint 4 Part 1/2/3 + Phase 0B closure** — DONE (2026-04-19 22:22–23:40)
- ✅ **Phase 1 Part A code + tests + live** — DONE (2026-04-20 00:30–00:55); pytest 818/818 green
- ✅ **Phase 1 Part B code + tests + live** — DONE (2026-04-20 01:00–01:28); pytest 860/860 green
- ✅ **Phase 1 Part C code + tests + live** — DONE (2026-04-20 02:00–02:11); pytest **914/914 green** (was 860; +54 new; 0 weakened). Live dog-food: 5/5 DNA markers (ოზურგეთი YES + დვაბზუ NO + elasticity + 🟢/🟡 confidence + DNA hypothesis); ~2 წთ, $0.14, `stop_reason=end_turn`.
- ✅ **Backend restart #8** — DONE (2026-04-20 02:11, parent-venv PID 31176 via `Win32_Process.CommandLine` + 15-marker probe)
- ✅ **Phase 1 Part D code + tests + live** — DONE (2026-04-20 02:30–02:50); pytest **969/969 green** (was 914; +55 new; 0 weakened). Live dog-food **5/5 PASS** — same BOG 2026-02 question that previously failed → AI made 17 tool calls (4× recall_context Latin alias progression + 6× read_data_json + 3× read_excel_source + grep/read_source) + structured `ვცადე: (1)... (2)... (3)...` fallback with 3 clarifying questions. NEW caveat: `read_excel_source` blocks Georgian folder paths (separate carry-forward).
- ✅ **Backend restart #9** — DONE (2026-04-20 02:50, parent-venv PID **7776** via `Win32_Process.CommandLine` + 15-marker probe + AIConfig.enable_thinking=True)
- **Playwright full E2E run** — not executed (last green 9/9 on 2026-04-18 02:00; no frontend changes in Phase 1 Part A/B/C/D)
- **UI E2E for 🧠 Deep Think toggle** — not added (Sprint 1 carry-over; deferred)
- **`--full --replace` overnight indexing pass** — parking-lot (sampled mode 18,263 chunks in place)
- **Dashboard UI surface for decision journal** — parking-lot (Phase 3.4 in v2.1 plan)

## communication + interaction rules (CRITICAL — carry forward)

- მომხმარებლის ენა: **plain ქართული**; technical jargon ახსენი მხოლოდ მაგალითთან ერთად
- მომხმარებელი არ არის პროგრამისტი — ფაილის/ფუნქციის სახელი ახსენე მხოლოდ თუ user-მა თვითონ იხსენია
- ცხრილი / bullet list / emoji — თვალსაჩინოდ; კოდის block მხოლოდ საჭიროებისას
- ყოველი feature ახსენი 3 ფენად: რას აკეთებს + რატომ გჭირდება + შედეგი რა იქნება
- `ask_user_question` interactive widget — **არასოდეს** multi-choice-სთვის; user ნელა კითხულობს; plain text + მარტივი `კი/არა` ითხოვე
- API keys / tokens — NEVER ask to paste in chat
- მოქმედებამდე მოკლე `გააგრძელო? (კი / არა)` — ამ დადასტურების მოთხოვნას ახსნა არ დაურთო
- სესიაში progress narration-ს გაურბოდე; მხოლოდ blockers + questions + final summary
- "პროცესში თუ რამე შეგხვდე გასასწორებელი გვერდი არ ააუარო ან არ გადადო გავასწოროთ" — gap გამოჩნდა → მაშინვე გააკეთე, არ გადადო

## Copy/paste brief ახალი ჩატისთვის

```text
გააგრძელე აქედან. startup order:
1. PLAN.md
2. root AGENTS.md
3. financial-dashboard/CONTEXT_HANDOFF.md
4. financial-dashboard/AI_GENIUS_PARTNER_PLAN.md (active master plan v2.1)
5. financial-dashboard/HANDOFF.md — მხოლოდ file-level evidence საჭიროებისას
6. financial-dashboard/HANDOFF_ARCHIVE/2026-04-packet-h.md — მხოლოდ Packet H ისტორიისთვის

workspace root:
C:\Users\tengiz\OneDrive\Desktop\AI აგენტი

canonical project path:
C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\financial-dashboard

backend interpreter (mandatory):
C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe

active packet/status:
- Packet H ✅ (2026-04-17) — Process 0-12 accepted, cashflow exception documented
- AI Phase 0 / 1 / 1 Polish / Streaming SSE / Phase 2 Sprint 1-3 + Live + UI Dog-Food ✅ (2026-04-17/18)
- Waybill Arithmetic Bug-Fix ✅ (2026-04-18 04:00) — Feb 27 = 7,882.68 ₾, Feb 28 = 2,675.86 ₾ pinned
- Phase 0A Critical Foundation ✅ (2026-04-18 23:00) — 73 new tests, 381 green
- Service Worker Cache Bug-Fix ✅ (2026-04-19 00:20)
- Phase 0B Sprint 1 (Extended Thinking + Multi-hypothesis) ✅ (2026-04-19)
- Phase 0B Sprint 2 (Prophet Forecasting) ✅ + LIVE (2026-04-19 18:42)
- Phase 0B Sprint 3 (ChromaDB + RAG) ✅ + LIVE + Latin fix + path_token SHA256 fix (2026-04-19 21:35) — 26 files → 18,263 unique chunks
- Phase 0B Sprint 4 Part 1 (Decision Journal code + LIVE CRUD + LIVE Anthropic dog-food) ✅ (2026-04-19 22:05–23:05) — `journal.py` CRUD + 3 tools (TOOL_SCHEMAS 10 → 13) + `<TODAY>` ⏳ block + `SYSTEM_PROMPT_KA` 📋 section + 109 new tests
- 2 bug-fixes en route: (1) Windows venv Path-check caveat (use `Win32_Process.CommandLine` / `sys.prefix`, NOT `Get-Process Path`); (2) ChromaDB 1.5.x `$lt`/`$gt` silent no-op on string metadata (date filters in Python)
- Phase 0B Sprint 4 Part 2 (Phase 0B-wide metrics + deep-iteration fix) ✅ (2026-04-19 23:15–23:34) — 7 scripted `/api/chat` calls: ~$0.25 total / ~2.4 min / cache warm calls 2–7 (~10× drop); surfaced Sprint 1 `MAX_TOOL_ITERATIONS=6` cap on Extended Thinking → introduced `MAX_TOOL_ITERATIONS_DEEP=10` + `_resolve_max_iterations(mode, thinking_enabled)` helper. 9 `TestDeepIterationCap` cases; pytest 752/752 green.
- Phase 0B Sprint 4 Part 3 (retrospective + docs refresh + closure) ✅ (2026-04-19 23:40)
- **Phase 0B FULLY CLOSED** ✔️ (2026-04-19 23:40)
- **Phase 1 Part A — AI "ხასიათი" + "საზრისობა" Layer 1 COMPLETE + LIVE VERIFIED** ✅ (2026-04-20 00:55) — 8 CRITICAL sections in `SYSTEM_PROMPT_KA` (🎯 role-contract + 🗺️ project-map + ⚖️ source-hierarchy + 🕵 data-skepticism + 🎭 5-hats + 🎯 confidence-labels + 📌 assumption-vs-fact + reinforced strict-tone); persona "სტრატეგიული ფინანსური პარტნიორი"; `MAX_TOOL_ITERATIONS_DEEP` **10 → 12**; `today_context.py` weekday + VAT/საპენსიო day-15 deadline block; 66 new tests; pytest 818/818 green. **LIVE (2026-04-20 00:55)** — 5 hats + 3-version multi-hypothesis + 🟢 საიმედო + auto `save_memory` (chat_705a38ef) + `journal_add_entry` (journal_886cce34); 26 tool calls, 151.6s, ≈$0.12.
- **Phase 1 Part B — ქართული რეგულაცია + ფრენჩაიზი კონტექსტი COMPLETE + LIVE VERIFIED** ✅ (2026-04-20 01:28) — `SYSTEM_PROMPT_KA` gained `🇬🇪 ქართული რეგულაცია` section between 🗺️ პროექტის რუკა and ⚖️ წყაროების იერარქია: (a) `💰 საჯარო გადასახადები` — VAT 18% (day 15) + საპენსიო 2% + 2% (day 15) + standard 15% / small-business 1% / < 500K ₾ / < 100K ₾ VAT threshold + CB+1% penalty; (b) `🧾 RS.ge` — ე-ინვოისი 30-day unpaid warning + waybill 3-date cross-reference; (c) `🏪 ფრენჩაიზი` — Royalty 4-7% + Sourcing 60-75% + Opening fee $5-20K + Brand standards (contract breach / royalty freeze / termination); (d) `📋 Baseline facts` — 4 user-specific facts (Royalty %, Sourcing %, income tax status, VAT registration) → AI asks + `journal_add_entry(kind="reminder")` auto-invocation; (e) `🌅 ქართული თვის რიტმი` — 4 buckets (1-10 calm / 11-14 pre-deadline / 15 deadline day / 16-30 accumulation) + recommendation rules. 42 new tests in `test_ai_prompts_phase1b.py` (8 classes: section anchor + tax + RS.ge + franchise + baseline + rhythm + wiring + investigator-untouched). Investigator prompt UNTOUCHED (4 do-not-touch tests). pytest **860/860 green** (was 818; +42; 0 weakened). **LIVE dog-food (2026-04-20 01:28)** — 1 scripted in-process `AIAgent.chat(think=True)` call with ოზურგეთი POS 20K ₾ capex timing question: 4/5 hats (💼/⚠️/🎯/🪞; 🔧 skip) + multi-hypothesis 40/35/25% + 🟢 საიმედო + 🟡 ვარაუდი stack + VAT/საპენსიო 15 მაისი mention + inline წყარო + **Monthly rhythm rule LIVE-applied** ("2026-05-16 — 2026-06-01 მე-2 ტერმინალი **15-ის deadline-ის შემდეგ**") + **Baseline facts mechanism LIVE** (`recall_context("VAT სტატუსი ... მცირე ბიზნესი cash planning")`) + auto `journal_add_entry` (journal_15c67afa... post-run cancelled). 10 tool calls under 12-iter cap; 111.72s; 30,197 in + 4,507 out + 108,127 cache_read; ≈$0.19; `stop_reason=end_turn`.

- 🆕 **Phase 1 Part C — Multi-Store DNA COMPLETE + LIVE VERIFIED** ✅ (2026-04-20 02:11) — `SYSTEM_PROMPT_KA` gained `🏪 მაღაზიების DNA` section between 🌅 ქართული თვის რიტმი and ⚖️ წყაროების იერარქია (~700 tokens): (a) `🏪 ოზურგეთი — Urban Flagship` 10-row DNA card; (b) `🏡 დვაბზუ — Rural Local` 10-row DNA card; (c) `🌅 სეზონური რიტმი` soft hint (ოზურგეთი 6-9 ზაფხული + დეკემბერი; დვაბზუ 10/25 payday + Easter; ორივეს 31 დეკემბერი); precise numbers → `forecast_revenue(store=...)`; (d) `🎯 DNA-ს გამოყენება` 7-dimension guidance table (Promotion / ახალი კატეგორია / Supplier / Staffing / Pricing / Cash / Store comparison); (e) `📋 Baseline facts — store-level` 4 placeholders (ტურისტული თვეების ფანჯარა / ხელფასი days / Top-3 supplier concentration / Evening:Daytime ratio) tagged `topic:store_dna` + `kind:reminder`; (f) `⚠️ DNA-ს over-apply` guardrails — DNA მხოლოდ სტრატეგიულზე. 54 new tests in `test_ai_prompts_phase1c.py` (10 classes). Investigator prompt UNTOUCHED (6 do-not-touch tests + 15 Part C markers absent). pytest **914/914 green** (was 860; +54; 0 weakened). **LIVE dog-food (2026-04-20 02:11)** — 1 scripted in-process `AIAgent.chat(think=True, mode="chat")` call with თამბაქოს 10-15% ფასდაკლება cross-store question: 5/5 DNA markers (ოზურგეთი YES + დვაბზუ NO + elasticity reasoning + 🟢 საიმედო + 🟡 ვარაუდი confidence + DNA-based hypothesis). 6+ tool calls under 12-iter cap (`read_data_json` ×4 + `recall_context` excel + `read_excel_source`); ~2 წთ; 178,889 in + 5,607 out + **166,817 cache_read**; ≈$0.14; `stop_reason=end_turn`.
- **🎉 Phase 1 FULLY COMPLETE** (Part A ✅ + Part B ✅ + Part C ✅ + Part D ✅)
- **🎉 Phase 2.11 + 2.12 FULLY LIVE VERIFIED** ✅ (2026-04-20 15:30) — Backend restart #10 (PID 29332, `AI_ENABLE_THINKING=true` target state reached) + 3 scripted `/api/chat/stream` dog-foods all PASS on real Anthropic Sonnet 4.6:
  - Phase 2.12 Focused (ჯიდიაი) 9/9 PASS, 49.8s, ~$0.10
  - Phase 2.12 Portfolio (ranked Top-10, HHI 551, ~$40K + $27K + $0.9K savings on top-3) 10/10 PASS, 49.1s, ~$0.27, `usage.thinking=true` ✅
  - Phase 2.11 Dead Stock (~1.49M ₾ frozen, 3-bucket salvage plan, 30.3% unmatched warning LIVE) 9/9 PASS, 65.9s, ~$0.11, `usage.thinking=true` ✅
  - Cross-link: AI correctly paired specific dead-stock SKU (`პარლამენტი აქვა ბლუ 87,850 ₾ → ჯიდიაი`) with the #1 supplier flagged by Phase 2.12 portfolio — full strategic composition works end-to-end
- **🎉 Phase 3.1 Co-Designer Mode FULLY LIVE VERIFIED** ✅ (2026-04-20 17:50) — Backend restart #11 (PID 29400, `TOOL_SCHEMAS=16`, PULL-ONLY policy):
  - TRIGGER `"რას შემომთავაზებდი?"` → 3 structured proposals (all 6 fields + critic self-review + journal IDs); AI first checked existing proposals via `journal_list_entries` + `recall_context`; 146.1s ✅
  - ANTI-TRIGGER strategic `"რატომ margin −80%?"` → 0 `propose_feature` calls, analyzed via `compute` + 5× `read_data_json`; 75.4s ✅
  - ANTI-TRIGGER data `"რამდენი მომწოდებელი?"` → 0 `propose_feature` calls, quick `read_data_json` (270); 9.5s ✅
  - All `stop_reason=end_turn` + `usage.thinking=true` ✅; 3 test proposals cancelled post-verification (journal clean)
- **🎉 Phase 3.5 + 3.7 Cash Runway + Dashboard Widgets FULLY LIVE VERIFIED** ✅ (2026-04-20 23:50) — Backend restart #12 (PID 20876, `TOOL_SCHEMAS=17` with `compute_cash_runway` at index 11): 3 ახალი ნაწილი (1) `💀 Dead Stock` გვერდი ანალიტიკური ტაბ-ჯგუფში (donut + Top-30 + 4-action salvage + 30%+ unmatched warning); (2) `⚠️ Supplier Concentration` widget `🏢 მომწოდებლები` ტაბში (HHI gauge + Top-5/10/20 bars + Top-3 leverage candidates + `#1 priority` steering); (3) `compute_cash_runway` AI tool (PULL-ONLY; burn rate + runway label 🟢/🟡/🔴 + burn_trend honesty). pytest 1303/1303 green; live dog-food 6/6 PASS (57.1s, `usage.thinking=true`, user provided BOG 52K + TBC 28K → 3.2-თვე runway / 25,054 ₾/თვე burn / multi-hypothesis / Multi-Store DNA / 🪞 critic).
- **🎉 Phase 4A Debt Repayment Plan Part A FULLY LIVE VERIFIED** ✅ (2026-04-21 00:50) — Backend restart #13 (PID 10800, `TOOL_SCHEMAS=18` with `build_debt_repayment_plan` at index 12): AUTONOMOUS STRATEGIST philosophy shift (dashboard AI → Cascade-ივით თავისუფალი / აზრების მომცემი); new `debt_plan.py` (~620 lines) 4-factor criticality (debt 30% + aging 25% + freq 25% + dysfunc 20%) + 3-month inflow forecast ±10% + per-supplier recommendations + sustainable allocation bool + risks + 🪞 critic; `SYSTEM_PROMPT_KA` 📋 ვალების გეგმა section with BROAD triggers + IMMEDIATELY-call workflow + anti-triggers → `prepare_supplier_brief`/`compute_cash_runway`; pytest 1393/1393 green (+90); live 12/12 PASS across 3 scenarios (BROAD trigger / focused priority list / anti-trigger).
- **🎉 Phase 4A Part B FULLY LIVE VERIFIED + 2 BUG-FIX** ✅ (2026-04-21 02:35) — Backend restart #14 (PID 21408) after React page + tests + endpoints landed; Backend restart #16 (PID **18960**) after mid-session crash. React `DebtPlan.jsx` (~600 lines) auto-generates on `#debt_plan` mount via POST `/api/debt-plan` → 3-card strip (Forecast / Allocation sustainable bool / NonPriority baseline) + RisksBox + PriorityTable with expandable rows + duration/priority dropdowns + Approve → POST `/api/debt-plan/save`; 39 new endpoint tests in `test_api_debt_plan.py`; `tools.py::JOURNAL_KINDS` mirror-tuple synced 5→6 (`repayment_plan`).
  - **Bug #1 — Schema** (`debt_plan.py::_active_debt_suppliers` expected dict but `supplier_aging` is a list directly in production `data.json`): fixed with list+dict tolerance; 4 new `TestSupplierAgingListSchema` tests ✅
  - **Bug #2 — Ranking** (1,434-day zombie suppliers ranked #1; ჯიდიაი 313K ₾ active debtor at #30 because weight formula was aging-dominant): fixed with `ACTIVE_CUTOFF_DAYS=365` dormant-quarantine + weight rebalance (debt 0.30→**0.50**, aging 0.25→0.15, freq 0.25→0.20, dysfunc 0.20→0.15); **ჯიდიაი now #1 score 0.585** (was #30 score 0.412); 6 new `TestDormantSupplierQuarantine` tests ✅
  - pytest **1443/1443 green** (was 1433; +10 new; 0 weakened)
  - Live POST smoke realistic: 2-თვე unsustainable (246K/თვე > 140K inflow); 6-თვე უკეთესი (priority 85,700 ₾ = 61% forecast) but baseline exceeds — business cash deficit ~35K ₾/თვე cleanly surfaced
  - Playwright click-through `#debt_plan` ✅: 3 cards + risks + 5 priority rows render; row expansion → "💡 რატომ კრიტიკული" + analysis visible
  - **⚠️ Pending**: approve/save + regenerate button clicks UI-test; `/api/debt-plan/save` journal smoke; `/api/chat/stream` dog-food (`"შემიდგინე ვალების გეგმა"` → AI `build_debt_repayment_plan`)

ამ ჩატში რა შეიცვალა (2026-04-21 03:12+) — Phase 4A closure დოკუმენტაცია:
- **Context**: წინა სესია დასრულდა Phase 4A Part B LIVE VERIFIED + 2 BUG-FIX-ით (2026-04-21 02:35), მაგრამ `CONTEXT_HANDOFF.md` Copy/paste brief + `PLAN.md` იყო stale — Phase 3.1/Backend #11 PID 29400/TOOL_SCHEMAS=16/pytest 1163-ს აჩვენებდა, ხოლო სინამდვილეში Phase 4A / Backend #16 PID 18960 / TOOL_SCHEMAS=18 / pytest 1443 იყო ცოცხალი.
- **PLAN.md** — რედაქტირდა 3 ადგილას: (1) მთავარი სტატუსის ბანერი Phase 4A Part B-ზე; (2) "Backend live" ხაზი PID 18960 + TOOL_SCHEMAS=18 + Phase 4A-ის ყველა ფაზა ცოცხალი; (3) v2.1 დამატებები block-ში ახალი ჩანაწერი Phase 4A Part B + Backend #14/#16.
- **CONTEXT_HANDOFF.md** — რედაქტირდა 6 სექცია: (1) canonical snapshot backend server line PID 31176→**PID 18960**; (2) completion timeline — Phase 4A Part B "LIVE UI VERIFY PENDING" → **COMPLETE**, + ახალი entries: Part B LIVE VERIFIED + 2 BUG-FIX / Backend #14 / Backend #16; (3) active packet/status block — Phase 3.5/3.7 + Phase 4A Part A + Part B FULLY LIVE VERIFIED entries; (4) backend live line TOOL_SCHEMAS 16→18 + Phase 4A phases; (5) verified facts — TOOL_SCHEMAS list 16→18 + `compute_cash_runway` contract + `build_debt_repayment_plan` contract + JOURNAL_KINDS 5→6-tuple; (6) pytest baseline 1163 → 1443 progression (+280 since last brief refresh); (7) next recommended step — Option A Phase 4A closure / B Phase 5 kickoff / C parking-lot / D real-user dog-food expansion; (8) verification pending — Phase 4A Part B 3 pending items clearly flagged (approve/save UI test / chat-stream dog-food / preview doc banner); (9) authoritative files — added `debt_plan.py` + `DebtPlan.jsx` + `test_ai_debt_plan.py` + `test_api_debt_plan.py`; (10) "ამ ჩატში რა შეიცვალა" — ეს ბლოკი (docs-refresh work).
- **არ შეცვლილა**: არც backend, არც production კოდი, არც ტესტები, არც ფრონტენდი, არც `.env`, არც HANDOFF.md. მხოლოდ documentation sync.
- **Pending ახალ ჩატში**: 3 ცალი (Phase 4A Part B UI approve/save click-through + `/api/chat/stream` dog-food + `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B LIVE VERIFIED banner).

OLD-CHANGE BLOCK (Phase 2.11/2.12 Live dog-food, 2026-04-20 15:00–15:30, kept for reference):
- **Backend restart #10** — intermediate PID 27700 (parent-venv CommandLine OK, but launching shell missing `AI_ENABLE_THINKING` env) stopped; fresh **PID 29332** via `$env:AI_ENABLE_THINKING="true"; Start-Process '...\venv\Scripts\python.exe' -ArgumentList '-u','server.py'`. Verified: `/api/status` 200, `Win32_Process.CommandLine` matches parent-venv, in-process `TOOL_SCHEMAS=15` + `config.enable_thinking=true` + `MAX_TOOL_ITERATIONS_DEEP=12` + `DEFAULT_TIMEOUT_S=120.0` + 15 Phase 2.12 📞 markers (chat 15/15 / investigator 0/15).
- **New do-not-touch rule** — after any backend restart, confirm env propagation via **`usage.thinking=true` in a real SSE call**, not just `Win32_Process.CommandLine` match. CommandLine only shows the executable path; the launching shell's env vars are invisible there. Focused dog-food #1 ran on pre-restart PID 27700 and still returned feature-accurate output, but `usage.thinking=false` — silently degraded. Always verify env on first live call after any `Start-Process` launch.
- **Phase 2.12 Focused dog-food** — `"ხვალ შპს ჯიდიაი-სთან მაქვს შეხვედრა, რა ვთხოვო?"` → `prepare_supplier_brief(supplier_name="ჯიდიაი")` + bonus `recall_context` → 2661-char Georgian brief: tax_id `406181616` auto-resolved; `match_confidence 🟢 HIGH (exact name match)`; Ranking #1; `Leverage: 🟢 HIGH (71/100)`; 5-row factor table (897,043 ₾ spend / 17.25% share / 313,922 ₾ debt / 51d inactivity / 44mo tenure); 3 ranked plays (6% discount vs 313K ₾ 15-day payment / 3% volume + 61K blanket / price alignment fallback); critical-signal callout; inline `წყარო:`. 9/9 criteria PASS on feature layer. Ran on pre-restart PID 27700 (pre-env-fix), so `usage.thinking=false` — not a regression, just missing the deep cap.
- **Phase 2.12 Portfolio dog-food** — `"ვის უნდა ვესაუბრო პირველად ფასდაკლებისთვის?"` → `prepare_supplier_brief()` (no identifier = portfolio mode) → 2248-char ranking deck: 270 suppliers / 5,201,362 ₾ / Top-5 41.9% / HHI 551 (moderate); Top-3 table `#1 ჯიდიაი 17.25% 🟢 HIGH 71 ~39,800 ₾ / #2 კოკა-კოლა გურია 7.72% 🟡 MEDIUM 57 ~27,091 ₾ / #3 პარტნიორი 1.41% 🟡 MEDIUM 55 ~903 ₾`; full Top-10 with leverage icons; `🎯 სტრატეგია` section with `1. ჯიდიაი — დაიწყე აქ, ეს ყველაზე მომგებიანია` steering + `#1 priority`. 10/10 PASS including `usage.thinking=true` ✅. 3104 in + 1569 out + 62400 cache_create (fresh post-restart).
- **Phase 2.11 Dead Stock dog-food** — `"რომელი პროდუქტები ზიან გაუყიდელი 6+ თვე? რა ფული გვაქვს გაყინული..."` → `analyze_dead_stock(days_threshold=180, top_n=30, store="total")` + 3 `compute` aggregations → 3964-char strategic brief opening with mandatory 30.3% unmatched warning (4,049 / 13,344 SKU barcode drift); 3-bucket breakdown (181–365d 2,003 SKU ~452,634 ₾ / 365d+ 2,799 SKU ~1,040,336 ₾ / Unmatched 4,049 SKU 🟠); 3-action Salvage Plan (−30% discount 452K ₾ 🟡 / supplier return 1,040K ₾ 🟢 / write-off+manual audit 🟠); Top-10 specific products with name + supplier + frozen ₾ + last-sale-date + recommended action. Total frozen-cash estimate `~1,492,970 ₾ (🟡 ზედა შეფასება)`. 9/9 PASS including `usage.thinking=true` ✅. 13684 in + 3198 out + 93589 cache_read (warm).
- **Session cost** — ~$0.48 total for 3 scripted dog-foods on real Anthropic Sonnet 4.6 with Extended Thinking engaged on 2/3 calls.

OLD-CHANGE BLOCK (Phase 2.12 CODE COMPLETE, kept for reference):
- **New tool** — `dashboard_pipeline/ai/supplier_brief.py` (~1280 lines): `prepare_supplier_brief(data_loader, *, supplier_name=None, tax_id=None, lookback_months=12, top_n=5, benchmark_n=5, today=None)` triangulates `suppliers` × `imported_products.suppliers` × `imported_products.products` × `supplier_aging` → 1-page negotiation deck. Match precedence: `tax_id_exact` (high) → `name_exact` (high) → `name_substring` (medium) → `name_partial` (low). Focused-mode output: supplier identity + volume_snapshot (spend / share / tenure / monthly_avg) + payment_profile (billed / paid / debt / unpaid_pct / reliability label) + price_benchmark (dual-source comparison rows + cheapest alternative + gap %) + leverage_score 0-100 + 1-3 negotiation_plays (each with `ask_ka` / `give_ka` / `rationale_ka` / `evidence_refs[]` / `warning_ka`). Portfolio mode: HHI concentration + top-5/10/20 Pareto + ranked top_candidates. Leverage score weighting: `portfolio_share 30 + payment_leverage 20 + dual_sourcing 20 + tenure 15 + relationship_health 15`; bands 🟢 HIGH ≥70 / 🟡 MEDIUM ≥40 / 🟠 LOW <40. Plays: (1) `cash_discount_for_payment_speed` (🟢 high; unpaid ≥10 %) / (2) `volume_commitment_discount` (🟡 medium; share ≥3 % + monthly_avg ≥20K) / (3) `dual_source_leverage` (🟠 use_only_if_stalled; requires comparable-row + more-expensive).
- **Tool wiring** — `dashboard_pipeline/ai/tools.py` gained `PREPARE_SUPPLIER_BRIEF_TOOL` schema at `TOOL_SCHEMAS[10]` (right after `analyze_dead_stock`); dispatcher routes via LAZY import; `TOOL_SCHEMAS` length **14 → 15**; investigator tools stay at the end (cache-prefix placement preserved).
- **Prompt section** — `SYSTEM_PROMPT_KA` gained `📞 მომწოდებელთან მოლაპარაკების მომზადება (CRITICAL — Phase 2.12)` section between 💀 Dead Stock and 🔄 Self-Correction: triggers (meeting / discount-ask / leverage-question / alternative-supplier / portfolio-wide) + anti-triggers (debt/payment/waybill lookups route to `read_data_json`) + 🪪 Identity Confidence Protocol (medium/low must prompt user for confirmation before quoting figures) + output-format contract (🟢/🟡/🟠 leverage label + factor table + negotiation plays table + `warning_ka` verbatim relay + `data.json` source attribution) + 🛡 Relationship Discipline (Relationship > margin; `#3 dual_source_leverage` last-resort; no data-less aggressive moves) + 🧠 Portfolio Mode example + 🎯 confidence labels. Investigator prompt **UNTOUCHED**.
- **Module tests** — `tests/test_ai_supplier_brief.py` (**NEW** — 76 cases across 13 classes): TestPrepareSupplierBriefSchema 7 + TestPrepareSupplierBriefDispatch 4 + TestHelpers 10 + TestSupplierResolution 8 + TestDateRangeResolution 5 + TestVolumeSnapshot 5 + TestPaymentProfile 5 + TestPriceBenchmark 5 + TestLeverageScore 6 + TestNegotiationPlays 7 + TestEndToEnd 6 + TestMatchingWarnings 3 + TestPortfolioMode 5.
- **Prompt-guard tests** — `tests/test_ai_prompts_phase2_12.py` (**NEW** — 54 cases across 10 classes): TestSupplierNegotiationSection 5 + TestTriggerList 7 + TestAntiTriggers 4 + TestIdentityConfidenceProtocol 5 + TestOutputFormat 7 + TestRelationshipDiscipline 4 + TestPortfolioModeExample 4 + TestConfidenceLabels 2 + TestBuildSystemPromptIntegration 3 + TestInvestigatorPromptUntouched 6 + TestPriorPhasesStillPresent 6 (15 Phase 2.12 markers absent from investigator prompt confirmed).
- **Existing test bumps** — Tool-count pins 14 → 15 in 5 files: `tests/test_ai_memory.py::test_tool_count_is_15`, `tests/test_ai_journal.py::test_total_count_is_15`, `tests/test_ai_forecasting.py::test_tool_count_is_15`, `tests/test_ai_investigator.py::TestExtendedToolSchemas::test_all_tools_exposed` (now asserts 15), `tests/test_ai_agent.py::test_investigate_mode_preserves_tool_surface` (name set includes `prepare_supplier_brief`).
- **Bug caught en-route** — `_normalize_name` regex ordering: `( 123-დღგ ) შპს X` parenthetical cleanup left leading space that blocked `^შპს|^სს|^ი.მ` legal-prefix anchors. Fix: `text = text.lstrip()` inserted BEFORE `_LEGAL_PREFIX_RE.sub(...)`. Also fixed a corrupted `📞` emoji (U+FFFD replacement char from initial write) back to the proper telephone emoji in `SYSTEM_PROMPT_KA`.
- **Smoke test** (not committed) — 5 scenarios against real `data.json` all PASS: focused via `tax_id="406181616"` → rank #1 / share 17.25 % / leverage 71 🟢 HIGH / 3 plays / 0 warnings; focused via fuzzy `supplier_name="ჯიდიაი"` → high-confidence exact match (after `_normalize_name` fix); კოკა-კოლა გურია → 34 dual-source rows + 27K ₾ savings; portfolio mode (no args) → 270 suppliers, HHI 551 moderate, top-5 41.9 %; unknown supplier → Georgian error + hint.
- **Docs refresh** — `PLAN.md` status banner + v2.1 დამატებები block updated with Phase 2.11 + 2.12 COMPLETE lines; `CONTEXT_HANDOFF.md` top banner + completion timeline + copy/paste brief refreshed (this turn).
- **Zero regressions** — pytest **1163/1163 green** (was 1033 before 2.11 + 2.12; +76 module + +54 prompt-guard = +130 new; 0 tests weakened or deleted); no contract breaks.

OLD-CHANGE BLOCK (Phase 1 Part D, kept for reference):
- Phase 1 Part D COMPLETE + LIVE VERIFIED (2026-04-20 02:50); `🔄 საკუთარი თავის გასწორების ციკლი` section added to `SYSTEM_PROMPT_KA`; 55 new tests; 969/969 green; Backend restart #9 → PID 7776; Live dog-food 5/5 PASS on BOG 2026-02 question (17 tool calls; AI retried with Latin alias progression). Detailed evidence in HANDOFF.md.
- Full Phase 1 Part D evidence preserved in `HANDOFF.md` Phase 1 Part D section.
OLD-CHANGE BLOCK (Phase 1 Part C, kept for reference):
- Phase 1 Part C COMPLETE + LIVE VERIFIED (2026-04-20 02:11); `🏪 მაღაზიების DNA` section added (ოზურგეთი Urban + დვაბზუ Rural); 54 new tests; 914/914 green; Backend restart #8 → PID 31176; Live dog-food 5/5 DNA markers (cross-store elasticity reasoning). Detailed evidence in HANDOFF.md.
- 🐞 Bug surfaced: scratch-script `$env:AI_ENABLE_THINKING="true"` MUST be set in launching shell before in-process `AIAgent.chat(think=True)`; otherwise `_resolve_thinking` silently degrades to False and deep cap 12 collapses to plain cap 6.
- Full Phase 1 Part C evidence preserved in `HANDOFF.md` Phase 1 Part C section. წინა ჭატის ცვლილებები (Phase 1 Part B) HANDOFF.md-ში.

backend live: parent-venv PID **18960** (Backend restart #16, 2026-04-21 02:30-ის შემდგომ after mid-session crash) on 127.0.0.1:8000 with `AI_ENABLE_THINKING=true` + `MAX_TOOL_ITERATIONS_DEEP=12` + `DEFAULT_TIMEOUT_S=120` + `TOOL_SCHEMAS=18` (Phase 3.5/3.7 `compute_cash_runway` at index 11 + Phase 4A `build_debt_repayment_plan` at index 12 + Phase 3.1 `propose_feature` at index 17). Phase 1 Part A + B + C + D + Phase 2.11 + Phase 2.12 + Phase 3.1 + Phase 3.5/3.7 + Phase 4A Part A + Part B all live in `SYSTEM_PROMPT_KA`; investigator prompt stays 0-marker-free for all Phase 1+ sections.
**⚠️ Windows venv verification rule**: NEVER rely on `Get-Process <pid> | Select Path` (always shows base Python on Windows); ALWAYS use `Get-CimInstance Win32_Process -Filter "ProcessId=X" | Select CommandLine` OR probe `sys.prefix` in-process.
**⚠️ NEW (Backend restart #10 do-not-touch)**: after any backend restart, verify env propagation via real `usage.thinking=true` in an SSE call, NOT just `Win32_Process.CommandLine` match. CommandLine only shows the executable path; the launching shell's env vars are invisible there. Intermediate PID 27700 caveat confirmed this (parent-venv CommandLine OK, but missing `AI_ENABLE_THINKING` → silent degrade).
**⚠️ In-process AIAgent think=True rule**: launch shell MUST have `$env:AI_ENABLE_THINKING="true"` set BEFORE spawning the script, otherwise `_resolve_thinking(True)` silently degrades to False → deep cap 12 collapses to plain cap 6 → strategic questions hit `max_iterations`.

verified facts only (carry forward):
- Waybill ground truth: Feb 27 2026 transport_start_date + default exclusions = 7,882.68 ₾ (20 rows); Feb 28 = 2,675.86 ₾ (11 rows)
- waybills[] row shape: date + transport_start_date + delivery_date + supplier + waybill_number + nominal_amount + status + type + effective_amount
- monthly_pnl shape: list of {month, objects: {ოზურგეთი, დვაბზუ, საერთო, გაუნაწილებელი}[pos_income/expenses/net], total: {pos_income/expenses/net}} — 44 rows (2022-06 → 2026-02)
- 🆕 TOOL_SCHEMAS length = **18** (Phase 4A): read_data_json, compute_waybill_total, compute, forecast_revenue, recall_context, save_memory, journal_add_entry, journal_list_entries, journal_update_entry, analyze_dead_stock, prepare_supplier_brief, compute_cash_runway, build_debt_repayment_plan, read_source_code, grep_code, read_excel_source, validate_vs_source, propose_feature
- 🆕 compute_cash_runway contract (Phase 3.7): {mode:"full"|"insufficient"|"profit", cash_balance_total_ge, balances:[{account, balance_ge}], burn_rate_ge, burn_trend:"stable|accelerating|decelerating|insufficient_history", runway_months, runway_label:"🟢 SAFE|🟡 WATCH|🔴 CRITICAL|🟢 PROFIT", notes[]} or {error, hint} — PULL-ONLY, requires user-provided balances
- 🆕 build_debt_repayment_plan contract (Phase 4A): {mode, plan_duration_months, priority_suppliers:[{name, debt_ge, criticality_score, criticality_factors:{debt/aging/frequency/dysfunction}, recommended_monthly_payment_ge, recommended_weekly_payment_ge, days_to_clear_est, confidence_label:"🟢🟡🔴", rationale_ka, days_since_last, amount_breakdown}], non_priority_summary:{baseline_monthly_ge, suppliers_count}, allocation_summary:{forecast_monthly_inflow_ge, priority_monthly_total_ge, non_priority_monthly_total_ge, sustainable:bool, gap_ge}, forecast_bracket:{low_ge, expected_ge, high_ge}, risks[], summary_ka, notes[], today, source} or {error, hint} — AUTONOMOUS; dormant suppliers (>365 days inactive) auto-quarantined unless user-named; weights: debt 0.50 + aging 0.15 + frequency 0.20 + dysfunction 0.15
- 🆕 prepare_supplier_brief contract (Phase 2.12 focused mode): {mode:"focused", supplier:{identity, match_confidence, match_source}, volume_snapshot:{total_spend_ge, portfolio_share_pct, monthly_avg, tenure_months, active_months, rank_among_active}, payment_profile:{billed_ge, paid_ge, debt_ge, unpaid_pct, reliability_label}, price_benchmark:{dual_source_rows:[{product, this_price, cheapest_alternative_price, gap_pct, suggested_action}], gap_pct_total, cheapest_alternative_name}, leverage_score:{total:0-100, band:"🟢 HIGH|🟡 MEDIUM|🟠 LOW", factors:{portfolio_share, payment_leverage, dual_sourcing, tenure, relationship_health}}, negotiation_plays:[{type, priority_label, ask_ka, give_ka, rationale_ka, evidence_refs:[], warning_ka}], matching_warnings:[], today, lookback_months}
- 🆕 prepare_supplier_brief contract (Phase 2.12 portfolio mode, no identifier): {mode:"portfolio", concentration:{top5_pct, top10_pct, top20_pct, hhi, label:"low|moderate|high"}, top_candidates:[{rank, supplier, spend_ge, share_pct, leverage_score, estimated_annual_savings_ge, primary_play_type}], total_suppliers, total_spend_ge, today, lookback_months} or {error, hint}
- SUPPORTED_STORES = ("total", "ოზურგეთი", "დვაბზუ"); _STORE_ALIASES accepts "ozurgeti"/"dvabzu"/"ჯამი" + empty→total
- forecast_revenue contract: {source, store, horizon_months, history_months, history_start, history_end, last_12_months_total, yoy_growth_pct, engines_used, forecast[{month, baseline, optimistic, pessimistic}], notes[]} or {error, hint}
- recall_context contract: {source, query, limit, result_count, results: [{id, rank, distance, summary, tags, source, created_at, collection, metadata}]} or {error, hint}
- save_memory contract: {ok, memory_id, stored_chars, tags, source, collection} or {error, hint}
- 🆕 JOURNAL_KINDS (Phase 4A) = ("promise", "ai_commitment", "recommendation", "reminder", "proposal", "repayment_plan"); JOURNAL_STATUSES = ("open", "done", "cancelled"); `PROPOSAL_AUTO_CLEANUP_DAYS=30` auto-janitor via `cleanup_stale_proposals()`; `tools.py::JOURNAL_KINDS` mirror-tuple must stay in sync with `journal.py` (Phase 4A Part B fix)
- 🆕 add_journal_entry(title: 3-500, kind, *, due_date: YYYY-MM-DD|None, tags, problem, benefit, mvp_scope, data_needed, time_estimate, risk_critique) → {ok, entry_id, title, kind, status, due_date, created_at, tags, proposal_payload?} or {error, hint}; when kind=='proposal' the 6 proposal fields are REQUIRED
- 🆕 propose_feature(title, problem, benefit, mvp_scope, data_needed, time_estimate, risk_critique) → {ok, entry_id, title, kind:"proposal", status:"open", created_at, proposal_payload:{problem, benefit, mvp_scope, data_needed, time_estimate, risk_critique}} — PULL-ONLY, only invoked on one of 6 trigger phrases
- 🆕 list_journal_entries(*, status?, kind?, overdue?, due_before?, due_after?, limit: 1-100=20, today?) → {count, entries: [...], today} or {error, hint} — entries sorted overdue (most-days first) → upcoming (earliest-due first) → rest (newest first)
- 🆕 update_journal_entry(entry_id, *, status) → {ok, entry_id, status, previous_status, tags} or {error, hint}; rejects non-journal rows via discriminator guard
- 🆕 `<TODAY>` block shows ⏳ ღია დაპირებები sub-section (overdue + 3 newest-open); suppressed entirely when empty; entry icons 4 kinds (🤝/🔍/💡/⏰) + 🚨 tag for overdue
- memory tool bounds: query ≤500 chars; summary 10-8000 chars; limit 1-50 (default 5); embedding model paraphrase-multilingual-MiniLM-L12-v2 (multilingual, ~120 MB HF cache); persist dir ai_vectors/ (gitignored line 42)
- 🆕 **ChromaDB 1.5.x range operator caveat**: `$lt`/`$gt`/`$lte`/`$gte` work ONLY on numeric metadata; on string metadata they silently return 0 rows; `$eq`/`$ne` work on any type. Journal date filtering is done in Python post-fetch (`_apply_python_date_filters`) — DO NOT revert to ChromaDB-side date comparisons until upstream adds string-range support.
- 🆕 **Windows venv Path check caveat**: `Get-Process Path` unreliable on Windows (venv stub shows base Python image); use `Win32_Process.CommandLine` or in-process `sys.prefix` / `importlib.util.find_spec` instead.
- forecast_revenue bounds: horizon_months 1..12 (default 3); MIN_HISTORY_MONTHS=12 hard-requires; pessimistic/baseline/optimistic clamped ≥ 0
- SUPPORTED_MODES = ("chat", "investigate"); DEFAULT_MODE = "chat"
- 🆕 `MAX_TOOL_ITERATIONS = 6` (plain chat default) + `MAX_TOOL_ITERATIONS_DEEP = 12` (Phase 1 Part A bumped from 10) + `AIAgent._resolve_max_iterations(*, mode, thinking_enabled)` helper; returns 12 when `think=True` OR `mode=="investigate"`, else 6; two switches don't compound
- 🆕 **Phase 1 Part A SYSTEM_PROMPT_KA sections** (chat mode only — investigator untouched): `🎯 როლის კონტრაქტი` / `🗺️ პროექტის რუკა` / `⚖️ წყაროების იერარქია` (Excel > data.json > ChromaDB > AI's head) / `🕵 Data-ზე სკეპტიციზმი` (manual_payments.csv freshness, rows_preview lag) / `🎭 5 ქუდი` (💼 ფინანსური / 🔧 ოპერაციული / 🎯 სტრატეგი / ⚠️ რისკის / 🪞 კრიტიკოსი) / `🎯 Confidence ნიშნები` (✅ 95%+ / 🟢 75-95% / 🟡 50-75% / 🟠 25-50% / ⚪ 0-25%; factual questions skip) / `📌 ვარაუდი vs ფაქტი` (anti-hallucination v2 — "ალბათ"/"დაახლოებით"/"ჩვეულებრივ" forbidden without 📌 mark + confidence label) / reinforced strict-tone (flattery + soft-pedaling forbidden)
- 🆕 Phase 1 Part A `today_context.py` additions: `_WEEKDAY_CONTEXT` 7-entry Georgian weekday hints (Mon "კვირის დასაწყისი" → Sat/Sun "weekend — retail peak"; rendered inline on `თარიღი: {ISO} ({weekday}) — {hint}` header line); `_FIXED_MONTHLY_DEADLINES = (("VAT დეკლარაცია (RS.ge)", 15), ("საპენსიო ფონდი", 15))`; `_upcoming_deadlines(today)` returns entries within 10-day horizon with severity buckets (`urgent` ≤3d / `approaching` ≤7d / `normal` ≤10d); rendered as `⏰ უახლოესი ვადები` block section with 🚨/⏰/📆 emoji prefix + "დღესვე / ხვალ / N დღეში" humanized suffix
- Phase 0B live metrics envelope (2026-04-19 23:15 scripted run): 7 `/api/chat` calls ≈ $0.25 / ≈2.4 min total; cache warm on calls 2–7 (~$0.013–$0.017 each); Sprint 1 Alpha strategic re-run after deep-cap fix: 155s / 8 tool calls / $0.186 / `stop_reason=end_turn`
- Anthropic models: Sonnet 4.6 primary, Haiku 4.5 fallback; prompt caching active on system + tools prefix; mode-namespaced cache
- Extended Thinking contract: temperature=1.0 forced + max_tokens ≥ budget + 1024 + thinking={"type":"enabled","budget_tokens":N}; deployment gate config.enable_thinking is authoritative
- Live forecast baselines (smoke test, not ground truth): Total 134,944 / 141,994 / 147,679 ₾ (2026-03/04/05 baseline); YoY Total +18.2%, Ozurgeti -12.47%, Dvabzu +45.14%
- Prophet wall-clock: 9.17s cold (cmdstan), ~1.2s warm
- data.json size ~135.84 MB; 26 API artifacts; waybills[] 21,233 rows
- Parent venv pins: pandas 3.0.2, openpyxl 3.1.5, fastapi 0.135.3, uvicorn 0.44.0, anthropic 0.96.0, python-dotenv 1.2.2, pytest 9.0.3, prophet 1.3.0, statsmodels 0.14.6, scipy 1.17.1, matplotlib 3.10.8, cmdstanpy 1.3.0, holidays 0.94; 🆕 chromadb 1.5.8, sentence-transformers 5.4.1, torch 2.11.0, transformers 5.5.4, huggingface-hub 1.11.0
- localStorage keys: "ai-advisor-mode" (chat/investigate) + "ai-advisor-think" (true/false)

do-not-touch rules:
- `.env`: NEVER commit, echo, or overwrite; gitignored; secrets stored in ../claude_key.txt + ../telegram_token.txt outside workspace
- project-local .venv for backend: prohibited (use parent venv)
- cashflow tab period-aware refactor: documented intentional exception; do not attempt
- broad refactor / unrelated code edits: prohibited
- TOOL_SCHEMAS module constant must stay cache-control-free (annotate only via get_cached_tool_schemas deep-copy)
- SYSTEM_PROMPT_KA_INVESTIGATOR (investigator prompt): untouched through Sprint 1, 2 AND 3 — all sprints live in SYSTEM_PROMPT_KA chat mode only
- today_context block: non-cached by design (second system block); never add cache_control to it
- analytics_builders.py::build_supplier_aging + build_ap_monthly_trend still use `გააქტიურების თარ.` — changing requires explicit user sign-off
- tests: never delete or weaken without explicit user direction
- ping_anthropic.py + ping_telegram.py: keep at root (reusable health-checks)
- API keys / tokens: NEVER accept from chat paste, NEVER print
- _safe_round_nonneg clamp (≥0) is part of forecast contract — tests pin it; don't revert to plain _safe_round
- Prophet + statsmodels lazy-imported in forecasting.py — if wheel breaks, forecast_revenue returns Georgian error + pip install hint; rest of pipeline keeps working
- 🆕 chromadb + sentence-transformers lazy-imported in memory.py — if wheel breaks, recall_context/save_memory return Georgian error + pip install hint; rest of pipeline keeps working
- 🆕 ai_vectors/ persist dir is gitignored (.gitignore line 42); HF embedding model cache lives outside repo (~/.cache/huggingface/) — no risk of vector store / model bloat in git
- 🆕 Latin alias guidance in SYSTEM_PROMPT_KA memory section + `_FOLDER_LATIN_HINTS` map in memory.py are paired — DO NOT remove one without the other; pure Georgian query-only path loses BOG/TBC/RS distinguishability on multilingual MiniLM
- 🆕 Re-indexing is required (`python index_project_files.py --replace`) after any edit to `_build_chunk_header` or `_FOLDER_LATIN_HINTS`; old headers don't auto-migrate
- `path_token` in `index_project_files()` MUST stay unicode-safe (`hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]`) — reverting to any ASCII-only regex (`[^a-z0-9]+`) silently collapses every Georgian folder into the same token and causes `upsert()` to overwrite chunks across different files
- 🆕 **Sprint 4** journal metadata keys (`journal_entry_type="journal"` discriminator + `journal_kind` + `journal_status` + `journal_due_date` + `journal_title`) are part of the stored contract; renaming them orphans every existing journal row
- 🆕 **Sprint 4** `MemoryStore.get_entries` / `update_metadata` / `delete_entry` must fail softly (return None/False/[] on error, never raise) — `today_context._collect_open_promises` assumes silent fail contract
- 🆕 **Sprint 4** `update_journal_entry` requires the discriminator guard (`journal_entry_type == "journal"`) to prevent status stamping plain save_memory rows — do not remove
- 🆕 **Sprint 4** `journal.py::_build_journal_where` MUST emit only `$eq`/`$ne` clauses — NEVER re-introduce `$lt`/`$gt` on `journal_due_date` (ChromaDB 1.5.x limitation); date filters live in `_apply_python_date_filters` (Python post-fetch)
- 🆕 **Sprint 4** `_apply_python_date_filters` `overdue=True` branch guard `isinstance(overdue_days, int) and overdue_days > 0` must stay — undated entries must never match overdue
- 🆕 **Phase 1 Part A** chat-mode persona marker `"🎯 როლის კონტრაქტი"` is the new durable chat-vs-investigator anchor — 5 existing tests depend on it. Don't remove or rename without updating `test_ai_agent.py` + `test_ai_today_context.py` assertions.
- 🆕 **Phase 1 Part A** `SYSTEM_PROMPT_KA` 🎭 5-hats table must preserve all 5 icons `💼/🔧/🎯/⚠️/🪞` + Georgian labels — prompt tests pin each icon+label pair.
- 🆕 **Phase 1 Part A** `SYSTEM_PROMPT_KA_INVESTIGATOR` **must stay Phase-1-free** — the do-not-touch rule from Sprint 1/2/3/4 now covers Phase 1 Part A too; tests assert `🎯 როლის კონტრაქტი` + `🎭 5 ქუდი` + `outcome-based` absent from investigator prompt.
- 🆕 **Phase 1 Part A** `_FIXED_MONTHLY_DEADLINES` intentionally ships only VAT + საპენსიო (universal for any Georgian legal entity). Franchise royalty / income tax / property tax dates are contract-specific and must live in the user's `journal_add_entry` workflow — do not add them to this hard-coded list.
- 🆕 **Phase 1 Part A** `_DEADLINE_HORIZON_DAYS = 10` is the upper bound for the `⏰ უახლოესი ვადები` block; going above ~14 starts shoveling noise onto every chat's `<TODAY>` header.
- 🆕 **Phase 1 Part A** `MAX_TOOL_ITERATIONS_DEEP = 12` ceiling — raising above ~14 not validated for tool-use cost (Phase 0B Sprint 4 observed ~$0.19 per strategic Alpha turn at 8-10 tools; 14+ tools routinely would push cost over $0.30/turn).
- 🆕 **Phase 1 Part A** `DEFAULT_TIMEOUT_S` must stay **≥ 120 s** (`dashboard_pipeline/ai/agent.py:47`). The heavier Phase 1 Part A prompt + Extended Thinking + Prophet cold-start can push a single Anthropic `messages.create` call to 40-80 s; reverting below 120 s re-opens the SDK auto-retry-loop failure mode that caused a ~10-minute server lock on 2026-04-20.
- **Phase 1 Part B** `SYSTEM_PROMPT_KA`-ში `🇬🇪 ქართული რეგულაცია` სექცია უნდა დარჩეს `🗺️ პროექტის რუკა`-ს შემდეგ და `⚖️ წყაროების იერარქია`-ს წინ — ტესტები pin-უნდა ამ ტოპოლოგიას (`test_ai_prompts_phase1b.py::TestGeorgianRegulationSection::test_section_placed_after_project_map_before_source_hierarchy`). ტაქს-ინტანგიბი `topic:franchise` + `topic:tax` + `kind:reminder` baseline facts-ისთვის დამაცვითებულია.
- **Phase 1 Part B** `Baseline facts` 4 მექანიზმი (Royalty % / Sourcing % / income tax status / VAT registration status) — journal-ში უნდა ინახებოდეს, `SYSTEM_PROMPT_KA`-ში hardcoded კონკრეტული რიცხვი არა.
- 🆕 **Phase 1 Part C** `SYSTEM_PROMPT_KA`-ში `🏪 მაღაზიების DNA` სექცია უნდა დარჩეს `🌅 ქართული თვის რიტმი`-ს შემდეგ და `⚖️ წყაროების იერარქია`-ს წინ — ტოპოლოგიური pin `test_ai_prompts_phase1c.py::TestMultiStoreDnaSection::test_section_placed_after_monthly_rhythm_before_source_hierarchy`. მაღაზიების DNA 7 დიმენსია — დამაცვითებული `TestOzurgetiDna` (7) + `TestDvabzuDna` (7) — `3 ტერმინალი` / `2 ტერმინალი` / `12-საათიანი` / `8-საათიანი` / `20:00-22:00` / `10 + 25` (payday) / `Fast & high pass-through` / `Slow & low pass-through` literal strings must stay.
- 🆕 **Phase 1 Part C** Generic DNA numbers (traffic 2-3×, ratio 50-60%, peak 20-22) stay marked as `📌 ვარაუდი`; user-specific numbers saved via `journal_add_entry(kind="reminder", tags=["topic:store_dna"])` upgrade confidence to `🟢 საიმედო` at read-time.
- 🆕 **Phase 1 Part C** Seasonality stays **soft hint** (`soft hint` keyword + `forecast_revenue(store=...)` deferral); NEVER hardcode precise tourist-season months — 2026’s reality may diverge from 2024-2025 pattern (flight routes, kurort openings, macro shifts).
- 🆕 **Phase 1 Part C** Investigator prompt must stay 15 Part C markers-free (6 do-not-touch tests pin it).
- 🆕 **Phase 1 Part C** DNA over-apply guardrails — 3 simple-lookup counter-examples (`რამდენი მომწოდებელია?` / `POS income` / `2026-02-27 ზედნადები`) must remain so AI skips DNA essays on pure data lookups.
- 🆕 **Phase 2.11** `analyze_dead_stock` bucket thresholds (`active` <91d / `slow_91_180` / `slow_181_365` / `dead_365_plus`) and `recommended_action` mapping (`discount_15` / `discount_30` / `supplier_return` / `write_off`) are pinned by module tests — changing thresholds orphans tests.
- 🆕 **Phase 2.12** `dashboard_pipeline/ai/supplier_brief.py::_normalize_name` MUST call `text.lstrip()` BEFORE `_LEGAL_PREFIX_RE.sub(...)`; reverting the ordering re-opens the `( 123-დღგ ) შპს X` → `' შპს X'` → prefix-not-stripped bug that silently collapses every exact match to substring/partial.
- 🆕 **Phase 2.12** `LEVERAGE_WEIGHTS = {portfolio_share: 30, payment_leverage: 20, dual_sourcing: 20, tenure: 15, relationship_health: 15}` sums to 100; tests pin each weight. Bands 🟢 HIGH ≥70 / 🟡 MEDIUM ≥40 / 🟠 LOW <40 are also pinned.
- 🆕 **Phase 2.12** Negotiation plays 1+2+3 stay in `TOP_NEGOTIATION_PLAYS` sorted by priority. `#3 dual_source_leverage` MUST require both `dual_source_row` AND `more_expensive=True` AND `comparable_product`; loosening this re-opens the relationship-damage risk the prompt section warns about.
- 🆕 **Phase 2.12** `SYSTEM_PROMPT_KA` 📞 section must stay between 💀 Dead Stock and 🔄 Self-Correction; topology pin `test_ai_prompts_phase2_12.py::TestSupplierNegotiationSection::test_section_placed_after_dead_stock_before_self_correction`.
- 🆕 **Phase 2.12** `SYSTEM_PROMPT_KA_INVESTIGATOR` must stay **15 Phase 2.12 markers absent** (pinned by `TestInvestigatorPromptUntouched::test_fifteen_phase_2_12_markers_all_absent` — no `prepare_supplier_brief`, no `📞`, no `🪪 Identity Confidence Protocol`, etc.).
- 🆕 **Phase 2.12** Identity Confidence Protocol — `match_confidence=medium` or `low` MUST prompt user for confirmation BEFORE quoting figures; removing the "არასოდეს ნუ გადახვალ პირდაპირ ციფრებზე" phrase collapses the user-confirmation gate.

pytest baseline: 381 → 458 (+77) → 548 (+80) → 633 (+85) → 742 (+109) → 743 (+1 chromadb fix) → 752 (+9 deep-cap) → 818 (+66 Phase 1 Part A) → 860 (+42 Phase 1 Part B) → 914 (+54 Phase 1 Part C) → 969 (+55 Phase 1 Part D) → 976 (+7 Excel-Path-Fix) → 1033 (+57 Phase 2.11) → 1109 (+76 Phase 2.12 module) → 1163 (+54 Phase 2.12 prompt-guard) → 1242 (+79 Phase 3.1 Co-Designer) → 1303 (+61 Phase 3.7 Cash Runway) → 1393 (+90 Phase 4A Part A debt plan) → 1433 (+40 Phase 4A Part B endpoints/journal sync) → **1443** (+10 Phase 4A Part B bug-fix: 4 schema + 6 ranking); 0 tests weakened throughout.

next recommended step (user choice):
- **Option A — Phase 4A closure** (finish what was left mid-session): (1) UI click-through რომ ცხოვრობს Playwright-ით `#debt_plan` — approve ღილაკი → POST `/api/debt-plan/save` → journal `entry_id` დაბრუნდება; (2) regenerate ღილაკის ქცევის ტესტი სხვა duration/priority-ით; (3) optional `/api/chat/stream` dog-food (`"შემიდგინე ვალების გეგმა"` → AI calls `build_debt_repayment_plan` → ცოცხალი pipeline + brief); (4) `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B section with LIVE VERIFIED banner.
- **Option B — Phase 5 / Phase 4B kickoff** per `AI_GENIUS_PARTNER_PLAN.md` v2.1. Candidates: Web Search integration (CB rate / competitor intel) / Sub-agent Debate / Proactive anomaly surface / RAG re-indexing with e5-large embeddings.
- **Option C — Parking-lot polish** (not blocking):
  - `python index_project_files.py --full --replace` overnight pass for complete historical coverage
  - `intfloat/multilingual-e5-large` embedding upgrade (removes Latin-alias MANDATORY rule)
  - Dashboard UI surface for decision journal (currently chat-only)
  - Playwright full E2E suite re-run (last green 2026-04-18; regression check recommended before Phase 5 UI work)
- **Option D — Real-user dog-food expansion** — run Phase 4A on user-phrased Georgian strategic questions; verify autonomy + critic + multi-hypothesis still land correctly under the new debt-plan tool.

verification pending (not run this session):
- ✅ Phase 1 Part A/B/C/D + Phase 0B closure — DONE previous sessions
- ✅ Excel Georgian Path Fix code + tests + LIVE — DONE (2026-04-20 12:45); pytest 976/976 green
- ✅ Phase 2.11 Dead Stock + Phase 2.12 Supplier Brief code + LIVE — DONE (2026-04-20 15:30); pytest 1163/1163 green
- ✅ Phase 3.1 Co-Designer Mode code + LIVE — DONE (2026-04-20 17:50); pytest 1242/1242 green; 3/3 trigger/anti-trigger live dog-foods PASS
- ✅ Phase 3.5/3.7 Dead Stock page + Supplier Concentration widget + `compute_cash_runway` tool + LIVE — DONE (2026-04-20 23:50); pytest 1303/1303 green; live dog-food 6/6 PASS (3.2-თვე runway)
- ✅ Phase 4A Debt Repayment Plan Part A (backend tool + prompt + endpoints) + LIVE — DONE (2026-04-21 00:50); pytest 1393/1393 green; live 12/12 PASS
- ✅ Phase 4A Part B React page + journal mirror sync + endpoint tests + 2 BUG-FIX + UI click-through — DONE (2026-04-21 02:35); pytest **1443/1443 green** (+10: 4 schema + 6 ranking); ჯიდიაი #1 score 0.585 (was #30)
- ✅ Backend restart #16 — DONE (2026-04-21 02:30-ის შემდგომ after mid-session crash); PID 18960 live, `TOOL_SCHEMAS=18`, `/api/status` 200
- 🟡 **Phase 4A Part B — LIVE UI approve/save + regenerate button smoke** — **PENDING** (backend crash interrupted; next chat to run Playwright click-through on approve → `/api/debt-plan/save` → journal `entry_id` flow, plus regenerate with different duration/priority combo)
- 🟡 **Phase 4A — `/api/chat/stream` dog-food** — **PENDING** (user asks AI `"შემიდგინე ვალების გეგმა"` → AI calls `build_debt_repayment_plan` on real `data.json` + summarises)
- 🟡 **Phase 4A — `PHASE_4A_DEBT_PLAN_PREVIEW.md` Part B section with LIVE VERIFIED banner** — **PENDING**
- 🔴 Phase 5 / Phase 4B kickoff — not yet started (user should pick direction from `AI_GENIUS_PARTNER_PLAN.md` v2.1)
- 🔴 Playwright full E2E suite — not executed recently (last green 2026-04-18 02:00; regression check recommended before Phase 5 UI work)
- 🔴 🧠 Deep Think toggle E2E — not added (Sprint 1 carry-over; deferred)
- 🔴 `--full --replace` overnight indexing pass — parking-lot
- 🔴 Dashboard UI surface for decision journal — parking-lot (Phase 3.4 in v2.1 plan; chat-only today)
- ✅ Real-world user dog-food of Phase 2.11/2.12 (not scripted) — DONE (2026-04-20 15:54); 88.7s / 7 tool calls / usage.thinking=true / ~$0.20

authoritative files:
- PLAN.md (Phase 4A Part A + Part B COMPLETE blocks, updated this session)
- root AGENTS.md (plain ქართული communication rule — CRITICAL)
- CONTEXT_HANDOFF.md (this canonical short brief, updated this session)
- AI_GENIUS_PARTNER_PLAN.md v2.1 (active master plan)
- PHASE_1_PART_A/B/C/D_PREVIEW.md (all ✅ COMPLETE banners)
- PHASE_4A_DEBT_PLAN_PREVIEW.md (Part A + Part B live; Part B LIVE VERIFIED banner update still pending)
- HANDOFF.md (slim banner + all closures)
- HANDOFF_ARCHIVE/2026-04-packet-h.md (Packet H archive)
- Backend AI module: config.py, agent.py (deep-cap 12 + timeout 120), prompts.py (Phase 1 Part A+B+C+D + Phase 2.11 💀 + Phase 2.12 📞 + Phase 3.1 🎨 + Phase 3.7 💰 + Phase 4A 📋 sections), tools.py (**TOOL_SCHEMAS=18**), forecasting.py, memory.py, today_context.py, journal.py, supplier_brief.py (Phase 2.12), dead_stock.py (Phase 2.11), **🆕 debt_plan.py (Phase 4A Part A — ~620 lines; list+dict schema + dormant quarantine + rebalanced weights)**
- Server: server.py (+ POST `/api/debt-plan` + POST `/api/debt-plan/save` endpoints)
- Frontend: `rs-dashboard/src/DebtPlan.jsx` (**🆕 Phase 4A Part B — ~600 lines** auto-generate + 3-card + priority table + approve/regen), `rs-dashboard/src/tabConfig.js` (`debt_plan` tab in ანალიტიკური group), `rs-dashboard/src/App.jsx` (lazy import + fetch exclusion)
- Tests: test_ai_prompts_phase1.py (66) + _phase1b.py (42) + _phase1c.py (54) + _phase1d.py (55) + _phase2_12.py (54), test_ai_journal.py (109), test_ai_agent.py (+9 TestDeepIterationCap), test_ai_dead_stock.py (Phase 2.11), test_ai_supplier_brief.py (76 Phase 2.12), test_ai_co_designer.py (78 Phase 3.1), test_ai_cash_runway.py (61 Phase 3.7), **🆕 test_ai_debt_plan.py (90 Phase 4A Part A)**, **🆕 test_api_debt_plan.py (39 Phase 4A Part B)**, 10+ other files — **1443 total green**

communication rules (CRITICAL):
- plain ქართული; user არ არის პროგრამისტი
- technical jargon → მაგალითი + ახსნა, მერე (optional) სახელი
- ცხრილი / bullet list / emoji — თვალსაჩინოდ
- კოდის block-ი მხოლოდ თუ user თვითონ იხსენია ან business-value ცხადი diff
- ask_user_question widget — არასოდეს multi-choice; user ნელა კითხულობს
- API keys / tokens: NEVER paste request in chat
- მოქმედებამდე `გააგრძელო? (კი / არა)` — ახსნის გარეშე
- session progress narration — გაურბოდე; მხოლოდ blockers + questions + final summary
- "გასწორებელი პროცესში → მაშინვე გააკეთე, არ გადადო"
```
