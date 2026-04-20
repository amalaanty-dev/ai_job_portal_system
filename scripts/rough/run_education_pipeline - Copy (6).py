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
# CLEAN TEXT
# ----------------------------
def clean(x):
    if isinstance(x, list):
        return " ".join([str(i) for i in x if i]).lower().strip()
    if isinstance(x, str):
        return x.lower().strip()
    return ""


# ----------------------------
# JD TEXT BUILDER
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
# CERT PROCESSING
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

        if name in jd_text or category in jd_text:
            matches += 1

    score = (matches / len(processed)) * 100 if processed else 0

    return processed, score


# ----------------------------
# YEAR EXTRACTION
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
# EDUCATION RELEVANCE (FINAL)
# ----------------------------
def calculate_education_relevance(education, certifications, jd_text):

    if not education:
        return 0

    jd_text = jd_text.lower()

    # ----------------------------
    # DEGREE SCORE
    # ----------------------------
    DEGREE_WEIGHT = {
        "PHD": 1.0,
        "MBA": 0.9,
        "M.TECH": 0.85,
        "MSC": 0.8,
        "MCA": 0.8,
        "B.TECH": 0.75,
        "B.E": 0.75,
        "BSC": 0.7,
        "BBA": 0.7
    }

    degree_score = max([
        DEGREE_WEIGHT.get(e.get("degree", ""), 0.5)
        for e in education
    ]) * 100

    # ----------------------------
    # FIELD SCORE
    # ----------------------------
    field_score = max([
        100 if e.get("field", "").lower() in jd_text
        else SequenceMatcher(None, e.get("field", "").lower(), jd_text).ratio() * 100
        for e in education
    ], default=0)

    # ----------------------------
    # CERT SCORE
    # ----------------------------
    matched = sum(
        1 for c in certifications
        if c.get("name", "").lower() in jd_text
    )

    cert_score = (matched / len(certifications)) * 100 if certifications else 0

    # ----------------------------
    # FINAL SCORE
    # ----------------------------
    score = (
        degree_score * 0.4 +
        field_score * 0.4 +
        cert_score * 0.2
    )

    return round(score, 2)


# ----------------------------
# CORE PIPELINE
# ----------------------------
def run_education_pipeline(resume_json, jd_json):

    jd_text = get_jd_text(jd_json)

    # ----------------------------
    # PARSE + FORMAT
    # ----------------------------
    parsed = extract_education(resume_json)
    formatted = format_academic_profile(parsed)

    edu_data = formatted["education_data"]

    education = edu_data["education_details"]
    certifications = edu_data["certifications"]
    degree = edu_data["academic_profile"]["highest_degree"]

    # ----------------------------
    # PROCESS CERTIFICATIONS
    # ----------------------------
    cert_processed, cert_score = process_certifications(certifications, jd_text)

    # ----------------------------
    # STRENGTH (KEEP FORMATTER OUTPUT)
    # ----------------------------
    latest_year = extract_latest_year(education)

    DEGREE_MAP = {
        "PHD": 100, "MBA": 90, "M.TECH": 85,
        "MSC": 80, "MCA": 80,
        "B.TECH": 75, "B.E": 75,
        "BSC": 70, "BCA": 70,
        "DIPLOMA": 60
    }

    degree_score = DEGREE_MAP.get(degree, 50)

    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        gap = datetime.now().year - latest_year
        recency_score = 100 if gap <= 2 else 80 if gap <= 5 else 60

    education_strength = round(
        degree_score * 0.4 +
        recency_score * 0.3 +
        cert_score * 0.2 +
        60 * 0.1,
        2
    )

    # ----------------------------
    # RELEVANCE
    # ----------------------------
    relevance_score = calculate_education_relevance(
        education,
        cert_processed,
        jd_text
    )

    # ----------------------------
    # OUTPUT
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
# EXECUTION
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

        output_file = resume_file
        output_path = os.path.join(OUTPUT_DIR, output_file)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)

        print(f"✅ Saved: {output_file}")
        print(f"🎯 Score: {result['education_relevance_score']}")