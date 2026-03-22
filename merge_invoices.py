#!/usr/bin/env python
"""Merge all parsed invoice data into seed_data.js"""

import json
import re
from collections import Counter
from datetime import datetime

BASE = "C:/Users/speci/OneDrive/Desktop/kimchi-invoice-system"

# ── 1. Load existing seed_data.js ──────────────────────────────────────────
with open(f"{BASE}/seed_data.js", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.index("const SEED_DATA = ") + len("const SEED_DATA = ")
json_str = content[idx:].rstrip().rstrip(";")
seed = json.loads(json_str)
existing_invoices = seed["invoices"]

# ── 2. Load Rhee Bros parsed ───────────────────────────────────────────────
with open(f"{BASE}/rhee_parsed_all.json", "r", encoding="utf-8") as f:
    rhee_invoices = json.load(f)

# ── 3. Load Choripdong parsed ─────────────────────────────────────────────
with open(f"{BASE}/choripdong_parsed.json", "r", encoding="utf-8") as f:
    chori_data = json.load(f)
chori_invoices = chori_data["invoices"]


# ── Helper: format dateDisplay as MM/DD/YY ─────────────────────────────────
def make_date_display(date_str):
    """Convert YYYY-MM-DD to MM/DD/YY"""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%m/%d/%y")
    except Exception:
        return date_str


# ── Helper: normalize item ─────────────────────────────────────────────────
def normalize_item(item):
    """Normalize an item to standard schema."""
    return {
        "itemNo": item.get("itemNo", ""),
        "brand": item.get("brand", ""),
        "description": item.get("description", ""),
        "size": item.get("size", item.get("unit", "")),
        "qty": item.get("qty", 0),
        "unit": item.get("unit", item.get("size", "")),
        "unitPrice": item.get("unitPrice", 0),
        "lineTotal": item.get("lineTotal", item.get("totalPrice", 0)),
    }


# ── Helper: normalize invoice ──────────────────────────────────────────────
def normalize_invoice(inv, source="existing"):
    """Normalize an invoice to standard schema."""
    # Determine branchId
    branch_id = inv.get("branchId", inv.get("branch", ""))
    # ft_lauderdale -> fort_lauderdale mapping
    if branch_id == "ft_lauderdale":
        branch_id = "fort_lauderdale"

    date_str = inv.get("date", "")
    # Always regenerate dateDisplay from date for consistency
    date_display = make_date_display(date_str) if date_str else (inv.get("dateDisplay", "") or "")

    # Determine vendor name
    vendor = inv.get("vendor", "")
    if source == "choripdong":
        vendor = "Choripdong"
    elif source == "rhee":
        vendor = "Rhee Bros"

    # Invoice number - Choripdong prefix
    inv_num = inv.get("invoiceNumber", "") or ""
    if source == "choripdong" and inv_num and not inv_num.startswith("CH-"):
        inv_num = f"CH-{inv_num}"

    # Total
    total = inv.get("total", 0)

    # Normalize items
    raw_items = inv.get("items", [])
    items = [normalize_item(it) for it in raw_items]

    return {
        "invoiceNumber": inv_num,
        "date": date_str,
        "dateDisplay": date_display,
        "branchId": branch_id,
        "vendor": vendor,
        "total": total,
        "itemCount": len(items),
        "items": items,
        "note": inv.get("note", ""),
    }


# ── 4. Build master invoice dict (keyed by invoiceNumber) ─────────────────
# Strategy: for duplicates, keep whichever has more items.
master = {}


def add_invoice(inv_norm):
    key = inv_norm["invoiceNumber"]
    if key in master:
        if len(inv_norm["items"]) > len(master[key]["items"]):
            master[key] = inv_norm
    else:
        master[key] = inv_norm


# First: add non-Rhee, non-Choripdong from existing (Wang, Namdaemun, etc.)
for inv in existing_invoices:
    vendor = inv.get("vendor", "")
    if vendor not in ("Rhee Bros", "Choripdong"):
        norm = normalize_invoice(inv, source="existing")
        add_invoice(norm)

# Existing Rhee Bros and Choripdong (will be replaced if new data has more items)
for inv in existing_invoices:
    vendor = inv.get("vendor", "")
    if vendor in ("Rhee Bros", "Choripdong"):
        norm = normalize_invoice(inv, source="existing")
        add_invoice(norm)

# Add new Rhee Bros (97 invoices)
for inv in rhee_invoices:
    norm = normalize_invoice(inv, source="rhee")
    add_invoice(norm)

# Add new Choripdong (69 invoices)
for inv in chori_invoices:
    norm = normalize_invoice(inv, source="choripdong")
    add_invoice(norm)


# ── 5. Sort by date desc, then invoiceNumber ──────────────────────────────
all_invoices = sorted(master.values(), key=lambda x: (x["date"], x["invoiceNumber"]), reverse=True)


# ── 6. Build output ───────────────────────────────────────────────────────
branches = {
    "miami": {"id": "miami", "name": "Miami", "code": "FL116"},
    "pembroke_pines": {"id": "pembroke_pines", "name": "Pembroke Pines", "code": "FL342"},
    "hollywood": {"id": "hollywood", "name": "Hollywood", "code": "FL381"},
    "coral_springs": {"id": "coral_springs", "name": "Coral Springs", "code": "FL417"},
    "fort_lauderdale": {"id": "fort_lauderdale", "name": "Fort Lauderdale (Palm Beach)", "code": "FL432"},
}

output_data = {"branches": branches, "invoices": all_invoices}

# Stats for header comment
total_inv = len(all_invoices)
total_items = sum(len(inv["items"]) for inv in all_invoices)
vendor_counts = Counter()
for inv in all_invoices:
    vendor_counts[inv["vendor"]] += 1

vendor_json = json.dumps(dict(vendor_counts.most_common()), ensure_ascii=False)

json_body = json.dumps(output_data, ensure_ascii=False, indent=1)

output = f"""// Kimchi Mart Invoice System
// {total_inv} invoices, {total_items} items
// {vendor_json}

const SEED_DATA = {json_body};
"""

with open(f"{BASE}/seed_data.js", "w", encoding="utf-8") as f:
    f.write(output)

# ── 7. Print stats ────────────────────────────────────────────────────────
print(f"=== MERGE COMPLETE ===")
print(f"Total invoices: {total_inv}")
print(f"Total items: {total_items}")
print()
print("By vendor:")
vendor_items = Counter()
for inv in all_invoices:
    vendor_items[inv["vendor"]] += len(inv["items"])
for v, c in vendor_counts.most_common():
    print(f"  {v}: {c} invoices, {vendor_items[v]} items")

print()
print("By branch:")
branch_inv = Counter()
branch_items = Counter()
for inv in all_invoices:
    b = inv["branchId"]
    branch_inv[b] += 1
    branch_items[b] += len(inv["items"])
for b, c in branch_inv.most_common():
    print(f"  {b}: {c} invoices, {branch_items[b]} items")
