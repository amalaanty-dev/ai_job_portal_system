import re

# ----------------------------
# DEGREE MAP
# ----------------------------
DEGREE_MAP = {
    "bachelor": "BACHELOR",
    "b.tech": "B.TECH",
    "btech": "B.TECH",
    "b.e": "B.E",
    "be": "B.E",
    "bsc": "BSC",
    "b.sc": "BSC",
    "bca": "BCA",

    "master": "MASTER",
    "m.tech": "M.TECH",
    "mtech": "M.TECH",
    "msc": "MSC",
    "m.sc": "MSC",
    "mba": "MBA",
    "mca": "MCA",

    "phd": "PHD",
    "diploma": "DIPLOMA"
}

CERTIFICATION_KEYWORDS = [
    "certified", "certification", "certificate", "training", "license"
]


# ----------------------------
# MAIN FUNCTION (UPDATED)
# ----------------------------
def extract_education(resume_json):

    education_list = []
    certifications = []

    # ✅ DIRECT SECTIONED INPUT
    education_section = resume_json.get("education", [])

    # If already structured list (your case)
    if isinstance(education_section, list):

        for item in education_section:

            if not item or len(str(item).strip()) < 5:
                continue

            item_str = str(item).strip()
            item_lower = item_str.lower()

            degree = extract_degree(item_lower)

            # ----------------------------
            # EDUCATION DETECTION
            # ----------------------------
            if degree != "UNKNOWN":

                education_list.append({
                    "degree": degree,
                    "field": extract_field(item_str),
                    "institution": extract_institution(item_str),
                    "graduation_year": extract_year(item_str)
                })

            # ----------------------------
            # CERTIFICATION DETECTION
            # ----------------------------
            elif is_certification_line(item_lower):

                certifications.append({
                    "name": item_str,
                    "issuer": extract_institution(item_str),
                    "year": extract_year(item_str),
                    "category": categorize_certification(item_str)
                })

    return {
        "education": education_list,
        "certifications": certifications
    }


# ----------------------------
# HELPERS
# ----------------------------
def extract_degree(text):
    text = text.lower()

    for key, value in DEGREE_MAP.items():
        if key in text:
            return value

    return "UNKNOWN"


def extract_field(text):
    text_lower = text.lower()

    # Pattern: "MBA Finance"
    match = re.search(r"(mba|msc|bsc|btech|mtech|bca|mca)\s*[-–]?\s*([a-z &]+)", text_lower)
    if match:
        return match.group(2).title()

    # Pattern: "in Computer Science"
    match = re.search(r"in\s+([a-z &]+)", text_lower)
    if match:
        return match.group(1).title()

    return "UNKNOWN"


def extract_institution(text):
    match = re.search(r"([A-Z][a-zA-Z &]{3,} (college|university|institute))", text)
    if match:
        return match.group(0).title()

    return "UNKNOWN"


def extract_year(text):
    match = re.search(r"(19|20)\d{2}", text)
    return match.group() if match else "UNKNOWN"


# ----------------------------
# CERTIFICATION HELPERS
# ----------------------------
def is_certification_line(text):
    return any(k in text for k in CERTIFICATION_KEYWORDS)


def categorize_certification(text):
    text = text.lower()

    if any(w in text for w in ["aws", "azure", "gcp", "cloud"]):
        return "CLOUD"

    if any(w in text for w in ["data", "machine learning", "ai", "analytics"]):
        return "DATA/AI"

    if any(w in text for w in ["pmp", "management"]):
        return "BUSINESS"

    if any(w in text for w in ["python", "java", "developer"]):
        return "TECH"

    return "GENERAL"