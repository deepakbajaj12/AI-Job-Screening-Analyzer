# ASYNC TASK WORKER: Processes resume analysis jobs in background queue with user association for history tracking
import sys
import os
from datetime import datetime

# Add root directory to path so imports work correctly
# We are assuming worker_tasks.py is now inside backend/
# So __file__ is /.../backend/worker_tasks.py
# Root is one level up
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from backend.mongo_db import get_db
except ImportError:
    try:
        from mongo_db import get_db
    except ImportError:
        from .mongo_db import get_db

def process_resume_analysis(resume_text, jd_text, mode, user_id="anonymous"):
    """
    Background Task:
    Runs AI analysis + Saves to MongoDB with user association
    """
    
    # We must delay this import to avoid circular dependencies and import errors
    # backend.app imports worker_tasks (this file)
    # worker_tasks imports backend.app
    # Moving import inside the function breaks the cycle at module level
    try:
        from backend.app import run_analysis_task
        from backend.mongo_db import save_analysis
    except ImportError:
        # If running from inside Backend_old
        try:
            from app import run_analysis_task
            from mongo_db import save_analysis
        except ImportError:
            from .app import run_analysis_task
            from .mongo_db import save_analysis

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

    # Save result using proper save_analysis function to include user association
    try:
        save_analysis(
            user_id=user_id,
            mode=mode,
            result=result,
            resume_excerpt=resume_text[:500],
            job_desc_excerpt=jd_text[:500]
        )
    except Exception as e:
        print(f"MongoDB save error: {e}")

    return result
