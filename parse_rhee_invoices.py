"""
Parse ALL Rhee Bros invoice PDFs into structured JSON.
Skips Statement PDFs and SR-prefixed files.
"""

import os
import re
import json
import sys
import pdfplumber

# Force UTF-8 output
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

PDF_DIR = r"C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\rhee_pdfs"
OUTPUT_FILE = r"C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\rhee_parsed_all.json"

BRANCH_MAP = {
    "FL116": "miami",
    "FL342": "pembroke_pines",
    "FL381": "hollywood",
    "FL417": "coral_springs",
    "FL432": "ft_lauderdale",
}

# Regex patterns
ITEM_NO_RE = re.compile(r'^(\d{4,5}[A-Z0-9]{1,2})\s+')
INVOICE_NO_RE = re.compile(r'Invoice No[.,]?\s*(PSI-\d+)')
DATE_RE = re.compile(r'Invoice Date:\s*(\d{2}/\d{2}/\d{2,4})')
CUSTOMER_RE = re.compile(r'Customer No\.\s*(FL\d{3})')
TOTAL_RE = re.compile(r'Total\s+\$?([\d,]+\.\d{2})')
PRICE_TRIPLE_RE = re.compile(r'([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$')
TYPE_RE = re.compile(r'\s+(Dry|Ref|Frz)\s*$', re.IGNORECASE)
UM_RE = re.compile(
    r'\s+(Case|Bag|Box|Each|Pail|Bucket|Drum|Pack|Sack|Tray|Pair|Set|Roll|Can|Bottle|Jar|Pallet|PC|Bunch|Bundle|Pound|Unit|Tub|Pcs)\s*$',
    re.IGNORECASE
)
QTY_RE = re.compile(r'\s+(\d+(?:\.\d+)?)\s*$')
UNITS_STR = r'LB|OZ|GAL|ML|L|G|KG|CT|SHT|PC|EA|LITER|FL OZ'
SIZE_RE = re.compile(
    r'\s+((?:\d+X)*\d+(?:\.\d+)?\s*(?:' + UNITS_STR + r'))\s*$',
    re.IGNORECASE
)
# Korean character detection
KOREAN_RE = re.compile(r'^[\uac00-\ud7af\u3130-\u318f\u1100-\u11ff]')
# Shipping line
SHIPPING_RE = re.compile(r'^Shipping.*?(\d[\d,]*\.\d{2})\s*$')


def parse_money(s):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0


def parse_date(s):
    parts = s.strip().split("/")
    if len(parts) == 3:
        month, day, year = parts
        if len(year) == 2:
            year = "20" + year
        return f"{year}-{month}-{day}"
    return s.strip()


def extract_brand_desc_size(text):
    """From 'BRAND DESC... SIZE', extract brand, description, size."""
    size = ""
    # Try to find size pattern at end
    sm = SIZE_RE.search(text)
    if sm:
        size = sm.group(1).strip()
        text = text[:sm.start()].strip()
    else:
        # Try size without unit (has X separator like 8X16X0.14)
        no_unit = re.search(r'\s+((?:\d+X)+\d+(?:\.\d+)?)\s*$', text)
        if no_unit:
            size = no_unit.group(1).strip()
            text = text[:no_unit.start()].strip()

    # Split brand (first word) and description (rest)
    parts = text.split(None, 1)
    brand = parts[0] if parts else ""
    description = parts[1] if len(parts) > 1 else ""

    return brand, description, size


def parse_item_line(line):
    """Parse a single item line. Returns dict or None."""
    m = ITEM_NO_RE.match(line)
    if not m:
        return None

    item_no = m.group(1)
    rest = line[m.end():].strip()

    # Must have 3 price columns at end
    pm = PRICE_TRIPLE_RE.search(rest)
    if not pm:
        return None

    unit_price = parse_money(pm.group(1))
    each_price = parse_money(pm.group(2))
    line_total = parse_money(pm.group(3))

    before_prices = rest[:pm.start()].strip()

    # Extract Type (Dry/Ref/Frz) from end
    tm = TYPE_RE.search(before_prices)
    if tm:
        before_prices = before_prices[:tm.start()].strip()

    # Extract Unit of Measure from end
    um = UM_RE.search(before_prices)
    unit = ""
    if um:
        unit = um.group(1)
        before_prices = before_prices[:um.start()].strip()

    # Extract Qty from end
    qm = QTY_RE.search(before_prices)
    qty = 0
    if qm:
        qty_val = float(qm.group(1))
        qty = int(qty_val) if qty_val == int(qty_val) else qty_val
        before_prices = before_prices[:qm.start()].strip()

    brand, description, size = extract_brand_desc_size(before_prices)

    return {
        "itemNo": item_no,
        "brand": brand,
        "description": description,
        "size": size,
        "qty": qty,
        "unit": unit,
        "unitPrice": unit_price,
        "lineTotal": line_total,
    }


