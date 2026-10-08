#!/usr/bin/env python3
"""Builds the Emailing Letter + Statement Draft Workflow from Printing Letter_Invoices.

The emailing workflow is the printing workflow with one difference. The printing workflow
renders two PDFs - Billing and Shipping - each holding every past-due account back to back.
This one renders two PDFs per account instead: Letter and Statement.

Everything up to and including "Transform (group + tokens)" is copied verbatim from the
source workflow, so the two stay in step on how customers qualify, how addresses are
cleaned and how statements are built. Only the renderer's n8n driver is swapped, and the
email nodes are appended.

Doing it this way - rather than running the printing workflow and splitting its PDFs
afterwards - means no PDF parsing and no external modules. The renderer writes PDF bytes
itself, so nothing here needs pdf-lib, which matters because n8n Cloud does not allow
external modules in Code nodes.

Usage:
    python3 tools/build_workflow.py <source-workflow.json> [--with-secrets]

Without --with-secrets the Client_ID and Client_Secret in Keys1 are blanked, which is what
gets committed. With it they are carried over, for pushing straight to n8n.
"""
import json
import pathlib
import sys

# Nodes copied unchanged from the printing workflow, in chain order.
COPIED_CHAIN = [
    "Settings",
    "Keys1",
    "Get Token1",
    "Get Open Invoices",
    "Qualifying Customer Nos",
    "Get Customers",
    "Get Ship-to Addresses",
    "Transform (group + tokens)",
]

# Replaces everything from the "--- n8n driver" marker in Render & Merge PDFs.
NEW_DRIVER = '''// --- n8n driver -------------------------------------------------------------
// Two PDFs per account - Letter and Statement - rather than the printing workflow's two
// combined packs, Billing and Shipping.
//
// This is the ONLY part that differs from Printing Letter_Invoices. Every page-building
// helper above is identical, so the letters and statements look exactly like the printed
// ones. The printing workflow pads each customer out to a whole number of sheets so the
// double-sided run folds into envelopes correctly; an attachment needs no blank filler
// pages, so this passes pad:false.
//
// Where billing and shipping addresses differ, the letter carries both address variants
// and the statement is repeated once per variant, so each packet stays self-contained.
const all = items.map((i) => i.json);
// Defensive: only render records that actually carry tokens, so one malformed or stale
// item can never crash the whole batch.
const records = all.filter((r) => r && r.tokens);
const skipped = all.length - records.length;

const today = new Date().toISOString().slice(0, 10);
const o = { pad: false };
const out = [];
const excluded = [];

// Recipient addresses come from the Customer page this workflow already queries, rather
// than a separate contact lookup: Customer is published as a web service and proven to
// work here, and an endpoint that is not published fails the whole run.
const emailByAccount = new Map();
for (const it of $('Get Customers').all()) {
  const rows = Array.isArray(it.json && it.json.value) ? it.json.value : [it.json];
  for (const c of rows) {
    if (c && c.No) emailByAccount.set(String(c.No).trim(), clean(c.E_Mail).trim());
  }
}

for (const rec of records) {
  const billing = rec.tokens;
  const accountNumber = clean(billing.AccountNumber);
  const name = clean(billing.Description);

  if (!accountNumber) {
    excluded.push({ name, reason: "no account number" });
    continue;
  }

  // An undeliverable address still matters: the letter prints an address block, and a
  // blank one means the customer record needs fixing before they are chased.
  const problem = addressProblem(billing);
  if (problem) {
    excluded.push({ accountNumber, name, reason: problem });
    continue;
  }

  const statement = rec.statement && rec.statement.lines ? rec.statement : { lines: [], total: 0 };

  // Billing, plus shipping only when it genuinely differs. sameAddress is the same
  // comparison the printing workflow uses to decide who goes in the Shipping pack, so the
  // two agree on what "different" means.
  const variants = [billing];
  if (rec.shipTokens && !sameAddress(billing, rec.shipTokens)) variants.push(rec.shipTokens);

  const letterContents = [];
  const statementContents = [];
  for (const t of variants) {
    letterContents.push(...letterPages(t));
    statementContents.push(...statementPages(t, statement, o));
  }

  const letterFileName = `Letter_${accountNumber}_${today}.pdf`;
  const statementFileName = `Statement_${accountNumber}_${today}.pdf`;

  // Emitted as base64 in JSON rather than as binary: these items pass through HTTP Request
  // nodes on the way to the draft, which do not carry binary through, and the Graph
  // message payload wants base64 anyway.
  out.push({
    json: {
      accountNumber,
      accountName: name,
      recipientEmail: emailByAccount.get(accountNumber) || "",
      addressVariants: variants.length,
      letterPageCount: letterContents.length,
      statementPageCount: statementContents.length,
      balanceDue: statement.total,
      letterFileName,
      statementFileName,
      letterBase64: Buffer.from(
        buildPdf(letterContents, { title: "Past Due Letter " + accountNumber })).toString("base64"),
      statementBase64: Buffer.from(
        buildPdf(statementContents, { title: "Past Due Statement " + accountNumber })).toString("base64"),
      skipped,
      excluded,
    },
  });
}

if (out.length === 0) {
  throw new Error(
    `No customers to draft for: ${records.length} qualifying record(s), ${excluded.length} excluded.`
  );
}

return out;
'''

