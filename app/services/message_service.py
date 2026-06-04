from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.time import utc_now
from app.db.session import db
from app.repositories import messages as message_repository
from app.repositories import users as user_repository
from app.schemas.messages import MessagePayload


def send_message(payload: MessagePayload, user: dict[str, Any]) -> dict[str, Any]:
    if payload.recipient_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot message yourself")
    with db() as conn:
        recipient = user_repository.get_user_by_id(conn, payload.recipient_id)
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        row = message_repository.create_message(
            conn,
            sender_id=user["id"],
            recipient_id=payload.recipient_id,
            body=payload.body,
            created_at=utc_now(),
        )
    return dict(row)


def list_messages(user: dict[str, Any], with_user_id: int) -> list[dict[str, Any]]:
    with db() as conn:
        peer = user_repository.get_user_by_id(conn, with_user_id)
        if not peer:
            raise HTTPException(status_code=404, detail="User not found")
        rows = message_repository.list_messages(conn, user_id=user["id"], peer_id=with_user_id)
        message_repository.mark_messages_read(
            conn,
            recipient_id=user["id"],
            sender_id=with_user_id,
            read_at=utc_now(),
        )
    return [dict(row) for row in rows]


def conversations(user: dict[str, Any]) -> list[dict[str, Any]]:
    with db() as conn:
        rows = message_repository.list_conversations(conn, user["id"])
    return [dict(row) for row in rows]
