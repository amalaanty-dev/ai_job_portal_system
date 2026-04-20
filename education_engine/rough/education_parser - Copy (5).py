import re

# ----------------------------
# DEGREE MAP (STRICT MATCH)
# ----------------------------
DEGREE_MAP = {
    r"\bmba\b": "MBA",
    r"\bbba\b": "BBA",
    r"\bb\.tech\b|\bbtech\b": "B.TECH",
    r"\bb\.e\b": "B.E",
    r"\bbsc\b": "BSC",
    r"\bmsc\b": "MSC",
    r"\bm\.tech\b": "M.TECH",
    r"\bmca\b": "MCA",
    r"\bbca\b": "BCA",
    r"\bphd\b": "PHD",
    r"\bdiploma\b": "DIPLOMA"
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
    seen_degrees = set()

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

            # prevent duplicates
            if degree in seen_degrees:
                i += 1
                continue

            next_line = education_section[i + 1] if i + 1 < len(education_section) else ""

            combined_text = line + " " + str(next_line)

            institution = extract_institution(combined_text)
            field = extract_field(combined_text)
            year_range = extract_year_range(combined_text)

            # VALIDATION (CRITICAL FIX)
            if not is_valid_entry(degree, institution, year_range):
                i += 1
                continue

            education_list.append({
                "degree": degree,
                "field": field,
                "institution": institution,
                "graduation_year": year_range
            })

            seen_degrees.add(degree)

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
# DEGREE DETECTION (STRICT)
# ----------------------------
def detect_degree(text):
    for pattern, degree in DEGREE_MAP.items():
        if re.search(pattern, text):
            return degree
    return "UNKNOWN"


# ----------------------------
# VALIDATION (NEW)
# ----------------------------
def is_valid_entry(degree, institution, year):

    if degree == "UNKNOWN":
        return False

    if institution == "UNKNOWN" and year == "UNKNOWN":
        return False

    return True


# ----------------------------
# YEAR RANGE (IMPROVED)
# ----------------------------
def extract_year_range(text):

    years = re.findall(r"\d{4}", text)

    if len(years) >= 2:
        return f"{min(years)}-{max(years)}"

    if len(years) == 1:
        return years[0]

    return "UNKNOWN"


# ----------------------------
# FIELD EXTRACTION (IMPROVED)
# ----------------------------
def extract_field(text):

    text_lower = text.lower()

    # Pattern 1: MBA in Finance
    match = re.search(r"(mba|bba|btech|mtech|msc|mca)\s*(in)?\s*([a-z &]+)", text_lower)
    if match:
        field = match.group(3).strip()
        return field.upper()

    # Pattern 2: MBA - Finance
    match = re.search(r"(mba|bba|btech|mtech|msc|mca)\s*[-–]\s*([a-z &]+)", text_lower)
    if match:
        return match.group(2).strip().upper()

    # Pattern 3: MBA (Finance)
    match = re.search(r"\(([^)]+)\)", text)
    if match:
        return match.group(1).strip().upper()

    return ""




# ----------------------------
# INSTITUTION EXTRACTION (FIXED)
# ----------------------------
def extract_institution(text):

    # Capture full institution name including suffix
    match = re.search(
        r"([A-Z][a-zA-Z &]+(?:College|University|Institute)(?: of [A-Za-z &]+)*)",
        text
    )

    if match:
        return match.group(0).strip()

    return "UNKNOWN"   # 🔥 FIXED (no fake "abc institute")


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
# YEAR EXTRACTION
# ----------------------------
def extract_year(text):

    years = re.findall(r"\d{4}", text)
    return years[-1] if years else "UNKNOWN"