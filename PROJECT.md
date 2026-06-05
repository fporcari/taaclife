# Proto-progetto: NutriCoach (nome di lavoro)

Documento di partenza per implementazione con Claude Code. Descrive cosa
costruire, con quali vincoli e in quale ordine. Non è codice: è il contratto
che il codice deve rispettare.

---

## 1. Obiettivo in una frase

Web app multi-utente che tiene un diario alimentare basato su un database di
alimenti, calcola in modo deterministico fabbisogni e bilanci, e usa un LLM
(Claude API) come interfaccia conversazionale per spiegare, suggerire e
rispondere in linguaggio naturale, senza mai inventare numeri.

## 2. Principio architetturale non negoziabile

**I numeri li fa il motore di calcolo. L'LLM parla.**

- Calorie, macro, fabbisogno, bilancio giornaliero: calcolati da codice Python
  deterministico e testabile. Mai chiesti all'LLM.
- L'LLM riceve i numeri già calcolati come contesto e li spiega, commenta,
  suggerisce. Non somma, non stima porzioni a mente, non deduce calorie.
- Ogni risposta dell'LLM che contiene un numero deve poter essere ricondotta a
  un valore prodotto dal motore. Se il dato non c'è, l'LLM lo dice, non lo
  inventa.

Questa separazione è la ragione per cui l'app è affidabile invece di essere un
chatbot che allucina. Va difesa in ogni fase.

## 3. Disclaimer obbligatorio

L'app non è un dispositivo medico e non sostituisce un nutrizionista o un
medico. Va mostrato un disclaimer all'onboarding e reso accessibile sempre.
Nessun linguaggio diagnostico o prescrittivo. Tono di supporto, non di giudizio:
niente "cibi buoni/cattivi", niente sensi di colpa, niente celebrazione del
deficit calorico fine a se stesso.

## 4. Stack tecnico

| Livello   | Scelta                                              |
|-----------|-----------------------------------------------------|
| Backend   | FastAPI (Python 3.12)                               |
| DB        | SQLite (file su volume), WAL mode attivo            |
| ORM       | SQLAlchemy 2.x + Alembic per le migrazioni          |
| Auth      | JWT (access + refresh), password con bcrypt/argon2  |
| LLM       | Anthropic API (Claude), SDK ufficiale               |
| Frontend  | da decidere in fase 2 (vedi §11). API-first.        |
| Container | Docker (immagine singola)                           |
| Hosting   | macchina personale del committente (self-host)      |
| Test      | pytest                                              |

Motivazione: side project leggero. SQLite è adatto al profilo d'uso (diario
alimentare: molte letture, scritture sporadiche e singole). Multi-utente qui
significa account con dati separati, non alta concorrenza in scrittura, quindi
SQLite regge senza problemi. WAL mode permette letture e scritture concorrenti.
FastAPI dà OpenAPI gratis e tipizzazione Pydantic, utile a tenere onesto il
confine tra motore di calcolo e LLM.

Grazie a SQLAlchemy il codice resta indipendente dal motore: se un domani serve
più concorrenza (molti writer simultanei, o API scalata su più processi), si
migra a Postgres cambiando solo la `DATABASE_URL`, senza riscrivere le query.

## 5. Modello dati (prima bozza)

```
users
  id (uuid, pk)
  email (unique)
  password_hash
  created_at

profiles                      # dati per il calcolo del fabbisogno
  user_id (fk users, unique)
  sex            # 'F' | 'M' | 'other' -> per Mifflin si usa F/M, gestire 'other'
  birth_date
  height_cm
  activity_level # enum: sedentary, light, moderate, active, very_active
  goal           # enum: maintain, gentle_loss, gentle_gain  (vedi nota etica §7)
  updated_at

weight_logs
  id (pk)
  user_id (fk)
  measured_at (date)
  weight_kg

foods                         # il database alimenti (vedi §6)
  id (pk)
  name
  category
  kcal_100g
  protein_100g
  carbs_100g
  fat_100g
  fiber_100g (nullable)
  source         # 'CREA' | 'user' | 'off'
  is_public (bool)            # alimenti di sistema vs creati dall'utente
  created_by (fk users, nullable)

portions                      # porzioni di riferimento per alimento
  id (pk)
  food_id (fk)
  label          # es. "un piatto", "una fetta"
  grams

diary_entries
  id (pk)
  user_id (fk)
  consumed_at (timestamp)
  meal           # enum: breakfast, lunch, dinner, snack
  food_id (fk)
  grams          # quantità effettiva consumata
  -- kcal/macro NON si salvano qui: si calcolano da food + grams.
  -- (eventuale cache denormalizzata solo se serve per performance)

preferences                   # i "gusti" dell'app precedente, se si vogliono tenere
  user_id (fk)
  liked   (text[] o tabella a parte)
  avoided (text[])

chat_messages                 # storico conversazione con l'LLM
  id (pk)
  user_id (fk)
  role           # 'user' | 'assistant'
  content
  created_at
```

