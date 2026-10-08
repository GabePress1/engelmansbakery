#!/usr/bin/env python3
"""Generates the n8n workflow export.

The Code nodes carry enough JS that hand-escaping them inside JSON is a good way to
introduce a silent typo, so the JS lives here as plain strings and json.dump does the
escaping.
"""
import json
import pathlib

NORMALIZE_JS = """\
// One item per address variant arrives here: billing, then shipping when they differ.
// Normalise both the account fields and the name of the letter PDF's binary property, so
// everything downstream can rely on a single shape.
const j = $input.item.json;
const binary = $input.item.binary ?? {};

const accountNumber = (
  j.accountNumber ?? j.Integration_Customer_No ?? j.integrationCustomerNo ??
  j.No ?? j.number ?? j.customerNumber ?? ''
).toString().trim();

const accountName = (
  j.accountName ?? j.Company_Name ?? j.companyName ?? j.Name ?? j.displayName ?? ''
).toString().trim();

// Billing vs shipping, used to order the pages inside the merged letter PDF.
const addressType = (j.addressType ?? j.AddressType ?? j.addressKind ?? '').toString().trim();

// The letter workflow may name its binary property anything; settle on letterPdf.
const letterKey = ['letterPdf', 'letter', 'data', 'pdf', 'file'].find((k) => binary[k]) ??
  Object.keys(binary)[0];

if (!letterKey) {
  throw new Error(
    `No letter PDF on the item for account ${accountNumber || '(unknown)'}. ` +
      'Printing Letter_Invoices is expected to return the letter as binary data.'
  );
}

return {
  json: {
    ...j,
    accountNumber,
    accountName,
    addressType,
    // Only present if the letter workflow also emits text alongside the PDF.
    letterHtml: (j.letterHtml ?? j.letter ?? j.html ?? '').toString(),
  },
  binary: { ...binary, letterPdf: binary[letterKey] },
};
"""

ERP_FILTER_EXPR = (
    "={{ (() => { const f = ($('ERP Account Number (Filter)').first().json.erpAccountNumber "
    "?? '').toString().trim(); return !f || f === ($json.accountNumber ?? '').toString().trim(); })() }}"
)

GROUP_JS = """\
// Collapse the per-address items into one item per account. Without this an account whose
// billing and shipping addresses differ would produce two drafts, two Business Central
// statement calls, and the same statement attached twice.
const groups = new Map();

for (const item of $input.all()) {
  const j = item.json;
  const key = (j.accountNumber || '').toString().trim();

  if (!groups.has(key)) {
    groups.set(key, { ...j, letters: [] });
    delete groups.get(key).letterPdfBase64;
    delete groups.get(key).addressType;
  }

  const group = groups.get(key);
  group.letters.push({
    addressType: (j.addressType || '').toString(),
    pdfBase64: j.letterPdfBase64,
  });

  // Keep the first non-empty name and letter text we see across the variants.
  if (!group.accountName && j.accountName) group.accountName = j.accountName;
  if (!group.letterHtml && j.letterHtml) group.letterHtml = j.letterHtml;
}

// Billing page first, shipping second, anything unlabelled last, so the merged letter PDF
// reads in the same order as the printed pack.
const rank = (t) => {
  const v = (t || '').toLowerCase();
  if (v.includes('bill')) return 0;
  if (v.includes('ship')) return 1;
  return 2;
};

return [...groups.values()].map((group) => {
  group.letters.sort((a, b) => rank(a.addressType) - rank(b.addressType));
  group.letterPdfsBase64 = group.letters.map((l) => l.pdfBase64).filter(Boolean);
  group.addressTypes = group.letters.map((l) => l.addressType);
  group.addressVariantCount = group.letterPdfsBase64.length;
  delete group.letters;
  return { json: group };
});
"""

REQUIRE_ACCOUNT_JS = """\
// The account number is the join key for everything downstream: the Business Central
// contact lookup and the statement render. Fail loudly here rather than letting an empty
// key through - an empty $filter would match every contact in the company.
const accountNumber = ($input.item.json.accountNumber || '').toString().trim();

if (!accountNumber) {
  throw new Error(
    'No account number on this item. Everything downstream (the Business Central contact ' +
      'lookup and the statement) is keyed on it. Check the accountNumber mapping in ' +
      '"Normalize Letter Item" against what Printing Letter_Invoices actually emits.'
  );
}

return { json: { ...$input.item.json, accountNumber } };
"""

