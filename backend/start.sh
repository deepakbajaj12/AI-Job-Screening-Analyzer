#!/bin/bash
set -e

# Open the HTTP port as early as possible to avoid Render wake-time routing 503s.
gunicorn --bind 0.0.0.0:$PORT --timeout 120 backend.app:app &
GUNICORN_PID=$!

# Start async workers in background.
rq worker resume-tasks --url "$REDIS_URL" &
RQ_PID=$!
celery -A backend.app.celery worker --loglevel=info &
CELERY_PID=$!

cleanup() {
	kill "$RQ_PID" "$CELERY_PID" "$GUNICORN_PID" 2>/dev/null || true
}

trap cleanup SIGTERM SIGINT

# Keep container tied to the web process lifecycle.
wait "$GUNICORN_PID"
