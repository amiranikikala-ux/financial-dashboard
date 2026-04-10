import pandas as pd
import glob
import os

print("="*80)
print("TBC ფაილების სრული დიაგნოსტიკა")
print("="*80)

tbc_files = glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')
print(f"\nნაპოვნი TBC ფაილები: {len(tbc_files)}")
for f in tbc_files:
    print(f"  - {os.path.basename(f)}")

def find_header_row(file_path):
    df = pd.read_excel(file_path, header=None, nrows=20)
    for i, row in df.iterrows():
        if row.astype(str).str.contains('თარიღი').any():
            return i
    return 0

for f in tbc_files:
    print(f"\n{'='*80}")
    print(f"ფაილი: {os.path.basename(f)}")
    print(f"{'='*80}")
    
    # 1. Read raw first 5 rows
    try:
        raw = pd.read_excel(f, header=None, nrows=5)
        print("\nRaw პირველი 5 სტრიქონი:")
        for i, row in raw.iterrows():
            vals = [f"{v}" for v in row.values if str(v) != 'nan']
            if vals:
                print(f"  Row {i}: {vals[:6]}")
    except Exception as e:
        print(f"Raw Read Error: {e}")
    
    # 2. Find header and read properly
    try:
        header_idx = find_header_row(f)
        print(f"\nHeader Row: {header_idx}")
        df = pd.read_excel(f, header=header_idx)
        print(f"სვეტების სია ({len(df.columns)} სვეტი):")
        for col in df.columns:
            print(f"  - '{col}'")
        print(f"სულ სტრიქონები: {len(df)}")
        
        # 3. Check specific columns
        debit_col = None
        id_col = None
        for c in df.columns:
            if 'გასული' in str(c):
                debit_col = c
                print(f"\n✅ გასული თანხა სვეტი ნაპოვნია: '{c}'")
            if 'საგადასახადო' in str(c):
                id_col = c
                print(f"✅ საგადასახადო კოდი სვეტი ნაპოვნია: '{c}'")
            if 'პარტნიორ' in str(c).lower():
                print(f"  ℹ️ პარტნიორის სვეტი: '{c}' -> Sample: {df[c].dropna().head(3).tolist()}")
        
        if not debit_col:
            print("\n❌ 'გასული თანხა' სვეტი ვერ მოიძებნა!")
            # ვეძებთ მსგავს სვეტებს
            for c in df.columns:
                if any(kw in str(c).lower() for kw in ['თანხა', 'debit', 'გასული', 'გადარიცხ']):
                    print(f"  🔎 მსგავსი სვეტი: '{c}'")
        
        if not id_col:
            print("❌ 'პარტნიორის საგადასახადო კოდი' სვეტი ვერ მოიძებნა!")
            for c in df.columns:
                if any(kw in str(c).lower() for kw in ['კოდი', 'id', 'საიდენტიფ', 'საგადასახადო']):
                    print(f"  🔎 მსგავსი სვეტი: '{c}'")
        
        # 4. Search for Ifkli specifically
        if id_col:
            # Show sample IDs
            sample_ids = df[id_col].dropna().head(5).tolist()
            print(f"\nID სვეტის ტიპი: {df[id_col].dtype}")
            print(f"Sample IDs: {sample_ids}")
            
            # Search for Ifkli 200179118
            ifkli_match = df[df[id_col].astype(str).str.contains('200179118', na=False)]
            print(f"\nიფქლი (200179118) ძებნის შედეგი: {len(ifkli_match)} ჩანაწერი")
            if len(ifkli_match) > 0 and debit_col:
                print(f"  გასული თანხა: {pd.to_numeric(ifkli_match[debit_col], errors='coerce').sum():.2f}")
                print(f"  პირველი 3 ჩანაწერი:")
                for _, row in ifkli_match.head(3).iterrows():
                    print(f"    ID: {row[id_col]}, თანხა: {row[debit_col]}")
        
        # 5. Also check partner name column for Ifkli
        partner_col = next((c for c in df.columns if 'პარტნიორი' == str(c).strip()), None)
        if not partner_col:
            partner_col = next((c for c in df.columns if c == 'პარტნიორი'), None)
        if partner_col:
            ifkli_name = df[df[partner_col].astype(str).str.contains('იფქლი', case=False, na=False)]
            print(f"\n'იფქლი' სახელით ძებნა (სვეტი '{partner_col}'): {len(ifkli_name)} ჩანაწერი")
            if len(ifkli_name) > 0:
                print("  Sample:")
                for _, row in ifkli_name.head(3).iterrows():
                    vals = {c: row[c] for c in [partner_col, id_col, debit_col] if c and c in df.columns}
                    print(f"    {vals}")
                    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*80}")
print("დიაგნოსტიკა დასრულდა")
print(f"{'='*80}")
