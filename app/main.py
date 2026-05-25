from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("DATABASE_URL", BASE_DIR / "data" / "coaching.db"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
APP_SECRET = os.getenv("APP_SECRET", "dev-secret-change-before-deploy")
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
ALLOWED_ROLES = {"student", "teacher"}
ALLOWED_MEDIA_TYPES = {"video", "audio", "pdf"}
MAX_UPLOAD_BYTES = 250 * 1024 * 1024

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Coaching App MVP", version="1.0.0") #app creation with title and version
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static") #mounting the static files directory to serve frontend assets
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid ISO datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@contextmanager
def db() -> Any:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'teacher')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                media_type TEXT NOT NULL CHECK(media_type IN ('video', 'audio', 'pdf')),
                file_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_id INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS live_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                starts_at TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                meeting_url TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 30,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'booked',
                created_at TEXT NOT NULL,
                UNIQUE(session_id, student_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read_at TEXT
            );
            """
        )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


class RegisterPayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["student", "teacher"]


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class CommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=1200)


class SessionPayload(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=1200)
    starts_at: str
    duration_minutes: int = Field(ge=15, le=240)
    meeting_url: str | None = Field(default=None, max_length=500)
    capacity: int = Field(default=30, ge=1, le=500)

    @field_validator("starts_at")
    @classmethod
    def starts_at_must_parse(cls, value: str) -> str:
        parse_iso_datetime(value)
        return value


class MessagePayload(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1, max_length=2000)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2_sha256$200000${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool: #verify the password
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


def create_token(user: sqlite3.Row) -> str: #create a JWT-like token with user ID, role, and expiration
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


def clean_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


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


def media_url(row: sqlite3.Row) -> str:
    return f"/uploads/{row['file_name']}"


def media_response(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "teacher_id": row["teacher_id"],
        "teacher_name": row["teacher_name"],
        "title": row["title"],
        "description": row["description"],
        "media_type": row["media_type"],
        "url": media_url(row),
        "original_name": row["original_name"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
    }


def insert_media_item(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    title: str,
    description: str,
    media_type: str,
    file_name: str,
    original_name: str,
    content_type: str,
    size_bytes: int,
) -> sqlite3.Row:
    cursor = conn.execute(
        """
        INSERT INTO media_items
            (
                teacher_id, title, description, media_type, file_name, original_name,
                content_type, size_bytes, created_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title.strip(),
            description.strip(),
            media_type,
            file_name,
            original_name,
            content_type,
            size_bytes,
            utc_now(),
        ),
    )
    return conn.execute(
        """
        SELECT m.*, u.name AS teacher_name
        FROM media_items m
        JOIN users u ON u.id = m.teacher_id
        WHERE m.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()


def session_response(row: sqlite3.Row, user: dict[str, Any] | None = None) -> dict[str, Any]:
    meeting_url = row["meeting_url"]
    if user and user["role"] == "student":
        is_booked = "is_booked" in row.keys() and bool(row["is_booked"])
        if not is_booked:
            meeting_url = None
    return {
        "id": row["id"],
        "teacher_id": row["teacher_id"],
        "teacher_name": row["teacher_name"],
        "title": row["title"],
        "description": row["description"],
        "starts_at": row["starts_at"],
        "duration_minutes": row["duration_minutes"],
        "meeting_url": meeting_url,
        "capacity": row["capacity"],
        "booked_count": row["booked_count"],
        "created_at": row["created_at"],
        "is_booked": "is_booked" in row.keys() and bool(row["is_booked"]),
    }


def current_user(request: Request) -> dict[str, Any]: #This function checks the incoming HTTP request and returns the logged-in user. It looks for the "Authorization" header, verifies the token, and retrieves the user from the database. If anything goes wrong (missing header, invalid token, user not found), it raises an HTTP 401 error.
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_token(auth.removeprefix("Bearer ").strip())
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (payload["sub"],)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return clean_user(row)


def require_role(role: str):
    def dependency(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
        if user["role"] != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{role.title()} role required")
        return user

    return dependency


def get_session_row(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT s.*, u.name AS teacher_name, COUNT(b.id) AS booked_count
        FROM live_sessions s
        JOIN users u ON u.id = s.teacher_id
        LEFT JOIN bookings b ON b.session_id = s.id AND b.status = 'booked'
        WHERE s.id = ?
        GROUP BY s.id
        """,
        (session_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


@app.get("/", include_in_schema=False) #redirect root URL to the frontend
def root() -> RedirectResponse:
    return RedirectResponse("/static/index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register")
def register(payload: RegisterPayload) -> dict[str, Any]:
    with db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.name.strip(),
                    payload.email.lower(),
                    hash_password(payload.password),
                    payload.role,
                    utc_now(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Email is already registered") from exc
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return {"token": create_token(row), "user": clean_user(row)}


@app.post("/api/auth/login") #receives login requests, verifies credentials, and returns an auth token on success
def login(payload: LoginPayload) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(row), "user": clean_user(row)}


@app.get("/api/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return user


@app.get("/api/users")
def list_users(
    user: Annotated[dict[str, Any], Depends(current_user)],
    role: Literal["student", "teacher"] | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM users"
    params: tuple[Any, ...] = ()
    if role:
        query += " WHERE role = ?"
        params = (role,)
    query += " ORDER BY name"
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [clean_user(row) for row in rows]


@app.post("/api/media")
async def upload_media(
    user: Annotated[dict[str, Any], Depends(require_role("teacher"))],
    title: Annotated[str, Form(min_length=2, max_length=140)],
    description: Annotated[str, Form(max_length=1200)] = "",
    media_type: Annotated[Literal["video", "audio", "pdf"], Form()] = "video",
    file: UploadFile = File(...),
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
        row = insert_media_item(
            conn,
            user_id=user["id"],
            title=title,
            description=description,
            media_type=media_type,
            file_name=stored_name,
            original_name=original_name,
            content_type=content_type,
            size_bytes=len(contents),
        )
    return media_response(row)


@app.get("/api/media")
def list_media(
    user: Annotated[dict[str, Any], Depends(current_user)],
    media_type: Literal["video", "audio", "pdf"] | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT m.*, u.name AS teacher_name
        FROM media_items m
        JOIN users u ON u.id = m.teacher_id
    """
    params: tuple[Any, ...] = ()
    if media_type:
        query += " WHERE m.media_type = ?"
        params = (media_type,)
    query += " ORDER BY m.created_at DESC"
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [media_response(row) for row in rows]


@app.get("/api/media/{media_id}")
def get_media(media_id: int, user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            """
            SELECT m.*, u.name AS teacher_name
            FROM media_items m
            JOIN users u ON u.id = m.teacher_id
            WHERE m.id = ?
            """,
            (media_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Media item not found")
    return media_response(row)


@app.post("/api/media/{media_id}/comments")
def create_comment(
    media_id: int,
    payload: CommentPayload,
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> dict[str, Any]:
    with db() as conn:
        exists = conn.execute("SELECT id FROM media_items WHERE id = ?", (media_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Media item not found")
        cursor = conn.execute(
            "INSERT INTO comments (media_id, user_id, body, created_at) VALUES (?, ?, ?, ?)",
            (media_id, user["id"], payload.body.strip(), utc_now()),
        )
        row = conn.execute(
            """
            SELECT c.*, u.name AS user_name, u.role AS user_role
            FROM comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


@app.get("/api/media/{media_id}/comments")
def list_comments(media_id: int, user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, u.name AS user_name, u.role AS user_role
            FROM comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.media_id = ?
            ORDER BY c.created_at ASC
            """,
            (media_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/live-sessions")
def create_live_session(
    payload: SessionPayload,
    user: Annotated[dict[str, Any], Depends(require_role("teacher"))],
) -> dict[str, Any]:
    starts_at = parse_iso_datetime(payload.starts_at)
    if starts_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Session must be scheduled in the future")
    meeting_url = payload.meeting_url or f"https://meet.jit.si/coaching-{uuid.uuid4().hex[:12]}"
    with db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO live_sessions
                (teacher_id, title, description, starts_at, duration_minutes, meeting_url, capacity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                payload.title.strip(),
                payload.description.strip(),
                starts_at.isoformat(),
                payload.duration_minutes,
                meeting_url,
                payload.capacity,
                utc_now(),
            ),
        )
        row = get_session_row(conn, cursor.lastrowid)
    return session_response(row, user)


@app.get("/api/live-sessions")
def list_live_sessions(user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                s.*,
                u.name AS teacher_name,
                COUNT(b.id) AS booked_count,
                EXISTS(
                    SELECT 1
                    FROM bookings my_booking
                    WHERE my_booking.session_id = s.id
                      AND my_booking.student_id = ?
                      AND my_booking.status = 'booked'
                ) AS is_booked
            FROM live_sessions s
            JOIN users u ON u.id = s.teacher_id
            LEFT JOIN bookings b ON b.session_id = s.id AND b.status = 'booked'
            GROUP BY s.id
            ORDER BY s.starts_at ASC
            """,
            (user["id"],),
        ).fetchall()
    return [session_response(row, user) for row in rows]


@app.post("/api/live-sessions/{session_id}/book")
def book_session(
    session_id: int,
    user: Annotated[dict[str, Any], Depends(require_role("student"))],
) -> dict[str, Any]:
    with db() as conn:
        row = get_session_row(conn, session_id)
        if parse_iso_datetime(row["starts_at"]) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Cannot book a session that has already started")
        if row["booked_count"] >= row["capacity"]:
            raise HTTPException(status_code=409, detail="Session is fully booked")
        try:
            cursor = conn.execute(
                "INSERT INTO bookings (session_id, student_id, status, created_at) VALUES (?, ?, 'booked', ?)",
                (session_id, user["id"], utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="You already booked this session") from exc
        booking = conn.execute("SELECT * FROM bookings WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(booking)


@app.get("/api/bookings")
def list_bookings(user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    if user["role"] == "teacher":
        query = """
            SELECT b.*, s.title AS session_title, s.starts_at, s.meeting_url, u.name AS student_name
            FROM bookings b
            JOIN live_sessions s ON s.id = b.session_id
            JOIN users u ON u.id = b.student_id
            WHERE s.teacher_id = ?
            ORDER BY s.starts_at ASC
        """
    else:
        query = """
            SELECT b.*, s.title AS session_title, s.starts_at, s.meeting_url, u.name AS teacher_name
            FROM bookings b
            JOIN live_sessions s ON s.id = b.session_id
            JOIN users u ON u.id = s.teacher_id
            WHERE b.student_id = ?
            ORDER BY s.starts_at ASC
        """
    with db() as conn:
        rows = conn.execute(query, (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/messages")
def send_message(
    payload: MessagePayload,
    user: Annotated[dict[str, Any], Depends(current_user)],
) -> dict[str, Any]:
    if payload.recipient_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot message yourself")
    with db() as conn:
        recipient = conn.execute("SELECT id FROM users WHERE id = ?", (payload.recipient_id,)).fetchone()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        cursor = conn.execute(
            "INSERT INTO messages (sender_id, recipient_id, body, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], payload.recipient_id, payload.body.strip(), utc_now()),
        )
        row = conn.execute(
            """
            SELECT m.*, s.name AS sender_name, r.name AS recipient_name
            FROM messages m
            JOIN users s ON s.id = m.sender_id
            JOIN users r ON r.id = m.recipient_id
            WHERE m.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


@app.get("/api/messages")
def list_messages(
    user: Annotated[dict[str, Any], Depends(current_user)],
    with_user_id: int = Query(..., gt=0),
) -> list[dict[str, Any]]:
    with db() as conn:
        peer = conn.execute("SELECT id FROM users WHERE id = ?", (with_user_id,)).fetchone()
        if not peer:
            raise HTTPException(status_code=404, detail="User not found")
        rows = conn.execute(
            """
            SELECT m.*, s.name AS sender_name, r.name AS recipient_name
            FROM messages m
            JOIN users s ON s.id = m.sender_id
            JOIN users r ON r.id = m.recipient_id
            WHERE (m.sender_id = ? AND m.recipient_id = ?)
               OR (m.sender_id = ? AND m.recipient_id = ?)
            ORDER BY m.created_at ASC
            """,
            (user["id"], with_user_id, with_user_id, user["id"]),
        ).fetchall()
        conn.execute(
            "UPDATE messages SET read_at = COALESCE(read_at, ?) WHERE recipient_id = ? AND sender_id = ?",
            (utc_now(), user["id"], with_user_id),
        )
    return [dict(row) for row in rows]


@app.get("/api/conversations")
def conversations(user: Annotated[dict[str, Any], Depends(current_user)]) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            """
            WITH related AS (
                SELECT
                    CASE WHEN sender_id = ? THEN recipient_id ELSE sender_id END AS peer_id,
                    MAX(created_at) AS last_at
                FROM messages
                WHERE sender_id = ? OR recipient_id = ?
                GROUP BY peer_id
            )
            SELECT related.peer_id, users.name AS peer_name, users.role AS peer_role, related.last_at
            FROM related
            JOIN users ON users.id = related.peer_id
            ORDER BY related.last_at DESC
            """,
            (user["id"], user["id"], user["id"]),
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/files/{file_name:path}", include_in_schema=False, response_model=None)
def download_file(file_name: str, user: Annotated[dict[str, Any], Depends(current_user)]) -> Any:
    target = (UPLOAD_DIR / file_name).resolve()
    if UPLOAD_DIR.resolve() not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)
