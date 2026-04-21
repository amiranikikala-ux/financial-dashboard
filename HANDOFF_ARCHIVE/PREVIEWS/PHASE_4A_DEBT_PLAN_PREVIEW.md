# Phase 4A — Debt Repayment Plan (Autonomous Strategist)

> **თარიღი:** 2026-04-21
> **სტატუსი:** 🎉 **Part A + Part B COMPLETE + LIVE VERIFIED** (Part B verified 2026-04-21 04:02)
> **Parent paradigm:** Phase 4 "Autonomous Strategic Advisor" — AI proposes first, user approves/edits
> **pytest:** 1443/1443 green (+100 across `test_ai_debt_plan.py` / `test_api_debt_plan.py`)
> **Backend:** restart #17 PID **5388**, `TOOL_SCHEMAS=18`, `AI_ENABLE_THINKING=true`
> **Live verify (Part A):** 12/12 chat dog-food smoke checks PASS across 3 scenarios (broad / named / anti-trigger)
> **Live verify (Part B):** UI click-through — regenerate (2→6 თვე) + approve (`/api/debt-plan/save` → journal `journal_816295fd222b495199c30599510d8d7f`) + `/api/chat/stream` dog-food autonomous tool call all PASS

---

## 🎯 What this ships

### 1. New AI tool — `build_debt_repayment_plan`

**AUTONOMOUS strategist tool.** Given data.json alone (no mandatory user input), composes a 1-2 month debt repayment plan covering 3-5 auto-detected critical suppliers + historical baseline minimums for the rest. Designed per Phase 4 philosophy: **AI proposes first, user approves or edits — never "ask first"**.

**Input (all optional):**

- `priority_suppliers: string[]` — optional list of names/tax_ids to force. OMIT for AI auto-detection.
- `plan_duration_months: int` — 1-6, default 2
- `max_priority_count: int` — 2-8, default 5

**Output shape:**

```json
{
  "as_of_date": "2026-04-21",
  "plan_duration_months": 2,
  "forecast": {
    "monthly_inflow_ge": 142000,
    "low_ge": 128000, "high_ge": 156000,
    "trend": "stable | growing | declining | insufficient_history",
    "method": "3-month moving average (2026-01 → 2026-03)",
    "window_months": ["2026-01", "2026-02", "2026-03"]
  },
  "priority_suppliers": [
    {
      "tax_id": "406181616", "org": "შპს ჯიდიაი",
      "total_debt_ge": 313000, "days_since_last": 6,
      "criticality_score": 0.78,
      "criticality_reasons": ["დიდი ვალი (313,000 ₾)", "ხშირი მიწოდება (5.0/თვე)"],
      "historical_monthly_paid_ge": 25700,
      "recommended_monthly_payment_ge": 46_300,
      "recommended_weekly_payment_ge": 11_500,
      "days_to_clear_est": 42,
      "confidence_label": "🟢 მაღალი",
      "rationale_ka": "..."
    }
  ],
  "non_priority_summary": {
    "supplier_count": 265,
    "total_baseline_monthly_ge": 92000,
    "average_per_supplier_ge": 347,
    "note_ka": "..."
  },
  "allocation_summary": {
    "priority_monthly_ge": 28400,
    "non_priority_monthly_ge": 92000,
    "buffer_ge": 21600, "buffer_pct": 15.2,
    "forecast_ge": 142000,
    "sustainable": true
  },
  "risks": ["..."],
  "summary_ka": "...",
  "notes": ["..."]
}
```

### 2. Criticality ranking formula (4-factor weighted)

| ფაქტორი | წონა | წყარო |
|---|---|---|
| ვალის ოდენობა | 30% | `supplier_aging.total_debt` |
| ვალის ასაკი | 25% | `supplier_aging.days_since_last` |
| მიწოდების სიხშირე | 25% | `waybill_count / active_months` |
| გადახდის დისფუნქცია | 20% | `1 - (total_paid / total_effective)` |

ყოველი ფაქტორი ნორმირდება peer-maximum-ით; ტოპ-N ირჩევა by score desc.

### 3. Payment recommendation logic

```
boost = 1.20 + (1.80 - 1.20) × criticality_score    # 1.2-1.8 scaling
base = historical_monthly_paid × boost
required = total_debt / plan_duration_months
recommended = max(base, required, 1000 ₾ floor)     # floor protects new suppliers
recommended = round(recommended / 100) × 100        # clean numbers
weekly = round(recommended / 4 / 50) × 50           # round to 50 ₾
```

### 4. Non-priority baseline

ყოველი არაპრიორიტეტული მომწოდებლისთვის: `historical_monthly_paid × 0.9` = baseline floor. **Rationale:** გაჩერების რისკი ამ ტემპზე ისტორიულად არ ყოფილა — 10% cushion-ი უსაფრთხო ზონა.

