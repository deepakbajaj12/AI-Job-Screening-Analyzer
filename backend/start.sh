#!/bin/bash
set -e

# Open the HTTP port as early as possible to avoid Render wake-time routing 503s.
gunicorn --bind 0.0.0.0:$PORT --timeout 120 backend.app:app &
GUNICORN_PID=$!

# Start async worker in low-memory mode for 512MB instances.
celery -A backend.app.celery worker --loglevel=info --pool=solo --concurrency=1 &
CELERY_PID=$!

cleanup() {
	kill "$CELERY_PID" "$GUNICORN_PID" 2>/dev/null || true
}

trap cleanup SIGTERM SIGINT

# Keep container tied to the web process lifecycle.
wait "$GUNICORN_PID"
