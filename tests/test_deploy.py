"""
The things a deploy breaks, which no other test can see.

Every other suite imports `app` with a key already in the environment and a
working directory of the repository root — the two conditions a serverless
host does not provide. Both of the failures these cover produced the same
thing in a browser: a 500 with nothing in it.
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

VALID = {"resume": "Ayush. Python. Three internships.", "job_description": "AI intern. RAG."}


@pytest.fixture
def keyless(monkeypatch):
    """The app as it is imported on a host where GROQ_API_KEY was never set."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # load_dotenv() at import would put the developer's own .env back.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)

    import app as app_module

    module = importlib.reload(app_module)
    yield module

    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-used")
    importlib.reload(app_module)



# ------------------------------------------------------- a missing API key --

def test_the_app_imports_without_a_key(keyless):
    """
    The regression that produced FUNCTION_INVOCATION_FAILED.

    It used to raise at import, and on a serverless host the import is the
    request — so every route died, including the ones that never touch Groq,
    and the browser was told only that a function had failed.
    """
    assert keyless.client is None


def test_the_page_still_loads_without_a_key(keyless):
    response = TestClient(keyless.app).get("/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_the_routes_that_do_not_need_the_key_still_work(keyless):
    client = TestClient(keyless.app)
    assert client.get("/formats").status_code == 200
    assert client.get("/health").status_code == 200


def test_health_says_the_key_is_missing(keyless):
    body = TestClient(keyless.app).get("/health").json()
    assert body["groq_key"] is False
    assert body["status"] == "degraded"


def test_roasting_without_a_key_is_503_and_says_what_to_do(keyless):
    # 503, not 500: the deploy is fine and the code is fine. It is one
    # environment variable short, which is an operator's problem.
    response = TestClient(keyless.app).post("/roast", json=VALID)
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_uploading_without_a_key_still_works(keyless):
    # Extraction never touches the model, so a missing key must not block it.
    client = TestClient(keyless.app)
    response = client.post(
        "/upload", files={"file": ("resume.txt", b"Ayush. Python.", "text/plain")}
    )
    assert response.status_code == 200
    assert "Ayush" in response.json()["text"]


def test_health_says_the_key_is_present_when_it_is():
    import app as app_module

    assert app_module.client is not None
    body = TestClient(app_module.app).get("/health").json()
    assert body["groq_key"] is True
    assert body["status"] == "ok"


# ------------------------------------------------- the page, from anywhere --

def test_index_is_found_from_an_unrelated_working_directory(tmp_path):
    """
    The second deploy-only failure: FileResponse was given a bare filename,
    which resolves against the working directory. Locally that is the
    repository root; on a host it is wherever the bundle was unpacked.
    """
    script = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from fastapi.testclient import TestClient\n"
        "import app\n"
        "r = TestClient(app.app).get('/')\n"
        "print(json.dumps({'status': r.status_code, 'html': '<!DOCTYPE html>' in r.text}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "GROQ_API_KEY": "test-key-not-used"},
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == 200
    assert payload["html"] is True


def test_the_index_path_is_absolute():
    import app as app_module

    assert app_module.INDEX_HTML.is_absolute()
    assert app_module.INDEX_HTML.is_file()


# --------------------------------------------------------- the entry point --

def test_vercel_handler_exports_the_same_app():
    sys.path.insert(0, str(ROOT / "api"))
    import index

    import app as app_module

    assert index.app is app_module.app


def test_vercel_json_routes_everything_to_the_one_function():
    config = json.loads((ROOT / "vercel.json").read_text())
    rewrites = config["rewrites"]
    assert any(r["source"] == "/(.*)" for r in rewrites), rewrites
    assert all(r["destination"] == "/api/index" for r in rewrites)


def test_the_function_outlasts_the_model_timeout():
    # The roast waits on Groq for 30 seconds. A function cut off before that
    # turns a slow model into a platform error with nothing to read.
    import app as app_module

    config = json.loads((ROOT / "vercel.json").read_text())
    max_duration = config["functions"]["api/index.py"]["maxDuration"]
    assert max_duration > app_module.REQUEST_TIMEOUT_SECONDS


def test_the_bundle_leaves_out_what_it_does_not_run():
    ignored = {
        line.strip()
        for line in (ROOT / ".vercelignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert "tests/" in ignored
    assert "requirements-dev.txt" in ignored
