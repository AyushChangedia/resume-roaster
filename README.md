# 🔥 Resume Roaster

A full-stack AI web app that scores your resume against a job description — and roasts your gaps without mercy.

Paste your resume, paste a job description, hit the button, and get judged by an LLM playing a savage tech recruiter.

## What it does

- **SCORE** — how well you match, 0–100
- **MISSING** — keywords from the job description your resume lacks
- **STRENGTHS** — what's actually working (still a little sarcastic)
- **ROAST** — a brutally honest, funny take on your weak spots

## Tech Stack

**Backend:** Python · FastAPI · Groq LLM API (Llama 3.3 70B)
**Frontend:** HTML · CSS · JavaScript (fetch)
**Other:** python-dotenv, CORS, prompt engineering

## How it works

A JavaScript frontend sends the resume + job description to a FastAPI backend, which calls an LLM with a carefully engineered prompt and returns structured feedback — rendered live on the page.

## Running locally

1. Clone the repo
2. `pip install fastapi uvicorn groq python-dotenv`
3. Create a `.env` file with your Groq key: `GROQ_API_KEY=your_key`
4. Start the backend: `python -m uvicorn app:app --reload`
5. Open `index.html` in your browser

---
*Built while learning AI engineering and full-stack development — one roast at a time.*
