import pdfplumber
import json
import re
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

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

ITEM_NO_PATTERN = re.compile(r'^(\d{4,5}[A-Z]{1,2})\s+')
INVOICE_PATTERN = re.compile(r'PSI-(\d{7})')
DATE_PATTERN = re.compile(r'Invoice Date:\s*(\d{2}/\d{2}/\d{2,4})')
CUSTOMER_PATTERN = re.compile(r'Customer No\.\s*(FL\d{3})')
TOTAL_PATTERN = re.compile(r'Total\s+\$?([\d,]+\.\d{2})')

UNITS = r'LB|OZ|GAL|ML|L|G|KG|CT|SHT|PC|EA|LITER|FL OZ|PR|#'


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

    um_pattern = re.compile(
        r'\s+(Case|Bag|Box|Each|Pail|Drum|Roll|Pack|Tray|Bundle|Bottle|Jar|Pcs|Set|Tub|Can|Unit|Sack|Bucket|Pound|case|bag|box|pound)\s*$',
        re.IGNORECASE
    )
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


def parse_invoice(pdf_path):
    filename = os.path.basename(pdf_path)
    pdf = pdfplumber.open(pdf_path)
    all_text = ''
    all_lines = []
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            all_text += text + '\n'
            all_lines.extend(text.split('\n'))
    pdf.close()

    inv_match = INVOICE_PATTERN.search(all_text)
    invoice_number = f"PSI-{inv_match.group(1)}" if inv_match else ''

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


pdfs = [
    r'C:\Users\speci\Downloads\Sales Invoice PSI-0161421.pdf',
    r'C:\Users\speci\Downloads\Sales Invoice PSI-0161541.pdf',
    r'C:\Users\speci\Downloads\Sales Invoice PSI-0161631.pdf',
    r'C:\Users\speci\Downloads\Sales Invoice PSI-0167977.pdf',
    r'C:\Users\speci\Downloads\Sales Invoice PSI-0171177.pdf',
]

results = []
for pdf_path in pdfs:
    print(f"\nParsing: {os.path.basename(pdf_path)}")
    result = parse_invoice(pdf_path)
    print(f"  Invoice: {result['invoiceNumber']}")
    print(f"  Branch: {result['branchId']} ({result['customer']})")
    print(f"  Date: {result['dateDisplay']}")
    print(f"  Total: ${result['total']:,.2f}")
    print(f"  Items: {result['itemCount']}")
    results.append(result)

output_path = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\rhee_5_parsed.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n\nAll 5 parsed successfully. Saved to {output_path}")
