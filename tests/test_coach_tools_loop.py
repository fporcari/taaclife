"""Test del loop di tool-use in /coach/chat.

Usa un fake client che restituisce una sequenza predefinita di risposte:
- prima un `tool_use` (search_food),
- poi un `tool_use` (add_diary_entry confermato),
- infine un blocco `text` con la chiusura.

Verifichiamo che il router:
- esegue i tool tramite `ToolRunner` reale (DB di test);
- propaga i risultati a Claude come `tool_result`;
- ritorna il testo finale e lo salva in `chat_messages`;
- rispetta il limite massimo di iterazioni.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.coach.deps import get_coach_client, get_rate_limiter
from app.coach.rate_limit import SlidingWindowLimiter
from app.models import (
    ActivityLevel,
    CalcBasis,
    DiaryEntry,
    Food,
    FoodSource,
    Goal,
    Profile,
    Sex,
    WeightLog,
)


# ---------- Fake SDK blocks ----------


class _TextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _ToolUseBlock:
    def __init__(self, tu_id: str, name: str, tool_input: dict[str, Any]) -> None:
        self.type = "tool_use"
        self.id = tu_id
        self.name = name
        self.input = tool_input


class _FakeResponse:
    def __init__(self, blocks, stop_reason: str) -> None:
        self.content = blocks
        self.stop_reason = stop_reason


class ScriptedClient:
    """Restituisce in sequenza le risposte preconfigurate, indipendentemente
    dai messaggi passati. Registra le chiamate per asserzioni nei test."""

    def __init__(self, scripted: list[_FakeResponse]) -> None:
        self._scripted = scripted
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system, messages):
        raise AssertionError("complete() non dovrebbe essere chiamato nel path tools")

    def complete_with_tools(self, *, system, messages, tools):
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        if not self._scripted:
            return _FakeResponse([_TextBlock("(fine)")], "end_turn")
        return self._scripted.pop(0)


# ---------- Helpers ----------


def _register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_user_with_profile(client: TestClient, db_session, email: str, today: date):
    token = _register_and_login(client, email)
    user_id = client.get("/auth/me", headers=_auth(token)).json()["id"]
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
    return token, user_id


def _override(client: TestClient, fake: ScriptedClient) -> None:
    client.app.dependency_overrides[get_coach_client] = lambda: fake
    client.app.dependency_overrides[get_rate_limiter] = (
        lambda: SlidingWindowLimiter(max_calls=1000, window_seconds=3600)
    )


# ---------- Tests ----------


def test_loop_executes_search_food_then_text(client: TestClient, db_session) -> None:
    token, _ = _setup_user_with_profile(
        client, db_session, "alice@example.com", date(2026, 6, 1)
    )
    db_session.add(Food(
        name="Pasta di semola", category="cereali",
        kcal_100g=353, protein_100g=12.5, carbs_100g=71.2, fat_100g=1.4, fiber_100g=2.7,
        source=FoodSource.CREA.value, is_public=True,
    ))
    db_session.commit()

    scripted = ScriptedClient([
        _FakeResponse(
            [_ToolUseBlock("tu_1", "search_food", {"query": "pasta"})],
            stop_reason="tool_use",
        ),
        _FakeResponse([_TextBlock("Ho trovato la pasta nel database.")], "end_turn"),
    ])
    _override(client, scripted)

    r = client.post(
        "/coach/chat",
        json={"message": "cerca pasta"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "Ho trovato la pasta nel database."

    # Due chiamate al modello: la prima emette tool_use, la seconda chiude.
    assert len(scripted.calls) == 2
    # Nel secondo turno, l'ultimo messaggio user contiene un tool_result.
    second_messages = scripted.calls[1]["messages"]
    assert second_messages[-1]["role"] == "user"
    assert isinstance(second_messages[-1]["content"], list)
    tool_results = [
        block for block in second_messages[-1]["content"]
        if block.get("type") == "tool_result"
    ]
    assert tool_results, "il secondo turno deve contenere tool_result"
    payload = json.loads(tool_results[0]["content"])
    assert payload["query"] == "pasta"
    assert any(f["name"] == "Pasta di semola" for f in payload["results"])


def test_loop_add_diary_entry_with_confirmation_writes(
    client: TestClient, db_session
) -> None:
    token, user_id = _setup_user_with_profile(
        client, db_session, "alice@example.com", date(2026, 6, 1)
    )
    food = Food(
        name="Pasta di semola", category="cereali",
        kcal_100g=353, protein_100g=12.5, carbs_100g=71.2, fat_100g=1.4, fiber_100g=2.7,
        source=FoodSource.CREA.value, is_public=True,
    )
    db_session.add(food)
    db_session.commit()
    db_session.refresh(food)

    # Sequenza: preview -> testo "vuoi confermare?".
    scripted = ScriptedClient([
        _FakeResponse(
            [_ToolUseBlock(
                "tu_preview", "add_diary_entry",
                {"food_id": food.id, "grams": 80, "meal": "lunch"},
            )],
            stop_reason="tool_use",
        ),
        _FakeResponse(
            [_TextBlock("Confermi 80g di pasta a pranzo?")], "end_turn"
        ),
    ])
    _override(client, scripted)

    r = client.post(
        "/coach/chat",
        json={"message": "registra 80g di pasta a pranzo"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    # Niente diary entries scritte: era solo la preview.
    assert db_session.query(DiaryEntry).count() == 0

    # Secondo turno: l'utente conferma e Claude richiama add_diary_entry
    # con confirmed=true, poi conclude.
    scripted2 = ScriptedClient([
        _FakeResponse(
            [_ToolUseBlock(
                "tu_confirm", "add_diary_entry",
                {"food_id": food.id, "grams": 80, "meal": "lunch", "confirmed": True},
            )],
            stop_reason="tool_use",
        ),
        _FakeResponse([_TextBlock("Aggiunta.")], "end_turn"),
    ])
    _override(client, scripted2)

    r = client.post(
        "/coach/chat",
        json={"message": "si' conferma"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "Aggiunta."
    assert db_session.query(DiaryEntry).count() == 1
    entry = db_session.query(DiaryEntry).one()
    assert entry.user_id == user_id
    assert entry.food_id == food.id
    assert entry.grams == 80


def test_loop_max_iterations_returns_503(client: TestClient, db_session) -> None:
    """Se il modello continua a richiedere tool oltre MAX_TOOL_ITERATIONS,
    il router risponde 503 (neutro). Non blocca mai per sempre."""
    token, _ = _setup_user_with_profile(
        client, db_session, "alice@example.com", date(2026, 6, 1)
    )

    # Script infinito di tool_use. ScriptedClient cade su default solo se
    # finiscono i copioni; qui mettiamo 10 risposte tool_use senza testo.
    scripted = ScriptedClient([
        _FakeResponse(
            [_ToolUseBlock(f"tu_{i}", "search_food", {"query": "x"})],
            stop_reason="tool_use",
        )
        for i in range(10)
    ])
    _override(client, scripted)

    r = client.post(
        "/coach/chat",
        json={"message": "loop infinito"},
        headers=_auth(token),
    )
    assert r.status_code == 503
    assert "troppe iterazioni" in r.json()["detail"]


def test_loop_unknown_tool_becomes_error_payload_for_llm(client: TestClient, db_session) -> None:
    """Se il modello chiede un tool sconosciuto, il runner solleva
    `UnknownToolError` (sottoclasse di `ToolError`). Il router la
    cattura come errore "di dominio" e la rimanda a Claude come
    `{error: ...}`, cosi' la chat non crasha e il modello puo'
    correggere il tiro al turno successivo.
    """
    token, _ = _setup_user_with_profile(
        client, db_session, "alice@example.com", date(2026, 6, 1)
    )
    scripted = ScriptedClient([
        _FakeResponse(
            [_ToolUseBlock("tu_x", "tool_che_non_esiste", {})],
            stop_reason="tool_use",
        ),
        _FakeResponse([_TextBlock("Ops, riprovo.")], "end_turn"),
    ])
    _override(client, scripted)

    r = client.post(
        "/coach/chat",
        json={"message": "x"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    tool_results = [
        b for b in scripted.calls[1]["messages"][-1]["content"]
        if b.get("type") == "tool_result"
    ]
    payload = json.loads(tool_results[0]["content"])
    assert "error" in payload
    assert "sconosciuto" in payload["error"].lower()


def test_loop_tool_error_becomes_payload_for_llm(client: TestClient, db_session) -> None:
    """Errori "di dominio" (es. query vuota) non crashano la chat:
    diventano `{error: ...}` nel tool_result e Claude puo' continuare."""
    token, _ = _setup_user_with_profile(
        client, db_session, "alice@example.com", date(2026, 6, 1)
    )
    scripted = ScriptedClient([
        _FakeResponse(
            [_ToolUseBlock("tu_e", "search_food", {"query": "   "})],
            stop_reason="tool_use",
        ),
        _FakeResponse([_TextBlock("Riformulo la ricerca.")], "end_turn"),
    ])
    _override(client, scripted)

    r = client.post(
        "/coach/chat", json={"message": "cerca qualcosa"}, headers=_auth(token),
    )
    assert r.status_code == 200
    # Il secondo turno ha ricevuto il tool_result con `error`.
    tool_results = [
        b for b in scripted.calls[1]["messages"][-1]["content"]
        if b.get("type") == "tool_result"
    ]
    payload = json.loads(tool_results[0]["content"])
    assert "error" in payload