def parse_invoice(filepath):
    """Parse a single Rhee Bros invoice PDF."""
    all_lines = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_lines.extend(text.split("\n"))
    except Exception as e:
        return None, str(e)

    if not all_lines:
        return None, "No text extracted"

    all_text = "\n".join(all_lines)

    # Extract header info
    inv_match = INVOICE_NO_RE.search(all_text)
    if not inv_match:
        return None, "No invoice number found"

    invoice_number = inv_match.group(1)

    date_match = DATE_RE.search(all_text)
    date_str = parse_date(date_match.group(1)) if date_match else ""

    cust_match = CUSTOMER_RE.search(all_text)
    branch_id = ""
    if cust_match:
        fl_code = cust_match.group(1)
        branch_id = BRANCH_MAP.get(fl_code, fl_code)

    # Extract total from last occurrence
    total = 0.0
    for m in TOTAL_RE.finditer(all_text):
        total = parse_money(m.group(1))  # last one wins

    # Parse line items
    items = []
    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()

        # Skip empty, Korean, header/footer lines
        if not line or KOREAN_RE.match(line):
            i += 1
            continue

        # Handle Shipping line
        ship_m = SHIPPING_RE.match(line)
        if ship_m:
            items.append({
                "itemNo": "SHIPPING",
                "brand": "",
                "description": "Shipping (Fuel) Charge - Delivery",
                "size": "",
                "qty": 1,
                "unit": "Each",
                "unitPrice": parse_money(ship_m.group(1)),
                "lineTotal": parse_money(ship_m.group(1)),
            })
            i += 1
            continue

        # Check if line starts with item number
        item_start = ITEM_NO_RE.match(line)
        if not item_start:
            i += 1
            continue

        # Try parsing this line directly
        item = parse_item_line(line)
        if item:
            items.append(item)
            i += 1
            continue

        # Line might be split across multiple lines - collect continuations
        full_line = line
        j = i + 1
        while j < len(all_lines) and j <= i + 4:
            next_line = all_lines[j].strip()
            if not next_line:
                j += 1
                continue
            # Stop if Korean text
            if KOREAN_RE.match(next_line):
                j += 1
                continue
            # Stop if new item or known header/footer
            if ITEM_NO_RE.match(next_line) or next_line.startswith("No. Brand") or \
               next_line.startswith("PSI-") or next_line.startswith("All Units") or \
               next_line.startswith("Received") or next_line.startswith("Shipping") or \
               next_line.startswith("Subtotal") or next_line.startswith("Check#") or \
               next_line.startswith("NOTICE") or next_line.startswith("Note:") or \
               next_line.startswith("TERMS") or next_line.startswith("These"):
                break
            # Append continuation
            full_line = full_line + " " + next_line
            j += 1
            # Try parsing the extended line
            item = parse_item_line(full_line)
            if item:
                items.append(item)
                break

        i += 1

    # Deduplicate items by (itemNo, qty, lineTotal) - same item on page boundary
    seen = set()
    unique_items = []
    for item in items:
        key = (item["itemNo"], item["qty"], item["lineTotal"])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    items = unique_items

    invoice = {
        "invoiceNumber": invoice_number,
        "date": date_str,
        "branchId": branch_id,
        "vendor": "Rhee Bros",
        "total": total,
        "items": items,
    }

    return invoice, None


def main():
    pdf_files = sorted([
        f for f in os.listdir(PDF_DIR)
        if f.lower().endswith(".pdf")
        and f.startswith("Sales Invoice PSI-")
    ])

    print(f"Found {len(pdf_files)} invoice PDFs to parse (skipping Statement/SR files)")

    all_invoices = []
    errors = []

    for idx, filename in enumerate(pdf_files):
        filepath = os.path.join(PDF_DIR, filename)

        invoice, err = parse_invoice(filepath)
        if err:
            errors.append((filename, err))
        elif invoice:
            all_invoices.append(invoice)
        else:
            errors.append((filename, "Unknown error"))

        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1}/{len(pdf_files)} files...")

    # Save JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_invoices, f, indent=2, ensure_ascii=False)

    # Summary
    total_items = sum(len(inv["items"]) for inv in all_invoices)
    branch_counts = {}
    branch_totals = {}
    for inv in all_invoices:
        b = inv["branchId"]
        branch_counts[b] = branch_counts.get(b, 0) + 1
        branch_totals[b] = branch_totals.get(b, 0) + inv["total"]

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total invoices parsed: {len(all_invoices)}")
    print(f"Total line items extracted: {total_items}")

    print(f"\nInvoices per branch:")
    for b in sorted(branch_counts.keys()):
        print(f"  {b}: {branch_counts[b]} invoices, ${branch_totals[b]:,.2f} total")

    if errors:
        print(f"\nErrors/Warnings ({len(errors)}):")
        for fn, err in errors:
            print(f"  {fn}: {err}")

    # Date range
    dates = [inv["date"] for inv in all_invoices if inv["date"]]
    if dates:
        print(f"\nDate range: {min(dates)} to {max(dates)}")

    # Items per invoice stats
    item_counts = [len(inv["items"]) for inv in all_invoices]
    if item_counts:
        avg_items = sum(item_counts) / len(item_counts)
        print(f"Avg items per invoice: {avg_items:.1f}")
        zero_items = sum(1 for c in item_counts if c == 0)
        if zero_items:
            print(f"WARNING: {zero_items} invoices with 0 items parsed")

    print(f"\nOutput saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
