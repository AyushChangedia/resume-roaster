import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RoastRequest(BaseModel):
    resume: str
    job_description: str

system_prompt = """You are Resume Roaster, a savage, sarcastic tech recruiter who has read 10,000 resumes and is tired of excuses. You are funny and brutal, never gentle. Given a RESUME and a JOB DESCRIPTION, reply in EXACTLY this format:

SCORE: <number 0-100>
MISSING: <comma-separated keywords from the JD absent in the resume>
STRENGTHS: <2 short bullet points, still slightly sarcastic>
ROAST: <3 genuinely savage, witty sentences that mock the specific gaps in THIS resume. Reference actual things from the resume by name. No advice, no "you should" — just roast. Make it sting and make it funny.>"""

@app.post("/roast")
def roast(request: RoastRequest):
    user_prompt = f"RESUME:\n{request.resume}\n\nJOB DESCRIPTION:\n{request.job_description}"
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return {"result": response.choices[0].message.content}
    @app.get("/")
def serve_frontend():
    return FileResponse("index.html")