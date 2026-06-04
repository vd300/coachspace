from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.time import parse_iso_datetime


class SessionPayload(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=1200)
    starts_at: str
    duration_minutes: int = Field(ge=15, le=240)
    meeting_url: str | None = Field(default=None, max_length=500)
    capacity: int = Field(default=30, ge=1, le=500)

    @field_validator("starts_at")
    @classmethod
    def starts_at_must_parse(cls, value: str) -> str:
        parse_iso_datetime(value)
        return value
