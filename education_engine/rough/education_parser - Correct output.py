"""
education_parser.py
───────────────────
Robust education-section extractor for ANY sectioned resume format.

Handles:
  • Indian style  – "MBA – Finance & Marketing 2016–2018"
  • US style      – "B.S. in Health Information Management\nDePaul University · 2023"
  • Full words    – "Master of Science in Data Science\nCarnegie Mellon, 2022"
  • 3-line blocks – degree / institution / year on separate lines
  • Same-line     – "B.Tech – CS, IIT Bombay, 2020"
  • Comma lists   – "MBA, Finance, Symbiosis, Pune, 2014-2016"
  • Noise-heavy   – (cid:xxx), private-use unicode, declarations, achievements
  • Integrated    – "BBA LLB (Hons), Symbiosis Law School, 2018"
  • Honorifics    – "B.Sc. (Hons) in Statistics (First Class with Distinction)"
  • SSC / HSC     – "12th | Science | 87% | 2014"
"""

import re

# ═══════════════════════════════════════════════════════════════
# 1.  DEGREE MAP  (list of (pattern, label) — order matters)
#     Longer / more-specific patterns MUST come before shorter ones.
#     All patterns match against normalised lowercase text.
# ═══════════════════════════════════════════════════════════════
DEGREE_MAP = [

    # ── INTEGRATED / DUAL ─────────────────────────────────────
    (r"\bbba\s*ll\.?b\b",                           "BBA LLB"),
    (r"\bba\s*ll\.?b\b",                            "BA LLB"),
    (r"\bb\.?tech\s*mba\b",                         "B.TECH MBA"),

    # ── POSTGRADUATE ──────────────────────────────────────────
    (r"\bexecutive\s+mba\b",                        "EXECUTIVE MBA"),
    (r"\bmba\s*\(iim\)",                            "MBA (IIM)"),
    (r"\bmba\b",                                    "MBA"),
    (r"\bmaster\s+of\s+business\s+administration\b","MBA"),
    (r"\bpgdm\b",                                   "PGDM"),
    (r"\bpgdbm\b",                                  "PGDBM"),
    (r"\bpgdca\b",                                  "PGDCA"),
    (r"\bpg\s+diploma\b|\bpost.?graduate\s+diploma\b","PG DIPLOMA"),
    (r"\bm\.?tech\b|\bmtech\b",                     "M.TECH"),
    (r"\bmaster\s+of\s+technology\b",               "M.TECH"),
    (r"\bm\.?e\b(?!\s*[a-z]{2,})",                 "M.E"),
    (r"\bmaster\s+of\s+engineering\b",              "M.E"),
    (r"\bmsc\b|\bm\.sc\b",                          "MSC"),
    (r"\bmaster\s+of\s+science\b",                  "MS"),
    (r"\bm\.s\b(?!\s*[a-z]{2,})",                  "MS"),
    (r"\bms\b(?!\s*(?:excel|office|word|sql|access|powerpoint|teams|dynamics))", "MS"),
    (r"\bm\.com\b|\bmcom\b",                        "M.COM"),
    (r"\bmaster\s+of\s+commerce\b",                 "M.COM"),
    (r"\bm\.?a\b(?!\s*[a-z]{3,})",                 "MA"),
    (r"\bmaster\s+of\s+arts\b",                     "MA"),
    (r"\bmca\b",                                    "MCA"),
    (r"\bmaster\s+of\s+computer\s+applications\b",  "MCA"),
    (r"\bllm\b|\bll\.m\b",                         "LLM"),
    (r"\bmaster\s+of\s+laws\b",                    "LLM"),
    (r"\bm\.ed\b|\bmed\b(?!\s*school)",             "M.ED"),
    (r"\bmaster\s+of\s+education\b",                "M.ED"),
    (r"\bm\.phil\b|\bmphil\b",                      "M.PHIL"),
    (r"\bphd\b|\bph\.d\.?\b",                      "PHD"),
    (r"\bdoctor\s+of\s+philosophy\b",               "PHD"),
    (r"\bm\.arch\b|\bmarch\b(?!\s+[12]\d)",         "M.ARCH"),
    (r"\bmaster\s+of\s+architecture\b",             "M.ARCH"),
    (r"\bm\.plan\b",                                "M.PLAN"),
    (r"\bmd\b(?!\s*[a-z]{2,})",                    "MD"),
    (r"\bmds\b",                                    "MDS"),
    (r"\bm\.?pharm\b|\bmpharm\b",                   "M.PHARM"),
    (r"\bm\.lib\b",                                 "M.LIB"),
    (r"\bcma\s*\(inter\)|\bicwa\s*inter\b",         "CMA INTER"),
    (r"\bcma\b|\bicwa\b",                           "CMA"),
    (r"\bca\s*final\b",                             "CA FINAL"),
    (r"\bca\s*inter\b|\bca\s*ipcc\b",              "CA INTER"),
    (r"\bca\b(?!\s*[a-z]{3,})",                    "CA"),
    (r"\bcs\s*final\b",                             "CS FINAL"),
    (r"\bcs\s*inter\b",                             "CS INTER"),
    (r"\bcfa\b",                                    "CFA"),
    (r"\bfrm\b",                                    "FRM"),
    (r"\bactuarial\b",                              "ACTUARIAL"),

    # ── UNDERGRADUATE ─────────────────────────────────────────
    (r"\bbba\b",                                    "BBA"),
    (r"\bb\.com\b|\bbcom\b",                       "B.COM"),
    (r"\bbachelor\s+of\s+commerce\b",               "B.COM"),
    (r"\bb\.sc\s+nursing\b|\bbsc\s+nursing\b",      "BSC NURSING"),
    (r"\bbsc\b|\bb\.sc\b",                         "BSC"),
    (r"\bb\.tech\b|\bbtech\b",                     "B.TECH"),
    (r"\bbachelor\s+of\s+technology\b",               "B.TECH"),
    (r"\bb\.e\b(?!\s*(?:d\b|c\b|ng\b))",            "B.E"),
    (r"\bbe\b(?!\s*(?:d\b|c\b|ng\b|[a-z]{3,}))",   "B.E"),
    (r"\bbachelor\s+of\s+engineering\b",            "B.E"),
    (r"\bbca\b",                                    "BCA"),
    (r"\bbachelor\s+of\s+computer\s+applications\b","BCA"),
    (r"\bllb\b|\bll\.b\b",                         "LLB"),
    (r"\bbachelor\s+of\s+laws\b",                  "LLB"),
    (r"\bmbbs\b",                                   "MBBS"),
    (r"\bbds\b(?!\s*[a-z]{2,})",                   "BDS"),
    (r"\bbhms\b",                                   "BHMS"),
    (r"\bbams\b",                                   "BAMS"),
    (r"\bpharm\.?d\b",                             "PHARM.D"),
    (r"\bb\.?pharm\b|\bbpharm\b",                  "B.PHARM"),
    (r"\bb\.arch\b|\bbarch\b",                     "B.ARCH"),
    (r"\bbachelor\s+of\s+architecture\b",             "B.ARCH"),
    (r"\bb\.plan\b",                                "B.PLAN"),
    (r"\bb\.ed\b|\bbed\b(?!\s*room)",              "B.ED"),
    (r"\bbachelor\s+of\s+education\b",               "B.ED"),
    (r"\bb\.lib\b",                                 "B.LIB"),
    (r"\bbhm\b|\bb\.h\.m\b",                       "BHM"),
    (r"\bbnys\b",                                   "BNYS"),
    (r"\bb\.des\b|\bbdes\b",                       "B.DES"),
    (r"\bb\.fa\b|\bbfa\b",                         "BFA"),
    # B.S. / BS — must come AFTER B.Sc, B.Tech, B.Ed etc.
    (r"\bb\.s\b(?!\s*c\b)",                        "BS"),
    (r"\bbs\b(?!\s*(?:c\b|[a-z]{4,}))",           "BS"),
    (r"\bbachelor\s+of\s+science\b",                "BS"),
    # B.A. / BA — after more-specific BA combos
    (r"\bb\.a\b(?!\s*[a-z]{3,})",                  "BA"),
    (r"\bba\b(?!\s*[a-z]{3,})",                    "BA"),
    (r"\bbachelor\s+of\s+arts\b",                   "BA"),

    # ── DIPLOMA / SCHOOL ──────────────────────────────────────
    (r"\badvanced\s+diploma\b",                     "ADVANCED DIPLOMA"),
    (r"\bdiploma\b",                                "DIPLOMA"),
    (r"\bpolytechnic\b|\bpoly\b",                   "POLYTECHNIC"),
    (r"\bitti\b|\biti\b",                           "ITI"),
    (r"\bsslc\b",                                   "SSLC"),
    (r"\bhsc\b|\b10\+2\b|\bintermediate\b|\bplus\s+two\b|\bplus\s+2\b|\b12th\b|\bclass\s+xii\b|\bxii\b(?!\s*[a-z])", "HSC"),
    (r"\bssc\b|\b10th\b|\bmatriculation\b|\bclass\s+x\b(?!\s*[a-z])", "SSC"),
]

