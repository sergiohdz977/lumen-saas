/* Role-aware dashboard covering everything the account owns in the API:
   notifications, booking requests, shoots + galleries, catalog, studio
   settings, clients, favorites, reviews and payments. */

const gate = document.getElementById("gate");
const dash = document.getElementById("dash");
const dashStatus = document.getElementById("dash-status");
const dashContent = document.getElementById("dash-content");
const lightbox = document.getElementById("lightbox");
const lbImg = document.getElementById("lb-img");
const lbCaption = document.getElementById("lb-caption");
const lbCounter = document.getElementById("lb-counter");

let me = null;
let myRole = "";
let currentGalleryId = null;
let galleryPhotos = [];
let lbIndex = 0;
let galleryByShoot = new Map();
let shootsForGallery = [];
let bookingsForOverview = [];
let galleriesForOverview = [];
let paymentsForOverview = [];
let reviewsForOverview = [];
let paymentsByBooking = new Map();
let favoritesByPhoto = new Map();
let catalogPackages = [];
let editingReviewId = null;
let currentGalleryPaid = true;

const HIGH_RES_LOCKED =
  "Complete the payment to download photos in high quality.";

function showGate() {
  gate.hidden = false;
  dash.hidden = true;
}

function showDash() {
  gate.hidden = true;
  dash.hidden = false;
}

function activateTab(name) {
  document.querySelectorAll("#dash-tabs .tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.hidden =
      panel.dataset.panel !== name ||
      (panel.dataset.roles &&
        !panel.dataset.roles.split(" ").includes(myRole));
  });
}

function setupTabs() {
  document.querySelectorAll("#dash-tabs .tab").forEach((tab) => {
    if (tab.dataset.roles && !tab.dataset.roles.split(" ").includes(myRole)) {
      tab.hidden = true;
    }
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
  const visible = [...document.querySelectorAll("#dash-tabs .tab")].filter(
    (tab) => !tab.hidden
  );
  const requested = new URLSearchParams(window.location.search).get("tab");
  const requestedTab = visible.find((tab) => tab.dataset.tab === requested);
  const first = requestedTab || visible[0];
  activateTab(first ? first.dataset.tab : "overview");
}

function renderMe() {
  document.getElementById("me-username").textContent = me.username;
  document.getElementById("me-email").textContent = me.email;
  document.getElementById("me-role").textContent = me.role;
  document.getElementById("btn-new-gallery").hidden = me.role !== "photographer";
  document.getElementById("billing-section").hidden =
    me.role !== "photographer";

  const publicBtn = document.getElementById("btn-view-public");
  const canShowPublic =
    me.role === "photographer" && me.profile && me.profile.is_published;
  if (canShowPublic) {
    publicBtn.href = `profile.html?slug=${encodeURIComponent(me.profile.slug)}`;
  }
  publicBtn.hidden = !canShowPublic;
  renderOverview();

  if (me.role !== "photographer" || !me.profile) {
    return;
  }
  const profile = me.profile;
  document.getElementById("profile-studio").hidden = false;
  document.getElementById("me-studio").textContent = profile.studio_name || "—";
  document.getElementById("me-city").textContent = profile.city || "—";
  document.getElementById("me-plan").textContent = profile.plan;
  document.getElementById("me-published").textContent = profile.is_published
    ? "Yes"
    : "No";
  const stripeConnected = Boolean(profile.stripe_connected);
  document.getElementById("me-stripe").textContent = stripeConnected
    ? "Connected"
    : "Not connected";
  document.getElementById("btn-connect-stripe").hidden = stripeConnected;
  document.getElementById("pro-upgrade").hidden = profile.plan === "pro";
  const publicUrl = `profile.html?slug=${encodeURIComponent(profile.slug)}`;
  const viewLink = document.getElementById("studio-view-link");
  viewLink.href = publicUrl;
  viewLink.hidden = !profile.is_published;
  document.getElementById("me-chips").innerHTML = (profile.specialties || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");

  document.getElementById("st-studio").value = profile.studio_name || "";
  document.getElementById("st-city").value = profile.city || "";
  document.getElementById("st-specialties").value = profile.specialties || "";
  document.getElementById("st-phone").value = profile.phone || "";
  document.getElementById("st-bio").value = profile.bio || "";
  document.getElementById("st-published").checked = Boolean(
    profile.is_published
  );
}

/* ---------------------------- overview cards ---------------------------- */

function startOnboard() {
  const country = document.getElementById("onboard-country");
  apiFetch("/payments/onboard/", {
    method: "POST",
    body: { country: country ? country.value : "US" },
  })
    .then(async (response) => {
      if (!response.ok) {
        showToast(await readError(response));
        return;
      }
      const data = await response.json();
      window.location.href = data.onboarding_url;
    })
    .catch((error) => {
      console.error(error);
      showToast("Could not reach the API.");
    });
}

function updateStripeAlert() {
  const alertBox = document.getElementById("stripe-alert");
  if (!alertBox || !me) {
    return;
  }
  const connected = Boolean(me.profile && me.profile.stripe_connected);
  const moneyWaiting =
    myRole === "photographer" &&
    !connected &&
    bookingsForOverview.some((booking) =>
      ["accepted", "accepted_pending_deposit"].includes(booking.status)
    );
  alertBox.hidden = !moneyWaiting;
}

function renderOverview() {
  const grid = document.getElementById("overview-cards");
  if (!grid || !me) {
    return;
  }
  const cards = [];
  if (myRole === "photographer") {
    const now = new Date();
    const earnedCents = paymentsForOverview
      .filter((payment) => {
        if (payment.status !== "paid") {
          return false;
        }
        const date = new Date(payment.paid_at || payment.created_at);
        return (
          date.getMonth() === now.getMonth() &&
          date.getFullYear() === now.getFullYear()
        );
      })
      .reduce((sum, payment) => sum + Number(payment.amount_cents || 0), 0);
    const pending = bookingsForOverview.filter(
      (booking) => booking.status === "pending"
    ).length;
    const emptyGalleries = galleriesForOverview.filter(
      (gallery) => !gallery.photo_count
    ).length;
    const connected = Boolean(me.profile && me.profile.stripe_connected);
    cards.push(
      {
        tab: "payments",
        title: "Earnings this month",
        value: `$${(earnedCents / 100).toFixed(2)}`,
        hint: `Deposits and balances in ${now.toLocaleString(undefined, {
          month: "long",
        })}`,
      },
      connected
        ? {
            tab: "payments",
            title: "Stripe status",
            value: "Connected",
            hint: "Deposits go straight to your account",
          }
        : {
            tab: "payments",
            title: "Stripe status",
            value: "Pending",
            hint: "Not connected yet",
            alert: true,
            action: "onboard",
          },
      {
        tab: "requests",
        title: "Booking requests",
        value: String(pending),
        hint: pending
          ? `${pending} new waiting for your answer`
          : "Nothing waiting",
      },
      {
        tab: "galleries",
        title: "Galleries",
        value: String(emptyGalleries),
        hint: emptyGalleries
          ? `${emptyGalleries} pending photo upload`
          : galleriesForOverview.length
            ? "All galleries have photos"
            : "Create one from a shoot",
      }
    );
  } else {
    const pendingMine = bookingsForOverview.filter(
      (booking) => booking.status === "pending"
    ).length;
    cards.push(
      {
        tab: "requests",
        title: "My requests",
        value: String(bookingsForOverview.length),
        hint: pendingMine
          ? `${pendingMine} awaiting response`
          : "All answered",
      },
      {
        tab: "galleries",
        title: "Galleries",
        value: String(galleriesForOverview.length),
        hint: "Photos shared with you",
      },
      {
        tab: "favorites",
        title: "Favorites",
        value: String(favoritesByPhoto.size),
        hint: "Saved gallery photos",
      },
      {
        tab: "reviews",
        title: "My reviews",
        value: String(reviewsForOverview.length),
        hint: "Reviews you wrote",
      }
    );
  }
  grid.innerHTML = cards
    .map(
      (card) => `
      <div class="ov-card${card.alert ? " ov-alert" : ""}" role="button" tabindex="0" data-goto="${card.tab}">
        <div class="ov-title">${escapeHtml(card.title)}</div>
        <div class="ov-value">${escapeHtml(card.value)}</div>
        <div class="ov-hint">${escapeHtml(card.hint)}</div>
        ${
          card.action === "onboard"
            ? '<button class="btn btn-sm ov-action" type="button" data-onboard-now>Connect now</button>'
            : ""
        }
      </div>`
    )
    .join("");
  grid.querySelectorAll("[data-goto]").forEach((card) => {
    const go = (event) => {
      if (event.target.closest("[data-onboard-now]")) {
        return;
      }
      activateTab(card.dataset.goto);
    };
    card.addEventListener("click", go);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        go(event);
      }
    });
  });
  const onboardNow = grid.querySelector("[data-onboard-now]");
  if (onboardNow) {
    onboardNow.addEventListener("click", (event) => {
      event.stopPropagation();
      startOnboard();
    });
  }
}

