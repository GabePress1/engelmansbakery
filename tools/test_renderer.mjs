#!/usr/bin/env node
// Runs the Render Letter + Statement Code node against mock records, with n8n stubbed,
// so the renderer can be checked without an n8n instance or a Business Central tenant.
// Usage: cd tools && npm install && cd .. && node tools/test_renderer.mjs
// Runs the new "Render Letter + Statement" Code node verbatim, with n8n stubbed.
import { readFile, writeFile } from 'node:fs/promises';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';

const wfPath = new URL('../workflows/emailing-letter-statement-draft.json', import.meta.url);
const wf = JSON.parse(await readFile(wfPath, 'utf8'));
const code = wf.nodes.find((n) => n.name === 'Render Letter + Statement').parameters.jsCode;

const mkLines = (n) => Array.from({ length: n }, (_, i) => ({
  Document_Date: `2026-08-${String((i % 28) + 1).padStart(2, '0')}`,
  Document_Type: 'Invoice', Document_No: `PS-INV2445${i}`, Order_No: `S-ORD2445${i}`,
  Due_Date: `2026-09-${String((i % 28) + 1).padStart(2, '0')}`, Remaining_Amount: 100 + i,
}));

const billing = {
  Description: 'Cosm', AccountNumber: '13287',
  Address_1: '85 Centennial Olympic Park Dr NW', Address_2: 'Suite A100',
  City: 'Atlanta', State: 'GA', Zipcode: '30303', Converted_balance: '6,661.23',
};
// Same account, genuinely different ship-to.
const shipDiff = { ...billing, Address_1: '1 Peachtree St', Address_2: '', City: 'Atlanta', Zipcode: '30303' };

const items = [
  { json: { customerNo: '13287', tokens: billing, statement: { lines: mkLines(14), total: 6661.23 } } },
  { json: { customerNo: '12308', tokens: { ...billing, AccountNumber: '12308', Description: 'That Burger Spot' },
            shipTokens: { ...shipDiff, AccountNumber: '12308', Description: 'That Burger Spot' },
            statement: { lines: mkLines(6), total: 1234.5 } } },
];

const customers = { json: { value: [
  { No: '13287', Name: 'Cosm', E_Mail: 'ap@cosm.example' },
  { No: '12308', Name: 'That Burger Spot', E_Mail: '' },   // no email on file
] } };
const helpers = { async prepareBinaryData(b, n, m) { return { b, n, m }; } };
const out = await new Function('items', '$input', '$', 'Buffer',
  `return (async function(){${code}}).call(this)`)
  .call({ helpers }, items, { all: () => items }, (name) => ({ all: () => (name === 'Get Customers' ? [customers] : []), first: () => ({ json: {} }) }), Buffer);

console.log(`emitted ${out.length} account item(s)\n`);
for (const it of out) {
  const j = it.json;
  const pages = async (b64) => (await getDocument({ data: new Uint8Array(Buffer.from(b64, 'base64')), useSystemFonts: true }).promise).numPages;
  console.log(`  acct ${j.accountNumber} (${j.accountName}) | variants=${j.addressVariants} | email=${j.recipientEmail || '(none)'}`);
  console.log(`     letter    : ${await pages(j.letterBase64)}p  claimed ${j.letterPageCount}  ${j.letterFileName}`);
  console.log(`     statement : ${await pages(j.statementBase64)}p  claimed ${j.statementPageCount}  ${j.statementFileName}`);
  await writeFile(`out_${j.accountNumber}_letter.pdf`, Buffer.from(j.letterBase64, 'base64'));
  await writeFile(`out_${j.accountNumber}_statement.pdf`, Buffer.from(j.statementBase64, 'base64'));
}
