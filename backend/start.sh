#!/bin/bash
# Start the RQ worker in the background (used by /analyze queue)
rq worker resume-tasks --url "$REDIS_URL" &

# Start the Celery worker in the background (used by salary/tailor/career async tasks)
celery -A backend.app.celery worker --loglevel=info &

# Start the Gunicorn web server
# The exec command replaces the shell with the gunicorn process, handling signals correctly
exec gunicorn --bind 0.0.0.0:$PORT --timeout 120 backend.app:app
