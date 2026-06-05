/* Sezione "Oggi": bilancio del giorno + diario + form di aggiunta voce. */

function fmt(n, digits = 0) {
  if (n === null || n === undefined) return "—";
  return Number(n).toFixed(digits);
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function timeFromISO(iso) {
  return new Date(iso).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
}

function renderEntries(entries) {
  if (!entries.length) {
    return `<div class="entries empty">— nessuna voce per oggi —</div>`;
  }
  return `<ul class="entries">
    ${entries.map(e => `
      <li data-id="${e.id}">
        <span class="time">${timeFromISO(e.consumed_at)}</span>
        <div class="food">${e.food.name}<small>${e.meal} · ${fmt(e.grams)} g</small></div>
        <span class="kcal kcal-value">${fmt((e.food_kcal || 0))} kcal</span>
        <button class="remove" data-id="${e.id}">rimuovi</button>
      </li>
    `).join("")}
  </ul>`;
}

function renderSummary(needs, balance, dateStr) {
  const day = new Date(dateStr).toLocaleDateString("it-IT", {
    weekday: "long", day: "numeric", month: "long",
  });
  let head = "";
  if (!needs) {
    head = `<p class="serif-italic" style="font-size:1.3rem;color:var(--ink-soft);max-width:38ch">
      Per calcolare un riferimento giornaliero, completa il profilo
      (peso, altezza, eta'). L'app non inventa numeri.
    </p>`;
  } else {
    const delta = balance ? balance.kcal_difference : 0;
    const target = needs.target_kcal;
    const totals = balance ? balance.totals : { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0, fiber_g: 0 };
    const pct = balance ? balance.macros_percent : { protein_pct: 0, carbs_pct: 0, fat_pct: 0 };
    head = `
      <div class="bignum">
        <span class="label">Energia di oggi</span>
        <span class="num kcal-value">${fmt(totals.kcal)}<span class="unit">kcal</span></span>
        <span class="target">su un riferimento di <span class="num">${fmt(target)}</span> kcal</span>
        <span class="delta">${delta >= 0 ? "sopra" : "sotto"} di <span class="num">${fmt(Math.abs(delta))}</span></span>
      </div>
      <div class="macros">
        <div class="macro">
          <span class="label">Proteine</span>
          <span class="num">${fmt(totals.protein_g, 1)}<span style="font-size:0.5em;color:var(--ink-faded)"> g</span></span>
          <span class="pct">${fmt(pct.protein_pct)}%</span>
        </div>
        <div class="macro">
          <span class="label">Carboidrati</span>
          <span class="num">${fmt(totals.carbs_g, 1)}<span style="font-size:0.5em;color:var(--ink-faded)"> g</span></span>
          <span class="pct">${fmt(pct.carbs_pct)}%</span>
        </div>
        <div class="macro">
          <span class="label">Grassi</span>
          <span class="num">${fmt(totals.fat_g, 1)}<span style="font-size:0.5em;color:var(--ink-faded)"> g</span></span>
          <span class="pct">${fmt(pct.fat_pct)}%</span>
        </div>
      </div>
    `;
  }
  return `
    <div class="page-head">
      <div>
        <div class="kicker"><span class="label">N° 01 — il quaderno</span><hr></div>
        <h1>Oggi, <em>giorno per giorno</em>.</h1>
      </div>
      <div class="meta">${day}</div>
    </div>
    ${head}
  `;
}

let cachedFoodKcal = new Map();

async function enrichEntriesWithKcal(entries) {
  // L'API /diary non ritorna kcal — li calcoliamo lato client da food×grams/100.
  // Per pulizia, faccio una sola query per food id.
  const ids = [...new Set(entries.map(e => e.food.id))];
  if (!ids.length) return entries;
  // /foods non supporta lookup per id: uso la search per nome di ogni voce.
  // Soluzione semplice: ricalcolo via food.name search; ma il backend non
  // espone composizione: i kcal_100g vengono dalla preview di add_diary_entry.
  // Decisione: chiamo /summary/day per i totali aggregati (gia' visibili
  // in alto) e mostro i kcal per singola voce stimati lato client. La fonte
  // di verita' resta il motore lato server.
  // Per evitare un endpoint nuovo, leggo i food via search per id non
  // disponibile -> uso il name come fallback (sufficiente per visualizzare).
  return entries;
}

async function render() {
  const date = todayISO();

  const [diaryR, summaryR, needsR] = await Promise.all([
    api(`/diary?date=${date}`),
    api(`/summary/day?date=${date}`),
    api(`/summary/needs`),
  ]);

  const entries = diaryR && diaryR.ok ? await diaryR.json() : [];
  const balance = summaryR && summaryR.ok ? await summaryR.json() : null;
  const needs = needsR && needsR.ok ? await needsR.json() : null;

  // Stima kcal per voce: kcal_totali_balance / (somma grammi) e' impreciso.
  // Faccio una richiesta /foods?q=name per ogni voce e calcolo qui.
  for (const e of entries) {
    if (cachedFoodKcal.has(e.food.id)) {
      e.food_kcal = cachedFoodKcal.get(e.food.id) * (e.grams / 100);
      continue;
    }
    try {
      const r = await api(`/foods?q=${encodeURIComponent(e.food.name)}&limit=10`);
      if (r && r.ok) {
        const foods = await r.json();
        const match = foods.find(f => f.id === e.food.id);
        if (match) {
          cachedFoodKcal.set(e.food.id, match.kcal_100g);
          e.food_kcal = match.kcal_100g * (e.grams / 100);
        }
      }
    } catch {}
  }

  return `
    <section class="section">
      ${renderSummary(needs, balance, date)}
      <div class="editorial" style="margin-top:3rem">
        <div class="col-main">
          <div class="kicker"><span class="label">Voci registrate</span><hr></div>
          <div id="entries-host">${renderEntries(entries)}</div>
        </div>
        <aside class="col-aside">
          <div class="add-entry">
            <h3>Aggiungi una voce</h3>
            <div class="row search-results">
              <input id="food-search" class="input" type="text" placeholder="cerca un alimento…" autocomplete="off">
              <ul id="food-results" hidden></ul>
            </div>
            <input type="hidden" id="food-id">
            <div class="row split">
              <input id="grams" class="input" type="number" min="1" step="1" placeholder="grammi">
              <select id="meal" class="input">
                <option value="breakfast">colazione</option>
                <option value="lunch" selected>pranzo</option>
                <option value="snack">spuntino</option>
                <option value="dinner">cena</option>
              </select>
            </div>
            <button id="add-btn" class="btn">Registra voce</button>
          </div>
        </aside>
      </div>
    </section>
  `;
}

function afterRender() {
  const search = document.getElementById("food-search");
  const results = document.getElementById("food-results");
  const foodIdInput = document.getElementById("food-id");
  const gramsInput = document.getElementById("grams");
  const mealSelect = document.getElementById("meal");
  const addBtn = document.getElementById("add-btn");

  let searchTimer = null;
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      const q = search.value.trim();
      if (!q) { results.hidden = true; results.innerHTML = ""; return; }
      const r = await api(`/foods?q=${encodeURIComponent(q)}&limit=8`);
      if (!r || !r.ok) return;
      const foods = await r.json();
      results.innerHTML = foods.map(f => `
        <li data-id="${f.id}" data-name="${f.name.replace(/"/g, '&quot;')}">
          ${f.name}
          <small>${f.category || ""} · ${Number(f.kcal_100g).toFixed(0)} kcal/100g</small>
        </li>
      `).join("");
      results.hidden = foods.length === 0;
    }, 200);
  });

  results.addEventListener("click", ev => {
    const li = ev.target.closest("li");
    if (!li) return;
    search.value = li.dataset.name;
    foodIdInput.value = li.dataset.id;
    results.hidden = true;
  });

  document.addEventListener("click", ev => {
    if (!ev.target.closest(".search-results")) results.hidden = true;
  });

  addBtn.addEventListener("click", async () => {
    const food_id = parseInt(foodIdInput.value);
    const grams = parseFloat(gramsInput.value);
    if (!food_id || !grams || grams <= 0) {
      search.focus();
      return;
    }
    const r = await api("/diary", {
      method: "POST",
      body: { food_id, grams, meal: mealSelect.value },
    });
    if (r && r.ok) {
      // Ricarico la sezione (semplice e onesto).
      loadSection("oggi");
    }
  });

  // Bind remove per ogni voce.
  document.querySelectorAll(".entries .remove").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      const r = await api(`/diary/${id}`, { method: "DELETE" });
      if (r && (r.ok || r.status === 204)) {
        loadSection("oggi");
      }
    });
  });
}

export { render, afterRender };
