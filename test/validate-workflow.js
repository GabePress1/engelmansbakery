/*
 * validate-workflow.js
 * --------------------
 * Executes the ACTUAL Code-node source embedded in the generated workflow JSON
 * against the sample BC responses, using a minimal n8n-context mock. This proves
 * the inlined code (after extraction) still produces correct results.
 *
 *   node test/validate-workflow.js
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const wf = JSON.parse(
  fs.readFileSync(path.join(ROOT, "n8n", "Printing_Letter_Invoices.workflow.json"), "utf8")
);
const sample = JSON.parse(
  fs.readFileSync(path.join(__dirname, "sample-customers.json"), "utf8")
);

const codeOf = (name) =>
  wf.nodes.find((n) => n.name === name).parameters.jsCode;

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

// Mock n8n's $('NodeName') accessor. BC OData responses look like { value: [...] }.
function makeDollar(nodeData) {
  return (nodeName) => {
    const data = nodeData[nodeName];
    return {
      first: () => ({ json: data }),
      all: () => (Array.isArray(data.value) ? data.value.map((v) => ({ json: v })) : [{ json: data }]),
    };
  };
}

let failures = 0;
const assert = (c, m) => { if (!c) { failures++; console.error("  FAIL: " + m); } };

// Emulate BC's server-side $filter on the ledger page (ALL open entries: Open eq true).
function serverFilterEntries(entries) {
  return entries.filter((e) => e.Open === true);
}

async function main() {
  // ---- Node: Qualifying Customer Nos --------------------------------------
  // In production the ledger response is already server-filtered; emulate that.
  const invoiceResp = { value: serverFilterEntries(sample.ledgerEntries) };
  // Get Sales Orders is already server-filtered to tomorrow; pass the fixture through.
  const salesResp = { value: sample.salesOrders };
  // Settings node: threshold low enough that both sample customers still qualify,
  // so the 2-customer pipeline is exercised end-to-end. Default 2024 cutoff.
  const settingsResp = { Min_Overdue_Balance: 1000, Oldest_Open_Invoice: "2024-12-31" };
  const qualifyDollar = (settings) => (nodeName) => {
    if (nodeName === "Get Open Invoices") return { first: () => ({ json: invoiceResp }) };
    if (nodeName === "Get Sales Orders") return { first: () => ({ json: salesResp }) };
    if (nodeName === "Settings") return { first: () => ({ json: settings }) };
    throw new Error("unexpected $() node: " + nodeName);
  };
  const qualifyFn = new AsyncFunction("$", "items", "require", codeOf("Qualifying Customer Nos"));
  const qualifyOut = await qualifyFn.call({}, qualifyDollar(settingsResp), [], require);

  // Threshold check: at $2,000 only 20382 (net 3,500.50) clears; C00021 ($1,290) drops.
  const qHigh = (await qualifyFn.call({}, qualifyDollar({ Min_Overdue_Balance: 2000 }), [], require))
    .flatMap((o) => o.json.customerNos);
  assert(qHigh.length === 1 && qHigh[0] === "20382",
    `minBalance 2000 should leave only 20382, got [${qHigh.join(", ")}]`);

  // Blank Oldest_Open_Invoice -> age rule dropped: C00070 (2025 overdue, ordering
  // tomorrow) now qualifies alongside 20382 and C00021.
  const qAnyAge = (await qualifyFn.call({}, qualifyDollar({ Min_Overdue_Balance: 100, Oldest_Open_Invoice: "" }), [], require))
    .flatMap((o) => o.json.customerNos);
  assert(qAnyAge.includes("C00070") && qAnyAge.length === 3,
    `blank Oldest_Open_Invoice should add C00070 (3 total), got [${qAnyAge.join(", ")}]`);

  // Qualifying now emits ONE ITEM PER BATCH; combine their customerNos.
  const qNos = qualifyOut.flatMap((o) => o.json.customerNos);
  assert(qualifyOut.length >= 1, "Qualifying node should emit at least one batch");
  assert(qNos.length === 2, `expected 2 qualifying customer Nos, got ${qNos.length}`);
  assert(qNos.includes("20382") && qNos.includes("C00021"), "20382 and C00021 should qualify");
  assert(!qNos.includes("C00080"), "C00080 (route RT 21) must NOT qualify");
  assert(!qNos.includes("C00090"), "C00090 (not ordering tomorrow) must NOT qualify");
  assert(!qNos.includes("C00050") && !qNos.includes("C00060") && !qNos.includes("C00070") && !qNos.includes("C00034"),
    "C00050 (negative), C00060 (future), C00070 (2025-only doc date), C00034 (paid) must NOT qualify");
  console.log(`Qualifying node -> ${qualifyOut.length} batch(es), [${qNos.join(", ")}]`);

  // ---- Emulate: Get Customers runs once per batch, each returning its batch --
  const getCustomersItems = qualifyOut.map((o) => ({
    json: { value: sample.customers.filter((c) => o.json.customerNos.includes(String(c.No))) },
  }));
  const fetchedCustomers = getCustomersItems.flatMap((it) => it.json.value);
  assert(fetchedCustomers.length === 2, "Get Customers should fetch only the 2 qualifying customers");

  // ---- Node: Transform -----------------------------------------------------
  const $forTransform = (nodeName) => {
    if (nodeName === "Get Customers") return { all: () => getCustomersItems, first: () => getCustomersItems[0] };
    if (nodeName === "Get Open Invoices") return { first: () => ({ json: invoiceResp }), all: () => [{ json: invoiceResp }] };
    if (nodeName === "Get Sales Orders") return { first: () => ({ json: salesResp }), all: () => [{ json: salesResp }] };
    if (nodeName === "Settings") return { first: () => ({ json: settingsResp }) };
    if (nodeName === "Keys") return { first: () => ({ json: { Output_Folder: "C:\\Users\\GPress\\OneDrive\\Gabe's Projects" } }) };
    throw new Error("unexpected $() node: " + nodeName);
  };
  const transformFn = new AsyncFunction("$", "items", "require", codeOf("Transform (group + tokens)"));
  const records = await transformFn.call({}, $forTransform, [], require);

  assert(records.length === 2, `expected 2 records, got ${records.length}`);
  const stiles = records.find((r) => r.json.customerNo === "20382");
  assert(stiles && stiles.json.tokens.Converted_balance === "3,500.50",
    "20382 balance should be 3,500.50 (past-due invoices minus open credit)");
  assert(stiles && stiles.json.tokens.Route === "RT 5", "20382 route should be RT 5 (from its sales order)");
  assert(records[0].json.customerNo === "20382" && records[1].json.customerNo === "C00021",
    "records should be sorted by Route (RT 5 before RT 8)");
  console.log(`Transform node -> ${records.length} qualifying customers`);

  // ---- Node: Render & Merge PDFs ------------------------------------------
  const $forRender = makeDollar({
    Keys: { Output_Folder: "C:\\Users\\GPress\\OneDrive - engelmansbakery.com\\Gabe's Projects" },
  });
  const thisCtx = {
    helpers: {
      // Mimic n8n binary helper: return a descriptor with size for assertions.
      prepareBinaryData: async (buf, fileName, mimeType) => ({
        fileName, mimeType, size: buf.length, data: "<base64>",
      }),
    },
  };
  const renderFn = new AsyncFunction("$", "items", "require", codeOf("Render & Merge PDFs"));
  const rendered = await renderFn.call(thisCtx, $forRender, records, require);

  // New behavior: ONE combined statement PDF (no letter, no address).
  assert(rendered.length === 1, `expected 1 PDF (combined notice), got ${rendered.length}`);
  const notice = rendered[0];
  assert(notice && /^Past-Due-Notice-\d{4}-\d{2}-\d{2}\.pdf$/.test(notice.json.fileName),
    `PDF name should be dated Past-Due-Notice, got ${notice && notice.json.fileName}`);
  assert(notice && notice.json.customers === 2, `notice should list 2 customers, got ${notice && notice.json.customers}`);
  assert(notice.binary && notice.binary.data && notice.binary.data.size > 1500,
    `notice PDF looks too small (${notice.binary && notice.binary.data && notice.binary.data.size})`);
  console.log(`Render node -> notice ${notice.binary.data.size}B, ${notice.json.customers} customers`);

  if (failures) { console.error(`\n${failures} check(s) failed.`); process.exit(1); }
  console.log("\nWorkflow Code nodes execute correctly against sample data.");
}

main().catch((e) => { console.error(e); process.exit(1); });
