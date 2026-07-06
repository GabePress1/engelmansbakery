# Credit Request Form — HubSpot Custom Module

Front-end credit/complaint request form embedded on engelmansbakery.com. Submits
a multipart payload (JSON + photo files) to the n8n `credit-request` webhook,
which creates the HubSpot Ticket + associated Item records.

## Files
- `module.html` — static form shell (contact, account, notes, submit). Product
  lines are rendered dynamically by `module.js`.
- `module.css` — styles, including the custom two-column Complaint Type picker.
- `module.js` — product-line management, validation, payload build, submission.

## Module fields (set in HubSpot)
- `webhook_url` — n8n credit-request webhook URL
- `items_endpoint_url` — endpoint returning BC items (`{ number, displayName }`)
- `form_title`, `success_message`, `error_message`

## Notes
- **Complaint Type** is a custom click-to-open picker showing all classifications
  in two columns (see `buildClassificationOptions` / `.cr-select__panel`). The
  input keeps the `cr-product-classification` class so validation is unchanged.
- Photo uploads are required for certain classifications
  (`PHOTO_REQUIRED_CLASSIFICATIONS`).
- File fields are named `photo_line{n}_file{n}` to match the n8n handler's
  `^photo_line(\d+)_file(\d+)$` parsing.

The backend that consumes this form lives in `n8n/workflows/credit-request-handler.json`.
