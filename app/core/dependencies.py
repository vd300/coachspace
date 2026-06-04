from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from app.core.security import decode_token
from app.db.session import db
from app.repositories.users import clean_user, get_user_by_id


def current_user(request: Request) -> dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_token(auth.removeprefix("Bearer ").strip())
    with db() as conn:
        row = get_user_by_id(conn, payload["sub"])
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return clean_user(row)


def require_role(role: str):
    def dependency(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
        if user["role"] != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{role.title()} role required")
        return user

    return dependency
