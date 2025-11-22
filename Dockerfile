FROM python:3.12-slim

WORKDIR /app

# System deps (if pdf parsing or spaCy models need them)
RUN apt-get update && apt-get install -y build-essential poppler-utils && rm -rf /var/lib/apt/lists/*

COPY Backend_old/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend_old ./Backend_old

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "Backend_old/app.py"]