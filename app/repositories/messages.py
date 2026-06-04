from __future__ import annotations

import sqlite3


def create_message(
    conn: sqlite3.Connection,
    *,
    sender_id: int,
    recipient_id: int,
    body: str,
    created_at: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        "INSERT INTO messages (sender_id, recipient_id, body, created_at) VALUES (?, ?, ?, ?)",
        (sender_id, recipient_id, body.strip(), created_at),
    )
    return conn.execute(
        """
        SELECT m.*, s.name AS sender_name, r.name AS recipient_name
        FROM messages m
        JOIN users s ON s.id = m.sender_id
        JOIN users r ON r.id = m.recipient_id
        WHERE m.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()


def list_messages(conn: sqlite3.Connection, *, user_id: int, peer_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.*, s.name AS sender_name, r.name AS recipient_name
        FROM messages m
        JOIN users s ON s.id = m.sender_id
        JOIN users r ON r.id = m.recipient_id
        WHERE (m.sender_id = ? AND m.recipient_id = ?)
           OR (m.sender_id = ? AND m.recipient_id = ?)
        ORDER BY m.created_at ASC
        """,
        (user_id, peer_id, peer_id, user_id),
    ).fetchall()


def mark_messages_read(conn: sqlite3.Connection, *, recipient_id: int, sender_id: int, read_at: str) -> None:
    conn.execute(
        "UPDATE messages SET read_at = COALESCE(read_at, ?) WHERE recipient_id = ? AND sender_id = ?",
        (read_at, recipient_id, sender_id),
    )


def list_conversations(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH related AS (
            SELECT
                CASE WHEN sender_id = ? THEN recipient_id ELSE sender_id END AS peer_id,
                MAX(created_at) AS last_at
            FROM messages
            WHERE sender_id = ? OR recipient_id = ?
            GROUP BY peer_id
        )
        SELECT related.peer_id, users.name AS peer_name, users.role AS peer_role, related.last_at
        FROM related
        JOIN users ON users.id = related.peer_id
        ORDER BY related.last_at DESC
        """,
        (user_id, user_id, user_id),
    ).fetchall()
