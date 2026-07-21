print("1. script started")

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
print("3. calling the API...")

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Roast my empty resume in one savage sentence."}]
)

print("4. reply received:")
print(response.choices[0].message.content)