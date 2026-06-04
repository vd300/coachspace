from __future__ import annotations

import sqlite3
from typing import Any


def create_booking(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    student_id: int,
    created_at: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        "INSERT INTO bookings (session_id, student_id, status, created_at) VALUES (?, ?, 'booked', ?)",
        (session_id, student_id, created_at),
    )
    return conn.execute("SELECT * FROM bookings WHERE id = ?", (cursor.lastrowid,)).fetchone()


def list_bookings(conn: sqlite3.Connection, user: dict[str, Any]) -> list[sqlite3.Row]:
    if user["role"] == "teacher":
        query = """
            SELECT b.*, s.title AS session_title, s.starts_at, s.meeting_url, u.name AS student_name
            FROM bookings b
            JOIN live_sessions s ON s.id = b.session_id
            JOIN users u ON u.id = b.student_id
            WHERE s.teacher_id = ?
            ORDER BY s.starts_at ASC
        """
    else:
        query = """
            SELECT b.*, s.title AS session_title, s.starts_at, s.meeting_url, u.name AS teacher_name
            FROM bookings b
            JOIN live_sessions s ON s.id = b.session_id
            JOIN users u ON u.id = s.teacher_id
            WHERE b.student_id = ?
            ORDER BY s.starts_at ASC
        """
    return conn.execute(query, (user["id"],)).fetchall()
