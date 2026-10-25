const API = "http://127.0.0.1:8000/api";

const STORAGE = {
  access: "lumen_access",
  refresh: "lumen_refresh",
  username: "lumen_username",
};

const params = new URLSearchParams(window.location.search);
const slug = params.get("slug");

const statusEl = document.getElementById("profile-status");
const view = document.getElementById("profile-view");
const btnLogin = document.getElementById("btn-login");
const btnLogout = document.getElementById("btn-logout");
const authUser = document.getElementById("auth-user");
const authUsername = document.getElementById("auth-username");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function initSession() {
  const username = localStorage.getItem(STORAGE.username);
  const loggedIn = Boolean(username && localStorage.getItem(STORAGE.access));
  btnLogin.hidden = loggedIn;
  authUser.hidden = !loggedIn;
  if (loggedIn) {
    authUsername.textContent = username;
  }
}

function renderProfile(p) {
  document.title = `${p.studio_name || p.username} — Lumen`;
  const name = p.studio_name || p.username;
  document.getElementById("p-avatar").textContent = (name || "?")
    .charAt(0)
    .toUpperCase();
  document.getElementById("p-studio").textContent = name;

  const joined = new Date(p.created_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
  });
  document.getElementById("p-meta").textContent = `@${p.username} · ${
    p.city || "Location not set"
  } · Member since ${joined}`;

  document.getElementById("p-bio").textContent =
    p.bio || "This photographer has not added a bio yet.";

  document.getElementById("p-plan").hidden = p.plan !== "pro";

  document.getElementById("p-chips").innerHTML = (p.specialties || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");

  if (p.phone) {
    const phone = document.getElementById("p-phone");
    phone.hidden = false;
    phone.textContent = `Contact: ${p.phone}`;
  }

  statusEl.hidden = true;
  view.hidden = false;
}

async function loadPackages() {
  try {
    const response = await fetch(
      `${API}/packages/?profile=${encodeURIComponent(slug)}`
    );
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const items = Array.isArray(data) ? data : data.results || [];
    if (items.length === 0) {
      return;
    }
    document.getElementById("packages-grid").innerHTML = items
      .map(
        (pkg) => `
      <div class="package-card">
        <h3>${escapeHtml(pkg.title)}</h3>
        <p class="pkg-desc">${escapeHtml(
          pkg.description || "Session details on request."
        )}</p>
        <div class="pkg-price">$${Number(pkg.price).toFixed(2)}</div>
      </div>`
      )
      .join("");
    document.getElementById("packages-section").hidden = false;
  } catch (error) {
    console.error(error);
  }
}

async function loadPortfolio() {
  try {
    const response = await fetch(
      `${API}/portfolio-photos/?profile=${encodeURIComponent(slug)}`
    );
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const items = Array.isArray(data) ? data : data.results || [];
    if (items.length === 0) {
      return;
    }
    document.getElementById("portfolio-grid").innerHTML = items
      .map(
        (photo) => `
      <figure class="photo-card">
        <img src="${escapeHtml(photo.image)}" alt="${escapeHtml(
          photo.caption || "Portfolio photo"
        )}" loading="lazy" />
        ${
          photo.caption
            ? `<figcaption>${escapeHtml(photo.caption)}</figcaption>`
            : ""
        }
      </figure>`
      )
      .join("");
    document.getElementById("portfolio-section").hidden = false;
  } catch (error) {
    console.error(error);
  }
}

async function loadProfile() {
  if (!slug) {
    statusEl.textContent = "No profile specified.";
    return;
  }
  try {
    const response = await fetch(
      `${API}/profiles/${encodeURIComponent(slug)}/`
    );
    if (response.status === 404) {
      statusEl.textContent = "Profile not found.";
      return;
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    renderProfile(await response.json());
    loadPackages();
    loadPortfolio();
  } catch (error) {
    console.error(error);
    statusEl.textContent =
      "Could not reach the API. Is daphne running on port 8000?";
  }
}

btnLogin.addEventListener("click", () => {
  window.location.href = "index.html?login=1";
});
btnLogout.addEventListener("click", () => {
  localStorage.removeItem(STORAGE.access);
  localStorage.removeItem(STORAGE.refresh);
  localStorage.removeItem(STORAGE.username);
  initSession();
});

initSession();
loadProfile();
