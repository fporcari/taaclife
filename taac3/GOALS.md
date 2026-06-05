# GOALS.md — goal pronti per fase (v3)

Comandi `/goal` da incollare in Claude Code uno alla volta, in ordine. Dai il
goal successivo solo quando la fase precedente è completa e committata.

Prima di tutto incolla il **prompt di handoff** (vedi in fondo) e aspetta che
Claude Code abbia confermato di aver letto PROJECT.md, CLAUDE.md e questo
file. Poi parti da qui.

---

## Fase 1 — Scaffold + PWA shell

```
/goal Completa la Fase 1 (scaffold + PWA shell) come da PROJECT.md §15.
Inizializza un progetto SvelteKit con adapter-static, TypeScript strict,
Vite. Crea manifest.json (nome, icone segnaposto, theme color, display
standalone), service worker base che cache-a il bundle. Layout mobile-first
con bottom tab bar che ha 4 voci stub (Chat, Percorsi, Profilo,
Impostazioni — le altre arriveranno dopo). Routing client-side via
SvelteKit. Configura Vitest e Playwright. La home (/) renderizza una
schermata "Chat (in arrivo)". Test: Vitest gira a vuoto, Playwright smoke
"la app carica e mostra le 4 tab". Fase completa quando i test passano e
il commit è fatto.
```

## Fase 2 — SQLite-WASM + persistenza OPFS

```
/goal Completa la Fase 2 (SQLite-WASM + OPFS) come da PROJECT.md §7 e §8.
Integra @sqlite.org/sqlite-wasm con persistenza in OPFS. Crea
src/lib/db/index.ts con: openDb() (apre o crea il .db in OPFS),
closeDb(), runMigrations() (legge file SQL in src/lib/db/migrations/
e applica in ordine, traccia in schema_version), helper query (run,
get, all) tipizzati. Inizializza il DB all'avvio dell'app (loader UI
durante il warmup). Test: aprire, scrivere una riga in una tabella di
test, chiudere, riaprire, leggere e vedere il dato; migrations
idempotenti. Fase completa quando i test passano e il commit è fatto.
```

## Fase 3 — Modello dati + seed alimenti

```
/goal Completa la Fase 3 (modello dati + seed) come da PROJECT.md §8 e §9.
Crea migration 001_initial_schema.sql con tutte le tabelle di §8 (users,
settings, profile, preferences_liked, preferences_avoided, constraints,
weight_logs, foods, portions, paths, diary_entries, chat_messages,
schema_version). Crea src/lib/seed/foods.json convertendo
taaclife/seed/foods.csv (~130 alimenti CREA con porzioni etichettate
"da crudo"). Crea seed runner che popola foods+portions solo se vuoto
(idempotente). Stub di "primo avvio" che inserisce la riga unica in
users (display_name='io') e in profile (vuoto, goal=feel_good).
Test: schema applicato, seed idempotente, query base. Fase completa
quando i test passano e il commit è fatto.
```

## Fase 4 — Motore di calcolo (verificatore)

```
/goal Completa la Fase 4 (motore) come da PROJECT.md §10. Crea src/lib/
engine/nutrition.ts PURO (niente import di sqlite, niente import del SDK
Anthropic, niente import della UI). Implementa: tipi Profile, Sex
('F'|'M'), ActivityLevel, Goal (feel_good|maintain|gentle_loss|
gentle_gain), FoodNutrients, DiaryItem, MacroBreakdown, Needs, BMI,
DailyBalance, VerifyResult, PathStructure. Funzioni: computeBMR,
computeTDEE, computeNeeds, computeBMI (peso/(altezza_m)^2, neutro),
computeItemNutrients, sumItems, computeDailyBalance, verifyPath
(riceve path + database alimenti come arg, ritorna VerifyResult con
totals/notes/verified). Costanti dal v1 (ACTIVITY_FACTORS,
GOAL_FACTORS). Test completi con Vitest: Mifflin M/F casi noti, TDEE
per ogni livello, BMI casi noti, verifyPath con percorso coerente
(verified=true), verifyPath con totali fuori range (verified=false +
notes neutre), edge case (alimento non in DB → "stima" nelle notes).
Fase completa quando i test passano e il commit è fatto.
```

