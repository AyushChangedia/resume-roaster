import pdfplumber

with pdfplumber.open("resume.pdf") as pdf:
    text = ""
    for page in pdf.pages:
        text += page.extract_text() or ""

print("----- EXTRACTED TEXT -----")
print(text)