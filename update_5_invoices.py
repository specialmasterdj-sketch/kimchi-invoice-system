"""Update seed_data.js with 5 freshly parsed Rhee Bros invoices.
Uses Node.js to parse the JS file since it contains JS object notation."""
import json
import subprocess
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

SEED_FILE = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data.js'
PARSED_FILE = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\rhee_5_parsed.json'
TEMP_JSON = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data_temp.json'

# Step 1: Use Node.js to convert seed_data.js to JSON
node_script = f"""
const fs = require('fs');
const code = fs.readFileSync({json.dumps(SEED_FILE)}, 'utf-8');
const fn = new Function(code + '; return SEED_DATA;');
const data = fn();
fs.writeFileSync({json.dumps(TEMP_JSON)}, JSON.stringify(data), 'utf-8');
console.log('Exported ' + data.invoices.length + ' invoices');
"""

result = subprocess.run(['node', '-e', node_script], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Node.js error: {result.stderr}")
    sys.exit(1)
print(result.stdout.strip())

# Step 2: Load both files
with open(TEMP_JSON, 'r', encoding='utf-8') as f:
    seed = json.load(f)

with open(PARSED_FILE, 'r', encoding='utf-8') as f:
    parsed = json.load(f)

# Build lookup of parsed invoices
parsed_lookup = {p['invoiceNumber']: p for p in parsed}

# Step 3: Update matching invoices
for i, inv in enumerate(seed['invoices']):
    inv_num = inv['invoiceNumber']
    if inv_num in parsed_lookup:
        p = parsed_lookup[inv_num]
        old_count = inv.get('itemCount', len(inv.get('items', [])))

        seed['invoices'][i]['items'] = p['items']
        seed['invoices'][i]['itemCount'] = p['itemCount']
        seed['invoices'][i]['total'] = p['total']
        seed['invoices'][i]['date'] = p['date']
        seed['invoices'][i]['dateDisplay'] = p['dateDisplay']
        seed['invoices'][i]['customer'] = p['customer']
        seed['invoices'][i]['branchId'] = p['branchId']
        seed['invoices'][i]['source'] = p['source']
        # Remove gmail stub fields if present
        if 'note' in seed['invoices'][i]:
            del seed['invoices'][i]['note']

        print(f"Updated {inv_num}: {old_count} -> {p['itemCount']} items, branch={p['branchId']}, total=${p['total']:,.2f}")

# Step 4: Recalculate stats
total_invoices = len(seed['invoices'])
total_items = sum(inv.get('itemCount', len(inv.get('items', []))) for inv in seed['invoices'])

vendor_counts = {}
for inv in seed['invoices']:
    v = inv.get('vendor', 'Unknown')
    vendor_counts[v] = vendor_counts.get(v, 0) + 1

print(f"\nTotal invoices: {total_invoices}")
print(f"Total items: {total_items}")

# Step 5: Write back
json_output = json.dumps(seed, indent=1, ensure_ascii=False)

header = f"""// Kimchi Mart Invoice System
// {total_invoices} invoices, {total_items} items
// {json.dumps(vendor_counts)}

const SEED_DATA = """

output = header + json_output + ';\n'

with open(SEED_FILE, 'w', encoding='utf-8') as f:
    f.write(output)

# Clean up temp file
os.remove(TEMP_JSON)

print(f"\nSeed data updated successfully!")
print(f"File size: {os.path.getsize(SEED_FILE):,} bytes")