BC_API_BASE = (
    "https://api.businesscentral.dynamics.com/v2.0/"
    "{{ $('Keys1').first().json.Tenant_ID }}/{{ $('Keys1').first().json.Environment }}"
    "/api/v2.0/companies({{ $('Keys1').first().json.Company_ID }})"
)

AUTH_HEADER = {"name": "Authorization", "value": "=Bearer {{ $('Get Token1').first().json.access_token }}"}

PICK_EMAIL_JS = """\
// Choose the address the draft goes to.
//
// The contacts chain is preferred because that is where the AP contact lives, but the
// Customer card's own E-Mail is kept as a fallback so a customer with no linked contact
// still gets drafted rather than silently dropping out of the run. recipientSource says
// which one was used, so a run can be audited without guessing.
const account = $('Matches ERP Filter?').item.json;
const contacts = $input.item.json.value ?? [];

const withEmail = contacts.filter((c) => (c.email || '').toString().trim());

// An accounts-payable contact is the right recipient for a past due notice when there is
// one; otherwise take the first contact that has an address at all.
const isPayable = (c) => /payable|accounts\\s*pay|\\bA\\/?P\\b/i.test(
  `${c.displayName || ''} ${c.jobTitle || ''}`);
const chosen = withEmail.find(isPayable) ?? withEmail[0] ?? null;

const fromCustomer = (account.recipientEmail || '').toString().trim();
const recipientEmail = chosen ? chosen.email.toString().trim() : fromCustomer;

return {
  json: {
    ...account,
    recipientEmail,
    recipientSource: chosen ? 'contact' : (fromCustomer ? 'customer' : 'none'),
    contactName: chosen ? chosen.displayName ?? '' : '',
    contactNumber: chosen ? chosen.number ?? '' : '',
    contactMatchCount: contacts.length,
    contactsWithEmail: withEmail.length,
  },
};
"""

ERP_FILTER_EXPR = (
    "={{ (() => { const f = ($('ERP Account Number (Filter)').first().json.erpAccountNumber "
    "?? '').toString().trim(); return !f || f === ($json.accountNumber ?? '').toString().trim(); })() }}"
)

