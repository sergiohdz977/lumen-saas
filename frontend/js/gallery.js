/* Public viewer for signed share links: /gallery.html?token=<signed token> */

const params = new URLSearchParams(window.location.search);
const token = params.get("token");

const statusEl = document.getElementById("g-status");
const view = document.getElementById("g-view");
const grid = document.getElementById("g-grid");
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCaption = document.getElementById("lb-caption");
const lbCounter = document.getElementById("lb-counter");

let photos = [];
let lbIndex = 0;
let myRole = null;
let galleryInfo = null;
let favoritesByPhoto = new Map();

const HIGH_RES_LOCKED =
  "Complete the payment to download photos in high quality.";

function isHighResLocked() {
  return (
    myRole === "customer" &&
    galleryInfo &&
    galleryInfo.fully_paid === false
  );
}

function renderBanner() {
  const banner = document.getElementById("g-banner");
  const text = document.getElementById("g-banner-text");
  const action = document.getElementById("g-banner-action");
  const status = galleryInfo ? galleryInfo.booking_status : null;
  const awaitingDeposit = status === "accepted_pending_deposit" || status === "accepted";
  const awaitingBalance = status === "confirmed" && !galleryInfo.fully_paid;
  if (myRole !== "customer" || (!awaitingDeposit && !awaitingBalance)) {
    banner.hidden = true;
    return;
  }
  if (awaitingDeposit) {
    text.textContent = "Pay the deposit to confirm your booking.";
    action.textContent = "Pay deposit (20%)";
  } else {
    text.textContent =
      "Your booking is confirmed. Pay the remaining balance to download your photos.";
    action.textContent = "Pay remaining balance (80%)";
  }
  banner.hidden = false;
}

function renderGrid() {
  grid.innerHTML = photos
    .map((photo, index) => {
      const tools = [];
      if (myRole === "customer") {
        const favorite = favoritesByPhoto.has(photo.id);
        tools.push(
          `<button class="btn btn-ghost btn-sm${
            favorite ? " is-fav" : ""
          }" type="button" data-fav-photo="${photo.id}">${
            favorite ? "★ Favorite" : "☆ Favorite"
          }</button>`
        );
      }
      if (myRole) {
        const locked = isHighResLocked();
        tools.push(
          locked
            ? `<button class="btn btn-sm" type="button" data-download="${photo.id}" disabled title="${HIGH_RES_LOCKED}">Download high res</button>`
            : `<button class="btn btn-sm" type="button" data-download="${photo.id}">Download high res</button>`,
          `<button class="btn btn-ghost btn-sm" type="button" data-download="${photo.id}" data-version="light">Download preview</button>`
        );
      }
      return `
      <figure class="photo-card" data-index="${index}">
        <img src="${escapeHtml(photo.thumbnail || photo.image)}" alt="${escapeHtml(
          photo.caption || "Gallery photo"
        )}" loading="lazy" />
        ${
          photo.caption
            ? `<figcaption>${escapeHtml(photo.caption)}</figcaption>`
            : ""
        }
        ${tools.length ? `<div class="photo-tools">${tools.join("")}</div>` : ""}
      </figure>`;
    })
    .join("");
  document.getElementById("g-empty").hidden = photos.length > 0;
}

async function loadMe() {
  const me = await fetchMe();
  myRole = me ? me.role : null;
  renderBanner();
}

async function loadFavorites() {
  if (myRole !== "customer") {
    return;
  }
  try {
    const response = await apiFetch("/favorites/", { silentAuth: true });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const items = data.results || [];
    favoritesByPhoto = new Map(items.map((item) => [item.photo, item.id]));
    renderGrid();
  } catch (error) {
    console.error(error);
  }
}

async function toggleFavorite(photoId) {
  if (myRole !== "customer") {
    return;
  }
  const existing = favoritesByPhoto.get(photoId);
  if (existing) {
    const response = await apiFetch(`/favorites/${existing}/`, {
      method: "DELETE",
    }).catch(() => null);
    if (response && response.ok) {
      favoritesByPhoto.delete(photoId);
      renderGrid();
      showToast("Removed from favorites.");
    } else if (response) {
      showToast(await readError(response));
    }
    return;
  }
  const response = await apiFetch("/favorites/", {
    method: "POST",
    body: { photo: photoId },
  }).catch(() => null);
  if (response && response.ok) {
    const data = await response.json();
    favoritesByPhoto.set(photoId, data.id);
    renderGrid();
    showToast("Saved to favorites.");
  } else if (response) {
    showToast(await readError(response));
  }
}

