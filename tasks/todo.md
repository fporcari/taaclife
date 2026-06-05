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
