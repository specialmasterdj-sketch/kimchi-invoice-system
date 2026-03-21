"""
Parse Rhee Bros invoice PDFs from drive-download ZIPs and local .txt files,
then update seed_data.js with real item data.

Targets: Miami (FL116), Coral Springs (FL417), Fort Lauderdale (FL432)
"""

import pdfplumber
import json
import re
import os
import sys
import zipfile
import tempfile
import shutil

# Force UTF-8 output
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

SEED_DATA_PATH = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data.js'

ZIP_FILES = [
    r'C:\Users\speci\Downloads\drive-download-20260321T055444Z-1-001.zip',
    r'C:\Users\speci\Downloads\drive-download-20260321T055627Z-1-001.zip',
    r'C:\Users\speci\Downloads\drive-download-20260321T064118Z-1-001.zip',
]

# Also check unsorted PDFs
UNSORTED_PDFS = [
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\_UNSORTED\RheeBros_Sales Invoice 5002092.pdf',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\_UNSORTED\RheeBros_Sales Invoice 5002117.pdf',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\_UNSORTED\RheeBros_PSI-0171177.pdf',
]

# Also check existing Miami PDFs
MIAMI_PDFS = [
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_FL342.pdf',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154058_08-09-25.pdf',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154059_08-09-25.pdf',
    r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154158_08-11-25.pdf',
]

# TXT files with parsed item data
TXT_FILES = {
    'coral_springs': [
        r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\CORAL SPRINGS (FL417)\Rhee Bros\RheeBros_PSI-0170362_03-10-26.txt',
    ],
    'fort_lauderdale': [
        r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\FORT LAUDERDALE (FL432)\Rhee Bros\RheeBros_PSI-0171141_03-19-26.txt',
        r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\FORT LAUDERDALE (FL432)\Rhee Bros\RheeBros_PSI-0167845_02-06-26.txt',
    ],
    'miami': [
        r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154058_08-09-25.txt',
        r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154059_08-09-25.txt',
        r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Rhee Bros\RheeBros_PSI-0154158_08-11-25.txt',
    ],
}

BRANCH_MAP = {
    'FL116': 'miami',
    'FL342': 'miami',        # some Miami invoices use FL342
    'FL351': 'pembroke_pines',
    'FL381': 'hollywood',
    'FL417': 'coral_springs',
    'FL432': 'fort_lauderdale',
}

BRANCH_NAMES = {
    'miami': 'KIMCHI MART AT MIAMI',
    'pembroke_pines': 'KIMCHI MART',
    'hollywood': 'KIMCHI MART AT HOLLYWOOD',
    'coral_springs': 'KIMCHI MART AT CORAL SPRINGS',
    'fort_lauderdale': 'KIMCHI MART AT FT. LAUDERDALE',
}

# Target branches we need data for
TARGET_BRANCHES = {'miami', 'coral_springs', 'fort_lauderdale'}

# Pattern for item lines: starts with item number (digits + letters)
ITEM_NO_PATTERN = re.compile(r'^(\d{4,5}[A-Z]{1,2})\s+')
INVOICE_PATTERN = re.compile(r'PSI-(\d{7})')
DATE_PATTERN = re.compile(r'Invoice Date:\s*(\d{2}/\d{2}/\d{2,4})')
CUSTOMER_PATTERN = re.compile(r'Customer No\.\s*(FL\d{3})')
TOTAL_PATTERN = re.compile(r'Total\s+\$?([\d,]+\.\d{2})')

