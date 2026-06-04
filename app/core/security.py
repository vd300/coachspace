from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from typing import Any

from fastapi import HTTPException, status

from app.core.config import APP_SECRET, TOKEN_TTL_SECONDS


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(user: sqlite3.Row) -> str:
    payload = {
        "sub": user["id"],
        "role": user["role"],
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{b64url(signature)}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        expected = b64url(hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(b64url_decode(body))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
