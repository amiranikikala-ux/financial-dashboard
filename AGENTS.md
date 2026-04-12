# აგენტისთვის — სად არის Excel წყაროები

პროექტის **ფესვიდან** (საქაღალდე, სადაც `generate_dashboard_data.py`):

## სტრუქტურა და გზები


| მონაცემი                       | საქაღალდე                                              | Python                                                                   | ფარდობითი glob (ფესვიდან)                                    |
| ------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------ |
| BOG ბანკის ამონაწერი           | `Financial_Analysis/ბოგ ბანკი ამონაწერი/`              | `list_bog_bank_statement_xlsx()`                                         | `Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx`              |
| TBC / თბს ბანკის ამონაწერი     | `Financial_Analysis/თბს ბანკი ამონაწერი/`              | `list_tbc_bank_statement_xlsx()`                                         | `Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx`              |
| RS ზედნადები                   | `Financial_Analysis/რს ზედნადები/`                     | `list_rs_waybill_files()`                                                | `Financial_Analysis/რს ზედნადები/*.xlsx` + `*.xls`           |
| შემოტანილი პროდუქცია           | `Financial_Analysis/შემოტანილი პროდუქცია/`             | `list_imported_product_files()` — ჯერ `*.csv`, fallback `*.xls`/`*.xlsx` | `Financial_Analysis/შემოტანილი პროდუქცია/*.csv`              |
| გაყიდული პროდუქტები — დვაბზუ   | `Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/`   | ჯერ dedicated loader არ დგას; source-only line export                    | `Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/*.xlsx`   |
| გაყიდული პროდუქტები — ოზურგეთი | `Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/` | ჯერ dedicated loader არ დგას; source-only line export                    | `Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/*.xlsx` |


ახალი პერიოდის ფაილები დაამატე იმავე საქაღალდეებში — სახელი მნიშვნელობას არ აქვს, თუ გაფართოება შეესაბამება ცხრილს.

თუ ამოცანა ეხება supplier -> imported products ანალიზს, პირველ რიგში მოძებნე `Financial_Analysis/შემოტანილი პროდუქცია/*.csv`. ეს არის preferred სრული export; თუ `csv` არ დევს, მხოლოდ მაშინ დაეყრდენი legacy `*.xls` / `*.xlsx` ფაილებს. ამ წყაროში, როგორც წესი, არის line-level ჩანაწერები: `გამყიდველი`, `საქონლის დასახელება`, `რაოდ.`, `ერთეულის ფასი`, `საქონლის ფასი`, `ზედნადების ნომერი`, `სტატუსი`, `გააქტიურების თარიღი`.

თუ ამოცანა ეხება retail/product sales ან store-level sell-through ანალიზს, გადაამოწმე:

- `Financial_Analysis/გაყიდული პროდუქტები სოფ დვაბზუ/*.xlsx`
- `Financial_Analysis/გაყიდული პროდუქტები სოფ ოზურგეთი/*.xlsx`

ამ Excel-ებში ამჟამად ჩანს line-level გაყიდვების schema: `P_ID`, `კოდი`, `შტრიხკოდი`, `დასახელება`, `ერთეული`, `რაოდენობა`, `ფასი`, `თვითღირებულება`, `დრო`, `ობიექტი`, `მოგება`, `ქვეჯგუფი`, `ცვლა`.

Parsing caveat: ამ ფაილებში `openpyxl`-ის `read_only`/dimension მეტამონაცემი ზოგჯერ მცდარად აჩვენებს მხოლოდ header row `P_ID`-ს. ამ წყაროსთვის დაეყრდენი `pandas.read_excel()`-ს ან full workbook read-ს; არ დაეყრდნო მარტო `openpyxl` `max_row`/`max_column`-ს.

**სვეტის ასოები (L, V, B …) არ გამოიყენო დოკუმენტაციაში საყრდენად** — ბანკის ექსპორტში მდებარეობა იცვლება. `generate_dashboard_data.py` იყენებს **სათაურის ქართულ სახელებს**. `get_bank_payments` — მხოლოდ **გასავალი** (დებეტი / გასული თანხა), არა მთელი ამონაწერის დებეტი↔კრედიტი.

დეტალურად: `[.cursor/rules/financial-excel-locations.mdc](.cursor/rules/financial-excel-locations.mdc)` · მოკლედ: `[README.md](README.md)`.