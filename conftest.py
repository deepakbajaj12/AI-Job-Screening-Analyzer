"""
Root-level conftest.py - ensures sys.path is configured before any test discovery.
This runs BEFORE pytest even looks for tests in subdirectories.
"""
import sys
import os

print("=" * 70)
print("ROOT CONFTEST.PY EXECUTING")
print("=" * 70)

# Get the project root (directory containing this file)
project_root = os.path.dirname(os.path.realpath(__file__))
print(f"Calculated project_root: {project_root}")

# Ensure project root is first in sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Inserted {project_root} at sys.path[0]")
else:
    sys.path.remove(project_root)
    sys.path.insert(0, project_root)
    print(f"Moved {project_root} to sys.path[0]")

print(f"sys.path[0] is now: {sys.path[0]}")

# Set working directory
os.chdir(project_root)
print(f"Changed to directory: {os.getcwd()}")

# Set test environment variables
os.environ["DEV_BYPASS_AUTH"] = "1"
os.environ["FIREBASE_CREDENTIAL_PATH"] = "Backend_old/firebase-service-account.json"
print("Environment variables set")

# Verify Backend_old exists
backend_path = os.path.join(project_root, 'Backend_old')
backend_exists = os.path.exists(backend_path)
print(f"Backend_old exists at {backend_path}: {backend_exists}")

if not backend_exists:
    raise RuntimeError(f"CRITICAL: Backend_old not found at {project_root}")

print("=" * 70)
print("ROOT CONFTEST.PY SETUP COMPLETE")
print("=" * 70)


def pytest_configure(config):
    """Early pytest hook to ensure setup is complete before collection."""
    print("\n" + "=" * 70)
    print("pytest_configure HOOK (ROOT)")
    print("=" * 70)
    print(f"  sys.path[0]: {sys.path[0]}")
    print(f"  cwd: {os.getcwd()}")
    print("=" * 70 + "\n")
