# CONTAINERIZATION: Docker image for backend with Python 3.12, Flask server, and dependency installation
FROM python:3.12-slim

WORKDIR /app

# System deps (if pdf parsing or spaCy models need them)
RUN apt-get update && apt-get install -y build-essential poppler-utils && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Make start script executable
RUN chmod +x backend/start.sh

# Start both worker and server using the script
CMD ["/bin/bash", "backend/start.sh"]