ATTACH_EMAIL_JS = """\
// Fold the Business Central contact lookup back onto the account item.
const account = $('Require Account Number').item.json;
const rows = $input.item.json.value ?? [];

// Prefer a contact that actually has an email; otherwise take the first match.
const contact = rows.find((r) => (r.E_Mail || '').toString().trim()) ?? rows[0] ?? {};

const recipientEmail = (contact.E_Mail || account.recipientEmail || '').toString().trim();

return {
  json: {
    ...account,
    recipientEmail,
    contactNumber: contact.No ?? '',
    contactName: contact.Name ?? '',
    accountName: (account.accountName || contact.Company_Name || '').toString().trim(),
    contactMatchCount: rows.length,
  },
};
"""

MERGE_LETTERS_JS = """\
// One letter PDF per draft, whatever the number of address variants.
const json = $('Has Email on File?').item.json;
const letters = json.letterPdfsBase64 ?? [];
const accountNumber = json.accountNumber;

if (letters.length === 0) {
  throw new Error(`No letter PDF to attach for account ${accountNumber}.`);
}

// Single address: nothing to merge, so this path needs no external module at all.
if (letters.length === 1) {
  return { json: { ...json, letterBase64: letters[0], statementBase64: $input.item.json.value } };
}

// Billing and shipping differ, so the pages are concatenated into one document rather than
// sent as two separate letter attachments.
let PDFDocument;
try {
  ({ PDFDocument } = require('pdf-lib'));
} catch (error) {
  throw new Error(
    `Account ${accountNumber} has ${letters.length} letter PDFs (billing and shipping ` +
      'addresses) that need merging into one. That needs the pdf-lib module: set ' +
      'NODE_FUNCTION_ALLOW_EXTERNAL=pdf-lib on the n8n instance and restart. Accounts with a ' +
      'single address are unaffected and will keep drafting normally.'
  );
}

const merged = await PDFDocument.create();
for (const pdfBase64 of letters) {
  const source = await PDFDocument.load(Buffer.from(pdfBase64, 'base64'));
  const pages = await merged.copyPages(source, source.getPageIndices());
  for (const page of pages) merged.addPage(page);
}

return {
  json: {
    ...json,
    letterBase64: Buffer.from(await merged.save()).toString('base64'),
    statementBase64: $input.item.json.value,
  },
};
"""

BUILD_PAYLOAD_JS = """\
// Name the attachments and write the subject and body.
const json = $input.item.json;

const accountNumber = (json.accountNumber || '').toString().trim();
const accountName = (json.accountName || '').toString().trim();
const statementDate = new Date().toISOString().slice(0, 10);

if (!json.statementBase64) {
  throw new Error(
    `Business Central returned no statement PDF for account ${accountNumber}. ` +
      'Check that the StatementApi codeunit is published as a web service.'
  );
}

const safeAccount = (accountNumber || 'account').replace(/[^A-Za-z0-9._-]/g, '_');

// The letter arrives as a PDF, so it cannot be the HTML body. If Printing Letter_Invoices
// also emits letter text, use it; otherwise the body is a short cover note and the letter
// is read from its attachment.
const letterHtml = (json.letterHtml || '').toString().trim();
const bodyInner = letterHtml ||
  `<p>Dear ${accountName || 'Customer'},</p>` +
  '<p>Please find attached your letter and your current account statement.</p>' +
  "<p>Regards,<br/>Engelman's Bakery</p>";

const emailBodyHtml = bodyInner.toLowerCase().includes('<html')
  ? bodyInner
  : `<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;font-size:11pt;color:#000;">${bodyInner}</body></html>`;

return {
  json: {
    ...json,
    statementDate,
    letterFileName: `Letter_${safeAccount}_${statementDate}.pdf`,
    statementFileName: `Statement_${safeAccount}_${statementDate}.pdf`,
    emailBodyHtml,
    emailSubject: accountName
      ? `Engelman's Bakery \\u2014 Account Statement for ${accountName}`
      : `Engelman's Bakery \\u2014 Account Statement (${accountNumber})`,
  },
};
"""

