/*
 * add-webhooks.js
 * ---------------
 * Adds the "self-serve" webhook layer to the Printing Statements workflow so a
 * HubSpot page can run it and download the PDF, using an async job pattern:
 *
 *   POST  /webhook/sw-statements-run       {jobId, minBalance, oldestInvoice, secret}
 *         -> responds immediately, starts the run, stores the PDF under jobId
 *   GET   /webhook/sw-statements-status?jobId=&secret=   -> {status: running|done|...}
 *   GET   /webhook/sw-statements-download?jobId=&secret= -> the PDF (one time)
 *
 * The finished PDF is held in the workflow's static data keyed by jobId (the
 * "inside n8n" storage choice) and deleted on download. The two Code nodes that
 * read settings prefer the per-run override ("SW Make Job") and fall back to the
 * manual Settings node, so the manual Execute button is unaffected.
 *
 * This module EXPORTS addWebhookLayer(workflow, secret) so a deploy script can
 * apply it to a live workflow JSON. Secret is injected at deploy time (never
 * committed).
 */
const crypto = require("crypto");
const uuid = () => crypto.randomUUID();

// --- Code-node sources (SECRET is substituted at deploy) --------------------
const MAKE_JOB = `
const b = ($json && $json.body) || {};
const SECRET = '__SECRET__';
if (String(b.secret || '') !== SECRET) { throw new Error('unauthorized'); }
const rawId = String(b.jobId || '').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64);
const jobId = rawId || (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
const minBalance = (b.minBalance === '' || b.minBalance == null) ? 0 : Number(b.minBalance);
const oldestInvoice = (b.oldestInvoice == null) ? '' : String(b.oldestInvoice).slice(0, 10);
const sd = $getWorkflowStaticData('global');
sd['job_' + jobId] = { status: 'running', at: Date.now() };
return [{ json: { jobId, minBalance, oldestInvoice } }];
`.trim();

const STORE_RESULT = `
let jobId = null;
try { jobId = $('SW Make Job').first().json.jobId; } catch (e) {}
if (!jobId) { return $input.all(); } // manual run: nothing to store
const item = $input.first();
let buf = null;
try { buf = await this.helpers.getBinaryDataBuffer(0, 'data'); } catch (e) {}
const sd = $getWorkflowStaticData('global');
if (buf) {
  sd['job_' + jobId] = {
    status: 'done', at: Date.now(),
    fileName: (item.json && item.json.fileName) || 'Past-Due-Notice.pdf',
    customers: (item.json && item.json.customers) || 0,
    size: buf.length, b64: buf.toString('base64'),
  };
} else {
  sd['job_' + jobId] = { status: 'error', at: Date.now(), message: 'no PDF produced' };
}
return $input.all();
`.trim();

const STATUS_READ = `
const q = ($json && $json.query) || {};
const SECRET = '__SECRET__';
if (String(q.secret || '') !== SECRET) { return [{ json: { status: 'unauthorized' } }]; }
const jobId = String(q.jobId || '');
const sd = $getWorkflowStaticData('global');
const rec = sd['job_' + jobId];
if (!rec) { return [{ json: { status: 'unknown' } }]; }
return [{ json: {
  status: rec.status,
  fileName: rec.fileName || null,
  customers: rec.customers || 0,
  size: rec.size || null,
  message: rec.message || null,
} }];
`.trim();

const DOWNLOAD_READ = `
const q = ($json && $json.query) || {};
const SECRET = '__SECRET__';
const jobId = String(q.jobId || '');
const sd = $getWorkflowStaticData('global');
const rec = sd['job_' + jobId];
if (String(q.secret || '') !== SECRET || !rec || rec.status !== 'done' || !rec.b64) {
  return [{ json: { error: 'not_ready' } }];
}
const buf = Buffer.from(rec.b64, 'base64');
const fileName = rec.fileName || 'Past-Due-Notice.pdf';
delete sd['job_' + jobId]; // one-time download frees the memory
const bin = await this.helpers.prepareBinaryData(buf, fileName, 'application/pdf');
return [{ json: { ok: true }, binary: { data: bin } }];
`.trim();

const codeNode = (name, id, code, pos) => ({
  parameters: { jsCode: code },
  id, name, type: "n8n-nodes-base.code", typeVersion: 2, position: pos,
});
const webhookNode = (name, id, path, method, extraParams, pos) => ({
  parameters: { httpMethod: method, path, options: { allowedOrigins: "*" }, ...extraParams },
  id, name, type: "n8n-nodes-base.webhook", typeVersion: 2, position: pos,
  webhookId: uuid(),
});

function addWebhookLayer(wf, secret) {
  const sub = (s) => s.split("__SECRET__").join(secret);
  const names = new Set(wf.nodes.map((n) => n.name));
  const add = (node) => { if (!names.has(node.name)) { wf.nodes.push(node); names.add(node.name); } };

  add(webhookNode("SW Run", "sw_run", "sw-statements-run", "POST",
    { responseMode: "onReceived" }, [-1000, 620]));
  add(codeNode("SW Make Job", "sw_makejob", sub(MAKE_JOB), [-800, 620]));
  add(codeNode("SW Store Result", "sw_store", sub(STORE_RESULT), [900, 300]));
  add(webhookNode("SW Status", "sw_status", "sw-statements-status", "GET",
    { responseMode: "lastNode", responseData: "firstEntryJson" }, [-1000, 780]));
  add(codeNode("SW Status Read", "sw_statusread", sub(STATUS_READ), [-800, 780]));
  add(webhookNode("SW Download", "sw_download", "sw-statements-download", "GET",
    { responseMode: "lastNode", responseData: "firstEntryBinary", responseBinaryPropertyName: "data" }, [-1000, 940]));
  add(codeNode("SW Download Read", "sw_downloadread", sub(DOWNLOAD_READ), [-800, 940]));

  const c = wf.connections;
  const link = (from, to) => { c[from] = { main: [[{ node: to, type: "main", index: 0 }]] }; };
  link("SW Run", "SW Make Job");
  link("SW Make Job", "Settings"); // webhook path joins the pipeline at Settings
  link("Render & Merge PDFs", "SW Store Result");
  link("SW Status", "SW Status Read");
  link("SW Download", "SW Download Read");
  return wf;
}

module.exports = { addWebhookLayer };
