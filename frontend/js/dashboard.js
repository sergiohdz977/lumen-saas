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
let catalogCollections = [];
let portfolioItems = [];
let activeCollectionFilter = "all"; // "all" | "none" | collection id
let portfolioPreviewPhotos = []; // photos listed in the Portfolio tab, in view order
let portfolioPreviewIndex = 0;
let currentGalleryPaid = true;
let activeRequestId = null; // booking open in the slide-in drawer
let chatPollTimer = null;
let pendingOpenRequest = null; // booking to open once the list loads
let deepLinkPackageId = null; // package to edit once the catalog loads
let requestFilter = "all"; // all | pending | accepted
let lastRequestsData = null;
let lastRequestsRole = "";
const REQUEST_FILTERS = {
  all: () => true,
  pending: (booking) =>
    ["requested", "awaiting_payment"].includes(booking.status),
  accepted: (booking) => booking.status === "accepted",
  cancelled: (booking) => booking.status === "cancelled",
};

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

const JOB_VIEWS = ["requests", "shoots", "galleries"];
let lastJobView = "requests";

/* Settings sub-tabs: Public profile / Account / Billing / Studio / Clients.
   Sections only show when allowed for the role AND their tab is active. */
const SETTINGS_TABS = {
  public: ["pp-section", "profile-studio"],
  account: ["account-section"],
  billing: ["billing-section"],
  studio: ["studio-settings"],
  clients: ["clients-settings"],
};
let activeSettingsTab = "public";

function setSettingsSection(id, allowed) {
  const el = document.getElementById(id);
  if (el) {
    el.dataset.allowed = allowed ? "true" : "false";
  }
}

function applySettingsTab() {
  const available = (key) =>
    (SETTINGS_TABS[key] || []).some((id) => {
      const el = document.getElementById(id);
      return el && el.dataset.allowed === "true";
    });
  if (!available(activeSettingsTab)) {
    const fallback = Object.keys(SETTINGS_TABS).find(available);
    if (fallback) {
      activeSettingsTab = fallback;
    }
  }
  Object.entries(SETTINGS_TABS).forEach(([key, ids]) => {
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.hidden = !(key === activeSettingsTab && el.dataset.allowed === "true");
      }
    });
  });
  document.querySelectorAll("#settings-bar .sub-tab").forEach((btn) => {
    const key = btn.dataset.subtab;
    btn.hidden = !available(key);
    btn.classList.toggle("is-active", key === activeSettingsTab);
  });
}

function activateSettingsTab(key) {
  activeSettingsTab = SETTINGS_TABS[key] ? key : "public";
  applySettingsTab();
  if (activeSettingsTab === "clients") {
    // Refresh on every visit so new bookings show up automatically.
    loadClients();
  }
}

function visibleJobViews() {
  return JOB_VIEWS.filter((view) => {
    const panel = document.querySelector(`.tab-panel[data-panel="${view}"]`);
    return (
      !panel ||
      !panel.dataset.roles ||
      panel.dataset.roles.split(" ").includes(myRole)
    );
  });
}

function activateTab(name) {
  if (name === "jobs") {
    const views = visibleJobViews();
    name = views.includes(lastJobView) ? lastJobView : views[0] || "requests";
  }
  const inJobs = JOB_VIEWS.includes(name);
  if (inJobs) {
    lastJobView = name;
  }
  const mainKey = inJobs ? "jobs" : name;
  document.querySelectorAll("#dash-tabs .tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.tab === mainKey);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.hidden =
      panel.dataset.panel !== name ||
      (panel.dataset.roles &&
        !panel.dataset.roles.split(" ").includes(myRole));
  });
  const jobsBar = document.getElementById("jobs-bar");
  if (jobsBar) {
    jobsBar.hidden = !inJobs;
    jobsBar.querySelectorAll(".sub-tab").forEach((btn) => {
      btn.hidden = Boolean(
        btn.dataset.roles && !btn.dataset.roles.split(" ").includes(myRole)
      );
      btn.classList.toggle("is-active", btn.dataset.view === name);
    });
  }
  if (name === "profile") {
    // Opening Settings always starts on "Public profile".
    activateSettingsTab("public");
  }
  if (name !== "requests" && activeRequestId) {
    // The drawer lives inside the requests view: leaving it closes the drawer.
    closeRequestDetail();
  }
  if (name === "notifications") {
    // Viewing the notifications clears every unread badge.
    markAllNotificationsRead();
  }
}

function markAllNotificationsRead() {
  apiFetch("/notifications/read-all/", { method: "POST" })
    .catch(() => null)
    .then(() => {
      loadNotifications();
      refreshBellBadge();
    });
}

/* Deep links between dashboard tabs must not reload the page.
   `item` marks the row the notification is about (slight highlight).
   Gallery links still navigate for real. */
let pendingHighlight = null; // { tab, id }

function applyPendingHighlight(list, tab) {
  if (!pendingHighlight || pendingHighlight.tab !== tab || !list) {
    return;
  }
  const target = list.querySelector(
    `[data-highlight-id="${pendingHighlight.id}"]`
  );
  if (target) {
    target.classList.add("row-highlight");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    pendingHighlight = null;
  }
}

function finishPendingHighlight() {
  applyPendingHighlight(
    document.getElementById("requests-list"),
    "requests"
  );
  applyPendingHighlight(document.getElementById("payments-list"), "payments");
  applyPendingHighlight(document.getElementById("pkg-list"), "packages");
}

window.lumenNavigate = function (href) {
  if (href && href.startsWith("dashboard.html")) {
    const query = new URLSearchParams(href.split("?")[1] || "");
    const tab = query.get("tab");
    if (tab) {
      const item = query.get("item");
      pendingHighlight = item ? { tab, id: item } : null;
      pendingOpenRequest = tab === "requests" && item ? item : null;
      activateTab(tab);
      window.history.replaceState(
        {},
        "",
        `?tab=${tab}${item ? `&item=${item}` : ""}`
      );
      window.scrollTo({ top: 0, behavior: "smooth" });
      if (tab === "requests") {
        loadRequests().then(finishPendingHighlight);
      } else if (tab === "payments") {
        loadPayments().then(finishPendingHighlight);
      } else if (tab === "packages") {
        loadCatalog().then(() => {
          finishPendingHighlight();
          openDeepLinkedPackage();
        });
      } else {
        finishPendingHighlight();
      }
      return;
    }
  }
  window.location.href = href;
};

function setupTabs() {
  document.querySelectorAll("#dash-tabs .tab").forEach((tab) => {
    // Tabs are authored hidden when role-gated: unhide them for the right role.
    tab.hidden = Boolean(
      tab.dataset.roles && !tab.dataset.roles.split(" ").includes(myRole)
    );
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
  document.querySelectorAll("#jobs-bar .sub-tab").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.view));
  });
  document.querySelectorAll("#settings-bar .sub-tab").forEach((btn) => {
    btn.addEventListener("click", () => activateSettingsTab(btn.dataset.subtab));
  });
  const visible = [...document.querySelectorAll("#dash-tabs .tab")].filter(
    (tab) => !tab.hidden
  );
  const query = new URLSearchParams(window.location.search);
  const requested = query.get("tab");
  const requestedItem = query.get("item");
  if (requestedItem) {
    pendingHighlight = { tab: requested, id: requestedItem };
    if (requested === "requests") {
      pendingOpenRequest = requestedItem;
    }
    if (requested === "packages") {
      deepLinkPackageId = Number(requestedItem) || null;
    }
  }
  let target = requested;
  const known = visible.some((tab) => tab.dataset.tab === requested);
  if (!target || (!known && !JOB_VIEWS.includes(target) && target !== "jobs")) {
    target = visible[0] ? visible[0].dataset.tab : "overview";
  }
  activateTab(target);
}

function refreshDirtySaves() {
  const profile = me && me.profile;
  const ppfSave = document.getElementById("ppf-save");
  if (ppfSave) {
    const dirty = Boolean(profile) &&
      (document.getElementById("ppf-studio").value.trim() !==
        (profile.studio_name || "").trim() ||
        document.getElementById("ppf-city").value.trim() !==
        (profile.city || "").trim() ||
        document.getElementById("ppf-published").checked !==
        Boolean(profile.is_published));
    ppfSave.hidden = !dirty;
  }
  const accSave = document.getElementById("acc-save");
  if (accSave && me) {
    accSave.hidden = !(
      document.getElementById("acc-email").value.trim() !==
        (me.email || "") ||
      document.getElementById("acc-username").value.trim() !==
        (me.username || "")
    );
  }
  const stSave = document.getElementById("st-save");
  if (stSave) {
    stSave.hidden = !(
      profile &&
      (document.getElementById("st-studio").value !==
        (profile.studio_name || "") ||
        document.getElementById("st-city").value !==
          (profile.city || "") ||
        document.getElementById("st-specialties").value !==
          (profile.specialties || "") ||
        document.getElementById("st-phone").value !==
          (profile.phone || "") ||
        document.getElementById("st-bio").value !==
          (profile.bio || "") ||
        document.getElementById("st-experience").value !==
          (profile.years_experience != null
            ? String(profile.years_experience)
            : "") ||
        document.getElementById("st-languages").value !==
          (profile.languages || "") ||
        document.getElementById("st-equipment").value !==
          (profile.equipment || "") ||
        document.getElementById("st-published").checked !==
          Boolean(profile.is_published))
    );
  }
}

function renderMe() {
  if (me && me.profile && isDemoStripeConnected()) {
    me.profile.stripe_connected = true;
  }
  document.getElementById("acc-username").value = me.username;
  document.getElementById("acc-email").value = me.email;
  document.getElementById("me-role").textContent = me.role;
  document.getElementById("btn-new-gallery").hidden = me.role !== "photographer";
  // Account details is the one section every role can see and edit.
  setSettingsSection("account-section", true);
  setSettingsSection("billing-section", me.role === "photographer");

  const publicBtn = document.getElementById("btn-view-public");
  const canShowPublic =
    me.role === "photographer" && me.profile && me.profile.is_published;
  if (canShowPublic) {
    publicBtn.href = `profile.html?slug=${encodeURIComponent(me.profile.slug)}`;
  }
  publicBtn.hidden = !canShowPublic;
  renderOverview();

  if (me.role !== "photographer" || !me.profile) {
    setSettingsSection("pp-section", false);
    setSettingsSection("profile-studio", false);
    setSettingsSection("studio-settings", false);
    setSettingsSection("clients-settings", false);
    applySettingsTab();
    refreshDirtySaves();
    return;
  }
  const profile = me.profile;
  setSettingsSection("pp-section", true);
  renderProfilePicture();
  setSettingsSection("profile-studio", true);
  setSettingsSection("studio-settings", true);
  setSettingsSection("clients-settings", true);
  document.getElementById("ppf-studio").value = profile.studio_name || "";
  document.getElementById("ppf-city").value = profile.city || "";
  document.getElementById("ppf-published").checked = Boolean(
    profile.is_published
  );
  document.getElementById("me-plan").textContent = profile.plan;
  const stripeConnected = Boolean(profile.stripe_connected);
  const stripeDemo = stripeConnected && isDemoStripeConnected();
  const meStripe = document.getElementById("me-stripe");
  meStripe.textContent = stripeConnected
    ? stripeDemo
      ? "Connected (Test Mode)"
      : "Connected"
    : "Not connected";
  meStripe.classList.toggle("stripe-demo", stripeDemo);
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
  document.getElementById("st-experience").value =
    profile.years_experience != null ? profile.years_experience : "";
  document.getElementById("st-languages").value = profile.languages || "";
  document.getElementById("st-equipment").value = profile.equipment || "";
  document.getElementById("st-published").checked = Boolean(
    profile.is_published
  );
  renderCoverPreview();
  applySettingsTab();
  refreshDirtySaves();
}

