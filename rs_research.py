import pandas as pd
import glob
import json

rs_files = glob.glob('Financial_Analysis/რს ზედნადები/*.xls')
all_rs = []

for f in rs_files:
    try:
        df = pd.read_excel(f)
        all_rs.append(df)
    except Exception as e:
        print(f"Error {f}: {e}")

if all_rs:
    df = pd.concat(all_rs, ignore_index=True)
    status_unique = df['სტატუსი'].unique() if 'სტატუსი' in df.columns else []
    state_unique = df['მდგომარეობა'].unique() if 'მდგომარეობა' in df.columns else []
    type_unique = df['ტიპი'].unique() if 'ტიპი' in df.columns else []
    cat_unique = df['კატეგორია'].unique() if 'კატეგორია' in df.columns else []
    
    out = {
        'სტატუსი': [str(x) for x in status_unique],
        'მდგომარეობა': [str(x) for x in state_unique],
        'ტიპი': [str(x) for x in type_unique],
        'კატეგორია': [str(x) for x in cat_unique],
        'columns': df.columns.tolist()
    }
    
    with open('rs_research.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
else:
    print("No RS data loaded.")
