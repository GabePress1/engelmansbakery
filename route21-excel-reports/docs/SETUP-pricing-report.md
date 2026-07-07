# Route 21 – BC Item Pricing → Excel (Daily) — Setup Guide

## What This Workflow Does

Runs daily at 6 AM. Pulls item pricing and order data from Business Central (same BC instance and credentials as your existing "Route 21 – BC Item Pricing This Year" workflow) and writes it to an Excel file on SharePoint/OneDrive.

### Flow

```
Schedule Trigger (6 AM daily) or Manual Trigger
  → Keys (BC + Azure AD credentials — same as your existing workflow)
  ├→ Get BC Token (BC OData API auth)
  │   → Set Date Range (Jan 1 this year → today)
  │     ├→ Fetch All Invoice Lines (YTD)  ─┐
  │     ├→ Fetch All Invoice Headers (YTD) ─┤→ Build Invoice Rows
  │     └→ Fetch Open Sales Orders ────────→ Build Sales Order Rows
  └→ Get Graph Token (Microsoft Graph auth for SharePoint)
      → Configure SharePoint IDs

  Build Invoice Rows → Clear InvoiceLines Sheet → Write Invoice Rows to Excel ─┐
  Build Sales Order Rows → Clear SalesOrders Sheet → Write SO Rows to Excel ───┤→ Summary
```

### Excel Sheets

| Sheet | Refreshed | Contents |
|---|---|---|
| **InvoiceLines** | Replaced daily | All posted invoice line items YTD |
| **OpenSalesOrders** | Replaced daily | Current open/released sales orders |

### InvoiceLines Columns

| Column | BC Source |
|---|---|
| Item No | `Posted_Sales_Invoice_Lines_Excel.No` |
| Description | `Posted_Sales_Invoice_Lines_Excel.Description` |
| Invoice No | `Posted_Sales_Invoice_Lines_Excel.Document_No` |
| Customer No | `Sell_to_Customer_No` |
| Customer Name | `Sell_to_Customer_Name` |
| Quantity | `Quantity` |
| Unit Price | `Unit_Price` |
| Amount | `Amount` |
| Sales Order No | `Order_No` |
| PO Number | `Posted_Sales_Invoice_Excel.External_Document_No` |
| Posting Date | `ERC_Posting_Date` |
| Requested Delivery | `Requested_Delivery_Date_SOD` |

### OpenSalesOrders Columns

| Column | BC Source |
|---|---|
| Order No | `Sales_Order_Excel.No` |
| Customer No | `Sell_to_Customer_No` |
| Customer Name | `Sell_to_Customer_Name` |
| PO Number | `External_Document_No` |
| Status | `Status` (Open / Released) |
| Requested Delivery | `Requested_Delivery_Date` |

---

## Setup

### 1. Add Graph API Permission to Your Azure AD App

Your existing app registration (`db88be9e-de13-4205-b0c1-472007c60c36`) already has BC permissions. Add:

- **Microsoft Graph → Application permissions → Files.ReadWrite.All**
- Grant admin consent

This lets the workflow write to SharePoint Excel files using client credentials.

### 2. Upload the Excel Template to SharePoint

1. Upload `Route21_Pricing_Report.xlsx` to your SharePoint document library
2. Get the IDs you need via [Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer):

```
# Find your site ID
GET https://graph.microsoft.com/v1.0/sites/{your-sharepoint-host}:/sites/{site-name}

# List drives (document libraries)
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives

# Find the file item ID
GET https://graph.microsoft.com/v1.0/drives/{drive-id}/root/children
```

### 3. Configure the Workflow

Open the **"Configure SharePoint IDs"** node and replace the three placeholder values:

```javascript
const SHAREPOINT_SITE_ID = 'YOUR_SHAREPOINT_SITE_ID';     // from step 2
const DRIVE_ID           = 'YOUR_DRIVE_ID';                // from step 2
const EXCEL_FILE_ITEM_ID = 'YOUR_EXCEL_FILE_ITEM_ID';      // from step 2
```

### 4. Activate

Toggle the workflow to **Active**. Test with the manual trigger first.
