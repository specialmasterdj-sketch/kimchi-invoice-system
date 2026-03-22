import pdfplumber
import json
import re
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

new_invoices = []

# 1. WISMETTAC
wis_path = r"C:\Users\speci\OneDrive\Desktop\Invoices\wismettacusa_188813_20260311_31830630_14960603774.pdf"
with pdfplumber.open(wis_path) as pdf:
    full_text = ""
    for p in pdf.pages:
        t = p.extract_text()
        if t:
            full_text += t + "\n"

inv_blocks = re.split(r'INVOICE #:\s*(\d+)', full_text)
i = 1
while i < len(inv_blocks) - 1:
    inv_num = inv_blocks[i]
    inv_text = inv_blocks[i+1]

    date_match = re.search(r'INVOICE DATE:\s*(\d{2}/\d{2}/\d{2})', inv_text)
    date_str = date_match.group(1) if date_match else ""

    total_match = re.search(r'Total \(USD\)\s*(?:Cash Price\s*)?\$?([\d,]+\.\d{2})', inv_text)
    if not total_match:
        total_match = re.search(r'Sub Total\s+([\d,]+\.\d{2})', inv_text)
    total = float(total_match.group(1).replace(',','')) if total_match else 0

    items = []
    item_lines = re.findall(
        r'(\d+)\s+(\w+)\s+[\d/]*\s+([\d.]+)\s+(?:CS|Ea|EA)\s+(.+?)\s+\d+/.*?\s+(?:Yes|No)\s+([\d.]+)\s+([\d.]+)',
        inv_text
    )
    for line in item_lines:
        no, item_code, qty, desc, unit_price, total_price = line
        if float(total_price) == 0:
            continue
        items.append({
            "itemNo": item_code,
            "brand": "WISMETTAC",
            "description": desc.strip(),
            "size": "CS",
            "qty": int(float(qty)),
            "unitPrice": float(unit_price),
            "eachPrice": float(unit_price),
            "totalPrice": float(total_price)
        })

    if date_str:
        parts = date_str.split('/')
        iso_date = f"20{parts[2]}-{parts[0]}-{parts[1]}"
    else:
        iso_date = "2026-03-10"

    invoice = {
        "invoiceNumber": f"WIS-{inv_num}",
        "vendor": "Wismettac",
        "date": iso_date,
        "dateDisplay": date_str if date_str else "03/10/26",
        "customer": "KIMCHI MART AT HOLLYWOOD",
        "total": total,
        "branchId": "hollywood",
        "items": items,
        "itemCount": len(items),
        "source": "wismettac_pdf"
    }
    new_invoices.append(invoice)
    i += 2

print(f"Wismettac: {len([x for x in new_invoices if x['vendor']=='Wismettac'])} invoices")

# 2. FRESHPOINT
fp_path = r"C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\FreshPoint\FreshPoint_002106.pdf"
with pdfplumber.open(fp_path) as pdf:
    text = ""
    for p in pdf.pages:
        t = p.extract_text()
        if t:
            text += t + "\n"

fp_items = []
fp_lines = re.findall(
    r'(\d{6})\s+\d+\s+(\d+)\s+([\d/]+\s+\w+)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',
    text
)
for line in fp_lines:
    item_no, qty_ship, pack, desc, unit_wt, ext_wt, unit_price, ext_price = line
    if int(qty_ship) == 0:
        continue
    fp_items.append({
        "itemNo": item_no,
        "brand": "FRESHPOINT",
        "description": desc.strip(),
        "size": pack.strip(),
        "qty": int(qty_ship),
        "unitPrice": float(unit_price),
        "eachPrice": float(unit_price),
        "totalPrice": float(ext_price)
    })

fp_total = sum(i['totalPrice'] for i in fp_items)
fp_invoice = {
    "invoiceNumber": "FP-2778329837",
    "vendor": "FreshPoint",
    "date": "2026-03-13",
    "dateDisplay": "03/13/26",
    "customer": "KIMCHI MART CORAL SPRINGS",
    "total": round(fp_total, 2),
    "branchId": "coral_springs",
    "items": fp_items,
    "itemCount": len(fp_items),
    "source": "freshpoint_pdf"
}
new_invoices.append(fp_invoice)
print(f"FreshPoint: {fp_invoice['itemCount']} items, total=${fp_invoice['total']}")