# ═══════════════════════════════════════════════════════════════
# 2.  FIELD VOCABULARY  (longer entries must come before shorter)
# ═══════════════════════════════════════════════════════════════
FIELD_KEYWORDS = [
    # Business & Management
    "finance & marketing", "finance and marketing",
    "banking and finance", "financial accounting",
    "business administration", "business analytics",
    "financial management", "strategic management",
    "organizational behavior", "project management",
    "healthcare management", "hospitality management",
    "retail management", "international business",
    "wealth management", "rural management",
    "agri business", "e-commerce",
    "human resources", "supply chain",
    "finance", "marketing", "operations", "management",
    "entrepreneurship", "logistics", "banking", "insurance",
    "taxation", "accounting", "auditing", "investment",
    # Engineering & Technology
    "computer science and engineering", "electronics and communication engineering",
    "electronics and communication",
    "information technology", "software engineering",
    "computer science", "computer applications",
    "electrical engineering", "mechanical engineering",
    "civil engineering", "chemical engineering",
    "aerospace engineering", "environmental engineering",
    "marine engineering", "industrial engineering",
    "electronics", "electrical", "mechanical", "civil", "chemical",
    "aerospace", "automobile", "instrumentation", "telecommunication",
    "biomedical", "biotechnology", "metallurgy", "textile",
    "production", "robotics", "mechatronics",
    "artificial intelligence", "machine learning", "data science",
    "cyber security", "cloud computing", "networking",
    "embedded systems", "vlsi", "signal processing", "mining",
    # Health / Medical Informatics
    "health information management", "health informatics",
    "biomedical informatics", "clinical informatics",
    "public health informatics", "healthcare informatics",
    "health data analytics", "medical informatics",
    # Science
    "physics", "chemistry", "mathematics", "statistics", "biology",
    "microbiology", "biochemistry", "zoology", "botany", "geology",
    "environmental science", "food science", "nutrition",
    "forensic science", "astronomy", "bioinformatics",
    "biological sciences", "chemical sciences", "physical sciences",
    "mathematical sciences", "life sciences", "earth sciences",
    "natural sciences", "applied sciences", "social sciences",
    "cognitive science", "neuroscience", "exercise science",
    "sport science", "kinesiology", "actuarial science",
    "marine science", "atmospheric science", "materials science",
    # Arts & Humanities
    "political science", "mass communication", "public administration",
    "visual communication", "performing arts", "fine arts",
    "social work", "education", "journalism",
    "english", "hindi", "tamil", "malayalam", "kannada", "telugu",
    "history", "geography", "sociology", "psychology",
    "philosophy", "economics", "literature", "linguistics",
    "archaeology", "anthropology", "music",
    # Medical & Health
    "public health", "community medicine",
    "occupational therapy", "physiotherapy",
    "medicine", "surgery", "dentistry", "nursing", "pharmacy",
    "radiology", "pathology", "pediatrics", "gynecology",
    "orthopedics", "dermatology", "ophthalmology", "psychiatry",
    "anaesthesia", "homeopathy", "ayurveda",
    # Law
    "corporate law", "criminal law", "constitutional law",
    "intellectual property", "labour law", "tax law", "cyber law", "law",
    # Commerce
    "commerce", "cost accounting", "company secretary",
    # Architecture & Design
    "interior design", "urban planning",
    "product design", "fashion design", "graphic design", "animation",
    "industrial design", "architecture", "landscape",
    # Agriculture
    "agriculture", "horticulture", "agronomy", "soil science",
    "animal husbandry", "fisheries", "dairy science", "forestry",
    # Education subtypes
    "primary education", "secondary education", "special education",
    "physical education", "library science",
]

