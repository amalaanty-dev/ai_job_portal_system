# resume parser- good

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
    from experience_parser import build_structured_experience

INPUT_FOLDER = "data/resumes/raw_resumes/"
OUTPUT_FOLDER = "data/resumes/parsed_resumes/json/"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ─────────────────────────────────────────────
# Global Field Extraction Logic
# ─────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def extract_name(text: str):
    lines = text.strip().splitlines()
    for line in lines[:8]:
        line = line.strip()
        if not line or re.search(r'[@:/\\]', line) or re.search(r'\d{5,}', line):
            continue
        if 2 <= len(line.split()) <= 4 and re.match(r'^[A-Z][A-Za-z\s.\-]{2,40}$', line):
            return line.strip()
    return "Unknown"

# ─────────────────────────────────────────────
# UPDATED: Full Education Extraction
# ─────────────────────────────────────────────

def extract_full_education(text: str) -> list:
    """
    Extracts multiple education entries including degree, 
    specialization, and year.
    """
    education_list = []
    
    # Global Degree patterns
    DEGREE_PATTERN = r'\b(PH\.?D|MBA|B\.?TECH|M\.?TECH|B\.?SC|M\.?SC|BBA|BCA|MCA|BACHELOR OF [A-Z]+|MASTER OF [A-Z]+)\b'
    # Year pattern (e.g., 2016 - 2018 or 2018)
    YEAR_PATTERN = r'\b(20\d{2})\b'

    lines = text.splitlines()
    for i, line in enumerate(lines):
        # Look for a line containing a degree keyword
        degree_match = re.search(DEGREE_PATTERN, line, re.IGNORECASE)
        if degree_match:
            # Check current line and next line for a year
            context = line + " " + (lines[i+1] if i+1 < len(lines) else "")
            years = re.findall(YEAR_PATTERN, context)
            
            education_list.append({
                "degree": degree_match.group(0).upper().replace(".", ""),
                "full_line": line.strip(),
                "years": years if years else []
            })
            
    # Deduplicate based on degree type
    seen = set()
    unique_edu = []
    for edu in education_list:
        if edu["degree"] not in seen:
            unique_edu.append(edu)
            seen.add(edu["degree"])
            
    return unique_edu

# ─────────────────────────────────────────────
# Orchestration Logic
# ─────────────────────────────────────────────

def parse_resume(raw_text: str) -> dict:
    cleaned = clean_text(raw_text)
    
    # Use advanced experience engine
    exp_data = build_structured_experience(cleaned)
    
    return {
        "name":       extract_name(cleaned),
        "roles":      exp_data["entries"],
        "experience": round(exp_data["total_experience_months"] / 12, 1),
        "education":  extract_full_education(cleaned), # Now returns list of objects
        "clean_text": cleaned,
    }

def process_resumes():
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith((".pdf", ".docx"))]

    for file in files:
        file_path = os.path.join(INPUT_FOLDER, file)
        print(f"Processing: {file}")

        # Text extraction logic (assumed helper)
        raw_text = ""
        if file_path.endswith(".pdf"):
            with pdfplumber.open(file_path) as pdf:
                raw_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        else:
            doc = docx.Document(file_path)
            raw_text = "\n".join(p.text for p in doc.paragraphs)

        parsed = parse_resume(raw_text)

        output_data = {
            "resume_name": file,
            "name":        parsed["name"],
            "roles":       parsed["roles"],
            "experience":  parsed["experience"],
            "education":   parsed["education"],
            "clean_text":  parsed["clean_text"]
        }

        output_path = os.path.join(OUTPUT_FOLDER, os.path.splitext(file)[0] + ".json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        print(f"  OK Saved -> {output_path}")

if __name__ == "__main__":
    process_resumes()