from __future__ import annotations

import sqlite3
from typing import Any


def session_response(row: sqlite3.Row, user: dict[str, Any] | None = None) -> dict[str, Any]:
    meeting_url = row["meeting_url"]
    if user and user["role"] == "student":
        is_booked = "is_booked" in row.keys() and bool(row["is_booked"])
        if not is_booked:
            meeting_url = None
    return {
        "id": row["id"],
        "teacher_id": row["teacher_id"],
        "teacher_name": row["teacher_name"],
        "title": row["title"],
        "description": row["description"],
        "starts_at": row["starts_at"],
        "duration_minutes": row["duration_minutes"],
        "meeting_url": meeting_url,
        "capacity": row["capacity"],
        "booked_count": row["booked_count"],
        "created_at": row["created_at"],
        "is_booked": "is_booked" in row.keys() and bool(row["is_booked"]),
    }


def create_live_session(
    conn: sqlite3.Connection,
    *,
    teacher_id: int,
    title: str,
    description: str,
    starts_at: str,
    duration_minutes: int,
    meeting_url: str,
    capacity: int,
    created_at: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        """
        INSERT INTO live_sessions
            (teacher_id, title, description, starts_at, duration_minutes, meeting_url, capacity, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            teacher_id,
            title.strip(),
            description.strip(),
            starts_at,
            duration_minutes,
            meeting_url,
            capacity,
            created_at,
        ),
    )
    return get_session_row(conn, cursor.lastrowid)


def get_session_row(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT s.*, u.name AS teacher_name, COUNT(b.id) AS booked_count
        FROM live_sessions s
        JOIN users u ON u.id = s.teacher_id
        LEFT JOIN bookings b ON b.session_id = s.id AND b.status = 'booked'
        WHERE s.id = ?
        GROUP BY s.id
        """,
        (session_id,),
    ).fetchone()


def list_live_sessions(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            s.*,
            u.name AS teacher_name,
            COUNT(b.id) AS booked_count,
            EXISTS(
                SELECT 1
                FROM bookings my_booking
                WHERE my_booking.session_id = s.id
                  AND my_booking.student_id = ?
                  AND my_booking.status = 'booked'
            ) AS is_booked
        FROM live_sessions s
        JOIN users u ON u.id = s.teacher_id
        LEFT JOIN bookings b ON b.session_id = s.id AND b.status = 'booked'
        GROUP BY s.id
        ORDER BY s.starts_at ASC
        """,
        (user_id,),
    ).fetchall()
