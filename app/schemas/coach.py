from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def _not_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("messaggio vuoto")
        return value


class ChatOut(BaseModel):
    user_message_id: int
    assistant_message_id: int
    reply: str
    needs_missing: str | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime
