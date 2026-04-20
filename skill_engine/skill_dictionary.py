# 1. SKILL CATEGORIES
# ----------------------------------

TECH_SKILLS = [
    "python", "java", "c++", "c#", "javascript", "typescript", "html", "css", 
    "react", "angular", "nodejs", "sql", "mongodb", "postgresql",
    "machine learning", "deep learning", "nlp", "computer vision",
    "data analysis", "data visualization", "tensorflow", "pytorch", "scikit-learn",
    "aws", "azure", "gcp", "docker", "kubernetes", "git", "linux", "excel",
    "etl", "data engineering", "mlops", "regex",
    
    # Added from DS/DA and NLP Specialist profile
    "pandas", "numpy", "matplotlib", "seaborn", "xgboost", "streamlit", 
    "statsmodels", "nltk", "spacy", "transformers", "keras", "jupyter notebook",
    "visual studio code", "google colab", "postman", "jenkins",
    
    # Added from Healthcare Data Analyst profiles
    "epic", "cerner", "meditech", "medidata rave", "oracle clinical", 
    "redcap", "hl7", "fhir", "icd-10", "cpt codes", "ehr", "emr",
    "sas", "sql server", "azure health data services", "reporting workbench", "medisoft", "kareo"
]

BUSINESS_SKILLS = [
    "project management", "business analysis", "agile", "scrum",
    "stakeholder management", "strategic planning", "process improvement", 
    "workflow optimization", "lean", "six sigma", "risk analysis", 
    "cost analysis", "kpi analysis", "claims analysis", "fraud detection", 
    "revenue cycle analysis", "report writing", "compliance", "data governance",
    
    # Added Domain & Regulatory
    "bfsi", "banking", "financial services", "hipaa", "hedis", 
    "quality reporting", "population health analytics", "clinical workflow design",
    "medical billing", "research methodology"
]

CREATIVE_SKILLS = [
    "graphic design", "ui design", "ux design", "photoshop", "illustrator", "figma",
    "tableau", "power bi"
]

# ----------------------------------
# 2. MASTER SKILL DATABASE
# ----------------------------------

MASTER_SKILLS_DB = list(set(
    TECH_SKILLS +
    BUSINESS_SKILLS +
    CREATIVE_SKILLS +
    [
        # Advanced Analytics & Research
        "data mining", "data modeling", "data validation", "data extraction", 
        "data interpretation", "eda", "feature engineering", "hyperparameter tuning",
        "model evaluation", "data wrangling", "data cleaning", "statistical analysis",
        "predictive modeling", "clinical research", "bioinformatics",
        
        # NLP & Conversational AI Specifics
        "intent classification", "ner", "dialog management", "faq modeling", 
        "llm", "chatbot training", "sentiment analysis", "ontology", "knowledge graphs",
        
        # Public Health & Soft Skills
        "epidemiology", "public health analytics", "disease surveillance",
        "analytical thinking", "problem solving", "attention to detail", 
        "communication skills", "leadership", "interdisciplinary collaboration"
    ]
))

# ----------------------------------
# 3. SKILL SYNONYMS (Expanded from Resume Outputs)
# ----------------------------------

SKILL_SYNONYMS = {
    # Tech & AI
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "js": "javascript",
    "node": "nodejs",
    "powerbi": "power bi",
    "python3": "python",
    "python programming": "python",
    "sklearn": "scikit-learn",
    "scikit": "scikit-learn",
    "natural language processing": "nlp",
    "neural networks": "deep learning",
    "dnn": "deep learning",
    "llms": "llm",
    "stats": "statistical analysis",
    "viz": "data visualization",
    "data viz": "data visualization",
    "dashboard creation": "dashboard development",
    
    # Database
    "structured query language": "sql",
    "mysql": "sql",
    "postgresql": "sql",
    "sql server": "sql",
    
    # Healthcare Specifics
    "electronic health records": "ehr",
    "electronic medical records": "emr",
    "interoperability": "hl7",
    "fhir": "hl7",
    "icd-10 coding": "icd-10",
    "medical record analysis": "medical record analysis",
    "healthcare reporting": "report writing",
    "clinical trial reporting": "clinical research",
    
    # Cloud & Tools
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "advanced excel": "excel",
    "pivot tables": "excel",
    "vsc": "visual studio code",
    
    # Business & Soft Skills
    "data analytics": "data analysis",
    "data insights": "data analysis",
    "business analytics": "business analysis",
    "critical thinking": "analytical thinking",
    "logical thinking": "analytical thinking",
    "detail oriented": "attention to detail",
    "team leadership": "leadership",
    "stakeholder communication": "stakeholder management"
}

# ----------------------------------
# 4. SKILL STACKS
# ----------------------------------

SKILL_STACKS = {
    "mern": ["mongodb", "express", "react", "nodejs"],
    "mean": ["mongodb", "express", "angular", "nodejs"],
    "conversational ai": ["nlp", "dialog management", "intent classification", "ner"],
    "data science": ["python", "machine learning", "statistics", "data visualization"]
}

# ----------------------------------
# 5. HELPER FUNCTIONS
# ----------------------------------

def normalize_skill(skill):
    skill = skill.lower().strip()
    return SKILL_SYNONYMS.get(skill, skill)

def get_skill_category(skill):
    skill = skill.lower().strip()
    normalized = normalize_skill(skill)
    
    if normalized in TECH_SKILLS:
        return "tech"
    elif normalized in BUSINESS_SKILLS:
        return "business"
    elif normalized in CREATIVE_SKILLS:
        return "creative"
    return "other"