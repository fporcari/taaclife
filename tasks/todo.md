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
