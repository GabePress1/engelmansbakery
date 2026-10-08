#!/usr/bin/env node
/**
 * Splits the Past Due packs produced by Printing Letter_Invoices into, per account, one
 * letter PDF and one statement PDF.
 *
 * The packs arrive as one PDF per address type (billing, shipping), each holding every
 * past-due account back to back in blocks of:
 *
 *     letter page -> address page -> statement page(s) -> blank separator
 *
 * Block length is deliberately NOT assumed to be four pages: a customer with enough open
 * invoices to spill onto a second statement page still has to work. Blocks are cut at each
 * letter page instead, and the account number is read off the statement page.
 *
 * An account that appears in both packs has differing billing and shipping addresses. Its
 * letter PDF carries both variants, and its statement PDF repeats the statement once per
 * variant, so each printed packet is self-contained.
 *
 * Usage: node tools/split_pack.mjs <billing.pdf> [shipping.pdf] [...]
 * Writes out/Letter_<account>.pdf and out/Statement_<account>.pdf.
 *
 * This is the reference implementation of the logic the n8n "Split Packs by Account" node
 * runs, kept runnable so it can be checked against real packs without an n8n instance.
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { PDFDocument } from 'pdf-lib';
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';

const LETTER_MARKER = /Subject: Past Due Balance/;
const STATEMENT_MARKER = /Past Due Invoices/;
const ACCOUNT_MARKER = /Account Number:\s*(\d+)/;

async function classifyPages(bytes) {
  const doc = await getDocument({ data: new Uint8Array(bytes), useSystemFonts: true }).promise;
  const pages = [];

  for (let i = 1; i <= doc.numPages; i++) {
    const flat = (await (await doc.getPage(i)).getTextContent())
      .items.map((t) => t.str).join(' ').replace(/\s+/g, ' ').trim();

    let kind = 'blank';
    if (LETTER_MARKER.test(flat)) kind = 'letter';
    else if (STATEMENT_MARKER.test(flat)) kind = 'statement';
    else if (flat.length > 0) kind = 'address';

    pages.push({
      index: i - 1,
      kind,
      accountNumber: flat.match(ACCOUNT_MARKER)?.[1] ?? null,
    });
  }

  return pages;
}

function toBlocks(pages) {
  const blocks = [];

  for (const page of pages) {
    if (page.kind === 'letter' || blocks.length === 0) blocks.push([]);
    blocks[blocks.length - 1].push(page);
  }

  return blocks
    .map((block) => ({
      accountNumber: block.find((p) => p.accountNumber)?.accountNumber ?? null,
      // Letter side is everything before the statement starts: the letter and its address
      // page. Blank separators exist for duplex printing and are dropped.
      letterPages: block.filter((p) => p.kind === 'letter' || p.kind === 'address').map((p) => p.index),
      statementPages: block.filter((p) => p.kind === 'statement').map((p) => p.index),
    }))
    .filter((block) => block.accountNumber);
}

async function buildPdf(parts) {
  const out = await PDFDocument.create();

  for (const { bytes, pages } of parts) {
    const source = await PDFDocument.load(bytes);
    const copied = await out.copyPages(source, pages);
    for (const page of copied) out.addPage(page);
  }

  return out.save();
}

async function main(files) {
  if (files.length === 0) {
    console.error('usage: node tools/split_pack.mjs <billing.pdf> [shipping.pdf] [...]');
    process.exit(1);
  }

  /** @type {Map<string, {letter: object[], statement: object[]}>} */
  const accounts = new Map();

  for (const file of files) {
    const bytes = await readFile(file);
    for (const block of toBlocks(await classifyPages(bytes))) {
      if (!accounts.has(block.accountNumber)) {
        accounts.set(block.accountNumber, { letter: [], statement: [] });
      }
      const account = accounts.get(block.accountNumber);
      account.letter.push({ bytes, pages: block.letterPages });
      // One statement per address variant: a customer whose billing and shipping addresses
      // differ gets two printed packets, and each needs its own copy.
      account.statement.push({ bytes, pages: block.statementPages });
    }
  }

  await mkdir('out', { recursive: true });

  for (const [accountNumber, parts] of accounts) {
    await writeFile(`out/Letter_${accountNumber}.pdf`, await buildPdf(parts.letter));
    await writeFile(`out/Statement_${accountNumber}.pdf`, await buildPdf(parts.statement));

    const variants = parts.letter.length;
    const count = (p) => p.reduce((n, x) => n + x.pages.length, 0);
    console.log(
      `acct ${accountNumber}: ${variants} address variant${variants > 1 ? 's' : ''}, ` +
      `letter ${count(parts.letter)}p, statement ${count(parts.statement)}p`
    );
  }
}

await main(process.argv.slice(2));
