import pandas as pd
import glob
import os

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
    
    # Flags checking text
    df['უკან დაბრუნება (ფლეგი)'] = df['ტიპი'].astype(str).str.contains('უკან დაბრუნება', case=False, na=False)
    df['გაუქმებული (ფლეგი)'] = df['სტატუსი'].astype(str).str.contains('გაუქმებული', case=False, na=False)
    
    # Calculate amounts
    def get_nominal(row):
        return pd.to_numeric(row['თანხა'], errors='coerce') if not pd.isna(row['თანხა']) else 0

    def get_effective(row):
        val = get_nominal(row)
        if row['გაუქმებული (ფლეგი)']: return 0
        if row['უკან დაბრუნება (ფლეგი)']:
            v = float(val) if not pd.isna(val) else 0.0
            return v if v < 0 else -v
        return val
        
    def get_returned(row):
        val = get_nominal(row)
        if row['უკან დაბრუნება (ფლეგი)'] and not row['გაუქმებული (ფლეგი)']: return val
        return 0

    df['ნომინალური თანხა'] = df.apply(get_nominal, axis=1)
    df['ეფექტური თანხა'] = df.apply(get_effective, axis=1)
    df['დაბრუნებული თანხა'] = df.apply(get_returned, axis=1)
    
    # Group by Organization
    agg_df = df.groupby('ორგანიზაცია').agg(
        ზედნადებების_რაოდენობა=('ზედნადები', 'count'),
        ჯამური_თანხა_ნომინალი=('ნომინალური თანხა', 'sum'),
        უკან_დაბრუნებული_თანხა=('დაბრუნებული თანხა', 'sum'),
        რეალური_ჯამი_გაუქმებულების_გამოკლებით=('ეფექტური თანხა', 'sum')
    ).reset_index()
    
    agg_df = agg_df.sort_values('რეალური_ჯამი_გაუქმებულების_გამოკლებით', ascending=False)
    
    # Add Index starting from 1
    agg_df.insert(0, '#', range(1, len(agg_df) + 1))
    
    # Output file
    out_file = 'RS_Final_Check.xlsx'
    agg_df.to_excel(out_file, index=False)
    print(f"Successfully saved {out_file}")
