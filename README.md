# 🔥 Resume Roaster

### An AI web app that scores your resume against any job description — and roasts your gaps without mercy.

Paste your resume, paste a job description, and get judged by an LLM playing a savage tech recruiter who has read 10,000 resumes and is tired of excuses.

## 🚀 Live Demo

### 👉 **[Try it live: resume-roaster-fr4i.onrender.com](https://resume-roaster-fr4i.onrender.com)**

> ⏳ *Hosted on a free tier — the first load may take ~50 seconds to wake the server, then it's instant.*
> 

## 💡 What it does

Feed it your resume and a target job description, and it returns:

- **📊 SCORE** — how well you match, 0–100
- **❌ MISSING** — keywords from the job description your resume is missing
- **✅ STRENGTHS** — what's actually working (with a hint of sarcasm)
- **🔥 ROAST** — a brutally honest, genuinely funny take on your weak spots

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, Uvicorn |
| **AI** | Groq LLM API (Llama 3.3 70B) |
| **Frontend** | HTML, CSS, JavaScript (Fetch API) |
| **Concepts** | REST API design, prompt engineering, CORS, environment-based secrets |
| **Deployment** | Render |

## ⚙️ How it works

1. A **JavaScript frontend** collects the resume + job description and sends them to the backend via a `fetch` POST request.
2. A **FastAPI backend** receives the data, injects it into a carefully engineered prompt, and calls an LLM.
3. The model returns **structured feedback** (score, gaps, strengths, roast), which is rendered live on the page.

The API key is never stored in code — it's loaded from an environment variable, keeping secrets out of the repo.

## 🖥️ Running locally

```bash
# 1. Clone the repo
git clone https://github.com/AyushChangedia/resume-roaster.git
cd resume-roaster

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Groq API key to a .env file
echo GROQ_API_KEY=your_key_here > .env

# 4. Start the server
python -m uvicorn app:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

## 🔮 Roadmap

- [ ] PDF resume upload (drag & drop)
- [ ] Support for multiple job descriptions at once
- [ ] Shareable roast results

---

*Built while learning AI engineering and full-stack development — one roast at a time.* 🔥
