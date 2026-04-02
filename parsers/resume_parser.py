import pdfplumber
import docx
import os
import re
import json

def extract_pdf_text(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


def extract_docx_text(file_path):
    doc = docx.Document(file_path)
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return "\n".join(text)


def clean_text(text):

    # remove special characters
    text = re.sub(r'[^\w\s]', ' ', text)

    # remove extra spaces
    text = re.sub(r'\s+', ' ', text)

    # lowercase normalization
    text = text.lower()

    return text


def extract_resume(file_path):

    if file_path.endswith(".pdf"):
        raw_text = extract_pdf_text(file_path)

    elif file_path.endswith(".docx"):
        raw_text = extract_docx_text(file_path)

    else:
        raise ValueError("Unsupported file format")

    cleaned_text = clean_text(raw_text)

    return cleaned_text


def process_resume_folder(input_folder, output_file):

    resumes_data = []

    for file in os.listdir(input_folder):

        file_path = os.path.join(input_folder, file)

        if file.endswith(".pdf") or file.endswith(".docx"):

            text = extract_resume(file_path)

            resumes_data.append({
                "file_name": file,
                "clean_text": text
            })

    with open(output_file, "w") as f:
        json.dump(resumes_data, f, indent=4)

    return resumes_data