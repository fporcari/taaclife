# NutriCoach v3 — proto-progetto (browser-native)

Documento di partenza per la **terza** prospettiva del prodotto. Le due
versioni precedenti (`/PROJECT.md` v1 server-side diario-centrico, e
`taac2/PROJECT.md` v2 server-side chat-centrico) sono state archiviate
come riferimento. Questa è la versione corrente.

---

## 1. Frase di partenza

NutriCoach è una **PWA browser-native, single-user per dispositivo, senza
backend**. È un layer di contesto sulla chat con un assistente di
nutrizione: dà persistenza alla situazione (chi sei, cosa ti piace, cosa
hai mangiato, che piano segui) e alla sua evoluzione (come cambia nel
tempo). La chat è l'interfaccia; un SQLite locale nel browser è la
memoria del rapporto coach-utente.

## 2. Il vincolo che decide tutto: niente fornitori

L'utente non vuole dipendere da nessun fornitore di servizi (incluso me
che scrivo il codice). I dati personali e la chiave Anthropic devono
**stare solo sul dispositivo dell'utente**. Niente hosting di un backend,
niente database in cloud, niente "fidati di chi ospita".

Conseguenze architetturali, tutte derivate da questo vincolo:

- **Zero server**: nessun FastAPI, nessun Hetzner, nessun Docker. L'app
  è un bundle di file statici (HTML+JS+WASM+CSS).
- **SQLite-WASM nel browser** con persistenza in OPFS (Origin Private
  File System). Il database `.db` vive nel filesystem privato del
  browser dell'utente.
- **Chiave Anthropic in `localStorage`** del browser, mai trasmessa
  altrove se non direttamente a `api.anthropic.com`.
- **Chiamate Anthropic dirette dal browser**. Anthropic accetta
  questo caso d'uso con il flag `dangerouslyAllowBrowser: true` del
  SDK ufficiale: è "pericoloso" per un fornitore SaaS che esporrebbe
  la sua chiave ai browser dei clienti, ma per noi è **sicuro perché
  la chiave è dell'utente stesso**. Non c'è nessuno a cui rubarla che
  non sia l'utente.
- **Multi-utente = multi-browser/dispositivo**. Ogni browser ha il suo
  database. Te e tua moglie aprite lo stesso URL ma vedete dati
  diversi perché ognuno è nel proprio OPFS. Niente login,
  niente account, niente confusione.
- **Niente autenticazione tradizionale.** Senza server non c'è nessuno
  a cui presentare credenziali, e non c'è nessuna ragione per averle.
  L'unica protezione che ha senso è un **blocco locale opzionale** —
  vedi §11bis.
- **Hosting**: Netlify (statico, gratis, HTTPS automatico). L'app vive
  su un URL pubblico ma i dati non escono mai dal browser.

## 3. Layer di contesto sulla chat

Definizione di prodotto:

> NutriCoach è un layer di contesto sulla chat: dà persistenza alla
> situazione e alla sua evoluzione. La chat è l'interfaccia; il DB è
> la memoria del rapporto coach-utente.

Implicazione: ogni tabella del modello dati (profilo, gusti, pesi,
percorsi, voci diario) è un pezzo del "layer di contesto". L'LLM senza
queste tabelle è un chatbot generico; con queste tabelle è un coach
che ti conosce.

A ogni nuovo turno della chat, l'app:
1. legge dal DB locale lo stato corrente (profilo + gusti +
   constraints + ultimo peso + percorsi salvati + ultime voci di
   diario);
2. costruisce un blocco JSON di contesto da iniettare nel prompt;
3. chiama Claude con la chiave dell'utente, system prompt del
   contratto §6, e i tool;
4. interpreta la risposta e **persiste subito nel DB** ogni dato
   significativo che l'utente ha confermato in chat (peso, altezza,
   gusti, piani settimanali).

Lo storico chat resta in tabella `chat_messages` come traccia
narrativa, ma è il DB strutturato che dà al coach il contesto
persistente, non il riassunto della chat.

## 4. Onboarding conversazionale (l'esperienza primaria)

L'utente apre l'app, mette la chiave Claude in Impostazioni, e da quel
momento parla con il nutrizionista AI. Niente form di profilo, niente
"compila prima". La prima chat **è** l'onboarding:

