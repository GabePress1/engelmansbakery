---
name: n8n-deploy-sync
description: Deploy workflow JSON files from this repo to the n8n instance (create vs update by id), and keep git and n8n in sync. Use when pushing a new/changed workflow live, importing a workflow from n8n into git, or setting up automated sync via GitHub Actions.
---

# Git ↔ n8n Sync

Git is the reviewable source of truth; the n8n instance is the runtime. Every workflow change should land in both.

## Deploying a workflow JSON

Decide create vs update from the `id` field in the JSON:

```bash
WORKFLOW_ID=$(jq -r '.id // empty' "$file")
if [ -z "$WORKFLOW_ID" ]; then
  curl -X POST "$N8N_URL/api/v1/workflows" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" -H "Content-Type: application/json" -d @"$file"
else
  curl -X PUT "$N8N_URL/api/v1/workflows/$WORKFLOW_ID" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" -H "Content-Type: application/json" -d @"$file"
fi
```

- After a POST creates a workflow, write the returned `id` back into the JSON file and commit, so future deploys update instead of duplicating.
- The workflows API rejects unknown top-level fields on PUT — send only `name`, `nodes`, `connections`, `settings` (strip `active`, `tags`, timestamps with `jq` if the file came from an export).
- Activation is separate: `POST $N8N_URL/api/v1/workflows/{id}/activate` (and `/deactivate`).

## Importing from n8n into git

`GET $N8N_URL/api/v1/workflows/{id}` → save to `workflows/<kebab-name>.json`. Do this after any UI-side edit so git doesn't drift (drift is how the Phase 2 `=`-prefix crash went unnoticed).

## Automated sync (GitHub Actions)

`.github/workflows/sync-to-n8n.yml` (on the `git-n8n-sync` branch) syncs `workflows/**.json` to n8n on push to main using repo secrets `N8N_URL` and `N8N_API_KEY`, with the same id-based create/update logic and per-file error counting. Reuse that action rather than writing a new one.

## Secrets hygiene

- Never commit `.mcp.json`, API tokens, or credential values — these repos gitignore `.mcp.json` and token files for a reason. Workflow JSONs reference n8n credentials by id/name only; actual secrets live in n8n's credential store or GitHub secrets.
