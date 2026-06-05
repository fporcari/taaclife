"""Aggrega DB + motore in un `core.coach.CoachContext`.

Confine architetturale: `core.coach` non sa cosa sia SQLAlchemy.
Qui mappiamo modelli DB e dataclass del motore nei tipi richiesti.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatMessage, DiaryEntry, PrefKind, PreferenceItem, Profile, User
from app.summary.adapter import build_core_profile, entries_to_core_items
from core.coach import (
    CoachContext,
    DailyBalanceSummary,
    DiaryItemSummary,
    HistoryMessage,
    MacroSummary,
    NeedsSummary,
    PreferencesSummary,
    ProfileSummary,
    truncate_history,
)
from core.nutrition import (
    ProfileIncompleteError,
    compute_daily_balance,
    compute_needs,
)

RECENT_DIARY_LIMIT = 20
HISTORY_LIMIT = 20
WEEK_DAYS = 7


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _fetch_entries(
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
        .order_by(DiaryEntry.consumed_at)
    )
    return list(db.execute(stmt).scalars().all())


def build_coach_context(db: Session, user: User, today: date) -> CoachContext:
    core_profile = build_core_profile(db, user, today)

    profile_summary = ProfileSummary(
        age_years=core_profile.age_years,
        sex_identity=_user_identity_sex(db, user.id),
        calc_basis=core_profile.calc_basis.value if core_profile.calc_basis else None,
        height_cm=core_profile.height_cm,
        weight_kg=core_profile.weight_kg,
        activity_level=(
            core_profile.activity_level.value if core_profile.activity_level else None
        ),
        goal=(core_profile.goal.value if core_profile.goal else "maintain"),
    )

    needs_summary: NeedsSummary | None
    needs_missing: str | None
    needs_obj = None
    try:
        needs_obj = compute_needs(core_profile)
        needs_summary = NeedsSummary(
            bmr=needs_obj.bmr,
            tdee=needs_obj.tdee,
            target_kcal=needs_obj.target_kcal,
            goal_applied=needs_obj.goal_applied.value,
            calc_basis_assumed=needs_obj.calc_basis_assumed,
            activity_assumed=needs_obj.activity_assumed,
        )
        needs_missing = None
    except ProfileIncompleteError as exc:
        needs_summary = None
        needs_missing = exc.missing

    # Today balance: solo se needs c'e'.
    today_balance: DailyBalanceSummary | None = None
    if needs_obj is not None:
        start, end = _day_bounds(today)
        entries_today = _fetch_entries(db, user.id, start, end)
        balance = compute_daily_balance(entries_to_core_items(entries_today), needs_obj)
        today_balance = DailyBalanceSummary(
            date=today,
            totals=MacroSummary(
                kcal=balance.totals.kcal,
                protein_g=balance.totals.protein_g,
                carbs_g=balance.totals.carbs_g,
                fat_g=balance.totals.fat_g,
                fiber_g=balance.totals.fiber_g,
            ),
            target_kcal=balance.target_kcal,
            kcal_difference=balance.kcal_difference,
            protein_pct=balance.macros_percent.protein_pct,
            carbs_pct=balance.macros_percent.carbs_pct,
            fat_pct=balance.macros_percent.fat_pct,
        )

    # Settimana: 6 giorni fa + oggi -> 7 totali.
    week_balances: list[DailyBalanceSummary] = []
    if needs_obj is not None:
        week_start = today - timedelta(days=WEEK_DAYS - 1)
        week_range_start, _ = _day_bounds(week_start)
        week_range_end = week_range_start + timedelta(days=WEEK_DAYS)
        entries_week = _fetch_entries(db, user.id, week_range_start, week_range_end)
        by_day: dict[date, list[DiaryEntry]] = {
            week_start + timedelta(days=i): [] for i in range(WEEK_DAYS)
        }
        for entry in entries_week:
            day = entry.consumed_at.astimezone(timezone.utc).date()
            if day in by_day:
                by_day[day].append(entry)
        for i in range(WEEK_DAYS):
            day = week_start + timedelta(days=i)
            balance = compute_daily_balance(
                entries_to_core_items(by_day[day]), needs_obj
            )
            week_balances.append(
                DailyBalanceSummary(
                    date=day,
                    totals=MacroSummary(
                        kcal=balance.totals.kcal,
                        protein_g=balance.totals.protein_g,
                        carbs_g=balance.totals.carbs_g,
                        fat_g=balance.totals.fat_g,
                        fiber_g=balance.totals.fiber_g,
                    ),
                    target_kcal=balance.target_kcal,
                    kcal_difference=balance.kcal_difference,
                    protein_pct=balance.macros_percent.protein_pct,
                    carbs_pct=balance.macros_percent.carbs_pct,
                    fat_pct=balance.macros_percent.fat_pct,
                )
            )

    # Ultime voci di diario (ovunque nel tempo, fino a RECENT_DIARY_LIMIT).
    recent_stmt = (
        select(DiaryEntry)
        .options(selectinload(DiaryEntry.food))
        .where(DiaryEntry.user_id == user.id)
        .order_by(DiaryEntry.consumed_at.desc())
        .limit(RECENT_DIARY_LIMIT)
    )
    recent_entries = list(db.execute(recent_stmt).scalars().all())
    recent_diary = tuple(
        DiaryItemSummary(
            consumed_at=e.consumed_at.astimezone(timezone.utc).isoformat(),
            meal=e.meal,
            food_name=e.food.name,
            grams=e.grams,
        )
        for e in recent_entries
    )

    # Preferenze.
    pref_rows = db.execute(
        select(PreferenceItem).where(PreferenceItem.user_id == user.id)
    ).scalars().all()
    liked = tuple(p.value for p in pref_rows if p.kind == PrefKind.LIKED.value)
    avoided = tuple(p.value for p in pref_rows if p.kind == PrefKind.AVOIDED.value)

    # Storico chat (ultimi HISTORY_LIMIT, ordine cronologico).
    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_LIMIT)
    )
    history_rows = list(db.execute(history_stmt).scalars().all())
    history_rows.reverse()  # ordine cronologico
    history = tuple(HistoryMessage(role=m.role, content=m.content) for m in history_rows)
    history = truncate_history(history, HISTORY_LIMIT)

    return CoachContext(
        today=today,
        profile=profile_summary,
        needs=needs_summary,
        needs_missing=needs_missing,
        today_balance=today_balance,
        week_balances=tuple(week_balances),
        recent_diary=recent_diary,
        preferences=PreferencesSummary(liked=liked, avoided=avoided),
        history=history,
    )


def _user_identity_sex(db: Session, user_id: str) -> str | None:
    """Recupera il campo `sex` (identita') dal profilo, distinto da
    `calc_basis` (parametro Mifflin)."""
    return db.execute(
        select(Profile.sex).where(Profile.user_id == user_id)
    ).scalar_one_or_none()
