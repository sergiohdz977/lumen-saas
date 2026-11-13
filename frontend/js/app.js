const grid = document.getElementById("grid");
const status = document.getElementById("status");
const loadMoreBtn = document.getElementById("load-more");
const searchForm = document.getElementById("search-form");
const searchCity = document.getElementById("search-city");
const searchSpecialty = document.getElementById("search-specialty");
const searchRating = document.getElementById("search-rating");
const searchPrice = document.getElementById("search-price");
const searchClear = document.getElementById("search-clear");
const searchMore = document.getElementById("search-more");
const searchExtra = document.getElementById("search-extra");

const authStatus = document.getElementById("auth-status");
const loginModal = document.getElementById("login-modal");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const loginClose = document.getElementById("login-close");
const loginError = document.getElementById("login-error");
const registerError = document.getElementById("register-error");
const languageSelect = document.getElementById("language-select");

const translations = {
  en: {
    "language.label": "Language", "notifications.all": "View all notifications", "auth.hi": "Hi",
    "auth.login": "Log in", "auth.signup": "Sign up", "auth.welcome": "Welcome back",
    "auth.subtitle": "Sign in to manage your studio and bookings.", "auth.create": "Create your account",
    "auth.createSubtitle": "Customers book sessions, photographers sell them.", "auth.createButton": "Create account",
    "hero.kicker": "Photography booking platform", "hero.title": "Find the photographer for your",
    "hero.titleAccent": "next story", "hero.subtitle": "Browse studios, explore their specialties and book in minutes. A more considered way to find the right eye for every occasion.",
    "hero.cta": "Explore photographers", "hero.note": "Curated for memorable moments",
    "trust.discover": "Discover with intention", "trust.compare": "Compare the details", "trust.book": "Book with confidence", "trust.caption": "Your next chapter, beautifully framed.",
    "guide.eyebrow": "A simpler way to begin", "guide.title": "Your perfect session,", "guide.titleAccent": "in three thoughtful steps.",
    "guide.intro": "Lumen brings the right details forward so choosing a photographer feels as natural as the story you want to tell.",
    "guide.step1.title": "Discover your match", "guide.step1.body": "Search by city, specialty and style to find a photographer who sees things your way.",
    "guide.step2.title": "See the feeling", "guide.step2.body": "Explore portfolios, packages and reviews before you choose the energy that fits.",
    "guide.step3.title": "Make it yours", "guide.step3.body": "Send a request, secure your date and keep every important detail in one place.",
    "search.city": "City — e.g. Madrid", "search.specialty": "Specialty — e.g. weddings", "search.more": "More filters", "search.hide": "Hide filters", "search.anyRating": "Any rating", "search.anyPrice": "Any price", "search.submit": "Search", "search.clear": "Clear",
    "footer": "Lumen — photography booking platform · API powered by Django REST Framework", "status.loading": "Loading photographers…", "status.empty": "No photographers match your search.", "status.apiError": "Could not reach the API. Is the server running on port 8000?", "card.locationUnset": "Location not set", "card.noBio": "This photographer has not added a bio yet.", "card.new": "New", "auth.invalid": "Invalid username or password.", "auth.unreachable": "Could not reach the API. Is the server running?", "auth.accountCreated": "Account created! Log in to continue."
  },
  es: {
    "language.label": "Idioma", "notifications.all": "Ver todas las notificaciones", "auth.hi": "Hola",
    "auth.login": "Iniciar sesión", "auth.signup": "Crear cuenta", "auth.welcome": "Qué bueno verte",
    "auth.subtitle": "Entra para gestionar tu estudio y tus reservas.", "auth.create": "Crea tu cuenta",
    "auth.createSubtitle": "Los clientes reservan sesiones y los fotógrafos las ofrecen.", "auth.createButton": "Crear cuenta",
    "hero.kicker": "Plataforma de reservas fotográficas", "hero.title": "Encuentra al fotógrafo para tu", "hero.titleAccent": "próxima historia",
    "hero.subtitle": "Descubre estudios, explora sus especialidades y reserva en minutos. Una forma más cuidada de encontrar la mirada adecuada para cada ocasión.", "hero.cta": "Explorar fotógrafos", "hero.note": "Selección para momentos memorables",
    "trust.discover": "Descubre con intención", "trust.compare": "Compara los detalles", "trust.book": "Reserva con confianza", "trust.caption": "Tu próxima historia, enmarcada con intención.",
    "guide.eyebrow": "Una forma más sencilla de empezar", "guide.title": "Tu sesión ideal,", "guide.titleAccent": "en tres pasos pensados para ti.",
    "guide.intro": "Lumen pone los detalles importantes en primer plano para que elegir fotógrafo se sienta tan natural como la historia que quieres contar.",
    "guide.step1.title": "Encuentra tu mirada", "guide.step1.body": "Busca por ciudad, especialidad y estilo para encontrar un fotógrafo que vea las cosas como tú.",
    "guide.step2.title": "Siente el estilo", "guide.step2.body": "Explora portafolios, paquetes y reseñas antes de elegir la energía que más encaja contigo.",
    "guide.step3.title": "Hazlo tuyo", "guide.step3.body": "Envía una solicitud, asegura tu fecha y guarda cada detalle importante en un solo lugar.",
    "search.city": "Ciudad — ej. Madrid", "search.specialty": "Especialidad — ej. bodas", "search.more": "Más filtros", "search.hide": "Ocultar filtros", "search.anyRating": "Cualquier valoración", "search.anyPrice": "Cualquier precio", "search.submit": "Buscar", "search.clear": "Limpiar",
    "footer": "Lumen — plataforma de reservas fotográficas · API desarrollada con Django REST Framework", "status.loading": "Cargando fotógrafos…", "status.empty": "Ningún fotógrafo coincide con tu búsqueda.", "status.apiError": "No se pudo conectar con la API. ¿Está funcionando el servidor en el puerto 8000?", "card.locationUnset": "Ubicación no indicada", "card.noBio": "Este fotógrafo aún no ha añadido una biografía.", "card.new": "Nuevo", "auth.invalid": "El usuario o la contraseña no son válidos.", "auth.unreachable": "No se pudo conectar con la API. ¿Está funcionando el servidor?", "auth.accountCreated": "Cuenta creada. Inicia sesión para continuar."
  }
};

