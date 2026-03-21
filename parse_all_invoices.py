#!/usr/bin/env python3
"""Parse ALL vendor invoice PDFs and generate seed_data.js for invoice comparison system."""
import pdfplumber
import json
import os
import re
import glob
import sys

# Branch mapping from folder names
BRANCH_MAP = {
    'MIAMI': {'id': 'miami', 'name': 'Miami', 'code': 'FL116'},
    'PEMBROKE': {'id': 'pembroke_pines', 'name': 'Pembroke Pines', 'code': 'FL342'},
    'HOLLYWOOD': {'id': 'hollywood', 'name': 'Hollywood', 'code': 'FL381'},
    'CORAL': {'id': 'coral_springs', 'name': 'Coral Springs', 'code': 'FL417'},
    'FORT': {'id': 'fort_lauderdale', 'name': 'Fort Lauderdale (Palm Beach)', 'code': 'FL432'},
    'LAUDERDALE': {'id': 'fort_lauderdale', 'name': 'Fort Lauderdale (Palm Beach)', 'code': 'FL432'},
}

def get_branch_from_path(filepath):
    """Determine branch from folder path."""
    upper = filepath.upper()
    for key, val in BRANCH_MAP.items():
        if key in upper:
            return val['id']
    return 'unsorted'

def parse_choripdong_pdf(filepath):
    """Parse a Choripdong/Seoul Trading invoice PDF."""
    try:
        pdf = pdfplumber.open(filepath)
        all_text = ''
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                all_text += t + '\n'
        pdf.close()

        if not all_text.strip():
            return None

        # Extract invoice number
        inv_match = re.search(r'Sales Invoice Number.*?(\d{9,})', all_text, re.S)
        if not inv_match:
            inv_match = re.search(r'(\d{9,})', all_text)
        inv_number = inv_match.group(1) if inv_match else os.path.basename(filepath).replace('.pdf','')

        # Extract date
        date_match = re.search(r'Document Date.*?(\d{2}-\d{2}-\d{4})', all_text, re.S)
        if not date_match:
            date_match = re.search(r'(\d{2}-\d{2}-\d{4})', all_text)
        date_str = date_match.group(1) if date_match else ''

        # Convert date format MM-DD-YYYY to YYYY-MM-DD
        iso_date = ''
        display_date = date_str
        if date_str:
            parts = date_str.split('-')
            if len(parts) == 3:
                iso_date = f"{parts[2]}-{parts[0]}-{parts[1]}"
                display_date = f"{parts[0]}/{parts[1]}/{parts[2][2:]}"

        # Extract customer
        cust_match = re.search(r'Customer No\.\s+Customer Name\s+(\w+)\s+(.+?)(?:\n|Tel)', all_text, re.S)
        customer = cust_match.group(2).strip() if cust_match else ''

        # Extract total
        total_match = re.search(r'Total:\s*\$?([\d,]+\.?\d*)', all_text)
        total = float(total_match.group(1).replace(',','')) if total_match else 0

        # Extract items - pattern: Storage ItemCode QTY UoM Description Price Total EA Price
        items = []
        # Match lines like: JDRY VSA12006 1 BOX description 78.00 78.00 3.90
        item_pattern = re.compile(
            r'(?:JDRY|JFROZEN|JREFR|DRY|FROZEN|REFR|JOTHER)\s+'  # storage type
            r'(\w+)\s+'           # item code
            r'(\d+)\s+'           # qty
            r'(\w+)\s+'           # UoM
            r'(.+?)\s+'           # description
            r'([\d,]+\.\d{2})\s+' # price
            r'([\d,]+\.\d{2})\s+' # total
            r'([\d,]+\.\d{2})'    # ea price
        )

        for match in item_pattern.finditer(all_text):
            item_code = match.group(1)
            qty = int(match.group(2))
            uom = match.group(3)
            desc = match.group(4).strip()
            unit_price = float(match.group(5).replace(',',''))
            line_total = float(match.group(6).replace(',',''))
            each_price = float(match.group(7).replace(',',''))

            # Clean description - remove barcode numbers at end
            desc = re.sub(r'\s*\d{10,}\s*$', '', desc)
            # Remove duplicate Korean/English lines
            desc_lines = desc.split('\n')
            desc = desc_lines[0].strip() if desc_lines else desc

            items.append({
                'itemNo': item_code,
                'brand': 'CHORIPDONG',
                'description': desc,
                'size': uom,
                'qty': qty,
                'unitPrice': unit_price,
                'eachPrice': each_price,
                'totalPrice': line_total
            })

        if not items and not total:
            return None

        return {
            'invoiceNumber': f"CH-{inv_number}",
            'vendor': 'Choripdong',
            'date': iso_date,
            'dateDisplay': display_date,
            'customer': customer,
            'total': total,
            'items': items,
            'itemCount': len(items),
            'source': os.path.basename(filepath)
        }
    except Exception as e:
        print(f"  ERROR parsing {filepath}: {e}", file=sys.stderr)
        return None

