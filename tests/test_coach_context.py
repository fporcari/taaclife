"""Test del builder di contesto del coach.

Verifica:
- profile/needs popolati con valori reali via motore;
- profilo incompleto -> `needs=None`, `needs_missing` valorizzato;
- today_balance e week_balances calcolati dal motore;
- recent_diary troncato;
- liked/avoided separati;
- storico chat troncato e in ordine cronologico.
"""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.coach.context_builder import (
    HISTORY_LIMIT,
    RECENT_DIARY_LIMIT,
    WEEK_DAYS,
    build_coach_context,
)
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
    PrefKind,
    PreferenceItem,
    Profile,
    Sex,
    User,
    WeightLog,
)
from app.security import hash_password


def _user(db: Session, email: str = "alice@example.com") -> User:
    user = User(email=email, password_hash=hash_password("abcdefgh"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _food(db: Session, name: str = "Pasta") -> Food:
    food = Food(
        name=name, category="cereali",
        kcal_100g=353, protein_100g=12.5, carbs_100g=71.2,
        fat_100g=1.4, fiber_100g=2.7,
        source=FoodSource.CREA.value, is_public=True,
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


def _complete_profile(db: Session, user_id: str, today: date) -> None:
    db.add_all([
        Profile(
            user_id=user_id,
            sex=Sex.OTHER.value,
            calc_basis=CalcBasis.F.value,
            birth_date=date(today.year - 30, today.month, today.day),
            height_cm=165.0,
            activity_level=ActivityLevel.MODERATE.value,
            goal=Goal.MAINTAIN.value,
        ),
        WeightLog(user_id=user_id, measured_at=today, weight_kg=60.0),
    ])
    db.commit()


def test_context_with_complete_profile(db_session: Session) -> None:
    user = _user(db_session)
    today = date(2026, 6, 1)
    _complete_profile(db_session, user.id, today)

    ctx = build_coach_context(db_session, user, today)
    assert ctx.today == today
    assert ctx.profile.age_years == 30
    assert ctx.profile.sex_identity == "other"
    assert ctx.profile.calc_basis == "F"
    assert ctx.profile.height_cm == 165.0
    assert ctx.profile.weight_kg == 60.0
    assert ctx.profile.activity_level == "moderate"
    assert ctx.profile.goal == "maintain"
    assert ctx.needs is not None
    assert ctx.needs_missing is None
    assert ctx.needs.bmr == pytest.approx(1320.25)
    assert ctx.needs.tdee == pytest.approx(2046.3875)
    assert ctx.today_balance is not None
    assert len(ctx.week_balances) == WEEK_DAYS


def test_context_with_incomplete_profile_reports_missing(db_session: Session) -> None:
    user = _user(db_session)
    today = date(2026, 6, 1)
    # Niente profilo, niente weight: manca peso per primo.
    ctx = build_coach_context(db_session, user, today)
    assert ctx.needs is None
    assert ctx.needs_missing == "weight_kg"
    # Senza needs, niente today_balance ne' week_balances.
    assert ctx.today_balance is None
    assert ctx.week_balances == ()


def test_context_uses_engine_numbers_for_today(db_session: Session) -> None:
    """Il bilancio di oggi deve combaciare esattamente coi numeri prodotti
    dal motore sui food+grams reali (non somme fatte a mano)."""
    user = _user(db_session)
    today = date(2026, 6, 1)
    _complete_profile(db_session, user.id, today)
    food = _food(db_session)

    # 80g pasta a pranzo, oggi.
    db_session.add(DiaryEntry(
        user_id=user.id,
        consumed_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        meal=Meal.LUNCH.value,
        food_id=food.id,
        grams=80,
    ))
    db_session.commit()

    ctx = build_coach_context(db_session, user, today)
    assert ctx.today_balance is not None
    # 80/100 * 353 = 282.4
    assert ctx.today_balance.totals.kcal == pytest.approx(282.4)


def test_context_truncates_recent_diary(db_session: Session) -> None:
    user = _user(db_session)
    today = date(2026, 6, 1)
    _complete_profile(db_session, user.id, today)
    food = _food(db_session)

    # Crea piu' voci di RECENT_DIARY_LIMIT, sparse all'indietro.
    for i in range(RECENT_DIARY_LIMIT + 5):
        db_session.add(DiaryEntry(
            user_id=user.id,
            consumed_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
            + (i * (datetime(2026, 5, 1, 12, 0) - datetime(2026, 5, 1, 11, 0))),
            meal=Meal.LUNCH.value,
            food_id=food.id,
            grams=100 + i,
        ))
    db_session.commit()

    ctx = build_coach_context(db_session, user, today)
    assert len(ctx.recent_diary) == RECENT_DIARY_LIMIT
    # In ordine: piu' recente prima.
    grams = [item.grams for item in ctx.recent_diary]
    assert grams == sorted(grams, reverse=True)


def test_context_includes_preferences(db_session: Session) -> None:
    user = _user(db_session)
    today = date(2026, 6, 1)
    _complete_profile(db_session, user.id, today)

    db_session.add_all([
        PreferenceItem(user_id=user.id, kind=PrefKind.LIKED.value, value="pasta"),
        PreferenceItem(user_id=user.id, kind=PrefKind.LIKED.value, value="pesce"),
        PreferenceItem(user_id=user.id, kind=PrefKind.AVOIDED.value, value="cavolfiore"),
    ])
    db_session.commit()

    ctx = build_coach_context(db_session, user, today)
    assert set(ctx.preferences.liked) == {"pasta", "pesce"}
    assert set(ctx.preferences.avoided) == {"cavolfiore"}


def test_context_history_in_chronological_order_and_truncated(db_session: Session) -> None:
    user = _user(db_session)
    today = date(2026, 6, 1)
    _complete_profile(db_session, user.id, today)

    # Inserisco piu' di HISTORY_LIMIT messaggi: devono essere mantenuti
    # solo gli ultimi HISTORY_LIMIT, in ordine cronologico.
    for i in range(HISTORY_LIMIT + 5):
        role = ChatRole.USER if i % 2 == 0 else ChatRole.ASSISTANT
        db_session.add(ChatMessage(
            user_id=user.id,
            role=role.value,
            content=f"msg-{i}",
            created_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
            + (i * (datetime(2026, 5, 1, 12, 1) - datetime(2026, 5, 1, 12, 0))),
        ))
    db_session.commit()

    ctx = build_coach_context(db_session, user, today)
    assert len(ctx.history) == HISTORY_LIMIT
    # Cronologico: msg-5, msg-6, ... fino a msg-(HISTORY_LIMIT+4)
    contents = [m.content for m in ctx.history]
    assert contents[0] == "msg-5"
    assert contents[-1] == f"msg-{HISTORY_LIMIT + 4}"
