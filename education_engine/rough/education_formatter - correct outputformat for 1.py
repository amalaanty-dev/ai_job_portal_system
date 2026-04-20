import re
from datetime import datetime
from difflib import SequenceMatcher

# ----------------------------
# DEGREE PRIORITY (LOW = HIGHER)
# ----------------------------
DEGREE_PRIORITY = {
    "PHD": 1,
    "MBA": 2,
    "M.TECH": 3,
    "MSC": 4,
    "MCA": 5,
    "B.TECH": 6,
    "B.E": 6,
    "BSC": 7,
    "BBA": 8
}

# ----------------------------
# DEGREE SCORE (FOR STRENGTH)
# ----------------------------
DEGREE_SCORE_MAP = {
    "PHD": 100,
    "MBA": 90,
    "M.TECH": 85,
    "MSC": 80,
    "MCA": 78,
    "B.TECH": 75,
    "B.E": 75,
    "BSC": 70,
    "BBA": 65
}


# ----------------------------
# MAIN FORMATTER
# ----------------------------
def format_academic_profile(parsed, jd_text=""):

    edu = parsed.get("education", [])
    cert = parsed.get("certifications", [])

    latest_year = get_latest_year(edu)
    strength = calculate_strength(edu, cert, latest_year)
    relevance = calculate_education_relevance(edu, cert, jd_text)

    return {
        "education_data": {
            "academic_profile": {
                "highest_degree": get_highest(edu),
                "total_degrees": len(edu),
                "certification_count": len(cert),
                "latest_graduation_year": latest_year,
                "education_strength": strength
            },
            "education_details": edu,
            "certifications": cert
        },
        "education_relevance_score": relevance
    }


# ----------------------------
# HIGHEST DEGREE (FIXED)
# ----------------------------
def get_highest(edu_list):

    if not edu_list:
        return "UNKNOWN"

    sorted_edu = sorted(
        edu_list,
        key=lambda x: DEGREE_PRIORITY.get(x.get("degree", ""), 999)
    )

    return sorted_edu[0]["degree"]


# ----------------------------
# LATEST YEAR (FIXED)
# ----------------------------
def get_latest_year(edu_list):

    years = []

    for e in edu_list:
        y = str(e.get("graduation_year", ""))
        found = re.findall(r"\d{4}", y)

        if found:
            years.append(max(map(int, found)))

    return max(years) if years else "UNKNOWN"


# ----------------------------
# EDUCATION STRENGTH (REAL)
# ----------------------------
def calculate_strength(edu, cert, latest_year):

    # Degree Score
    highest = get_highest(edu)
    degree_score = DEGREE_SCORE_MAP.get(highest, 50)

    # Certification Score
    cert_score = min(len(cert) * 20, 80)

    # Recency Score
    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        gap = datetime.now().year - latest_year
        if gap <= 2:
            recency_score = 100
        elif gap <= 5:
            recency_score = 80
        else:
            recency_score = 60

    # Final Weighted Score
    score = (
        degree_score * 0.5 +
        cert_score * 0.2 +
        recency_score * 0.3
    )

    return round(score, 2)


# ----------------------------
# SIMILARITY
# ----------------------------
def similarity(a, b):
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()


# ----------------------------
# EDUCATION RELEVANCE (JD MATCH)
# ----------------------------
def calculate_education_relevance(edu_list, cert_list, jd_text):

    if not edu_list:
        return 0

    jd_text = jd_text.lower()

    # Degree Match
    degree_match = max([
        similarity(e["degree"], jd_text)
        for e in edu_list
    ], default=0) * 100

    # Field Match
    field_match = max([
        similarity(e.get("field", ""), jd_text)
        for e in edu_list
    ], default=0) * 100

    # Certification Match
    matched = 0
    for c in cert_list:
        if c.get("category", "").lower() in jd_text:
            matched += 1

    cert_match = (matched / len(cert_list)) * 100 if cert_list else 0

    # Final Score
    score = (
        degree_match * 0.4 +
        field_match * 0.4 +
        cert_match * 0.2
    )

    return round(score, 2)