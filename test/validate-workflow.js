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

async function main() {
  // ---- Node: Transform -----------------------------------------------------
  const $forTransform = makeDollar({
    Keys: { Output_Folder: "C:\\Users\\GPress\\OneDrive\\Gabe's Projects" },
    "Get Customers": { value: sample.customers },
    "Get Ledger Entries": { value: sample.ledgerEntries },
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
