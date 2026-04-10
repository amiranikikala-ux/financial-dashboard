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
    
    # Required columns:
    # თარიღი: 'გააქტიურების თარ.'
    # მომწოდებელი: 'ორგანიზაცია'
    # ზედნადების ნომერი: 'ზედნადები'
    # თანხა: 'თანხა'
    
    master = pd.DataFrame()
    master['თარიღი'] = pd.to_datetime(df['გააქტიურების თარ.'], errors='coerce').dt.strftime('%Y-%m-%d')
    master['მომწოდებელი'] = df['ორგანიზაცია']
    master['ზედნადების ნომერი'] = df['ზედნადები']
    master['თანხა'] = df['თანხა']
    
    # Flags checking text
    master['უკან დაბრუნება'] = df['ტიპი'].astype(str).str.contains('უკან დაბრუნება', case=False, na=False)
    master['გაუქმებული'] = df['სტატუსი'].astype(str).str.contains('გაუქმებული', case=False, na=False)
    
    # Create the markdown preview
    with open('rs_preview.md', 'w', encoding='utf-8') as file:
        file.write(master.head(5).to_markdown())
