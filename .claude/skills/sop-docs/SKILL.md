---
name: sop-docs
description: Write standard operating procedure (SOP) documents for bakery business processes and their automations — customer-facing and developer-facing HTML docs under docs/. Use when a new workflow/phase ships, a process changes (credit requests, sales & customer service, invoice analytics), or someone asks to document how an automation works.
---

# Writing SOPs for Engelman's Bakery

Every shipped automation phase gets SOP documentation in `docs/` as self-contained HTML (viewable directly from the repo or shareable as a file — no external assets).

## Two audiences, two docs

Follow the established split (see `docs/phase1_customer_sop.html`, `docs/phase1_developer_sop.html`, `docs/phase2_customer_sop.html`, `docs/CREDIT_REQUEST_SOP.html`):

- **Customer/business SOP**: what the process is, who does what, step-by-step with the actual screens (HubSpot forms, ticket stages), what happens automatically vs. manually, and who to contact when something looks wrong. No API details.
- **Developer SOP**: which n8n workflows implement the process (workflow names + JSON paths in the repo), data flow (BC entities → transforms → HubSpot properties / Excel sheets), schedules and timezones, credentials used (by name, never values), and known failure modes with pointers to the `n8n-debugging` skill steps.

## Conventions

- Naming: `docs/phase{N}_{audience}_sop.html` for phased projects, `docs/{PROCESS}_SOP.html` for standalone processes.
- State business rules explicitly and precisely (e.g. "first_invoice_date is set only from won deals with posting date on/after 2026-01-01, with re-onboarding detection") — SOPs are where these rules are agreed on; workflows implement them.
- Include a change log section at the bottom (date, change, author) and update it on every revision.
- When a workflow changes behavior, update the SOP in the same branch/PR as the workflow change.
