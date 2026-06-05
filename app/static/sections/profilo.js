/* Sezione "Profilo": dati per il calcolo del fabbisogno (Mifflin).
 *
 * Vincolo §14: identita' (sex) e parametro di calcolo (calc_basis)
 * sono separati. Niente BMI in UI: scelta di prodotto coerente con §7
 * (no shaming, no categorie su misure corporee).
 */

const SEX_OPTIONS = [
  { v: "", label: "— non specificato —" },
  { v: "F", label: "femminile" },
  { v: "M", label: "maschile" },
  { v: "other", label: "altro / non binario" },
];

const CALC_BASIS_OPTIONS = [
  { v: "", label: "— media F/M (dichiarata come stima) —" },
  { v: "F", label: "formula F" },
  { v: "M", label: "formula M" },
];

const ACTIVITY_OPTIONS = [
  { v: "", label: "— non specificato (default: sedentario) —" },
  { v: "sedentary", label: "sedentario  ·  poco movimento" },
  { v: "light", label: "leggero  ·  camminate, qualche allenamento" },
  { v: "moderate", label: "moderato  ·  attivita' regolare 3-5 volte/sett" },
  { v: "active", label: "attivo  ·  allenamento quasi quotidiano" },
  { v: "very_active", label: "molto attivo  ·  sport intenso o lavoro fisico" },
];

const GOAL_OPTIONS = [
  { v: "maintain", label: "mantenimento  ·  il default" },
  { v: "gentle_loss", label: "perdita gentile  ·  −15% sul fabbisogno" },
  { v: "gentle_gain", label: "guadagno gentile  ·  +10% sul fabbisogno" },
];

function opt(options, selected) {
  return options.map(o =>
    `<option value="${o.v}" ${o.v === (selected || "") ? "selected" : ""}>${o.label}</option>`
  ).join("");
}

