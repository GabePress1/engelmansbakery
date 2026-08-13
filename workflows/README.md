# Workflows

n8n workflow exports.

## Emailing Letter + Statement Draft Workflow

Takes the letter produced by **Printing Letter: Invoices Workflow**, puts it in the body of an
email, attaches the PDF from **Printing Statement Workflow**, and creates an **unsent Outlook
draft** addressed to the email on the same account.

Nothing is ever sent. The workflow contains no `send` operation — only `draft: create`.

### Flow

```
Manual trigger
  └─ Printing Letter: Invoices Workflow   (sub-workflow, runs once)
       └─ Normalize Account Fields        (accountNumber / accountName / recipientEmail / letterHtml)
            └─ Has Email on File?
                 ├─ true  ─┬─ Printing Statement Workflow  (sub-workflow, once per account)
                 │         └─ Combine Letter + Statement    (merge by position)
                 │              └─ Build Draft Payload      (letter → HTML body, PDF → attachment)
                 │                   └─ Create Outlook Draft (Do Not Send)
                 │                        └─ Drafts Ready for Review
                 └─ false ─── Skipped — No Email on File
```

### Before first run — four placeholders to replace

| Where | Placeholder | Replace with |
|---|---|---|
| `Printing Letter: Invoices Workflow` | `REPLACE_WITH_PRINTING_LETTER_INVOICES_WORKFLOW_ID` | that workflow's n8n ID |
| `Printing Statement Workflow` | `REPLACE_WITH_PRINTING_STATEMENT_WORKFLOW_ID` | that workflow's n8n ID |
| `Create Outlook Draft (Do Not Send)` | `REPLACE_WITH_OUTLOOK_CREDENTIAL_ID` | the Microsoft Outlook OAuth2 credential for **gpress@engelmansbakery.com** |
| `Normalize Account Fields` | the `??` fallback chains | the actual field names the letter workflow emits |

The draft is created in whichever mailbox owns the OAuth2 credential, so that credential must be
gpress@engelmansbakery.com.

### Assumptions

- The letter workflow returns **one item per account**, carrying the letter content and the
  account's email address.
- The statement workflow returns **exactly one item** per account with the statement PDF as
  binary data. `Build Draft Payload` looks for a binary property named `statement`, `data`, `pdf`,
  or `file`, and falls back to the first binary property present.
- Letter and statement are paired **by position**, which holds because the statement sub-workflow
  runs in "run once for each item" mode.

### Notes

- Accounts with no email on file are routed to `Skipped — No Email on File` rather than dropped
  silently. Check that branch after each run.
- `Build Draft Payload` throws with the account number if the letter body or the statement PDF is
  missing, so a bad account fails loudly instead of producing an empty draft.
- Attachment filename: `Statement_<account>_<YYYY-MM-DD>.pdf`.
- Subject: `Engelman's Bakery — Account Statement for <account name>`.