def parse_wang_pdf(filepath):
    """Parse a Wang/CJ invoice PDF."""
    try:
        pdf = pdfplumber.open(filepath)
        all_text = ''
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                all_text += t + '\n'
        pdf.close()

        if not all_text.strip():
            return None

        # Extract invoice info
        inv_match = re.search(r'Invoice[# ]*:?\s*(\w[\w-]+)', all_text)
        inv_number = inv_match.group(1) if inv_match else os.path.basename(filepath).replace('.pdf','')

        date_match = re.search(r'(?:Date|Invoice Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', all_text)
        date_str = date_match.group(1) if date_match else ''

        total_match = re.search(r'(?:Total|Grand Total|Amount Due)[:\s]*\$?([\d,]+\.?\d*)', all_text)
        total = float(total_match.group(1).replace(',','')) if total_match else 0

        # Parse items - Wang format varies, try table extraction
        items = []
        item_pattern = re.compile(
            r'(\d{3,})\s+'  # item number
            r'(.+?)\s+'     # description
            r'(\d+)\s+'     # qty
            r'([\d.]+)\s+'  # price
            r'([\d,.]+)'    # total
        )

        for match in item_pattern.finditer(all_text):
            items.append({
                'itemNo': match.group(1),
                'brand': 'WANG',
                'description': match.group(2).strip(),
                'size': '',
                'qty': int(match.group(3)),
                'unitPrice': float(match.group(4)),
                'eachPrice': 0,
                'totalPrice': float(match.group(5).replace(',',''))
            })

        iso_date = ''
        display_date = date_str
        if date_str:
            parts = re.split(r'[/-]', date_str)
            if len(parts) == 3:
                year = parts[2] if len(parts[2]) == 4 else f"20{parts[2]}"
                iso_date = f"{year}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                display_date = f"{parts[0]}/{parts[1]}/{year[2:]}"

        return {
            'invoiceNumber': f"WG-{inv_number}",
            'vendor': 'Wang',
            'date': iso_date,
            'dateDisplay': display_date,
            'customer': '',
            'total': total,
            'items': items,
            'itemCount': len(items),
            'source': os.path.basename(filepath)
        }
    except Exception as e:
        print(f"  ERROR parsing {filepath}: {e}", file=sys.stderr)
        return None

