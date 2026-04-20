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
# NOISE FILTER
# ----------------------------
IGNORE_KEYWORDS = [
    "achievement", "awarded", "declaration", "hereby", "resume",
    "contact", "email", "phone", "profile", "skills", "experience",
    "project", "summary"
]


# ----------------------------
# MAIN FUNCTION (FIXED)
# ----------------------------
def extract_education(resume_json):

    education_section = resume_json.get("education", [])
    education_list = []
    certifications = []

    if not isinstance(education_section, list):
        return {"education": [], "certifications": []}

    for item in education_section:

        if not item:
            continue

        text = str(item).strip()
        lower = text.lower()

        # ----------------------------
        # REMOVE NOISE LINES
        # ----------------------------
        if any(k in lower for k in IGNORE_KEYWORDS):
            continue

        if len(text) < 5:
            continue

        # ----------------------------
        # DEGREE DETECTION
        # ----------------------------
        degree = extract_degree(lower)

        if degree != "UNKNOWN":

            education_list.append({
                "degree": degree,
                "field": extract_field(text),
                "institution": extract_institution(text),
                "graduation_year": extract_year_range(text)
            })

        # ----------------------------
        # CERTIFICATION DETECTION
        # ----------------------------
        elif is_certification_line(lower):

            certifications.append({
                "name": text,
                "issuer": extract_institution(text),
                "year": extract_year(text),
                "category": categorize_certification(text)
            })

    return {
        "education": merge_duplicate_education(education_list),
        "certifications": certifications
    }


# ----------------------------
# DEGREE EXTRACTION
# ----------------------------
def extract_degree(text):

    text = text.lower()

    for key, value in DEGREE_MAP.items():
        if key in text:
            return value

    return "UNKNOWN"


# ----------------------------
# FIELD EXTRACTION (IMPROVED)
# ----------------------------
def extract_field(text):

    text_lower = text.lower()

    patterns = [
        r"mba\s*[-–]?\s*([a-z &]+)",
        r"m\.?tech\s*[-–]?\s*([a-z &]+)",
        r"b\.?tech\s*[-–]?\s*([a-z &]+)",
        r"bba\s*[-–]?\s*([a-z &]+)",
        r"in\s+([a-z &]+)"
    ]

    for p in patterns:
        match = re.search(p, text_lower)
        if match:
            return match.group(1).title().strip()

    return "UNKNOWN"


# ----------------------------
# INSTITUTION EXTRACTION (FIXED)
# ----------------------------
def extract_institution(text):

    match = re.search(
        r"([A-Z][a-zA-Z &,.]{5,}(college|university|institute|school))",
        text
    )

    if match:
        return match.group(0).strip()

    return "UNKNOWN"


# ----------------------------
# YEAR RANGE EXTRACTION (NEW FIX)
# ----------------------------
def extract_year_range(text):

    # CASE 1: 2016–2018 / 2016 - 2018
    match = re.search(r"(20\d{2})\s*[-–]\s*(20\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # CASE 2: single year fallback
    match = re.search(r"(19|20)\d{2}", text)
    if match:
        return match.group()

    return "UNKNOWN"


# ----------------------------
# SINGLE YEAR (CERTS)
# ----------------------------
def extract_year(text):
    match = re.search(r"(19|20)\d{2}", text)
    return match.group() if match else "UNKNOWN"


# ----------------------------
# CERTIFICATION CHECK
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


# ----------------------------
# REMOVE DUPLICATES
# ----------------------------
def merge_duplicate_education(edu_list):

    seen = set()
    cleaned = []

    for e in edu_list:

        key = (e.get("degree"), e.get("graduation_year"))

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(e)

    return cleaned