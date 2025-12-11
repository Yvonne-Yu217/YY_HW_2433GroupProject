import pdfplumber
import sys

pdf_path = "/Users/mac/Desktop/Lecture_2433/group_project_121125/Session 11 - Project Part 4 Specification.pdf"

try:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        print(full_text)
except Exception as e:
    print(f"Error reading PDF: {e}")
