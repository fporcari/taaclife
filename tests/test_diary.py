from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Food, FoodSource


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_food(db_session: Session, name: str = "Pasta") -> Food:
    food = Food(
        name=name,
        category="cereali",
        kcal_100g=353,
        protein_100g=12.5,
        carbs_100g=71.2,
        fat_100g=1.4,
        fiber_100g=2.7,
        source=FoodSource.CREA.value,
        is_public=True,
    )
    db_session.add(food)
    db_session.commit()
    db_session.refresh(food)
    return food


def test_post_diary_requires_token(client: TestClient) -> None:
    r = client.post("/diary", json={"food_id": 1, "grams": 100, "meal": "lunch"})
    assert r.status_code == 401


def test_post_diary_creates_entry(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token = _register_and_login(client, "alice@example.com")

    r = client.post(
        "/diary",
        json={
            "food_id": food.id,
            "grams": 80,
            "meal": "lunch",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["grams"] == 80
    assert body["meal"] == "lunch"
    assert body["food"]["id"] == food.id
    assert body["food"]["name"] == "Pasta"


def test_post_diary_with_explicit_consumed_at(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token = _register_and_login(client, "alice@example.com")
    when = datetime(2026, 6, 1, 12, 30, tzinfo=timezone.utc).isoformat()

    r = client.post(
        "/diary",
        json={
            "food_id": food.id,
            "grams": 100,
            "meal": "lunch",
            "consumed_at": when,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["consumed_at"].startswith("2026-06-01T12:30")


def test_post_diary_food_not_found(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/diary",
        json={"food_id": 9999, "grams": 100, "meal": "lunch"},
        headers=_auth(token),
    )
    assert r.status_code == 404


def test_post_diary_others_personal_food_returns_404(
    client: TestClient,
) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")

    # Alice crea un suo alimento personale.
    r = client.post(
        "/foods",
        json={
            "name": "Pollo di Alice",
            "kcal_100g": 100,
            "protein_100g": 23,
            "carbs_100g": 0,
            "fat_100g": 1,
        },
        headers=_auth(token_a),
    )
    assert r.status_code == 201
    alice_food_id = r.json()["id"]

    # Bob tenta di registrarlo nel suo diario -> 404 (niente info leak).
    r = client.post(
        "/diary",
        json={"food_id": alice_food_id, "grams": 100, "meal": "dinner"},
        headers=_auth(token_b),
    )
    assert r.status_code == 404


def test_post_diary_invalid_grams_rejected(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token = _register_and_login(client, "alice@example.com")

    r = client.post(
        "/diary",
        json={"food_id": food.id, "grams": 0, "meal": "lunch"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_post_diary_invalid_meal_rejected(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/diary",
        json={"food_id": food.id, "grams": 100, "meal": "colazione"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_get_diary_filters_by_day(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token = _register_and_login(client, "alice@example.com")

    today = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    yesterday = today - timedelta(days=1)

    for when in (today, yesterday):
        client.post(
            "/diary",
            json={
                "food_id": food.id,
                "grams": 50,
                "meal": "lunch",
                "consumed_at": when.isoformat(),
            },
            headers=_auth(token),
        )

    r = client.get(
        "/diary",
        params={"date": today.date().isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["consumed_at"].startswith("2026-06-01")


def test_get_diary_scoped_to_user(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")
    when = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc).isoformat()

    client.post(
        "/diary",
        json={"food_id": food.id, "grams": 100, "meal": "lunch", "consumed_at": when},
        headers=_auth(token_a),
    )

    r = client.get("/diary", params={"date": "2026-06-01"}, headers=_auth(token_b))
    assert r.status_code == 200
    assert r.json() == []


def test_delete_diary_entry(client: TestClient, db_session: Session) -> None:
    food = _make_food(db_session)
    token = _register_and_login(client, "alice@example.com")
    r = client.post(
        "/diary",
        json={"food_id": food.id, "grams": 100, "meal": "lunch"},
        headers=_auth(token),
    )
    entry_id = r.json()["id"]

    r = client.delete(f"/diary/{entry_id}", headers=_auth(token))
    assert r.status_code == 204

    r = client.delete(f"/diary/{entry_id}", headers=_auth(token))
    assert r.status_code == 404  # gia' cancellata


def test_delete_diary_entry_of_other_user_returns_404(
    client: TestClient, db_session: Session
) -> None:
    food = _make_food(db_session)
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")

    r = client.post(
        "/diary",
        json={"food_id": food.id, "grams": 100, "meal": "lunch"},
        headers=_auth(token_a),
    )
    alice_entry_id = r.json()["id"]

    r = client.delete(f"/diary/{alice_entry_id}", headers=_auth(token_b))
    assert r.status_code == 404
