from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Meal

MAX_FUTURE = timedelta(hours=24)
MAX_PAST = timedelta(days=5 * 365)


class FoodMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str | None


class DiaryEntryIn(BaseModel):
    food_id: int = Field(ge=1)
    grams: float = Field(gt=0)
    meal: Meal
    consumed_at: datetime | None = None

    @field_validator("consumed_at")
    @classmethod
    def _within_reasonable_range(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if value > now + MAX_FUTURE:
            raise ValueError("consumed_at troppo nel futuro")
        if value < now - MAX_PAST:
            raise ValueError("consumed_at troppo nel passato")
        return value


class DiaryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consumed_at: datetime
    meal: str
    grams: float
    food: FoodMini
