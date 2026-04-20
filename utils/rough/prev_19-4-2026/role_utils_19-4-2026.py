from typing import Dict, List
import re

# ── ROLE SYNONYMS ─────────────────────────────────────────────────────
ROLE_SYNONYMS: Dict[str, List[str]] = {
    # === Your original entries (untouched) ===
    "healthcare data analyst (junior)": [
        "junior healthcare data analyst", "jr healthcare data analyst",
        "entry level healthcare data analyst"
    ],
    "clinical data analyst": [
        "clinical analytics analyst", "clinical trial data analyst"
    ],
    "healthcare reporting analyst": [
        "healthcare report analyst", "reporting analyst healthcare"
    ],
    "medical data analyst": [
        "medical analytics analyst", "healthcare domain medical data"
    ],
    "health information analyst": [
        "health information data analyst", "health information systems analyst", "his analyst"
    ],
    "data entry analyst (healthcare)": ["healthcare data entry analyst"],
    "public health data analyst (entry-level)": ["entry level public health data analyst"],
    "ehr data analyst": ["electronic health record analyst", "ehr analytics specialist", "ehr analyst"],
    "healthcare data analyst": [
        "health data analyst", "healthcare analyst", "data analyst healthcare",
        "health analytics analyst", "healthcare data specialist", "healthcare data associate"
    ],
    "senior clinical data analyst": ["sr clinical data analyst"],
    "healthcare business analyst": ["healthcare ba", "business analyst healthcare"],
    "population health analyst": ["population health data analyst"],
    "quality improvement analyst (healthcare)": ["healthcare quality analyst"],
    "healthcare operations analyst": ["hospital operations analyst"],
    "revenue cycle data analyst": ["revenue cycle analyst", "rcm analyst"],
    "healthcare performance analyst": ["hospital performance analyst"],

    # === STRONG MAPPING FOR THE JD YOU SHARED ===
    "healthcare bi (business intelligence) analyst": [
        "healthcare bi analyst", "healthcare business intelligence analyst",
        "bi analyst healthcare", "healthcare bi (business intelligence) analyst",
        # Direct match from your parsed JD
        "data modeling", "etl", "power bi", "sql", "tableau",
        # Your resume title + common Data Engineer variants
        "data engineer", "big data engineer", "etl engineer", "data pipeline engineer",
        "cloud data engineer", "spark engineer", "etl developer", "analytics engineer",
        "data infrastructure engineer", "database engineer"
    ],

    # === Other common roles (kept for completeness) ===
    "claims data analyst": ["insurance claims analyst"],
    "senior healthcare data analyst": ["sr healthcare data analyst"],
    "lead data analyst (healthcare)": ["lead healthcare data analyst"],
    "healthcare analytics manager": ["manager healthcare analytics"],
    "healthcare data science manager": ["healthcare ds manager"],
    "director of healthcare analytics": ["healthcare analytics director"],
    "chief data officer": ["cdo"],
    "head of health informatics": ["health informatics head"],
    "healthcare data scientist": ["healthcare ai data scientist"],
    "clinical data scientist": ["clinical analytics scientist"],
    "healthcare machine learning engineer": ["ml engineer healthcare"],
    "ai specialist in healthcare analytics": ["healthcare ai engineer"],
    "predictive analytics specialist": ["predictive healthcare analyst"],
    "healthcare statistician": ["clinical statistician"],
    "biostatistician": ["bio statistician"],
    "clinical research data analyst": ["clinical research analyst"],
    "clinical trials data manager": ["clinical trial data manager"],
    "epidemiologist": ["public health epidemiologist"],
    "healthcare outcomes analyst": ["health outcomes analyst"],
    "real world evidence (rwe) analyst": ["rwe analyst"],
    "health informatics specialist": ["health informatics analyst"],
    "clinical informatics analyst": ["clinical informatics specialist"],
    "healthcare data integration specialist": [
        "health data integration analyst",
        "data engineer", "etl engineer", "data pipeline engineer",
        "cloud data engineer", "spark engineer"
    ],
    "ehr implementation analyst": ["ehr implementation specialist"],
    "healthcare data architect": ["health data architect"],
    "health information systems analyst": ["his analyst"],
    "healthcare financial analyst": ["healthcare finance analyst"],
    "medical billing data analyst": ["billing analytics analyst"],
    "insurance claims analyst": ["claims analytics analyst"],
    "cost & utilization analyst": ["cost utilization analyst"],
    "public health analyst": ["public health analytics analyst"],
    "health policy analyst": ["healthcare policy analyst"],
    "epidemiology data analyst": ["epidemiology analyst"],
    "healthcare program analyst": ["health program analyst"],
    "global health data analyst": ["global health analyst"],
    "digital health analyst": ["digital healthcare analyst"],
    "telehealth data analyst": ["telemedicine data analyst"],
    "healthcare ai analyst": ["ai healthcare analyst"],
    "patient experience analyst": ["patient satisfaction analyst"],
    "healthcare risk analyst": ["clinical risk analyst"],
    "fraud & compliance analyst": ["fraud compliance analyst"],
    "wearable health data analyst": ["wearable analytics analyst"],
    "genomics data analyst": ["genomic data analyst", "bioinformatics analyst"],
    "freelance healthcare data analyst": ["contract healthcare data analyst"],
    "healthcare analytics consultant": ["healthcare analytics advisor"],
    "data analytics trainer": ["analytics instructor"],
    "healthcare dashboard developer": ["healthcare bi dashboard developer"],
    "remote clinical data analyst": ["virtual clinical data analyst"],

    # === Standalone canonicals (safety net) ===
    "data engineer": [
        "data engineer", "big data engineer", "etl engineer", "data pipeline engineer",
        "cloud data engineer", "spark engineer", "etl developer", "analytics engineer",
        "data infrastructure engineer", "database engineer"
    ],
    "healthcare data engineer": [
        "healthcare etl engineer", "health data pipeline engineer",
        "medical data engineer", "clinical data engineer"
    ],
}