/* ----------------------------- notifications ---------------------------- */

function renderNotifications(data) {
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
        <div class="n-date">
          ${formatDate(item.created_at, { withTime: true })}
          ${
            item.is_read
              ? ""
              : `<button class="btn btn-ghost btn-sm" type="button" data-read="${item.id}">Mark read</button>`
          }
        </div>
      </div>`
    )
    .join("");
  list.querySelectorAll("[data-read]").forEach((button) => {
    button.addEventListener("click", async () => {
      await apiFetch(`/notifications/${button.dataset.read}/read/`, {
        method: "POST",
      }).catch(() => null);
      loadNotifications();
    });
  });
}

async function loadNotifications() {
  try {
    const [listResponse, unreadResponse] = await Promise.all([
      apiFetch("/notifications/"),
      apiFetch("/notifications/?unread=1"),
    ]);
    if (listResponse.ok) {
      renderNotifications(await listResponse.json());
    }
    if (unreadResponse.ok) {
      const unread = await unreadResponse.json();
      document.getElementById("notif-count").textContent = String(unread.count);
    }
  } catch (error) {
    console.error(error);
  }
}

document
  .getElementById("notif-read-all")
  .addEventListener("click", async () => {
    await apiFetch("/notifications/read-all/", { method: "POST" }).catch(
      () => null
    );
    loadNotifications();
  });

/* ------------------------- booking requests ----------------------------- */

function payActionHtml(booking) {
  const pays = paymentsByBooking.get(booking.id) || {};
  const depositPaid = Boolean(pays.deposit && pays.deposit.status === "paid");
  const balancePaid = Boolean(pays.balance && pays.balance.status === "paid");
  if (booking.status === "confirmed") {
    if (balancePaid) {
      return '<span class="status-chip status-paid">fully paid</span>';
    }
    const galleryShoots = new Set(
      galleriesForOverview.map((gallery) => gallery.shoot)
    );
    if (booking.shoot != null && galleryShoots.has(booking.shoot)) {
      return `<button class="btn btn-sm" type="button" data-pay="${
        booking.id
      }" data-kind="balance">Pay remaining balance (80%)</button>`;
    }
    return '<span class="status-chip status-pending">awaiting gallery</span>';
  }
  if (depositPaid) {
    return '<span class="status-chip status-paid">deposit paid</span>';
  }
  return `<button class="btn btn-sm" type="button" data-pay="${
    booking.id
  }" data-kind="deposit">Pay deposit (20%)</button>`;
}

function requestRow(booking, role) {
  const other =
    role === "photographer"
      ? booking.customer_username
      : booking.profile_studio_name || booking.profile_slug;
  let extra = "";
  if (role === "photographer" && booking.status === "pending") {
    extra = `
      <button class="btn btn-sm" type="button" data-accept="${booking.id}">Accept</button>
      <button class="btn btn-ghost btn-sm" type="button" data-reject="${booking.id}">Reject</button>`;
  }
  if (
    role === "customer" &&
    ["accepted", "accepted_pending_deposit", "confirmed"].includes(
      booking.status
    )
  ) {
    extra = payActionHtml(booking);
  }
  return `
    <div class="request-row">
      <div class="req-info">
        <strong>${escapeHtml(booking.package_title)}</strong>
        <span class="meta">${escapeHtml(other)} · ${formatDate(
          booking.date,
          { withTime: true }
        )}</span>
        ${booking.message ? `<span class="req-msg">${escapeHtml(booking.message)}</span>` : ""}
      </div>
      ${statusChip(booking.status)}
      ${extra}
    </div>`;
}

