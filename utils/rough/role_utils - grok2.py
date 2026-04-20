from typing import Dict, List
import re

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

def normalize_role(role: str) -> str:
    """
    Normalize job role to canonical form.
    """
    if not role or not role.strip():
        return ""

    cleaned = role.lower().strip()
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # 1. Exact canonical
    if cleaned in ROLE_SYNONYMS:
        return cleaned

    # 2. Synonym match
    for main_role, synonyms in ROLE_SYNONYMS.items():
        if cleaned in [s.lower().strip() for s in synonyms]:
            return main_role

    # 3. Remove levels + retry
    without_level = re.sub(
        r'\b(junior|jr|senior|sr|lead|principal|entry.?level|mid.?level)\b',
        '', cleaned
    ).strip()
    if without_level and without_level in ROLE_SYNONYMS:
        return without_level
    for main_role, synonyms in ROLE_SYNONYMS.items():
        if without_level in [s.lower().strip() for s in synonyms]:
            return main_role

    # 4. Strict partial fallback
    for main_role in ROLE_SYNONYMS:
        if main_role in cleaned or cleaned in main_role:
            return main_role

    return cleaned


# Optional helper
def add_role_synonym(canonical: str, new_synonym: str) -> None:
    canonical = canonical.lower().strip()
    if canonical not in ROLE_SYNONYMS:
        ROLE_SYNONYMS[canonical] = []
    clean_syn = new_synonym.lower().strip()
    if clean_syn not in [s.lower().strip() for s in ROLE_SYNONYMS[canonical]]:
        ROLE_SYNONYMS[canonical].append(new_synonym)