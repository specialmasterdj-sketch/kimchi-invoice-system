import pdfplumber
import json
import re
import os
import sys

# Force UTF-8 output
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

PDF_DIR = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\rhee_pdfs'
OUTPUT_FILE = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\rhee_parsed.json'

BRANCH_MAP = {
    'FL116': 'miami',
    'FL342': 'pembroke_pines',
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

# Pattern for item lines: starts with item number (digits + letters)
ITEM_NO_PATTERN = re.compile(r'^(\d{4,5}[A-Z]{1,2})\s+')

# Pattern for invoice number
INVOICE_PATTERN = re.compile(r'PSI-(\d{7})')

# Pattern for date
DATE_PATTERN = re.compile(r'Invoice Date:\s*(\d{2}/\d{2}/\d{2,4})')

# Pattern for customer number
CUSTOMER_PATTERN = re.compile(r'Customer No\.\s*(FL\d{3})')

# Pattern for total
TOTAL_PATTERN = re.compile(r'Total\s+\$?([\d,]+\.\d{2})')


def parse_price(s):
    """Parse a price string like '1,125.00' to float."""
    try:
        return float(s.replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0


def parse_int_safe(s):
    """Parse an integer safely."""
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def parse_item_line(line):
    """Parse a single item line from the invoice.
    Format: ItemNo Brand Description Size Qty UM Type UnitPrice EachPrice Total

    The challenge is that Description can contain spaces and Size can contain spaces.
    We parse from both ends - item number from left, prices from right, then work inward.
    """
    m = ITEM_NO_PATTERN.match(line)
    if not m:
        return None

    item_no = m.group(1)
    rest = line[m.end():].strip()

    # Skip shipping/freight/fuel lines
    if 'Shipping' in rest or 'Fuel' in rest or 'Freight' in rest or 'Delivery' in rest:
        return None

    # Parse prices from the right side
    # The last 3 numbers are: Unit Price, Each Price, Total
    # Pattern: ... Type UnitPrice EachPrice Total
    # Prices can have commas: 1,125.00
    price_pattern = re.compile(
        r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$'
    )
    pm = price_pattern.search(rest)
    if not pm:
        return None

    unit_price = parse_price(pm.group(1))
    each_price = parse_price(pm.group(2))
    total_price = parse_price(pm.group(3))

    before_prices = rest[:pm.start()].strip()

    # Now parse: Brand Description Size Qty UM Type
    # Type is usually: Dry, Ref, Frz (last word before prices)
    # UM is usually: Case, Bag, Box, Each, Pail, Drum, Roll, Pack, Tray, Bundle, Bottle, Jar, Pcs, Set, Tub, Can
    # Qty is a number
    # We parse from right: Type UM Qty ... then the rest is Brand Description Size

    type_pattern = re.compile(r'\s+(Dry|Ref|Frz|dry|ref|frz|DRY|REF|FRZ)\s*$')
    tm = type_pattern.search(before_prices)
    item_type = ''
    if tm:
        item_type = tm.group(1).capitalize()
        if item_type == 'Ref':
            item_type = 'Ref'
        before_prices = before_prices[:tm.start()].strip()

    # Now parse UM (unit of measure)
    um_pattern = re.compile(r'\s+(Case|Bag|Box|Each|Pail|Drum|Roll|Pack|Tray|Bundle|Bottle|Jar|Pcs|Set|Tub|Can|Unit|Sack|Bucket|Pound|case|bag|box|pound)\s*$', re.IGNORECASE)
    um_match = um_pattern.search(before_prices)
    um = ''
    if um_match:
        um = um_match.group(1).capitalize()
        before_prices = before_prices[:um_match.start()].strip()

    # Now parse Qty (number at end) - can be decimal for Pound items
    qty_pattern = re.compile(r'\s+(\d+(?:\.\d+)?)\s*$')
    qty_match = qty_pattern.search(before_prices)
    qty = 0
    if qty_match:
        qty_val = float(qty_match.group(1))
        qty = int(qty_val) if qty_val == int(qty_val) else qty_val
        before_prices = before_prices[:qty_match.start()].strip()

    # What remains is: Brand Description Size
    # Size is typically at the end, patterns like: 8X5 LB, 12X29.08 OZ, 40 LB, 22 LB, etc.
    # Size pattern: number(Xnumber)? (LB|OZ|GAL|ML|L|G|KG|CT|SHT|PC|EA)
    # But size can be complex like "4X6X6.8 OZ" or "2X30X0.56 OZ"
    UNITS = r'LB|OZ|GAL|ML|L|G|KG|CT|SHT|PC|EA|LITER|FL OZ|PR|#'
    size_pattern = re.compile(
        r'\s+('
        r'(?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r')'
        r')\s*$',
        re.IGNORECASE
    )
    size_match = size_pattern.search(before_prices)
    size = ''
    if size_match:
        size = size_match.group(1).strip()
        before_prices = before_prices[:size_match.start()].strip()

    # Also try to find size glued to end of text with no space, e.g., "(BANANA_ 6P)20X9.1 OZ"
    # or "(15#_NEW)15 LB" or "(40#)40 LB" or "RADISH20X24.7 OZ"
    if not size:
        glued_size = re.compile(
            r'([)\w])((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r'))\s*$',
            re.IGNORECASE
        )
        gm = glued_size.search(before_prices)
        if gm:
            size = gm.group(2).strip()
            before_prices = before_prices[:gm.start() + 1].strip()  # keep the char before size

    # Try size at end without unit (unit was on next PDF line), e.g., "8X16X0.14"
    if not size:
        no_unit_size = re.compile(
            r'\s+((?:\d+X)+\d+(?:\.\d+)?)\s*$'
        )
        num = no_unit_size.search(before_prices)
        if num:
            # Only match if it looks like a size (has X separator)
            size = num.group(1).strip()
            before_prices = before_prices[:num.start()].strip()

    # Now split Brand (first word) and Description (rest)
    parts = before_prices.split(None, 1)
    brand = parts[0] if parts else ''
    description = parts[1] if len(parts) > 1 else ''

    # If no size was found, the description might contain it - try broader match
    if not size and description:
        # Try to find size-like pattern at end of description
        broad_size = re.compile(
            r'\s+('
            r'(?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS + r')'
            r')\s*$',
            re.IGNORECASE
        )
        bm = broad_size.search(description)
        if bm:
            size = bm.group(1).strip()
            description = description[:bm.start()].strip()

    # Also try glued size in description
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


