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
    "biostatistics": ["biostatistics", "statistics"],
    "statistics": ["statistics"],
    "computer science": ["computer science", "software", "programming"],
    "life sciences": ["biology", "biotech"],
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
# FIELD FALLBACK (NEW FIX)
# ----------------------------
def infer_field_from_text(text):

    text = text.lower()

    for key, values in FIELD_SYNONYMS.items():
        for v in values:
            if v in text:
                return key.upper()

    return ""


# ----------------------------
# INSTITUTION FIX (NEW)
# ----------------------------
def fix_institution_name(inst, full_text):

    if inst != "UNKNOWN" and len(inst.split()) >= 3:
        return inst

    # try extracting full name
    match = re.search(
        r"([A-Z][a-zA-Z &]{5,}(College|University|Institute)[a-zA-Z ,]*)",
        full_text
    )

    if match:
        return match.group(0).strip()

    return inst


# ----------------------------
# FIELD MATCH (IMPROVED)
# ----------------------------
def field_match(field, jd_text, resume_text):

    field = clean(field)

    if not field:
        field = infer_field_from_text(resume_text)

    for key, values in FIELD_SYNONYMS.items():
        if field in values or field == key:
            if any(v in jd_text for v in values):
                return 1.0

    return sim(field, jd_text)


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

        if any(k in jd_text for k in [name, category]):
            matches += 1

    score = (matches / len(processed)) * 100 if processed else 0

    return processed, score


# ----------------------------
# YEAR FIX
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
# CORE PIPELINE (UPDATED)
# ----------------------------
def run_education_pipeline(resume_json, jd_json):

    jd_text = clean(" ".join([
        str(jd_json.get("education", "")),
        str(jd_json.get("role", "")),
        str(jd_json.get("required_skills", ""))
    ]))

    resume_text = clean(resume_json.get("full_text", ""))

    parsed = extract_education(resume_json)
    formatted = format_academic_profile(parsed)

    edu_data = formatted["education_data"]

    education = edu_data["education_details"]
    certifications = edu_data["certifications"]
    degree = edu_data["academic_profile"]["highest_degree"]

    # ----------------------------
    # FIX FIELD + INSTITUTION
    # ----------------------------
    for e in education:

        if not e.get("field"):
            e["field"] = infer_field_from_text(resume_text)

        e["institution"] = fix_institution_name(
            e.get("institution", ""),
            resume_text
        )

    # ----------------------------
    # DEGREE SCORE
    # ----------------------------
    DEGREE_MAP = {
        "PHD": 100, "MBA": 90, "M.TECH": 85,
        "MSC": 80, "MCA": 80,
        "B.TECH": 75, "B.E": 75,
        "BSC": 70, "BCA": 70,
        "DIPLOMA": 60
    }

    degree_score = DEGREE_MAP.get(degree, 50)

    # ----------------------------
    # FIELD SCORE (FIXED)
    # ----------------------------
    field_score = max(
        [field_match(e.get("field", ""), jd_text, resume_text) for e in education],
        default=0
    ) * 100

    # ----------------------------
    # CERT SCORE
    # ----------------------------
    cert_processed, cert_score = process_certifications(certifications, jd_text)

    # ----------------------------
    # STRENGTH
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
        60 * 0.1,
        2
    )

    # ----------------------------
    # RELEVANCE (BOOSTED)
    # ----------------------------
    relevance_score = round(
        degree_score * 0.4 +   # increased weight
        field_score * 0.4 +
        cert_score * 0.2,
        2
    )

    if field_score < 40:
        relevance_score -= 5

    relevance_score = max(relevance_score, 0)

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

    jd_path = os.path.join(JD_PATH, jd_files[0])

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_json = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for resume_file in resume_files:

        resume_path = os.path.join(RESUME_PATH, resume_file)

        with open(resume_path, "r", encoding="utf-8") as f:
            resume_json = json.load(f)

        print(f"\n📄 Processing: {resume_file}")

        result = run_education_pipeline(resume_json, jd_json)

        output_path = os.path.join(OUTPUT_DIR, resume_file)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)

        print(f"✅ Saved: {resume_file}")
        print(f"🎯 Score: {result['education_relevance_score']}")