# ═══════════════════════════════════════════════════════════════
# 3.  CERTIFICATION KEYWORDS
# ═══════════════════════════════════════════════════════════════
CERT_KEYWORDS = [
    "certified", "certificate", "certification", "training", "rhit", "cmaa",
    "license", "coursera", "udemy", "edx", "nptel", "linkedin learning",
    "google", "microsoft", "aws", "azure", "pmp", "six sigma", "hipaa",
    "iso", "comptia", "cisco", "oracle", "salesforce", "hubspot",
]

# ═══════════════════════════════════════════════════════════════
# 4.  NOISE PATTERNS  – lines matching any of these are dropped
# ═══════════════════════════════════════════════════════════════
NOISE_PATTERNS = [
    r"^\(cid:\d+\)",
    r"^[\uf000-\uf8ff\u2022\u25cf\u25aa\u25ba\u2023\u2043]+",
    r"^[•●◆▪▸►✓✔\-–—]+\s*$",
    r"^i\s+hereby\s+declare",
    r"\bkey\s+achievements\b",
    r"^\d+%$",
    r"^page\s+\d+\s*(?:of\s*\d+)?$",
    r"^references?\s*(available)?\s*(on\s+request)?$",
    r"^skills?\s*:?$",
    r"^activities\s*:?$",
    r"^hobbies?\s*:?$",
    r"^languages?\s*:?$",
    r"^(tel|phone|email|mobile)\s*[:\-]",
    r"^https?://",
    r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$",
    r"^\+?\d[\d\s\-()]{6,}$",
]

