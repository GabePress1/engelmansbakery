# Customer Invoice Workbook Export (n8n)

`customer-invoice-workbook-export.json` is an importable n8n workflow that returns every
Business Central sales invoice for a customer account, with item-level lines expanded,
as a single JSON payload. It exists so an invoice workbook can be produced for any
account without hand-querying BC.

## Flow

```
Webhook → Auth + Keys → Get BC Token → Fetch Invoices + Lines → Flatten → Respond to Webhook
```

| Node | What it does |
|---|---|
| **Webhook** | `GET /webhook/customer-invoice-export?customer=<account>` |
| **Auth + Keys** | Validates the `x-export-token` header, then emits the BC tenant/client/company IDs |
| **Get BC Token** | Client-credentials token from `login.microsoftonline.com` |
| **Fetch Invoices + Lines** | `salesInvoices` with `$expand=salesInvoiceLines`, paged via `@odata.nextLink` (up to 50 pages) |
| **Flatten** | Splits the response into invoice headers and item-level lines |
| **Respond to Webhook** | Returns `{ customer, invoiceCount, lineCount, invoices[], lines[] }` |

## Before importing

Two values are redacted in this file and must be filled in:

- `<<BC_CLIENT_SECRET>>` — the Business Central app registration secret, in the **Auth + Keys** node.
- `<<EXPORT_TOKEN>>` — a shared secret of your choosing, also in **Auth + Keys**. Callers must
  send it as the `x-export-token` header; requests without it fail with `unauthorized`.

## Usage

```bash
curl -G "https://engelmansbakery.app.n8n.cloud/webhook/customer-invoice-export" \
  -H "x-export-token: $EXPORT_TOKEN" \
  --data-urlencode "customer=10540-03"
```

The workflow must be **active** for the production webhook path to respond. Leave it
deactivated when not in use — the endpoint returns customer invoice history, so an active
webhook plus a leaked token exposes sales data.

## Notes

- Returns posted invoices (the `PS-INV` series), including any with status `Canceled`.
  Filter on the `status` field if cancelled documents should be excluded.
- `lines` contains only `lineType == "Item"` rows. Comment lines carry no quantity or
  amount, so excluding them does not change any total.
- No date filter is applied; the call returns the account's full invoice history.

## Credential handling

Other workflows on this instance hardcode the BC client secret in a `Keys` Set node. This
workflow follows that existing pattern so it behaves identically, which is why the secret
has to be stripped before the JSON can live in git. Moving these values into an n8n
credential — or at minimum rotating the secret, since it is in plaintext across several
workflows — would remove that hazard.
