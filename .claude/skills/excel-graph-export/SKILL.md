---
name: excel-graph-export
description: Write data to Excel workbooks in OneDrive/SharePoint via the Microsoft Graph workbook API — sessions, throttling, file locks, templates, tables, and pivot-style summary sheets. Use when building or fixing any BC-to-Excel export (e.g. the daily RT 21 orders/invoices export).
---

# Excel-on-Graph Export Patterns

## Setup

- Azure AD app with Graph permissions `Files.ReadWrite.All` and `Sites.ReadWrite.All` (client credentials).
- Base: `https://graph.microsoft.com/v1.0/drives/{driveId}/items/{itemId}/workbook/...`
- Keep `driveId` / folder ids / template item id in a single `Init` code node at the top of the workflow so paths are configured in one place.

## The template + working-file pattern (from RT 21 daily export)

Editing a workbook users have open fails with lock errors. Instead, each run:

1. Copy a committed template (`n8n/templates/*.xlsx`) to a new working file via Graph `copy`.
2. Write all data into the working file.
3. Delete the old published file and move/rename the working file into place.

Commit the `.xlsx` template to the repo; it defines sheets, headers, and formatting.

## Workbook sessions and throttling

- Always create a workbook session (`POST .../workbook/createSession`, persist `true`) and send `workbook-session-id` on every write; close it at the end. Sessions make writes atomic-ish and much faster.
- Graph throttles workbook writes hard. Chunk range writes (`Prepare Write Chunks` → `Loop Writes` with `splitInBatches`), and on `429`/`503`/`Locked` responses retry with backoff instead of failing the run.
- Write ranges with explicit addresses (`PATCH .../worksheets('{name}')/range(address='A2:H500')`) rather than row-by-row.

## Sheets and tables

- Before writing, ensure required sheets exist (`List Required Sheets` → `Add Sheet If Missing`); Graph errors on missing sheets rather than creating them.
- Convert written ranges to tables (`POST .../tables/add`) so users get filtering/sorting.
- Summary/pivot-style sheets (e.g. the RT21 "Combined" sheet with customer-name backfill and Requested_Delivery_Date) are computed in a code node and written as a plain range — Graph cannot create real PivotTables.

## Fallback

If Graph writing is disproportionate for the task, generating the file locally and uploading via a single `PUT .../content` also works (used for one-off exports like `Auto Dist.xlsx`).
