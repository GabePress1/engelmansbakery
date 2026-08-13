/*
 * original/test.js
 * ----------------
 * Verifies the "Printing Letter_Invoices  Original" build (letter + statement,
 * billing + shipping) plus the three requested changes:
 *   1. Shipping PDF excludes customers whose ship-to == billing address.
 *   2. Each account is padded to an even page count (letter sheet + invoice sheet).
 *   3. A Min_Overdue_Balance threshold (Settings node) gates who gets a letter.
 *
 *   node original/test.js
 */
const fs = require("fs");
const path = require("path");

const { buildRecords } = require("./transform");
const { buildBatchPdf, customerPages, sameAddress, addressProblem, cityStateZip, stateFromZip } = require("./pure-pdf");

const sample = JSON.parse(fs.readFileSync(path.join(__dirname, "sample.json"), "utf8"));
const wf = JSON.parse(fs.readFileSync(path.join(__dirname, "Printing_Letter_Invoices_Original.workflow.json"), "utf8"));

let failures = 0;
const assert = (c, m) => { if (!c) { failures++; console.error("  FAIL: " + m); } };
const codeOf = (name) => wf.nodes.find((n) => n.name === name).parameters.jsCode;
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const countPages = (pdf) => (pdf.toString("latin1").match(/\/Type\s*\/Page\s/g) || []).length;

