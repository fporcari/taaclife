#!/bin/sh
set -e

# Applica le migrazioni Alembic.
alembic upgrade head

# Seed idempotente del database alimenti (no-op se foods e' gia' popolato).
python -m app.seed

# Avvia FastAPI.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
