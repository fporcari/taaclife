"""Vincolo PROJECT.md §8: se la chiave Anthropic manca, la chat si
disattiva ma il resto dell'app continua a funzionare.
"""
from fastapi.testclient import TestClient


def test_health_works_without_anthropic_key(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200


def test_auth_works_without_anthropic_key(client: TestClient) -> None:
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": "x@example.com", "password": "abcdefgh"})
    assert r.status_code == 200


def test_foods_works_without_anthropic_key(client: TestClient) -> None:
    # register + login
    client.post("/auth/register", json={"email": "x@example.com", "password": "abcdefgh"})
    token = client.post("/auth/login", json={"email": "x@example.com", "password": "abcdefgh"}).json()["access_token"]
    r = client.get("/foods", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_summary_works_without_anthropic_key(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "x@example.com", "password": "abcdefgh"})
    token = client.post("/auth/login", json={"email": "x@example.com", "password": "abcdefgh"}).json()["access_token"]
    # Senza profilo, summary/needs ritorna 422 (non 500): la rotta funziona.
    r = client.get("/summary/needs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_history_works_without_anthropic_key(client: TestClient) -> None:
    """/coach/history NON richiede la chiave (legge solo dal DB)."""
    client.post("/auth/register", json={"email": "x@example.com", "password": "abcdefgh"})
    token = client.post("/auth/login", json={"email": "x@example.com", "password": "abcdefgh"}).json()["access_token"]
    r = client.get("/coach/history", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


def test_chat_returns_503_without_anthropic_key(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "x@example.com", "password": "abcdefgh"})
    token = client.post("/auth/login", json={"email": "x@example.com", "password": "abcdefgh"}).json()["access_token"]
    r = client.post(
        "/coach/chat",
        json={"message": "ciao"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503
    assert "coach non disponibile" in r.json()["detail"]
