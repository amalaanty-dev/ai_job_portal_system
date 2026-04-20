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


# ═══════════════════════════════════════════════════════════════
# CONFIG TABLES
# ═══════════════════════════════════════════════════════════════

# ----------------------------
# DEGREE PRESTIGE WEIGHT
# BUG 7 FIX: added BS, MS, MA, BA, PGDM, M.PHARM and all
#            other abbreviations the parser can emit.
# ----------------------------
DEGREE_WEIGHT = {
    # Doctoral
    "PHD":           1.00,
    "MD":            1.00,
    "MDS":           0.95,
    # Postgraduate
    "MBA":           0.90,
    "EXECUTIVE MBA": 0.90,
    "MBA (IIM)":     0.92,
    "PGDM":          0.88,
    "PGDBM":         0.85,
    "PGDCA":         0.80,
    "PG DIPLOMA":    0.75,
    "M.TECH":        0.87,
    "M.E":           0.85,
    "MSC":           0.82,
    "MS":            0.82,
    "MA":            0.78,
    "M.COM":         0.78,
    "MCA":           0.80,
    "LLM":           0.80,
    "M.ED":          0.72,
    "M.PHIL":        0.78,
    "M.ARCH":        0.80,
    "M.PLAN":        0.78,
    "M.PHARM":       0.80,
    "M.LIB":         0.72,
    "CA":            0.85,
    "CMA":           0.80,
    "CFA":           0.85,
    "CS":            0.78,
    "FRM":           0.80,
    "ACTUARIAL":     0.82,
    # Undergraduate
    "B.TECH":        0.75,
    "B.E":           0.75,
    "BSC":           0.70,
    "BS":            0.70,       # FIX: was missing → defaulted to 0.5
    "BCA":           0.70,
    "BBA":           0.68,
    "BA":            0.65,       # FIX: was missing
    "B.COM":         0.65,
    "LLB":           0.68,
    "MBBS":          0.82,
    "BDS":           0.75,
    "B.PHARM":       0.70,
    "B.ARCH":        0.70,
    "B.ED":          0.65,
    "B.DES":         0.68,
    "BFA":           0.65,
    "BHM":           0.65,
    "BSC NURSING":   0.70,
    "BBA LLB":       0.70,
    "BA LLB":        0.68,
    # Diploma / School
    "DIPLOMA":       0.55,
    "ADVANCED DIPLOMA": 0.58,
    "POLYTECHNIC":   0.52,
    "ITI":           0.45,
    "HSC":           0.40,
    "SSC":           0.30,
}


# ----------------------------
# DEGREE → LEVEL MAP
# BUG 1 FIX: replaces string-in-text boost with level hierarchy matching.
# ----------------------------
DEGREE_LEVEL = {
    # Doctoral
    "PHD": "PHD", "MD": "PHD", "MDS": "PHD",
    # Postgraduate
    "MBA": "PG", "EXECUTIVE MBA": "PG", "MBA (IIM)": "PG",
    "M.TECH": "PG", "M.E": "PG", "MSC": "PG", "MS": "PG",
    "MA": "PG", "M.COM": "PG", "MCA": "PG", "LLM": "PG",
    "M.ED": "PG", "M.PHIL": "PG", "M.ARCH": "PG", "M.PLAN": "PG",
    "M.PHARM": "PG", "M.LIB": "PG", "PGDM": "PG", "PGDBM": "PG",
    "PGDCA": "PG", "PG DIPLOMA": "PG",
    "CA": "PG", "CMA": "PG", "CFA": "PG", "CS": "PG",
    "FRM": "PG", "ACTUARIAL": "PG",
    # Undergraduate
    "B.TECH": "UG", "B.E": "UG", "BSC": "UG", "BS": "UG",
    "BCA": "UG", "BBA": "UG", "BA": "UG", "B.COM": "UG",
    "LLB": "UG", "MBBS": "UG", "BDS": "UG", "B.PHARM": "UG",
    "B.ARCH": "UG", "B.ED": "UG", "B.DES": "UG", "BFA": "UG",
    "BHM": "UG", "BSC NURSING": "UG", "BBA LLB": "UG", "BA LLB": "UG",
    # Diploma / School
    "DIPLOMA": "DIPLOMA", "ADVANCED DIPLOMA": "DIPLOMA",
    "POLYTECHNIC": "DIPLOMA", "ITI": "DIPLOMA",
    "HSC": "SCHOOL", "SSC": "SCHOOL",
}