/* ---------------------------- overview cards ---------------------------- */

function renderProfilePicture() {
  const preview = document.getElementById("pp-preview");
  const url = me.profile && me.profile.profile_picture;
  const name =
    (me.profile && me.profile.studio_name) || (me && me.username) || "?";
  const initial = name.charAt(0).toUpperCase();
  preview.innerHTML = url
    ? `<img class="pp-img" src="${escapeHtml(
        url
      )}" alt="${escapeHtml(name)}">`
    : `<div class="pp-img pp-img--empty">${escapeHtml(initial)}</div>`;
  preview.classList.toggle("pp-preview--clickable", Boolean(url));
  if (url) {
    preview.setAttribute("role", "button");
    preview.setAttribute("tabindex", "0");
    preview.setAttribute("aria-label", "View profile picture");
  } else {
    preview.removeAttribute("role");
    preview.removeAttribute("tabindex");
    preview.removeAttribute("aria-label");
  }
  renderGettingStarted();
}

const cropState = {
  scale: 1,
  minScale: 1,
  tx: 0,
  ty: 0,
  rotation: 0,
  objectUrl: null,
};

function cropStageSize() {
  const stage = document.getElementById("crop-stage");
  return stage.clientWidth || 300;
}

function cropRotatedDims() {
  const img = document.getElementById("crop-img");
  const swapped = (cropState.rotation / 90) % 2 !== 0;
  return swapped
    ? { w: img.naturalHeight, h: img.naturalWidth }
    : { w: img.naturalWidth, h: img.naturalHeight };
}

function cropMinScale() {
  const { w, h } = cropRotatedDims();
  const size = cropStageSize();
  return Math.max(size / w, size / h);
}

function clampCrop() {
  const size = cropStageSize();
  const { w, h } = cropRotatedDims();
  const maxX = Math.max(0, (w * cropState.scale - size) / 2);
  const maxY = Math.max(0, (h * cropState.scale - size) / 2);
  cropState.tx = Math.min(maxX, Math.max(-maxX, cropState.tx));
  cropState.ty = Math.min(maxY, Math.max(-maxY, cropState.ty));
}

function renderCrop() {
  const img = document.getElementById("crop-img");
  clampCrop();
  img.style.transform =
    `translate(-50%, -50%) translate(${cropState.tx}px, ${cropState.ty}px)` +
    ` rotate(${cropState.rotation}deg) scale(${cropState.scale})`;
}

function resetCrop(resetRotation) {
  if (resetRotation) {
    cropState.rotation = 0;
  }
  cropState.minScale = cropMinScale();
  cropState.scale = cropState.minScale;
  cropState.tx = 0;
  cropState.ty = 0;
  document.getElementById("crop-zoom").value = "1";
  renderCrop();
}

function closeCropModal() {
  document.getElementById("pp-crop-modal").hidden = true;
  if (cropState.objectUrl) {
    URL.revokeObjectURL(cropState.objectUrl);
    cropState.objectUrl = null;
  }
  document.getElementById("crop-img").removeAttribute("src");
}

function openCropModal(file) {
  const img = document.getElementById("crop-img");
  if (cropState.objectUrl) {
    URL.revokeObjectURL(cropState.objectUrl);
  }
  cropState.objectUrl = URL.createObjectURL(file);
  img.onload = () => {
    resetCrop(true);
    document.getElementById("pp-crop-modal").hidden = false;
  };
  img.onerror = () => {
    closeCropModal();
    showToast("Could not read that image.");
  };
  img.src = cropState.objectUrl;
}

function buildCroppedFile() {
  const img = document.getElementById("crop-img");
  const out = 512;
  const size = cropStageSize();
  const canvas = document.createElement("canvas");
  canvas.width = out;
  canvas.height = out;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, out, out);
  ctx.save();
  ctx.translate(out / 2, out / 2);
  ctx.scale(out / size, out / size);
  ctx.translate(cropState.tx, cropState.ty);
  ctx.rotate((cropState.rotation * Math.PI) / 180);
  ctx.scale(cropState.scale, cropState.scale);
  ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
  ctx.restore();
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("Crop failed"));
          return;
        }
        resolve(
          new File([blob], "profile-picture.jpg", {
            type: "image/jpeg",
          })
        );
      },
      "image/jpeg",
      0.92
    );
  });
}

async function uploadProfilePicture(file) {
  const form = new FormData();
  form.append("profile_picture", file);
  const response = await apiFetch("/profiles/picture/", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    showToast(await readError(response));
    return false;
  }
  const data = await response.json();
  me.profile = { ...me.profile, profile_picture: data.profile_picture };
  renderProfilePicture();
  showToast("Profile picture updated.");
  return true;
}

function wireProfilePictureUpload() {
  const button = document.getElementById("btn-upload-pp");
  const input = document.getElementById("pp-file");
  const zoom = document.getElementById("crop-zoom");
  const stage = document.getElementById("crop-stage");

  button.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    input.value = "";
    if (!file) {
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      showToast("Image must be 2 MB or smaller.");
      return;
    }
    if (!file.type || !file.type.startsWith("image/")) {
      showToast("Please choose an image file.");
      return;
    }
    openCropModal(file);
  });

  document
    .getElementById("pp-crop-close")
    .addEventListener("click", closeCropModal);
  document
    .getElementById("crop-cancel")
    .addEventListener("click", closeCropModal);

  zoom.addEventListener("input", () => {
    cropState.scale = cropState.minScale * Number(zoom.value);
    renderCrop();
  });
  document.getElementById("crop-zoom-in").addEventListener("click", () => {
    zoom.value = String(Math.min(4, Number(zoom.value) + 0.15));
    zoom.dispatchEvent(new Event("input"));
  });
  document.getElementById("crop-zoom-out").addEventListener("click", () => {
    zoom.value = String(Math.max(1, Number(zoom.value) - 0.15));
    zoom.dispatchEvent(new Event("input"));
  });
  document.getElementById("crop-rotate").addEventListener("click", () => {
    cropState.rotation = (cropState.rotation + 90) % 360;
    resetCrop(false);
  });
  document
    .getElementById("crop-reset")
    .addEventListener("click", () => resetCrop(true));

  let drag = null;
  stage.addEventListener("pointerdown", (event) => {
    drag = { x: event.clientX, y: event.clientY };
    stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener("pointermove", (event) => {
    if (!drag) {
      return;
    }
    cropState.tx += event.clientX - drag.x;
    cropState.ty += event.clientY - drag.y;
    drag = { x: event.clientX, y: event.clientY };
    renderCrop();
  });
  stage.addEventListener("pointerup", () => {
    drag = null;
  });
  stage.addEventListener("pointercancel", () => {
    drag = null;
  });

  const preview = document.getElementById("pp-preview");
  const viewer = document.getElementById("pp-viewer-modal");
  const viewerImg = document.getElementById("pp-viewer-img");

  function openViewer() {
    const url = me.profile && me.profile.profile_picture;
    if (!url) {
      return;
    }
    viewerImg.src = url;
    viewer.hidden = false;
  }

  function closeViewer() {
    viewer.hidden = true;
    viewerImg.removeAttribute("src");
  }

  preview.addEventListener("click", openViewer);
  preview.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openViewer();
    }
  });
  document
    .getElementById("pp-viewer-close")
    .addEventListener("click", closeViewer);
  viewer.addEventListener("click", (event) => {
    if (event.target === viewer) {
      closeViewer();
    }
  });

  document
    .getElementById("pp-viewer-replace")
    .addEventListener("click", () => {
      closeViewer();
      input.click();
    });

  document
    .getElementById("pp-viewer-remove")
    .addEventListener("click", async () => {
      if (!confirm("Remove your profile picture?")) {
        return;
      }
      try {
        const response = await apiFetch("/profiles/picture/", {
          method: "DELETE",
        });
        if (!response.ok) {
          showToast(await readError(response));
          return;
        }
        me.profile = { ...me.profile, profile_picture: null };
        renderProfilePicture();
        closeViewer();
        showToast("Profile picture removed.");
      } catch (error) {
        console.error(error);
        showToast("Could not remove the photo. Try again.");
      }
    });

  document
    .getElementById("crop-upload")
    .addEventListener("click", async () => {
      const uploadButton = document.getElementById("crop-upload");
      uploadButton.disabled = true;
      try {
        const file = await buildCroppedFile();
        const done = await uploadProfilePicture(file);
        if (done) {
          closeCropModal();
        }
      } catch (error) {
        console.error(error);
        showToast("Crop failed. Try another photo.");
      } finally {
        uploadButton.disabled = false;
      }
    });
}

const DEMO_CONNECT_KEY = "stripe_demo_connected";

function isDemoStripeConnected() {
  try {
    return localStorage.getItem(DEMO_CONNECT_KEY) === "true";
  } catch (error) {
    return false;
  }
}

function demoConnectStripe() {
  showToast("Connecting to Stripe...");
  window.setTimeout(() => {
    try {
      localStorage.setItem(DEMO_CONNECT_KEY, "true");
    } catch (error) {
      console.error(error);
    }
    if (me && me.profile) {
      me.profile.stripe_connected = true;
    }
    renderMe();
    renderPaymentActions();
    updateStripeAlert();
    showToast("Stripe connected (Test Mode).");
  }, 1500);
}

function startOnboard() {
  // SIMULACIÓN FRONTEND: El código real de onboarding está en payments/services.py (start_onboarding).
  if (STRIPE_DEMO_MODE) {
    demoConnectStripe();
    return;
  }
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
      ["awaiting_payment"].includes(booking.status)
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
      (booking) => booking.status === "requested"
    ).length;
    const emptyGalleries = galleriesForOverview.filter(
      (gallery) => !gallery.photo_count
    ).length;
    const connected = Boolean(me.profile && me.profile.stripe_connected);
    const stripeDemo = connected && isDemoStripeConnected();
    const ratingCount = reviewsForOverview.length;
    const ratingAvg = ratingCount
      ? reviewsForOverview.reduce(
          (sum, review) => sum + Number(review.rating || 0),
          0
        ) / ratingCount
      : 0;
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
            value: stripeDemo ? "Connected (Test Mode)" : "Connected",
            hint: stripeDemo
              ? "Test mode: no live charges are processed"
              : "Deposits go straight to your account",
            ok: stripeDemo,
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
        title: "Rating",
        value: ratingCount ? `★ ${ratingAvg.toFixed(1)}` : "★ —",
        hint: ratingCount
          ? `Based on ${ratingCount} review${ratingCount === 1 ? "" : "s"}`
          : "No reviews yet",
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
      (booking) => booking.status === "requested"
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
      <div class="ov-card${card.alert ? " ov-alert" : ""}${
        card.ok ? " ov-ok" : ""
      }"${
        card.tab
          ? ` role="button" tabindex="0" data-goto="${card.tab}"`
          : ""
      }>
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
  renderGettingStarted();
}

/* ----------------------------- empty states ----------------------------- */

const EMPTY_ICONS = {
  clients:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="19" cy="16" r="7"/><path d="M7 39c0-6.6 5.4-12 12-12s12 5.4 12 12"/><path d="M32 11a7 7 0 0 1 0 12"/><path d="M34 27c3.8 2.4 6 6.4 6 12"/></svg>',
  packages:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M24 5 7 13v16l17 8 17-8V13L24 5z"/><path d="M7 13l17 8 17-8"/><path d="M24 21v16"/><path d="M15.5 9l17 8"/></svg>',
  galleries:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="10" width="36" height="28" rx="3"/><circle cx="17" cy="20" r="3.5"/><path d="M10 34l10-10 6 6 5-5 7 7"/></svg>',
  requests:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 8h20l6 14v16H8V22L14 8z"/><path d="M8 22h10l3 5h6l3-5h10"/></svg>',
  payments:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="38" height="26" rx="3"/><path d="M5 20h38"/><path d="M13 29h9"/><path d="M31 29h4"/></svg>',
  bell:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M24 7c-7 0-12 5-12 12v8l-4 6h32l-4-6v-8c0-7-5-12-12-12z"/><path d="M19 33a5 5 0 0 0 10 0"/></svg>',
  star:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M24 7l5.4 11.2 12.4 1.6-9.1 8.6 2.3 12.2L24 33.7 13 40.6l2.3-12.2L6.2 19.8l12.4-1.6L24 7z"/></svg>',
  photos:
    '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="10" width="36" height="28" rx="3"/><circle cx="17" cy="20" r="3.5"/><path d="M10 34l10-10 6 6 5-5 7 7"/></svg>',
};

function emptyState({ icon, title, text, action, actionLabel }) {
  return `
    <div class="empty-state">
      <span class="empty-state-icon">${EMPTY_ICONS[icon] || ""}</span>
      <h4 class="empty-state-title">${escapeHtml(title)}</h4>
      <p class="empty-state-text">${escapeHtml(text)}</p>
      ${
        action && actionLabel
          ? `<button class="btn btn-sm" type="button" data-empty-action="${escapeHtml(
              action
            )}">${escapeHtml(actionLabel)}</button>`
          : ""
      }
    </div>`;
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-empty-action]");
  if (!button) {
    return;
  }
  const action = button.dataset.emptyAction;
  if (action === "add-client") {
    const btn = document.getElementById("btn-add-client");
    if (btn) {
      btn.click();
    }
  } else if (action === "add-package") {
    const btn = document.getElementById("btn-add-package");
    if (btn) {
      btn.click();
    }
  } else if (action === "add-photo") {
    const btn = document.getElementById("btn-add-photo");
    if (btn) {
      btn.click();
    }
  } else if (action === "go-requests") {
    activateTab("requests");
  } else if (action === "browse") {
    window.location.href = "index.html";
  } else if (action === "view-profile") {
    const slug = me && me.profile && me.profile.slug;
    window.location.href = slug
      ? `profile.html?slug=${encodeURIComponent(slug)}`
      : "index.html";
  } else if (action === "connect-stripe") {
    startOnboard();
  }
});

/* --------------------------- getting started ---------------------------- */

function renderGettingStarted() {
  const box = document.getElementById("getting-started");
  if (!box) {
    return;
  }
  if (myRole !== "photographer" || !me) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const profile = me.profile || {};
  const tasks = [
    {
      label: "Upload profile picture",
      done: Boolean(profile.profile_picture),
      action: "settings",
    },
    {
      label: "Create your first package",
      done: catalogPackages.length > 0,
      action: "packages",
    },
    {
      label: "Connect Stripe",
      done: Boolean(profile.stripe_connected) || isDemoStripeConnected(),
      action: "stripe",
    },
  ];
  const pending = tasks.filter((task) => !task.done);
  if (pending.length === 0) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = `
    <div class="gs-head">
      <h3>Getting started</h3>
      <p class="meta">${pending.length} of ${tasks.length} steps left — finish these to start receiving bookings.</p>
    </div>
    <ul class="gs-list">
      ${tasks
        .map(
          (task) => `
        <li class="gs-item${task.done ? " is-done" : ""}">
          <span class="gs-check" aria-hidden="true">${task.done ? "✓" : ""}</span>
          <span class="gs-label">${escapeHtml(task.label)}</span>
          ${
            task.done
              ? '<span class="gs-done">Done</span>'
              : `<button class="btn btn-ghost btn-sm" type="button" data-gs-action="${task.action}">Go</button>`
          }
        </li>`
        )
        .join("")}
    </ul>`;
  box.querySelectorAll("[data-gs-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.gsAction;
      if (action === "settings") {
        activateTab("profile");
        activateSettingsTab("public");
      } else if (action === "packages") {
        activateTab("packages");
      } else if (action === "stripe") {
        startOnboard();
      }
    });
  });
}

/* ----------------------------- notifications ---------------------------- */

function renderNotifications(data) {
  const list = document.getElementById("notif-list");
  if (!data.results || data.results.length === 0) {
    list.innerHTML = emptyState({
      icon: "bell",
      title: "No notifications yet",
      text: "Booking updates, new messages and payment confirmations will appear here.",
    });
    return;
  }
  list.innerHTML = data.results
    .map(
      (item, index) => `
      <div class="notif ${item.is_read ? "" : "unread"}${
        item.link ? " notif-link" : ""
      }"${
        item.link
          ? ` data-link="${escapeHtml(
              item.link
            )}" data-note-id="${item.id}" role="button" tabindex="0"`
          : ""
      } style="animation-delay: ${Math.min(index, 9) * 45}ms">
        ${
          item.link
            ? '<span class="notif-go" aria-hidden="true">&rarr;</span>'
            : ""
        }
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
      refreshBellBadge();
    });
  });
}

function openNotificationTarget(item) {
  if (!item || !item.dataset.link) {
    return;
  }
  window.lumenNavigate(item.dataset.link);
}

document.getElementById("notif-list").addEventListener("click", (event) => {
  if (event.target.closest("[data-read]")) {
    return;
  }
  openNotificationTarget(event.target.closest("[data-link]"));
});
document
  .getElementById("notif-list")
  .addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    const item = event.target.closest("[data-link]");
    if (!item) {
      return;
    }
    event.preventDefault();
    openNotificationTarget(item);
  });

// The header bell marks everything read when its panel opens.
document.addEventListener("notifications:read", loadNotifications);

// A WebSocket message arrived (chat, offer, payment…): refresh the list.
document.addEventListener("notifications:push", loadNotifications);

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
  const cashPaid = Boolean(pays.cash && pays.cash.status === "paid");
  if (cashPaid) {
    return '<span class="status-chip status-paid">fully paid</span>';
  }
  if (booking.status === "accepted") {
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
  if (booking.status === "awaiting_payment" && !depositPaid) {
    return `<button class="btn btn-sm" type="button" data-pay="${
      booking.id
    }" data-kind="deposit">Pay deposit (20%)</button>`;
  }
  if (depositPaid) {
    return '<span class="status-chip status-paid">deposit paid</span>';
  }
  return "";
}

/* One row per request: clicking it opens the detail panel (details + chat). */
function requestRow(booking, role) {
  const other =
    role === "photographer"
      ? booking.customer_username
      : booking.profile_studio_name || booking.profile_slug;
  return `
    <div class="request-row is-clickable" role="button" tabindex="0"
         data-highlight-id="${booking.id}" data-open-request="${booking.id}">
      <div class="req-info">
        <strong>${escapeHtml(booking.package_title)}</strong>
        <span class="meta">${escapeHtml(other)} · ${formatDate(
          booking.date
        )}</span>
        ${booking.message ? `<span class="req-msg">${escapeHtml(booking.message)}</span>` : ""}
      </div>
      ${statusChip(booking.status)}
      <span class="req-open" aria-hidden="true">&rsaquo;</span>
    </div>`;
}

function markRequestRowActive() {
  document
    .querySelectorAll("#requests-list [data-open-request]")
    .forEach((row) => {
      row.classList.toggle(
        "is-open",
        String(row.dataset.openRequest) === String(activeRequestId)
      );
    });
}

function closeRequestDetail() {
  activeRequestId = null;
  clearInterval(chatPollTimer);
  chatPollTimer = null;
  sessionStorage.removeItem("lumen_open_request");
  const drawer = document.getElementById("request-drawer");
  const backdrop = document.getElementById("request-drawer-backdrop");
  if (drawer) {
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
  }
  if (backdrop) {
    backdrop.classList.remove("is-open");
  }
  markRequestRowActive();
}

function isRequestDrawerOpen() {
  const drawer = document.getElementById("request-drawer");
  return Boolean(drawer && drawer.classList.contains("is-open"));
}

/* Opening the drawer is idempotent: switching cards while it is open only
   refreshes the content, the panel never closes (no flicker). */
function openRequestDrawer() {
  const drawer = document.getElementById("request-drawer");
  const backdrop = document.getElementById("request-drawer-backdrop");
  if (!drawer || drawer.classList.contains("is-open")) {
    return;
  }
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  if (backdrop) {
    backdrop.classList.add("is-open");
  }
}

function detailNote(booking, isPhotographer) {
  if (booking.status === "requested") {
    return isPhotographer
      ? '<p class="detail-note">Negotiate below: send a custom offer, record a cash payment, or reject.</p>'
      : '<p class="detail-note">Waiting for the photographer to answer your request.</p>';
  }
  if (booking.status === "awaiting_payment") {
    return isPhotographer
      ? '<p class="detail-note">Waiting for the client\u2019s deposit. You can still adjust the offer or record a cash payment.</p>'
      : '<p class="detail-note">Pay the 20% deposit to confirm the booking.</p>';
  }
  if (booking.status === "accepted") {
    return isPhotographer
      ? '<p class="detail-note">Deposit received. Upload the gallery after the session, then mark as completed.</p>'
      : '<p class="detail-note">Deposit received — your date is confirmed.</p>';
  }
  if (booking.status === "completed") {
    return '<p class="detail-note">Session completed.</p>';
  }
  if (booking.status === "rejected") {
    return '<p class="detail-note">This request was rejected.</p>';
  }
  if (booking.status === "cancelled") {
    return '<p class="detail-note">This booking was cancelled.</p>';
  }
  return "";
}

