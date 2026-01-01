import os
import sys
import pytest
import importlib.util

# ===== DEFENSIVE: Ensure project root is in sys.path BEFORE any imports =====
# This is critical insurance in case conftest.py doesn't run first in CI
# Use realpath to handle symlinks and relative paths correctly
test_file = os.path.realpath(__file__)
tests_dir = os.path.dirname(test_file)
_project_root = os.path.dirname(tests_dir)

# Insert at beginning if not already there (first occurrence only)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
else:
    # Move it to the front if it's already in the path
    sys.path.remove(_project_root)
    sys.path.insert(0, _project_root)

os.chdir(_project_root)

# Ensure dev bypass for tests
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "test-version")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")


@pytest.fixture(scope="session", autouse=True)
def setup_app_module():
    """Load the Flask app module - this fixture runs before any tests"""
    # Load Backend_old.app module
    spec = importlib.util.find_spec("Backend_old.app")
    if spec is None:
        raise ImportError(
            f"Cannot find Backend_old.app module.\n"
            f"Project root in sys.path: {sys.path}\n"
            f"Current directory: {os.getcwd()}"
        )
    app_module = importlib.util.module_from_spec(spec)
    sys.modules["Backend_old.app"] = app_module
    spec.loader.exec_module(app_module)
    return app_module


# This will be set by the setup_app_module fixture
app = None

def _load_app():
    """Get the app from sys.modules after fixture loads it"""
    return sys.modules.get("Backend_old.app").app

@pytest.fixture()
def client(setup_app_module):
    """Create a test client for the Flask app"""
    app = _load_app()
    app.config.update({
        "TESTING": True
    })
    with app.test_client() as c:
        yield c

def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'ok'
    assert 'version' in data


def test_version(client):
    r = client.get('/version')
    assert r.status_code == 200
    data = r.get_json()
    assert data['version'] == 'test-version'
