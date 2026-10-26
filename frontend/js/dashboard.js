const API =
  window.location.port === "8000" || window.location.port === ""
    ? "/api"
    : "http://127.0.0.1:8000/api";

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

let myRole = "";

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

function statusChip(status) {
  return `<span class="status-chip status-${escapeHtml(
    status
  )}">${escapeHtml(status)}</span>`;
}

function renderRequests(data, role) {
  document.getElementById("requests-panel").hidden = false;
  document.getElementById("requests-title").textContent =
    role === "photographer" ? "Incoming requests" : "My requests";
  const list = document.getElementById("requests-list");
  if (!data.results || data.results.length === 0) {
    list.innerHTML = '<p class="meta">No booking requests yet.</p>';
    return;
  }
  list.innerHTML = data.results
    .map((booking) => {
      const other =
        role === "photographer"
          ? booking.customer_username
          : booking.profile_studio_name || booking.profile_slug;
      return `
      <div class="request-row">
        <div class="req-info">
          <strong>${escapeHtml(booking.package_title)}</strong>
          <span class="meta">${escapeHtml(other)} · ${new Date(
            booking.date
          ).toLocaleString()}</span>
        </div>
        ${statusChip(booking.status)}
        ${
          role === "photographer" && booking.status === "pending"
            ? `
        <button class="btn btn-sm" type="button" data-accept="${booking.id}">Accept</button>
        <button class="btn btn-ghost btn-sm" type="button" data-reject="${booking.id}">Reject</button>`
            : ""
        }
      </div>`;
    })
    .join("");

  if (role === "photographer") {
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
  }
}

async function loadRequests(access, role) {
  try {
    const response = await fetch(`${API}/bookings/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    if (response.ok) {
      renderRequests(await response.json(), role);
    }
  } catch (error) {
    console.error(error);
  }
}

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
  document.getElementById("shoots-panel").hidden = false;
  const list = document.getElementById("shoots-list");
  if (!data.results || data.results.length === 0) {
    list.innerHTML = '<p class="meta">No shoots yet.</p>';
    return;
  }
  list.innerHTML = data.results
    .map((shoot) => {
      const action = nextShootAction(shoot.status);
      return `
      <div class="request-row">
        <div class="req-info">
          <strong>${escapeHtml(shoot.title)}</strong>
          <span class="meta">${escapeHtml(shoot.client_name)} · ${new Date(
            shoot.date
          ).toLocaleString()}</span>
        </div>
        ${statusChip(shoot.status)}
        ${
          action
            ? `<button class="btn btn-sm" type="button"
                data-shoot="${shoot.id}" data-next="${action.next}">${action.label}</button>`
            : ""
        }
      </div>`;
    })
    .join("");

  list.querySelectorAll("[data-shoot]").forEach((button) => {
    button.addEventListener("click", () =>
      updateShoot(button.dataset.shoot, button.dataset.next)
    );
  });
}

async function loadShoots(access) {
  try {
    const response = await fetch(`${API}/shoots/`, {
      headers: { Authorization: `Bearer ${access}` },
    });
    if (response.ok) {
      renderShoots(await response.json());
    }
  } catch (error) {
    console.error(error);
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
  const access = localStorage.getItem(STORAGE.access);
  try {
    const response = await fetch(`${API}/shoots/${id}/`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access}`,
      },
      body: JSON.stringify({ status: nextStatus }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      let message = "Could not update the shoot.";
      if (error && error.detail) {
        message = Array.isArray(error.detail)
          ? error.detail.join(" ")
          : String(error.detail);
      }
      alert(message);
      return;
    }
    await loadShoots(access);
  } catch (error) {
    console.error(error);
  }
}

async function transitionBooking(id, action) {
  const access = localStorage.getItem(STORAGE.access);
  try {
    const response = await fetch(`${API}/bookings/${id}/${action}/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${access}` },
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      let message = `Could not ${action} the request.`;
      if (error && error.detail) {
        message = Array.isArray(error.detail)
          ? error.detail.join(" ")
          : String(error.detail);
      }
      alert(message);
      return;
    }
    await loadRequests(access, myRole);
    await loadNotifications(access);
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
    myRole = me.role;
    renderMe(me);
    showDash(me.username);
    dashStatus.hidden = true;
    dashContent.hidden = false;
    await loadNotifications(access);
    await loadRequests(access, me.role);
    if (me.role === "photographer") {
      await loadShoots(access);
    }
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
