from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


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
