"""
Root-level conftest.py - ensures sys.path is configured before any test discovery.
This runs BEFORE pytest even looks for tests in subdirectories.
"""
import sys
import os

# Get the project root (directory containing this file)
project_root = os.path.dirname(os.path.realpath(__file__))

# Ensure project root is first in sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
else:
    sys.path.remove(project_root)
    sys.path.insert(0, project_root)

# Set working directory
os.chdir(project_root)

# Set test environment variables
os.environ["DEV_BYPASS_AUTH"] = "1"
os.environ["FIREBASE_CREDENTIAL_PATH"] = "Backend_old/firebase-service-account.json"


def pytest_configure(config):
    """Early pytest hook to ensure setup is complete before collection."""
    # Verify Backend_old is accessible
    if not os.path.exists(os.path.join(project_root, 'Backend_old')):
        raise RuntimeError(f"Backend_old not found at {project_root}")
    
    # Re-apply sys.path setup as insurance
    if project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)
    
    print(f"\nROOT conftest.py setup complete")
    print(f"  Project root: {project_root}")
    print(f"  sys.path[0]: {sys.path[0]}")
    print(f"  cwd: {os.getcwd()}")
