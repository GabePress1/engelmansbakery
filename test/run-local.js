/*
 * run-local.js
 * ------------
 * End-to-end local proof of the pipeline WITHOUT Business Central or n8n:
 *   sample data -> transform -> render letter + statement PDFs (pure JS, no deps)
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
const { buildCustomerPdf, buildBatchPdf } = require("../scripts/pure-pdf");

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
    today: "2026-07-17",
  });

  // --- transform assertions -------------------------------------------------
  assert(records.length === 2, `expected 2 qualifying customers, got ${records.length}`);
  assert(!records.some((r) => r.customerNo === "C00034"), "C00034 (fully paid) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00050"),
    "C00050 (negative net balance) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00060"),
    "C00060 (no past-due invoice) must be excluded");
  const stiles = records.find((r) => r.customerNo === "20382");
  assert(!!stiles, "20382 should qualify (positive net past-due balance)");
  if (stiles) {
    // 3200.50 + 500.00 past-due invoices - 200.00 open credit = 3500.50.
    // The 290.11 invoice (not yet due) is excluded.
    assert(stiles.tokens.Converted_balance === "3,500.50",
      `20382 balance expected 3,500.50, got ${stiles.tokens.Converted_balance}`);
    assert(stiles.statement.lines.length === 3,
      `20382 expected 3 lines (2 past-due invoices + 1 credit), got ${stiles.statement.lines.length}`);
    assert(stiles.statement.lines.some((l) => l.kind === "credit" && l.remaining < 0),
      "20382 statement should include a negative credit line");
    assert(stiles.tokens.AccountNumber === "20382",
      `20382 AccountNumber token missing/wrong: ${stiles.tokens.AccountNumber}`);
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

    // 2) Default render path: zero-dependency PDF (letter + statement as one doc)
    const merged = buildCustomerPdf(rec.tokens, rec.statement, { asOfDate: "2026-07-14" });
    assert(merged.slice(0, 5).toString() === "%PDF-", `${name}: output is not a PDF`);
    const outFile = path.join(OUT, `${name}.pdf`);
    fs.writeFileSync(outFile, merged);
    perCustomerPdfs.push(merged);

    console.log(
      `  ${rec.tokens.Description}: $${rec.tokens.Converted_balance}  ` +
        `(${rec.statement.lines.length} open invoice(s)) -> out/${name}.pdf (+ .docx)`
    );
  }

  // 4) Combined batch PDF for the printer
  const batch = buildBatchPdf(records, { asOfDate: "2026-07-14" });
  assert(batch.slice(0, 5).toString() === "%PDF-", "batch output is not a PDF");
  fs.writeFileSync(path.join(OUT, "batch-all.pdf"), batch);
  console.log(`Batch: out/batch-all.pdf  (${perCustomerPdfs.length} customers)`);

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
