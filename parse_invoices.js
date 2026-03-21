const fs = require('fs');
const path = require('path');

const INVOICE_DIR = path.join('C:', 'Users', 'speci', 'OneDrive', 'Desktop', 'Invoices', 'rhee_bros_psi');

// Branch mapping from FL codes
const BRANCH_MAP = {
  'FL116': { id: 'miami', name: 'Miami (Oriental Mart)' },
  'FL342': { id: 'pembroke_pines', name: 'Pembroke Pines' },
  'FL381': { id: 'hollywood', name: 'Hollywood' },
  'FL417': { id: 'coral_springs', name: 'Coral Springs' },
  'FL432': { id: 'fort_lauderdale', name: 'Fort Lauderdale (Palm Beach)' }
};

const invoiceFiles = [
  'invoice_PSI-0154058.txt',
  'invoice_PSI-0154059.txt',
  'invoice_PSI-0154158.txt',
  'invoice_PSI-0167845.txt',
  'invoice_PSI-0170144.txt',
  'invoice_PSI-0170145.txt',
  'invoice_PSI-0170362.txt',
  'invoice_PSI-0171139.txt',
  'invoice_PSI-0171141.txt'
];

function parseInvoice(filename) {
  const filepath = path.join(INVOICE_DIR, filename);
  const content = fs.readFileSync(filepath, 'utf-8');
  const lines = content.split('\n').map(l => l.trim()).filter(l => l);

  let invoiceNumber = '';
  let date = '';
  let customer = '';
  let total = '';
  let branchId = '';
  let branchCode = '';
  const items = [];
  let headerFound = false;

  for (const line of lines) {
    if (line.startsWith('INVOICE:')) {
      invoiceNumber = line.replace('INVOICE:', '').trim();
    } else if (line.startsWith('DATE:')) {
      date = line.replace('DATE:', '').trim();
    } else if (line.startsWith('CUSTOMER:')) {
      customer = line.replace('CUSTOMER:', '').trim();
      // Extract FL code
      const flMatch = customer.match(/FL(\d+)/);
      if (flMatch) {
        branchCode = 'FL' + flMatch[1];
        if (BRANCH_MAP[branchCode]) {
          branchId = BRANCH_MAP[branchCode].id;
        }
      }
    } else if (line.startsWith('TOTAL:')) {
      total = line.replace('TOTAL:', '').trim().replace('$', '').replace(/,/g, '');
    } else if (line.startsWith('No') && line.includes('Brand') && line.includes('Description')) {
      headerFound = true;
      continue;
    } else if (line.startsWith('NOTE:') || line.startsWith('ORDER:') ||
               line.startsWith('SHIP TO:') || line.startsWith('SALESPERSON:') ||
               line.startsWith('TERMS:')) {
      continue;
    } else if (headerFound) {
      const parts = line.split('|');
      if (parts.length >= 9) {
        const itemNo = parts[0].trim();
        const brand = parts[1].trim();
        const description = parts[2].trim();
        const size = parts[3].trim();
        const qty = parts[4].trim();
        const um = parts[5].trim();
        const type = parts[6].trim();
        const unitPrice = parts[7].trim();
        const eachPrice = parts[8].trim();
        const totalPrice = parts[9] ? parts[9].trim().replace(/,/g, '') : '';

        // Skip items with no price data (like PSI-0167845 incomplete entries)
        if (!unitPrice || !brand || !description) continue;
        // Skip shipping lines
        if (itemNo === 'SHIPPING') continue;

        items.push({
          itemNo,
          brand,
          description,
          size,
          qty: parseInt(qty) || 0,
          um,
          type,
          unitPrice: parseFloat(unitPrice) || 0,
          eachPrice: parseFloat(eachPrice) || 0,
          totalPrice: parseFloat(totalPrice) || 0
        });
      }
    }
  }

  // Convert date from MM/DD/YY to ISO-ish format
  let isoDate = '';
  if (date) {
    const [m, d, y] = date.split('/');
    isoDate = `20${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
  }

  return {
    invoiceNumber,
    date: isoDate,
    dateDisplay: date,
    customer,
    branchCode,
    branchId,
    total: parseFloat(total) || 0,
    items
  };
}

// Parse all invoices
const allInvoices = [];
for (const f of invoiceFiles) {
  const inv = parseInvoice(f);
  if (inv.items.length > 0) {
    allInvoices.push(inv);
    console.log(`Parsed ${f}: ${inv.invoiceNumber} | ${inv.branchCode} (${inv.branchId}) | ${inv.date} | ${inv.items.length} items`);
  } else {
    console.log(`SKIPPED ${f}: ${inv.invoiceNumber} | ${inv.branchCode} (${inv.branchId}) | ${inv.date} | 0 items (no data)`);
  }
}

// Group by branch
const byBranch = {};
for (const inv of allInvoices) {
  if (!byBranch[inv.branchId]) {
    byBranch[inv.branchId] = [];
  }
  byBranch[inv.branchId].push(inv);
}

// Sort each branch's invoices by date
for (const bid of Object.keys(byBranch)) {
  byBranch[bid].sort((a, b) => a.date.localeCompare(b.date));
}

// Build seed data structure
const seedData = {
  branches: {
    miami: { id: 'miami', name: 'Miami (Oriental Mart)', code: 'FL116' },
    pembroke_pines: { id: 'pembroke_pines', name: 'Pembroke Pines', code: 'FL342' },
    hollywood: { id: 'hollywood', name: 'Hollywood', code: 'FL381' },
    coral_springs: { id: 'coral_springs', name: 'Coral Springs', code: 'FL417' },
    fort_lauderdale: { id: 'fort_lauderdale', name: 'Fort Lauderdale (Palm Beach)', code: 'FL432' }
  },
  invoices: allInvoices.map(inv => ({
    invoiceNumber: inv.invoiceNumber,
    date: inv.date,
    dateDisplay: inv.dateDisplay,
    branchId: inv.branchId,
    branchCode: inv.branchCode,
    customer: inv.customer,
    total: inv.total,
    itemCount: inv.items.length,
    items: inv.items
  }))
};

// Generate seed_data.js
const output = `// Kimchi Mart Invoice Comparison System - Seed Data
// Generated from ${allInvoices.length} Rhee Bros invoices
// Generated on: ${new Date().toISOString()}

const SEED_DATA = ${JSON.stringify(seedData, null, 2)};
`;

fs.writeFileSync(path.join('C:', 'Users', 'speci', 'OneDrive', 'Desktop', 'kimchi-invoice-system', 'seed_data.js'), output, 'utf-8');

console.log('\n--- Summary ---');
for (const [bid, invs] of Object.entries(byBranch)) {
  console.log(`${bid}: ${invs.length} invoices, total items: ${invs.reduce((s,i) => s + i.items.length, 0)}`);
}
console.log(`\nTotal invoices with data: ${allInvoices.length}`);
console.log('seed_data.js written successfully.');
