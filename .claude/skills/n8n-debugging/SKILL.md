---
name: n8n-debugging
description: Diagnose and fix crashing, hanging, or auto-deactivated n8n workflows using the n8n REST API (executions, logs, workflow definitions). Use when a workflow failed, was deactivated after repeated crashes, runs suspiciously long, or produces wrong/missing data.
---

# Debugging n8n Workflows via the API

Workflow definitions and execution history live in the n8n instance, not in git. Debug through the REST API, then document findings and fixes in git.

## API access

```bash
N8N_URL=https://engelmansbakery.app.n8n.cloud
# All calls: -H "X-N8N-API-KEY: $N8N_API_KEY"  ($N8N_API_KEY is in the session env)
```

## Standard crash investigation

1. Find the workflow ID by name:
   `GET $N8N_URL/api/v1/workflows?filter[name]=Phase%202%20-%20Customer%20Invoice%20Analytics`
2. Pull recent executions to see the failure pattern:
   `GET $N8N_URL/api/v1/executions?filter[workflowId]={ID}&limit=20`
   Note when the last success was and whether crash durations cluster (seconds = immediate error; 10+ minutes = hang/timeout/OOM).
3. Inspect a failed execution in full:
   `GET $N8N_URL/api/v1/executions/{EXECUTION_ID}`
   Check `nodeExecutionStack`: if only the trigger node appears, the crash is at startup/parse time, not inside a node.
4. Fetch and read the workflow definition itself:
   `GET $N8N_URL/api/v1/workflows/{ID}` — many "engine" crashes are actually definition bugs.
5. Apply the fix via `PUT $N8N_URL/api/v1/workflows/{ID}`, then reactivate (`POST .../workflows/{ID}/activate` or via UI) and watch the next 2–3 executions.

## Known failure signatures in this instance

- **Hangs 10–17 min at the trigger, then crashes; only trigger in nodeExecutionStack** → a parameter with a stray leading `=` being parsed as a broken JS expression (e.g. `"url": "=https://login.microsoftonline.com/..."`). Remove the `=`.
- **OOM / crash partway through large loops** → flat workflow accumulating thousands of BC records. Restructure into parent + batch sub-workflow (see `n8n-workflow-builder` skill).
- **"Static data overflow"** → large arrays saved into workflow static data; store only cursors/IDs.
- **BC OData 400 errors** → filter syntax, most often quoting an `Edm.Date` value (see `business-central-api` skill).
- **Sudden onset after days of success** → diff the current workflow definition against the git copy; a manual UI edit likely introduced the break.

## After fixing

- Commit the corrected workflow JSON and a short findings doc (root cause, executions affected, fix, verification) to the repo.
- Reactivate the workflow and state its next scheduled run in the summary.
