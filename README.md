# AI აგენტი — ფინანსური დეშბორდი

**პროექტის სტატუსი:** Phase 4A CLOSED (2026-04-21) — AI Business Advisor ცოცხლად. შემდეგი: Phase 4B prompt tuning (planned).
**დოკუმენტები:**
- [`PHASE_STATUS_MATRIX.md`](PHASE_STATUS_MATRIX.md) — ცხრილი ყველა phase-ის მდგომარეობით
- [`AI_GENIUS_PARTNER_PLAN.md`](AI_GENIUS_PARTNER_PLAN.md) v2.1 — active master roadmap
- [`PLAN.md`](PLAN.md) — live status tracker
- [`CONTEXT_HANDOFF.md`](CONTEXT_HANDOFF.md) — ახალი ჩატისთვის მოკლე brief
- [`AGENTS.md`](AGENTS.md) — agent work rules

## წყარო Excel-ები (`Financial_Analysis/`)

პროექტის **ფესვიდან** (საქაღალდე, სადაც `generate_dashboard_data.py` ზის):

| წყარო | საქაღალდე (ფესვიდან) | ფაილები | ფარდობითი glob |
|--------|------------------------|---------|------------------|
| BOG ბანკის ამონაწერი | `Financial_Analysis/ბოგ ბანკი ამონაწერი/` | ყველა `.xlsx` | `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx` |
| TBC / თბს ბანკის ამონაწერი | `Financial_Analysis/თბს ბანკი ამონაწერი/` | ყველა `.xlsx` | `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx` |
| RS ზედნადები | `Financial_Analysis/რს ზედნადები/` | ყველა `.xlsx` და `.xls` | `*.xlsx` და `*.xls` იმავე საქაღალდეში |

კოდი იყენებს: `list_bog_bank_statement_xlsx()`, `list_tbc_bank_statement_xlsx()`, `list_rs_waybill_files()` — გზები იკითხება **სკრიპტის მდებარეობიდან** (`_financial_analysis_path`), არა `cwd`-დან.

დეტალები: [`AGENTS.md`](AGENTS.md), Cursor წესი: [`.cursor/rules/financial-excel-locations.mdc`](.cursor/rules/financial-excel-locations.mdc).
