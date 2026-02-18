import os
from redis import Redis
from rq import Queue
from dotenv import load_dotenv

load_dotenv()

# Connect to Redis Cloud
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    # Fallback to localhost or raise clear error
    redis_url = "redis://localhost:6379"

redis_conn = Redis.from_url(redis_url)

# Create queue
task_queue = Queue("resume-tasks", connection=redis_conn)
