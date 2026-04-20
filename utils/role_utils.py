from typing import Dict, List
import re

# ── ROLE SYNONYMS ─────────────────────────────────────────────────────
# Rules:
#   - Keys   : canonical role titles (lowercase)
#   - Values : alternate role title strings only — NO skill names,
#              technology names, or tool names (those go in jd_skills)
#   - Every synonym must be a plausible job title a resume might use

ROLE_SYNONYMS: Dict[str, List[str]] = {
    "healthcare data analyst (junior)": [
        "junior healthcare data analyst",
        "jr healthcare data analyst",
        "entry level healthcare data analyst",
    ],
    "clinical data analyst": [
        "clinical analytics analyst",
        "clinical trial data analyst",
    ],
    "healthcare reporting analyst": [
        "healthcare report analyst",
        "reporting analyst healthcare",
    ],
    "medical data analyst": [
        "medical analytics analyst",
        "healthcare domain medical data analyst",
    ],
    "health information analyst": [
        "health information data analyst",
        "health information systems analyst",
        "his analyst",
    ],
    "data entry analyst (healthcare)": [
        "healthcare data entry analyst",
    ],
    "public health data analyst (entry-level)": [
        "entry level public health data analyst",
    ],
    "ehr data analyst": [
        "electronic health record analyst",
        "ehr analytics specialist",
        "ehr analyst",
    ],
    "healthcare data analyst": [
        "health data analyst",
        "healthcare analyst",
        "data analyst healthcare",
        "health analytics analyst",
        "healthcare data specialist",
        "healthcare data associate",
    ],
    "senior clinical data analyst": [
        "sr clinical data analyst",
    ],
    "healthcare business analyst": [
        "healthcare ba",
        "business analyst healthcare",
    ],
    "population health analyst": [
        "population health data analyst",
    ],
    "quality improvement analyst (healthcare)": [
        "healthcare quality analyst",
    ],
    "healthcare operations analyst": [
        "hospital operations analyst",
    ],
    "revenue cycle data analyst": [
        "revenue cycle analyst",
        "rcm analyst",
    ],
    "healthcare performance analyst": [
        "hospital performance analyst",
    ],
    "healthcare bi analyst": [
        "healthcare business intelligence analyst",
        "bi analyst healthcare",
        "healthcare bi (business intelligence) analyst",
        "healthcare dashboard analyst",
        "healthcare reporting and bi analyst",
    ],
    "claims data analyst": [
        "insurance claims analyst",
    ],
    "senior healthcare data analyst": [
        "sr healthcare data analyst",
    ],
    "lead data analyst (healthcare)": [
        "lead healthcare data analyst",
    ],
    "healthcare analytics manager": [
        "manager healthcare analytics",
    ],
    "healthcare data science manager": [
        "healthcare ds manager",
    ],
    "director of healthcare analytics": [
        "healthcare analytics director",
    ],
    "chief data officer": [
        "cdo",
    ],
    "head of health informatics": [
        "health informatics head",
    ],
    "healthcare data scientist": [
        "healthcare ai data scientist",
    ],
    "clinical data scientist": [
        "clinical analytics scientist",
    ],
    "healthcare machine learning engineer": [
        "ml engineer healthcare",
    ],
    "ai specialist in healthcare analytics": [
        "healthcare ai engineer",
    ],
    "predictive analytics specialist": [
        "predictive healthcare analyst",
    ],
    "healthcare statistician": [
        "clinical statistician",
    ],
    "biostatistician": [
        "bio statistician",
    ],
    "clinical research data analyst": [
        "clinical research analyst",
    ],
    "clinical trials data manager": [
        "clinical trial data manager",
    ],
    "epidemiologist": [
        "public health epidemiologist",
    ],
    "healthcare outcomes analyst": [
        "health outcomes analyst",
    ],
    "real world evidence analyst": [
        "rwe analyst",
        "real world evidence (rwe) analyst",
    ],
    "health informatics specialist": [
        "health informatics analyst",
    ],
    "clinical informatics analyst": [
        "clinical informatics specialist",
    ],
    "healthcare data integration specialist": [
        "health data integration analyst",
        "healthcare etl analyst",
        "healthcare data pipeline analyst",
    ],
    "ehr implementation analyst": [
        "ehr implementation specialist",
    ],
    "healthcare data architect": [
        "health data architect",
    ],
    "health information systems analyst": [
        "his analyst",
    ],
    "healthcare financial analyst": [
        "healthcare finance analyst",
    ],
    "medical billing data analyst": [
        "billing analytics analyst",
    ],
    "insurance claims analyst": [
        "claims analytics analyst",
    ],
    "cost and utilization analyst": [
        "cost utilization analyst",
        "cost & utilization analyst",
    ],
    "public health analyst": [
        "public health analytics analyst",
    ],
    "health policy analyst": [
        "healthcare policy analyst",
    ],
    "epidemiology data analyst": [
        "epidemiology analyst",
    ],
    "healthcare program analyst": [
        "health program analyst",
    ],
    "global health data analyst": [
        "global health analyst",
    ],
    "digital health analyst": [
        "digital healthcare analyst",
    ],
    "telehealth data analyst": [
        "telemedicine data analyst",
    ],
    "healthcare ai analyst": [
        "ai healthcare analyst",
    ],
    "patient experience analyst": [
        "patient satisfaction analyst",
    ],
    "healthcare risk analyst": [
        "clinical risk analyst",
    ],
    "fraud and compliance analyst": [
        "fraud compliance analyst",
        "fraud & compliance analyst",
    ],
    "wearable health data analyst": [
        "wearable analytics analyst",
    ],
    "genomics data analyst": [
        "genomic data analyst",
        "bioinformatics analyst",
    ],
    "freelance healthcare data analyst": [
        "contract healthcare data analyst",
    ],
    "healthcare analytics consultant": [
        "healthcare analytics advisor",
    ],
    "data analytics trainer": [
        "analytics instructor",
    ],
    "healthcare dashboard developer": [
        "healthcare bi dashboard developer",
    ],
    "remote clinical data analyst": [
        "virtual clinical data analyst",
    ],
    # ── General data / engineering roles ─────────────────────────────
    "data analyst": [
        "analyst data",
        "junior data analyst",
        "senior data analyst",
        "sr data analyst",
        "jr data analyst",
        "lead data analyst",
    ],
    "data engineer": [
        "big data engineer",
        "etl engineer",
        "data pipeline engineer",
        "cloud data engineer",
        "spark engineer",
        "etl developer",
        "analytics engineer",
        "data infrastructure engineer",
        "database engineer",
        "data engineer ii",
        "senior data engineer",
        "sr data engineer",
        "junior data engineer",
    ],
    "healthcare data engineer": [
        "healthcare etl engineer",
        "health data pipeline engineer",
        "medical data engineer",
        "clinical data engineer",
    ],
    "data scientist": [
        "junior data scientist",
        "senior data scientist",
        "sr data scientist",
        "jr data scientist",
        "lead data scientist",
        "ml engineer",
        "machine learning engineer",
    ],
}


