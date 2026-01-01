import sys
import os

# Add the project root to sys.path so that Backend_old and tests can be imported
# conftest.py is in the tests directory, so go up one level to get the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure project root is FIRST in sys.path (before anything else)
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

# Also change to project root for relative imports to work
os.chdir(project_root)

# Set environment variables for Firebase
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")
