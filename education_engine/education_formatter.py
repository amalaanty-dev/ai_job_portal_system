"""
education_formatter.py
──────────────────────
Formats parsed education data into a structured academic profile.

Fixes applied vs. original:
  BUG 1 – calculate_education_relevance() replaced broken similarity()
           scorer with domain-keyword matching (same approach as pipeline).
  BUG 2 – calculate_strength() recency thresholds now 4-tier (added gap<=8→70)
           so 6-8 year old degrees are not penalised like stale ones.
  BUG 3 – calculate_strength() weights rebalanced:
           degree*0.40 + cert*0.20 + recency*0.30 + base*0.10
           (was degree*0.50 — over-weighted; base_score added to match pipeline)
  BUG 4 – CERT_RELEVANCE_MAP: added missing HEALTHCARE category
           so RHIT / CMAA / billing certs score correctly for medical JDs.
  BUG 5 – DEGREE_SCORE_MAP expanded from 9 to 50+ entries (all parser labels).
  BUG 6 – DEGREE_PRIORITY expanded from 9 to 50+ entries (all parser labels).
"""

import re
from datetime import datetime
from difflib import SequenceMatcher


# ═══════════════════════════════════════════════════════════════
# DEGREE PRIORITY  (1 = highest)
# BUG 6 FIX: was only 9 entries; now covers every label the parser emits.
# ═══════════════════════════════════════════════════════════════
DEGREE_PRIORITY = {
    # Doctoral
    "PHD":              1,
    "MD":               1,
    "MDS":              2,
    # Postgraduate
    "MBA":              3,
    "EXECUTIVE MBA":    3,
    "MBA (IIM)":        3,
    "PGDM":             4,
    "PGDBM":            4,
    "PGDCA":            5,
    "PG DIPLOMA":       5,
    "M.TECH":           4,
    "M.E":              4,
    "MSC":              5,
    "MS":               5,
    "MA":               6,
    "M.COM":            6,
    "MCA":              5,
    "LLM":              5,
    "M.ED":             6,
    "M.PHIL":           5,
    "M.ARCH":           5,
    "M.PLAN":           6,
    "M.PHARM":          5,
    "M.LIB":            6,
    "CA":               4,
    "CMA":              5,
    "CFA":              4,
    "CS":               6,
    "FRM":              5,
    "ACTUARIAL":        4,
    "CMA INTER":        7,
    "CA INTER":         7,
    "CA FINAL":         4,
    "CS INTER":         7,
    "CS FINAL":         5,
    # Undergraduate
    "B.TECH":           8,
    "B.E":              8,
    "BSC":              9,
    "BS":               9,
    "BCA":              9,
    "BBA":              10,
    "BA":               11,
    "B.COM":            10,
    "LLB":              10,
    "MBBS":             8,
    "BDS":              9,
    "BHMS":             9,
    "BAMS":             9,
    "B.PHARM":          9,
    "PHARM.D":          8,
    "B.ARCH":           9,
    "B.PLAN":           10,
    "B.ED":             10,
    "B.LIB":            11,
    "BHM":              10,
    "BNYS":             10,
    "B.DES":            10,
    "BFA":              11,
    "BSC NURSING":      9,
    "BBA LLB":          9,
    "BA LLB":           10,
    # Diploma / School
    "ADVANCED DIPLOMA": 12,
    "DIPLOMA":          13,
    "POLYTECHNIC":      14,
    "ITI":              15,
    "HSC":              16,
    "SSC":              17,
}


# ═══════════════════════════════════════════════════════════════
# DEGREE SCORE MAP  (for education_strength)
# BUG 5 FIX: was 9 entries; now covers every label the parser emits.
#            Missing entries defaulted to 50 — now explicit values.
# ═══════════════════════════════════════════════════════════════
DEGREE_SCORE_MAP = {
    # Doctoral
    "PHD":              100,
    "MD":               100,
    "MDS":               95,
    # Postgraduate
    "MBA":               90,
    "EXECUTIVE MBA":     90,
    "MBA (IIM)":         92,
    "PGDM":              88,
    "PGDBM":             85,
    "PGDCA":             80,
    "PG DIPLOMA":        75,
    "M.TECH":            87,
    "M.E":               85,
    "MSC":               82,
    "MS":                82,
    "MA":                78,
    "M.COM":             78,
    "MCA":               80,
    "LLM":               78,
    "M.ED":              72,
    "M.PHIL":            78,
    "M.ARCH":            80,
    "M.PLAN":            78,
    "M.PHARM":           80,
    "M.LIB":             72,
    "CA":                85,
    "CA FINAL":          85,
    "CA INTER":          60,
    "CMA":               80,
    "CMA INTER":         58,
    "CFA":               85,
    "CS":                78,
    "CS FINAL":          78,
    "CS INTER":          58,
    "FRM":               80,
    "ACTUARIAL":         82,
    # Undergraduate
    "B.TECH":            75,
    "B.E":               75,
    "BSC":               70,
    "BS":                70,
    "BCA":               70,
    "BBA":               68,
    "BA":                65,
    "B.COM":             65,
    "LLB":               68,
    "MBBS":              82,
    "BDS":               75,
    "BHMS":              70,
    "BAMS":              70,
    "B.PHARM":           70,
    "PHARM.D":           75,
    "B.ARCH":            70,
    "B.PLAN":            65,
    "B.ED":              65,
    "B.LIB":             60,
    "BHM":               65,
    "BNYS":              65,
    "B.DES":             68,
    "BFA":               65,
    "BSC NURSING":       70,
    "BBA LLB":           70,
    "BA LLB":            68,
    # Diploma / School
    "ADVANCED DIPLOMA":  58,
    "DIPLOMA":           55,
    "POLYTECHNIC":       52,
    "ITI":               45,
    "HSC":               40,
    "SSC":               30,
}