# Level compatibility: given what JD requires, how well does candidate level fit?
LEVEL_MATCH_SCORE = {
    "PHD":     {"PHD": 1.0, "PG": 0.60, "UG": 0.30, "DIPLOMA": 0.10, "SCHOOL": 0.0},
    "PG":      {"PHD": 1.0, "PG": 1.00, "UG": 0.55, "DIPLOMA": 0.20, "SCHOOL": 0.0},
    "UG":      {"PHD": 1.0, "PG": 1.00, "UG": 1.00, "DIPLOMA": 0.40, "SCHOOL": 0.1},
    "DIPLOMA": {"PHD": 1.0, "PG": 1.00, "UG": 1.00, "DIPLOMA": 1.00, "SCHOOL": 0.3},
    "SCHOOL":  {"PHD": 1.0, "PG": 1.00, "UG": 1.00, "DIPLOMA": 1.00, "SCHOOL": 1.0},
    None:      {"PHD": 0.9, "PG": 0.80, "UG": 0.70, "DIPLOMA": 0.50, "SCHOOL": 0.3},
}


# ----------------------------
# FIELD DOMAIN MAP
# BUG 2 FIX: replaces bare token overlap with domain synonym matching.
# Each domain maps field keywords → JD keywords.
# ----------------------------
FIELD_DOMAIN_MAP = {
    # Technology
    "computer_science":    ["computer science", "cs", "software", "information technology", "it", "computing"],
    "data_science":        ["data science", "data analytics", "analytics", "machine learning", "ai",
                            "artificial intelligence", "deep learning", "nlp", "data analysis"],
    "electronics":         ["electronics", "ece", "embedded", "vlsi", "telecommunication"],
    "electrical":          ["electrical", "power systems"],
    "mechanical":          ["mechanical", "manufacturing", "production", "automobile"],
    "civil":               ["civil", "structural", "construction"],
    "chemical":            ["chemical", "process engineering"],
    "biotechnology":       ["biotechnology", "biotech", "genetic", "genomics"],
    "cyber_security":      ["cyber security", "cybersecurity", "information security", "network security"],
    # Business
    "business":            ["business", "management", "administration", "mba", "commerce"],
    "finance":             ["finance", "financial", "accounting", "investment", "banking",
                            "wealth", "cfa", "frm", "treasury", "audit"],
    "marketing":           ["marketing", "brand", "digital marketing", "seo", "advertising", "sales"],
    "hr":                  ["human resources", "hr", "talent", "recruitment", "payroll"],
    "operations":          ["operations", "supply chain", "logistics", "scm", "procurement"],
    # Health & Life Sciences
    "health_informatics":  ["health informatics", "health information", "healthcare informatics",
                            "medical informatics", "clinical informatics", "ehr", "health data"],
    "public_health":       ["public health", "epidemiology", "community health", "health policy"],
    "biological_sciences": ["biology", "biological", "life sciences", "biosciences",
                            "biochemistry", "microbiology", "genetics", "molecular"],
    "health_sciences":     ["health sciences", "health science", "kinesiology", "exercise science",
                            "nutrition", "physiology", "anatomy"],
    "medicine":            ["medicine", "clinical", "medical", "surgery"],
    "nursing":             ["nursing", "patient care"],
    "pharmacy":            ["pharmacy", "pharmaceutical", "pharmacology"],
    # Law
    "law":                 ["law", "legal", "llb", "corporate law", "litigation", "compliance"],
    # Social Sciences
    "economics":           ["economics", "econometrics", "economic policy"],
    "psychology":          ["psychology", "behavioral", "counseling"],
    "sociology":           ["sociology", "social work"],
    "communication":       ["communication", "journalism", "media", "mass communication"],
    "education_field":     ["education", "teaching", "pedagogy", "curriculum"],
    # Design
    "design":              ["design", "graphic design", "ux", "ui", "product design"],
    "architecture":        ["architecture", "urban planning"],
    # Statistics & Math
    "statistics":          ["statistics", "statistical", "biostatistics", "quantitative",
                            "mathematics", "math", "actuarial"],
    # Agriculture & Environment
    "agriculture":         ["agriculture", "agronomy", "horticulture"],
    "environment":         ["environmental", "ecology", "sustainability"],
}


