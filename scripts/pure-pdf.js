/*
 * pure-pdf.js
 * -----------
 * Zero-dependency PDF generator. Emits the past-due letter + statement as ONE
 * multi-page PDF per customer using the base-14 fonts (no embedding, no modules,
 * no external service) — so it runs inside an n8n Cloud Code node as-is.
 *
 * Exports buildCustomerPdf(tokens, statement, opts) -> Buffer.
 *
 * Font widths are approximated (slightly generous) purely for line-wrapping and
 * centering; glyph rendering itself is exact (the viewer uses the real metrics).
 */

// --- WinAnsi text encoding + PDF string escaping ---------------------------
function toWin(s) {
  return String(s == null ? "" : s)
    .replace(/–/g, "\x96") // en dash
    .replace(/—/g, "\x97") // em dash
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/…/g, "...");
}
function esc(s) {
  return toWin(s).replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}

// Approximate glyph width in em units (generous, so lines never overflow).
function emWidth(ch) {
  if (ch === " ") return 0.3;
  if ("iljI.,:;'!|`".includes(ch)) return 0.3;
  if ("ftr()[]-".includes(ch)) return 0.4;
  if ("mwMW".includes(ch)) return 0.92;
  if (ch >= "A" && ch <= "Z") return 0.72;
  if (ch >= "0" && ch <= "9") return 0.56;
  return 0.53;
}
function approxWidth(s, size) {
  let w = 0;
  for (const ch of toWin(s)) w += emWidth(ch);
  return w * size;
}
function wrap(text, size, maxWidth) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let cur = "";
  for (const w of words) {
    const trial = cur ? cur + " " + w : w;
    if (approxWidth(trial, size) > maxWidth && cur) {
      lines.push(cur);
      cur = w;
    } else cur = trial;
  }
  if (cur) lines.push(cur);
  return lines;
}

// --- content-stream draw helpers -------------------------------------------
// Fonts: F1 Helvetica, F2 Helvetica-Bold, F3 Times-Roman, F4 Times-Bold
function text(x, y, s, font, size, gray) {
  const col = gray != null ? `${gray} g ` : "0 g ";
  return `${col}BT /${font} ${size} Tf 1 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)} Tm (${esc(s)}) Tj ET\n`;
}
function hline(x1, x2, y) {
  return `0.6 G 0.7 w ${x1.toFixed(2)} ${y.toFixed(2)} m ${x2.toFixed(2)} ${y.toFixed(2)} l S\n`;
}

const PAGE_W = 612, PAGE_H = 792, MARGIN = 72;
const HEAD = "ENGELMAN'S BAKERY";

function letterhead(size, y) {
  const w = approxWidth(HEAD, size);
  return text((PAGE_W - w) / 2, y - size, HEAD, "F4", size, "0.5");
}

// --- letter (2 pages) -------------------------------------------------------
function letterPages(t) {
  const cw = PAGE_W - 2 * MARGIN;
  const size = 11, lh = 15;

  // Page 1
  let c = letterhead(22, PAGE_H - MARGIN);
  let y = PAGE_H - MARGIN - 22 - 40;
  c += text(MARGIN, y, "Subject:", "F4", size);
  c += text(MARGIN + approxWidth("Subject:  ", size), y, "Past Due Balance – Immediate Attention Required", "F3", size);
  y -= lh + 12;
  c += text(MARGIN, y, `Dear ${t.Description},`, "F3", size);
  y -= lh + 12;

  const paras = [
    `We are writing to inform you that your account with Engelman's Bakery is currently past due. As of today, your overdue balance is $${t.Converted_balance}. We have enclosed an account statement for your convenience.`,
    "We kindly request that you remit payment in full to satisfy your payment obligation. Please contact us at 770-248-1444 ext. 2 to arrange payment or discuss any questions regarding your account. If the account is not paid, further collection proceedings will be taken.",
    "We appreciate your prompt attention to this matter and look forward to resolving it quickly.",
  ];
  for (const p of paras) {
    for (const ln of wrap(p, size, cw)) {
      c += text(MARGIN, y, ln, "F3", size);
      y -= lh;
    }
    y -= 10;
  }
  y -= 12;
  c += text(MARGIN, y, "Best Regards,", "F3", size); y -= lh;
  c += text(MARGIN, y, "Engelman's Bakery", "F3", size); y -= lh;
  c += text(MARGIN, y, "770-248-1444", "F3", size);

  // Page 2 — mailing address block (window-envelope position)
  let c2 = letterhead(22, PAGE_H - MARGIN);
  const addr = [
    t.Description,
    t.Address_1,
    t.Address_2,
    `${t.City}, ${t.State} ${t.Zipcode}`,
  ].filter((l) => l && String(l).trim() && String(l).trim() !== ",");
  let ay = 150;
  for (const ln of addr) {
    c2 += text(MARGIN, ay, ln, "F3", size);
    ay -= lh;
  }
  return [c, c2];
}

