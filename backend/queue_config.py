import os
import logging
from redis import Redis
from rq import Queue
from dotenv import load_dotenv

load_dotenv()

# Configure simple logging for queue setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("queue_config")

# Connect to Redis Cloud
# Priority: REDIS_URL -> CELERY_BROKER_URL -> Localhost
redis_url = os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL"))

if not redis_url:
    logger.warning("REDIS_URL not found. Defaulting to localhost.")
    redis_url = "redis://localhost:6379"

# Handle potential SSL requirement for rediss:// URLs
connection_kwargs = {}
if redis_url.startswith("rediss://"):
    connection_kwargs = {
        "ssl_cert_reqs": None  # Bypass certificate verification if needed for some providers
    }

try:
    redis_conn = Redis.from_url(redis_url, **connection_kwargs)
    # Test connection immediately to fail fast if broken
    redis_conn.ping()
    logger.info(f"Successfully connected to Redis at {redis_url.split('@')[-1]}") # Log only host part for security
except Exception as e:
    logger.error(f"FATAL: Could not connect to Redis: {e}")
    # We don't raise here to allow app to start, but queue functionality will be broken.
    # In production, this might be better to raise.
    redis_conn = None

# Create queue
if redis_conn:
    task_queue = Queue("resume-tasks", connection=redis_conn)
else:
    # specific fallback or dummy if needed, but for now we leave it
    # so imports don't crash, but usage will fail
    task_queue = None

