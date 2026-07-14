/*
 * run-local.js
 * ------------
 * End-to-end local proof of the pipeline WITHOUT Business Central or n8n:
 *   sample data -> transform -> render letter + statement PDFs (pure pdf-lib)
 *   -> merge letter+statement per customer -> batch PDF.
 * Also fills the Word template (docxtemplater) and ASSERTS the merge tokens
 * landed, so the "Word mail merge" path is verified too.
 *
 * Outputs land in ./out (PDFs + filled .docx). Run:
 *   node templates/build-template.js   # once, to (re)build the template
 *   node test/run-local.js
 */
const fs = require("fs");
const path = require("path");
const PizZip = require("pizzip");

const { buildRecords } = require("../scripts/transform");
const { fillLetter } = require("../scripts/fill-letter");
const { renderLetterPdf, renderStatementPdf } = require("../scripts/render-pdf");
const { mergePdfs } = require("../scripts/merge-pdfs");

const ROOT = path.join(__dirname, "..");
const OUT = path.join(ROOT, "out");
const TEMPLATE = path.join(ROOT, "templates", "past-due-letter.docx");

function safeName(s) {
  return String(s).replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "");
}

// Read the text of word/document.xml out of a .docx buffer (for assertions).
function docxText(buf) {
  return new PizZip(buf).file("word/document.xml").asText();
}

let failures = 0;
function assert(cond, msg) {
  if (!cond) { failures++; console.error("  ASSERT FAILED: " + msg); }
}

async function main() {
  if (!fs.existsSync(TEMPLATE)) {
    throw new Error("Template missing. Run: node templates/build-template.js");
  }
  fs.mkdirSync(OUT, { recursive: true });

  const data = JSON.parse(
    fs.readFileSync(path.join(__dirname, "sample-customers.json"), "utf8")
  );
  const templateBuf = fs.readFileSync(TEMPLATE);

  const records = buildRecords(data.customers, data.ledgerEntries, {
    amountSource: "filtered", // switch to "balanceDue" to use Balance_Due_LCY
  });

  // --- transform assertions -------------------------------------------------
  assert(records.length === 2, `expected 2 qualifying customers, got ${records.length}`);
  assert(!records.some((r) => r.customerNo === "C00034"), "C00034 (fully paid) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00045"),
    "C00045 (open invoice but dated 2025, out of window) must be excluded");
  const sunrise = records.find((r) => r.customerNo === "C00010");
  assert(!!sunrise, "C00010 should qualify");
  if (sunrise) {
    // 3200.50 + 1620.25 in-window; the 900.00 (2022) must be excluded.
    assert(sunrise.tokens.Converted_balance === "4,820.75",
      `C00010 balance expected 4,820.75, got ${sunrise.tokens.Converted_balance}`);
    assert(sunrise.statement.lines.length === 2,
      `C00010 expected 2 in-window invoices, got ${sunrise.statement.lines.length}`);
  }

  console.log(`Qualifying customers: ${records.length}`);
  const perCustomerPdfs = [];

  for (const rec of records) {
    const name = safeName(rec.tokens.Description) || rec.customerNo;

    // 1) Word mail-merge path: fill template + assert tokens landed
    const letterDocx = fillLetter(templateBuf, rec.tokens);
    const xml = docxText(letterDocx);
    assert(xml.includes(rec.tokens.Description), `docx missing name for ${name}`);
    assert(xml.includes(rec.tokens.Converted_balance), `docx missing balance for ${name}`);
    assert(!xml.includes("{Description}") && !xml.includes("{Converted_balance}"),
      `docx still has unfilled tags for ${name}`);
    fs.writeFileSync(path.join(OUT, `${name}.docx`), letterDocx);

    // 2) Default render path: pure-JS PDF for letter + statement
    const letterPdf = await renderLetterPdf(rec.tokens);
    const stmtPdf = await renderStatementPdf(rec.tokens, rec.statement, {
      asOfDate: "2026-07-14",
    });

    // 3) Merge letter + statement
    const merged = await mergePdfs([letterPdf, stmtPdf]);
    const outFile = path.join(OUT, `${name}.pdf`);
    fs.writeFileSync(outFile, merged);
    perCustomerPdfs.push(merged);

    console.log(
      `  ${rec.tokens.Description}: $${rec.tokens.Converted_balance}  ` +
        `(${rec.statement.lines.length} open invoice(s)) -> out/${name}.pdf (+ .docx)`
    );
  }

  // 4) Combined batch PDF for the printer
  const batch = await mergePdfs(perCustomerPdfs);
  fs.writeFileSync(path.join(OUT, "batch-all.pdf"), batch);
  console.log(`Batch: out/batch-all.pdf`);

  if (failures) {
    console.error(`\n${failures} assertion(s) failed.`);
    process.exit(1);
  }
  console.log("\nAll assertions passed.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
