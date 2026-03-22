#!/usr/bin/env python3
"""Parse all Choripdong invoice PDFs into structured JSON."""

import os
import re
import json
import sys

# Fix encoding for Windows console
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

import pdfplumber

INVOICE_DIR = r'C:\Users\speci\OneDrive\Desktop\Invoices\choripdong'
OUTPUT_PATH = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\choripdong_parsed.json'

BRANCH_MAP = {
    'CA00200': {'branch': 'miami', 'label': 'Kimchi_M'},
    'CA01351': {'branch': 'pembroke_pines', 'label': 'Kimchi_P'},
    'CA01356': {'branch': 'hollywood', 'label': 'Kimchi_H'},
    'CA01516': {'branch': 'coral_springs', 'label': 'Kimchi_C'},
    'CA01650': {'branch': 'ft_lauderdale', 'label': 'Kimchi_Palm Beach'},
}

# Storage types: COOL, DRY, FROZEN, JCOOL, JDRY, JFROZEN, FRZ, etc.
STORAGE_PATTERN = r'(J?(?:COOL|DRY|FROZEN|FRZ))'

# Item code: 2+ uppercase letters followed by digits, possibly with trailing letter (e.g. VFH0001A, EH1103, VR164102)
ITEM_CODE_PATTERN = r'([A-Z]{2}[A-Z0-9]{2,10})'

# Unit: CS, EA, BG, BX, PK, PC, BT, BOX, etc.
UNIT_PATTERN = r'(CS|EA|BG|BX|PK|PC|BT|BOX|BAG|SET|CTN)'


def is_invoice_file(filename):
    """Check if filename matches invoice pattern (starts with 6-digit date)."""
    return bool(re.match(r'^\d{6}\s+CA\d{5}', filename))


def parse_filename(filename):
    """Extract invoice metadata from filename."""
    base = filename.replace('.pdf', '')
    parts = base.split()

    date_raw = parts[0]  # MMDDYY
    ca_code = parts[1]   # CA#####

    # Invoice number is the last numeric-only token (strip leading underscores)
    invoice_num = None
    for p in reversed(parts):
        cleaned = p.lstrip('_')
        if re.match(r'^\d{9,}$', cleaned):
            invoice_num = cleaned
            break

    # Parse date
    if len(date_raw) == 6:
        mm, dd, yy = date_raw[:2], date_raw[2:4], date_raw[4:6]
        year = int(yy)
        if year < 50:
            year += 2000
        else:
            year += 1900
        date_str = f"{year}-{mm}-{dd}"
    else:
        date_str = date_raw

    branch_info = BRANCH_MAP.get(ca_code, {'branch': 'unknown', 'label': ca_code})

    return {
        'invoiceNumber': invoice_num,
        'date': date_str,
        'caCode': ca_code,
        'branch': branch_info['branch'],
        'branchLabel': branch_info['label'],
    }


def parse_invoice_pdf(filepath):
    """Parse a single Choripdong invoice PDF and extract line items."""
    items = []
    total = None
    sub_total = None
    freight = None

    # Build the item line regex:
    # STORAGE ITEMCODE QTY [UoM] Description... Price Total EAPrice
    # The last 3 numbers are always: unitPrice lineTotal eaPrice (all with 2 decimal places)
    item_re = re.compile(
        r'^' + STORAGE_PATTERN + r'\s+'
        r'' + ITEM_CODE_PATTERN + r'\s+'
        r'(\d+)\s+'                          # qty
        r'(?:' + UNIT_PATTERN + r'\s+)?'     # unit (optional)
        r'(.+?)\s+'                          # description
        r'([\d,]+\.\d{2})\s+'               # unit price
        r'([\d,]+\.\d{2})\s+'               # line total
        r'([\d,]+\.\d{2})$'                 # EA price
    )

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')

            for line in lines:
                line = line.strip()

                # Check for Sub Total / Freight / Total
                st_match = re.search(r'Sub\s*Total:\s*([\d,]+\.\d{2})', line)
                if st_match:
                    sub_total = float(st_match.group(1).replace(',', ''))

                fr_match = re.search(r'Freight:\s*([\d,]+\.\d{2})', line)
                if fr_match:
                    freight = float(fr_match.group(1).replace(',', ''))

                # Total line (not Sub Total)
                if 'Sub' not in line:
                    tot_match = re.search(r'Total:\s*([\d,]+\.\d{2})', line)
                    if tot_match:
                        total = float(tot_match.group(1).replace(',', ''))

                # Try to match item line
                m = item_re.match(line)
                if m:
                    storage = m.group(1)
                    item_code = m.group(2)
                    qty = int(m.group(3))
                    unit = m.group(4) or 'CS'
                    desc = m.group(5).strip()
                    unit_price = float(m.group(6).replace(',', ''))
                    line_total = float(m.group(7).replace(',', ''))
                    ea_price = float(m.group(8).replace(',', ''))

                    items.append({
                        'itemNo': item_code,
                        'storage': storage,
                        'brand': '',
                        'description': desc,
                        'descriptionEnglish': '',
                        'qty': qty,
                        'unit': unit,
                        'unitPrice': unit_price,
                        'lineTotal': line_total,
                        'eaPrice': ea_price,
                    })
                    continue

                # Check if this is the English description / barcode line for the last item
                if items:
                    # English description lines end with a barcode (10+ digits)
                    eng_match = re.match(r'^(.+?)\s+(\d{10,})$', line)
                    if eng_match:
                        eng_desc = eng_match.group(1).strip()
                        # Only update if it looks like an English description (not another item line)
                        if not item_re.match(line):
                            items[-1]['descriptionEnglish'] = eng_desc
                            # Extract brand from "Brand)Description" pattern
                            brand_match = re.match(r'^([^)]+)\)', eng_desc)
                            if brand_match:
                                items[-1]['brand'] = brand_match.group(1).strip()

    return items, total, sub_total, freight


