import os
import sys
import pytest

# Ensure environment is set
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "test-version")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json")


@pytest.fixture(scope="session", autouse=True)
def setup_app_module():
    """Load the Flask app module - lazy import happens here after conftest setup"""
    import importlib.util
    
    # Load Backend_old.app module
    spec = importlib.util.find_spec("Backend_old.app")
    if spec is None:
        import sys as sys_debug
        raise ImportError(
            f"Cannot find Backend_old.app module.\n"
            f"sys.path: {sys_debug.path}\n"
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


def test_sys_info(client):
    r = client.get('/internal/sys-info')
    assert r.status_code == 200
    data = r.get_json()
    assert 'platform' in data
    assert 'python_version' in data
    assert 'cpu_count' in data


def test_process_info(client):
    r = client.get('/internal/process-info')
    assert r.status_code == 200
    data = r.get_json()
    assert 'pid' in data
    assert 'thread_count' in data


