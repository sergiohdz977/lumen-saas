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

/* Demo mode: this demo cannot use a real Stripe account (no verified
   business / country restrictions), so the frontend simulates checkout
   through /api/payments/simulate/. The real flow only runs when this
   flag is false (payments/services.py -> start_checkout). */
const STRIPE_DEMO_MODE = true;

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
      <div class="modal-panel">
        <button class="modal-close" id="sim-checkout-close" type="button" aria-label="Close">&times;</button>
        <h3>Simulated Stripe Checkout</h3>
        <div class="sim-rows">
          <div class="kv"><span>Booking</span><strong id="sim-booking"></strong></div>
          <div class="kv"><span>Type</span><strong id="sim-kind"></strong></div>
          <div class="kv"><span>Amount to pay</span><strong id="sim-amount">Loading...</strong></div>
        </div>
        <p class="meta">No card is charged. The payment is settled inside Lumen for the demo.</p>
        <div class="form-actions">
          <button class="btn" id="sim-confirm" type="button" disabled>Simulate Successful Payment</button>
        </div>
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
    document
      .getElementById("sim-confirm")
      .addEventListener("click", async () => {
        const button = document.getElementById("sim-confirm");
        button.disabled = true;
        try {
          const response = await apiFetch("/payments/simulate/", {
            method: "POST",
            body: {
              booking: Number(modal.dataset.booking),
              kind: modal.dataset.kind,
            },
          });
          if (!response.ok) {
            showToast(await readError(response));
            button.disabled = false;
            return;
          }
          closeSim();
          showToast("Payment simulated successfully. Refreshing...");
          window.setTimeout(() => window.location.reload(), 1200);
        } catch (error) {
          console.error(error);
          showToast("Could not reach the API.");
          button.disabled = false;
        }
      });
  }
  modal.dataset.booking = String(bookingId);
  modal.dataset.kind = kind;
  document.getElementById("sim-booking").textContent =
    details.title || `#${bookingId}`;
  document.getElementById("sim-kind").textContent =
    kind === "balance" ? "Remaining balance (80%)" : "Deposit (20%)";
  const amountEl = document.getElementById("sim-amount");
  amountEl.textContent = "Loading...";
  const confirm = document.getElementById("sim-confirm");
  confirm.disabled = true;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  confirm.focus();
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
      amountEl.textContent = `$${(Number(data.amount_cents) / 100).toFixed(2)}`;
      confirm.disabled = false;
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
};

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

/* Redirect to the login screen unless a session exists. */
function requireLogin() {
  if (isLoggedIn()) {
    return true;
  }
  window.location.href = "index.html?login=1";
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