ATTACH_PDFS_JS = """\
// Turn both base64 strings into real binary PDFs: one letter, one statement.
const json = $input.item.json;

const letter = await this.helpers.prepareBinaryData(
  Buffer.from(json.letterBase64, 'base64'), json.letterFileName, 'application/pdf');
const statement = await this.helpers.prepareBinaryData(
  Buffer.from(json.statementBase64, 'base64'), json.statementFileName, 'application/pdf');

// Drop the base64 copies so the item does not carry each PDF twice.
const { letterBase64, statementBase64, letterPdfsBase64, ...rest } = json;

return { json: rest, binary: { letter, statement } };
"""

BC_BASE = "https://api.businesscentral.dynamics.com/v2.0/{{ $vars.BC_TENANT_ID }}/{{ $vars.BC_ENVIRONMENT }}"

nodes = [
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000001",
        "name": "When clicking 'Execute workflow'",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [-1760, 300],
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
        "id": "a1000000-0000-4000-8000-000000000017",
        "name": "ERP Account Number (Filter)",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-1540, 300],
        "notes": "TYPE THE ERP ACCOUNT NUMBER HERE before running, e.g. 10981, to draft for that one customer. Leave it blank to draft for every account Printing Letter_Invoices returns.",
    },
    {
        "parameters": {
            "workflowId": {
                "__rl": True,
                "value": "REPLACE_WITH_PRINTING_LETTER_INVOICES_WORKFLOW_ID",
                "mode": "id",
                "cachedResultName": "Printing Letter_Invoices",
            },
            "mode": "once",
            "options": {"waitForSubWorkflow": True},
        },
        "id": "a1000000-0000-4000-8000-000000000002",
        "name": "Printing Letter_Invoices",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.2,
        "position": [-1320, 300],
        "notes": "Returns the letter as a PDF binary, one item per address variant - billing, then shipping when it differs. Those variants are collapsed to one item per account further down.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": NORMALIZE_JS},
        "id": "a1000000-0000-4000-8000-000000000003",
        "name": "Normalize Letter Item",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-1100, 300],
        "notes": "Fallback chains cover both Business Central shapes: OData page fields (No, Name, Company_Name, Integration_Customer_No) and API v2.0 fields. Also settles the letter PDF under a known binary property name. accountNumber must resolve to the customer number (e.g. 10981) - it is the key for the contact lookup and the statement.",
    },
    {
        "parameters": {
            "operation": "binaryToPropery",
            "binaryPropertyName": "letterPdf",
            "destinationKey": "letterPdfBase64",
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000020",
        "name": "Letter PDF → Base64",
        "type": "n8n-nodes-base.extractFromFile",
        "typeVersion": 1,
        "position": [-880, 300],
        "notes": "Moves the letter PDF into JSON as base64. Binary data does not survive the HTTP Request nodes further down, whereas JSON does, so the letter rides along as text and is turned back into a PDF at the end.",
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
        "id": "a1000000-0000-4000-8000-000000000018",
        "name": "Matches ERP Filter?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [-660, 300],
        "notes": "Blank filter lets every account through; a filter value keeps only the account whose number matches exactly. If you typed a number and everything lands in the 'Filtered Out' branch, the number does not match what Printing Letter_Invoices emits - check for leading zeros or padding.",
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000019",
        "name": "Filtered Out — Different Account",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [-660, 560],
        "notes": "Accounts excluded by the ERP filter. On a single-account run every other account lands here, which is expected. If ALL accounts land here, the ERP number you typed matched nothing.",
    },
    {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": GROUP_JS},
        "id": "a1000000-0000-4000-8000-000000000021",
        "name": "Group Letters by Account",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-440, 300],
        "notes": "One item per account from here on. Without this an account whose billing and shipping addresses differ would produce two drafts, two statement calls, and the same statement attached twice. Letter pages are ordered billing first, then shipping.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": REQUIRE_ACCOUNT_JS},
        "id": "a1000000-0000-4000-8000-000000000013",
        "name": "Require Account Number",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-220, 300],
        "notes": "Guard: an empty account number would turn the BC $filter into a match-everything query and would render the wrong account's statement.",
    },
    {
        "parameters": {
            "url": f"={BC_BASE}/ODataV4/Company('{{{{ $vars.BC_COMPANY_NAME }}}}')/ContactList",
            "authentication": "genericCredentialType",
            "genericAuthType": "oAuth2Api",
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
        "position": [0, 300],
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
        "credentials": {"oAuth2Api": {"id": "REPLACE_WITH_BUSINESS_CENTRAL_OAUTH2_CREDENTIAL_ID", "name": "Business Central OAuth2"}},
        "notes": "Queries the Contact List page (5052 / table 5050) published as the OData web service 'ContactList', filtered to the contact whose Integration Customer No. matches this customer - the CT020141 -> 10981 link. If the published web service has a different name, change the last URL segment.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": ATTACH_EMAIL_JS},
        "id": "a1000000-0000-4000-8000-000000000012",
        "name": "Attach Contact Email",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [220, 300],
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
        "id": "a1000000-0000-4000-8000-000000000004",
        "name": "Has Email on File?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [440, 300],
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000010",
        "name": "Skipped — No Email on File",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [440, 560],
        "notes": "Accounts whose Business Central contact has no usable E-Mail land here instead of silently disappearing. Review this branch after each run - contactMatchCount of 0 means no contact matched the customer number at all.",
    },
    {
        "parameters": {
            "method": "POST",
            "url": f"={BC_BASE}/ODataV4/StatementApi_GetCustomerStatementPdf",
            "authentication": "genericCredentialType",
            "genericAuthType": "oAuth2Api",
            "sendQuery": True,
            "queryParameters": {"parameters": [{"name": "company", "value": "={{ $vars.BC_COMPANY_NAME }}"}]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ customerNo: $json.accountNumber, reportId: Number($vars.BC_STATEMENT_REPORT_ID), requestPageXml: $vars.BC_STATEMENT_REQUEST_XML ?? '' }) }}",
            "options": {},
        },
        "id": "a1000000-0000-4000-8000-000000000014",
        "name": "Render Statement PDF (Business Central)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 300],
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
        "onError": "continueErrorOutput",
        "credentials": {"oAuth2Api": {"id": "REPLACE_WITH_BUSINESS_CENTRAL_OAUTH2_CREDENTIAL_ID", "name": "Business Central OAuth2"}},
        "notes": "Calls the Statement Api codeunit (businesscentral/StatementApi.Codeunit.al) as an OData V4 unbound action. BC cannot return a report as PDF over a plain OData query - $format=PDF is not supported on report web services - so the codeunit renders the report scoped to this customer and returns it base64 encoded in the 'value' property. Called once per account, so the statement is never duplicated. BC_STATEMENT_REPORT_ID must be set to 50042.",
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000016",
        "name": "Statement Not Rendered — Review",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [660, 560],
        "notes": "Accounts whose statement could not be rendered land here so one bad account does not abort the whole batch. Two different things arrive here and the item's error message tells them apart: 'no open ledger entries' means the customer owes nothing, while anything else is a genuine Business Central or auth failure. Do not ignore this branch - a failure here means a customer who should have been chased was not.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": MERGE_LETTERS_JS},
        "id": "a1000000-0000-4000-8000-000000000022",
        "name": "Merge Letter PDFs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [880, 300],
        "notes": "Produces exactly one letter PDF per draft. A single-address account passes straight through and needs no external module. Only accounts with differing billing and shipping addresses need pdf-lib, which requires NODE_FUNCTION_ALLOW_EXTERNAL=pdf-lib on the n8n instance.",
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": BUILD_PAYLOAD_JS},
        "id": "a1000000-0000-4000-8000-000000000007",
        "name": "Build Draft Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1100, 300],
    },
    {
        "parameters": {"mode": "runOnceForEachItem", "jsCode": ATTACH_PDFS_JS},
        "id": "a1000000-0000-4000-8000-000000000015",
        "name": "Attach Letter + Statement PDFs",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [1320, 300],
        "notes": "Turns the two base64 strings back into binary PDFs under the binary properties 'letter' and 'statement', which is what the Outlook node attaches.",
    },
    {
        "parameters": {
            "resource": "draft",
            "operation": "create",
            "subject": "={{ $json.emailSubject }}",
            "bodyContent": "={{ $json.emailBodyHtml }}",
            "additionalFields": {
                "bodyContentType": "html",
                "toRecipients": "={{ $json.recipientEmail }}",
                "attachments": {"attachments": [
                    {"binaryPropertyName": "letter"},
                    {"binaryPropertyName": "statement"},
                ]},
            },
        },
        "id": "a1000000-0000-4000-8000-000000000008",
        "name": "Create Outlook Draft (Do Not Send)",
        "type": "n8n-nodes-base.microsoftOutlook",
        "typeVersion": 2,
        "position": [1540, 300],
        "credentials": {"microsoftOutlookOAuth2Api": {"id": "REPLACE_WITH_OUTLOOK_CREDENTIAL_ID", "name": "Microsoft Outlook account (gpress@engelmansbakery.com)"}},
        "notes": "Creates an UNSENT draft only, with two attachments: one letter PDF and one statement PDF. The draft lands in the mailbox that owns the OAuth2 credential, so this credential must be gpress@engelmansbakery.com. There is deliberately no 'send' operation anywhere in this workflow.",
    },
    {
        "parameters": {},
        "id": "a1000000-0000-4000-8000-000000000009",
        "name": "Drafts Ready for Review",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [1760, 300],
    },
]

