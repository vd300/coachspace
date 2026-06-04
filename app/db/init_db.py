from __future__ import annotations

from app.core.config import UPLOAD_DIR
from app.db.session import db
from app.models.tables import DATABASE_SCHEMA


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(DATABASE_SCHEMA)
