from pydantic import BaseModel, ConfigDict, Field

from app.models import PrefKind


class PreferenceItemIn(BaseModel):
    kind: PrefKind
    value: str = Field(min_length=1, max_length=128)


class PreferenceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    value: str


class PreferencesOut(BaseModel):
    liked: list[PreferenceItemOut]
    avoided: list[PreferenceItemOut]
