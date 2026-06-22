(function () {
  var ISSUE_CLASSIFICATIONS = [
    "Resale Product",
    "Service Quality",
    "Product Quality",
    "Foreign Object",
    "Shortage",
    "Rejected Substitution",
    "Mispick",
    "Office Error"
  ];

  var MAX_LINES = 10;
  var MIN_LINES = 1;

  var wrapper = document.getElementById("credit-request-module");
  if (!wrapper) return;

  var webhookUrl = wrapper.getAttribute("data-webhook-url");
  var itemsEndpoint = wrapper.getAttribute("data-items-endpoint");

  var form = document.getElementById("credit-request-form");
  var productContainer = document.getElementById("cr-product-lines");
  var addBtn = document.getElementById("cr-add-product");
  var productCount = document.getElementById("cr-product-count");
  var submitBtn = document.getElementById("cr-submit");
  var loadingEl = document.getElementById("cr-loading");
  var successEl = document.getElementById("cr-success");
  var errorEl = document.getElementById("cr-error");

  var bcItems = [];
  var lineCount = 0;

  // ── BC Items Loading ──

  function loadBCItems() {
    if (!itemsEndpoint) {
      showItemsError("Items endpoint not configured.");
      return;
    }

    productContainer.innerHTML =
      '<div class="cr-items-loading"><span class="cr-spinner"></span> Loading products...</div>';

    fetch(itemsEndpoint)
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        bcItems = Array.isArray(data) ? data : data.value || [];
        productContainer.innerHTML = "";
        addProductLine();
      })
      .catch(function () {
        productContainer.innerHTML = "";
        showItemsError("Unable to load products. Please refresh the page.");
      });
  }

  function showItemsError(msg) {
    productContainer.innerHTML = '<div class="cr-items-error">' + escapeHtml(msg) + "</div>";
  }

  // ── Product Line Management ──

  function buildProductOptions() {
    var html = '<option value="">Select a product...</option>';
    for (var i = 0; i < bcItems.length; i++) {
      html +=
        '<option value="' +
        escapeAttr(bcItems[i].number) +
        '" data-description="' +
        escapeAttr(bcItems[i].displayName) +
        '">' +
        escapeHtml(bcItems[i].number) +
        " — " +
        escapeHtml(bcItems[i].displayName) +
        "</option>";
    }
    return html;
  }

  function buildClassificationOptions() {
    var html = '<option value="">Select classification...</option>';
    for (var i = 0; i < ISSUE_CLASSIFICATIONS.length; i++) {
      html +=
        '<option value="' +
        escapeAttr(ISSUE_CLASSIFICATIONS[i]) +
        '">' +
        escapeHtml(ISSUE_CLASSIFICATIONS[i]) +
        "</option>";
    }
    return html;
  }

  function createProductLineHtml(index) {
    return (
      '<div class="cr-product-line" data-line="' + index + '">' +
        '<div class="cr-product-line__header">' +
          '<span class="cr-product-line__label">Product Line ' + index + "</span>" +
          '<button type="button" class="cr-btn cr-btn--remove cr-remove-line">Remove</button>' +
        "</div>" +
        '<div class="cr-product-line__grid">' +
          '<div class="cr-form__field">' +
            '<label>Item No. <span class="cr-required">*</span></label>' +
            '<select class="cr-product-select" required>' +
              buildProductOptions() +
            "</select>" +
            '<span class="cr-form__error" data-error="productNumber"></span>' +
          "</div>" +
          '<div class="cr-form__field">' +
            "<label>Description</label>" +
            '<input type="text" class="cr-product-description" readonly placeholder="Auto-fills when item is selected">' +
          "</div>" +
          '<div class="cr-form__field">' +
            '<label>Quantity <span class="cr-required">*</span></label>' +
            '<input type="number" class="cr-product-qty" min="1" step="1" required placeholder="Qty">' +
            '<span class="cr-form__error" data-error="quantity"></span>' +
          "</div>" +
          '<div class="cr-form__field">' +
            '<label>Credit Amount <span class="cr-required">*</span></label>' +
            '<div class="cr-form__credit-wrapper">' +
              '<input type="number" class="cr-product-credit" min="0.01" step="0.01" required placeholder="0.00">' +
            "</div>" +
            '<span class="cr-form__error" data-error="creditAmount"></span>' +
          "</div>" +
          '<div class="cr-form__field">' +
            '<label>Issue Classification <span class="cr-required">*</span></label>' +
            '<select class="cr-product-classification" required>' +
              buildClassificationOptions() +
            "</select>" +
            '<span class="cr-form__error" data-error="classification"></span>' +
          "</div>" +
          '<div class="cr-form__field">' +
            "<label>Reason / Notes</label>" +
            '<textarea class="cr-product-notes" rows="2" placeholder="Optional notes for this line"></textarea>' +
          "</div>" +
        "</div>" +
      "</div>"
    );
  }

  function addProductLine() {
    if (lineCount >= MAX_LINES) return;
    lineCount++;
    var temp = document.createElement("div");
    temp.innerHTML = createProductLineHtml(lineCount);
    var lineEl = temp.firstChild;
    productContainer.appendChild(lineEl);

    lineEl.querySelector(".cr-product-select").addEventListener("change", onProductChange);
    lineEl.querySelector(".cr-remove-line").addEventListener("click", function () {
      removeProductLine(lineEl);
    });

    updateProductUI();
  }

  function removeProductLine(lineEl) {
    if (lineCount <= MIN_LINES) return;
    lineEl.remove();
    lineCount--;
    renumberLines();
    updateProductUI();
  }

  function renumberLines() {
    var lines = productContainer.querySelectorAll(".cr-product-line");
    for (var i = 0; i < lines.length; i++) {
      lines[i].setAttribute("data-line", i + 1);
      lines[i].querySelector(".cr-product-line__label").textContent =
        "Product Line " + (i + 1);
    }
  }

  function updateProductUI() {
    productCount.textContent = lineCount + " of " + MAX_LINES;
    addBtn.disabled = lineCount >= MAX_LINES;

    var removeBtns = productContainer.querySelectorAll(".cr-remove-line");
    for (var i = 0; i < removeBtns.length; i++) {
      removeBtns[i].style.display = lineCount <= MIN_LINES ? "none" : "";
    }
  }

  function onProductChange(e) {
    var select = e.target;
    var selectedOption = select.options[select.selectedIndex];
    var description = selectedOption.getAttribute("data-description") || "";
    var line = select.closest(".cr-product-line");
    line.querySelector(".cr-product-description").value = description;
  }

  // ── Validation ──

  function clearErrors() {
    var errorFields = wrapper.querySelectorAll(".cr-form__field--error");
    for (var i = 0; i < errorFields.length; i++) {
      errorFields[i].classList.remove("cr-form__field--error");
    }
    var errorMsgs = wrapper.querySelectorAll(".cr-form__error");
    for (var j = 0; j < errorMsgs.length; j++) {
      errorMsgs[j].textContent = "";
    }
  }

  function setFieldError(field, message) {
    var parent = field.closest(".cr-form__field");
    if (parent) {
      parent.classList.add("cr-form__field--error");
      var errorSpan = parent.querySelector(".cr-form__error");
      if (errorSpan) errorSpan.textContent = message;
    }
  }

  function validateForm() {
    clearErrors();
    var firstError = null;

    function markError(field, msg) {
      setFieldError(field, msg);
      if (!firstError) firstError = field;
    }

    var accountNum = document.getElementById("cr-account-number");
    if (!accountNum.value.trim()) {
      markError(accountNum, "Account number is required.");
    }

    var firstName = document.getElementById("cr-first-name");
    if (!firstName.value.trim()) {
      markError(firstName, "First name is required.");
    }

    var lastName = document.getElementById("cr-last-name");
    if (!lastName.value.trim()) {
      markError(lastName, "Last name is required.");
    }

    var email = document.getElementById("cr-email");
    var emailVal = email.value.trim();
    if (!emailVal) {
      markError(email, "Email is required.");
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) {
      markError(email, "Enter a valid email address.");
    }

    var lines = productContainer.querySelectorAll(".cr-product-line");
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];

      var productSelect = line.querySelector(".cr-product-select");
      if (!productSelect.value) {
        markError(productSelect, "Select a product.");
      }

      var qty = line.querySelector(".cr-product-qty");
      var qtyVal = parseInt(qty.value, 10);
      if (!qty.value || isNaN(qtyVal) || qtyVal < 1) {
        markError(qty, "Enter a valid quantity.");
      }

      var credit = line.querySelector(".cr-product-credit");
      var creditVal = parseFloat(credit.value);
      if (!credit.value || isNaN(creditVal) || creditVal <= 0) {
        markError(credit, "Enter a valid credit amount.");
      }

      var classification = line.querySelector(".cr-product-classification");
      if (!classification.value) {
        markError(classification, "Select a classification.");
      }
    }

    if (firstError) {
      firstError.scrollIntoView({ behavior: "smooth", block: "center" });
      firstError.focus();
    }

    return { isValid: !firstError, firstErrorElement: firstError };
  }

  // ── Form Submission ──

  function buildPayload() {
    var lines = productContainer.querySelectorAll(".cr-product-line");
    var productLines = [];
    var totalCredit = 0;

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var creditAmt = parseFloat(line.querySelector(".cr-product-credit").value) || 0;
      totalCredit += creditAmt;

      productLines.push({
        lineNumber: i + 1,
        productNumber: line.querySelector(".cr-product-select").value,
        productDescription: line.querySelector(".cr-product-description").value,
        quantity: parseInt(line.querySelector(".cr-product-qty").value, 10) || 0,
        creditAmount: creditAmt,
        issueClassification: line.querySelector(".cr-product-classification").value,
        notes: line.querySelector(".cr-product-notes").value.trim()
      });
    }

    return {
      submittedAt: new Date().toISOString(),
      account: {
        accountNumber: document.getElementById("cr-account-number").value.trim(),
        accountName: document.getElementById("cr-account-name").value.trim()
      },
      contact: {
        firstName: document.getElementById("cr-first-name").value.trim(),
        lastName: document.getElementById("cr-last-name").value.trim(),
        email: document.getElementById("cr-email").value.trim()
      },
      productLines: productLines,
      ticketNotes: document.getElementById("cr-ticket-notes").value.trim(),
      totalCreditRequested: Math.round(totalCredit * 100) / 100,
      totalLineItems: productLines.length,
      source: "engelmansbakery.com/credit-request"
    };
  }

  function setSubmitLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.style.display = loading ? "none" : "";
    loadingEl.style.display = loading ? "flex" : "none";
  }

  function submitForm() {
    var result = validateForm();
    if (!result.isValid) return;

    if (!webhookUrl) {
      showFormError("Webhook URL not configured. Please contact the administrator.");
      return;
    }

    setSubmitLoading(true);
    errorEl.style.display = "none";

    var payload = buildPayload();

    fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () {
            return {};
          }).then(function (body) {
            throw { status: res.status, body: body };
          });
        }
        return res.json().catch(function () {
          return { success: true };
        });
      })
      .then(function (data) {
        if (data.success === false) {
          showFormError(data.message || errorEl.textContent);
          setSubmitLoading(false);
          return;
        }
        form.style.display = "none";
        successEl.style.display = "block";
      })
      .catch(function (err) {
        var msg = "";
        if (err && err.body && err.body.message) {
          msg = err.body.message;
        }
        showFormError(msg);
        setSubmitLoading(false);
      });
  }

  function showFormError(msg) {
    if (msg) {
      errorEl.textContent = msg;
    }
    errorEl.style.display = "block";
    errorEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  // ── Utility ──

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  function escapeAttr(str) {
    return (str || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // ── Event Binding ──

  addBtn.addEventListener("click", addProductLine);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    submitForm();
  });

  // ── Init ──

  loadBCItems();
})();
