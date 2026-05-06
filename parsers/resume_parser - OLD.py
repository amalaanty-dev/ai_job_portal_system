import pdfplumber
import docx
import os
import re
import json
import sys

# ─────────────────────────────────────────────
# Path Setup & Imports
# ─────────────────────────────────────────────

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from experience_engine.experience_parser import build_structured_experience
except ImportError:
    # Fallback for different folder structures
    from experience_parser import build_structured_experience

INPUT_FOLDER = "data/resumes/raw_resumes/"
OUTPUT_FOLDER = "data/resumes/parsed_resumes/json/"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ─────────────────────────────────────────────
# Text Extraction & Cleaning
# ─────────────────────────────────────────────

def extract_raw_text(file_path: str):
    ext = file_path.lower()
    text = ""
    try:
        if ext.endswith(".pdf"):
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        elif ext.endswith(".docx"):
            doc = docx.Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        print(f"  x Error extracting {file_path}: {e}")
    return text

def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

# ─────────────────────────────────────────────
# Attribute Extraction
# ─────────────────────────────────────────────

def extract_name(text: str):
    lines = text.strip().splitlines()
    for line in lines[:10]:
        line = line.strip()
        if not line or re.search(r'[@:/\\]', line) or re.search(r'\d{5,}', line):
            continue
        if 2 <= len(line.split()) <= 4 and re.match(r'^[A-Z][A-Za-z\s.\-]{2,40}$', line):
            return line.strip()
    return "Unknown"

def extract_full_education(text: str) -> list:
    education_list = []
    # Pattern covers common global degree abbreviations
    DEGREE_PATTERN = r'\b(PH\.?D|MBA|B\.?TECH|M\.?TECH|B\.?SC|M\.?SC|BBA|BCA|MCA|BACHELOR OF [A-Z]+|MASTER OF [A-Z]+)\b'
    YEAR_PATTERN = r'\b(20\d{2})\b'

    lines = text.splitlines()
    for i, line in enumerate(lines):
        degree_match = re.search(DEGREE_PATTERN, line, re.IGNORECASE)
        if degree_match:
            # Check current and adjacent lines for graduation years
            context = " ".join(lines[max(0, i-1):min(len(lines), i+2)])
            years = sorted(list(set(re.findall(YEAR_PATTERN, context))))
            
            education_list.append({
                "degree": degree_match.group(0).upper().replace(".", ""),
                "full_line": line.strip(),
                "years": years
            })
            
    # Remove duplicates based on degree name
    unique_edu = []
    seen = set()
    for edu in education_list:
        if edu["degree"] not in seen:
            unique_edu.append(edu)
            seen.add(edu["degree"])
    return unique_edu

# ─────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────

def parse_resume(raw_text: str) -> dict:
    cleaned = clean_text(raw_text)
    exp_data = build_structured_experience(cleaned)
    
    return {
        "name":       extract_name(cleaned),
        "roles":      exp_data["entries"],
        "experience": round(exp_data["total_experience_months"] / 12, 1),
        "education":  extract_full_education(cleaned),
        "clean_text": cleaned,
    }

def process_resumes():
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith((".pdf", ".docx"))]
    if not files:
        print("No resumes found.")
        return

    for file in files:
        print(f"Processing: {file}")
        raw_text = extract_raw_text(os.path.join(INPUT_FOLDER, file))
        if not raw_text: continue

        parsed = parse_resume(raw_text)

        output_path = os.path.join(OUTPUT_FOLDER, os.path.splitext(file)[0] + ".json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({**{"resume_name": file}, **parsed}, f, indent=4)
        
        print(f"  OK Saved -> {output_path}")

if __name__ == "__main__":
    process_resumes()