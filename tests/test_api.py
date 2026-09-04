"""
The /roast endpoint, with the model stubbed.

No test here spends a real API call. What is worth checking is everything
around the call: what the endpoint refuses before paying for it, and what it
does when the model fails or answers badly.
"""

import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from groq import APIConnectionError, APIStatusError, APITimeoutError

os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")

import app as app_module  # noqa: E402  (must follow the env var)

VALID = {"resume": "Ayush. Python. Three internships.", "job_description": "AI intern. RAG."}

REPLY = """SCORE: 34
MISSING: RAG, SQL
ROAST: Five sentences of it.
VERDICT: Next."""


@pytest.fixture
def client(monkeypatch):
    """A client whose model call is replaced by a canned reply."""

    def fake_create(**kwargs):
        fake_create.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=REPLY))]
        )

    monkeypatch.setattr(app_module.client.chat.completions, "create", fake_create)
    test_client = TestClient(app_module.app)
    test_client.fake_create = fake_create
    return test_client


def raises(exception):
    def create(**kwargs):
        raise exception

    return create


REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def status_error(code):
    return APIStatusError(
        str(code), response=httpx.Response(code, request=REQUEST), body=None
    )


# ------------------------------------------------------------- the happy path --


def test_a_roast_comes_back_as_fields(client):
    response = client.post("/roast", json=VALID)
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 34
    assert body["missing"] == "RAG, SQL"
    assert body["roast"] == "Five sentences of it."
    assert body["verdict"] == "Next."


def test_the_response_carries_no_strengths_field(client):
    # The page renders whatever fields arrive; a strengths key would be a
    # praise section reappearing through the back door.
    assert "strengths" not in client.post("/roast", json=VALID).json()


def test_the_prompt_and_both_documents_reach_the_model(client):
    client.post("/roast", json=VALID)
    messages = client.fake_create.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "Resume Roaster" in messages[0]["content"]
    assert VALID["resume"] in messages[1]["content"]
    assert VALID["job_description"] in messages[1]["content"]


def test_the_call_carries_a_timeout(client):
    # Without one, a hung connection holds the worker until the platform kills
    # it, long after the browser gave up.
    client.post("/roast", json=VALID)
    assert client.fake_create.kwargs["timeout"] > 0


# ---------------------------------------------------------------- validation --


@pytest.mark.parametrize(
    "payload",
    [
        {"resume": "", "job_description": "jd"},
        {"resume": "   \n  ", "job_description": "jd"},
        {"resume": "cv", "job_description": ""},
        {"resume": "cv"},
        {"job_description": "jd"},
        {},
    ],
)
def test_an_incomplete_request_is_refused_before_the_model_is_called(client, payload):
    # Each of these was previously a paid round trip to be told nothing.
    response = client.post("/roast", json=payload)
    assert response.status_code == 422
    assert not hasattr(client.fake_create, "kwargs"), "the model was called anyway"


def test_an_oversized_resume_is_refused(client):
    response = client.post(
        "/roast",
        json={"resume": "x" * (app_module.MAX_RESUME_CHARS + 1), "job_description": "jd"},
    )
    assert response.status_code == 422


def test_a_resume_at_the_limit_is_accepted(client):
    # The cap is generous on purpose; a real resume must never hit it.
    response = client.post(
        "/roast",
        json={"resume": "x" * app_module.MAX_RESUME_CHARS, "job_description": "jd"},
    )
    assert response.status_code == 200


def test_surrounding_whitespace_is_stripped_before_the_prompt(client):
    client.post("/roast", json={"resume": "  cv  ", "job_description": "  jd  "})
    assert "RESUME:\ncv\n" in client.fake_create.kwargs["messages"][1]["content"]


# ------------------------------------------------------------ upstream errors --


@pytest.mark.parametrize(
    "exception, expected_status",
    [
        (status_error(429), 429),
        (status_error(500), 502),
        (status_error(401), 502),
        (APIConnectionError(request=REQUEST), 504),
        (APITimeoutError(request=REQUEST), 504),
    ],
)
def test_an_upstream_failure_becomes_a_useful_status(
    monkeypatch, exception, expected_status
):
    # All of these used to raise out of the handler as a 500 with a traceback,
    # which the page rendered as the word "undefined".
    monkeypatch.setattr(app_module.client.chat.completions, "create", raises(exception))
    response = TestClient(app_module.app, raise_server_exceptions=False).post(
        "/roast", json=VALID
    )
    assert response.status_code == expected_status
    assert response.json()["detail"], "the page displays this text directly"


def test_a_rate_limit_says_so_rather_than_blaming_the_user(monkeypatch):
    monkeypatch.setattr(
        app_module.client.chat.completions, "create", raises(status_error(429))
    )
    detail = TestClient(app_module.app).post("/roast", json=VALID).json()["detail"]
    assert "rate limited" in detail.lower()


# ----------------------------------------------------------- malformed replies --


def test_an_unparseable_reply_is_returned_rather_than_discarded(monkeypatch):
    # A roast with a missing label is still a perfectly readable roast. Losing
    # one to a formatting slip would be its own bug.
    def create(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="just prose, no labels"))]
        )

    monkeypatch.setattr(app_module.client.chat.completions, "create", create)
    body = TestClient(app_module.app).post("/roast", json=VALID).json()
    assert body["roast"] == "just prose, no labels"
    assert body["score"] is None


# ------------------------------------------------------------------- the page --


def test_the_root_serves_the_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Resume Roaster" in response.text


def test_the_page_promises_no_encouraging_part(client):
    assert "no encouraging part" in client.get("/").text.lower()