let currentLanguage = localStorage.getItem("lumen-language") || "en";
function t(key) { return translations[currentLanguage][key] || translations.en[key] || key; }
function applyLanguage(language) {
  currentLanguage = translations[language] ? language : "en";
  localStorage.setItem("lumen-language", currentLanguage);
  document.documentElement.lang = currentLanguage;
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => { element.placeholder = t(element.dataset.i18nPlaceholder); });
  if (languageSelect) { languageSelect.value = currentLanguage; languageSelect.setAttribute("aria-label", t("language.label")); }
  if (searchMore) searchMore.textContent = searchExtra.hidden ? t("search.more") : t("search.hide");
}

let nextUrl = null;

function cardHtml(profile) {
  const name = profile.studio_name || profile.username;
  const initial = (name || "?").charAt(0).toUpperCase();
  const planBadge =
    profile.plan === "pro" ? '<span class="badge badge-pro">PRO</span>' : "";
  const avatar = profile.profile_picture
    ? `<img class="avatar avatar-img" src="${escapeHtml(
        profile.profile_picture
      )}" alt="${escapeHtml(name)}" loading="lazy">`
    : `<div class="avatar">${escapeHtml(initial)}</div>`;
  const chips = (profile.specialties || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");
  const rating =
    profile.rating_avg !== null && profile.rating_avg !== undefined
      ? `<span class="card-rating">★ ${Number(profile.rating_avg).toFixed(1)}</span>`
      : `<span class="card-rating card-rating--none">★ ${t("card.new")}</span>`;

  return `
    <a class="card-link" href="profile.html?slug=${encodeURIComponent(profile.slug)}">
      <article class="card">
        <div class="card-top">
          ${avatar}
          ${planBadge}
        </div>
        <h2>${escapeHtml(name)} ${rating}</h2>
        <p class="meta">${escapeHtml(profile.city || t("card.locationUnset"))} · @${escapeHtml(
          profile.username
        )}</p>
        <p class="bio">${escapeHtml(
          profile.bio || t("card.noBio")
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
  if (searchRating.value) {
    params.set("min_rating", searchRating.value);
  }
  const price = searchPrice.value.trim();
  if (price) {
    params.set("max_price", price);
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
  status.textContent = t("status.loading");
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
      status.textContent = t("status.empty");
    } else {
      status.hidden = true;
    }
  } catch (error) {
    status.hidden = false;
    status.textContent = t("status.apiError");
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
    if (!response.ok) {
      header.update();
    }
  } catch (error) {
    console.error(error);
  }
}

/* Same-page return after login/register; only local *.html pages allowed. */
function safeNextPage() {
  const next = auto.get("next");
  return next && /^[a-z0-9._-]+\.html(\?[a-z0-9&=_.%-]*)?$/i.test(next)
    ? next
    : null;
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
          ? t("auth.invalid")
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
    const next = safeNextPage();
    if (next) {
      window.location.href = next;
      return;
    }
    if (me && me.role === "photographer") {
      window.location.href = "dashboard.html";
    }
  } catch (error) {
    loginError.textContent = t("auth.unreachable");
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
    // Registration flows straight to the dashboard for every role (the
    // first-visit product tour greets them there).
    if (login.ok) {
      window.location.href = "dashboard.html";
      return;
    }
    showToast(t("auth.accountCreated"));
  } catch (error) {
    registerError.textContent = t("auth.unreachable");
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
  searchRating.value = "";
  searchPrice.value = "";
  loadPage(listUrl(), { replace: true });
});

searchMore.addEventListener("click", () => {
  const willOpen = searchExtra.hidden;
  searchExtra.hidden = !willOpen;
  searchMore.textContent = willOpen ? t("search.hide") : t("search.more");
  searchMore.classList.toggle("is-active", willOpen);
});
loadMoreBtn.addEventListener("click", () => {
  if (nextUrl) {
    loadPage(nextUrl);
  }
});

const revealItems = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !loginModal.hidden) {
    closeAuth();
  }
});

header.update();
if (languageSelect) languageSelect.addEventListener("change", (event) => applyLanguage(event.target.value));
applyLanguage(currentLanguage);
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
