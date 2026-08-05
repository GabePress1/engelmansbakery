/*
 * run-local.js
 * ------------
 * End-to-end local proof of the pipeline WITHOUT Business Central or n8n:
 *   sample data -> transform -> render statement PDFs (pure JS, no deps).
 * Outputs land in ./out. Run:
 *   node test/run-local.js
 */
const fs = require("fs");
const path = require("path");

const { buildRecords } = require("../scripts/transform");
const { buildCustomerPdf, buildBatchPdf, customerPages } = require("../scripts/pure-pdf");

const ROOT = path.join(__dirname, "..");
const OUT = path.join(ROOT, "out");

function safeName(s) {
  return String(s).replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "");
}

let failures = 0;
function assert(cond, msg) {
  if (!cond) { failures++; console.error("  ASSERT FAILED: " + msg); }
}

// Count page objects in a PDF ("/Type /Page " but not "/Type /Pages").
function countPages(pdf) {
  return (pdf.toString("latin1").match(/\/Type\s*\/Page\s/g) || []).length;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });

  const data = JSON.parse(
    fs.readFileSync(path.join(__dirname, "sample-customers.json"), "utf8")
  );

  const records = buildRecords(data.customers, data.ledgerEntries, {
    amountSource: "filtered", // switch to "balanceDue" to use Balance_Due_LCY
    today: "2026-07-17",
    salesOrders: data.salesOrders, // tomorrow's orders -> gate + route
  });

  // --- transform assertions -------------------------------------------------
  assert(records.length === 2, `expected 2 qualifying customers, got ${records.length}`);
  assert(!records.some((r) => r.customerNo === "C00034"), "C00034 (fully paid) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00050"), "C00050 (negative net) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00060"), "C00060 (not past due) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00070"), "C00070 (2025-only doc date) must be excluded");
  assert(!records.some((r) => r.customerNo === "C00080"),
    "C00080 excluded: its DEFAULT route is RT 21 (even though tomorrow's order is RT 8) — proves the exclusion uses the customer's route");
  assert(!records.some((r) => r.customerNo === "C00090"),
    "C00090 (past due but NOT ordering tomorrow) must be excluded");

  // Sorted by Route: RT 5 (20382) before RT 8 (C00021).
  assert(records[0].customerNo === "20382" && records[1].customerNo === "C00021",
    `records should sort by Route (RT 5 then RT 8), got ` +
      records.map((r) => r.customerNo + "/" + r.tokens.Route).join(", "));

  const stiles = records.find((r) => r.customerNo === "20382");
  assert(!!stiles, "20382 should qualify (past due + ordering tomorrow on RT 5)");
  if (stiles) {
    assert(stiles.tokens.Route === "RT 5", `20382 route should be RT 5, got ${stiles.tokens.Route}`);
    assert(stiles.tokens.Converted_balance === "3,500.50",
      `20382 balance expected 3,500.50, got ${stiles.tokens.Converted_balance}`);
    assert(!("Address_1" in stiles.tokens), "tokens should carry NO mailing address (route replaces it)");
    assert(stiles.statement.lines.length === 3,
      `20382 expected 3 lines (2 past-due invoices + 1 credit), got ${stiles.statement.lines.length}`);
    const inv1 = stiles.statement.lines.find((l) => l.documentNo === "5192222");
    assert(inv1 && inv1.orderNo === "Order S-ORD1001", "Order No. should be the Description");
    assert(inv1 && inv1.docType === "Invoice", "docType should be Invoice");
  }
  const blue = records.find((r) => r.customerNo === "C00021");
  assert(blue && blue.tokens.Route === "RT 8", `C00021 route should be RT 8, got ${blue && blue.tokens.Route}`);

  // With the default 2024 cutoff, C00070 (2025-only doc date) is excluded even though
  // it is ordering tomorrow.
  assert(!records.some((r) => r.customerNo === "C00070"),
    "C00070 (2025-only doc date) excluded under the default Oldest_Open_Invoice cutoff");

  // --- minimum-balance threshold (the "Settings" node) ----------------------
  const highBar = buildRecords(data.customers, data.ledgerEntries, {
    amountSource: "filtered", today: "2026-07-17", salesOrders: data.salesOrders, minBalance: 1500,
  });
  assert(highBar.length === 1 && highBar[0].customerNo === "20382",
    "minBalance 1500 -> only 20382 (net 3,500.50); C00021 ($1,290) excluded");

  // --- blank Oldest_Open_Invoice -> any overdue invoice qualifies -----------
  const anyAge = buildRecords(data.customers, data.ledgerEntries, {
    amountSource: "filtered", today: "2026-07-17", salesOrders: data.salesOrders, qualifyCutoff: "",
  });
  assert(anyAge.some((r) => r.customerNo === "C00070"),
    "blank Oldest_Open_Invoice -> C00070 (2025 overdue invoice, ordering tomorrow) now qualifies");
  assert(anyAge.length === 3,
    `blank cutoff -> 3 customers (20382, C00021, C00070), got ${anyAge.length}`);

  console.log(`Qualifying customers: ${records.length}`);

  for (const rec of records) {
    const name = safeName(rec.tokens.Description) || rec.customerNo;

    // Statement-only PDF (no letter, no address). Padded to even pages for duplex.
    const pdf = buildCustomerPdf(rec.tokens, rec.statement, { asOfDate: "2026-07-14" });
    assert(pdf.slice(0, 5).toString() === "%PDF-", `${name}: output is not a PDF`);
    const pages = customerPages(rec.tokens, rec.statement, { asOfDate: "2026-07-14" }).length;
    assert(pages % 2 === 0 && pages >= 2,
      `${name}: each statement should be padded to an even page count, got ${pages}`);
    fs.writeFileSync(path.join(OUT, `${name}.pdf`), pdf);

    console.log(
      `  ${rec.tokens.Description} (Route ${rec.tokens.Route}): $${rec.tokens.Converted_balance}  ` +
        `${rec.statement.lines.length} line(s), ${pages} page(s) -> out/${name}.pdf`
    );
  }

  // One combined PDF: statements only, sorted by route, each padded to even pages.
  const notice = buildBatchPdf(records, { asOfDate: "2026-07-17", title: "Past Due Notice" }, "tokens");
  assert(notice.slice(0, 5).toString() === "%PDF-", "combined PDF invalid");
  const totalPages = countPages(notice);
  assert(totalPages === 4, `combined PDF should be 4 pages (2 customers x 2), got ${totalPages}`);
  fs.writeFileSync(path.join(OUT, "Past-Due-Notice.pdf"), notice);
  console.log(`Combined: out/Past-Due-Notice.pdf  (${records.length} customers, ${totalPages} pages)`);

  // pad:false -> compact copy: no blank filler pages (each 1-page statement stays 1 page).
  const oneCompact = customerPages(records[0].tokens, records[0].statement, { asOfDate: "2026-07-17", pad: false }).length;
  assert(oneCompact === 1, `pad:false single customer (1-page stmt) should be 1 page, got ${oneCompact}`);
  const compact = buildBatchPdf(records, { asOfDate: "2026-07-17", pad: false }, "tokens");
  const compactPages = countPages(compact);
  assert(compactPages === 2, `compact (pad:false) should be 2 pages (no blanks), got ${compactPages}`);
  console.log(`Compact (pad:false): ${compactPages} pages`);

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
