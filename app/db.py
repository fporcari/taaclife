from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite:")


def _is_sqlite_memory_url(url: str) -> bool:
    return ":memory:" in url or url.endswith("sqlite://")


def build_engine(database_url: str) -> Engine:
    connect_args: dict = {}
    if _is_sqlite_url(database_url):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        future=True,
    )

    if _is_sqlite_url(database_url):
        _register_sqlite_pragmas(engine, in_memory=_is_sqlite_memory_url(database_url))

    return engine


def _register_sqlite_pragmas(engine: Engine, in_memory: bool) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            if not in_memory:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


_settings = get_settings()
engine: Engine = build_engine(_settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
