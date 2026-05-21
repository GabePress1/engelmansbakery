# Workflow Setup Instructions

## Step 1 — Update your Excel workbook

Rename the existing sheets and add two new ones:

| Sheet name | Column headers (row 1) |
|---|---|
| `sync_log` | run_date \| phase \| records_processed \| last_bc_timestamp |
| `customers` | erp_account_number \| hubspot_company_id \| name \| email \| phone \| city \| last_synced |
| `invoices` | invoice_number \| customer_number \| hubspot_deal_id \| amount \| due_date \| status \| last_synced |
| `payments` | payment_number \| customer_number \| amount \| payment_date \| applied_to_invoice \| description \| last_synced |

You can delete the `hubspot_id_cache` sheet — the `customers` sheet replaces it.

## Step 2 — Get your Excel Workbook ID

1. Open `BC_HubSpot_Sync.xlsx` in OneDrive in a browser
2. Look at the URL — find `resid=` and copy the value after it (up to the next `&`)
3. That's your `EXCEL_WORKBOOK_ID`

## Step 3 — Add Credentials in n8n

Go to **Settings → Credentials → Add Credential** for each:

**Microsoft Excel 365**
- Sign in with the Microsoft account that owns the OneDrive file
- Name it exactly: `Microsoft 365 - Engelmans`

**HubSpot**
- Use a Private App token: HubSpot → Settings → Integrations → Private Apps → Create
- Required scopes: `crm.objects.companies.write`, `crm.objects.deals.write`
- Name it exactly: `HubSpot - Engelmans`

**Business Central (OAuth2)**
- Use your Azure AD app registration for BC
- Name it exactly: `BC OAuth2`

## Step 4 — Fill in the Config node

Each workflow has a **Config** node at the top. Open it and paste in:

| Field | Value |
|---|---|
| `EXCEL_WORKBOOK_ID` | From Step 2 |
| `BC_BASE_URL` | e.g. `https://api.businesscentral.dynamics.com/v2.0/YOUR_TENANT_ID/production/api/v2.0` |
| `BC_COMPANY_ID` | Your BC company GUID (visible in BC under Company Information) |

Do this for all three workflows — the Config node is the only place you need to change values.

## Step 5 — Import and Activate

1. n8n → Workflows → **Import from File**
2. Import in order: `phase1_companies.json`, `phase2_invoices.json`, `phase3_payments.json`
3. Open each, verify credentials are mapped, then **Activate**

## Schedule

| Phase | Time | What it does |
|---|---|---|
| Phase 1 | 6:00 AM Mon–Fri | BC customers → HubSpot companies + customers sheet |
| Phase 2 | 6:30 AM Mon–Fri | BC invoices → HubSpot deals + invoices sheet |
| Phase 3 | 7:00 AM Mon–Fri | BC payments → payments sheet + marks deals paid in HubSpot |

## First Run

On first run all three phases do a **full pull** — no prior timestamp in sync_log so they
start from 2000-01-01. This is expected and only happens once. Every run after that
only processes records changed since the previous run.
