from difflib import SequenceMatcher


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

# ----------------------------
# DEGREE PRESTIGE WEIGHT
# Higher = stronger academic signal
# Covers every abbreviation the parser can emit
# ----------------------------
DEGREE_WEIGHT = {
    # Doctoral
    "PHD":          1.00,
    "MD":           1.00,
    "MDS":          0.95,
    # Postgraduate
    "MBA":          0.90,
    "EXECUTIVE MBA":0.90,
    "MBA (IIM)":    0.92,
    "M.TECH":       0.87,
    "M.E":          0.85,
    "MSC":          0.82,
    "MS":           0.82,
    "MA":           0.78,
    "M.COM":        0.78,
    "MCA":          0.80,
    "LLM":          0.80,
    "M.ED":         0.75,
    "M.PHIL":       0.78,
    "M.ARCH":       0.80,
    "M.PLAN":       0.78,
    "M.PHARM":      0.80,
    "M.LIB":        0.72,
    "PGDM":         0.85,
    "PGDBM":        0.82,
    "PGDCA":        0.78,
    "PG DIPLOMA":   0.75,
    "CMA":          0.80,
    "CA":           0.82,
    "CFA":          0.82,
    "CS":           0.78,
    "FRM":          0.80,
    "ACTUARIAL":    0.82,
    # Undergraduate
    "B.TECH":       0.75,
    "B.E":          0.75,
    "BSC":          0.70,
    "BS":           0.70,
    "BCA":          0.70,
    "BBA":          0.68,
    "BA":           0.65,
    "B.COM":        0.65,
    "LLB":          0.68,
    "MBBS":         0.80,
    "BDS":          0.75,
    "B.PHARM":      0.70,
    "B.ARCH":       0.70,
    "B.ED":         0.65,
    "B.DES":        0.68,
    "BFA":          0.65,
    "BHM":          0.65,
    "BSC NURSING":  0.70,
    "BBA LLB":      0.70,
    "BA LLB":       0.68,
    # Diploma / School
    "DIPLOMA":      0.55,
    "ADVANCED DIPLOMA": 0.58,
    "POLYTECHNIC":  0.52,
    "ITI":          0.45,
    "HSC":          0.40,
    "SSC":          0.35,
}


# ----------------------------
# DEGREE → LEVEL MAP
# Used to match a candidate's degree level against JD requirements.
# Levels: PHD > PG > UG > DIPLOMA > SCHOOL
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
    "CMA": "PG", "CA": "PG", "CFA": "PG", "CS": "PG",
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

# Level compatibility matrix:
# Given the JD requirement, which candidate levels satisfy it and at what score?
#   key   = JD requirement level
#   value = dict of candidate_level → match_score (0.0-1.0)
LEVEL_MATCH_SCORE = {
    "PHD":     {"PHD": 1.0, "PG": 0.6,  "UG": 0.3,  "DIPLOMA": 0.1,  "SCHOOL": 0.0},
    "PG":      {"PHD": 1.0, "PG": 1.0,  "UG": 0.5,  "DIPLOMA": 0.2,  "SCHOOL": 0.0},
    "UG":      {"PHD": 1.0, "PG": 1.0,  "UG": 1.0,  "DIPLOMA": 0.4,  "SCHOOL": 0.1},
    "DIPLOMA": {"PHD": 1.0, "PG": 1.0,  "UG": 1.0,  "DIPLOMA": 1.0,  "SCHOOL": 0.3},
    "SCHOOL":  {"PHD": 1.0, "PG": 1.0,  "UG": 1.0,  "DIPLOMA": 1.0,  "SCHOOL": 1.0},
    None:      {"PHD": 0.9, "PG": 0.8,  "UG": 0.7,  "DIPLOMA": 0.5,  "SCHOOL": 0.3},
}