# ── FAST LOOKUP CACHE ─────────────────────────────────────────────────
# Maps every synonym (and canonical) → canonical for O(1) lookups
_SYNONYM_LOOKUP: Dict[str, str] = {}

for _main_role, _synonyms in ROLE_SYNONYMS.items():
    _SYNONYM_LOOKUP[_main_role] = _main_role
    for _s in _synonyms:
        _SYNONYM_LOOKUP[_s.lower().strip()] = _main_role


# ── NORMALIZATION ─────────────────────────────────────────────────────
# Significant words used in partial-match fallback — generic words
# ("analyst", "data") alone are not enough to confirm a match
_STOP_WORDS = {
    "a", "an", "the", "of", "in", "at", "for", "and", "or",
    "to", "with", "on", "by", "as", "is",
}

_LEVEL_RE = re.compile(
    r'\b(junior|jr|senior|sr|lead|principal|entry.?level|mid.?level)\b'
)


def normalize_role(role: str) -> str:
    """
    Normalise a raw role string to its canonical form.

    Steps:
      1. Clean punctuation and whitespace
      2. Direct lookup in synonym cache (fastest path)
      3. Lookup after stripping seniority level words
      4. Partial fallback — requires ≥2 significant word overlap
         to avoid false matches on generic single words like "analyst"
      5. Return cleaned string as-is if nothing matched
    """
    if not role or not role.strip():
        return ""

    cleaned = role.lower().strip()
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Step 1 — direct lookup
    if cleaned in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[cleaned]

    # Step 2 — lookup after stripping seniority level words
    without_level = _LEVEL_RE.sub("", cleaned).strip()
    without_level = re.sub(r'\s+', ' ', without_level).strip()

    if without_level and without_level in _SYNONYM_LOOKUP:
        return _SYNONYM_LOOKUP[without_level]

    # Step 3 — partial fallback with minimum 2 significant word overlap
    cleaned_words = set(cleaned.split()) - _STOP_WORDS

    best_canonical = None
    best_overlap   = 0

    for main_role in ROLE_SYNONYMS:
        main_words = set(main_role.split()) - _STOP_WORDS
        overlap    = len(cleaned_words & main_words)

        # Require at least 2 significant words to match
        if overlap >= 2 and overlap > best_overlap:
            best_overlap   = overlap
            best_canonical = main_role

    if best_canonical:
        return best_canonical

    return cleaned


# ── ROLE SIMILARITY ───────────────────────────────────────────────────
def role_similarity(role1: str, role2: str) -> float:
    """
    Returns similarity score between two role strings in [0.0, 1.0].
    Used for external callers; the experience_matcher uses its own
    SequenceMatcher-based _similar() directly.
    """
    r1 = normalize_role(role1)
    r2 = normalize_role(role2)

    if not r1 or not r2:
        return 0.0

    if r1 == r2:
        return 1.0

    set1 = set(r1.split()) - _STOP_WORDS
    set2 = set(r2.split()) - _STOP_WORDS

    if not set1 or not set2:
        return 0.0

    overlap    = len(set1 & set2)
    base_score = overlap / max(len(set1), len(set2))

    # Keyword boost — both roles mention core data/analytics terms
    _KEYWORDS = {"data", "analyst", "engineer", "healthcare", "clinical",
                 "etl", "bi", "analytics", "ml", "ai", "health"}

    if any(k in r1 for k in _KEYWORDS) and any(k in r2 for k in _KEYWORDS):
        base_score = max(base_score, 0.4)

    return round(base_score, 3)


# ── ADD SYNONYM (runtime utility) ─────────────────────────────────────
def add_role_synonym(canonical: str, new_synonym: str) -> None:
    """Add a new synonym for a canonical role at runtime."""
    canonical  = canonical.lower().strip()
    clean_syn  = new_synonym.lower().strip()

    if canonical not in ROLE_SYNONYMS:
        ROLE_SYNONYMS[canonical] = []

    existing = [s.lower().strip() for s in ROLE_SYNONYMS[canonical]]
    if clean_syn not in existing:
        ROLE_SYNONYMS[canonical].append(new_synonym)
        _SYNONYM_LOOKUP[clean_syn] = canonical