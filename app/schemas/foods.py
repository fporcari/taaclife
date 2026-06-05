from pydantic import BaseModel, ConfigDict, Field


class PortionIn(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    grams: float = Field(gt=0)


class PortionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    grams: float


class FoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str | None
    kcal_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    fiber_100g: float | None
    source: str
    is_public: bool
    created_by: str | None
    portions: list[PortionOut] = []


class FoodCreateIn(BaseModel):
    """Body per `POST /foods`.

    `source`, `is_public` e `created_by` NON sono accettati dal client:
    li imposta il server (`source='user'`, `is_public=False`,
    `created_by=current_user.id`). Vincolo CLAUDE.md §3.
    """

    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    kcal_100g: float = Field(ge=0)
    protein_100g: float = Field(ge=0)
    carbs_100g: float = Field(ge=0)
    fat_100g: float = Field(ge=0)
    fiber_100g: float | None = Field(default=None, ge=0)
    portions: list[PortionIn] = Field(default_factory=list)
