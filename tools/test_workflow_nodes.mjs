#!/usr/bin/env node
// Usage: node tools/test_workflow_nodes.mjs <billing.pdf> <shipping.pdf>
// Deps live in tools/ (npm install), and the packs are passed as arguments.
// Runs the Explode and Assemble Code-node sources verbatim out of the workflow export,
// with n8n's $input / $() / this.helpers stubbed, against the real packs.
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';

const require = createRequire(import.meta.url);
const wfPath = new URL('../workflows/emailing-letter-statement-draft.json', import.meta.url);
const wf = JSON.parse(await readFile(wfPath, 'utf8'));
const src = (name) => wf.nodes.find((n) => n.name === name).parameters.jsCode;

const helpers = {
  async getBinaryDataBuffer(i, key) { return packs[i].binary[key].buffer; },
  async prepareBinaryData(buffer, fileName, mimeType) { return { buffer, fileName, mimeType }; },
};
const run = (code, ctx) =>
  new Function('$input', '$', 'require', 'Buffer', `return (async function(){${code}}).call(this)`)
    .call({ helpers }, ctx.$input, ctx.$, require, Buffer);

// --- Printing Letter_Invoices output ---
const files = process.argv.slice(2);
if (files.length === 0) {
  console.error('usage: node tools/test_workflow_nodes.mjs <billing.pdf> [shipping.pdf]');
  process.exit(1);
}
const packs = [];
for (const f of files) packs.push({ binary: { data: { buffer: await readFile(f) } } });

const pages = await run(src('Explode Packs to Pages'), { $input: { all: () => packs }, $: null });
console.log(`Explode Packs to Pages -> ${pages.length} page items`);

// --- stand in for n8n's Extract from File (pdf) node ---
const extracted = [];
for (const p of pages) {
  const doc = await getDocument({ data: new Uint8Array(p.binary.page.buffer), useSystemFonts: true }).promise;
  const text = (await (await doc.getPage(1)).getTextContent()).items.map((t) => t.str).join(' ');
  extracted.push({ json: { pageText: text } });
}

const accounts = await run(src('Assemble Letter + Statement'), {
  $input: { all: () => extracted },
  $: (name) => ({ all: () => (name === 'Explode Packs to Pages' ? pages : []) }),
});

console.log(`Assemble Letter + Statement -> ${accounts.length} account items\n`);
const { PDFDocument } = require('pdf-lib');
for (const a of accounts) {
  const j = a.json;
  const letter = await PDFDocument.load(Buffer.from(j.letterBase64, 'base64'));
  const statement = await PDFDocument.load(Buffer.from(j.statementBase64, 'base64'));
  console.log(
    `  acct ${j.accountNumber}: ${j.addressVariants} variant(s) | ` +
    `letter ${letter.getPageCount()}p (claimed ${j.letterPageCount}) | ` +
    `statement ${statement.getPageCount()}p (claimed ${j.statementPageCount})`
  );
}
