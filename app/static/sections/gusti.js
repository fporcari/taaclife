/* Sezione "Gusti": liked / avoided. */

function chip(item, kind) {
  return `<span class="chip ${kind}">
    ${item.value}
    <button data-id="${item.id}" aria-label="rimuovi">✕</button>
  </span>`;
}

async function render() {
  const r = await api("/preferences");
  const prefs = r && r.ok ? await r.json() : { liked: [], avoided: [] };
  return `
    <section class="section">
      <div class="page-head">
        <div>
          <div class="kicker"><span class="label">N° 02 — il palato</span><hr></div>
          <h1>Quello che <em>ami</em>, quello che eviti.</h1>
        </div>
        <div class="meta">le preferenze<br>non sono un giudizio</div>
      </div>
      <p class="serif-italic" style="font-size:1.2rem;color:var(--ink-soft);max-width:48ch;margin-bottom:3rem">
        Una mappa dei tuoi gusti aiuta il coach a proporti cose che davvero
        ti piacciono. Niente etichette di "buono" o "cattivo".
      </p>
      <div class="tastes">
        <div class="taste-col">
          <h2>Mi piace</h2>
          <p>I sapori che cerchi.</p>
          <div class="chips" id="liked-chips">
            ${prefs.liked.map(it => chip(it, "liked")).join("") || '<em style="color:var(--ink-faded)">nessuno ancora</em>'}
          </div>
          <form id="liked-form" class="row split" style="display:grid;gap:0.8rem;grid-template-columns:1fr auto">
            <input class="input" name="value" placeholder="es. pasta al pomodoro" required>
            <button class="btn" type="submit">aggiungi</button>
          </form>
        </div>
        <div class="taste-col">
          <h2>Evito</h2>
          <p>Le cose che lasci da parte.</p>
          <div class="chips" id="avoided-chips">
            ${prefs.avoided.map(it => chip(it, "avoided")).join("") || '<em style="color:var(--ink-faded)">nessuna ancora</em>'}
          </div>
          <form id="avoided-form" class="row split" style="display:grid;gap:0.8rem;grid-template-columns:1fr auto">
            <input class="input" name="value" placeholder="es. cavolfiore" required>
            <button class="btn btn-ghost" type="submit">aggiungi</button>
          </form>
        </div>
      </div>
    </section>
  `;
}

function bindForm(formId, kind) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const value = form.value.value.trim();
    if (!value) return;
    const r = await api("/preferences", {
      method: "POST",
      body: { kind, value },
    });
    if (r && (r.ok || r.status === 201 || r.status === 409)) {
      loadSection("gusti");
    }
  });
}

function bindRemoveAll() {
  document.querySelectorAll(".chip button").forEach(b => {
    b.addEventListener("click", async () => {
      const id = b.dataset.id;
      const r = await api(`/preferences/${id}`, { method: "DELETE" });
      if (r && (r.ok || r.status === 204)) {
        loadSection("gusti");
      }
    });
  });
}

function afterRender() {
  bindForm("liked-form", "liked");
  bindForm("avoided-form", "avoided");
  bindRemoveAll();
}

export { render, afterRender };
