import re

plan_path = r"C:\Users\tengiz\.gemini\antigravity\brain\babef18e-5231-4a6b-9902-2311decdd657\implementation_plan.md"
table_path = r"c:\Users\tengiz\OneDrive\Desktop\AI აგენტი\rs_aggregated_preview_v2.md"

with open(plan_path, 'r', encoding='utf-8') as f:
    plan_content = f.read()

with open(table_path, 'r', encoding='utf-8') as f:
    new_table = f.read()

# Replace everything from the first '|' up to '## Proposed Changes'
pattern = re.compile(r'(\| ორგანიზაცია.*?)(?=\n\n## Proposed Changes)', re.DOTALL)
new_plan_content = pattern.sub(new_table, plan_content)

with open(plan_path, 'w', encoding='utf-8') as f:
    f.write(new_plan_content)

print("Updated plan!")
