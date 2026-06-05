# CLAUDE.md — vincoli duri (v3 browser-native)

Istruzioni operative per chi lavora su questo repo (incluso Claude Code).
Il progetto completo è in PROJECT.md. Questo file sono le regole che non
si violano mai, da rileggere all'inizio di ogni sessione.

## Cos'è questo progetto

NutriCoach è una **PWA browser-native, single-user per dispositivo**:
una chat con un assistente di nutrizione che ha persistenza locale
del contesto in un SQLite-WASM (OPFS). Niente server, niente
fornitori intermediari. Stack: TypeScript + SvelteKit (static) +
sqlite-wasm + Anthropic SDK browser-side + Netlify per il deploy.

Le versioni precedenti (v1 e v2 server-side Python) vivono nel repo
storico `taaclife` come archivio. Questo è un repo **nuovo**.

## Regole dure (non negoziabili)

### 1. Niente server, niente fornitori intermediari

I dati personali e la chiave Anthropic dell'utente vivono **solo nel
suo browser**. Nessuno deve poterli leggere se non l'utente stesso.
Non si introducono backend, non si introducono servizi di sync, non
si introducono telemetrie. L'app fa due cose: gira nel browser, e
chiama `api.anthropic.com` con la chiave dell'utente. Punto.

Se senti il bisogno di aggiungere un backend (per qualunque motivo:
sync, backup, auth, sharing), **fermati e chiedi**. Probabilmente
c'è un altro modo. Spesso è export/import manuale.

### 2. L'LLM propone, il motore verifica

I valori nutrizionali e i conti di un percorso sono **garantiti dal
motore deterministico** (`engine/nutrition.ts`), non dall'LLM. L'LLM
ha libertà creativa sui percorsi e sul dialogo, ma:

- i kcal/macro di un alimento vengono dal database alimenti (DB locale);
- i totali di un percorso vengono dal motore (somma deterministica);
- BMR/TDEE/BMI vengono dal motore;
- ciò che non è in database va dichiarato esplicitamente come stima,
  mai presentato come fatto.

`engine/nutrition.ts` è puro: niente import di SQLite, niente import
del SDK Anthropic, niente import della UI. Riceve dati come argomenti,
ritorna risultati. Testabile in isolamento con Vitest.

### 3. Scritture solo dietro conferma esplicita

Ogni tool che modifica il DB locale (add_food, save_path,
update_profile, add_weight, add_preference, set_constraints,
add_diary_entry) richiede un parametro `confirmed: true` nel suo
input. Pattern obbligato:

1. L'LLM chiama il tool con `confirmed=false` (o senza il campo) →
   il tool ritorna una **preview** dei dati che verrebbero scritti,
   senza scrivere nulla.
2. L'LLM mostra la preview all'utente in linguaggio naturale e chiede
   conferma esplicita ("aggiungo questa voce? si'/no").
3. **Solo** dopo un consenso esplicito dell'utente nel messaggio
   successivo, l'LLM richiama il tool con `confirmed=true` per
   scrivere davvero.

Questo è il meccanismo che impedisce all'LLM di modificare i dati
senza che l'utente l'abbia chiesto. È un vincolo testato in v1/v2 e
riconfermato qui.

### 4. Chiave Anthropic dell'utente: mai loggata, mai esposta

La chiave dell'utente vive in `settings` (tabella SQLite). Va caricata
in memoria solo quando serve (chiamata a Anthropic) e:

- mai stampata in log (`console.log`, `console.error`, ecc.);
- mai inclusa in messaggi di errore mostrati all'utente;
- mai trasmessa a terzi se non a `api.anthropic.com` direttamente;
- mai serializzata in export JSON (l'export deve escluderla
  esplicitamente);
- mai inclusa in screenshot di debug o telemetria (che non esistono
  comunque, vedi §1).

