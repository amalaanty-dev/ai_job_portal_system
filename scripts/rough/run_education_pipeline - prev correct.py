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
JD_PATH     = "data/job_descriptions/parsed_jd/"
OUTPUT_DIR  = "data/education_outputs/"


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

    for k in ["education", "role", "required_skills", "preferred_skills",
              "responsibilities", "title", "job_title"]:
        v = jd_json.get(k)

        if isinstance(v, list):
            parts.append(" ".join([str(i) for i in v if i]))
        elif isinstance(v, str):
            parts.append(v)

    return clean(" ".join(parts))


# ----------------------------
# JD MATCHER
# — picks best JD for each resume
# — falls back to first JD if no match
# ----------------------------
def find_best_jd(resume_json, jd_list):

    # build resume title tokens from filename-agnostic fields
    resume_title = clean(
        resume_json.get("job_title", "") + " " +
        resume_json.get("target_role", "") + " " +
        resume_json.get("desired_role", "") + " " +
        " ".join(resume_json.get("skills", [])[:10])
    )

    best_jd   = jd_list[0]          # safe fallback
    best_score = 0

    for jd_name, jd_json in jd_list:

        jd_title = clean([
            jd_json.get("title", ""),
            jd_json.get("job_title", ""),
            jd_json.get("role", "")
        ])

        # token overlap ratio
        resume_tokens = set(resume_title.split())
        jd_tokens     = set(jd_title.split())

        if not jd_tokens:
            continue

        overlap = len(resume_tokens & jd_tokens) / len(jd_tokens)

        # fallback: sequence similarity on titles
        seq_score = SequenceMatcher(None, resume_title[:200], jd_title).ratio()

        combined = max(overlap, seq_score)

        if combined > best_score:
            best_score = combined
            best_jd    = (jd_name, jd_json)

    return best_jd