## Fase 5 — Sezioni "a mano" (CRUD UI senza LLM)

```
/goal Completa la Fase 5 (CRUD UI manuali) come da PROJECT.md §12.
Implementa le sezioni che permettono all'utente di gestire i dati
SENZA passare per il coach (sono un'alternativa al flow conversazionale):
- /profilo: form per calc_basis, birth_date, height_cm, activity_level,
  goal. GET/PUT su SQLite via Svelte store.
- /gusti: due liste (liked, avoided) con add/remove + campo constraints
  (text area). CRUD su preferences_liked, preferences_avoided, constraints.
- /peso: lista cronologica + form add. Sparkline SVG inline (riusa
  l'idea dal v1). CRUD su weight_logs.
- /diario: lista per giorno + form add con scelta food_id OPPURE free_text.
  CRUD su diary_entries.
- /impostazioni: toggle hide_calories, link disclaimer, stub per chiave
  Claude (vuoto, viene riempito in Fase 6).
Tutte le sezioni mostrano i numeri rilevanti chiamando il motore di
Fase 4 (BMI in profilo, fabbisogno in profilo se completo, totali
giornalieri in diario). Test e2e Playwright dei flussi principali.
Fase completa quando i test passano e il commit è fatto.
```

## Fase 6 — Impostazioni chiave Claude

```
/goal Completa la Fase 6 (chiave Claude) come da PROJECT.md §11.
In /impostazioni, sezione "Chiave Claude": campo password per
inserirla, pulsante "salva", pulsante "rimuovi". Al salvataggio,
validazione con call test al SDK Anthropic (messaggio "ping" da
max 10 token, mockata nei test). Se valida, salva in
settings(key='anthropic_api_key', value=...). Mostra stato:
"chiave configurata" / "chiave assente". Mai mostrare la chiave
in chiaro nella UI dopo il salvataggio (mostra solo "sk-...XYZ"
con i primi 4 e ultimi 4 caratteri). Test: salvataggio, recupero,
rimozione, leak-test (eccezione SDK contenente la chiave → la
chiave non compare nel detail mostrato all'utente né nei
console.log). NON chiamare davvero Anthropic nei test (mocka).
Fase completa quando i test passano e il commit è fatto.
```

## Fase 6.5 — Blocco locale (passphrase opzionale)

```
/goal Completa la Fase 6.5 (blocco locale Livello A) come da PROJECT.md
§11bis. In /impostazioni, sezione "Blocco app": toggle per attivare.
All'attivazione, modale che chiede passphrase + conferma + avviso
"non c'è recovery, se la dimentichi esporta il backup ora". Al
salvataggio, deriva un hash PBKDF2 (WebCrypto, 100k iter) e salva in
settings(key='lock_hash', value=...) + settings(key='lock_salt', ...)
+ settings(key='lock_enabled', value='1'). All'apertura dell'app, se
lock_enabled='1', mostra schermata "Sblocca" che chiede la passphrase
e la verifica contro l'hash. Senza passphrase corretta, la UI è
inaccessibile. "Cambia passphrase" e "Disattiva" richiedono la
corrente. Niente cifratura del DB qui (Livello A, vedi §11bis).
Test: attivazione, sblocco corretto, sblocco errato, cambio, disattivazione.
Fase completa quando i test passano e il commit è fatto.
```

## Fase 7 — Coach (chat)

