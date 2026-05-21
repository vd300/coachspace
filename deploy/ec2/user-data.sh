#!/usr/bin/env bash
set -euxo pipefail

# Edit these before using this as EC2 user data.
APP_IMAGE="YOUR_DOCKER_IMAGE_HERE"
APP_SECRET="replace-with-a-long-random-secret"
CORS_ORIGINS="*"

APP_DIR="/opt/coachspace"

if command -v yum >/dev/null 2>&1; then
  yum update -y
  yum install -y docker
elif command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker.io
else
  echo "No supported package manager found. Install Docker manually." >&2
  exit 1
fi

systemctl enable --now docker

mkdir -p "${APP_DIR}/data" "${APP_DIR}/uploads"

docker pull "${APP_IMAGE}"
docker rm -f coachspace || true
docker run -d \
  --name coachspace \
  --restart unless-stopped \
  -p 80:8000 \
  -e APP_SECRET="${APP_SECRET}" \
  -e DATABASE_URL="/app/data/coaching.db" \
  -e UPLOAD_DIR="/app/uploads" \
  -e CORS_ORIGINS="${CORS_ORIGINS}" \
  -v "${APP_DIR}/data:/app/data" \
  -v "${APP_DIR}/uploads:/app/uploads" \
  "${APP_IMAGE}"
