"""Test dei tool del coach (Fase 9).

Coperti:
- definizioni schema: nomi attesi, struttura, presenza di `confirmed`
  per `add_diary_entry`;
- runner per ogni tool con dati noti;
- conferma esplicita: senza `confirmed=true` la voce NON viene scritta;
- scoping: tool su utente A non vede dati personali di utente B;
- numeri prodotti dal motore (verifica match con `compute_*`).
"""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.coach.tool_runner import ToolError, ToolRunner, UnknownToolError
from app.models import (
    ActivityLevel,
    CalcBasis,
    DiaryEntry,
    Food,
    FoodSource,
    Goal,
    Meal,
    Profile,
    Sex,
    User,
    WeightLog,
)
from app.security import hash_password
from core.coach_tools import (
    TOOL_ADD_DIARY_ENTRY,
    TOOL_GET_DAILY_BALANCE,
    TOOL_GET_WEEKLY_SUMMARY,
    TOOL_NAMES,
    TOOL_SEARCH_FOOD,
    TOOLS,
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


def _user(db: Session, email: str) -> User:
    user = User(email=email, password_hash=hash_password("abcdefgh"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _setup_profile(db: Session, user_id: str, today: date) -> None:
    db.add_all([
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
    db.commit()


def _make_food(db: Session, name: str, is_public: bool = True, owner: str | None = None,
               kcal: float = 353, prot: float = 12.5, carb: float = 71.2, fat: float = 1.4,
               fiber: float | None = 2.7, category: str = "cereali") -> Food:
    food = Food(
        name=name, category=category,
        kcal_100g=kcal, protein_100g=prot, carbs_100g=carb, fat_100g=fat, fiber_100g=fiber,
        source=FoodSource.CREA.value if is_public else FoodSource.USER.value,
        is_public=is_public, created_by=owner,
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


# ---------- Schema ----------


def test_tools_have_four_expected_entries() -> None:
    names = {t["name"] for t in TOOLS}
    assert names == {
        TOOL_GET_DAILY_BALANCE,
        TOOL_GET_WEEKLY_SUMMARY,
        TOOL_SEARCH_FOOD,
        TOOL_ADD_DIARY_ENTRY,
    }
    assert names == set(TOOL_NAMES)


def test_each_tool_has_required_keys() -> None:
    for t in TOOLS:
        assert "name" in t and "description" in t and "input_schema" in t
        schema = t["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema


def test_add_diary_entry_schema_has_confirmed_field() -> None:
    add = next(t for t in TOOLS if t["name"] == TOOL_ADD_DIARY_ENTRY)
    assert "confirmed" in add["input_schema"]["properties"]
    # `confirmed` NON e' nei required: il default e' "non conferma".
    assert "confirmed" not in add["input_schema"].get("required", [])
    # Required minimi:
    assert set(add["input_schema"]["required"]) == {"food_id", "grams", "meal"}


# ---------- ToolRunner: dispatcher ----------


def test_unknown_tool_raises(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    _setup_profile(db_session, user.id, today)
    runner = ToolRunner(db=db_session, user=user, today=today)
    with pytest.raises(UnknownToolError):
        runner.run("not_a_tool", {})


# ---------- get_daily_balance ----------


def test_get_daily_balance_matches_engine(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    _setup_profile(db_session, user.id, today)

    food = _make_food(db_session, "Pasta")
    db_session.add(DiaryEntry(
        user_id=user.id,
        consumed_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        meal=Meal.LUNCH.value, food_id=food.id, grams=80,
    ))
    db_session.commit()

    runner = ToolRunner(db=db_session, user=user, today=today)
    out = runner.run(TOOL_GET_DAILY_BALANCE, {"date": "2026-06-01"})

    age = today.year - 1996 - ((today.month, today.day) < (6, 1))
    needs = compute_needs(CoreProfile(
        weight_kg=60.0, height_cm=165.0, age_years=age,
        calc_basis=CoreSex.F, activity_level=CoreActivityLevel.MODERATE,
        goal=CoreGoal.MAINTAIN,
    ))
    expected = compute_daily_balance(
        [DiaryItem(food=FoodNutrients(353, 12.5, 71.2, 1.4, 2.7), grams=80)],
        needs,
    )

    assert out["date"] == "2026-06-01"
    assert out["totals"]["kcal"] == pytest.approx(expected.totals.kcal)
    assert out["target_kcal"] == pytest.approx(expected.target_kcal)
    assert out["kcal_difference"] == pytest.approx(expected.kcal_difference)


def test_get_daily_balance_returns_error_when_profile_incomplete(
    db_session: Session,
) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    # Niente profilo.
    runner = ToolRunner(db=db_session, user=user, today=today)
    out = runner.run(TOOL_GET_DAILY_BALANCE, {})
    assert out["error"] == "profilo incompleto"
    assert out["missing"] == "weight_kg"


# ---------- get_weekly_summary ----------


def test_get_weekly_summary_returns_seven_days(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 7)  # ultimo giorno della settimana di test
    _setup_profile(db_session, user.id, today)
    food = _make_food(db_session, "Pasta")
    db_session.add(DiaryEntry(
        user_id=user.id,
        consumed_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        meal=Meal.LUNCH.value, food_id=food.id, grams=100,
    ))
    db_session.commit()

    runner = ToolRunner(db=db_session, user=user, today=today)
    out = runner.run(TOOL_GET_WEEKLY_SUMMARY, {"from_date": "2026-06-01"})
    assert out["from_date"] == "2026-06-01"
    assert out["to_date"] == "2026-06-07"
    assert len(out["days"]) == 7
    # Il 2026-06-01 ha 353 kcal (100g pasta).
    by_date = {d["date"]: d["totals"]["kcal"] for d in out["days"]}
    assert by_date["2026-06-01"] == pytest.approx(353.0)
    assert by_date["2026-06-02"] == 0


# ---------- search_food ----------


def test_search_food_returns_public_results(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    _make_food(db_session, "Pasta di semola")
    _make_food(db_session, "Pasta integrale")
    _make_food(db_session, "Pollo")
    runner = ToolRunner(db=db_session, user=user, today=today)

    out = runner.run(TOOL_SEARCH_FOOD, {"query": "pasta"})
    names = [r["name"] for r in out["results"]]
    assert "Pasta di semola" in names
    assert "Pasta integrale" in names
    assert "Pollo" not in names
    assert out["count"] == len(out["results"])


def test_search_food_respects_category(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    _make_food(db_session, "Pasta", category="cereali")
    _make_food(db_session, "Lenticchie", category="legumi", kcal=291, prot=22.7, carb=51.1, fat=1.0)
    runner = ToolRunner(db=db_session, user=user, today=today)

    out = runner.run(TOOL_SEARCH_FOOD, {"query": "l", "category": "legumi"})
    names = [r["name"] for r in out["results"]]
    assert names == ["Lenticchie"]


def test_search_food_empty_query_raises_tool_error(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    runner = ToolRunner(db=db_session, user=user, today=today)
    with pytest.raises(ToolError):
        runner.run(TOOL_SEARCH_FOOD, {"query": "  "})


def test_search_food_does_not_leak_other_users_personal_foods(db_session: Session) -> None:
    alice = _user(db_session, "alice@example.com")
    bob = _user(db_session, "bob@example.com")
    today = date(2026, 6, 1)
    # Food personale di Alice
    _make_food(db_session, "Tisana di Alice", is_public=False, owner=alice.id,
               kcal=2, prot=0, carb=0.5, fat=0)
    # Food personale di Bob (visibile a Bob, NON ad Alice)
    _make_food(db_session, "Frullato di Bob", is_public=False, owner=bob.id,
               kcal=120, prot=2, carb=18, fat=4)

    runner_alice = ToolRunner(db=db_session, user=alice, today=today)
    out = runner_alice.run(TOOL_SEARCH_FOOD, {"query": "frullato"})
    assert out["count"] == 0

    runner_bob = ToolRunner(db=db_session, user=bob, today=today)
    out = runner_bob.run(TOOL_SEARCH_FOOD, {"query": "frullato"})
    assert out["count"] == 1
    assert out["results"][0]["name"] == "Frullato di Bob"

    # E Alice continua a vedere il suo.
    out = runner_alice.run(TOOL_SEARCH_FOOD, {"query": "tisana"})
    assert out["count"] == 1


# ---------- add_diary_entry: protocollo di conferma ----------


def test_add_diary_entry_without_confirmed_does_not_write(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    food = _make_food(db_session, "Pasta")

    runner = ToolRunner(db=db_session, user=user, today=today)
    out = runner.run(TOOL_ADD_DIARY_ENTRY, {
        "food_id": food.id, "grams": 80, "meal": "lunch",
    })
    assert out["status"] == "needs_confirmation"
    assert "preview" in out and "draft" in out
    # Niente righe scritte.
    assert db_session.query(DiaryEntry).count() == 0
    # Preview con numeri dal motore: 80g pasta -> 282.4 kcal.
    assert out["preview"]["kcal"] == pytest.approx(282.4)


def test_add_diary_entry_with_confirmed_true_writes(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    food = _make_food(db_session, "Pasta")

    runner = ToolRunner(db=db_session, user=user, today=today)
    out = runner.run(TOOL_ADD_DIARY_ENTRY, {
        "food_id": food.id, "grams": 80, "meal": "lunch",
        "consumed_at": "2026-06-01T13:00:00+00:00",
        "confirmed": True,
    })
    assert out["status"] == "added"
    assert out["entry_id"]
    assert out["totals_added"]["kcal"] == pytest.approx(282.4)
    assert db_session.query(DiaryEntry).count() == 1
    entry = db_session.query(DiaryEntry).one()
    assert entry.user_id == user.id
    assert entry.food_id == food.id
    assert entry.grams == 80
    assert entry.meal == Meal.LUNCH.value


def test_add_diary_entry_food_not_visible_returns_not_found(db_session: Session) -> None:
    alice = _user(db_session, "alice@example.com")
    bob = _user(db_session, "bob@example.com")
    today = date(2026, 6, 1)
    bob_food = _make_food(db_session, "Frullato di Bob", is_public=False, owner=bob.id,
                          kcal=120, prot=2, carb=18, fat=4)

    runner_alice = ToolRunner(db=db_session, user=alice, today=today)
    out = runner_alice.run(TOOL_ADD_DIARY_ENTRY, {
        "food_id": bob_food.id, "grams": 100, "meal": "snack", "confirmed": True,
    })
    assert out["status"] == "not_found"
    assert db_session.query(DiaryEntry).count() == 0


def test_add_diary_entry_invalid_meal_raises(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    food = _make_food(db_session, "Pasta")
    runner = ToolRunner(db=db_session, user=user, today=today)
    with pytest.raises(ToolError):
        runner.run(TOOL_ADD_DIARY_ENTRY, {
            "food_id": food.id, "grams": 80, "meal": "colazione", "confirmed": True,
        })


def test_add_diary_entry_zero_grams_raises(db_session: Session) -> None:
    user = _user(db_session, "alice@example.com")
    today = date(2026, 6, 1)
    food = _make_food(db_session, "Pasta")
    runner = ToolRunner(db=db_session, user=user, today=today)
    with pytest.raises(ToolError):
        runner.run(TOOL_ADD_DIARY_ENTRY, {
            "food_id": food.id, "grams": 0, "meal": "lunch", "confirmed": True,
        })
