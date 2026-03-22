import json
import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read existing seed_data.js
seed_path = r"C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data.js"
with open(seed_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the JSON object from seed_data.js
# Find "const SEED_DATA = {" and take from that opening brace
match = re.search(r'const\s+SEED_DATA\s*=\s*\{', content)
json_start = match.start() + match.group().index('{')
json_end = content.rindex('}') + 1
json_str = content[json_start:json_end]

# Parse existing data
seed_data = json.loads(json_str)
existing_invoices = seed_data['invoices']
print(f"Existing invoices: {len(existing_invoices)}")

# Read new vendor invoices
with open(r"C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\new_vendor_invoices.json", 'r', encoding='utf-8') as f:
    new_invoices = json.load(f)
print(f"New invoices to add: {len(new_invoices)}")

# Add new invoices
existing_invoices.extend(new_invoices)

# Count by vendor
vendor_counts = {}
total_items = 0
for inv in existing_invoices:
    v = inv['vendor']
    vendor_counts[v] = vendor_counts.get(v, 0) + 1
    total_items += len(inv.get('items', []))

print(f"\nTotal invoices: {len(existing_invoices)}")
print(f"Total items: {total_items}")
print(f"Vendors ({len(vendor_counts)}):")
for v, c in sorted(vendor_counts.items()):
    print(f"  {v}: {c} invoices")

# Write back
header = f"// Kimchi Mart Invoice System\n// {len(existing_invoices)} invoices, {total_items} items\n// {json.dumps(vendor_counts, ensure_ascii=False)}\n\nconst SEED_DATA = "

# Serialize with compact formatting for items to keep file manageable
output = header + json.dumps(seed_data, ensure_ascii=False, indent=1) + ";\n"

with open(seed_path, 'w', encoding='utf-8') as f:
    f.write(output)

print(f"\nseed_data.js updated successfully!")
print(f"File size: {len(output):,} chars")