# ═══════════════════════════════════════════════════════════════
# FIELD DOMAIN MAP
# BUG 1 FIX: replaces similarity(field, jd_text) with keyword matching.
# ═══════════════════════════════════════════════════════════════
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
    "biological_sciences": ["biology", "biological sciences", "biological", "life sciences", "biosciences",
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


# ═══════════════════════════════════════════════════════════════
# CERT CATEGORY → JD RELEVANCE KEYWORDS
# BUG 1 FIX: replaces similarity(cert_name, jd_text) with keyword map.
# BUG 4 FIX: added HEALTHCARE category — RHIT / CMAA / medical certs
#            were silently falling through to GENERAL (score=0).
# ═══════════════════════════════════════════════════════════════
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
    # BUG 4 FIX: HEALTHCARE was missing — parser emits it for RHIT / CMAA / billing certs
    "HEALTHCARE":          ["healthcare", "medical", "health", "clinical", "ehr", "hipaa",
                            "rhit", "cmaa", "billing", "coding", "icd", "cpt", "patient"],
    "GENERAL":             [],
}

PRESTIGE_ISSUERS = {
    "coursera", "google", "microsoft", "aws", "ibm", "mit", "harvard",
    "stanford", "johns hopkins", "ahima", "nha", "medtrainer",
    "nptel", "linkedin", "udemy", "edx",
}


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _kw_in_text(keywords, text):
    """Return True if ANY keyword appears in text (word-boundary aware)."""
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text):
            return True
    return False


def similarity(a, b):
    """Character-level SequenceMatcher ratio (kept for any callers that need it)."""
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()


# ═══════════════════════════════════════════════════════════════
# MAIN FORMATTER
# ═══════════════════════════════════════════════════════════════

def format_academic_profile(parsed, jd_text=""):

    edu  = parsed.get("education",      [])
    cert = parsed.get("certifications", [])

    latest_year = get_latest_year(edu)
    strength    = calculate_strength(edu, cert, latest_year)
    relevance   = calculate_education_relevance(edu, cert, jd_text)

    return {
        "education_data": {
            "academic_profile": {
                "highest_degree":         get_highest(edu),
                "total_degrees":          len(edu),
                "certification_count":    len(cert),
                "latest_graduation_year": latest_year,
                "education_strength":     strength
            },
            "education_details": edu,
            "certifications":    cert
        },
        "education_relevance_score": relevance
    }


# ═══════════════════════════════════════════════════════════════
# HIGHEST DEGREE
# BUG 6 FIX: uses expanded DEGREE_PRIORITY (was 9 entries → 50+)
# ═══════════════════════════════════════════════════════════════

def get_highest(edu_list):

    if not edu_list:
        return "UNKNOWN"

    sorted_edu = sorted(
        edu_list,
        key=lambda x: DEGREE_PRIORITY.get(x.get("degree", ""), 999)
    )

    return sorted_edu[0]["degree"]


# ═══════════════════════════════════════════════════════════════
# LATEST GRADUATION YEAR
# ═══════════════════════════════════════════════════════════════

def get_latest_year(edu_list):

    years = []

    for e in edu_list:
        y     = str(e.get("graduation_year", ""))
        found = re.findall(r"\b(?:19|20)\d{2}\b", y)
        if found:
            years.append(max(map(int, found)))

    return max(years) if years else "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# EDUCATION STRENGTH
# BUG 2 FIX: recency now 4-tier (added gap<=8→70); stale threshold at 12 yrs.
# BUG 3 FIX: weights rebalanced — degree*0.40 + recency*0.30 + cert*0.20 + base*0.10
# BUG 5 FIX: uses expanded DEGREE_SCORE_MAP (was 9 entries → 50+)
# ═══════════════════════════════════════════════════════════════