- il coach si presenta (con disclaimer di partenza, §5),
- chiede peso, altezza, età, attività;
- calcola e mostra **BMI** (numero neutro, niente categorie
  "sottopeso/normopeso");
- chiede gusti (liked, avoided) e vincoli (es. "vegetariana",
  "poco tempo la sera");
- propone un primo **piano settimanale** sui gusti dell'utente,
  verificato dal motore;
- salva tutto nel DB (profile, preferences, weight_log, path).

Da lì in avanti l'app sa chi è l'utente. Le chat successive ereditano
il contesto. "Voglio variare il martedì sera" diventa: il coach carica
l'ultimo path attivo dal DB, modifica solo quel pasto, fa verificare al
motore, salva una **nuova versione** del path (non sovrascrive — la
storia si conserva).

## 5. Disclaimer

L'app **non è un dispositivo medico** e **non sostituisce un
nutrizionista o un medico**. Disclaimer mostrato:

- al primo avvio (modale di onboarding non skippabile),
- sempre accessibile da Impostazioni,
- presente nel system prompt del coach.

Tono di supporto, mai diagnostico. I percorsi sono suggerimenti di
benessere, non prescrizioni dietetiche.

In più, per scelta di prodotto (uso personale dell'utente proprietario):
- niente categorizzazione del BMI ("sottopeso/normopeso/sovrappeso");
- niente celebrazione del deficit calorico;
- l'utente può nascondere le calorie dall'UI in qualsiasi momento.

## 6. Principio architetturale: l'LLM propone, il motore verifica

Il ruolo dell'LLM e del motore sono separati:

- **L'LLM genera e racconta**: costruisce i percorsi alimentari sui
  gusti dell'utente, dialoga, spiega, adatta. È la parte creativa e
  relazionale.
- **Il motore verifica**: `engine/nutrition.ts` (TypeScript puro,
  testabile), valida i conti di un percorso proposto contro il
  database alimenti e il fabbisogno stimato.
- **Numeri mostrati come fatti certi vengono dal motore o dal database
  alimenti**, non inventati dall'LLM. Quando l'LLM propone un percorso,
  i valori nutrizionali si ricavano dal database; il motore somma e
  confronta. Se un alimento non è in database, l'LLM lo segnala come
  stima, non come dato.

L'LLM ha libertà creativa sui *percorsi e sul dialogo*, ma i *numeri*
restano ancorati a database + motore.

## 7. Stack tecnico

| Livello             | Scelta                                                           |
|---------------------|------------------------------------------------------------------|
| Linguaggio          | TypeScript (strict mode)                                         |
| Framework UI        | SvelteKit (mode SPA, adapter-static)                             |
| Database (locale)   | SQLite via sqlite-wasm ufficiale + OPFS                          |
| Query layer         | sql.js wrapper sottile / Kysely (se serve type-safety)           |
| LLM SDK             | `@anthropic-ai/sdk` con `dangerouslyAllowBrowser: true`         |
| Stile               | CSS vanilla + variabili. Niente Tailwind (PWA leggera)           |
| Test                | Vitest (unit) + Playwright (e2e/PWA)                             |
| Build               | Vite (via SvelteKit)                                             |
| Hosting             | Netlify (statico, HTTPS, deploy via git push)                    |
| Mobile              | PWA installabile (manifest + service worker)                     |

Note di scelta:

- **SvelteKit modalità statica**: l'app è un bundle prerenderizzato.
  Zero server. Configurazione `adapter-static` con `fallback: 'index.html'`
  perché è una SPA con routing client-side.
- **sqlite-wasm + OPFS**: il binario WASM è ~1MB, caricato una volta.
  OPFS è uno standard moderno (Chrome 102+, Safari 17.4+, Firefox 111+).
  Niente IndexedDB hacky.
- **Niente Tailwind, niente UI library**: PWA leggera e veloce. CSS
  vanilla con variabili e un design system minimale.
- **Mobile-first**: il layout è pensato per il telefono. Scale fluida
  su desktop, niente layout drasticamente diverso.

## 8. Modello dati (SQLite locale)

```
users                              # in pratica c'è una sola riga: l'utente
  id (integer pk)                   # del browser. Tabella tenuta per ordine
  display_name (text)               # e per supportare future estensioni.
  created_at (datetime)

settings                            # chiave-valore semplice
  key (text pk)
  value (text)
  -- es. 'anthropic_api_key', 'coach_model', 'hide_calories' (bool stringato)

profile                             # un profilo per database (single-user)
  id (integer pk)                   # sempre 1, vincolo CHECK
  calc_basis (text)                 # 'F' | 'M' (parametro Mifflin)
  birth_date (date)
  height_cm (real)
  activity_level (text)             # sedentary/light/moderate/active/very_active
  goal (text)                       # feel_good (default) | maintain | gentle_loss | gentle_gain
  updated_at (datetime)

preferences_liked                   # lista cibi/piatti graditi
  id (integer pk)
  value (text not null)
  created_at (datetime)

preferences_avoided                 # lista cibi/piatti evitati
  id (integer pk)
  value (text not null)
  reason (text)                     # opzionale: "allergia", "non mi piace"
  created_at (datetime)

constraints                         # note libere di contesto (1 riga di solito)
  id (integer pk)
  text (text)                       # "vegetariana, palestra mar/gio, poco tempo la sera"
  updated_at (datetime)

weight_logs
  id (integer pk)
  measured_at (date not null)
  weight_kg (real not null)
  unique (measured_at)

foods                               # database alimenti (CREA + personali)
  id (integer pk)
  name (text not null)
  category (text)
  kcal_100g (real not null)
  protein_100g (real not null)
  carbs_100g (real not null)
  fat_100g (real not null)
  fiber_100g (real)
  source (text)                     # 'CREA' | 'user'

portions                            # porzioni di riferimento per alimento
  id (integer pk)
  food_id (fk foods)
  label (text)                      # "80 g di pasta cruda"
  grams (real not null)

paths                               # i percorsi alimentari generati
  id (integer pk)
  created_at (datetime)
  title (text not null)
  summary (text)                    # descrizione narrativa
  content (text not null)           # JSON dei pasti/giorni/porzioni
  verified (integer)                # 0/1
  verify_notes (text)
  parent_id (fk paths)              # versioning: questa è una variazione di X
  active (integer)                  # 0/1, il path "in uso" è active=1

diary_entries                       # opzionale, materiale per il dialogo
  id (integer pk)
  consumed_at (datetime not null)
  meal (text)                       # breakfast/lunch/dinner/snack
  food_id (fk foods)
  free_text (text)                  # "una pizza con gli amici" senza per forza il DB
  grams (real)
  -- CHECK (food_id IS NOT NULL AND grams > 0) OR free_text IS NOT NULL

chat_messages                       # storico narrativo della chat
  id (integer pk)
  role (text)                       # 'user' | 'assistant' | 'system_event'
  content (text not null)
  created_at (datetime)

schema_version                      # per migrazioni future
  version (integer pk)
  applied_at (datetime)
```

Nota: il vincolo "single-user per database" è tenuto a livello
applicativo (CHECK sui PK + UI che non espone "switch user"). Il
multi-utente è il multi-browser.

## 9. Database alimenti

### Fonte
Tabelle di composizione degli alimenti CREA (ex-INRAN), valori per 100 g
di parte edibile. Seed iniziale di ~100 alimenti italiani comuni
incorporato nel bundle JS (file `seed/foods.json` generato dal CSV).

### Strategia
- Al primo avvio, se la tabella `foods` è vuota, l'app legge il JSON
  embed e popola SQLite.
- L'utente può aggiungere alimenti personali (`source='user'`) da UI o
  via chat ("aggiungi 'tortino della nonna': 250 kcal, 5g proteine..."
  → il coach chiama un tool `add_food` con conferma).

### Convenzione crudo/cotto
Valori per 100 g di alimento **da crudo / a peso secco**. Le porzioni
etichettate di conseguenza ("80 g di pasta cruda"). Sbagliarla raddoppia
i conti. Documentato nel commento del JSON di seed e nel system prompt.

## 10. Motore di calcolo (verificatore deterministico)

Modulo `engine/nutrition.ts`, puro (niente DB direct, niente rete, niente
LLM). Riceve in ingresso dati e database alimenti come argomento.

### Funzioni di calcolo (formule da PROJECT v2 §9)
- **BMR** Mifflin-St Jeor (base M / F).
- **TDEE** = BMR × fattore attività (1.2 / 1.375 / 1.55 / 1.725 / 1.9).
- **BMI** = peso / (altezza_m)². Numero neutro, niente categoria.
- **Fabbisogno** secondo il goal: `feel_good` ≈ TDEE,
  `maintain` ≈ TDEE, `gentle_loss` TDEE × 0.85, `gentle_gain` TDEE × 1.10.

### Verifica di un percorso
Data la struttura di un percorso proposto dall'LLM (giorni, pasti,
alimenti con grammature), il motore:
- somma kcal e macro usando i valori del database (passati come arg);
- confronta col fabbisogno stimato;
- ritorna `VerifyResult { verified: boolean, totals, notes }` con note
  neutre.

