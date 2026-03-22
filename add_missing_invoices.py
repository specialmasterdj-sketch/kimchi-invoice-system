"""
Add missing invoice headers to seed_data.js for:
1. Rhee Bros invoices for Miami, Coral Springs, Fort Lauderdale
2. Other vendor placeholder headers for ALL branches
3. Remove duplicates
4. Update sw.js cache version
"""
import re
import json
from datetime import datetime

SEED_FILE = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data.js'
SW_FILE = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\sw.js'

# ── Rhee Bros invoices to add (header-only) ─────────────────────────────────

rhee_miami = [
    ("PSI-0170119", "03/06/26"), ("PSI-0169194", "02/24/26"), ("PSI-0167977", "02/07/26"),
    ("PSI-0166932", "01/24/26"), ("PSI-0165691", "01/09/26"), ("PSI-0164846", "12/29/25"),
    ("PSI-0163742", "12/15/25"), ("PSI-0162522", "12/04/25"), ("PSI-0161631", "11/24/25"),
    ("PSI-0160605", "11/13/25"), ("PSI-0159577", "11/03/25"), ("PSI-0158693", "10/24/25"),
    ("PSI-0157740", "10/13/25"), ("PSI-0156837", "10/03/25"), ("PSI-0155201", "09/19/25"),
    ("PSI-0154058", "08/09/25"), ("PSI-0152096", "07/14/25"), ("PSI-0150822", "06/25/25"),
    ("PSI-0149048", "06/11/25"), ("PSI-0148108", "05/30/25"), ("PSI-0147207", "05/19/25"),
    ("PSI-0146284", "05/08/25"), ("PSI-0145501", "04/28/25"), ("PSI-0144718", "04/17/25"),
    ("PSI-0143824", "04/04/25"), ("PSI-0143623", "03/21/25"),
]

rhee_coral = [
    ("PSI-0170362", "03/10/26"), ("PSI-0169017", "02/20/26"), ("PSI-0167979", "02/07/26"),
    ("PSI-0166971", "01/24/26"), ("PSI-0166970", "01/24/26"), ("PSI-0165777", "01/09/26"),
    ("PSI-0164676", "12/26/25"), ("PSI-0163650", "12/14/25"), ("PSI-0162412", "12/03/25"),
    ("PSI-0161421", "11/20/25"), ("PSI-0160442", "11/10/25"), ("PSI-0159451", "10/30/25"),
    ("PSI-0158580", "10/20/25"), ("PSI-0157615", "10/09/25"), ("PSI-0156092", "09/22/25"),
    ("PSI-0155316", "09/15/25"), ("PSI-0155056", "09/08/25"), ("PSI-0153889", "08/25/25"),
    ("PSI-0152960", "08/11/25"), ("PSI-0151882", "07/28/25"), ("PSI-0150901", "06/30/25"),
    ("PSI-0149977", "06/16/25"), ("PSI-0148932", "05/30/25"), ("PSI-0148928", "05/30/25"),
    ("PSI-0147105", "05/15/25"), ("PSI-0141747", "04/03/25"), ("PSI-0140582", "03/10/25"),
]

rhee_ftl = [
    ("PSI-0171141", "03/19/26"), ("PSI-0167845", "03/13/26"), ("PSI-0170086", "03/13/26"),
    ("PSI-0169015", "03/13/26"), ("PSI-0166878", "01/23/26"), ("PSI-0165635", "01/08/26"),
    ("PSI-0164730", "12/27/25"), ("PSI-0163703", "12/16/25"), ("PSI-0162531", "12/05/25"),
    ("PSI-0161541", "11/25/25"), ("PSI-0159550", "10/31/25"), ("PSI-0155197", "09/15/25"),
    ("PSI-0140359", "03/06/25"),
]

# ── Other vendors to add for ALL branches ────────────────────────────────────

other_vendors = [
    ("Wismettac", "WIS"),
    ("Eden", "EDEN"),
    ("Bandi Foods", "BANDI"),
    ("Wei-Chuan", "WC"),
    ("KOCO Trading", "KOCO"),
    ("Well Luck", "WL"),
    ("KC Trading", "KC"),
    ("Two Bros Food", "2BROS"),
    ("POCAS", "POCAS"),
    ("Eastland Food", "EAST"),
    ("Sysco", "SYSCO"),
]

