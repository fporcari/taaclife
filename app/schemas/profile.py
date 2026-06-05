"""Schemi del profilo utente.

Vincolo §14: identita' (`sex`) e parametro di calcolo Mifflin
(`calc_basis`) sono distinti. Sono esposti come enum separati:
- `sex` accetta {F, M, other}
- `calc_basis` accetta solo {F, M} (Mifflin non ha "other")
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models import ActivityLevel, CalcBasis, Goal, Sex


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    sex: Sex | None
    calc_basis: CalcBasis | None
    birth_date: date | None
    height_cm: float | None
    activity_level: ActivityLevel | None
    goal: Goal


class ProfileUpdateIn(BaseModel):
    """Body per `PUT /profile` (upsert, tutti i campi opzionali).

    `user_id` non e' accettato: viene preso dal token (vincolo
    CLAUDE.md §3).
    """

    sex: Sex | None = None
    calc_basis: CalcBasis | None = None
    birth_date: date | None = None
    height_cm: float | None = Field(default=None, gt=0)
    activity_level: ActivityLevel | None = None
    goal: Goal | None = None