function renderRequests(data, role) {
  document.getElementById("requests-title").textContent =
    role === "photographer" ? "Incoming requests" : "My requests";
  const list = document.getElementById("requests-list");
  bookingsForOverview = data.results || [];
  renderOverview();
  updateStripeAlert();
  renderPaymentsSummary();
  if (!data.results || data.results.length === 0) {
    list.innerHTML = '<p class="meta">No booking requests yet.</p>';
    return;
  }
  list.innerHTML = data.results
    .map((booking) => requestRow(booking, role))
    .join("");

  list.querySelectorAll("[data-accept]").forEach((button) => {
    button.addEventListener("click", () =>
      transitionBooking(button.dataset.accept, "accept")
    );
  });
  list.querySelectorAll("[data-reject]").forEach((button) => {
    button.addEventListener("click", () =>
      transitionBooking(button.dataset.reject, "reject")
    );
  });
  list.querySelectorAll("[data-pay]").forEach((button) => {
    button.addEventListener("click", () =>
      startPayment(button.dataset.pay, button.dataset.kind || "deposit")
    );
  });
  customerPayActions();
}

async function loadRequests() {
  try {
    const response = await apiFetch("/bookings/");
    if (response.ok) {
      renderRequests(await response.json(), myRole);
    }
  } catch (error) {
    console.error(error);
  }
}

