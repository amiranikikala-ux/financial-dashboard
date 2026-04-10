import pandas as pd
import json

out = {}

try:
    bog = pd.read_excel('Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx')
    out['BOG Columns'] = bog.columns.tolist()
    out['BOG sample'] = bog.head(2).astype(str).to_dict(orient='records')
except Exception as e:
    out['BOG error'] = str(e)

try:
    tbc = pd.read_excel('Financial_Analysis/თბს ბანკი ამონაწერი/2023.xlsx')
    out['TBC Columns'] = tbc.columns.tolist()
    out['TBC sample'] = tbc.head(2).astype(str).to_dict(orient='records')
except Exception as e:
    out['TBC error'] = str(e)

try:
    rs = pd.read_excel('Financial_Analysis/რს ზედნადები/2023.xls')
    out['RS Columns'] = rs.columns.tolist()
except Exception as e:
    out['RS error'] = str(e)

with open('headers_output.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
