# AI აგენტი — ფინანსური დეშბორდი

**პროექტის სტატუსი (2026-04-25):** Phase 4A/4B/4C CLOSED · Phase 2.1–2.9 + Phase 3.8 `margin_radar` COMPLETE · Phase 5 VAT audit system (Sprint 5.1–5.12) COMPLETE · Tier 2 per-file cache series (Sprint 2/3a–3f) COMPLETE. 28 AI tools, 2,166 pytest green, 15 dashboard tabs.

**დოკუმენტები:**
- [`CONTEXT_HANDOFF.md`](CONTEXT_HANDOFF.md) — ცოცხალი სტატუსი, verified facts, do-not-touch, next step (**ახალი ჩატისთვის ჯერ ეს**)
- [`PHASE_STATUS_MATRIX.md`](PHASE_STATUS_MATRIX.md) — ცხრილი ყველა phase-ის მდგომარეობით
- [`AGENTS.md`](AGENTS.md) — agent work rules (session pacing, GitNexus, prompt hygiene)
- [`HANDOFF.md`](HANDOFF.md) — commit SHA → archive evidence pointer
- `HANDOFF_ARCHIVE/` — historical evidence + superseded roadmaps

## წყარო Excel-ები (`Financial_Analysis/`)

პროექტის **ფესვიდან** (საქაღალდე, სადაც `generate_dashboard_data.py` ზის):

| წყარო | საქაღალდე (ფესვიდან) | ფაილები | ფარდობითი glob |
|--------|------------------------|---------|------------------|
| BOG ბანკის ამონაწერი | `Financial_Analysis/ბოგ ბანკი ამონაწერი/` | ყველა `.xlsx` | `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx` |
| TBC / თბს ბანკის ამონაწერი | `Financial_Analysis/თბს ბანკი ამონაწერი/` | ყველა `.xlsx` | `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx` |
| RS ზედნადები | `Financial_Analysis/რს ზედნადები/` | ყველა `.xlsx` და `.xls` | `*.xlsx` და `*.xls` იმავე საქაღალდეში |

კოდი იყენებს: `list_bog_bank_statement_xlsx()`, `list_tbc_bank_statement_xlsx()`, `list_rs_waybill_files()` — გზები იკითხება **სკრიპტის მდებარეობიდან** (`_financial_analysis_path`), არა `cwd`-დან.

დეტალები: [`AGENTS.md`](AGENTS.md), Cursor წესი: [`.cursor/rules/financial-excel-locations.mdc`](.cursor/rules/financial-excel-locations.mdc).
