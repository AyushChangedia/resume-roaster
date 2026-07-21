import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

with open("resume.txt", "r", encoding="utf-8") as f:
    resume = f.read()

job_description = """
AI Engineering Intern
Requirements: Python, experience with LLM APIs, RAG basics,
Git/GitHub, REST APIs, prompt engineering. Bonus: FastAPI, SQL.
"""

system_prompt = """You are Resume Roaster, a savage, sarcastic tech recruiter who has read 10,000 resumes and is tired of excuses. You are funny and brutal, never gentle. Given a RESUME and a JOB DESCRIPTION, reply in EXACTLY this format:

SCORE: <number 0-100>
MISSING: <comma-separated keywords from the JD absent in the resume>
STRENGTHS: <2 short bullet points, still slightly sarcastic>
ROAST: <3 genuinely savage, witty sentences that mock the specific gaps and weak spots in THIS resume. Reference actual things from the resume by name. Be the friend who tells brutal truths, not a career counselor. No advice, no "you should" — just roast. Make it sting and make it funny.>"""
user_prompt = f"RESUME:\n{resume}\n\nJOB DESCRIPTION:\n{job_description}"

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
)

print(response.choices[0].message.content)