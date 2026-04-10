import pandas as pd

try:
    bog = pd.read_excel('Financial_Analysis/ბოგ ბანკი ამონაწერი/2023.xlsx')
    print("BOG Columns:", bog.columns.tolist())
    print("BOG sample:", bog.head(2).to_dict(orient='records'))
except Exception as e:
    print("BOG error:", e)

try:
    tbc = pd.read_excel('Financial_Analysis/თბს ბანკი ამონაწერი/2023.xlsx')
    print("TBC Columns:", tbc.columns.tolist())
    print("TBC sample:", tbc.head(2).to_dict(orient='records'))
except Exception as e:
    print("TBC error:", e)

try:
    rs = pd.read_excel('Financial_Analysis/რს ზედნადები/2023.xls')
    print("RS Columns:", rs.columns.tolist())
except Exception as e:
    print("RS error:", e)