def parse_invoice(pdf_path):
    """Parse a single Rhee Bros invoice PDF."""
    filename = os.path.basename(pdf_path)

    # Skip statement PDFs and SR- files
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
        print(f"  ERROR reading pages of {filename}: {e}")
        pdf.close()
        return None

    pdf.close()

    # Extract invoice number
    inv_match = INVOICE_PATTERN.search(all_text)
    if not inv_match:
        print(f"  WARNING: No invoice number found in {filename}")
        return None
    invoice_number = f"PSI-{inv_match.group(1)}"

    # Extract date
    date_match = DATE_PATTERN.search(all_text)
    date_display = ''
    date_iso = ''
    if date_match:
        date_display = date_match.group(1)
        # Convert to ISO format
        parts = date_display.split('/')
        month, day = parts[0], parts[1]
        year = parts[2]
        if len(year) == 2:
            year = '20' + year
        date_iso = f"{year}-{month}-{day}"

    # Extract customer number
    cust_match = CUSTOMER_PATTERN.search(all_text)
    customer_code = ''
    branch_id = ''
    customer_name = ''
    if cust_match:
        customer_code = cust_match.group(1)
        branch_id = BRANCH_MAP.get(customer_code, customer_code.lower())
        customer_name = BRANCH_NAMES.get(branch_id, customer_code)

    # Extract total
    total = 0.0
    total_match = TOTAL_PATTERN.search(all_text)
    if total_match:
        total = parse_price(total_match.group(1))

    # Parse line items
    items = []
    items_by_no = {}  # Track items by item number to handle duplicates

    for line in all_lines:
        line = line.strip()
        if not line:
            continue

        item = parse_item_line(line)
        if item is None:
            continue

        # Skip promo/credit lines (unit price $2 or less)
        if item['unitPrice'] <= 2.0:
            continue

        item_no = item['itemNo']

        # Handle duplicate items - keep the one with higher unit price
        if item_no in items_by_no:
            existing = items_by_no[item_no]
            if item['unitPrice'] > existing['unitPrice']:
                items_by_no[item_no] = item
            # else keep existing (higher price)
        else:
            items_by_no[item_no] = item

    items = list(items_by_no.values())

    result = {
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

    return result


def main():
    pdf_files = sorted([
        f for f in os.listdir(PDF_DIR)
        if f.lower().endswith('.pdf')
    ])

    print(f"Found {len(pdf_files)} PDF files to process")

    results = []
    errors = []
    skipped = []

    for i, filename in enumerate(pdf_files):
        filepath = os.path.join(PDF_DIR, filename)

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(pdf_files)} PDFs processed...")

        result = parse_invoice(filepath)

        if result is None:
            skipped.append(filename)
            continue

        if result['itemCount'] == 0:
            print(f"  WARNING: No items parsed from {filename}")
            errors.append(filename)

        results.append(result)

    # Save results
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'='*60}")
    print(f"PARSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total PDFs found: {len(pdf_files)}")
    print(f"Successfully parsed: {len(results)}")
    print(f"Skipped (not invoices): {len(skipped)}")
    print(f"Warnings (0 items): {len(errors)}")

    total_items = sum(r['itemCount'] for r in results)
    print(f"Total line items: {total_items}")

    # Branch breakdown
    branch_counts = {}
    for r in results:
        bid = r['branchId']
        if bid not in branch_counts:
            branch_counts[bid] = {'invoices': 0, 'items': 0, 'total': 0.0}
        branch_counts[bid]['invoices'] += 1
        branch_counts[bid]['items'] += r['itemCount']
        branch_counts[bid]['total'] += r['total']

    print(f"\nBranch breakdown:")
    for bid, counts in sorted(branch_counts.items()):
        print(f"  {bid}: {counts['invoices']} invoices, {counts['items']} items, ${counts['total']:,.2f}")

    # Date range
    dates = [r['date'] for r in results if r['date']]
    if dates:
        print(f"\nDate range: {min(dates)} to {max(dates)}")

    if skipped:
        print(f"\nSkipped files: {skipped}")
    if errors:
        print(f"\nFiles with 0 items: {errors}")

    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
