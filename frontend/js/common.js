/* Shared helpers for every Lumen page.
   Plain script (no build step): load this first, then the page script.
   Page scripts must NOT redeclare API/STORAGE/escapeHtml. */

const API =
  window.location.port === "8000" || window.location.port === ""
    ? "/api"
    : "http://127.0.0.1:8000/api";

const STORAGE = {
  access: "lumen_access",
  refresh: "lumen_refresh",
  username: "lumen_username",
  role: "lumen_role",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function getAccess() {
  return localStorage.getItem(STORAGE.access);
}

function isLoggedIn() {
  return Boolean(getAccess() && localStorage.getItem(STORAGE.username));
}

function saveSession({ access, refresh, username, role }) {
  localStorage.setItem(STORAGE.access, access);
  if (refresh) {
    localStorage.setItem(STORAGE.refresh, refresh);
  }
  if (username) {
    localStorage.setItem(STORAGE.username, username);
  }
  if (role) {
    localStorage.setItem(STORAGE.role, role);
  }
}

function clearSession() {
  localStorage.removeItem(STORAGE.access);
  localStorage.removeItem(STORAGE.refresh);
  localStorage.removeItem(STORAGE.username);
  localStorage.removeItem(STORAGE.role);
}

async function refreshAccessToken() {
  const refresh = localStorage.getItem(STORAGE.refresh);
  if (!refresh) {
    return null;
  }
  try {
    const response = await fetch(`${API}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    if (data.access) {
      localStorage.setItem(STORAGE.access, data.access);
      return data.access;
    }
    return null;
  } catch (error) {
    console.error(error);
    return null;
  }
}

/* Fetch with automatic JSON handling, auth header and token refresh.
   options: standard fetch options plus:
     body  - object (stringified), FormData or string
     silentAuth - on 401, clear the session without redirecting */
async function apiFetch(path, options = {}) {
  const { body, headers, silentAuth, ...rest } = options;
  const isForm = body instanceof FormData;
  let payload = body;
  if (body && !isForm && typeof body !== "string") {
    payload = JSON.stringify(body);
  }
  const baseHeaders = { ...(headers || {}) };
  if (payload && !isForm && !baseHeaders["Content-Type"]) {
    baseHeaders["Content-Type"] = "application/json";
  }
  const url = /^https?:\/\//.test(path) ? path : `${API}${path}`;
  const send = (token) =>
    fetch(url, {
      ...rest,
      headers: token
        ? { ...baseHeaders, Authorization: `Bearer ${token}` }
        : baseHeaders,
      body: payload,
    });

  let access = getAccess();
  let response = await send(access);

  if (response.status === 401 && access) {
    const renewed = await refreshAccessToken();
    if (renewed) {
      access = renewed;
      response = await send(access);
    } else {
      clearSession();
      if (!silentAuth) {
        window.location.href = "index.html?login=1";
      }
    }
  }
  return response;
}

/* Turn a failed response into a human message. */
async function readError(response) {
  const data = await response.json().catch(() => null);
  if (!data) {
    return `Server error (HTTP ${response.status}).`;
  }
  const parts = [];
  const push = (value) => {
    if (Array.isArray(value)) {
      value.forEach(push);
    } else if (value && typeof value === "object") {
      Object.values(value).forEach(push);
    } else if (value) {
      parts.push(String(value));
    }
  };
  push(data);
  return parts.join(" ") || `Server error (HTTP ${response.status}).`;
}

function showToast(message) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, 4000);
}

/* Professional notice card: floats at the top-right of the viewport
   (outside the sidebar) and disappears as soon as the user taps
   anywhere else, presses Escape or hits the X. */
function showNotice({ title, text, tone = "success" } = {}) {
  const old = document.getElementById("notice");
  if (old) {
    old.remove();
  }
  const notice = document.createElement("div");
  notice.id = "notice";
  notice.className = `notice notice-${tone}`;
  notice.setAttribute("role", "status");
  notice.innerHTML = `
    <span class="notice-icon" aria-hidden="true">${
      tone === "success" ? "✓" : "!"
    }</span>
    <div class="notice-body">
      <strong>${escapeHtml(title || "")}</strong>
      <p>${escapeHtml(text || "")}</p>
    </div>
    <button class="notice-close" type="button" aria-label="Dismiss">&times;</button>`;
  document.body.appendChild(notice);
  requestAnimationFrame(() => notice.classList.add("is-visible"));

  const detach = () => {
    document.removeEventListener("pointerdown", onOutside, true);
    document.removeEventListener("keydown", onKey, true);
    clearTimeout(autoHide);
  };
  const hide = () => {
    if (!notice.isConnected) {
      return;
    }
    detach();
    notice.classList.remove("is-visible");
    setTimeout(() => {
      if (notice.isConnected) {
        notice.remove();
      }
    }, 220);
  };
  const onOutside = (event) => {
    if (!notice.contains(event.target)) {
      hide();
    }
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      hide();
    }
  };
  notice
    .querySelector(".notice-close")
    .addEventListener("click", hide);
  document.addEventListener("pointerdown", onOutside, true);
  document.addEventListener("keydown", onKey, true);
  const autoHide = setTimeout(hide, 9000);
}

/* Demo mode: this demo cannot use a real Stripe account (no verified
   business / country restrictions), so the frontend settles checkout
   through /api/payments/simulate/ with an in-app card form. The real
   flow only runs when this flag is false (payments/services.py -> start_checkout). */
const STRIPE_DEMO_MODE = true;

const CARD_DECLINES = {
  "4000000000000002": "Your card was declined.",
  "4000000000009995": "Your card has insufficient funds.",
  "4000000000000127": "Your card's security code is incorrect.",
};

function detectCardBrand(digits) {
  if (/^4/.test(digits)) return "visa";
  if (/^5[1-5]/.test(digits) || /^2[2-7]/.test(digits)) return "mastercard";
  if (/^3[47]/.test(digits)) return "amex";
  return "";
}

function luhnValid(digits) {
  let sum = 0;
  let alt = false;
  for (let i = digits.length - 1; i >= 0; i -= 1) {
    let n = Number(digits[i]);
    if (alt) {
      n *= 2;
      if (n > 9) n -= 9;
    }
    sum += n;
    alt = !alt;
  }
  return digits.length > 0 && sum % 10 === 0;
}

function formatCardNumber(value) {
  const digits = String(value).replace(/\D/g, "").slice(0, 19);
  if (/^3[47]/.test(digits)) {
    return [digits.slice(0, 4), digits.slice(4, 10), digits.slice(10, 15)]
      .filter(Boolean)
      .join(" ");
  }
  return digits.replace(/(.{4})/g, "$1 ").trim();
}

function formatCardExpiry(value) {
  const digits = String(value).replace(/\D/g, "").slice(0, 4);
  return digits.length > 2
    ? `${digits.slice(0, 2)} / ${digits.slice(2)}`
    : digits;
}

function expiryValid(expiryDigits) {
  if (expiryDigits.length < 4) {
    return false;
  }
  const month = Number(expiryDigits.slice(0, 2));
  const year = 2000 + Number(expiryDigits.slice(2, 4));
  if (month < 1 || month > 12) {
    return false;
  }
  const now = new Date();
  if (year < now.getFullYear()) {
    return false;
  }
  return !(year === now.getFullYear() && month < now.getMonth() + 1);
}

function checkoutDigits(id) {
  return (document.getElementById(id).value || "").replace(/\D/g, "");
}

function checkoutComplete() {
  const digits = checkoutDigits("card-number");
  const brand = detectCardBrand(digits);
  const minNumber = brand === "amex" ? 15 : 13;
  const minCvc = brand === "amex" ? 4 : 3;
  return (
    digits.length >= minNumber &&
    checkoutDigits("card-expiry").length === 4 &&
    checkoutDigits("card-cvc").length >= minCvc
  );
}

function setCheckoutFieldError(fieldId, message) {
  document.getElementById(fieldId).classList.add("is-error");
  const errorBox = document.getElementById("card-error");
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearCheckoutErrors() {
  ["card-number-field", "card-expiry-field", "card-cvc-field"].forEach((id) => {
    document.getElementById(id).classList.remove("is-error");
  });
  document.getElementById("card-error").hidden = true;
}

function renderCardBrands() {
  const digits = checkoutDigits("card-number");
  const brand = detectCardBrand(digits);
  const target = document.getElementById("card-brands");
  if (brand === "visa") {
    target.innerHTML = '<span class="brand-badge brand-visa">VISA</span>';
  } else if (brand === "mastercard") {
    target.innerHTML =
      '<svg class="brand-badge" viewBox="0 0 36 22" width="30" height="19" aria-hidden="true">' +
      '<circle cx="14" cy="11" r="9" fill="#EB001B"/>' +
      '<circle cx="22" cy="11" r="9" fill="#F79E1B" fill-opacity="0.9"/>' +
      "</svg>";
  } else if (brand === "amex") {
    target.innerHTML = '<span class="brand-badge brand-amex">AMEX</span>';
  } else {
    target.innerHTML = "";
  }
  document.getElementById("card-number").maxLength = brand === "amex" ? 17 : 19;
  document.getElementById("card-cvc").maxLength = brand === "amex" ? 4 : 3;
}

function updateCheckoutPayState() {
  const button = document.getElementById("sim-confirm");
  button.disabled =
    button.dataset.ready !== "true" || !checkoutComplete();
}

async function submitSimulatedPayment(closeSim) {
  const errorBox = document.getElementById("card-error");
  clearCheckoutErrors();
  const numberInput = document.getElementById("card-number");
  const cvcInput = document.getElementById("card-cvc");
  const digits = numberInput.value.replace(/\D/g, "");
  const expiry = checkoutDigits("card-expiry");
  const cvc = cvcInput.value.replace(/\D/g, "");
  const brand = detectCardBrand(digits);
  const minNumber = brand === "amex" ? 15 : 13;
  const minCvc = brand === "amex" ? 4 : 3;

  if (digits.length < minNumber) {
    setCheckoutFieldError(
      "card-number-field",
      "Your card number is incomplete."
    );
    return;
  }
  if (!luhnValid(digits)) {
    setCheckoutFieldError("card-number-field", "Your card number is invalid.");
    return;
  }
  if (expiry.length < 4) {
    setCheckoutFieldError(
      "card-expiry-field",
      "Your card's expiration date is incomplete."
    );
    return;
  }
  if (!expiryValid(expiry)) {
    setCheckoutFieldError(
      "card-expiry-field",
      "Your card's expiration date is invalid."
    );
    return;
  }
  if (cvc.length < minCvc) {
    setCheckoutFieldError(
      "card-cvc-field",
      "Your card's security code is incomplete."
    );
    return;
  }
  const decline = CARD_DECLINES[digits];
  if (decline) {
    setCheckoutFieldError("card-number-field", decline);
    cvcInput.value = "";
    updateCheckoutPayState();
    return;
  }

  const button = document.getElementById("sim-confirm");
  const spinner = document.getElementById("pay-spinner");
  const payText = document.getElementById("pay-text");
  const originalLabel = payText.textContent;
  button.disabled = true;
  spinner.hidden = false;
  payText.textContent = "Processing…";
  await new Promise((resolve) => setTimeout(resolve, 900));

  try {
    const modal = document.getElementById("sim-checkout-modal");
    const response = await apiFetch("/payments/simulate/", {
      method: "POST",
      body: {
        booking: Number(modal.dataset.booking),
        kind: modal.dataset.kind,
      },
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      spinner.hidden = true;
      payText.textContent = originalLabel;
      updateCheckoutPayState();
      return;
    }
    closeSim();
    showToast("Payment successful. Refreshing...");
    window.setTimeout(() => window.location.reload(), 1200);
  } catch (error) {
    console.error(error);
    showToast("Could not reach the API.");
    spinner.hidden = true;
    payText.textContent = originalLabel;
    updateCheckoutPayState();
  }
}

function openSimulatedCheckout(bookingId, kind, details = {}) {
  const closeSim = () => {
    const current = document.getElementById("sim-checkout-modal");
    if (current) {
      current.hidden = true;
    }
    document.body.style.overflow = "";
  };
  let modal = document.getElementById("sim-checkout-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "sim-checkout-modal";
    modal.className = "modal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="modal-panel checkout-panel">
        <button class="modal-close" id="sim-checkout-close" type="button" aria-label="Close">&times;</button>
        <p class="checkout-kicker">
          <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M12 7V5a4 4 0 0 0-8 0v2H3a1 1 0 0 0-1 1v5a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1h-1zm-7-2a2.5 2.5 0 0 1 5 0v2H5V5z"/></svg>
          Secure checkout
        </p>
        <div class="sim-rows">
          <div class="kv"><span>Booking</span><strong id="sim-booking"></strong></div>
          <div class="kv"><span>Type</span><strong id="sim-kind"></strong></div>
          <div class="kv"><span>Amount</span><strong id="sim-amount">Loading...</strong></div>
        </div>
        <form id="card-form" novalidate>
          <label class="checkout-label">Card information</label>
          <div class="card-field" id="card-number-field">
            <input id="card-number" inputmode="numeric" autocomplete="cc-number" placeholder="1234 1234 1234 1234" maxlength="19" />
            <span class="card-brands" id="card-brands"></span>
          </div>
          <div class="card-field-row">
            <div class="card-field" id="card-expiry-field">
              <input id="card-expiry" inputmode="numeric" autocomplete="cc-exp" placeholder="MM / YY" maxlength="7" />
            </div>
            <div class="card-field" id="card-cvc-field">
              <input id="card-cvc" inputmode="numeric" autocomplete="cc-csc" placeholder="CVC" maxlength="3" />
            </div>
          </div>
          <p id="card-error" class="checkout-error" hidden></p>
          <button class="btn btn-block btn-pay" id="sim-confirm" type="submit" data-ready="false" disabled>
            <span class="pay-spinner" id="pay-spinner" hidden></span>
            <span id="pay-text">Pay</span>
          </button>
        </form>
        <p class="checkout-foot">
          <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true"><path fill="currentColor" d="M12 7V5a4 4 0 0 0-8 0v2H3a1 1 0 0 0-1 1v5a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1h-1zM5 5a3 3 0 0 1 6 0v2H5V5z"/></svg>
          Payments are secure and encrypted
        </p>
      </div>`;
    document.body.appendChild(modal);

    modal.addEventListener("click", (event) => {
      if (
        event.target === modal ||
        event.target.closest("#sim-checkout-close")
      ) {
        closeSim();
      }
    });
    document.addEventListener("keydown", (event) => {
      const current = document.getElementById("sim-checkout-modal");
      if (event.key === "Escape" && current && !current.hidden) {
        closeSim();
      }
    });

    const numberInput = document.getElementById("card-number");
    const expiryInput = document.getElementById("card-expiry");
    const cvcInput = document.getElementById("card-cvc");
    numberInput.addEventListener("input", () => {
      numberInput.value = formatCardNumber(numberInput.value);
      renderCardBrands();
      clearCheckoutErrors();
      updateCheckoutPayState();
    });
    expiryInput.addEventListener("input", () => {
      expiryInput.value = formatCardExpiry(expiryInput.value);
      clearCheckoutErrors();
      updateCheckoutPayState();
    });
    cvcInput.addEventListener("input", () => {
      cvcInput.value = cvcInput.value.replace(/\D/g, "");
      clearCheckoutErrors();
      updateCheckoutPayState();
    });
    document
      .getElementById("card-form")
      .addEventListener("submit", async (event) => {
        event.preventDefault();
        await submitSimulatedPayment(closeSim);
      });
  }

  modal.dataset.booking = String(bookingId);
  modal.dataset.kind = kind;
  document.getElementById("sim-booking").textContent =
    details.title || `#${bookingId}`;
  document.getElementById("sim-kind").textContent =
    kind === "balance" ? "Remaining balance (80%)" : "Deposit (20%)";
  document.getElementById("card-number").value = "";
  document.getElementById("card-expiry").value = "";
  document.getElementById("card-cvc").value = "";
  renderCardBrands();
  clearCheckoutErrors();
  const confirm = document.getElementById("sim-confirm");
  confirm.dataset.ready = "false";
  confirm.disabled = true;
  document.getElementById("pay-spinner").hidden = true;
  document.getElementById("pay-text").textContent = "Pay";
  const amountEl = document.getElementById("sim-amount");
  amountEl.textContent = "Loading...";
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  document.getElementById("card-number").focus();
  apiFetch(
    `/payments/simulate/?booking=${encodeURIComponent(
      bookingId
    )}&kind=${encodeURIComponent(kind)}`
  )
    .then(async (response) => {
      if (!response.ok) {
        showToast(await readError(response));
        closeSim();
        return;
      }
      const data = await response.json();
      const amountText = `$${(Number(data.amount_cents) / 100).toFixed(2)}`;
      amountEl.textContent = amountText;
      confirm.dataset.ready = "true";
      document.getElementById("pay-text").textContent = `Pay ${amountText}`;
      updateCheckoutPayState();
    })
    .catch((error) => {
      console.error(error);
      showToast("Could not reach the API.");
      closeSim();
    });
}

const STATUS_LABELS = {
  requested: "requested",
  awaiting_payment: "awaiting payment",
  accepted: "accepted",
  completed: "completed",
  rejected: "rejected",
  cancelled: "cancelled",
  refunded: "refunded",
};

const CANCELLATION_POLICY_LABELS = {
  flexible: "Flexible",
  moderate: "Moderate",
  strict: "Strict",
};

const CANCELLATION_POLICY_TEXTS = {
  flexible:
    "Cancel at least 48 hours before the shoot and your deposit is " +
    "refunded in full to your original payment method. Cancellations " +
    "inside the last 48 hours keep the deposit.",
  moderate:
    "Cancel at least 7 days before the shoot and 50% of your deposit is " +
    "refunded. Cancellations inside the last 7 days keep the deposit.",
  strict:
    "The deposit is non-refundable once the booking is confirmed, " +
    "regardless of when you cancel.",
};

function cancellationPolicyLabel(policy) {
  return CANCELLATION_POLICY_LABELS[policy] || "Moderate";
}

function moneyLabel(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return "$0";
  }
  return amount % 1 === 0 ? `$${amount.toFixed(0)}` : `$${amount.toFixed(2)}`;
}

function priceRangeLabel(min, max) {
  const minLabel = moneyLabel(min);
  const maxValue =
    max === null || max === undefined || max === "" ? null : Number(max);
  if (
    maxValue === null ||
    !Number.isFinite(maxValue) ||
    maxValue <= Number(min)
  ) {
    return minLabel;
  }
  return `${minLabel} – ${moneyLabel(maxValue)}`;
}

function statusChip(status) {
  const label = STATUS_LABELS[status] || status;
  return `<span class="status-chip status-${escapeHtml(
    status
  )}">${escapeHtml(label)}</span>`;
}

function starsHtml(rating) {
  const value = Math.min(5, Math.max(0, Math.round(Number(rating) || 0)));
  const full = "★".repeat(value);
  const empty = "☆".repeat(5 - value);
  return `<span class="stars" title="${value} of 5">${full}${empty}</span>`;
}

function formatDate(value, { withTime = false } = {}) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return withTime
    ? date.toLocaleString()
    : date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
}

