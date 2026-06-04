from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterPayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["student", "teacher"]


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
