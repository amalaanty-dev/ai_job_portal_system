import re

# ----------------------------
# DEGREE MAP (EXPANDED)
# ----------------------------
DEGREE_MAP = {

    # --- POSTGRADUATE ---
    r"\bmba\b": "MBA",
    r"\bm\.com\b|\bmcom\b": "M.COM",
    r"\bma\b": "MA",
    r"\bmsc\b|\bm\.sc\b": "MSC",
    r"\bm\.tech\b|\bmtech\b": "M.TECH",
    r"\bme\b|\bm\.e\b": "M.E",
    r"\bmca\b": "MCA",
    r"\bmba\b": "MBA",
    r"\bllm\b": "LLM",
    r"\bm\.ed\b|\bmed\b": "M.ED",
    r"\bm\.phil\b|\bmphil\b": "M.PHIL",
    r"\bphd\b|\bph\.d\b": "PHD",
    r"\bpgdm\b": "PGDM",
    r"\bpgdbm\b": "PGDBM",
    r"\bpgdca\b": "PGDCA",
    r"\bpg diploma\b|\bpost.?graduate diploma\b": "PG DIPLOMA",
    r"\bexecutive mba\b": "EXECUTIVE MBA",
    r"\bm\.arch\b|\bmarch\b": "M.ARCH",
    r"\bm\.plan\b": "M.PLAN",
    r"\bmd\b": "MD",
    r"\bms\b(?!\s*excel|\s*office|\s*word)": "MS",
    r"\bmds\b": "MDS",
    r"\bm\.pharm\b|\bmpharm\b": "M.PHARM",
    r"\bm\.lib\b": "M.LIB",
    r"\bmba\s*\(iim\)": "MBA (IIM)",
    r"\bcma\s*\(inter\)|\bicwa\s*inter\b": "CMA INTER",
    r"\bcma\b|\bicwa\b": "CMA",
    r"\bca\s*final\b": "CA FINAL",
    r"\bca\s*inter\b|\bca\s*ipcc\b": "CA INTER",
    r"\bca\b(?!\s*[a-z]{3,})": "CA",
    r"\bcs\s*final\b": "CS FINAL",
    r"\bcs\s*inter\b": "CS INTER",
    r"\bcs\b(?!\s*[a-z]{3,})": "CS",
    r"\bcfa\b": "CFA",
    r"\bfrm\b": "FRM",
    r"\bactuarial\b": "ACTUARIAL",

    # --- UNDERGRADUATE ---
    r"\bbba\b": "BBA",
    r"\bb\.com\b|\bbcom\b": "B.COM",
    r"\bba\b(?!\s*[a-z]{3,})": "BA",
    r"\bbsc\b|\bb\.sc\b": "BSC",
    r"\bb\.tech\b|\bbtech\b": "B.TECH",
    r"\bbe\b|\bb\.e\b": "B.E",
    r"\bbca\b": "BCA",
    r"\bllb\b|\bll\.b\b": "LLB",
    r"\bmbbs\b": "MBBS",
    r"\bbds\b": "BDS",
    r"\bbhms\b": "BHMS",
    r"\bbams\b": "BAMS",
    r"\bpharm\.?d\b": "PHARM.D",
    r"\bb\.pharm\b|\bbpharm\b": "B.PHARM",
    r"\bb\.arch\b|\bbarch\b": "B.ARCH",
    r"\bb\.plan\b": "B.PLAN",
    r"\bb\.ed\b|\bbed\b": "B.ED",
    r"\bb\.lib\b": "B.LIB",
    r"\bbhm\b|\bb\.h\.m\b": "BHM",
    r"\bbnys\b": "BNYS",
    r"\bb\.sc\s*nursing\b|\bbsc\s*nursing\b": "BSC NURSING",
    r"\bb\.des\b|\bbdes\b": "B.DES",
    r"\bb\.fa\b|\bbfa\b": "BFA",
    r"\bba\s*llb\b": "BA LLB",
    r"\bbba\s*llb\b": "BBA LLB",

    # --- DIPLOMA / CERTIFICATE ---
    r"\bdiploma\b": "DIPLOMA",
    r"\badvanced diploma\b": "ADVANCED DIPLOMA",
    r"\bpolytechnic\b|\bpoly\b": "POLYTECHNIC",
    r"\bitti\b|\biti\b": "ITI",
    r"\bsslc\b": "SSLC",
    r"\bhsc\b|\b10\+2\b|\bintermediate\b|\bplus two\b|\bplus 2\b|\b12th\b|\bxii\b": "HSC",
    r"\bssc\b|\b10th\b|\bmatriculation\b|\bx\b(?=\s)": "SSC",
}