def parse_rhee_txt(filepath):
    """Parse Rhee Bros text-extracted invoice."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    lines = text.strip().split('\n')
    inv_number = ''
    date_str = ''
    customer = ''
    total = 0
    items = []

    for line in lines:
        line = line.strip()
        if line.startswith('INVOICE:'):
            inv_number = line.split(':',1)[1].strip()
        elif line.startswith('DATE:'):
            date_str = line.split(':',1)[1].strip()
        elif line.startswith('CUSTOMER:'):
            customer = line.split(':',1)[1].strip()
        elif line.startswith('TOTAL:'):
            total_str = line.split(':',1)[1].strip().replace('$','').replace(',','')
            total = float(total_str) if total_str else 0
        elif '|' in line and not line.startswith('No'):
            parts = line.split('|')
            if len(parts) >= 8:
                item_no = parts[0].strip()
                if not re.match(r'\d{4,5}[A-Za-z]', item_no):
                    continue
                brand = parts[1].strip()
                desc = parts[2].strip()
                size = parts[3].strip()
                qty = int(parts[4].strip()) if parts[4].strip().isdigit() else 0
                unit_price = float(parts[7].strip().replace(',','')) if parts[7].strip() else 0
                each_price = float(parts[8].strip().replace(',','')) if len(parts) > 8 and parts[8].strip() else 0
                line_total = float(parts[9].strip().replace(',','')) if len(parts) > 9 and parts[9].strip() else 0

                items.append({
                    'itemNo': item_no,
                    'brand': brand,
                    'description': desc,
                    'size': size,
                    'qty': qty,
                    'unitPrice': unit_price,
                    'eachPrice': each_price,
                    'totalPrice': line_total
                })

    # Convert date MM/DD/YY to ISO
    iso_date = ''
    display_date = date_str
    if date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            year = f"20{parts[2]}" if len(parts[2]) == 2 else parts[2]
            iso_date = f"{year}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            display_date = date_str

    # FL code to branch
    branch_id = 'unsorted'
    fl_match = re.search(r'FL(\d+)', customer)
    if fl_match:
        fl_code = fl_match.group(1)
        fl_map = {'116': 'miami', '342': 'pembroke_pines', '381': 'hollywood', '417': 'coral_springs', '432': 'fort_lauderdale'}
        branch_id = fl_map.get(fl_code, 'unsorted')

    return {
        'invoiceNumber': inv_number,
        'vendor': 'Rhee Bros',
        'date': iso_date,
        'dateDisplay': display_date,
        'customer': customer,
        'total': total,
        'items': items,
        'itemCount': len(items),
        'branchId': branch_id,
        'source': os.path.basename(filepath)
    }

def main():
    base_dir = r'C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES'
    rhee_txt_dir = r'C:\Users\speci\OneDrive\Desktop\Invoices\rhee_bros_psi'

    all_invoices = []

    # 1. Parse Rhee Bros text files
    print("=== Parsing Rhee Bros text files ===")
    for f in glob.glob(os.path.join(rhee_txt_dir, 'invoice_PSI-*.txt')):
        print(f"  Parsing {os.path.basename(f)}...")
        inv = parse_rhee_txt(f)
        if inv and inv['items']:
            all_invoices.append(inv)
            print(f"    -> {inv['invoiceNumber']}: {len(inv['items'])} items, ${inv['total']:,.2f}")

    # 2. Parse Choripdong PDFs
    print("\n=== Parsing Choripdong PDFs ===")
    choripdong_count = 0
    for f in glob.glob(os.path.join(base_dir, '**', 'Choripdong', 'Choripdong_*.pdf'), recursive=True):
        print(f"  Parsing {os.path.basename(f)}...")
        inv = parse_choripdong_pdf(f)
        if inv:
            inv['branchId'] = get_branch_from_path(f)
            all_invoices.append(inv)
            choripdong_count += 1
            print(f"    -> {inv['invoiceNumber']}: {len(inv['items'])} items, ${inv['total']:,.2f}")
    print(f"  Choripdong total: {choripdong_count} invoices")

    # 3. Parse Wang PDFs
    print("\n=== Parsing Wang PDFs ===")
    wang_count = 0
    for f in glob.glob(os.path.join(base_dir, '**', 'Wang', 'Wang_*.pdf'), recursive=True):
        print(f"  Parsing {os.path.basename(f)}...")
        inv = parse_wang_pdf(f)
        if inv:
            inv['branchId'] = get_branch_from_path(f)
            all_invoices.append(inv)
            wang_count += 1
            print(f"    -> {inv['invoiceNumber']}: {len(inv['items'])} items, ${inv['total']:,.2f}")
    print(f"  Wang total: {wang_count} invoices")

    # 4. Parse Rhee Bros PDFs from organized folders
    print("\n=== Parsing Rhee Bros PDFs from organized folders ===")
    rhee_pdf_count = 0
    for f in glob.glob(os.path.join(base_dir, '**', 'Rhee Bros', 'RheeBros_PSI*.pdf'), recursive=True):
        print(f"  Parsing {os.path.basename(f)}...")
        try:
            pdf = pdfplumber.open(f)
            all_text = ''
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    all_text += t + '\n'
            pdf.close()
            # Try to extract items using similar pattern to text files
            if all_text:
                rhee_pdf_count += 1
                print(f"    -> Extracted {len(all_text)} chars")
        except Exception as e:
            print(f"    ERROR: {e}")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"Total invoices parsed: {len(all_invoices)}")

    by_vendor = {}
    by_branch = {}
    total_items = 0
    for inv in all_invoices:
        v = inv.get('vendor', 'Unknown')
        b = inv.get('branchId', 'unsorted')
        by_vendor[v] = by_vendor.get(v, 0) + 1
        by_branch[b] = by_branch.get(b, 0) + 1
        total_items += len(inv.get('items', []))

    print(f"Total items: {total_items}")
    print(f"By vendor: {json.dumps(by_vendor, indent=2)}")
    print(f"By branch: {json.dumps(by_branch, indent=2)}")

    # 5. Generate seed_data.js
    branches = {
        'miami': {'id': 'miami', 'name': 'Miami', 'nameKr': '', 'code': 'FL116'},
        'pembroke_pines': {'id': 'pembroke_pines', 'name': 'Pembroke Pines', 'nameKr': '', 'code': 'FL342'},
        'hollywood': {'id': 'hollywood', 'name': 'Hollywood', 'nameKr': '', 'code': 'FL381'},
        'coral_springs': {'id': 'coral_springs', 'name': 'Coral Springs', 'nameKr': '', 'code': 'FL417'},
        'fort_lauderdale': {'id': 'fort_lauderdale', 'name': 'Fort Lauderdale (Palm Beach)', 'nameKr': '', 'code': 'FL432'},
    }

    seed = {
        'branches': branches,
        'invoices': all_invoices
    }

    output_path = r'C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\seed_data.js'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('// Kimchi Mart Invoice Comparison System - Seed Data\n')
        f.write(f'// Generated from {len(all_invoices)} invoices across all vendors\n')
        f.write(f'// Total items: {total_items}\n')
        f.write(f'// Vendors: {", ".join(by_vendor.keys())}\n\n')
        f.write('const SEED_DATA = ')
        json.dump(seed, f, ensure_ascii=False, indent=2)
        f.write(';\n')

    print(f"\nSeed data written to {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")

if __name__ == '__main__':
    main()
