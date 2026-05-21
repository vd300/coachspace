# CoachSpace MVP

A deploy-ready coaching app MVP with FastAPI, SQLite, role-based auth, learning media uploads, comments, live session booking, and in-app messaging.

## Features

- User registration and login with signed bearer tokens.
- Student and teacher roles.
- Teachers can upload videos, audio files, and PDF books.
- Students and teachers can view learning materials.
- Comments are available on every media item.
- Teachers can schedule live sessions with a meeting URL or an auto-created Jitsi room.
- Students can book live sessions and see the join link only after booking.
- Teachers can view bookings for their sessions.
- In-app messaging between teachers and students.
- Static responsive UI served by FastAPI.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:APP_SECRET="replace-this-with-a-long-random-secret"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Environment Variables

- `APP_SECRET`: Required in production. Used to sign auth tokens.
- `DATABASE_URL`: Optional SQLite path. Defaults to `data/coaching.db`.
- `UPLOAD_DIR`: Optional upload directory. Defaults to `uploads`.
- `CORS_ORIGINS`: Optional comma-separated origins. Defaults to `*`.

## Deployment

### AWS

For AWS, use Docker on Elastic Beanstalk or ECS/Fargate, and store uploaded media in S3:

```text
STORAGE_BACKEND=s3
S3_BUCKET_NAME=your-media-bucket
AWS_REGION=your-aws-region
APP_SECRET=replace-this-with-a-long-random-secret
```

See `AWS_DEPLOYMENT.md` for the full setup, including S3 CORS and IAM permissions.

### Docker

```bash
docker build -t coachspace .
docker run -p 8000:8000 -e APP_SECRET="replace-this" coachspace
```

### Render

This repo includes `render.yaml`. Create a Render Blueprint from the repo and Render will generate `APP_SECRET`. For persistent production uploads and SQLite data, attach a persistent disk and point:

```text
DATABASE_URL=/var/data/coaching.db
UPLOAD_DIR=/var/data/uploads
```

## API Overview

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/me`
- `GET /api/users`
- `POST /api/media` teacher only
- `GET /api/media`
- `POST /api/media/{media_id}/comments`
- `GET /api/media/{media_id}/comments`
- `POST /api/live-sessions` teacher only
- `GET /api/live-sessions`
- `POST /api/live-sessions/{session_id}/book` student only
- `GET /api/bookings`
- `POST /api/messages`
- `GET /api/messages?with_user_id=...`
- `GET /api/conversations`

## MVP Notes

The app uses generated or supplied meeting links for live video sessions. For a later production release, add a managed video provider such as Twilio, Daily, Zoom, or LiveKit when you need attendance controls, recording, and stronger room security.
