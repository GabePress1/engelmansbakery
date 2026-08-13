# Workflows

n8n workflow exports. These live in n8n under
`My project / Engelman's Bakery / Printing Letter_Invoices`.

## Emailing Letter + Statement Draft Workflow

Takes the letter produced by **Printing Letter_Invoices**, puts it in the body of an email,
attaches the customer's statement rendered from **Business Central**, and creates an **unsent
Outlook draft** addressed to the AP contact on the same account.

Nothing is ever sent. The workflow contains no `send` operation — only `draft: create`.

### Flow

```
Manual trigger
  └─ Printing Letter_Invoices              (sub-workflow, runs once)
       └─ Normalize Account Fields         (accountNumber / accountName / letterHtml)
            └─ Require Account Number      (guard — the join key must exist)
                 └─ Look Up AP Contact (Business Central)
                      └─ Attach Contact Email
                           └─ Has Email on File?
                                ├─ true  ─── Render Statement PDF (Business Central)
                                │              ├─ ok    ─ Build Draft Payload
                                │              │           └─ Statement Base64 → PDF File
                                │              │                └─ Create Outlook Draft (Do Not Send)
                                │              │                     └─ Drafts Ready for Review
                                │              └─ error ─ Statement Not Rendered — Review
                                └─ false ─── Skipped — No Email on File
```

### The account number is the join key

Business Central is the system of record, and every piece of the email is tied together by the
customer account number:

| Piece | Keyed on account number via |
|---|---|
| Letter (email body) | `Printing Letter_Invoices` emits one item per account |
| Email address | `$filter=Integration_Customer_No eq '<accountNumber>'` against BC contacts |
| Statement (attachment) | `customerNo` posted to the BC `StatementApi` codeunit |

`Require Account Number` throws if the key is missing. Without it an empty `$filter` would match
every contact in the company, and the statement would be rendered for the wrong account.

### Where the recipient address comes from

```
Customer Card  10981 · Berkeley Hills Country Club
  └─ Integration Customer No. ──→ Contact CT020141   (Contact table 5050, "ATTN: Accts Payable")
                                    └─ E-Mail  ← the address the draft goes to
```

`Look Up AP Contact (Business Central)` queries the **Contact List** page (5052) published as an
OData V4 web service named `ContactList`:

```
GET .../ODataV4/Company('{BC_COMPANY_NAME}')/ContactList
    ?$filter=Integration_Customer_No eq '10981' and Business_Relation eq 'Customer'
    &$select=No,Name,Company_Name,E_Mail,Integration_Customer_No
```

If more than one contact matches, `Attach Contact Email` prefers the first with an actual email.
The match count rides along as `contactMatchCount`, so a zero-match account is diagnosable from
the skip branch.

### Where the statement comes from

Business Central **cannot** return a report as a PDF over a plain OData query — `$format=PDF` is
not supported on report web services. The PDF has to be rendered in AL and handed back as text, so
this repo ships a small codeunit for it:

**`businesscentral/StatementApi.Codeunit.al`** — renders a statement report, scoped to one
customer, and returns it base64 encoded.

The report is **passed in, not hardcoded**, so the custom statement Engelman's actually prints
stays the source of truth and can change without redeploying the extension. There is deliberately
no default — a missing ID errors out rather than quietly sending customers a statement in the
wrong layout.

Set `BC_STATEMENT_REPORT_ID` to **`50042`**, the custom statement report Engelman's prints.

Deploy it and publish it as a web service:

| Web Services page field | Value |
|---|---|
| Object Type | `Codeunit` |
| Object ID | `50100` |
| Service Name | `StatementApi` |
| Published | yes |

The workflow then calls it as an OData V4 unbound action:

```
POST .../ODataV4/StatementApi_GetCustomerStatementPdf?company={BC_COMPANY_NAME}
{ "customerNo": "10981", "reportId": 50042, "requestPageXml": "" }

→ { "value": "<base64 pdf>" }
```

