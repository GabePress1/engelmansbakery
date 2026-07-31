# HubSpot self-serve "Past Due Notice" generator

Two ways to put the generator on a **membership-gated** (staff-only) HubSpot page.
Both call the same n8n webhooks on the `Printing Statements` workflow (async
run → poll status → download the PDF).

## Option A — Custom module via the HubSpot CLI (recommended)

Files: [`past-due-generator.module/`](./past-due-generator.module/) — a proper
Design Manager module (renders natively in the page body, with an explanation of
the filters/process). The webhook URL and shared **secret** are module **fields**,
so the secret is entered in the page editor and never committed here.

### One-time CLI setup
```bash
npm install -g @hubspot/cli     # install the HubSpot CLI
hs init                         # paste a Personal Access Key for the Engelman's portal
```

### Upload / update the module
```bash
# from the repo root:
hs upload hubspot/past-due-generator.module past-due-generator.module
```
Re-run that command any time you edit the module files to push the update.

### Add it to a page
1. Content → **Website Pages** → open (or create) a **membership-gated** page.
2. In the editor, delete the leftover marketing modules from the body, then
   **Add modules → search "Past Due Generator"** → drag it into the section.
3. Click the module → set **Shared secret** (and confirm the **Webhook base URL**).
4. If you previously pasted the form into **Settings → Footer HTML**, remove it so
   it isn't duplicated.
5. **Settings → Control audience access → "Private – Registration required"** →
   add your staff → **Publish**.

## Option B — Footer HTML (no CLI)

[`self-serve-statements.html`](./self-serve-statements.html) — a single self-
contained block. Fill in `WEBHOOK_BASE` and `SECRET` at the top, paste the whole
thing into the page's **Settings → Advanced options → Footer HTML**, and publish.
Works, but renders at the bottom of the page.

## Notes
- The editor canvas does **not** run the JavaScript — test on **Preview** or the
  published page.
- Keep the tab open while generating; large runs take a few minutes.
- Don't run two generations at the exact same moment (the held PDFs share one n8n
  storage slot). Fine for occasional internal use.
- After publishing, restrict the n8n webhook CORS from `*` to the exact page
  domain for extra safety.
