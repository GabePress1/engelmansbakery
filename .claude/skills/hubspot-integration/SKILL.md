---
name: hubspot-integration
description: Sync Business Central data into HubSpot (companies, custom properties, tickets) and work on HubSpot CMS modules. Use when creating/updating HubSpot companies keyed on ERP Account Number, adding analytics properties like first_invoice_date, wiring ticket/CAPA sync workflows, or editing the credit-request-form CMS module.
---

# HubSpot Integration Patterns

## Company sync (BC → HubSpot)

- **Join key is the ERP Account Number** custom company property, matching the BC customer number. Search HubSpot for the ERP Account Number first; update if found, create only if missing (dedup was a real problem — a `dedup_companies` cleanup workflow exists).
- Phase 1 syncs BC customers → HubSpot companies; Phase 2 writes invoice analytics onto those companies (e.g. `first_invoice_date`).

## Search API limits

- HubSpot CRM search caps page size — use `limit: 200` and paginate with the `after` cursor rather than adding Wait nodes between pages (the "Wait HS Pagination" node was removed as unnecessary).
- Batch property updates through the batch endpoints instead of per-record PATCH calls when touching hundreds of companies.

## Business rules encoded in previous phases

- `first_invoice_date` is only set from **won deals with posting date on/after 2026-01-01**, with re-onboarding detection (a returning customer gets a fresh first_invoice_date, not the historical one). Don't regress these rules when editing Phase 2.
- Ticket pipelines have guard workflows (`credit-given-guard`, `ticket-close-guard`, `capa-to-closed-sync-ticket`): stage transitions are synced/blocked by n8n, so ticket-stage changes should go through those workflows, not around them.

## CMS module: credit-request-form

- Source of truth lives in `src/modules/credit-request-form.module/` (fields.json, meta.json, module.html/css/js), with a mirrored copy under `hubspot/modules/credit-request-form/`.
- Keep both copies in sync when editing.
- Styling quirk: readonly fields get grayed by HubSpot defaults; the Complaint Type picker has an explicit white-background override — preserve it.
- The form posts to the n8n `credit-request-handler` webhook workflow; if fields change, update that workflow and the `docs/CREDIT_REQUEST_SOP.html` doc together.
