import os
import json
import pdfplumber
import docx
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


# ✅ Download NLTK data only if missing
def download_nltk_resources():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')


download_nltk_resources()


# =========================
# 🔹 Text Extraction
# =========================

def extract_text_from_pdf(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + " "
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")
    return text


def extract_text_from_docx(file_path):
    text = ""
    try:
        doc = docx.Document(file_path)
        text = " ".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Error reading DOCX {file_path}: {e}")
    return text


# =========================
# 🔹 Text Cleaning
# =========================

def clean_text(text):
    words = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    words = [w for w in words if w.isalpha() and w not in stop_words]
    return " ".join(words)


# =========================
# 🔹 Main Processing Function
# =========================

def process_resume_folder(input_folder, output_folder):

    os.makedirs(output_folder, exist_ok=True)

    processed_count = 0
    skipped_count = 0

    for file in os.listdir(input_folder):

        file_path = os.path.join(input_folder, file)

        # ✅ Handle file types (case-insensitive)
        if file.lower().endswith(".pdf"):
            text = extract_text_from_pdf(file_path)

        elif file.lower().endswith(".docx"):
            text = extract_text_from_docx(file_path)

        else:
            print(f"Skipped unsupported file: {file}")
            skipped_count += 1
            continue

        # ✅ Skip empty files
        if not text or not text.strip():
            print(f"Skipped empty file: {file}")
            skipped_count += 1
            continue

        clean_resume = clean_text(text)

        # ✅ Dynamic output filename
        base_name = os.path.splitext(file)[0]
        output_file = os.path.join(output_folder, f"{base_name}.json")

        # ✅ Save JSON
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "file_name": file,
                    "raw_text": text,
                    "clean_text": clean_resume
                }, f, indent=4, ensure_ascii=False)

            print(f"Saved: {output_file}")
            processed_count += 1

        except Exception as e:
            print(f"Error saving file {output_file}: {e}")
            skipped_count += 1

    # =========================
    # 🔹 Summary
    # =========================
    print("\n===== Extraction Summary =====")
    print(f"Processed files: {processed_count}")
    print(f"Skipped files: {skipped_count}")
    print("Resume text extraction completed")