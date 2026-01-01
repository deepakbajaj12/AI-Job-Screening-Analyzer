
import os
import sys
import pytest
import importlib.util


# Ensure dev bypass for tests
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "test-version")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")

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
