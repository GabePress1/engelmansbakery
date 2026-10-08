#!/usr/bin/env python3
"""Generates the n8n workflow export.

The Code nodes carry enough JS that hand-escaping them inside JSON is a good way to
introduce a silent typo, so the JS lives here as plain strings and json.dump does the
escaping. The page-splitting logic mirrors tools/split_pack.mjs, which is runnable
standalone and has been checked against real packs.
"""
import json
import pathlib

# --------------------------------------------------------------------------------------
# Code node sources
# --------------------------------------------------------------------------------------

EXPLODE_JS = """\
// Printing Letter_Invoices returns one PDF per address type - billing, and shipping when
// any account's addresses differ - each holding every past-due account back to back.
// Burst them into one item per page so n8n's own PDF text extractor can read each page.
const { PDFDocument } = require('pdf-lib');

const packs = $input.all();
const pages = [];

for (let packIndex = 0; packIndex < packs.length; packIndex++) {
  const binary = packs[packIndex].binary ?? {};
  const key = ['data', 'pdf', 'file', 'letterPdf'].find((k) => binary[k]) ?? Object.keys(binary)[0];

  if (!key) {
    throw new Error(
      `Item ${packIndex} from Printing Letter_Invoices carries no PDF. That workflow is ` +
        'expected to return each pack as binary data.'
    );
  }

  const buffer = await this.helpers.getBinaryDataBuffer(packIndex, key);
  const pack = await PDFDocument.load(buffer);

  for (let pageIndex = 0; pageIndex < pack.getPageCount(); pageIndex++) {
    const single = await PDFDocument.create();
    const [page] = await single.copyPages(pack, [pageIndex]);
    single.addPage(page);
    const bytes = Buffer.from(await single.save());

    pages.push({
      json: {
        packIndex,
        pageIndex,
        // Kept as base64 in JSON as well: JSON survives every node reliably, so the
        // reassembly step can reach it without depending on binary storage mode.
        pageBase64: bytes.toString('base64'),
      },
      binary: {
        page: await this.helpers.prepareBinaryData(
          bytes, `pack${packIndex}-page${pageIndex}.pdf`, 'application/pdf'),
      },
    });
  }
}

if (pages.length === 0) {
  throw new Error('Printing Letter_Invoices returned no pages.');
}

return pages;
"""

