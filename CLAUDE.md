# Engelmansbakery N8N Business Central Integration

This document describes the n8n workflow setup for exporting Business Central data to Excel.

## Overview

This project automates the daily export of Business Central invoices, orders, and their line items for all accounts with Shipping Agent Code = "RT 21" (Route 21) to an Excel file stored in OneDrive/SharePoint.

## Prerequisites

- **n8n Instance**: A running n8n installation (self-hosted or cloud)
- **Business Central Tenant**: Access to your Business Central instance
- **OneDrive/SharePoint Access**: A Microsoft 365 account with OneDrive or SharePoint access
- **OAuth2 Credentials**: For both Business Central and Microsoft 365 authentication

## Credentials Setup

### Business Central OAuth2 Setup

1. In Business Central, register your n8n application:
   - Go to your Business Central instance
   - Register an OAuth application with your n8n webhook URL
   - Record these values:
     - **Tenant ID**: Your Azure AD tenant ID
     - **Client ID**: The application client ID
     - **Client Secret**: The application client secret

2. In n8n:
   - Create a new "Business Central" credential
   - Use OAuth2 authentication
   - Paste the Tenant ID, Client ID, and Client Secret
   - Configure the redirect URL (provided by n8n)

### Microsoft 365 OAuth2 Setup

1. In Azure Active Directory:
   - Register an application for Microsoft Graph
   - Create a client secret
   - Grant permissions for "Files.ReadWrite.All" and "Sites.ReadWrite.All"
   - Record:
     - **Client ID**: The application client ID
     - **Client Secret**: The application client secret

2. In n8n:
   - Create a new "Microsoft 365" or "OneDrive" credential
   - Use OAuth2 authentication
   - Paste the Client ID and Client Secret

## Workflow Configuration

### Execution Schedule

The workflow runs daily at **6:00 AM UTC** (configurable).

To change the schedule:
1. Open the workflow in n8n
2. Edit the "Schedule Trigger" node
3. Change the "Trigger Time" setting

### Output Configuration

Excel file is saved to **OneDrive/SharePoint** with the following naming convention:
- `BusinessCentral_Route21_Export_{YYYY-MM-DD}.xlsx`

To change the output location:
1. Edit the "Save to OneDrive" node in the workflow
2. Update the folder path and file naming

### Data Filtering

The workflow filters Business Central data by **Shipping Agent Code = "RT 21"**.

To modify the filter:
1. Edit each data retrieval node (Invoices, Invoice Lines, Sales Orders, Sales Order Lines)
2. Update the OData `$filter` parameter from `shippingAgentCode eq 'RT 21'` to your desired value

## Workflow Nodes

The workflow consists of the following node layers:

1. **Schedule Trigger** - Daily execution at 6 AM
2. **Data Retrieval** (4 parallel nodes):
   - Invoices Query (Business Central OData)
   - Invoice Lines Query (Business Central OData)
   - Sales Orders Query (Business Central OData)
   - Sales Order Lines Query (Business Central OData)
3. **Data Processing** (2 nodes):
   - Merge Invoices + Sales Orders
   - Merge Invoice Lines + Sales Order Lines
4. **Excel Generation** - Create 2-sheet workbook
5. **Error Handling** - Email notification and logging on failure
6. **OneDrive Upload** - Save Excel to cloud storage

## Troubleshooting

### Workflow Not Running

Check the n8n logs:
1. Open n8n execution history
2. Look for failed executions
3. Check error messages for authentication or API issues

### Authentication Errors

- **Business Central**: Verify OAuth credentials are current; tokens may need refresh
- **OneDrive**: Check that the Microsoft 365 credential is still valid; re-authenticate if needed

### Data Not Appearing

- Verify Business Central data exists with Shipping Agent Code = "RT 21"
- Check OData API endpoints are accessible
- Ensure the filter syntax is correct in the HTTP request nodes

### Excel File Format Issues

- Verify the Excel generation node has proper column mappings
- Check that data types match expected formats (dates, numbers, text)
- Review the data transformation nodes for consistency

## File Structure

```
/home/user/engelmansbakery/
├── CLAUDE.md                                    # This file
├── SETUP.md                                     # Setup instructions
├── README.md                                    # Project overview
└── workflows/
    └── business-central-excel-export.json       # N8n workflow export
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review n8n execution logs
3. Verify Business Central API connectivity
4. Test individual nodes in n8n for debugging