# ═══════════════════════════════════════════════════════════════
# 5.  INSTITUTION SUFFIX VOCABULARY
# ═══════════════════════════════════════════════════════════════
_INST_SUFFIX_SET = {
    "college", "university", "institute", "school", "academy",
    "polytechnic", "iit", "nit", "iim", "xlri", "bits", "nift",
    "nlu", "iiser", "iisc", "ximb", "fms", "spjimr",
    "coursera", "ibm", "ahima", "nha", "medtrainer", "johns hopkins"
}

_INST_SUFFIX_RE = (
    r"College|University|Institute|School|Academy|Polytechnic|"
    r"IIT|NIT|IIM|XLRI|BITS|NIFT|NLU|IISER|IISc|Coursera|IBM|AHIMA|NHA|MedTrainer"
)

# ═══════════════════════════════════════════════════════════════
# 6.  TEXT NORMALISATION
# ═══════════════════════════════════════════════════════════════
def _normalise(text):
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"[\u00b7\u2022\u25cf·•]", " ", text)
    text = re.sub(r"\u00a0", " ", text)
    return text


def _is_noise(line):
    if not line:
        return True
    lower = line.lower().strip()
    for pat in NOISE_PATTERNS:
        if re.search(pat, lower):
            return True
    return False


# ═══════════════════════════════════════════════════════════════
# 7.  DEGREE DETECTION
# ═══════════════════════════════════════════════════════════════
def detect_degree(raw):
    text = _normalise(raw).lower()
    # Strip trailing honours / class markers before matching
    text = re.sub(
        r"\s*\((?:hons?|honors?|first\s+class[^)]*|second\s+class[^)]*|distinction[^)]*)\)",
        "", text
    )
    for pattern, degree in DEGREE_MAP:
        if re.search(pattern, text):
            return degree
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# 8.  YEAR EXTRACTION
# ═══════════════════════════════════════════════════════════════
def extract_year_range(text):
    text = _normalise(text)
    m = re.search(r"\b((?:19|20)\d{2})\s*[-/]\s*((?:19|20)\d{2})\b", text)
    if m:
        return "{}-{}".format(m.group(1), m.group(2))
    years = re.findall(r"\b((?:19|20)\d{2})\b", text)
    if len(years) >= 2:
        return "{}-{}".format(min(years), max(years))
    if len(years) == 1:
        return years[0]
    return "UNKNOWN"


def extract_year(text):
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    return years[-1] if years else "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# 9.  FIELD EXTRACTION
# ═══════════════════════════════════════════════════════════════

# All degree stems for use inside field-extraction regex
_DEG_STEMS = (
    r"(?:ph\.?d|doctor\s+of\s+philosophy"
    r"|m\.?tech|mtech|master\s+of\s+technology"
    r"|m\.?e\b|master\s+of\s+engineering"
    # MS/BS patterns with optional periods placed BEFORE M.Sc/B.Sc
    r"|master\s+of\s+science|m\.s\.?\b|ms\b"
    r"|msc|m\.sc"
    r"|mba|master\s+of\s+business\s+administration"
    r"|pgdm|m\.com|mcom|master\s+of\s+commerce"
    r"|m\.?a\b|master\s+of\s+arts|mca|llm|m\.ed|m\.phil"
    r"|bba|b\.com|bcom|bachelor\s+of\s+commerce"
    r"|b\.sc\s+nursing|bsc\s+nursing"
    # Bachelor of Science (B.S.) placed BEFORE B.Sc
    r"|bachelor\s+of\s+science|b\.s\.?\b|bs\b"
    r"|bsc|b\.sc"
    r"|b\.tech|btech|bachelor\s+of\s+technology"
    r"|b\.e\b|be\b|bachelor\s+of\s+engineering"
    r"|bca|bachelor\s+of\s+computer\s+applications"
    r"|llb|bachelor\s+of\s+laws"
    r"|bachelor\s+of\s+arts|b\.a\.?\b|ba\b"
    r"|b\.ed|bachelor\s+of\s+education"
    r"|b\.arch|bachelor\s+of\s+architecture"
    r"|b\.pharm|b\.des|bfa"
    r"|diploma|advanced\s+diploma)"
)



