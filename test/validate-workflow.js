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
  const $forQualify = makeDollar({ "Get Open Invoices": invoiceResp });
  const qualifyFn = new AsyncFunction("$", "items", "require", codeOf("Qualifying Customer Nos"));
  const qualifyOut = await qualifyFn.call({}, $forQualify, [], require);

  // Qualifying now emits ONE ITEM PER BATCH; combine their customerNos.
  const qNos = qualifyOut.flatMap((o) => o.json.customerNos);
  assert(qualifyOut.length >= 1, "Qualifying node should emit at least one batch");
  assert(qNos.length === 2, `expected 2 qualifying customer Nos, got ${qNos.length}`);
  assert(qNos.includes("20382") && qNos.includes("C00021"), "20382 and C00021 should qualify");
  assert(!qNos.includes("C00050") && !qNos.includes("C00060") && !qNos.includes("C00070") && !qNos.includes("C00034"),
    "C00050 (negative), C00060 (future), C00070 (2025-only doc date), C00034 (paid) must NOT qualify");
  console.log(`Qualifying node -> ${qualifyOut.length} batch(es), [${qNos.join(", ")}]`);

  // ---- Emulate: Get Customers runs once per batch, each returning its batch --
  const getCustomersItems = qualifyOut.map((o) => ({
    json: { value: sample.customers.filter((c) => o.json.customerNos.includes(String(c.No))) },
  }));
  const fetchedCustomers = getCustomersItems.flatMap((it) => it.json.value);
  assert(fetchedCustomers.length === 2, "Get Customers should fetch only the 2 qualifying customers");

  // ---- Emulate: Get Ship-to Addresses runs once per Get Customers batch ------
  const getShipToItems = getCustomersItems.map((it) => {
    const nos = it.json.value.map((c) => String(c.No));
    return { json: { value: (sample.shipTos || []).filter((s) => nos.includes(String(s.HFSCustomerNo))) } };
  });

  // ---- Node: Transform -----------------------------------------------------
  const $forTransform = (nodeName) => {
    if (nodeName === "Get Customers") return { all: () => getCustomersItems, first: () => getCustomersItems[0] };
    if (nodeName === "Get Ship-to Addresses") return { all: () => getShipToItems, first: () => getShipToItems[0] };
    if (nodeName === "Get Open Invoices") return { first: () => ({ json: invoiceResp }), all: () => [{ json: invoiceResp }] };
    if (nodeName === "Keys") return { first: () => ({ json: { Output_Folder: "C:\\Users\\GPress\\OneDrive\\Gabe's Projects" } }) };
    throw new Error("unexpected $() node: " + nodeName);
  };
  const transformFn = new AsyncFunction("$", "items", "require", codeOf("Transform (group + tokens)"));
  const records = await transformFn.call({}, $forTransform, [], require);

  assert(records.length === 2, `expected 2 records, got ${records.length}`);
  const stiles = records.find((r) => r.json.customerNo === "20382");
  assert(stiles && stiles.json.tokens.Converted_balance === "3,500.50",
    "20382 balance should be 3,500.50 (past-due invoices minus open credit)");
  assert(stiles && stiles.json.shipTokens.Address_1 === "50 Dockside Ave",
    "20382 shipTokens should use the default ship-to address");
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

  // New behavior: TWO combined PDFs — billing + shipping.
  assert(rendered.length === 2, `expected 2 PDFs (billing + shipping), got ${rendered.length}`);
  const billing = rendered.find((r) => r.json.type === "billing");
  const shipping = rendered.find((r) => r.json.type === "shipping");
  assert(billing && /^Past-Due-Billing-\d{4}-\d{2}-\d{2}\.pdf$/.test(billing.json.fileName),
    `billing PDF name should be dated, got ${billing && billing.json.fileName}`);
  assert(shipping && /^Past-Due-Shipping-\d{4}-\d{2}-\d{2}\.pdf$/.test(shipping.json.fileName),
    `shipping PDF name should be dated, got ${shipping && shipping.json.fileName}`);
  for (const p of [billing, shipping]) {
    assert(p.binary && p.binary.data && p.binary.data.size > 1500,
      `${p.json.type} PDF looks too small (${p.binary && p.binary.data && p.binary.data.size})`);
  }
  console.log(`Render node -> billing ${billing.binary.data.size}B + shipping ${shipping.binary.data.size}B, ${billing.json.customers} customers`);

  if (failures) { console.error(`\n${failures} check(s) failed.`); process.exit(1); }
  console.log("\nWorkflow Code nodes execute correctly against sample data.");
}

main().catch((e) => { console.error(e); process.exit(1); });
