#!/bin/bash
set -e

# Open the HTTP port as early as possible to avoid Render wake-time routing 503s.
# Emit access/error logs so request traffic is visible in Render live tail.
gunicorn --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile - backend.app:app &
GUNICORN_PID=$!

cleanup() {
	kill "$GUNICORN_PID" 2>/dev/null || true
}

trap cleanup SIGTERM SIGINT

# Keep container tied to the web process lifecycle.
wait "$GUNICORN_PID"
