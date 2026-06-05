from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    ActivityLevel,
    CalcBasis,
    Food,
    FoodSource,
    Goal,
    Profile,
    Sex,
    User,
    WeightLog,
)
from core.nutrition import (
    DiaryItem,
    FoodNutrients,
    Profile as CoreProfile,
    Sex as CoreSex,
    ActivityLevel as CoreActivityLevel,
    Goal as CoreGoal,
    compute_daily_balance,
    compute_needs,
)


def _register_and_login(client: TestClient, email: str) -> str:
    r = client.post("/auth/register", json={"email": email, "password": "abcdefgh"})
    assert r.status_code == 201
    r = client.post("/auth/login", json={"email": email, "password": "abcdefgh"})
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_id_from(client: TestClient, token: str) -> str:
    return client.get("/auth/me", headers=_auth(token)).json()["id"]


def _provision_complete_profile(
    db_session: Session,
    user_id: str,
    *,
    weight_kg: float = 60.0,
    height_cm: float = 165.0,
    birth_year: int = 1996,
    sex: Sex = Sex.F,
    calc_basis: CalcBasis = CalcBasis.F,
    activity_level: ActivityLevel = ActivityLevel.MODERATE,
    goal: Goal = Goal.MAINTAIN,
) -> None:
    """Crea profilo + ultimo peso. Le rotte /profile e /weights arrivano in F7."""
    profile = Profile(
        user_id=user_id,
        sex=sex.value,
        calc_basis=calc_basis.value,
        birth_date=date(birth_year, 6, 1),
        height_cm=height_cm,
        activity_level=activity_level.value,
        goal=goal.value,
    )
    weight_log = WeightLog(
        user_id=user_id,
        measured_at=date(2026, 1, 1),
        weight_kg=weight_kg,
    )
    db_session.add_all([profile, weight_log])
    db_session.commit()


def _make_food(
    db_session: Session,
    name: str,
    kcal: float,
    prot: float,
    carb: float,
    fat: float,
    fiber: float | None = None,
) -> Food:
    food = Food(
        name=name,
        category="test",
        kcal_100g=kcal,
        protein_100g=prot,
        carbs_100g=carb,
        fat_100g=fat,
        fiber_100g=fiber,
        source=FoodSource.CREA.value,
        is_public=True,
    )
    db_session.add(food)
    db_session.commit()
    db_session.refresh(food)
    return food


def test_summary_routes_require_token(client: TestClient) -> None:
    assert client.get("/summary/needs").status_code == 401
    assert client.get("/summary/day").status_code == 401
    assert client.get("/summary/week").status_code == 401


