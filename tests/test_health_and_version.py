
import os
import sys
import pytest
from importlib import import_module


# Determine project root - this file is in tests/, so go up one level
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)

# Ensure project root is first in sys.path for module resolution
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Ensure current working directory is available (for CI environments)
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

# Change to project root to ensure relative paths work correctly
original_cwd = os.getcwd()
os.chdir(project_root)

# Ensure dev bypass for tests
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "test-version")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")

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
