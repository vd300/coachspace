from __future__ import annotations

import sqlite3
from typing import Any, Literal


def clean_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def create_user(
    conn: sqlite3.Connection,
    *,
    name: str,
    email: str,
    password_hash: str,
    role: Literal["student", "teacher"],
    created_at: str,
) -> sqlite3.Row:
    cursor = conn.execute(
        """
        INSERT INTO users (name, email, password_hash, role, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name.strip(), email.lower(), password_hash, role, created_at),
    )
    return get_user_by_id(conn, cursor.lastrowid)


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()


def list_users(conn: sqlite3.Connection, role: Literal["student", "teacher"] | None = None) -> list[sqlite3.Row]:
    query = "SELECT * FROM users"
    params: tuple[Any, ...] = ()
    if role:
        query += " WHERE role = ?"
        params = (role,)
    query += " ORDER BY name"
    return conn.execute(query, params).fetchall()
