# tasks/todo.md

Memoria di lavoro fase per fase. Si spunta man mano. Una sessione interrotta
riparte da qui.

---

## Fase 1 — Scaffold

Obiettivo (da PROJECT.md §12.1): repo + FastAPI hello-world + Dockerfile +
SQLite su volume con WAL + Alembic inizializzato + pytest che gira a vuoto.
Fase completa quando `pytest` passa e tutto è committato.

### Decisioni di fase (più semplice possibile, da CLAUDE.md "Metodo di lavoro")

- Layout: `app/` (FastAPI, settings, db), `core/` (motore puro, vuoto in F1),
  `tests/`, `alembic/`, `seed/` (vuota in F1).
- Gestione dipendenze: `requirements.txt` + `requirements-dev.txt` (no Poetry).
- Python: `python:3.12-slim` in Docker (coerente con §4 di PROJECT.md).
- WAL + foreign keys: applicati via SQLAlchemy event listener su ogni `connect`.
- Settings da env con `pydantic-settings` (`DATABASE_URL`, `COACH_MODEL`,
  `ANTHROPIC_API_KEY`, `JWT_SECRET`, `JWT_REFRESH_SECRET`). In F1 sono solo letti,
  non usati tutti.
- Alembic inizializzato ma senza revisioni (quelle arrivano in Fase 3).
- Entrypoint container: `alembic upgrade head` (no-op ora) + `uvicorn`.

### Checklist

- [x] `git init` + branch `main` + primo commit dei documenti esistenti.
- [x] `.gitignore` (venv, `__pycache__`, `.env`, `*.db`, `.pytest_cache`, ecc.).
- [x] `pyproject.toml` minimo (solo `[tool.pytest.ini_options]`).
- [x] `requirements.txt`: fastapi, uvicorn[standard], sqlalchemy, alembic,
      pydantic, pydantic-settings.
- [x] `requirements-dev.txt`: pytest, httpx (per TestClient).
- [x] `app/__init__.py`
- [x] `app/settings.py`: `Settings` con pydantic-settings, legge `.env`.
- [x] `app/db.py`: engine SQLAlchemy + event listener WAL/foreign_keys +
      `SessionLocal` + `Base = DeclarativeBase`.
- [x] `app/main.py`: `create_app()` + `app = create_app()`, rotta `GET /health`
      che ritorna `{"status": "ok"}`.
- [x] `core/__init__.py` (vuoto, segnaposto per Fase 5).
- [x] `alembic.ini` + `alembic/env.py` configurati per leggere `DATABASE_URL`
      dalle settings (non hardcoded).
- [x] `alembic/versions/` vuota (nessuna migrazione in F1).
- [x] `Dockerfile`: `python:3.12-slim`, copia codice, `pip install`, espone
      8000, entrypoint che fa `alembic upgrade head` + `uvicorn`.
- [x] `entrypoint.sh` separato, eseguibile.
- [x] `.dockerignore` per non infilare `__pycache__`, `.git`, venv, `.env`,
      `*.db` nell'immagine.
- [x] `tests/__init__.py` + `tests/conftest.py` (TestClient su `create_app()`).
- [x] `tests/test_health.py`: `GET /health` → 200 e body atteso.
- [x] `tests/test_db.py`: WAL e foreign_keys attivi su SQLite su file
      (`tmp_path`); su `:memory:` WAL non si applica (journal_mode=`memory`).
- [x] `pytest` verde in locale (3 passed).
- [x] Commit unico di fine fase con messaggio chiaro che cita la Fase 1.
- [x] Spuntare tutto qui sopra.

### Verifica end-to-end (manuale, oltre a pytest)

- `uvicorn app.main:app --reload` parte senza errori, `GET /health` → 200.
- `docker build -t nutricoach:dev .` riesce (build only, non eseguo ora).

### Fuori scope (in fasi successive)

- Auth, modello dati esteso, migrazioni reali, seed alimenti, motore di
  calcolo, coach, frontend, `build.sh`.

---

## Fase 2 — Auth

Obiettivo (PROJECT.md §9 e §12.2): tabella `users`, `POST /auth/register`,
`POST /auth/login`, `POST /auth/refresh` con JWT access+refresh, hashing
password con argon2. Ogni rotta protetta ricava l'utente dal token (mai
da input del client). Test su registrazione, login, refresh, accesso negato
senza token.

### Decisioni di fase

