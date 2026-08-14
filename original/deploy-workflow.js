/*
 * original/deploy-workflow.js
 * --------------------------
 * Produces the DEPLOYABLE "Printing Letter_Invoices  Original" workflow — the one
 * the HubSpot "Letters & Statements (for Mailing)" page actually calls.
 *
 * build-workflow.js writes only the BASE workflow (manual trigger, no webhooks).
 * The HubSpot page talks to /webhook/sw-letters-run|status|download, which exist
 * only once addWebhookLayer() from add-webhooks.js has been applied. Nothing used
 * to call it, so regenerating the base JSON updated the repo and never n8n — the
 * live workflow kept running whatever copy of pure-pdf.js was inlined the day it
 * was assembled. This script closes that gap.
 *
 *   node original/deploy-workflow.js        (or: npm run deploy:letters)
 *
 * Set N8N_WEBHOOK_SECRET to bake the shared secret in; otherwise the __SECRET__
 * placeholder is left in place and you fill it in n8n. Output goes to out/, which
 * is gitignored — the workflow JSON can contain the real secret, so it must never
 * be committed.
 *
 * Two artifacts, because there are two ways to deploy:
 *
 *   out/render-node.js  — the "Render & Merge PDFs" Code-node body on its own.
 *     PREFERRED: paste it over that node in the live workflow. Surgical, so the
 *     Business Central credentials, the registered webhook paths and the active
 *     state all survive. It is also the only node that changes when the renderer
 *     changes — transform.js drives a different node and is usually untouched.
 *
 *   out/Printing_Letter_Invoices_Original.webhook.workflow.json — the whole
 *     workflow. Use for a first-time deploy, or import INTO the existing workflow
 *     so it keeps its id. Importing it as a NEW workflow will contend with the
 *     live one for the same sw-letters-* paths and lose the credential links.
 */
const fs = require("fs");
const path = require("path");
const { addWebhookLayer } = require("./add-webhooks");

const ROOT = path.join(__dirname, "..");
const BASE = path.join(__dirname, "Printing_Letter_Invoices_Original.workflow.json");
const OUT_DIR = path.join(ROOT, "out");
const RENDER_NODE = "Render & Merge PDFs";

const secret = process.env.N8N_WEBHOOK_SECRET || "";
if (!secret) {
  console.warn(
    "!! N8N_WEBHOOK_SECRET is not set — leaving the __SECRET__ placeholder in the\n" +
    "!! workflow JSON. Replace it in n8n, or re-run with the env var set. The\n" +
    "!! render-node.js output carries no secret either way."
  );
}

if (!fs.existsSync(BASE)) {
  throw new Error("base workflow missing — run `node original/build-workflow.js` first: " + BASE);
}
const wf = addWebhookLayer(JSON.parse(fs.readFileSync(BASE, "utf8")), secret || "__SECRET__");

const render = wf.nodes.find((n) => n.name === RENDER_NODE);
if (!render || !render.parameters || !render.parameters.jsCode) {
  throw new Error(`"${RENDER_NODE}" node or its jsCode is missing from the base workflow`);
}

fs.mkdirSync(OUT_DIR, { recursive: true });
const wfPath = path.join(OUT_DIR, "Printing_Letter_Invoices_Original.webhook.workflow.json");
const nodePath = path.join(OUT_DIR, "render-node.js");
fs.writeFileSync(wfPath, JSON.stringify(wf, null, 2));
fs.writeFileSync(nodePath, render.parameters.jsCode);

const added = wf.nodes.filter((n) => n.name.startsWith("SW ")).map((n) => n.name);
console.log(`Wrote ${path.relative(ROOT, wfPath)}  (${wf.nodes.length} nodes, webhook layer: ${added.join(", ")})`);
console.log(`Wrote ${path.relative(ROOT, nodePath)}  (${render.parameters.jsCode.length} bytes)`);
console.log(`
To update the live workflow:
  n8n -> "Printing Letter_Invoices  Original" -> open the "${RENDER_NODE}" node
      -> select all in the JS panel, paste out/render-node.js over it -> Save.
Then re-run from the HubSpot page. On the address page the block should sit at the
top-left and the city line should read "Atlanta, GA 30303" — a state can only
appear under the new code.
`);
