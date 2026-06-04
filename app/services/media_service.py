from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, UploadFile

from app.core.config import MAX_UPLOAD_BYTES, UPLOAD_DIR
from app.core.time import utc_now
from app.db.session import db
from app.repositories import comments as comment_repository
from app.repositories import media as media_repository
from app.schemas.comments import CommentPayload


def normalized_content_type(file_name: str, content_type: str | None) -> str:
    return content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"


def validate_media_file(media_type: str, file_name: str, content_type: str, size_bytes: int) -> None:
    if size_bytes <= 0:
        raise HTTPException(status_code=400, detail="Upload cannot be empty")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 250 MB")

    expected_prefix = {"video": "video/", "audio": "audio/", "pdf": "application/pdf"}[media_type]
    if media_type == "pdf":
        valid = content_type == expected_prefix or file_name.lower().endswith(".pdf")
    else:
        valid = content_type.startswith(expected_prefix)
    if not valid:
        raise HTTPException(status_code=400, detail=f"File does not look like a {media_type}")


async def upload_media(
    *,
    user: dict[str, Any],
    title: str,
    description: str,
    media_type: Literal["video", "audio", "pdf"],
    file: UploadFile,
) -> dict[str, Any]:
    contents = await file.read()
    original_name = file.filename or "upload"
    content_type = normalized_content_type(original_name, file.content_type)
    validate_media_file(media_type, original_name, content_type, len(contents))

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    destination = UPLOAD_DIR / stored_name
    destination.write_bytes(contents)

    with db() as conn:
        row = media_repository.create_media_item(
            conn,
            user_id=user["id"],
            title=title,
            description=description,
            media_type=media_type,
            file_name=stored_name,
            original_name=original_name,
            content_type=content_type,
            size_bytes=len(contents),
            created_at=utc_now(),
        )
    return media_repository.media_response(row)


def list_media(media_type: Literal["video", "audio", "pdf"] | None = None) -> list[dict[str, Any]]:
    with db() as conn:
        rows = media_repository.list_media(conn, media_type)
    return [media_repository.media_response(row) for row in rows]


def get_media(media_id: int) -> dict[str, Any]:
    with db() as conn:
        row = media_repository.get_media_by_id(conn, media_id)
    if not row:
        raise HTTPException(status_code=404, detail="Media item not found")
    return media_repository.media_response(row)


def create_comment(media_id: int, payload: CommentPayload, user: dict[str, Any]) -> dict[str, Any]:
    with db() as conn:
        if not media_repository.media_exists(conn, media_id):
            raise HTTPException(status_code=404, detail="Media item not found")
        row = comment_repository.create_comment(
            conn,
            media_id=media_id,
            user_id=user["id"],
            body=payload.body,
            created_at=utc_now(),
        )
    return dict(row)


def list_comments(media_id: int) -> list[dict[str, Any]]:
    with db() as conn:
        rows = comment_repository.list_comments(conn, media_id)
    return [dict(row) for row in rows]
