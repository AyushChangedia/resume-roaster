# 🔥 Resume Roaster

### An AI web app that scores your resume against a job description and then takes it apart. There is no encouraging section.

Upload or paste your resume, paste a job description, and get read by an LLM playing the hiring manager who looks at it for eleven seconds, decides, and says out loud what everyone else only thinks.

## 🚀 Live Demo

### 👉 **[Try it live: resume-roaster-fr4i.onrender.com](https://resume-roaster-fr4i.onrender.com)**

> ⏳ *Hosted on a free tier — the first load may take ~50 seconds to wake the server, then it's instant.*

## 💡 What it does

Drop in your resume — **PDF, Word, or plain text** — or paste it. Add a target job description. It returns four things:

- **📊 SCORE** — how well you match, 0–100, on a stated curve rather than a vibe
- **❌ MISSING** — keywords from the job description your resume does not have
- **🔥 ROAST** — five sentences, every one of them naming something real from *your* resume
- **⚰️ VERDICT** — one flat line, the thing said as it goes in the no pile

### What it does not return

There is no **STRENGTHS** section. There used to be, and removing it is the point.

Two bullet points about what's working undid everything after them: the roast lands differently when it arrives immediately after a compliment, and the reader gets to stop at the nice part and close the tab. A roaster that also tells you what you're good at is a career counselor wearing a costume.

The prompt says so explicitly — no strengths, no compliments, no encouraging closing line, no "but" — because a model trained to be helpful puts the praise back on its own if you only delete the field.

### The scoring is not generous either

`SCORE: 0-100` with no definition let the model anchor around 70, because 70 feels fair. It now scores on a curve with named bands, and three rules that catch what a padded resume actually does:

| Band | Means |
|------|-------|
| 90–100 | Would interview you today. Almost nobody. |
| 70–89 | Real, evidenced experience in most of what the JD asks for. |
| 50–69 | The keywords are there. The evidence is thin. |
| 30–49 | A course list wearing a resume. |
| 0–29 | Not a candidate for this role. |

A technology listed without a project using it caps the score at 55. Coursework is not experience. A personal project with no users is not production.

### Where the line is

It roasts the document and the choices in it — the claims, the gaps, the padding, the writing. It does not go after anyone's identity, background, name, or worth as a person.

That is not squeamishness, it's what makes it work. A roast lands because the target earned it, and nobody earns it by existing. "Three internships and not one shipped thing" stings because it's true and specific; an insult about who you are is neither, and it isn't about the only thing here you can actually change.

## 📄 Uploading a resume

Drop a file on the box or click to choose one. **PDF, `.docx`, `.txt` and `.md`.**

The extracted text goes **into the textarea, not straight to the model.** That
is deliberate. PDF extraction is lossy and resume layouts are hostile to it —
two columns interleave, tables scramble, icon fonts come out as garbage — so
you get to see what was actually read before paying for a roast of it. Nothing
is roasted until you press the button.

The file type is decided by its **bytes, not its name**: a PNG renamed
`resume.pdf` is refused, and a `.docx` renamed `.pdf` is read anyway, because
that mistake is common and the content is fine.

Four things it will not read, each of which tells you what to do instead:

| | |
|---|---|
| **A scanned PDF** | A photo of a page has no text in it. `pypdf` returns an empty string rather than an error, so this is caught by length — otherwise it would upload as a blank resume and get roasted for being empty. |
| **A password-protected PDF** | Tried with an empty password first, which opens the "restricted against editing" case Word produces. |
| **A `.doc`** | The old binary format. Save it as `.docx`. |
| **Anything over 5 MB** | Refused after reading 5 MB, not after loading the whole thing. A text-layer resume PDF is tens of kilobytes. |

A resume longer than 20,000 characters is **truncated rather than refused** —
you get the first part in the box and are told how much was cut, instead of a
refusal with nothing to show for it.

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, Uvicorn |
| **AI** | Groq LLM API (Llama 3.3 70B) |
| **Frontend** | HTML, CSS, JavaScript (Fetch API, drag & drop) |
| **Parsing** | pypdf, python-docx |
| **Tests** | pytest — 109 tests, no API key needed |
| **Deployment** | Render |

## ⚙️ How it works

1. The **frontend** either takes pasted text, or POSTs an uploaded file to `/upload` and puts the extracted text in the box.
2. The **frontend** then POSTs the resume and job description to `/roast`.
3. **FastAPI** validates them, builds the prompt, and calls the model.
4. The reply is **parsed server-side** into `score`, `missing`, `roast` and `verdict`, so the page can render the score as a number rather than printing one wall of text.

The API key is loaded from the environment, never committed. `app.py` refuses to start without it, so a misconfigured deploy fails on deploy rather than on the first person who tries it.

## 🖥️ Running locally

```bash
git clone https://github.com/AyushChangedia/resume-roaster.git
cd resume-roaster

pip install -r requirements.txt

echo GROQ_API_KEY=your_key_here > .env

python -m uvicorn app:app --reload
```

Then open **http://127.0.0.1:8000**.

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Every test stubs the model, so the suite needs no API key and cannot spend one.

What's covered is the parsing (the only place a wrong answer is silent — a bad parse renders a blank card that looks exactly like the app working), the endpoint's validation and error handling, and **the prompt itself**.

That last one is the unusual part and the most important. There is no compiler for tone. Nobody softens a prompt on purpose — it happens one reasonable-looking edit at a time until the app is encouraging again. So `tests/test_prompt.py` asserts that the STRENGTHS field is gone, that praise and hedging are banned by name, that the scoring curve still has its bands, and that the "roast the document, not the person" rule is still there. CI runs it as its own step, so when it goes soft the failure says *Tone has not softened* rather than being one red tick among a hundred and nine.

### The CLI

```bash
python roaster.py                              # the bundled sample
RESUME_PATH=my_resume.pdf python roaster.py    # a PDF, a .docx, or text
RESUME_PATH=cv.docx JD_PATH=job.txt python roaster.py
```

Same extractor as the web upload, so anything you can drop on the page works
here. Defaults to `sample_resume.txt`, a synthetic resume built to be worth
roasting. `resume.txt` and `resume.pdf` are gitignored — do not commit your own.

## 🔮 Roadmap

- [x] PDF resume upload (drag & drop) — also Word and plain text
- [ ] OCR, so a scanned resume can be read rather than refused
- [ ] Support for multiple job descriptions at once
- [ ] Shareable roast results

---

*Built while learning AI engineering and full-stack development — one roast at a time.* 🔥
