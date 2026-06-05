from pathlib import Path

from sqlalchemy import text

from app.db import build_engine


def test_sqlite_file_engine_enables_wal_and_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = build_engine(f"sqlite:///{db_path}")

    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()

    assert journal_mode == "wal"
    assert foreign_keys == 1


def test_sqlite_memory_engine_skips_wal_but_enables_foreign_keys() -> None:
    engine = build_engine("sqlite:///:memory:")

    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()

    # In-memory SQLite non supporta WAL; il default è "memory".
    assert journal_mode == "memory"
    assert foreign_keys == 1
