# AI აგენტი — ფინანსური დეშბორდი

## წყარო Excel-ები (`Financial_Analysis/`)

პროექტის **ფესვიდან** (საქაღალდე, სადაც `generate_dashboard_data.py` ზის):

| წყარო | საქაღალდე (ფესვიდან) | ფაილები | ფარდობითი glob |
|--------|------------------------|---------|------------------|
| BOG ბანკის ამონაწერი | `Financial_Analysis/ბოგ ბანკი ამონაწერი/` | ყველა `.xlsx` | `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx` |
| TBC / თბს ბანკის ამონაწერი | `Financial_Analysis/თბს ბანკი ამონაწერი/` | ყველა `.xlsx` | `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx` |
| RS ზედნადები | `Financial_Analysis/რს ზედნადები/` | ყველა `.xlsx` და `.xls` | `*.xlsx` და `*.xls` იმავე საქაღალდეში |

კოდი იყენებს: `list_bog_bank_statement_xlsx()`, `list_tbc_bank_statement_xlsx()`, `list_rs_waybill_files()` — გზები იკითხება **სკრიპტის მდებარეობიდან** (`_financial_analysis_path`), არა `cwd`-დან.

დეტალები: [`AGENTS.md`](AGENTS.md), Cursor წესი: [`.cursor/rules/financial-excel-locations.mdc`](.cursor/rules/financial-excel-locations.mdc).
