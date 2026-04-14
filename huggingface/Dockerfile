ARG IMAGE_REF=ghcr.io/zeropointsix/outlook-email-plus:latest
FROM ${IMAGE_REF}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_SOURCE=image \
    APP_IMAGE_DIR=/app \
    APP_GIT_DIR=/workspace/app-git \
    DATA_DIR=/data \
    DATABASE_PATH=/data/outlook_accounts.db \
    PORT=5000 \
    GUNICORN_TIMEOUT=300 \
    GUNICORN_THREADS=4

WORKDIR /workspace

ARG GIT_REPO=https://github.com/ZeroPointSix/outlookEmailPlus.git

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 "$GIT_REPO" "$APP_GIT_DIR" \
    && pip install --upgrade pip \
    && pip install -r "$APP_GIT_DIR/requirements.txt" \
    && pip install gunicorn

RUN mkdir -p /data \
    && cat <<'EOF' > /usr/local/bin/start-hf-space.sh
#!/usr/bin/env bash
set -euo pipefail

APP_SOURCE="${APP_SOURCE:-image}"
APP_IMAGE_DIR="${APP_IMAGE_DIR:-/app}"
APP_GIT_DIR="${APP_GIT_DIR:-/workspace/app-git}"
DATA_DIR="${DATA_DIR:-/data}"
PORT="${PORT:-5000}"

if [ "$APP_SOURCE" = "git" ]; then
  APP_DIR="$APP_GIT_DIR"
else
  APP_DIR="$APP_IMAGE_DIR"
fi

if [ ! -f "$APP_DIR/web_outlook_app.py" ]; then
  echo "[hf-space] app entrypoint not found in $APP_DIR" >&2
  exit 1
fi

mkdir -p "$DATA_DIR"

export DATA_DIR
export DATABASE_PATH="${DATABASE_PATH:-$DATA_DIR/outlook_accounts.db}"
export HOST="0.0.0.0"
export PORT

cd "$APP_DIR"
exec gunicorn -k gthread -w 1 --threads "${GUNICORN_THREADS:-4}" \
  -b "0.0.0.0:${PORT}" \
  --timeout "${GUNICORN_TIMEOUT:-300}" \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  web_outlook_app:app
EOF

RUN chmod +x /usr/local/bin/start-hf-space.sh

EXPOSE 5000

CMD ["/usr/local/bin/start-hf-space.sh"]