def _truncate_at_inst_word(raw: str) -> str:
    """
    Truncate a field candidate at the first institution-suffix token.
    e.g. "biological sciences georgia state university 2020"
         → "biological sciences"
    Also strips trailing Proper-Noun tokens that look like an institution
    name prefix (e.g. "Georgia State" after "Biological Sciences").
    """
    _INST_STOP = {
        "college", "university", "institute", "school", "academy",
        "polytechnic", "iit", "nit", "iim", "xlri", "bits", "nift", "nlu",
    }
    tokens = raw.strip().split()
    # Step 1: cut at first hard institution keyword
    for idx, tok in enumerate(tokens):
        if tok.lower() in _INST_STOP:
            tokens = tokens[:idx]
            break
    # Step 2: strip trailing Title-Case proper-noun tokens
    # (catches "Georgia State" in "biological sciences Georgia State")
    while tokens and re.match(r'^[A-Z]', tokens[-1]):
        tokens.pop()
    return " ".join(tokens).strip().rstrip("0123456789 -,|.()")

def extract_field(text, combined=None):
    norm = _normalise(text)
    tl = norm.lower()

    # Optimized Pattern: Explicitly handles the period after degree and forces a separator check
    m = re.search(
        _DEG_STEMS + 
        r"\.?\s*" +  # Matches the optional period and trailing space
        r"(?:in|of|major\s+in|specialization\s+in|specialising\s+in|[-/:]?)\s+" + # Separators
        r"([a-z][a-z ,&()/]+)", # The Field Capture Group
        tl
    )
    
    if m:
        raw = m.group(1).strip().rstrip("0123456789 -,|")
        # Truncate at the first institution-suffix word so that
        # "biological sciences georgia state university" → "biological sciences"
        raw = _truncate_at_inst_word(raw)
        if len(raw) > 2 and not _is_inst_fragment(raw):
            return _clean_field(raw)


    # P2: explicit dash separator
    m = re.search(_DEG_STEMS + r"\.?\s*-\s*([a-z][a-z ,&()/]+)", tl)
    if m:
        raw = m.group(1).strip().rstrip("0123456789 -,|")
        raw = _truncate_at_inst_word(raw)
        if len(raw) > 2 and not _is_inst_fragment(raw):
            return _clean_field(raw)

    # For P3/P4/P5 use combined text (if provided) so we get more signal
    scan_text  = combined if combined else text
    scan_lower = _normalise(scan_text).lower()

    # P3: "Specialization: <field>"
    m = re.search(
        r"(?:specialization|specialisation|major|stream|branch|discipline|focus)"
        r"\s*[:\-]\s*([a-z][a-z ,&]+)",
        scan_lower
    )
    if m:
        return _clean_field(m.group(1).strip())

    # P4: parenthesised field (not year, not honours, not institution)
    for m in re.finditer(r"\(([^()]{3,50})\)", _normalise(scan_text)):
        candidate = m.group(1).strip()
        c_lower = candidate.lower()
        if (not re.match(r"^\d", candidate)
                and not re.match(
                    r"^(?:hons?|honors?|first|second|distinction|autonomous|pvt|ltd)",
                    c_lower)
                and not _is_inst_fragment(candidate)):
            return candidate.title()

    # P5: vocabulary keyword scan (longest match wins)
    for kw in sorted(FIELD_KEYWORDS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(kw) + r"\b", scan_lower):
            return kw.title()

    return ""


def _clean_field(raw):
    raw = re.sub(r"\s*[\|,]\s*.*$", "", raw)
    raw = re.sub(r"\s+\d.*$", "", raw)
    raw = raw.strip(" -,.()")
    return raw.title() if raw else ""


def _is_inst_fragment(text):
    return any(w in text.lower() for w in _INST_SUFFIX_SET)


