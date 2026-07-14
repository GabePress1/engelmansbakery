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

// Emulate BC's server-side $filter on the ledger page (open + Invoice + in 2023-2024).
function serverFilterLedger(entries) {
  const inWin = (d) => { const s = String(d || "").slice(0, 10); return s >= "2023-01-01" && s <= "2024-12-31"; };
  return entries.filter(
    (e) => String(e.Document_Type) === "Invoice" && e.Open === true && inWin(e.Document_Date)
  );
}

async function main() {
  // ---- Node: Qualifying Customer Nos --------------------------------------
  // In production the ledger response is already server-filtered; emulate that.
  const ledgerResp = { value: serverFilterLedger(sample.ledgerEntries) };
  const $forQualify = makeDollar({ "Get Ledger Entries": ledgerResp });
  const qualifyFn = new AsyncFunction("$", "items", "require", codeOf("Qualifying Customer Nos"));
  const qualifyOut = await qualifyFn.call({}, $forQualify, [], require);

  const qNos = qualifyOut.length ? qualifyOut[0].json.customerNos : [];
  assert(qualifyOut.length === 1, "Qualifying node should emit exactly one item");
  assert(qNos.length === 2, `expected 2 qualifying customer Nos, got ${qNos.length}`);
  assert(qNos.includes("C00010") && qNos.includes("C00021"), "C00010 and C00021 should qualify");
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
    "Get Ledger Entries": ledgerResp,
  });
  const transformFn = new AsyncFunction("$", "items", "require", codeOf("Transform (group + tokens)"));
  const records = await transformFn.call({}, $forTransform, [], require);

  assert(records.length === 2, `expected 2 records, got ${records.length}`);
  const sunrise = records.find((r) => r.json.customerNo === "C00010");
  assert(sunrise && sunrise.json.tokens.Converted_balance === "4,820.75",
    "C00010 balance should be 4,820.75");
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

  assert(rendered.length === 2, `expected 2 rendered items, got ${rendered.length}`);
  for (const r of rendered) {
    assert(r.binary && r.binary.data && r.binary.data.size > 800,
      `${r.json.name}: PDF looks too small (${r.binary && r.binary.data && r.binary.data.size})`);
    assert(r.json.fullPath.endsWith(".pdf") && r.json.fullPath.includes("\\"),
      `${r.json.name}: fullPath not a Windows path (${r.json.fullPath})`);
    console.log(`Render node -> ${r.json.name}: ${r.binary.data.size} bytes -> ${r.json.fullPath}`);
  }

  if (failures) { console.error(`\n${failures} check(s) failed.`); process.exit(1); }
  console.log("\nWorkflow Code nodes execute correctly against sample data.");
}

main().catch((e) => { console.error(e); process.exit(1); });
