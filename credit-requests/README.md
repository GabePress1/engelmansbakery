# Credit Request System

Customer credit request intake and processing: a HubSpot CMS form module on
`engelmansbakery.com/credit-request`, backed by n8n workflows that create and
manage HubSpot tickets and the **Credit Request** custom object
(object type ID `2-48651243`), including CAPA sync and guard rules.

## Workflows (`workflows/`)

| File | Role |
|---|---|
| `credit-request-handler.json` | Receives form submissions, creates the Credit Request object + ticket, associations, file uploads. |
| `credit-decision-capa-sync-ticket.json` | Syncs credit decision → CAPA / ticket stage. |
| `capa-to-closed-sync-ticket.json` | Moves ticket to closed when CAPA completes. |
| `item-stage-sync-ticket.json` | Keeps item stage and ticket stage in sync. |
| `credit-given-guard.json` | Guard: prevents invalid "credit given" transitions. |
| `ticket-close-guard.json` | Guard: prevents closing tickets prematurely. |
| `bc-items-proxy.json` | Proxy endpoint serving Business Central finished-goods items to the form. |

## HubSpot module (`hubspot-module/`)

The `credit-request-form` CMS module (HTML/CSS/JS + `fields.json`/`meta.json`)
deployed to the HubSpot site. See its README for deploy instructions.

## Docs

- `docs/CREDIT_REQUEST_SOP.html` — standard operating procedure
