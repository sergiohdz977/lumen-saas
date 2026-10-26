const API =
  window.location.port === "8000" || window.location.port === ""
    ? "/api"
    : "http://127.0.0.1:8000/api";

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
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCaption = document.getElementById("lb-caption");
const lbCounter = document.getElementById("lb-counter");
const portfolioGrid = document.getElementById("portfolio-grid");
const bookModal = document.getElementById("book-modal");
const bookForm = document.getElementById("book-form");
const bookPackage = document.getElementById("book-package");
const bookDate = document.getElementById("book-date");
const bookMessage = document.getElementById("book-message");
const bookError = document.getElementById("book-error");

let portfolioPhotos = [];
let lbIndex = 0;
let myRole = null;

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
        <button class="btn btn-block pkg-book" type="button"
          data-package-id="${pkg.id}"
          data-title="${escapeHtml(pkg.title)}">Book session</button>
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
    portfolioPhotos = items;
    portfolioGrid.innerHTML = items
      .map(
        (photo, index) => `
      <figure class="photo-card" data-index="${index}">
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

function renderLightbox() {
  const photo = portfolioPhotos[lbIndex];
  lbImg.src = photo.image;
  lbImg.alt = photo.caption || "Portfolio photo";
  lbCaption.textContent = photo.caption || "";
  lbCounter.textContent = `${lbIndex + 1} / ${portfolioPhotos.length}`;
}

function openLightbox(index) {
  if (portfolioPhotos.length === 0) {
    return;
  }
  lbIndex = index;
  renderLightbox();
  lightbox.hidden = false;
  document.body.style.overflow = "hidden";
  document.getElementById("lb-close").focus();
}

function closeLightbox() {
  lightbox.hidden = true;
  document.body.style.overflow = "";
}

function stepLightbox(delta) {
  lbIndex = (lbIndex + delta + portfolioPhotos.length) % portfolioPhotos.length;
  renderLightbox();
}

portfolioGrid.addEventListener("click", (event) => {
  const card = event.target.closest(".photo-card");
  if (!card) {
    return;
  }
  openLightbox(Number(card.dataset.index) || 0);
});
document.getElementById("lb-close").addEventListener("click", closeLightbox);
document
  .getElementById("lb-prev")
  .addEventListener("click", () => stepLightbox(-1));
document
  .getElementById("lb-next")
  .addEventListener("click", () => stepLightbox(1));
lightbox.addEventListener("click", (event) => {
  if (event.target === lightbox) {
    closeLightbox();
  }
});
document.addEventListener("keydown", (event) => {
  if (lightbox.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closeLightbox();
  } else if (event.key === "ArrowRight") {
    stepLightbox(1);
  } else if (event.key === "ArrowLeft") {
    stepLightbox(-1);
  }
});

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

function openBookModal(packageId, title) {
  bookForm.dataset.packageId = packageId;
  bookPackage.textContent = title;
  bookError.hidden = true;
  bookForm.reset();
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  bookDate.min = now.toISOString().slice(0, 16);
  bookModal.hidden = false;
  bookDate.focus();
}

function closeBookModal() {
  bookModal.hidden = true;
}

async function loadMeRole() {
  const access = localStorage.getItem(STORAGE.access);
  if (!access) {
    return;
  }
  try {
    const response = await fetch(`${API}/auth/me/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    if (response.status === 401) {
      localStorage.removeItem(STORAGE.access);
      localStorage.removeItem(STORAGE.refresh);
      localStorage.removeItem(STORAGE.username);
      initSession();
      return;
    }
    if (response.ok) {
      const me = await response.json();
      myRole = me.role;
    }
  } catch (error) {
    console.error(error);
  }
}

async function handleBookSubmit(event) {
  event.preventDefault();
  bookError.hidden = true;
  const access = localStorage.getItem(STORAGE.access);
  if (!access) {
    window.location.href = "index.html?login=1";
    return;
  }
  if (myRole && myRole !== "customer") {
    bookError.textContent =
      "Only customer accounts can send booking requests.";
    bookError.hidden = false;
    return;
  }
  const packageId = Number(bookForm.dataset.packageId);
  if (!bookDate.value) {
    bookError.textContent = "Please choose a date and time.";
    bookError.hidden = false;
    return;
  }
  try {
    const response = await fetch(`${API}/bookings/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access}`,
      },
      body: JSON.stringify({
        package: packageId,
        date: bookDate.value,
        message: bookMessage.value.trim(),
      }),
    });
    if (response.status === 401) {
      closeBookModal();
      window.location.href = "index.html?login=1";
      return;
    }
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      let message = `Server error (HTTP ${response.status}).`;
      if (error) {
        const raw = error.detail || Object.values(error)[0];
        if (Array.isArray(raw)) {
          message = raw.join(" ");
        } else if (raw) {
          message = String(raw);
        }
      }
      bookError.textContent = message;
      bookError.hidden = false;
      return;
    }
    closeBookModal();
    const button = document.querySelector(
      `.pkg-book[data-package-id="${bookForm.dataset.packageId}"]`
    );
    if (button) {
      button.textContent = "Request sent ✓";
      button.disabled = true;
    }
    showToast(
      "Request sent! Track it in your dashboard under \u201cMy requests\u201d."
    );
  } catch (error) {
    console.error(error);
    bookError.textContent =
      "Could not reach the API. Check that the server is running on port 8000.";
    bookError.hidden = false;
  }
}

document.getElementById("packages-grid").addEventListener("click", (event) => {
  const button = event.target.closest(".pkg-book");
  if (!button) {
    return;
  }
  openBookModal(button.dataset.packageId, button.dataset.title);
});
document.getElementById("book-close").addEventListener("click", closeBookModal);
bookModal.addEventListener("click", (event) => {
  if (event.target === bookModal) {
    closeBookModal();
  }
});
bookForm.addEventListener("submit", handleBookSubmit);

initSession();
loadProfile();
loadMeRole();
