
import os
import sys
import pytest
from importlib import import_module
import importlib.util


# ===== EARLY SETUP: Must happen before any imports =====
# Determine project root - this file is in tests/, so go up one level
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)

# Change working directory to project root FIRST
os.chdir(project_root)

# Add to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Ensure dev bypass for tests - set before importing app
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "test-version")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")

# ===== IMPORT THE APP =====
# Load using spec to be absolutely sure
spec = importlib.util.find_spec("Backend_old.app")
if spec is None:
    raise ImportError(f"Cannot find Backend_old.app module. Project root: {project_root}, sys.path: {sys.path}")
app_module = importlib.util.module_from_spec(spec)
sys.modules["Backend_old.app"] = app_module
spec.loader.exec_module(app_module)

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
