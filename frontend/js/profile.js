const params = new URLSearchParams(window.location.search);
const slug = params.get("slug");

const statusEl = document.getElementById("profile-status");
const view = document.getElementById("profile-view");
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCaption = document.getElementById("lb-caption");
const lbCounter = document.getElementById("lb-counter");
const portfolioGrid = document.getElementById("portfolio-grid");
const bookModal = document.getElementById("book-modal");
const bookForm = document.getElementById("book-form");
const bookDate = document.getElementById("book-date");
const bookMessage = document.getElementById("book-message");
const bookLocation = document.getElementById("book-location");
const bookTime = document.getElementById("book-time");
const bookNotes = document.getElementById("book-notes");
const bookError = document.getElementById("book-error");
const reviewModal = document.getElementById("review-modal");
const reviewForm = document.getElementById("review-form");
const reviewError = document.getElementById("review-error");
const reviewCta = document.getElementById("review-cta");
const reviewsList = document.getElementById("reviews-list");

let portfolioPhotos = [];
let lbIndex = 0;
let myRole = null;
let myId = null;
let photographerId = null;
let packageItems = [];

function isOwner() {
  return Boolean(myId) && photographerId != null &&
    Number(myId) === Number(photographerId);
}

function updateOwnerBanner() {
  document.getElementById("owner-banner").hidden = !isOwner();
}

function renderProfile(p) {
  document.title = `${p.studio_name || p.username} — Lumen`;
  const name = p.studio_name || p.username;
  const avatar = document.getElementById("p-avatar");
  const initial = (name || "?").charAt(0).toUpperCase();
  if (p.profile_picture) {
    avatar.innerHTML = `<img class="avatar-img" src="${escapeHtml(
      p.profile_picture
    )}" alt="${escapeHtml(name)}">`;
  } else {
    avatar.textContent = initial;
  }
  document.getElementById("p-studio").textContent = name;

  const joined = new Date(p.created_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
  });
  document.getElementById("p-meta").textContent = `@${p.username} · ${
    p.city || "Location not set"
  } · Member since ${joined}`;

  const hero = document.getElementById("profile-hero");
  const coverBanner = document.getElementById("cover-banner");
  if (p.cover_image) {
    document.getElementById("cover-img").src = p.cover_image;
    coverBanner.hidden = false;
    hero.classList.add("has-cover");
  } else {
    coverBanner.hidden = true;
    hero.classList.remove("has-cover");
  }

  const aboutBio = document.getElementById("about-bio");
  const aboutStats = document.getElementById("about-stats");
  const bio = (p.bio || "").trim();
  aboutBio.textContent = bio;
  const stats = [];
  if (p.years_experience != null && p.years_experience !== "") {
    stats.push(`${p.years_experience} years of experience`);
  }
  if (p.languages) {
    stats.push(`Languages: ${p.languages}`);
  }
  const equipment = (p.equipment || "").trim();
  aboutStats.innerHTML =
    stats
      .map((stat) => `<span class="chip">${escapeHtml(stat)}</span>`)
      .join("") +
    (equipment
      ? `<p class="about-equipment"><strong>Equipment:</strong> ${escapeHtml(
          equipment
        )}</p>`
      : "");
  document.getElementById("about-section").hidden = !(
    bio ||
    stats.length > 0 ||
    equipment
  );

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

  photographerId = p.user_id;
  updateOwnerBanner();
  statusEl.hidden = true;
  view.hidden = false;
}

function renderPackageCards() {
  const section = document.getElementById("packages-section");
  if (packageItems.length === 0) {
    return;
  }
  const owner = isOwner();
  const isPhotographer = myRole === "photographer";
  document.getElementById("packages-grid").innerHTML = packageItems
    .map((pkg) => {
      let action = "";
      if (owner) {
        action = `<button class="btn btn-block pkg-book" type="button"
          data-package-id="${pkg.id}"
          data-title="${escapeHtml(pkg.title)}"
          data-action="edit">Edit this package</button>`;
      } else if (!isPhotographer) {
        action = `<button class="btn btn-block pkg-book" type="button"
          data-package-id="${pkg.id}"
          data-title="${escapeHtml(pkg.title)}">Book session</button>`;
      }
      return `
      <div class="package-card">
        <h3>${escapeHtml(pkg.title)}</h3>
        <p class="pkg-desc">${escapeHtml(
          pkg.description || "Session details on request."
        )}</p>
        <div class="pkg-price">$${Number(pkg.price).toFixed(2)}</div>
        ${action}
      </div>`;
    })
    .join("");
  section.hidden = false;
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
    packageItems = items;
    renderPackageCards();
  } catch (error) {
    console.error(error);
  }
}

