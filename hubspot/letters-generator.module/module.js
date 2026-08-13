(function () {
  var POLL_MS = 5000;
  var MAX_MINUTES = 10;

  function jobId() {
    try { return crypto.randomUUID(); }
    catch (e) { return "job-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10); }
  }
  function plural(n) { return n + " customer" + (Number(n) === 1 ? "" : "s"); }

  function init(root) {
    if (root.__ldgInit) return;
    root.__ldgInit = true;

    var BASE = (root.getAttribute("data-base") || "").replace(/\/+$/, "");
    var SECRET = root.getAttribute("data-secret") || "";
    var runBtn = root.querySelector(".ldg-run");
    var statusEl = root.querySelector(".ldg-status");
    var minEl = root.querySelector(".ldg-min");
    var oldestEl = root.querySelector(".ldg-oldest");
    var padEl = root.querySelector(".ldg-pad");
    if (!runBtn) return;

    function setStatus(m, c) { statusEl.textContent = m; statusEl.className = "ldg-status" + (c ? " " + c : ""); }
    function done(m, c) { setStatus(m, c); runBtn.disabled = false; }

    // Fetch one of the two PDFs and trigger a browser download.
    function grab(id, file, fallbackName) {
      return fetch(BASE + "/sw-letters-download?jobId=" + encodeURIComponent(id) +
                   "&secret=" + encodeURIComponent(SECRET) + "&file=" + file)
        .then(function (r) { return r.blob(); })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url; a.download = fallbackName;
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
        });
    }

    function downloadBoth(id, s) {
      var today = new Date().toISOString().slice(0, 10);
      var billName = (s.billing && s.billing.fileName) || ("Past-Due-Billing-" + today + ".pdf");
      var shipName = (s.shipping && s.shipping.fileName) || ("Past-Due-Shipping-" + today + ".pdf");
      var billC = (s.billing && s.billing.customers) || 0;
      var shipC = (s.shipping && s.shipping.customers) || 0;
      setStatus("Ready — " + plural(billC) + " (billing), " + shipC + " with a separate shipping address. Downloading both…", "ok");
      grab(id, "billing", billName)
        .then(function () { return grab(id, "shipping", shipName); })
        .then(function () { done("Downloaded Billing (" + plural(billC) + ") and Shipping (" + plural(shipC) + "). You can generate another.", "ok"); })
        .catch(function (e) { done("Generated, but a download failed: " + e.message, "err"); });
    }

    function poll(id, startedAt) {
      if (Date.now() - startedAt > MAX_MINUTES * 60000) {
        return done("Timed out. It may still be processing, or no customers matched — try again or check n8n.", "err");
      }
      fetch(BASE + "/sw-letters-status?jobId=" + encodeURIComponent(id) + "&secret=" + encodeURIComponent(SECRET))
        .then(function (r) { return r.json(); })
        .then(function (s) {
          if (s.status === "done") {
            if (!s.customers) { return done("Finished — no customers matched your filters.", "ok"); }
            return downloadBoth(id, s);
          }
          if (s.status === "error") { return done("The run reported an error. Please check n8n.", "err"); }
          if (s.status === "unauthorized") { return done("Not authorized (check the shared secret).", "err"); }
          setTimeout(function () { poll(id, startedAt); }, POLL_MS);
        })
        .catch(function () { setTimeout(function () { poll(id, startedAt); }, POLL_MS); });
    }

    runBtn.addEventListener("click", function () {
      if (!BASE || !SECRET) { return done("This module isn't configured yet (missing webhook URL or secret).", "err"); }
      var id = jobId();
      var body = {
        jobId: id,
        minBalance: minEl.value === "" ? "" : Number(minEl.value),
        oldestInvoice: oldestEl.value || "",
        pad: padEl ? !!padEl.checked : true,
        secret: SECRET
      };
      runBtn.disabled = true;
      setStatus("Starting…");
      fetch(BASE + "/sw-letters-run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body)
      }).then(function () {
        setStatus("Generating… this can take a few minutes. Please keep this page open.");
        poll(id, Date.now());
      }).catch(function (e) { done("Could not start the run: " + e.message, "err"); });
    });
  }

  function boot() {
    var nodes = document.querySelectorAll(".ldg");
    for (var i = 0; i < nodes.length; i++) init(nodes[i]);
  }
  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
