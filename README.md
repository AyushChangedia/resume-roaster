# 🔥 Resume Roaster

An AI-powered resume analyzer that scores your resume against a job description — and roasts your gaps without mercy.

Built with Python and the Groq LLM API (Llama 3.3 70B).

## What it does

Feed it your resume and a target job description, and it returns:
- **SCORE** — how well you match, 0–100
- **MISSING** — keywords from the job description your resume lacks
- **STRENGTHS** — what's actually working
- **ROAST** — a brutally honest take on where you fall short

## How it works

1. Reads resume text from a file
2. Sends it to an LLM with a job description and a carefully engineered prompt
3. Returns structured, parseable feedback

## Tech

`Python` · `Groq API` · `LLM prompt engineering` · `python-dotenv`

## Running it

1. Clone the repo
2. `pip install groq python-dotenv`
3. Add your Groq API key to a `.env` file: `GROQ_API_KEY=your_key`
4. Put your resume in `resume.txt`
5. `python roaster.py`

---
*Built while learning AI engineering — one roast at a time.*
