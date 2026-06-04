from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import BASE_DIR, CORS_ORIGINS, UPLOAD_DIR
from app.db.init_db import init_db
from app.routes import include_routes


UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Coaching App MVP", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
include_routes(app)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
