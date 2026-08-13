# Workflows

n8n workflow exports. These live in n8n under
`My project / Engelman's Bakery / Printing Letter_Invoices`.

## Emailing Letter + Statement Draft Workflow

Takes the letter produced by **Printing Letter_Invoices**, puts it in the body of an email,
attaches the PDF from **Printing Statements**, and creates an **unsent Outlook draft** addressed
to the email on the same account.

Nothing is ever sent. The workflow contains no `send` operation — only `draft: create`.

### Flow

```
Manual trigger
  └─ Printing Letter_Invoices              (sub-workflow, runs once)
       └─ Normalize Account Fields         (accountNumber / accountName / recipientEmail / letterHtml)
            └─ Has Email on File?
                 ├─ true  ─┬─ Printing Statements   (sub-workflow, once per account)
                 │         └─ Combine Letter + Statement   (merge by position)
                 │              └─ Build Draft Payload     (letter → HTML body, PDF → attachment)
                 │                   └─ Create Outlook Draft (Do Not Send)
                 │                        └─ Drafts Ready for Review
                 └─ false ─── Skipped — No Email on File
```

### Before first run — three placeholders to replace

| Where | Placeholder | Replace with |
|---|---|---|
| `Printing Letter_Invoices` | `REPLACE_WITH_PRINTING_LETTER_INVOICES_WORKFLOW_ID` | that workflow's n8n ID |
| `Printing Statements` | `REPLACE_WITH_PRINTING_STATEMENTS_WORKFLOW_ID` | that workflow's n8n ID |
| `Create Outlook Draft (Do Not Send)` | `REPLACE_WITH_OUTLOOK_CREDENTIAL_ID` | the Microsoft Outlook OAuth2 credential for **gpress@engelmansbakery.com** |

The draft is created in whichever mailbox owns the OAuth2 credential, so that credential must be
gpress@engelmansbakery.com.

### Account data (Business Central)

The recipient address is carried through from `Printing Letter_Invoices` — this workflow does not
do its own lookup. In Business Central the chain is:

```
Customer Card  10981 · Berkeley Hills Country Club
  └─ Integration Customer No. ──→ Contact CT020141   (Contact table 5050, "ATTN: Accts Payable")
                                    └─ E-Mail  ← the address the draft goes to
```

`Normalize Account Fields` accepts either Business Central shape, so it works whether the letter
workflow reads BC via OData page endpoints or the v2.0 API:

| Field | OData page fields | API v2.0 fields |
|---|---|---|
| `accountNumber` | `Integration_Customer_No`, `No` | `number`, `customerNumber` |
| `accountName` | `Company_Name`, `Name` | `companyName`, `displayName` |
| `recipientEmail` | `E_Mail` | `email` |

Once the `Printing Letter_Invoices` export is available these fallback chains should be trimmed to
the one real field name each.

### Assumptions

- `Printing Letter_Invoices` returns **one item per account**, carrying the letter content and the
  account's email address.
- `Printing Statements` returns **exactly one item** per account with the statement PDF as binary
  data. `Build Draft Payload` looks for a binary property named `statement`, `data`, `pdf`, or
  `file`, and falls back to the first binary property present.
- Letter and statement are paired **by position**, which holds because `Printing Statements` runs
  in "run once for each item" mode.

### Notes

- Accounts with no email on file are routed to `Skipped — No Email on File` rather than dropped
  silently. Check that branch after each run.
- `Build Draft Payload` throws with the account number if the letter body or the statement PDF is
  missing, so a bad account fails loudly instead of producing an empty draft.
- Attachment filename: `Statement_<account>_<YYYY-MM-DD>.pdf`.
- Subject: `Engelman's Bakery — Account Statement for <account name>`.