BUILD_PAYLOAD_JS = """\
// Build the Microsoft Graph message payload for the draft.
//
// Same payload shape the RT 21 - Daily Email workflow uses, except it is POSTed to
// /me/messages rather than /me/sendMail, which creates an unsent draft.
const json = $input.item.json;

const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const money = (v) => typeof v === 'number'
  ? '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  : null;

const balance = money(json.balanceDue);

// The letter is a PDF, so it cannot be the HTML body. The body is a short cover note and
// the letter is read from its attachment.
const html =
  '<div style="font:14px Segoe UI,Arial,sans-serif;color:#1a1a1a">' +
  `<p>Dear ${esc(json.accountName) || 'Customer'},</p>` +
  "<p>Your account with Engelman's Bakery is currently past due" +
  (balance ? `, with an overdue balance of <b>${balance}</b>` : '') +
  '. Attached are your past due notice and an account statement.</p>' +
  '<p>Please contact us at 770-248-1444 ext. 2 to arrange payment or discuss any ' +
  'questions regarding your account.</p>' +
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
    accountNumber: json.accountNumber,
    accountName: json.accountName,
    recipientEmail: json.recipientEmail,
    addressVariants: json.addressVariants,
    letterPageCount: json.letterPageCount,
    statementPageCount: json.statementPageCount,
    payload: {
      subject: json.accountName
        ? `Engelman's Bakery \\u2014 Past Due Balance for ${json.accountName}`
        : `Engelman's Bakery \\u2014 Past Due Balance (${json.accountNumber})`,
      body: { contentType: 'HTML', content: html },
      toRecipients: [{ emailAddress: { address: json.recipientEmail } }],
      attachments: [
        attachment(json.letterFileName, json.letterBase64),
        attachment(json.statementFileName, json.statementBase64),
      ],
    },
  },
};
"""


def link(name, index=0):
    return {"node": name, "type": "main", "index": index}


