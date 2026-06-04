from __future__ import annotations

import sqlite3
from typing import Any, Literal


def media_url(row: sqlite3.Row) -> str:
    return f"/uploads/{row['file_name']}"


def media_response(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "teacher_id": row["teacher_id"],
        "teacher_name": row["teacher_name"],
        "title": row["title"],
        "description": row["description"],
        "media_type": row["media_type"],
        "url": media_url(row),
        "original_name": row["original_name"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
    }


def create_media_item(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    title: str,
    description: str,
    media_type: Literal["video", "audio", "pdf"],
    file_name: str,
    original_name: str,
    content_type: str,
    size_bytes: int,
    created_at: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        """
        INSERT INTO media_items
            (
                teacher_id, title, description, media_type, file_name, original_name,
                content_type, size_bytes, created_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title.strip(),
            description.strip(),
            media_type,
            file_name,
            original_name,
            content_type,
            size_bytes,
            created_at,
        ),
    )
    return get_media_by_id(conn, cursor.lastrowid)


def get_media_by_id(conn: sqlite3.Connection, media_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT m.*, u.name AS teacher_name
        FROM media_items m
        JOIN users u ON u.id = m.teacher_id
        WHERE m.id = ?
        """,
        (media_id,),
    ).fetchone()


def media_exists(conn: sqlite3.Connection, media_id: int) -> bool:
    return conn.execute("SELECT id FROM media_items WHERE id = ?", (media_id,)).fetchone() is not None


def list_media(
    conn: sqlite3.Connection,
    media_type: Literal["video", "audio", "pdf"] | None = None,
) -> list[sqlite3.Row]:
    query = """
        SELECT m.*, u.name AS teacher_name
        FROM media_items m
        JOIN users u ON u.id = m.teacher_id
    """
    params: tuple[Any, ...] = ()
    if media_type:
        query += " WHERE m.media_type = ?"
        params = (media_type,)
    query += " ORDER BY m.created_at DESC"
    return conn.execute(query, params).fetchall()
