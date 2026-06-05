from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class WeightLogIn(BaseModel):
    weight_kg: float = Field(gt=0)
    measured_at: date | None = None


class WeightLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    measured_at: date
    weight_kg: float
