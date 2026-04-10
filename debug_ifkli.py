import pandas as pd
import glob
import re
import os

# ====== იფქლი-ს კონკრეტული გამოკვლევა ======

# 1. RS-ში რა აქვს იფქლს
rs_files = glob.glob('Financial_Analysis/რს ზედნადები/*.xls')
all_rs = []
for f in rs_files:
    try:
        df = pd.read_excel(f)
        all_rs.append(df)
    except:
        pass

rs_df = pd.concat(all_rs, ignore_index=True)

# ვიპოვოთ იფქლი
ifkli_rows = rs_df[rs_df['ორგანიზაცია'].astype(str).str.contains('იფქლი', case=False, na=False)]

print("="*80)
print("RS-ში 'იფქლი'-ს მონაცემები:")
print(f"  სულ ზედნადებები: {len(ifkli_rows)}")

# Extract ID
org_name = ifkli_rows['ორგანიზაცია'].iloc[0] if len(ifkli_rows) > 0 else "N/A"
print(f"  სრული სახელი: {org_name}")

match = re.search(r'\((\d+)', str(org_name))
ifkli_id = match.group(1) if match else None
print(f"  საიდენტიფიკაციო კოდი: {ifkli_id}")

nominal_sum = pd.to_numeric(ifkli_rows['თანხა'], errors='coerce').sum()
print(f"  ჯამური ნომინალი (ყველა ზედნადების თანხების ჯამი): {nominal_sum:.2f}")

# ტიპი და სტატუსი
types = ifkli_rows['ტიპი'].value_counts()
statuses = ifkli_rows['სტატუსი'].value_counts()
print(f"\n  ტიპების განაწილება:")
for t, c in types.items():
    print(f"    {t}: {c}")
print(f"\n  სტატუსების განაწილება:")
for s, c in statuses.items():
    print(f"    {s}: {c}")

# რეალური ჯამის გამოთვლა
def calc_effective(row):
    val = pd.to_numeric(row['თანხა'], errors='coerce')
    if pd.isna(val):
        val = 0
    is_canceled = 'გაუქმებული' in str(row['სტატუსი'])
    is_return = 'უკან დაბრუნება' in str(row['ტიპი'])
    if is_canceled:
        return 0
    if is_return:
        v = float(val)
        return v if v < 0 else -v
    return val

ifkli_rows = ifkli_rows.copy()
ifkli_rows['ეფექტური'] = ifkli_rows.apply(calc_effective, axis=1)
effective_sum = ifkli_rows['ეფექტური'].sum()
print(f"\n  რეალური ჯამი (ეფექტური): {effective_sum:.2f}")

# 2. BOG-ში რა აქვს
print("\n" + "="*80)
print(f"BOG ბანკში '{ifkli_id}' ID-ით გადახდები:")

def find_header_row(file_path):
    df = pd.read_excel(file_path, header=None, nrows=20)
    for i, row in df.iterrows():
        if row.astype(str).str.contains('თარიღი').any():
            return i
    return 0

bog_total = 0.0
bog_files = glob.glob('Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx')
for f in bog_files:
    try:
        header_idx = find_header_row(f)
        df = pd.read_excel(f, header=header_idx)
        cols = df.columns
        
        debit_col = next((c for c in cols if 'დებეტი' in str(c) and 'ბრუნვა' not in str(c)), None)
        id_col = next((c for c in cols if 'მიმღების საიდენტიფიკაციო' in str(c)), None)
        
        if debit_col and id_col:
            matched = df[df[id_col].astype(str).str.contains(ifkli_id, na=False)]
            matched_valid = matched[matched[debit_col].notna()]
            file_sum = pd.to_numeric(matched_valid[debit_col], errors='coerce').sum()
            if file_sum > 0:
                print(f"  {os.path.basename(f)}: {file_sum:.2f} ლარი ({len(matched_valid)} ტრანზაქცია)")
                bog_total += file_sum
    except Exception as e:
        print(f"  Error: {e}")

print(f"  BOG ჯამი: {bog_total:.2f}")

# 3. TBC-ში რა აქვს
print("\n" + "="*80)
print(f"TBC ბანკში '{ifkli_id}' ID-ით გადახდები:")

tbc_total = 0.0
tbc_files = glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')
for f in tbc_files:
    try:
        header_idx = find_header_row(f)
        df = pd.read_excel(f, header=header_idx)
        cols = df.columns
        
        debit_col = next((c for c in cols if 'გასული თანხა' in str(c)), None)
        id_col = next((c for c in cols if 'პარტნიორის საგადასახადო კოდი' in str(c)), None)
        
        if debit_col and id_col:
            matched = df[df[id_col].astype(str).str.contains(ifkli_id, na=False)]
            matched_valid = matched[matched[debit_col].notna()]
            file_sum = pd.to_numeric(matched_valid[debit_col], errors='coerce').sum()
            if file_sum > 0:
                print(f"  {os.path.basename(f)}: {file_sum:.2f} ლარი ({len(matched_valid)} ტრანზაქცია)")
                tbc_total += file_sum
    except Exception as e:
        print(f"  Error: {e}")

print(f"  TBC ჯამი: {tbc_total:.2f}")

# 4. საბოლოო შეჯამება
print("\n" + "="*80)
print("საბოლოო შეჯამება:")
total_paid = bog_total + tbc_total
print(f"  RS რეალური ჯამი:         {effective_sum:.2f}")
print(f"  BOG გადახდილი:            {bog_total:.2f}")
print(f"  TBC გადახდილი:            {tbc_total:.2f}")
print(f"  სულ გადახდილი (BOG+TBC):  {total_paid:.2f}")
print(f"  დავალიანება:              {effective_sum - total_paid:.2f}")
print("="*80)
