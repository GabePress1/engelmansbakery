# Engelman's Bakery — Past-Due Letter + Statement Batch

Generates personalized **past-due collection letters** and matching **customer statements**
for Engelman's Bakery customers who have **open invoices dated 2023–2024** in Microsoft
Dynamics 365 Business Central, and renders them to printable PDFs.

The intended runtime is the n8n workflow **`Printing Letter_Invoices`** (which already holds the
BC app-registration keys in its `Keys` node). This repo contains the importable workflow, the
letter template, and the reusable scripts — all verified locally with a synthetic dataset.

```
templates/   past-due-letter.docx + generator (Word "mail merge" template)
scripts/     transform, render (pdf-lib), docx fill (docxtemplater), pdf merge, docx→pdf
n8n/         Printing_Letter_Invoices.workflow.json + its generator
test/        sample data + end-to-end and workflow-code validators
```

## What it does

1. **Read the open invoices first** (OData V4): the `Customer_Ledger_Entries` page filtered to
   `Open = true`, `Document_Type = 'Invoice'`, `Document_Date` in **2023-01-01 … 2024-12-31**.
   **These invoices decide who gets a letter** — nobody else is ever fetched or processed.
2. **Derive the qualifying customers**: the `Qualifying Customer Nos` node takes the distinct
   `Customer_No` set from those invoices and builds the `$filter` used to fetch **only** those
   customers from the `Customer` page (name/address/`Balance_Due_LCY`). If no invoices qualify,
   it emits nothing and the run produces **zero** letters.
3. **Group + tokenize**: group the invoices by customer and sum `Remaining_Amount`; a customer
   whose filtered open balance nets to zero still gets **no** letter.
4. **Render** a letter (the seven merge tokens) + a statement (the open-invoice table) per
   customer, **merge** them into one PDF, and write it to the output folder.

> **Only customers with an open 2023–2024 invoice are targeted — at two levels.** The customer
> fetch itself is filtered to the qualifying set (step 2), and the Transform re-checks the window
> (step 3). Fully-paid customers and customers whose only open invoice falls outside 2023–2024 are
> excluded (see the `C00034` and `C00045` cases in `test/sample-customers.json`).

### The seven merge tokens (Customer page → letter)

| Letter token          | BC `Customer` field | Notes |
|-----------------------|---------------------|-------|
| `Description`         | `Name`              | account name |
| `Address_1`           | `Address`           | |
| `Address_2`           | `Address_2`         | blank-safe |
| `City`                | `City`              | |
| `State`               | `County`            | US localization stores state in `County` |
| `Zipcode`             | `Post_Code`         | |
| `Converted_balance`   | see below           | pre-formatted USD, e.g. `4,820.75` (template prints the `$`) |

### Which dollar amount goes in the letter — read this

`Converted_balance` defaults to the **sum of `Remaining_Amount` on the customer's 2023–2024 open
invoices** (`amountSource: 'filtered'`), which matches "overdue balance" for the filtered set and
equals the statement total. To instead use the customer's **total** open balance
(`Balance_Due_LCY`), change one setting:

- **n8n:** in the **Transform** node, `buildRecords(..., { amountSource: 'balanceDue' })`.
- **Local:** same flag in `test/run-local.js`.

These differ whenever a customer also has open invoices outside 2023–2024.

## Rendering: two paths

- **Default — pure JavaScript (`pdf-lib`), no external services.** Runs inside the n8n Code node.
  This is what the workflow ships with and what the local tests exercise.
  Requirement on self-hosted n8n:
  - set env var `NODE_FUNCTION_ALLOW_EXTERNAL=pdf-lib`
  - make `pdf-lib` requireable by n8n (e.g. `npm i pdf-lib` in your n8n user folder / custom
    extensions dir, or bake it into your n8n image).
- **High-fidelity Word "mail merge" (optional).** Fill `templates/past-due-letter.docx` with
  `docxtemplater` (`scripts/fill-letter.js`) and convert docx→PDF with **headless LibreOffice**
  (`scripts/docx-to-pdf.js`, `soffice --headless --convert-to pdf`) or **Gotenberg**
  (`POST /forms/libreoffice/convert`). Use this if you want pixel-exact fidelity to the Word file.

