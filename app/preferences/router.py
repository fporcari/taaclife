from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import PrefKind, PreferenceItem, User
from app.schemas.preferences import (
    PreferenceItemIn,
    PreferenceItemOut,
    PreferencesOut,
)

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesOut)
def list_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesOut:
    rows = db.execute(
        select(PreferenceItem)
        .where(PreferenceItem.user_id == current_user.id)
        .order_by(PreferenceItem.value)
    ).scalars().all()
    return PreferencesOut(
        liked=[PreferenceItemOut.model_validate(r) for r in rows if r.kind == PrefKind.LIKED.value],
        avoided=[PreferenceItemOut.model_validate(r) for r in rows if r.kind == PrefKind.AVOIDED.value],
    )


@router.post("", response_model=PreferenceItemOut, status_code=status.HTTP_201_CREATED)
def add_preference(
    payload: PreferenceItemIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferenceItemOut:
    item = PreferenceItem(
        user_id=current_user.id,
        kind=payload.kind.value,
        value=payload.value.strip(),
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="preferenza gia' presente",
        )
    db.refresh(item)
    return PreferenceItemOut.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_preference(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    item = db.execute(
        select(PreferenceItem).where(
            PreferenceItem.id == item_id,
            PreferenceItem.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="non trovata")
    db.delete(item)
    db.commit()
