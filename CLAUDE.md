# Engelman's Bakery — Automation Repo

This repo holds all n8n workflows, HubSpot assets, and docs for Engelman's Bakery
automations. Claude Code reads this file automatically at the start of every
session — everything below is standing context so the user (Gabe,
gpress@engelmansbakery.com) never has to repeat it.

## Keys & credentials — READ THIS FIRST

**Never ask the user to paste keys, and never write secret values into any file
in this repo.** All secrets live in exactly two places:

1. **Claude environment variables** (persist across sessions, set in the Claude
   Code environment settings):
   - `N8N_API_KEY` — n8n REST API key for the instance below.
     If an n8n API call returns `401 unauthorized`, the key has expired: ask the
     user to create a fresh key in n8n (Settings → n8n API) and update the
     `N8N_API_KEY` environment variable in their Claude environment settings —
     do NOT ask them to paste it into chat or into a file.
2. **n8n credentials / the "Keys" node** inside workflows on the n8n instance —
   OAuth client secrets for Business Central, HubSpot, and Microsoft Graph are
   stored there, never in this repo.

Workflow JSON exported into this repo must keep secrets as placeholders
(e.g. `{{SECRET_ID}}`, `<REDACTED - set in n8n>`) — that is the existing
convention, keep it.

### n8n instance

- URL: `https://engelmansbakery.app.n8n.cloud/`
- REST API: `https://engelmansbakery.app.n8n.cloud/api/v1/`
- Auth header: `X-N8N-API-KEY: $N8N_API_KEY`
- Useful calls:
  ```bash
  # list workflows
  curl -H "X-N8N-API-KEY: $N8N_API_KEY" "https://engelmansbakery.app.n8n.cloud/api/v1/workflows?limit=100"
  # recent executions for a workflow
  curl -H "X-N8N-API-KEY: $N8N_API_KEY" "https://engelmansbakery.app.n8n.cloud/api/v1/executions?filter[workflowId]={ID}&limit=20"
  # full detail of one execution (error logs)
  curl -H "X-N8N-API-KEY: $N8N_API_KEY" "https://engelmansbakery.app.n8n.cloud/api/v1/executions/{EXECUTION_ID}"
  ```

### Business Central (Dynamics 365)

These are identifiers, not secrets — reuse them freely:

- **Tenant ID**: `bddeba87-9d41-4063-a0e3-be9e6afcd2ba`
- **OAuth Client ID** (app registration): `db88be9e-de13-4205-b0c1-472007c60c36`
  (client *secret* lives only in n8n)
- **Environment**: `Production`
- **Company (OData)**: `Live-EB`
- OData base:
  `https://api.businesscentral.dynamics.com/v2.0/bddeba87-9d41-4063-a0e3-be9e6afcd2ba/Production/ODataV4/Company('Live-EB')/`
- REST v2.0 base:
  `https://api.businesscentral.dynamics.com/v2.0/bddeba87-9d41-4063-a0e3-be9e6afcd2ba/production/api/v2.0/`
  (REST `companyId` GUID is stored in the workflows' "Keys" node)
- Token endpoint: Azure AD `client_credentials` grant, scope
  `https://api.businesscentral.dynamics.com/.default`
- Route 21 data is filtered by `Shipping_Agent_Code eq 'RT 21'`

### HubSpot

- Auth: private-app token stored in n8n credentials (never in this repo)
- Custom object **Credit Request**: object type ID `2-48651243`
- Public site: `engelmansbakery-8355567hs-sites.com` (HubSpot CMS)

### Microsoft 365 / OneDrive / SharePoint

- Graph API OAuth credentials stored in n8n; used to write Excel reports.

## Repo layout — folders by project

| Folder | Project |
|---|---|
| `route21-hubspot-sync/` | BC → HubSpot sync "Phases": Phase 1 companies, Phase 2 customer invoice analytics, Phase 3 payments, plus Route 21 company/item-pricing syncs. `archive/` holds superseded versions (v1.1–v1.4 etc.). |
| `route21-excel-reports/` | Daily BC → Excel (OneDrive/SharePoint) exports: RT21 orders & invoices daily report, YTD item-pricing report, plus templates and helper script. |
| `credit-requests/` | Credit request system: HubSpot CMS form module, n8n handler + CAPA/ticket sync workflows, customer SOP. |
| `archive/early-experiments/` | One-off/experimental workflows from May 2026. Don't build on these. |

Each project folder has its own README with details. Current/live workflow JSON
goes in the project's `workflows/`; superseded versions move to the project's
`archive/`.

## Working conventions for Claude sessions

- **Git**: `main` is the source of truth. Work on your session branch, then
  **merge to main via PR** (or tell the user the branch name and remind them to
  merge). Never leave finished work stranded on an orphan branch — that is how
  this repo got messy before the July 2026 cleanup.
- **Exporting workflows from n8n**: after changing a workflow in n8n, export
  the JSON into the matching project folder so git stays in sync with the
  instance. Strip/placeholder any secrets before committing.
- The n8n instance is the runtime source of truth for *activation state and
  credentials*; this repo is the source of truth for *workflow definitions,
  docs, and history*.
- Debugging write-ups go in the project's `docs/` folder, dated, e.g.
  `docs/2026-06-26_phase2-crash-findings.md`.

## Known history

- **June 2026**: "Phase 2 – Customer Invoice Analytics" crashed repeatedly
  (OOM at startup) and was auto-deactivated; fixed by splitting into a parent +
  batch sub-workflow. See `route21-hubspot-sync/docs/2026-06-26_*.md`.
- **July 2026**: repo consolidated from 17 orphan session branches into this
  per-project layout.
