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

// Map the BC Document_Type to a short label for the statement's "Document Type"
// column: Invoice / Credit / Payment / Refund (unknown types pass through as-is).
function displayDocType(type) {
  const t = String(type == null ? "" : type).trim();
  if (t === "Credit Memo" || t === "Credit") return "Credit";
  if (t === "Invoice") return "Invoice";
  if (t === "Payment") return "Payment";
  if (t === "Refund") return "Refund";
  return t;
}

/**
 * @param {Object[]} customers
 * @param {Object[]} entries     Customer Ledger Entries (OData V4 CustomerLedgerEntries)
 * @param {Object}   [options]
 * @param {string}   [options.today] ISO date used for the past-due test (default: today). An
 *        invoice is past due when its Due Date is strictly before this date.
 * @param {"filtered"|"balanceDue"} [options.amountSource="filtered"]
 *        "filtered"   -> Converted_balance = past-due invoices minus open credits/payments
 *        "balanceDue" -> Converted_balance = customer's Balance_Due_LCY (total open balance)
 *
 * Counted customers = those with a POSITIVE net past-due balance. The statement lists the
 * past-due invoices plus open credits/payments (negative lines); the total nets to the letter
 * amount.
 * @returns {Object[]} qualifying customer records
 */
function buildRecords(customers, entries, options = {}) {
  const amountSource = options.amountSource || "filtered";
  // "Past due" = an open invoice whose Due Date is strictly before `today`.
  const today = options.today || new Date().toISOString().slice(0, 10);
  // A customer is counted only if they have an open invoice with remaining balance
  // dated on/before this cutoff (default 2024 or older). BLANK ("") drops the age
  // rule so any overdue invoice qualifies.
  const qualifyCutoff = options.qualifyCutoff == null
    ? "2024-12-31"
    : String(options.qualifyCutoff).slice(0, 10);
  // Minimum net past-due balance to include a customer (default 0). The workflow's
  // "Settings" node sets this to 1000 so only customers owing >= $1,000 get a letter.
  const minBalance = Number(options.minBalance) || 0;
  // Exclude customers whose default route (Customer.Shipping_Agent_Code) matches this
  // (default "RT 21"). Fail-open: a missing/blank route is never excluded.
  const normRoute = (s) => String(s == null ? "" : s).toUpperCase().replace(/[^A-Z0-9]/g, "");
  const excludeRoute = options.excludeRoute === null ? "" : normRoute(options.excludeRoute || "RT 21");

  // Index customers by their number for O(1) join.
  const custByNo = new Map();
  for (const c of customers || []) custByNo.set(String(c.No), c);

  // First ship-to per customer = the default; used for the shipping-address PDF.
  const shipByNo = new Map();
  for (const st of options.shipTos || []) {
    const k = String(st.HFSCustomerNo);
    if (!shipByNo.has(k)) shipByNo.set(k, st);
  }

  // Per customer, collect: PAST-DUE invoice lines, plus OPEN credit/payment lines
  // (any date). Non-invoice open entries (Payment/Credit Memo/Refund) are credits
  // with a negative Remaining_Amount that reduce the balance. `hasOld` flags an open
  // invoice with remaining dated on/before the qualify cutoff.
  const grouped = new Map(); // customerNo -> { lines[], total, hasOld }
  for (const e of entries || []) {
    const isOpen = e.Open === true || e.Open === "true" || e.Open === 1;
    if (!isOpen) continue;

    const type = String(e.Document_Type);
    const remaining = Number(e.Remaining_Amount) || 0;
    const documentDate = isoDate(e.Document_Date);
    const dueDate = isoDate(e.Due_Date);
    const key = String(e.Customer_No);
    if (!grouped.has(key)) grouped.set(key, { lines: [], total: 0, hasOld: false });
    const g = grouped.get(key);

    if (type === "Invoice") {
      // Qualify gate: an open invoice with a remaining balance dated <= cutoff.
      // Blank cutoff -> any remaining invoice satisfies the gate.
      if (remaining !== 0 && documentDate && (!qualifyCutoff || documentDate <= qualifyCutoff)) g.hasOld = true;
      // Statement shows only PAST-DUE invoices.
      if (dueDate && dueDate < today) {
        g.total += remaining;
        g.lines.push({
          documentDate, docType: "Invoice",
          orderNo: e.Description || "", documentNo: e.Document_No || "",
          dueDate, remaining, kind: "invoice",
        });
      }
    } else {
      // Open payment/credit/refund — an unapplied credit, included regardless of date.
      g.total += remaining;
      g.lines.push({
        documentDate, docType: displayDocType(type),
        orderNo: e.Order_No || "", documentNo: e.Document_No || "",
        dueDate, remaining, kind: "credit",
      });
    }
  }

  const records = [];
  for (const [customerNo, g] of grouped) {
    // Counted only if they have a remaining invoice dated 2024-or-older AND a
    // positive net past-due balance that meets the minimum threshold.
    if (!g.hasOld) continue;
    if (Math.round(g.total * 100) <= 0) continue;
    if (Math.round(g.total * 100) < Math.round(minBalance * 100)) continue;

    const c = custByNo.get(customerNo) || {};
    // Exclude the RT 21 route (from the customer's default Shipping_Agent_Code).
    if (excludeRoute && normRoute(c.Shipping_Agent_Code) === excludeRoute) continue;
    const balanceDue = Number(c.Balance_Due_LCY) || 0;
    const amount = amountSource === "balanceDue" ? balanceDue : g.total;
    const Converted_balance = formatUSD(amount);
    const name = c.Name || customerNo;

    const lines = g.lines.sort((a, b) =>
      a.documentDate < b.documentDate ? -1 : a.documentDate > b.documentDate ? 1 : 0
    );

    const tokens = {
      Description: name, AccountNumber: customerNo,
      Address_1: c.Address || "", Address_2: c.Address_2 || "",
      City: c.City || "", State: c.County || "", Zipcode: c.Post_Code || "",
      Converted_balance,
    };
    // Shipping tokens: default ship-to address (fall back to billing when none).
    const st = shipByNo.get(customerNo);
    const shipTokens = st
      ? {
          Description: name, AccountNumber: customerNo,
          Address_1: st.Address || "", Address_2: st.Address_2 || "",
          City: st.City || "", State: st.County || st.State || "", Zipcode: st.Post_Code || "",
          Converted_balance,
        }
      : { ...tokens };

    records.push({ customerNo, tokens, shipTokens, statement: { lines, total: g.total, balanceDue } });
  }

  // Deterministic order: by customer name.
  records.sort((a, b) => a.tokens.Description.localeCompare(b.tokens.Description));
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
