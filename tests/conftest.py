import sys
import os

print("\n" + "=" * 70)
print("TESTS/CONFTEST.PY EXECUTING")
print("=" * 70)

# ===== ABSOLUTE CRITICAL: Setup sys.path BEFORE anything else =====
# This code runs at conftest.py import time (earliest possible)
# Use os.path.realpath() for absolute path resolution, not relying on cwd
conftest_file = os.path.realpath(__file__)
conftest_dir = os.path.dirname(conftest_file)  # /path/to/tests
project_root = os.path.dirname(conftest_dir)   # /path/to/project

print(f"conftest_file: {conftest_file}")
print(f"conftest_dir: {conftest_dir}")
print(f"project_root: {project_root}")

# Verify project root is correct
backend_path = os.path.join(project_root, 'Backend_old')
if not os.path.exists(backend_path):
    raise RuntimeError(
        f"Backend_old not found at {backend_path}. "
        f"conftest.py at: {conftest_file}, "
        f"calculated project_root: {project_root}"
    )

print(f"Backend_old verified at: {backend_path}")

# Force project root to be first in sys.path
while project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)
print(f"sys.path[0] set to: {sys.path[0]}")

# Change to project root immediately
os.chdir(project_root)
print(f"Changed to cwd: {os.getcwd()}")

# Set environment variables BEFORE anything imports the app
os.environ["DEV_BYPASS_AUTH"] = "1"
os.environ["FIREBASE_CREDENTIAL_PATH"] = "Backend_old/firebase-service-account.json"
print("Environment variables set")

print("=" * 70)
print("TESTS/CONFTEST.PY SETUP COMPLETE")
print("=" * 70 + "\n")


def pytest_configure(config):
    """
    Pytest configuration hook - runs before test collection.
    Ensures sys.path is configured before pytest tries to collect test modules.
    """
    global project_root
    print("\n" + "=" * 70)
    print("pytest_configure HOOK (TESTS)")
    print("=" * 70)
    
    # Re-apply setup as extra insurance
    while project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)
    
    print(f"  Project root: {project_root}")
    print(f"  sys.path[0]: {sys.path[0]}")
    print(f"  cwd: {os.getcwd()}")
    print(f"  Backend_old exists: {os.path.exists(os.path.join(project_root, 'Backend_old'))}")
    print("=" * 70 + "\n")

