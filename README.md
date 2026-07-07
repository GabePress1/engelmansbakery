# Engelman's Bakery — Automations

n8n workflows, HubSpot assets, and documentation for Engelman's Bakery business
automations (Business Central ↔ HubSpot ↔ Excel/OneDrive).

## Projects

| Folder | What it does |
|---|---|
| [`route21-hubspot-sync/`](route21-hubspot-sync/) | Syncs Business Central Route 21 data into HubSpot: Phase 1 (companies), Phase 2 (customer invoice analytics), Phase 3 (payments). |
| [`route21-excel-reports/`](route21-excel-reports/) | Daily Excel reports from Business Central to OneDrive/SharePoint: RT21 orders & invoices, YTD item pricing. |
| [`credit-requests/`](credit-requests/) | Customer credit request system: HubSpot form module + n8n workflows for tickets, CAPA sync, and guards. |
| [`archive/early-experiments/`](archive/early-experiments/) | Early one-off experiments (May 2026), kept for reference only. |

## Where things run

- Workflows run on n8n Cloud: `https://engelmansbakery.app.n8n.cloud/`
- This repo stores the exported workflow definitions, docs, and history.
- **No secrets in this repo** — API keys and OAuth secrets live in n8n
  credentials and in the Claude Code environment settings. See `CLAUDE.md`.
