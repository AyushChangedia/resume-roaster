import os
from dotenv import load_dotenv
from groq import Groq

from prompt import SYSTEM_PROMPT, build_user_prompt

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

with open("resume.txt", "r", encoding="utf-8") as f:
    resume = f.read()

job_description = """
AI Engineering Intern
Requirements: Python, experience with LLM APIs, RAG basics,
Git/GitHub, REST APIs, prompt engineering. Bonus: FastAPI, SQL.
"""

user_prompt = build_user_prompt(resume, job_description)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
)

print(response.choices[0].message.content)