from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from app.core.security import create_token, hash_password, verify_password
from app.core.time import utc_now
from app.db.session import db
from app.repositories import users as user_repository
from app.schemas.auth import LoginPayload, RegisterPayload


def register_user(payload: RegisterPayload) -> dict[str, Any]:
    with db() as conn:
        try:
            row = user_repository.create_user(
                conn,
                name=payload.name,
                email=payload.email,
                password_hash=hash_password(payload.password),
                role=payload.role,
                created_at=utc_now(),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Email is already registered") from exc
    return {"token": create_token(row), "user": user_repository.clean_user(row)}


def login_user(payload: LoginPayload) -> dict[str, Any]:
    with db() as conn:
        row = user_repository.get_user_by_email(conn, payload.email)
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(row), "user": user_repository.clean_user(row)}


def list_users(role: str | None = None) -> list[dict[str, Any]]:
    with db() as conn:
        rows = user_repository.list_users(conn, role)
    return [user_repository.clean_user(row) for row in rows]