# ═══════════════════════════════════════════════════════════════
# 10.  INSTITUTION EXTRACTION
#      Try each lookahead line individually first so that
#      "B.S. in Field\nInstitution · Year" never bleeds field
#      words into the institution name.
# ═══════════════════════════════════════════════════════════════
def extract_institution(text):
    norm = _normalise(text)

    # Pattern 1 – proper-cased name with a known suffix keyword
    m = re.search(
        r"([A-Z][a-zA-Z]+(?:\s+(?:of\s+)?[A-Za-z]+){0,6}?"
        r"\s*(?:" + _INST_SUFFIX_RE + r")"
        r"(?:\s+of\s+[A-Za-z &]+)*)",
        norm
    )
    if m:
        raw    = m.group(0).strip()
        tokens = raw.split()
        kw_idx = next(
            (i for i, t in enumerate(tokens) if t.lower() in _INST_SUFFIX_SET),
            None
        )
        if kw_idx is not None:
            start = kw_idx
            while start > 0:
                prev = tokens[start - 1]
                if (re.match(r"^[A-Z]", prev)
                        and prev.lower() not in {"in", "of", "and", "the", "for", "at", "by", "with"}):
                    start -= 1
                else:
                    break
            return " ".join(tokens[start:]).strip()
        return raw

    # Pattern 2 – "University of <Place>"
    m = re.search(
        r"University\s+of\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*",
        norm
    )
    if m:
        return m.group(0).strip()

    # Pattern 3 – all-caps abbreviation
    m = re.search(r"\b([A-Z]{2,6}(?:\s+[A-Z][a-z]+){0,3})\b", norm)
    if m:
        candidate = m.group(0).strip()
        if detect_degree(candidate) == "UNKNOWN":
            return candidate
    
    # Fallback: check for specific online platforms/providers
    for kw in ["Coursera", "IBM", "Johns Hopkins", "AHIMA", "NHA", "MedTrainer"]:
        if kw.lower() in norm.lower():
            return kw

    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# 11.  CERTIFICATION HELPERS
# ═══════════════════════════════════════════════════════════════
def is_certification(text):
    tl = text.lower()
    # Captures "Certificate in..." specifically
    if re.search(r"\bcertificate\s+in\b", tl): return True
    return any(k in tl for k in CERT_KEYWORDS)


def categorize_cert(text):
    t = text.lower()
    if any(x in t for x in ["aws", "azure", "gcp", "cloud"]):                   return "CLOUD"
    if any(x in t for x in ["data", "ai", "machine learning", "deep learning", "nlp"]): return "DATA/AI"
    if any(x in t for x in ["python", "sql", "java", "javascript", "react"]):   return "TECH"
    if any(x in t for x in ["pmp", "prince2", "six sigma", "agile", "scrum"]):  return "PROJECT MANAGEMENT"
    if any(x in t for x in ["cisco", "comptia", "networking", "security"]):      return "NETWORKING/SECURITY"
    if any(x in t for x in ["finance", "cfa", "frm", "banking"]):                return "FINANCE"
    if any(x in t for x in ["hr", "human resource", "shrm", "payroll"]):         return "HR"
    if any(x in t for x in ["marketing", "seo", "google ads", "hubspot"]):       return "MARKETING"
    if any(x in t for x in ["medical", "billing", "healthcare", "hipaa", "rhit", "cmaa"]): return "HEALTHCARE"
    return "GENERAL"


# ═══════════════════════════════════════════════════════════════
# 12.  VALIDATION
# ═══════════════════════════════════════════════════════════════
def is_valid_entry(degree, institution, year):
    if degree == "UNKNOWN":
        return False
    if institution == "UNKNOWN" and year == "UNKNOWN":
        return False
    return True