# ----------------------------
# FIELD DOMAIN MAP  (expanded)
# Each domain maps to keywords to look for in the candidate's field
# AND in the JD text.  Match = keyword in field AND keyword in JD.
# ----------------------------
FIELD_DOMAIN_MAP = {
    # Technology & CS
    "computer_science":    ["computer science", "cs", "software", "information technology", "it", "computing"],
    "data_science":        ["data science", "data analytics", "analytics", "machine learning", "ai", "artificial intelligence", "deep learning", "nlp"],
    "electronics":         ["electronics", "ece", "embedded", "vlsi", "signal processing", "telecommunication"],
    "electrical":          ["electrical", "power systems", "electrical engineering"],
    "mechanical":          ["mechanical", "manufacturing", "production", "automobile"],
    "civil":               ["civil", "structural", "construction"],
    "chemical":            ["chemical", "process engineering"],
    "biotechnology":       ["biotechnology", "biotech", "genetic", "genomics"],
    "cyber_security":      ["cyber security", "cybersecurity", "information security", "network security"],
    # Business & Management
    "business":            ["business", "management", "administration", "mba"],
    "finance":             ["finance", "financial", "accounting", "investment", "banking", "wealth", "cfa", "frm"],
    "marketing":           ["marketing", "brand", "digital marketing", "seo", "advertising"],
    "hr":                  ["human resources", "hr", "talent", "recruitment", "shrm", "payroll"],
    "operations":          ["operations", "supply chain", "logistics", "scm"],
    "entrepreneurship":    ["entrepreneurship", "startup", "venture"],
    # Health & Life Sciences
    "health_informatics":  ["health informatics", "health information", "healthcare informatics", "medical informatics", "clinical informatics"],
    "public_health":       ["public health", "epidemiology", "community health", "health policy"],
    "biological_sciences": ["biology", "biological sciences", "life sciences", "biosciences", "biochemistry", "microbiology", "genetics"],
    "health_sciences":     ["health sciences", "health science", "kinesiology", "exercise science", "nutrition", "physiology"],
    "medicine":            ["medicine", "clinical", "mbbs", "surgery", "medical"],
    "nursing":             ["nursing", "patient care", "clinical care"],
    "pharmacy":            ["pharmacy", "pharmaceutical", "drug", "pharmacology"],
    # Law
    "law":                 ["law", "legal", "llb", "corporate law", "litigation", "compliance"],
    # Social Sciences & Humanities
    "economics":           ["economics", "econometrics", "economic policy"],
    "psychology":          ["psychology", "behavioral", "counseling"],
    "sociology":           ["sociology", "social work", "social sciences"],
    "communication":       ["communication", "journalism", "media", "mass communication"],
    "education":           ["education", "teaching", "pedagogy", "curriculum"],
    # Design & Architecture
    "design":              ["design", "graphic design", "ux", "ui", "product design", "fashion design"],
    "architecture":        ["architecture", "urban planning", "landscape"],
    # Agriculture & Environment
    "agriculture":         ["agriculture", "agronomy", "horticulture", "farming"],
    "environment":         ["environmental", "ecology", "sustainability", "climate"],
    # Statistics & Math
    "statistics":          ["statistics", "statistical", "biostatistics", "quantitative", "mathematics", "math"],
}