function renderRequestDetail(booking) {
  const body = document.getElementById("drawer-body");
  const actionsBox = document.getElementById("drawer-actions");
  if (!body || !actionsBox) {
    return;
  }
  const isPhotographer = myRole === "photographer";
  const other = isPhotographer
    ? `Client @${escapeHtml(booking.customer_username)}`
    : `Studio ${escapeHtml(
        booking.profile_studio_name || booking.profile_slug || ""
      )}`;
  const price = Number(booking.effective_price || 0);
  const policyLabel = cancellationPolicyLabel(booking.cancellation_policy);
  const policyBanner =
    isPhotographer && booking.policy_accepted
      ? `<p class="policy-banner">Client agreed to the ${policyLabel} policy${
          booking.cancellation_policy_summary
            ? ` — ${booking.cancellation_policy_summary}`
            : "."
        }</p>`
      : "";
  const rows = [
    ["Date", formatDate(booking.date)],
    booking.event_time ? ["Event time", String(booking.event_time)] : null,
    booking.event_location ? ["Location", booking.event_location] : null,
    booking.final_price ? ["Agreed price", `$${price.toFixed(2)}`] : null,
    booking.status === "awaiting_payment" && booking.deposit_deadline
      ? [
          "Deposit deadline",
          formatDate(booking.deposit_deadline, { withTime: true }),
        ]
      : null,
  ].filter(Boolean);
  let actions = "";
  const canCancel = [
    "requested",
    "awaiting_payment",
    "accepted",
  ].includes(booking.status);
  const cancelBtn = canCancel
    ? `<button class="btn btn-ghost btn-sm btn-danger" type="button" data-detail-cancel="${booking.id}">Cancel Booking</button>`
    : "";
  if (isPhotographer) {
    if (
      booking.status === "requested" ||
      booking.status === "awaiting_payment"
    ) {
      actions = `
        <button class="btn btn-ghost btn-sm btn-danger" type="button" data-detail-reject="${booking.id}">Reject</button>
        <button class="btn btn-sm" type="button" data-detail-offer="${booking.id}" data-tip="Change the final price or details before sending the payment request.">Customize Offer</button>
        <button class="btn btn-ghost btn-sm" type="button" data-detail-cash="${booking.id}" data-tip="Use this if the client paid you outside the app. It bypasses Stripe.">Mark as Paid in Cash</button>
        <p class="hint">Bypasses Stripe. Use only if paid outside the platform.</p>
        ${cancelBtn}`;
    } else if (booking.status === "accepted") {
      actions = `<button class="btn btn-sm" type="button" data-detail-complete="${booking.id}">Mark as Completed</button>${cancelBtn}`;
    }
  } else if (
    booking.status === "awaiting_payment" ||
    booking.status === "accepted"
  ) {
    actions = payActionHtml(booking) + cancelBtn;
  } else if (booking.status === "requested") {
    actions = cancelBtn;
  }
  if (
    booking.status === "cancelled" &&
    isPhotographer &&
    booking.payment_status === "refund_pending"
  ) {
    actions = `<button class="btn btn-sm btn-danger" type="button" data-detail-refund="${booking.id}" data-tip="Return the client's deposit in full. The refund is recorded immediately.">Refund Deposit</button>`;
  }
  let reviewBlock = "";
  if (
    isPhotographer &&
    !["requested", "rejected", "cancelled"].includes(booking.status)
  ) {
    const review = reviewsForOverview.find(
      (item) => item.customer_username === booking.customer_username
    );
    if (review) {
      reviewBlock = `
      <div class="req-review">
        <div class="review-head">
          ${starsHtml(review.rating)}
          <span class="meta">Review from @${escapeHtml(
            review.customer_username
          )}</span>
        </div>
        ${
          review.comment
            ? `<p class="req-msg">${escapeHtml(review.comment)}</p>`
            : ""
        }
      </div>`;
    }
  }
  const switching = body.dataset.renderedId !== String(booking.id);
  body.dataset.renderedId = String(booking.id);
  body.innerHTML = `
    <div class="detail-summary">
      <div class="detail-title">
        <strong>${escapeHtml(booking.package_title)}</strong>
        <span class="meta">${other} · ${formatDate(booking.date)}</span>
      </div>
      <div class="detail-price">
        ${statusChip(booking.status)}
        <strong>$${price.toFixed(2)}</strong>
      </div>
    </div>
    ${detailNote(booking, isPhotographer)}
    ${policyBanner}
    <div class="detail-grid">
      ${rows
        .map(
          ([key, value]) =>
            `<div class="kv"><span>${escapeHtml(
              key
            )}</span><strong>${escapeHtml(value)}</strong></div>`
        )
        .join("")}
    </div>
    ${
      booking.event_notes
        ? `<p class="req-msg"><strong>Notes:</strong> ${escapeHtml(
            booking.event_notes
          )}</p>`
        : ""
    }
    ${booking.message ? `<p class="req-msg">${escapeHtml(booking.message)}</p>` : ""}
    ${reviewBlock}
    <div class="chat-box">
      <div class="chat-list" id="chat-list"><p class="meta">Loading messages…</p></div>
      ${
        booking.status === "cancelled"
          ? '<div class="chat-closed">This conversation is closed because the booking was cancelled.</div>'
          : `<form class="chat-form" id="chat-form">
        <input id="chat-input" type="text" maxlength="500" placeholder="Write a message…" autocomplete="off" aria-label="Message" />
        <button class="btn btn-sm" type="submit">Send</button>
      </form>`
      }
    </div>`;
  if (switching) {
    body.scrollTop = 0;
  }
  actionsBox.innerHTML = actions
    ? `<div class="detail-actions">${actions}</div>`
    : "";
  const offerButton = actionsBox.querySelector("[data-detail-offer]");
  if (offerButton) {
    offerButton.addEventListener("click", () => openOfferModal(booking));
  }
  const cashButton = actionsBox.querySelector("[data-detail-cash]");
  if (cashButton) {
    cashButton.addEventListener("click", () => confirmCashPayment(booking.id));
  }
  const rejectButton = actionsBox.querySelector("[data-detail-reject]");
  if (rejectButton) {
    rejectButton.addEventListener("click", () => confirmReject(booking.id));
  }
  const completeButton = actionsBox.querySelector("[data-detail-complete]");
  if (completeButton) {
    completeButton.addEventListener("click", () =>
      confirmComplete(booking.id)
    );
  }
  const cancelButton = actionsBox.querySelector("[data-detail-cancel]");
  if (cancelButton) {
    cancelButton.addEventListener("click", () => openCancelModal(booking));
  }
  const refundButton = actionsBox.querySelector("[data-detail-refund]");
  if (refundButton) {
    refundButton.addEventListener("click", () =>
      confirmRefundDeposit(booking.id)
    );
  }
  actionsBox.querySelectorAll("[data-pay]").forEach((button) => {
    button.addEventListener("click", () =>
      startPayment(button.dataset.pay, button.dataset.kind || "deposit")
    );
  });
  const chatForm = document.getElementById("chat-form");
  if (chatForm) {
    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = document.getElementById("chat-input");
      const text = input.value.trim();
      if (!text) {
        return;
      }
      input.value = "";
      await sendChatMessage(booking.id, text);
    });
  }
}

async function openRequestDetail(id) {
  const drawer = document.getElementById("request-drawer");
  const body = document.getElementById("drawer-body");
  const actionsBox = document.getElementById("drawer-actions");
  if (!drawer || !body || !actionsBox) {
    return;
  }
  const wasOpen = drawer.classList.contains("is-open");
  activeRequestId = String(id);
  sessionStorage.setItem("lumen_open_request", String(id));
  markRequestRowActive();
  clearInterval(chatPollTimer);
  chatPollTimer = null;
  // Paint what we already know right away: switching cards never flashes.
  const cached = bookingsForOverview.find(
    (item) => String(item.id) === String(id)
  );
  if (cached) {
    renderRequestDetail(cached);
  } else {
    body.dataset.renderedId = "";
    body.innerHTML = '<p class="meta">Loading…</p>';
    actionsBox.innerHTML = "";
  }
  openRequestDrawer();
  try {
    const response = await apiFetch(`/bookings/${id}/`);
    if (response.ok) {
      const booking = await response.json();
      const index = bookingsForOverview.findIndex(
        (item) => String(item.id) === String(booking.id)
      );
      if (index >= 0) {
        bookingsForOverview[index] = booking;
      } else {
        bookingsForOverview.unshift(booking);
      }
      renderOverview();
      if (String(activeRequestId) === String(id)) {
        renderRequestDetail(booking);
      }
    }
  } catch (error) {
    console.error(error);
  }
  const booking = bookingsForOverview.find(
    (item) => String(item.id) === String(id)
  );
  if (!booking) {
    body.innerHTML = '<p class="meta">This request is no longer available.</p>';
    actionsBox.innerHTML = "";
    return;
  }
  await loadChat(booking.id);
  chatPollTimer = window.setInterval(() => {
    if (activeRequestId) {
      loadChat(activeRequestId);
    }
  }, 4000);
  if (!wasOpen) {
    body.scrollTop = 0;
  }
}

/* Drawer chrome: the X button, the dark backdrop and the Escape key all
   close the panel. Clicking another card only refreshes the content, the
   panel stays open (no flicker). */
const drawerCloseButton = document.getElementById("drawer-close");
if (drawerCloseButton) {
  drawerCloseButton.addEventListener("click", closeRequestDetail);
}
const drawerBackdrop = document.getElementById("request-drawer-backdrop");
if (drawerBackdrop) {
  drawerBackdrop.addEventListener("click", closeRequestDetail);
}
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !isRequestDrawerOpen()) {
    return;
  }
  // Let open modals handle Escape first (offer, simulated checkout…).
  const offerModal = document.getElementById("offer-modal");
  const simModal = document.getElementById("sim-checkout-modal");
  if (
    (offerModal && !offerModal.hidden) ||
    (simModal && !simModal.hidden)
  ) {
    return;
  }
  closeRequestDetail();
});

/* Filter chips at the top of the requests list. */
function setRequestFilter(name) {
  requestFilter = REQUEST_FILTERS[name] ? name : "all";
  document
    .querySelectorAll("#request-filters [data-filter]")
    .forEach((chip) => {
      chip.classList.toggle(
        "is-active",
        chip.dataset.filter === requestFilter
      );
    });
}

document
  .querySelectorAll("#request-filters [data-filter]")
  .forEach((chip) => {
    chip.addEventListener("click", () => {
      setRequestFilter(chip.dataset.filter);
      if (lastRequestsData) {
        renderRequests(lastRequestsData, lastRequestsRole);
      }
    });
  });

async function loadChat(bookingId) {
  const list = document.getElementById("chat-list");
  if (!list) {
    return;
  }
  try {
    const response = await apiFetch(`/bookings/${bookingId}/messages/`);
    if (!response.ok) {
      return;
    }
    const messages = await response.json();
    renderChat(messages, list.dataset.chatFor !== String(bookingId));
    list.dataset.chatFor = String(bookingId);
  } catch (error) {
    console.error(error);
  }
}

function renderChat(messages, forceBottom) {
  const list = document.getElementById("chat-list");
  if (!list) {
    return;
  }
  const username = localStorage.getItem(STORAGE.username) || "";
  if (!messages || messages.length === 0) {
    list.innerHTML = '<p class="meta">No messages yet. Say hello!</p>';
    return;
  }
  const nearBottom =
    list.scrollHeight - list.scrollTop - list.clientHeight < 60;
  list.innerHTML = messages
    .map((message) => {
      const time = `<span class="chat-time">${formatDate(message.created_at, {
        withTime: true,
      })}</span>`;
      if (message.is_system || !message.sender_username) {
        return `<div class="chat-line chat-system">${escapeHtml(
          message.text
        )}${time}</div>`;
      }
      const mine = message.sender_username === username;
      return `
      <div class="chat-line ${mine ? "chat-mine" : "chat-theirs"}">
        <div class="chat-bubble">
          <span class="chat-author">${
            mine ? "You" : escapeHtml(message.sender_username)
          }</span>
          <span class="chat-text">${escapeHtml(message.text)}</span>
        </div>
        ${time}
      </div>`;
    })
    .join("");
  if (forceBottom || nearBottom) {
    list.scrollTop = list.scrollHeight;
  }
}

async function sendChatMessage(bookingId, text) {
  try {
    const response = await apiFetch(`/bookings/${bookingId}/messages/`, {
      method: "POST",
      body: { text },
    });
    if (!response.ok) {
      showToast(await readError(response));
      return;
    }
    await loadChat(bookingId);
  } catch (error) {
    console.error(error);
    showToast("Could not reach the API.");
  }
}

