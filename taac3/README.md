# NutriCoach v3 — documenti di progetto (browser-native)

Assistente conversazionale per l'alimentazione, **single-user per
dispositivo, completamente browser-based, senza backend**. La chat è
l'interfaccia, un SQLite locale (sqlite-wasm + OPFS) è la memoria. Ogni
utente porta la propria chiave Claude, salvata solo nel suo browser.
Stack: TypeScript + SvelteKit (static) + sqlite-wasm + Anthropic SDK
browser-side. Deploy su Netlify.

Questa cartella contiene i documenti di partenza per la **terza**
prospettiva del prodotto. Non è ancora codice: è il materiale per
partire.

Le due versioni precedenti vivono separate:

- **v1** (server-side Python, diario-centrica): implementata, ~220 test
  verdi, su GitHub come repo `taaclife`. Archivio storico.
- **v2** (server-side Python, chat-centrica con paths e chiave
  per-utente): solo documenti, in `taac2/`. Mai implementata: durante il
  ragionamento è emersa la motivazione "niente fornitori" che ha portato
  direttamente a v3 browser-native.

## I file, in ordine d'uso

1. **PROJECT.md** — la specifica completa di v3: vision, vincolo
   strutturale (niente fornitori), stack, modello dati, motore di
   calcolo, layer LLM, UI, export, blocco locale, fasi, decisioni.
   Leggi questo per primo.

2. **CLAUDE.md** — i vincoli duri, in forma breve. Da copiare nella
   root del repo nuovo: Claude Code lo rilegge a ogni sessione.

3. **GOALS.md** — i 11 comandi `/goal` pronti (Fase 1 → Fase 10, con
   Fase 6.5), uno per ogni fase. Include il **prompt di handoff** da
   incollare in una sessione fresca di Claude Code.

## Come iniziare il v3

1. **Crea un repo Git nuovo** (es. `nutricoach-pwa` su GitHub, pubblico
   o privato). Questo è un progetto separato da `taaclife` (lì resta
   il v1 archiviato). Decisione presa: v3 è TypeScript / SvelteKit /
   browser-native, niente in comune col codice del v1.

2. **Copia nel nuovo repo** i tre file di questa cartella: `PROJECT.md`,
   `CLAUDE.md`, `GOALS.md`. Aggiungi un `README.md` minimo (puoi
   sintetizzare questo).

3. **Apri Claude Code** in quella cartella nuova.

4. **Incolla il prompt di handoff** che trovi in fondo a `GOALS.md`.
   Aspetta che Claude Code abbia confermato di aver letto i tre file
   con un riassunto di 5 righe.

5. **Lancia i goal in ordine**, uno alla volta, copiando da `GOALS.md`.
   Dai il goal successivo solo quando la fase precedente è completa
   e committata.

6. **A fine progetto**, deploy su Netlify (vedi PROJECT.md §19 e Fase 10
   di GOALS.md).

## Promemoria

- **Niente segreti nel repo, mai.** Niente `ANTHROPIC_API_KEY` in
  nessun `.env`, niente `JWT_SECRET`, niente `ENCRYPTION_KEY`. La
  chiave Claude la mette l'utente dall'app, sta solo nel suo browser.
- **Niente backend in deploy.** Netlify serve solo file statici. Se
  qualcuno propone di aggiungere una Netlify Function o un Edge Worker,
  fermati: probabilmente sta violando il vincolo §1 di CLAUDE.md.
- **`tasks/todo.md`** (che Claude Code crea durante il lavoro) è la
  memoria del progetto: se una sessione si interrompe, si riprende
  da lì.
- **Lancia tu Vitest/Playwright ogni tanto**, come verifica indipendente.
- **Backup utente**: l'app esporterà `.db` raw + JSON semantico
  (Fase 9). L'utente è responsabile di salvarsi i backup periodici.
  Niente cloud sync.
