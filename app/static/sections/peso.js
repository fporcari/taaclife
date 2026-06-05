/* Sezione "Peso": lista cronologica + sparkline SVG inline. */

function fmt(n, d = 1) { return Number(n).toFixed(d); }

function sparkline(points) {
  if (!points.length) {
    return `<div class="coach-empty" style="font-size:1.4rem">
      ancora nessun peso registrato
    </div>`;
  }
  const W = 600, H = 180, padL = 40, padR = 10, padT = 20, padB = 25;

  // Ordina per data crescente.
  const sorted = [...points].sort((a, b) => a.measured_at.localeCompare(b.measured_at));
  const xs = sorted.map(p => new Date(p.measured_at).getTime());
  const ys = sorted.map(p => p.weight_kg);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const dy = Math.max(maxY - minY, 1.0);

  const x = t => padL + (maxX === minX ? (W - padL - padR) / 2
    : ((t - minX) / (maxX - minX)) * (W - padL - padR));
  const y = w => padT + (1 - (w - (minY - dy * 0.2)) / (dy * 1.4)) * (H - padT - padB);

  const path = sorted.map((p, i) => `${i ? "L" : "M"} ${x(xs[i]).toFixed(1)} ${y(ys[i]).toFixed(1)}`).join(" ");
  const area = `${path} L ${x(xs[xs.length - 1]).toFixed(1)} ${H - padB} L ${x(xs[0]).toFixed(1)} ${H - padB} Z`;

  const dots = sorted.map((p, i) => `<circle class="dot" cx="${x(xs[i]).toFixed(1)}" cy="${y(ys[i]).toFixed(1)}" r="3"/>`).join("");

  // Etichette: estremi sull'asse Y
  const labels = `
    <text class="axis" x="6" y="${y(maxY) + 4}">${fmt(maxY)}</text>
    <text class="axis" x="6" y="${y(minY) + 4}">${fmt(minY)}</text>
    <line class="grid" x1="${padL}" y1="${y(maxY).toFixed(1)}" x2="${W - padR}" y2="${y(maxY).toFixed(1)}"/>
    <line class="grid" x1="${padL}" y1="${y(minY).toFixed(1)}" x2="${W - padR}" y2="${y(minY).toFixed(1)}"/>
  `;
  const xlabel0 = new Date(minX).toLocaleDateString("it-IT", { day: "2-digit", month: "short" });
  const xlabel1 = new Date(maxX).toLocaleDateString("it-IT", { day: "2-digit", month: "short" });
  const xLabels = `
    <text class="axis" x="${padL}" y="${H - 6}">${xlabel0}</text>
    <text class="axis" x="${W - padR}" y="${H - 6}" text-anchor="end">${xlabel1}</text>
  `;

  return `
    <div class="spark">
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-label="Andamento del peso">
        ${labels}
        ${xLabels}
        <path class="area" d="${area}"/>
        <path class="line" d="${path}"/>
        ${dots}
      </svg>
    </div>
  `;
}

async function render() {
  const r = await api("/weights?limit=365");
  const list = r && r.ok ? await r.json() : [];

  const items = list.map(w => `
    <li><span class="date">${new Date(w.measured_at).toLocaleDateString("it-IT", { day: "2-digit", month: "short", year: "2-digit" })}</span>
      <span class="kg">${fmt(w.weight_kg)} kg</span></li>
  `).join("");

  const today = new Date().toISOString().slice(0, 10);

  return `
    <section class="section">
      <div class="page-head">
        <div>
          <div class="kicker"><span class="label">N° 03 — la traiettoria</span><hr></div>
          <h1>Il <em>peso</em>, nel tempo.</h1>
        </div>
        <div class="meta">una linea che si muove,<br>non un voto</div>
      </div>
      <div class="weight-grid">
        <div>
          ${sparkline(list)}
          <form id="weight-form" style="display:grid;grid-template-columns:auto 1fr auto;gap:1rem;align-items:end;margin-top:2rem">
            <div>
              <span class="label" style="display:block;margin-bottom:0.3rem">data</span>
              <input class="input" type="date" name="measured_at" value="${today}" required>
            </div>
            <div>
              <span class="label" style="display:block;margin-bottom:0.3rem">peso (kg)</span>
              <input class="input" type="number" step="0.1" min="20" max="300" name="weight_kg" placeholder="es. 62.4" required>
            </div>
            <button class="btn" type="submit">registra</button>
          </form>
        </div>
        <div>
          <div class="kicker"><span class="label">Cronologia</span><hr></div>
          <ul class="weight-list">${items || '<li><em style="color:var(--ink-faded)">nessuna voce</em></li>'}</ul>
        </div>
      </div>
    </section>
  `;
}

function afterRender() {
  const form = document.getElementById("weight-form");
  if (!form) return;
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    data.weight_kg = parseFloat(data.weight_kg);
    const r = await api("/weights", { method: "POST", body: data });
    if (r && (r.ok || r.status === 201)) loadSection("peso");
  });
}

export { render, afterRender };
