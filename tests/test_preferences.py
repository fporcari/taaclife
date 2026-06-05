from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_preferences_require_token(client: TestClient) -> None:
    assert client.get("/preferences").status_code == 401
    assert client.post("/preferences", json={"kind": "liked", "value": "pasta"}).status_code == 401


def test_get_empty_preferences(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.get("/preferences", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == {"liked": [], "avoided": []}


def test_add_liked_and_avoided(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r1 = client.post("/preferences", json={"kind": "liked", "value": "pasta"}, headers=_auth(token))
    r2 = client.post("/preferences", json={"kind": "avoided", "value": "cavolfiore"}, headers=_auth(token))
    assert r1.status_code == 201
    assert r2.status_code == 201

    body = client.get("/preferences", headers=_auth(token)).json()
    assert [it["value"] for it in body["liked"]] == ["pasta"]
    assert [it["value"] for it in body["avoided"]] == ["cavolfiore"]


def test_duplicate_returns_409(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    client.post("/preferences", json={"kind": "liked", "value": "pasta"}, headers=_auth(token))
    r = client.post("/preferences", json={"kind": "liked", "value": "pasta"}, headers=_auth(token))
    assert r.status_code == 409


def test_delete_preference(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post("/preferences", json={"kind": "liked", "value": "pasta"}, headers=_auth(token))
    pref_id = r.json()["id"]
    r = client.delete(f"/preferences/{pref_id}", headers=_auth(token))
    assert r.status_code == 204
    body = client.get("/preferences", headers=_auth(token)).json()
    assert body["liked"] == []


def test_delete_other_user_returns_404(client: TestClient) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")
    r = client.post("/preferences", json={"kind": "liked", "value": "pasta"}, headers=_auth(token_a))
    alice_id = r.json()["id"]
    r = client.delete(f"/preferences/{alice_id}", headers=_auth(token_b))
    assert r.status_code == 404


def test_preferences_scoped(client: TestClient) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")
    client.post("/preferences", json={"kind": "liked", "value": "pasta"}, headers=_auth(token_a))
    body = client.get("/preferences", headers=_auth(token_b)).json()
    assert body == {"liked": [], "avoided": []}
