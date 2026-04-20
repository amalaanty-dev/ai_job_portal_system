# 1. SKILL CATEGORIES
# ----------------------------------

TECH_SKILLS = [
    "python","java","c++","c#","javascript","typescript",
    "html","css","react","angular","nodejs",
    "sql","mysql","postgresql","mongodb",
    "machine learning","deep learning","nlp","computer vision",
    "data analysis","data visualization",
    "tensorflow","pytorch","scikit-learn",
    "aws","azure","gcp","docker","kubernetes",
    "git","linux","excel",
    "etl","data engineering","mlops"
]


BUSINESS_SKILLS = [
    "project management","business analysis","agile","scrum",
    "stakeholder management","stakeholder communication",
    "strategic planning",
    "process improvement","workflow optimization","lean","six sigma",
    "risk analysis","cost analysis","kpi analysis",
    "claims analysis","fraud detection","revenue cycle analysis",
    "report writing"
]


CREATIVE_SKILLS = [
    "graphic design","ui design","ux design",
    "photoshop","illustrator","figma"
]


# ----------------------------------
# 2. MASTER SKILL DATABASE
# ----------------------------------

MASTER_SKILLS_DB = list(set(

    TECH_SKILLS +
    BUSINESS_SKILLS +
    CREATIVE_SKILLS +

    [

    # Advanced Analytics
    "data mining","data modeling","data validation",
    "data extraction","data interpretation",

    # Visualization
    "dashboard development","visual analytics",

    # Statistics
    "statistics","statistical analysis",
    "statistical modeling","predictive modeling",

    # AI extra
    "ai",

    # Healthcare
    "healthcare analytics","health informatics",
    "clinical data analysis","clinical research",
    "ehr","emr","hl7","fhir","bioinformatics",

    # Public Health
    "epidemiology","public health analytics","disease surveillance",

    # Soft Skills
    "analytical thinking","problem solving",
    "attention to detail","communication skills","leadership"
]

))


# ----------------------------------
# 3. SKILL SYNONYMS
# ----------------------------------

SKILL_SYNONYMS = {

    "ml": "machine learning",
    "ai": "artificial intelligence",
    "js": "javascript",
    "node": "nodejs",
    "powerbi": "power bi",

    "python3": "python",
    "python programming": "python",

    "structured query language": "sql",
    "mysql": "sql",
    "postgresql": "sql",

    "data viz": "data visualization",
    "dashboard creation": "dashboard development",

    "machine-learning": "machine learning",
    "neural networks": "deep learning",
    "dnn": "deep learning",

    "natural language processing": "nlp",

    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",

    "electronic health records": "ehr",
    "electronic medical records": "emr",

    "data analytics": "data analysis",
    "data insights": "data analysis",

    "business analytics": "business analysis",

    "ms excel": "excel",
    "microsoft excel": "excel",

    "critical thinking": "analytical thinking",
    "logical thinking": "analytical thinking",
    "detail oriented": "attention to detail",
    "team leadership": "leadership"
}


# ----------------------------------
# 4. SKILL STACKS
# ----------------------------------

SKILL_STACKS = {
    "mern": ["mongodb","express","react","nodejs"],
    "mean": ["mongodb","express","angular","nodejs"]
}


# ----------------------------------
# 5. HELPER FUNCTIONS
# ----------------------------------

def normalize_skill(skill):
    skill = skill.lower().strip()
    return SKILL_SYNONYMS.get(skill, skill)


def get_skill_category(skill):

    skill = skill.lower()

    if skill in TECH_SKILLS:
        return "tech"
    elif skill in BUSINESS_SKILLS:
        return "business"
    elif skill in CREATIVE_SKILLS:
        return "creative"
    else:
        return "other"
