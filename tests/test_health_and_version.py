
import os
import sys
import pytest
from importlib import import_module


# Ensure dev bypass for tests
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "test-version")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")

# Add project root to sys.path for module resolution
# Handle both local and CI environments
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Also ensure current directory is in path for pytest execution from any location
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

# Import the app dynamically
app_module = import_module("Backend_old.app")
app = app_module.app

@pytest.fixture()
def client():
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