Nota: tenere `diary_entries` snello e calcolare i totali al volo o in una vista.
Denormalizzare solo se un profiling mostra che serve.

## 6. Database alimenti

### Fonte
Tabelle di composizione degli alimenti **CREA** (ex-INRAN), valori per 100 g di
parte edibile. Sono lo standard italiano di riferimento. In alternativa o in
aggiunta, **Open Food Facts** per prodotti confezionati (ha API e dump, licenza
ODbL — verificare requisiti di attribuzione prima di redistribuire).

### Strategia
- Partire con un seed curato di ~80-120 alimenti italiani comuni (pasta, riso,
  pane, pollo, uova, legumi, verdure, frutta, latticini, oli) come file
  `seed/foods.csv` versionato nel repo.
- I valori per 100 g sono dati di composizione di pubblico dominio; la CSV di
  seed va comunque corredata da una nota sulla fonte.
- Migrazione Alembic che crea le tabelle + script di seed idempotente che
  popola `foods` e `portions` solo se vuote.
- Lasciare predisposto un importer per dump CREA/OFF più ampi in fase 2.

### Attenzione (mettere come commento nel seed)
- Valori "crudo" vs "cotto" sono diversi: la pasta cruda ~350 kcal/100g, da
  cotta pesa ~2x con meno densità calorica. Decidere una convenzione (consiglio:
  registrare il peso da crudo dove ha senso, con porzioni etichettate) e
  documentarla, altrimenti i totali sono fuori di un fattore 2.

## 7. Motore di calcolo (deterministico)

Modulo `core/nutrition.py`, puro, senza dipendenze da DB o LLM, interamente
testato con pytest.

### Fabbisogno energetico
- **BMR** con **Mifflin-St Jeor**:
  - Uomo: `10*kg + 6.25*cm - 5*età + 5`
  - Donna: `10*kg + 6.25*cm - 5*età - 161`
- **TDEE** = BMR × fattore attività:
  - sedentary 1.2, light 1.375, moderate 1.55, active 1.725, very_active 1.9
- Obiettivo: maintain = TDEE; gentle_loss = TDEE − ~10-15%;
  gentle_gain = TDEE + ~10%.

### Nota etica sul "goal" (importante, leggere)
Il brief originale di questo progetto era "non deve dimagrire, vuole sentirsi
bene". Tenere quindi:
- Default su `maintain`, non su perdita di peso.
- Niente obiettivi aggressivi: il deficit massimo selezionabile resta moderato.
- Nessuna gamification del deficit (niente streak di "giorni sotto soglia").
- Possibilità di nascondere del tutto le calorie e usare l'app solo come diario
  + dialogo, per chi conta le calorie sta peggio.
Questa non è una richiesta cosmetica: è un requisito di prodotto.

### Bilancio giornaliero
- Dato un giorno: somma kcal e macro dalle `diary_entries` (food × grams / 100).
- Confronto con il fabbisogno: produce un oggetto `DailyBalance` con totali,
  target, differenza, ripartizione macro. Niente giudizi nel dato grezzo.

### Test minimi
- Mifflin uomo/donna con casi noti.
- TDEE per ogni livello attività.
- Somma diario con porzioni e grammature varie.
- Edge case: profilo incompleto, età mancante, peso assente.

## 8. Layer LLM (il "nutrizionista che dialoga")

Modulo `core/coach.py`. È la chat: l'utente scrive in linguaggio naturale, e
Claude risponde **sui dati reali di quell'utente**, non in astratto.