def calculate_strength(edu, cert, latest_year):

    # Degree Score
    highest      = get_highest(edu)
    degree_score = DEGREE_SCORE_MAP.get(highest, 50)

    # Certification Score
    cert_score = min(len(cert) * 20, 80)

    # Recency Score
    # BUG 2 FIX: 4 tiers instead of 2; a 6-8 yr gap gives 70, not 60
    if latest_year == "UNKNOWN":
        recency_score = 50
    else:
        gap = datetime.now().year - int(latest_year)
        recency_score = (
            100 if gap <= 2  else
             85 if gap <= 5  else
             70 if gap <= 8  else
             60 if gap <= 12 else
             45
        )

    # Final Weighted Score
    # BUG 3 FIX: degree 0.40 (was 0.50); base_score 0.10 added
    score = (
        degree_score  * 0.40 +
        recency_score * 0.30 +
        cert_score    * 0.20 +
        60            * 0.10     # base_score: reasonable floor for any graduate
    )

    return round(score, 2)


# ═══════════════════════════════════════════════════════════════
# EDUCATION RELEVANCE  (JD MATCH)
# BUG 1 FIX: replaced similarity(label, long_jd_text) with:
#   • Degree  – level-hierarchy + prestige weight
#   • Field   – domain keyword map (same as run_education_pipeline)
#   • Cert    – 3-tier category / name / issuer matching
# BUG 4 FIX: CERT_RELEVANCE_MAP now includes HEALTHCARE
# Weights: degree 0.40 + field 0.30 + cert 0.30
# ═══════════════════════════════════════════════════════════════

