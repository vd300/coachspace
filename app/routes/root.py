from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse


router = APIRouter()


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/static/index.html")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
