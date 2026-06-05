from fastapi.testclient import TestClient

from app.models import Goal


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_profile_requires_token(client: TestClient) -> None:
    assert client.get("/profile").status_code == 401
    assert client.put("/profile", json={}).status_code == 401


def test_get_profile_without_record_returns_empty_skeleton(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.get("/profile", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["sex"] is None
    assert body["calc_basis"] is None
    assert body["birth_date"] is None
    assert body["height_cm"] is None
    assert body["activity_level"] is None
    assert body["goal"] == "maintain"  # default etico §7
    assert body["user_id"]


def test_put_profile_creates_then_get_reflects_values(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    payload = {
        "sex": "F",
        "calc_basis": "F",
        "birth_date": "1990-05-01",
        "height_cm": 168.0,
        "activity_level": "moderate",
        "goal": "maintain",
    }
    r = client.put("/profile", json=payload, headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sex"] == "F"
    assert body["calc_basis"] == "F"
    assert body["height_cm"] == 168.0

    r = client.get("/profile", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["height_cm"] == 168.0
    assert body["activity_level"] == "moderate"


def test_put_profile_partial_update_keeps_other_fields_only_when_provided(
    client: TestClient,
) -> None:
    """PUT semantico: lo stato finale e' quello del body. Campi non
    forniti tornano al default. Test esplicito di questo comportamento.
    """
    token = _register_and_login(client, "alice@example.com")
    client.put(
        "/profile",
        json={
            "sex": "F", "calc_basis": "F",
            "birth_date": "1990-05-01", "height_cm": 168.0,
            "activity_level": "moderate", "goal": "maintain",
        },
        headers=_auth(token),
    )

    # Secondo PUT con solo height: gli altri tornano None / goal default.
    r = client.put("/profile", json={"height_cm": 170.0}, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["height_cm"] == 170.0
    assert body["sex"] is None
    assert body["goal"] == "maintain"


def test_put_profile_rejects_calc_basis_other(client: TestClient) -> None:
    """§14: Mifflin non ha "other"; il calc_basis accetta solo F/M.
    L'identita' invece accetta anche "other"."""
    token = _register_and_login(client, "alice@example.com")
    r = client.put(
        "/profile",
        json={"sex": "other", "calc_basis": "other"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_put_profile_accepts_other_sex_with_calc_basis_F(client: TestClient) -> None:
    """Identita' (sex) separata dal parametro di calcolo (calc_basis).
    L'utente puo' identificarsi come "other" usando F (o M) per la formula."""
    token = _register_and_login(client, "alice@example.com")
    r = client.put(
        "/profile",
        json={"sex": "other", "calc_basis": "F"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sex"] == "other"
    assert body["calc_basis"] == "F"


def test_put_profile_rejects_extreme_loss_goal(client: TestClient) -> None:
    """Requisito etico §7: niente deficit aggressivo."""
    token = _register_and_login(client, "alice@example.com")
    r = client.put(
        "/profile",
        json={"goal": "extreme_loss"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_put_profile_height_must_be_positive(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.put("/profile", json={"height_cm": -10}, headers=_auth(token))
    assert r.status_code == 422


def test_profile_scoped_to_user(client: TestClient) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")

    client.put("/profile", json={"height_cm": 170.0}, headers=_auth(token_a))
    client.put("/profile", json={"height_cm": 185.0}, headers=_auth(token_b))

    body_a = client.get("/profile", headers=_auth(token_a)).json()
    body_b = client.get("/profile", headers=_auth(token_b)).json()
    assert body_a["height_cm"] == 170.0
    assert body_b["height_cm"] == 185.0
    assert body_a["user_id"] != body_b["user_id"]


def test_goal_enum_exposes_exactly_three_values() -> None:
    """Verifica strutturale: lo schema OpenAPI espone solo i 3 goal etici.

    Se qualcuno aggiunge un EXTREME_LOSS al modello, questo test
    fallisce.
    """
    assert {g.value for g in Goal} == {"maintain", "gentle_loss", "gentle_gain"}