async function downloadPhoto(photoId, version = "original") {
  const photo = photos.find((item) => item.id === photoId);
  if (!photo || !requireLogin()) {
    return;
  }
  if (version === "original" && isHighResLocked()) {
    showToast(HIGH_RES_LOCKED);
    return;
  }
  try {
    const response = await apiFetch(`/photos/${photo.id}/download/`, {
      method: "POST",
      body: { version },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const url =
      version === "light"
        ? photo.preview || photo.thumbnail || photo.image
        : photo.image;
    window.open(url, "_blank", "noopener");
  } catch (error) {
    console.error(error);
  }
}

async function loadGallery() {
  if (!token) {
    statusEl.textContent = "No gallery link provided.";
    return;
  }
  try {
    const response = await fetch(
      `${API}/gallery-view/${encodeURIComponent(token)}/`
    );
    if (response.status === 404) {
      statusEl.textContent = "This link has expired or is not valid.";
      return;
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    document.title = `${data.gallery.shoot_title || "Gallery"} — Lumen`;
    document.getElementById("g-title").textContent =
      data.gallery.shoot_title || "Gallery";
    document.getElementById("g-meta").textContent = `Shared ${formatDate(
      data.gallery.created_at
    )}`;
    galleryInfo = data.gallery;
    photos = data.photos || [];
    renderGrid();
    renderBanner();
    statusEl.hidden = true;
    view.hidden = false;
  } catch (error) {
    console.error(error);
    statusEl.textContent =
      "Could not reach the API. Is the server running on port 8000?";
  }
}

function renderLightbox() {
  const photo = photos[lbIndex];
  if (!photo) {
    return;
  }
  lbImg.src = photo.preview || photo.image;
  lbImg.alt = photo.caption || "Gallery photo";
  lbCaption.textContent = photo.caption || "";
  lbCounter.textContent = `${lbIndex + 1} / ${photos.length}`;
  const locked = isHighResLocked();
  const downloadBtn = document.getElementById("lb-download");
  downloadBtn.disabled = locked;
  downloadBtn.title = locked ? HIGH_RES_LOCKED : "";
}

function openLightbox(index) {
  if (photos.length === 0) {
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
  lbIndex = (lbIndex + delta + photos.length) % photos.length;
  renderLightbox();
}

async function downloadCurrent(version = "original") {
  const photo = photos[lbIndex];
  if (!photo) {
    return;
  }
  if (!requireLogin()) {
    return;
  }
  if (version === "original" && isHighResLocked()) {
    showToast(HIGH_RES_LOCKED);
    return;
  }
  try {
    const response = await apiFetch(`/photos/${photo.id}/download/`, {
      method: "POST",
      body: { version },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const url =
      version === "light"
        ? photo.preview || photo.thumbnail || photo.image
        : photo.image;
    window.open(url, "_blank", "noopener");
  } catch (error) {
    console.error(error);
  }
}

grid.addEventListener("click", async (event) => {
  const fav = event.target.closest("[data-fav-photo]");
  if (fav) {
    await toggleFavorite(Number(fav.dataset.favPhoto));
    return;
  }
  const download = event.target.closest("[data-download]");
  if (download) {
    await downloadPhoto(
      Number(download.dataset.download),
      download.dataset.version || "original"
    );
    return;
  }
  const card = event.target.closest(".photo-card");
  if (!card) {
    return;
  }
  openLightbox(Number(card.dataset.index) || 0);
});

document.getElementById("g-share").addEventListener("click", async () => {
  const url = window.location.href;
  if (navigator.share) {
    try {
      await navigator.share({ title: document.title, url });
      return;
    } catch (error) {
      if (error && error.name === "AbortError") {
        return;
      }
    }
  }
  try {
    await navigator.clipboard.writeText(url);
    const status = document.getElementById("g-share-status");
    status.hidden = false;
    window.setTimeout(() => {
      status.hidden = true;
    }, 2500);
  } catch (error) {
    showToast("Copy the link from the address bar.");
  }
});
document.getElementById("lb-close").addEventListener("click", closeLightbox);
document.getElementById("lb-prev").addEventListener("click", () => stepLightbox(-1));
document.getElementById("lb-next").addEventListener("click", () => stepLightbox(1));
document.getElementById("lb-download").addEventListener("click", () =>
  downloadCurrent("original")
);
document.getElementById("lb-download-web").addEventListener("click", () =>
  downloadCurrent("light")
);
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

initHeader();
loadMe().then(() => {
  renderGrid();
  renderBanner();
  loadFavorites();
});
loadGallery();