async function loadPortfolio() {
  try {
    const [photosResponse, collectionsResponse] = await Promise.all([
      fetch(`${API}/portfolio-photos/?profile=${encodeURIComponent(slug)}`),
      fetch(
        `${API}/portfolio-collections/?profile=${encodeURIComponent(slug)}`
      ),
    ]);
    if (!photosResponse.ok) {
      return;
    }
    const data = await photosResponse.json();
    const items = Array.isArray(data) ? data : data.results || [];
    if (items.length === 0) {
      return;
    }
    let collections = [];
    if (collectionsResponse.ok) {
      const collectionsData = await collectionsResponse.json();
      collections = Array.isArray(collectionsData)
        ? collectionsData
        : collectionsData.results || [];
    }
    const groups = collections
      .map((collection) => ({
        title: collection.title,
        photos: items.filter((photo) => photo.collection === collection.id),
      }))
      .filter((group) => group.photos.length > 0);
    const ungrouped = items.filter((photo) => !photo.collection);
    if (ungrouped.length > 0) {
      groups.unshift({ title: "Selected work", photos: ungrouped });
    }
    if (groups.length === 0) {
      return;
    }
    const renderOrder = [];
    portfolioGrid.innerHTML = groups
      .map((group) => {
        const figures = group.photos
          .map((photo) => {
            const index = renderOrder.push(photo) - 1;
            return `
      <figure class="photo-card" data-index="${index}">
        <img src="${escapeHtml(photo.image)}" alt="${escapeHtml(
              photo.caption || "Portfolio photo"
            )}" loading="lazy" />
        ${
          photo.caption
            ? `<figcaption class="photo-caption">${escapeHtml(
                photo.caption
              )}</figcaption>`
            : ""
        }
      </figure>`;
          })
          .join("");
        return `
      <div class="collection-block">
        <h3 class="collection-title">${escapeHtml(group.title)} <span class="collection-count">${group.photos.length}</span></h3>
        <div class="portfolio-grid">${figures}</div>
      </div>`;
      })
      .join("");
    portfolioPhotos = renderOrder;
    document.getElementById("portfolio-section").hidden = false;
  } catch (error) {
    console.error(error);
  }
}

function reviewHtml(item) {
  return `
    <div class="review-row">
      <div class="review-head">
        ${starsHtml(item.rating)}
        <strong>${escapeHtml(item.customer_username)}</strong>
        <span class="meta">${formatDate(item.created_at)}</span>
      </div>
      ${
        item.comment
          ? `<p class="review-comment">${escapeHtml(item.comment)}</p>`
          : ""
      }
    </div>`;
}

function showRating(average, count) {
  const row = document.getElementById("p-rating");
  document.getElementById("p-rating-stars").innerHTML = starsHtml(average);
  document.getElementById("p-rating-label").textContent =
    `${average.toFixed(1)} · ${count} review${count === 1 ? "" : "s"}`;
  row.hidden = false;
}

function updateReviewCta() {
  const eligible =
    isLoggedIn() &&
    myRole === "customer" &&
    Boolean(myId) &&
    myId !== photographerId;
  reviewCta.hidden = !eligible;
}

async function loadReviews() {
  if (!photographerId) {
    return;
  }
  document.getElementById("reviews-section").hidden = false;
  if (!isLoggedIn()) {
    reviewsList.innerHTML =
      '<p class="meta">Log in to read and write reviews.</p>';
    updateReviewCta();
    return;
  }
  try {
    const response = await apiFetch(
      `/reviews/?photographer=${photographerId}`,
      { silentAuth: true }
    );
    if (!response.ok) {
      reviewsList.innerHTML =
        '<p class="meta">Log in to read and write reviews.</p>';
      return;
    }
    const data = await response.json();
    const items = data.results || [];
    if (items.length === 0) {
      reviewsList.innerHTML =
        '<p class="meta">No reviews yet — be the first.</p>';
    } else {
      reviewsList.innerHTML = items.map(reviewHtml).join("");
      const average =
        items.reduce((sum, item) => sum + Number(item.rating), 0) /
        items.length;
      showRating(average, data.count || items.length);
    }
    updateReviewCta();
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
    loadReviews();
  } catch (error) {
    console.error(error);
    statusEl.textContent =
      "Could not reach the API. Is the server running on port 8000?";
  }
}

