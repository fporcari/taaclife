/* NutriCoach — JS minimale.
 *
 * Tre cose:
 *   1) Token JWT in localStorage; tutte le richieste API includono
 *      l'header Authorization. Su 401, redirect a /login.
 *   2) Toggle "nascondi calorie" persistito in localStorage.
 *   3) Navigazione fra sezioni (caricamento lazy via fetch).
 */

const TOKEN_KEY = "nutricoach.access_token";
const REFRESH_KEY = "nutricoach.refresh_token";
const HIDE_CAL_KEY = "nutricoach.hide_calories";

const NC = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  set token(v) { v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY); },
  get refresh() { return localStorage.getItem(REFRESH_KEY); },
  set refresh(v) { v ? localStorage.setItem(REFRESH_KEY, v) : localStorage.removeItem(REFRESH_KEY); },
  clear() { this.token = null; this.refresh = null; },
};

async function api(path, options = {}) {
  const opts = {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  };
  if (NC.token) opts.headers["Authorization"] = `Bearer ${NC.token}`;
  if (options.body !== undefined) opts.body = JSON.stringify(options.body);

  const resp = await fetch(path, opts);
  if (resp.status === 401 && !path.startsWith("/auth/")) {
    NC.clear();
    window.location.href = "/login";
    return null;
  }
  return resp;
}

function requireAuth() {
  if (!NC.token && !window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/register")) {
    window.location.href = "/login";
  }
}

// ---------------- Toggle calorie ----------------

function applyHideCalories() {
  const hide = localStorage.getItem(HIDE_CAL_KEY) === "1";
  document.body.classList.toggle("hide-calories", hide);
  const cb = document.getElementById("toggle-hide-calories");
  if (cb) cb.checked = hide;
}

function bindHideCaloriesToggle() {
  const cb = document.getElementById("toggle-hide-calories");
  if (!cb) return;
  cb.addEventListener("change", () => {
    localStorage.setItem(HIDE_CAL_KEY, cb.checked ? "1" : "0");
    applyHideCalories();
  });
}

// ---------------- Sezioni (lazy load via fetch) ----------------

const SECTIONS = ["oggi", "gusti", "peso", "coach"];

async function loadSection(name) {
  const main = document.getElementById("section");
  if (!main) return;
  main.innerHTML = `<div class="htmx-indicator"
    style="opacity:1;padding:4rem 0;text-align:center">caricamento…</div>`;

  let html = "";
  try {
    const mod = await import(`/static/sections/${name}.js`);
    html = await mod.render();
  } catch (e) {
    console.error(e);
    html = `<div class="section"><h2>Errore</h2><p>${e.message}</p></div>`;
  }
  main.innerHTML = html;

  // Eventuali handler di sezione
  try {
    const mod = await import(`/static/sections/${name}.js`);
    if (mod.afterRender) mod.afterRender();
  } catch (e) { /* ignore */ }

  document.querySelectorAll(".nav a[data-section]").forEach(a => {
    a.classList.toggle("active", a.dataset.section === name);
  });
  history.replaceState(null, "", `#${name}`);
  applyHideCalories();
}

function bindNav() {
  document.querySelectorAll(".nav a[data-section]").forEach(a => {
    a.addEventListener("click", ev => {
      ev.preventDefault();
      loadSection(a.dataset.section);
    });
  });
}

// ---------------- Bootstrap shell ----------------

function bootstrapShell() {
  requireAuth();
  if (!NC.token) return;
  applyHideCalories();
  bindHideCaloriesToggle();
  bindNav();
  const hash = window.location.hash.replace("#", "");
  const initial = SECTIONS.includes(hash) ? hash : "oggi";
  loadSection(initial);

  const logout = document.getElementById("logout");
  if (logout) {
    logout.addEventListener("click", ev => {
      ev.preventDefault();
      NC.clear();
      window.location.href = "/login";
    });
  }
}

// ---------------- Bootstrap auth ----------------

async function submitAuth(mode, form) {
  const errEl = form.querySelector(".err");
  errEl.classList.remove("show");
  const data = Object.fromEntries(new FormData(form).entries());
  const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
  const resp = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    let detail = "errore";
    try { detail = (await resp.json()).detail || detail; } catch {}
    if (typeof detail !== "string") detail = JSON.stringify(detail);
    errEl.textContent = detail;
    errEl.classList.add("show");
    return;
  }
  if (mode === "register") {
    // Dopo register, login automatico.
    const loginResp = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: data.email, password: data.password }),
    });
    if (!loginResp.ok) {
      errEl.textContent = "registrato — accedi ora";
      errEl.classList.add("show");
      return;
    }
    const body = await loginResp.json();
    NC.token = body.access_token;
    NC.refresh = body.refresh_token;
  } else {
    const body = await resp.json();
    NC.token = body.access_token;
    NC.refresh = body.refresh_token;
  }
  window.location.href = "/";
}

function bootstrapAuth(mode) {
  const form = document.getElementById("auth-form");
  if (!form) return;
  form.addEventListener("submit", ev => {
    ev.preventDefault();
    submitAuth(mode, form);
  });
}

window.NC = NC;
window.api = api;
window.bootstrapShell = bootstrapShell;
window.bootstrapAuth = bootstrapAuth;
window.loadSection = loadSection;
