# Workflows

n8n workflow exports. These live in n8n under
`My project / Engelman's Bakery / Printing Letter_Invoices`.

## Emailing Letter + Statement Draft Workflow

Takes the letter produced by **Printing Letter_Invoices**, puts it in the body of an email,
attaches the PDF from **Printing Statements**, and creates an **unsent Outlook draft** addressed to
the AP contact on the same account.

Nothing is ever sent. The workflow contains no `send` operation — only `draft: create`.

### Flow

```
Manual trigger
  └─ Printing Letter_Invoices                  (sub-workflow, runs once)
       └─ Normalize Account Fields             (accountNumber / accountName / letterHtml)
            └─ Look Up AP Contact (Business Central)
                 └─ Attach Contact Email
                      └─ Has Email on File?
                           ├─ true  ─┬─ Printing Statements   (sub-workflow, once per account)
                           │         └─ Combine Letter + Statement   (merge by position)
                           │              └─ Build Draft Payload
                           │                   └─ Create Outlook Draft (Do Not Send)
                           │                        └─ Drafts Ready for Review
                           └─ false ─── Skipped — No Email on File
```

### Where the recipient address comes from

`Printing Letter_Invoices` supplies the letter and the customer number, but **not** the email
address. This workflow looks it up in Business Central:

```
Customer Card  10981 · Berkeley Hills Country Club
  └─ Integration Customer No. ──→ Contact CT020141   (Contact table 5050, "ATTN: Accts Payable")
                                    └─ E-Mail  ← the address the draft goes to
```

`Look Up AP Contact (Business Central)` queries the **Contact List** page (5052) published as an
OData V4 web service named `ContactList`:

```
GET https://api.businesscentral.dynamics.com/v2.0/{BC_TENANT_ID}/{BC_ENVIRONMENT}/ODataV4/Company('{BC_COMPANY_NAME}')/ContactList
    ?$filter=Integration_Customer_No eq '10981' and Business_Relation eq 'Customer'
    &$select=No,Name,Company_Name,E_Mail,Integration_Customer_No
```

If more than one contact matches, `Attach Contact Email` prefers the first one that actually has an
email address. The match count is kept on the item as `contactMatchCount` so a zero-match account
is diagnosable from the skip branch.

### Before first run

**Three credential/ID placeholders:**

| Node | Placeholder | Replace with |
|---|---|---|
| `Printing Letter_Invoices` | `REPLACE_WITH_PRINTING_LETTER_INVOICES_WORKFLOW_ID` | that workflow's n8n ID |
| `Printing Statements` | `REPLACE_WITH_PRINTING_STATEMENTS_WORKFLOW_ID` | that workflow's n8n ID |
| `Look Up AP Contact (Business Central)` | `REPLACE_WITH_BUSINESS_CENTRAL_OAUTH2_CREDENTIAL_ID` | a generic OAuth2 credential for the BC API |
| `Create Outlook Draft (Do Not Send)` | `REPLACE_WITH_OUTLOOK_CREDENTIAL_ID` | the Outlook OAuth2 credential for **gpress@engelmansbakery.com** |

The draft is created in whichever mailbox owns the Outlook OAuth2 credential, so that credential
must be gpress@engelmansbakery.com.

**Three project Variables** (Project settings → Variables):

| Variable | Example |
|---|---|
| `BC_TENANT_ID` | your Entra tenant GUID |
| `BC_ENVIRONMENT` | `Production` |
| `BC_COMPANY_NAME` | the BC company name, as it appears in the OData URL |

**One BC prerequisite:** the Contact List page (5052) must be published as a web service named
`ContactList`. If it's published under a different name, change the last segment of the URL.

### Assumptions

- `Printing Letter_Invoices` returns **one item per account**, carrying the letter content and the
  customer number. `accountNumber` must resolve to the customer number (e.g. `10981`) — it is the
  key for the contact lookup.
- `Printing Statements` returns **exactly one item** per account with the statement PDF as binary
  data. `Build Draft Payload` looks for a binary property named `statement`, `data`, `pdf`, or
  `file`, and falls back to the first binary property present.
- Letter and statement are paired **by position**, which holds because `Printing Statements` runs
  in "run once for each item" mode.
- `Integration_Customer_No` on the Contact record is the link back to the Customer. This is the
  field shown on the Contact Card; if it turns out to be extension-provided rather than base
  application, the `$filter` needs adjusting.

### Notes

- Accounts with no usable email are routed to `Skipped — No Email on File` rather than dropped
  silently. Check that branch after each run.
- `Has Email on File?` requires the address to be non-empty *and* contain `@`, so a malformed BC
  record doesn't produce a draft that fails at send time.
- `Build Draft Payload` throws with the account number if the letter body or the statement PDF is
  missing, so a bad account fails loudly instead of producing an empty draft.
- The BC lookup retries 3 times with a 2s backoff on transient failures.
- Attachment filename: `Statement_<account>_<YYYY-MM-DD>.pdf`.
- Subject: `Engelman's Bakery — Account Statement for <account name>`.
