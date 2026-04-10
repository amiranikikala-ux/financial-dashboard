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
    
    # Create flags
    df['უკან დაბრუნება'] = df['ტიპი'].astype(str).str.contains('უკან დაბრუნება', case=False, na=False)
    df['გაუქმებული'] = df['სტატუსი'].astype(str).str.contains('გაუქმებული', case=False, na=False)
    
    # Calculate effective amount
    def get_effective_amount(row):
        val = pd.to_numeric(row['თანხა'], errors='coerce')
        if pd.isna(val):
            return 0
        if row['გაუქმებული']:
            return 0
        if row['უკან დაბრუნება']:
            v = float(val)
            return v if v < 0 else -v
        return val
        
    df['ეფექტური თანხა'] = df.apply(get_effective_amount, axis=1)
    
    # Group by Organization
    agg_df = df.groupby('ორგანიზაცია').agg(
        ზედნადებების_რაოდენობა=('ზედნადები', 'count'),
        ჯამური_თანხა_ნომინალი=('თანხა', lambda x: pd.to_numeric(x, errors='coerce').sum()),
        რეალური_ჯამი_გაუქმებულების_გამოკლებით=('ეფექტური თანხა', 'sum')
    ).reset_index()
    
    agg_df = agg_df.sort_values('რეალური_ჯამი_გაუქმებულების_გამოკლებით', ascending=False)
    
    with open('rs_aggregated_preview.md', 'w', encoding='utf-8') as file:
        file.write(agg_df.to_markdown(index=False))