function renderRequests(data, role) {
  document.getElementById("requests-title").textContent =
    role === "photographer" ? "Incoming requests" : "My requests";
  const list = document.getElementById("requests-list");
  lastRequestsData = data;
  lastRequestsRole = role;
  bookingsForOverview = data.results || [];
  if (role === "customer") {
    // A photographer cancellation leaves a pending refund: tell the client
    // once per booking, no matter how many times the list refreshes.
    const cancelledByStudio = bookingsForOverview.find(
      (item) =>
        item.status === "cancelled" &&
        item.payment_status === "refund_pending" &&
        !sessionStorage.getItem(`lumen_refund_notice_${item.id}`)
    );
    if (cancelledByStudio) {
      sessionStorage.setItem(
        `lumen_refund_notice_${cancelledByStudio.id}`,
        "1"
      );
      showNotice({
        title: "Booking cancelled",
        text: "The photographer has cancelled. A full refund will be processed.",
        tone: "warning",
      });
    }
  }
  renderOverview();
  updateStripeAlert();
  renderPaymentsSummary();
  renderPaymentsTable();

  // Filter chips: keep counts and the active pill in sync.
  const allResults = data.results || [];
  const counts = {
    all: allResults.length,
    pending: allResults.filter(REQUEST_FILTERS.pending).length,
    accepted: allResults.filter(REQUEST_FILTERS.accepted).length,
    cancelled: allResults.filter(REQUEST_FILTERS.cancelled).length,
  };
  document
    .querySelectorAll("#request-filters [data-filter]")
    .forEach((chip) => {
      const key = chip.dataset.filter;
      const countEl = chip.querySelector(".filter-count");
      if (countEl) {
        countEl.textContent = String(counts[key] ?? 0);
      }
      chip.classList.toggle("is-active", key === requestFilter);
    });
  // A request opened from a notification must always be visible.
  if (pendingOpenRequest) {
    setRequestFilter("all");
  }
  const visible = allResults.filter(
    REQUEST_FILTERS[requestFilter] || REQUEST_FILTERS.all
  );

  if (allResults.length === 0) {
    list.innerHTML =
      myRole === "photographer"
        ? emptyState({
            icon: "requests",
            title: "No booking requests yet",
            text: "New requests from clients will appear here so you can accept, counter-offer or reject them.",
            action: "view-profile",
            actionLabel: "See your public profile",
          })
        : emptyState({
            icon: "requests",
            title: "No booking requests yet",
            text: "Find a photographer you like and send your first booking request.",
            action: "browse",
            actionLabel: "Explore Photographers",
          });
  } else if (visible.length === 0) {
    list.innerHTML = '<p class="meta">No requests in this filter.</p>';
  } else {
    list.innerHTML = visible
      .map((booking) => requestRow(booking, role))
      .join("");
    applyPendingHighlight(list, "requests");
    list.querySelectorAll("[data-open-request]").forEach((row) => {
      const open = () => openRequestDetail(row.dataset.openRequest);
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    });
  }

  if (pendingOpenRequest) {
    const wanted = pendingOpenRequest;
    pendingOpenRequest = null;
    if (
      bookingsForOverview.some((item) => String(item.id) === String(wanted))
    ) {
      openRequestDetail(wanted);
      return;
    }
  }
  if (activeRequestId) {
    const current = bookingsForOverview.find(
      (item) => String(item.id) === String(activeRequestId)
    );
    if (current) {
      renderRequestDetail(current);
      markRequestRowActive();
    } else {
      closeRequestDetail();
    }
    return;
  }
  const stored = sessionStorage.getItem("lumen_open_request");
  if (
    stored &&
    bookingsForOverview.some((item) => String(item.id) === stored)
  ) {
    openRequestDetail(stored);
  }
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

async function bookingAction(id, action, body) {
  try {
    const response = await apiFetch(`/bookings/${id}/${action}/`, {
      method: "POST",
      body: body || {},
    });
    if (!response.ok) {
      showToast(await readError(response));
      return false;
    }
    return true;
  } catch (error) {
    console.error(error);
    showToast("Could not reach the API.");
    return false;
  }
}

/* Reload everything the open detail depends on: payments first so the
   pay buttons reflect the latest state, then the list (which re-renders
   the detail), chat, notifications and the bell badge. */
async function refreshRequestView(id) {
  await loadPayments();
  await loadRequests();
  if (myRole === "photographer") {
    await Promise.all([loadShoots(), loadClients(), loadGalleries()]);
  } else {
    // A cancelled booking must disappear from the client's galleries.
    await loadGalleries();
  }
  await loadChat(id);
  await loadNotifications();
  refreshBellBadge();
}

async function confirmCashPayment(id) {
  const confirmed = window.confirm(
    "Mark this booking as paid in cash? The full amount counts toward your earnings."
  );
  if (!confirmed) {
    return;
  }
  const ok = await bookingAction(id, "pay_cash");
  if (ok) {
    showToast("Cash payment recorded — added to your earnings.");
    await refreshRequestView(id);
  }
}

async function confirmComplete(id) {
  const confirmed = window.confirm(
    "Mark this session as completed? The client will be asked to leave a review."
  );
  if (!confirmed) {
    return;
  }
  const ok = await bookingAction(id, "complete");
  if (ok) {
    showToast("Booking completed.");
    await refreshRequestView(id);
  }
}

async function confirmReject(id) {
  const confirmed = window.confirm(
    "Are you sure you want to reject this booking? This action cannot be undone."
  );
  if (!confirmed) {
    return;
  }
  const ok = await bookingAction(id, "reject");
  if (ok) {
    showToast("Request rejected.");
    await refreshRequestView(id);
  }
}

async function confirmRefundDeposit(id) {
  const confirmed = window.confirm(
    "Refund the client's deposit in full? This cannot be undone."
  );
  if (!confirmed) {
    return;
  }
  const ok = await bookingAction(id, "refund");
  if (ok) {
    showToast("Deposit refunded.");
    await refreshRequestView(id);
  }
}

/* Cancellation modal: photographers always end up refunding in full
   (pending until issued from the request); clients follow the package
   policy (Flexible 48h, Moderate 50% at 7 days, Strict never). Without a
   paid deposit there is no money at risk, so the message stays generic. */
function openCancelModal(booking) {
  const depositCents = booking.deposit_cents;
  const hasDeposit = depositCents !== null && depositCents !== undefined;
  const amount = `$${(Number(depositCents || 0) / 100).toFixed(2)}`;
  const refundCents = Number(booking.expected_refund_cents || 0);
  const refundAmount = `$${(refundCents / 100).toFixed(2)}`;
  const policyLabel = cancellationPolicyLabel(booking.cancellation_policy);
  let message;
  let noticeText;
  let noticeTone = "success";
  if (myRole === "photographer") {
    message =
      "Are you sure you want to cancel? Canceling as a photographer " +
      "issues a full refund to the client and releases the date.";
    noticeText = hasDeposit
      ? "The client will receive a full refund. Issue it with the " +
        "“Refund Deposit” button in this booking."
      : "The date is available again for new bookings.";
  } else if (!hasDeposit) {
    message = "Are you sure you want to cancel this booking?";
    noticeText =
      "No payment was collected for this booking, so nothing was charged.";
  } else if (refundCents >= Number(depositCents)) {
    message =
      `You are cancelling with enough time. Your deposit of ${amount} ` +
      "will be fully refunded.";
    noticeText =
      `Your deposit of ${amount} has been refunded. ` +
      "It will return to your original payment method.";
  } else if (refundCents > 0) {
    const percent = Math.round((refundCents / Number(depositCents)) * 100);
    message =
      `You will receive a ${refundAmount} refund (${percent}% of your ` +
      `deposit) according to the ${policyLabel} policy.`;
    noticeText =
      `A refund of ${refundAmount} (${percent}% of your deposit) has been ` +
      "processed to your original payment method.";
  } else {
    message =
      `Warning: according to the ${policyLabel} policy, your deposit of ` +
      `${amount} is non-refundable.`;
    noticeTone = "danger";
    noticeText =
      "Booking cancelled. Per the policy, the deposit is non-refundable.";
  }
  let modal = document.getElementById("cancel-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "cancel-modal";
    modal.className = "modal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="modal-panel">
        <button class="modal-close" id="cancel-close" type="button" aria-label="Close">&times;</button>
        <h3>Cancel Booking</h3>
        <p class="modal-sub" id="cancel-message"></p>
        <div class="form-actions">
          <button class="btn btn-ghost" id="cancel-keep" type="button">Keep booking</button>
          <button class="btn btn-danger" id="cancel-confirm" type="button">Cancel Booking</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const closeCancel = () => {
      modal.hidden = true;
      document.body.style.overflow = "";
    };
    modal.addEventListener("click", (event) => {
      if (
        event.target === modal ||
        event.target.closest("#cancel-close") ||
        event.target.closest("#cancel-keep")
      ) {
        closeCancel();
      }
    });
    document
      .getElementById("cancel-confirm")
      .addEventListener("click", async () => {
        const id = modal.dataset.booking;
        const confirmBtn = document.getElementById("cancel-confirm");
        confirmBtn.disabled = true;
        const ok = await bookingAction(id, "cancel");
        confirmBtn.disabled = false;
        if (ok) {
          closeCancel();
          showNotice({
            title: "Booking cancelled",
            text: modal.dataset.notice,
            tone: modal.dataset.noticeTone || "success",
          });
          await refreshRequestView(id);
        }
      });
  }
  modal.dataset.booking = String(booking.id);
  modal.dataset.notice = noticeText;
  modal.dataset.noticeTone = noticeTone;
  document.getElementById("cancel-message").textContent = message;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function openOfferModal(booking) {
  let modal = document.getElementById("offer-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "offer-modal";
    modal.className = "modal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="modal-panel">
        <button class="modal-close" id="offer-close" type="button" aria-label="Close">&times;</button>
        <h3>Customize Offer</h3>
        <p class="meta">Propose the final price for this request. The client sees the offer in the chat and by notification.</p>
        <label for="offer-price">Final price (USD)</label>
        <input id="offer-price" type="number" min="1" step="0.01" inputmode="decimal" />
        <p class="hint">The 20% deposit will be requested to the client upon accepting this offer.</p>
        <div class="form-actions">
          <button class="btn btn-ghost" id="offer-cancel" type="button">Cancel</button>
          <button class="btn" id="offer-send" type="button">Send offer</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    const closeOffer = () => {
      modal.hidden = true;
      document.body.style.overflow = "";
    };
    modal.addEventListener("click", (event) => {
      if (
        event.target === modal ||
        event.target.closest("#offer-close") ||
        event.target.closest("#offer-cancel")
      ) {
        closeOffer();
      }
    });
    document
      .getElementById("offer-send")
      .addEventListener("click", async () => {
        const input = document.getElementById("offer-price");
        const price = Number(input.value);
        if (!input.value || !Number.isFinite(price) || price <= 0) {
          showToast("Enter a valid price greater than zero.");
          input.focus();
          return;
        }
        const id = modal.dataset.booking;
        const sendButton = document.getElementById("offer-send");
        sendButton.disabled = true;
        const ok = await bookingAction(id, "offer", { final_price: price });
        sendButton.disabled = false;
        if (ok) {
          modal.hidden = true;
          document.body.style.overflow = "";
          showToast("Offer sent to the client.");
          await refreshRequestView(id);
        }
      });
  }
  modal.dataset.booking = String(booking.id);
  const input = document.getElementById("offer-price");
  input.value = Number(booking.effective_price || 0).toFixed(2);
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  input.focus();
  input.select();
}

async function startPayment(bookingId, kind = "deposit") {
  // SIMULACIÓN FRONTEND: El flujo real crea una Checkout Session en Django (start_checkout) y redirige a Stripe. Aquí simulamos el pago para la demo.
  if (STRIPE_DEMO_MODE) {
    const booking = bookingsForOverview.find(
      (item) => String(item.id) === String(bookingId)
    );
    openSimulatedCheckout(bookingId, kind, {
      title: booking ? booking.package_title : "",
    });
    return;
  }
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
    list.innerHTML = emptyState({
      icon: "requests",
      title: "No shoots yet",
      text: "Accepted bookings show up here with their date, status and next step.",
      action: "go-requests",
      actionLabel: "View requests",
    });
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
  renderPaymentsSummary();
  renderPaymentsTable();
  if (items.length === 0) {
    list.innerHTML =
      myRole === "photographer"
        ? emptyState({
            icon: "galleries",
            title: "No galleries yet",
            text: "Galleries are created from a shoot once it is ready. Your shared photos will appear here.",
            action: "go-requests",
            actionLabel: "View bookings",
          })
        : emptyState({
            icon: "galleries",
            title: "No galleries yet",
            text: "Photos shared with you by your photographer will appear here.",
            action: "browse",
            actionLabel: "Find a photographer",
          });
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
    const awaitingDeposit = detail.booking_status === "awaiting_payment";
    const awaitingBalance =
      detail.booking_status === "accepted" && !currentGalleryPaid;
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
  if (!document.getElementById("pf-preview").hidden) {
    if (event.key === "Escape") {
      closePortfolioPreview();
    } else if (event.key === "ArrowRight") {
      stepPortfolioPreview(1);
    } else if (event.key === "ArrowLeft") {
      stepPortfolioPreview(-1);
    }
    return;
  }
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
    document.getElementById("collection-modal").hidden = true;
    document.getElementById("client-modal").hidden = true;
    document.getElementById("reply-modal").hidden = true;
  }
});

/* -------------------------------- catalog ------------------------------- */

function renderPackages(items) {
  catalogPackages = items;
  const list = document.getElementById("pkg-list");
  if (items.length === 0) {
    list.innerHTML = emptyState({
      icon: "packages",
      title: "No packages yet",
      text: "Create your first package to start receiving bookings.",
      action: "add-package",
      actionLabel: "+ Create Package",
    });
    renderGettingStarted();
    return;
  }
  list.innerHTML = items
    .map(
      (pkg) => `
      <div class="package-card" data-highlight-id="${pkg.id}">
        <h3>${escapeHtml(pkg.title)}</h3>
        <p class="pkg-desc">${escapeHtml(pkg.description || "No description")}</p>
        <div class="pkg-price">${priceRangeLabel(pkg.price, pkg.price_max)}</div>
        <div class="pkg-actions">
          <button class="btn btn-sm" type="button" data-edit-pkg="${pkg.id}">Edit</button>
          <button class="btn btn-ghost btn-sm" type="button" data-del-pkg="${pkg.id}">Delete</button>
        </div>
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
  renderGettingStarted();
}

function renderCollectionChips() {
  const bar = document.getElementById("collection-chips");
  if (!bar) {
    return;
  }
  if (catalogCollections.length === 0) {
    activeCollectionFilter = "all";
    bar.hidden = true;
    bar.innerHTML = "";
    return;
  }
  const total = portfolioItems.length;
  const chips = [
    `<span class="filter-chip${
      activeCollectionFilter === "all" ? " is-active" : ""
    }" data-collection="all">All <span class="filter-count">${total}</span></span>`,
  ];
  catalogCollections.forEach((collection) => {
    const count = portfolioItems.filter(
      (photo) => photo.collection === collection.id
    ).length;
    chips.push(`
      <span class="filter-chip${
        activeCollectionFilter === String(collection.id) ? " is-active" : ""
      }" data-collection="${collection.id}">${escapeHtml(
      collection.title
    )} <span class="filter-count">${count}</span><button class="chip-x" type="button" data-del-collection="${
      collection.id
    }" aria-label="Delete collection">&times;</button></span>`);
  });
  bar.innerHTML = chips.join("");
  bar.hidden = false;
  bar.querySelectorAll("[data-collection]").forEach((chip) => {
    chip.addEventListener("click", (event) => {
      if (event.target.closest("[data-del-collection]")) {
        return;
      }
      activeCollectionFilter = chip.dataset.collection;
      renderCollectionChips();
      renderPortfolioItems(portfolioItems);
    });
  });
  bar.querySelectorAll("[data-del-collection]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!confirm("Delete this collection? Its photos stay in your portfolio.")) {
        return;
      }
      const response = await apiFetch(
        `/portfolio-collections/${button.dataset.delCollection}/`,
        { method: "DELETE" }
      ).catch(() => null);
      if (response && response.ok) {
        showToast("Collection deleted.");
        if (activeCollectionFilter === button.dataset.delCollection) {
          activeCollectionFilter = "all";
        }
        loadCatalog();
      } else if (response) {
        showToast(await readError(response));
      }
    });
  });
}