ASSEMBLE_JS = """\
// Turn the exploded pages back into one letter PDF and one statement PDF per account.
//
// Each account occupies a block of: letter page -> address page -> statement page(s) ->
// blank separator. The four-page stride is deliberately NOT assumed - blocks are cut at
// each letter page instead, so a customer with enough open invoices to spill onto a second
// statement page still splits correctly rather than silently shifting every account after
// them by a page.
const { PDFDocument } = require('pdf-lib');

const LETTER_MARKER = /Subject: Past Due Balance/;
const STATEMENT_MARKER = /Past Due Invoices/;
const ACCOUNT_MARKER = /Account Number:\\s*(\\d+)/;

const sources = $('Explode Packs to Pages').all();
const extracted = $input.all();

const classified = extracted.map((item, i) => {
  const source = sources[i].json;
  const flat = (item.json.pageText ?? item.json.text ?? '')
    .toString().replace(/\\s+/g, ' ').trim();

  let kind = 'blank';
  if (LETTER_MARKER.test(flat)) kind = 'letter';
  else if (STATEMENT_MARKER.test(flat)) kind = 'statement';
  else if (flat.length > 0) kind = 'address';

  return {
    packIndex: source.packIndex,
    pageBase64: source.pageBase64,
    kind,
    accountNumber: flat.match(ACCOUNT_MARKER)?.[1] ?? null,
  };
});

// Cut a block at every letter page, and never let a block span two packs.
const blocks = [];
let current = null;
for (const page of classified) {
  if (page.kind === 'letter' || current === null || page.packIndex !== current.packIndex) {
    current = { packIndex: page.packIndex, pages: [] };
    blocks.push(current);
  }
  current.pages.push(page);
}

const accounts = new Map();
for (const block of blocks) {
  const accountNumber = block.pages.find((p) => p.accountNumber)?.accountNumber;
  if (!accountNumber) continue;

  if (!accounts.has(accountNumber)) {
    accounts.set(accountNumber, { letter: [], statement: [], addressVariants: 0 });
  }
  const account = accounts.get(accountNumber);

  // Letter side is the letter and its address page. Blank separators exist for duplex
  // printing and are dropped.
  account.letter.push(
    ...block.pages.filter((p) => p.kind === 'letter' || p.kind === 'address').map((p) => p.pageBase64));

  // One statement per address variant: an account whose billing and shipping addresses
  // differ gets two packets, and each needs its own copy.
  account.statement.push(...block.pages.filter((p) => p.kind === 'statement').map((p) => p.pageBase64));

  account.addressVariants += 1;
}

if (accounts.size === 0) {
  throw new Error(
    'No account numbers found in the packs. Pages are identified by the "Account Number:" ' +
      'line on the statement page - check that the pack layout still carries it.'
  );
}

const concat = async (pagesBase64) => {
  const out = await PDFDocument.create();
  for (const pageBase64 of pagesBase64) {
    const doc = await PDFDocument.load(Buffer.from(pageBase64, 'base64'));
    const copied = await out.copyPages(doc, doc.getPageIndices());
    for (const page of copied) out.addPage(page);
  }
  return Buffer.from(await out.save()).toString('base64');
};

const results = [];
for (const [accountNumber, parts] of accounts) {
  if (parts.letter.length === 0) {
    throw new Error(`Account ${accountNumber} has a statement but no letter pages.`);
  }
  if (parts.statement.length === 0) {
    throw new Error(`Account ${accountNumber} has letter pages but no statement.`);
  }

  results.push({
    json: {
      accountNumber,
      addressVariants: parts.addressVariants,
      letterPageCount: parts.letter.length,
      statementPageCount: parts.statement.length,
      letterBase64: await concat(parts.letter),
      statementBase64: await concat(parts.statement),
    },
  });
}

return results;
"""

ERP_FILTER_EXPR = (
    "={{ (() => { const f = ($('ERP Account Number (Filter)').first().json.erpAccountNumber "
    "?? '').toString().trim(); return !f || f === ($json.accountNumber ?? '').toString().trim(); })() }}"
)

ATTACH_EMAIL_JS = """\
// Fold the Business Central contact lookup back onto the account item.
const account = $('Matches ERP Filter?').item.json;
const rows = $input.item.json.value ?? [];

// Prefer a contact that actually has an email; otherwise take the first match.
const contact = rows.find((r) => (r.E_Mail || '').toString().trim()) ?? rows[0] ?? {};

return {
  json: {
    ...account,
    recipientEmail: (contact.E_Mail || '').toString().trim(),
    accountName: (contact.Company_Name || contact.Name || '').toString().trim(),
    contactNumber: contact.No ?? '',
    contactName: contact.Name ?? '',
    contactMatchCount: rows.length,
  },
};
"""