Quando il SDK Anthropic alza un'eccezione, il wrapper deve rimappare
in messaggi neutri (es. "errore di autenticazione" non "401 invalid
key sk-ant-..."). Stesso pattern del `app/coach/llm.py` del v1.

### 5. Convenzione alimenti: da crudo / peso secco

I valori in `foods.kcal_100g` (e affini) sono **per 100g di alimento
crudo / a peso secco**. Le porzioni in `portions` sono etichettate
di conseguenza ("80 g di pasta cruda"). Sbagliarla raddoppia i conti
del diario e dei percorsi.

Documentato nel JSON di seed, nel system prompt del coach, e qui.

### 6. Tono non giudicante e default `feel_good`

Niente cibi "buoni" o "cattivi", niente celebrazione del deficit
calorico, niente shaming, niente categorie sul BMI
("sottopeso/normopeso"). Il default del goal è `feel_good` (nessun
obiettivo di peso). Le opzioni di perdita/guadagno sono **moderate**
(max -15% / +10%, identiche a v1/v2). Nessuna opzione "aggressiva"
esposta in UI.

L'app non è un dispositivo medico, non sostituisce un medico o un
nutrizionista. Disclaimer al primo avvio (modale non skippabile) e
sempre accessibile da Impostazioni.

### 7. Blocco locale opzionale (passphrase) ≠ autenticazione

Il blocco locale (§11bis di PROJECT.md) è un **freno fisico**: serve a
proteggere contro l'accesso non autorizzato al dispositivo. Non è
autenticazione (non c'è server). Non c'è recovery: dimenticare la
passphrase significa perdere i dati locali (o recuperare dal backup
`.db` esportato). Questo è dichiarato esplicitamente all'utente
quando attiva il blocco.

Non implementare mai "password dimenticata" via email, SMS, o
qualunque altro canale che richieda un servizio terzo. Sarebbe
violazione del §1.

### 8. TypeScript strict, niente `any`

Tutto il codice è TypeScript in `strict` mode. `any` è ammesso solo
con commento esplicito che spiega perché (es. integrazione con un
SDK che non ha tipi). `unknown` è preferibile quasi sempre.

### 9. Niente librerie inutili

PWA leggera. Ogni dipendenza aggiunta deve essere giustificata. In
particolare:

- **No Tailwind**: CSS vanilla con variabili è sufficiente per questo
  prodotto. Niente classi-utility a profusione.
- **No state management library** (no Redux, no Zustand, no MobX):
  Svelte stores bastano.
- **No date library** (no moment, no dayjs): l'API nativa
  `Intl.DateTimeFormat` + `Temporal` (quando disponibile) bastano.
  Per parsing/format basic, scrivere helper di 10 righe.
- **No HTTP client** (no axios): `fetch` nativo basta.
- **Sì** al SDK Anthropic ufficiale, **sì** a sqlite-wasm ufficiale,
  **sì** a un piccolo wrapper di Kysely se serve query type-safe
  (valutare a Fase 3).

### 10. Mobile-first sempre

Ogni pezzo di UI nasce pensato per il telefono. Tap target ≥ 44px.
Niente comportamenti hover-only. Layout a colonna stretta che
fluisce a desktop, non viceversa.

## Metodo di lavoro

- Seguire l'ordine di fasi di PROJECT.md §15, una alla volta.
- **Committare a fine di ogni fase**, con messaggio chiaro.
- **Non passare alla fase successiva se i test della fase corrente
  non passano.** Vitest verde è il cancello. Per le fasi che toccano
  l'LLM, i test mockano il SDK Anthropic — mai chiamate reali nei
  test automatici.
- "Fase completa" = test verdi E vincoli duri rispettati. Non far
  passare i test con scorciatoie che violano i vincoli.
- Se una decisione non è coperta da PROJECT.md, scegliere l'opzione
  più semplice e documentarla in `tasks/todo.md`, oppure fermarsi e
  segnalarla, invece di inventare.
- Mantenere `tasks/todo.md` aggiornato come memoria del progetto.
  Se una sessione si interrompe, si riprende da lì.

## File di riferimento

- **PROJECT.md** — specifica completa.
- **GOALS.md** — comandi /goal pronti, uno per fase.
- **README.md** — indice e come iniziare.
- **CLAUDE.md** — questo file.
