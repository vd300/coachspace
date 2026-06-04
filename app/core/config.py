from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = Path(os.getenv("DATABASE_URL", BASE_DIR / "data" / "coaching.db"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
APP_SECRET = os.getenv("APP_SECRET", "dev-secret-change-before-deploy")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
ALLOWED_MEDIA_TYPES = {"video", "audio", "pdf"}
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
