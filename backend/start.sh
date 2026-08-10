#!/bin/bash
set -e

# Memory optimizations for low-RAM containers (Render 512MB Free Tier)
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Single worker + 2 threads to stay within 512MB RAM limit.
# --max-requests recycles the worker periodically to prevent memory leaks.
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --threads 2 \
  --max-requests 200 \
  --max-requests-jitter 20 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  backend.app:app
