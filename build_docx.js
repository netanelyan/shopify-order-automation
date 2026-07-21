/**
 * build_docx.js
 * -------------
 * Reads the JSON produced by parse_orders.py and writes a .docx file.
 *
 * Usage:
 *   node build_docx.js orders.json output.docx
 */

const { Document, Packer, Paragraph, TextRun, PageBreak } = require('docx');
const fs = require('fs');

const [,, inputJson, outputDocx] = process.argv;

if (!inputJson || !outputDocx) {
  console.error('Usage: node build_docx.js <orders.json> <output.docx>');
  process.exit(1);
}

const orders = JSON.parse(fs.readFileSync(inputJson, 'utf8'));

// ── Helpers ──────────────────────────────────────────────────────────────────

function p(runs, before = 0, after = 60) {
  return new Paragraph({ children: runs, spacing: { before, after } });
}

function blank() {
  return new Paragraph({ children: [], spacing: { before: 0, after: 80 } });
}

// Asterisks = bold in WhatsApp; do NOT use actual bold formatting
function b(text, size = 22) {
  return new TextRun({ text: `*${text}*`, size, font: 'Arial' });
}

function n(text, size = 22) {
  return new TextRun({ text, size, font: 'Arial' });
}

// ── Order builder ─────────────────────────────────────────────────────────────

function buildOrder(order, isLast) {
  const blocks = [];

  // Header — no blank lines between any of these lines
  blocks.push(p([b(`Order number ${order.order}`, 26)], 0, 0));
  blocks.push(p([b('Shipping info')],                   0, 0));
  blocks.push(p([n(order.shipping_name)],               0, 0));
  blocks.push(p([n(`${order.address}${order.city ? ', ' + order.city : ''}`)], 0, 0));
  blocks.push(p([n(order.phone)],                       0, 0));
  blocks.push(p([n(order.email)],                       0, 0));
  blocks.push(p([b(`price - $${order.price}`)],         0, 160));

  // Order note — often a Hebrew instruction from the customer or staff that
  // changes what the supplier must print. Flagged loudly; translate by hand.
  if (order.note) {
    blocks.push(p([b('⚠ ORDER NOTE — READ')], 0, 0));
    blocks.push(p([n(order.note)], 0, 160));
  }

  // Items — qty field expands duplicates in place (preserves Shopify row order)
  let itemNum = 0;
  order.items.forEach((item) => {
    const qty = item.qty || 1;
    for (let q = 0; q < qty; q++) {
      itemNum++;
      blocks.push(p([b(`item ${itemNum} details`)], 0, 60));
      blocks.push(p([n(`Edition - ${item.edition}`)]));
      blocks.push(p([n(`Kit - ${item.kit}`)]));
      blocks.push(p([n(`Size - ${item.size || '?'}`)]));
      if (item.name)                             blocks.push(p([n(`Name - ${item.name}`)]));
      if (item.number)                           blocks.push(p([n(`Number - ${item.number}`)]));
      if (item.patch && item.patch !== '—')      blocks.push(p([n(`Patch - ${item.patch}`)]));
      if (item.has_pants)                        blocks.push(p([n('Note: +Pants')]));
      if (item.unclear)                          blocks.push(p([b('⚠ CHECK: '), n(item.raw)]));
      blocks.push(blank());
    }
  });

  if (!isLast) {
    blocks.push(new Paragraph({
      children: [new PageBreak()],
      spacing: { before: 0, after: 0 },
    }));
  }

  return blocks;
}

// ── Build document ────────────────────────────────────────────────────────────

const allChildren = [];
orders.forEach((order, i) => {
  buildOrder(order, i === orders.length - 1).forEach(c => allChildren.push(c));
});

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
  },
  sections: [{
    properties: {
      page: {
        size:   { width: 12240, height: 15840 },   // US Letter
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }, // 1 inch
      },
    },
    children: allChildren,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outputDocx, buf);
  console.log(`✓ Written to ${outputDocx}`);
});
