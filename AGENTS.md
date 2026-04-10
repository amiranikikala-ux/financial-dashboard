# აგენტისთვის — სად არის Excel წყაროები

პროექტის **ფესვიდან** (საქაღალდე, სადაც `generate_dashboard_data.py`):

## სტრუქტურა და გზები

| მონაცემი | საქაღალდე | Python | ფარდობითი glob (ფესვიდან) |
|----------|------------|--------|----------------------------|
| BOG ბანკის ამონაწერი | `Financial_Analysis/ბოგ ბანკი ამონაწერი/` | `list_bog_bank_statement_xlsx()` | `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx` |
| TBC / თბს ბანკის ამონაწერი | `Financial_Analysis/თბს ბანკი ამონაწერი/` | `list_tbc_bank_statement_xlsx()` | `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx` |
| RS ზედნადები | `Financial_Analysis/რს ზედნადები/` | `list_rs_waybill_files()` | `Financial_Analysis/რს ზედნადები/*.xlsx` + `*.xls` |

ახალი პერიოდის ფაილები დაამატე იმავე საქაღალდეებში — სახელი მნიშვნელობას არ აქვს, თუ გაფართოება შეესაბამება ცხრილს.

**სვეტის ასოები (L, V, B …) არ გამოიყენო დოკუმენტაციაში საყრდენად** — ბანკის ექსპორტში მდებარეობა იცვლება. `generate_dashboard_data.py` იყენებს **სათაურის ქართულ სახელებს**. `get_bank_payments` — მხოლოდ **გასავალი** (დებეტი / გასული თანხა), არა მთელი ამონაწერის დებეტი↔კრედიტი.

დეტალურად: [`.cursor/rules/financial-excel-locations.mdc`](.cursor/rules/financial-excel-locations.mdc) · მოკლედ: [`README.md`](README.md).