async function transitionBooking(id, action) {
  try {
    const response = await apiFetch(`/bookings/${id}/${action}/`, {
      method: "POST",
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    showToast(
      action === "accept"
        ? "Request accepted — the shoot and client were created."
        : "Request rejected."
    );
    await loadRequests();
    await loadNotifications();
    if (action === "accept") {
      await loadShoots();
      await loadClients();
      await loadGalleries();
      if (myRole === "photographer") {
        activateTab("shoots");
      }
    }
  } catch (error) {
    console.error(error);
  }
}

async function startPayment(bookingId, kind = "deposit") {
  try {
    const response = await apiFetch("/payments/checkout/", {
      method: "POST",
      body: { booking: Number(bookingId), kind },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const data = await response.json();
    window.location.href = data.checkout_url;
  } catch (error) {
    console.error(error);
    showToast("Could not reach the API.");
  }
}

/* -------------------------------- shoots -------------------------------- */

function nextShootAction(status) {
  if (status === "booked") {
    return { label: "Start editing", next: "editing" };
  }
  if (status === "editing") {
    return { label: "Mark delivered", next: "delivered" };
  }
  return null;
}

function renderShoots(data) {
  const list = document.getElementById("shoots-list");
  shootsForGallery = data.results || [];
  if (!data.results || data.results.length === 0) {
    list.innerHTML = '<p class="meta">No shoots yet.</p>';
    return;
  }
  list.innerHTML = data.results
    .map((shoot) => {
      const action = nextShootAction(shoot.status);
      const gallery = galleryByShoot.get(shoot.id);
      const galleryButton = gallery
        ? `<button class="btn btn-ghost btn-sm" type="button" data-open-gallery="${gallery.id}">Gallery</button>`
        : myRole === "photographer"
          ? `<button class="btn btn-ghost btn-sm" type="button" data-create-gallery="${shoot.id}">Create gallery</button>`
          : "";
      return `
      <div class="request-row">
        <div class="req-info">
          <strong>${escapeHtml(shoot.title)}</strong>
          <span class="meta">${escapeHtml(shoot.client_name)} · ${formatDate(
            shoot.date,
            { withTime: true }
          )}</span>
        </div>
        ${statusChip(shoot.status)}
        ${
          action
            ? `<button class="btn btn-sm" type="button"
                data-shoot="${shoot.id}" data-next="${action.next}">${action.label}</button>`
            : ""
        }
        ${galleryButton}
      </div>`;
    })
    .join("");

  list.querySelectorAll("[data-shoot]").forEach((button) => {
    button.addEventListener("click", () =>
      updateShoot(button.dataset.shoot, button.dataset.next)
    );
  });
  list.querySelectorAll("[data-create-gallery]").forEach((button) => {
    button.addEventListener("click", () =>
      createGallery(button.dataset.createGallery)
    );
  });
  list.querySelectorAll("[data-open-gallery]").forEach((button) => {
    button.addEventListener("click", () =>
      openGallery(button.dataset.openGallery)
    );
  });
}

async function loadShoots() {
  try {
    const response = await apiFetch("/shoots/");
    if (response.ok) {
      renderShoots(await response.json());
    } else {
      document.getElementById("shoots-list").innerHTML =
        "<p class=\"meta\">Could not load shoots: " +
        escapeHtml(await readError(response)) +
        "</p>";
    }
  } catch (error) {
    console.error(error);
    document.getElementById("shoots-list").innerHTML =
      '<p class="meta">Could not load shoots.</p>';
  }
}

async function updateShoot(id, nextStatus) {
  if (
    nextStatus === "delivered" &&
    !confirm(
      "Mark this shoot as delivered? The client will consider it final."
    )
  ) {
    return;
  }
  try {
    const response = await apiFetch(`/shoots/${id}/`, {
      method: "PATCH",
      body: { status: nextStatus },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    await loadShoots();
  } catch (error) {
    console.error(error);
  }
}

async function createGallery(shootId) {
  try {
    const response = await apiFetch("/galleries/", {
      method: "POST",
      body: { shoot: Number(shootId) },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const gallery = await response.json();
    showToast("Gallery created — upload the photos to share them.");
    await loadGalleries();
    await loadShoots();
    openGallery(gallery.id);
  } catch (error) {
    console.error(error);
  }
}

/* ------------------------------- galleries ------------------------------ */

function renderGalleries(items) {
  const list = document.getElementById("galleries-list");
  galleriesForOverview = items;
  renderOverview();
  if (items.length === 0) {
    list.innerHTML =
      '<p class="meta">No galleries yet.' +
      (myRole === "photographer"
        ? " Create one from a shoot when it is ready."
        : "") +
      "</p>";
    return;
  }
  list.innerHTML = items
    .map(
      (gallery) => `
      <div class="request-row">
        <div class="req-info">
          <strong>${escapeHtml(gallery.shoot_title)}</strong>
          <span class="meta">${
            myRole === "photographer"
              ? `Client: ${escapeHtml(gallery.client_username || "—")} · `
              : ""
          }Created ${formatDate(gallery.created_at)}</span>
        </div>
        <button class="btn btn-sm" type="button" data-open-gallery="${
          gallery.id
        }">Open</button>
      </div>`
    )
    .join("");
  list.querySelectorAll("[data-open-gallery]").forEach((button) => {
    button.addEventListener("click", () => openGallery(button.dataset.openGallery));
  });
  customerPayActions();
}

async function loadGalleries() {
  try {
    const response = await apiFetch("/galleries/");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const items = data.results || [];
    galleryByShoot = new Map(items.map((gallery) => [gallery.shoot, gallery]));
    renderGalleries(items);
  } catch (error) {
    console.error(error);
  }
}

function galleryPhotoCard(photo, index) {
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
    if (currentGalleryPaid) {
      tools.push(
        `<button class="btn btn-sm" type="button" data-download="${photo.id}">Download high res</button>`
      );
    } else {
      tools.push(
        `<button class="btn btn-sm" type="button" data-download="${photo.id}" disabled title="${HIGH_RES_LOCKED}">Download high res</button>`
      );
    }
    tools.push(
      `<button class="btn btn-ghost btn-sm" type="button" data-download="${photo.id}" data-version="light">Download preview</button>`
    );
  }
  if (myRole === "photographer") {
    tools.push(
      `<button class="btn btn-ghost btn-sm" type="button" data-del-photo="${photo.id}">Delete</button>`
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
      <div class="photo-tools">${tools.join("")}</div>
    </figure>`;
}

function renderGalleryPhotos() {
  const grid = document.getElementById("gallery-photos");
  const empty = document.getElementById("gallery-empty");
  grid.innerHTML = galleryPhotos
    .map((photo, index) => galleryPhotoCard(photo, index))
    .join("");
  empty.hidden = galleryPhotos.length > 0;
}

async function openGallery(galleryId) {
  currentGalleryId = Number(galleryId);
  galleryPhotos = [];
  document.getElementById("gallery-title").textContent = "Loading gallery…";
  document.getElementById("gallery-sub").textContent = "";
  document.getElementById("gallery-photos").innerHTML = "";
  document.getElementById("gallery-empty").hidden = true;
  document.getElementById("gallery-share").hidden = myRole !== "photographer";
  document.getElementById("upload-form").hidden = myRole !== "photographer";
  document.getElementById("gallery-client-hint").hidden =
    myRole !== "customer";
  document.getElementById("share-url").value = "";
  document.getElementById("btn-copy-share").hidden = true;
  document.getElementById("upload-error").hidden = true;
  syncUploadFileName();
  document.getElementById("gallery-modal").hidden = false;

  try {
    const [detailResponse, photoResponse] = await Promise.all([
      apiFetch(`/galleries/${currentGalleryId}/`),
      apiFetch(`/photos/?gallery=${currentGalleryId}`),
    ]);
    if (!detailResponse.ok || !photoResponse.ok) {
      document.getElementById("gallery-title").textContent =
        "Gallery unavailable";
      return;
    }
    const detail = await detailResponse.json();
    currentGalleryPaid = detail.fully_paid !== false;
    const payBanner = document.getElementById("gallery-pay-banner");
    const payText = document.getElementById("gallery-pay-text");
    const payAction = document.getElementById("gallery-pay-action");
    const awaitingDeposit =
      detail.booking_status === "accepted_pending_deposit" ||
      detail.booking_status === "accepted";
    const awaitingBalance =
      detail.booking_status === "confirmed" && !currentGalleryPaid;
    if (myRole === "customer" && (awaitingDeposit || awaitingBalance)) {
      payText.textContent = awaitingDeposit
        ? "Pay the deposit to confirm your booking."
        : "Your booking is confirmed. Pay the remaining balance to download your photos.";
      payAction.textContent = awaitingDeposit
        ? "Pay deposit (20%)"
        : "Pay remaining balance (80%)";
      payBanner.hidden = false;
    } else {
      payBanner.hidden = true;
    }
    document.getElementById("gallery-title").textContent =
      detail.shoot_title || "Gallery";
    document.getElementById("gallery-sub").textContent =
      (myRole === "photographer"
        ? `For ${detail.client_username || "your client"}`
        : "Your private gallery") +
      ` · created ${formatDate(detail.created_at)}`;

    const photoData = await photoResponse.json();
    galleryPhotos = photoData.results || [];
    renderGalleryPhotos();
  } catch (error) {
    console.error(error);
    document.getElementById("gallery-title").textContent =
      "Could not reach the API";
  }
}

document.getElementById("gallery-close").addEventListener("click", () => {
  document.getElementById("gallery-modal").hidden = true;
});
document.getElementById("gallery-pay-action").addEventListener("click", () => {
  document.getElementById("gallery-modal").hidden = true;
  activateTab("payments");
});
document.getElementById("gallery-modal").addEventListener("click", (event) => {
  if (event.target.id === "gallery-modal") {
    event.currentTarget.hidden = true;
  }
});

/* ------------------------- create gallery modal -------------------------- */

function openNewGalleryModal() {
  const select = document.getElementById("gallery-new-shoot");
  const hint = document.getElementById("gallery-new-error");
  const submit = document.querySelector('#gallery-new-form [type="submit"]');
  const candidates = shootsForGallery.filter(
    (shoot) => !galleryByShoot.has(shoot.id)
  );
  select.innerHTML = candidates.length
    ? candidates
        .map(
          (shoot) =>
            `<option value="${shoot.id}">${escapeHtml(shoot.title)} — ${formatDate(
              shoot.date,
              { withTime: true }
            )}</option>`
        )
        .join("")
    : '<option value="" disabled selected>No shoots available</option>';
  hint.hidden = candidates.length > 0;
  hint.textContent =
    "No shoots available yet — accept a booking request first.";
  submit.disabled = candidates.length === 0;
  document.getElementById("gallery-new-modal").hidden = false;
}

document
  .getElementById("btn-new-gallery")
  .addEventListener("click", openNewGalleryModal);

document
  .getElementById("gallery-new-close")
  .addEventListener("click", () => {
    document.getElementById("gallery-new-modal").hidden = true;
  });

document
  .getElementById("gallery-new-modal")
  .addEventListener("click", (event) => {
    if (event.target.id === "gallery-new-modal") {
      event.currentTarget.hidden = true;
    }
  });

document
  .getElementById("gallery-new-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const shootId = document.getElementById("gallery-new-shoot").value;
    if (!shootId) {
      return;
    }
    document.getElementById("gallery-new-modal").hidden = true;
    await createGallery(shootId);
  });

document.getElementById("gallery-photos").addEventListener("click", async (event) => {
  const del = event.target.closest("[data-del-photo]");
  if (del) {
    if (!confirm("Delete this photo from the gallery?")) {
      return;
    }
    const response = await apiFetch(`/photos/${del.dataset.delPhoto}/`, {
      method: "DELETE",
    }).catch(() => null);
    if (response && response.ok) {
      showToast("Photo deleted.");
      await openGallery(currentGalleryId);
    } else if (response) {
      showToast(await readError(response));
    }
    return;
  }
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
  if (card) {
    openLightbox(Number(card.dataset.index) || 0);
  }
});

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
      renderGalleryPhotos();
      if (!lightbox.hidden) {
        renderLightbox();
      }
      loadFavorites();
    }
    return;
  }
  try {
    const response = await apiFetch("/favorites/", {
      method: "POST",
      body: { photo: photoId },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const favorite = await response.json();
    favoritesByPhoto.set(photoId, favorite.id);
    renderGalleryPhotos();
    if (!lightbox.hidden) {
      renderLightbox();
    }
    loadFavorites();
  } catch (error) {
    console.error(error);
  }
}

async function downloadPhoto(photoId, version = "original") {
  if (!requireLogin()) {
    return;
  }
  if (version === "original" && myRole === "customer" && !currentGalleryPaid) {
    showToast(HIGH_RES_LOCKED);
    return;
  }
  try {
    const response = await apiFetch(`/photos/${photoId}/download/`, {
      method: "POST",
      body: { version },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const photo = galleryPhotos.find((item) => item.id === photoId);
    if (photo) {
      const url =
        version === "light"
          ? photo.preview || photo.thumbnail || photo.image
          : photo.image;
      window.open(url, "_blank", "noopener");
    }
  } catch (error) {
    console.error(error);
  }
}

function syncUploadFileName() {
  const file = document.getElementById("upload-file").files[0];
  document.getElementById("upload-file-name").textContent = file
    ? file.name
    : "No photo selected";
}

document.getElementById("upload-file").addEventListener("change", syncUploadFileName);

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("upload-file");
  const errorBox = document.getElementById("upload-error");
  errorBox.hidden = true;
  const file = fileInput.files[0];
  if (!file) {
    errorBox.textContent = "Choose a photo first.";
    errorBox.hidden = false;
    return;
  }
  if (!currentGalleryId) {
    return;
  }
  const form = new FormData();
  form.append("gallery", String(currentGalleryId));
  form.append("image", file);
  const caption = document.getElementById("upload-caption").value.trim();
  if (caption) {
    form.append("caption", caption);
  }
  try {
    const response = await apiFetch("/photos/", { method: "POST", body: form });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    showToast("Photo uploaded — variants are generated in the background.");
    event.target.reset();
    syncUploadFileName();
    await openGallery(currentGalleryId);
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

document.getElementById("btn-share").addEventListener("click", async () => {
  if (!currentGalleryId) {
    return;
  }
  try {
    const response = await apiFetch(`/galleries/${currentGalleryId}/share-link/`, {
      method: "POST",
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const data = await response.json();
    document.getElementById("share-url").value = data.url;
    document.getElementById("btn-copy-share").hidden = false;
    showToast(`Share link valid for ${data.expires_in_days} days.`);
  } catch (error) {
    console.error(error);
  }
});

document.getElementById("btn-copy-share").addEventListener("click", async () => {
  const input = document.getElementById("share-url");
  try {
    await navigator.clipboard.writeText(input.value);
    showToast("Link copied to clipboard.");
  } catch (error) {
    input.select();
    showToast("Press Ctrl+C to copy the link.");
  }
});

/* ------------------------------- lightbox ------------------------------- */

function renderLightbox() {
  const photo = galleryPhotos[lbIndex];
  if (!photo) {
    return;
  }
  lbImg.src = photo.preview || photo.image;
  lbImg.alt = photo.caption || "Gallery photo";
  lbCaption.textContent = photo.caption || "";
  lbCounter.textContent = `${lbIndex + 1} / ${galleryPhotos.length}`;
  const downloadBtn = document.getElementById("lb-download");
  downloadBtn.hidden = !isLoggedIn();
  const highResLocked = myRole === "customer" && !currentGalleryPaid;
  downloadBtn.disabled = highResLocked;
  downloadBtn.title = highResLocked ? HIGH_RES_LOCKED : "";
  const downloadWebBtn = document.getElementById("lb-download-web");
  downloadWebBtn.hidden = !isLoggedIn();
  const favoriteBtn = document.getElementById("lb-favorite");
  favoriteBtn.hidden = myRole !== "customer";
  if (myRole === "customer") {
    favoriteBtn.textContent = favoritesByPhoto.has(photo.id)
      ? "★ Favorited"
      : "☆ Favorite";
  }
}

function openLightbox(index) {
  if (galleryPhotos.length === 0) {
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
  lbIndex = (lbIndex + delta + galleryPhotos.length) % galleryPhotos.length;
  renderLightbox();
}

document.getElementById("lb-close").addEventListener("click", closeLightbox);
document.getElementById("lb-prev").addEventListener("click", () => stepLightbox(-1));
document.getElementById("lb-next").addEventListener("click", () => stepLightbox(1));
document.getElementById("lb-download").addEventListener("click", () => {
  const photo = galleryPhotos[lbIndex];
  if (photo) {
    downloadPhoto(photo.id, "original");
  }
});
document.getElementById("lb-download-web").addEventListener("click", () => {
  const photo = galleryPhotos[lbIndex];
  if (photo) {
    downloadPhoto(photo.id, "light");
  }
});
document.getElementById("lb-favorite").addEventListener("click", () => {
  const photo = galleryPhotos[lbIndex];
  if (photo) {
    toggleFavorite(photo.id);
  }
});
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
  if (event.key === "Escape") {
    document.getElementById("gallery-modal").hidden = true;
    document.getElementById("pkg-modal").hidden = true;
    document.getElementById("photo-modal").hidden = true;
    document.getElementById("review-modal").hidden = true;
  }
});

/* -------------------------------- catalog ------------------------------- */

function renderPackages(items) {
  catalogPackages = items;
  const list = document.getElementById("pkg-list");
  if (items.length === 0) {
    list.innerHTML = '<p class="meta">No packages yet — add your first one.</p>';
    return;
  }
  list.innerHTML = items
    .map(
      (pkg) => `
      <div class="request-row">
        <div class="req-info">
          <strong>${escapeHtml(pkg.title)}</strong>
          <span class="meta">${escapeHtml(pkg.description || "No description")}</span>
        </div>
        <strong class="price-inline">$${Number(pkg.price).toFixed(2)}</strong>
        <button class="btn btn-sm" type="button" data-edit-pkg="${pkg.id}">Edit</button>
        <button class="btn btn-ghost btn-sm" type="button" data-del-pkg="${pkg.id}">Delete</button>
      </div>`
    )
    .join("");
  list.querySelectorAll("[data-edit-pkg]").forEach((button) => {
    button.addEventListener("click", () =>
      openPackageModal(Number(button.dataset.editPkg))
    );
  });
  list.querySelectorAll("[data-del-pkg]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this package?")) {
        return;
      }
      const response = await apiFetch(
        `/packages/${button.dataset.delPkg}/`,
        { method: "DELETE" }
      ).catch(() => null);
      if (response && response.ok) {
        showToast("Package deleted.");
        loadCatalog();
      } else if (response) {
        showToast(await readError(response));
      }
    });
  });
}

function renderPortfolioItems(items) {
  const list = document.getElementById("portfolio-list");
  if (items.length === 0) {
    list.innerHTML = '<p class="meta">No photos yet.</p>';
    return;
  }
  list.innerHTML = items
    .map(
      (photo) => `
      <figure class="photo-card">
        <img src="${escapeHtml(photo.image)}" alt="${escapeHtml(
          photo.caption || "Portfolio photo"
        )}" loading="lazy" />
        <div class="photo-tools">
          <button class="btn btn-ghost btn-sm" type="button" data-del-photo-id="${
            photo.id
          }">Delete</button>
        </div>
      </figure>`
    )
    .join("");
  list.querySelectorAll("[data-del-photo-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Remove this photo from your portfolio?")) {
        return;
      }
      const response = await apiFetch(
        `/portfolio-photos/${button.dataset.delPhotoId}/`,
        { method: "DELETE" }
      ).catch(() => null);
      if (response && response.ok) {
        showToast("Photo removed.");
        loadCatalog();
      } else if (response) {
        showToast(await readError(response));
      }
    });
  });
}

async function loadCatalog() {
  const profile = me && me.profile;
  if (!profile) {
    return;
  }
  try {
    const [packagesResponse, photosResponse] = await Promise.all([
      apiFetch(`/packages/?profile=${encodeURIComponent(profile.slug)}`),
      apiFetch(`/portfolio-photos/?profile=${encodeURIComponent(profile.slug)}`),
    ]);
    if (packagesResponse.ok) {
      const data = await packagesResponse.json();
      renderPackages(data.results || []);
    }
    if (photosResponse.ok) {
      const data = await photosResponse.json();
      renderPortfolioItems(data.results || []);
    }
  } catch (error) {
    console.error(error);
  }
}

function openPackageModal(packageId) {
  const form = document.getElementById("pkg-form");
  form.dataset.id = packageId ? String(packageId) : "";
  document.getElementById("pkg-title").textContent = packageId
    ? "Edit package"
    : "Add package";
  document.getElementById("pkg-error").hidden = true;
  form.reset();
  if (packageId) {
    const pkg = catalogPackages.find((item) => item.id === packageId);
    if (pkg) {
      document.getElementById("pkg-name").value = pkg.title;
      document.getElementById("pkg-desc").value = pkg.description || "";
      document.getElementById("pkg-price").value = pkg.price;
    }
  }
  document.getElementById("pkg-modal").hidden = false;
  document.getElementById("pkg-name").focus();
}

document.getElementById("btn-add-package").addEventListener("click", () => {
  openPackageModal(null);
});
document.getElementById("pkg-close").addEventListener("click", () => {
  document.getElementById("pkg-modal").hidden = true;
});
document.getElementById("pkg-modal").addEventListener("click", (event) => {
  if (event.target.id === "pkg-modal") {
    event.currentTarget.hidden = true;
  }
});

document.getElementById("pkg-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const errorBox = document.getElementById("pkg-error");
  errorBox.hidden = true;
  const body = {
    title: document.getElementById("pkg-name").value.trim(),
    description: document.getElementById("pkg-desc").value.trim(),
    price: document.getElementById("pkg-price").value,
  };
  const id = form.dataset.id;
  try {
    const response = await apiFetch(id ? `/packages/${id}/` : "/packages/", {
      method: id ? "PATCH" : "POST",
      body,
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    document.getElementById("pkg-modal").hidden = true;
    showToast(id ? "Package updated." : "Package added.");
    loadCatalog();
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

document.getElementById("btn-add-photo").addEventListener("click", () => {
  document.getElementById("photo-error").hidden = true;
  document.getElementById("photo-form").reset();
  document.getElementById("photo-modal").hidden = false;
  document.getElementById("photo-url").focus();
});
document.getElementById("photo-close").addEventListener("click", () => {
  document.getElementById("photo-modal").hidden = true;
});
document.getElementById("photo-modal").addEventListener("click", (event) => {
  if (event.target.id === "photo-modal") {
    event.currentTarget.hidden = true;
  }
});

document.getElementById("photo-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = document.getElementById("photo-error");
  errorBox.hidden = true;
  const body = {
    image: document.getElementById("photo-url").value.trim(),
    caption: document.getElementById("photo-caption").value.trim(),
  };
  try {
    const response = await apiFetch("/portfolio-photos/", {
      method: "POST",
      body,
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    document.getElementById("photo-modal").hidden = true;
    showToast("Photo added to your portfolio.");
    loadCatalog();
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

/* ----------------------------- studio profile --------------------------- */

document.getElementById("studio-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = document.getElementById("studio-error");
  errorBox.hidden = true;
  if (!me || !me.profile) {
    return;
  }
  try {
    const response = await apiFetch(
      `/profiles/${encodeURIComponent(me.profile.slug)}/`,
      {
        method: "PATCH",
        body: {
          studio_name: document.getElementById("st-studio").value.trim(),
          city: document.getElementById("st-city").value.trim(),
          specialties: document.getElementById("st-specialties").value.trim(),
          phone: document.getElementById("st-phone").value.trim(),
          bio: document.getElementById("st-bio").value.trim(),
          is_published: document.getElementById("st-published").checked,
        },
      }
    );
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    const updated = await response.json();
    me.profile = { ...me.profile, ...updated };
    renderMe();
    showToast("Studio profile saved.");
    loadCatalog();
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

/* -------------------------------- clients ------------------------------- */

async function loadClients() {
  try {
    const response = await apiFetch("/clients/");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const items = data.results || [];
    const list = document.getElementById("clients-list");
    if (items.length === 0) {
      list.innerHTML =
        '<p class="meta">No clients yet — they appear when you accept a booking.</p>';
      return;
    }
    list.innerHTML = items
      .map(
        (client) => `
        <div class="request-row">
          <div class="req-info">
            <strong>${escapeHtml(client.name)}</strong>
            <span class="meta">${escapeHtml(client.email || "—")} · ${escapeHtml(
              client.phone || "no phone"
            )}</span>
          </div>
          <span class="meta">Since ${formatDate(client.created_at)}</span>
        </div>`
      )
      .join("");
  } catch (error) {
    console.error(error);
  }
}

/* ------------------------------- favorites ------------------------------ */

async function loadFavorites() {
  try {
    const response = await apiFetch("/favorites/");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const items = data.results || [];
    favoritesByPhoto = new Map(items.map((item) => [item.photo, item.id]));
    renderOverview();
    const list = document.getElementById("favorites-list");
    if (items.length === 0) {
      list.innerHTML =
        '<p class="meta">No favorites yet — tap the star on your gallery photos.</p>';
      return;
    }
    list.innerHTML = items
      .map(
        (item) => `
        <div class="request-row">
          <img class="fav-thumb" src="${escapeHtml(
            item.photo_thumbnail || ""
          )}" alt="" />
          <div class="req-info">
            <strong>${escapeHtml(item.photo_caption || "Photo")}</strong>
            <span class="meta">Saved ${formatDate(item.created_at)}</span>
          </div>
          <button class="btn btn-ghost btn-sm" type="button" data-del-fav="${
            item.id
          }">Remove</button>
        </div>`
      )
      .join("");
    list.querySelectorAll("[data-del-fav]").forEach((button) => {
      button.addEventListener("click", async () => {
        const response = await apiFetch(
          `/favorites/${button.dataset.delFav}/`,
          { method: "DELETE" }
        ).catch(() => null);
        if (response && response.ok) {
          showToast("Removed from favorites.");
          await loadFavorites();
          if (currentGalleryId && !document.getElementById("gallery-modal").hidden) {
            await openGallery(currentGalleryId);
          }
        }
      });
    });
  } catch (error) {
    console.error(error);
  }
}

/* ------------------------------ my reviews ------------------------------ */

function renderMyReviews(items) {
  const list = document.getElementById("my-reviews-list");
  reviewsForOverview = items;
  renderOverview();
  if (items.length === 0) {
    list.innerHTML =
      '<p class="meta">You have not reviewed anyone yet — open a photographer profile to write one.</p>';
    return;
  }
  list.innerHTML = items
    .map(
      (review) => `
      <div class="request-row">
        <div class="req-info">
          <div class="review-head">
            ${starsHtml(review.rating)}
            <strong>@${escapeHtml(review.photographer_username)}</strong>
          </div>
          ${
            review.comment
              ? `<p class="req-msg">${escapeHtml(review.comment)}</p>`
              : ""
          }
          <span class="meta">${formatDate(review.created_at)}</span>
        </div>
        <button class="btn btn-sm" type="button" data-edit-review="${
          review.id
        }">Edit</button>
        <button class="btn btn-ghost btn-sm" type="button" data-del-review="${
          review.id
        }">Delete</button>
      </div>`
    )
    .join("");
  list.querySelectorAll("[data-edit-review]").forEach((button) => {
    button.addEventListener("click", () => {
      const review = items.find(
        (item) => item.id === Number(button.dataset.editReview)
      );
      if (review) {
        openReviewModal(review);
      }
    });
  });
  list.querySelectorAll("[data-del-review]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!confirm("Delete this review?")) {
        return;
      }
      const response = await apiFetch(
        `/reviews/${button.dataset.delReview}/`,
        { method: "DELETE" }
      ).catch(() => null);
      if (response && response.ok) {
        showToast("Review deleted.");
        loadMyReviews();
      }
    });
  });
}

async function loadMyReviews() {
  try {
    const response = await apiFetch("/reviews/");
    if (response.ok) {
      const data = await response.json();
      renderMyReviews(data.results || []);
    }
  } catch (error) {
    console.error(error);
  }
}

function openReviewModal(review) {
  editingReviewId = review.id;
  document.getElementById("review-modal-title").textContent =
    `Your review for @${review.photographer_username}`;
  document.getElementById("review-error").hidden = true;
  document.getElementById("review-rating").value = String(review.rating);
  document.getElementById("review-comment").value = review.comment || "";
  document.getElementById("review-modal").hidden = false;
  document.getElementById("review-rating").focus();
}

document.getElementById("review-close").addEventListener("click", () => {
  document.getElementById("review-modal").hidden = true;
});
document.getElementById("review-modal").addEventListener("click", (event) => {
  if (event.target.id === "review-modal") {
    event.currentTarget.hidden = true;
  }
});

document.getElementById("review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = document.getElementById("review-error");
  errorBox.hidden = true;
  if (!editingReviewId) {
    return;
  }
  try {
    const response = await apiFetch(`/reviews/${editingReviewId}/`, {
      method: "PATCH",
      body: {
        rating: Number(document.getElementById("review-rating").value),
        comment: document.getElementById("review-comment").value.trim(),
      },
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    document.getElementById("review-modal").hidden = true;
    editingReviewId = null;
    showToast("Review updated.");
    loadMyReviews();
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

/* -------------------------------- payments ------------------------------ */

const COUNTRIES = [
  ["US", "United States"],
  ["ES", "Spain"],
  ["MX", "Mexico"],
  ["CO", "Colombia"],
  ["AR", "Argentina"],
  ["CL", "Chile"],
  ["PE", "Peru"],
  ["BR", "Brazil"],
  ["FR", "France"],
  ["DE", "Germany"],
  ["IT", "Italy"],
  ["GB", "United Kingdom"],
  ["CU", "Cuba"],
];

function customerPayActions() {
  const actions = document.getElementById("payments-actions");
  if (myRole !== "customer") {
    return;
  }
  const payable = bookingsForOverview.filter((booking) =>
    ["accepted", "accepted_pending_deposit", "confirmed"].includes(
      booking.status
    )
  );
  const rows = payable
    .map(
      (booking) => `
      <div class="request-row">
        <div class="req-info">
          <strong>${escapeHtml(booking.package_title)}</strong>
          <span class="meta">${formatDate(booking.date, {
            withTime: true,
          })}</span>
        </div>
        ${payActionHtml(booking)}
      </div>`
    )
    .join("");
  actions.innerHTML = rows
    ? `<div class="setup-block">
        <h3>Booking payments</h3>
        <p class="meta">The deposit confirms your booking. The balance unlocks high-quality downloads.</p>
        ${rows}
      </div>`
    : "";
  actions.hidden = !rows;
  actions.querySelectorAll("[data-pay]").forEach((button) => {
    button.addEventListener("click", () =>
      startPayment(button.dataset.pay, button.dataset.kind || "deposit")
    );
  });
}

function renderPaymentActions() {
  const actions = document.getElementById("payments-actions");
  if (myRole !== "photographer") {
    actions.hidden = true;
    actions.innerHTML = "";
    return;
  }
  actions.hidden = false;
  actions.innerHTML = `
    <div class="setup-block">
      <h3>Accept deposits</h3>
      <p class="meta">Connect your Stripe account so customers pay you directly (test keys in development).</p>
      <form id="onboard-form" class="inline-form">
        <select id="onboard-country" aria-label="Country">
          ${COUNTRIES.map(
            ([code, name]) => `<option value="${code}">${name}</option>`
          ).join("")}
        </select>
        <button class="btn btn-sm" type="submit">Set up payouts</button>
      </form>
    </div>`;

  document
    .getElementById("onboard-form")
    .addEventListener("submit", (event) => {
      event.preventDefault();
      startOnboard();
    });
}

function renderPaymentsSummary() {
  const box = document.getElementById("payments-summary");
  if (!box) {
    return;
  }
  const paidCents = paymentsForOverview
    .filter((payment) => payment.status === "paid")
    .reduce((sum, payment) => sum + Number(payment.amount_cents || 0), 0);
  const pendingCount = bookingsForOverview.filter((booking) => {
    if (
      !["accepted", "accepted_pending_deposit"].includes(booking.status)
    ) {
      return false;
    }
    const pays = paymentsByBooking.get(booking.id) || {};
    const depositPaid =
      pays.deposit && pays.deposit.status === "paid";
    return !depositPaid;
  }).length;
  const totalLabel =
    myRole === "photographer" ? "Total received" : "Total paid";
  box.innerHTML = `
    <span class="sum-chip ${
      pendingCount ? "sum-pending" : "sum-zero"
    }">Pending payments: ${pendingCount}</span>
    <span class="sum-chip ${
      paidCents > 0 ? "sum-paid" : "sum-zero"
    }">${totalLabel}: $${(paidCents / 100).toFixed(2)}</span>`;
  const list = document.getElementById("payments-list");
  if (list && paymentsForOverview.length === 0) {
    list.innerHTML =
      pendingCount > 0
        ? `<p class="meta">${pendingCount} booking${
            pendingCount === 1 ? " is" : "s are"
          } waiting for payment.</p>`
        : '<p class="meta">No payments yet.</p>';
  }
}

