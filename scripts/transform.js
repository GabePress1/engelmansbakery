/*
 * transform.js
 * ------------
 * Pure data transforms shared by the local test harness and the n8n Code node.
 * No I/O, no dependencies — safe to paste into an n8n Code node.
 *
 * Inputs (arrays of plain objects):
 *   customers[] (OData V4 Customer page):
 *     { No, Name, Address, Address_2, City, County, Post_Code, Balance_Due_LCY }
 *   entries[] (OData V4 CustomerLedgerEntries page — table 21):
 *     { Customer_No, Document_Type, Document_No, Document_Date, Due_Date,
 *       Amount, Remaining_Amount, Open }   // Open=true & Document_Type='Invoice' = unpaid invoice
 *
 * Output: one record per QUALIFYING customer (>=1 open invoice dated in the window):
 *   { customerNo, tokens{...seven merge tokens...}, statement{ lines[], total, balanceDue } }
 */

const WINDOW_START = "2023-01-01";
const WINDOW_END = "2024-12-31";

// Format a number as a USD amount WITHOUT the currency symbol: 1234.5 -> "1,234.50".
// The letter template already prints a literal "$" before {Converted_balance}.
function formatUSD(n) {
  const num = Number(n) || 0;
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Normalize a BC date (which may arrive as "2023-05-01" or full ISO) to YYYY-MM-DD.
function isoDate(d) {
  if (!d) return "";
  return String(d).slice(0, 10);
}

function inWindow(dateStr) {
  const d = isoDate(dateStr);
  return d >= WINDOW_START && d <= WINDOW_END;
}

/**
 * @param {Object[]} customers
 * @param {Object[]} entries     Customer Ledger Entries (OData V4 CustomerLedgerEntries)
 * @param {Object}   [options]
 * @param {string}   [options.qualifyCutoff="2024-12-31"] a customer is counted only if they
 *        have >= 1 open invoice with Document_Date on/before this date; once counted, ALL of
 *        their open invoices (incl. 2025/2026) are included on the statement and in the total.
 * @param {"filtered"|"balanceDue"} [options.amountSource="filtered"]
 *        "filtered"   -> Converted_balance = sum of Remaining_Amount of ALL open invoices
 *        "balanceDue" -> Converted_balance = customer's Balance_Due_LCY (total open balance)
 * @returns {Object[]} qualifying customer records
 */
function buildRecords(customers, entries, options = {}) {
  const amountSource = options.amountSource || "filtered";
  // A customer is "counted" if they have >= 1 OPEN invoice dated on/before this cutoff.
  const qualifyCutoff = options.qualifyCutoff || "2024-12-31";

  // Index customers by their number for O(1) join.
  const custByNo = new Map();
  for (const c of customers || []) custByNo.set(String(c.No), c);

  // Group ALL open invoice entries by customer (no date window here). We also flag
  // whether each customer has an open invoice on/before the qualify cutoff.
  const grouped = new Map(); // customerNo -> { lines[], total, hasPreCutoff }
  for (const e of entries || []) {
    const isInvoice = String(e.Document_Type) === "Invoice";
    const isOpen = e.Open === true || e.Open === "true" || e.Open === 1;
    if (!isInvoice || !isOpen) continue;

    const key = String(e.Customer_No);
    if (!grouped.has(key)) grouped.set(key, { lines: [], total: 0, hasPreCutoff: false });
    const g = grouped.get(key);
    const remaining = Number(e.Remaining_Amount) || 0;
    const documentDate = isoDate(e.Document_Date);
    g.total += remaining;
    if (documentDate && documentDate <= qualifyCutoff) g.hasPreCutoff = true;
    g.lines.push({
      documentDate: documentDate,
      documentNo: e.Document_No || "",
      dueDate: isoDate(e.Due_Date),
      amount: Number(e.Amount) || 0,
      remaining: remaining,
    });
  }

  const records = [];
  for (const [customerNo, g] of grouped) {
    // Only customers with an open invoice on/before the cutoff are counted.
    if (!g.hasPreCutoff) continue;
    // Skip anyone whose total open balance nets to zero.
    if (Math.round(g.total * 100) === 0) continue;

    const c = custByNo.get(customerNo) || {};
    const balanceDue = Number(c.Balance_Due_LCY) || 0;
    const amount = amountSource === "balanceDue" ? balanceDue : g.total;

    const lines = g.lines.sort((a, b) =>
      a.documentDate < b.documentDate ? -1 : a.documentDate > b.documentDate ? 1 : 0
    );

    records.push({
      customerNo,
      tokens: {
        Description: c.Name || customerNo,
        AccountNumber: customerNo,
        Address_1: c.Address || "",
        Address_2: c.Address_2 || "",
        City: c.City || "",
        State: c.County || "",
        Zipcode: c.Post_Code || "",
        Converted_balance: formatUSD(amount),
      },
      statement: {
        lines,
        total: g.total,
        balanceDue,
      },
    });
  }

  // Deterministic order: by customer name.
  records.sort((a, b) =>
    a.tokens.Description.localeCompare(b.tokens.Description)
  );
  return records;
}

module.exports = {
  buildRecords,
  formatUSD,
  isoDate,
  inWindow,
  WINDOW_START,
  WINDOW_END,
};