# ----------------------------
# CERT PROCESSING
# ----------------------------
def process_certifications(cert_list, jd_text):

    processed = []
    matches   = 0

    for c in cert_list:

        name     = c.get("name", "").lower()
        category = c.get("category", "").lower()

        if not name:
            continue

        processed.append({
            "name":   c.get("name", ""),
            "issuer": c.get("issuer", ""),
            "year":   c.get("year", "")
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
        y     = str(e.get("graduation_year", ""))
        found = re.findall(r"\b(?:19|20)\d{2}\b", y)

        if found:
            years.append(max(map(int, found)))

    return max(years) if years else "UNKNOWN"


# ----------------------------
# FIELD SCORE (FIXED)
# — keyword overlap instead of full-text SequenceMatcher
# ----------------------------
def calculate_field_score(education, jd_text):

    if not education:
        return 0

    jd_tokens = set(re.findall(r"\b[a-z]+\b", jd_text.lower()))

    scores = []

    for e in education:

        field = e.get("field", "").lower().strip()

        if not field:
            scores.append(0)
            continue

        field_tokens = set(re.findall(r"\b[a-z]+\b", field))

        if not field_tokens:
            scores.append(0)
            continue

        # direct substring match → full score
        if field in jd_text:
            scores.append(100)
            continue

        # token overlap
        overlap = len(field_tokens & jd_tokens) / len(field_tokens)
        scores.append(round(overlap * 100, 2))

    return max(scores) if scores else 0


# ----------------------------
# DEGREE RELEVANCE SCORE (FIXED)
# — checks degree against JD education requirements
# ----------------------------
def calculate_degree_score(education, jd_text):

    DEGREE_WEIGHT = {
        "PHD":           1.0,
        "MD":            1.0,
        "MBA":           0.9,
        "EXECUTIVE MBA": 0.9,
        "PGDM":          0.88,
        "M.TECH":        0.85,
        "M.E":           0.85,
        "MSC":           0.82,
        "MCA":           0.80,
        "MS":            0.80,
        "M.COM":         0.78,
        "MA":            0.75,
        "LLM":           0.75,
        "M.PHARM":       0.75,
        "M.ED":          0.70,
        "B.TECH":        0.75,
        "B.E":           0.75,
        "BSC":           0.70,
        "BBA":           0.70,
        "B.COM":         0.68,
        "BCA":           0.68,
        "BA":            0.65,
        "LLB":           0.65,
        "MBBS":          0.80,
        "BDS":           0.72,
        "B.PHARM":       0.70,
        "B.ED":          0.65,
        "BHM":           0.65,
        "BSC NURSING":   0.70,
        "DIPLOMA":       0.55,
        "POLYTECHNIC":   0.50,
        "HSC":           0.40,
        "SSC":           0.30,
        "CA":            0.85,
        "CMA":           0.80,
        "CS":            0.75,
        "CFA":           0.85,
    }

    if not education:
        return 0

    scores = []

    for e in education:

        degree       = e.get("degree", "")
        base_weight  = DEGREE_WEIGHT.get(degree, 0.5)
        degree_score = base_weight * 100

        # boost if JD explicitly mentions this degree
        if degree.lower() in jd_text:
            degree_score = min(100, degree_score * 1.15)

        scores.append(degree_score)

    return max(scores) if scores else 0


# ----------------------------
# EDUCATION RELEVANCE (REBUILT)
# ----------------------------
def calculate_education_relevance(education, certifications, jd_text):

    if not education:
        return 0

    jd_text = jd_text.lower()

    degree_score = calculate_degree_score(education, jd_text)
    field_score  = calculate_field_score(education, jd_text)

    matched    = sum(1 for c in certifications if c.get("name", "").lower() in jd_text)
    cert_score = (matched / len(certifications)) * 100 if certifications else 0

    score = (
        degree_score * 0.40 +
        field_score  * 0.40 +
        cert_score   * 0.20
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
    parsed    = extract_education(resume_json)
    formatted = format_academic_profile(parsed)

    edu_data = formatted["education_data"]

    education      = edu_data["education_details"]
    certifications = edu_data["certifications"]
    degree         = edu_data["academic_profile"]["highest_degree"]

    # ----------------------------
    # PROCESS CERTIFICATIONS
    # ----------------------------
    cert_processed, cert_score = process_certifications(certifications, jd_text)

    # ----------------------------
    # EDUCATION STRENGTH
    # ----------------------------
    latest_year = extract_latest_year(education)

    DEGREE_STRENGTH = {
        "PHD":           100,
        "MD":            100,
        "MBA":           90,
        "EXECUTIVE MBA": 90,
        "PGDM":          88,
        "M.TECH":        85,
        "M.E":           85,
        "MSC":           82,
        "MCA":           80,
        "MS":            80,
        "M.COM":         78,
        "MA":            75,
        "B.TECH":        75,
        "B.E":           75,
        "BSC":           70,
        "BBA":           70,
        "BCA":           68,
        "B.COM":         68,
        "BA":            65,
        "MBBS":          80,
        "BDS":           72,
        "B.PHARM":       70,
        "BSC NURSING":   70,
        "CA":            85,
        "CMA":           80,
        "CFA":           85,
        "DIPLOMA":       55,
        "HSC":           40,
        "SSC":           30,
    }

    degree_score = DEGREE_STRENGTH.get(degree, 50)

    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        gap           = datetime.now().year - int(latest_year)
        recency_score = 100 if gap <= 2 else 80 if gap <= 5 else 60 if gap <= 10 else 40

    education_strength = round(
        degree_score * 0.40 +
        recency_score * 0.30 +
        cert_score    * 0.20 +
        60            * 0.10,
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
    # OUTPUT  (matches required format)
    # ----------------------------
    return {
        "education_data": {
            "academic_profile": {
                "highest_degree":        degree,
                "total_degrees":         len(education),
                "certification_count":   len(cert_processed),
                "latest_graduation_year": latest_year,
                "education_strength":    education_strength
            },
            "education_details": education,
            "certifications":    cert_processed
        },
        "education_relevance_score": relevance_score
    }


# ----------------------------
# EXECUTION
# ----------------------------
if __name__ == "__main__":

    resume_files = sorted([f for f in os.listdir(RESUME_PATH) if f.endswith(".json")])
    jd_files     = sorted([f for f in os.listdir(JD_PATH)     if f.endswith(".json")])

    if not resume_files:
        raise Exception("❌ No resume files found")

    if not jd_files:
        raise Exception("❌ No JD files found")

    # ----------------------------
    # LOAD ALL JDs ONCE
    # ----------------------------
    loaded_jds = []

    for jd_file in jd_files:
        jd_path = os.path.join(JD_PATH, jd_file)
        try:
            with open(jd_path, "r", encoding="utf-8") as f:
                loaded_jds.append((jd_file, json.load(f)))
        except Exception as e:
            print(f"⚠️  Skipping JD {jd_file}: {e}")

    if not loaded_jds:
        raise Exception("❌ No valid JD files loaded")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for resume_file in resume_files:

        resume_path = os.path.join(RESUME_PATH, resume_file)

        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                resume_json = json.load(f)
        except Exception as e:
            print(f"❌ Skipping {resume_file}: {e}")
            continue

        # ----------------------------
        # MATCH JD TO RESUME
        # ----------------------------
        jd_name, jd_json = find_best_jd(resume_json, loaded_jds)

        print(f"\n📄 Resume : {resume_file}")
        print(f"📋 JD used: {jd_name}")

        result = run_education_pipeline(resume_json, jd_json)

        output_path = os.path.join(OUTPUT_DIR, resume_file)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)

        print(f"✅ Saved  : {resume_file}")
        print(f"🎯 Score  : {result['education_relevance_score']}")