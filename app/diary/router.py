from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_user, get_db
from app.models import DiaryEntry, Food, User
from app.schemas.diary import DiaryEntryIn, DiaryEntryOut

router = APIRouter(prefix="/diary", tags=["diary"])


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _user_can_use_food(db: Session, user: User, food_id: int) -> Food | None:
    stmt = select(Food).where(
        Food.id == food_id,
        or_(Food.is_public.is_(True), Food.created_by == user.id),
    )
    return db.execute(stmt).scalar_one_or_none()


@router.post("", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED)
def create_diary_entry(
    payload: DiaryEntryIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiaryEntryOut:
    food = _user_can_use_food(db, current_user, payload.food_id)
    if food is None:
        # 404 anche per "esiste ma di altro utente": niente info leak.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="alimento non trovato",
        )

    consumed_at = payload.consumed_at or datetime.now(timezone.utc)
    if consumed_at.tzinfo is None:
        consumed_at = consumed_at.replace(tzinfo=timezone.utc)

    entry = DiaryEntry(
        user_id=current_user.id,
        consumed_at=consumed_at,
        meal=payload.meal.value,
        food_id=food.id,
        grams=payload.grams,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    # Forza il caricamento del food per la response.
    db.refresh(entry, attribute_names=["food"])
    return DiaryEntryOut.model_validate(entry)


@router.get("", response_model=list[DiaryEntryOut])
def list_diary_for_day(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DiaryEntryOut]:
    day = date_ if date_ is not None else datetime.now(timezone.utc).date()
    start, end = _day_bounds(day)
    stmt = (
        select(DiaryEntry)
        .options(selectinload(DiaryEntry.food))
        .where(
            DiaryEntry.user_id == current_user.id,
            DiaryEntry.consumed_at >= start,
            DiaryEntry.consumed_at < end,
        )
        .order_by(DiaryEntry.consumed_at)
    )
    entries = db.execute(stmt).scalars().all()
    return [DiaryEntryOut.model_validate(e) for e in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(DiaryEntry).where(
        DiaryEntry.id == entry_id,
        DiaryEntry.user_id == current_user.id,
    )
    entry = db.execute(stmt).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="non trovato")
    db.delete(entry)
    db.commit()
