from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.dependencies import current_user, require_role
from app.schemas.comments import CommentPayload
from app.services import media_service


router = APIRouter(prefix="/api")


@router.post("/media")
async def upload_media(
    user: Annotated[dict[str, Any], Depends(require_role("teacher"))],
    title: Annotated[str, Form(min_length=2, max_length=140)],
    description: Annotated[str, Form(max_length=1200)] = "",
    media_type: Annotated[Literal["video", "audio", "pdf"], Form()] = "video",
    file: UploadFile = File(...),
) -> dict[str, Any]:
    return await media_service.upload_media(
        user=user,
        title=title,
        description=description,
        media_type=media_type,
        file=file,
    )


@router.get("/media")
def list_media(
    user: Annotated[dict[str, Any], Depends(current_user)],
    media_type: Literal["video", "audio", "pdf"] | None = None,
) -> list[dict[str, Any]]:
    return media_service.list_media(media_type)


@router.get("/media/{media_id}")
def get_media(media_id: int, user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return media_service.get_media(media_id)


@router.post("/media/{media_id}/comments")
def create_comment(
    media_id: int,
    payload: CommentPayload,
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> dict[str, Any]:
    return media_service.create_comment(media_id, payload, user)


@router.get("/media/{media_id}/comments")
def list_comments(media_id: int, user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    return media_service.list_comments(media_id)