function renderPayments(data) {
  const list = document.getElementById("payments-list");
  paymentsForOverview = data.results || [];
  renderOverview();
  paymentsByBooking = new Map();
  for (const payment of data.results || []) {
    const entry = paymentsByBooking.get(payment.booking) || {};
    entry[payment.kind === "balance" ? "balance" : "deposit"] = payment;
    paymentsByBooking.set(payment.booking, entry);
  }
  renderPaymentsSummary();
  customerPayActions();
  if (!data.results || data.results.length === 0) {
    return;
  }
  list.innerHTML = data.results
    .map(
      (payment) => `
      <div class="request-row">
        <div class="req-info">
          <strong>${
            payment.kind === "balance" ? "Balance" : "Deposit"
          } · Booking #${escapeHtml(payment.booking)}</strong>
          <span class="meta">${formatDate(payment.created_at, {
            withTime: true,
          })}</span>
        </div>
        <strong class="price-inline">${escapeHtml(payment.currency || "usd").toUpperCase()} ${(Number(
          payment.amount_cents
        ) / 100).toFixed(2)}</strong>
        ${statusChip(payment.status)}
      </div>`
    )
    .join("");
}

async function loadPayments() {
  try {
    const response = await apiFetch("/payments/");
    if (response.ok) {
      renderPayments(await response.json());
    }
  } catch (error) {
    console.error(error);
  }
}

