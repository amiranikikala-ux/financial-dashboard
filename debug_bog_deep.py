import pandas as pd
import glob
import os

# BOG-ში ლაქტალისის სრული ძებნა ყველა სვეტში
def find_header_row(file_path):
    df = pd.read_excel(file_path, header=None, nrows=20)
    for i, row in df.iterrows():
        if row.astype(str).str.contains('თარიღი').any():
            return i
    return 0

lakt_id = '404898973'

print("="*80)
print("BOG-ში ლაქტალისის ძებნა ყველა სვეტში")
print("="*80)

bog_files = glob.glob('Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx')

for f in bog_files:
    h = find_header_row(f)
    df = pd.read_excel(f, header=h)
    
    print(f"\n--- {os.path.basename(f)} ---")
    
    # ძებნა ID-ით ნებისმიერ სვეტში
    for col in df.columns:
        matches = df[df[col].astype(str).str.contains(lakt_id, na=False)]
        if len(matches) > 0:
            print(f"  ✅ სვეტი '{col}': {len(matches)} ჩანაწერი")
            # ვნახოთ ეს ჩანაწერი სრულად
            for _, row in matches.head(2).iterrows():
                debit = next((row[c] for c in df.columns if 'დებეტი' in str(c) and 'ბრუნვა' not in str(c)), None)
                credit = next((row[c] for c in df.columns if 'კრედიტი' in str(c) and 'ბრუნვა' not in str(c)), None)
                sender_col = next((c for c in df.columns if 'გამგზავნის დასახელება' in str(c)), None)
                sender_id_col = next((c for c in df.columns if 'გამგზავნის საიდენტიფიკაციო' in str(c)), None)
                recv_col = next((c for c in df.columns if 'მიმღების დასახელება' in str(c)), None)
                recv_id_col = next((c for c in df.columns if 'მიმღების საიდენტიფიკაციო' in str(c)), None)
                
                sender = row[sender_col] if sender_col else 'N/A'
                sender_id = row[sender_id_col] if sender_id_col else 'N/A'
                recv = row[recv_col] if recv_col else 'N/A'
                recv_id = row[recv_id_col] if recv_id_col else 'N/A'
                
                print(f"    დებეტი={debit}, კრედიტი={credit}")
                print(f"    გამგზავნი: {sender} (ID: {sender_id})")
                print(f"    მიმღები: {recv} (ID: {recv_id})")
                print()
    
    # ასევე სახელით ძებნა
    for col in df.columns:
        matches = df[df[col].astype(str).str.contains('ლაქტალის|lactalis', case=False, na=False)]
        if len(matches) > 0:
            print(f"  ✅ სახელით '{col}': {len(matches)} ჩანაწერი")

print(f"\n{'='*80}")
print("BOG-ში დებეტის (გასული) სტრუქტურის ანალიზი")
print(f"{'='*80}")

# ვნახოთ BOG-ში დებეტის ჩანაწერების სტატისტიკა
df0 = pd.read_excel(bog_files[0], header=find_header_row(bog_files[0]))
debit_col = next((c for c in df0.columns if 'დებეტი' in str(c) and 'ბრუნვა' not in str(c)), None)
recv_id_col = next((c for c in df0.columns if 'მიმღების საიდენტიფიკაციო' in str(c)), None)
sender_id_col = next((c for c in df0.columns if 'გამგზავნის საიდენტიფიკაციო' in str(c)), None)

if debit_col:
    debit_rows = df0[df0[debit_col].notna()]
    print(f"\nპირველ ფაილში სულ დებეტის ჩანაწერები: {len(debit_rows)}")
    if recv_id_col:
        has_recv = debit_rows[debit_rows[recv_id_col].notna()]
        no_recv = debit_rows[debit_rows[recv_id_col].isna()]
        print(f"  მათთგან მიმღების ID აქვს: {len(has_recv)}")
        print(f"  მათთგან მიმღების ID არ აქვს: {len(no_recv)}")
    if sender_id_col:
        has_sender = debit_rows[debit_rows[sender_id_col].notna()]
        print(f"  მათთგან გამგზავნის ID აქვს: {len(has_sender)}")
    
    # ნახოთ დებეტის ჩანაწერი სადაც მიმღები != ჩვენი კომპანია
    if recv_id_col:
        external = debit_rows[(debit_rows[recv_id_col].notna()) & (~debit_rows[recv_id_col].astype(str).str.contains('400333858', na=False))]
        print(f"\n  დებეტი სადაც მიმღები != ჯეო ფუდთაიმი: {len(external)}")
        if len(external) > 0:
            print(f"  პირველი 3 მაგალითი:")
            for _, row in external.head(3).iterrows():
                recv = row[next((c for c in df0.columns if 'მიმღების დასახელება' in str(c)), recv_id_col)]
                amt = row[debit_col]
                print(f"    მიმღები: {recv}, თანხა: {amt}")