### Test
Vitest. Mifflin M/F su casi noti, TDEE per ogni livello, BMI, verifica
percorso con totali noti, edge case (profilo incompleto, alimento fuori
DB → dichiarato come stima nelle note).

## 11. Layer LLM (l'assistente)

Modulo `app/coach/` (TypeScript). È il cuore conversazionale.

### Chiave
La chiave Anthropic dell'utente, presa da `settings` in SQLite, viene
caricata in memoria a inizio sessione del browser. Mai loggata, mai
mandata altrove se non a `api.anthropic.com`.

### Contesto a ogni messaggio
Il modulo `coach/context.ts` legge da SQLite e costruisce un oggetto
`CoachContext` strutturato:
- profilo + BMI calcolato,
- gusti (liked / avoided / constraints),
- ultimo peso e storia recente (ultimi 30 giorni),
- path attivo + ultimi 2 path archiviati,
- ultime voci di diario,
- ultimi N messaggi della chat (finestra).

Iniettato come primo "user message" in formato `<context>...</context>`.

### System prompt (contratto)
Vedi §5 e §6: non sostituisce un medico; può proporre percorsi e dialogare
ma i numeri si ancorano al database; passa i percorsi al motore prima di
presentarli come "a posto"; tono non giudicante; default `feel_good`.

