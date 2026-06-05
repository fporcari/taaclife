"""Test di hardening (Fase 10).

Copre:
- rate limit anti brute-force su /auth/{register,login,refresh};
- disclaimer accessibile via GET /disclaimer;
- header X-Medical-Disclaimer su ogni response;
- validatori extra (chat whitespace, diary consumed_at fuori range);
- errori LLM aggiuntivi (timeout, status error) gestiti puliti
  senza far cadere l'app e senza leak della chiave;
- sweep statico: nessuno schema "In" espone `user_id`.
"""
from __future__ import annotations

import ast
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from app.coach.deps import get_coach_client, get_rate_limiter
from app.coach.llm import AnthropicCoachClient, CoachUnavailableError
from app.coach.rate_limit import SlidingWindowLimiter
from app.middleware import DISCLAIMER_HEADER_NAME, DISCLAIMER_HEADER_VALUE
from app.models import (
    ActivityLevel,
    CalcBasis,
    Food,
    FoodSource,
    Goal,
    Profile,
    Sex,
    WeightLog,
)


SECRET_KEY_PLACEHOLDER = "sk-ant-FAKE-DO-NOT-LEAK-1234567890abcdef"


# ---------- Disclaimer ----------


def test_disclaimer_endpoint_is_public_and_contains_key_clauses(
    client: TestClient,
) -> None:
    r = client.get("/disclaimer")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body and "text" in body
    text = body["text"].lower()
    assert "dispositivo medico" in text
    assert "non sostituisce" in text
    assert "mantenimento" in text


def test_disclaimer_header_present_on_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.headers.get(DISCLAIMER_HEADER_NAME) == DISCLAIMER_HEADER_VALUE


def test_disclaimer_header_present_on_protected_route_too(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401
    # Anche sulle response 401 il middleware deve aver aggiunto l'header.
    assert r.headers.get(DISCLAIMER_HEADER_NAME) == DISCLAIMER_HEADER_VALUE


# ---------- Auth rate limit ----------


def test_login_rate_limit_returns_429(client: TestClient) -> None:
    # Registrazione una volta (consuma 1 slot di register, ok).
    client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "abcdefgh"},
    )
    # Limite default: 10 login/15min. 11° tentativo -> 429.
    for _ in range(10):
        r = client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "abcdefgh"},
        )
        assert r.status_code in (200, 401), r.status_code
    r = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "abcdefgh"},
    )
    assert r.status_code == 429
    assert "troppe richieste" in r.json()["detail"].lower()


def test_register_rate_limit_returns_429(client: TestClient) -> None:
    # Default: 5 register/15min.
    for i in range(5):
        r = client.post(
            "/auth/register",
            json={"email": f"user{i}@example.com", "password": "abcdefgh"},
        )
        assert r.status_code in (201, 409)
    r = client.post(
        "/auth/register",
        json={"email": "user99@example.com", "password": "abcdefgh"},
    )
    assert r.status_code == 429


def test_refresh_rate_limit_shares_login_bucket(client: TestClient) -> None:
    """`/auth/refresh` usa lo stesso limiter di `/auth/login` (entrambi
    auth-bound). Test minimo: dopo aver saturato il bucket login, anche
    refresh restituisce 429."""
    for _ in range(10):
        client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "abcdefgh"},
        )
    # 11esimo tentativo (refresh): bucket saturato.
    r = client.post("/auth/refresh", json={"refresh_token": "qualunque"})
    assert r.status_code == 429


# ---------- Validatori ----------


