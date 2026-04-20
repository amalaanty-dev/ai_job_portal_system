from typing import Dict, List
import re

ROLE_SYNONYMS: Dict[str, List[str]] = {
    "healthcare data analyst (junior)": [
        "junior healthcare data analyst", "jr healthcare data analyst",
        "entry level healthcare data analyst", "jr. healthcare data analyst",
        "healthcare data analyst junior", "junior health data analyst",
    ],
    "clinical data analyst": [
        "clinical analytics analyst", "clinical trial data analyst",
        "clinical data analytics analyst", "clinical research data analyst",
    ],
    "healthcare reporting analyst": [
        "healthcare report analyst", "reporting analyst healthcare",
        "healthcare reports analyst",
    ],
    "medical data analyst": [
        "medical analytics analyst", "medical data analytics",
    ],
    "health information analyst": [
        "health information data analyst", "health information systems analyst",
        "his analyst",
    ],
    "data entry analyst (healthcare)": [
        "healthcare data entry analyst", "healthcare data entry specialist",
    ],
    "public health data analyst (entry-level)": [
        "entry level public health data analyst", "junior public health data analyst",
    ],
    "ehr data analyst": [
        "electronic health record analyst", "ehr analytics specialist",
        "ehr analyst", "electronic medical record analyst",
    ],
    "healthcare data analyst": [
        "health data analyst", "healthcare analyst", "data analyst healthcare",
        "healthcare data analytics", "data analyst in healthcare", "health analytics analyst",
    ],
    "senior clinical data analyst": [
        "sr clinical data analyst", "senior clinical analytics analyst",
    ],
    "healthcare business analyst": [
        "healthcare ba", "business analyst healthcare", "healthcare business analytics",
    ],
    "population health analyst": [
        "population health data analyst", "population health analytics analyst",
    ],
    "quality improvement analyst (healthcare)": [
        "healthcare quality analyst", "quality improvement data analyst",
    ],
    "healthcare operations analyst": [
        "hospital operations analyst", "healthcare ops analyst",
    ],
    "revenue cycle data analyst": [
        "revenue cycle analyst", "rcm analyst", "revenue cycle management analyst",
    ],
    "healthcare performance analyst": [
        "hospital performance analyst", "healthcare performance analytics",
    ],
    "healthcare bi (business intelligence) analyst": [
        "healthcare bi analyst", "healthcare business intelligence analyst",
        "healthcare bi developer",
    ],
    "claims data analyst": [
        "insurance claims analyst", "claims analytics analyst",
    ],
    "senior healthcare data analyst": [
        "sr healthcare data analyst", "senior health data analyst",
    ],
    "lead data analyst (healthcare)": [
        "lead healthcare data analyst", "lead health data analyst",
    ],
    "healthcare analytics manager": [
        "manager healthcare analytics", "healthcare analytics lead",
    ],
    "healthcare data science manager": [
        "healthcare ds manager", "manager healthcare data science",
    ],
    "director of healthcare analytics": [
        "healthcare analytics director", "director healthcare analytics",
    ],
    "chief data officer": ["cdo"],
    "head of health informatics": ["health informatics head"],
    "healthcare data scientist": [
        "healthcare ai data scientist", "health data scientist",
    ],
    "clinical data scientist": ["clinical analytics scientist"],
    "healthcare machine learning engineer": ["ml engineer healthcare"],
    "ai specialist in healthcare analytics": ["healthcare ai engineer", "healthcare ai analyst"],
    "predictive analytics specialist": ["predictive healthcare analyst"],
    "healthcare statistician": ["clinical statistician"],
    "biostatistician": ["bio statistician", "biostatistics analyst"],
    "clinical trials data manager": ["clinical trial data manager"],
    "epidemiologist": ["public health epidemiologist"],
    "healthcare outcomes analyst": ["health outcomes analyst"],
    "real world evidence (rwe) analyst": ["rwe analyst"],
    "health informatics specialist": ["health informatics analyst"],
    "clinical informatics analyst": ["clinical informatics specialist"],
    "healthcare data integration specialist": ["health data integration analyst"],
    "ehr implementation analyst": ["ehr implementation specialist"],
    "healthcare data architect": ["health data architect"],
    "healthcare financial analyst": ["healthcare finance analyst"],
    "medical billing data analyst": ["billing analytics analyst"],
    "insurance claims analyst": ["claims analytics analyst"],
    "cost & utilization analyst": ["cost utilization analyst"],
    "public health analyst": ["public health analytics analyst"],
    "health policy analyst": ["healthcare policy analyst"],
    "epidemiology data analyst": ["epidemiology analyst"],
    "digital health analyst": ["digital healthcare analyst"],
    "telehealth data analyst": ["telemedicine data analyst"],
    "patient experience analyst": ["patient satisfaction analyst"],
    "healthcare risk analyst": ["clinical risk analyst"],
    "genomics data analyst": ["genomic data analyst", "bioinformatics analyst"],
    "freelance healthcare data analyst": ["contract healthcare data analyst"],
    "healthcare analytics consultant": ["healthcare analytics advisor"],
    "healthcare dashboard developer": ["healthcare bi dashboard developer"],
    "remote clinical data analyst": ["virtual clinical data analyst"],
}

# Pre-computed flat map: variant -> canonical
_ROLE_CANONICAL_MAP: Dict[str, str] = {}


def _build_role_map() -> None:
    """Build reverse mapping for fast lookups (run once at import)"""
    global _ROLE_CANONICAL_MAP
    _ROLE_CANONICAL_MAP.clear()

    for canonical, synonyms in ROLE_SYNONYMS.items():
        clean_canonical = canonical.lower().strip()
        _ROLE_CANONICAL_MAP[clean_canonical] = canonical

        for syn in synonyms:
            clean_syn = syn.lower().strip()
            _ROLE_CANONICAL_MAP[clean_syn] = canonical


# Build the map immediately when the module is imported
_build_role_map()


def normalize_role(role: str) -> str:
    """
    Normalize a job role string to its canonical form.
    
    Returns the canonical role if a match is found,
    otherwise returns a cleaned version of the input.
    """
    if not role or not role.strip():
        return ""

    # Basic cleaning
    cleaned = role.lower().strip()
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)   # remove punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()  # normalize spaces

    # Fast exact match
    if cleaned in _ROLE_CANONICAL_MAP:
        return _ROLE_CANONICAL_MAP[cleaned]

    # Remove common level words and try again
    without_level = re.sub(
        r'\b(junior|jr|senior|sr|lead|principal|entry level|mid level|mid-level)\b',
        '', cleaned
    ).strip()
    if without_level and without_level in _ROLE_CANONICAL_MAP:
        return _ROLE_CANONICAL_MAP[without_level]

    # Partial contains match as last resort (less strict)
    for variant in list(_ROLE_CANONICAL_MAP.keys()):
        if variant in cleaned or cleaned in variant:
            return _ROLE_CANONICAL_MAP[variant]

    # Final fallback: return nicely cleaned input
    return cleaned


# Optional helper to add new synonyms dynamically
def add_role_synonym(canonical: str, new_synonym: str) -> None:
    """Add a new synonym at runtime and update the map"""
    canonical = canonical.lower().strip()
    if canonical not in ROLE_SYNONYMS:
        ROLE_SYNONYMS[canonical] = []

    clean_syn = new_synonym.lower().strip()
    if clean_syn not in ROLE_SYNONYMS[canonical]:
        ROLE_SYNONYMS[canonical].append(clean_syn)

    _ROLE_CANONICAL_MAP[clean_syn] = canonical