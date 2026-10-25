const API = "http://127.0.0.1:8000/api";

const STORAGE = {
  access: "lumen_access",
  refresh: "lumen_refresh",
  username: "lumen_username",
};

const gate = document.getElementById("gate");
const dash = document.getElementById("dash");
const dashStatus = document.getElementById("dash-status");
const dashContent = document.getElementById("dash-content");
const btnLogin = document.getElementById("btn-login");
const btnLogout = document.getElementById("btn-logout");
const btnGoLogin = document.getElementById("btn-go-login");
const authUser = document.getElementById("auth-user");
const authUsername = document.getElementById("auth-username");

function clearSession() {
  localStorage.removeItem(STORAGE.access);
  localStorage.removeItem(STORAGE.refresh);
  localStorage.removeItem(STORAGE.username);
}

function showGate() {
  gate.hidden = false;
  dash.hidden = true;
  btnLogin.hidden = false;
  authUser.hidden = true;
}

function showDash(username) {
  gate.hidden = true;
  dash.hidden = false;
  btnLogin.hidden = true;
  authUser.hidden = false;
  authUsername.textContent = username;
}

function renderMe(me) {
  document.getElementById("me-username").textContent = me.username;
  document.getElementById("me-email").textContent = me.email;
  document.getElementById("me-role").textContent = me.role;

  if (me.profile) {
    document.getElementById("profile-panel").hidden = false;
    document.getElementById("me-studio").textContent =
      me.profile.studio_name || "—";
    document.getElementById("me-city").textContent = me.profile.city || "—";
    document.getElementById("me-plan").textContent = me.profile.plan;
    document.getElementById("me-published").textContent = me.profile
      .is_published
      ? "Yes"
      : "No";
    const chips = document.getElementById("me-chips");
    chips.innerHTML = (me.profile.specialties || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
      .join("");
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderNotifications(data) {
  document.getElementById("notif-count").textContent = String(data.count);
  const list = document.getElementById("notif-list");
  if (!data.results || data.results.length === 0) {
    list.innerHTML = '<p class="meta">No notifications yet.</p>';
    return;
  }
  list.innerHTML = data.results
    .map(
      (item) => `
      <div class="notif ${item.is_read ? "" : "unread"}">
        <div class="n-title">${escapeHtml(item.title)}</div>
        <div class="n-msg">${escapeHtml(item.message)}</div>
        <div class="n-date">${new Date(item.created_at).toLocaleString()}</div>
      </div>`
    )
    .join("");
}

async function loadNotifications(access) {
  try {
    const response = await fetch(`${API}/notifications/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    if (response.ok) {
      renderNotifications(await response.json());
    }
  } catch (error) {
    console.error(error);
  }
}

async function init() {
  const access = localStorage.getItem(STORAGE.access);
  if (!access) {
    showGate();
    return;
  }

  try {
    const response = await fetch(`${API}/auth/me/`, {
      headers: { Authorization: `Bearer ${access}` },
    });

    if (response.status === 401) {
      clearSession();
      showGate();
      return;
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const me = await response.json();
    renderMe(me);
    showDash(me.username);
    dashStatus.hidden = true;
    dashContent.hidden = false;
    await loadNotifications(access);
  } catch (error) {
    console.error(error);
    dashStatus.hidden = false;
    dashStatus.textContent =
      "Could not reach the API. Is daphne running on port 8000?";
    dash.hidden = false;
    gate.hidden = true;
    btnLogin.hidden = true;
    authUser.hidden = false;
    authUsername.textContent = localStorage.getItem(STORAGE.username) || "";
  }
}

btnGoLogin.addEventListener("click", () => {
  window.location.href = "index.html?login=1";
});
btnLogin.addEventListener("click", () => {
  window.location.href = "index.html?login=1";
});
btnLogout.addEventListener("click", () => {
  clearSession();
  window.location.href = "index.html";
});

init();
