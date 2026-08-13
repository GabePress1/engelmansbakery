/*
 * original/fold-test.js
 * ---------------------
 * Renders a short sample of the real mail piece for a physical fold test on the
 * FPi 700 — the calibration step in docs/fpi-700-fold-spec.md §8.
 *
 * It goes through the SAME buildBatchPdf() the production workflow uses, so what
 * you fold is exactly what you will mail. Re-run it after changing WINDOW_Y_MIN /
 * WINDOW_Y_MAX / WINDOW_X_MAX in pure-pdf.js to check a new calibration.
 *
 * The names are obviously fake so a test print can never be mistaken for real
 * mail, but the address SHAPES mirror the 2026-08-13 run: three-line addresses
 * (16 of 19 records), a four-line address with a suite line (the tallest block,
 * worst case for the window), and an over-long company name that trips the
 * shrink-to-fit. State is deliberately left blank on every record, exactly as
 * Business Central returns it, so the ZIP-derived state shows up in the output.
 *
 *   node original/fold-test.js   ->  out/FPi700-Fold-Test.pdf
 */
const fs = require("fs");
const path = require("path");
const { buildBatchPdf } = require("./pure-pdf");

const OUT = path.join(__dirname, "..", "out", "FPi700-Fold-Test.pdf");

const lines = (n, start) =>
  Array.from({ length: n }, (_, i) => ({
    documentDate: `2025-${String(3 + i).padStart(2, "0")}-14`,
    docType: "Invoice",
    documentNo: "PS-INV" + (start + i),
    orderNo: "Order S-ORD" + (start + i),
    dueDate: `2025-${String(5 + i).padStart(2, "0")}-13`,
    remaining: 240.5 + i * 137.25,
  }));

const samples = [
  {
    label: "three-line address (the common case)",
    tokens: { Description: "SAMPLE - Peachtree Test Cafe", Address_1: "1435 Hills Pl NW",
      Address_2: "", City: "Atlanta", State: "", Zipcode: "30318" },
    statement: lines(5, 160950),
  },
  {
    label: "four-line address with a suite line (tallest block)",
    tokens: { Description: "SAMPLE - Riverdale Test Kitchen", Address_1: "723 Highway 138",
      Address_2: "Unit C", City: "Jonesboro", State: "", Zipcode: "30238" },
    statement: lines(3, 175090),
  },
  {
    label: "over-long company name (trips the shrink-to-fit)",
    tokens: { Description: "SAMPLE - Sterling Estates Retirement Community of West Cobb",
      Address_1: "3165 Dallas Hwy", Address_2: "Building 4, Suite 220", City: "Marietta",
      State: "", Zipcode: "30064" },
    statement: lines(8, 210980),
  },
];

const records = samples.map((s) => {
  const total = s.statement.reduce((a, l) => a + l.remaining, 0);
  return {
    tokens: Object.assign({}, s.tokens, {
      AccountNumber: "TEST-0000",
      Converted_balance: total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    }),
    statement: { lines: s.statement, total },
  };
});

const excluded = [];
const pdf = buildBatchPdf(records, { title: "FPi 700 Fold Test", asOfDate: new Date().toISOString().slice(0, 10), excluded }, "tokens");
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, pdf);

const pages = (pdf.toString("latin1").match(/\/Type\s*\/Page\s/g) || []).length;
console.log(`${OUT}  (${pages} pages, ${records.length - excluded.length} customers, ${pages / 2} duplex sheets)`);
samples.forEach((s, i) => console.log(`  ${i + 1}. ${s.label}`));
if (excluded.length) console.log(`  excluded: ${excluded.map((e) => e.name + " (" + e.reason + ")").join("; ")}`);
console.log(`
Print DOUBLE-SIDED, flip on the LONG edge, at 100% scale (no "fit to page").
Each customer is 2 sheets: letter+address / blank, then statement / blank.
`);
