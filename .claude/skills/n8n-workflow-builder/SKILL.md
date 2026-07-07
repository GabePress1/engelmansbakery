---
name: n8n-workflow-builder
description: Build import-ready n8n workflow JSON for Engelman's Bakery automations (Business Central syncs, HubSpot updates, Excel exports, scheduled emails). Use whenever creating or modifying a workflow JSON file, adding schedule triggers, or restructuring a workflow that processes large datasets.
---

# Building n8n Workflows for Engelman's Bakery

## Instance

- n8n Cloud instance: `https://engelmansbakery.app.n8n.cloud/`
- REST API base: `https://engelmansbakery.app.n8n.cloud/api/v1/`
- Auth header: `X-N8N-API-KEY: $N8N_API_KEY` (available in the session environment)

## Workflow JSON conventions

- Store workflow definitions in `workflows/*.json` (import-ready n8n format: top-level `name`, `nodes`, `connections`, `settings`).
- Keep the `id` field in the JSON once a workflow exists in n8n — deploy tooling uses `id` to decide create (POST) vs update (PUT).
- Give nodes descriptive names (`Get BC Token`, `Fetch Invoices`, `Loop Chunks`) — other workflows reference node output by name via `$('Node Name')`.
- Common node types used here: `scheduleTrigger`, `webhook` (as a "Run Now (Test)" manual trigger alongside the schedule), `httpRequest`, `code`, `splitInBatches`, `if`, `set`.

## Expression syntax — the `=` prefix

n8n parameter values starting with `=` are evaluated as expressions. Two hard-won rules:

1. A plain URL must NOT have a leading `=`. `"url": "=https://login.microsoftonline.com/..."` makes the parser hang for 10–17 minutes and crash the workflow (this auto-deactivated Phase 2 in production).
2. A dynamic URL MUST have the `=` prefix and be a valid JS expression, e.g. `"url": "={{ 'https://api.businesscentral...' + $json.filter }}"`.

## Scheduling

- Business schedules are Eastern Time. Set the workflow `settings.timezone` to `America/New_York` explicitly — do not rely on the instance default (UTC).
- Weekday-only runs: cron-style trigger with days `1-5`, e.g. weekdays at 8am EST for the BC→HubSpot sync.

## Large datasets: the parent + batch sub-workflow pattern

Workflows that loop over thousands of BC records (invoices, companies) accumulate static/run data and crash with OOM when built as one flat loop. The fix, applied to Phase 1 and Phase 2:

- Parent workflow: fetch the ID list, chunk it, and call an Execute Workflow node per chunk.
- Sub-workflow (`*-batch-processor*.json`): process one chunk and return only the summary, so memory is released between chunks.
- Never carry full record payloads through `splitInBatches` accumulation in a single workflow; also avoid stashing large arrays in workflow static data (caused "static data overflow" crashes).

## Testing and deployment

- Include a webhook "Run Now (Test)" trigger next to the schedule trigger so a workflow can be exercised without waiting for the schedule.
- Deploy via the API (see the `n8n-deploy-sync` skill) rather than pasting into the UI; commit the JSON to git first so there is a reviewable record.
