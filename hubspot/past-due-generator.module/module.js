(function () {
  var POLL_MS = 5000;      // status poll interval
  var MAX_MINUTES = 8;     // give up after this long

  function jobId() {
    try { return crypto.randomUUID(); }
    catch (e) { return "job-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10); }
  }

  function init(root) {
    if (root.__pdgInit) return;
    root.__pdgInit = true;

    var BASE = (root.getAttribute("data-base") || "").replace(/\/+$/, "");
    var SECRET = root.getAttribute("data-secret") || "";
    var runBtn = root.querySelector(".pdg-run");
    var statusEl = root.querySelector(".pdg-status");
    var minEl = root.querySelector(".pdg-min");
    var oldestEl = root.querySelector(".pdg-oldest");
    if (!runBtn) return;

    function setStatus(m, c) { statusEl.textContent = m; statusEl.className = "pdg-status" + (c ? " " + c : ""); }
    function done(m, c) { setStatus(m, c); runBtn.disabled = false; }

    function download(id) {
      fetch(BASE + "/sw-statements-download?jobId=" + encodeURIComponent(id) + "&secret=" + encodeURIComponent(SECRET))
        .then(function (r) { return r.blob(); })
        .then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          var today = new Date().toISOString().slice(0, 10);
          a.href = url; a.download = "Past-Due-Notice-" + today + ".pdf";
          document.body.appendChild(a); a.click(); a.remove();
          setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
          done("Downloaded. You can generate another.", "ok");
        })
        .catch(function (e) { done("Generated, but the download failed: " + e.message, "err"); });
    }

    function poll(id, startedAt) {
      if (Date.now() - startedAt > MAX_MINUTES * 60000) {
        return done("Timed out. It may still be processing, or no customers matched — try again or check n8n.", "err");
      }
      fetch(BASE + "/sw-statements-status?jobId=" + encodeURIComponent(id) + "&secret=" + encodeURIComponent(SECRET))
        .then(function (r) { return r.json(); })
        .then(function (s) {
          if (s.status === "done") {
            if (!s.customers) { return done("Finished — no customers matched your filters for tomorrow's orders.", "ok"); }
            setStatus("Ready — downloading " + s.customers + " statement(s)…", "ok");
            return download(id);
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
        secret: SECRET
      };
      runBtn.disabled = true;
      setStatus("Starting…");
      fetch(BASE + "/sw-statements-run", {
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
    var nodes = document.querySelectorAll(".pdg");
    for (var i = 0; i < nodes.length; i++) init(nodes[i]);
  }
  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();
