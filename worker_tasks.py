import sys
import os
from datetime import datetime

# Add root directory to path so imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mongo_db import analysis_collection
# Import the actual function from your app
# Since run.py adds the root directory to path, we can import Backend_old
try:
    from Backend_old.app import run_analysis_task
except ImportError:
    # Fallback if running directly without proper path setup
    sys.path.append(os.path.join(os.path.dirname(__file__), 'Backend_old'))
    from Backend_old.app import run_analysis_task

def process_resume_analysis(resume_text, jd_text, mode):
    """
    Background Task:
    Runs AI analysis + Saves to MongoDB
    """
    
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
    analysis_collection.insert_one({
        "resume": resume_text,
        "job_description": jd_text,
        "mode": mode,
        "result": result,
        "timestamp": datetime.utcnow()
    })

    return result