BUILD_PAYLOAD_JS = """\
// Build the Microsoft Graph message payload for the draft.
//
// This follows the same shape the RT 21 - Daily Email workflow uses, except it is POSTed
// to /me/messages rather than /me/sendMail, which creates an unsent draft.
const json = $input.item.json;

const accountNumber = (json.accountNumber || '').toString().trim();
const accountName = (json.accountName || '').toString().trim();
const today = new Date().toISOString().slice(0, 10);
const safeAccount = (accountNumber || 'account').replace(/[^A-Za-z0-9._-]/g, '_');

const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// The letter is a PDF, so it cannot be the HTML body. The body is a short cover note and
// the letter is read from its attachment.
const html =
  '<div style="font:14px Segoe UI,Arial,sans-serif;color:#1a1a1a">' +
  `<p>Dear ${esc(accountName) || 'Customer'},</p>` +
  "<p>Your account with Engelman's Bakery is currently past due. Attached are your past " +
  'due notice and your account statement.</p>' +
  '<p>Please contact us at 770-248-1444 ext. 2 to arrange payment or discuss any questions ' +
  'regarding your account.</p>' +
  "<p>Best Regards,<br/>Engelman's Bakery<br/>770-248-1444</p>" +
  '</div>';

const attachment = (name, contentBytes) => ({
  '@odata.type': '#microsoft.graph.fileAttachment',
  name,
  contentType: 'application/pdf',
  contentBytes,
});

return {
  json: {
    accountNumber,
    accountName,
    recipientEmail: json.recipientEmail,
    addressVariants: json.addressVariants,
    letterPageCount: json.letterPageCount,
    statementPageCount: json.statementPageCount,
    payload: {
      subject: accountName
        ? `Engelman's Bakery \u2014 Past Due Balance for ${accountName}`
        : `Engelman's Bakery \u2014 Past Due Balance (${accountNumber})`,
      body: { contentType: 'HTML', content: html },
      toRecipients: [{ emailAddress: { address: json.recipientEmail } }],
      attachments: [
        attachment(`Letter_${safeAccount}_${today}.pdf`, json.letterBase64),
        attachment(`Statement_${safeAccount}_${today}.pdf`, json.statementBase64),
      ],
    },
  },
};
"""

BC_BASE = (
    "https://api.businesscentral.dynamics.com/v2.0/"
    "{{ $('BC Keys').first().json.Tenant_ID }}/{{ $('BC Keys').first().json.Environment }}"
    "/ODataV4/Company('{{ $('BC Keys').first().json.Company }}')"
)

# --------------------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------------------