function renderPortfolioItems(items) {
  portfolioItems = items;
  const list = document.getElementById("portfolio-list");
  const visible = items.filter((photo) => {
    if (activeCollectionFilter === "all") {
      return true;
    }
    if (activeCollectionFilter === "none") {
      return !photo.collection;
    }
    return photo.collection === Number(activeCollectionFilter);
  });
  if (visible.length === 0) {
    portfolioPreviewPhotos = [];
    list.innerHTML =
      items.length === 0
        ? emptyState({
            icon: "photos",
            title: "No photos yet",
            text: "Upload your best work so clients can see your style before they book.",
            action: "add-photo",
            actionLabel: "+ Add photo",
          })
        : '<p class="meta">No photos in this collection yet.</p>';
    return;
  }
  portfolioPreviewPhotos = visible;
  list.innerHTML = visible
    .map(
      (photo, index) => `
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
    const [packagesResponse, photosResponse, collectionsResponse] =
      await Promise.all([
        apiFetch(`/packages/?profile=${encodeURIComponent(profile.slug)}`),
        apiFetch(`/portfolio-photos/?profile=${encodeURIComponent(profile.slug)}`),
        apiFetch(
          `/portfolio-collections/?profile=${encodeURIComponent(profile.slug)}`
        ),
      ]);
    if (packagesResponse.ok) {
      const data = await packagesResponse.json();
      renderPackages(data.results || []);
    }
    if (collectionsResponse.ok) {
      const data = await collectionsResponse.json();
      catalogCollections = data.results || [];
    }
    if (photosResponse.ok) {
      const data = await photosResponse.json();
      renderPortfolioItems(data.results || []);
    }
    renderCollectionChips();
  } catch (error) {
    console.error(error);
  }
}

function toggleCustomPolicyFields() {
  const policy = document.getElementById("pkg-policy").value;
  document.getElementById("pkg-custom-policy").hidden = policy !== "custom";
}

function openPackageModal(packageId) {
  const form = document.getElementById("pkg-form");
  form.dataset.id = packageId ? String(packageId) : "";
  document.getElementById("pkg-title").textContent = packageId
    ? "Edit package"
    : "Create new package";
  document.getElementById("pkg-error").hidden = true;
  form.reset();
  if (packageId) {
    const pkg = catalogPackages.find((item) => item.id === packageId);
    if (pkg) {
      document.getElementById("pkg-name").value = pkg.title;
      document.getElementById("pkg-desc").value = pkg.description || "";
      document.getElementById("pkg-price").value = pkg.price;
      document.getElementById("pkg-price-max").value = pkg.price_max || "";
      document.getElementById("pkg-policy").value =
        pkg.cancellation_policy || "moderate";
      document.getElementById("pkg-policy-percent").value =
        pkg.cancellation_refund_percent === null ||
        pkg.cancellation_refund_percent === undefined
          ? 100
          : pkg.cancellation_refund_percent;
      document.getElementById("pkg-policy-hours").value =
        pkg.cancellation_refund_hours === null ||
        pkg.cancellation_refund_hours === undefined
          ? 48
          : pkg.cancellation_refund_hours;
    }
  } else {
    document.getElementById("pkg-policy").value = "moderate";
    document.getElementById("pkg-policy-percent").value = 100;
    document.getElementById("pkg-policy-hours").value = 48;
  }
  toggleCustomPolicyFields();
  document.getElementById("pkg-modal").hidden = false;
  document.getElementById("pkg-name").focus();
}

function openDeepLinkedPackage() {
  if (!deepLinkPackageId) {
    return;
  }
  if (catalogPackages.some((pkg) => pkg.id === deepLinkPackageId)) {
    openPackageModal(deepLinkPackageId);
    deepLinkPackageId = null;
  }
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
document
  .getElementById("pkg-policy")
  .addEventListener("change", toggleCustomPolicyFields);

document.getElementById("pkg-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const errorBox = document.getElementById("pkg-error");
  errorBox.hidden = true;
  const body = {
    title: document.getElementById("pkg-name").value.trim(),
    description: document.getElementById("pkg-desc").value.trim(),
    price: document.getElementById("pkg-price").value,
    price_max: document.getElementById("pkg-price-max").value || null,
    cancellation_policy: document.getElementById("pkg-policy").value,
    cancellation_refund_percent: Number(
      document.getElementById("pkg-policy-percent").value
    ),
    cancellation_refund_hours: Number(
      document.getElementById("pkg-policy-hours").value
    ),
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
  document.getElementById("photo-file-name").textContent = "No file chosen";
  const select = document.getElementById("photo-collection");
  select.innerHTML =
    `<option value="">No collection</option>` +
    catalogCollections
      .map(
        (collection) =>
          `<option value="${collection.id}">${escapeHtml(
            collection.title
          )}</option>`
      )
      .join("");
  if (activeCollectionFilter !== "all" && activeCollectionFilter !== "none") {
    select.value = activeCollectionFilter;
  }
  document.getElementById("photo-modal").hidden = false;
  document.getElementById("photo-url").focus();
});
document.getElementById("photo-close").addEventListener("click", () => {
  document.getElementById("photo-modal").hidden = true;
});
document.getElementById("btn-pick-photo").addEventListener("click", () => {
  document.getElementById("photo-file").click();
});
document.getElementById("photo-file").addEventListener("change", (event) => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("photo-file-name").textContent = file
    ? file.name
    : "No file chosen";
  if (file) {
    document.getElementById("photo-url").value = "";
  }
});
document.getElementById("photo-url").addEventListener("input", () => {
  if (document.getElementById("photo-url").value.trim()) {
    document.getElementById("photo-file").value = "";
    document.getElementById("photo-file-name").textContent = "No file chosen";
  }
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
  const caption = document.getElementById("photo-caption").value.trim();
  const collectionValue = document.getElementById("photo-collection").value;
  const collection = collectionValue ? Number(collectionValue) : null;
  const fileInput = document.getElementById("photo-file");
  const file = fileInput.files && fileInput.files[0];
  const url = document.getElementById("photo-url").value.trim();
  if (!file && !url) {
    errorBox.textContent =
      "Choose a file from your computer or paste an image URL.";
    errorBox.hidden = false;
    return;
  }
  if (file) {
    if (!file.type || !file.type.startsWith("image/")) {
      errorBox.textContent = "Only image files are allowed.";
      errorBox.hidden = false;
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      errorBox.textContent = "Image must be 8 MB or smaller.";
      errorBox.hidden = false;
      return;
    }
  }
  try {
    let response;
    if (file) {
      const form = new FormData();
      form.append("image", file);
      form.append("caption", caption);
      if (collection) {
        form.append("collection", collection);
      }
      response = await apiFetch("/portfolio-photos/upload/", {
        method: "POST",
        body: form,
      });
    } else {
      response = await apiFetch("/portfolio-photos/", {
        method: "POST",
        body: { image: url, caption, collection },
      });
    }
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

/* ------------------------------ photo preview ---------------------------- */

function renderPortfolioPreview() {
  const photo = portfolioPreviewPhotos[portfolioPreviewIndex];
  if (!photo) {
    return;
  }
  const image = document.getElementById("pf-img");
  image.src = photo.image;
  image.alt = photo.caption || "Portfolio photo";
  document.getElementById("pf-caption").textContent = photo.caption || "";
  document.getElementById("pf-counter").textContent = `${
    portfolioPreviewIndex + 1
  } / ${portfolioPreviewPhotos.length}`;
}

function openPortfolioPreview(index) {
  if (portfolioPreviewPhotos.length === 0) {
    return;
  }
  portfolioPreviewIndex = Math.max(
    0,
    Math.min(index, portfolioPreviewPhotos.length - 1)
  );
  renderPortfolioPreview();
  document.getElementById("pf-preview").hidden = false;
  document.body.style.overflow = "hidden";
  document.getElementById("pf-close").focus();
}

function closePortfolioPreview() {
  document.getElementById("pf-preview").hidden = true;
  document.body.style.overflow = "";
}

function stepPortfolioPreview(delta) {
  portfolioPreviewIndex =
    (portfolioPreviewIndex + delta + portfolioPreviewPhotos.length) %
    portfolioPreviewPhotos.length;
  renderPortfolioPreview();
}

document.getElementById("portfolio-list").addEventListener("click", (event) => {
  if (event.target.closest("[data-del-photo-id]")) {
    return;
  }
  const card = event.target.closest(".photo-card");
  if (!card) {
    return;
  }
  const index = Number(card.dataset.index);
  if (!Number.isNaN(index)) {
    openPortfolioPreview(index);
  }
});
document.getElementById("pf-close").addEventListener("click", closePortfolioPreview);
document.getElementById("pf-prev").addEventListener("click", () => stepPortfolioPreview(-1));
document.getElementById("pf-next").addEventListener("click", () => stepPortfolioPreview(1));
document.getElementById("pf-preview").addEventListener("click", (event) => {
  if (event.target.id === "pf-preview") {
    closePortfolioPreview();
  }
});

/* ------------------------------ collections ----------------------------- */

document.getElementById("btn-new-collection").addEventListener("click", () => {
  document.getElementById("collection-error").hidden = true;
  document.getElementById("collection-form").reset();
  document.getElementById("collection-modal").hidden = false;
  document.getElementById("collection-name").focus();
});
document
  .getElementById("collection-close")
  .addEventListener("click", () => {
    document.getElementById("collection-modal").hidden = true;
  });
document.getElementById("collection-modal").addEventListener("click", (event) => {
  if (event.target.id === "collection-modal") {
    event.currentTarget.hidden = true;
  }
});

document.getElementById("collection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = document.getElementById("collection-error");
  errorBox.hidden = true;
  try {
    const response = await apiFetch("/portfolio-collections/", {
      method: "POST",
      body: { title: document.getElementById("collection-name").value.trim() },
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    document.getElementById("collection-modal").hidden = true;
    showToast("Collection created.");
    loadCatalog();
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

/* ----------------------------- public profile --------------------------- */

document
  .getElementById("public-profile-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorBox = document.getElementById("ppf-error");
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
            studio_name: document.getElementById("ppf-studio").value.trim(),
            city: document.getElementById("ppf-city").value.trim(),
            is_published: document.getElementById("ppf-published").checked,
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
      showToast("Profile saved.");
    } catch (error) {
      console.error(error);
      errorBox.textContent = "Could not reach the API.";
      errorBox.hidden = false;
    }
  });

/* ---------------------------- account details --------------------------- */

function wireAccountActions() {
  const errorBox = document.getElementById("acc-error");
  const emailInput = document.getElementById("acc-email");
  const usernameInput = document.getElementById("acc-username");

  document
    .getElementById("account-form")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      errorBox.hidden = true;
      const body = {};
      const email = emailInput.value.trim();
      const username = usernameInput.value.trim();
      if (email !== me.email) {
        body.email = email;
      }
      if (username !== me.username) {
        body.username = username;
      }
      if (Object.keys(body).length === 0) {
        showToast("No changes to save.");
        return;
      }
      try {
        const response = await apiFetch("/auth/me/", {
          method: "PATCH",
          body,
        });
        if (!response.ok) {
          errorBox.textContent = await readError(response);
          errorBox.hidden = false;
          return;
        }
        const data = await response.json();
        me.email = data.email;
        me.username = data.username;
        localStorage.setItem(STORAGE.username, data.username);
        renderMe();
        showToast("Account details updated.");
      } catch (error) {
        console.error(error);
        errorBox.textContent = "Could not reach the API.";
        errorBox.hidden = false;
      }
    });

  const modal = document.getElementById("acc-modal");
  const form = document.getElementById("acc-form");
  const pwError = document.getElementById("acc-pw-error");
  const valueInput = document.getElementById("acc-value");
  const currentInput = document.getElementById("acc-current");

  function openPasswordModal() {
    valueInput.value = "";
    currentInput.value = "";
    pwError.hidden = true;
    modal.hidden = false;
    currentInput.focus();
  }

  function closeModal() {
    modal.hidden = true;
  }

  document
    .getElementById("btn-change-password")
    .addEventListener("click", openPasswordModal);
  document.getElementById("acc-close").addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    pwError.hidden = true;
    try {
      const response = await apiFetch("/auth/change-password/", {
        method: "POST",
        body: {
          current_password: currentInput.value,
          new_password: valueInput.value,
        },
      });
      if (!response.ok) {
        pwError.textContent = await readError(response);
        pwError.hidden = false;
        return;
      }
      closeModal();
      showToast("Password updated.");
    } catch (error) {
      console.error(error);
      pwError.textContent = "Could not reach the API.";
      pwError.hidden = false;
    }
  });
}

function wireDirtyForms() {
  [
    "ppf-studio",
    "ppf-city",
    "ppf-published",
    "acc-email",
    "acc-username",
    "st-studio",
    "st-city",
    "st-specialties",
    "st-phone",
    "st-bio",
    "st-experience",
    "st-languages",
    "st-equipment",
    "st-published",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.addEventListener("input", refreshDirtySaves);
    el.addEventListener("change", refreshDirtySaves);
  });
}

/* ------------------------------ cover image ----------------------------- */

function renderCoverPreview() {
  const preview = document.getElementById("cover-preview");
  const removeBtn = document.getElementById("btn-remove-cover");
  if (!preview) {
    return;
  }
  const cover = me && me.profile ? me.profile.cover_image : null;
  preview.innerHTML = cover
    ? `<img class="cover-preview-img" src="${escapeHtml(
        cover
      )}" alt="Cover photo">`
    : '<span class="meta">No cover photo</span>';
  if (removeBtn) {
    removeBtn.hidden = !cover;
  }
}

