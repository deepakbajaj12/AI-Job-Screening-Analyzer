#!/bin/bash
# Start the RQ worker in the background
rq worker resume-tasks --url $REDIS_URL &

# Start the Gunicorn web server
# The exec command replaces the shell with the gunicorn process, handling signals correctly
exec gunicorn --bind 0.0.0.0:$PORT --timeout 120 Backend_old.app:app