nodes = [
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000001",
        "name": "When clicking 'Execute workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [-1540, 300],
    },
    {
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {"assignments": [
                {"id": "f-erp-filter", "name": "erpAccountNumber", "value": "", "type": "string"}
            ]},
            "includeOtherFields": False,
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000002",
        "name": "ERP Account Number (Filter)",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-1320, 300],
        "notes": "TYPE THE ERP ACCOUNT NUMBER HERE before running, e.g. 13287, to draft for that one customer. Leave it blank to draft for every past-due account in the run.",
    },
    {
        "parameters": {
            "mode": "manual",
            "duplicateItem": False,
            "assignments": {"assignments": [
                {"id": "k-tenant", "name": "Tenant_ID", "value": "bddeba87-9d41-4063-a0e3-be9e6afcd2ba", "type": "string"},
                {"id": "k-env", "name": "Environment", "value": "Production", "type": "string"},
                {"id": "k-company", "name": "Company", "value": "Live-EB", "type": "string"},
                {"id": "k-clientid", "name": "Client_ID", "value": "", "type": "string"},
                {"id": "k-secret", "name": "Client_Secret", "value": "", "type": "string"},
            ]},
            "includeOtherFields": False,
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000003",
        "name": "BC Keys",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-1100, 300],
        "notes": "Tenant, environment and company match Printing Letter_Invoices. Client_ID and Client_Secret are deliberately BLANK - copy them from that workflow's Keys1 node, or better, move both workflows onto a stored credential so the secret is not sitting in a Set node.",
    },
    {
        "parameters": {
            "method": "POST",
            "url": "=https://login.microsoftonline.com/{{ $('BC Keys').first().json.Tenant_ID }}/oauth2/v2.0/token",
            "sendBody": True,
            "contentType": "form-urlencoded",
            "bodyParameters": {"parameters": [
                {"name": "grant_type", "value": "client_credentials"},
                {"name": "client_id", "value": "={{ $('BC Keys').first().json.Client_ID }}"},
                {"name": "client_secret", "value": "={{ $('BC Keys').first().json.Client_Secret }}"},
                {"name": "scope", "value": "https://api.businesscentral.dynamics.com/.default"},
            ]},
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000004",
        "name": "Get BC Token",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [-880, 300],
        "executeOnce": True,
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
        "notes": "Client credentials token for the Business Central API, the same pattern Printing Letter_Invoices uses. Runs once per execution, not once per account.",
    },
    {
        "parameters": {
            "workflowId": {
                "__rl": True,
                "value": "Fn9PTTNOT2rSFwag",
                "mode": "list",
                "cachedResultName": "Printing Letter_Invoices",
            },
            "mode": "once",
            "options": {"waitForSubWorkflow": True},
        },
        "id": "a1000000-0000-4000-8000-000000000005",
        "name": "Printing Letter_Invoices",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2,
        "position": [-660, 300],
        "notes": "Returns two items - type 'billing' and type 'shipping' - each carrying a pack PDF on binary property 'data'. Each pack holds every past-due account back to back.",
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": EXPLODE_JS},
        "id": "a1000000-0000-4000-8000-000000000006",
        "name": "Explode Packs to Pages",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-440, 300],
        "notes": "One item per page, so n8n's own PDF text extractor can read each page separately. Needs the pdf-lib module: NODE_FUNCTION_ALLOW_EXTERNAL=pdf-lib.",
    },
    {
        "parameters": {
            "operation": "pdf",
            "binaryPropertyName": "page",
            "destinationKey": "pageText",
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000007",
        "name": "Read Page Text",
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": [-220, 300],
        "notes": "n8n's built-in PDF text extractor, run per page. Used instead of a second external module - the page's text is all that is needed to tell a letter page from an address page from a statement page.",
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": ASSEMBLE_JS},
        "id": "a1000000-0000-4000-8000-000000000008",
        "name": "Assemble Letter + Statement",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [0, 300],
        "notes": "One item per account from here on, each carrying a letter PDF and a statement PDF as base64. Blocks are cut at each letter page rather than on a fixed four-page stride, so an account whose statement spills onto a second page still splits correctly. Needs pdf-lib.",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "c-erp-filter",
                    "leftValue": ERP_FILTER_EXPR,
                    "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000009",
        "name": "Matches ERP Filter?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [220, 300],
        "notes": "Blank filter lets every account through; a filter value keeps only the account whose number matches exactly. If you typed a number and everything lands in the 'Filtered Out' branch, that account is not past due in this run.",
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000010",
        "name": "Filtered Out \u2014 Different Account",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [220, 560],
        "notes": "Accounts excluded by the ERP filter. On a single-account run every other account lands here, which is expected. If ALL accounts land here, the ERP number you typed matched nothing.",
    },
    {
        "parameters": {
            "url": "=" + BC_BASE + "/ContactList",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization", "value": "=Bearer {{ $('Get BC Token').first().json.access_token }}"},
            ]},
            "sendQuery": True,
            "queryParameters": {"parameters": [
                {"name": "$filter", "value": "=Integration_Customer_No eq '{{ $json.accountNumber }}' and Business_Relation eq 'Customer'"},
                {"name": "$select", "value": "No,Name,Company_Name,E_Mail,Integration_Customer_No"},
            ]},
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000011",
        "name": "Look Up AP Contact (Business Central)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [440, 300],
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
        "notes": "The only Business Central call: it supplies the recipient address. Queries the Contact List page (5052 / table 5050) published as the OData web service 'ContactList', filtered to the contact whose Integration Customer No. matches this account. NOTE: Printing Letter_Invoices does not use this endpoint, so confirm ContactList is actually published as a web service - a 404 here means it is not.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": ATTACH_EMAIL_JS},
        "id": "a1000000-0000-4000-8000-000000000012",
        "name": "Attach Contact Email",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [660, 300],
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [
                    {"id": "c-has-email", "leftValue": "={{ $json.recipientEmail }}", "rightValue": "",
                     "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}},
                    {"id": "c-email-shape", "leftValue": "={{ $json.recipientEmail }}", "rightValue": "@",
                     "operator": {"type": "string", "operation": "contains"}},
                ],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000013",
        "name": "Has Email on File?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [880, 300],
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000014",
        "name": "Skipped \u2014 No Email on File",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [880, 560],
        "notes": "Accounts whose Business Central contact has no usable E-Mail land here instead of silently disappearing. Review this branch after each run - contactMatchCount of 0 means no contact matched the account number at all, and these customers still need chasing by post.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": BUILD_PAYLOAD_JS},
        "id": "a1000000-0000-4000-8000-000000000015",
        "name": "Build Draft Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 300],
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://graph.microsoft.com/v1.0/me/messages",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "microsoftOutlookOAuth2Api",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.payload) }}",
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000016",
        "name": "Create Outlook Draft (Do Not Send)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1320, 300],
        "credentials": {"microsoftOutlookOAuth2Api": {"id": "xQT64Ugiue2WLNks", "name": "Microsoft Outlook account (Gabe Press)"}},
        "notes": "POSTs to /me/messages, which CREATES A DRAFT. The RT 21 - Daily Email workflow POSTs the same payload shape to /me/sendMail, which sends; this deliberately does not. The draft lands in the Drafts folder of the mailbox owning the credential, with the letter and statement attached as fileAttachments.",
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000017",
        "name": "Drafts Ready for Review",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1540, 300],
    },
]

