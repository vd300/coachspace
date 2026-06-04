from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import current_user
from app.schemas.messages import MessagePayload
from app.services import message_service


router = APIRouter(prefix="/api")


@router.post("/messages")
def send_message(
    payload: MessagePayload,
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> dict[str, Any]:
    return message_service.send_message(payload, user)


@router.get("/messages")
def list_messages(
    user: Annotated[dict[str, Any], Depends(current_user)],
    with_user_id: int = Query(..., gt=0),
) -> list[dict[str, Any]]:
    return message_service.list_messages(user, with_user_id)


@router.get("/conversations")
def conversations(user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    return message_service.conversations(user)