def test_needs_without_profile_returns_422_with_missing(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.get("/summary/needs", headers=_auth(token))
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "profilo incompleto"
    # Niente peso e niente profilo: il primo che manca e' weight_kg.
    assert body["detail"]["missing"] == "weight_kg"


def test_needs_returns_engine_numbers(client: TestClient, db_session: Session) -> None:
    """Donna 30 anni (nata nel 1996 e calcolo a una data successiva al
    compleanno), 60 kg, 165 cm, moderate, maintain -> BMR 1320.25,
    TDEE 2046.3875. Verifico match con `compute_needs` su CoreProfile
    equivalente.
    """
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id_from(client, token)
    _provision_complete_profile(db_session, user_id, birth_year=1996)

    r = client.get("/summary/needs", headers=_auth(token))
    assert r.status_code == 200, r.text

    # Calcolo l'atteso col motore puro su un profilo equivalente,
    # usando "oggi" come riferimento (eta' coerente con il backend).
    today = datetime.now(timezone.utc).date()
    age = today.year - 1996 - ((today.month, today.day) < (6, 1))
    expected = compute_needs(
        CoreProfile(
            weight_kg=60.0,
            height_cm=165.0,
            age_years=age,
            calc_basis=CoreSex.F,
            activity_level=CoreActivityLevel.MODERATE,
            goal=CoreGoal.MAINTAIN,
        )
    )

    body = r.json()
    assert body["bmr"] == pytest.approx(expected.bmr)
    assert body["tdee"] == pytest.approx(expected.tdee)
    assert body["target_kcal"] == pytest.approx(expected.target_kcal)
    assert body["goal_applied"] == "maintain"
    assert body["calc_basis_assumed"] is False
    assert body["activity_assumed"] is False


def test_day_summary_totals_match_engine(client: TestClient, db_session: Session) -> None:
    """Aggiungo voci di diario e verifico che `/summary/day` ritorni
    esattamente i numeri prodotti da `compute_daily_balance` sugli
    stessi food+grams. Vincolo CLAUDE.md: i numeri li fa il motore.
    """
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id_from(client, token)
    _provision_complete_profile(db_session, user_id)

    pasta = _make_food(db_session, "Pasta", 353, 12.5, 71.2, 1.4, 2.7)
    olio = _make_food(db_session, "Olio", 899, 0, 0, 99.9, None)
    pollo = _make_food(db_session, "Pollo", 100, 23.3, 0, 0.8, None)

    when = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc).isoformat()
    for food_id, grams in ((pasta.id, 80), (olio.id, 10), (pollo.id, 150)):
        r = client.post(
            "/diary",
            json={"food_id": food_id, "grams": grams, "meal": "lunch", "consumed_at": when},
            headers=_auth(token),
        )
        assert r.status_code == 201

    r = client.get("/summary/day", params={"date": "2026-06-01"}, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()

    # Replica esatta col motore.
    today = datetime.now(timezone.utc).date()
    age = today.year - 1996 - ((today.month, today.day) < (6, 1))
    needs = compute_needs(
        CoreProfile(
            weight_kg=60.0, height_cm=165.0, age_years=age,
            calc_basis=CoreSex.F, activity_level=CoreActivityLevel.MODERATE,
            goal=CoreGoal.MAINTAIN,
        )
    )
    expected = compute_daily_balance(
        [
            DiaryItem(
                food=FoodNutrients(353, 12.5, 71.2, 1.4, 2.7), grams=80
            ),
            DiaryItem(
                food=FoodNutrients(899, 0, 0, 99.9, None), grams=10
            ),
            DiaryItem(
                food=FoodNutrients(100, 23.3, 0, 0.8, None), grams=150
            ),
        ],
        needs,
    )

    assert body["date"] == "2026-06-01"
    assert body["totals"]["kcal"] == pytest.approx(expected.totals.kcal)
    assert body["totals"]["protein_g"] == pytest.approx(expected.totals.protein_g)
    assert body["totals"]["carbs_g"] == pytest.approx(expected.totals.carbs_g)
    assert body["totals"]["fat_g"] == pytest.approx(expected.totals.fat_g)
    assert body["totals"]["fiber_g"] == pytest.approx(expected.totals.fiber_g)
    assert body["target_kcal"] == pytest.approx(expected.target_kcal)
    assert body["kcal_difference"] == pytest.approx(expected.kcal_difference)
    assert body["macros_percent"]["protein_pct"] == pytest.approx(
        expected.macros_percent.protein_pct
    )


def test_day_summary_empty_day_has_zero_totals(client: TestClient, db_session: Session) -> None:
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id_from(client, token)
    _provision_complete_profile(db_session, user_id)

    r = client.get("/summary/day", params={"date": "2026-06-01"}, headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["kcal"] == 0
    assert body["kcal_difference"] == pytest.approx(-body["target_kcal"])


def test_day_summary_without_profile_returns_422(client: TestClient) -> None:
    token = _register_and_login(client, "alice@example.com")
    r = client.get("/summary/day", params={"date": "2026-06-01"}, headers=_auth(token))
    assert r.status_code == 422


def test_week_summary_seven_days_with_correct_totals(
    client: TestClient, db_session: Session
) -> None:
    token = _register_and_login(client, "alice@example.com")
    user_id = _user_id_from(client, token)
    _provision_complete_profile(db_session, user_id)

    pasta = _make_food(db_session, "Pasta", 353, 12.5, 71.2, 1.4, 2.7)
    olio = _make_food(db_session, "Olio", 899, 0, 0, 99.9, None)

    monday = date(2026, 6, 1)  # 2026-06-01 e' lunedi
    # Lunedi: 100g pasta. Mercoledi: 10g olio. Venerdi: nulla.
    plan = {
        monday: [(pasta.id, 100)],
        monday + timedelta(days=2): [(olio.id, 10)],
    }
    for day, items in plan.items():
        when = datetime.combine(
            day, datetime.min.time(), tzinfo=timezone.utc
        ) + timedelta(hours=12)
        for food_id, grams in items:
            client.post(
                "/diary",
                json={
                    "food_id": food_id,
                    "grams": grams,
                    "meal": "lunch",
                    "consumed_at": when.isoformat(),
                },
                headers=_auth(token),
            )

    r = client.get(
        "/summary/week",
        params={"from": monday.isoformat()},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["from_date"] == "2026-06-01"
    assert body["to_date"] == "2026-06-07"
    assert len(body["days"]) == 7

    kcal_by_date = {d["date"]: d["totals"]["kcal"] for d in body["days"]}
    assert kcal_by_date["2026-06-01"] == pytest.approx(353.0)
    assert kcal_by_date["2026-06-03"] == pytest.approx(89.9)
    # Tutti gli altri giorni: zero.
    for other in ("2026-06-02", "2026-06-04", "2026-06-05", "2026-06-06", "2026-06-07"):
        assert kcal_by_date[other] == 0


def test_summary_scoped_alice_does_not_see_bob_entries(
    client: TestClient, db_session: Session
) -> None:
    token_a = _register_and_login(client, "alice@example.com")
    token_b = _register_and_login(client, "bob@example.com")
    a_id = _user_id_from(client, token_a)
    b_id = _user_id_from(client, token_b)
    _provision_complete_profile(db_session, a_id)
    _provision_complete_profile(db_session, b_id)

    pasta = _make_food(db_session, "Pasta", 353, 12.5, 71.2, 1.4, 2.7)
    when = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc).isoformat()

    # Bob mangia 200g di pasta lo stesso giorno; non deve influenzare Alice.
    client.post(
        "/diary",
        json={"food_id": pasta.id, "grams": 200, "meal": "lunch", "consumed_at": when},
        headers=_auth(token_b),
    )

    r = client.get(
        "/summary/day", params={"date": "2026-06-01"}, headers=_auth(token_a)
    )
    assert r.json()["totals"]["kcal"] == 0

    r = client.get(
        "/summary/day", params={"date": "2026-06-01"}, headers=_auth(token_b)
    )
    assert r.json()["totals"]["kcal"] == pytest.approx(706.0)