# Certification relevance keywords:
# Maps cert category → JD keywords that indicate the cert is relevant
CERT_RELEVANCE_MAP = {
    "DATA/AI":              ["data", "analytics", "machine learning", "ai", "python", "sql", "tableau", "power bi", "analysis"],
    "CLOUD":                ["cloud", "aws", "azure", "gcp", "devops", "infrastructure"],
    "TECH":                 ["software", "programming", "developer", "engineering", "python", "java", "sql"],
    "PROJECT MANAGEMENT":   ["project", "management", "agile", "scrum", "pmp", "delivery"],
    "NETWORKING/SECURITY":  ["network", "security", "cyber", "infrastructure"],
    "FINANCE":              ["finance", "financial", "investment", "banking", "accounting"],
    "HR":                   ["hr", "human resources", "talent", "recruitment"],
    "MARKETING":            ["marketing", "digital", "seo", "brand", "content"],
    "GENERAL":              [],
}


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def similarity(a, b):
    """
    Character-level SequenceMatcher ratio.
    NOTE: Only reliable when both strings are SHORT and similar length.
    Do NOT use this to compare a short phrase against a long JD text.
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _keywords_in_text(keywords, text):
    """Return True if ANY keyword from the list appears in text."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def extract_jd_degree_requirement(jd_text):
    """
    Detect the minimum degree level the JD requires.
    Returns one of: 'PHD', 'PG', 'UG', 'DIPLOMA', 'SCHOOL', or None.

    BUG FIX: original only checked 3 strings.
    Now checks all common abbreviations and phrasings.
    """
    t = jd_text.lower()

    # Doctoral
    if any(k in t for k in ["ph.d", "phd", "doctorate", "doctoral"]):
        return "PHD"

    # Postgraduate — check before UG because "master" contains "master"
    if any(k in t for k in [
        "master", "postgraduate", "post-graduate", "post graduate",
        "m.tech", "mtech", "m.sc", "msc", "mba", "pgdm", "m.e",
        "ms ", "m.s", "ma ", "m.a", "mca", "llm", "pg degree",
        "graduate degree",   # US usage: "graduate" often means PG
    ]):
        return "PG"

    # Undergraduate
    if any(k in t for k in [
        "bachelor", "undergraduate", "b.tech", "btech", "b.sc", "bsc",
        "b.e", "be ", "b.com", "bcom", "bca", "ba ", "b.a", "bs ",
        "b.s", "llb", "mbbs", "under graduate", "ug degree",
        "college degree", "4-year degree", "4 year degree",
    ]):
        return "UG"

    # Diploma
    if any(k in t for k in ["diploma", "polytechnic", "iti", "certificate program"]):
        return "DIPLOMA"

    return None


def get_degree_level(degree):
    """Return the DEGREE_LEVEL category for a parsed degree string."""
    return DEGREE_LEVEL.get(degree.upper(), "UG")  # default UG if unknown


def score_degree_level_match(candidate_degree, jd_level):
    """
    BUG FIX: old code did similarity(degree_abbrev, long_jd_text) → always ~0.
    New code: look up the candidate's level and compare against JD requirement.
    Returns a 0.0–1.0 score.
    """
    cand_level = get_degree_level(candidate_degree)
    level_scores = LEVEL_MATCH_SCORE.get(jd_level, LEVEL_MATCH_SCORE[None])
    return level_scores.get(cand_level, 0.5)


def detect_field_match(field, jd_text):
    """
    BUG FIX: old code used similarity(field, long_jd_text) → always near 0.
    New code:
      1. Find which domain(s) the candidate's field belongs to.
      2. Check whether any of that domain's keywords appear in the JD.
      3. If yes → strong match (1.0).
      4. If the domain appears in the field but not the JD → partial (0.3).
      5. Fall back to word-level overlap as last resort.
    """
    field_lower = field.lower()
    jd_lower    = jd_text.lower()

    best_score = 0.0

    for domain, keywords in FIELD_DOMAIN_MAP.items():
        field_hit = any(kw in field_lower for kw in keywords)
        jd_hit    = any(kw in jd_lower    for kw in keywords)

        if field_hit and jd_hit:
            best_score = max(best_score, 1.0)   # strong match
        elif field_hit:
            best_score = max(best_score, 0.30)  # candidate has the field but JD doesn't need it

    if best_score > 0:
        return best_score

    # Last resort: word-level overlap between field tokens and JD tokens
    field_words = set(field_lower.split())
    jd_words    = set(jd_lower.split())
    overlap     = field_words & jd_words
    # Remove stop words
    stop = {"in", "of", "and", "the", "a", "an", "for", "or", "with", "&"}
    meaningful = overlap - stop
    if field_words - stop:
        return len(meaningful) / len(field_words - stop)

    return 0.0


