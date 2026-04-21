# Phase 3.5 + 3.7 + Cash Runway — Dashboard Widgets + AI Tool Packet

> **თარიღი:** 2026-04-20  
> **სტატუსი:** ✅ **COMPLETE + LIVE VERIFIED** (2026-04-20 23:45)  
> **Scope:** 3 ახალი ნაწილი — 2 Dashboard UI + 1 AI chat tool  
> **Parent packet:** Phase 3 — Co-Designer + Memory  
> **pytest:** 1303/1303 green (+61 new in `test_ai_cash_runway.py`)  
> **Backend:** restart #12 PID 20876, `TOOL_SCHEMAS=17`, `AI_ENABLE_THINKING=true`  
> **Live verify:** `/api/data?tab=dead_stock` ✅ + `/api/data?tab=supplier_concentration` ✅ + chat dog-food 6/6 PASS (compute_cash_runway called, usage.thinking=true, 57.1s, real AI brief with 3.2-თვე runway + multi-hypothesis + DNA + 🪞 critic self-critique)

---

## 🎯 რა კეთდება

### Part A — 💀 Dead Stock გვერდი (Phase 3.7)

**რას აკეთებს:** ახალი "ანალიტიკური" ტაბი Dashboard-ში — **"💀 Dead Stock"** — რომელიც აჩვენებს:

- **🎯 Top-30 გაყინული SKU** — პროდუქტის სახელი, მომწოდებელი, გაყინული ₾, ბოლო გაყიდვის დღე, რეკომენდებული action (🟢 discount_15 / 🟡 discount_30 / 🟢 supplier_return / 🔴 write_off)
- **📊 3-bucket donut** — 181-365 დღე vs 365+ დღე vs unmatched
- **💰 4-action salvage plan** — თითო action-ზე SKU რაოდ. + მოსალოდნელი გათავისუფლებული ₾
- **⚠️ 30% unmatched warning** — თუ barcode drift ≥ 30%, ზედა შეფასების გაფრთხილება

**მონაცემის წყარო:** `analyze_dead_stock()` — უკვე არსებული AI tool (Phase 2.11); pre-computed `data.json`-ში.

**UI პატერნი:** მსგავსი `ImportedProducts.jsx`-სა — ცხრილი + ფილტრი + sort.

---

### Part B — ⚠️ Supplier Concentration Widget (Phase 3.6)

**რას აკეთებს:** პატარა top-banner ვიჯეტი, რომელიც **ჩაჯდება არსებულ "🏢 მომწოდებლები" ტაბში** (არა ცალკე გვერდი):

- **HHI gauge** — Herfindahl–Hirschman index (0-10000), 🟢 low / 🟡 moderate / 🟠 high / 🔴 extreme
- **Top-5 share %** — Pareto concentration
- **Top-3 მომწოდებელი** — leverage label (🟢/🟡/🟠) + spend % + ~annual savings (₾)
- **1-liner steering** — "დაიწყე X-დან, ყველაზე მომგებიანია" (უმაღლესი leverage × savings)

**მონაცემის წყარო:** `prepare_supplier_brief()` portfolio mode — Phase 2.12; pre-computed `data.json`-ში.

**UI პატერნი:** Recharts + Tailwind-less CSS (`App.css` pattern).

---

### Part C — 💰 Cash Runway AI Tool (Phase 3.5)

**რას აკეთებს:** **Dashboard-ში widget არ ემატება**. ამის ნაცვლად AI-ს აქვს ახალი tool:

```
compute_cash_runway(
    current_balance_bog_ge,
    current_balance_tbc_ge,
    lookback_months=3  # ბოლო X თვის burn rate საშუალოდ
)
```

**Trigger ფრაზები (AI იცნობს):**
- *"რამდენი თვე ვძლებ?"*
- *"cash runway რა არის?"*
- *"ფული თავდება?"*
- *"წლიური ხარჯს მივდევ?"*

**Anti-trigger (NO tool call):**
- *"რამდენი ფული მიდევს ახლა?"* → ეს უბრალო lookup-ია
- Strategic questions სხვა feature-ებს ეხება

