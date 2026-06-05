from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ActivityLevel,
    CalcBasis,
    ChatMessage,
    ChatRole,
    DiaryEntry,
    Food,
    FoodSource,
    Goal,
    Meal,
    Portion,
    PrefKind,
    PreferenceItem,
    Profile,
    Sex,
    User,
    WeightLog,
)
from app.security import hash_password


def _make_user(db_session: Session, email: str = "tester@example.com") -> User:
    user = User(email=email, password_hash=hash_password("abcdefgh"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_food(db_session: Session, name: str = "Pasta") -> Food:
    food = Food(
        name=name,
        category="cereali",
        kcal_100g=353.0,
        protein_100g=12.5,
        carbs_100g=72.0,
        fat_100g=1.5,
        fiber_100g=2.7,
        source=FoodSource.CREA.value,
        is_public=True,
    )
    db_session.add(food)
    db_session.commit()
    db_session.refresh(food)
    return food


def test_user_profile_one_to_one(db_session: Session) -> None:
    user = _make_user(db_session)
    profile = Profile(
        user_id=user.id,
        sex=Sex.F.value,
        calc_basis=CalcBasis.F.value,
        birth_date=date(1990, 5, 1),
        height_cm=168.0,
        activity_level=ActivityLevel.MODERATE.value,
        goal=Goal.MAINTAIN.value,
    )
    db_session.add(profile)
    db_session.commit()

    duplicate = Profile(
        user_id=user.id,
        sex=Sex.F.value,
        calc_basis=CalcBasis.F.value,
        activity_level=ActivityLevel.LIGHT.value,
        goal=Goal.MAINTAIN.value,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_profile_invalid_enum_rejected(db_session: Session) -> None:
    user = _make_user(db_session)
    bad = Profile(
        user_id=user.id,
        sex="maschio",  # non in {'F','M','other'}
        calc_basis=CalcBasis.M.value,
        activity_level=ActivityLevel.MODERATE.value,
        goal=Goal.MAINTAIN.value,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_profile_height_must_be_positive(db_session: Session) -> None:
    user = _make_user(db_session)
    bad = Profile(
        user_id=user.id,
        sex=Sex.M.value,
        calc_basis=CalcBasis.M.value,
        height_cm=-10.0,
        activity_level=ActivityLevel.LIGHT.value,
        goal=Goal.MAINTAIN.value,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_food_portion_diary_entry_grams_positive(db_session: Session) -> None:
    user = _make_user(db_session)
    food = _make_food(db_session)
    portion = Portion(food_id=food.id, label="piatto medio", grams=80.0)
    db_session.add(portion)
    db_session.commit()

    entry = DiaryEntry(
        user_id=user.id,
        consumed_at=datetime.now(timezone.utc),
        meal=Meal.LUNCH.value,
        food_id=food.id,
        grams=0,  # violazione CHECK grams > 0
    )
    db_session.add(entry)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_diary_entry_invalid_meal_rejected(db_session: Session) -> None:
    user = _make_user(db_session)
    food = _make_food(db_session)
    entry = DiaryEntry(
        user_id=user.id,
        consumed_at=datetime.now(timezone.utc),
        meal="colazione",  # italiano: non nell'enum
        food_id=food.id,
        grams=100,
    )
    db_session.add(entry)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_delete_user_cascades_to_diary(db_session: Session) -> None:
    user = _make_user(db_session)
    food = _make_food(db_session)
    db_session.add(
        DiaryEntry(
            user_id=user.id,
            consumed_at=datetime.now(timezone.utc),
            meal=Meal.DINNER.value,
            food_id=food.id,
            grams=120,
        )
    )
    db_session.add(
        ChatMessage(user_id=user.id, role=ChatRole.USER.value, content="ciao")
    )
    db_session.add(
        WeightLog(user_id=user.id, measured_at=date.today(), weight_kg=70.0)
    )
    db_session.add(
        PreferenceItem(user_id=user.id, kind=PrefKind.LIKED.value, value="pasta")
    )
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(DiaryEntry).count() == 0
    assert db_session.query(ChatMessage).count() == 0
    assert db_session.query(WeightLog).count() == 0
    assert db_session.query(PreferenceItem).count() == 0
    # Il food invece deve rimanere (alimento personale, autore SET NULL).
    surviving = db_session.query(Food).one()
    assert surviving.id == food.id


def test_food_with_diary_entries_cannot_be_deleted(db_session: Session) -> None:
    user = _make_user(db_session)
    food = _make_food(db_session)
    db_session.add(
        DiaryEntry(
            user_id=user.id,
            consumed_at=datetime.now(timezone.utc),
            meal=Meal.LUNCH.value,
            food_id=food.id,
            grams=100,
        )
    )
    db_session.commit()

    db_session.delete(food)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_weight_logs_unique_per_day(db_session: Session) -> None:
    user = _make_user(db_session)
    today = date.today()
    db_session.add(WeightLog(user_id=user.id, measured_at=today, weight_kg=70.0))
    db_session.commit()
    db_session.add(WeightLog(user_id=user.id, measured_at=today, weight_kg=70.5))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_preference_items_unique_triple(db_session: Session) -> None:
    user = _make_user(db_session)
    db_session.add(
        PreferenceItem(user_id=user.id, kind=PrefKind.LIKED.value, value="pasta")
    )
    db_session.commit()
    db_session.add(
        PreferenceItem(user_id=user.id, kind=PrefKind.LIKED.value, value="pasta")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Liked vs avoided dello stesso valore: ammesso (kind diverso).
    db_session.add(
        PreferenceItem(user_id=user.id, kind=PrefKind.AVOIDED.value, value="pasta")
    )
    db_session.commit()
