# CONTAINERIZATION: Docker image for backend with Python 3.12, Flask server, and dependency installation
FROM python:3.12-slim

WORKDIR /app

# System deps (pdf parsing + spaCy models)
RUN apt-get update && apt-get install -y build-essential poppler-utils dos2unix && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Convert line endings to Unix (LF) — prevents \r\n issues from Windows dev machines
RUN dos2unix backend/start.sh && chmod +x backend/start.sh

# Use exec form so gunicorn receives OS signals directly
CMD ["/bin/bash", "backend/start.sh"]