async function uploadCoverPhoto(file) {
  const form = new FormData();
  form.append("cover_image", file);
  const response = await apiFetch("/profiles/cover/", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    showToast(await readError(response));
    return;
  }
  const data = await response.json();
  me.profile = { ...me.profile, cover_image: data.cover_image };
  renderCoverPreview();
  showToast("Cover photo updated.");
}

function wireCoverUpload() {
  const button = document.getElementById("btn-upload-cover");
  const input = document.getElementById("cover-file");
  const removeBtn = document.getElementById("btn-remove-cover");
  if (!button || !input) {
    return;
  }
  button.addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    const file = input.files && input.files[0];
    input.value = "";
    if (!file) {
      return;
    }
    if (file.size > 4 * 1024 * 1024) {
      showToast("Image must be 4 MB or smaller.");
      return;
    }
    if (!file.type || !file.type.startsWith("image/")) {
      showToast("Please choose an image file.");
      return;
    }
    await uploadCoverPhoto(file);
  });
  if (removeBtn) {
    removeBtn.addEventListener("click", async () => {
      if (!confirm("Remove the cover photo?")) {
        return;
      }
      const response = await apiFetch("/profiles/cover/", {
        method: "DELETE",
      }).catch(() => null);
      if (response && response.ok) {
        me.profile = { ...me.profile, cover_image: null };
        renderCoverPreview();
        showToast("Cover photo removed.");
      } else if (response) {
        showToast(await readError(response));
      }
    });
  }
}

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
          years_experience:
            document.getElementById("st-experience").value === ""
              ? null
              : Number(document.getElementById("st-experience").value),
          languages: document.getElementById("st-languages").value.trim(),
          equipment: document.getElementById("st-equipment").value.trim(),
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
    const items = [];
    let next = "/clients/";
    while (next) {
      const response = await apiFetch(next);
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      items.push(...(data.results || []));
      next = data.next;
    }
    const list = document.getElementById("clients-list");
    if (items.length === 0) {
      list.innerHTML = emptyState({
        icon: "clients",
        title: "No clients yet",
        text: "They will appear here when a booking is accepted, or you can add them manually.",
        action: "add-client",
        actionLabel: "+ Add Client manually",
      });
      return;
    }
    list.innerHTML = `
      <table class="pay-table client-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Source</th>
            <th>Client since</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (client) => `
          <tr>
            <td><strong>${escapeHtml(client.name)}</strong></td>
            <td>${escapeHtml(client.email || "—")}</td>
            <td>${escapeHtml(client.phone || "—")}</td>
            <td>
              <span class="chip${
                client.is_manual ? " chip--manual" : ""
              }">${client.is_manual ? "Added manually" : "Booked online"}</span>
            </td>
            <td>${formatDate(client.created_at)}</td>
          </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  } catch (error) {
    console.error(error);
  }
}

document.getElementById("btn-add-client").addEventListener("click", () => {
  document.getElementById("client-error").hidden = true;
  document.getElementById("client-form").reset();
  document.getElementById("client-modal").hidden = false;
  document.getElementById("client-name").focus();
});
document.getElementById("client-close").addEventListener("click", () => {
  document.getElementById("client-modal").hidden = true;
});
document.getElementById("client-modal").addEventListener("click", (event) => {
  if (event.target.id === "client-modal") {
    event.currentTarget.hidden = true;
  }
});

