# გეგმა — სტეკი + დასრულებული სამუშაოები

> **ცოცხალი სტატუსისთვის** → `CONTEXT_HANDOFF.md`
> **ყველა phase-ის სტატუსი ცხრილად** → `PHASE_STATUS_MATRIX.md`
> **Master roadmap** → `AI_GENIUS_PARTNER_PLAN.md` v2.1
> **ისტორიული evidence** → `HANDOFF.md` + `HANDOFF_ARCHIVE/`
>
> ეს ფაილი არ არის day-to-day ჩანაწერი — აქ მხოლოდ (1) სტეკი და (2) closed milestones-ის ერთსტრიქონიანი ლოგია. ყოველი sprint-ის ვრცელი ისტორია commit message-ში და `HANDOFF_ARCHIVE/PREVIEWS/`-ში ცხოვრობს.

---

## სტეკი

- **Backend**: Python 3.14 + pandas + FastAPI (`server.py`)
- **Frontend**: React 19 + Vite (`rs-dashboard/`)
- **Data flow**: Excel → `dashboard_pipeline/` → `data.json` (131 MB) → UI
- **AI stack**: Anthropic Sonnet 4.6 + Extended Thinking + ChromaDB 1.5 (`ai_vectors/`) + Prophet 1.3 + ARIMA ensemble
- **Service**: Windows Service `FinancialDashboardBackend` (NSSM 2.24, auto-start + auto-restart 2s)
- **Python interpreter (canonical)**: `C:\Users\tengiz\OneDrive\Desktop\AI აგენტი\venv\Scripts\python.exe`

---

## Dashboard MVP — Phases 1–9 (დასრულებული, 2025 – 2026-Q1)

| phase | რა გაკეთდა |
|---|---|
| 1–2 | აუდიტი, logging, DRY refactor, dead code cleanup, Cashflow extraction |
| 3 | App.jsx decomposition (→ Suppliers/Waybills), `run()` 1024→211 line refactor (8 helper), CSS → 7 ფაილი, 105 ახალი unit test, API rate limiting |
| 4 | APScheduler 30წთ auto-refresh, RefreshButton, ExportButton (11/14 tab), მობილური bottom nav, touch UX |
| 5 | Playwright E2E (38 test / 5 spec), API auth ApiKeyMiddleware, PWA offline (manifest + sw.js) |
| 6 | PWA icons, bundle optimization (manualChunks, esnext, gzip 87KB initial) |
| 7 | Extra E2E: export (9) + supplier-modal (16); 63/63 E2E, 125/125 unit |
| 8 | Packet F — `react-datepicker` replaces 3 custom calendars |
| 9 | Packet G — `/api/data` canonical date-range contract; filtered retail_sales 672s → 26s |

## AI Advisor Foundation — Phase 0A / 0B (დასრულებული, 2026-04-18 → 04-19)

| ნაწილი | შედეგი |
|---|---|
| 0A Critical Foundation | Calculator Enforcement + Self-Critique Loop + Today's Pulse (73 test) |
| 0B Sprint 1 | Extended Thinking wiring, 🧠 Deep Think toggle, STOP-CHECK |
| 0B Sprint 2 | Prophet 1.3 + ARIMA ensemble, `forecast_revenue` tool |
| 0B Sprint 3 | ChromaDB 1.5 semantic memory, `recall_context` + `save_memory` tools, 18,263 indexed Excel chunks |
| 0B Sprint 4 | Decision Journal (`journal_{add,list,update}_entry`), `MAX_TOOL_ITERATIONS_DEEP=10`, live dog-food 7/7 PASS |

## AI Genius Partner — Phase 1–4 (დასრულებული, 2026-04-20 → 04-22)

| ნაწილი | შედეგი |
|---|---|
| 1 Part A | Strategic Partner persona + 5-hat + project map + source hierarchy + confidence labels + 📌 anti-hallucination v2; `MAX_TOOL_ITERATIONS_DEEP 10→12` |
| 1 Part B | Georgian regulation (VAT/საპენსიო/franchise/RS.ge) + monthly rhythm + baseline facts |
| 1 Part C | Multi-Store DNA (ოზურგეთი urban vs დვაბზუ rural) |
| 1 Part D | Self-Correction Loop (retry / Latin alias / self-triage) |
| 2.1–2.9 | AI tools: analyze_dead_stock, prepare_supplier_brief, compute_cash_runway, analyze_product_profitability, find_promotion_candidates, detect_trends + dashboard tabs |
| 3.1 + 3.5 + 3.7 | Co-Designer (`propose_feature`) + Dead Stock page + Supplier Concentration widget + Cash Runway |
| 4A | Debt Repayment Plan (`build_debt_repayment_plan`) + React DebtPlan page + Windows Service install |
| 4B | AI Personality Tuning — 28 new rules across 4 tiers, 171 new tests, SYSTEM_PROMPT_KA 1,290→1,100 lines |
| 4C.1 + 4C.2 + 4C.3 | Tool Schema Poka-yoke (Part A + B, 8 tools) + `summary_ka` on 4 headline tools + full-stack dog-food |

## VAT / Tax Audit — Phase 5 (დასრულებული, 2026-04-23 → 04-24)

| sprint | შედეგი |
|---|---|
| 5.1–5.2 | VAT reconciliation module + 3 AI tools + TBC POS terminal-ID matching (5 physical terminals, transit-IBAN double-count eliminated) |
| 5.3–5.4 | Dashboard 🧾 VAT tab + Excel export for auditor |
| 5.5 | Revenue formula fix (`unit_price × quantity`, 9% drift → 612K revenue drop) |
| 5.6–5.9 | VAT AI live dog-food 3/3 PASS + per-shop by_shop breakdown + MAX-data-gap `insufficient_data` status |
| 5.10 | Unit error diagnosis (gross vs net mismatch inflating gap by +702K) — evidence-only |
| 5.11 | Unit-fix landed end-to-end (NET basis primary, 5 new regression tests, live AI 1/1 PASS) |
| 5.12 | TBC shortage 2023-08→2024-03 diagnosis — root cause = statement format change; no safe auto-fix |

## Tier 2 Pipeline Cache — Sprint 2 / 3a / 3b / 3c (დასრულებული, 2026-04-22 → 04-24)

| sprint | section | speedup |
|---|---|---|
| 2 | retail_sales per-file cache | 2× cold→hot |
| 3a | cache slim-down 864→207 MB | — |
| 3b | bank samurneo (TBC+BOG) | TBC 200× / BOG 748× |
| 3c | bank expense_categories (TBC+BOG) | TBC 62× / BOG 246× |

---

## ახლა ღია — next recommended work

სრული priority ცხრილი → `CONTEXT_HANDOFF.md:107-116`. Highlights:

1. **Sprint 3d** — `collect_tax_flow` per-file cache (cross-bank; `_run_cached_per_file` generic helper უკვე მზად)
2. **Sprint 3e** — POS terminal income cache (Sprint 5.12-sensitive — საჭიროა pin test)
3. **Sprint 3f** — foodmart cashback cache
4. Phase 4C.1 Part C (evidence-driven, only if live dog-food routing miss surfaces)
5. Phase 2.3 `industry_benchmark` (blocked on external data source decision)
6. Phase 3 remaining (4 features) + Phase 4 Advanced (9 features) + Parking Lot (~40)

## Parking Lot

40+ feature `AI_GENIUS_PARTNER_PLAN.md` v2.1-ში. არ დაილუქოს — arbitration ხდება `CONTEXT_HANDOFF.md` "Still-open work" ცხრილით.