def test_chat_rejects_whitespace_only_message(client: TestClient) -> None:
    """Il validator agisce sul body PRIMA che la chat venga inviata
    all'LLM. Override del client cosi' la dependency 503 non maschera
    il 422 atteso."""
    client.post("/auth/register", json={"email": "x@example.com", "password": "abcdefgh"})
    token = client.post(
        "/auth/login", json={"email": "x@example.com", "password": "abcdefgh"}
    ).json()["access_token"]

    class _NoopClient:
        def complete(self, **_): return "unused"
        def complete_with_tools(self, **_): return None
    client.app.dependency_overrides[get_coach_client] = lambda: _NoopClient()
    client.app.dependency_overrides[get_rate_limiter] = (
        lambda: SlidingWindowLimiter(max_calls=100, window_seconds=3600)
    )

    r = client.post(
        "/coach/chat",
        json={"message": "   \t  \n  "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_diary_rejects_consumed_at_too_far_in_future(client: TestClient, db_session) -> None:
    food = Food(
        name="Pasta", category="cereali",
        kcal_100g=353, protein_100g=12.5, carbs_100g=71.2, fat_100g=1.4, fiber_100g=2.7,
        source=FoodSource.CREA.value, is_public=True,
    )
    db_session.add(food)
    db_session.commit()
    db_session.refresh(food)

    client.post("/auth/register", json={"email": "y@example.com", "password": "abcdefgh"})
    token = client.post(
        "/auth/login", json={"email": "y@example.com", "password": "abcdefgh"}
    ).json()["access_token"]

    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    r = client.post(
        "/diary",
        json={"food_id": food.id, "grams": 100, "meal": "lunch", "consumed_at": future},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_diary_rejects_consumed_at_too_far_in_past(client: TestClient, db_session) -> None:
    food = Food(
        name="Pasta", category="cereali",
        kcal_100g=353, protein_100g=12.5, carbs_100g=71.2, fat_100g=1.4, fiber_100g=2.7,
        source=FoodSource.CREA.value, is_public=True,
    )
    db_session.add(food)
    db_session.commit()
    db_session.refresh(food)

    client.post("/auth/register", json={"email": "y@example.com", "password": "abcdefgh"})
    token = client.post(
        "/auth/login", json={"email": "y@example.com", "password": "abcdefgh"}
    ).json()["access_token"]

    long_ago = (datetime.now(timezone.utc) - timedelta(days=365 * 10)).isoformat()
    r = client.post(
        "/diary",
        json={"food_id": food.id, "grams": 100, "meal": "lunch", "consumed_at": long_ago},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ---------- Errori LLM aggiuntivi ----------


def test_anthropic_timeout_becomes_neutral_503(
    monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    class _Messages:
        def create(self, **_kwargs):
            raise anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))

    class _FakeAnthropic:
        def __init__(self, *_args, **_kwargs):
            self.messages = _Messages()

    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)

    wrapper = AnthropicCoachClient(
        api_key=SECRET_KEY_PLACEHOLDER,
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
    )
    with caplog.at_level(logging.DEBUG, logger="nutricoach.coach"):
        with pytest.raises(CoachUnavailableError) as exc_info:
            wrapper.complete(system="s", messages=[{"role": "user", "content": "x"}])
    assert "timeout" in str(exc_info.value).lower()
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert SECRET_KEY_PLACEHOLDER not in log_text
    assert SECRET_KEY_PLACEHOLDER not in str(exc_info.value)


def test_anthropic_status_error_500_becomes_neutral_503(
    monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    response = httpx.Response(
        500,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        text=f"upstream sees {SECRET_KEY_PLACEHOLDER}",
    )

    class _Messages:
        def create(self, **_kwargs):
            raise anthropic.InternalServerError(
                message=f"500 upstream {SECRET_KEY_PLACEHOLDER}",
                response=response,
                body=None,
            )

    class _FakeAnthropic:
        def __init__(self, *_args, **_kwargs):
            self.messages = _Messages()

    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)
    wrapper = AnthropicCoachClient(
        api_key=SECRET_KEY_PLACEHOLDER,
        model="claude-haiku-4-5-20251001",
        max_tokens=128,
    )
    with caplog.at_level(logging.DEBUG, logger="nutricoach.coach"):
        with pytest.raises(CoachUnavailableError) as exc_info:
            wrapper.complete(system="s", messages=[{"role": "user", "content": "x"}])
    # Messaggio neutro, no chiave nel detail.
    assert SECRET_KEY_PLACEHOLDER not in str(exc_info.value)
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert SECRET_KEY_PLACEHOLDER not in log_text


def test_app_with_timeout_in_coach_chat_returns_503(
    client: TestClient, db_session
) -> None:
    """Integrazione: nel flusso /coach/chat, se il client alza
    CoachUnavailableError("timeout"), il router risponde 503."""
    client.post("/auth/register", json={"email": "z@example.com", "password": "abcdefgh"})
    token = client.post(
        "/auth/login", json={"email": "z@example.com", "password": "abcdefgh"}
    ).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    today = date(2026, 6, 1)
    db_session.add_all([
        Profile(
            user_id=me["id"], sex=Sex.F.value, calc_basis=CalcBasis.F.value,
            birth_date=date(today.year - 30, today.month, today.day),
            height_cm=165.0, activity_level=ActivityLevel.MODERATE.value,
            goal=Goal.MAINTAIN.value,
        ),
        WeightLog(user_id=me["id"], measured_at=today, weight_kg=60.0),
    ])
    db_session.commit()

    class TimeoutClient:
        def complete(self, **_):
            raise CoachUnavailableError("coach non disponibile (timeout)")

        def complete_with_tools(self, **_):
            raise CoachUnavailableError("coach non disponibile (timeout)")

    client.app.dependency_overrides[get_coach_client] = lambda: TimeoutClient()
    client.app.dependency_overrides[get_rate_limiter] = (
        lambda: SlidingWindowLimiter(max_calls=100, window_seconds=3600)
    )
    r = client.post(
        "/coach/chat", json={"message": "ciao"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503
    assert "timeout" in r.json()["detail"].lower()


# ---------- Sweep statico: nessuno schema "In" espone user_id ----------


def test_no_input_schema_exposes_user_id() -> None:
    """Vincolo CLAUDE.md §3: il `user_id` arriva sempre dal token,
    mai dal body/query/path. Sweep AST sui file `app/schemas/*`:
    nessun campo `user_id` nelle classi Pydantic di tipo "In".
    """
    schemas_dir = Path(__file__).resolve().parents[1] / "app" / "schemas"
    offenders: list[str] = []
    for path in sorted(schemas_dir.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("In"):
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if stmt.target.id == "user_id":
                        offenders.append(f"{path.name}:{node.name}.user_id")
    assert not offenders, f"schemi 'In' espongono user_id: {offenders}"
