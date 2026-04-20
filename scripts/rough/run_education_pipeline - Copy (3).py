import os
import json
import sys
import re
from datetime import datetime
from difflib import SequenceMatcher

# ----------------------------
# PATH FIX
# ----------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from education_engine.education_parser import extract_education
from education_engine.education_formatter import format_academic_profile


# ----------------------------
# PATH CONFIG
# ----------------------------
RESUME_PATH = "data/resumes/sectioned_resumes/"
JD_PATH = "data/job_descriptions/parsed_jd/"
OUTPUT_DIR = "data/education_outputs/"


# ----------------------------
# SEMANTIC MAP
# ----------------------------
FIELD_SYNONYMS = {
    "data science": ["data science", "machine learning", "ai", "analytics"],
    "biostatistics": ["biostatistics", "statistics", "clinical statistics"],
    "statistics": ["statistics", "biostatistics"],
    "computer science": ["computer science", "software", "programming"],
    "life sciences": ["biology", "biotech", "clinical research"],
    "finance": ["finance", "accounting", "banking"],
    "marketing": ["marketing", "sales", "branding"]
}


# ----------------------------
# CLEAN TEXT
# ----------------------------
def clean(x):
    if isinstance(x, list):
        return " ".join([str(i) for i in x if i]).lower().strip()
    if isinstance(x, str):
        return x.lower().strip()
    return ""


# ----------------------------
# SIMILARITY
# ----------------------------
def sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


# ----------------------------
# RESUME INPUT
# ----------------------------
def get_resume_text(resume_json):
    edu = resume_json.get("education")

    if isinstance(edu, list):
        return clean(edu)
    if isinstance(edu, str):
        return clean(edu)

    return clean(resume_json.get("full_text", "")[:2000])


# ----------------------------
# JD INPUT
# ----------------------------
def get_jd_text(jd_json):
    parts = []

    for k in ["education", "role", "required_skills"]:
        v = jd_json.get(k)

        if isinstance(v, list):
            parts.append(" ".join([str(i) for i in v if i]))
        elif isinstance(v, str):
            parts.append(v)

    return clean(" ".join(parts))


# ----------------------------
# FIELD MATCH (IMPROVED)
# ----------------------------
def field_match(field, jd_text):

    field = clean(field)

    # check synonym groups both ways
    for key, values in FIELD_SYNONYMS.items():
        if field in values:
            if any(v in jd_text for v in values):
                return 1.0

    return sim(field, jd_text)


# ----------------------------
# CERT PROCESSING (IMPROVED)
# ----------------------------
def process_certifications(cert_list, jd_text):

    processed = []
    matches = 0

    for c in cert_list:
        name = c.get("name", "").lower()
        category = c.get("category", "").lower()

        if not name:
            continue

        processed.append({
            "name": c.get("name", ""),
            "issuer": c.get("issuer", ""),
            "year": c.get("year", "")
        })

        if any(k in jd_text for k in [name, category]):
            matches += 1

    score = (matches / len(processed)) * 100 if processed else 0

    return processed, score


# ----------------------------
# FIX: EXTRACT LATEST YEAR
# ----------------------------
def extract_latest_year(education):

    years = []

    for e in education:
        y = str(e.get("graduation_year", ""))
        found = re.findall(r"\d{4}", y)

        if found:
            years.append(max(map(int, found)))

    return max(years) if years else "UNKNOWN"


# ----------------------------
# CORE PIPELINE (FIXED)
# ----------------------------
def run_education_pipeline(resume_json, jd_json):

    jd_text = get_jd_text(jd_json)

    parsed = extract_education(resume_json)
    formatted = format_academic_profile(parsed)

    edu_data = formatted["education_data"]

    education = edu_data["education_details"]
    certifications = edu_data["certifications"]
    degree = edu_data["academic_profile"]["highest_degree"]

    # education = formatted["education_data"]["education_details"]
    # certifications = formatted["education_data"]["certifications"]

    # ----------------------------
    # DEGREE SCORE (INTRINSIC)
    # ----------------------------
    DEGREE_MAP = {
        "PHD": 100,
        "MBA": 90,
        "M.TECH": 85,
        "MSC": 80,
        "MCA": 80,
        "B.TECH": 75,
        "B.E": 75,
        "BSC": 70,
        "BCA": 70,
        "DIPLOMA": 60
    }

    degree = formatted["education_data"]["academic_profile"]["highest_degree"]
    degree_score = DEGREE_MAP.get(degree, 50)

    # ----------------------------
    # FIELD SCORE
    # ----------------------------
    field_score = max(
        [field_match(e.get("field", ""), jd_text) for e in education],
        default=0
    ) * 100

    # ----------------------------
    # CERT SCORE
    # ----------------------------
    cert_processed, cert_score = process_certifications(certifications, jd_text)

    # ----------------------------
    # EDUCATION STRENGTH (FIXED)
    # ----------------------------
    latest_year = extract_latest_year(education)

    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        gap = datetime.now().year - latest_year
        recency_score = 100 if gap <= 2 else 80 if gap <= 5 else 60

    education_strength = round(
        degree_score * 0.4 +
        recency_score * 0.3 +
        cert_score * 0.2 +
        50 * 0.1,   # base institution placeholder
        2
    )

    # ----------------------------
    # RELEVANCE SCORE (FIXED)
    # ----------------------------
    relevance_score = round(
        degree_score * 0.3 +
        field_score * 0.4 +
        cert_score * 0.3,
        2
    )

    if field_score < 40:
        relevance_score -= 10

    relevance_score = max(relevance_score, 0)

    # ----------------------------
    # FINAL OUTPUT
    # ----------------------------
    return {
        "education_data": {
            "academic_profile": {
                "highest_degree": degree,
                "total_degrees": len(education),
                "certification_count": len(cert_processed),
                "latest_graduation_year": latest_year,
                "education_strength": education_strength
            },
            "education_details": education,
            "certifications": cert_processed
        },
        "education_relevance_score": relevance_score
    }


# ----------------------------
# EXECUTION (BATCH MODE)
# ----------------------------
if __name__ == "__main__":

    resume_files = sorted([f for f in os.listdir(RESUME_PATH) if f.endswith(".json")])
    jd_files = sorted([f for f in os.listdir(JD_PATH) if f.endswith(".json")])

    if not resume_files:
        raise Exception("❌ No resume files found")

    if not jd_files:
        raise Exception("❌ No JD files found")

    jd_path = os.path.join(JD_PATH, jd_files[0])

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_json = json.load(f)

    print(f"📄 Using JD: {jd_files[0]}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for resume_file in resume_files:

        resume_path = os.path.join(RESUME_PATH, resume_file)

        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                resume_json = json.load(f)
        except Exception as e:
            print(f"❌ Skipping {resume_file}: {e}")
            continue

        print(f"\n📄 Processing: {resume_file}")

        result = run_education_pipeline(resume_json, jd_json)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.splitext(resume_file)[0]

        output_file = f"{name}_{timestamp}.json"
        output_path = os.path.join(OUTPUT_DIR, output_file)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)

        print(f"✅ Saved: {output_file}")
        print(f"🎯 Score: {result['education_relevance_score']}")