# ----------------------------
# CERT CATEGORY → JD RELEVANCE KEYWORDS
# BUG 4 FIX: replaces full-name substring match with category keyword matching.
# ----------------------------
CERT_RELEVANCE_MAP = {
    "DATA/AI":             ["data", "analytics", "machine learning", "ai", "python",
                            "sql", "tableau", "power bi", "analysis", "visualization"],
    "CLOUD":               ["cloud", "aws", "azure", "gcp", "devops", "infrastructure"],
    "TECH":                ["software", "programming", "developer", "engineering", "python",
                            "java", "sql", "coding"],
    "PROJECT MANAGEMENT":  ["project", "management", "agile", "scrum", "pmp", "delivery"],
    "NETWORKING/SECURITY": ["network", "security", "cyber", "infrastructure", "firewall"],
    "FINANCE":             ["finance", "financial", "investment", "banking", "accounting", "cfa"],
    "HR":                  ["hr", "human resources", "talent", "recruitment", "payroll"],
    "MARKETING":           ["marketing", "digital", "seo", "brand", "content", "social media"],
    "GENERAL":             [],
}

# Prestige issuers: add a small bonus for recognised cert providers
PRESTIGE_ISSUERS = {
    "coursera", "google", "microsoft", "aws", "ibm", "mit", "harvard",
    "stanford", "johns hopkins", "ahima", "nptel", "linkedin", "udemy", "edx",
}


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def clean(x):
    if isinstance(x, list):
        return " ".join([str(i) for i in x if i]).lower().strip()
    if isinstance(x, str):
        return x.lower().strip()
    return ""


def _kw_in_text(keywords, text):
    """Return True if ANY keyword appears in text (word-boundary aware)."""
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            return True
    return False


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
# JD DEGREE REQUIREMENT
# BUG 1 FIX (part): detects PG/UG/PHD/DIPLOMA from JD text.
# ----------------------------
def extract_jd_level(jd_text):
    """
    Return the minimum degree level the JD requires:
    'PHD', 'PG', 'UG', 'DIPLOMA', or None.
    Uses word-boundary matching to avoid false positives.
    """
    t = jd_text.lower()

    if re.search(r"\b(?:ph\.?d|doctorate|doctoral)\b", t):
        return "PHD"

    if re.search(
        r"\b(?:master|postgraduate|post.graduate|m\.tech|mtech|m\.sc|msc|"
        r"mba|pgdm|m\.e|ms\b|m\.s|ma\b|m\.a|mca|llm|graduate\s+degree)\b", t
    ):
        return "PG"

    if re.search(
        r"\b(?:bachelor|undergraduate|b\.tech|btech|b\.sc|bsc|b\.e\b|be\b|"
        r"b\.com|bcom|bca|ba\b|b\.a|bs\b|b\.s|llb|mbbs|college\s+degree|"
        r"4.year\s+degree|under.graduate|ug\s+degree)\b", t
    ):
        return "UG"

    if re.search(r"\b(?:diploma|polytechnic|iti|certificate\s+program)\b", t):
        return "DIPLOMA"

    return None


# ----------------------------
# JD MATCHER
# BUG 6 FIX: also uses education degree/field tokens for matching,
#            not just skills (which were too generic).
# ----------------------------
def find_best_jd(resume_json, jd_list):

    # Build resume context from multiple fields
    skills_text = clean(" ".join(resume_json.get("skills", [])[:10]))
    role_text   = clean(
        resume_json.get("job_title",    "") + " " +
        resume_json.get("target_role",  "") + " " +
        resume_json.get("desired_role", "")
    )
    # Also pull education degree/field if present in sectioned JSON
    edu_text = ""
    for edu_item in resume_json.get("education", []):
        edu_text += " " + str(edu_item)
    edu_text = clean(edu_text)

    resume_context = (role_text + " " + edu_text + " " + skills_text).strip()
    if not resume_context:
        resume_context = skills_text

    best_jd    = jd_list[0]
    best_score = 0.0

    for jd_name, jd_json in jd_list:

        jd_title = clean([
            jd_json.get("title",     ""),
            jd_json.get("job_title", ""),
            jd_json.get("role",      "")
        ])
        jd_full = get_jd_text(jd_json)

        # Token overlap: resume context vs JD title
        r_tokens = set(resume_context.split())
        j_tokens = set(jd_title.split())
        overlap  = len(r_tokens & j_tokens) / len(j_tokens) if j_tokens else 0

        # Sequence similarity on short titles
        seq_score = SequenceMatcher(None, resume_context[:200], jd_title).ratio()

        # Domain match: check if any field domain keywords appear in both
        domain_score = 0.0
        for domain, keywords in FIELD_DOMAIN_MAP.items():
            in_resume = any(re.search(r"\b" + re.escape(k) + r"\b", resume_context) for k in keywords)
            in_jd     = any(re.search(r"\b" + re.escape(k) + r"\b", jd_full)       for k in keywords)
            if in_resume and in_jd:
                domain_score = max(domain_score, 0.6)

        combined = max(overlap, seq_score, domain_score)

        if combined > best_score:
            best_score = combined
            best_jd    = (jd_name, jd_json)

    return best_jd


