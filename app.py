import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from prompt import SYSTEM_PROMPT, build_user_prompt

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

@app.post("/roast")
def roast(request: RoastRequest):
    user_prompt = build_user_prompt(request.resume, request.job_description)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return {"result": response.choices[0].message.content}


@app.get("/")
def serve_frontend():
    return FileResponse("index.html")