# ----------------------------
# FIELD VOCABULARY (EXPANDED)
# ----------------------------
FIELD_KEYWORDS = [

    # Business & Management
    "finance", "marketing", "human resources", "hr", "operations",
    "business administration", "management", "entrepreneurship",
    "supply chain", "logistics", "retail management", "international business",
    "banking", "insurance", "taxation", "accounting", "auditing",
    "financial management", "investment", "wealth management",
    "organizational behavior", "strategic management", "project management",
    "business analytics", "e-commerce", "hospitality management",
    "healthcare management", "rural management", "agri business",

    # Engineering & Technology
    "computer science", "information technology", "software engineering",
    "electronics", "electrical", "mechanical", "civil", "chemical",
    "aerospace", "automobile", "instrumentation", "telecommunication",
    "biomedical", "biotechnology", "environmental engineering",
    "marine engineering", "mining", "metallurgy", "textile",
    "production", "industrial engineering", "robotics", "mechatronics",
    "artificial intelligence", "machine learning", "data science",
    "cyber security", "cloud computing", "networking",
    "embedded systems", "vlsi", "signal processing",

    # Science
    "physics", "chemistry", "mathematics", "statistics", "biology",
    "microbiology", "biochemistry", "zoology", "botany", "geology",
    "environmental science", "food science", "nutrition",
    "forensic science", "astronomy", "bioinformatics",

    # Arts & Humanities
    "english", "hindi", "tamil", "malayalam", "kannada", "telugu",
    "history", "geography", "political science", "sociology",
    "psychology", "philosophy", "economics", "public administration",
    "journalism", "mass communication", "social work", "education",
    "fine arts", "performing arts", "music", "visual communication",
    "literature", "linguistics", "archaeology", "anthropology",

    # Medical & Health
    "medicine", "surgery", "dentistry", "nursing", "pharmacy",
    "physiotherapy", "occupational therapy", "radiology",
    "pathology", "pediatrics", "gynecology", "orthopedics",
    "dermatology", "ophthalmology", "psychiatry", "anaesthesia",
    "public health", "community medicine", "homeopathy", "ayurveda",

    # Law
    "law", "corporate law", "criminal law", "constitutional law",
    "intellectual property", "labour law", "tax law", "cyber law",

    # Commerce
    "commerce", "cost accounting", "company secretary", "taxation",
    "banking and finance", "financial accounting",

    # Architecture & Design
    "architecture", "interior design", "urban planning", "landscape",
    "product design", "fashion design", "graphic design", "animation",
    "industrial design",

    # Agriculture
    "agriculture", "horticulture", "agronomy", "soil science",
    "animal husbandry", "fisheries", "dairy science", "forestry",

    # Education
    "primary education", "secondary education", "special education",
    "physical education", "library science",
]


