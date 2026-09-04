"""
Roast a resume from the terminal.

    python roaster.py
    RESUME_PATH=my_resume.txt python roaster.py
    RESUME_PATH=cv.txt JD_PATH=job.txt python roaster.py

Same prompt and same parser as the web app, so the CLI and the browser cannot
disagree about what a resume scores.
"""

import os
import sys

from dotenv import load_dotenv
from groq import APIError, Groq

from parsing import RoastFormatError, parse_roast
from prompt import SYSTEM_PROMPT, build_user_prompt

load_dotenv()

MODEL = "llama-3.3-70b-versatile"

# sample_resume.txt is a synthetic stand-in. Point RESUME_PATH at your own file
# to roast it — just do not commit that file to a public repository.
RESUME_PATH = os.getenv("RESUME_PATH", "sample_resume.txt")
JD_PATH = os.getenv("JD_PATH")

DEFAULT_JOB_DESCRIPTION = """
AI Engineering Intern
Requirements: Python, experience with LLM APIs, RAG basics,
Git/GitHub, REST APIs, prompt engineering. Bonus: FastAPI, SQL.
"""

RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Escape codes in a redirected file are noise, so they are dropped when the
# output is not a terminal.
if not sys.stdout.isatty():
    RED = BOLD = DIM = RESET = ""


def read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        sys.exit(f"No such file: {path}")


def band_for(score: int) -> str:
    """The same bands the prompt scores against, in the reader's words."""
    if score >= 90:
        return "They would interview you today. Suspicious."
    if score >= 70:
        return "Real experience in most of what they asked for."
    if score >= 50:
        return "The keywords are there. The evidence is thin."
    if score >= 30:
        return "A course list wearing a resume."
    return "Not a candidate for this role."


def heading(text: str) -> str:
    return f"\n{DIM}{text.upper()}{RESET}\n{DIM}{'─' * len(text)}{RESET}"


def main() -> int:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        sys.exit(
            "GROQ_API_KEY is not set. Put it in a .env file next to this "
            "script (GROQ_API_KEY=your_key_here) or set it in the environment."
        )

    resume = read(RESUME_PATH)
    job_description = read(JD_PATH) if JD_PATH else DEFAULT_JOB_DESCRIPTION

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(resume, job_description)},
            ],
            timeout=30.0,
        )
    except APIError as error:
        sys.exit(f"The model call failed: {error}")

    raw = response.choices[0].message.content

    try:
        result = parse_roast(raw)
    except RoastFormatError:
        # The roast is readable even when the labels are not where they should
        # be. Print it rather than losing it to a formatting slip.
        print(raw)
        return 0

    if result["score"] is not None:
        print(f"\n{BOLD}{RED}{result['score']}{RESET}{DIM}/100{RESET}  {band_for(result['score'])}")

    if result["missing"]:
        print(heading("Missing"))
        print(result["missing"])

    print(heading("Roast"))
    print(result["roast"])

    if result["verdict"]:
        print(heading("Verdict"))
        print(f"{BOLD}{result['verdict']}{RESET}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
