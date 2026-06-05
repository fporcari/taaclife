#!/bin/sh
set -e

# Applica le migrazioni (no-op in Fase 1, nessuna revisione ancora).
alembic upgrade head

# Avvia FastAPI.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
