from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends

from app.core.dependencies import current_user
from app.services import auth_service


router = APIRouter(prefix="/api")


@router.get("/users")
def list_users(
    user: Annotated[dict[str, Any], Depends(current_user)],
    role: Literal["student", "teacher"] | None = None,
) -> list[dict[str, Any]]:
    return auth_service.list_users(role)