branches = {
    "miami": {"code": "FL116", "customer": "ORIENTAL MART OF MIAMI"},
    "pembroke_pines": {"code": "FL342", "customer": "KIMCHI MART PEMBROKE PINES"},
    "hollywood": {"code": "FL381", "customer": "KIMCHI MART AT HOLLYWOOD"},
    "coral_springs": {"code": "FL417", "customer": "KIMCHI MART CORAL SPRINGS"},
    "fort_lauderdale": {"code": "FL432", "customer": "KIMCHI MART PALM BEACH"},
}

def parse_date(date_display):
    """Convert MM/DD/YY to YYYY-MM-DD"""
    parts = date_display.split("/")
    month, day, year = parts
    year_full = "20" + year
    return f"{year_full}-{month}-{day}"

def make_invoice_entry(inv_num, date_display, vendor, branch_id, customer, source="gmail_search", note=None):
    entry = {
        "invoiceNumber": inv_num,
        "vendor": vendor,
        "date": parse_date(date_display),
        "dateDisplay": date_display,
        "customer": customer,
        "total": 0,
        "branchId": branch_id,
        "items": [],
        "itemCount": 0,
        "source": source,
    }
    if note:
        entry["note"] = note
    return entry

def format_invoice_js(inv):
    """Format a single invoice dict as JS object string matching seed_data.js style."""
    lines = []
    lines.append("  {")
    lines.append(f'   "invoiceNumber": "{inv["invoiceNumber"]}",')
    lines.append(f'   "vendor": "{inv["vendor"]}",')
    lines.append(f'   "date": "{inv["date"]}",')
    lines.append(f'   "dateDisplay": "{inv["dateDisplay"]}",')
    lines.append(f'   "customer": "{inv["customer"]}",')
    lines.append(f'   "total": {inv["total"]},')
    lines.append(f'   "branchId": "{inv["branchId"]}",')
    lines.append(f'   "items": [],')
    lines.append(f'   "itemCount": 0,')
    lines.append(f'   "source": "{inv["source"]}"' + ("," if "note" in inv else ""))
    if "note" in inv:
        lines.append(f'   "note": "{inv["note"]}"')
    lines.append("  }")
    return "\n".join(lines)

# ── Main ─────────────────────────────────────────────────────────────────────

