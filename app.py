import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from extraction import SUPPORTED, ExtractionError, extract_text
from parsing import RoastFormatError, parse_roast
from prompt import SYSTEM_PROMPT, build_user_prompt

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MISSING_KEY_MESSAGE = (
    "GROQ_API_KEY is not set. Locally, put it in a .env file next to app.py "
    "(GROQ_API_KEY=your_key_here). On a host, set it as an environment "
    "variable and redeploy."
)

# Raising here used to kill the process at import. On a long-running server
# that is the right trade — it fails at startup, where somebody is watching,
# rather than on the first roast. On a serverless host it is the wrong one:
# the import *is* the request, so a missing key takes down every route,
# including the page itself and /health, and the only thing the browser is
# told is FUNCTION_INVOCATION_FAILED with no clue which function or why.
#
# So the app always starts. The one route that needs the key says so, with
# the message above, and /health reports it before anybody clicks anything.
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MODEL = "llama-3.3-70b-versatile"

# Roughly 4 characters per token, so 20k characters is about 5k tokens of
# resume — comfortably more than any real one, and far short of the context
# limit or a bill worth noticing. A resume longer than this is a mistake, and
# a 200k-character paste is somebody testing what happens.
MAX_RESUME_CHARS = 20_000
MAX_JD_CHARS = 10_000

# An uploaded file is read into memory before it is parsed, so the cap is what
# stops one request from being a memory problem. A text-layer resume PDF is
# tens of kilobytes; 5 MB is generous enough that a real one never hits it and
# small enough that it does not matter if somebody sends a hundred.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# A roast is five sentences. If the model has not started answering in half a
# minute it is not going to, and the browser has long since given up.
REQUEST_TIMEOUT_SECONDS = 30.0

app = FastAPI(title="Resume Roaster")

# The page is served from this same app, so same-origin requests need no CORS
# header at all and the default is an empty list. ALLOWED_ORIGINS exists for
# the case where the frontend is hosted separately; "*" let any site on the
# internet spend this deployment's API quota through a visitor's browser.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )

class RoastRequest(BaseModel):
    resume: str = Field(..., max_length=MAX_RESUME_CHARS)
    job_description: str = Field(..., max_length=MAX_JD_CHARS)

    @field_validator("resume", "job_description")
    @classmethod
    def not_blank(cls, value: str) -> str:
        # A blank field is a paid round trip to be told nothing. The model
        # will happily roast an empty string, at full price.
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

@app.post("/roast")
def roast(request: RoastRequest):
    if client is None:
        # 503, not 500: the service is correctly deployed and the code is
        # fine — it is one environment variable short of being able to work,
        # which is an operator's problem and is worth naming as one.
        raise HTTPException(status_code=503, detail=MISSING_KEY_MESSAGE)

    user_prompt = build_user_prompt(request.resume, request.job_description)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except APIStatusError as error:
        # Rate limits are the one upstream failure a user can act on, so they
        # get their own message rather than the generic one.
        if error.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="The roaster is rate limited right now. Give it a minute.",
            ) from error
        raise HTTPException(
            status_code=502,
            detail="The model refused to answer. Try again in a moment.",
        ) from error
    except (APIConnectionError, APITimeoutError) as error:
        raise HTTPException(
            status_code=504,
            detail="Could not reach the model in time. Try again in a moment.",
        ) from error

    raw = response.choices[0].message.content

    try:
        return parse_roast(raw)
    except RoastFormatError:
        # The roast is still readable even when the labels are not where they
        # should be, so hand it over rather than failing the request.
        return {"score": None, "missing": "", "roast": raw, "verdict": "", "raw": raw}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Turn an uploaded resume into text for the textarea.

    This does not roast anything. It hands back what was extracted so the user
    can read it, fix it, and then press the button — extraction is lossy
    enough that going straight to the model would sometimes roast a layout
    accident rather than a resume.
    """
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That file is bigger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
            "A resume should be a few hundred kilobytes.",
        )

    try:
        text = extract_text(data, file.filename or "")
    except ExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    # Truncating here rather than refusing: somebody who uploads a thesis
    # should get the first twenty thousand characters in the box, see it, and
    # decide — not be told no with nothing to show for it.
    truncated = len(text) > MAX_RESUME_CHARS
    return {
        "text": text[:MAX_RESUME_CHARS],
        "filename": file.filename or "",
        "characters": len(text),
        "truncated": truncated,
    }


@app.get("/health")
def health():
    """
    What is actually running.

    Exists because "the upload does not work" has two very different causes —
    a bug, or a deploy that has not picked up the new code — and from a
    browser they look identical. Loading this says which: if `upload` is
    false or the key is absent, the running build predates the upload feature.
    """
    return {
        "status": "ok" if client is not None else "degraded",
        "upload": "/upload" in {route.path for route in app.routes if hasattr(route, "path")},
        "formats": sorted(SUPPORTED),
        "model": MODEL,
        # The single most common reason a working deploy cannot roast anything.
        "groq_key": client is not None,
    }


@app.get("/formats")
def formats():
    """What the file picker should accept. Built from one table in extraction.py."""
    return {"extensions": sorted(SUPPORTED), "labels": SUPPORTED}


# Resolved from this file, not from the working directory. FileResponse was
# given the bare name "index.html", which only finds the page when the process
# happens to have been started in the repository root. A serverless host runs
# the handler from wherever it unpacked the bundle, so the one route a visitor
# actually lands on answered 500 while every API route beneath it worked.
INDEX_HTML = Path(__file__).resolve().parent / "index.html"


@app.get("/")
def serve_frontend():
    return FileResponse(INDEX_HTML)