"""Adapter fra modelli DB e dataclass del motore (`core.nutrition`).

Confine architetturale: il motore non importa SQLAlchemy. Qui mappiamo
`User+Profile+WeightLog` -> `core.Profile` e `(DiaryEntry, Food)` ->
`core.DiaryItem`. Tutti i numeri vengono poi prodotti dal motore.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DiaryEntry, Food, Profile, User, WeightLog
from core.nutrition import (
    ActivityLevel,
    DiaryItem,
    FoodNutrients,
    Goal,
    Profile as CoreProfile,
    Sex,
)


def _latest_weight_kg(db: Session, user_id: str) -> float | None:
    stmt = (
        select(WeightLog.weight_kg)
        .where(WeightLog.user_id == user_id)
        .order_by(WeightLog.measured_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _age_years(birth: date | None, today: date) -> int | None:
    if birth is None:
        return None
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years


def build_core_profile(db: Session, user: User, today: date) -> CoreProfile:
    """Aggrega Profile + ultimo WeightLog per produrre un `core.Profile`.

    I valori mancanti restano `None`: e' il motore a decidere se
    sollevare `ProfileIncompleteError` o applicare un fallback
    dichiarato. Mai inventare un default qui (vincolo §2).
    """
    profile: Profile | None = db.execute(
        select(Profile).where(Profile.user_id == user.id)
    ).scalar_one_or_none()

    weight = _latest_weight_kg(db, user.id)

    if profile is None:
        return CoreProfile(
            weight_kg=weight,
            height_cm=None,
            age_years=None,
            calc_basis=None,
            activity_level=None,
            goal=None,
        )

    return CoreProfile(
        weight_kg=weight,
        height_cm=profile.height_cm,
        age_years=_age_years(profile.birth_date, today),
        calc_basis=Sex(profile.calc_basis) if profile.calc_basis else None,
        activity_level=(
            ActivityLevel(profile.activity_level) if profile.activity_level else None
        ),
        goal=Goal(profile.goal) if profile.goal else None,
    )


def entry_to_core_item(entry: DiaryEntry) -> DiaryItem:
    """Converte una `DiaryEntry` (con Food eager-loaded) in `core.DiaryItem`."""
    food: Food = entry.food
    return DiaryItem(
        food=FoodNutrients(
            kcal_100g=food.kcal_100g,
            protein_100g=food.protein_100g,
            carbs_100g=food.carbs_100g,
            fat_100g=food.fat_100g,
            fiber_100g=food.fiber_100g,
        ),
        grams=entry.grams,
    )


def entries_to_core_items(entries: Iterable[DiaryEntry]) -> list[DiaryItem]:
    return [entry_to_core_item(e) for e in entries]