> The template here is a faithful **reconstruction** with a **text** letterhead placeholder
> (`ENGELMAN'S BAKERY`). To keep the exact brand logo, either drop the logo image into
> `past-due-letter.docx`, or open your original Word file and replace each `«Field»` mergefield
> with a `{Field}` tag (`«Description»`→`{Description}`, `«Converted_balance»`→`{Converted_balance}`,
> etc.), then point `scripts/fill-letter.js` at it.

## Business Central setup

**App registration / `Keys` node** — the workflow reads these from the `Keys` node (never commit
real values):

| Key             | Example        | Used for |
|-----------------|----------------|----------|
| `Tenant_ID`     | GUID           | token endpoint + BC URL |
| `Client_ID`     | GUID           | client-credentials auth |
| `Client_Secret` | secret         | client-credentials auth |
| `Environment`   | `Production`   | BC URL segment |
| `Company`       | `Live-EB`      | `Company('…')` in the OData URL |
| `Output_Folder` | the OneDrive path below | where PDFs are written |

Output folder (default):
`C:\Users\GPress\OneDrive - engelmansbakery.com\2. Financial\C. Accounting\e. Controller's Folders\Gabe's Projects`

**OData V4 endpoints used** (base
`https://api.businesscentral.dynamics.com/v2.0/{Tenant_ID}/{Environment}/ODataV4/Company('{Company}')`):

- `…/Customer?$select=No,Name,Address,Address_2,City,County,Post_Code,Balance_Due_LCY`
- `…/Customer_Ledger_Entries?$filter=Open eq true and Document_Type eq 'Invoice' and Document_Date ge 2023-01-01 and Document_Date le 2024-12-31&$select=Customer_No,Document_Type,Document_No,Document_Date,Due_Date,Amount,Remaining_Amount,Open`

If your published ledger web service has a different name or field names, edit the
**Get Ledger Entries** node. (You confirmed the `Customer` page exposes `Balance_Due_LCY`; the
`Customer_Ledger_Entries` page must be published for the date-filtered invoice detail — if it
isn't, publish page 25 as a web service, or switch `amountSource` to `balanceDue` and drop the
statement detail.)

## Import & run in n8n

1. **n8n → Workflows → Import from File →** `n8n/Printing_Letter_Invoices.workflow.json`.
   (Or merge its nodes into your existing `Printing Letter_Invoices` workflow.)
2. Put your real values in the **`Keys`** node (or reuse your existing `Keys` node and delete the
   imported placeholder one — the placeholders are not real secrets).
3. Ensure `pdf-lib` is available to the Code node (see *Rendering* above).
4. Confirm the **Get Ledger Entries** node points at your published page.
5. **Execute** once and check the output folder. Hand-check 2–3 customer totals against BC's
   Customer Ledger.

Flow: `Keys → Get Token → Get Ledger Entries → Qualifying Customer Nos → Get Customers → Transform → Render & Merge PDFs → Write PDF to OneDrive`.

> If your qualifying set is very large, the `Get Customers` `$filter` (`No eq '…' or …`) can get
> long; split it into batches to stay under URL-length limits. For a typical past-due run the set
> is small enough for a single request.

## Local development & verification

```bash
npm install
npm run build:template     # regenerate templates/past-due-letter.docx
npm run build:workflow     # regenerate n8n/Printing_Letter_Invoices.workflow.json from scripts/*
npm test                   # run both validators
```

- `npm run test:local` → `test/run-local.js`: full pipeline on `test/sample-customers.json`,
  writing PDFs + filled `.docx` to `./out`, with assertions (correct customers qualify, 2022
  invoice excluded, payment line excluded, USD formatting, tokens filled).
- `npm run test:workflow` → `test/validate-workflow.js`: executes the **actual Code-node source**
  embedded in the workflow JSON against the sample data, so the workflow can't silently drift from
  the tested scripts.

`out/` and `node_modules/` are git-ignored; credentials must never be committed (see `.gitignore`).