`Statement Base64 → PDF File` converts that string into a real binary PDF under the binary
property `statement`, which is what the Outlook node attaches.

**Scoping.** The statement report is built over `Cust. Ledger Entry`, so that is the table the
codeunit filters and hands to `Report.SaveAs` as a `RecordRef`. Filtering `Customer` instead would
not scope the report at all — every account would come back in one PDF.

**Open items only** is enforced by that same filter:

```al
CustLedgerEntry.SetRange("Customer No.", customerNo);
CustLedgerEntry.SetRange(Open, true);      // open items only
```

Because the filter does it, `BC_STATEMENT_REQUEST_XML` is only needed for *other* request page
options (a date range, a layout choice). An empty string is fine and is the expected default. To
capture XML if you do need it: open the report in BC, set the request page, save it as a report
setting, and read the parameter XML from the **Report Settings** page.

**Customers with nothing outstanding.** The codeunit errors rather than producing an empty
statement. That error is routed to `Statement Not Rendered — Review` instead of aborting the run,
so one such account does not stop the rest of the batch from drafting.

### Before first run

**Four credential/ID placeholders:**

| Node | Placeholder | Replace with |
|---|---|---|
| `Printing Letter_Invoices` | `REPLACE_WITH_PRINTING_LETTER_INVOICES_WORKFLOW_ID` | that workflow's n8n ID |
| `Look Up AP Contact` / `Render Statement PDF` | `REPLACE_WITH_BUSINESS_CENTRAL_OAUTH2_CREDENTIAL_ID` | a generic OAuth2 credential for the BC API (both nodes) |
| `Create Outlook Draft (Do Not Send)` | `REPLACE_WITH_OUTLOOK_CREDENTIAL_ID` | the Outlook OAuth2 credential for **gpress@engelmansbakery.com** |

The draft is created in whichever mailbox owns the Outlook OAuth2 credential, so that credential
must be gpress@engelmansbakery.com.

**Five project Variables** (Project settings → Variables):

| Variable | Example |
|---|---|
| `BC_TENANT_ID` | your Entra tenant GUID |
| `BC_ENVIRONMENT` | `Production` |
| `BC_COMPANY_NAME` | the BC company name, as it appears in the OData URL |
| `BC_STATEMENT_REPORT_ID` | `50042` — the custom statement report Engelman's prints |
| `BC_STATEMENT_REQUEST_XML` | saved request page XML for open-items-only, or empty |

**Two BC prerequisites:**

- Contact List page (5052) published as a web service named `ContactList`.
- `Statement Api` codeunit (50100) deployed and published as `StatementApi`.

### Assumptions

- `Printing Letter_Invoices` returns **one item per account**, carrying the letter content and the
  customer number. `accountNumber` must resolve to the customer number (e.g. `10981`).
- The custom statement report is built over `Cust. Ledger Entry` and its top-level dataitem is that
  table, so the `RecordRef` the codeunit passes matches what the report expects.
- `Integration_Customer_No` on the Contact record is the link back to the Customer. This is the
  field shown on the Contact Card; if it turns out to be extension-provided rather than base
  application, the `$filter` needs adjusting.

### Notes

- Two review branches, both of which mean a customer did *not* get chased. Check them after every
  run: `Skipped — No Email on File` (no usable address on the BC contact) and
  `Statement Not Rendered — Review` (no open entries, or a genuine BC/auth failure — the item's
  error message tells them apart).
- `Has Email on File?` requires the address to be non-empty *and* contain `@`, so a malformed BC
  record doesn't produce a draft that fails at send time.
- `Build Draft Payload` throws with the account number if the letter body or the statement PDF is
  missing, so a bad account fails loudly instead of producing an empty draft.
- Both BC calls retry 3 times with a 2s backoff on transient failures.
- Attachment filename: `Statement_<account>_<YYYY-MM-DD>.pdf`.
- Subject: `Engelman's Bakery — Account Statement for <account name>`.
