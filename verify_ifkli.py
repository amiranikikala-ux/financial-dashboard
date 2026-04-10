import pandas as pd
import glob

# ყველა TBC ფაილში ვეძებთ იფქლს სახელით
tbc_files = glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')
total = 0.0
count = 0

for f in tbc_files:
    df = pd.read_excel(f)
    ifkli = df[df['პარტნიორი'].astype(str).str.contains('იფქლი', case=False, na=False)]
    if len(ifkli) > 0:
        amt = pd.to_numeric(ifkli['გასული თანხა'], errors='coerce').sum()
        print(f"{f}: {len(ifkli)} ჩანაწერი, გასული: {amt:.2f}")
        total += amt
        count += len(ifkli)

print(f"\nსულ TBC-ში იფქლი: {count} ჩანაწერი, ჯამი: {total:.2f}")

# ახლა data.json-ში რა წერია
import json
with open('rs-dashboard/public/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for s in data['suppliers']:
    if 'იფქლი' in s.get('ორგანიზაცია', ''):
        print(f"\nDashboard-ში იფქლი:")
        print(f"  რეალური ჯამი: {s['total_effective']:.2f}")
        print(f"  გადახდილი:    {s['total_paid']:.2f}")
        print(f"  დავალიანება:  {s['total_debt']:.2f}")
        break