/* ---------------------------------- init -------------------------------- */

document.getElementById("btn-go-login").addEventListener("click", () => {
  window.location.href = "index.html?login=1";
});

document
  .getElementById("stripe-alert-action")
  .addEventListener("click", () => {
    activateTab("payments");
  });

document.getElementById("btn-upgrade").addEventListener("click", async () => {
  try {
    const response = await apiFetch("/payments/upgrade/", { method: "POST" });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    const data = await response.json();
    window.location.href = data.checkout_url;
  } catch (error) {
    console.error(error);
    showToast("Could not reach the API.");
  }
});

document
  .getElementById("btn-connect-stripe")
  .addEventListener("click", () => {
    startOnboard();
  });

async function init() {
  if (!getAccess()) {
    showGate();
    return;
  }

  let meData = null;
  try {
    meData = await fetchMe();
  } catch (error) {
    console.error(error);
  }

  if (!meData) {
    if (getAccess()) {
      showDash();
      dashStatus.hidden = false;
      dashStatus.textContent =
        "Could not reach the API. Is the server running on port 8000?";
    } else {
      showGate();
    }
    return;
  }

  me = meData;
  myRole = me.role;
  renderMe();
  setupTabs();
  showDash();
  dashStatus.hidden = true;
  dashContent.hidden = false;
  updateStripeAlert();

  renderPaymentActions();

  // Payments first for customers: accepted requests show their deposit state.
  await loadNotifications();
  if (myRole === "customer") {
    await loadPayments();
    await Promise.all([
      loadRequests(),
      loadGalleries(),
      loadFavorites(),
      loadMyReviews(),
    ]);
  } else {
    await loadGalleries();
    await Promise.all([
      loadRequests(),
      loadShoots(),
      loadCatalog(),
      loadClients(),
      loadPayments(),
    ]);
  }
}

initHeader();
init();
