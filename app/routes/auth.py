from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import current_user
from app.schemas.auth import LoginPayload, RegisterPayload
from app.services import auth_service


router = APIRouter(prefix="/api")


@router.post("/auth/register")
def register(payload: RegisterPayload) -> dict[str, Any]:
    return auth_service.register_user(payload)


@router.post("/auth/login")
def login(payload: LoginPayload) -> dict[str, Any]:
    return auth_service.login_user(payload)


@router.get("/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return user