### 5. System prompt section `📋 ვალების გეგმა` (Phase 4A)

Chat prompt gained a new section with:
- **AUTONOMOUS STRATEGIST** label — opposite of Co-Designer's PULL-ONLY pattern
- **BROAD triggers** — even vague debt references count
- **IMMEDIATELY call** workflow — no "ask first" mandate
- **5-part response format** (priority table + rationale per supplier + allocation + risks + call-to-action)
- **🪞 Critic's hat** mandate for every plan
- **Anti-triggers** — route single-supplier / HHI / cash-runway to existing specialized tools
- **Cross-tool chain** suggestions (analyze_dead_stock / compute_cash_runway / prepare_supplier_brief follow-ups)

**Investigator prompt** — 0/7 markers absent (do-not-touch rule holds).

---

## 🧪 Tests (90 new)

`tests/test_ai_debt_plan.py`:

| Class | # tests | Coverage |
|---|---|---|
| `TestClampInt` | 6 | argument coercion |
| `TestConstants` | 2 | criticality weights sum to 1.0, bounds |
| `TestInflowForecast` | 5 | series extraction, ±10% bracket, window |
| `TestInflowTrend` | 4 | stable / growing / declining / insufficient |
| `TestSupplierHelpers` | 8 | active months, monthly_paid, frequency, dysfunction |
| `TestNormalizeSeries` | 3 | nonempty / all-zero / empty |
| `TestCriticalityScoring` | 4 | ranking + reasons + aging surfaces |
| `TestResolvePriority` | 6 | tax_id / name fragment / ambiguity / empty |
| `TestRecommendPriorityPayment` | 5 | debt÷duration / boost / floor / rounding |
| `TestConfidence` | 3 | HIGH/MID/LOW based on active months |
| `TestBuildPlanAutoDetect` | 7 | end-to-end auto path + shape checks |
| `TestBuildPlanUserSpecified` | 4 | user-provided priority + ambiguous return |
| `TestBuildPlanFailures` | 5 | no debt / no pnl / short pnl / bad today / loader err |
| `TestRiskFlags` | 2 | unsustainable / stale supplier |
| `TestDebtPlanToolSchema` | 7 | registered / count / position / shape / mentions |
| `TestDebtPlanDispatch` | 2 | happy path + user priority |
| `TestDebtPlanPromptChat` | 9 | section header / philosophy / triggers / format / critic / anti / cross-tool / guardrail |
| `TestDebtPlanPromptInvestigatorUntouched` | 7 | parametrized marker absence |

---

## 🔬 Live verification (2026-04-21 00:45)

3 scenarios on backend #13 PID 10800:

### A / Broad trigger (no suppliers named)
> *"მინდა ვალების გეგმა შევადგინოთ. ვის რამდენი გადავუხადო რომ სხვა კომპანიები არ გააჩერდეს?"*

- ✅ AI called `build_debt_repayment_plan` with **empty** `priority_suppliers` → tool auto-detected top-5
- ✅ Structured Georgian plan response: forecast inflow (~129,662 ₾ from last 2 months), burn warning, priority allocation
- ✅ `usage.thinking=true`, `stop_reason=end_turn`

### B / Named priorities
> *"ვასაძეს 12,000 ₾ და კოკაკოლას 18,000 ₾ ვალი მაქვს. გეგმა გააკეთე რომ ორივე მოვრიგდე 2 თვეში."*

- ✅ AI's FIRST tool call: `build_debt_repayment_plan(priority_suppliers=["ვასაძე", "კოკაკოლა"], plan_duration_months=2)` — **pure Phase 4 behavior**
- ✅ 14 tools total — AI then verified user's numbers against data.json and **surfaced discrepancy**: "შენ კი ამბობ 12,000 ₾ და 18,000 ₾. data.json-ში ჩანს 10,977 ₾ / 13,825 ₾" — honest advisor pattern
- ✅ `usage.thinking=true`, 103s, `stop_reason=end_turn`

### C / Anti-trigger (single-supplier leverage)
> *"ჯიდიაი მომწოდებლის leverage deep-dive გინდა."*

- ✅ AI correctly routed to `prepare_supplier_brief(supplier_name="ჯიდიაი")` — **NOT** debt plan
- ✅ Returned full Phase 2.12 Leverage 🟢 71/100 brief with 3 negotiation plays
- ✅ `usage.thinking=true`, 42.9s, `stop_reason=end_turn`

**Total: 12/12 smoke checks PASS** across all 3 scenarios.

---

## 🎉 Part B — COMPLETE + LIVE VERIFIED (2026-04-21 04:02)

React dashboard page `📋 ვალების გეგმა` + server endpoints + journal integration — all ცოცხლად ვერიფიცირებული backend #17 PID 5388-ზე.

### Delivered surface