# ── FAST LOOKUP CACHE (NEW - performance fix) ─────────────────────────
_SYNONYM_LOOKUP = {}

for main_role, synonyms in ROLE_SYNONYMS.items():
    _SYNONYM_LOOKUP[main_role] = main_role
    for s in synonyms:
        _SYNONYM_LOOKUP[s.lower().strip()] = main_role


# ── NORMALIZATION ─────────────────────────────────────────────────────
def normalize_role(role: str) -> str:
    if not role or not role.strip():
        return ""

    cleaned = role.lower().strip()
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # 1. Direct lookup (FAST)
    if cleaned in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[cleaned]

    # 2. Remove level words
    without_level = re.sub(
        r'\b(junior|jr|senior|sr|lead|principal|entry.?level|mid.?level)\b',
        '', cleaned
    ).strip()

    if without_level in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[without_level]

    # 3. Partial fallback (SAFE)
    for main_role in ROLE_SYNONYMS:
        if main_role in cleaned or cleaned in main_role:
            return main_role

    return cleaned


# ── ROLE SIMILARITY (🔥 NEW CORE FIX) ─────────────────────────────────
def role_similarity(role1: str, role2: str) -> float:
    """
    Returns similarity score between two roles (0 → 1)
    """

    r1 = normalize_role(role1)
    r2 = normalize_role(role2)

    if not r1 or not r2:
        return 0.0

    # ✅ Exact match
    if r1 == r2:
        return 1.0

    # ✅ Word overlap similarity
    set1 = set(r1.split())
    set2 = set(r2.split())

    if not set1 or not set2:
        return 0.0

    overlap = len(set1 & set2)
    base_score = overlap / len(set2)

    # ✅ Keyword boost (IMPORTANT FIX)
    KEYWORDS = {
        "data", "analyst", "engineer", "healthcare",
        "etl", "bi", "analytics", "ml", "ai"
    }

    if any(k in r1 for k in KEYWORDS) and any(k in r2 for k in KEYWORDS):
        base_score = max(base_score, 0.5)

    return round(base_score, 3)


# ── MATCH SCORE CALCULATION (🔥 NEW) ──────────────────────────────────
def calculate_relevance_score(experiences: List[dict], jd_roles: List[str]) -> float:
    """
    Final relevance score (0 → 100)
    """

    if not experiences or not jd_roles:
        return 0.0

    total_score = 0.0

    for exp in experiences:
        job_title = exp.get("job_title", "")

        for jd_role in jd_roles:
            sim = role_similarity(job_title, jd_role)
            total_score += sim

    max_possible = len(experiences) * len(jd_roles)

    if max_possible == 0:
        return 0.0

    return round((total_score / max_possible) * 100, 2)


# ── OPTIONAL: ADD SYNONYM ─────────────────────────────────────────────
def add_role_synonym(canonical: str, new_synonym: str) -> None:
    canonical = canonical.lower().strip()

    if canonical not in ROLE_SYNONYMS:
        ROLE_SYNONYMS[canonical] = []

    clean_syn = new_synonym.lower().strip()

    if clean_syn not in [s.lower().strip() for s in ROLE_SYNONYMS[canonical]]:
        ROLE_SYNONYMS[canonical].append(new_synonym)
        _SYNONYM_LOOKUP[clean_syn] = canonical