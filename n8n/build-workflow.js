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
const invResp = $('Get Open Invoices').first().json;
const invoices = invResp.value || (Array.isArray(invResp) ? invResp : []);

// amountSource: "filtered" = sum of 2023-2024 open invoices (default),
//               "balanceDue" = customer's Balance_Due_LCY (total open balance).
const records = buildRecords(customers, invoices, { amountSource: 'filtered' });
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
// 2023-2024 from the (already server-filtered) salesInvoices, and builds the
// OData $filter used to fetch ONLY those customers. If nobody qualifies it emits
// no items, so nothing downstream runs and no letters are produced.
const qualifyNodeCode = `const inv = $('Get Open Invoices').first().json;
const invoices = inv.value || (Array.isArray(inv) ? inv : []);
const inWindow = (d) => { const s = String(d || '').slice(0, 10); return s >= '2023-01-01' && s <= '2024-12-31'; };
const remaining = (e) => (e.remainingAmount != null && e.remainingAmount !== '') ? (Number(e.remainingAmount) || 0) : (Number(e.totalAmountIncludingTax) || 0);

const nos = [...new Set(
  invoices
    .filter((e) =>
      String(e.status) === 'Open' &&
      inWindow(e.invoiceDate) &&
      remaining(e) !== 0
    )
    .map((e) => String(e.customerNumber))
)];

// Nobody qualifies -> stop here so NO customers are fetched and NO letters go out.
if (nos.length === 0) return [];

// Build "No eq 'X' or No eq 'Y' ..." (single-quotes doubled per OData escaping).
const customerFilter = nos.map((n) => "No eq '" + n.replace(/'/g, "''") + "'").join(' or ');
return [{ json: { customerNos: nos, count: nos.length, customerFilter } }];`;

// --- helpers to build nodes -------------------------------------------------
const TENANT = "={{ $('Keys').first().json.Tenant_ID }}";
// OData V4 custom pages (used for the Customer page).
const BC_ODATA =
  "https://api.businesscentral.dynamics.com/v2.0/{{ $('Keys').first().json.Tenant_ID }}/{{ $('Keys').first().json.Environment }}/ODataV4/Company('{{ $('Keys').first().json.Company }}')";
// Standard API v2.0 (used for salesInvoices — has status + remainingAmount).
const BC_API =
  "https://api.businesscentral.dynamics.com/v2.0/{{ $('Keys').first().json.Tenant_ID }}/{{ $('Keys').first().json.Environment }}/api/v2.0/companies({{ $('Keys').first().json.Company_ID }})";

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
          { id: "a7", name: "Company_ID", value: "REPLACE_WITH_COMPANY_GUID", type: "string" },
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
      "Distinct customers with an open 2023-2024 invoice, derived from Get Open Invoices. Emits nothing if none qualify, so no letters go out.",
  },
  {
    parameters: {
      url: `=${BC_ODATA}/Customer`,
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
      url: `=${BC_API}/salesInvoices`,
      sendQuery: true,
      queryParameters: {
        parameters: [
          // Posted & unpaid (status Open) invoices whose Document Date is in 2023-2024.
          {
            name: "$filter",
            value: "status eq 'Open' and invoiceDate ge 2023-01-01 and invoiceDate le 2024-12-31",
          },
          // No $select on purpose: returns every property so you can see the field
          // names in the node output. Add a $select later to trim the payload.
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
    id: "n_invoices",
    name: "Get Open Invoices",
    type: "n8n-nodes-base.httpRequest",
    typeVersion: 4.2,
    position: [220, 400],
    notes:
      "Standard API v2.0 salesInvoices (status Open = posted & unpaid). Uses Company_ID (GUID) from Keys. Fields used: customerNumber, number, invoiceDate, dueDate, totalAmountIncludingTax, remainingAmount, status.",
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
];
// NOTE: The workflow ends at "Render & Merge PDFs", which outputs one PDF per
// customer in binary field `data` — downloadable straight from the execution,
// no credentials or external service. To auto-save instead, append EITHER a
// Microsoft OneDrive "upload" node (fileName={{ $json.fileName }}, binary `data`)
// on n8n Cloud, OR a Read/Write File node writing to {{ $json.fullPath }} on a
// self-hosted n8n.

const connections = {
  "When clicking Test workflow": { main: [[{ node: "Keys", type: "main", index: 0 }]] },
  Keys: { main: [[{ node: "Get Token", type: "main", index: 0 }]] },
  // Invoice-driven: the filtered 2023-2024 open invoices decide who gets a letter.
  "Get Token": { main: [[{ node: "Get Open Invoices", type: "main", index: 0 }]] },
  "Get Open Invoices": { main: [[{ node: "Qualifying Customer Nos", type: "main", index: 0 }]] },
  "Qualifying Customer Nos": { main: [[{ node: "Get Customers", type: "main", index: 0 }]] },
  "Get Customers": { main: [[{ node: "Transform (group + tokens)", type: "main", index: 0 }]] },
  "Transform (group + tokens)": { main: [[{ node: "Render & Merge PDFs", type: "main", index: 0 }]] },
  // Terminal: PDFs are emitted here (binary `data`), downloadable from the run.
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
