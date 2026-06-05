import os
from collections.abc import Generator
from pathlib import Path

# Settings di test: definite PRIMA di importare moduli che leggono get_settings().
os.environ.setdefault("JWT_SECRET", "test-access-secret-not-for-prod")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret-not-for-prod")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.rate_limit import _login_limiter, _register_limiter
from app.coach.deps import _build_limiter
from app.db import Base, build_engine
from app.deps import get_db
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    """I limiter sono cached con `lru_cache` per condividerli tra le request
    dello stesso processo. Nei test questo li fa persistere tra casi
    consecutivi: azzero la cache a inizio di ogni test."""
    _login_limiter.cache_clear()
    _register_limiter.cache_clear()
    _build_limiter.cache_clear()


@pytest.fixture
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
