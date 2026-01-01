import sys
import os

# ===== ABSOLUTE CRITICAL: Setup sys.path BEFORE anything else =====
# This code runs at conftest.py import time (earliest possible)
# Use os.path.realpath() for absolute path resolution, not relying on cwd
conftest_file = os.path.realpath(__file__)
conftest_dir = os.path.dirname(conftest_file)  # /path/to/tests
project_root = os.path.dirname(conftest_dir)   # /path/to/project

# Verify project root is correct
if not os.path.exists(os.path.join(project_root, 'Backend_old')):
    raise RuntimeError(
        f"Backend_old not found at {project_root}. "
        f"conftest.py at: {conftest_file}, "
        f"calculated project_root: {project_root}"
    )

# Force project root to be first in sys.path
while project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

# Change to project root immediately
os.chdir(project_root)

# Set environment variables BEFORE anything imports the app
os.environ["DEV_BYPASS_AUTH"] = "1"
os.environ["FIREBASE_CREDENTIAL_PATH"] = "Backend_old/firebase-service-account.json"


def pytest_configure(config):
    """
    Earliest pytest hook - runs before test collection.
    Ensures sys.path is configured before pytest tries to collect test modules.
    """
    global project_root
    # Re-apply setup as extra insurance
    while project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)

