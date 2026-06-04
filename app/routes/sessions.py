from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.dependencies import current_user, require_role
from app.schemas.sessions import SessionPayload
from app.services import session_service


router = APIRouter(prefix="/api")


@router.post("/live-sessions")
def create_live_session(
    payload: SessionPayload,
    user: Annotated[dict[str, Any], Depends(require_role("teacher"))],
) -> dict[str, Any]:
    return session_service.create_live_session(payload, user)


@router.get("/live-sessions")
def list_live_sessions(user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    return session_service.list_live_sessions(user)


@router.post("/live-sessions/{session_id}/book")
def book_session(
    session_id: int,
    user: Annotated[dict[str, Any], Depends(require_role("student"))],
) -> dict[str, Any]:
    return session_service.book_session(session_id, user)


@router.get("/bookings")
def list_bookings(user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    return session_service.list_bookings(user)