- Hashing: `argon2-cffi` (default OWASP, no toolchain nativa pesante).
- JWT: `pyjwt`, algoritmo `HS256`. Access TTL 15 min, refresh TTL 7 giorni.
- Token discriminato da claim `type` (`access` | `refresh`): rotte di refresh
  accettano solo `type=refresh`, dipendenze di accesso solo `type=access`.
- `User.id` come UUID stringa (TEXT in SQLite) generato a livello applicativo.
- Migrazione Alembic `0001_create_users.py` (prima revisione del progetto).
  Le altre tabelle di PROJECT.md §5 arrivano in Fase 3.
- Rotta probe protetta `GET /auth/me` per testare il vincolo "utente dal token".
- Test su DB SQLite file temporaneo (`tmp_path`) con override della dipendenza
  `get_db`. Schema creato con `Base.metadata.create_all` nei test (no Alembic
  nei test, ma la migrazione resta verificata a parte).
- Niente refresh rotation né blacklist in F2: hardening è Fase 10.

### Vincoli duri rispettati

- `JWT_SECRET`/`JWT_REFRESH_SECRET` solo da `.env` via settings (mai hardcoded).
- `ANTHROPIC_API_KEY` non tocca questa fase.
- `user_id` ricavato sempre dal token, mai da body/query/path.
- Tono non giudicante: gli errori parlano di "credenziali non valide", senza
  rivelare se è la mail o la password (niente shaming né enumeration).

### Checklist

- [x] `app/security.py`: `hash_password`, `verify_password` (argon2);
      `create_access_token`, `create_refresh_token`, `decode_token` (PyJWT,
      validazione `type`, `sub`, `exp`).
- [x] `app/models.py`: `User` (id TEXT pk, email unique, password_hash,
      created_at). `Base` riusato da `app.db`.
- [x] `app/schemas/__init__.py` + `app/schemas/auth.py`:
      `RegisterIn`, `LoginIn`, `RefreshIn`, `TokenPair`, `UserOut`.
- [x] `app/deps.py`: `get_db()` generator (yield session, close finally) +
      `get_current_user(...)` che decodifica access token e fa lookup.
- [x] `app/auth/__init__.py` + `app/auth/router.py`:
      register / login / refresh / me.
- [x] `app/main.py`: include router auth.
- [x] `alembic/versions/0001_create_users.py`: prima revisione, crea `users`.
- [x] `alembic/env.py`: importa `app.models` per popolare `Base.metadata`.
- [x] `requirements.txt`: aggiunte `argon2-cffi`, `PyJWT`, `email-validator`.
- [x] `tests/conftest.py`: fixture `db_engine` (engine SQLite su `tmp_path`
      con `dispose()` in teardown), `db_session`, `client` con override di
      `get_db`. Settings di test via env (`JWT_SECRET`/`JWT_REFRESH_SECRET`).
- [x] `tests/test_auth.py`: registrazione (OK / duplicato / case-insensitive
      / password debole), login (OK / password errata / email inesistente
      stesso 401 → no enumeration), refresh (OK / rifiuta access token),
      `/auth/me` (no token → 401 / access valido → 200 / refresh → 401 /
      scaduto → 401 / tampered → 401).
- [x] `tests/test_db.py`: aggiunto `engine.dispose()` per evitare
      `ResourceWarning` con `filterwarnings = ["error"]`.
- [x] `pytest` verde: 17 passed.
- [x] Migrazione Alembic verificata: upgrade crea `users`, downgrade la
      rimuove.
- [x] Commit di fine fase citando la Fase 2.
- [x] Spuntare tutto qui sopra.

### Verifica end-to-end (manuale, oltre a pytest)

- Migrazione: `DATABASE_URL=sqlite:///./_check.db alembic upgrade head` crea
  la tabella `users`; `alembic downgrade base` la rimuove (verificato).

---

## Fase 3 — Modello dati

Obiettivo (PROJECT.md §5 e §12.3): tutte le tabelle del modello dati con
migrazioni Alembic. `diary_entries` NON salva kcal/macro (vincolo duro §2/§5).
Test che migrazioni applicano e rollback è pulito.

### Decisioni di fase

- Una sola revisione `0002_create_core_schema` con tutte le tabelle (più
  semplice da rollbackare in blocco; il goal chiede "rollback puliti").
- PK intere autoincrement su tutte le tabelle salvo `users` (UUID stringa,
  già esistente da F2).
