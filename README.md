# Engelmansbakery Business Central Integration

## Project Overview

This project automates the daily export of Business Central data to Excel using n8n. Specifically, it extracts invoices, invoice lines, sales orders, and sales order lines for all accounts with Shipping Agent Code = "RT 21" and consolidates them into a formatted Excel file stored in OneDrive/SharePoint.

## What This Does

- **Daily Schedule**: Runs automatically every morning at 6 AM UTC
- **Data Source**: Microsoft Dynamics 365 Business Central
- **Data Exported**: 
  - Invoices (with key fields like invoice number, customer, dates, amounts)
  - Invoice Lines (item details, quantities, unit prices)
  - Sales Orders (order information filtered by route)
  - Sales Order Lines (order item details)
- **Filter**: Only includes records with Shipping Agent Code = "RT 21"
- **Output Format**: Excel file with 2 sheets:
  - Sheet 1: Parent documents (Invoices + Sales Orders)
  - Sheet 2: Detail lines (Invoice Lines + Sales Order Lines)
- **Storage**: Saved to OneDrive/SharePoint with automatic daily updates

## Quick Start

1. **Review Setup Requirements**: See `CLAUDE.md` for credential setup
2. **Follow Setup Steps**: See `SETUP.md` for detailed import and configuration instructions
3. **Import the Workflow**: Use the workflow file at `workflows/business-central-excel-export.json`
4. **Configure Credentials**: Set up Business Central and Microsoft 365 OAuth2 credentials
5. **Test**: Run the workflow manually to verify it works
6. **Enable**: Activate the daily schedule

## Files

- `CLAUDE.md` - Credentials and integration configuration reference
- `SETUP.md` - Step-by-step setup and configuration guide
- `workflows/business-central-excel-export.json` - The n8n workflow export (import this into n8n)

## Technology Stack

- **Automation Platform**: n8n
- **Data Source**: Microsoft Dynamics 365 Business Central (OData API)
- **Cloud Storage**: Microsoft OneDrive/SharePoint
- **Output Format**: Excel (.xlsx)

## Key Features

✅ Automated daily execution at 6 AM UTC  
✅ Filters Business Central data by Shipping Agent Code = "RT 21"  
✅ Exports 4 related tables: Invoices, Invoice Lines, Sales Orders, Sales Order Lines  
✅ Creates clean, formatted Excel with proper column headers  
✅ Stores files in cloud (OneDrive) for easy access  
✅ Includes error handling with email notifications  
✅ Fully configurable schedule, filter, and output location  

## Support & Troubleshooting

For setup and configuration help, see `SETUP.md`.

For troubleshooting and credential configuration, see `CLAUDE.md`.

For n8n documentation, visit https://docs.n8n.io