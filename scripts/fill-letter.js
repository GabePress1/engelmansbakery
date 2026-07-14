/*
 * fill-letter.js
 * --------------
 * Fill the past-due-letter.docx template with one customer's merge tokens and
 * return the resulting .docx as a Buffer. Used by the local harness and the
 * n8n Code node (which supplies the template bytes read earlier in the flow).
 */
const PizZip = require("pizzip");
const Docxtemplater = require("docxtemplater");

/**
 * @param {Buffer} templateBuffer  bytes of past-due-letter.docx
 * @param {Object} tokens          { Description, Address_1, Address_2, City, State, Zipcode, Converted_balance }
 * @returns {Buffer} filled .docx
 */
function fillLetter(templateBuffer, tokens) {
  const zip = new PizZip(templateBuffer);
  const doc = new Docxtemplater(zip, {
    paragraphLoop: true,
    linebreaks: true,
    // Missing tags render as empty string instead of throwing (e.g. blank Address_2).
    nullGetter: () => "",
  });
  doc.render(tokens);
  return doc.getZip().generate({ type: "nodebuffer", compression: "DEFLATE" });
}

module.exports = { fillLetter };
