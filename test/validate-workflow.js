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

// Emulate BC's server-side $filter on the ledger page (ALL open Invoice entries, no date bound).
function serverFilterEntries(entries) {
  return entries.filter((e) => String(e.Document_Type) === "Invoice" && e.Open === true);
}

async function main() {
  // ---- Node: Qualifying Customer Nos --------------------------------------
  // In production the ledger response is already server-filtered; emulate that.
  const invoiceResp = { value: serverFilterEntries(sample.ledgerEntries) };
  const $forQualify = makeDollar({ "Get Open Invoices": invoiceResp });
  const qualifyFn = new AsyncFunction("$", "items", "require", codeOf("Qualifying Customer Nos"));
  const qualifyOut = await qualifyFn.call({}, $forQualify, [], require);

  const qNos = qualifyOut.length ? qualifyOut[0].json.customerNos : [];
  assert(qualifyOut.length === 1, "Qualifying node should emit exactly one item");
  assert(qNos.length === 2, `expected 2 qualifying customer Nos, got ${qNos.length}`);
  assert(qNos.includes("20382") && qNos.includes("C00021"), "20382 and C00021 should qualify");
  assert(!qNos.includes("C00034") && !qNos.includes("C00045"),
    "C00034 (paid) and C00045 (2025, out of window) must NOT qualify");
  console.log(`Qualifying node -> [${qNos.join(", ")}]`);

  // ---- Emulate: Get Customers fetches ONLY the qualifying customers --------
  const fetchedCustomers = sample.customers.filter((c) => qNos.includes(String(c.No)));
  assert(fetchedCustomers.length === 2, "Get Customers should fetch only the 2 qualifying customers");
  assert(!fetchedCustomers.some((c) => c.No === "C00045"),
    "C00045 must never be fetched (not in the $filter)");

  // ---- Node: Transform -----------------------------------------------------
  const $forTransform = makeDollar({
    Keys: { Output_Folder: "C:\\Users\\GPress\\OneDrive\\Gabe's Projects" },
    "Get Customers": { value: fetchedCustomers },
    "Get Open Invoices": invoiceResp,
  });
  const transformFn = new AsyncFunction("$", "items", "require", codeOf("Transform (group + tokens)"));
  const records = await transformFn.call({}, $forTransform, [], require);

  assert(records.length === 2, `expected 2 records, got ${records.length}`);
  const stiles = records.find((r) => r.json.customerNo === "20382");
  assert(stiles && stiles.json.tokens.Converted_balance === "6,220.75",
    "20382 balance should be 6,220.75 (all open incl. 2025)");
  assert(stiles && stiles.json.tokens.AccountNumber === "20382",
    "20382 record should carry AccountNumber token");
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

  // New behavior: ONE combined batch PDF for the whole run.
  assert(rendered.length === 1, `expected 1 combined PDF, got ${rendered.length}`);
  const batch = rendered[0];
  assert(batch.json.customers === records.length,
    `batch should cover all ${records.length} customers, got ${batch.json.customers}`);
  assert(batch.json.fileName === "Past-Due-Letters-Batch.pdf",
    `unexpected batch fileName: ${batch.json.fileName}`);
  assert(batch.binary && batch.binary.data && batch.binary.data.size > 1500,
    `combined PDF looks too small (${batch.binary && batch.binary.data && batch.binary.data.size})`);
  console.log(`Render node -> 1 combined PDF, ${batch.json.customers} customers, ${batch.binary.data.size} bytes`);

  if (failures) { console.error(`\n${failures} check(s) failed.`); process.exit(1); }
  console.log("\nWorkflow Code nodes execute correctly against sample data.");
}

main().catch((e) => { console.error(e); process.exit(1); });