def score_certifications(certifications, jd_text):
    """
    BUG FIX: old code used similarity(cert_name, long_jd_text) → always ~0.24.
    New approach (3 tiers):
      Tier 1 — cert CATEGORY matches JD keywords (uses CERT_RELEVANCE_MAP)
      Tier 2 — individual cert name keywords appear in JD
      Tier 3 — cert name words overlap with JD words
    Each matched cert contributes to a normalised 0–100 score.
    """
    if not certifications:
        return 0.0

    jd_lower   = jd_text.lower()
    total      = len(certifications)
    match_sum  = 0.0

    for cert in certifications:
        cert_name     = cert.get("name", "").lower()
        cert_category = cert.get("category", "GENERAL")
        cert_score    = 0.0

        # Tier 1: category-level match
        relevance_kws = CERT_RELEVANCE_MAP.get(cert_category, [])
        if relevance_kws and _keywords_in_text(relevance_kws, jd_lower):
            cert_score = max(cert_score, 0.80)

        # Tier 2: cert name keywords in JD
        # Extract meaningful words (≥4 chars) from cert name
        cert_words = [w for w in cert_name.split() if len(w) >= 4
                      and w not in {"with", "from", "that", "this", "have", "your"}]
        if cert_words:
            hits = sum(1 for w in cert_words if w in jd_lower)
            tier2 = hits / len(cert_words)
            cert_score = max(cert_score, tier2 * 0.70)

        # Tier 3: issuer prestige bonus (well-known issuers signal quality)
        issuer = cert.get("issuer", "").lower()
        prestige_issuers = [
            "coursera", "google", "microsoft", "aws", "ibm", "mit",
            "harvard", "stanford", "johns hopkins", "ahima", "ahrq",
            "nptel", "linkedin", "udemy", "edx",
        ]
        if any(p in issuer for p in prestige_issuers):
            cert_score = min(cert_score + 0.10, 1.0)

        match_sum += cert_score

    return (match_sum / total) * 100


# ═══════════════════════════════════════════════════════════════
# MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════

def calculate_education_relevance(education_data, jd_text):
    """
    Calculate how well a candidate's education matches a job description.

    Returns a float score 0–100.

    Components:
        Degree score  (40%) — level match + prestige weight
        Field score   (30%) — domain keyword matching
        Cert score    (30%) — category + keyword matching

    Fixes applied vs. original:
        • Degree scoring: level-based match instead of similarity(abbrev, long_jd)
        • Degree level map covers all abbreviations (BS→UG, MBA→PG, etc.)
        • Level boost: PHD/PG/UG compared by level hierarchy, not string contains
        • Field matching: domain keyword map instead of similarity(field, long_jd)
        • Cert scoring: 3-tier keyword approach instead of similarity threshold
        • JD degree extraction: catches all common phrasings and abbreviations
    """

    jd_text_lower = jd_text.lower()
    jd_level      = extract_jd_degree_requirement(jd_text)

    education_list = education_data.get("education_details", [])
    certifications = education_data.get("certifications", [])


    # ─────────────────────────────────────────────────────────
    # 1. DEGREE SCORE  (40%)
    #    Best-degree-wins: take the highest scoring degree.
    #    Score = level_match_score × prestige_weight × 100
    # ─────────────────────────────────────────────────────────
    degree_score = 0.0

    for edu in education_list:
        degree = edu.get("degree", "").strip().upper()
        if not degree or degree == "UNKNOWN":
            continue

        prestige     = DEGREE_WEIGHT.get(degree, 0.62)      # default mid-range
        level_match  = score_degree_level_match(degree, jd_level)

        # Combined: level match determines the ceiling; prestige scales within it
        score = level_match * prestige

        degree_score = max(degree_score, score)

    degree_score = min(degree_score, 1.0) * 100


    # ─────────────────────────────────────────────────────────
    # 2. FIELD SCORE  (30%)
    #    Best-field-wins across all listed degrees.
    # ─────────────────────────────────────────────────────────
    field_score = 0.0

    for edu in education_list:
        field = edu.get("field", "").strip()
        if not field or field.lower() in ("", "unknown"):
            continue

        score = detect_field_match(field, jd_text)
        field_score = max(field_score, score)

    field_score = field_score * 100


    # ─────────────────────────────────────────────────────────
    # 3. CERTIFICATION SCORE  (30%)
    # ─────────────────────────────────────────────────────────
    cert_score = score_certifications(certifications, jd_text)


    # ─────────────────────────────────────────────────────────
    # FINAL WEIGHTED SCORE
    # ─────────────────────────────────────────────────────────
    final_score = (
        degree_score * 0.40 +
        field_score  * 0.30 +
        cert_score   * 0.30
    )

    return round(final_score, 2)