### Tool esposti
- `search_food(query)` — ricerca nel DB locale
- `add_food(food)` — aggiunge alimento personale (richiede `confirmed=true`)
- `verify_path(path)` — chiama il motore per validare un percorso
- `save_path(path)` — salva (con `confirmed=true`)
- `update_profile(field, value)` — aggiorna profilo (con `confirmed=true`)
- `add_weight(date, kg)` — registra peso (con `confirmed=true`)
- `add_preference(kind, value)` — aggiunge gusto (con `confirmed=true`)
- `set_constraints(text)` — aggiorna note libere (con `confirmed=true`)
- `add_diary_entry(...)` — registra voce diario (con `confirmed=true`)

Tutte le scritture passano per **conferma esplicita**: preview senza
scrittura → utente dice "sì" a parole → re-chiamata con
`confirmed=true` → scrittura effettiva. Pattern provato nelle v1/v2.

### Loop di tool-use
Max 5 iterazioni, come nella v2. Se l'LLM continua a chiedere tool senza
chiudere con un text, abortiamo con messaggio neutro.

### Comportamento senza chiave
La chat è disattivata con un banner chiaro che porta a Impostazioni.
Il resto dell'app funziona: l'utente può vedere il profilo,
modificarlo a mano, vedere i percorsi salvati, vedere il diario.

## 11bis. Blocco locale (passphrase opzionale)

Niente autenticazione tradizionale, ma una protezione locale leggera ha
senso per uno scenario realistico: **furto del telefono / accesso fisico
non autorizzato al dispositivo**. Se qualcuno apre l'app dal tuo
browser senza che ci sia un blocco, vede subito tutta la tua storia
nutrizionale + ha la possibilità di usare la **tua** chiave Claude
(che paghi tu) finché non te ne accorgi.

### Cosa è il blocco locale (cosa sembra)

Tipo "blocco di 1Password". Una passphrase impostata dall'utente
**localmente nel browser**, mai trasmessa altrove. Funziona così:

- L'utente attiva il blocco da Impostazioni (è opzionale, di default
  spento per non aggiungere attrito).