connections = {
    "When clicking 'Execute workflow'": {"main": [[{"node": "ERP Account Number (Filter)", "type": "main", "index": 0}]]},
    "ERP Account Number (Filter)": {"main": [[{"node": "BC Keys", "type": "main", "index": 0}]]},
    "BC Keys": {"main": [[{"node": "Get BC Token", "type": "main", "index": 0}]]},
    "Get BC Token": {"main": [[{"node": "Printing Letter_Invoices", "type": "main", "index": 0}]]},
    "Printing Letter_Invoices": {"main": [[{"node": "Explode Packs to Pages", "type": "main", "index": 0}]]},
    "Explode Packs to Pages": {"main": [[{"node": "Read Page Text", "type": "main", "index": 0}]]},
    "Read Page Text": {"main": [[{"node": "Assemble Letter + Statement", "type": "main", "index": 0}]]},
    "Assemble Letter + Statement": {"main": [[{"node": "Matches ERP Filter?", "type": "main", "index": 0}]]},
    "Matches ERP Filter?": {"main": [
        [{"node": "Look Up AP Contact (Business Central)", "type": "main", "index": 0}],
        [{"node": "Filtered Out \u2014 Different Account", "type": "main", "index": 0}],
    ]},
    "Look Up AP Contact (Business Central)": {"main": [[{"node": "Attach Contact Email", "type": "main", "index": 0}]]},
    "Attach Contact Email": {"main": [[{"node": "Has Email on File?", "type": "main", "index": 0}]]},
    "Has Email on File?": {"main": [
        [{"node": "Build Draft Payload", "type": "main", "index": 0}],
        [{"node": "Skipped \u2014 No Email on File", "type": "main", "index": 0}],
    ]},
    "Build Draft Payload": {"main": [[{"node": "Create Outlook Draft (Do Not Send)", "type": "main", "index": 0}]]},
    "Create Outlook Draft (Do Not Send)": {"main": [[{"node": "Drafts Ready for Review", "type": "main", "index": 0}]]},
}

workflow = {
    "name": "Emailing Letter + Statement Draft Workflow",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"},
}

out = pathlib.Path(__file__).resolve().parents[1] / "workflows" / "emailing-letter-statement-draft.json"
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {out} ({len(nodes)} nodes)")