# ═══════════════════════════════════════════════════════════════
# SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════════

# ----------------------------
# CERT PROCESSING
# BUG 4 FIX: cert matching now uses category keyword map
#            instead of full-name substring lookup.
# ----------------------------
def process_certifications(cert_list, jd_text):

    processed = []
    match_sum = 0.0

    for c in cert_list:
        name     = c.get("name", "")
        category = c.get("category", "GENERAL")
        issuer   = c.get("issuer",   "").lower()

        if not name:
            continue

        processed.append({
            "name":   name,
            "issuer": c.get("issuer", ""),
            "year":   c.get("year",   "")
        })

        cert_score = 0.0

        # Tier 1: category keyword match in JD
        rel_kws = CERT_RELEVANCE_MAP.get(category, [])
        if rel_kws and _kw_in_text(rel_kws, jd_text):
            cert_score = max(cert_score, 0.80)

        # Tier 2: cert name word overlap with JD
        cert_words = [w for w in name.lower().split()
                      if len(w) >= 4 and w not in {"with", "from", "that", "this"}]
        if cert_words:
            hits   = sum(1 for w in cert_words if re.search(r"\b" + re.escape(w) + r"\b", jd_text))
            tier2  = (hits / len(cert_words)) * 0.70
            cert_score = max(cert_score, tier2)

        # Tier 3: prestige issuer bonus
        if any(p in issuer for p in PRESTIGE_ISSUERS):
            cert_score = min(cert_score + 0.10, 1.0)

        match_sum += cert_score

    cert_score_pct = (match_sum / len(processed)) * 100 if processed else 0.0
    return processed, round(cert_score_pct, 2)


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
# DEGREE SCORE
# BUG 1 + 7 + 8 FIX:
#   • Level-hierarchy match instead of similarity(abbrev, long_jd)
#   • Word-boundary JD boost instead of substring `in`
#   • Full DEGREE_WEIGHT table covering all abbreviations
# ----------------------------
def calculate_degree_score(education, jd_text):

    if not education:
        return 0.0

    jd_level = extract_jd_level(jd_text)
    best     = 0.0

    for e in education:
        degree  = e.get("degree", "").strip().upper()
        if not degree or degree == "UNKNOWN":
            continue

        prestige    = DEGREE_WEIGHT.get(degree, 0.62)
        cand_level  = DEGREE_LEVEL.get(degree, "UG")
        level_scores = LEVEL_MATCH_SCORE.get(jd_level, LEVEL_MATCH_SCORE[None])
        level_match  = level_scores.get(cand_level, 0.5)

        score = level_match * prestige * 100

        # BUG 8 FIX: word-boundary boost when JD explicitly names this degree
        deg_lower = degree.lower().replace(".", r"\.")
        if re.search(r"\b" + deg_lower + r"\b", jd_text):
            score = min(100.0, score * 1.10)

        best = max(best, score)

    return round(best, 2)


# ----------------------------
# FIELD SCORE
# BUG 2 + 3 FIX:
#   • Domain synonym map replaces bare token overlap
#   • Weight corrected to 0.30 (was 0.40)
# ----------------------------
def calculate_field_score(education, jd_text):

    if not education:
        return 0.0

    best = 0.0

    for e in education:
        field = e.get("field", "").strip()
        if not field or field.lower() == "unknown":
            continue

        field_lower = field.lower()
        score       = 0.0

        # Domain map: strong match if field domain keywords appear in JD too
        for domain, keywords in FIELD_DOMAIN_MAP.items():
            field_hit = any(kw in field_lower for kw in keywords)
            jd_hit    = _kw_in_text(keywords, jd_text)
            if field_hit and jd_hit:
                score = max(score, 1.0)   # full score
            elif field_hit:
                score = max(score, 0.25)  # candidate has field, JD doesn't need it

        # Fallback: word-level overlap (handles uncommon fields)
        if score == 0.0:
            field_tokens = set(re.findall(r"\b[a-z]{3,}\b", field_lower))
            stop_words   = {"and", "the", "for", "with", "from"}
            field_tokens -= stop_words
            if field_tokens:
                hits  = sum(1 for t in field_tokens
                            if re.search(r"\b" + re.escape(t) + r"\b", jd_text))
                score = hits / len(field_tokens)

        best = max(best, score)

    return round(best * 100, 2)