def main():
    # Get all invoice PDF files (filter out non-invoice files)
    all_files_raw = sorted([f for f in os.listdir(INVOICE_DIR) if f.endswith('.pdf')])
    all_files = [f for f in all_files_raw if is_invoice_file(f)]
    skipped = [f for f in all_files_raw if not is_invoice_file(f)]

    print(f"Found {len(all_files)} invoice PDFs (skipped {len(skipped)} non-invoice files)")
    if skipped:
        for s in skipped:
            print(f"  Skipped: {s}")

    invoices = []
    errors = []
    total_items = 0
    branch_counts = {}

    for i, filename in enumerate(all_files):
        filepath = os.path.join(INVOICE_DIR, filename)

        try:
            meta = parse_filename(filename)
            items, total, sub_total, freight = parse_invoice_pdf(filepath)

            invoice = {
                'filename': filename,
                'invoiceNumber': meta['invoiceNumber'],
                'date': meta['date'],
                'caCode': meta['caCode'],
                'branch': meta['branch'],
                'branchLabel': meta['branchLabel'],
                'subTotal': sub_total,
                'freight': freight,
                'total': total,
                'itemCount': len(items),
                'items': items,
            }
            invoices.append(invoice)
            total_items += len(items)

            branch = meta['branch']
            if branch not in branch_counts:
                branch_counts[branch] = {'invoices': 0, 'items': 0}
            branch_counts[branch]['invoices'] += 1
            branch_counts[branch]['items'] += len(items)

        except Exception as e:
            errors.append({'filename': filename, 'error': str(e)})
            print(f"  ERROR parsing {filename}: {e}")

        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(all_files)} files...")

    # Save output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    output = {
        'vendor': 'choripdong',
        'vendorFull': 'Seoul Trading USA Co (Choripdong)',
        'totalInvoices': len(invoices),
        'totalItems': total_items,
        'totalErrors': len(errors),
        'branchSummary': branch_counts,
        'invoices': invoices,
        'errors': errors,
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"PARSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total invoices parsed: {len(invoices)}")
    print(f"Total line items:      {total_items}")
    print(f"Errors:                {len(errors)}")
    print(f"\nBreakdown by branch:")
    for branch, counts in sorted(branch_counts.items()):
        print(f"  {branch:20s}: {counts['invoices']:3d} invoices, {counts['items']:4d} items")
    print(f"\nOutput saved to: {OUTPUT_PATH}")

    # Show invoices with 0 items for debugging
    zero_item = [inv for inv in invoices if inv['itemCount'] == 0]
    if zero_item:
        print(f"\nWARNING: {len(zero_item)} invoices with 0 items:")
        for inv in zero_item:
            print(f"  {inv['filename']}")

    # Validate: check some item totals vs reported totals
    print(f"\nValidation sample (first 5 invoices):")
    for inv in invoices[:5]:
        calc_sub = sum(it['lineTotal'] for it in inv['items'])
        match = "OK" if inv['subTotal'] and abs(calc_sub - inv['subTotal']) < 0.02 else "MISMATCH"
        print(f"  {inv['invoiceNumber']}: {inv['itemCount']} items, calc=${calc_sub:.2f} vs reported=${inv['subTotal']}, {match}")


if __name__ == '__main__':
    main()
