// Build seed_data.js from invoice text files
const fs = require('fs');
const path = require('path');

const invoiceDir = 'C:/Users/speci/OneDrive/Desktop/Invoices/rhee_bros_psi';
const outputFile = path.join(__dirname, 'seed_data.js');

const BRANCH_MAP = {
  'FL116': { id: 'miami', name: 'Miami (Oriental Mart)', nameKr: '마이애미 (오리엔탈 마트)', code: 'FL116' },
  'FL342': { id: 'pembroke_pines', name: 'Pembroke Pines', nameKr: '펨브로크 파인스', code: 'FL342' },
  'FL381': { id: 'hollywood', name: 'Hollywood', nameKr: '할리우드', code: 'FL381' },
  'FL417': { id: 'coral_springs', name: 'Coral Springs', nameKr: '코랄 스프링스', code: 'FL417' },
  'FL432': { id: 'fort_lauderdale', name: 'Fort Lauderdale (Palm Beach)', nameKr: '포트 로더데일 (팜비치)', code: 'FL432' }
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

function parseDate(dateStr) {
  // MM/DD/YY
  const [m, d, y] = dateStr.split('/');
  const year = parseInt(y) < 50 ? '20' + y : '19' + y;
  return `${year}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;
}

function parseInvoice(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n').map(l => l.trim()).filter(l => l.length > 0);

  let invoiceNumber = '';
  let date = '';
  let dateDisplay = '';
  let customer = '';
  let total = 0;
  let branchCode = '';
  let note = '';
  const items = [];
  let headerDone = false;

  for (const line of lines) {
    if (line.startsWith('INVOICE:')) {
      invoiceNumber = line.replace('INVOICE:', '').trim();
    } else if (line.startsWith('DATE:')) {
      dateDisplay = line.replace('DATE:', '').trim();
      date = parseDate(dateDisplay);
    } else if (line.startsWith('CUSTOMER:')) {
      customer = line.replace('CUSTOMER:', '').trim();
      const match = customer.match(/FL(\d+)/);
      if (match) branchCode = 'FL' + match[1];
    } else if (line.startsWith('TOTAL:')) {
      total = parseFloat(line.replace('TOTAL:', '').trim().replace(/[$,]/g, ''));
    } else if (line.startsWith('NOTE:')) {
      note = line.replace('NOTE:', '').trim();
    } else if (line.startsWith('No') && line.includes('Brand') && line.includes('Description')) {
      headerDone = true;
      continue;
    } else if (headerDone && line.includes('|')) {
      const parts = line.split('|');
      if (parts.length >= 10) {
        const itemNo = parts[0].trim();
        const brand = parts[1].trim();
        const description = parts[2].trim();
        const size = parts[3].trim();
        const qty = parseInt(parts[4].trim()) || 0;
        const um = parts[5].trim();
        const type = parts[6].trim();
        const unitPrice = parseFloat(parts[7].trim()) || 0;
        const eachPrice = parseFloat(parts[8].trim()) || 0;
        const totalPrice = parseFloat(parts[9].trim().replace(/,/g, '')) || 0;

        // Skip items with no data (PSI-0167845 has empty items)
        if (!brand && !description && !size) continue;
        // Skip shipping lines
        if (itemNo === 'SHIPPING') continue;

        items.push({
          itemNo, brand, description, size, qty, um, type,
          unitPrice, eachPrice, totalPrice
        });
      }
    }
  }

  const branchInfo = BRANCH_MAP[branchCode];
  return {
    invoiceNumber,
    date,
    dateDisplay,
    branchId: branchInfo ? branchInfo.id : 'unknown',
    branchCode,
    customer,
    total,
    note: note || undefined,
    itemCount: items.length,
    items
  };
}

// Parse all invoices
const invoices = [];
for (const file of invoiceFiles) {
  const filePath = path.join(invoiceDir, file);
  if (fs.existsSync(filePath)) {
    const inv = parseInvoice(filePath);
    console.log(`Parsed ${file}: ${inv.invoiceNumber} | ${inv.branchCode} (${inv.branchId}) | ${inv.date} | ${inv.itemCount} items | $${inv.total}`);
    invoices.push(inv);
  }
}

// Sort by date
invoices.sort((a, b) => a.date.localeCompare(b.date));

// Build branches object
const branches = {};
for (const [code, info] of Object.entries(BRANCH_MAP)) {
  branches[info.id] = { ...info };
}

// Build the output
const seedData = {
  branches,
  invoices
};

const output = `// Kimchi Mart Invoice Comparison System - Seed Data
// Generated from ${invoices.length} Rhee Bros invoices (9 files, ${invoices.filter(i => i.itemCount > 0).length} with item data)
// Generated on: ${new Date().toISOString()}
// Branches: ${Object.values(BRANCH_MAP).map(b => b.code + '=' + b.name).join(', ')}

const SEED_DATA = ${JSON.stringify(seedData, null, 2)};
`;

fs.writeFileSync(outputFile, output, 'utf8');
console.log(`\nWrote seed_data.js (${(output.length / 1024).toFixed(1)} KB)`);
console.log(`Total invoices: ${invoices.length}`);
console.log(`Total items across all invoices: ${invoices.reduce((s, i) => s + i.itemCount, 0)}`);