# 3. EDEN
eden_invoice = {
    "invoiceNumber": "EDEN-SQ145079",
    "vendor": "Eden",
    "date": "2025-04-29",
    "dateDisplay": "04/29/25",
    "customer": "KIMCHI MART HOLLYWOOD",
    "total": 4674.05,
    "branchId": "hollywood",
    "items": [],
    "itemCount": 0,
    "source": "eden_pdf",
    "note": "Sales quotation - housewares and kitchen supplies"
}
new_invoices.append(eden_invoice)
print(f"Eden: header only, total=$4,674.05")

# 4. KC TRADING
kc_path = r"C:\Users\speci\OneDrive\Desktop\Invoices\Inv_2502003_from_K.C._TRADI.pdf"
with pdfplumber.open(kc_path) as pdf:
    text = ""
    for p in pdf.pages:
        t = p.extract_text()
        if t:
            text += t + "\n"

kc_items = []
kc_lines = re.findall(
    r'(\d+)\s+(\w[\w-]+)\s+(.+?)\s+\d{10,}\S*\s+([\d.]+)\s+([\d.]+)',
    text
)
for line in kc_lines:
    qty, item_code, desc, price, amount = line
    if float(amount) == 0:
        continue
    kc_items.append({
        "itemNo": item_code,
        "brand": "KC TRADING",
        "description": desc.strip(),
        "size": "EA",
        "qty": int(qty),
        "unitPrice": float(price),
        "eachPrice": float(price),
        "totalPrice": float(amount)
    })

kc_total = sum(i['totalPrice'] for i in kc_items)
kc_invoice = {
    "invoiceNumber": "KC-2502003",
    "vendor": "KC Trading",
    "date": "2025-02-10",
    "dateDisplay": "02/10/25",
    "customer": "KIMCHI MART PEMBROKE PINES",
    "total": round(kc_total, 2),
    "branchId": "pembroke_pines",
    "items": kc_items,
    "itemCount": len(kc_items),
    "source": "kc_trading_pdf"
}
new_invoices.append(kc_invoice)
print(f"KC Trading: {kc_invoice['itemCount']} items, total=${kc_total}")

# 5. KOCO TRADING
koco_invoice = {
    "invoiceNumber": "KOCO-92410",
    "vendor": "KOCO Trading",
    "date": "2024-02-29",
    "dateDisplay": "02/29/24",
    "customer": "KIMCHI MARKET #2 PEMBROKE PINES",
    "total": 0,
    "branchId": "pembroke_pines",
    "items": [],
    "itemCount": 0,
    "source": "koco_pdf",
    "note": "Housewares and kitchen supplies"
}
new_invoices.append(koco_invoice)
print(f"KOCO Trading: header only")

# 6. NAMDAEMUN
ndm_files = [
    (r"C:\Users\speci\OneDrive\Desktop\Invoices\Inv_87376_from_NAMDAEMUN_CFC_2512.pdf", "87376", "01/13/20", "2020-01-13", "miami"),
    (r"C:\Users\speci\OneDrive\Desktop\Invoices\Inv_96382_from_NAMDAEMUN_CFC_6996.pdf", "96382", "07/14/20", "2020-07-14", "pembroke_pines"),
]

for fpath, inv_num, date_disp, iso_date, branch in ndm_files:
    try:
        with pdfplumber.open(fpath) as pdf:
            text = ""
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    text += t + "\n"

        ndm_items = []
        lines = re.findall(
            r'^(\d+)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s*$',
            text, re.MULTILINE
        )
        for qty, desc, price, amount in lines:
            if float(amount) == 0:
                continue
            ndm_items.append({
                "itemNo": "",
                "brand": "NAMDAEMUN",
                "description": desc.strip(),
                "size": "CS",
                "qty": int(qty),
                "unitPrice": float(price),
                "eachPrice": float(price),
                "totalPrice": float(amount)
            })

        ndm_total = sum(i['totalPrice'] for i in ndm_items)
        ndm_invoice = {
            "invoiceNumber": f"NDM-{inv_num}",
            "vendor": "Namdaemun",
            "date": iso_date,
            "dateDisplay": date_disp,
            "customer": "KIMCHI MART",
            "total": round(ndm_total, 2),
            "branchId": branch,
            "items": ndm_items,
            "itemCount": len(ndm_items),
            "source": "namdaemun_pdf"
        }
        new_invoices.append(ndm_invoice)
        print(f"Namdaemun {inv_num}: {len(ndm_items)} items, total=${ndm_total}")
    except Exception as e:
        print(f"Namdaemun {inv_num} error: {e}")