# ═══════════════════════════════════════════════════════════════
# 13.  MAIN PARSER
# ═══════════════════════════════════════════════════════════════
def extract_education(resume_json):
    """
    Input : resume_json with an "education" key (list of strings).
    Output: {"education": [...], "certifications": [...]}
    """
    raw_section = resume_json.get("education", [])
    if not isinstance(raw_section, list):
        return {"education": [], "certifications": []}

    # Step 1 – strip noise
    cleaned = [str(ln).strip() for ln in raw_section]
    cleaned = [ln for ln in cleaned if ln and not _is_noise(ln)]

    education_list = []
    certifications = []
    seen_degrees   = set()

    i = 0
    while i < len(cleaned):
        line   = cleaned[i]
        degree = detect_degree(line)

        # ── Education block ──────────────────────────────────
        if degree != "UNKNOWN":
            if degree in seen_degrees:
                i += 1
                continue

            # Collect up to 4 lookahead lines
            lookahead = []
            for offset in range(1, 5):
                if i + offset >= len(cleaned):
                    break
                nxt = cleaned[i + offset]
                if detect_degree(nxt) != "UNKNOWN":
                    break
                if is_certification(nxt.lower()):
                    break
                lookahead.append(nxt)

            # Try institution line-by-line first (avoids field bleed)
            institution = "UNKNOWN"
            for la in lookahead:
                candidate = extract_institution(la)
                if candidate != "UNKNOWN":
                    institution = candidate
                    break
            if institution == "UNKNOWN":
                institution = extract_institution(line)

            combined = line + " " + " ".join(lookahead)
            if institution == "UNKNOWN":
                institution = extract_institution(combined)

            field      = extract_field(line, combined)
            year_range = extract_year_range(combined)

            if not is_valid_entry(degree, institution, year_range):
                i += 1
                continue

            education_list.append({
                "degree":          degree,
                "field":           field,
                "institution":     institution,
                "graduation_year": year_range,
            })
            seen_degrees.add(degree)
            i += 1 + len(lookahead)
            continue

        # ── Certification block (Multi-line Lookahead Implemented) ──────────────────────────────
        if is_certification(line):
            # Peek at next line ONLY if it is pure issuer/year metadata.
            # A metadata line may contain platform names (coursera, ibm, google)
            # but must NOT contain cert-title words (certified, certificate, etc.)
            _CERT_TITLE_WORDS = {
                "certified", "certificate", "certification", "training", "license"
            }
            cert_lookahead = ""
            if i + 1 < len(cleaned):
                nxt = cleaned[i + 1]
                nxt_lower = nxt.lower()
                nxt_is_meta      = bool(re.search(r"[\u00b7·/|]|\b(?:19|20)\d{2}\b", nxt))
                nxt_has_title    = any(w in nxt_lower for w in _CERT_TITLE_WORDS)
                nxt_is_degree    = detect_degree(nxt) != "UNKNOWN"
                # Merge if: looks like metadata AND has no cert-title words AND not a degree
                if nxt_is_meta and not nxt_has_title and not nxt_is_degree:
                    cert_lookahead = nxt

            full_cert_text = (line + " " + cert_lookahead).strip()
            certifications.append({
                "name":     line.strip(" •·"),
                "issuer":   extract_institution(full_cert_text if cert_lookahead else line),
                "year":     extract_year(full_cert_text),
                "category": categorize_cert(full_cert_text),
            })
            i += (2 if cert_lookahead else 1)
            continue

        i += 1

    return {"education": education_list, "certifications": certifications}


