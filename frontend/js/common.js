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

const STATUS_LABELS = {
  pending: "pending",
  accepted: "accepted",
  accepted_pending_deposit: "awaiting deposit",
  confirmed: "confirmed",
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
  const onIndex =
    window.location.pathname.endsWith("index.html") ||
    window.location.pathname === "/" ||
    window.location.pathname === "";

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
      navPublic.hidden = !isPhotographer;
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

/* Header bell: unread badge + floating panel with the 3 latest items. */
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
        <div class="bell-item${item.is_read ? "" : " is-unread"}">
          <strong>${escapeHtml(item.title)}</strong>
          ${
            item.message
              ? `<span class="meta">${escapeHtml(item.message)}</span>`
              : ""
          }
          <span class="meta bell-time">${formatDate(item.created_at, {
            withTime: true,
          })}</span>
        </div>`
        )
        .join("");
    } catch (error) {
      console.error(error);
      list.innerHTML = '<p class="meta">Could not load notifications.</p>';
    }
  }

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    const opening = panel.hidden;
    panel.hidden = !opening;
    button.setAttribute("aria-expanded", String(opening));
    if (opening) {
      loadPanel();
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
    }
  };
  headerUpdaters.push(sync);
  sync();
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
