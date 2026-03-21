"""
Update seed_data.js: replace header-only entries with real parsed data.
Uses JSON-aware approach to avoid duplicates.

Sources:
1. PDFs from drive-download ZIPs (parsed with pdfplumber)
2. TXT files from KIMCHI_MART_INVOICES with pre-parsed data
"""

import pdfplumber
import json
import re
import os
import sys
import zipfile
import tempfile
import shutil

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

SEED_DATA_PATH = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data.js'

ZIP_FILES = [
    r'C:\Users\speci\Downloads\drive-download-20260321T055444Z-1-001.zip',
    r'C:\Users\speci\Downloads\drive-download-20260321T055627Z-1-001.zip',
]

# TXT files with parsed item data
TXT_FILES = [
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\FORT LAUDERDALE (FL432)\Rhee Bros\RheeBros_PSI-0171141_03-19-26.txt',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154058_08-09-25.txt',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154059_08-09-25.txt',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154158_08-11-25.txt',
]

BRANCH_MAP = {
    'FL116': 'miami',
    'FL342': 'pembroke_pines',
    'FL351': 'pembroke_pines',
    'FL381': 'hollywood',
    'FL417': 'coral_springs',
    'FL432': 'fort_lauderdale',
}

ITEM_NO_PATTERN = re.compile(r'^(\d{4,5}[A-Z]{1,2})\s+')
INVOICE_PATTERN = re.compile(r'PSI-(\d{7})')
DATE_PATTERN = re.compile(r'Invoice Date:\s*(\d{2}/\d{2}/\d{2,4})')
CUSTOMER_PATTERN = re.compile(r'Customer No\.\s*(FL\d{3})')
TOTAL_PATTERN = re.compile(r'Total\s+\$?([\d,]+\.\d{2})')


