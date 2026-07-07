---
name: business-central-api
description: Query Microsoft Dynamics 365 Business Central (ERP) via OData — auth, endpoints, filter syntax, and known gotchas. Use when fetching customers, invoices, orders, line items, or item pricing from BC, or when a BC HTTP request in a workflow returns 400/401 errors.
---

# Business Central API Patterns

## Auth (OAuth2 client credentials)

Token request — plain POST to:
`https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token`
with `grant_type=client_credentials`, `scope=https://api.businesscentral.dynamics.com/.default`, client ID + secret. Tenant for this org: `bddeba87-9d41-4063-a0e3-be9e6afcd2ba`.

In n8n, the token URL must not carry a leading `=` unless it is a real expression (a stray `=` here crashed Phase 2 in production).

## Endpoints

ODataV4 (company-scoped, used by all existing workflows):
```
https://api.businesscentral.dynamics.com/v2.0/{TENANT_ID}/Production/ODataV4/Company('{COMPANY}')/{Entity}
```
Entities used previously: customers, sales orders, sales invoices, order/invoice line items, item pricing. Match the exact entity/field names already used in `workflows/*.json` and the RT21 workflow — they were verified against the live tenant.

## OData filter gotchas (each of these caused a production fix)

- **`Edm.Date` values take NO quotes**: `postingDate ge 2026-01-01` ✅ — `postingDate ge '2026-01-01'` ❌ returns 400.
- Strings DO take single quotes: `Shipping_Agent_Code eq 'RT 21'`.
- URL-encode the whole `$filter` when building URLs in code nodes (`encodeURIComponent`).
- Large `IN`-style lookups: batch document numbers into chunked `or` filters and loop the chunks (see `Fetch Lines Chunk` in the RT21 workflow) — one giant filter string hits URL length limits.

## Volume and paging

- Use `$select` to fetch only needed fields; unselected wide entities are a main cause of workflow OOM.
- Respect `@odata.nextLink` for paging; don't assume one page.
- Process results with the parent + batch sub-workflow pattern for anything beyond a few hundred records.
