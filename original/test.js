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
const { buildBatchPdf, customerPages, sameAddress } = require("./pure-pdf");

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

  console.log(`Unit -> ${records.length} customers, each 4 pages, shipping ${shippingRecords.length}, gated(1300) ${gated.length}`);

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
  assert(qNos.length === 2, `qualify (min 1000) -> 2, got [${qNos.join(", ")}]`);
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
