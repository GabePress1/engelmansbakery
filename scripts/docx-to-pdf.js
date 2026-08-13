/*
 * docx-to-pdf.js
 * --------------
 * Convert a .docx Buffer to a PDF Buffer using headless LibreOffice (soffice).
 *
 * This is the LOCAL renderer used by the test harness. In n8n you have two options,
 * both documented in the README:
 *   (a) an Execute Command node calling `soffice --headless --convert-to pdf ...`, or
 *   (b) an HTTP Request node posting the .docx to a Gotenberg /forms/libreoffice/convert.
 * LibreOffice is required for local runs (`which soffice`).
 */
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

/**
 * @param {Buffer} docxBuffer
 * @param {string} [soffice="soffice"]  path to the LibreOffice binary
 * @returns {Buffer} rendered PDF
 */
function docxToPdf(docxBuffer, soffice = "soffice") {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "docx2pdf-"));
  const inPath = path.join(dir, "doc.docx");
  const outPath = path.join(dir, "doc.pdf");
  try {
    fs.writeFileSync(inPath, docxBuffer);
    execFileSync(
      soffice,
      ["--headless", "--convert-to", "pdf", "--outdir", dir, inPath],
      { stdio: "pipe", env: { ...process.env, HOME: dir } }
    );
    return fs.readFileSync(outPath);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

module.exports = { docxToPdf };
