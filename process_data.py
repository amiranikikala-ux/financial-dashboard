import pandas as pd
import glob
import os
import re

def find_header_row(file_path):
    df = pd.read_excel(file_path, header=None, nrows=20)
    for i, row in df.iterrows():
        if row.astype(str).str.contains('თარიღი').any():
            return i
    return 0

def categorize(desc):
    desc = str(desc).lower()
    if re.search(r'ხელფასი|salary|შრომის', desc):
        return 'ხელფასი'
    elif re.search(r'დენი|წყალი|გაზი|telasi|gwp|energo|კომუნალური|დასუფთავება|სილქნეტი|მაგთი|კავშირი|ინტერნეტი', desc):
        return 'კომუნალური'
    elif re.search(r'ბიუჯეტი|გადასახადი|საშემოსავლო|tax|budget|საბაჟო|rs\.ge|შემოსავლების|სახაზინო|ჯარიმა|საურავი', desc):
        return 'გადასახადი'
    elif re.search(r'შპს|ltd|ინვოისი|ზედნადები|payment for|მომწოდებელი|შესყიდვა|purchase|pos|ierc|pay|tbc', desc):
        return 'მომწოდებელი'
    else:
        return 'სხვა'

bog_files = glob.glob('Financial_Analysis/ბოგ ბანკი ამონაწერი/*.xlsx')
tbc_files = glob.glob('Financial_Analysis/თბს ბანკი ამონაწერი/*.xlsx')

all_data = []

# Process BOG
for f in bog_files:
    try:
        header_idx = find_header_row(f)
        df = pd.read_excel(f, header=header_idx)
        
        # Identify columns
        cols = df.columns
        date_col = next((c for c in cols if 'თარიღი' in str(c)), None)
        desc_col = next((c for c in cols if 'დანიშნულება' in str(c) or 'ოპერაციის შინაარსი' in str(c)), None)
        out_col = next((c for c in cols if 'დებეტი' in str(c)), None)
        in_col = next((c for c in cols if 'კრედიტი' in str(c)), None)
        
        if date_col and desc_col:
            temp = pd.DataFrame()
            temp['Date'] = df[date_col]
            temp['Description'] = df[desc_col]
            temp['Paid Out'] = df[out_col] if out_col else None
            temp['Paid In'] = df[in_col] if in_col else None
            temp['Source'] = 'BOG'
            all_data.append(temp)
    except Exception as e:
        print(f"Error BOG {f}: {e}")

# Process TBC
for f in tbc_files:
    try:
        header_idx = find_header_row(f)
        df = pd.read_excel(f, header=header_idx)
        
        cols = df.columns
        date_col = next((c for c in cols if 'თარიღი' in str(c)), None)
        desc_col = next((c for c in cols if 'დანიშნულება' in str(c)), None)
        out_col = next((c for c in cols if 'გასული' in str(c)), None)
        in_col = next((c for c in cols if 'შემოსული' in str(c)), None)
        
        if date_col and desc_col:
            temp = pd.DataFrame()
            temp['Date'] = df[date_col]
            temp['Description'] = df[desc_col]
            temp['Paid Out'] = df[out_col] if out_col else None
            temp['Paid In'] = df[in_col] if in_col else None
            temp['Source'] = 'TBC'
            all_data.append(temp)
    except Exception as e:
        print(f"Error TBC {f}: {e}")

if all_data:
    master = pd.concat(all_data, ignore_index=True)
    master.dropna(subset=['Date', 'Description'], how='all', inplace=True)
    master['Date'] = pd.to_datetime(master['Date'], errors='coerce')
    master = master.dropna(subset=['Date'])
    master['Date'] = master['Date'].dt.strftime('%Y-%m-%d')
    
    master['Category'] = master['Description'].apply(categorize)
    print("Master Data Sample:")
    print(master.head(5).to_markdown())
else:
    print("No data extracted.")