# NDM-Duluth invoices (mislabeled as Sysco)
ndm_duluth_files = [
    (r"C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Sysco\Sysco_Inv_156769_from_S1Duluth_14120.pdf", "156769", "12/13/22", "2022-12-13", "hollywood"),
    (r"C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Sysco\Sysco_Inv_158857_from_S1Duluth_13520.pdf", "158857", "01/03/23", "2023-01-03", "hollywood"),
    (r"C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\MIAMI (FL342)\Sysco\Sysco_Inv_158858_from_S1Duluth_13520.pdf", "158858", "01/03/23", "2023-01-03", "hollywood"),
]

for fpath, inv_num, date_disp, iso_date, branch in ndm_duluth_files:
    try:
        with pdfplumber.open(fpath) as pdf:
            text = ""
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    text += t + "\n"

        ndm_items = []
        lines = re.findall(
            r'^(\d+)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s*$',
            text, re.MULTILINE
        )
        for qty, desc, price, amount in lines:
            if float(amount) == 0:
                continue
            ndm_items.append({
                "itemNo": "",
                "brand": "NAMDAEMUN",
                "description": desc.strip(),
                "size": "CS",
                "qty": int(qty),
                "unitPrice": float(price),
                "eachPrice": float(price),
                "totalPrice": float(amount)
            })

        ndm_total = sum(i['totalPrice'] for i in ndm_items)
        ndm_invoice = {
            "invoiceNumber": f"NDM-{inv_num}",
            "vendor": "Namdaemun",
            "date": iso_date,
            "dateDisplay": date_disp,
            "customer": "KIMCHI #3 HOLLYWOOD",
            "total": round(ndm_total, 2),
            "branchId": branch,
            "items": ndm_items,
            "itemCount": len(ndm_items),
            "source": "namdaemun_duluth_pdf"
        }
        new_invoices.append(ndm_invoice)
        print(f"Namdaemun-Duluth {inv_num}: {len(ndm_items)} items, total=${ndm_total}")
    except Exception as e:
        print(f"Namdaemun-Duluth {inv_num} error: {e}")

# 7. SYSCO (actual Sysco invoice)
sysco_items = [
    {
        "itemNo": "7792187",
        "brand": "SYSCO",
        "description": "CHICKEN CVP THIGH BNLS SKLS",
        "size": "CS",
        "qty": 7,
        "unitPrice": 77.08,
        "eachPrice": 77.08,
        "totalPrice": 539.56
    },
    {
        "itemNo": "9556481",
        "brand": "SYSCO",
        "description": "CHICKEN CVP WING 1&2JT JB 4-7",
        "size": "CS",
        "qty": 14,
        "unitPrice": 75.65,
        "eachPrice": 75.65,
        "totalPrice": 1059.10
    }
]

sysco_invoice = {
    "invoiceNumber": "SYSCO-519823",
    "vendor": "Sysco",
    "date": "2026-03-10",
    "dateDisplay": "03/10/26",
    "customer": "BB.Q CHICKEN KIMCHI MART FORT LAUDERDALE",
    "total": 1604.56,
    "branchId": "fort_lauderdale",
    "items": sysco_items,
    "itemCount": len(sysco_items),
    "source": "sysco_pdf"
}
new_invoices.append(sysco_invoice)
print(f"Sysco: {len(sysco_items)} items, total=$1,604.56")

# 8. WELL LUCK (from Excel)
import openpyxl
wb = openpyxl.load_workbook(r"C:\Users\speci\OneDrive\Desktop\KIMCHI_MART_INVOICES\_UNSORTED\Welluck_394426.xlsx")
ws = wb.active

