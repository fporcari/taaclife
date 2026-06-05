from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_user, get_db
from app.models import DiaryEntry, User
from app.schemas.summary import DailyBalanceOut, NeedsOut, WeekSummaryOut
from app.summary.adapter import build_core_profile, entries_to_core_items
from core.nutrition import (
    ProfileIncompleteError,
    compute_daily_balance,
    compute_needs,
)

router = APIRouter(prefix="/summary", tags=["summary"])

WEEK_DAYS = 7


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _fetch_entries_in_range(
    db: Session, user_id: str, start: datetime, end: datetime
) -> list[DiaryEntry]:
    stmt = (
        select(DiaryEntry)
        .options(selectinload(DiaryEntry.food))
        .where(
            DiaryEntry.user_id == user_id,
            DiaryEntry.consumed_at >= start,
            DiaryEntry.consumed_at < end,
        )
    )
    return list(db.execute(stmt).scalars().all())


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


@router.get("/needs", response_model=NeedsOut)
def get_needs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NeedsOut:
    """Fabbisogno energetico dell'utente, dal motore.

    Se il profilo e' incompleto (manca peso/altezza/eta'), risponde 422
    indicando il campo mancante. Mai numero finto (vincolo §2).
    """
    core_profile = build_core_profile(db, current_user, _today_utc())
    try:
        needs = compute_needs(core_profile)
    except ProfileIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "profilo incompleto", "missing": exc.missing},
        ) from exc
    return NeedsOut.from_core(needs)


@router.get("/day", response_model=DailyBalanceOut)
def get_day_summary(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyBalanceOut:
    """Bilancio giornaliero. Tutti i numeri provengono dal motore."""
    day = date_ if date_ is not None else _today_utc()
    core_profile = build_core_profile(db, current_user, day)
    try:
        needs = compute_needs(core_profile)
    except ProfileIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "profilo incompleto", "missing": exc.missing},
        ) from exc

    start, end = _day_bounds(day)
    entries = _fetch_entries_in_range(db, current_user.id, start, end)
    items = entries_to_core_items(entries)
    balance = compute_daily_balance(items, needs)
    return DailyBalanceOut.from_core(day, balance)


@router.get("/week", response_model=WeekSummaryOut)
def get_week_summary(
    from_: date | None = Query(default=None, alias="from"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeekSummaryOut:
    """Bilancio settimanale: 7 giorni a partire da `from` (default oggi).

    Ritorna sempre 7 `DailyBalance`, anche per i giorni vuoti. Tutti i
    numeri vengono dal motore (`compute_daily_balance` per ogni giorno).
    """
    start_day = from_ if from_ is not None else _today_utc()
    end_day = start_day + timedelta(days=WEEK_DAYS - 1)

    core_profile = build_core_profile(db, current_user, end_day)
    try:
        needs = compute_needs(core_profile)
    except ProfileIncompleteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "profilo incompleto", "missing": exc.missing},
        ) from exc

    # Una sola query per i 7 giorni, poi raggruppo per data.
    range_start, _ = _day_bounds(start_day)
    range_end = range_start + timedelta(days=WEEK_DAYS)
    entries = _fetch_entries_in_range(db, current_user.id, range_start, range_end)

    by_day: dict[date, list[DiaryEntry]] = {
        start_day + timedelta(days=i): [] for i in range(WEEK_DAYS)
    }
    for entry in entries:
        day = entry.consumed_at.astimezone(timezone.utc).date()
        if day in by_day:
            by_day[day].append(entry)

    days_out: list[DailyBalanceOut] = []
    for i in range(WEEK_DAYS):
        day = start_day + timedelta(days=i)
        items = entries_to_core_items(by_day[day])
        balance = compute_daily_balance(items, needs)
        days_out.append(DailyBalanceOut.from_core(day, balance))

    return WeekSummaryOut(
        from_date=start_day,
        to_date=end_day,
        needs=NeedsOut.from_core(needs),
        days=days_out,
    )