- Definisce una passphrase (libera; suggeriamo lunga e ricordabile).
- Da quel momento, all'apertura dell'app (o dopo N minuti di inattività)
  appare una schermata "sblocca" che chiede la passphrase.
- Senza passphrase corretta, l'app non parte. La chat è inaccessibile,
  il DB è inaccessibile.
- "Cambia passphrase" e "Disattiva blocco" sono disponibili
  conoscendo la passphrase corrente.

### Cosa NON è (cosa non sembra)

- **Non è autenticazione**. Non c'è server, non c'è "verifica
  identità". È solo un freno locale.
- **Non è un sistema di recovery**. Se dimentichi la passphrase **non
  c'è un "password dimenticata"** — la chiave Claude e il DB locale
  vanno persi (o l'utente recupera dal backup `.db` che ha
  esportato). Questo è un tradeoff esplicito che si dichiara
  all'attivazione.

### Implementazione concreta

Due livelli di sicurezza fra cui scegliere a tempo di disegno:

**Livello A — protezione UI semplice** (raccomandato per partire):
- La passphrase produce un hash (es. PBKDF2 / Argon2-WASM) salvato in
  `localStorage`.
- All'apertura, la UI confronta l'hash e svela o no l'app.
- La chiave Claude e il DB SQLite restano **non cifrati** sul disco
  del browser. Chi ha accesso fisico al dispositivo + skill tecniche
  (es. apre il DevTools, ispeziona OPFS) può comunque leggerli.
- È onesto come livello: protegge da chi prende il telefono in mano,
  non da un analista forense.

**Livello B — cifratura a riposo della chiave e/o del DB**:
- La passphrase deriva (PBKDF2) una chiave di cifratura.
- La chiave Claude in `settings` viene cifrata con WebCrypto (AES-GCM)
  prima di essere salvata.
- Optional: anche il DB SQLite viene cifrato a riposo (più complesso
  perché OPFS non ha cifratura nativa; si farebbe scrivendo il `.db`
  cifrato come blob e tenendo il "DB vivo" solo in RAM, con flush
  periodico cifrato).
- Più sicuro contro accesso forense, ma più complesso da
  implementare e da gestire (ricaricamento dopo crash, performance).

**Decisione**: partiamo con **Livello A** come opzione, da attivare in
Impostazioni. Aggiunto come **Fase 6.5** (dopo la fase Impostazioni
chiave Claude) senza bloccare il resto. Livello B resta possibile come
upgrade futuro se l'utente lo chiede.

## 12. UI / esperienza utente