wl_invoices = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    inv_no, ln, item_no, qty, um, desc, uprice, amount = row
    if not inv_no or not desc:
        continue
    inv_key = str(inv_no).strip()
    if inv_key not in wl_invoices:
        wl_invoices[inv_key] = {
            "invoiceNumber": f"WL-{inv_key.replace('DI ', '')}",
            "vendor": "Well Luck",
            "date": "2026-03-01",
            "dateDisplay": "03/01/26",
            "customer": "KIMCHI MART",
            "total": 0,
            "branchId": "hollywood",
            "items": [],
            "itemCount": 0,
            "source": "wellluck_xlsx"
        }

    item = {
        "itemNo": str(int(float(item_no))) if item_no and str(item_no).replace('.','').replace('-','').isdigit() else str(item_no) if item_no else "",
        "brand": "WELL LUCK",
        "description": str(desc).strip(),
        "size": str(um).strip() if um else "CS",
        "qty": int(float(qty)) if qty and str(qty).replace('.','').replace('-','').isdigit() else 1,
        "unitPrice": float(uprice) if uprice and str(uprice).replace('.','').replace('-','').isdigit() else 0,
        "eachPrice": float(uprice) if uprice and str(uprice).replace('.','').replace('-','').isdigit() else 0,
        "totalPrice": float(amount) if amount and str(amount).replace('.','').replace('-','').isdigit() else 0
    }
    wl_invoices[inv_key]["items"].append(item)
    wl_invoices[inv_key]["total"] += item["totalPrice"]

for inv_key, inv in wl_invoices.items():
    inv["itemCount"] = len(inv["items"])
    inv["total"] = round(inv["total"], 2)
    new_invoices.append(inv)
    print(f"Well Luck {inv_key}: {inv['itemCount']} items, total=${inv['total']}")

# 9. JFC (from statements)
jfc_invoices = [
    {
        "invoiceNumber": "JFC-1065350",
        "vendor": "JFC",
        "date": "2026-02-23",
        "dateDisplay": "02/23/26",
        "customer": "KIMCHI MART HOLLYWOOD",
        "total": 5750.86,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "jfc_statement",
        "note": "From JFC statement - grocery items"
    },
    {
        "invoiceNumber": "JFC-1065351",
        "vendor": "JFC",
        "date": "2026-02-23",
        "dateDisplay": "02/23/26",
        "customer": "KIMCHI MART HOLLYWOOD",
        "total": 330.70,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "jfc_statement",
        "note": "From JFC statement - liquor"
    }
]
new_invoices.extend(jfc_invoices)
print(f"JFC: 2 invoice headers from statements")

# 10. Header-only entries for vendors with no local PDFs yet
header_only_vendors = [
    {
        "invoiceNumber": "BANDI-001",
        "vendor": "Bandi Foods",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - PDF pending"
    },
    {
        "invoiceNumber": "WEICHUAN-001",
        "vendor": "Wei-Chuan",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - PDF pending"
    },
    {
        "invoiceNumber": "TWOBROSFOOD-001",
        "vendor": "Two Bros Food",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - catalogs available"
    },
    {
        "invoiceNumber": "POCAS-001",
        "vendor": "POCAS",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - offer sheets available"
    },
    {
        "invoiceNumber": "EASTLAND-001",
        "vendor": "Eastland Food",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - PDF pending"
    },
    {
        "invoiceNumber": "BUCKHEAD-001",
        "vendor": "Buckhead",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - PDF pending"
    },
    {
        "invoiceNumber": "WALONG-001",
        "vendor": "Walong",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - PDF pending"
    },
    {
        "invoiceNumber": "OCM-001",
        "vendor": "OCM",
        "date": "2026-03-01",
        "dateDisplay": "03/01/26",
        "customer": "KIMCHI MART",
        "total": 0,
        "branchId": "hollywood",
        "items": [],
        "itemCount": 0,
        "source": "gmail_search",
        "note": "Vendor identified from Gmail - catalog available"
    },
]
new_invoices.extend(header_only_vendors)
print(f"Header-only vendors: {len(header_only_vendors)} vendors added")

# SAVE
output_path = r"C:\Users\speci\OneDrive\Desktop\kimchi-invoice-system\new_vendor_invoices.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(new_invoices, f, ensure_ascii=False, indent=1)

print(f"\nTOTAL: {len(new_invoices)} new invoices saved")
total_items = sum(inv['itemCount'] for inv in new_invoices)
print(f"Total items across all new invoices: {total_items}")
vendors = sorted(set(inv['vendor'] for inv in new_invoices))
print(f"Vendors ({len(vendors)}): {vendors}")
