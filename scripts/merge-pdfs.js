/*
 * merge-pdfs.js
 * -------------
 * Combine PDFs with pdf-lib (pure JS, no native deps — runs in an n8n Code node).
 * Used to (a) join each customer's letter + statement, and (b) build one batch PDF.
 */
const { PDFDocument } = require("pdf-lib");

/**
 * @param {Buffer[]} pdfBuffers  PDFs to concatenate, in order
 * @returns {Promise<Buffer>} single merged PDF
 */
async function mergePdfs(pdfBuffers) {
  const out = await PDFDocument.create();
  for (const buf of pdfBuffers) {
    if (!buf || !buf.length) continue;
    const src = await PDFDocument.load(buf);
    const pages = await out.copyPages(src, src.getPageIndices());
    pages.forEach((p) => out.addPage(p));
  }
  const bytes = await out.save();
  return Buffer.from(bytes);
}

module.exports = { mergePdfs };