```
/goal Completa la Fase 7 (coach) come da PROJECT.md §11. Crea src/lib/
coach/: context.ts (legge da SQLite e produce CoachContext: profilo +
BMI + gusti + constraints + ultimo peso + path attivo + ultime voci
diario + ultimi N chat_messages), system_prompt.ts (testo del
contratto §6, adattato da taaclife/core/coach.py), tools.ts
(definizioni dei tool: search_food, add_food, verify_path, save_path,
update_profile, add_weight, add_preference, set_constraints,
add_diary_entry), tool_runner.ts (execution: ogni write tool richiede
confirmed=true, altrimenti ritorna preview), llm.ts (wrapper del SDK
Anthropic con dangerouslyAllowBrowser:true, error handling che
NEUTRALIZZA messaggi che potrebbero contenere la chiave). Crea
/chat (home): composer in basso, bolle messaggi, history caricata da
SQLite. Al submit: persisti user msg, costruisci contesto, chiama
LLM con tool, processa tool_use loop (max 5 iter), persisti
assistant msg + scrivi nel DB quello che i tool con confirmed=true
hanno deciso. Se chiave assente: banner "metti la chiave da
Impostazioni". Test: contesto corretto, tool runner preview vs
confirm, leak-test della chiave su errori SDK, NON chiamare davvero
Anthropic (mocka). Fase completa quando i test passano e il commit è
fatto.
```

## Fase 8 — Percorsi (paths)

```
/goal Completa la Fase 8 (percorsi) come da PROJECT.md §11 e §12.
Aggiungi sezione /percorsi: lista cronologica dei path salvati, con
quello active=1 in evidenza. Click su un path → vista dettaglio
(title, summary, content renderizzato come griglia giorni/pasti),
pulsante "rendi attivo" (set active=0 sugli altri, active=1 su
questo), pulsante "duplica e modifica" (crea path con parent_id =
quello corrente, lo apre in edit). Implementa verify_path e save_path
tool runner come da §10 di PROJECT.md, collegati al motore di Fase 4.
Quando l'LLM propone un path nella chat, l'utente può confermare
salvataggio direttamente da chat o passare a /percorsi per vederlo
in dettaglio. Schema Pydantic-style (Zod) per il path JSON dell'LLM
con validazione rigida. Test: lista, attivazione, duplicazione,
verify_path con path coerente vs incoerente, flusso mockato di
generazione + verifica + save. Fase completa quando i test passano
e il commit è fatto.
```

## Fase 9 — Export / Import

```
/goal Completa la Fase 9 (export/import) come da PROJECT.md §13. In
/impostazioni, sezione "Backup e portabilità":
- "Esporta backup (.db)": scarica il file SQLite raw via
  sqlite-wasm export. Nome: nutricoach-backup-YYYYMMDD-HHMM.db.
- "Importa backup (.db)": <input type=file>, chiede conferma
  "vuoi sovrascrivere il DB corrente?", se sì importa.
- "Esporta dati (.json)": scarica nutricoach-export-v1-YYYYMMDD.json
  con export_version, exported_at, profile, preferences (liked,
  avoided, constraints), weights, paths (con content JSON), diary,
  chat_messages. ESCLUDE settings (chiave Claude, lock_hash, ecc.).
- "Importa dati (.json)": chiede conferma, ricostruisce le tabelle
  dalla struttura JSON. Supporta migrazione da versioni vecchie
  (per ora c'è solo v1).
Test round-trip: esporta .db → reset DB → importa → tutto torna;
esporta JSON → reset → importa JSON → tutto torna (escluse settings).
Fase completa quando i test passano e il commit è fatto.
```

## Fase 10 — Hardening + polish + deploy Netlify