### Schermata principale: la chat
La home (`/`) è la chat con il coach. Non c'è una "dashboard". Il coach
mostra in alto un riepilogo testuale di chi sei ("ciao Francesco, oggi
sei a 62.3kg, segui il piano del 2 marzo, restano 4 giorni") e attende
il tuo messaggio.

### Sezioni laterali (tab/menu)
- **Chat** (home)
- **Percorsi** (lista dei path salvati, con quello `active=1` in
  evidenza; click su un path → vista dettaglio + bottone "rendi attivo")
- **Profilo** (i dati base, modificabili a mano se uno preferisce)
- **Gusti** (liked / avoided / constraints, modificabili a mano)
- **Peso** (lista cronologica + sparkline)
- **Diario** (solo se l'utente lo abilita esplicitamente)
- **Impostazioni** (chiave Claude, modello, hide_calories, export/import,
  reset DB, disclaimer)

### Mobile-first
- Layout a colonna stretta, max-width 720px su desktop.
- Tab in fondo allo schermo (bottom tab bar) su mobile, sidebar su
  desktop largo.
- Tap targets ≥ 44px.
- Niente hover-only.
- Composer chat sempre visibile, autoresize.

### Toggle "nascondi calorie"
In Impostazioni. Maschera i numeri kcal in tutta l'UI con `···`. Coerente
col vincolo etico.

### Tono visivo
Editorial leggero (carta + inchiostro + un solo accento), tipografia
serif espressiva per i titoli + sans clean per il body. Niente
gamification, niente badge, niente streak.

## 13. Export / import / backup

**Due livelli** di portabilità:

### Backup tecnico = `.db` raw
Pulsante "Esporta backup" che scarica un file `.db` binario. Importabile
con "Importa backup" che chiede conferma ("vuoi sovrascrivere il
database corrente?"). Veloce, fedele, leggibile da qualunque tool
SQLite anche fuori dall'app.

### Export semantico = JSON versionato
Pulsante "Esporta dati" che scarica un `nutricoach-export-v1-{data}.json`
con:
- `export_version`: 1
- `exported_at`: ISO datetime
- profile, preferences, constraints, weights, paths, diary, chat history
- (esclusi: chiave Anthropic, settings tecniche)

Importabile da "Importa dati" che ricostruisce il DB. Sopporta versioni
vecchie via migrazione del JSON.

### Strategia di sync (per chi vuole più dispositivi)
Mettere il file `.db` su iCloud Drive / Drive condiviso e fare
esporta/importa a mano. Niente sync automatico (sarebbe un servizio,
quindi un fornitore, quindi violerebbe il vincolo §2).

## 14. PWA (Progressive Web App)

- `manifest.json` con nome, icone, theme color, display:standalone.
- Service worker per **funzionamento offline parziale**: tutto il
  bundle JS/CSS/WASM in cache. Le sezioni che non richiedono Claude
  (vedere il proprio profilo, modificare gusti, vedere i path salvati,
  registrare peso) funzionano offline. La chat richiede rete.
- "Aggiungi a home" funziona su iOS (Safari) e Android (Chrome) e
  macOS (Chrome/Edge come app installabile).

## 15. Ordine di lavoro (fasi)

Fasi committabili e verificabili. Niente backend = meno fasi della v2.

1. **Scaffold + PWA shell**: SvelteKit con `adapter-static`, manifest,
   service worker base, layout mobile-first con bottom tab bar.
   Test: Vitest gira a vuoto, Playwright smoke "la app carica".

2. **SQLite-WASM + persistenza OPFS**: integrare il binario, aprire/
   creare il `.db`, eseguire migrazioni, helper di query type-safe.
   Test: aprire, scrivere, chiudere, riaprire, vedere il dato.

3. **Modello dati + seed**: schema SQL di §8, migrazione iniziale,
   seed di ~100 alimenti CREA da un JSON embed. Test: schema corretto,
   seed idempotente, query base.

4. **Motore di calcolo (verificatore)**: `engine/nutrition.ts` puro,
   tutte le formule + verify_path. Test completi.

5. **Sezioni "a mano"**: UI di profilo, gusti, peso, diario,
   impostazioni. CRUD su SQLite via Svelte stores. Niente LLM
   ancora. Test e2e Playwright dei flussi.

6. **Impostazioni chiave Claude**: form per inserire/cambiare/cancellare
   la chiave, salvataggio in `settings`, validazione con call test
   leggera al SDK Anthropic. Test: chiave salvata, ricaricamento la
   recupera, validazione mocked.

7. **Coach (chat)**: `coach/context.ts` legge il contesto da SQLite,
   `coach/llm.ts` chiama Anthropic SDK con tool, `coach/persist.ts`
   scrive i risultati dei tool nel DB. UI chat (composer, bolle,
   history). Test: contesto costruito correttamente, tool wired,
   chiamata mockata. Test e2e con SDK mockato per il flusso completo.

8. **Percorsi (paths)**: tool `verify_path`, `save_path` collegati
   al motore (Fase 4); sezione "Percorsi" con lista, dettaglio, "rendi
   attivo", versioning via `parent_id`. Test sul flusso genera→verifica→
   rifinisci→salva mockato.

9. **Export / import**: pulsanti per `.db` raw e JSON semantico nelle
   Impostazioni. Schema JSON versionato. Test round-trip
   (esporto → cancello DB → importo → tutto torna).

10. **Hardening + polish**: disclaimer modale al primo avvio,
    onboarding conversazionale (il coach guida la compilazione),
    error handling LLM (chiave invalida, rate limit, timeout), reset
    DB con conferma, UX su mobile, accessibility. Deploy su Netlify.

## 16. Decisioni di progetto (chiuse)

- **Stack**: TypeScript + SvelteKit static + sqlite-wasm + OPFS +
  Anthropic SDK browser-side. Niente Tailwind.
- **Database**: SQLite locale per dispositivo. No sync automatico.
- **Chiave Claude**: in `settings` table di SQLite, mai in chiaro fuori.
- **Multi-utente**: multi-browser. Niente login.
- **Mobile-first**: il telefono è il primo target.
- **Distribuzione**: Netlify. PWA installabile come app.
- **Niente Electron**: la PWA installata è già un'app nativa-like.
- **Backup**: manuale (export `.db` + export JSON), niente cloud sync.
- **goal default**: `feel_good`.
- **BMI**: calcolato e mostrato (numero neutro, niente categorie).
- **Open Food Facts**: rimandato a v3.1 se mai servirà.

## 17. Cosa si riusa dal vecchio progetto (taaclife/)

Molto poco di codice diretto (Python ≠ TypeScript), ma molto di
**conoscenza accumulata**:

- **Seed alimenti CSV** (`seed/foods.csv`): si converte in JSON
  embeddable. ~130 alimenti curati con convenzione da crudo già
  applicata e label porzioni etichettate. Riuso al 100% dei dati.
- **System prompt del coach** (`core/coach.py:SYSTEM_PROMPT`): è testo,
  si traduce in `coach/system_prompt.ts`. Da adattare ai nuovi tool
  e al nuovo contesto.
- **Formule del motore** (`core/nutrition.py`): le costanti
  (ACTIVITY_FACTORS, GOAL_FACTORS) e la logica di Mifflin/TDEE sono
  ~30 righe di matematica, da riscrivere in TS in mezz'ora.
- **Lista dei tool** (`core/coach_tools.py`): la struttura dei 4 tool
  esistenti (search_food, add_diary_entry, get_*) è un buon punto
  di partenza, da estendere coi nuovi (verify_path, save_path,
  update_profile, ecc.).
- **Disclaimer testo** (`app/disclaimer.py`): è italiano puro,
  riusabile.

Tutto il resto del codice Python (auth, FastAPI, Alembic, Docker,
build.sh) **non serve più** per questo prodotto.

## 18. CLAUDE.md (vincoli duri da fissare)

Vedi `CLAUDE.md` separato. Sintesi:

1. **Niente backend, niente fornitori**: i dati e la chiave restano nel
   browser dell'utente. Mai inviare la chiave a servizi terzi (eccetto
   `api.anthropic.com` direttamente).
2. **L'LLM propone, il motore verifica**: i numeri sui percorsi
   passano sempre da `engine/nutrition.ts`. L'LLM non li inventa.
3. **Scritture solo dietro conferma**: ogni tool che scrive nel DB
   richiede `confirmed=true`, che si ottiene solo dopo un'esplicita
   conferma dell'utente nel turno precedente.
4. **Convenzione alimenti da crudo**: invariata.
5. **Tono non giudicante, default `feel_good`**: invariato.
6. **Niente leak della chiave nei log / errori**: ogni handler di
   eccezione che arriva dal SDK deve produrre messaggi neutri.
7. **TypeScript strict mode**: niente `any` se non strettamente
   necessario e commentato.
8. **`engine/nutrition.ts` puro**: niente import di SQLite o LLM.
   Riceve dati come argomenti, ritorna risultati. Testabile in
   isolamento.

## 19. Deploy

`netlify deploy --prod` (o git push su main, con auto-deploy collegato).
Build di SvelteKit produce `build/` con index.html, assets, service
worker, manifest. Netlify serve il tutto su HTTPS con dominio
gratuito `*.netlify.app` o custom domain.

Niente segreti nel deploy: l'app è completamente pubblica come codice
e come bundle. Le chiavi sono solo nei browser degli utenti.

## 20. Open questions (da chiudere prima di partire)

Nessuna bloccante. Le tre scelte rimaste, ognuna risolvibile in fase:

1. **Nome dell'app**: NutriCoach va bene anche per v3? Cambiamo? La
   v1 è già pubblica su GitHub come `taaclife`, magari il nome del
   prodotto e il nome del repo possono divergere.
2. **Modello Claude di default**: haiku per economicità (utente paga)
   o sonnet per qualità. Configurabile, ma il default conta.
3. **Sponsor del seed**: si tiene il seed CREA originale o si fa una
   pulizia/espansione prima della Fase 3? Si può rimandare a una
   "Fase 8.5: estensione seed" dopo aver visto come gira con 130
   alimenti.
