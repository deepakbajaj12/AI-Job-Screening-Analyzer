import os
from redis import Redis
from rq import Queue
from dotenv import load_dotenv

load_dotenv()

# Connect to Redis Cloud
redis_conn = Redis.from_url(os.getenv("REDIS_URL"))

# Create queue
task_queue = Queue("resume-tasks", connection=redis_conn)
