# Workflows

n8n workflow exports. These live in n8n under
`My project / Engelman's Bakery / Printing Letter_Invoices`.

## Emailing Letter + Statement Draft Workflow

**Live:** https://engelmansbakery.app.n8n.cloud/workflow/HKwXwbVcl26PVl9J

This is **`Printing Letter_Invoices` with one change**. That workflow renders two combined
PDFs — `Past-Due-Billing` and `Past-Due-Shipping` — each holding every past-due account back to
back. This one renders two PDFs *per account* instead:

| Attachment | Contents |
|---|---|
| `Letter_<account>_<date>.pdf` | The past due letter and its address page |
| `Statement_<account>_<date>.pdf` | The Past Due Invoices statement |

and creates an **unsent Outlook draft** per account carrying both.

Nothing is ever sent. The draft node POSTs to `/me/messages`, which creates a draft;
`RT 21 - Daily Email` POSTs the same payload shape to `/me/sendMail`, which sends. This
deliberately does not.

### How it relates to Printing Letter_Invoices

Everything from `Settings` through `Transform (group + tokens)` is **copied verbatim** by
`tools/build_workflow.py`, so the two stay in step on how customers qualify, how addresses are
cleaned and how statements are built. There are exactly two deliberate differences:

1. **`Get Customers`** asks for one extra column, `E_Mail` — the address the draft goes to.
2. **`Render & Merge PDFs`** becomes **`Render Letter + Statement`**: only the n8n driver at the
   bottom of that Code node is replaced. Every page-building helper above it is untouched, so the
   letters and statements look exactly like the printed ones.

To regenerate after the printing workflow changes:

```sh
python3 tools/build_workflow.py <printing-letter-invoices-export.json>
```

### Flow

```
Manual trigger
  └─ ERP Account Number (Filter)       ← type the account number here
       └─ Settings → Keys1 → Get Token1 → Get Open Invoices
            → Qualifying Customer Nos → Get Customers → Get Ship-to Addresses
                 └─ Transform (group + tokens)          [all copied verbatim]
                      └─ Render Letter + Statement      ← the one changed node
                           └─ Matches ERP Filter?
                                ├─ false ─ Filtered Out — Different Account
                                └─ true ── Has Email on File?
                                     ├─ false ─ Skipped — No Email on File
                                     └─ true ── Build Draft Payload
                                          └─ Create Outlook Draft (Do Not Send)
                                               └─ Drafts Ready for Review
```

### Running it

1. Open the workflow and click into **ERP Account Number (Filter)**.
2. Type the ERP account number — e.g. `13287` — into `erpAccountNumber`.
3. **Execute workflow**.
4. The draft appears in the Drafts folder of the mailbox owning the Outlook credential.

Leave `erpAccountNumber` blank to draft for every past-due account in the run.

### Where the recipient address comes from

The **standard API v2.0**, which needs no web service publishing. An earlier version called a
`ContactList` OData web service and **returned 404** — that page is not published, and nothing in
`Printing Letter_Invoices` uses it either.

The AP contact's address takes three calls, because no single v2.0 resource carries both the
customer link and the email:

```
Get Customer (API v2.0)          customers?$filter=number eq '13287'   → the customer's GUID
Get Linked Contacts (API v2.0)   customers({id})/contactsInformation   → contactNumber(s), no email
Get Contact Emails (API v2.0)    contacts?$filter=number eq 'CT…'      → displayName + email
Pick Recipient Email             choose one
```

`contactInformation` is the customer-to-contact link but carries no email; `contacts` carries the
email but no customer number. Hence the hop through contact numbers.

**Pick Recipient Email** prefers, in order:

1. a linked contact whose name looks like accounts payable (`ATTN: Accts Payable`, `Accounts
   Payable Dept`, …) and has an email
2. any linked contact with an email
3. the **Customer card's** own `E_Mail`, which `Get Customers` already returns

That last fallback means a customer with no linked contact still gets drafted rather than dropping
out of the run. Every item carries `recipientSource` (`contact` / `customer` / `none`) so a run can
be audited without guessing which path was taken.

Accounts that reach `none` land in `Skipped — No Email on File`.

The two contact calls use `onError: continueRegularOutput`, so a customer with no linked contacts
degrades to the Customer email instead of failing the run.

`node tools/test_recipient_pick.mjs` exercises the selection logic across all five cases.

### Billing and shipping addresses

Where an account's shipping address genuinely differs from its billing address, the letter PDF
carries **both address variants** and the statement is **repeated once per variant**, so each
packet stays self-contained. `sameAddress()` — the same comparison the printing workflow uses to
decide who goes in the Shipping pack — decides what "different" means, so the two agree.

Blank filler pages are dropped (`pad: false`). They exist so a double-sided print run folds into
envelopes; an attachment does not need them.

### Checking the renderer without n8n

```sh
cd tools && npm install && cd ..
node tools/test_renderer.mjs
```

Runs the `Render Letter + Statement` Code node verbatim out of the export against mock records,
with n8n stubbed, and reports page counts per account. A single-address account yields a 2-page
letter and a 1-page statement; a two-address account yields 4 and 2.

### Known issue in the address comparison

Account `12308` ("That Burger Spot Riverdale") is treated as having different billing and shipping
addresses when it does not:

```
billing:   723 Highway 138 Unit C        shipping:   723 Highway 138
                                                     Unit C
```

`normAddr()` joins the address lines with `|` before comparing, so the same address split across
two lines does not match one on a single line. That account gets a duplicate letter and statement
it does not need. This is in `Printing Letter_Invoices` and affects the printed run too.

### Secrets

`Client_ID` and `Client_Secret` in `Keys1` are **blanked in the committed copy**.
`tools/build_workflow.py --with-secrets` carries them through from the source export for pushing
to n8n, and writes to `tools/_with-secrets.json`, which is gitignored.

Both workflows would be better off with those on a stored n8n credential than in a Set node.

### Not currently used

`businesscentral/StatementApi.Codeunit.al` renders statement report **50042** from Business
Central over an OData V4 unbound action. It was built when the statement was going to come from
BC rather than from the renderer.

It is **not wired into the workflow** and needs no deployment. Kept because switching the
statement attachment to the real BC report remains an option — the statement here is the renderer's
own Past Due Invoices layout, not report 50042.
