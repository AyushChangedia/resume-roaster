"""
The /upload endpoint.

The extraction itself is covered in test_extraction.py. What is tested here is
the layer around it: the size cap, the mapping from extraction failure to HTTP
status, and the fact that nothing on this path reaches the model.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")

import app as app_module  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    return TestClient(app_module.app)


def upload(client, name, data=None):
    payload = data if data is not None else (FIXTURES / name).read_bytes()
    return client.post("/upload", files={"file": (name, payload)})


# ---------------------------------------------------------------- happy path --


@pytest.mark.parametrize("name", ["resume.pdf", "resume.docx", "table_resume.docx", "resume.txt"])
def test_an_uploaded_resume_comes_back_as_text(client, name):
    response = upload(client, name)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Jordan Avery Blake" in body["text"]
    assert body["filename"] == name
    assert body["characters"] == len(body["text"])
    assert body["truncated"] is False


def test_upload_does_not_roast_anything(client, monkeypatch):
    # /upload fills the textarea. The roast is a separate, deliberate press of
    # the button — uploading must never be a billed model call.
    def explode(**kwargs):
        raise AssertionError("the model was called during an upload")

    monkeypatch.setattr(app_module.client.chat.completions, "create", explode)
    assert upload(client, "resume.pdf").status_code == 200


def test_the_response_carries_no_roast_fields(client):
    body = upload(client, "resume.pdf").json()
    for field in ("score", "roast", "verdict"):
        assert field not in body


# ----------------------------------------------------------------- refusals --


@pytest.mark.parametrize(
    "name, expected_fragment",
    [
        ("scanned.pdf", "scan"),
        ("encrypted.pdf", "password"),
        ("image.png", "does not look like"),
    ],
)
def test_an_unreadable_file_is_422_with_a_reason(client, name, expected_fragment):
    response = upload(client, name)
    assert response.status_code == 422
    assert expected_fragment in response.json()["detail"]


def test_an_empty_upload_is_refused(client):
    response = upload(client, "empty.pdf", data=b"")
    assert response.status_code == 422
    assert "empty" in response.json()["detail"]


def test_a_request_with_no_file_at_all_is_refused(client):
    assert client.post("/upload").status_code == 422


def test_an_oversized_file_is_413_and_says_the_limit(client):
    oversized = b"%PDF-" + b"x" * (app_module.MAX_UPLOAD_BYTES + 1)
    response = upload(client, "huge.pdf", data=oversized)
    assert response.status_code == 413
    assert "5 MB" in response.json()["detail"]


def test_a_file_at_the_limit_is_read_rather_than_refused(client):
    # The cap is generous on purpose; a real resume must never reach it.
    padded = (FIXTURES / "resume.txt").read_bytes()
    padded += b"\n" + b"x" * (app_module.MAX_UPLOAD_BYTES - len(padded) - 1)
    assert len(padded) == app_module.MAX_UPLOAD_BYTES
    assert upload(client, "big.txt", data=padded).status_code == 200


# -------------------------------------------------------------- truncation --


def test_a_huge_resume_is_truncated_rather_than_refused(client):
    # Somebody who uploads a thesis should see the first part of it in the box
    # and decide for themselves, not be told no with nothing to show for it.
    long_text = ("Jordan Blake\n" + "Experience line.\n" * 4000).encode()
    body = upload(client, "thesis.txt", data=long_text).json()
    assert body["truncated"] is True
    assert len(body["text"]) == app_module.MAX_RESUME_CHARS
    assert body["characters"] > app_module.MAX_RESUME_CHARS


def test_extracted_text_fits_the_roast_endpoint(client, monkeypatch):
    # The two limits have to agree: whatever /upload puts in the box must be
    # accepted by /roast, or the user is handed text they cannot submit.
    from types import SimpleNamespace

    monkeypatch.setattr(
        app_module.client.chat.completions,
        "create",
        lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="SCORE: 1\nROAST: ouch"))]
        ),
    )
    long_text = ("Jordan Blake\n" + "Experience line.\n" * 4000).encode()
    text = upload(client, "thesis.txt", data=long_text).json()["text"]
    assert client.post("/roast", json={"resume": text, "job_description": "jd"}).status_code == 200


# ----------------------------------------------------------------- /formats --


def test_formats_lists_what_the_picker_should_accept(client):
    body = client.get("/formats").json()
    assert ".pdf" in body["extensions"]
    assert ".docx" in body["extensions"]
    assert body["labels"][".pdf"] == "PDF"


def test_formats_matches_the_extraction_table(client):
    from extraction import SUPPORTED

    assert client.get("/formats").json()["extensions"] == sorted(SUPPORTED)


# ------------------------------------------------------------------- /health --


def test_health_reports_that_upload_is_available(client):
    # The point of this endpoint: "the upload does not work" is either a bug or
    # a stale deploy, and from a browser those look identical. A build without
    # the feature answers 404 here, or answers with upload false.
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["upload"] is True
    assert ".pdf" in body["formats"]


def test_health_needs_no_api_call(client, monkeypatch):
    def explode(**kwargs):
        raise AssertionError("the model was called by a health check")

    monkeypatch.setattr(app_module.client.chat.completions, "create", explode)
    assert client.get("/health").status_code == 200
