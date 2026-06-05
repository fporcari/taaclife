"""Verifica end-to-end delle migrazioni Alembic.

upgrade head -> tabelle attese presenti; downgrade base -> resta solo
alembic_version. Coerente col vincolo "rollback pulito".
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import build_engine

EXPECTED_TABLES = {
    "users",
    "profiles",
    "weight_logs",
    "foods",
    "portions",
    "diary_entries",
    "preference_items",
    "chat_messages",
}

REPO_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    url = f"sqlite:///{db_path}"
    cfg = _alembic_config(url)

    command.upgrade(cfg, "head")

    engine = build_engine(url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    finally:
        engine.dispose()

    assert EXPECTED_TABLES.issubset(tables), f"mancano: {EXPECTED_TABLES - tables}"
    assert "alembic_version" in tables


def test_downgrade_base_leaves_only_alembic_version(tmp_path: Path) -> None:
    db_path = tmp_path / "rollback.db"
    url = f"sqlite:///{db_path}"
    cfg = _alembic_config(url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = build_engine(url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    finally:
        engine.dispose()

    assert tables == {"alembic_version"}, f"rimaste tabelle inattese: {tables}"


def test_diary_entries_has_no_macros_columns(tmp_path: Path) -> None:
    """Vincolo duro PROJECT.md §2/§5: i numeri li fa il motore, non il DB.

    Se qualcuno aggiunge una colonna kcal/protein/carbs/fat denormalizzata a
    diary_entries, questo test fallisce.
    """
    db_path = tmp_path / "diary.db"
    url = f"sqlite:///{db_path}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")

    engine = build_engine(url)
    try:
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("diary_entries")}
    finally:
        engine.dispose()

    forbidden_substrings = ("kcal", "protein", "carb", "fat", "macro", "calor")
    offenders = {
        col for col in columns for sub in forbidden_substrings if sub in col.lower()
    }
    assert not offenders, (
        f"diary_entries non deve cachare valori nutrizionali; trovate: {offenders}"
    )
    assert columns == {"id", "user_id", "consumed_at", "meal", "food_id", "grams"}
