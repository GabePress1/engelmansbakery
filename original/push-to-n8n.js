/*
 * original/push-to-n8n.js
 * -----------------------
 * Deploys the generated renderer into the LIVE n8n workflow, so a change to
 * pure-pdf.js actually reaches production.
 *
 * Why this exists: build-workflow.js produces a workflow JSON, but nothing ever
 * delivered it. The live workflow carried its own inlined snapshot of
 * pure-pdf.js, updated only by pasting into the Code node by hand — and that
 * paste can fail silently. It did, twice: the code was never saved to n8n at
 * all, and two runs of wrong mail went out before an API check caught it.
 *
 *   N8N_API_KEY=... node original/push-to-n8n.js [letters|statements] [--dry-run]
 *   npm run push:letters
 *
 * IT REPLACES EXACTLY ONE FIELD: nodes["Render & Merge PDFs"].parameters.jsCode.
 * Never push the whole generated workflow — the live one has ~21 nodes (the
 * generated pipeline PLUS the SW webhook layer and real Business Central
 * credentials, neither of which the generated JSON contains). Pushing it
 * wholesale would delete the webhooks and the credential links and take the
 * HubSpot page down. Every other node is read, preserved and written back as-is.
 *
 * Env:
 *   N8N_API_KEY      required. Settings -> n8n API -> create an API key.
 *                    Env only, never a CLI arg, so it stays out of shell history.
 *   N8N_BASE_URL     default https://engelmansbakery.app.n8n.cloud
 *   N8N_WORKFLOW_ID  overrides the target's id (the signature check still applies)
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const RENDER_NODE = "Render & Merge PDFs";
const BASE = (process.env.N8N_BASE_URL || "https://engelmansbakery.app.n8n.cloud").replace(/\/+$/, "");

// The repo and n8n names are crossed over — the local file called
// "Printing_Letter_Invoices" builds the workflow n8n calls "Printing
// Statements", and the mailing workflow is named "Printing Letter_Invoices" in
// n8n despite being built from original/. Mixing them up is how the wrong
// workflow got edited in the first place, so each target carries a signature:
// a set of node names the live workflow must have, checked before any write.
const TARGETS = {
  letters: {
    label: "mailing (letter + address + statement, HubSpot 'Letters & Statements')",
    local: "original/Printing_Letter_Invoices_Original.workflow.json",
    workflowId: "Fn9PTTNOT2rSFwag", // n8n name: "Printing Letter_Invoices"
    mustHave: ["Get Ship-to Addresses", "SW Run", RENDER_NODE],
    mustNotHave: [],
  },
  statements: {
    label: "delivery (statements only, HubSpot 'Past-Due Notices')",
    local: "n8n/Printing_Letter_Invoices.workflow.json",
    workflowId: "JGRZcOulnHodMoFE", // n8n name: "Printing Statements"
    mustHave: ["SW Run", RENDER_NODE],
    mustNotHave: ["Get Ship-to Addresses"],
  },
};

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const name = args.find((a) => !a.startsWith("-")) || "letters";
const target = TARGETS[name];
if (!target) {
  console.error(`unknown target ${JSON.stringify(name)} — expected one of: ${Object.keys(TARGETS).join(", ")}`);
  process.exit(2);
}

const KEY = process.env.N8N_API_KEY;
if (!KEY) {
  console.error(
    "N8N_API_KEY is not set. Create one in n8n under Settings -> n8n API, then:\n" +
    `  N8N_API_KEY=... node original/push-to-n8n.js ${name}\n` +
    "Pass it via the environment, never as an argument — arguments land in shell history and ps."
  );
  process.exit(2);
}

async function api(method, p, body) {
  const res = await fetch(`${BASE}/api/v1${p}`, {
    method,
    headers: { "X-N8N-API-KEY": KEY, accept: "application/json", "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${p} -> ${res.status}: ${text.slice(0, 400)}`);
  return text ? JSON.parse(text) : null;
}

// The single render node, or a hard failure. The live canvas carries orphaned
// duplicates from past hand-merges; an ambiguous match is how an edit goes to
// the wrong copy, so refuse rather than guess.
function renderNodeOf(nodes, where) {
  const hits = (nodes || []).filter((n) => n.name === RENDER_NODE);
  if (hits.length !== 1) {
    throw new Error(`expected exactly one ${JSON.stringify(RENDER_NODE)} node in ${where}, found ${hits.length}`);
  }
  const code = hits[0].parameters && hits[0].parameters.jsCode;
  if (!code) throw new Error(`${RENDER_NODE} in ${where} has no jsCode`);
  return { node: hits[0], code };
}

async function main() {
  console.log(`target      ${name} — ${target.label}`);
  console.log(`host        ${BASE}`);

  const localPath = path.join(ROOT, target.local);
  if (!fs.existsSync(localPath)) {
    throw new Error(`generated workflow missing: ${target.local}\nRun the matching build-workflow.js first.`);
  }
  const local = renderNodeOf(JSON.parse(fs.readFileSync(localPath, "utf8")).nodes, target.local).code;

  const id = process.env.N8N_WORKFLOW_ID || target.workflowId;
  const live = await api("GET", `/workflows/${id}`);
  console.log(`workflow    ${id} ${JSON.stringify(live.name)}  active=${live.active}  nodes=${live.nodes.length}`);

  // Signature check — never write into a workflow that isn't the one we mean.
  const names = new Set(live.nodes.map((n) => n.name));
  const missing = target.mustHave.filter((n) => !names.has(n));
  const forbidden = target.mustNotHave.filter((n) => names.has(n));
  if (missing.length || forbidden.length) {
    throw new Error(
      `workflow ${id} does not match the "${name}" signature — refusing to write.\n` +
      (missing.length ? `  missing nodes:   ${missing.join(", ")}\n` : "") +
      (forbidden.length ? `  unexpected nodes: ${forbidden.join(", ")}\n` : "") +
      "  Check the id, or the target table at the top of this script."
    );
  }

  const current = renderNodeOf(live.nodes, `workflow ${id}`);
  console.log(`render node  live ${current.code.length} bytes -> local ${local.length} bytes`);

  if (current.code === local) {
    console.log("already up to date — nothing to push.");
    return;
  }
  if (dryRun) {
    console.log("--dry-run: would replace the render node's jsCode. Nothing written.");
    return;
  }

  // Back up the live workflow (draft AND activeVersion) before touching it.
  const outDir = path.join(ROOT, "out");
  fs.mkdirSync(outDir, { recursive: true });
  const stamp = String(live.updatedAt || "").replace(/[:-]/g, "").slice(0, 15) || "now";
  const backup = path.join(outDir, `n8n-backup-${id}-${stamp}.json`);
  fs.writeFileSync(backup, JSON.stringify(live, null, 2));
  console.log(`backup      ${path.relative(ROOT, backup)}`);

  current.node.parameters.jsCode = local;
  // Only the four writable keys; the API rejects id/createdAt/active/tags/etc.
  const { name: wfName, nodes, connections, settings } = live;
  await api("PUT", `/workflows/${id}`, { name: wfName, nodes, connections, settings });
  console.log("PUT         200 OK");

  // This n8n uses a draft/published version model. A PUT that lands in the draft
  // and leaves the published version stale is a silent no-op in production —
  // the exact failure this script exists to prevent — so verify, don't assume.
  const after = await api("GET", `/workflows/${id}`);
  const draft = renderNodeOf(after.nodes, "draft").code;
  const published = renderNodeOf((after.activeVersion || {}).nodes || after.nodes, "activeVersion").code;
  const ok = draft === local && published === local;
  console.log(`verify      draft=${draft === local}  published=${published === local}  ` +
              `versionId${after.versionId === after.activeVersionId ? " ==" : " !="}activeVersionId`);
  if (!ok) {
    throw new Error("the live workflow did not end up with the new code — publish it in the n8n UI and re-check.");
  }
  console.log("deployed.");
}

main().catch((e) => { console.error("\n" + e.message); process.exit(1); });
