from fastapi.testclient import TestClient

from app.models import Food, FoodSource
from app.seed import seed_foods


def _register_and_login(client: TestClient, email: str, password: str = "abcdefgh") -> str:
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_foods_requires_token(client: TestClient) -> None:
    r = client.get("/foods")
    assert r.status_code == 401


def test_list_foods_after_seed(client: TestClient, db_session) -> None:
    seed_foods(db_session)
    token = _register_and_login(client, "alice@example.com")

    r = client.get("/foods", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) > 0
    # Tutti i seedati sono pubblici, source CREA.
    assert all(f["is_public"] is True for f in body)
    assert all(f["source"] == FoodSource.CREA.value for f in body)


def test_search_by_query_case_insensitive(client: TestClient, db_session) -> None:
    seed_foods(db_session)
    token = _register_and_login(client, "alice@example.com")

    r = client.get("/foods", params={"q": "pasta"}, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) > 0
    names = [f["name"].lower() for f in body]
    assert all("pasta" in n for n in names)


def test_filter_by_category(client: TestClient, db_session) -> None:
    seed_foods(db_session)
    token = _register_and_login(client, "alice@example.com")

    r = client.get("/foods", params={"category": "legumi"}, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) > 0
    assert all(f["category"] == "legumi" for f in body)


def test_pagination_limit_and_offset(client: TestClient, db_session) -> None:
    seed_foods(db_session)
    token = _register_and_login(client, "alice@example.com")

    first = client.get("/foods", params={"limit": 5, "offset": 0}, headers=_auth(token)).json()
    second = client.get("/foods", params={"limit": 5, "offset": 5}, headers=_auth(token)).json()
    assert len(first) == 5
    assert len(second) == 5
    first_ids = {f["id"] for f in first}
    second_ids = {f["id"] for f in second}
    assert first_ids.isdisjoint(second_ids)


def test_pagination_limit_capped(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.get("/foods", params={"limit": 500}, headers=_auth(token))
    assert r.status_code == 422  # ge=1, le=200


def test_create_personal_food(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")

    payload = {
        "name": "Frittata della nonna",
        "category": "uova",
        "kcal_100g": 180.0,
        "protein_100g": 12.0,
        "carbs_100g": 1.0,
        "fat_100g": 14.0,
        "fiber_100g": None,
        "portions": [{"label": "una porzione", "grams": 120}],
    }
    r = client.post("/foods", json=payload, headers=_auth(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == payload["name"]
    assert body["source"] == FoodSource.USER.value
    assert body["is_public"] is False
    assert body["created_by"]  # uuid stringa dell'utente
    assert len(body["portions"]) == 1
    assert body["portions"][0]["grams"] == 120


def test_create_food_rejects_negative_kcal(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/foods",
        json={
            "name": "X",
            "kcal_100g": -5,
            "protein_100g": 0,
            "carbs_100g": 0,
            "fat_100g": 0,
        },
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_create_food_ignores_client_supplied_owner_fields(
    client: TestClient, db_session
) -> None:
    """Vincolo CLAUDE.md §3: il client non puo' impostare created_by/source.

    Lo schema FoodCreateIn non li accetta; FastAPI li ignora (extra='ignore').
    """
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/foods",
        json={
            "name": "Tentativo",
            "kcal_100g": 100,
            "protein_100g": 0,
            "carbs_100g": 0,
            "fat_100g": 0,
            "source": "CREA",  # tentativo di spoofing
            "is_public": True,  # tentativo di spoofing
            "created_by": "id-di-un-altro-utente",  # tentativo di spoofing
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    body = r.json()
    # Il server deve aver ignorato i campi malevoli.
    assert body["source"] == FoodSource.USER.value
    assert body["is_public"] is False
    # Riprende l'id dell'utente del token.
    me = client.get("/auth/me", headers=_auth(token)).json()
    assert body["created_by"] == me["id"]


def test_alice_personal_food_invisible_to_bob(client: TestClient) -> None:
    token_alice = _register_and_login(client, "alice@example.com")
    token_bob = _register_and_login(client, "bob@example.com")

    r = client.post(
        "/foods",
        json={
            "name": "Insalata di Alice",
            "kcal_100g": 50,
            "protein_100g": 2,
            "carbs_100g": 5,
            "fat_100g": 1,
        },
        headers=_auth(token_alice),
    )
    assert r.status_code == 201
    food_id = r.json()["id"]

    alice_list = client.get(
        "/foods", params={"q": "Insalata di Alice"}, headers=_auth(token_alice)
    ).json()
    assert any(f["id"] == food_id for f in alice_list)

    bob_list = client.get(
        "/foods", params={"q": "Insalata di Alice"}, headers=_auth(token_bob)
    ).json()
    assert all(f["id"] != food_id for f in bob_list)


def test_bob_sees_public_seeded_foods(client: TestClient, db_session) -> None:
    seed_foods(db_session)
    token_bob = _register_and_login(client, "bob@example.com")
    r = client.get("/foods", params={"q": "Pasta di semola"}, headers=_auth(token_bob))
    assert r.status_code == 200
    names = [f["name"] for f in r.json()]
    assert "Pasta di semola" in names


def test_create_food_with_no_portions(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/foods",
        json={
            "name": "Spuntino",
            "kcal_100g": 100,
            "protein_100g": 2,
            "carbs_100g": 10,
            "fat_100g": 5,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["portions"] == []
