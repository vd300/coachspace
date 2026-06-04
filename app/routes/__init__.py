from __future__ import annotations

from fastapi import FastAPI

from app.routes import auth, files, media, messages, root, sessions, users


def include_routes(app: FastAPI) -> None:
    app.include_router(root.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(media.router)
    app.include_router(sessions.router)
    app.include_router(messages.router)
    app.include_router(files.router)
