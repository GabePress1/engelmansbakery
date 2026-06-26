# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository is used to track and debug n8n workflows for Engelman's Bakery. The actual workflow definitions and execution history are stored in the n8n instance (not in git). This repo serves as a space for debugging, documenting issues, and tracking fixes.

## n8n Configuration

**N8N Instance**: https://engelmansbakery.app.n8n.cloud/

**API Access**:
- The N8N_API_KEY is available in the session environment
- Use it to access the n8n REST API at `https://engelmansbakery.app.n8n.cloud/api/v1/`
- Authentication: Add the header `X-N8N-API-KEY: {N8N_API_KEY}`

**User Email**: gpress@engelmansbakery.com (used in n8n notifications)

## Common Debugging Tasks

### Investigating Workflow Crashes

When a workflow is auto-deactivated due to repeated crashes:

1. **Get the workflow ID**: Use the workflow name to find its ID via the API
   ```bash
   curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
     "$N8N_URL/api/v1/workflows?filter[name]=Phase%202%20-%20Customer%20Invoice%20Analytics"
   ```

2. **Check recent executions**: Get the last 10-20 executions to see error patterns
   ```bash
   curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
     "$N8N_URL/api/v1/executions?filter[workflowId]={WORKFLOW_ID}&limit=20"
   ```

3. **Inspect execution details**: Get full logs/errors from a specific failed execution
   ```bash
   curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
     "$N8N_URL/api/v1/executions/{EXECUTION_ID}"
   ```

4. **After fixing**: Document the root cause and solution in a git commit, then reactivate the workflow in the n8n UI

### Key Workflows to Monitor

- **Phase 2 – Customer Invoice Analytics**: Processes customer invoices and generates analytics

## Development Workflow

1. When assigned to a debugging task, you'll be on a branch like `claude/workflow-crash-debug-{id}`
2. Investigate the n8n execution logs to identify the issue
3. Document findings and any fixes in commits on that branch
4. Push to the branch when complete

## Important Notes

- N8N workflows are defined in the n8n UI, not in this git repo
- Error logs come from n8n's execution history, accessible via the API
- Always ask the user for the n8n instance URL if not provided in the session context
