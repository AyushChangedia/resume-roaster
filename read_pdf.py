from pypdf import PdfReader

reader = PdfReader("resume.pdf")

print(f"This PDF has {len(reader.pages)} page(s).")

text = ""
for page in reader.pages:
    text += page.extract_text()

print("----- EXTRACTED TEXT -----")
print(text)