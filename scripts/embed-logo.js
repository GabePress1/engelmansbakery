/*
 * embed-logo.js
 * -------------
 * Injects the brand logo (scripts/logo-baseline.jpg — a BASELINE JPEG) into
 * scripts/pure-pdf.js as the inline `const LOGO = { w, h, b64 }` so the renderer
 * stays self-contained (works inside an n8n Code node with no file access).
 *
 * Re-run this whenever the logo changes:
 *   1) put the new logo at scripts/logo-baseline.jpg as a BASELINE JPEG
 *      (progressive JPEGs do NOT render via PDF /DCTDecode), then
 *   2) node scripts/embed-logo.js && node n8n/build-workflow.js
 */
const fs = require("fs");
const path = require("path");

const JPG = path.join(__dirname, "logo-baseline.jpg");
const PURE = path.join(__dirname, "pure-pdf.js");

// Read JPEG width/height from the SOF marker.
function jpegSize(buf) {
  let i = 2;
  while (i < buf.length) {
    if (buf[i] !== 0xff) { i++; continue; }
    const marker = buf[i + 1];
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
    }
    if (marker === 0xd8 || marker === 0xd9 || (marker >= 0xd0 && marker <= 0xd7)) { i += 2; continue; }
    i += 2 + buf.readUInt16BE(i + 2);
  }
  throw new Error("Could not read JPEG dimensions");
}

const buf = fs.readFileSync(JPG);
const { w, h } = jpegSize(buf);
const b64 = buf.toString("base64");

let src = fs.readFileSync(PURE, "utf8");
if (!/const LOGO = [^\n]*;/.test(src)) {
  throw new Error("Could not find `const LOGO = ...;` line in pure-pdf.js");
}
src = src.replace(/const LOGO = [^\n]*;/, `const LOGO = { w: ${w}, h: ${h}, b64: "${b64}" };`);
fs.writeFileSync(PURE, src);
console.log(`Embedded logo ${w}x${h}, ${buf.length} bytes (base64 ${b64.length} chars) into pure-pdf.js`);