# Also check for customer in ship-to or other patterns
CUSTOMER_ALT_PATTERN = re.compile(r'(FL\d{3})')
# Check for ORIENTAL MART pattern (used for Miami/FL116)
ORIENTAL_PATTERN = re.compile(r'ORIENTAL\s+MART', re.IGNORECASE)
# Check for MIAMI pattern
MIAMI_PATTERN = re.compile(r'MIAMI', re.IGNORECASE)
# Check for CORAL SPRINGS
CORAL_PATTERN = re.compile(r'CORAL\s+SPRINGS', re.IGNORECASE)
# Check for FT.? LAUDERDALE or PALM BEACH or FL432
FTLAUD_PATTERN = re.compile(r'(FT\.?\s*LAUDERDALE|PALM\s*BEACH|FL432)', re.IGNORECASE)


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
    size_pattern = re.compile(
        r'\s+((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$',
        re.IGNORECASE
    )
    size_match = size_pattern.search(before_prices)
    size = ''
    if size_match:
        size = size_match.group(1).strip()
        before_prices = before_prices[:size_match.start()].strip()

    if not size:
        glued_size = re.compile(
            r'([)\w])((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$',
            re.IGNORECASE
        )
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
        broad_size = re.compile(
            r'\s+((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$',
            re.IGNORECASE
        )
        bm = broad_size.search(description)
        if bm:
            size = bm.group(1).strip()
            description = description[:bm.start()].strip()

    if not size and description:
        glued_size2 = re.compile(
            r'([)\w])((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$',
            re.IGNORECASE
        )
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
    """Parse a single Rhee Bros invoice PDF."""
    filename = os.path.basename(pdf_path)
    if 'Statement' in filename or filename.startswith('SR-'):
        return None

    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        print(f"  ERROR opening {filename}: {e}")
        return None

    all_text = ''
    all_lines = []

    try:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + '\n'
                all_lines.extend(text.split('\n'))
    except Exception as e:
        print(f"  ERROR reading {filename}: {e}")
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
        customer_name = BRANCH_NAMES.get(branch_id, customer_code)
    else:
        # Try to determine branch from text content
        if ORIENTAL_PATTERN.search(all_text) or MIAMI_PATTERN.search(all_text):
            branch_id = 'miami'
            customer_name = 'ORIENTAL MART OF MIAMI'
        elif CORAL_PATTERN.search(all_text):
            branch_id = 'coral_springs'
            customer_name = 'KIMCHI MART AT CORAL SPRINGS'
        elif FTLAUD_PATTERN.search(all_text):
            branch_id = 'fort_lauderdale'
            customer_name = 'KIMCHI MART AT FT. LAUDERDALE'

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
    """Parse a .txt file with pre-parsed item data."""
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
            # Extract branch code from customer
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
                # UM = parts[5], Type = parts[6]
                unit_str = parts[7].strip()
                each_str = parts[8].strip()
                total_str = parts[9].strip()

                # Skip empty items (item number only, no data)
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
    print("STEP 1: Extract and parse PDFs from drive-download ZIPs")
    print("=" * 60)

    # Create temp directory for extracted PDFs
    temp_dir = tempfile.mkdtemp(prefix='rhee_pdfs_')
    print(f"Temp dir: {temp_dir}")

    all_pdfs = []

    # Extract PDFs from ZIPs
    for zip_path in ZIP_FILES:
        if not os.path.exists(zip_path):
            print(f"  ZIP not found: {zip_path}")
            continue
        print(f"\nExtracting: {os.path.basename(zip_path)}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.pdf') and 'PSI' in name:
                    zf.extract(name, temp_dir)
                    all_pdfs.append(os.path.join(temp_dir, name))
                    print(f"  Extracted: {name}")

    # Add local PDFs
    for pdf_path in UNSORTED_PDFS + MIAMI_PDFS:
        if os.path.exists(pdf_path):
            all_pdfs.append(pdf_path)
            print(f"  Local PDF: {os.path.basename(pdf_path)}")

    print(f"\nTotal PDFs to parse: {len(all_pdfs)}")

    # Parse all PDFs
    parsed_from_pdf = {}  # keyed by invoiceNumber
    for pdf_path in all_pdfs:
        result = parse_invoice_pdf(pdf_path)
        if result and result['itemCount'] > 0:
            inv_num = result['invoiceNumber']
            # Keep the one with more items if duplicate
            if inv_num not in parsed_from_pdf or result['itemCount'] > parsed_from_pdf[inv_num]['itemCount']:
                parsed_from_pdf[inv_num] = result

    print(f"\nParsed {len(parsed_from_pdf)} unique invoices from PDFs")

    # Branch breakdown
    branch_counts = {}
    for r in parsed_from_pdf.values():
        bid = r['branchId']
        if bid not in branch_counts:
            branch_counts[bid] = {'invoices': 0, 'items': 0}
        branch_counts[bid]['invoices'] += 1
        branch_counts[bid]['items'] += r['itemCount']
    for bid, counts in sorted(branch_counts.items()):
        print(f"  {bid}: {counts['invoices']} invoices, {counts['items']} items")

    print("\n" + "=" * 60)
    print("STEP 2: Parse TXT files with item data")
    print("=" * 60)

    parsed_from_txt = {}
    for branch_id, txt_files in TXT_FILES.items():
        for txt_path in txt_files:
            if not os.path.exists(txt_path):
                print(f"  TXT not found: {txt_path}")
                continue
            result = parse_txt_invoice(txt_path)
            if result:
                inv_num = result['invoiceNumber']
                parsed_from_txt[inv_num] = result
                print(f"  {os.path.basename(txt_path)}: {inv_num}, {result['itemCount']} items, branch={result['branchId']}")

    print(f"\nParsed {len(parsed_from_txt)} invoices from TXT files")

    # Merge: PDF data takes precedence over TXT, but TXT fills gaps
    all_parsed = dict(parsed_from_pdf)
    for inv_num, result in parsed_from_txt.items():
        if inv_num not in all_parsed:
            all_parsed[inv_num] = result
        elif all_parsed[inv_num]['itemCount'] == 0 and result['itemCount'] > 0:
            all_parsed[inv_num] = result

    print(f"\nTotal unique parsed invoices: {len(all_parsed)}")

    # Show target branches
    for target in sorted(TARGET_BRANCHES):
        target_invoices = [r for r in all_parsed.values() if r['branchId'] == target and r['itemCount'] > 0]
        print(f"\n  {target}: {len(target_invoices)} invoices with items")
        for r in target_invoices:
            print(f"    {r['invoiceNumber']}: {r['itemCount']} items, ${r['total']:,.2f}")

    print("\n" + "=" * 60)
    print("STEP 3: Update seed_data.js")
    print("=" * 60)

    # Read seed_data.js
    with open(SEED_DATA_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all header-only entries and their line positions
    # We'll work with the JSON portion
    # First, find the invoices array
    lines = content.split('\n')

    # Track replacements
    replacements_made = 0
    removals = 0

    # Find all entries with "items": [] and process them
    # We need to find each invoice block that has "items": []
    i = 0
    new_lines = []
    while i < len(lines):
        line = lines[i]

        # Look for start of an invoice entry with empty items
        # Pattern: we look ahead to find "items": []
        if '"invoiceNumber":' in line and i + 10 < len(lines):
            # Check if this block has empty items
            block_start = i
            # Go back to find the opening brace
            while block_start > 0 and '{' not in lines[block_start]:
                block_start -= 1

            # Find the closing of this invoice object
            brace_depth = 0
            block_end = block_start
            found_block = False
            for j in range(block_start, min(block_start + 500, len(lines))):
                for ch in lines[j]:
                    if ch == '{':
                        brace_depth += 1
                    elif ch == '}':
                        brace_depth -= 1
                        if brace_depth == 0:
                            block_end = j
                            found_block = True
                            break
                if found_block:
                    break

            if found_block:
                # Extract the block text to check if it has empty items
                block_text = '\n'.join(lines[block_start:block_end + 1])

                if '"items": []' in block_text:
                    # Extract invoice number
                    inv_match = re.search(r'"invoiceNumber":\s*"([^"]+)"', block_text)
                    if inv_match:
                        inv_num = inv_match.group(1)

                        # Check if we have parsed data for this invoice
                        if inv_num in all_parsed and all_parsed[inv_num]['itemCount'] > 0:
                            parsed = all_parsed[inv_num]
                            # Replace the block with full data
                            # Build the replacement
                            items_json = json.dumps(parsed['items'], indent=5, ensure_ascii=False)
                            # Indent each line by 4 spaces
                            items_lines = items_json.split('\n')
                            items_formatted = '\n'.join('    ' + l for l in items_lines)

                            # Check if there's a trailing comma
                            trailing = ''
                            end_line = lines[block_end].rstrip()
                            if end_line.endswith('},'):
                                trailing = ','

                            replacement = f'''  {{
   "invoiceNumber": "{parsed['invoiceNumber']}",
   "vendor": "Rhee Bros",
   "date": "{parsed['date']}",
   "dateDisplay": "{parsed['dateDisplay']}",
   "customer": "{parsed['customer']}",
   "total": {parsed['total']},
   "branchId": "{parsed['branchId']}",
   "items": {json.dumps(parsed['items'], indent=4, ensure_ascii=False).replace(chr(10), chr(10) + '   ')},
   "itemCount": {parsed['itemCount']},
   "source": "{parsed['source']}"
  }}{trailing}'''

                            # Skip the old block lines
                            # Add everything before the block that wasn't added yet
                            # We already added lines up to the current line
                            # We need to handle this differently...
                            # Let's just mark lines for replacement
                            pass

        new_lines.append(line)
        i += 1

    # The line-by-line approach is complex for a 267K line file.
    # Let's use a different strategy: regex replacement on the full text.

    print("Using regex replacement strategy...")

    # Find all invoice blocks with "items": []
    # Pattern: match from opening { to closing } of invoice objects with empty items
    # This is tricky with regex on nested JSON, so let's use a JSON-aware approach

    # Extract just the invoices array as JSON
    # The file starts with comments and "const SEED_DATA = {"
    # Find the invoices array start

    inv_array_start = content.find('"invoices": [')
    if inv_array_start == -1:
        inv_array_start = content.find('"invoices":[')

    # Parse using a state machine to find each invoice object
    # Actually, let's use a simpler approach: find each header-only block and replace it

    # Strategy: for each known empty invoice, find it and replace
    empty_invoice_pattern = re.compile(
        r'(\s*\{[^{}]*?"invoiceNumber":\s*"(PSI-[^"]+)"[^{}]*?"items":\s*\[\][^{}]*?\})',
        re.DOTALL
    )

    matches = list(empty_invoice_pattern.finditer(content))
    print(f"Found {len(matches)} empty invoice entries")

    # Process replacements from end to start so positions don't shift
    for match in reversed(matches):
        inv_num = match.group(2)
        full_match = match.group(1)

        if inv_num in all_parsed and all_parsed[inv_num]['itemCount'] > 0:
            parsed = all_parsed[inv_num]

            # Build items JSON
            items_str = json.dumps(parsed['items'], indent=4, ensure_ascii=False)
            # Add proper indentation (3 spaces for items array content)
            items_lines = items_str.split('\n')
            indented_items = items_lines[0]
            for il in items_lines[1:]:
                indented_items += '\n   ' + il

            replacement = f'''  {{
   "invoiceNumber": "{parsed['invoiceNumber']}",
   "vendor": "Rhee Bros",
   "date": "{parsed['date']}",
   "dateDisplay": "{parsed['dateDisplay']}",
   "customer": "{parsed['customer']}",
   "total": {parsed['total']},
   "branchId": "{parsed['branchId']}",
   "items": {indented_items},
   "itemCount": {parsed['itemCount']},
   "source": "{parsed['source']}"
  }}'''

            # Check if original had trailing comma
            end_pos = match.end()
            # Look at what comes after
            after = content[end_pos:end_pos + 5].strip()

            start_pos = match.start()
            # Preserve the leading whitespace/comma
            before_char = content[start_pos - 1] if start_pos > 0 else ''

            content = content[:match.start()] + '\n' + replacement + content[match.end():]
            replacements_made += 1
            print(f"  REPLACED: {inv_num} ({parsed['itemCount']} items, branch={parsed['branchId']})")
        else:
            # No data available - check if this is a target branch
            branch_match = re.search(r'"branchId":\s*"([^"]+)"', full_match)
            if branch_match:
                bid = branch_match.group(1)
                if bid in TARGET_BRANCHES:
                    print(f"  NO DATA for {inv_num} (branch={bid}) - keeping as-is")
                    removals += 1

    # Also check for the non-PSI empty entries (Wang, etc.)
    # These have total:0.0 but may have items - skip them

    print(f"\nReplacements made: {replacements_made}")
    print(f"Header-only entries without data: {removals}")

    # Update the comment at the top with new counts
    # Count total invoices and items
    item_count_matches = re.findall(r'"itemCount":\s*(\d+)', content)
    total_items = sum(int(x) for x in item_count_matches)
    invoice_count = len(item_count_matches)

    # Update the comment
    old_comment = re.search(r'^// (\d+) invoices, (\d+) items', content, re.MULTILINE)
    if old_comment:
        content = content.replace(
            old_comment.group(0),
            f'// {invoice_count} invoices, {total_items} items'
        )

    # Write updated file
    with open(SEED_DATA_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\nUpdated seed_data.js: {invoice_count} invoices, {total_items} items")
    print(f"File saved: {SEED_DATA_PATH}")

    # Cleanup temp dir
    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp dir")
    except:
        pass

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == '__main__':
    main()
