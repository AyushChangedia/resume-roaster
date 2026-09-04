import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from parsing import RoastFormatError, parse_roast
from prompt import SYSTEM_PROMPT, build_user_prompt

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    # Without this the Groq client is constructed with api_key=None and the
    # first roast fails deep inside an HTTP call, as an authentication error
    # about a request nobody made. Say it at startup, where it is fixable.
    raise RuntimeError(
        "GROQ_API_KEY is not set. Put it in a .env file next to app.py "
        "(GROQ_API_KEY=your_key_here) or set it in the environment."
    )

client = Groq(api_key=GROQ_API_KEY)

MODEL = "llama-3.3-70b-versatile"

# Roughly 4 characters per token, so 20k characters is about 5k tokens of
# resume — comfortably more than any real one, and far short of the context
# limit or a bill worth noticing. A resume longer than this is a mistake, and
# a 200k-character paste is somebody testing what happens.
MAX_RESUME_CHARS = 20_000
MAX_JD_CHARS = 10_000

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


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")