const grid = document.getElementById("grid");
const status = document.getElementById("status");
const loadMoreBtn = document.getElementById("load-more");
const searchForm = document.getElementById("search-form");
const searchCity = document.getElementById("search-city");
const searchSpecialty = document.getElementById("search-specialty");
const searchClear = document.getElementById("search-clear");

const authStatus = document.getElementById("auth-status");
const loginModal = document.getElementById("login-modal");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginClose = document.getElementById("login-close");
const loginError = document.getElementById("login-error");
const registerError = document.getElementById("register-error");

let nextUrl = null;

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
    <a class="card-link" href="profile.html?slug=${encodeURIComponent(profile.slug)}">
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
      </article>
    </a>`;
}

function listUrl() {
  const params = new URLSearchParams();
  const city = searchCity.value.trim();
  const specialty = searchSpecialty.value.trim();
  if (city) {
    params.set("city", city);
  }
  if (specialty) {
    params.set("specialty", specialty);
  }
  const query = params.toString();
  searchClear.hidden = !query;
  return `${API}/profiles/${query ? `?${query}` : ""}`;
}

async function loadPage(url, { replace = false } = {}) {
  if (replace) {
    grid.innerHTML = "";
  }
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
      status.textContent = "No photographers match your search.";
    } else {
      status.hidden = true;
    }
  } catch (error) {
    status.hidden = false;
    status.textContent =
      "Could not reach the API. Is the server running on port 8000?";
    console.error(error);
  }
}

function switchAuthTab(tab) {
  document.querySelectorAll(".modal-tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.authTab === tab);
  });
  document.querySelectorAll("[data-auth-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.authPanel !== tab;
  });
}

function openAuth(tab = "login") {
  loginError.hidden = true;
  registerError.hidden = true;
  switchAuthTab(tab);
  loginModal.hidden = false;
  const firstInput = loginModal.querySelector(
    `[data-auth-panel="${tab}"] input`
  );
  if (firstInput) {
    firstInput.focus();
  }
}

function closeAuth() {
  loginModal.hidden = true;
  loginForm.reset();
  registerForm.reset();
}

async function verifyToken() {
  if (!isLoggedIn() || !authStatus) {
    return;
  }
  try {
    const response = await apiFetch("/notifications/", { silentAuth: true });
    if (response.ok) {
      authStatus.textContent = " · JWT ✓";
    } else {
      header.update();
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
    meCache = null;
    saveSession({ access: data.access, refresh: data.refresh, username });
    closeAuth();
    header.update();
    verifyToken();
    showToast(`Welcome back, ${username}!`);
    const me = await fetchMe().catch(() => null);
    if (me && me.role === "photographer") {
      window.location.href = "dashboard.html";
    }
  } catch (error) {
    loginError.textContent = "Could not reach the API. Is the server running?";
    loginError.hidden = false;
    console.error(error);
  }
}

async function handleRegister(event) {
  event.preventDefault();
  registerError.hidden = true;
  const username = document.getElementById("reg-username").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const password = document.getElementById("reg-password").value;
  const role = document.getElementById("reg-role").value;

  try {
    const response = await fetch(`${API}/auth/register/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, role }),
    });
    if (!response.ok) {
      registerError.textContent = await readError(response);
      registerError.hidden = false;
      return;
    }

    // Sign the new account in automatically.
    const login = await fetch(`${API}/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (login.ok) {
      const data = await login.json();
      meCache = null;
      saveSession({
        access: data.access,
        refresh: data.refresh,
        username,
        role,
      });
      fetchMe().catch(() => null);
    }
    closeAuth();
    header.update();
    verifyToken();
    if (login.ok && role === "photographer") {
      window.location.href = "dashboard.html";
      return;
    }
    showToast(
      role === "photographer"
        ? "Account created! Set up your studio from the dashboard."
        : "Account created! Pick a photographer and book your first session."
    );
  } catch (error) {
    registerError.textContent =
      "Could not reach the API. Is the server running?";
    registerError.hidden = false;
    console.error(error);
  }
}

const header = initHeader({
  onLogin: () => openAuth("login"),
  onSignup: () => openAuth("register"),
});

loginClose.addEventListener("click", closeAuth);
loginModal.addEventListener("click", (event) => {
  if (event.target === loginModal) {
    closeAuth();
  }
});
document.querySelectorAll(".modal-tab").forEach((button) => {
  button.addEventListener("click", () => switchAuthTab(button.dataset.authTab));
});
loginForm.addEventListener("submit", handleLogin);
registerForm.addEventListener("submit", handleRegister);

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadPage(listUrl(), { replace: true });
});
searchClear.addEventListener("click", () => {
  searchCity.value = "";
  searchSpecialty.value = "";
  loadPage(listUrl(), { replace: true });
});
loadMoreBtn.addEventListener("click", () => {
  if (nextUrl) {
    loadPage(nextUrl);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !loginModal.hidden) {
    closeAuth();
  }
});

header.update();
verifyToken();
loadPage(listUrl());

const auto = new URLSearchParams(window.location.search);
if (!isLoggedIn() && auto.get("register") === "1") {
  openAuth("register");
  history.replaceState(null, "", "index.html");
} else if (!isLoggedIn() && auto.get("login") === "1") {
  openAuth("login");
  history.replaceState(null, "", "index.html");
}
