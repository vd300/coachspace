from __future__ import annotations

from pydantic import BaseModel, Field


class MessagePayload(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=2000)