# ----------------------------
# EDUCATION RELEVANCE  (final weighted score)
# BUG 3 FIX: rebalanced weights — degree 0.40, field 0.30, cert 0.30
# ----------------------------
def calculate_education_relevance(education, certifications, jd_text,
                                   precomputed_cert_score=None):
    """
    precomputed_cert_score: if provided (from process_certifications),
    use it directly instead of recomputing with a simpler heuristic.
    """
    if not education:
        return 0.0

    degree_score = calculate_degree_score(education, jd_text)
    field_score  = calculate_field_score(education, jd_text)

    if precomputed_cert_score is not None:
        cert_score = precomputed_cert_score
    else:
        # Fallback: keyword-based cert scoring (same as process_certifications tier 1+2)
        match_sum = 0.0
        for c in certifications:
            cs   = 0.0
            kws  = CERT_RELEVANCE_MAP.get(c.get("category","GENERAL"), [])
            if kws and _kw_in_text(kws, jd_text):
                cs = max(cs, 0.80)
            words = [w for w in c.get("name","").lower().split() if len(w) >= 4]
            if words:
                hits = sum(1 for w in words if re.search(r"\b"+re.escape(w)+r"\b", jd_text))
                cs   = max(cs, (hits/len(words))*0.70)
            match_sum += cs
        cert_score = (match_sum / len(certifications)) * 100 if certifications else 0.0

    score = (
        degree_score * 0.40 +
        field_score  * 0.30 +
        cert_score   * 0.30
    )

    return round(score, 2)


# ═══════════════════════════════════════════════════════════════
# CORE PIPELINE
# ═══════════════════════════════════════════════════════════════

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
    # BUG 4 FIX: keyword-based cert scoring
    # ----------------------------
    cert_processed, cert_score = process_certifications(certifications, jd_text)

    # ----------------------------
    # EDUCATION STRENGTH
    # BUG 5 FIX: recency thresholds relaxed — a 7-year-old degree
    #            is still relevant (80), not "stale" (60).
    # ----------------------------
    latest_year = extract_latest_year(education)

    DEGREE_STRENGTH = {
        "PHD": 100, "MD": 100, "MDS": 95,
        "MBA": 90,  "EXECUTIVE MBA": 90, "MBA (IIM)": 92,
        "PGDM": 88, "PGDBM": 85, "PGDCA": 80, "PG DIPLOMA": 75,
        "M.TECH": 87, "M.E": 85, "MSC": 82, "MS": 82,
        "MA": 78, "M.COM": 78, "MCA": 80, "LLM": 78,
        "M.ED": 72, "M.PHIL": 78, "M.ARCH": 80,
        "M.PHARM": 80, "M.LIB": 72,
        "CA": 85, "CMA": 80, "CFA": 85, "CS": 78,
        "B.TECH": 75, "B.E": 75, "BSC": 70, "BS": 70,
        "BBA": 68, "BA": 65, "B.COM": 65,
        "BCA": 70, "LLB": 68, "MBBS": 82, "BDS": 75,
        "B.PHARM": 70, "BSC NURSING": 70, "B.ED": 65,
        "BBA LLB": 70, "BA LLB": 68,
        "DIPLOMA": 55, "ADVANCED DIPLOMA": 58,
        "POLYTECHNIC": 52, "ITI": 45,
        "HSC": 40, "SSC": 30,
    }

    degree_strength = DEGREE_STRENGTH.get(degree, 50)

    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        gap = datetime.now().year - int(latest_year)
        # BUG 5 FIX: relaxed thresholds
        recency_score = (
            100 if gap <= 2  else
             85 if gap <= 5  else
             70 if gap <= 8  else
             60 if gap <= 12 else
             45
        )

    education_strength = round(
        degree_strength * 0.40 +
        recency_score   * 0.30 +
        cert_score      * 0.20 +
        60              * 0.10,
        2
    )

    # ----------------------------
    # RELEVANCE
    # ----------------------------
    relevance_score = calculate_education_relevance(
        education,
        cert_processed,
        jd_text,
        precomputed_cert_score=cert_score
    )

    # ----------------------------
    # OUTPUT
    # ----------------------------
    return {
        "education_data": {
            "academic_profile": {
                "highest_degree":         degree,
                "total_degrees":          len(education),
                "certification_count":    len(cert_processed),
                "latest_graduation_year": latest_year,
                "education_strength":     education_strength
            },
            "education_details": education,
            "certifications":    cert_processed
        },
        "education_relevance_score": relevance_score
    }


# ═══════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════

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