- **React page** `rs-dashboard/src/DebtPlan.jsx` (~600 lines) under `ანალიტიკური` tab group
- **Auto-generation on mount** — calls `POST /api/debt-plan` (direct non-AI endpoint that invokes `build_debt_repayment_plan`)
- **Controls:** `ხანგრძლივობა` dropdown (1/2/3/4/6 თვე) + `პრიორიტეტი` dropdown (Top-3/4/5/6/8) + `🔄 ახალი გეგმა` regenerate button
- **5-zone layout:**
  1. Forecast card (GEL 140,379 ±10% bracket + trend indicator 📉 declining)
  2. Allocation summary card (🔴/🟢 sustainable flag + buffer amount/%)
  3. Non-priority summary card (supplier count + baseline + per-supplier average + safety note)
  4. Risks list (dedicated ⚠️/🔴/📉 rendering)
  5. Priority table (rank / name / debt / historical / recommended / weekly / days-to-clear / confidence)
- **Action buttons:** `✅ ვეთანხმები — შენახვა` (POST `/api/debt-plan/save` → new journal entry) + `🔄 სხვა ვერსია` (regenerate with different params)
- **Journal kind `repayment_plan`** added to `JOURNAL_KINDS` 6-tuple in `journal.py` + mirrored in `tools.py`
- **Server endpoints:**
  - `POST /api/debt-plan` — direct tool invocation; returns full plan JSON
  - `POST /api/debt-plan/save` — persists approved plan as journal entry (returns `entry_id`)

### 🔬 Live verification (2026-04-21 04:02)

**Backend:** restart #17 PID 5388 parent-venv, `/api/status` 200 OK, `TOOL_SCHEMAS=18` (verified `idx 12=build_debt_repayment_plan`, `idx 17=propose_feature`).

**Test 1 — Scripted `/api/chat/stream` autonomous tool call:**
- Query: *"შემიდგინე ვალების გეგმა"* (`mode=chat`, `think=true`)
- Elapsed: 91.2s
- Tool calls: 1 × `build_debt_repayment_plan` at 49.7s (auto-detected priorities, 0 user args)
- `usage.thinking=true` ✅ (Extended Thinking env propagated)
- `stop_reason=end_turn` ✅
- Response: full 5-section Georgian strategic brief — ჯიდიაი #1 313,922 ₾, 2-თვიანი გეგმა arithmetically unsustainable (246K needed vs 140K forecast), relationship risk flags for 314/264/161-day missed-delivery suppliers, recommendation to extend to 4-6 თვე horizon
- Tokens: 3,946 in + 2,887 out + 81,046 cache_create

**Test 2 — UI regenerate click-through (Vite dev 5173 + Playwright MCP):**
- Initial load `#debt_plan` → **🐞 bug surfaced:** `App.jsx` kept `loading=true` forever because `debt_plan` was excluded from the main `/api/data` fetch but missing from `showGlobalLoading` exclusion list
- **Fix:** `App.jsx:307` — `showGlobalLoading` gained `&& activeTab !== 'debt_plan'` guard (1-line root-cause fix; same pattern as `insights`/`imported_products`/`waybills`)
- Post-fix reload → auto-generation rendered in <3s: 3 cards + 6 risks + 5-row priority table
- Changed duration 2→6 → clicked `🔄 ახალი გეგმა` → re-rendered with new figures (85,700 ₾/თვე priority vs 246,000 ₾/თვე before; buffer improved from −139.2% → −25.0%)

**Test 3 — UI approve click-through:**
- Clicked `✅ ვეთანხმები — შენახვა`
- `POST /api/debt-plan/save` → **200 OK**
- Button morphed to `✅ შენახულია ჟურნალში` [disabled]
- Journal entry persisted: `journal_816295fd222b495199c30599510d8d7f`, title *"ვალების გეგმა — 5 priority @ GEL 85,700/თვე (6-თვიანი)"*, status `🟡 open`
- Separately verified via `/api/chat` query *"ვნახე ბოლო repayment_plan journal entry"* → AI called `journal_list_entries` → returned exact same entry ID/title/status

### 🐞 Bug-fix en-route

- **`App.jsx:307` — `showGlobalLoading` missed `debt_plan`:** `loading` state defaults to `true` and is flipped to `false` only by the main `/api/data` useEffect, which early-returns for `debt_plan`. Without adding `debt_plan` to the render-gate exclusion, UI was stuck on "იტვირთება მონაცემები..." forever. Same pattern applies to `insights` / `imported_products` / `waybills` which already had exclusions.

### 🧹 Cleanup

- Scratch dog-food script `_scratch_dogfood_phase4a.py` + log deleted post-run.

---

Part A + Part B both ready for production use. Next recommended: Phase 4B / Phase 5 kickoff per `AI_GENIUS_PARTNER_PLAN.md` v2.1, or parking-lot polish items.