# ----------------------------
# CERTIFICATION KEYWORDS
# ----------------------------
CERT_KEYWORDS = [
    "certified", "certificate", "certification", "training",
    "license", "coursera", "udemy", "edx", "nptel", "linkedin learning",
    "google", "microsoft", "aws", "azure", "pmp", "six sigma",
    "iso", "comptia", "cisco", "oracle", "salesforce", "hubspot"
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

        if len(line) < 3:
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

            # collect up to 3 lookahead lines (safe boundary check)
            lookahead_lines = []
            for offset in range(1, 4):
                if i + offset >= len(education_section):
                    break
                candidate = str(education_section[i + offset]).strip()
                # stop if next line is another degree
                if detect_degree(candidate.lower()) != "UNKNOWN":
                    break
                lookahead_lines.append(candidate)

            combined_text = line + " " + " ".join(lookahead_lines)

            institution = extract_institution(combined_text)
            field       = extract_field(combined_text)
            year_range  = extract_year_range(combined_text)

            # VALIDATION
            if not is_valid_entry(degree, institution, year_range):
                i += 1
                continue

            education_list.append({
                "degree":          degree,
                "field":           field,
                "institution":     institution,
                "graduation_year": year_range
            })

            seen_degrees.add(degree)

            # advance past the lines we consumed
            i += 1 + len(lookahead_lines)
            continue

        # ----------------------------
        # CERTIFICATION BLOCK
        # ----------------------------
        if is_certification(lower):
            certifications.append({
                "name":     line,
                "issuer":   extract_institution(line),
                "year":     extract_year(line),
                "category": categorize_cert(line)
            })

        i += 1

    return {
        "education":      education_list,
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
# VALIDATION
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

    years = re.findall(r"\b(19|20)\d{2}\b", text)

    if len(years) >= 2:
        full = re.findall(r"\b(?:19|20)\d{2}\b", text)
        return f"{min(full)}-{max(full)}"

    if len(years) == 1:
        full = re.findall(r"\b(?:19|20)\d{2}\b", text)
        return full[0]

    return "UNKNOWN"


# ----------------------------
# FIELD EXTRACTION (EXPANDED)
# ----------------------------
def extract_field(text):

    text_lower = text.lower()

    # Pattern 1: degree in <field>  →  MBA in Finance
    match = re.search(
        r"(?:mba|bba|btech|b\.tech|mtech|m\.tech|msc|m\.sc|bsc|b\.sc|"
        r"be|b\.e|me|m\.e|mca|bca|ba|ma|b\.com|m\.com|llb|llm|b\.ed|m\.ed|pgdm)\s+"
        r"(?:in|of|specialization in|specialising in|major in)?\s*"
        r"([a-z][a-z ,&()/]+)",
        text_lower
    )
    if match:
        field = match.group(1).strip().rstrip("0123456789 -–")
        if len(field) > 2 and not _is_institution_fragment(field):
            return field.title()

    # Pattern 2: degree - <field>  →  MBA – Finance
    match = re.search(
        r"(?:mba|bba|btech|mtech|msc|bsc|be|me|mca|bca|ba|ma|b\.com|m\.com|llb|pgdm)"
        r"\s*[-–:]\s*([a-z][a-z ,&]+)",
        text_lower
    )
    if match:
        field = match.group(1).strip()
        if len(field) > 2 and not _is_institution_fragment(field):
            return field.title()

    # Pattern 3: (Finance)  →  parenthesised field
    match = re.search(r"\(([^()]{3,40})\)", text)
    if match:
        candidate = match.group(1).strip()
        # exclude year ranges like (2016-2018)
        if not re.match(r"^\d", candidate):
            return candidate.title()

    # Pattern 4: "Specialization: Finance" or "Major: Finance"
    match = re.search(
        r"(?:specialization|specialisation|major|stream|branch|discipline|focus)\s*[:\-–]\s*([a-z][a-z ,&]+)",
        text_lower
    )
    if match:
        return match.group(1).strip().title()

    # Pattern 5: standalone known field anywhere in combined text
    for field in sorted(FIELD_KEYWORDS, key=len, reverse=True):   # longest match first
        if re.search(rf"\b{re.escape(field)}\b", text_lower):
            return field.title()

    return ""


# ----------------------------
# INSTITUTION FRAGMENT CHECK
# (prevents "rajagiri college" being picked as field)
# ----------------------------
def _is_institution_fragment(text):
    inst_words = ["college", "university", "institute", "school",
                  "academy", "polytechnic", "iit", "nit", "iim"]
    return any(w in text.lower() for w in inst_words)


# ----------------------------
# INSTITUTION EXTRACTION
# ----------------------------
def extract_institution(text):

    # Pattern 1: Proper-cased institution with known suffix
    match = re.search(
        r"([A-Z][a-zA-Z ]+(?:College|University|Institute|School|Academy|"
        r"Polytechnic|IIT|NIT|IIM|XLRI|BITS|NIFT|NLU)"
        r"(?:\s+of\s+[A-Za-z &]+)*)",
        text
    )
    if match:
        return match.group(0).strip()

    # Pattern 2: All-caps institution abbreviation e.g. "CUSAT", "BITS Pilani"
    match = re.search(r"\b([A-Z]{2,6}(?:\s+[A-Z][a-z]+){0,3})\b", text)
    if match:
        candidate = match.group(0).strip()
        # make sure it's not just a degree token
        if detect_degree(candidate.lower()) == "UNKNOWN":
            return candidate

    return "UNKNOWN"


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

    if any(x in t for x in ["aws", "azure", "gcp", "cloud"]):
        return "CLOUD"

    if any(x in t for x in ["data", "ai", "machine learning", "deep learning", "nlp"]):
        return "DATA/AI"

    if any(x in t for x in ["python", "sql", "java", "javascript", "react"]):
        return "TECH"

    if any(x in t for x in ["pmp", "prince2", "six sigma", "agile", "scrum"]):
        return "PROJECT MANAGEMENT"

    if any(x in t for x in ["cisco", "comptia", "networking", "security"]):
        return "NETWORKING/SECURITY"

    if any(x in t for x in ["finance", "cfa", "frm", "banking"]):
        return "FINANCE"

    if any(x in t for x in ["hr", "human resource", "shrm", "payroll"]):
        return "HR"

    if any(x in t for x in ["marketing", "seo", "google ads", "hubspot"]):
        return "MARKETING"

    return "GENERAL"


# ----------------------------
# YEAR EXTRACTION
# ----------------------------
def extract_year(text):

    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    return years[-1] if years else "UNKNOWN"