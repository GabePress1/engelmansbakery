/*
 * render-pdf.js
 * -------------
 * PURE-JS renderer (pdf-lib only) for the past-due letter and the statement.
 * No LibreOffice, no Gotenberg, no external service — runs anywhere n8n runs,
 * including inside a Code node. This is the DEFAULT rendering path.
 *
 * The docx template (templates/past-due-letter.docx) remains available as the
 * high-fidelity "Word mail merge" alternative when you have LibreOffice/Gotenberg.
 */
const {
  PDFDocument,
  StandardFonts,
  rgb,
} = require("pdf-lib");
const { formatUSD } = require("./transform");

const PAGE = { w: 612, h: 792 }; // US Letter, points
const MARGIN = 72;
const GRAY = rgb(0.5, 0.5, 0.5);
const BLACK = rgb(0, 0, 0);
const LINE_GRAY = rgb(0.6, 0.6, 0.6);

// Word-wrap `text` to fit `maxWidth` at the given font/size.
function wrap(text, font, size, maxWidth) {
  const words = String(text).split(/\s+/);
  const lines = [];
  let cur = "";
  for (const w of words) {
    const trial = cur ? cur + " " + w : w;
    if (font.widthOfTextAtSize(trial, size) > maxWidth && cur) {
      lines.push(cur);
      cur = w;
    } else {
      cur = trial;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

async function renderLetterPdf(tokens) {
  const pdf = await PDFDocument.create();
  const times = await pdf.embedFont(StandardFonts.TimesRoman);
  const timesBold = await pdf.embedFont(StandardFonts.TimesRomanBold);

  const contentW = PAGE.w - 2 * MARGIN;

  // ---- Page 1 ----
  const p1 = pdf.addPage([PAGE.w, PAGE.h]);
  let y = PAGE.h - MARGIN;

  // Letterhead (text placeholder; swap for the brand logo in the docx path)
  const head = "ENGELMAN'S BAKERY";
  const headSize = 22;
  const headW = timesBold.widthOfTextAtSize(head, headSize);
  p1.drawText(head, {
    x: (PAGE.w - headW) / 2,
    y: y - headSize,
    size: headSize,
    font: timesBold,
    color: GRAY,
  });
  y -= headSize + 48;

  const size = 11;
  const lh = 15; // line height
  const drawLine = (segments, yy) => {
    // segments: [{text, bold}]
    let x = MARGIN;
    for (const s of segments) {
      const f = s.bold ? timesBold : times;
      p1.drawText(s.text, { x, y: yy, size, font: f, color: BLACK });
      x += f.widthOfTextAtSize(s.text, size);
    }
  };
  const drawPara = (text, opts = {}) => {
    const f = opts.bold ? timesBold : times;
    for (const ln of wrap(text, f, size, contentW)) {
      p1.drawText(ln, { x: MARGIN, y, size, font: f, color: BLACK });
      y -= lh;
    }
    y -= opts.gap != null ? opts.gap : 8;
  };

  drawLine(
    [
      { text: "Subject: ", bold: true },
      { text: "Past Due Balance – Immediate Attention Required", bold: false },
    ],
    y
  );
  y -= lh + 12;

  drawPara(`Dear ${tokens.Description},`, { gap: 12 });

  drawPara(
    `We are writing to inform you that your account with Engelman's Bakery is currently past due. As of today, your overdue balance is $${tokens.Converted_balance}. We have enclosed an account statement for your convenience.`,
    { gap: 10 }
  );
  drawPara(
    "We kindly request that you remit payment in full to satisfy your payment obligation. Please contact us at 770-248-1444 ext. 2 to arrange payment or discuss any questions regarding your account. If the account is not paid, further collection proceedings will be taken.",
    { gap: 10 }
  );
  drawPara(
    "We appreciate your prompt attention to this matter and look forward to resolving it quickly.",
    { gap: 22 }
  );

  drawPara("Best Regards,", { gap: 2 });
  drawPara("Engelman's Bakery", { gap: 2 });
  drawPara("770-248-1444", { gap: 2 });

  // ---- Page 2: mailing address block (window-envelope position) ----
  const p2 = pdf.addPage([PAGE.w, PAGE.h]);
  const head2W = timesBold.widthOfTextAtSize(head, headSize);
  p2.drawText(head, {
    x: (PAGE.w - head2W) / 2,
    y: PAGE.h - MARGIN - headSize,
    size: headSize,
    font: timesBold,
    color: GRAY,
  });
  const addrLines = [
    tokens.Description,
    tokens.Address_1,
    tokens.Address_2,
    `${tokens.City}, ${tokens.State} ${tokens.Zipcode}`,
  ].filter((l) => l && String(l).trim() && String(l).trim() !== ",");
  let ay = 120; // near bottom
  for (const ln of addrLines) {
    p2.drawText(ln, { x: MARGIN, y: ay, size, font: times, color: BLACK });
    ay -= lh;
  }

  return Buffer.from(await pdf.save());
}

async function renderStatementPdf(tokens, statement, opts = {}) {
  const asOf = opts.asOfDate || new Date().toISOString().slice(0, 10);
  const pdf = await PDFDocument.create();
  const helv = await pdf.embedFont(StandardFonts.Helvetica);
  const helvBold = await pdf.embedFont(StandardFonts.HelveticaBold);
  const times = await pdf.embedFont(StandardFonts.TimesRoman);
  const timesBold = await pdf.embedFont(StandardFonts.TimesRomanBold);

  const page = pdf.addPage([PAGE.w, PAGE.h]);
  let y = PAGE.h - MARGIN;

  const head = "ENGELMAN'S BAKERY";
  const headW = timesBold.widthOfTextAtSize(head, 20);
  page.drawText(head, { x: (PAGE.w - headW) / 2, y: y - 20, size: 20, font: timesBold, color: GRAY });
  y -= 20 + 18;
  const title = "Account Statement";
  const titleW = timesBold.widthOfTextAtSize(title, 16);
  page.drawText(title, { x: (PAGE.w - titleW) / 2, y: y - 16, size: 16, font: timesBold, color: BLACK });
  y -= 16 + 24;

  page.drawText(`Statement Date: ${asOf}`, { x: MARGIN, y, size: 10, font: helv, color: BLACK });
  y -= 20;

  // Bill-to block
  const billTo = [
    tokens.Description,
    tokens.Address_1,
    tokens.Address_2,
    `${tokens.City}, ${tokens.State} ${tokens.Zipcode}`,
  ].filter((l) => l && String(l).trim() && String(l).trim() !== ",");
  for (const ln of billTo) {
    page.drawText(ln, { x: MARGIN, y, size: 10, font: helv, color: BLACK });
    y -= 14;
  }
  y -= 12;

  page.drawText("Open invoices (Document Date 2023–2024):", {
    x: MARGIN, y, size: 10, font: helvBold, color: BLACK,
  });
  y -= 20;

  // Table columns (x positions and alignment)
  const cols = [
    { key: "documentDate", label: "Document Date", x: MARGIN, align: "left" },
    { key: "documentNo", label: "Invoice No.", x: MARGIN + 110, align: "left" },
    { key: "dueDate", label: "Due Date", x: MARGIN + 220, align: "left" },
    { key: "amount", label: "Amount", x: MARGIN + 355, align: "right", money: true },
    { key: "remaining", label: "Remaining", x: MARGIN + 465, align: "right", money: true },
  ];
  const rightEdge = PAGE.w - MARGIN;
  const drawRow = (getVal, font, size) => {
    for (const c of cols) {
      let v = getVal(c);
      if (c.align === "right") {
        const w = font.widthOfTextAtSize(v, size);
        page.drawText(v, { x: (c.money ? c.x : c.x) - w + 40, y, size, font, color: BLACK });
      } else {
        page.drawText(v, { x: c.x, y, size, font, color: BLACK });
      }
    }
  };

  // Header row
  drawRow((c) => c.label, helvBold, 9);
  y -= 6;
  page.drawLine({ start: { x: MARGIN, y }, end: { x: rightEdge, y }, thickness: 0.7, color: LINE_GRAY });
  y -= 14;

  // Data rows
  for (const ln of statement.lines) {
    drawRow((c) => {
      if (c.money) return "$" + formatUSD(ln[c.key]);
      return String(ln[c.key] || "");
    }, helv, 9);
    y -= 14;
    if (y < 120) { y = PAGE.h - MARGIN; pdf.addPage([PAGE.w, PAGE.h]); }
  }

  y -= 4;
  page.drawLine({ start: { x: MARGIN, y }, end: { x: rightEdge, y }, thickness: 0.7, color: LINE_GRAY });
  y -= 18;

  const totalLabel = "Total Due:";
  const totalVal = "$" + formatUSD(statement.total);
  page.drawText(totalLabel, { x: MARGIN + 355, y, size: 10, font: helvBold, color: BLACK });
  const tvW = helvBold.widthOfTextAtSize(totalVal, 10);
  page.drawText(totalVal, { x: rightEdge - tvW, y, size: 10, font: helvBold, color: BLACK });

  return Buffer.from(await pdf.save());
}

module.exports = { renderLetterPdf, renderStatementPdf };
