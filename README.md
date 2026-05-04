# AI აგენტი — ფინანსური დეშბორდი

**პროექტის სტატუსი (2026-05-04):** rs.ge SOAP connector + BOG API + TBC DBI ყველა PROOFED. 28 AI tools, 16 dashboard tabs, MegaPlus DB integration LIVE.

**დოკუმენტები:**
- [`CONTEXT_HANDOFF.md`](CONTEXT_HANDOFF.md) — ცოცხალი სტატუსი, verified facts, do-not-touch, next step (**ახალი ჩატისთვის ჯერ ეს**)
- [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) — 18-სექციის roadmap (A→F sequence)
- [`AGENTS.md`](AGENTS.md) — agent work rules (proof gate, session pacing, GitNexus, prompt hygiene)
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
