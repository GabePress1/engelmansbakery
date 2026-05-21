# Workflow Setup Instructions

## Step 1 — Get your Excel Workbook ID

1. Open `BC_HubSpot_Sync.xlsx` in OneDrive
2. Look at the browser URL — it contains `resid=XXXXXXX`
3. Copy that ID — you'll need it as `EXCEL_WORKBOOK_ID` below

## Step 2 — Set n8n Variables

In n8n go to **Settings → Variables** and create these:

| Variable | Value |
|---|---|
| `EXCEL_WORKBOOK_ID` | The resid value from the OneDrive URL |
| `BC_BASE_URL` | e.g. `https://api.businesscentral.dynamics.com/v2.0/YOUR_TENANT/production/api/v2.0` |
| `BC_COMPANY_ID` | Your BC company GUID |

## Step 3 — Add Credentials

### Microsoft 365
1. n8n → Settings → Credentials → Add
2. Search **Microsoft Excel 365**
3. Sign in with the same Microsoft account that owns the OneDrive file
4. Name it exactly: `Microsoft 365 - Engelmans`

### HubSpot
1. Add Credential → search **HubSpot**
2. Use a Private App token (HubSpot → Settings → Integrations → Private Apps)
3. Required scopes: `crm.objects.companies.write`, `crm.objects.contacts.write`
4. Name it exactly: `HubSpot - Engelmans`

### Business Central
1. Add Credential → **OAuth2**
2. Use your Azure AD app registration for BC
3. Name it exactly: `BC OAuth2`

## Step 4 — Import Workflows

1. n8n → Workflows → **Import from File**
2. Import `phase1_companies.json`
3. Import `phase2_contacts.json`
4. Open each workflow and verify credentials are mapped correctly
5. Activate both workflows

## Schedule

- Phase 1 (Companies): runs at **6:00 AM** Mon–Fri
- Phase 2 (Contacts): runs at **6:30 AM** Mon–Fri (after Phase 1 completes)

## First Run

On first run, both workflows will do a **full pull** (no prior timestamp in Excel).
This is expected — subsequent runs will only process changed records.
