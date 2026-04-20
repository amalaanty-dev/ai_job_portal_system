import pdfplumber
import docx
import os
import re
import json

# Project folders
INPUT_FOLDER = "data/resumes/raw_resumes/"
OUTPUT_FOLDER = "data/resumes/parsed_resumes/json/"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────
# Text Extraction
# ─────────────────────────────────────────────

def extract_pdf_text(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_docx_text(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs)


def extract_raw_text(file_path: str):
    if file_path.endswith(".pdf"):
        return extract_pdf_text(file_path)
    elif file_path.endswith(".docx"):
        return extract_docx_text(file_path)
    return None


# ─────────────────────────────────────────────
# Clean Text
# ─────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


# ─────────────────────────────────────────────
# Extract Name
# ─────────────────────────────────────────────

def extract_name(text: str):
    lines = text.strip().splitlines()
    for line in lines[:5]:  # Name is usually in the first few lines
        line = line.strip()
        # Skip emails, phone numbers, URLs, and short/empty lines
        if not line:
            continue
        if re.search(r'[@:/\\]', line):
            continue
        if re.search(r'\d{5,}', line):
            continue
        if len(line.split()) < 2:
            continue
        # Check it looks like a name (only letters, spaces, dots, hyphens)
        if re.match(r'^[A-Za-z][A-Za-z\s.\-]{2,40}$', line):
            return line.strip()
    return None


# ─────────────────────────────────────────────
# Extract Skills
# ─────────────────────────────────────────────

SKILLS_DB = [
    # Programming Languages
    "python", "java", "javascript", "typescript", "c", "c++", "c#", "r", "scala",
    "go", "golang", "kotlin", "swift", "ruby", "php", "perl", "bash", "shell",
    "matlab", "rust", "dart", "vba",
    # Web
    "html", "css", "react", "angular", "vue", "node.js", "nodejs", "django",
    "flask", "fastapi", "spring", "spring boot", "express", "bootstrap", "tailwind",
    # Data & ML
    "sql", "mysql", "postgresql", "mongodb", "sqlite", "oracle", "nosql",
    "machine learning", "deep learning", "nlp", "computer vision", "data analysis",
    "data science", "data engineering", "statistics", "pandas", "numpy", "scipy",
    "matplotlib", "seaborn", "scikit-learn", "sklearn", "tensorflow", "keras",
    "pytorch", "xgboost", "lightgbm", "opencv", "nltk", "spacy", "transformers",
    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "jenkins",
    "git", "github", "gitlab", "bitbucket", "ci/cd", "terraform", "ansible",
    "linux", "unix", "hadoop", "spark", "kafka", "airflow",
    # BI & Analytics
    "power bi", "tableau", "excel", "google sheets", "looker", "qlik",
    # Soft Skills
    "communication", "teamwork", "leadership", "problem solving", "time management",
    "project management", "agile", "scrum", "jira", "confluence",
]


def extract_skills(text: str):
    text_lower = text.lower()
    found = []
    for skill in SKILLS_DB:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            if skill.upper() in ["SQL", "AWS", "GCP", "HTML", "CSS", "NLP",
                                  "VBA", "PHP", "API", "CI/CD"]:
                found.append(skill.upper())
            else:
                found.append(skill.title())
    return list(dict.fromkeys(found))  # Remove duplicates, preserve order


# ─────────────────────────────────────────────
# Extract Experience
# ─────────────────────────────────────────────

def extract_experience(text: str):
    text_lower = text.lower()

    # Pattern: "3 years", "3+ years", "3.5 years of experience"
    patterns = [
        r'(\d+\.?\d*)\s*\+?\s*years?\s+of\s+experience',
        r'(\d+\.?\d*)\s*\+?\s*years?\s+experience',
        r'experience\s+of\s+(\d+\.?\d*)\s*\+?\s*years?',
        r'(\d+\.?\d*)\s*\+?\s*years?\s+of\s+work',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return float(match.group(1))

    # Fallback: count year ranges like "2020 - 2023" or "Jan 2019 - Mar 2022"
    year_ranges = re.findall(r'\b(20\d{2}|19\d{2})\b.*?\b(20\d{2}|19\d{2}|present|current)\b',
                             text_lower)
    if year_ranges:
        total = 0
        current_year = 2025
        for start, end in year_ranges:
            try:
                s = int(start)
                e = current_year if end in ("present", "current") else int(end)
                if e >= s:
                    total += e - s
            except ValueError:
                continue
        if total > 0:
            return round(total, 1)

    return None


# ─────────────────────────────────────────────
# Extract Education
# ─────────────────────────────────────────────

EDUCATION_KEYWORDS = [
    "ph.d", "phd", "doctor of philosophy",
    "m.tech", "mtech", "m.e", "master of technology", "master of engineering",
    "m.sc", "msc", "master of science",
    "mba", "master of business administration",
    "m.a", "master of arts",
    "b.tech", "btech", "b.e", "bachelor of technology", "bachelor of engineering",
    "b.sc", "bsc", "bachelor of science",
    "b.com", "bcom", "bachelor of commerce",
    "b.a", "bachelor of arts",
    "be", "bca", "mca", "b.ca", "m.ca",
    "diploma", "associate degree", "high school", "12th", "10th",
]


def extract_education(text: str):
    text_lower = text.lower()
    for keyword in EDUCATION_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            return keyword.upper()
    return None


# ─────────────────────────────────────────────
# Main Parser
# ─────────────────────────────────────────────

def parse_resume(raw_text: str) -> dict:
    cleaned = clean_text(raw_text)
    return {
        "name":       extract_name(cleaned),
        "skills":     extract_skills(cleaned),
        "experience": extract_experience(cleaned),
        "education":  extract_education(cleaned),
        "clean_text": cleaned,
    }


def process_resumes():
    files = [
        f for f in os.listdir(INPUT_FOLDER)
        if f.endswith(".pdf") or f.endswith(".docx")
    ]

    if not files:
        print(f"No PDF or DOCX files found in '{INPUT_FOLDER}'.")
        return

    for file in files:
        file_path = os.path.join(INPUT_FOLDER, file)
        print(f"Processing: {file}")

        raw_text = extract_raw_text(file_path)
        if not raw_text:
            print(f"  x  Could not extract text. Skipping.")
            continue

        parsed = parse_resume(raw_text)

        resume_data = {
            "resume_name": file,
            "name":        parsed["name"],
            "skills":      parsed["skills"],
            "experience":  parsed["experience"],
            "education":   parsed["education"],
            "clean_text":  parsed["clean_text"]
        }

        output_file = os.path.join(
            OUTPUT_FOLDER,
            file.replace(".pdf", ".json").replace(".docx", ".json")
        )

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(resume_data, f, indent=4, ensure_ascii=False)

        print(f"  OK  Saved -> {output_file}")
        print(f"     Name      : {parsed['name']}")
        print(f"     Skills    : {parsed['skills']}")
        print(f"     Experience: {parsed['experience']} years")
        print(f"     Education : {parsed['education']}\n")


if __name__ == "__main__":
    process_resumes()