- Enum gestiti come `String` con `CHECK` constraint esplicito; lato Python
  `enum.StrEnum`.
- `profiles.calc_basis` ('F'|'M'|null) separato da `profiles.sex`
  ('F'|'M'|'other'|null), come §14: identità ≠ parametro di calcolo.
- `diary_entries` minimale: `user_id, consumed_at, meal, food_id, grams`.
  Nessuna colonna `kcal_*`, `protein_*`, ecc. (i numeri li fa il motore).
- `preferences`: SQLite non ha array → tabella `preference_items(user_id,
  kind, value)` con `kind in {'liked','avoided'}`. Portabile a Postgres.
- Timestamp `DateTime(timezone=True)` ovunque; `measured_at` come `Date`.
- ON DELETE: CASCADE su tutto ciò che è "di proprietà" dell'utente; SET NULL
  su `foods.created_by` (gli alimenti personali sopravvivono all'utente);
  RESTRICT su `diary_entries.food_id` (non si cancella un food con voci).
- CHECK `grams > 0` su `diary_entries` e `portions`.
- `foods`: indice su `name` per la ricerca della Fase 4; `is_public` NOT NULL.

### Vincoli duri rispettati

- `diary_entries` snello, niente kcal/macro denormalizzati: test apposito
  che ispeziona la tabella e fallisce se compaiono colonne `kcal*/macro*`.
- Alimenti da crudo: la convenzione vive nei commenti del seed (Fase 4),
  ma `foods.kcal_100g` ecc. sono "per 100 g di alimento crudo".
- Nessuna API key nel codice (nessuna nuova rotta che chiama l'LLM in F3).

### Checklist

- [x] `app/models.py`: aggiunti `Profile`, `WeightLog`, `Food`, `Portion`,
      `DiaryEntry`, `PreferenceItem`, `ChatMessage` + tutti gli enum.
- [x] `alembic/versions/0002_create_core_schema.py`: crea tutte le tabelle
      con FK, CHECK, indici. `downgrade()` rimuove tutto in ordine inverso.
- [x] Bug fix `alembic/env.py`: non sovrascrivere `sqlalchemy.url` se già
      impostata (era il motivo per cui le migrazioni programmatiche
      finivano sul file di default `./nutricoach.db`).
- [x] `tests/test_migrations.py`: upgrade head, downgrade base, ispezione
      `diary_entries` per assenza di colonne kcal/macro.
- [x] `tests/test_models.py`: User+Profile 1-to-1, CHECK enum, CHECK
      `grams>0`, CHECK altezza, CASCADE su utente, RESTRICT su food,
      unique weight per giorno, unique preference triple.
- [x] `pytest` verde: 29 passed.
- [x] CLI end-to-end: `alembic upgrade head` crea 8 tabelle, `downgrade base`
      lascia solo `alembic_version`.
- [x] Commit di fine fase citando la Fase 3.

### Verifica end-to-end (manuale)

- `alembic upgrade head` su `_check.db` crea 8 tabelle (users +
  profiles + weight_logs + foods + portions + diary_entries +
  preference_items + chat_messages) + `alembic_version`. (verificato)
- `alembic downgrade base` lascia solo `alembic_version`. (verificato)

---

## Fase 4 — Database alimenti

Obiettivo (PROJECT.md §6 e §12.4): CSV di seed di ~100 alimenti italiani da
CREA, convenzione DA CRUDO; script di seed idempotente; rotte `GET /foods`
con ricerca + filtro categoria e `POST /foods` per alimenti personali.

### Decisioni di fase

- File `seed/foods.csv` con header commenti `#` (skippati dal reader). Header
  CSV vero: `name,category,kcal_100g,protein_100g,carbs_100g,fat_100g,
  fiber_100g,portions` dove `portions` è una stringa
  `label1:grams1|label2:grams2` (semplice, niente JSON innestato nella CSV).
- Convenzione **DA CRUDO / peso secco** documentata in tre punti:
  1. commento `#` in testa al CSV, 2. docstring di `app/seed.py`,
  3. label delle porzioni quando ambigue (es. "80 g (pasta cruda)").
- Script di seed: `app/seed.py` con `seed_foods(db, csv_path) -> int`.
  Idempotente: se `foods` non è vuoto ritorna 0. Eseguibile come
  `python -m app.seed`.
- Aggancio in `entrypoint.sh`: `alembic upgrade head` → seed → uvicorn.
- Rotta `GET /foods`: protetta JWT; visibilità = `is_public=True OR
  created_by=user.id` (mai esposti alimenti personali altrui — vincolo
  CLAUDE.md §3 "ogni rotta scoped sull'utente del token"); query params
  `q` (LIKE case-insensitive su `name`), `category` (match esatto),
  `limit` (default 50, max 200), `offset` (default 0).
- Rotta `POST /foods`: protetta JWT; crea food personale con `source='user'`,
  `is_public=False`, `created_by=user.id`. Accetta porzioni opzionali.
- Niente `GET /foods/{id}` in F4 (non richiesto dal goal; rinviato a F6).
- Categoria: stringa libera (validata solo per lunghezza). La lista di
  categorie effettivamente in uso emerge dal seed.

### Vincoli duri rispettati

- Numeri da fonte CREA, valori per 100 g **da crudo**: commento esplicito
  nel CSV e nelle docstring.
- `POST /foods`: `created_by` viene **sempre** preso da `current_user.id`,
  mai dal body (anche se il client lo manda, viene ignorato).
- `GET /foods` non espone mai alimenti personali di altri utenti.
- Niente API key LLM in F4.

### Checklist

- [x] `seed/foods.csv` con 133 alimenti italiani comuni in 13 categorie
      (cereali, legumi, carni, salumi, pesce, uova, latticini, oli e
      grassi, frutta, verdure, frutta secca, dolci e zuccheri, bevande).
      Commenti `#` in testa: fonte CREA, convenzione DA CRUDO.
- [x] `app/seed.py`: `load_foods_from_csv()`, `seed_foods(db)` idempotente,
      `main()` per `python -m app.seed`. Docstring che ribadisce DA CRUDO.
- [x] `app/schemas/foods.py`: `PortionIn/Out`, `FoodOut`, `FoodCreateIn`
      (no `created_by`/`source`/`is_public` esposti in input).
- [x] `app/foods/router.py`: `GET /foods` scoped sull'utente,
      `POST /foods` con `source/is_public/created_by` impostati dal server.
- [x] `app/main.py`: include router foods.
- [x] `entrypoint.sh`: `python -m app.seed` dopo `alembic upgrade head`.
- [x] `Dockerfile`: copia `seed/` nell'immagine.
- [x] `tests/test_seed.py`: caricamento CSV, popolamento, idempotenza,
      attributi (source CREA, is_public, no owner), label "crud" presente
      sugli alimenti che lo richiedono.
- [x] `tests/test_foods.py`: 401 senza token, ricerca case-insensitive,
      filtro categoria, paginazione, cap limit, creazione personale,
      validazione kcal>=0, scoping (Alice vs Bob), tentativo spoofing
      `created_by` ignorato, food senza porzioni.
- [x] `pytest` verde: 47 passed.
- [x] End-to-end CLI: 133 alimenti + 140 porzioni seedati; secondo run
      idempotente (skip).
- [x] Commit di fine fase citando la Fase 4.

### Verifica end-to-end (manuale)

- `python -m app.seed` su DB pulito (dopo `alembic upgrade head`) popola
  133 foods e 140 porzioni. Secondo run: skip. (verificato)

---

## Fase 5 — Motore di calcolo

Obiettivo (PROJECT.md §7 e §12.5): `core/nutrition.py` puro, deterministico,
con Mifflin-St Jeor, TDEE, target per goal, somma diario e `DailyBalance`.
Test completi su Mifflin uomo/donna, TDEE per ogni livello, somma diario,
edge case. Requisito etico §7 rispettato.

### Decisioni di fase

- **Confine architetturale**: `core/` non importa da `app/` (sarebbe una
  dipendenza inversa). `core/nutrition.py` definisce le sue dataclass e
  i suoi enum. L'adapter "modello DB → dataclass core" verra' alle fasi
  successive (6/7/8). I valori string degli enum coincidono con quelli
  di `app/models.py` (test apposito).
- **Solo standard library**: `dataclasses`, `enum`, `math`. Nessun
  `sqlalchemy`, `fastapi`, `httpx`, `anthropic`, `app.*`. Test
  introspettivo via AST.
- **Tipi pubblici**: `Sex`, `ActivityLevel`, `Goal`, `Profile`,
  `FoodNutrients`, `DiaryItem`, `MacroBreakdown`, `Needs`, `DailyBalance`.
- **Eccezione `ProfileIncompleteError`**: alzata quando manca un dato
  necessario al calcolo (peso, altezza, eta'). MAI ritornare un numero
  finto (vincolo §2 "se manca un dato, dice che manca").
- **Goal default `MAINTAIN`** (requisito etico §7).
  `GENTLE_LOSS` = TDEE × 0.85 (max -15%, limite superiore del range
  "10-15%" — esposto come singola scelta moderata).
  `GENTLE_GAIN` = TDEE × 1.10.
  Niente parametro libero `deficit_pct`; niente `EXTREME_LOSS`.
- **`calc_basis` mancante**: §14 -> media delle due formule, con
  `Needs.calc_basis_assumed=True` per dichiarare l'assunzione.
- **`activity_level` mancante**: fallback `SEDENTARY` (piu' conservativo)
  con `Needs.activity_assumed=True`.
- **`goal` mancante**: `MAINTAIN` (e' il default di prodotto, non
  un'assunzione: niente flag).
- **Diario vuoto**: totali a zero. Non e' un errore, e' un fatto.
- **Fibre `None`** in un food: tratte come 0 nella somma; documento
  questa scelta nel docstring.
- **Niente giudizi nel dato grezzo**: `DailyBalance` ha numeri e
  differenza grezza (segnata), nessun campo "status" o "label".

### Vincoli duri rispettati

- "I numeri li fa il motore": tutto qui dentro, deterministico.
- "Se manca un dato, dice che manca": `ProfileIncompleteError`,
  oppure flag `*_assumed=True` per assunzioni dichiarate.
- "Default mantenimento, niente deficit aggressivo": API non lo permette.
- "Niente giudizi nel dato grezzo": test che verifica i campi.
- `core/` non tocca DB ne' rete ne' LLM: test AST sui moduli importati.

### Checklist

- [x] `core/nutrition.py`: enum (Sex, ActivityLevel, Goal),
      dataclass (Profile, FoodNutrients, DiaryItem, MacroBreakdown,
      Needs, MacrosPercent, DailyBalance), funzioni pure
      (compute_bmr, compute_tdee, compute_needs,
       compute_item_nutrients, sum_items, compute_daily_balance),
      eccezione `ProfileIncompleteError`.
- [x] `tests/test_nutrition.py`:
      - Mifflin uomo 30/75/180 -> 1730 (calcolato a mano);
      - Mifflin donna 30/60/165 -> 1320.25 (calcolato a mano);
      - Mifflin altri due casi noti (uomo 25/80/180 -> 1805,
        donna 25/65/170 -> 1426.5);
      - TDEE per ogni livello (5 parametri);
      - target per ogni goal (3 casi) + default MAINTAIN se goal None;
      - GENTLE_LOSS -15% (×0.85), GENTLE_GAIN +10% (×1.10) esatti;
      - `compute_item_nutrients` con grammature 0/50/80/100/150/250;
      - `sum_items` con mix di alimenti, fibre None come 0;
      - `compute_daily_balance` sotto/uguale/sopra target;
      - macros_percent con caso noto (solo proteine -> 100% prot);
      - `ProfileIncompleteError` per peso/altezza/eta' mancanti;
      - `calc_basis=None` -> media F/M, `assumed=True`;
      - `activity_level=None` -> SEDENTARY, `assumed=True`;
      - test "purezza": AST verifica che core/nutrition.py non
        importi sqlalchemy/alembic/fastapi/pydantic/httpx/anthropic/app;
      - test "no giudizi": fields di DailyBalance non contengono
        nomi tipo status/label/good/bad/over/under;
      - test "no deficit aggressivo": Goal ha esattamente
        {MAINTAIN, GENTLE_LOSS, GENTLE_GAIN}, fattori entro -15%/+10%;
      - test "compatibilita' enum": valori string di
        Sex/ActivityLevel/Goal di core coincidono con quelli
        di app.models (CalcBasis/ActivityLevel/Goal).
- [x] `pytest` verde: 87 passed.
- [x] End-to-end REPL: caso donna 35/65/168 moderata -> TDEE 2114.2,
      diario plausibile -> bilancio coerente.
- [x] Commit di fine fase citando la Fase 5.

### Verifica end-to-end (manuale)

- Importare `core.nutrition` e calcolare un caso noto in REPL:
  donna 35/65/168 moderata -> TDEE 2114.2; verificato.

---

## Fase 6 — Diario + summary

Obiettivo (PROJECT.md §9 e §12.6): rotte `/diary` (POST/GET/DELETE) e
`/summary/*` (day/week/needs) che usano il motore di Fase 5 per i calcoli.
Tutto scoped sull'utente del token.

### Decisioni di fase

- **Le rotte profile/weights NON vengono create qui** (sono Fase 7 di
  PROJECT.md §12). `/summary/needs` ha pero' bisogno del profilo e
  dell'ultimo peso: se mancano, risponde 422 con `missing`. Nei test
  riempio profile/weight_logs direttamente via session (la Fase 7
  esporra' le rotte).
- **Adapter motore <-> DB** in `app/summary/adapter.py`:
  - `core_profile_from_db(user) -> core.Profile`: usa `Profile` (per
    calc_basis/activity_level/goal/height/age) e l'ultimo `WeightLog`
    (per `weight_kg`). Eta' calcolata da `birth_date` rispetto a `today`.
  - `core_item_from_entry(entry) -> core.DiaryItem`: usa il `Food`
    collegato (eager load nel router).
- **Range giorno in UTC**: `consumed_at >= start AND < start + 1 day`.
  La query param `date` e' un `YYYY-MM-DD`. Niente fusi orari in F6.
- **Settimana**: 7 giorni consecutivi a partire da `from` (default oggi
  UTC). Ritorna 7 `DailyBalance` (uno per giorno) anche se vuoti.
- **DELETE /diary/{id}** di un'altra utente: 404 (non 403, niente
  info leak sull'esistenza).
- **POST /diary**: `food_id` deve essere visibile all'utente (pubblico
  oppure di sua proprieta'), altrimenti 404.
- **Risposta `/summary/needs` con profilo incompleto**: 422 con detail
  `{missing: "weight_kg"}` ecc. Mai numero finto (vincolo §2).
- **Niente giudizi nelle response**: il `DailyBalance` viene serializzato
  cosi' com'e' (totals + target + diff + macros_percent). L'UI/LLM
  formattera'.
- **Profilo "incompleto vs assunto"**: se calc_basis/activity_level
  sono `None` il motore usa fallback con flag `*_assumed=True`; la
  response li propaga. NON e' un errore (e' info dichiarata).

### Vincoli duri rispettati

- I numeri (totali, target, diff, BMR/TDEE) sono SEMPRE prodotti dal
  motore (`core.nutrition`): test che verifica match esatto fra
  response e calcolo diretto del motore sugli stessi input.
- Tutte le rotte scoped: `user_id = current_user.id`. Mai accettato
  da body/query/path. Test su Alice/Bob.
- Nessuna nuova dipendenza LLM in F6.

### Checklist

- [x] `app/schemas/diary.py`: `DiaryEntryIn`, `DiaryEntryOut`, `FoodMini`.
- [x] `app/schemas/summary.py`: `MacroBreakdownOut`, `MacrosPercentOut`,
      `NeedsOut`, `DailyBalanceOut`, `WeekSummaryOut`, con `from_core(...)`.
- [x] `app/summary/adapter.py`: `build_core_profile`, `entry_to_core_item`,
      `entries_to_core_items`. Eta' calcolata da `birth_date`.
- [x] `app/diary/router.py`: POST/GET/DELETE; food visibile = pubblico OR
      di proprieta'; food non visibile -> 404; DELETE altrui -> 404.
- [x] `app/summary/router.py`: `/needs`, `/day`, `/week`. Tutti chiamano
      il motore; 422 con `missing` se profilo incompleto.
- [x] `app/main.py`: include router diary + summary.
- [x] `tests/test_diary.py` (11 nuovi): 401 senza token, POST crea,
      `consumed_at` esplicito, food inesistente -> 404, food personale
      altrui -> 404, grams<=0 -> 422, meal non valido -> 422, filtro
      per data, scoping Alice vs Bob, DELETE, DELETE altrui -> 404.
- [x] `tests/test_summary.py` (8 nuovi): 401, needs senza profilo ->
      422 missing=weight_kg, needs con profilo -> numeri esatti dal
      motore, day con voci -> match esatto con `compute_daily_balance`
      sugli stessi input, day vuoto -> totali zero, day senza
      profilo -> 422, week 7 giorni con voci distribuite -> totali
      per giorno corretti, scoping Alice vs Bob.
- [x] `pytest` verde: 106 passed.
- [x] Commit di fine fase citando la Fase 6.

### Verifica end-to-end (manuale)

- Smoke test routes: tutte le 8 rotte previste in §9 (auth + foods +
  diary + summary) registrate dall'app.

---

## Fase 7 — Pesi + profilo

Obiettivo (PROJECT.md §9, §12.7): rotte `GET/PUT /profile` e `POST/GET
/weights`. Il profilo separa identita' (`sex` F/M/other) dal parametro di
calcolo Mifflin (`calc_basis` F/M, §14). `/summary/needs` calcola dal
profilo via motore (e' gia' wired in F6: in F7 lo rendiamo raggiungibile
"via API" senza dover popolare via session).

### Decisioni di fase

- `GET /profile`: se non esiste profilo, ritorno scheletro con tutti i
  campi `None` salvo `goal=MAINTAIN` (default etico §7). Niente 404:
  evita casi speciali nel client al primo accesso.
- `PUT /profile`: upsert con campi tutti opzionali. Mai accetta
  `user_id` dal client (sempre dal token). Lo schema espone
  `sex` e `calc_basis` come enum DISTINTI:
  - `sex` accetta {F, M, other};
  - `calc_basis` accetta solo {F, M} (Mifflin non ha "other").
  Test che verifica che `calc_basis="other"` -> 422.
- `Goal` esposto: esattamente {maintain, gentle_loss, gentle_gain}.
  Nessuna API espone "extreme_loss" o equivalente. Test apposito.
- `POST /weights`: upsert per giorno. Se esiste gia' un log per
  `(user_id, measured_at)`, aggiorna `weight_kg` (stesso id). Caso
  comune: ci si pesa di nuovo e si vuole correggere.
- `GET /weights`: paginato (limit default 50, max 365), ordine
  `measured_at` desc.
- Nessun `DELETE /weights/{id}` in F7 (non richiesto dal goal,
  non in §9). Aggiungibile in futuro senza rotture.

### Vincoli duri rispettati

- Tutte le rotte scoped: `user_id` solo dal token, mai dal client.
- `/summary/needs` chiama il motore (gia' fatto in F6); F7 garantisce
  che ora c'e' una via API per popolare i prerequisiti.
- Default `goal=MAINTAIN` rispettato come default di prodotto.
- Niente deficit aggressivo: enum `Goal` ha esattamente 3 valori.

### Checklist

- [x] `app/schemas/profile.py`: `ProfileOut`, `ProfileUpdateIn` (campi
      opzionali; `sex` Sex enum {F,M,other}, `calc_basis` CalcBasis
      enum {F,M} — distinti, §14).
- [x] `app/schemas/weights.py`: `WeightLogIn` (weight_kg>0,
      measured_at? default oggi), `WeightLogOut`.
- [x] `app/profile/router.py`: `GET /profile` ritorna scheletro
      con goal=maintain se non esiste; `PUT /profile` upsert.
- [x] `app/weights/router.py`: `POST /weights` upsert per giorno;
      `GET /weights` ordinato desc, paginato (limit max 365).
- [x] `app/main.py`: include router profile + weights.
- [x] `tests/test_profile.py` (10): 401, GET scheletro, PUT crea,
      GET riflette, PUT parziale (semantico: campi non forniti
      tornano None), `calc_basis="other"` -> 422,
      `goal="extreme_loss"` -> 422, scoping Alice vs Bob,
      identita' separata (sex="other" + calc_basis="F" -> ok),
      height_cm<=0 -> 422, Goal enum esposto = {3 valori etici}.
- [x] `tests/test_weights.py` (8): 401, POST crea, default
      measured_at = oggi, upsert stesso giorno (id stabile, valore
      aggiornato), GET ordinato desc, paginazione, weight_kg<=0 ->
      422, scoping Alice vs Bob.
- [x] `tests/test_needs_via_api.py` (3): integrazione end-to-end
      via API -> caso noto Mifflin donna 30/60/165 moderate maintain
      -> BMR 1320.25, TDEE 2046.3875; solo peso -> 422 missing
      height_cm; usa l'ultimo peso per data.
- [x] `pytest` verde: 127 passed.
- [x] Commit di fine fase citando la Fase 7.

### Verifica end-to-end (manuale)

- Tutte le rotte di PROJECT.md §9 (eccetto `/coach/*`) registrate:
  auth, profile, foods, diary, summary, weights. (verificato)
