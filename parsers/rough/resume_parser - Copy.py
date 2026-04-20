import pdfplumber
import docx
import os
import re
import json

# Project folders
INPUT_FOLDER = "data/resumes/raw_resumes/"
OUTPUT_FOLDER = "data/resumes/parsed_resumes/json/"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def extract_pdf_text(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_docx_text(file_path):
    doc = docx.Document(file_path)
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return "\n".join(text)


def clean_text(text):

    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.lower()

    return text


def extract_resume(file_path):

    if file_path.endswith(".pdf"):
        raw_text = extract_pdf_text(file_path)

    elif file_path.endswith(".docx"):
        raw_text = extract_docx_text(file_path)

    else:
        return None

    cleaned_text = clean_text(raw_text)

    return cleaned_text


def process_resumes():

    for file in os.listdir(INPUT_FOLDER):

        file_path = os.path.join(INPUT_FOLDER, file)

        if file.endswith(".pdf") or file.endswith(".docx"):

            text = extract_resume(file_path)

            resume_data = {
                "resume_name": file,
                "clean_text": text
            }

            output_file = os.path.join(
                OUTPUT_FOLDER,
                file.replace(".pdf", ".json").replace(".docx", ".json")
            )

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(resume_data, f, indent=4)

            print(f"Parsed: {file}")


if __name__ == "__main__":
    process_resumes()