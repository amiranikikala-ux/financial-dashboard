import pandas as pd
import glob
import re
import json

# ============= ლაქტალისის სრული დიაგნოსტიკა =============

# 1. Dashboard-ში რა წერია
with open('rs-dashboard/public/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for s in data['suppliers']:
    if 'ლაქტალის' in s.get('ორგანიზაცია', ''):
        print(f"Dashboard-ში:")
        print(f"  ორგანიზაცია: {s['ორგანიზაცია']}")
        print(f"  ზედნადებები: {s['waybills_count']}")
        print(f"  ნომინალი:    {s['total_nominal']:.2f}")
        print(f"  რეალური:     {s['total_effective']:.2f}")
        print(f"  გადახდილი:   {s['total_paid']:.2f}")
        print(f"  დავალიანება: {s['total_debt']:.2f}")

# 2. RS-ში ლაქტალისის ID
rs_files = glob.glob('Financial_Analysis/რს ზედნადები/*.xls')
all_rs = []
for f in rs_files:
    try:
        df = pd.read_excel(f)
        all_rs.append(df)
    except: pass
rs_df = pd.concat(all_rs, ignore_index=True)

lakt = rs_df[rs_df['ორგანიზაცია'].astype(str).str.contains('ლაქტალის', case=False, na=False)]
org_name = lakt['ორგანიზაცია'].iloc[0]
match = re.search(r'\((\d+)', str(org_name))
lakt_id = match.group(1) if match else None
print(f"\nRS ID: {lakt_id}")
print(f"RS სახელი: {org_name}")

# 3. BOG-ში ძებნა
def find_header_row(file_path):
    df = pd.read_excel(file_path, header=None, nrows=20)
    for i, row in df.iterrows():
        if row.astype(str).str.contains('თარიღი').any():
            return i
    return 0

print(f"\n{'='*80}")
print(f"BOG ბანკი - ID '{lakt_id}':")
bog_total = 0
bog_files = glob.glob('Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx')
for f in bog_files:
    try:
        h = find_header_row(f)
        df = pd.read_excel(f, header=h)
        id_col = next((c for c in df.columns if 'მიმღების საიდენტიფიკაციო' in str(c)), None)
        debit_col = next((c for c in df.columns if 'დებეტი' in str(c) and 'ბრუნვა' not in str(c)), None)
        if id_col and debit_col:
            matched = df[df[id_col].astype(str).str.contains(lakt_id, na=False)]
            if len(matched) > 0:
                amt = pd.to_numeric(matched[debit_col], errors='coerce').sum()
                print(f"  {glob.os.path.basename(f)}: {len(matched)} ტრანზ., {amt:.2f} ₾")
                bog_total += amt
    except: pass
print(f"  BOG ჯამი: {bog_total:.2f}")

# 4. TBC-ში ძებნა - ორი მეთოდით
print(f"\n{'='*80}")
print(f"TBC ბანკი:")
tbc_files = glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')

tbc_by_id = 0
tbc_by_name = 0
tbc_id_count = 0
tbc_name_count = 0

for f in tbc_files:
    try:
        h = find_header_row(f)
        df = pd.read_excel(f, header=h)
        id_col = next((c for c in df.columns if 'პარტნიორის საგადასახადო კოდი' in str(c)), None)
        debit_col = next((c for c in df.columns if 'გასული თანხა' in str(c)), None)
        partner_col = next((c for c in df.columns if c == 'პარტნიორი'), None)
        
        if not debit_col: continue
        
        # ID-ით ძებნა
        if id_col:
            matched_id = df[df[id_col].astype(str).str.contains(lakt_id, na=False)]
            valid = matched_id[matched_id[debit_col].notna()]
            if len(valid) > 0:
                amt = pd.to_numeric(valid[debit_col], errors='coerce').sum()
                print(f"  {glob.os.path.basename(f)} (ID-ით): {len(valid)} ტრანზ., {amt:.2f} ₾")
                tbc_by_id += amt
                tbc_id_count += len(valid)
        
        # სახელით ძებნა (ვეძებთ "ლაქტალის" ან "lactalis")
        if partner_col:
            matched_name = df[df[partner_col].astype(str).str.contains('ლაქტალის|lactalis', case=False, na=False)]
            # გავფილტროთ ის ჩანაწერები, რომლებიც ID-ით უკვე ვიპოვეთ
            if id_col:
                already_matched = matched_name[matched_name[id_col].astype(str).str.contains(lakt_id, na=False)]
                new_by_name = matched_name[~matched_name.index.isin(already_matched.index)]
            else:
                new_by_name = matched_name
            
            valid_name = new_by_name[new_by_name[debit_col].notna()]
            if len(valid_name) > 0:
                amt = pd.to_numeric(valid_name[debit_col], errors='coerce').sum()
                print(f"  {glob.os.path.basename(f)} (სახელით): {len(valid_name)} ტრანზ., {amt:.2f} ₾")
                tbc_by_name += amt
                tbc_name_count += len(valid_name)
                
                # ვნახოთ ამ ჩანაწერებში ID რა არის
                for _, row in valid_name.head(3).iterrows():
                    print(f"    Partner: '{str(row[partner_col])[:60]}', ID: '{row[id_col]}', Amount: {row[debit_col]}")
    except Exception as e:
        print(f"  Error: {e}")

print(f"\n  TBC ID-ით: {tbc_id_count} ტრანზ., {tbc_by_id:.2f} ₾")
print(f"  TBC სახელით (დამატებითი): {tbc_name_count} ტრანზ., {tbc_by_name:.2f} ₾")
print(f"  TBC ჯამი: {tbc_by_id + tbc_by_name:.2f} ₾")

print(f"\n{'='*80}")
print(f"საბოლოო:")
total = bog_total + tbc_by_id + tbc_by_name
print(f"  BOG: {bog_total:.2f}")
print(f"  TBC: {tbc_by_id + tbc_by_name:.2f}")
print(f"  სულ: {total:.2f}")