def build(source_path, with_secrets):
    source = json.loads(pathlib.Path(source_path).read_text(encoding="utf-8"))
    by_name = {n["name"]: n for n in source["nodes"]}

    missing = [n for n in COPIED_CHAIN + ["Render & Merge PDFs"] if n not in by_name]
    if missing:
        sys.exit(f"source workflow is missing: {missing}")

    nodes = []

    for i, name in enumerate(COPIED_CHAIN):
        node = json.loads(json.dumps(by_name[name]))
        node.pop("webhookId", None)
        if name == "Get Customers":
            # One added column: the address the draft goes to.
            for q in node["parameters"]["queryParameters"]["parameters"]:
                if q["name"] == "$select" and "E_Mail" not in q["value"]:
                    q["value"] = q["value"] + ",E_Mail"
        if name == "Keys1" and not with_secrets:
            for a in node["parameters"]["assignments"]["assignments"]:
                if a["name"] in ("Client_ID", "Client_Secret"):
                    a["value"] = ""
        nodes.append(node)

    renderer = json.loads(json.dumps(by_name["Render & Merge PDFs"]))
    code = renderer["parameters"]["jsCode"]
    renderer["parameters"]["jsCode"] = code[:code.index("// --- n8n driver")] + NEW_DRIVER
    renderer["name"] = "Render Letter + Statement"
    renderer["id"] = "b2000000-0000-4000-8000-000000000001"
    renderer["notes"] = (
        "Copied from Printing Letter_Invoices with only the n8n driver at the bottom "
        "replaced, so every page-building helper is identical and the output looks exactly "
        "like the printed letters and statements. Emits Letter and Statement per account "
        "instead of Billing and Shipping packs, as base64, with pad:false so there are no "
        "blank filler pages. Writes PDF bytes itself - no external modules needed."
    )
    nodes.append(renderer)

    nodes += [
        {
            "parameters": {},
            "id": "b2000000-0000-4000-8000-000000000002",
            "name": "When clicking 'Execute workflow'",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-2420, 300],
        },
        {
            "parameters": {
                "mode": "manual",
                "duplicateItem": False,
                "assignments": {"assignments": [
                    {"id": "f-erp", "name": "erpAccountNumber", "value": "", "type": "string"}
                ]},
                "includeOtherFields": False,
                "options": {},
            },
            "id": "b2000000-0000-4000-8000-000000000003",
            "name": "ERP Account Number (Filter)",
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [-2200, 300],
            "notes": "TYPE THE ERP ACCOUNT NUMBER HERE before running, e.g. 13287, to draft for that one customer. Leave it blank to draft for every past-due account.",
        },
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": "c-erp",
                        "leftValue": ERP_FILTER_EXPR,
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }],
                    "combinator": "and",
                },
                "looseTypeValidation": True,
                "options": {},
            },
            "id": "b2000000-0000-4000-8000-000000000004",
            "name": "Matches ERP Filter?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [0, 300],
            "notes": "Blank filter lets every past-due account through; a filter value keeps only the matching account. If you typed a number and everything lands in 'Filtered Out', that account is not past due in this run.",
        },
        {
            "parameters": {},
            "id": "b2000000-0000-4000-8000-000000000005",
            "name": "Filtered Out — Different Account",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [0, 560],
            "notes": "Accounts excluded by the ERP filter. On a single-account run every other account lands here, which is expected. If ALL accounts land here, the number you typed matched nothing.",
        },
        {
            "parameters": {
                "url": "=" + BC_API_BASE + "/customers",
                "sendHeaders": True,
                "headerParameters": {"parameters": [AUTH_HEADER]},
                "sendQuery": True,
                "queryParameters": {"parameters": [
                    {"name": "$filter", "value": "=number eq '{{ $json.accountNumber }}'"},
                    {"name": "$select", "value": "id,number,displayName,email"},
                ]},
                "options": {},
            },
            "id": "b2000000-0000-4000-8000-000000000013",
            "name": "Get Customer (API v2.0)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1680, 400],
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 2000,
            "notes": "Standard API v2.0, which needs no web service publishing - unlike the ContactList OData page, which returned 404 because it is not published. Resolves the account number to the customer's GUID, which is what the contacts link is keyed on.",
        },
        {
            "parameters": {
                "url": "=" + BC_API_BASE + "/customers({{ $json.value?.[0]?.id ?? '00000000-0000-0000-0000-000000000000' }})/contactsInformation",
                "sendHeaders": True,
                "headerParameters": {"parameters": [AUTH_HEADER]},
                "options": {},
            },
            "id": "b2000000-0000-4000-8000-000000000014",
            "name": "Get Linked Contacts (API v2.0)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1904, 400],
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 2000,
            "onError": "continueRegularOutput",
            "notes": "contactsInformation is the customer-to-contact link. It carries contactNumber but NOT the email, so the numbers are resolved to addresses in the next node. An account with no linked contact falls through to the Customer card's own E-Mail rather than failing.",
        },
        {
            "parameters": {
                "url": "=" + BC_API_BASE + "/contacts",
                "sendHeaders": True,
                "headerParameters": {"parameters": [AUTH_HEADER]},
                "sendQuery": True,
                "queryParameters": {"parameters": [
                    {"name": "$filter", "value": "={{ (($json.value ?? []).map(r => \"number eq '\" + r.contactNumber + \"'\").join(' or ')) || \"number eq ''\" }}"},
                    {"name": "$select", "value": "id,number,displayName,email,companyNumber,type"},
                ]},
                "options": {},
            },
            "id": "b2000000-0000-4000-8000-000000000015",
            "name": "Get Contact Emails (API v2.0)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [2128, 400],
            "retryOnFail": True,
            "maxTries": 3,
            "waitBetweenTries": 2000,
            "onError": "continueRegularOutput",
            "notes": "Resolves the linked contact numbers to addresses. The filter degrades to number eq '' when the customer has no linked contacts, which returns an empty set rather than erroring.",
        },
        {
            "parameters": {"mode": "runOnceForEachItem", "jsCode": PICK_EMAIL_JS},
            "id": "b2000000-0000-4000-8000-000000000016",
            "name": "Pick Recipient Email",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [2352, 400],
        },
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                    "conditions": [
                        {"id": "c-email", "leftValue": "={{ $json.recipientEmail }}", "rightValue": "",
                         "operator": {"type": "string", "operation": "notEmpty", "singleValue": True}},
                        {"id": "c-shape", "leftValue": "={{ $json.recipientEmail }}", "rightValue": "@",
                         "operator": {"type": "string", "operation": "contains"}},
                    ],
                    "combinator": "and",
                },
                "looseTypeValidation": True,
                "options": {},
            },
            "id": "b2000000-0000-4000-8000-000000000008",
            "name": "Has Email on File?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [660, 300],
        },
        {
            "parameters": {},
            "id": "b2000000-0000-4000-8000-000000000009",
            "name": "Skipped — No Email on File",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [660, 560],
            "notes": "Accounts whose Business Central contact has no usable E-Mail land here instead of silently disappearing. Review after every run - these past-due customers were NOT chased and still need contacting by post. contactMatchCount of 0 means no contact matched the account number at all.",
        },
        {
            "parameters": {"mode": "runOnceForEachItem", "jsCode": BUILD_PAYLOAD_JS},
            "id": "b2000000-0000-4000-8000-000000000010",
            "name": "Build Draft Payload",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [880, 300],
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
            "id": "b2000000-0000-4000-8000-000000000011",
            "name": "Create Outlook Draft (Do Not Send)",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [1100, 300],
            "credentials": {"microsoftOutlookOAuth2Api": {"id": "xQT64Ugiue2WLNks", "name": "Microsoft Outlook account (Gabe Press)"}},
            "notes": "POSTs to /me/messages, which CREATES A DRAFT. RT 21 - Daily Email POSTs the same payload shape to /me/sendMail, which sends; this deliberately does not. The draft lands in the Drafts folder of the mailbox owning the credential.",
        },
        {
            "parameters": {},
            "id": "b2000000-0000-4000-8000-000000000012",
            "name": "Drafts Ready for Review",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [1320, 300],
        },
    ]

    connections = {
        "When clicking 'Execute workflow'": {"main": [[link("ERP Account Number (Filter)")]]},
        "ERP Account Number (Filter)": {"main": [[link("Settings")]]},
        "Transform (group + tokens)": {"main": [[link("Render Letter + Statement")]]},
        "Render Letter + Statement": {"main": [[link("Matches ERP Filter?")]]},
        "Matches ERP Filter?": {"main": [
            [link("Get Customer (API v2.0)")],
            [link("Filtered Out — Different Account")],
        ]},
        "Get Customer (API v2.0)": {"main": [[link("Get Linked Contacts (API v2.0)")]]},
        "Get Linked Contacts (API v2.0)": {"main": [[link("Get Contact Emails (API v2.0)")]]},
        "Get Contact Emails (API v2.0)": {"main": [[link("Pick Recipient Email")]]},
        "Pick Recipient Email": {"main": [[link("Has Email on File?")]]},
        "Has Email on File?": {"main": [
            [link("Build Draft Payload")],
            [link("Skipped — No Email on File")],
        ]},
        "Build Draft Payload": {"main": [[link("Create Outlook Draft (Do Not Send)")]]},
        "Create Outlook Draft (Do Not Send)": {"main": [[link("Drafts Ready for Review")]]},
    }
    for a, b in zip(COPIED_CHAIN, COPIED_CHAIN[1:]):
        connections[a] = {"main": [[link(b)]]}

    return {
        "name": "Emailing Letter + Statement Draft Workflow",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    secrets = "--with-secrets" in sys.argv
    wf = build(args[0], secrets)
    root = pathlib.Path(__file__).resolve().parents[1]
    out = (root / "tools" / "_with-secrets.json") if secrets else (root / "workflows" / "emailing-letter-statement-draft.json")
    out.write_text(json.dumps(wf, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(wf['nodes'])} nodes, secrets={'carried' if secrets else 'blanked'})")
