from datetime import date, datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.coach.deps import get_coach_client, get_rate_limiter
from app.coach.llm import CoachClient, CoachUnavailableError
from app.coach.rate_limit import SlidingWindowLimiter
from app.models import (
    ActivityLevel,
    CalcBasis,
    Goal,
    Profile,
    Sex,
    WeightLog,
)


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_TextBlock(text)] if text else []
        self.stop_reason = stop_reason


class FakeClient:
    """Implementazione fittizia di `CoachClient`: registra le chiamate
    e ritorna una risposta di solo testo (nessun tool_use)."""

    def __init__(self, reply: str = "ciao") -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system: str, messages):
        self.calls.append({"system": system, "messages": messages})
        return self.reply

    def complete_with_tools(self, *, system, messages, tools):
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        return _FakeResponse(text=self.reply, stop_reason="end_turn")


class FailingClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def complete(self, *, system, messages):
        raise self.exc

    def complete_with_tools(self, *, system, messages, tools):
        raise self.exc


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_id(client: TestClient, token: str) -> str:
    return client.get("/auth/me", headers=_auth(token)).json()["id"]


def _complete_profile(db_session, user_id: str, today: date) -> None:
    db_session.add_all([
        Profile(
            user_id=user_id,
            sex=Sex.F.value, calc_basis=CalcBasis.F.value,
            birth_date=date(today.year - 30, today.month, today.day),
            height_cm=165.0,
            activity_level=ActivityLevel.MODERATE.value,
            goal=Goal.MAINTAIN.value,
        ),
        WeightLog(user_id=user_id, measured_at=today, weight_kg=60.0),
    ])
    db_session.commit()


def _override_client(client: TestClient, fake: CoachClient) -> None:
    client.app.dependency_overrides[get_coach_client] = lambda: fake


def _override_limiter(client: TestClient, max_calls: int = 1000) -> SlidingWindowLimiter:
    lim = SlidingWindowLimiter(max_calls=max_calls, window_seconds=3600)
    client.app.dependency_overrides[get_rate_limiter] = lambda: lim
    return lim


def test_chat_requires_token(client: TestClient) -> None:
    r = client.post("/coach/chat", json={"message": "ciao"})
    assert r.status_code == 401


def test_history_requires_token(client: TestClient) -> None:
    r = client.get("/coach/history")
    assert r.status_code == 401


def test_chat_with_missing_key_returns_503(client: TestClient) -> None:
    """Senza ANTHROPIC_API_KEY la dependency restituisce 503. Le altre
    rotte continuano a funzionare (test in test_app_works_without_coach)."""
    # Assicuriamoci che la dependency reale non sia stata overridata.
    client.app.dependency_overrides.pop(get_coach_client, None)
    # conftest non popola ANTHROPIC_API_KEY -> default "" -> 503.
    token = _register_and_login(client, "alice@example.com")
    r = client.post("/coach/chat", json={"message": "ciao"}, headers=_auth(token))
    assert r.status_code == 503
    assert "coach non disponibile" in r.json()["detail"]


def test_chat_persists_user_and_assistant_messages(
    client: TestClient, db_session
) -> None:
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id(client, token)
    _complete_profile(db_session, user_id, date(2026, 6, 1))

    fake = FakeClient(reply="Buona idea, prova con un piatto di pasta integrale.")
    _override_client(client, fake)
    _override_limiter(client)

    r = client.post(
        "/coach/chat",
        json={"message": "Cosa potrei mangiare stasera?"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == fake.reply
    assert body["user_message_id"]
    assert body["assistant_message_id"]
    assert body["assistant_message_id"] != body["user_message_id"]

    # Storico riflette i due messaggi.
    history = client.get("/coach/history", headers=_auth(token)).json()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Cosa potrei mangiare stasera?"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == fake.reply

    # Il fake ha visto il system prompt e un primo messaggio user con <context>.
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert "non sei un medico" in call["system"].lower()
    assert "<context>" in call["messages"][0]["content"]


def test_chat_includes_engine_numbers_in_context(
    client: TestClient, db_session
) -> None:
    """Il primo messaggio user del prompt contiene i numeri del motore
    (BMR/TDEE/target) presi dal contesto. L'LLM non li deve ricalcolare."""
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id(client, token)
    _complete_profile(db_session, user_id, date(2026, 6, 1))

    fake = FakeClient(reply="ok")
    _override_client(client, fake)
    _override_limiter(client)

    client.post(
        "/coach/chat",
        json={"message": "Come sto andando?"},
        headers=_auth(token),
    )

    context_payload = fake.calls[0]["messages"][0]["content"]
    assert "1320.25" in context_payload  # BMR
    assert "2046.3875" in context_payload  # TDEE


def test_chat_rate_limit(client: TestClient, db_session) -> None:
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id(client, token)
    _complete_profile(db_session, user_id, date(2026, 6, 1))

    fake = FakeClient(reply="ok")
    _override_client(client, fake)
    # Limite stretto: 2 messaggi.
    _override_limiter(client, max_calls=2)

    r1 = client.post("/coach/chat", json={"message": "m1"}, headers=_auth(token))
    r2 = client.post("/coach/chat", json={"message": "m2"}, headers=_auth(token))
    r3 = client.post("/coach/chat", json={"message": "m3"}, headers=_auth(token))

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert "limite messaggi" in r3.json()["detail"].lower()


def test_chat_503_when_client_raises_unavailable(
    client: TestClient, db_session
) -> None:
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id(client, token)
    _complete_profile(db_session, user_id, date(2026, 6, 1))

    _override_client(client, FailingClient(CoachUnavailableError("upstream giù")))
    _override_limiter(client)

    r = client.post(
        "/coach/chat", json={"message": "ciao"}, headers=_auth(token)
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "upstream giù"


def test_history_scoped_per_user(client: TestClient, db_session) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")
    a_id = _user_id(client, token_a)
    b_id = _user_id(client, token_b)
    _complete_profile(db_session, a_id, date(2026, 6, 1))
    _complete_profile(db_session, b_id, date(2026, 6, 1))

    fake = FakeClient(reply="ok")
    _override_client(client, fake)
    _override_limiter(client)

    client.post("/coach/chat", json={"message": "ciao da Alice"}, headers=_auth(token_a))
    client.post("/coach/chat", json={"message": "ciao da Bob"}, headers=_auth(token_b))

    a_hist = client.get("/coach/history", headers=_auth(token_a)).json()
    b_hist = client.get("/coach/history", headers=_auth(token_b)).json()
    a_contents = {m["content"] for m in a_hist}
    b_contents = {m["content"] for m in b_hist}
    assert "ciao da Alice" in a_contents
    assert "ciao da Alice" not in b_contents
    assert "ciao da Bob" in b_contents
    assert "ciao da Bob" not in a_contents


def test_chat_with_incomplete_profile_still_works_and_reports_missing(
    client: TestClient,
) -> None:
    """L'utente puo' chattare anche prima di compilare il profilo: i
    numeri saranno assenti nel contesto e l'LLM sa che deve dirlo."""
    token = _register_and_login(client, "alice@example.com")
    fake = FakeClient(reply="non ho ancora i tuoi dati")
    _override_client(client, fake)
    _override_limiter(client)

    r = client.post(
        "/coach/chat",
        json={"message": "ciao"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["needs_missing"] == "weight_kg"
