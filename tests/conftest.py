import sys
import os

# ===== CRITICAL: Setup sys.path FIRST before anything else =====
# This must run before pytest collects any test modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Force project root to be first in sys.path
while project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

# Change to project root immediately
os.chdir(project_root)

# Set environment variables BEFORE anything imports the app
os.environ["DEV_BYPASS_AUTH"] = "1"
os.environ["FIREBASE_CREDENTIAL_PATH"] = "Backend_old/firebase-service-account.json"