# ═══════════════════════════════════════════════════════════════
# 14.  SELF-TEST  (python education_parser.py)
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import json

    TESTS = [
        {
            "name": "1. Indian MBA/BBA (Amala-style)",
            "education": [
                "MBA \u2013 Finance & Marketing 2016 \u2013 2018",
                "Rajagiri College of Social Sciences (Autonomous), RCBS | 70%",
                "BBA \u2013 Business Administration 2013 \u2013 2016",
                "Rajagiri College of Management and Applied Sciences, RCMAS | 84%",
                "KEY ACHIEVEMENTS",
                "\uf0d8 Received Client Appreciation",
                "I hereby declare that all information furnished above is true.",
            ],
            "expect_degrees": ["MBA", "BBA"],
        },
        {
            "name": "2. US B.S. with middot year",
            "education": [
                "(cid:127) Attention to Detail",
                "(cid:127) Team Collaboration",
                "B.S. in Health Information Management",
                "DePaul University \u00b7 2023",
            ],
            "expect_degrees": ["BS"],
        },
        {
            "name": "3. M.S. + B.S. with middot",
            "education": [
                "Collaboration",
                "M.S. in Biomedical Informatics",
                "Boston University \u00b7 2021",
                "B.S. in Biochemistry",
                "University of Ghana \u00b7 2019",
            ],
            "expect_degrees": ["MS", "BS"],
        },
        {
            "name": "4. Degree + institution same line",
            "education": [
                "B.Tech in Computer Science - IIT Bombay, 2020",
                "Class XII - Delhi Public School, 2016",
            ],
            "expect_degrees": ["B.TECH", "HSC"],
        },
        {
            "name": "5. 3-line block: degree / institution / year",
            "education": [
                "Master of Business Administration",
                "Harvard Business School",
                "2019 - 2021",
            ],
            "expect_degrees": ["MBA"],
        },
        {
            "name": "6. PhD",
            "education": [
                "Ph.D. in Computer Science",
                "Stanford University, 2018",
            ],
            "expect_degrees": ["PHD"],
        },
        {
            "name": "7. Year range with slash",
            "education": [
                "MBA Finance, XLRI Jamshedpur, 2019/2021",
            ],
            "expect_degrees": ["MBA"],
        },
        {
            "name": "8. GPA on institution line",
            "education": [
                "B.Sc Computer Science",
                "University of Mumbai | CGPA: 8.5 | 2018-2021",
            ],
            "expect_degrees": ["BSC"],
        },
        {
            "name": "9. Certifications mixed in",
            "education": [
                "B.Tech - Electronics & Communication",
                "NIT Trichy, 2015-2019",
                "AWS Certified Solutions Architect - 2022",
                "Google Data Analytics Certificate - Coursera, 2023",
            ],
            "expect_degrees": ["B.TECH"],
            "expect_certs": 2,
        },
        {
            "name": "10. All-caps institution (CUSAT)",
            "education": [
                "MCA - Computer Applications",
                "CUSAT, Kochi | 2017-2020",
            ],
            "expect_degrees": ["MCA"],
        },
        {
            "name": "11. Indian 10th and 12th",
            "education": [
                "12th | Science Stream | 2014 | 87%",
                "St. Joseph's Higher Secondary School",
                "10th | 2012 | 91%",
                "St. Joseph's High School",
            ],
            "expect_degrees": ["HSC", "SSC"],
        },
        {
            "name": "12. Degree with Honors text",
            "education": [
                "Bachelor of Science in Statistics (First Class with Distinction)",
                "University of Nairobi, 2020",
            ],
            "expect_degrees": ["BS"],
        },
        {
            "name": "13. Heavy noise lines",
            "education": [
                "Skills: Python, SQL",
                "\u2022 Communication",
                "\u2022 Leadership",
                "M.Tech in Data Science",
                "IIT Madras | 2020-2022",
                "B.E in Mechanical Engineering",
                "Anna University | 2015-2019",
                "References available on request",
            ],
            "expect_degrees": ["M.TECH", "B.E"],
        },
        {
            "name": "14. Full-word degree names",
            "education": [
                "Master of Science in Data Science",
                "Carnegie Mellon University, 2022",
                "Bachelor of Technology in Electrical Engineering",
                "IIT Delhi, 2020",
            ],
            "expect_degrees": ["MS", "B.TECH"],
        },
        {
            "name": "15. Single-line comma format",
            "education": [
                "MBA, Finance, Symbiosis Institute of Business Management, Pune, 2014-2016",
                "B.Com, Accounting, St. Xavier's College, Mumbai, 2011-2014",
            ],
            "expect_degrees": ["MBA", "B.COM"],
        },
        {
            "name": "16. No year present",
            "education": [
                "B.Sc. in Physics",
                "Presidency College, Chennai",
            ],
            "expect_degrees": ["BSC"],
        },
        {
            "name": "17. LLB Law degree",
            "education": [
                "LLB (Hons) - Corporate Law",
                "National Law School of India, Bangalore, 2018",
            ],
            "expect_degrees": ["LLB"],
        },
        {
            "name": "18. BBA LLB integrated",
            "education": [
                "BBA LLB (Hons), Symbiosis Law School, Pune, 2013-2018",
            ],
            "expect_degrees": ["BBA LLB"],
        },
        {
            "name": "19. No parseable education",
            "education": [
                "Strong communication skills",
                "Team player",
                "5 years of experience",
            ],
            "expect_degrees": [],
        },
        {
            "name": "20. PGDM",
            "education": [
                "PGDM - Marketing & Sales",
                "IIM Ahmedabad, 2015-2017",
            ],
            "expect_degrees": ["PGDM"],
        },
    ]

    PASS = FAIL = 0
    for tc in TESTS:
        result      = extract_education({"education": tc["education"]})
        got_degrees = [e["degree"] for e in result["education"]]
        expected    = tc.get("expect_degrees", [])
        exp_certs   = tc.get("expect_certs", None)
        ok_deg      = set(got_degrees) == set(expected)
        ok_cert     = exp_certs is None or len(result["certifications"]) == exp_certs
        ok          = ok_deg and ok_cert

        symbol = "\u2705 PASS" if ok else "\u274c FAIL"
        if ok: PASS += 1
        else:  FAIL += 1

        print("{} {}".format(symbol, tc["name"]))
        if not ok_deg:
            print("       degrees  expected={}  got={}".format(expected, got_degrees))
        if not ok_cert:
            print("       certs    expected={}  got={}".format(exp_certs, len(result["certifications"])))
        for e in result["education"]:
            print("         -> {:<12} | field: {:<35} | inst: {:<45} | year: {}".format(
                e["degree"], e["field"], e["institution"], e["graduation_year"]))
        for c in result["certifications"]:
            print("         CERT -> Name: {:<40} | Issuer: {:<20} | Year: {}".format(
                c["name"][:40], c["issuer"], c["year"]))

    print("\n" + "="*60)
    print("RESULTS: {}/{} passed   ({} failed)".format(PASS, PASS+FAIL, FAIL))