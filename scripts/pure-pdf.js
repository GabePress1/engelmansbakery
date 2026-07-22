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

// Embedded brand logo (baseline JPEG). Populated by scripts/embed-logo.js.
const LOGO = { w: 263, h: 53, b64: "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" };

// Draw the letterhead centered at the top: the logo image if present, else grey text.
// Returns { content, bottom } where `bottom` is the y just below the header.
function header(topY, dispW, textSize) {
  if (LOGO && LOGO.b64) {
    const w = dispW;
    const h = dispW * (LOGO.h / LOGO.w);
    const x = (PAGE_W - w) / 2;
    const bottom = topY - h;
    const content =
      `q ${w.toFixed(2)} 0 0 ${h.toFixed(2)} ${x.toFixed(2)} ${bottom.toFixed(2)} cm /Im0 Do Q\n`;
    return { content, bottom };
  }
  const size = textSize || 22;
  const w = approxWidth(HEAD, size);
  return { content: text((PAGE_W - w) / 2, topY - size, HEAD, "F4", size, "0.5"), bottom: topY - size };
}

// --- letter (2 pages) -------------------------------------------------------
function letterPages(t) {
  const cw = PAGE_W - 2 * MARGIN;
  const size = 11, lh = 15;

  // Page 1
  const h1 = header(PAGE_H - MARGIN, 170, 22);
  let c = h1.content;
  let y = h1.bottom - 30;
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
  let c2 = header(PAGE_H - MARGIN, 170, 22).content;
  const addr = [
    t.Description,
    t.Address_1,
    t.Address_2,
    cityStateZip(t),
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
// Signed dollar amount: 1234.5 -> "$1,234.50", -200 -> "-$200.00".
function money(n) {
  const num = Number(n) || 0;
  return (num < 0 ? "-$" : "$") + formatUSD(Math.abs(num));
}
// "City, State Zip" — omits the state/zip cleanly when missing (ship-to has no state).
function cityStateZip(t) {
  const cs = [t.City, t.State].filter((x) => x && String(x).trim()).join(", ");
  return [cs, t.Zipcode].filter((x) => x && String(x).trim()).join(" ");
}
function statementPages(t, statement, opts) {
  const asOf = (opts && opts.asOfDate) || new Date().toISOString().slice(0, 10);
  const cols = [
    { key: "documentDate", label: "Document Date", x: MARGIN },
    { key: "docType", label: "Document Type", x: MARGIN + 66 },
    { key: "documentNo", label: "Document No.", x: MARGIN + 128 },
    { key: "orderNo", label: "Order No.", x: MARGIN + 188 },
    { key: "dueDate", label: "Due Date", x: MARGIN + 268 },
    { key: "remaining", label: "Remaining Balance", x: MARGIN + 340, money: true, right: PAGE_W - MARGIN },
  ];
  const size = 8, lh = 14;

  const pages = [];
  let c = "";
  let y;
  const startPage = (withHeader) => {
    const hd = header(PAGE_H - MARGIN, 150, 20);
    c = hd.content;
    y = hd.bottom - 34; // extra space between the logo and the title
    const title = "Past Due Invoices";
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
        cityStateZip(t),
      ].filter((l) => l && String(l).trim() && String(l).trim() !== ",");
      for (const l of bill) { c += text(MARGIN, y, l, "F1", 10); y -= 13; }
      y -= 18;
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
      const v = col.money ? money(ln[col.key]) : String(ln[col.key] || "");
      if (col.right) c += text(col.right - approxWidth(v, size), y, v, "F1", size);
      else c += text(col.x, y, v, "F1", size);
    }
    y -= lh;
  }
  y -= 4;
  c += hline(MARGIN, PAGE_W - MARGIN, y);
  y -= 16;
  const totLabel = "Total Past Due:";
  const totVal = money(statement.total);
  c += text(MARGIN + 300, y, totLabel, "F2", 10);
  c += text((PAGE_W - MARGIN) - approxWidth(totVal, 10), y, totVal, "F2", 10);
  pages.push(c);
  return pages;
}

