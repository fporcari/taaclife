from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.security import ALGORITHM
from app.settings import get_settings


@pytest.fixture
def registered(client: TestClient) -> dict:
    email = "mario@example.com"
    password = "supersegreta123"
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"email": email, "password": password, "user": r.json()}


def test_register_creates_user(client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        json={"email": "anna@example.com", "password": "abcdefgh"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "anna@example.com"
    assert "id" in body and body["id"]
    assert "created_at" in body
    assert "password_hash" not in body
    assert "password" not in body


def test_register_duplicate_email_rejected(registered: dict, client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        json={"email": registered["email"], "password": "altraPassword!"},
    )
    assert r.status_code == 409


def test_register_normalizes_email_case(client: TestClient) -> None:
    r1 = client.post(
        "/auth/register",
        json={"email": "Mixed@Example.com", "password": "abcdefgh"},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/auth/register",
        json={"email": "mixed@example.com", "password": "abcdefgh"},
    )
    assert r2.status_code == 409


def test_register_weak_password_rejected(client: TestClient) -> None:
    r = client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )
    assert r.status_code == 422


def test_login_returns_token_pair(registered: dict, client: TestClient) -> None:
    r = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_login_wrong_password_rejected(registered: dict, client: TestClient) -> None:
    r = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": "passwordSbagliata"},
    )
    assert r.status_code == 401


def test_login_unknown_email_same_error_as_wrong_password(client: TestClient) -> None:
    r = client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "qualunque1"},
    )
    assert r.status_code == 401
    # Stesso codice di "password sbagliata": niente user enumeration.


def test_me_requires_token(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_valid_access_token(registered: dict, client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    ).json()
    r = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == registered["email"]


def test_me_rejects_refresh_token(registered: dict, client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    ).json()
    r = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login['refresh_token']}"},
    )
    assert r.status_code == 401


def test_refresh_returns_new_pair(registered: dict, client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    ).json()
    r = client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    # Il nuovo access deve funzionare su /auth/me.
    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == registered["email"]


def test_refresh_rejects_access_token(registered: dict, client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    ).json()
    r = client.post(
        "/auth/refresh",
        json={"refresh_token": login["access_token"]},
    )
    assert r.status_code == 401


def test_me_rejects_expired_access_token(registered: dict, client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    ).json()
    # Decodifico il token valido per riprendere il subject, poi fabbrico un
    # token con exp nel passato firmato con la stessa chiave.
    settings = get_settings()
    payload = jwt.decode(
        login["access_token"], settings.jwt_secret, algorithms=[ALGORITHM]
    )
    expired = jwt.encode(
        {
            "sub": payload["sub"],
            "type": "access",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_me_rejects_tampered_token(client: TestClient, registered: dict) -> None:
    login = client.post(
        "/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
    ).json()
    tampered = login["access_token"] + "x"
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401
