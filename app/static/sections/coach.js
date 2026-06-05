/* Sezione "Coach": chat con il coach LLM. */

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function bubble(msg) {
  return `<div class="bubble ${msg.role}">${escapeHtml(msg.content).replace(/\n/g, "<br>")}</div>`;
}

async function render() {
  const r = await api("/coach/history?limit=200");
  const history = r && r.ok ? await r.json() : [];

  const stream = history.length
    ? history.map(bubble).join("")
    : `<div class="coach-empty">Cosa vorresti raccontarmi oggi?</div>`;

  return `
    <section class="section">
      <div class="page-head">
        <div>
          <div class="kicker"><span class="label">N° 04 — la conversazione</span><hr></div>
          <h1>Un dialogo, <em>non un verdetto</em>.</h1>
        </div>
        <div class="meta">il coach legge i tuoi dati,<br>non li inventa</div>
      </div>
      <div class="coach">
        <div class="coach-stream" id="coach-stream">${stream}</div>
        <form class="coach-input" id="coach-form">
          <textarea id="coach-msg" placeholder="scrivi al coach… (invio per inviare, shift+invio per andare a capo)" required></textarea>
          <button class="btn" type="submit">invia</button>
        </form>
      </div>
    </section>
  `;
}

function scrollToBottom() {
  const stream = document.getElementById("coach-stream");
  if (stream) stream.scrollTop = stream.scrollHeight;
}

function afterRender() {
  scrollToBottom();
  const form = document.getElementById("coach-form");
  const txt = document.getElementById("coach-msg");
  const stream = document.getElementById("coach-stream");

  txt.addEventListener("keydown", ev => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // Autoresize textarea
  txt.addEventListener("input", () => {
    txt.style.height = "auto";
    txt.style.height = Math.min(txt.scrollHeight, 128) + "px";
  });

  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const content = txt.value.trim();
    if (!content) return;

    // Pulisci eventuale "empty state"
    const empty = stream.querySelector(".coach-empty");
    if (empty) empty.remove();

    // Renderizza subito la bolla utente
    stream.insertAdjacentHTML("beforeend", bubble({ role: "user", content }));
    txt.value = "";
    txt.style.height = "auto";
    scrollToBottom();

    // Placeholder "sta pensando"
    const placeholder = document.createElement("div");
    placeholder.className = "bubble assistant";
    placeholder.style.opacity = "0.6";
    placeholder.innerHTML = "<em>sto leggendo i tuoi dati…</em>";
    stream.appendChild(placeholder);
    scrollToBottom();

    const r = await api("/coach/chat", { method: "POST", body: { message: content } });
    placeholder.remove();

    if (!r) return;
    if (!r.ok) {
      let detail = `errore (HTTP ${r.status})`;
      try { detail = (await r.json()).detail || detail; } catch {}
      if (typeof detail !== "string") detail = JSON.stringify(detail);
      stream.insertAdjacentHTML("beforeend",
        `<div class="bubble assistant" style="border-color:var(--ink-faded);font-style:italic;color:var(--ink-faded)">${escapeHtml(detail)}</div>`);
    } else {
      const data = await r.json();
      stream.insertAdjacentHTML("beforeend", bubble({ role: "assistant", content: data.reply }));
      if (data.needs_missing) {
        stream.insertAdjacentHTML("beforeend",
          `<div class="bubble assistant" style="border-color:var(--accent);font-style:italic;color:var(--ink-soft);font-size:0.9rem;font-family:var(--mono)">
            nota: dato mancante nel profilo (${escapeHtml(data.needs_missing)}). compilalo nella sezione peso/profilo per un calcolo completo.
          </div>`);
      }
    }
    scrollToBottom();
  });
}

export { render, afterRender };