def parse_price(s):
    try:
        return float(s.replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0


def parse_item_line(line):
    m = ITEM_NO_PATTERN.match(line)
    if not m:
        return None
    item_no = m.group(1)
    rest = line[m.end():].strip()
    if 'Shipping' in rest or 'Fuel' in rest or 'Freight' in rest or 'Delivery' in rest:
        return None

    price_pattern = re.compile(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$')
    pm = price_pattern.search(rest)
    if not pm:
        return None

    unit_price = parse_price(pm.group(1))
    each_price = parse_price(pm.group(2))
    total_price = parse_price(pm.group(3))
    before_prices = rest[:pm.start()].strip()

    type_pattern = re.compile(r'\s+(Dry|Ref|Frz|dry|ref|frz|DRY|REF|FRZ)\s*$')
    tm = type_pattern.search(before_prices)
    if tm:
        before_prices = before_prices[:tm.start()].strip()

    um_pattern = re.compile(r'\s+(Case|Bag|Box|Each|Pail|Drum|Roll|Pack|Tray|Bundle|Bottle|Jar|Pcs|Set|Tub|Can|Unit|Sack|Bucket|Pound|case|bag|box|pound)\s*$', re.IGNORECASE)
    um_match = um_pattern.search(before_prices)
    if um_match:
        before_prices = before_prices[:um_match.start()].strip()

    qty_pattern = re.compile(r'\s+(\d+(?:\.\d+)?)\s*$')
    qty_match = qty_pattern.search(before_prices)
    qty = 0
    if qty_match:
        qty_val = float(qty_match.group(1))
        qty = int(qty_val) if qty_val == int(qty_val) else qty_val
        before_prices = before_prices[:qty_match.start()].strip()

    UNITS = r'LB|OZ|GAL|ML|L|G|KG|CT|SHT|PC|EA|LITER|FL OZ|PR|#'
    size_pattern = re.compile(r'\s+((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$', re.IGNORECASE)
    size_match = size_pattern.search(before_prices)
    size = ''
    if size_match:
        size = size_match.group(1).strip()
        before_prices = before_prices[:size_match.start()].strip()
    if not size:
        glued_size = re.compile(r'([)\w])((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$', re.IGNORECASE)
        gm = glued_size.search(before_prices)
        if gm:
            size = gm.group(2).strip()
            before_prices = before_prices[:gm.start() + 1].strip()
    if not size:
        no_unit_size = re.compile(r'\s+((?:\d+X)+\d+(?:\.\d+)?)\s*$')
        num = no_unit_size.search(before_prices)
        if num:
            size = num.group(1).strip()
            before_prices = before_prices[:num.start()].strip()

    parts = before_prices.split(None, 1)
    brand = parts[0] if parts else ''
    description = parts[1] if len(parts) > 1 else ''

    if not size and description:
        broad_size = re.compile(r'\s+((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$', re.IGNORECASE)
        bm = broad_size.search(description)
        if bm:
            size = bm.group(1).strip()
            description = description[:bm.start()].strip()
    if not size and description:
        glued_size2 = re.compile(r'([)\w])((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$', re.IGNORECASE)
        gm2 = glued_size2.search(description)
        if gm2:
            size = gm2.group(2).strip()
            description = description[:gm2.start() + 1].strip()

    return {
        'itemNo': item_no,
        'brand': brand,
        'description': description,
        'size': size,
        'qty': qty,
        'unitPrice': unit_price,
        'eachPrice': each_price,
        'totalPrice': total_price,
    }


def parse_invoice_pdf(pdf_path):
    filename = os.path.basename(pdf_path)
    if 'Statement' in filename or filename.startswith('SR-'):
        return None
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        return None

    all_text = ''
    all_lines = []
    try:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + '\n'
                all_lines.extend(text.split('\n'))
    except:
        pdf.close()
        return None
    pdf.close()

    inv_match = INVOICE_PATTERN.search(all_text)
    if not inv_match:
        return None
    invoice_number = f"PSI-{inv_match.group(1)}"

    date_match = DATE_PATTERN.search(all_text)
    date_display = ''
    date_iso = ''
    if date_match:
        date_display = date_match.group(1)
        parts = date_display.split('/')
        month, day = parts[0], parts[1]
        year = parts[2]
        if len(year) == 2:
            year = '20' + year
        date_iso = f"{year}-{month}-{day}"

    cust_match = CUSTOMER_PATTERN.search(all_text)
    customer_code = ''
    branch_id = ''
    customer_name = ''
    if cust_match:
        customer_code = cust_match.group(1)
        branch_id = BRANCH_MAP.get(customer_code, customer_code.lower())

    total = 0.0
    total_match = TOTAL_PATTERN.search(all_text)
    if total_match:
        total = parse_price(total_match.group(1))

    items = []
    items_by_no = {}
    for line in all_lines:
        line = line.strip()
        if not line:
            continue
        item = parse_item_line(line)
        if item is None:
            continue
        if item['unitPrice'] <= 2.0:
            continue
        item_no = item['itemNo']
        if item_no in items_by_no:
            existing = items_by_no[item_no]
            if item['unitPrice'] > existing['unitPrice']:
                items_by_no[item_no] = item
        else:
            items_by_no[item_no] = item

    items = list(items_by_no.values())

    return {
        'invoiceNumber': invoice_number,
        'vendor': 'Rhee Bros',
        'date': date_iso,
        'dateDisplay': date_display,
        'customer': customer_name,
        'total': total,
        'branchId': branch_id,
        'items': items,
        'itemCount': len(items),
        'source': filename,
    }


def parse_txt_invoice(txt_path):
    filename = os.path.basename(txt_path)
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    invoice_number = ''
    date_display = ''
    date_iso = ''
    customer = ''
    total = 0.0
    branch_id = ''
    items = []
    header_done = False

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('INVOICE:'):
            invoice_number = line.split(':', 1)[1].strip()
        elif line.startswith('DATE:'):
            date_display = line.split(':', 1)[1].strip()
            parts = date_display.split('/')
            if len(parts) == 3:
                month, day, year = parts
                if len(year) == 2:
                    year = '20' + year
                date_iso = f"{year}-{month}-{day}"
        elif line.startswith('CUSTOMER:'):
            customer = line.split(':', 1)[1].strip()
            fl_match = re.search(r'FL(\d{3})', customer)
            if fl_match:
                code = 'FL' + fl_match.group(1)
                branch_id = BRANCH_MAP.get(code, code.lower())
        elif line.startswith('TOTAL:'):
            total_str = line.split('$', 1)
            if len(total_str) > 1:
                total = parse_price(total_str[1].strip())
        elif line.startswith('No.|'):
            header_done = True
            continue
        elif line.startswith('NOTE:'):
            continue
        elif header_done and '|' in line:
            parts = line.split('|')
            if len(parts) >= 10:
                item_no = parts[0].strip()
                brand = parts[1].strip()
                description = parts[2].strip()
                size = parts[3].strip()
                qty_str = parts[4].strip()
                unit_str = parts[7].strip()
                each_str = parts[8].strip()
                total_str = parts[9].strip()

                if not brand and not description:
                    continue
                try:
                    qty = int(qty_str) if qty_str else 0
                except ValueError:
                    try:
                        qty = float(qty_str)
                    except ValueError:
                        qty = 0

                unit_price = parse_price(unit_str) if unit_str else 0.0
                each_price = parse_price(each_str) if each_str else 0.0
                total_price = parse_price(total_str) if total_str else 0.0

                if unit_price <= 2.0:
                    continue

                items.append({
                    'itemNo': item_no,
                    'brand': brand,
                    'description': description,
                    'size': size,
                    'qty': qty,
                    'unitPrice': unit_price,
                    'eachPrice': each_price,
                    'totalPrice': total_price,
                })

    return {
        'invoiceNumber': invoice_number,
        'vendor': 'Rhee Bros',
        'date': date_iso,
        'dateDisplay': date_display,
        'customer': customer,
        'total': total,
        'branchId': branch_id,
        'items': items,
        'itemCount': len(items),
        'source': filename,
    }


def main():
    print("=" * 60)
    print("STEP 1: Parse PDFs from drive-download ZIPs")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp(prefix='rhee_pdfs_')
    all_parsed = {}  # keyed by invoiceNumber

    for zip_path in ZIP_FILES:
        if not os.path.exists(zip_path):
            print(f"  ZIP not found: {zip_path}")
            continue
        print(f"Extracting: {os.path.basename(zip_path)}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.pdf') and 'PSI' in name:
                    zf.extract(name, temp_dir)
                    pdf_path = os.path.join(temp_dir, name)
                    result = parse_invoice_pdf(pdf_path)
                    if result and result['itemCount'] > 0:
                        inv_num = result['invoiceNumber']
                        if inv_num not in all_parsed or result['itemCount'] > all_parsed[inv_num]['itemCount']:
                            all_parsed[inv_num] = result

    print(f"\nParsed {len(all_parsed)} invoices from PDFs")

    # Branch breakdown
    branch_counts = {}
    for r in all_parsed.values():
        bid = r['branchId']
        if bid not in branch_counts:
            branch_counts[bid] = 0
        branch_counts[bid] += 1
    for bid, count in sorted(branch_counts.items()):
        print(f"  {bid}: {count} invoices")

    print("\n" + "=" * 60)
    print("STEP 2: Parse TXT files")
    print("=" * 60)

    for txt_path in TXT_FILES:
        if not os.path.exists(txt_path):
            continue
        result = parse_txt_invoice(txt_path)
        if result and result['itemCount'] > 0:
            inv_num = result['invoiceNumber']
            if inv_num not in all_parsed or all_parsed[inv_num]['itemCount'] == 0:
                all_parsed[inv_num] = result
                print(f"  TXT: {inv_num} -> {result['branchId']}, {result['itemCount']} items")

    print(f"\nTotal parsed invoices with items: {len(all_parsed)}")

    print("\n" + "=" * 60)
    print("STEP 3: Load and update seed_data.js")
    print("=" * 60)

    with open(SEED_DATA_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract JSON portion
    js_start = content.find('{', content.find('const SEED_DATA'))
    depth = 0
    js_end = -1
    for i in range(js_start, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                js_end = i + 1
                break

    prefix = content[:js_start]
    suffix = content[js_end:]
    json_str = content[js_start:js_end]

    data = json.loads(json_str)
    invoices = data['invoices']

    print(f"Loaded {len(invoices)} invoices from seed_data.js")

    # Count empty before
    empty_before = sum(1 for inv in invoices if len(inv.get('items', [])) == 0)
    print(f"Empty items entries before: {empty_before}")

    # Update empty entries with parsed data
    replacements = 0
    removed = 0
    for i, inv in enumerate(invoices):
        if len(inv.get('items', [])) == 0:
            inv_num = inv['invoiceNumber']
            if inv_num in all_parsed:
                parsed = all_parsed[inv_num]
                if parsed['itemCount'] > 0:
                    # Update in place
                    invoices[i]['items'] = parsed['items']
                    invoices[i]['itemCount'] = parsed['itemCount']
                    if parsed['total'] > 0:
                        invoices[i]['total'] = parsed['total']
                    if parsed['customer']:
                        invoices[i]['customer'] = parsed['customer']
                    invoices[i]['source'] = parsed['source']
                    # Remove the "note" field if present
                    if 'note' in invoices[i]:
                        del invoices[i]['note']
                    replacements += 1
                    print(f"  REPLACED: {inv_num} ({inv['branchId']}) -> {parsed['itemCount']} items")

    # Remove header-only entries that are Rhee Bros with no data and note="header only"
    # These are the ones where we have no PDF
    new_invoices = []
    for inv in invoices:
        if (len(inv.get('items', [])) == 0 and
            inv.get('vendor') == 'Rhee Bros' and
            'header only' in inv.get('note', '')):
            removed += 1
            print(f"  REMOVED: {inv['invoiceNumber']} ({inv['branchId']}) - header only, no PDF available")
        else:
            new_invoices.append(inv)

    data['invoices'] = new_invoices

    # Also remove duplicate invoices (keep first occurrence with most items)
    seen = {}
    deduped = []
    dupes_removed = 0
    for inv in data['invoices']:
        inv_num = inv['invoiceNumber']
        if inv_num in seen:
            # Keep the one with more items
            existing_idx = seen[inv_num]
            existing = deduped[existing_idx]
            if len(inv.get('items', [])) > len(existing.get('items', [])):
                deduped[existing_idx] = inv
            dupes_removed += 1
        else:
            seen[inv_num] = len(deduped)
            deduped.append(inv)

    data['invoices'] = deduped

    # Count totals
    total_invoices = len(data['invoices'])
    total_items = sum(len(inv.get('items', [])) for inv in data['invoices'])
    empty_after = sum(1 for inv in data['invoices'] if len(inv.get('items', [])) == 0)

    print(f"\nReplacements: {replacements}")
    print(f"Removed (header only): {removed}")
    print(f"Duplicates removed: {dupes_removed}")
    print(f"Empty items after: {empty_after}")
    print(f"Total invoices: {total_invoices}")
    print(f"Total items: {total_items}")

    # Rebuild seed_data.js
    # Format the JSON nicely
    json_output = json.dumps(data, indent=1, ensure_ascii=False)

    # Build the new file
    # Update the comment header
    vendor_counts = {}
    for inv in data['invoices']:
        v = inv['vendor']
        vendor_counts[v] = vendor_counts.get(v, 0) + 1

    header = f'''// Kimchi Mart Invoice System
// {total_invoices} invoices, {total_items} items
// {json.dumps(vendor_counts, ensure_ascii=False)}

const SEED_DATA = {json_output};
'''

    with open(SEED_DATA_PATH, 'w', encoding='utf-8') as f:
        f.write(header)

    print(f"\nSaved: {SEED_DATA_PATH}")
    print(f"File size: {os.path.getsize(SEED_DATA_PATH):,} bytes")

    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except:
        pass

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == '__main__':
    main()
