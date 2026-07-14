/*
 * build-workflow.js
 * -----------------
 * Generates n8n/Printing_Letter_Invoices.workflow.json — an importable n8n workflow
 * that mirrors the verified local pipeline. The Code-node source is assembled from the
 * same scripts/*.js that the local harness runs, so the workflow can't drift from what
 * was tested.
 *
 * Run: node n8n/build-workflow.js
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const read = (p) => fs.readFileSync(path.join(ROOT, p), "utf8");

// Remove `const ... = require(...)` lines and the trailing module.exports block so the
// module body can be inlined into an n8n Code node (which has its own require + return).
function inlineable(src) {
  return src
    .replace(/^\s*const\s+\{[^}]*\}\s*=\s*require\([^)]*\);\s*$/gm, "")
    .replace(/^\s*const\s+\w+\s*=\s*require\([^)]*\);\s*$/gm, "")
    .replace(/module\.exports\s*=\s*\{[\s\S]*?\};\s*$/m, "")
    .trim();
}

const transformSrc = inlineable(read("scripts/transform.js"));
const renderSrc = inlineable(read("scripts/render-pdf.js"));
const mergeSrc = inlineable(read("scripts/merge-pdfs.js"));

// ---- Code node 1: Transform (pure JS, no external modules) -----------------
const transformNodeCode = `${transformSrc}

// --- n8n driver -------------------------------------------------------------
const custResp = $('Get Customers').first().json;
const customers = custResp.value || (Array.isArray(custResp) ? custResp : [custResp]);
const ledResp = $('Get Ledger Entries').first().json;
const ledgerEntries = ledResp.value || (Array.isArray(ledResp) ? ledResp : []);

// amountSource: "filtered" = sum of 2023-2024 open invoices (default),
//               "balanceDue" = customer's Balance_Due_LCY (total open balance).
const records = buildRecords(customers, ledgerEntries, { amountSource: 'filtered' });
return records.map((r) => ({ json: r }));`;

// ---- Code node 2: Render & Merge (requires pdf-lib) ------------------------
// pdf-lib must be importable: on self-hosted n8n set
//   NODE_FUNCTION_ALLOW_EXTERNAL=pdf-lib
// and `npm i pdf-lib` in the n8n custom-extensions / node_modules dir.
const renderNodeCode = `const { PDFDocument, StandardFonts, rgb } = require('pdf-lib');
function formatUSD(n){const num=Number(n)||0;return num.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});}

${renderSrc}

${mergeSrc}

// --- n8n driver -------------------------------------------------------------
const outFolder = ($('Keys').first().json.Output_Folder || '').replace(/[\\\\/]+$/,'');
const sep = outFolder.includes('\\\\') ? '\\\\' : '/';
const out = [];
for (const item of items) {
  const rec = item.json;
  const letterPdf = await renderLetterPdf(rec.tokens);
  const stmtPdf = await renderStatementPdf(rec.tokens, rec.statement, {});
  const merged = await mergePdfs([letterPdf, stmtPdf]);
  const base = String(rec.tokens.Description).replace(/[^a-z0-9]+/gi,'_').replace(/^_+|_+$/g,'') || rec.customerNo;
  const fileName = base + '.pdf';
  out.push({
    json: { customerNo: rec.customerNo, name: rec.tokens.Description, fileName, fullPath: outFolder ? outFolder + sep + fileName : fileName },
    binary: { data: await this.helpers.prepareBinaryData(Buffer.from(merged), fileName, 'application/pdf') },
  });
}
return out;`;

// --- helpers to build nodes -------------------------------------------------
const TENANT = "={{ $('Keys').first().json.Tenant_ID }}";
const BC_BASE =
  "https://api.businesscentral.dynamics.com/v2.0/{{ $('Keys').first().json.Tenant_ID }}/{{ $('Keys').first().json.Environment }}/ODataV4/Company('{{ $('Keys').first().json.Company }}')";

const nodes = [
  {
    parameters: {},
    id: "n_trigger",
    name: "When clicking Test workflow",
    type: "n8n-nodes-base.manualTrigger",
    typeVersion: 1,
    position: [-400, 300],
  },
  {
    parameters: {
      assignments: {
        assignments: [
          { id: "a1", name: "Tenant_ID", value: "REPLACE_WITH_TENANT_ID", type: "string" },
          { id: "a2", name: "Client_ID", value: "REPLACE_WITH_CLIENT_ID", type: "string" },
          { id: "a3", name: "Client_Secret", value: "REPLACE_WITH_CLIENT_SECRET", type: "string" },
          { id: "a4", name: "Environment", value: "Production", type: "string" },
          { id: "a5", name: "Company", value: "Live-EB", type: "string" },
          {
            id: "a6",
            name: "Output_Folder",
            value:
              "C:\\\\Users\\\\GPress\\\\OneDrive - engelmansbakery.com\\\\2. Financial\\\\C. Accounting\\\\e. Controller's Folders\\\\Gabe's Projects",
            type: "string",
          },
        ],
      },
      options: {},
    },
    id: "n_keys",
    name: "Keys",
    type: "n8n-nodes-base.set",
    typeVersion: 3.4,
    position: [-200, 300],
    notes:
      "You already have this node with your BC app-reg keys. Placeholders shown here are NOT real secrets. Do not commit real values.",
  },
  {
    parameters: {
      method: "POST",
      url: "=https://login.microsoftonline.com/{{ $('Keys').first().json.Tenant_ID }}/oauth2/v2.0/token",
      sendBody: true,
      contentType: "form-urlencoded",
      bodyParameters: {
        parameters: [
          { name: "grant_type", value: "client_credentials" },
          { name: "client_id", value: "={{ $('Keys').first().json.Client_ID }}" },
          { name: "client_secret", value: "={{ $('Keys').first().json.Client_Secret }}" },
          { name: "scope", value: "https://api.businesscentral.dynamics.com/.default" },
        ],
      },
      options: {},
    },
    id: "n_token",
    name: "Get Token",
    type: "n8n-nodes-base.httpRequest",
    typeVersion: 4.2,
    position: [0, 300],
  },
  {
    parameters: {
      url: `=${BC_BASE}/Customer`,
      sendQuery: true,
      queryParameters: {
        parameters: [
          { name: "$select", value: "No,Name,Address,Address_2,City,County,Post_Code,Balance_Due_LCY" },
        ],
      },
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: "Authorization", value: "=Bearer {{ $('Get Token').first().json.access_token }}" },
        ],
      },
      options: {},
    },
    id: "n_customers",
    name: "Get Customers",
    type: "n8n-nodes-base.httpRequest",
    typeVersion: 4.2,
    position: [220, 200],
  },
  {
    parameters: {
      url: `=${BC_BASE}/Customer_Ledger_Entries`,
      sendQuery: true,
      queryParameters: {
        parameters: [
          {
            name: "$filter",
            value:
              "Open eq true and Document_Type eq 'Invoice' and Document_Date ge 2023-01-01 and Document_Date le 2024-12-31",
          },
          {
            name: "$select",
            value: "Customer_No,Document_Type,Document_No,Document_Date,Due_Date,Amount,Remaining_Amount,Open",
          },
        ],
      },
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: "Authorization", value: "=Bearer {{ $('Get Token').first().json.access_token }}" },
        ],
      },
      options: {},
    },
    id: "n_ledger",
    name: "Get Ledger Entries",
    type: "n8n-nodes-base.httpRequest",
    typeVersion: 4.2,
    position: [220, 400],
    notes:
      "Requires a published web service named 'Customer_Ledger_Entries' exposing these fields. If your published page/query has a different name, change it here.",
  },
  {
    parameters: { jsCode: transformNodeCode },
    id: "n_transform",
    name: "Transform (group + tokens)",
    type: "n8n-nodes-base.code",
    typeVersion: 2,
    position: [460, 300],
  },
  {
    parameters: { jsCode: renderNodeCode },
    id: "n_render",
    name: "Render & Merge PDFs",
    type: "n8n-nodes-base.code",
    typeVersion: 2,
    position: [680, 300],
    notes:
      "Requires pdf-lib. On self-hosted n8n: set NODE_FUNCTION_ALLOW_EXTERNAL=pdf-lib and install pdf-lib where n8n can require it.",
  },
  {
    parameters: {
      operation: "write",
      fileName: "={{ $json.fullPath }}",
      dataPropertyName: "data",
      options: {},
    },
    id: "n_write",
    name: "Write PDF to OneDrive",
    type: "n8n-nodes-base.readWriteFile",
    typeVersion: 1,
    position: [900, 300],
  },
];

const connections = {
  "When clicking Test workflow": { main: [[{ node: "Keys", type: "main", index: 0 }]] },
  Keys: { main: [[{ node: "Get Token", type: "main", index: 0 }]] },
  "Get Token": {
    main: [[
      { node: "Get Customers", type: "main", index: 0 },
      { node: "Get Ledger Entries", type: "main", index: 0 },
    ]],
  },
  "Get Customers": { main: [[{ node: "Transform (group + tokens)", type: "main", index: 0 }]] },
  "Get Ledger Entries": { main: [[{ node: "Transform (group + tokens)", type: "main", index: 0 }]] },
  "Transform (group + tokens)": { main: [[{ node: "Render & Merge PDFs", type: "main", index: 0 }]] },
  "Render & Merge PDFs": { main: [[{ node: "Write PDF to OneDrive", type: "main", index: 0 }]] },
};

const workflow = {
  name: "Printing Letter_Invoices",
  nodes,
  connections,
  active: false,
  settings: { executionOrder: "v1" },
  pinData: {},
};

const outPath = path.join(__dirname, "Printing_Letter_Invoices.workflow.json");
fs.writeFileSync(outPath, JSON.stringify(workflow, null, 2));
console.log("Wrote " + path.relative(ROOT, outPath));
