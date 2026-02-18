import sys
import os
from datetime import datetime

# Add root directory to path so imports work correctly
# We are assuming worker_tasks.py is now inside Backend_old/
# So __file__ is /.../Backend_old/worker_tasks.py
# Root is one level up
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from Backend_old.mongo_db import analysis_collection
except ImportError:
    try:
        from mongo_db import analysis_collection
    except ImportError:
        # Fallback for relative import if running as module
        from .mongo_db import analysis_collection

def process_resume_analysis(resume_text, jd_text, mode):
    """
    Background Task:
    Runs AI analysis + Saves to MongoDB
    """
    
    # We must delay this import to avoid circular dependencies and import errors
    # Backend_old.app imports worker_tasks (this file)
    # worker_tasks imports Backend_old.app
    # Moving import inside the function breaks the cycle at module level
    try:
        from Backend_old.app import run_analysis_task
    except ImportError:
        # If running from inside Backend_old
        from app import run_analysis_task

    # Run AI analysis (synchronously calling the celery task function)
    # The arguments required are: mode, resume_text, job_desc_text, recruiter_email, user_info
    # We pass empty strings/dicts for optional fields not provided in this context
    recruiter_email = ""
    user_info = {} 

    try:
        # Calling extraction/AI logic
        # Note: calling a celery task directly executes it synchronously
        result = run_analysis_task(mode, resume_text, jd_text, recruiter_email, user_info)
    except Exception as e:
        result = {"error": str(e)}

    # Save result permanently
    if analysis_collection is not None:
        analysis_collection.insert_one({
            "resume": resume_text,
            "job_description": jd_text,
            "mode": mode,
            "result": result,
            "timestamp": datetime.utcnow()
        })
    else:
        print("MongoDB not connected, skipping save")

    return result
