#!/bin/bash
set -e

# Memory optimizations for low-RAM containers (Render 512MB Free Tier)
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Open the HTTP port with 1 worker and 2 threads to prevent spawning duplicate memory-heavy processes.
# Max-requests worker recycling prevents memory leaks over time.
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --max-requests 200 --max-requests-jitter 20 --timeout 120 --access-logfile - --error-logfile - backend.app:app &
GUNICORN_PID=$!

cleanup() {
	kill "$GUNICORN_PID" 2>/dev/null || true
}

trap cleanup SIGTERM SIGINT

# Keep container tied to the web process lifecycle.
wait "$GUNICORN_PID"