async function main() {
  // ---- Unit: transform + pure-pdf ----------------------------------------
  const records = buildRecords(sample.customers, sample.ledgerEntries, {
    amountSource: "filtered", today: "2026-07-17", shipTos: sample.shipTos,
  });
  assert(records.length === 2, `expected 2 qualifying customers, got ${records.length}`);

  // (2) Each account is an even page count: letter (2) + statement (padded to 2) = 4.
  for (const r of records) {
    const pages = customerPages(r.tokens, r.statement, { asOfDate: "2026-07-14" }).length;
    assert(pages % 2 === 0, `${r.customerNo}: account should be an even page count, got ${pages}`);
    assert(pages === 4, `${r.customerNo}: account should be 4 pages (letter sheet + invoice sheet), got ${pages}`);
  }

  // (1) Shipping de-dup: 20382 has a distinct ship-to; C00021 has none (== billing).
  const shippingRecords = records.filter((r) => r.shipTokens && !sameAddress(r.tokens, r.shipTokens));
  assert(shippingRecords.length === 1 && shippingRecords[0].customerNo === "20382",
    `shipping should hold only 20382 (distinct ship-to), got ${shippingRecords.map((r) => r.customerNo).join(",")}`);

  // (3) Threshold: minBalance 1300 -> only 20382 ($3,500); C00021 ($1,290) drops.
  const gated = buildRecords(sample.customers, sample.ledgerEntries, {
    amountSource: "filtered", today: "2026-07-17", shipTos: sample.shipTos, minBalance: 1300,
  });
  assert(gated.length === 1 && gated[0].customerNo === "20382",
    `minBalance 1300 -> only 20382, got ${gated.map((r) => r.customerNo).join(",")}`);

  // (4) pad:false -> compact: letter (1, address included) + statement (1) = 2 pages/account.
  for (const r of records) {
    const pages = customerPages(r.tokens, r.statement, { asOfDate: "2026-07-14", pad: false }).length;
    assert(pages === 2, `${r.customerNo}: compact account should be 2 pages, got ${pages}`);
  }

  // (4b) The address rides on the FRONT of sheet 1, with the letter. Only one face
  // of the folded piece shows through the window, and the front is the face the
  // standard fold presents — an address on the back only works if the machine
  // folds reverse-side-out. Nothing but the address may sit in the window band.
  const WIN_LO = 36, WIN_HI = 84;
  for (const r of records) {
    const set = customerPages(r.tokens, r.statement, { asOfDate: "2026-07-14" });
    assert(set.length === 4, `${r.customerNo}: set should still be 4 pages, got ${set.length}`);
    assert(set[0].includes("Subject:"), `${r.customerNo}: page 1 should carry the letter`);
    assert(set[0].includes(r.tokens.Address_1), `${r.customerNo}: page 1 should carry the address`);
    assert(set[1] === "", `${r.customerNo}: back of sheet 1 should be blank, got ${set[1].length} bytes`);
    // Every glyph on page 1 is either clear of the band, or part of the address.
    const addrLines = [r.tokens.Description, r.tokens.Address_1, r.tokens.Address_2, cityStateZip(r.tokens)]
      .filter(Boolean);
    for (const m of set[0].matchAll(/BT \/(\w+) ([\d.]+) Tf 1 0 0 1 ([\d.-]+) ([\d.-]+) Tm \((.*?)\) Tj ET/g)) {
      const size = Number(m[2]), y = Number(m[4]), body = m[5];
      const top = y + size * 0.73, bot = y - size * 0.22;
      if (top < WIN_LO || bot > WIN_HI) continue; // clear of the window band
      assert(addrLines.some((l) => body === l),
        `${r.customerNo}: non-address text "${body}" intrudes into the window band at y=${y}`);
    }
    // ...and every address line is fully inside it.
    for (const line of addrLines) {
      const m = new RegExp(`Tf 1 0 0 1 [\\d.-]+ ([\\d.-]+) Tm \\(${line.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\) Tj`).exec(set[0]);
      assert(m, `${r.customerNo}: address line "${line}" missing from page 1`);
      if (m) {
        const y = Number(m[1]);
        assert(y - 10 * 0.22 >= WIN_LO && y + 10 * 0.73 <= WIN_HI,
          `${r.customerNo}: address line "${line}" at y=${y} falls outside the window band`);
      }
    }
  }

  // (5) Editable cutoff: blank -> the 2025-only customer (C00070) now qualifies.
  const anyAge = buildRecords(sample.customers, sample.ledgerEntries, {
    amountSource: "filtered", today: "2026-07-17", shipTos: sample.shipTos, qualifyCutoff: "",
  });
  assert(anyAge.some((r) => r.customerNo === "C00070"),
    "blank cutoff -> C00070 (2025-only overdue) now qualifies");

  // (6) RT 21 exclusion: C00099 (default route RT 21) is dropped even though it qualifies.
  assert(!records.some((r) => r.customerNo === "C00099"),
    "C00099 (Customer route RT 21) must be excluded from the mailing");
  const withRt21 = buildRecords(sample.customers, sample.ledgerEntries, {
    amountSource: "filtered", today: "2026-07-17", shipTos: sample.shipTos, excludeRoute: null,
  });
  assert(withRt21.some((r) => r.customerNo === "C00099"),
    "excludeRoute:null -> C00099 (RT 21) is included, confirming the route filter is what drops it");

  // (7) Set length is FIXED, not merely even. The FPi 700 has no OMR, so it
  // separates customers by counting sheets: a set that runs to a third sheet
  // shifts every later customer into the wrong envelope. A long statement must
  // condense onto one sheet, never spill. See docs/fpi-700-fold-spec.md §4.
  const longStmt = (n) => {
    const lines = Array.from({ length: n }, (_, i) => ({
      documentDate: "2025-01-01", docType: "Invoice", documentNo: "PS-INV" + (100000 + i),
      orderNo: "Order S-ORD" + (100000 + i), dueDate: "2026-01-05", remaining: 100 + i,
    }));
    return { lines, total: lines.reduce((a, l) => a + l.remaining, 0) };
  };
  const bigTokens = records[0].tokens;
  for (const n of [0, 1, 66, 67, 500]) {
    const pages = customerPages(bigTokens, longStmt(n), { asOfDate: "2026-07-14" });
    assert(pages && pages.length === 4, `${n}-line statement should be 4 pages, got ${pages && pages.length}`);
  }
  const condensed = customerPages(bigTokens, longStmt(500), { asOfDate: "2026-07-14" }).join("");
  assert(condensed.includes("Balance Forward"), "a 500-line statement should carry a Balance Forward row");
  // The condensed statement must still reconcile: rows sum to the printed total.
  const big = longStmt(500);
  const amounts = [...condensed.matchAll(/\((-?)\$([\d,]+\.\d\d)\) Tj/g)]
    .map((m) => (m[1] ? -1 : 1) * Number(m[2].replace(/,/g, "")));
  const printedTotal = amounts[amounts.length - 1];
  const rowSum = amounts.slice(0, -1).reduce((a, b) => a + b, 0);
  assert(Math.abs(printedTotal - big.total) < 0.01, `condensed total ${printedTotal} != ${big.total}`);
  assert(Math.abs(rowSum - big.total) < 0.01, `condensed rows sum to ${rowSum}, expected ${big.total}`);
  // The compact on-screen copy has no machine to satisfy, so it stays uncondensed.
  const compactLong = customerPages(bigTokens, longStmt(500), { asOfDate: "2026-07-14", pad: false });
  assert(compactLong.length > 4 && !compactLong.join("").includes("Balance Forward"),
    `compact copy should run long and uncondensed, got ${compactLong.length} pages`);
  // And the batch as a whole is exactly 4 pages per customer.
  const mixed = [0, 500, 3, 900].map((n) => ({ tokens: bigTokens, statement: longStmt(n) }));
  const mixedPdf = buildBatchPdf(mixed, { asOfDate: "2026-07-14" }, "tokens");
  const mixedPages = (mixedPdf.toString("latin1").match(/\/Type\s*\/Page\s/g) || []).length;
  assert(mixedPages === mixed.length * 4,
    `mixed batch should be ${mixed.length * 4} pages, got ${mixedPages}`);

  // (8) Address hygiene. Business Central leaves County empty on every customer
  // and ship-tos carry no state field at all, so the state is derived from the
  // ZIP. Placeholder junk ("-") is not an address: the 2026-08-13 run mailed two
  // envelopes whose entire city/state/ZIP line was a single dash. See spec §7.
  const addrOf = (o) => Object.assign(
    { Description: "Acme Co", Address_1: "1 Main St", Address_2: "", City: "Atlanta", State: "", Zipcode: "30318" }, o);
  assert(cityStateZip(addrOf({})) === "Atlanta, GA 30318",
    `state should come from the ZIP, got ${cityStateZip(addrOf({}))}`);
  assert(cityStateZip(addrOf({ State: "GA" })) === "Atlanta, GA 30318", "an explicit state is kept");
  assert(cityStateZip(addrOf({ City: "-", Zipcode: "" })) === "", "placeholder city must not print");
  for (const [zip, want] of [["30318", "GA"], ["31401", "GA"], ["10001", "NY"], ["90210", "CA"], ["99501", "AK"], ["", ""]]) {
    assert(stateFromZip(zip) === want, `stateFromZip(${zip}) should be ${want || "empty"}, got ${stateFromZip(zip)}`);
  }
  assert(addressProblem(addrOf({})) === null, "a complete address is mailable");
  assert(addressProblem(addrOf({ State: "", City: "" })) === null, "ZIP alone is enough to route");
  assert(addressProblem(addrOf({ City: "-", Zipcode: "" })) !== null, "placeholder city + no ZIP is undeliverable");
  assert(addressProblem(addrOf({ Address_1: "", Address_2: "" })) !== null, "no street line is undeliverable");
  assert(addressProblem(addrOf({ Description: "" })) !== null, "no addressee is undeliverable");
  // Undeliverable records are pulled from the run and reported, not mailed blind.
  const addrExcluded = [];
  const addrRecs = [addrOf({}), addrOf({ Description: "Broken Co", City: "-", Zipcode: "" }), addrOf({})]
    .map((t) => ({ tokens: t, statement: longStmt(3) }));
  const addrPdf = buildBatchPdf(addrRecs, { asOfDate: "2026-07-14", excluded: addrExcluded }, "tokens");
  const addrPages = (addrPdf.toString("latin1").match(/\/Type\s*\/Page\s/g) || []).length;
  assert(addrPages === 8, `2 mailable of 3 -> 8 pages, got ${addrPages}`);
  assert(addrExcluded.length === 1 && addrExcluded[0].name === "Broken Co",
    `excluded sink should name Broken Co, got ${JSON.stringify(addrExcluded)}`);

  console.log(`Unit -> ${records.length} customers, each 4 pages (2 compact), shipping ${shippingRecords.length}, gated(1300) ${gated.length}, blankCutoff ${anyAge.length}`);
  console.log(`Set length -> fixed at 4 pages for 0..500-line statements; ${mixedPages}p for ${mixed.length} mixed customers`);
  console.log(`Address -> state derived from ZIP, ${addrExcluded.length} undeliverable pulled and reported`);

  // ---- Execute the generated Code nodes with n8n-style mocks --------------
  const invoiceResp = { value: sample.ledgerEntries.filter((e) => e.Open === true) };
  const settingsResp = { Min_Overdue_Balance: 1000 };

  const qualifyDollar = (settings) => (nm) => {
    if (nm === "Get Open Invoices") return { first: () => ({ json: invoiceResp }) };
    if (nm === "Settings") return { first: () => ({ json: settings }) };
    throw new Error("unexpected $() " + nm);
  };
  const qualifyFn = new AsyncFunction("$", "items", "require", codeOf("Qualifying Customer Nos"));
  const qOut = await qualifyFn.call({}, qualifyDollar(settingsResp), [], require);
  const qNos = qOut.flatMap((o) => o.json.customerNos);
  // Qualifying works off the ledger only, so C00099 is fetched here; the route filter
  // (which needs customer data) drops it later in Transform.
  assert(qNos.length === 3 && qNos.includes("C00099"),
    `qualify (min 1000) -> 3 incl C00099, got [${qNos.join(", ")}]`);
  const qHigh = (await qualifyFn.call({}, qualifyDollar({ Min_Overdue_Balance: 2000 }), [], require))
    .flatMap((o) => o.json.customerNos);
  assert(qHigh.length === 1 && qHigh[0] === "20382", `qualify (min 2000) -> [20382], got [${qHigh.join(", ")}]`);

  const getCustomersItems = qOut.map((o) => ({
    json: { value: sample.customers.filter((c) => o.json.customerNos.includes(String(c.No))) },
  }));
  const getShipToItems = getCustomersItems.map((it) => {
    const nos = it.json.value.map((c) => String(c.No));
    return { json: { value: (sample.shipTos || []).filter((s) => nos.includes(String(s.HFSCustomerNo))) } };
  });
  const $forTransform = (nm) => {
    if (nm === "Get Customers") return { all: () => getCustomersItems, first: () => getCustomersItems[0] };
    if (nm === "Get Ship-to Addresses") return { all: () => getShipToItems, first: () => getShipToItems[0] };
    if (nm === "Get Open Invoices") return { first: () => ({ json: invoiceResp }), all: () => [{ json: invoiceResp }] };
    if (nm === "Settings") return { first: () => ({ json: settingsResp }) };
    throw new Error("unexpected $() " + nm);
  };
  const transformFn = new AsyncFunction("$", "items", "require", codeOf("Transform (group + tokens)"));
  const recs = await transformFn.call({}, $forTransform, [], require);
  assert(recs.length === 2, `transform -> 2 records, got ${recs.length}`);
  assert(!recs.some((r) => r.json.customerNo === "C00099"),
    "Transform must drop C00099 (route RT 21) even though Qualifying fetched it");

  const thisCtx = { helpers: { prepareBinaryData: async (buf, fileName) => ({ fileName, size: buf.length, pages: countPages(buf) }) } };
  const renderFn = new AsyncFunction("$", "items", "require", codeOf("Render & Merge PDFs"));
  const rendered = await renderFn.call(thisCtx, () => ({}), recs, require);
  assert(rendered.length === 2, `render -> 2 PDFs (billing+shipping), got ${rendered.length}`);
  const billing = rendered.find((r) => r.json.type === "billing");
  const shipping = rendered.find((r) => r.json.type === "shipping");
  assert(billing.json.customers === 2, `billing -> 2 customers, got ${billing.json.customers}`);
  assert(shipping.json.customers === 1, `shipping -> 1 customer (distinct ship-to), got ${shipping.json.customers}`);
  assert(billing.binary.data.pages === 8, `billing should be 8 pages (2 accounts x 4), got ${billing.binary.data.pages}`);
  assert(shipping.binary.data.pages === 4, `shipping should be 4 pages (1 account x 4), got ${shipping.binary.data.pages}`);
  console.log(`Generated code -> billing ${billing.binary.data.pages}p/${billing.json.customers}c, shipping ${shipping.binary.data.pages}p/${shipping.json.customers}c`);

  if (failures) { console.error(`\n${failures} check(s) failed.`); process.exit(1); }
  console.log("\nOriginal workflow build verified.");
}

main().catch((e) => { console.error(e); process.exit(1); });