print("Reading seed_data.js...")
with open(SEED_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Get all existing invoice numbers
existing_inv_nums = set(re.findall(r'"invoiceNumber":\s*"([^"]+)"', content))
print(f"Existing invoices: {len(existing_inv_nums)}")

# Build new entries
new_entries = []

# 1. Rhee Bros - Miami
for inv_num, date_disp in rhee_miami:
    if inv_num not in existing_inv_nums:
        new_entries.append(make_invoice_entry(
            inv_num, date_disp, "Rhee Bros", "miami",
            "FL116 - ORIENTAL MART OF MIAMI",
            source="gmail_search",
            note="Rhee Bros invoice header from Gmail"
        ))
        existing_inv_nums.add(inv_num)
    else:
        print(f"  SKIP (exists): {inv_num} (Miami)")

# 2. Rhee Bros - Coral Springs
for inv_num, date_disp in rhee_coral:
    if inv_num not in existing_inv_nums:
        new_entries.append(make_invoice_entry(
            inv_num, date_disp, "Rhee Bros", "coral_springs",
            "FL417 - KIMCHI MART CORAL SPRINGS",
            source="gmail_search",
            note="Rhee Bros invoice header from Gmail"
        ))
        existing_inv_nums.add(inv_num)
    else:
        print(f"  SKIP (exists): {inv_num} (Coral Springs)")

# 3. Rhee Bros - Fort Lauderdale
for inv_num, date_disp in rhee_ftl:
    if inv_num not in existing_inv_nums:
        new_entries.append(make_invoice_entry(
            inv_num, date_disp, "Rhee Bros", "fort_lauderdale",
            "FL432 - KIMCHI MART PALM BEACH",
            source="gmail_search",
            note="Rhee Bros invoice header from Gmail"
        ))
        existing_inv_nums.add(inv_num)
    else:
        print(f"  SKIP (exists): {inv_num} (Fort Lauderdale)")

# 4. Other vendors - placeholder headers for ALL branches
for vendor, prefix in other_vendors:
    for branch_id, branch_info in branches.items():
        inv_num = f"{prefix}-{branch_info['code']}-001"
        if inv_num not in existing_inv_nums:
            new_entries.append(make_invoice_entry(
                inv_num, "03/01/26", vendor, branch_id,
                branch_info["customer"],
                source="gmail_search",
                note="Vendor identified from Gmail - PDF pending"
            ))
            existing_inv_nums.add(inv_num)
        else:
            print(f"  SKIP (exists): {inv_num} ({vendor} / {branch_id})")

print(f"\nNew entries to add: {len(new_entries)}")

if not new_entries:
    print("Nothing to add!")
else:
    # Format new entries as JS
    new_entries_js = ",\n".join(format_invoice_js(e) for e in new_entries)

    # Insert before the closing of the invoices array
    # Find the last `  }` followed by `\n ]` pattern (end of last invoice + end of array)
    # We need to add a comma after the last existing entry and then our new entries
    close_pattern = re.compile(r'(\n  \}\n \]\n\};?\s*)$')
    match = close_pattern.search(content)
    if match:
        insert_pos = match.start()
        new_content = content[:insert_pos] + "\n  },\n" + new_entries_js + "\n ]\n};\n"
        # Remove the trailing `  }` that was part of the last entry since we re-added it
        # Actually let's be more precise - the last entry ends with `  }\n ]\n};`
        # We need to replace `  }\n ]\n};\n` with `  },\n<new entries>\n ]\n};\n`
    else:
        print("ERROR: Could not find insertion point!")
        exit(1)

    # More careful approach: find the exact end
    # The file ends with: ...}\n ]\n};\n
    # Last invoice entry ends with `  }\n`, then ` ]\n};\n`
    end_match = re.search(r'(  \})\n( \]\n\};\n?)$', content)
    if not end_match:
        print("ERROR: Could not find end pattern!")
        exit(1)

    insert_pos = end_match.start(1) + len(end_match.group(1))
    new_content = content[:insert_pos] + ",\n" + new_entries_js + "\n" + content[insert_pos+1:]  # skip the \n after }

    # Update comment line with new counts
    total_invoices = len(existing_inv_nums)
    # Count existing items
    item_count_match = re.search(r'// \d+ invoices, (\d+) items', new_content)
    existing_items = int(item_count_match.group(1)) if item_count_match else 0

    # Update vendor counts in comment
    vendor_counts = {}
    for v_match in re.finditer(r'"vendor":\s*"([^"]+)"', new_content):
        v = v_match.group(1)
        vendor_counts[v] = vendor_counts.get(v, 0) + 1

    vendor_json = json.dumps(vendor_counts, ensure_ascii=False)
    new_content = re.sub(
        r'// \d+ invoices, \d+ items\n// \{[^\n]+\}',
        f'// {total_invoices} invoices, {existing_items} items\n// {vendor_json}',
        new_content
    )

    # Write back
    with open(SEED_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated seed_data.js with {len(new_entries)} new invoices (total: {total_invoices})")

# ── Update sw.js cache version ───────────────────────────────────────────────

print("\nUpdating sw.js cache version...")
with open(SW_FILE, 'r', encoding='utf-8') as f:
    sw_content = f.read()

# Increment version number
version_match = re.search(r"'kimchi-invoice-v(\d+)'", sw_content)
if version_match:
    old_ver = int(version_match.group(1))
    new_ver = old_ver + 1
    sw_content = sw_content.replace(f"'kimchi-invoice-v{old_ver}'", f"'kimchi-invoice-v{new_ver}'")
    with open(SW_FILE, 'w', encoding='utf-8') as f:
        f.write(sw_content)
    print(f"Cache version: v{old_ver} -> v{new_ver}")
else:
    print("WARNING: Could not find cache version in sw.js")

print("\nDone!")
