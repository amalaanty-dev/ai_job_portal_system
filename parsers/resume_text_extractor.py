import os
import json
import pdfplumber
import docx
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download stopwords if not already installed
nltk.download('punkt')
nltk.download('stopwords')


def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + " "
    return text


def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    text = " ".join([para.text for para in doc.paragraphs])
    return text


def clean_text(text):
    words = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    words = [w for w in words if w.isalpha() and w not in stop_words]
    return " ".join(words)


def process_resume_folder(input_folder, output_file):

    all_resumes = []

    for file in os.listdir(input_folder):

        file_path = os.path.join(input_folder, file)

        if file.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)

        elif file.endswith(".docx"):
            text = extract_text_from_docx(file_path)

        else:
            continue

        clean_resume = clean_text(text)

        all_resumes.append({
            "file_name": file,
            "clean_text": clean_resume
        })

    with open(output_file, "w") as f:
        json.dump(all_resumes, f, indent=4)

    print("Resume text extraction completed")