async function loadMe() {
  const me = await fetchMe();
  myRole = me ? me.role : null;
  myId = me ? me.id : null;
  updateOwnerBanner();
  if (packageItems.length > 0) {
    renderPackageCards();
  }
  updateReviewCta();
}

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
  if (!lightbox.hidden) {
    if (event.key === "Escape") {
      closeLightbox();
    } else if (event.key === "ArrowRight") {
      stepLightbox(1);
    } else if (event.key === "ArrowLeft") {
      stepLightbox(-1);
    }
    return;
  }
  if (event.key === "Escape" && !reviewModal.hidden) {
    closeReviewModal();
  }
});

function openBookModal(packageId, title) {
  bookForm.dataset.packageId = packageId;
  document.getElementById("book-package").textContent = title;
  bookError.hidden = true;
  bookForm.reset();
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  bookDate.min = now.toISOString().slice(0, 10);
  bookModal.hidden = false;
  bookDate.focus();
}

function closeBookModal() {
  bookModal.hidden = true;
}

async function handleBookSubmit(event) {
  event.preventDefault();
  bookError.hidden = true;
  if (!requireLogin()) {
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
    bookError.textContent = "Please choose a date.";
    bookError.hidden = false;
    return;
  }
  try {
    const response = await apiFetch("/bookings/", {
      method: "POST",
      body: {
        package: packageId,
        date: bookDate.value,
        message: bookMessage.value.trim(),
        event_location: bookLocation.value.trim(),
        event_time: bookTime.value || null,
        event_notes: bookNotes.value.trim(),
      },
    });
    if (!response.ok) {
      bookError.textContent = await readError(response);
      bookError.hidden = false;
      return;
    }
    const booking = await response.json();
    closeBookModal();
    // Land straight on the request detail (details + chat) in the dashboard.
    window.location.href = `dashboard.html?tab=requests&item=${booking.id}`;
  } catch (error) {
    console.error(error);
    bookError.textContent =
      "Could not reach the API. Check that the server is running on port 8000.";
    bookError.hidden = false;
  }
}

function openReviewModal() {
  if (!requireLogin()) {
    return;
  }
  reviewError.hidden = true;
  reviewForm.reset();
  reviewModal.hidden = false;
  document.getElementById("review-rating").focus();
}

function closeReviewModal() {
  reviewModal.hidden = true;
}

async function handleReviewSubmit(event) {
  event.preventDefault();
  reviewError.hidden = true;
  if (!requireLogin()) {
    return;
  }
  try {
    const response = await apiFetch("/reviews/", {
      method: "POST",
      body: {
        photographer: photographerId,
        rating: Number(document.getElementById("review-rating").value),
        comment: document.getElementById("review-comment").value.trim(),
      },
    });
    if (!response.ok) {
      reviewError.textContent = await readError(response);
      reviewError.hidden = false;
      return;
    }
    closeReviewModal();
    reviewCta.hidden = true;
    showToast("Thanks! Your review was published.");
    await loadReviews();
  } catch (error) {
    console.error(error);
    reviewError.textContent =
      "Could not reach the API. Check that the server is running on port 8000.";
    reviewError.hidden = false;
  }
}

document.getElementById("packages-grid").addEventListener("click", (event) => {
  const button = event.target.closest(".pkg-book");
  if (!button) {
    return;
  }
  if (button.dataset.action === "edit") {
    window.location.href = `dashboard.html?tab=packages&item=${button.dataset.packageId}`;
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

document
  .getElementById("btn-write-review")
  .addEventListener("click", openReviewModal);
document
  .getElementById("review-close")
  .addEventListener("click", closeReviewModal);
reviewModal.addEventListener("click", (event) => {
  if (event.target === reviewModal) {
    closeReviewModal();
  }
});
reviewForm.addEventListener("submit", handleReviewSubmit);

initHeader();
loadProfile();
loadMe();
