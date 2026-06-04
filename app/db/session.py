from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any

from app.core.config import DATABASE_PATH


@contextmanager
def db() -> Any:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
