/*
 * original/add-webhooks.js
 * ------------------------
 * Webhook layer for the "Printing Letter_Invoices  Original" workflow. Same async
 * job pattern as the statements tool, but this workflow produces TWO PDFs (Billing
 * + Shipping), so the job store holds both and the download endpoint serves whichever
 * is requested (?file=billing|shipping).
 *
 *   POST /webhook/sw-letters-run       {jobId, minBalance, oldestInvoice, pad, secret}
 *   GET  /webhook/sw-letters-status?jobId=&secret=   -> {status, billing:{...}, shipping:{...}}
 *   GET  /webhook/sw-letters-download?jobId=&secret=&file=billing|shipping -> that PDF
 *
 * Finished PDFs live in workflow static data keyed by jobId; old jobs are pruned
 * after 30 minutes (each run cleans up stale ones). Secret injected at deploy time.
 */
const crypto = require("crypto");
const uuid = () => crypto.randomUUID();
const TTL_MS = 30 * 60 * 1000;

const MAKE_JOB = `
const b = ($json && $json.body) || {};
const SECRET = '__SECRET__';
if (String(b.secret || '') !== SECRET) { throw new Error('unauthorized'); }
const rawId = String(b.jobId || '').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64);
const jobId = rawId || (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
const minBalance = (b.minBalance === '' || b.minBalance == null) ? 0 : Number(b.minBalance);
const oldestInvoice = (b.oldestInvoice == null) ? '' : String(b.oldestInvoice).slice(0, 10);
const pad = (b.pad === false || b.pad === 'false' || b.pad === 0 || b.pad === '0') ? false : true;
const sd = $getWorkflowStaticData('global');
const now = Date.now();
for (const k of Object.keys(sd)) { if (k.indexOf('job_') === 0 && sd[k] && sd[k].at && now - sd[k].at > ${TTL_MS}) delete sd[k]; }
sd['job_' + jobId] = { status: 'running', at: now };
return [{ json: { jobId, minBalance, oldestInvoice, pad } }];
`.trim();

const STORE_RESULT = `
let jobId = null;
try { jobId = $('SW Make Job').first().json.jobId; } catch (e) {}
if (!jobId) { return $input.all(); } // manual run: nothing to store
const items = $input.all();
const sd = $getWorkflowStaticData('global');
const rec = { status: 'done', at: Date.now() };
for (let i = 0; i < items.length; i++) {
  const it = items[i];
  const type = (it.json && it.json.type) || ('file' + i);
  let buf = null;
  try { buf = await this.helpers.getBinaryDataBuffer(i, 'data'); } catch (e) {}
  if (buf) {
    rec[type] = {
      fileName: (it.json && it.json.fileName) || (type + '.pdf'),
      customers: (it.json && it.json.customers) || 0,
      size: buf.length, b64: buf.toString('base64'),
    };
  }
}
sd['job_' + jobId] = rec;
return items;
`.trim();

const STATUS_READ = `
const q = ($json && $json.query) || {};
const SECRET = '__SECRET__';
if (String(q.secret || '') !== SECRET) { return [{ json: { status: 'unauthorized' } }]; }
const jobId = String(q.jobId || '');
const sd = $getWorkflowStaticData('global');
const rec = sd['job_' + jobId];
if (!rec) { return [{ json: { status: 'unknown' } }]; }
const meta = (p) => p ? { fileName: p.fileName, customers: p.customers || 0, size: p.size || 0 } : null;
return [{ json: {
  status: rec.status,
  empty: !!rec.empty,
  billing: meta(rec.billing),
  shipping: meta(rec.shipping),
  customers: (rec.billing && rec.billing.customers) || rec.customers || 0,
} }];
`.trim();

const DOWNLOAD_READ = `
const q = ($json && $json.query) || {};
const SECRET = '__SECRET__';
const jobId = String(q.jobId || '');
const file = (String(q.file || 'billing') === 'shipping') ? 'shipping' : 'billing';
const sd = $getWorkflowStaticData('global');
const rec = sd['job_' + jobId];
const part = rec && rec[file];
if (String(q.secret || '') !== SECRET || !rec || rec.status !== 'done' || !part || !part.b64) {
  return [{ json: { error: 'not_ready' } }];
}
const buf = Buffer.from(part.b64, 'base64');
const fileName = part.fileName || (file + '.pdf');
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

  add(webhookNode("SW Run", "swl_run", "sw-letters-run", "POST", { responseMode: "onReceived" }, [-1000, 620]));
  add(codeNode("SW Make Job", "swl_makejob", sub(MAKE_JOB), [-800, 620]));
  add(codeNode("SW Store Result", "swl_store", sub(STORE_RESULT), [1100, 300]));
  add(webhookNode("SW Status", "swl_status", "sw-letters-status", "GET",
    { responseMode: "lastNode", responseData: "firstEntryJson" }, [-1000, 780]));
  add(codeNode("SW Status Read", "swl_statusread", sub(STATUS_READ), [-800, 780]));
  add(webhookNode("SW Download", "swl_download", "sw-letters-download", "GET",
    { responseMode: "lastNode", responseData: "firstEntryBinary", responseBinaryPropertyName: "data" }, [-1000, 940]));
  add(codeNode("SW Download Read", "swl_downloadread", sub(DOWNLOAD_READ), [-800, 940]));

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
