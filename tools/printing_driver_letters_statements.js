// --- n8n driver -------------------------------------------------------------
// Two combined PDFs, split by DOCUMENT TYPE rather than by address:
//   Past-Due-Letters-<date>.pdf     every letter + address page, in customer order
//   Past-Due-Statements-<date>.pdf  every statement, in the SAME customer order
//
// The two files are collated against each other: sheet N of the letters belongs with
// sheet N of the statements. That only holds if both carry exactly the same packets in
// exactly the same order, so inclusion is decided ONCE, up front, and both files are
// built from that single list. A customer pulled from one is pulled from both.
const all = items.map((i) => i.json);
// Defensive: only render records that actually carry tokens, so one malformed or
// stale item can never crash the whole batch. 'skipped' surfaces any bad input.
const records = all.filter((r) => r && r.tokens);
const skipped = all.length - records.length;

// Double-sided padding on by default; the page can turn it off (pad:false) for a
// compact, screen/one-sided copy with no blank filler pages.
let pad = true;
try { const ovj = $('SW Make Job').first().json; if (ovj && ovj.pad === false) pad = false; } catch (e) {}
const o = { pad };

// 'excluded' collects customers pulled from the machine run: an undeliverable
// address (no street, or no ZIP and no city/state), or a statement that won't
// condense onto one sheet. They are left out of BOTH files so the collation stays
// aligned, and come back on the item so the operator knows who to chase by hand.
const excluded = [];
const sets = [];
let packets = 0;

for (const r of records) {
  // Billing, plus shipping only when it genuinely differs — the same rule the
  // billing/shipping split used to decide who needed a second envelope.
  const variants = [r.tokens];
  if (r.shipTokens && !sameAddress(r.tokens, r.shipTokens)) variants.push(r.shipTokens);

  const letter = [];
  const statement = [];
  let ok = true;

  for (const tok of variants) {
    const bad = addressProblem(tok);
    if (bad) {
      excluded.push({ name: clean(tok.Description), reason: bad });
      ok = false;
      break;
    }

    const lp = letterPages(tok);
    if (pad && lp.length % 2 === 1) lp.push(""); // pad the letter to a full sheet

    const s = r.statement && r.statement.lines ? r.statement : { lines: [], total: 0 };
    let sp;
    if (pad) {
      const fit = fitStatementPages(tok, s, o, STATEMENT_MAX_PAGES);
      if (!fit) {
        excluded.push({ name: clean(tok.Description), reason: "statement exceeds one sheet" });
        ok = false;
        break;
      }
      sp = fit.pages.slice();
      while (sp.length < STATEMENT_MAX_PAGES) sp.push(""); // fill out the sheet
    } else {
      sp = statementPages(tok, s, o);
    }

    letter.push(...lp);
    statement.push(...sp);
  }

  if (ok) {
    sets.push({ letter, statement });
    packets += variants.length;
  }
}

const letterContents = [];
const statementContents = [];
for (const set of sets) {
  letterContents.push(...set.letter);
  statementContents.push(...set.statement);
}

// Last line of defence. The two files are collated by position, so a length that does
// not divide evenly means some packet's letter would be paired with another packet's
// statement — fail the run rather than print mail that goes to the wrong people.
if (pad && (letterContents.length !== packets * LETTER_PAGES ||
            statementContents.length !== packets * STATEMENT_MAX_PAGES)) {
  throw new Error(
    `set-length invariant violated: ${letterContents.length} letter pages and ` +
      `${statementContents.length} statement pages for ${packets} packets (expected ` +
      `${packets * LETTER_PAGES} and ${packets * STATEMENT_MAX_PAGES})`
  );
}

// Filenames and PDF /Title both carry the date. Build one PDF at a time and hand it
// straight to prepareBinaryData (which offloads the bytes to n8n's binary store) BEFORE
// building the next, so we never hold two multi-MB buffers at once.
const today = new Date().toISOString().slice(0, 10);
const lettersName = 'Past-Due-Letters-' + today + '.pdf';
const statementsName = 'Past-Due-Statements-' + today + '.pdf';

const lettersData = await this.helpers.prepareBinaryData(
  buildPdf(letterContents, { title: 'Past-Due Letters ' + today }),
  lettersName, 'application/pdf');
const statementsData = await this.helpers.prepareBinaryData(
  buildPdf(statementContents, { title: 'Past-Due Statements ' + today }),
  statementsName, 'application/pdf');

return [
  {
    json: {
      type: 'letters', customers: sets.length, packets, skipped,
      excluded, fileName: lettersName,
    },
    binary: { data: lettersData },
  },
  {
    json: {
      type: 'statements', customers: sets.length, packets, skipped,
      excluded, fileName: statementsName,
    },
    binary: { data: statementsData },
  },
];

// To instead emit ONE PDF per customer (e.g. for individual mailing), replace the
// block above with a loop calling buildCustomerPdf(rec.tokens, rec.statement, {}).