def main(node, *targets, out=0):
    """One main-output connection entry."""
    return {node: {"main": [[{"node": t, "type": "main", "index": 0} for t in targets]]}}

connections = {
    "When clicking 'Execute workflow'": {"main": [[{"node": "ERP Account Number (Filter)", "type": "main", "index": 0}]]},
    "ERP Account Number (Filter)": {"main": [[{"node": "Printing Letter_Invoices", "type": "main", "index": 0}]]},
    "Printing Letter_Invoices": {"main": [[{"node": "Normalize Letter Item", "type": "main", "index": 0}]]},
    "Normalize Letter Item": {"main": [[{"node": "Letter PDF → Base64", "type": "main", "index": 0}]]},
    "Letter PDF → Base64": {"main": [[{"node": "Matches ERP Filter?", "type": "main", "index": 0}]]},
    "Matches ERP Filter?": {"main": [
        [{"node": "Group Letters by Account", "type": "main", "index": 0}],
        [{"node": "Filtered Out — Different Account", "type": "main", "index": 0}],
    ]},
    "Group Letters by Account": {"main": [[{"node": "Require Account Number", "type": "main", "index": 0}]]},
    "Require Account Number": {"main": [[{"node": "Look Up AP Contact (Business Central)", "type": "main", "index": 0}]]},
    "Look Up AP Contact (Business Central)": {"main": [[{"node": "Attach Contact Email", "type": "main", "index": 0}]]},
    "Attach Contact Email": {"main": [[{"node": "Has Email on File?", "type": "main", "index": 0}]]},
    "Has Email on File?": {"main": [
        [{"node": "Render Statement PDF (Business Central)", "type": "main", "index": 0}],
        [{"node": "Skipped — No Email on File", "type": "main", "index": 0}],
    ]},
    "Render Statement PDF (Business Central)": {"main": [
        [{"node": "Merge Letter PDFs", "type": "main", "index": 0}],
        [{"node": "Statement Not Rendered — Review", "type": "main", "index": 0}],
    ]},
    "Merge Letter PDFs": {"main": [[{"node": "Build Draft Payload", "type": "main", "index": 0}]]},
    "Build Draft Payload": {"main": [[{"node": "Attach Letter + Statement PDFs", "type": "main", "index": 0}]]},
    "Attach Letter + Statement PDFs": {"main": [[{"node": "Create Outlook Draft (Do Not Send)", "type": "main", "index": 0}]]},
    "Create Outlook Draft (Do Not Send)": {"main": [[{"node": "Drafts Ready for Review", "type": "main", "index": 0}]]},
}

workflow = {
    "name": "Emailing Letter + Statement Draft Workflow",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"},
    "pinData": {},
    "meta": {"instanceId": ""},
    "tags": [],
}

out = pathlib.Path(__file__).resolve().parents[1] / "workflows" / "emailing-letter-statement-draft.json"
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {out} ({len(nodes)} nodes)")
