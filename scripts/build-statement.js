/*
 * build-statement.js
 * ------------------
 * Build a customer statement as a standalone .docx (rendered to PDF downstream by
 * the same LibreOffice/Gotenberg step used for the letter). Lists the customer's
 * open 2023-2024 invoices with a total. No template file needed — authored inline.
 */
const PizZip = require("pizzip");
const { formatUSD } = require("./transform");

const esc = (s) =>
  String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

function tHeader() {
  const cells = ["Document Date", "Invoice No.", "Due Date", "Amount", "Remaining"];
  const tc = cells
    .map(
      (c) =>
        `<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>` +
        `<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>` +
        `<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">${esc(c)}</w:t></w:r></w:p></w:tc>`
    )
    .join("");
  return `<w:tr>${tc}</w:tr>`;
}

function tRow(line) {
  const vals = [
    line.documentDate,
    line.documentNo,
    line.dueDate,
    formatUSD(line.amount),
    formatUSD(line.remaining),
  ];
  const tc = vals
    .map(
      (v) =>
        `<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>` +
        `<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>` +
        `<w:r><w:t xml:space="preserve">${esc(v)}</w:t></w:r></w:p></w:tc>`
    )
    .join("");
  return `<w:tr>${tc}</w:tr>`;
}

function para(text, opts = {}) {
  const b = opts.bold ? "<w:b/>" : "";
  const sz = opts.size ? `<w:sz w:val="${opts.size}"/>` : "";
  const col = opts.color ? `<w:color w:val="${opts.color}"/>` : "";
  const align = opts.align ? `<w:jc w:val="${opts.align}"/>` : "";
  const rPr = b || sz || col ? `<w:rPr>${b}${sz}${col}</w:rPr>` : "";
  return (
    `<w:p><w:pPr><w:spacing w:after="${opts.spaceAfter != null ? opts.spaceAfter : 160}"/>${align}</w:pPr>` +
    `<w:r>${rPr}<w:t xml:space="preserve">${esc(text)}</w:t></w:r></w:p>`
  );
}

/**
 * @param {Object} tokens     the customer's merge tokens (name/address)
 * @param {Object} statement  { lines[], total } from transform.buildRecords
 * @param {Object} [opts]     { asOfDate }
 * @returns {Buffer} statement .docx
 */
function buildStatement(tokens, statement, opts = {}) {
  const asOf = opts.asOfDate || new Date().toISOString().slice(0, 10);
  const rows = [tHeader(), ...statement.lines.map(tRow)].join("");
  const table =
    `<w:tbl>` +
    `<w:tblPr><w:tblW w:w="0" w:type="auto"/>` +
    `<w:tblBorders>` +
    ["top", "left", "bottom", "right", "insideH", "insideV"]
      .map((s) => `<w:${s} w:val="single" w:sz="4" w:space="0" w:color="999999"/>`)
      .join("") +
    `</w:tblBorders></w:tblPr>` +
    rows +
    `</w:tbl>`;

  const bodyXml =
    para("ENGELMAN'S BAKERY", { bold: true, size: 44, color: "808080", align: "center", spaceAfter: 240 }) +
    para("Account Statement", { bold: true, size: 32, align: "center", spaceAfter: 240 }) +
    para(`Statement Date: ${asOf}`, { spaceAfter: 40 }) +
    para(tokens.Description || "", { bold: true, spaceAfter: 0 }) +
    para(tokens.Address_1 || "", { spaceAfter: 0 }) +
    (tokens.Address_2 ? para(tokens.Address_2, { spaceAfter: 0 }) : "") +
    para(`${tokens.City || ""}, ${tokens.State || ""} ${tokens.Zipcode || ""}`, { spaceAfter: 240 }) +
    para("Open invoices (Document Date 2023–2024):", { bold: true, spaceAfter: 120 }) +
    table +
    para(`Total Due: $${formatUSD(statement.total)}`, { bold: true, spaceAfter: 0 });

  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>${bodyXml}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>`;

  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;
  const rootRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;
  const docRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>`;

  const zip = new PizZip();
  zip.file("[Content_Types].xml", contentTypes);
  zip.folder("_rels").file(".rels", rootRels);
  zip.folder("word").file("document.xml", documentXml);
  zip.folder("word").folder("_rels").file("document.xml.rels", docRels);
  return zip.generate({ type: "nodebuffer", compression: "DEFLATE" });
}

module.exports = { buildStatement };
