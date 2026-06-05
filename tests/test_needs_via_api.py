"""Integrazione end-to-end: rotte profile/weights -> /summary/needs via motore.

Caso noto Mifflin (donna 30/60/165, moderate, maintain):
- BMR = 10*60 + 6.25*165 - 5*30 - 161 = 1320.25
- TDEE = 1320.25 * 1.55 = 2046.3875
- target = TDEE (maintain)
"""
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_needs_end_to_end_via_api(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")

    # Profilo: donna 30 anni a oggi, 165 cm, moderate, maintain.
    today = datetime.now(timezone.utc).date()
    birth = date(today.year - 30, today.month, today.day)
    r = client.put(
        "/profile",
        json={
            "sex": "F",
            "calc_basis": "F",
            "birth_date": birth.isoformat(),
            "height_cm": 165.0,
            "activity_level": "moderate",
            "goal": "maintain",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text

    # Peso: 60 kg oggi.
    r = client.post(
        "/weights",
        json={"weight_kg": 60.0, "measured_at": today.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 201

    # Senza dati prerequisiti il motore avrebbe risposto 422; qui deve
    # restituire i numeri attesi.
    r = client.get("/summary/needs", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bmr"] == pytest.approx(1320.25)
    assert body["tdee"] == pytest.approx(2046.3875)
    assert body["target_kcal"] == pytest.approx(2046.3875)
    assert body["goal_applied"] == "maintain"
    assert body["calc_basis_assumed"] is False
    assert body["activity_assumed"] is False


def test_needs_when_only_weight_set_reports_missing_height(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    today = datetime.now(timezone.utc).date()
    client.post(
        "/weights",
        json={"weight_kg": 60.0, "measured_at": today.isoformat()},
        headers=_auth(token),
    )
    r = client.get("/summary/needs", headers=_auth(token))
    assert r.status_code == 422
    assert r.json()["detail"]["missing"] == "height_cm"


def test_needs_uses_latest_weight(client: TestClient) -> None:
    """Se ci sono piu' weight logs, /summary/needs usa l'ultimo per data."""
    token = _register_and_login(client, "alice@example.com")
    today = datetime.now(timezone.utc).date()
    birth = date(today.year - 30, today.month, today.day)

    # Profilo completo.
    client.put(
        "/profile",
        json={
            "sex": "F", "calc_basis": "F",
            "birth_date": birth.isoformat(),
            "height_cm": 165.0,
            "activity_level": "moderate",
            "goal": "maintain",
        },
        headers=_auth(token),
    )
    # Due pesi su date diverse. L'ultimo (oggi) deve prevalere.
    client.post(
        "/weights",
        json={"weight_kg": 80.0, "measured_at": "2026-01-01"},
        headers=_auth(token),
    )
    client.post(
        "/weights",
        json={"weight_kg": 60.0, "measured_at": today.isoformat()},
        headers=_auth(token),
    )

    r = client.get("/summary/needs", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["bmr"] == pytest.approx(1320.25)  # con 60 kg, non 80
