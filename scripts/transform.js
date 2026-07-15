/*
 * transform.js
 * ------------
 * Pure data transforms shared by the local test harness and the n8n Code node.
 * No I/O, no dependencies — safe to paste into an n8n Code node.
 *
 * Inputs (arrays of plain objects):
 *   customers[] (OData V4 Customer page):
 *     { No, Name, Address, Address_2, City, County, Post_Code, Balance_Due_LCY }
 *   invoices[] (standard API v2.0 salesInvoices entity):
 *     { number, customerNumber, invoiceDate, dueDate, totalAmountIncludingTax,
 *       remainingAmount, status }   // status 'Open' = posted & unpaid
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

// Remaining balance of a salesInvoice: prefer remainingAmount; if the field isn't
// returned, fall back to the total (an open invoice with no partial payment).
function invoiceRemaining(e) {
  const r = e.remainingAmount;
  if (r != null && r !== "") return Number(r) || 0;
  return Number(e.totalAmountIncludingTax) || 0;
}

/**
 * @param {Object[]} customers
 * @param {Object[]} invoices    standard-API salesInvoices
 * @param {Object}   [options]
 * @param {"filtered"|"balanceDue"} [options.amountSource="filtered"]
 *        "filtered"   -> Converted_balance = sum of remaining of the 2023-2024 open invoices
 *        "balanceDue" -> Converted_balance = customer's Balance_Due_LCY (total open balance)
 * @returns {Object[]} qualifying customer records
 */
function buildRecords(customers, invoices, options = {}) {
  const amountSource = options.amountSource || "filtered";

  // Index customers by their number for O(1) join.
  const custByNo = new Map();
  for (const c of customers || []) custByNo.set(String(c.No), c);

  // Keep only OPEN invoices whose invoice (document) date is inside the window.
  const grouped = new Map(); // customerNo -> { lines[], filteredRemaining }
  for (const e of invoices || []) {
    const isOpen = String(e.status) === "Open";
    if (!isOpen || !inWindow(e.invoiceDate)) continue;

    const key = String(e.customerNumber);
    if (!grouped.has(key)) grouped.set(key, { lines: [], filteredRemaining: 0 });
    const g = grouped.get(key);
    const remaining = invoiceRemaining(e);
    g.filteredRemaining += remaining;
    g.lines.push({
      documentDate: isoDate(e.invoiceDate),
      documentNo: e.number || "",
      dueDate: isoDate(e.dueDate),
      amount: Number(e.totalAmountIncludingTax) || 0,
      remaining: remaining,
    });
  }

  const records = [];
  for (const [customerNo, g] of grouped) {
    // Skip anyone whose filtered open balance nets to zero.
    if (Math.round(g.filteredRemaining * 100) === 0) continue;

    const c = custByNo.get(customerNo) || {};
    const balanceDue = Number(c.Balance_Due_LCY) || 0;
    const amount =
      amountSource === "balanceDue" ? balanceDue : g.filteredRemaining;

    const lines = g.lines.sort((a, b) =>
      a.documentDate < b.documentDate ? -1 : a.documentDate > b.documentDate ? 1 : 0
    );

    records.push({
      customerNo,
      tokens: {
        Description: c.Name || customerNo,
        Address_1: c.Address || "",
        Address_2: c.Address_2 || "",
        City: c.City || "",
        State: c.County || "",
        Zipcode: c.Post_Code || "",
        Converted_balance: formatUSD(amount),
      },
      statement: {
        lines,
        total: g.filteredRemaining,
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
