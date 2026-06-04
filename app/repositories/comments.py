from __future__ import annotations

import sqlite3


def create_comment(
    conn: sqlite3.Connection,
    *,
    media_id: int,
    user_id: int,
    body: str,
    created_at: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        "INSERT INTO comments (media_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
        (media_id, user_id, body.strip(), created_at),
    )
    return conn.execute(
        """
        SELECT c.*, u.name AS user_name, u.role AS user_role
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()


def list_comments(conn: sqlite3.Connection, media_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT c.*, u.name AS user_name, u.role AS user_role
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.media_id = ?
        ORDER BY c.created_at ASC
        """,
        (media_id,),
    ).fetchall()