```
/goal Completa la Fase 10 (hardening + polish + deploy) come da
PROJECT.md §14 e §19. Aggiungi:
- modale disclaimer al primo avvio (non skippabile, "accetto" salva
  in settings.disclaimer_accepted_at);
- onboarding conversazionale: se profilo vuoto, la prima chat inizia
  con "ciao, mi presenti i tuoi dati?" e il coach guida la
  compilazione via tool con confirmed (la UI mostra le proposte e
  l'utente conferma);
- error handling LLM (chiave invalida → toast "la chiave non sembra
  valida, ricontrolla in Impostazioni"; rate limit → toast; timeout
  → toast; tutti con messaggi neutri, niente chiave nei dettagli);
- reset DB con conferma (Impostazioni → "Azzera tutto"; chiede
  passphrase del blocco se attivo);
- polish UX mobile (autoresize composer, scroll-to-bottom, swipe-to-
  delete dove rilevante);
- a11y base (ARIA labels sui tap target, contrast checks);
- service worker rifinito per offline (le rotte non-coach devono
  funzionare offline; la chat mostra "serve connessione");
- configura deploy Netlify (netlify.toml, build command, redirects
  per SPA);
- README di repo con quick start + screenshot.
Test e2e completi che simulano flow utente reale (mocca il SDK
Anthropic). Fase completa quando i test passano, il deploy Netlify
produce un'app accessibile, e il commit è fatto.
```

---

## Promemoria d'uso

- Un goal alla volta, in ordine. Aspetta che la fase sia committata.
- Se /goal si ferma per limite orario, riapri e di': "riprendi da
  tasks/todo.md, continua dalla prima voce non spuntata".
- La chiave Claude serve da te (utente) solo dalla Fase 6 in poi per
  il test manuale. La metti dall'app, mai nel codice.
- Nessuna fase richiede chiamate reali a Anthropic nei test
  automatici. Lo SDK va sempre mockato.

---

## Prompt di handoff (per nuova sessione di Claude Code)

Incollalo come **primo** messaggio in una nuova sessione, dalla root
del repo nuovo (quello che creerai per il v3).

```
Sei l'ingegnere di questo progetto. Prima di tutto leggi
CLAUDE.md, PROJECT.md, README.md interamente (tutti nella root),
poi conferma riassumendo in 5 righe: principio architetturale,
vincoli duri, stack, ordine fasi, cosa fa la Fase 1.
Non scrivere codice prima di averlo fatto.

Regole di ingaggio per questa sessione e le successive:

1. Pianifica prima di costruire. All'inizio di ogni fase entra in
   plan mode: leggi i file rilevanti (mai affermazioni sul codice
   senza averlo aperto), poi scrivi il piano della fase in
   tasks/todo.md come voci spuntabili.

2. Lavora a fasi sequenziali secondo l'ordine di GOALS.md / §15 di
   PROJECT.md. Le fasi dipendono l'una dall'altra: non saltarle.

3. I test sono il cancello. A fine fase: scrivi/aggiorna test
   Vitest e Playwright, eseguili, non considerare la fase completa
   finché non sono verdi. I test che toccano l'LLM mockano il
   SDK — NON chiamare davvero Anthropic.

4. Committa a fine di ogni fase con messaggio chiaro che cita la
   fase, e aggiorna tasks/todo.md spuntando le voci fatte.

5. Vincoli duri di CLAUDE.md, sempre, senza eccezioni:
   - niente backend, niente fornitori intermediari;
   - l'LLM propone, il motore verifica;
   - scritture solo dietro conferma esplicita (tool con
     confirmed=true);
   - chiave Anthropic mai loggata, mai esposta;
   - alimenti da crudo;
   - tono non giudicante e default feel_good;
   - blocco locale (Fase 6.5) ≠ autenticazione;
   - TypeScript strict, niente librerie superflue;
   - mobile-first.

6. Procedi da solo da una fase alla successiva quando la precedente
   è completa e committata. Fermati a chiedere solo se: un test
   non passa dopo un tentativo serio (senza barare sul test), o una
   decisione non è coperta da PROJECT.md. In quei casi spiega in
   poche righe e proponi un'opzione.

Userò /goal per farti procedere fase per fase. Quando ti do un
goal, lavoraci fino a raggiungerlo davvero secondo i criteri qui
sopra, senza ridarmi il controllo a metà a ogni turno.

Parti ora: leggi i file e conferma.
```
