#!/usr/bin/env node
// Exercises the Pick Recipient Email Code node against the cases that matter:
// AP contact present, only non-AP contacts, no contact emails, no contacts, nothing at all.
// Usage: node tools/test_recipient_pick.mjs
import { readFile } from 'node:fs/promises';
const wf = JSON.parse(await readFile(new URL('../workflows/emailing-letter-statement-draft.json', import.meta.url),'utf8'));
const code = wf.nodes.find(n => n.name === 'Pick Recipient Email').parameters.jsCode;

const run = (contacts, account) => new Function('$input','$',`return (function(){${code}})()`)(
  { item: { json: { value: contacts } } },
  (name) => ({ item: { json: account } }),
);

const cases = [
  ['AP contact present',      [{number:'CT1',displayName:'Jane Doe',email:'jane@x.com'},
                               {number:'CT2',displayName:'ATTN: Accts Payable',email:'ap@x.com'}], {accountNumber:'13287',recipientEmail:'cust@x.com'}],
  ['no AP, first with email', [{number:'CT1',displayName:'Jane Doe',email:''},
                               {number:'CT2',displayName:'Bob',email:'bob@x.com'}], {accountNumber:'13060',recipientEmail:'cust@x.com'}],
  ['no contact emails',       [{number:'CT1',displayName:'Jane Doe',email:''}], {accountNumber:'13061',recipientEmail:'cust@x.com'}],
  ['no contacts at all',      [], {accountNumber:'13161',recipientEmail:'cust@x.com'}],
  ['nothing anywhere',        [], {accountNumber:'12308',recipientEmail:''}],
  ['accounts payable wording',[{number:'CT9',displayName:'Accounts Payable Dept',email:'ap2@x.com'},
                               {number:'CT8',displayName:'Aaron',email:'aaron@x.com'}], {accountNumber:'12723',recipientEmail:''}],
];
for (const [label, contacts, account] of cases) {
  const r = run(contacts, account).json;
  console.log(`  ${label.padEnd(26)} -> ${(r.recipientEmail||'(none)').padEnd(12)} source=${r.recipientSource.padEnd(9)} contact=${r.contactName||'-'}`);
}