// --- statement (1+ pages) ---------------------------------------------------
function formatUSD(n) {
  const num = Number(n) || 0;
  return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function statementPages(t, statement, opts) {
  const asOf = (opts && opts.asOfDate) || new Date().toISOString().slice(0, 10);
  const cols = [
    { key: "documentDate", label: "Document Date", x: MARGIN },
    { key: "documentNo", label: "Invoice No.", x: MARGIN + 110 },
    { key: "dueDate", label: "Due Date", x: MARGIN + 220 },
    { key: "amount", label: "Amount", x: MARGIN + 300, money: true, right: MARGIN + 390 },
    { key: "remaining", label: "Remaining", x: MARGIN + 410, money: true, right: PAGE_W - MARGIN },
  ];
  const size = 9, lh = 14;

  const pages = [];
  let c = "";
  let y;
  const startPage = (withHeader) => {
    c = letterhead(20, PAGE_H - MARGIN);
    y = PAGE_H - MARGIN - 20 - 18;
    const title = "Account Statement";
    c += text((PAGE_W - approxWidth(title, 16)) / 2, y, title, "F4", 16);
    y -= 30;
    if (withHeader) {
      c += text(MARGIN, y, `Statement Date: ${asOf}`, "F1", 10); y -= 18;
      // Bill-to block: Company Name, Account Number, then address.
      const bill = [
        t.Description,
        t.AccountNumber ? "Account Number: " + t.AccountNumber : null,
        t.Address_1,
        t.Address_2,
        `${t.City}, ${t.State} ${t.Zipcode}`,
      ].filter((l) => l && String(l).trim() && String(l).trim() !== ",");
      for (const l of bill) { c += text(MARGIN, y, l, "F1", 10); y -= 13; }
      y -= 10;
      c += text(MARGIN, y, "Open Invoices:", "F2", 10); y -= 18;
    }
    // column header
    for (const col of cols) {
      if (col.right) c += text(col.right - approxWidth(col.label, size), y, col.label, "F2", size);
      else c += text(col.x, y, col.label, "F2", size);
    }
    y -= 5;
    c += hline(MARGIN, PAGE_W - MARGIN, y);
    y -= 13;
  };

  startPage(true);
  for (const ln of statement.lines) {
    if (y < 110) { pages.push(c); startPage(false); }
    for (const col of cols) {
      const v = col.money ? "$" + formatUSD(ln[col.key]) : String(ln[col.key] || "");
      if (col.right) c += text(col.right - approxWidth(v, size), y, v, "F1", size);
      else c += text(col.x, y, v, "F1", size);
    }
    y -= lh;
  }
  y -= 4;
  c += hline(MARGIN, PAGE_W - MARGIN, y);
  y -= 16;
  const totLabel = "Total Due:";
  const totVal = "$" + formatUSD(statement.total);
  c += text(MARGIN + 300, y, totLabel, "F2", 10);
  c += text((PAGE_W - MARGIN) - approxWidth(totVal, 10), y, totVal, "F2", 10);
  pages.push(c);
  return pages;
}

// --- low-level PDF assembler ------------------------------------------------
function buildPdf(pageContents) {
  const P = pageContents.length;
  const offsets = [];
  let file = "%PDF-1.4\n%\xe2\xe3\xcf\xd3\n";
  const emit = (num, body) => {
    offsets[num] = file.length;
    file += `${num} 0 obj\n${body}\nendobj\n`;
  };
  const pageNums = [];
  for (let i = 0; i < P; i++) pageNums.push(8 + i * 2);

  emit(1, "<< /Type /Catalog /Pages 2 0 R >>");
  emit(2, `<< /Type /Pages /Kids [ ${pageNums.map((n) => n + " 0 R").join(" ")} ] /Count ${P} >>`);
  emit(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  emit(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");
  emit(5, "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>");
  emit(6, "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>");
  for (let i = 0; i < P; i++) {
    const contentNum = 7 + i * 2;
    const pageNum = 8 + i * 2;
    const content = pageContents[i];
    emit(contentNum, `<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
    emit(
      pageNum,
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_W} ${PAGE_H}] ` +
        `/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> /Contents ${contentNum} 0 R >>`
    );
  }
  const lastObj = 6 + 2 * P;
  const xrefOffset = file.length;
  let xref = `xref\n0 ${lastObj + 1}\n0000000000 65535 f \n`;
  for (let n = 1; n <= lastObj; n++) {
    xref += String(offsets[n] || 0).padStart(10, "0") + " 00000 n \n";
  }
  file += xref;
  file += `trailer\n<< /Size ${lastObj + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(file, "latin1");
}

// Page-content array for one customer (letter pages + statement pages).
function customerPages(tokens, statement, opts) {
  return [...letterPages(tokens), ...statementPages(tokens, statement, opts || {})];
}

// One PDF (letter + statement) for a single customer.
function buildCustomerPdf(tokens, statement, opts) {
  return buildPdf(customerPages(tokens, statement, opts));
}

// One combined batch PDF for a list of records ({ tokens, statement }).
function buildBatchPdf(records, opts) {
  const pages = [];
  for (const r of records) pages.push(...customerPages(r.tokens, r.statement, opts));
  return buildPdf(pages);
}

module.exports = { buildCustomerPdf, buildBatchPdf, customerPages };