document.getElementById("client-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = document.getElementById("client-error");
  errorBox.hidden = true;
  const name = document.getElementById("client-name").value.trim();
  if (!name) {
    errorBox.textContent = "Name is required.";
    errorBox.hidden = false;
    return;
  }
  try {
    const response = await apiFetch("/clients/", {
      method: "POST",
      body: {
        name,
        email: document.getElementById("client-email").value.trim(),
        phone: document.getElementById("client-phone").value.trim(),
      },
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    document.getElementById("client-modal").hidden = true;
    showToast("Client added.");
    loadClients();
  } catch (error) {
    console.error(error);
    errorBox.textContent = "Could not reach the API.";
    errorBox.hidden = false;
  }
});

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
      list.innerHTML = emptyState({
        icon: "star",
        title: "No favorites yet",
        text: "Tap the star on gallery photos to save them here for later.",
        action: "browse",
        actionLabel: "Explore Photographers",
      });
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
  reviewsForOverview = items;
  renderOverview();
  const list = document.getElementById("my-reviews-list");
  const title = document.getElementById("my-reviews-title");
  const tabBtn = document.querySelector('#dash-tabs .tab[data-tab="reviews"]');
  const isCustomer = myRole === "customer";
  const heading = isCustomer ? "My reviews" : "Reviews";
  if (title) {
    title.textContent = heading;
  }
  if (tabBtn) {
    tabBtn.textContent = isCustomer ? "My reviews" : "Reviews";
  }
  const ownSlug = me && me.profile && me.profile.slug;
  if (items.length === 0) {
    list.innerHTML = isCustomer
      ? emptyState({
          icon: "star",
          title: "No reviews yet",
          text: "After a session you can review the studio from their public profile.",
          action: "browse",
          actionLabel: "Explore Photographers",
        })
      : emptyState({
          icon: "star",
          title: "You don't have reviews yet",
          text: "Here you will see reviews from people who have worked with you.",
        });
    return;
  }
  list.innerHTML = items
    .map((review) => {
      const who = isCustomer
        ? review.photographer_username
        : review.customer_username;
      const slug = isCustomer ? review.profile_slug : ownSlug;
      const profileLink = slug
        ? `<a class="btn btn-ghost btn-sm" href="profile.html?slug=${encodeURIComponent(
            slug
          )}">${isCustomer ? "View profile" : "See it on your profile"}</a>`
        : "";
      const replyBlock =
        !isCustomer && review.reply
          ? `<div class="review-reply">
               <span class="meta">Your reply · ${formatDate(
                 review.replied_at
               )}</span>
               <p class="req-msg">${escapeHtml(review.reply)}</p>
             </div>`
          : "";
      const replyBtn =
        !isCustomer && !review.reply
          ? `<button class="btn btn-sm" type="button" data-reply-review="${review.id}">Reply</button>`
          : "";
      const deleteBtn = isCustomer
        ? `<button class="btn btn-ghost btn-sm" type="button" data-del-review="${review.id}">Delete</button>`
        : "";
      return `
      <div class="request-row">
        <div class="req-info">
          <div class="review-head">
            ${starsHtml(review.rating)}
            <strong>@${escapeHtml(who)}</strong>
            <span class="meta">${formatDate(review.created_at)}</span>
          </div>
          ${
            review.comment
              ? `<p class="req-msg">${escapeHtml(review.comment)}</p>`
              : ""
          }
          ${replyBlock}
        </div>
        ${replyBtn}${profileLink}${deleteBtn}
      </div>`;
    })
    .join("");
  list.querySelectorAll("[data-reply-review]").forEach((button) => {
    button.addEventListener("click", () => {
      const review = items.find(
        (item) => String(item.id) === String(button.dataset.replyReview)
      );
      if (review) {
        openReplyModal(review);
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

/* One public reply per review, posted from the dashboard. */
function openReplyModal(review) {
  const modal = document.getElementById("reply-modal");
  if (!modal) {
    return;
  }
  modal.dataset.review = String(review.id);
  document.getElementById("reply-modal-title").textContent =
    `Reply to @${review.customer_username}`;
  document.getElementById("reply-error").hidden = true;
  document.getElementById("reply-text").value = "";
  modal.hidden = false;
  document.getElementById("reply-text").focus();
}

document.getElementById("reply-close").addEventListener("click", () => {
  document.getElementById("reply-modal").hidden = true;
});
document.getElementById("reply-modal").addEventListener("click", (event) => {
  if (event.target.id === "reply-modal") {
    event.currentTarget.hidden = true;
  }
});
document.getElementById("reply-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = document.getElementById("reply-error");
  errorBox.hidden = true;
  const modal = document.getElementById("reply-modal");
  const id = modal.dataset.review;
  const text = document.getElementById("reply-text").value.trim();
  if (!id || !text) {
    errorBox.textContent = "Write a reply first.";
    errorBox.hidden = false;
    return;
  }
  try {
    const response = await apiFetch(`/reviews/${id}/reply/`, {
      method: "POST",
      body: { reply: text },
    });
    if (!response.ok) {
      errorBox.textContent = await readError(response);
      errorBox.hidden = false;
      return;
    }
    modal.hidden = true;
    showToast("Reply posted.");
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

function renderPaymentActions() {
  const actions = document.getElementById("payments-actions");
  if (myRole !== "photographer") {
    actions.hidden = true;
    actions.innerHTML = "";
    return;
  }
  actions.hidden = false;
  const connected =
    Boolean(me && me.profile && me.profile.stripe_connected) ||
    isDemoStripeConnected();
  if (connected) {
    const demo = isDemoStripeConnected();
    actions.innerHTML = `
      <div class="setup-block setup-connected">
        <div class="setup-connected-title">
          <span class="setup-check" aria-hidden="true">&#10003;</span>
          Stripe Connected${demo ? " (Test Mode)" : ""}
        </div>
        <p class="meta">${
          demo
            ? "Test mode: no live charges are processed."
            : "Deposits go straight to your account."
        }</p>
        <a class="btn btn-sm" href="https://dashboard.stripe.com/test/payments" target="_blank" rel="noopener noreferrer">View Stripe Dashboard</a>
      </div>`;
    return;
  }
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

function countPendingPayments() {
  return bookingsForOverview.filter((booking) => {
    if (!["awaiting_payment", "accepted"].includes(booking.status)) {
      return false;
    }
    const pays = paymentsByBooking.get(booking.id) || {};
    return !(pays.deposit && pays.deposit.status === "paid");
  }).length;
}

/* Customer: what is still owed on this booking (total minus what was
   paid). Fully paid (balance or cash) and cancelled bookings owe 0. */
function customerBalanceDueCents(booking) {
  if (!["accepted", "completed"].includes(booking.status)) {
    return 0;
  }
  const pays = paymentsByBooking.get(booking.id) || {};
  const depositPaid = Boolean(pays.deposit && pays.deposit.status === "paid");
  const balancePaid = Boolean(pays.balance && pays.balance.status === "paid");
  const cashPaid = Boolean(pays.cash && pays.cash.status === "paid");
  if (cashPaid || balancePaid) {
    return 0;
  }
  const totalCents = Math.round(Number(booking.effective_price || 0) * 100);
  const paidCents = depositPaid ? Number(pays.deposit.amount_cents || 0) : 0;
  return Math.max(0, totalCents - paidCents);
}

/* Rows for money that is not collected yet: the deposit before it is
   paid, and the remaining balance once the deposit is in. */
function customerFutureRows() {
  const rows = [];
  bookingsForOverview.forEach((booking) => {
    const pays = paymentsByBooking.get(booking.id) || {};
    const depositPaid = Boolean(pays.deposit && pays.deposit.status === "paid");
    const cashPaid = Boolean(pays.cash && pays.cash.status === "paid");
    const totalCents = Math.round(Number(booking.effective_price || 0) * 100);
    if (booking.status === "awaiting_payment" && !depositPaid && !cashPaid) {
      rows.push({
        booking,
        amountCents: Math.round(totalCents * 0.2),
        label: "Deposit pending",
      });
      return;
    }
    const due = customerBalanceDueCents(booking);
    if (due > 0) {
      rows.push({
        booking,
        amountCents: due,
        label: "Balance pending",
      });
    }
  });
  return rows;
}

function renderPaymentsSummary() {
  const box = document.getElementById("payments-summary");
  if (!box) {
    return;
  }
  const pendingCount = countPendingPayments();
  if (myRole === "photographer") {
    const paidCents = paymentsForOverview
      .filter((payment) => payment.status === "paid")
      .reduce((sum, payment) => sum + Number(payment.amount_cents || 0), 0);
    // Refunds (e.g. a cancelled booking) come out of the total received.
    const refundedCents = paymentsForOverview
      .filter((payment) => payment.status === "refunded")
      .reduce((sum, payment) => sum + Number(payment.amount_cents || 0), 0);
    const netCents = Math.max(0, paidCents - refundedCents);
    box.innerHTML = `
    <span class="sum-chip ${
      pendingCount ? "sum-pending" : "sum-zero"
    }">Pending payments: ${pendingCount}</span>
    <span class="sum-chip ${
      netCents > 0 ? "sum-paid" : "sum-zero"
    }">Total received: $${(netCents / 100).toFixed(2)}</span>`;
    return;
  }
  const depositPaidCents = paymentsForOverview
    .filter(
      (payment) => payment.status === "paid" && payment.kind === "deposit"
    )
    .reduce((sum, payment) => sum + Number(payment.amount_cents || 0), 0);
  const refundedDepositCents = paymentsForOverview
    .filter(
      (payment) =>
        payment.status === "refunded" && payment.kind === "deposit"
    )
    .reduce((sum, payment) => sum + Number(payment.amount_cents || 0), 0);
  const netDepositCents = Math.max(0, depositPaidCents - refundedDepositCents);
  const balanceDueCents = bookingsForOverview.reduce(
    (sum, booking) => sum + customerBalanceDueCents(booking),
    0
  );
  box.innerHTML = `
    <span class="sum-chip ${
      netDepositCents > 0 ? "sum-paid" : "sum-zero"
    }">Deposit Paid: $${(netDepositCents / 100).toFixed(2)}</span>
    <span class="sum-chip ${
      balanceDueCents > 0 ? "sum-pending" : "sum-zero"
    }">Balance Due: $${(balanceDueCents / 100).toFixed(2)}</span>
    <span class="sum-chip ${
      pendingCount ? "sum-pending" : "sum-zero"
    }">Pending payments: ${pendingCount}</span>`;
}

function renderPaymentsTable() {
  const list = document.getElementById("payments-list");
  if (!list) {
    return;
  }
  const pendingCount = countPendingPayments();
  const futureRows = myRole === "customer" ? customerFutureRows() : [];
  const payments = paymentsForOverview;
  if (payments.length === 0 && futureRows.length === 0) {
    const needsStripe =
      myRole === "photographer" &&
      !(me && me.profile && me.profile.stripe_connected) &&
      !isDemoStripeConnected();
    list.innerHTML =
      pendingCount > 0
        ? emptyState({
            icon: "payments",
            title: "Waiting for payment",
            text: `${pendingCount} booking${
              pendingCount === 1 ? " is" : "s are"
            } waiting for you to pay the deposit.`,
          })
        : emptyState({
            icon: "payments",
            title: "No payments yet",
            text:
              myRole === "photographer"
                ? "Deposits and balances paid by your clients will show up here."
                : "Your deposits and remaining balances will show up here.",
            action: needsStripe ? "connect-stripe" : null,
            actionLabel: needsStripe ? "Connect Stripe" : null,
          });
    return;
  }
  const whoLabel = myRole === "photographer" ? "Client" : "Studio";
  const latest = [...payments]
    .sort(
      (a, b) =>
        new Date(b.paid_at || b.created_at) -
        new Date(a.paid_at || a.created_at)
    )
    .slice(0, 10);
  const paymentRows = latest
    .map((payment) => {
      const who =
        myRole === "photographer"
          ? payment.customer_username
          : payment.photographer_username;
      const kindLabel =
        payment.status === "refunded"
          ? "Deposit refund"
          : payment.kind === "balance"
          ? "Balance (80%)"
          : payment.kind === "cash"
          ? "Cash payment"
          : "Deposit (20%)";
      return `
      <tr data-highlight-id="${payment.id}">
        <td>${escapeHtml(who || "-")}</td>
        <td>${formatDate(payment.paid_at || payment.created_at)}</td>
        <td>$${(Number(payment.amount_cents || 0) / 100).toFixed(2)}
          <div class="meta">${kindLabel}</div>
        </td>
        <td>${statusChip(payment.status)}</td>
      </tr>`;
    })
    .join("");
  const futureHtml = futureRows
    .map((row) => {
      const booking = row.booking;
      const studio =
        booking.profile_studio_name || booking.profile_slug || "Studio";
      let action = payActionHtml(booking);
      if (booking.status === "completed") {
        action = '<span class="status-chip status-pending">balance due</span>';
      }
      return `
      <tr class="pay-upcoming">
        <td>
          <strong>${escapeHtml(studio)}</strong>
          <div class="meta">${escapeHtml(booking.package_title || "")}</div>
        </td>
        <td><span class="meta">Upcoming</span></td>
        <td>$${(row.amountCents / 100).toFixed(2)}
          <div class="meta">${row.label}</div>
        </td>
        <td>${action}</td>
      </tr>`;
    })
    .join("");
  list.innerHTML = `
    <table class="pay-table">
      <thead>
        <tr>
          <th>${whoLabel}</th>
          <th>Date</th>
          <th>Amount</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${futureHtml}
        ${paymentRows}
      </tbody>
    </table>`;
  list.querySelectorAll("[data-pay]").forEach((button) => {
    button.addEventListener("click", () =>
      startPayment(button.dataset.pay, button.dataset.kind || "deposit")
    );
  });
  applyPendingHighlight(list, "payments");
}

function renderPayments(data) {
  paymentsForOverview = data.results || [];
  renderOverview();
  paymentsByBooking = new Map();
  for (const payment of data.results || []) {
    const entry = paymentsByBooking.get(payment.booking) || {};
    entry[payment.kind] = payment;
    paymentsByBooking.set(payment.booking, entry);
  }
  renderPaymentsSummary();
  renderPaymentsTable();
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
    await loadMyReviews();
    await Promise.all([
      loadRequests(),
      loadShoots(),
      loadCatalog(),
      loadClients(),
      loadPayments(),
    ]);
  }
  finishPendingHighlight();
  openDeepLinkedPackage();
  showWelcomeOnce({
    username: me.username,
    role: myRole,
    name:
      (me.profile && me.profile.studio_name) || me.first_name || me.username,
    onGo: myRole === "customer" ? () => activateTab("requests") : null,
  });
}

initHeader();
wireProfilePictureUpload();
wireCoverUpload();
wireAccountActions();
wireDirtyForms();
init();
