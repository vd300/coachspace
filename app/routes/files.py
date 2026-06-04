from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.dependencies import current_user
from app.services.file_service import get_upload_path


router = APIRouter(prefix="/api")


@router.get("/files/{file_name:path}", include_in_schema=False, response_model=None)
def download_file(file_name: str, user: Annotated[dict[str, Any], Depends(current_user)]) -> Any:
    return FileResponse(get_upload_path(file_name))
