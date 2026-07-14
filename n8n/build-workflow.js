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
const pureSrc = inlineable(read("scripts/pure-pdf.js"));

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

// ---- Code node 2: Render PDF (zero dependencies) ---------------------------
// Pure JS, base-14 fonts, no require() of external modules and no external
// service — so it runs on n8n Cloud as-is. Builds letter + statement as one PDF.
const renderNodeCode = `${pureSrc}

// --- n8n driver -------------------------------------------------------------
const outFolder = ($('Keys').first().json.Output_Folder || '').replace(/[\\\\/]+$/,'');
const sep = outFolder.includes('\\\\') ? '\\\\' : '/';
const out = [];
for (const item of items) {
  const rec = item.json;
  const pdf = buildCustomerPdf(rec.tokens, rec.statement, {});
  const base = String(rec.tokens.Description).replace(/[^a-z0-9]+/gi,'_').replace(/^_+|_+$/g,'') || rec.customerNo;
  const fileName = base + '.pdf';
  out.push({
    json: { customerNo: rec.customerNo, name: rec.tokens.Description, fileName, fullPath: outFolder ? outFolder + sep + fileName : fileName },
    binary: { data: await this.helpers.prepareBinaryData(pdf, fileName, 'application/pdf') },
  });
}
return out;`;

// ---- Code node 0: Qualifying Customer Nos (pure JS, no modules) -------------
// Derives the DISTINCT set of customers that actually have an open invoice dated
// 2023-2024 from the (already server-filtered) ledger entries, and builds the
// OData $filter used to fetch ONLY those customers. If nobody qualifies it emits
// no items, so nothing downstream runs and no letters are produced.
const qualifyNodeCode = `const led = $('Get Ledger Entries').first().json;
const entries = led.value || (Array.isArray(led) ? led : []);
const inWindow = (d) => { const s = String(d || '').slice(0, 10); return s >= '2023-01-01' && s <= '2024-12-31'; };

const nos = [...new Set(
  entries
    .filter((e) =>
      String(e.Document_Type) === 'Invoice' &&
      (e.Open === true || e.Open === 'true' || e.Open === 1) &&
      inWindow(e.Document_Date) &&
      (Number(e.Remaining_Amount) || 0) !== 0
    )
    .map((e) => String(e.Customer_No))
)];

// Nobody qualifies -> stop here so NO customers are fetched and NO letters go out.
if (nos.length === 0) return [];

// Build "No eq 'X' or No eq 'Y' ..." (single-quotes doubled per OData escaping).
const customerFilter = nos.map((n) => "No eq '" + n.replace(/'/g, "''") + "'").join(' or ');
return [{ json: { customerNos: nos, count: nos.length, customerFilter } }];`;

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
    parameters: { jsCode: qualifyNodeCode },
    id: "n_qualify",
    name: "Qualifying Customer Nos",
    type: "n8n-nodes-base.code",
    typeVersion: 2,
    position: [440, 400],
    notes:
      "Distinct customers with an open 2023-2024 invoice, derived from the ledger entries. Emits nothing if none qualify, so no letters go out.",
  },
  {
    parameters: {
      url: `=${BC_BASE}/Customer`,
      sendQuery: true,
      queryParameters: {
        parameters: [
          // ONLY the customers that have a qualifying 2023-2024 open invoice.
          { name: "$filter", value: "={{ $('Qualifying Customer Nos').first().json.customerFilter }}" },
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
    position: [660, 400],
    notes:
      "Fetches ONLY qualifying customers (filtered by Qualifying Customer Nos). If your qualifying set is very large, split the $filter into batches to stay under URL-length limits.",
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
      "Zero dependencies (pure JS, base-14 fonts) — runs on n8n Cloud with no external modules or services. Builds the letter + statement as one PDF per customer.",
  },
  {
    // Cloud-compatible output: upload each PDF to OneDrive via Graph.
    // Self-hosted alternative: swap this for a Read/Write File node writing to
    // {{ $json.fullPath }} (the Keys.Output_Folder local path).
    parameters: {
      resource: "file",
      operation: "upload",
      fileName: "={{ $json.fileName }}",
      parentId: "",
      binaryData: true,
      binaryPropertyName: "data",
    },
    id: "n_onedrive",
    name: "Upload to OneDrive",
    type: "n8n-nodes-base.microsoftOneDrive",
    typeVersion: 1,
    position: [900, 300],
    notes:
      "SET ME UP: select your Microsoft OneDrive credential, and set Parent ID to the target folder (e.g. 'Gabe's Projects'). Uploads each customer PDF from binary field 'data'.",
  },
];

const connections = {
  "When clicking Test workflow": { main: [[{ node: "Keys", type: "main", index: 0 }]] },
  Keys: { main: [[{ node: "Get Token", type: "main", index: 0 }]] },
  // Ledger-driven: the filtered 2023-2024 open invoices decide who gets a letter.
  "Get Token": { main: [[{ node: "Get Ledger Entries", type: "main", index: 0 }]] },
  "Get Ledger Entries": { main: [[{ node: "Qualifying Customer Nos", type: "main", index: 0 }]] },
  "Qualifying Customer Nos": { main: [[{ node: "Get Customers", type: "main", index: 0 }]] },
  "Get Customers": { main: [[{ node: "Transform (group + tokens)", type: "main", index: 0 }]] },
  "Transform (group + tokens)": { main: [[{ node: "Render & Merge PDFs", type: "main", index: 0 }]] },
  "Render & Merge PDFs": { main: [[{ node: "Upload to OneDrive", type: "main", index: 0 }]] },
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