**AI-ს workflow:**
1. User ჰკითხავს runway-ს
2. AI ეკითხება user-ს მიმდინარე ნაშთს (BOG + TBC ცალ-ცალკე)
3. User აღებს ბანკის აპს, აწვდის ციფრებს
4. AI ი უხმობს `compute_cash_runway()` → ითვლის burn rate (ბოლო 3 თვის საშ.) და Days/Months remaining
5. AI პასუხობს 5-hats + 🟢/🟡/🔴 runway label-ით + სპეციფიკური რჩევა

**Output shape:**
```json
{
  "runway_months": 4.2,
  "runway_days": 127,
  "runway_label": "🟡 MEDIUM",
  "current_cash_ge": 80000,
  "monthly_burn_rate_ge": 19000,
  "lookback_months": 3,
  "burn_trend": "stable|accelerating|decelerating",
  "runway_label": "🟢 SAFE | 🟡 WATCH | 🔴 CRITICAL",
  "notes": [...]
}
```

---

## 📋 Implementation Plan

| Step | რა | ფაილი | სტატუსი |
|---|---|---|---|
| 1 | Pre-compute dead_stock + supplier_concentration ბლოკები | `generate_dashboard_data.py` | 🚧 |
| 2 | API tabs + contracts | `dashboard_pipeline/api_contracts.py` + `server.py` | 🚧 |
| 3 | Dead Stock page + Supplier Concentration widget | `rs-dashboard/src/DeadStock.jsx` + Suppliers embed | 🚧 |
| 4 | Cash Runway AI tool + prompt guidance | `dashboard_pipeline/ai/cash_runway.py` + `tools.py` + `prompts.py` | 🚧 |
| 5 | Backend restart + Live verify | pytest + `/api/data` + chat dog-food | 🚧 |

---

## ✅ Acceptance Criteria

### Part A — Dead Stock Page
- [ ] ახალი "💀 Dead Stock" ტაბი ჩანს "ანალიტიკური" ჯგუფში
- [ ] Top-30 SKU ცხრილში ჩანს: name / supplier / frozen ₾ / last sale / action
- [ ] 3-bucket donut რენდერდება (181-365 / 365+ / unmatched)
- [ ] 4-action salvage plan ჩანს SKU count + freed ₾
- [ ] Unmatched warning ≥30% → banner ჩანს
- [ ] `data.json` contains `dead_stock_summary` block

### Part B — Supplier Concentration Widget
- [ ] "🏢 მომწოდებლები" ტაბზე თავში ახალი ვიჯეტი ჩანს
- [ ] HHI gauge + concentration label (low/moderate/high/extreme)
- [ ] Top-3 მომწოდებელი leverage label-ით
- [ ] Steering 1-liner ("#1 priority") ჩანს
- [ ] `data.json` contains `supplier_concentration` block

### Part C — Cash Runway AI Tool
- [ ] `TOOL_SCHEMAS=17`; `compute_cash_runway` tool present
- [ ] Prompt section 💰 Cash Runway გვ. `SYSTEM_PROMPT_KA`-ში
- [ ] Investigator prompt UNTOUCHED (0/new-markers)
- [ ] 30+ new tests in `test_ai_cash_runway.py`
- [ ] Live chat: "რამდენი თვე ვძლებ?" → AI ეკითხება ნაშთს → user აწვდის → tool იძახება → runway answer

### Global
- [ ] pytest all-green (1242 → 1272+ expected)
- [ ] Backend restart #12 → new PID, `TOOL_SCHEMAS=17`
- [ ] E2E Playwright smoke test passes for Dead Stock tab

---

## 🛡 Do-not-touch Rules

- `JOURNAL_KINDS` (Phase 3.1) unchanged
- `TOOL_SCHEMAS[0..15]` order unchanged; `compute_cash_runway` appended at index 16
- Investigator prompt stays 0/new-marker free
- Existing tabs (suppliers, waybills, etc.) untouched except Suppliers gets NEW widget at top (doesn't break existing layout)
- `analyze_dead_stock()` + `prepare_supplier_brief()` contracts unchanged (read-only reuse)
