ROLE_SYNONYMS = {
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
    ],
    "health information analyst": [
        "health information data analyst",
        "health information systems analyst",
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
    ],
    "healthcare data analyst": [
        "health data analyst",
        "healthcare analyst",
        "data analyst healthcare",
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
    "healthcare bi (business intelligence) analyst": [
        "healthcare bi analyst",
        "healthcare business intelligence analyst",
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
    "real world evidence (rwe) analyst": [
        "rwe analyst",
    ],
    "health informatics specialist": [
        "health informatics analyst",
    ],
    "clinical informatics analyst": [
        "clinical informatics specialist",
    ],
    "healthcare data integration specialist": [
        "health data integration analyst",
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
    "cost & utilization analyst": [
        "cost utilization analyst",
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
    "fraud & compliance analyst": [
        "fraud compliance analyst",
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
}


def normalize_role(role: str) -> str:
    """
    Map a role string to its canonical form using ROLE_SYNONYMS.
    If no match is found, returns the cleaned input as-is.
    """
    if not role:
        return ""

    cleaned = role.lower().strip()

    # Direct match on canonical key
    if cleaned in ROLE_SYNONYMS:
        return cleaned

    # Match against synonym lists
    for main_role, synonyms in ROLE_SYNONYMS.items():
        if cleaned in synonyms:
            return main_role

    return cleaned