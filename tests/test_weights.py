from datetime import date

from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_weights_require_token(client: TestClient) -> None:
    assert client.get("/weights").status_code == 401
    assert client.post("/weights", json={"weight_kg": 70}).status_code == 401


def test_post_weight_creates_log(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/weights",
        json={"weight_kg": 65.5, "measured_at": "2026-06-01"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["weight_kg"] == 65.5
    assert body["measured_at"] == "2026-06-01"
    assert body["id"]


def test_post_weight_default_measured_at_is_today(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post("/weights", json={"weight_kg": 70}, headers=_auth(token))
    assert r.status_code == 201
    today_iso = date.today().isoformat()
    # Tolleranza: data UTC, ma il test gira su localtime: prendiamo entrambe.
    assert r.json()["measured_at"] in {today_iso}


def test_post_weight_upserts_same_day(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r1 = client.post(
        "/weights",
        json={"weight_kg": 70.0, "measured_at": "2026-06-01"},
        headers=_auth(token),
    )
    r2 = client.post(
        "/weights",
        json={"weight_kg": 70.5, "measured_at": "2026-06-01"},
        headers=_auth(token),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    # Upsert: stesso id, valore aggiornato.
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["weight_kg"] == 70.5

    listing = client.get("/weights", headers=_auth(token)).json()
    assert len(listing) == 1
    assert listing[0]["weight_kg"] == 70.5


def test_get_weights_ordered_desc(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    for d, w in [("2026-06-01", 70.0), ("2026-06-03", 69.8), ("2026-06-02", 69.9)]:
        client.post(
            "/weights",
            json={"weight_kg": w, "measured_at": d},
            headers=_auth(token),
        )
    r = client.get("/weights", headers=_auth(token))
    assert r.status_code == 200
    dates = [item["measured_at"] for item in r.json()]
    assert dates == ["2026-06-03", "2026-06-02", "2026-06-01"]


def test_get_weights_pagination(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    for i in range(10):
        client.post(
            "/weights",
            json={"weight_kg": 70.0 + i * 0.1, "measured_at": f"2026-06-{i+1:02d}"},
            headers=_auth(token),
        )
    first = client.get("/weights", params={"limit": 3, "offset": 0}, headers=_auth(token)).json()
    second = client.get("/weights", params={"limit": 3, "offset": 3}, headers=_auth(token)).json()
    assert len(first) == 3
    assert len(second) == 3
    assert {f["id"] for f in first}.isdisjoint({s["id"] for s in second})


def test_post_weight_rejects_non_positive(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post("/weights", json={"weight_kg": 0}, headers=_auth(token))
    assert r.status_code == 422
    r = client.post("/weights", json={"weight_kg": -1}, headers=_auth(token))
    assert r.status_code == 422


def test_weights_scoped_to_user(client: TestClient) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")
    client.post(
        "/weights",
        json={"weight_kg": 65, "measured_at": "2026-06-01"},
        headers=_auth(token_a),
    )
    r = client.get("/weights", headers=_auth(token_b))
    assert r.status_code == 200
    assert r.json() == []
