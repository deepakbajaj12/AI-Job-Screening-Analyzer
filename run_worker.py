import os
import sys
from redis import Redis
from rq import Worker, Queue, SimpleWorker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

listen = ['resume-tasks']

def start_worker():
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        print("Error: REDIS_URL not found in .env")
        return

    conn = Redis.from_url(redis_url)
    
    # Initialize queues explicitly with the connection
    queues = [Queue(name, connection=conn) for name in listen]
    
    print(f"Worker starting... listening on {listen}")

    # Use SimpleWorker on Windows because os.fork() is not available
    if os.name == 'nt':
        print("Running on Windows: Using SimpleWorker")
        worker = SimpleWorker(queues, connection=conn)
    else:
        worker = Worker(queues, connection=conn)

    worker.work()

if __name__ == '__main__':
    start_worker()