def calculate_education_relevance(edu_list, cert_list, jd_text):

    if not edu_list:
        return 0.0

    jd_lower = jd_text.lower()

    # ─────────────────────────────────────────────────────────
    # 1. DEGREE SCORE  (40%)
    # ─────────────────────────────────────────────────────────
    DEGREE_LEVEL = {
        "PHD": "PHD", "MD": "PHD", "MDS": "PHD",
        "MBA": "PG",  "EXECUTIVE MBA": "PG", "MBA (IIM)": "PG",
        "M.TECH": "PG", "M.E": "PG", "MSC": "PG", "MS": "PG",
        "MA": "PG",   "M.COM": "PG", "MCA": "PG", "LLM": "PG",
        "M.ED": "PG", "M.PHIL": "PG", "M.ARCH": "PG", "M.PLAN": "PG",
        "M.PHARM": "PG", "M.LIB": "PG", "PGDM": "PG", "PGDBM": "PG",
        "PGDCA": "PG", "PG DIPLOMA": "PG",
        "CA": "PG",   "CMA": "PG", "CFA": "PG", "CS": "PG",
        "FRM": "PG",  "ACTUARIAL": "PG",
        "B.TECH": "UG", "B.E": "UG", "BSC": "UG", "BS": "UG",
        "BCA": "UG",  "BBA": "UG", "BA": "UG", "B.COM": "UG",
        "LLB": "UG",  "MBBS": "UG", "BDS": "UG", "B.PHARM": "UG",
        "B.ARCH": "UG", "B.ED": "UG", "B.DES": "UG", "BFA": "UG",
        "BHM": "UG",  "BSC NURSING": "UG", "BBA LLB": "UG", "BA LLB": "UG",
        "DIPLOMA": "DIPLOMA", "ADVANCED DIPLOMA": "DIPLOMA",
        "POLYTECHNIC": "DIPLOMA", "ITI": "DIPLOMA",
        "HSC": "SCHOOL", "SSC": "SCHOOL",
    }

    LEVEL_MATCH_SCORE = {
        "PHD":     {"PHD": 1.0, "PG": 0.60, "UG": 0.30, "DIPLOMA": 0.10, "SCHOOL": 0.0},
        "PG":      {"PHD": 1.0, "PG": 1.00, "UG": 0.55, "DIPLOMA": 0.20, "SCHOOL": 0.0},
        "UG":      {"PHD": 1.0, "PG": 1.00, "UG": 1.00, "DIPLOMA": 0.40, "SCHOOL": 0.1},
        "DIPLOMA": {"PHD": 1.0, "PG": 1.00, "UG": 1.00, "DIPLOMA": 1.00, "SCHOOL": 0.3},
        "SCHOOL":  {"PHD": 1.0, "PG": 1.00, "UG": 1.00, "DIPLOMA": 1.00, "SCHOOL": 1.0},
        None:      {"PHD": 0.9, "PG": 0.80, "UG": 0.70, "DIPLOMA": 0.50, "SCHOOL": 0.3},
    }

    DEGREE_WEIGHT = {k: v / 100.0 for k, v in DEGREE_SCORE_MAP.items()}

    jd_level     = _extract_jd_level(jd_lower)
    degree_score = 0.0

    for e in edu_list:
        deg = e.get("degree", "").strip().upper()
        if not deg or deg == "UNKNOWN":
            continue
        prestige    = DEGREE_WEIGHT.get(deg, 0.62)
        cand_level  = DEGREE_LEVEL.get(deg, "UG")
        level_match = LEVEL_MATCH_SCORE.get(jd_level, LEVEL_MATCH_SCORE[None]).get(cand_level, 0.5)
        degree_score = max(degree_score, level_match * prestige)

    degree_score = round(min(degree_score, 1.0) * 100, 2)


    # ─────────────────────────────────────────────────────────
    # 2. FIELD SCORE  (30%)
    # ─────────────────────────────────────────────────────────
    field_score = 0.0

    for e in edu_list:
        field = e.get("field", "").strip()
        if not field or field.lower() == "unknown":
            continue

        field_lower = field.lower()
        score       = 0.0

        for domain, keywords in FIELD_DOMAIN_MAP.items():
            field_hit = any(kw in field_lower for kw in keywords)
            jd_hit    = _kw_in_text(keywords, jd_lower)
            if field_hit and jd_hit:
                score = max(score, 1.0)
            elif field_hit:
                score = max(score, 0.25)

        # Fallback: word-level overlap
        if score == 0.0:
            field_tokens = set(re.findall(r"\b[a-z]{3,}\b", field_lower))
            stop_words   = {"and", "the", "for", "with", "from"}
            field_tokens -= stop_words
            if field_tokens:
                hits  = sum(1 for t in field_tokens
                            if re.search(r"\b" + re.escape(t) + r"\b", jd_lower))
                score = hits / len(field_tokens)

        field_score = max(field_score, score)

    field_score = round(field_score * 100, 2)


    # ─────────────────────────────────────────────────────────
    # 3. CERTIFICATION SCORE  (30%)
    # BUG 4 FIX: HEALTHCARE category now in CERT_RELEVANCE_MAP
    # ─────────────────────────────────────────────────────────
    cert_score = 0.0

    if cert_list:
        match_sum = 0.0
        for c in cert_list:
            cert_name     = c.get("name",     "").lower()
            cert_category = c.get("category", "GENERAL")
            issuer        = c.get("issuer",   "").lower()
            cs            = 0.0

            # Tier 1: category keyword match
            rel_kws = CERT_RELEVANCE_MAP.get(cert_category, [])
            if rel_kws and _kw_in_text(rel_kws, jd_lower):
                cs = max(cs, 0.80)

            # Tier 2: cert name word overlap with JD
            cert_words = [w for w in cert_name.split()
                          if len(w) >= 4 and w not in {"with", "from", "that", "this"}]
            if cert_words:
                hits  = sum(1 for w in cert_words
                            if re.search(r"\b" + re.escape(w) + r"\b", jd_lower))
                cs    = max(cs, (hits / len(cert_words)) * 0.70)

            # Tier 3: prestige issuer bonus
            if any(p in issuer for p in PRESTIGE_ISSUERS):
                cs = min(cs + 0.10, 1.0)

            match_sum += cs

        cert_score = round((match_sum / len(cert_list)) * 100, 2)


    # ─────────────────────────────────────────────────────────
    # FINAL WEIGHTED SCORE
    # ─────────────────────────────────────────────────────────
    score = (
        degree_score * 0.40 +
        field_score  * 0.30 +
        cert_score   * 0.30
    )

    return round(score, 2)


# ═══════════════════════════════════════════════════════════════
# INTERNAL: JD LEVEL EXTRACTOR
# Detects minimum degree level required by the JD text.
# ═══════════════════════════════════════════════════════════════

def _extract_jd_level(jd_lower):
    """Return 'PHD', 'PG', 'UG', 'DIPLOMA', or None from JD text."""

    if re.search(r"\b(?:ph\.?d|doctorate|doctoral)\b", jd_lower):
        return "PHD"

    if re.search(
        r"\b(?:master|postgraduate|post.graduate|m\.tech|mtech|m\.sc|msc|"
        r"mba|pgdm|m\.e|ms\b|m\.s|ma\b|m\.a|mca|llm|graduate\s+degree)\b",
        jd_lower
    ):
        return "PG"

    if re.search(
        r"\b(?:bachelor|undergraduate|b\.tech|btech|b\.sc|bsc|b\.e\b|be\b|"
        r"b\.com|bcom|bca|ba\b|b\.a|bs\b|b\.s|llb|mbbs|college\s+degree|"
        r"4.year\s+degree|under.graduate|ug\s+degree)\b",
        jd_lower
    ):
        return "UG"

    if re.search(r"\b(?:diploma|polytechnic|iti|certificate\s+program)\b", jd_lower):
        return "DIPLOMA"

    return None