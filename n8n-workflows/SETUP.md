# BC - Hub Route 21 Pricing to Excel (Daily) — Setup Guide

## Overview

This n8n workflow pulls Route 21 pricing data from Business Central daily at 6 AM and writes it to an Excel workbook on SharePoint/OneDrive.

### Workflow Flow

```
Daily 6AM Trigger
  → BC - Get Route 21 Items (HTTP Request to BC OData API)
  → Extract Item Data (Code node — normalizes the response)
  → BC - Get Sales Prices (HTTP Request — fetches active prices per item)
  → Merge Item + Pricing Data (Code node — combines items + prices)
  → Clear Old PricingData Sheet (deletes stale sheet, continues on fail)
  → Create Fresh PricingData Sheet
  → Write Pricing to Excel (appends all rows to PricingData sheet)
  → Build Summary Row (Code node — counts, averages)
  → Append to DailyLog Sheet (running log of each daily refresh)
```

### Excel Workbook Sheets

| Sheet | Purpose |
|---|---|
| **PricingData** | Replaced daily with full Route 21 pricing snapshot |
| **DailyLog** | Append-only log — one row per day with summary stats |

### Columns Written to PricingData

| Column | Source |
|---|---|
| Item No. | BC Item number |
| Description | BC Item displayName |
| Category | itemCategoryCode |
| Unit Cost | Item card unit cost |
| List Price | Item card unit price |
| Sales Price | From Sales Prices table (if any) |
| Sales Type | Customer / Customer Price Group / All Customers |
| Sales Code | The specific customer or group code |
| Min. Quantity | Minimum quantity for this price |
| UOM | Unit of measure code |
| Price Start Date | When this price became active |
| Price End Date | When this price expires (blank = no end) |
| Inventory | Current inventory level |
| Blocked | Yes / No |
| Last Modified | Last modification timestamp |
| Report Date | Date the report was generated |

---

## Setup Steps

### 1. Import the Workflow

1. Open your n8n instance
2. Go to **Workflows → Import from File**
3. Select `BC_Hub_Route21_Pricing_to_Excel.json`

### 2. Create the Excel Workbook on SharePoint

1. Upload `Route21_Pricing_Report.xlsx` (included in this repo) to your SharePoint document library
2. Note the **workbook ID** — you can find it via Microsoft Graph Explorer:
   ```
   GET https://graph.microsoft.com/v1.0/sites/{site-id}/drive/root:/Route21_Pricing_Report.xlsx
   ```
   The `id` field in the response is your workbook ID.

### 3. Set Environment Variables in n8n

Go to **Settings → Environment Variables** in n8n and add:

| Variable | Value | Example |
|---|---|---|
| `BC_BASE_URL` | Your Business Central API base URL | `https://api.businesscentral.dynamics.com/v2.0/{tenant-id}/{environment}` |
| `BC_COMPANY_ID` | Your BC company GUID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `SHAREPOINT_WORKBOOK_ID` | The SharePoint file ID for the Excel workbook | `01ABCDEF...` |

### 4. Configure Credentials

#### Business Central OAuth2
1. In n8n, go to **Credentials → New → Microsoft Dynamics 365 Business Central OAuth2 API**
2. Enter your Azure AD App Registration details:
   - Client ID
   - Client Secret
   - Tenant ID
3. Set the required API permissions: `Financials.ReadWrite.All` or `API.ReadWrite.All`
4. Update the credential ID in nodes **"BC - Get Route 21 Items"** and **"BC - Get Sales Prices"**

#### Microsoft Excel OAuth2
1. In n8n, go to **Credentials → New → Microsoft Excel OAuth2 API**
2. Use the same or a separate Azure AD App Registration
3. Required permissions: `Files.ReadWrite.All`, `Sites.ReadWrite.All`
4. Update the credential ID in all Excel nodes

### 5. Adjust the Item Filter (if needed)

The default filter pulls items where `itemCategoryCode eq 'ROUTE21'`. If your BC uses a different category code or filtering field for Route 21 items, update the URL in the **"BC - Get Route 21 Items"** node.

Common alternatives:
- Filter by location: `locationCode eq 'ROUTE21'`
- Filter by dimension: requires a different API endpoint
- Filter by item attribute: use `/itemAttributes` endpoint

### 6. Activate the Workflow

Toggle the workflow to **Active**. It will run daily at 6:00 AM (server time). You can also click **Execute Workflow** to test manually.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| 401 Unauthorized from BC | Re-authorize the BC OAuth2 credential; check token hasn't expired |
| Empty data returned | Verify the item category filter matches your BC setup |
| Excel write fails | Confirm the workbook ID is correct and the credential has Files.ReadWrite.All |
| "Sheet not found" on first run | The workflow handles this — `Clear Old PricingData Sheet` has `continueOnFail: true` |
| Pagination not working | BC defaults to 100 records; the `Prefer: odata.maxpagesize=1000` header increases this |
