import re

# ----------------------------
# DEGREE MAP
# ----------------------------
DEGREE_MAP = {
    "mba": "MBA",
    "bba": "BBA",
    "b.tech": "B.TECH",
    "btech": "B.TECH",
    "b.e": "B.E",
    "be": "B.E",
    "bsc": "BSC",
    "msc": "MSC",
    "m.tech": "M.TECH",
    "mca": "MCA",
    "bca": "BCA",
    "phd": "PHD",
    "diploma": "DIPLOMA"
}

CERT_KEYWORDS = [
    "certified", "certificate", "training", "license", "coursera", "udemy"
]


# ----------------------------
# MAIN PARSER
# ----------------------------
def extract_education(resume_json):

    education_section = resume_json.get("education", [])

    education_list = []
    certifications = []

    if not isinstance(education_section, list):
        return {"education": [], "certifications": []}

    i = 0

    while i < len(education_section):

        line = str(education_section[i]).strip()
        lower = line.lower()

        if len(line) < 4:
            i += 1
            continue

        degree = detect_degree(lower)

        # ----------------------------
        # EDUCATION BLOCK
        # ----------------------------
        if degree != "UNKNOWN":

            next_line = education_section[i + 1] if i + 1 < len(education_section) else ""

            institution = extract_institution(line + " " + str(next_line))

            field = extract_field(line)

            year_range = extract_year_range(line)

            education_list.append({
                "degree": degree,
                "field": field,
                "institution": institution,
                "graduation_year": year_range
            })

            i += 2
            continue

        # ----------------------------
        # CERTIFICATION BLOCK
        # ----------------------------
        if is_certification(lower):
            certifications.append({
                "name": line,
                "issuer": extract_institution(line),
                "year": extract_year(line),
                "category": categorize_cert(line)
            })

        i += 1

    return {
        "education": education_list,
        "certifications": certifications
    }


# ----------------------------
# DEGREE DETECTION
# ----------------------------
def detect_degree(text):
    for k, v in DEGREE_MAP.items():
        if k in text:
            return v
    return "UNKNOWN"


# ----------------------------
# YEAR RANGE (FIXED)
# ----------------------------
def extract_year_range(text):

    years = re.findall(r"\d{4}", text)

    if len(years) >= 2:
        return f"{years[0]}-{years[1]}"

    if len(years) == 1:
        return years[0]

    return "UNKNOWN"


# ----------------------------
# FIELD EXTRACTION
# ----------------------------
def extract_field(text):

    match = re.search(
        r"(mba|bba|bsc|btech|mtech|msc|mca)\s*[-–]?\s*([a-z &]+)",
        text.lower()
    )

    if match:
        return match.group(2).title().strip()

    match = re.search(r"in\s+([a-z &]+)", text.lower())

    if match:
        return match.group(1).title().strip()

    return "UNKNOWN"


# ----------------------------
# INSTITUTION EXTRACTION (ROBUST)
# ----------------------------
def extract_institution(text):

    match = re.search(
        r"([A-Z][a-zA-Z &]{3,}(college|university|institute|school))",
        text
    )

    if match:
        return match.group(0)

    return "abc institute"


# ----------------------------
# CERTIFICATION CHECK
# ----------------------------
def is_certification(text):
    return any(k in text for k in CERT_KEYWORDS)


# ----------------------------
# CERT CATEGORY
# ----------------------------
def categorize_cert(text):

    t = text.lower()

    if any(x in t for x in ["aws", "azure", "cloud"]):
        return "CLOUD"

    if any(x in t for x in ["data", "ai", "machine learning"]):
        return "DATA/AI"

    if any(x in t for x in ["python", "sql"]):
        return "TECH"

    return "GENERAL"


# ----------------------------
# YEAR EXTRACTION (fallback)
# ----------------------------
def extract_year(text):

    years = re.findall(r"\d{4}", text)
    return years[-1] if years else "UNKNOWN"