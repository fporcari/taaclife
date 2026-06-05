from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Goal, Profile, User
from app.schemas.profile import ProfileOut, ProfileUpdateIn

router = APIRouter(prefix="/profile", tags=["profile"])


def _empty_profile_view(user: User) -> ProfileOut:
    """Vista "scheletro" quando l'utente non ha ancora un profilo.

    Default etico §7: `goal=MAINTAIN`. Tutti gli altri campi `None`:
    il motore sollevera' `ProfileIncompleteError` finche' peso/altezza
    /eta' non sono presenti.
    """
    return ProfileOut(
        user_id=user.id,
        sex=None,
        calc_basis=None,
        birth_date=None,
        height_cm=None,
        activity_level=None,
        goal=Goal.MAINTAIN,
    )


@router.get("", response_model=ProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileOut:
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    ).scalar_one_or_none()
    if profile is None:
        return _empty_profile_view(current_user)
    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut)
def upsert_profile(
    payload: ProfileUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileOut:
    profile = db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    ).scalar_one_or_none()

    fields = {
        "sex": payload.sex.value if payload.sex else None,
        "calc_basis": payload.calc_basis.value if payload.calc_basis else None,
        "birth_date": payload.birth_date,
        "height_cm": payload.height_cm,
        "activity_level": payload.activity_level.value if payload.activity_level else None,
        "goal": payload.goal.value if payload.goal else Goal.MAINTAIN.value,
    }

    if profile is None:
        profile = Profile(user_id=current_user.id, **fields)
        db.add(profile)
    else:
        for key, value in fields.items():
            setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return ProfileOut.model_validate(profile)