async function render() {
  const r = await api("/profile");
  const p = r && r.ok ? await r.json() : null;

  const sex = p?.sex || "";
  const calcBasis = p?.calc_basis || "";
  const birthDate = p?.birth_date || "";
  const heightCm = p?.height_cm ?? "";
  const activityLevel = p?.activity_level || "";
  const goal = p?.goal || "maintain";

  const needsR = await api("/summary/needs");
  let needsBlock = "";
  if (needsR && needsR.ok) {
    const n = await needsR.json();
    needsBlock = `
      <div class="bignum" style="margin-top:0">
        <span class="label">Riferimento giornaliero</span>
        <span class="num kcal-value">${Math.round(n.target_kcal)}<span class="unit">kcal</span></span>
        <span class="target">
          BMR <span class="num">${Math.round(n.bmr)}</span> ·
          TDEE <span class="num">${Math.round(n.tdee)}</span> ·
          obiettivo <span style="font-style:italic">${n.goal_applied}</span>
        </span>
        ${(n.calc_basis_assumed || n.activity_assumed) ? `
          <span class="delta serif-italic" style="font-size:0.95rem">
            ${n.calc_basis_assumed ? "calc_basis non specificato: ho usato la media delle due formule. " : ""}
            ${n.activity_assumed ? "livello attivita' non specificato: ho usato 'sedentario' come stima conservativa." : ""}
          </span>
        ` : ""}
      </div>
    `;
  } else if (needsR && needsR.status === 422) {
    const body = await needsR.json().catch(() => ({ detail: {} }));
    const missing = body?.detail?.missing || "alcuni dati";
    needsBlock = `
      <div class="bignum" style="margin-top:0">
        <span class="label">Riferimento giornaliero</span>
        <span class="serif-italic" style="font-size:1.3rem;color:var(--ink-soft);max-width:38ch">
          Manca: <strong>${missing}</strong>. Completa i campi qui sotto
          (e registra almeno un peso nella sezione Peso) e calcolero' il
          tuo fabbisogno. Non invento numeri.
        </span>
      </div>
    `;
  }

  return `
    <section class="section">
      <div class="page-head">
        <div>
          <div class="kicker"><span class="label">N° 02 — la cornice</span><hr></div>
          <h1>I tuoi <em>dati di partenza</em>.</h1>
        </div>
        <div class="meta">servono al motore<br>per stimare il fabbisogno</div>
      </div>

      <p class="serif-italic" style="font-size:1.15rem;color:var(--ink-soft);max-width:54ch;margin-bottom:2.5rem">
        Questi campi alimentano una formula standard
        (Mifflin&#8209;St&nbsp;Jeor). Sono tutti opzionali: se ne manca uno,
        l'app te lo dice invece di inventare un numero.
      </p>

      ${needsBlock}

      <form id="profile-form" style="margin-top:3rem;display:grid;gap:2rem;max-width:640px">
        <div class="field">
          <label class="label" style="display:block;margin-bottom:0.4rem">Identita' di genere</label>
          <select class="input" name="sex">${opt(SEX_OPTIONS, sex)}</select>
          <p style="margin:0.5rem 0 0;font-size:0.85rem;color:var(--ink-faded);font-style:italic">
            come ti identifichi. Non incide sul calcolo.
          </p>
        </div>

        <div class="field">
          <label class="label" style="display:block;margin-bottom:0.4rem">Parametro per la formula Mifflin</label>
          <select class="input" name="calc_basis">${opt(CALC_BASIS_OPTIONS, calcBasis)}</select>
          <p style="margin:0.5rem 0 0;font-size:0.85rem;color:var(--ink-faded);font-style:italic">
            scelta separata dall'identita'. Mifflin ha solo F o M; se non
            scegli, uso la media delle due formule e lo dichiaro.
          </p>
        </div>

        <div class="field" style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">
          <div>
            <label class="label" style="display:block;margin-bottom:0.4rem">Data di nascita</label>
            <input class="input" type="date" name="birth_date" value="${birthDate}">
          </div>
          <div>
            <label class="label" style="display:block;margin-bottom:0.4rem">Altezza (cm)</label>
            <input class="input" type="number" min="100" max="230" step="0.5"
                   name="height_cm" placeholder="es. 168" value="${heightCm}">
          </div>
        </div>

        <div class="field">
          <label class="label" style="display:block;margin-bottom:0.4rem">Livello di attivita'</label>
          <select class="input" name="activity_level">${opt(ACTIVITY_OPTIONS, activityLevel)}</select>
        </div>

        <div class="field">
          <label class="label" style="display:block;margin-bottom:0.4rem">Obiettivo</label>
          <select class="input" name="goal">${opt(GOAL_OPTIONS, goal)}</select>
          <p style="margin:0.5rem 0 0;font-size:0.85rem;color:var(--ink-faded);font-style:italic">
            il default e' il mantenimento. Le opzioni di perdita/guadagno
            sono moderate per scelta (max −15% / +10%).
          </p>
        </div>

        <div style="display:flex;align-items:center;gap:1.5rem;margin-top:1rem">
          <button class="btn" type="submit">salva</button>
          <span id="profile-msg" class="serif-italic" style="color:var(--ink-faded);font-size:0.95rem"></span>
        </div>
      </form>
    </section>
  `;
}

function afterRender() {
  const form = document.getElementById("profile-form");
  if (!form) return;
  const msg = document.getElementById("profile-msg");

  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());

    // Normalizzo: stringhe vuote -> null per non spedire enum invalidi.
    const body = {};
    for (const [k, v] of Object.entries(data)) {
      if (v === "" || v === null || v === undefined) {
        body[k] = null;
      } else if (k === "height_cm") {
        body[k] = parseFloat(v);
      } else {
        body[k] = v;
      }
    }

    msg.textContent = "salvo…";
    const r = await api("/profile", { method: "PUT", body });
    if (r && r.ok) {
      msg.textContent = "salvato. ricalcolo il riferimento…";
      // Ricarico la sezione cosi' vedo subito il BMR/TDEE aggiornato.
      setTimeout(() => loadSection("profilo"), 350);
    } else {
      let detail = "errore";
      try { detail = JSON.stringify((await r.json()).detail).slice(0, 160); } catch {}
      msg.textContent = `non sono riuscito a salvare: ${detail}`;
    }
  });
}

export { render, afterRender };
