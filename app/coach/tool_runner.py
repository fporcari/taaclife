"""Execution dei tool esposti al coach.

Confine: `core.coach_tools` definisce gli schema; qui c'e' l'execution
con DB + motore. Tutti i tool sono SCOPED sull'utente passato al
costruttore: il `user_id` non viene mai letto dall'input del tool
(vincolo CLAUDE.md §3).
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import DiaryEntry, Food, Meal, User
from app.summary.adapter import build_core_profile, entries_to_core_items
from core.coach_tools import (
    TOOL_ADD_DIARY_ENTRY,
    TOOL_GET_DAILY_BALANCE,
    TOOL_GET_WEEKLY_SUMMARY,
    TOOL_NAMES,
    TOOL_SEARCH_FOOD,
)
from core.nutrition import (
    DiaryItem,
    FoodNutrients,
    ProfileIncompleteError,
    compute_daily_balance,
    compute_item_nutrients,
    compute_needs,
)

WEEK_DAYS = 7
MAX_SEARCH_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10


class ToolError(ValueError):
    """Errore "di dominio" durante l'esecuzione di un tool. Viene
    serializzato come `{"error": "..."}` nel tool_result per Claude."""


class UnknownToolError(ToolError):
    pass


def _parse_date(raw: str | None, fallback: date) -> date:
    if raw is None:
        return fallback
    return date.fromisoformat(raw)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _serialize_food(food: Food) -> dict:
    return {
        "id": food.id,
        "name": food.name,
        "category": food.category,
        "kcal_100g": food.kcal_100g,
        "protein_100g": food.protein_100g,
        "carbs_100g": food.carbs_100g,
        "fat_100g": food.fat_100g,
        "fiber_100g": food.fiber_100g,
        "is_public": food.is_public,
    }


def _serialize_balance(day: date, balance) -> dict:
    return {
        "date": day.isoformat(),
        "totals": asdict(balance.totals),
        "target_kcal": balance.target_kcal,
        "kcal_difference": balance.kcal_difference,
        "macros_percent": asdict(balance.macros_percent),
    }


class ToolRunner:
    """Esegue i tool per conto dell'utente del token.

    Una nuova istanza per ogni chat (porta `user` e `today`).
    """

    def __init__(self, db: Session, user: User, today: date) -> None:
        self.db = db
        self.user = user
        self.today = today

    def run(self, name: str, tool_input: dict | None) -> dict:
        if name not in TOOL_NAMES:
            raise UnknownToolError(f"tool sconosciuto: {name}")
        payload = tool_input or {}
        if name == TOOL_GET_DAILY_BALANCE:
            return self._get_daily_balance(payload)
        if name == TOOL_GET_WEEKLY_SUMMARY:
            return self._get_weekly_summary(payload)
        if name == TOOL_SEARCH_FOOD:
            return self._search_food(payload)
        if name == TOOL_ADD_DIARY_ENTRY:
            return self._add_diary_entry(payload)
        # Non dovremmo arrivarci (gia' filtrato da TOOL_NAMES).
        raise UnknownToolError(name)

    # ---------- Implementazioni dei tool ----------

    def _needs_or_error(self) -> tuple[object | None, dict | None]:
        core_profile = build_core_profile(self.db, self.user, self.today)
        try:
            return compute_needs(core_profile), None
        except ProfileIncompleteError as exc:
            return None, {
                "error": "profilo incompleto",
                "missing": exc.missing,
            }

    def _get_daily_balance(self, payload: dict) -> dict:
        day = _parse_date(payload.get("date"), self.today)
        needs, err = self._needs_or_error()
        if err is not None:
            return err
        start, end = _day_bounds(day)
        entries = self._fetch_entries(start, end)
        balance = compute_daily_balance(entries_to_core_items(entries), needs)
        return _serialize_balance(day, balance)

    def _get_weekly_summary(self, payload: dict) -> dict:
        from_raw = payload.get("from_date")
        start_day = (
            _parse_date(from_raw, self.today - timedelta(days=WEEK_DAYS - 1))
        )
        end_day = start_day + timedelta(days=WEEK_DAYS - 1)
        needs, err = self._needs_or_error()
        if err is not None:
            return err
        range_start, _ = _day_bounds(start_day)
        range_end = range_start + timedelta(days=WEEK_DAYS)
        entries = self._fetch_entries(range_start, range_end)

        by_day: dict[date, list[DiaryEntry]] = {
            start_day + timedelta(days=i): [] for i in range(WEEK_DAYS)
        }
        for entry in entries:
            day = entry.consumed_at.astimezone(timezone.utc).date()
            if day in by_day:
                by_day[day].append(entry)

        days: list[dict] = []
        for i in range(WEEK_DAYS):
            day = start_day + timedelta(days=i)
            balance = compute_daily_balance(
                entries_to_core_items(by_day[day]), needs
            )
            days.append(_serialize_balance(day, balance))

        return {
            "from_date": start_day.isoformat(),
            "to_date": end_day.isoformat(),
            "days": days,
        }

    def _search_food(self, payload: dict) -> dict:
        query = (payload.get("query") or "").strip()
        if not query:
            raise ToolError("query mancante per search_food")
        category = payload.get("category")
        limit = int(payload.get("limit") or DEFAULT_SEARCH_LIMIT)
        if limit < 1 or limit > MAX_SEARCH_LIMIT:
            raise ToolError(f"limit fuori range (1..{MAX_SEARCH_LIMIT})")

        stmt = (
            select(Food)
            .where(
                or_(Food.is_public.is_(True), Food.created_by == self.user.id)
            )
            .where(Food.name.ilike(f"%{query}%"))
        )
        if category:
            stmt = stmt.where(Food.category == category)
        stmt = stmt.order_by(Food.name).limit(limit)

        foods = self.db.execute(stmt).scalars().all()
        return {
            "query": query,
            "category": category,
            "count": len(foods),
            "results": [_serialize_food(f) for f in foods],
        }

    def _add_diary_entry(self, payload: dict) -> dict:
        food_id = payload.get("food_id")
        grams = payload.get("grams")
        meal_raw = payload.get("meal")
        confirmed = bool(payload.get("confirmed", False))
        consumed_at_raw = payload.get("consumed_at")

        if food_id is None or grams is None or meal_raw is None:
            raise ToolError("food_id, grams e meal sono obbligatori")
        try:
            meal = Meal(meal_raw)
        except ValueError:
            raise ToolError(
                f"meal non valido: {meal_raw!r} (atteso: breakfast/lunch/dinner/snack)"
            )
        if grams <= 0:
            raise ToolError("grams deve essere > 0")

        # Visibilita': pubblico o personale dell'utente.
        food = self.db.execute(
            select(Food).where(
                Food.id == food_id,
                or_(Food.is_public.is_(True), Food.created_by == self.user.id),
            )
        ).scalar_one_or_none()
        if food is None:
            return {"status": "not_found", "food_id": food_id}

        # Calcolo dei numeri della preview tramite il motore.
        preview_macro = compute_item_nutrients(
            DiaryItem(
                food=FoodNutrients(
                    kcal_100g=food.kcal_100g,
                    protein_100g=food.protein_100g,
                    carbs_100g=food.carbs_100g,
                    fat_100g=food.fat_100g,
                    fiber_100g=food.fiber_100g,
                ),
                grams=float(grams),
            )
        )

        consumed_at = (
            datetime.fromisoformat(consumed_at_raw)
            if consumed_at_raw
            else datetime.now(timezone.utc)
        )
        if consumed_at.tzinfo is None:
            consumed_at = consumed_at.replace(tzinfo=timezone.utc)

        draft = {
            "food_id": food.id,
            "food_name": food.name,
            "grams": float(grams),
            "meal": meal.value,
            "consumed_at": consumed_at.isoformat(),
        }
        preview = {
            "kcal": preview_macro.kcal,
            "protein_g": preview_macro.protein_g,
            "carbs_g": preview_macro.carbs_g,
            "fat_g": preview_macro.fat_g,
            "fiber_g": preview_macro.fiber_g,
        }

        if not confirmed:
            return {
                "status": "needs_confirmation",
                "draft": draft,
                "preview": preview,
                "message": (
                    "Conferma esplicita dell'utente richiesta prima di scrivere. "
                    "Mostra la preview e chiedi conferma."
                ),
            }

        entry = DiaryEntry(
            user_id=self.user.id,
            consumed_at=consumed_at,
            meal=meal.value,
            food_id=food.id,
            grams=float(grams),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)

        return {
            "status": "added",
            "entry_id": entry.id,
            "draft": draft,
            "totals_added": preview,
        }

    def _fetch_entries(self, start: datetime, end: datetime) -> list[DiaryEntry]:
        stmt = (
            select(DiaryEntry)
            .options(selectinload(DiaryEntry.food))
            .where(
                DiaryEntry.user_id == self.user.id,
                DiaryEntry.consumed_at >= start,
                DiaryEntry.consumed_at < end,
            )
            .order_by(DiaryEntry.consumed_at)
        )
        return list(self.db.execute(stmt).scalars().all())
