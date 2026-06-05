from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Meal


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


class DiaryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    consumed_at: datetime
    meal: str
    grams: float
    food: FoodMini