### Chiave Claude
Una sola chiave di sistema, in `.env` come `ANTHROPIC_API_KEY`, fornita
dall'amministratore (il committente). Gli utenti non inseriscono chiavi: usano
tutti la chiave dell'istanza. Conseguenze da gestire:
- La chiave sta **solo nel backend**, mai inviata al frontend né visibile via
  API. Il client parla con `/coach/chat`, non con Anthropic.
- Il costo delle chiamate è a carico di chi ospita l'istanza. Quindi **rate
  limiting per utente** non è opzionale: serve a non far esplodere la spesa.
- Se la chiave manca o è invalida, la chat si disattiva con un messaggio
  chiaro ("coach non disponibile"), il resto dell'app (diario, calcoli)
  continua a funzionare. Il coach è un di più, non una dipendenza dura.

### Come il contesto arriva alla chat (il punto cruciale)
A **ogni** messaggio dell'utente, prima di chiamare Claude, il backend assembla
un contesto fresco dai dati reali:
1. Profilo dell'utente (età, sesso per il calcolo, altezza, attività, goal).
2. Fabbisogno calcolato dal motore (`/summary/needs`).
3. Bilancio di oggi e, se rilevante, riepilogo della settimana
   (`DailyBalance` già calcolati dal motore — **non ricalcolati dall'LLM**).
4. Ultime N voci di diario.
5. Preferenze: cibi graditi e da evitare.
6. Storico recente della conversazione (`chat_messages`), troncato a una
   finestra ragionevole per non gonfiare i token.

Tutto questo va nel contesto come **dati strutturati (JSON)**, accompagnato dal
system prompt. La differenza tra una chat utile e un chatbot generico è proprio
questa: Claude non indovina, legge i numeri che il motore ha già prodotto.

### System prompt (il contratto)
Deve:
- dichiarare il ruolo (assistente di supporto sull'alimentazione, **non
  medico**, non sostituisce un professionista),
- **vietare esplicitamente di calcolare o stimare numeri**: usa solo i valori
  presenti nel contesto; se un dato non c'è, dice "non ho questo dato",
- imporre tono non giudicante: niente cibi "buoni/cattivi", niente colpa,
  coerente col requisito etico del §7,
- ricordare di proporre solo tra i cibi graditi / nel database, senza inventare
  calorie di piatti che non ci sono.

### Flusso di una richiesta
```
utente scrive su /coach/chat  ->  backend:
  1. carica dati utente dal motore + DB
  2. costruisce contesto JSON + system prompt
  3. chiama Anthropic API con la chiave di sistema
  4. salva domanda e risposta in chat_messages
  5. restituisce la risposta al client
```

### Esempi di interazione
- "Cosa potrei mangiare stasera?" → Claude vede preferenze + bilancio residuo
  del giorno e propone tra i cibi graditi, senza inventare calorie di piatti non
  in database.
- "Come sto andando questa settimana?" → Claude riceve i 7 `DailyBalance` già
  calcolati e li racconta.
- "Perché mi sento gonfia?" → risponde con supporto, senza diagnosi, e se serve
  rimanda a un professionista.

### Function calling (fase 2, consigliato)
Invece di iniettare tutto il contesto a ogni messaggio, esporre tool a Claude:
`get_daily_balance(date)`, `search_food(query)`, `get_weekly_summary()`,
`add_diary_entry(...)`. Così Claude chiede i numeri al motore invece di
riceverli alla cieca, riduce i token, e può anche agire (aggiungere voci di
diario) su conferma esplicita dell'utente. Tenere ogni `add_*` dietro conferma.

### Sicurezza
- La API key Anthropic sta solo nel backend (`.env`), mai esposta al client.
- Rate limiting sulle chiamate LLM per utente (anche per contenere la spesa,
  vedi sopra).
- Lo storico chat è scoped sull'utente: nessuno vede le conversazioni altrui.

## 9. API (FastAPI) — superficie minima

```
POST /auth/register
POST /auth/login            -> access + refresh token
POST /auth/refresh

GET  /profile
PUT  /profile

GET  /foods?q=&category=    -> ricerca nel database
POST /foods                 -> alimento personale dell'utente

GET  /diary?date=
POST /diary                 -> aggiunge voce
DELETE /diary/{id}

GET  /summary/day?date=     -> DailyBalance dal motore
GET  /summary/week?from=
GET  /summary/needs         -> fabbisogno calcolato dal profilo

POST /weights
GET  /weights

POST /coach/chat            -> {message} -> risposta LLM con contesto
GET  /coach/history
```

Tutte le rotte dati sono scoped sull'utente autenticato. Mai fidarsi di uno
user_id passato dal client: prenderlo dal token.

## 10. Docker

**Immagine singola**, niente Postgres da orchestrare.

- Un Dockerfile che builda l'app FastAPI.
- Il database SQLite vive in un file su un **volume persistente** montato (es.
  `/data/nutricoach.db`), così sopravvive a riavvii e aggiornamenti
  dell'immagine.
- Entrypoint: applica le migrazioni Alembic + esegue il seed idempotente del
  database alimenti, poi avvia uvicorn.
- Abilitare **WAL mode** all'avvio (`PRAGMA journal_mode=WAL;`) per letture e
  scritture concorrenti.

Un `docker-compose.yml` resta comodo anche con un solo servizio, solo per
fissare in un posto la mappatura del volume, le porte e le variabili d'ambiente.
Ma è opzionale: `docker run` con `-v` per il volume e `--env-file` basta.

`.env` (non committato): `DATABASE_URL=sqlite:////data/nutricoach.db`,
`ANTHROPIC_API_KEY`, `JWT_SECRET`, `JWT_REFRESH_SECRET`. Fornire `.env.example`
committato senza valori reali.

Obiettivo dichiarato: **una sola immagine Docker che si avvia, si collega al db
alimenti (già popolato dal seed) e offre il coach**, senza passi manuali.

### Hosting
Self-host su una macchina personale del committente. Nessuna dipendenza da
piattaforme cloud o da fasce gratuite. Backup = copia del file `.db` dal volume.

## 11. Frontend (fase 2)

API-first: il backend è completo e testabile via OpenAPI prima di toccare la UI.
Per la UI, opzioni in ordine di leggerezza: HTML+HTMX, oppure un piccolo SPA
(React/Svelte). Decidere quando il backend è solido. Riusare i concetti della
UI già prototipata: diario, gusti, andamento peso, chat col coach.

## 12. Ordine di lavoro per Claude Code

Fasi pensate per essere committabili e verificabili una alla volta.

1. **Scaffold**: repo, FastAPI hello-world, Dockerfile, SQLite su volume con
   WAL, Alembic inizializzato, pytest che gira a vuoto.
2. **Auth**: users, register/login/refresh, JWT, test.
3. **Modello dati + migrazioni**: tutte le tabelle di §5.
4. **Database alimenti**: CSV di seed (~100 alimenti CREA), script di seed
   idempotente, rotte `/foods`.
5. **Motore di calcolo**: `core/nutrition.py` + test completi (Mifflin, TDEE,
   bilanci). Nessun DB qui dentro.
6. **Diario + summary**: rotte diario, `/summary/*` che usano il motore.
7. **Pesi + profilo**: rotte e calcolo fabbisogno.
8. **Coach LLM (chat)**: `core/coach.py`, costruzione del contesto da motore+DB
   a ogni messaggio, system prompt col contratto di §8, rotta `/coach/chat` +
   `/coach/history`. Chiave di sistema da `.env`; se assente, chat disattivata
   con messaggio chiaro e resto dell'app funzionante. Prima versione: contesto
   iniettato.
9. **Function calling** (opzionale): tool per il coach come da §8.
10. **Hardening**: rate limiting, validazioni, disclaimer, gestione errori LLM.
11. **Frontend**.

## 13. CLAUDE.md (da creare nel repo)

Il file `CLAUDE.md` è fornito già pronto insieme a questo documento. Ribadisce a
ogni sessione di Claude Code i vincoli duri:
- il principio "i numeri li fa il motore, l'LLM parla" (§2),
- il requisito etico sul goal e sul tono (§7),
- la convenzione alimenti **da crudo** (§14),
- "mai esporre la API key, mai fidarsi dello user_id del client",
- committare a ogni fase, non proseguire se i test non passano.

## 14. Decisioni di progetto (chiuse)

Queste erano le domande aperte. Sono chiuse con default ragionevoli; lo script
di Fase 0 (§15) le ripropone all'utente che può confermare o cambiare.

- **Nome app**: default `NutriCoach`. Modificabile in Fase 0.
- **Convenzione crudo/cotto**: gli alimenti nel database sono registrati **da
  crudo / a peso secco** (es. pasta 100g = ~350 kcal, da pesare prima della
  cottura). Le porzioni in tabella `portions` sono etichettate di conseguenza
  ("80 g di pasta cruda"). Questa convenzione va scritta nel `CLAUDE.md` e in un
  commento del CSV di seed, perché sbagliarla raddoppia i totali.
- **Modello Claude per il coach**: default `claude-haiku-4-5-20251001` (veloce,
  economico, adatto a una chat che spiega numeri già calcolati). Alternativa
  `claude-sonnet-4-6` se si vuole più qualità di dialogo. Configurabile in
  Fase 0 e via `.env` (`COACH_MODEL`).
- **Sesso biologico nel calcolo Mifflin**: il profilo separa l'identità dal
  parametro di calcolo. Campo `calc_basis` ('F'|'M') usato solo per la formula,
  distinto da come l'utente si identifica. Per profili che non vogliono
  specificarlo, default a una media delle due formule, dichiarando l'assunzione.
- **Open Food Facts**: **no in v1**. Si parte col solo seed CREA. L'importer OFF
  resta predisposto per la v2, con la sua attribuzione ODbL da gestire allora.

## 15. Fase 0 — Script di build interattivo (`build.sh`)

Lo scopo dichiarato dal committente: **poter generare immagini Docker diverse
cambiando parametri in modo facile, senza dover seguire il progetto**. La Fase 0
serve a questo.

### Cosa fa
Uno script `build.sh` che gira **sulla macchina di sviluppo** (non sul server),
fa alcune domande, e in fondo produce un'immagine Docker già configurata con le
**scelte di progetto**. Concentra tutte le decisioni in un unico momento
all'avvio, così il resto del lavoro procede senza interruzioni.

### Domande (con default — invio = accetta il default)
1. Nome dell'app / tag immagine [default: `nutricoach`]
2. Convenzione alimenti: crudo / cotto [default: crudo]
3. Modello coach: haiku / sonnet [default: haiku]
4. Includere Open Food Facts? s/n [default: n]
5. Lingua dei contenuti e dei seed [default: it]

Ogni domanda ha un default sensato: se l'utente preme invio senza rispondere, lo
script procede da solo. Si può anche lanciare `./build.sh --yes` per accettare
tutti i default senza domande (utile per ri-build automatici).

### Cosa NON chiede (importante)
Lo script **non** chiede né incorpora segreti: niente API key, niente JWT
secret. Quelli stanno nel `.env` al momento del deploy (§16). Motivo: un'immagine
con dentro la chiave è un rischio se l'immagine viene spostata o condivisa.
L'immagine deve restare "pulita" e riutilizzabile; i segreti si iniettano
all'avvio. (Se l'uso è strettamente personale su una sola macchina, incorporare
la chiave è una scorciatoia possibile ma sconsigliata di default.)

### Come funziona
- Le risposte vengono scritte in un file `build.config` (committabile, senza
  segreti) e passate come build-args / variabili al Dockerfile.
- Le scelte che plasmano i dati (convenzione alimenti, lingua, OFF sì/no)
  determinano quale seed viene incluso nell'immagine.
- La scelta del modello finisce come default in `COACH_MODEL`, comunque
  sovrascrivibile dal `.env` a runtime.
- Output finale: `docker build` eseguito, immagine taggata col nome scelto,
  pronta da spostare sul server.

### Ordine di lavoro
La Fase 0 va implementata **per ultima**, quando l'app è completa e
containerizzabile, ma documentata qui perché definisce l'interfaccia di build.

## 16. Deploy su server (Hetzner)

Il deploy è documentato in dettaglio nel file separato `DEPLOY-HETZNER.md`.
In sintesi: l'immagine costruita in Fase 0 si trasferisce sul server Hetzner, si
crea un `.env` coi segreti (API key, JWT secret), si avvia il container con un
volume per il file SQLite, e si mette un reverse proxy (Caddy) davanti per HTTPS
automatico sul dominio. I segreti vivono solo nel `.env` sul server, mai
nell'immagine.
