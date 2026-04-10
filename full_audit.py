import pandas as pd
import glob
import re
import json

print("="*80)
print("სრული აუდიტი: ყველა RS მომწოდებელი vs BOG/TBC")
print("="*80)

# 1. Dashboard-ის data.json წავიკითხოთ — ეს არის ის, რაც ახლა Dashboard-ში ჩანს
with open('rs-dashboard/public/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 2. TBC-ში სახელით ნაპოვნი კომპანიები vs ID-ით ნაპოვნი
# დავადგინოთ, ვის აქვს TBC-ში გადახდები მხოლოდ სახელით (ID ცარიელი)
tbc_files = glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')

# ავაწყოთ - რომელ კომპანიებს აქვთ TBC-ში ცარიელი ID
companies_with_empty_id = {}  # partner_name -> total_amount
companies_with_id = {}  # id -> total_amount

for f in tbc_files:
    try:
        df = pd.read_excel(f)
        id_col = 'პარტნიორის საგადასახადო კოდი'
        debit_col = 'გასული თანხა'
        partner_col = 'პარტნიორი'
        
        if debit_col not in df.columns:
            continue
            
        for _, row in df.iterrows():
            amt = pd.to_numeric(row[debit_col], errors='coerce')
            if pd.isna(amt) or amt <= 0:
                continue
            
            tax_id = str(row[id_col]).split('.')[0].strip() if pd.notna(row[id_col]) else ''
            partner = str(row[partner_col]).strip() if partner_col in df.columns else ''
            
            if tax_id and tax_id.isdigit() and len(tax_id) >= 5:
                companies_with_id[tax_id] = companies_with_id.get(tax_id, 0) + amt
            elif partner and partner != 'nan':
                # გავჭრათ სახელი მძიმემდე
                short_name = partner.split(',')[0].strip().lower()
                companies_with_empty_id[short_name] = companies_with_empty_id.get(short_name, {})
                companies_with_empty_id[short_name]['amount'] = companies_with_empty_id[short_name].get('amount', 0) + amt
                companies_with_empty_id[short_name]['count'] = companies_with_empty_id[short_name].get('count', 0) + 1
    except Exception as e:
        pass

print(f"\nTBC-ში ID-იანი უნიკალური კომპანიები: {len(companies_with_id)}")
print(f"TBC-ში ID-გარეშე უნიკალური სახელები: {len(companies_with_empty_id)}")

# 3. RS-ის კომპანიების სახელი -> ID map
rs_files = glob.glob('Financial_Analysis/რს ზედნადები/*.xls')
rs_name_to_id = {}
rs_id_to_name = {}

for f in rs_files:
    try:
        df = pd.read_excel(f)
        for org in df['ორგანიზაცია'].dropna().unique():
            org_str = str(org)
            match = re.search(r'\((\d+)', org_str)
            if match:
                s_id = match.group(1)
                name_part = re.sub(r'\([^)]*\)\s*', '', org_str).strip().lower()
                name_clean = re.sub(r'^(შპს|სს|ი/მ)\s+', '', name_part).strip()
                if name_clean and len(name_clean) > 2:
                    rs_name_to_id[name_clean] = s_id
                    rs_id_to_name[s_id] = org_str
    except:
        pass

# 4. დავადგინოთ ვისთვის იმუშავა name fallback-მა
print(f"\n{'='*80}")
print("TBC-ში ID-გარეშე ჩანაწერები, რომლებიც RS-ის კომპანიებს სახელით დაემთხვა:")
print(f"{'='*80}")

matched_by_name = []
unmatched = []

for partner_name, info in sorted(companies_with_empty_id.items(), key=lambda x: x[1]['amount'], reverse=True):
    found = False
    for rs_name, rs_id in rs_name_to_id.items():
        if rs_name in partner_name or partner_name.startswith(rs_name):
            matched_by_name.append({
                'tbc_name': partner_name,
                'rs_name': rs_id_to_name.get(rs_id, '?'),
                'rs_id': rs_id,
                'amount': info['amount'],
                'count': info['count']
            })
            found = True
            break
    if not found:
        unmatched.append({
            'tbc_name': partner_name,
            'amount': info['amount'],
            'count': info['count']
        })

print(f"\n✅ სახელით დაემთხვა: {len(matched_by_name)} კომპანია")
for m in matched_by_name:
    print(f"  TBC: '{m['tbc_name'][:50]}' -> RS: '{m['rs_name'][:50]}' | {m['count']} ტრანზ. | {m['amount']:.2f} ₾")

print(f"\n❌ ვერ დაემთხვა (არ არის RS-ში ან სახელი განსხვავდება): {len(unmatched)} სახელი")
for u in unmatched[:20]:  # Top 20 by amount
    print(f"  '{u['tbc_name'][:60]}' | {u['count']} ტრანზ. | {u['amount']:.2f} ₾")
if len(unmatched) > 20:
    print(f"  ... და კიდევ {len(unmatched) - 20} სახელი")

# 5. საბოლოო Dashboard-ის სანდოობის შეფასება
print(f"\n{'='*80}")
print("Dashboard-ის სანდოობის შეფასება:")
print(f"{'='*80}")

suppliers = data['suppliers']
has_payments = [s for s in suppliers if s.get('total_paid', 0) > 0]
no_payments = [s for s in suppliers if s.get('total_paid', 0) == 0]

print(f"  სულ RS მომწოდებლები: {len(suppliers)}")
print(f"  გადახდა ნაპოვნია:    {len(has_payments)} ({len(has_payments)/len(suppliers)*100:.1f}%)")
print(f"  გადახდა არ ნაპოვნია: {len(no_payments)} ({len(no_payments)/len(suppliers)*100:.1f}%)")

total_effective = sum(s.get('total_effective', 0) for s in suppliers)
total_paid = sum(s.get('total_paid', 0) for s in suppliers)
print(f"\n  ჯამური რეალური ბრუნვა (RS): {total_effective:,.2f} ₾")
print(f"  ჯამური გადახდა (BOG+TBC):    {total_paid:,.2f} ₾")
print(f"  ჯამური დავალიანება:           {total_effective - total_paid:,.2f} ₾")

# 6. TOP-10 კომპანია, სადაც გადახდა 0-ია (ეჭვის ქვეშ)
print(f"\n{'='*80}")
print("⚠️  TOP-10 კომპანია, სადაც გადახდა = 0 (შესაძლო პრობლემა):")
print(f"{'='*80}")
no_payments_sorted = sorted(no_payments, key=lambda x: x.get('total_effective', 0), reverse=True)
for i, s in enumerate(no_payments_sorted[:10], 1):
    print(f"  {i}. {s['ორგანიზაცია'][:60]} | RS ჯამი: {s['total_effective']:.2f} ₾")