// --- low-level PDF assembler ------------------------------------------------
// Memory-conscious: streams every object into a chunk array (each chunk becomes a
// small Buffer, joined once at the end) instead of growing one multi-MB string,
// and frees each page's content as soon as it is serialized. This keeps peak
// memory near one copy of the output — important for large batches inside the
// memory-capped n8n Cloud Code node. All emitted text is latin1 (bytes 0-255),
// so a string's .length equals its byte length and can drive the xref offsets.
function buildPdf(pageContents, docOpts) {
  const title = docOpts && docOpts.title;
  const P = pageContents.length;
  const offsets = [];
  const chunks = [];
  let pos = 0;
  const push = (s) => { chunks.push(s); pos += s.length; };
  push("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n");
  const emit = (num, body) => {
    offsets[num] = pos;
    push(`${num} 0 obj\n${body}\nendobj\n`);
  };
  // Optional logo image XObject is object 7; content/page objects start after it.
  const hasLogo = !!(LOGO && LOGO.b64);
  const imgObj = 7;
  const base = hasLogo ? 7 : 6; // last non-page object number
  const xobjRes = hasLogo ? ` /XObject << /Im0 ${imgObj} 0 R >>` : "";

  const pageNums = [];
  for (let i = 0; i < P; i++) pageNums.push(base + 2 + i * 2);

  emit(1, "<< /Type /Catalog /Pages 2 0 R >>");
  emit(2, `<< /Type /Pages /Kids [ ${pageNums.map((n) => n + " 0 R").join(" ")} ] /Count ${P} >>`);
  emit(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  emit(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");
  emit(5, "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>");
  emit(6, "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>");
  if (hasLogo) {
    const jpeg = Buffer.from(LOGO.b64, "base64").toString("latin1");
    emit(
      imgObj,
      `<< /Type /XObject /Subtype /Image /Width ${LOGO.w} /Height ${LOGO.h} ` +
        `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\n` +
        `stream\n${jpeg}\nendstream`
    );
  }
  for (let i = 0; i < P; i++) {
    const contentNum = base + 1 + i * 2;
    const pageNum = base + 2 + i * 2;
    const content = pageContents[i];
    pageContents[i] = null; // release the source string once we've consumed it
    emit(contentNum, `<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
    emit(
      pageNum,
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_W} ${PAGE_H}] ` +
        `/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >>${xobjRes} >> /Contents ${contentNum} 0 R >>`
    );
  }
  // Optional document Title (shows in the PDF viewer's title bar / tab).
  let infoObj = 0;
  if (title) {
    infoObj = base + 2 * P + 1;
    emit(infoObj, `<< /Title (${esc(title)}) >>`);
  }
  const lastObj = base + 2 * P + (infoObj ? 1 : 0);
  const xrefOffset = pos;
  let xref = `xref\n0 ${lastObj + 1}\n0000000000 65535 f \n`;
  for (let n = 1; n <= lastObj; n++) {
    xref += String(offsets[n] || 0).padStart(10, "0") + " 00000 n \n";
  }
  push(xref);
  const infoRef = infoObj ? ` /Info ${infoObj} 0 R` : "";
  push(`trailer\n<< /Size ${lastObj + 1} /Root 1 0 R${infoRef} >>\nstartxref\n${xrefOffset}\n%%EOF\n`);
  // Join once. Small per-chunk Buffers avoid a giant intermediate latin1 string.
  const out = Buffer.concat(chunks.map((c) => Buffer.from(c, "latin1")));
  chunks.length = 0;
  return out;
}

// Page-content array for one customer (letter pages + statement pages).
// Null-safe: a missing tokens/statement can never throw (renders empty fields).
function customerPages(tokens, statement, opts) {
  const t = tokens || {};
  const s = statement && statement.lines ? statement : { lines: [], total: 0 };
  return [...letterPages(t), ...statementPages(t, s, opts || {})];
}

// One PDF (letter + statement) for a single customer.
function buildCustomerPdf(tokens, statement, opts) {
  return buildPdf(customerPages(tokens, statement, opts));
}

// One combined batch PDF for a list of records. tokenKey selects the address set:
// "tokens" (billing, default) or "shipTokens" (shipping).
function buildBatchPdf(records, opts, tokenKey) {
  const key = tokenKey || "tokens";
  const pages = [];
  for (const r of records || []) {
    const tok = r && (r[key] || r.tokens);
    if (!tok) continue; // skip malformed records instead of crashing
    pages.push(...customerPages(tok, r.statement, opts));
  }
  return buildPdf(pages, opts);
}

module.exports = { buildCustomerPdf, buildBatchPdf, customerPages };
