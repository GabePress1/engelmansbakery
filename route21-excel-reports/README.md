# Route 21 — Business Central → Excel Reports

Daily n8n workflows that pull Business Central data and write Excel files to
OneDrive/SharePoint.

## Workflows (`workflows/`)

| File | Report |
|---|---|
| `rt21-bc-to-excel-daily.json` | RT21 orders & invoices daily export (Combined sheet incl. Requested_Delivery_Date and customer name backfill — latest, July 2026). |
| `route21-pricing-to-excel.json` | YTD item pricing + open sales orders report, refreshed daily at 6 AM. |
| `bc-to-excel-gabe.json` | BC → Excel export (Gabe's version). |
| `business-central-excel-export.json` | Generic BC invoices/orders → Excel export. |
| `business-central-hubspot-excel-export.json` | BC + HubSpot combined Excel export. |

## Supporting files

- `templates/` — Excel templates the workflows write into
  (`RT21_Orders_and_Invoices_template.xlsx`, `Route21_Pricing_Report.xlsx`)
- `data/` — reference data (`Auto Dist` files)
- `scripts/generate_excel_template.py` — regenerates the pricing report template
- `docs/SETUP-pricing-report.md`, `docs/SETUP-excel-export.md` — setup guides