/* Wire the header log in / sign up / log out buttons present on every page.
   Returns { update } to refresh the visible state after auth changes. */
const headerUpdaters = [];

function notifyHeader() {
  headerUpdaters.forEach((update) => update());
}

function initHeader({ onLogin, onSignup } = {}) {
  const btnLogin = document.getElementById("btn-login");
  const btnSignup = document.getElementById("btn-signup");
  const btnLogout = document.getElementById("btn-logout");
  const authUser = document.getElementById("auth-user");
  const authUsername = document.getElementById("auth-username");
  const authStatus = document.getElementById("auth-status");
  const navPhotos = document.querySelector("[data-nav-photos]");
  const navPublic = document.querySelector("[data-nav-public]");
  const navDash = document.querySelector("[data-nav-dash]");
  const onIndex =
    window.location.pathname.endsWith("index.html") ||
    window.location.pathname === "/" ||
    window.location.pathname === "";
  const onDashboard = window.location.pathname.endsWith("dashboard.html");

  const update = () => {
    const logged = isLoggedIn();
    if (btnLogin) {
      btnLogin.hidden = logged;
    }
    if (btnSignup) {
      btnSignup.hidden = logged;
    }
    if (authUser) {
      authUser.hidden = !logged;
    }
    if (authUsername) {
      authUsername.textContent = localStorage.getItem(STORAGE.username) || "";
    }
    if (authStatus) {
      authStatus.textContent = "";
    }
    if (navPhotos && navPublic) {
      const isPhotographer =
        localStorage.getItem(STORAGE.role) === "photographer";
      navPhotos.hidden = isPhotographer;
      navPublic.hidden = !isPhotographer || onIndex;
    }
    if (navDash) {
      const isCustomer = localStorage.getItem(STORAGE.role) === "customer";
      navDash.textContent = isCustomer ? "My Bookings" : "Dashboard";
      // Already on the dashboard: the link would only point at itself.
      navDash.hidden = onDashboard;
    }
  };

  if (btnLogin) {
    btnLogin.addEventListener("click", () => {
      if (onLogin) {
        onLogin();
      } else {
        window.location.href = "index.html?login=1";
      }
    });
  }
  if (btnSignup) {
    btnSignup.addEventListener("click", () => {
      if (onSignup) {
        onSignup();
      } else {
        window.location.href = "index.html?register=1";
      }
    });
  }
  if (btnLogout) {
    btnLogout.addEventListener("click", () => {
      clearSession();
      if (onIndex) {
        update();
      } else {
        window.location.href = "index.html";
      }
    });
  }
  headerUpdaters.push(update);
  update();
  initBell();
  return { update };
}

