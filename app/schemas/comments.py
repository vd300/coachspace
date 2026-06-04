from __future__ import annotations

from pydantic import BaseModel, Field


class CommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=1200)
