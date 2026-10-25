const API = "http://127.0.0.1:8000/api";

const STORAGE = {
  access: "lumen_access",
  refresh: "lumen_refresh",
  username: "lumen_username",
};

const grid = document.getElementById("grid");
const status = document.getElementById("status");
const loadMoreBtn = document.getElementById("load-more");

const btnLogin = document.getElementById("btn-login");
const btnLogout = document.getElementById("btn-logout");
const authUser = document.getElementById("auth-user");
const authUsername = document.getElementById("auth-username");
const authStatus = document.getElementById("auth-status");
const loginModal = document.getElementById("login-modal");
const loginForm = document.getElementById("login-form");
const loginClose = document.getElementById("login-close");
const loginError = document.getElementById("login-error");

let nextUrl = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function cardHtml(profile) {
  const name = profile.studio_name || profile.username;
  const initial = (name || "?").charAt(0).toUpperCase();
  const planBadge =
    profile.plan === "pro" ? '<span class="badge badge-pro">PRO</span>' : "";
  const chips = (profile.specialties || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");

  return `
    <article class="card">
      <div class="card-top">
        <div class="avatar">${escapeHtml(initial)}</div>
        ${planBadge}
      </div>
      <h2>${escapeHtml(name)}</h2>
      <p class="meta">${escapeHtml(profile.city || "Location not set")} · @${escapeHtml(
        profile.username
      )}</p>
      <p class="bio">${escapeHtml(
        profile.bio || "This photographer has not added a bio yet."
      )}</p>
      <div class="chips">${chips}</div>
    </article>`;
}

async function loadPage(url) {
  status.hidden = false;
  status.textContent = "Loading photographers…";
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    const results = Array.isArray(data) ? data : data.results || [];

    results.forEach((profile) => {
      grid.insertAdjacentHTML("beforeend", cardHtml(profile));
    });

    nextUrl = data.next || null;
    loadMoreBtn.hidden = !nextUrl;

    if (grid.children.length === 0) {
      status.textContent = "No photographers published yet.";
    } else {
      status.hidden = true;
    }
  } catch (error) {
    status.hidden = false;
    status.textContent =
      "Could not reach the API. Is daphne running on port 8000?";
    console.error(error);
  }
}

function openLogin() {
  loginError.hidden = true;
  loginModal.hidden = false;
  document.getElementById("login-username").focus();
}

function closeLogin() {
  loginModal.hidden = true;
  loginForm.reset();
}

function updateAuthUI() {
  const username = localStorage.getItem(STORAGE.username);
  const loggedIn = Boolean(username && localStorage.getItem(STORAGE.access));
  btnLogin.hidden = loggedIn;
  authUser.hidden = !loggedIn;
  authStatus.textContent = "";
  if (loggedIn) {
    authUsername.textContent = username;
  }
}

async function verifyToken() {
  const access = localStorage.getItem(STORAGE.access);
  if (!access) {
    return;
  }
  try {
    const response = await fetch(`${API}/notifications/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    if (response.ok) {
      authStatus.textContent = " · JWT ✓";
    } else {
      localStorage.removeItem(STORAGE.access);
      localStorage.removeItem(STORAGE.refresh);
      updateAuthUI();
    }
  } catch (error) {
    console.error(error);
  }
}

async function handleLogin(event) {
  event.preventDefault();
  loginError.hidden = true;
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const response = await fetch(`${API}/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      loginError.textContent =
        response.status === 401 || response.status === 400
          ? "Invalid username or password."
          : `Login failed (HTTP ${response.status}).`;
      loginError.hidden = false;
      return;
    }

    const data = await response.json();
    localStorage.setItem(STORAGE.access, data.access);
    localStorage.setItem(STORAGE.refresh, data.refresh || "");
    localStorage.setItem(STORAGE.username, username);
    closeLogin();
    updateAuthUI();
    verifyToken();
  } catch (error) {
    loginError.textContent = "Could not reach the API. Is daphne running?";
    loginError.hidden = false;
    console.error(error);
  }
}

function handleLogout() {
  localStorage.removeItem(STORAGE.access);
  localStorage.removeItem(STORAGE.refresh);
  localStorage.removeItem(STORAGE.username);
  updateAuthUI();
}

btnLogin.addEventListener("click", openLogin);
btnLogout.addEventListener("click", handleLogout);
loginClose.addEventListener("click", closeLogin);
loginModal.addEventListener("click", (event) => {
  if (event.target === loginModal) {
    closeLogin();
  }
});
loginForm.addEventListener("submit", handleLogin);
loadMoreBtn.addEventListener("click", () => {
  if (nextUrl) {
    loadPage(nextUrl);
  }
});

updateAuthUI();
verifyToken();
loadPage(`${API}/profiles/`);
