from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.core.time import parse_iso_datetime, utc_now
from app.db.session import db
from app.repositories import bookings as booking_repository
from app.repositories import sessions as session_repository
from app.schemas.sessions import SessionPayload


def get_session_row_or_404(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row = session_repository.get_session_row(conn, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


def create_live_session(payload: SessionPayload, user: dict[str, Any]) -> dict[str, Any]:
    starts_at = parse_iso_datetime(payload.starts_at)
    if starts_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Session must be scheduled in the future")
    meeting_url = payload.meeting_url or f"https://meet.jit.si/coaching-{uuid.uuid4().hex[:12]}"
    with db() as conn:
        row = session_repository.create_live_session(
            conn,
            teacher_id=user["id"],
            title=payload.title,
            description=payload.description,
            starts_at=starts_at.isoformat(),
            duration_minutes=payload.duration_minutes,
            meeting_url=meeting_url,
            capacity=payload.capacity,
            created_at=utc_now(),
        )
    return session_repository.session_response(row, user)


def list_live_sessions(user: dict[str, Any]) -> list[dict[str, Any]]:
    with db() as conn:
        rows = session_repository.list_live_sessions(conn, user["id"])
    return [session_repository.session_response(row, user) for row in rows]


def book_session(session_id: int, user: dict[str, Any]) -> dict[str, Any]:
    with db() as conn:
        row = get_session_row_or_404(conn, session_id)
        if parse_iso_datetime(row["starts_at"]) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Cannot book a session that has already started")
        if row["booked_count"] >= row["capacity"]:
            raise HTTPException(status_code=409, detail="Session is fully booked")
        try:
            booking = booking_repository.create_booking(
                conn,
                session_id=session_id,
                student_id=user["id"],
                created_at=utc_now(),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="You already booked this session") from exc
    return dict(booking)


def list_bookings(user: dict[str, Any]) -> list[dict[str, Any]]:
    with db() as conn:
        rows = booking_repository.list_bookings(conn, user)
    return [dict(row) for row in rows]
