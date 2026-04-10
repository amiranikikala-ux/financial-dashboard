import pandas as pd
import json

out = {}

try:
    bog = pd.read_excel('Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx', header=None)
    out['BOG sample'] = bog.head(20).astype(str).to_dict(orient='records')
except Exception as e:
    out['BOG error'] = str(e)

with open('headers_output.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
