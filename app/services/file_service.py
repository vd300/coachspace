from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.core.config import UPLOAD_DIR


def get_upload_path(file_name: str) -> Path:
    target = (UPLOAD_DIR / file_name).resolve()
    if UPLOAD_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return target
