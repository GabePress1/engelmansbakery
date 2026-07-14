/*
 * build-template.js
 * -----------------
 * Generates templates/past-due-letter.docx: a Word document containing docxtemplater
 * tags that reproduce the Engelman's Bakery "Past Due Balance" letter layout.
 *
 * Tags (docxtemplater default { } delimiters), filled per customer:
 *   {Description}        customer / account name
 *   {Address_1}          address line 1
 *   {Address_2}          address line 2
 *   {City} {State} {Zipcode}
 *   {Converted_balance}  overdue balance, pre-formatted as USD string (e.g. "1,234.56")
 *
 * NOTE: This is a faithful reconstruction from the rendered letter, using a TEXT
 * letterhead placeholder ("ENGELMAN'S BAKERY"). To keep the exact brand logo, either
 * drop the real logo image into this template, or take the original .docx and replace
 * each «Field» mergefield with a {Field} tag (see README).
 *
 * Run: node templates/build-template.js
 */
const fs = require("fs");
const path = require("path");
const PizZip = require("pizzip");

// --- tiny OOXML helpers -----------------------------------------------------
const esc = (s) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

// A single paragraph. `runs` is an array of { text, bold, size, color, align }.
function para(runs, opts = {}) {
  const align = opts.align ? `<w:jc w:val="${opts.align}"/>` : "";
  const spacing =
    opts.spaceAfter != null
      ? `<w:spacing w:after="${opts.spaceAfter}"/>`
      : `<w:spacing w:after="160"/>`;
  const pPr = `<w:pPr>${spacing}${align}</w:pPr>`;
  const body = runs
    .map((r) => {
      const rb = r.bold ? "<w:b/>" : "";
      const sz = r.size ? `<w:sz w:val="${r.size}"/>` : "";
      const col = r.color ? `<w:color w:val="${r.color}"/>` : "";
      const rPr = rb || sz || col ? `<w:rPr>${rb}${sz}${col}</w:rPr>` : "";
      // xml:space=preserve so leading/trailing spaces (e.g. "Subject: ") survive
      return `<w:r>${rPr}<w:t xml:space="preserve">${esc(r.text)}</w:t></w:r>`;
    })
    .join("");
  return `<w:p>${pPr}${body}</w:p>`;
}

const blank = () => `<w:p><w:pPr><w:spacing w:after="160"/></w:pPr></w:p>`;
const pageBreak = () => `<w:p><w:r><w:br w:type="page"/></w:r></w:p>`;

// Letterhead placeholder (swap for the real logo image to match brand exactly).
const letterhead = () =>
  para([{ text: "ENGELMAN'S BAKERY", bold: true, size: 44, color: "808080" }], {
    align: "center",
    spaceAfter: 480,
  });

// --- document body ----------------------------------------------------------
const bodyXml = [
  letterhead(),
  blank(),
  para([
    { text: "Subject: ", bold: true },
    { text: "Past Due Balance – Immediate Attention Required" },
  ]),
  blank(),
  para([{ text: "Dear {Description}," }]),
  blank(),
  para([
    {
      text:
        "We are writing to inform you that your account with Engelman's Bakery is currently past due. As of today, your overdue balance is ${Converted_balance}. We have enclosed an account statement for your convenience.",
    },
  ]),
  para([
    {
      text:
        "We kindly request that you remit payment in full to satisfy your payment obligation. Please contact us at 770-248-1444 ext. 2 to arrange payment or discuss any questions regarding your account. If the account is not paid, further collection proceedings will be taken.",
    },
  ]),
  para([
    {
      text:
        "We appreciate your prompt attention to this matter and look forward to resolving it quickly.",
    },
  ]),
  blank(),
  para([{ text: "Best Regards," }]),
  para([{ text: "Engelman's Bakery" }]),
  para([{ text: "770-248-1444" }]),
  pageBreak(),
  // Page 2: letterhead + mailing address block near the bottom (window-envelope position)
  letterhead(),
  ...Array.from({ length: 22 }, () => blank()),
  para([{ text: "{Description}" }], { spaceAfter: 0 }),
  para([{ text: "{Address_1}" }], { spaceAfter: 0 }),
  para([{ text: "{Address_2}" }], { spaceAfter: 0 }),
  para([{ text: "{City}, {State} {Zipcode}" }], { spaceAfter: 0 }),
].join("");

const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    ${bodyXml}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
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

// --- assemble the .docx (a zip) --------------------------------------------
const zip = new PizZip();
zip.file("[Content_Types].xml", contentTypes);
zip.folder("_rels").file(".rels", rootRels);
zip.folder("word").file("document.xml", documentXml);
zip.folder("word").folder("_rels").file("document.xml.rels", docRels);

const buf = zip.generate({ type: "nodebuffer", compression: "DEFLATE" });
const outPath = path.join(__dirname, "past-due-letter.docx");
fs.writeFileSync(outPath, buf);
console.log("Wrote " + outPath + " (" + buf.length + " bytes)");
