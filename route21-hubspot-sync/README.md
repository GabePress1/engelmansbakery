# Route 21 — Business Central → HubSpot Sync

Syncs Route 21 (Shipping Agent Code `RT 21`) data from Business Central into
HubSpot, in phases.

## Current workflows (`workflows/`)

| File | Phase | Notes |
|---|---|---|
| `phase1-bc-to-hubspot-companies.json` | Phase 1 — Companies | Parent workflow; restructured July 2026 into parent + batch sub-workflow to fix out-of-memory crashes. |
| `phase1-batch-processor-sub.json` | Phase 1 — Companies | Batch sub-workflow called by the parent. |
| `phase2-customer-invoice-analytics.json` | Phase 2 — Invoice analytics | Parent; refactored June 2026 to use a sub-workflow for batching after repeated OOM crashes (see `docs/2026-06-26_*`). |
| `phase2-batch-processor.json` | Phase 2 — Invoice analytics | Batch sub-workflow. |
| `phase3-payments.json` | Phase 3 — Payments | |
| `route21-companies.json` | Company sync | |
| `route21-item-pricing.json` | Item pricing sync | |
| `dedup-companies.json` | Utility | HubSpot company de-duplication. |

## Docs (`docs/`)

- `SETUP.md` — setup guide for the phase workflows
- `phase1_customer_sop.html`, `phase1_developer_sop.html`, `phase2_customer_sop.html` — SOPs
- `2026-06-26_phase2-*.md` — Phase 2 crash investigation, fix, and reactivation record

## Archive (`archive/`)

Superseded Phase 1 versions (v1.1–v1.4, select/subset/final variants) and older
Phase 2 monolithic versions. Kept for history — don't import these into n8n.
