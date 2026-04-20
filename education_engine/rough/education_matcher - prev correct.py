from difflib import SequenceMatcher


# ----------------------------
# CONFIG
# ----------------------------
DEGREE_WEIGHT = {
    "PHD": 1.0,
    "MBA": 0.9,
    "M.TECH": 0.85,
    "MSC": 0.8,
    "MASTER": 0.8,
    "MCA": 0.8,
    "B.TECH": 0.75,
    "B.E": 0.75,
    "BSC": 0.7,
    "BCA": 0.7,
    "BACHELOR": 0.7,
    "DIPLOMA": 0.6
}


FIELD_KEYWORDS = {
    "computer science": ["computer science", "cs", "software", "it"],
    "data science": ["data science", "machine learning", "ai", "analytics"],
    "electronics": ["electronics", "ece", "embedded"],
    "mechanical": ["mechanical"],
    "business": ["mba", "business", "management"]
}


# ----------------------------
# HELPERS
# ----------------------------

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def extract_jd_degree_requirement(jd_text):
    jd_text = jd_text.lower()

    if "phd" in jd_text:
        return "PHD"
    if "master" in jd_text or "m.tech" in jd_text or "msc" in jd_text:
        return "MASTER"
    if "bachelor" in jd_text or "b.tech" in jd_text or "bsc" in jd_text:
        return "BACHELOR"

    return None


def detect_field_match(field, jd_text):
    field = field.lower()
    jd_text = jd_text.lower()

    for domain, keywords in FIELD_KEYWORDS.items():
        if any(k in field for k in keywords):
            if any(k in jd_text for k in keywords):
                return 1.0  # strong match

    return similarity(field, jd_text)


# ----------------------------
# MAIN FUNCTION
# ----------------------------

def calculate_education_relevance(education_data, jd_text):

    jd_text_lower = jd_text.lower()
    jd_degree = extract_jd_degree_requirement(jd_text)

    education_list = education_data.get("education_details", [])
    certifications = education_data.get("certifications", [])

    # ----------------------------
    # 1. DEGREE SCORE (40%)
    # ----------------------------
    degree_score = 0

    for edu in education_list:
        degree = edu.get("degree", "").upper()

        if not degree:
            continue

        base_sim = similarity(degree, jd_text_lower)
        weight = DEGREE_WEIGHT.get(degree, 0.6)

        score = base_sim * weight

        # ✅ JD REQUIREMENT BOOST
        if jd_degree and jd_degree in degree:
            score += 0.2

        degree_score = max(degree_score, score)

    degree_score = min(degree_score, 1.0) * 100


    # ----------------------------
    # 2. FIELD SCORE (30%)
    # ----------------------------
    field_score = 0

    for edu in education_list:
        field = edu.get("field", "")

        if not field or field.lower() == "unknown":
            continue

        score = detect_field_match(field, jd_text)
        field_score = max(field_score, score)

    field_score = field_score * 100


    # ----------------------------
    # 3. CERTIFICATION SCORE (30%)
    # ----------------------------
    cert_matches = 0
    total_certs = len(certifications)

    for cert in certifications:
        cert_name = cert.get("name", "").lower()

        if not cert_name:
            continue

        if cert_name in jd_text_lower or similarity(cert_name, jd_text_lower) > 0.65:
            cert_matches += 1

    if total_certs > 0:
        cert_score = (cert_matches / total_certs) * 100
    else:
        cert_score = 0


    # ----------------------------
    # FINAL SCORE
    # ----------------------------
    final_score = (
        degree_score * 0.4 +
        field_score * 0.3 +
        cert_score * 0.3
    )

    return round(final_score, 2)