/* Header bell: unread badge + floating panel with the 3 latest items.
   refreshBellBadge() lets other pages (the dashboard) re-sync the badge. */
function refreshBellBadge() {}
function initBell() {
  const area = document.getElementById("bell-area");
  if (!area) {
    return;
  }
  const button = document.getElementById("btn-bell");
  const panel = document.getElementById("bell-panel");
  const badge = document.getElementById("bell-badge");
  const list = document.getElementById("bell-list");
  let badgeLoaded = false;

  const close = () => {
    panel.hidden = true;
    button.setAttribute("aria-expanded", "false");
  };

  async function loadBadge() {
    if (!isLoggedIn()) {
      badge.hidden = true;
      return;
    }
    try {
      const response = await apiFetch("/notifications/?unread=1", {
        silentAuth: true,
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      const count = data.count || 0;
      badge.hidden = count === 0;
      badge.textContent = count > 9 ? "9+" : String(count);
    } catch (error) {
      console.error(error);
    }
  }

  async function loadPanel() {
    list.innerHTML = '<p class="meta">Loading…</p>';
    try {
      const response = await apiFetch("/notifications/", {
        silentAuth: true,
      });
      if (!response.ok) {
        list.innerHTML = '<p class="meta">Could not load notifications.</p>';
        return;
      }
      const data = await response.json();
      const items = (data.results || []).slice(0, 3);
      if (items.length === 0) {
        list.innerHTML = '<p class="meta">No notifications yet.</p>';
        return;
      }
      list.innerHTML = items
        .map(
          (item) => `
        <${
          item.link ? "a" : "div"
        } class="bell-item${item.is_read ? "" : " is-unread"}"${
          item.link
            ? ` href="${escapeHtml(item.link)}" data-note-id="${item.id}"`
            : ` data-note-id="${item.id}"`
        }>
          <strong>${escapeHtml(item.title)}</strong>
          ${
            item.message
              ? `<span class="meta">${escapeHtml(item.message)}</span>`
              : ""
          }
          <span class="meta bell-time">${formatDate(item.created_at, {
            withTime: true,
          })}</span>
        </${item.link ? "a" : "div"}>`
        )
        .join("");
    } catch (error) {
      console.error(error);
      list.innerHTML = '<p class="meta">Could not load notifications.</p>';
    }
  }

  list.addEventListener("click", async (event) => {
    const item = event.target.closest("[data-note-id]");
    if (!item) {
      return;
    }
    const href = item.getAttribute("href");
    if (href) {
      // Follow the deep link once the notification counts are clean.
      event.preventDefault();
      if (typeof window.lumenNavigate === "function") {
        // Already on the dashboard: switch tabs without a reload.
        window.lumenNavigate(href);
        panel.hidden = true;
        button.setAttribute("aria-expanded", "false");
        loadPanel();
      } else {
        window.location.href = href;
      }
    } else {
      await apiFetch(`/notifications/${item.dataset.noteId}/read/`, {
        method: "POST",
        silentAuth: true,
      }).catch(() => null);
      loadBadge();
    }
  });

  button.addEventListener("click", async (event) => {
    event.stopPropagation();
    const opening = panel.hidden;
    panel.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
    if (opening) {
      loadPanel();
      // Seeing the notifications marks them read: the badge must clear.
      try {
        await apiFetch("/notifications/read-all/", {
          method: "POST",
          silentAuth: true,
        });
        document.dispatchEvent(new CustomEvent("notifications:read"));
      } catch (error) {
        console.error(error);
      }
      loadBadge();
    }
  });
  document.addEventListener("click", (event) => {
    if (!panel.hidden && !area.contains(event.target)) {
      close();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) {
      close();
    }
  });

  /* Live badge: the notifications WebSocket pushes a message whenever a
     notification is created (chat messages, offers, payments…). Refresh the
     badge and let the page react through the `notifications:push` event. */
  let badgeSocket = null;
  function connectBadgeSocket() {
    if (!isLoggedIn() || badgeSocket) {
      return;
    }
    const token = getAccess();
    if (!token) {
      return;
    }
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    try {
      badgeSocket = new WebSocket(
        `${protocol}://${
          window.location.host
        }/ws/notifications/?token=${encodeURIComponent(token)}`
      );
    } catch (error) {
      badgeSocket = null;
      return;
    }
    badgeSocket.onmessage = () => {
      loadBadge();
      document.dispatchEvent(new CustomEvent("notifications:push"));
    };
    badgeSocket.onclose = () => {
      badgeSocket = null;
      if (isLoggedIn()) {
        window.setTimeout(connectBadgeSocket, 5000);
      }
    };
    badgeSocket.onerror = () => {
      try {
        badgeSocket.close();
      } catch (error) {
        badgeSocket = null;
      }
    };
  }

  const sync = () => {
    const logged = isLoggedIn();
    area.hidden = !logged;
    if (!logged) {
      close();
      badge.hidden = true;
      badgeLoaded = false;
    } else if (!badgeLoaded) {
      badgeLoaded = true;
      loadBadge();
      connectBadgeSocket();
    }
  };
  headerUpdaters.push(sync);
  sync();
  refreshBellBadge = loadBadge;
}

/* Redirect to the login screen unless a session exists.
   The current page travels as `next` so login returns here. */
function requireLogin() {
  if (isLoggedIn()) {
    return true;
  }
  const page = window.location.pathname.split("/").pop();
  const next = `${page}${window.location.search}`;
  window.location.href = `index.html?login=1${
    next ? `&next=${encodeURIComponent(next)}` : ""
  }`;
  return false;
}

let meCache = null;

/* The current user (with profile) or null. Cached per page. */
async function fetchMe({ force = false } = {}) {
  if (meCache && !force) {
    return meCache;
  }
  if (!getAccess()) {
    return null;
  }
  try {
    const response = await apiFetch("/auth/me/", { silentAuth: true });
    if (!response.ok) {
      meCache = null;
      return null;
    }
    meCache = await response.json();
    if (meCache && meCache.role) {
      localStorage.setItem(STORAGE.role, meCache.role);
      notifyHeader();
    }
    return meCache;
  } catch (error) {
    console.error(error);
    return null;
  }
}

/* --------------------------- welcome modal ------------------------------ */

const WELCOME_ICONS = {
  camera:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 13l2.4-4.2h9.2L31 13h7a3 3 0 0 1 3 3v17a3 3 0 0 1-3 3H10a3 3 0 0 1-3-3V16a3 3 0 0 1 3-3h7z"/><circle cx="24" cy="25" r="7.5"/></svg>',
  user:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="17" r="8"/><path d="M9 40c0-7.7 6.7-14 15-14s15 6.3 15 14"/></svg>',
};

/* First-time product tour for this account. Shown the first time the user
   opens dashboard.html (localStorage `lumen_tour_seen_<username>`).
   Returns true when the modal is on screen. `onGo` runs on the CTA click. */
function showWelcomeOnce({ username, role, name, onGo } = {}) {
  if (!username) {
    return false;
  }
  const key = `lumen_tour_seen_${username}`;
  try {
    if (localStorage.getItem(key)) {
      return false;
    }
    localStorage.setItem(key, "1");
  } catch (error) {
    console.error(error);
  }
  const isPhotographer = role === "photographer";
  const title = isPhotographer
    ? `Welcome to your Studio, ${name || username}`
    : `Welcome to Lumen, ${name || username}`;
  const text = isPhotographer
    ? "This is your command center. Here you can manage your bookings, chat and negotiate with clients, manage your portfolio, and track your earnings. Let's get your business running!"
    : "From here you can track your bookings, chat directly with photographers to negotiate details, manage your payments, and download your final photos securely.";
  const buttonLabel = isPhotographer
    ? "Start working"
    : "Explore my bookings";
  const icon = isPhotographer ? WELCOME_ICONS.camera : WELCOME_ICONS.user;

  const modal = document.createElement("div");
  modal.id = "welcome-modal";
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-panel modal-welcome">
      <div class="welcome-hero" aria-hidden="true">${icon}</div>
      <h2 id="welcome-title"></h2>
      <p class="welcome-text">${escapeHtml(text)}</p>
      <button class="btn btn-block" id="welcome-go" type="button">${escapeHtml(
        buttonLabel
      )}</button>
    </div>`;
  document.body.appendChild(modal);
  modal.querySelector("#welcome-title").textContent = title;
  const close = () => {
    modal.remove();
  };
  modal.querySelector("#welcome-go").addEventListener("click", () => {
    if (typeof onGo === "function") {
      onGo();
    }
    close();
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      close();
    }
  });
  modal.hidden = false;
  return true;
}
