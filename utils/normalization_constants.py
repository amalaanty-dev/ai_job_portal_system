"""
Normalization Constants for Day 15 - Fairness, Normalization & Bias Reduction
Path: ai_job_portal_system/utils/normalization_constants.py

Contains:
- Standard resume schema
- PII regex patterns
- Bias-prone keywords
- Masking placeholders
"""

# ---------------------------------------------------------------
# 1. STANDARD RESUME SCHEMA (used by resume_normalizer.py)
# ---------------------------------------------------------------
STANDARD_RESUME_SCHEMA = {
    "candidate_id": None,
    "personal_info": {
        "name": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin": None,
    },
    "professional_summary": "",
    "skills": {
        "programming": [],
        "ml_ai": [],
        "frameworks": [],
        "tools": [],
        "domain": [],
        "soft_skills": [],
        "all_skills_flat": [],
    },
    "experience": {
        "total_years": 0.0,
        "roles": [],   # [{job_title, company, start_date, end_date, duration_months, duties}]
    },
    "education": [],   # [{degree, institution, score, start_year, end_year}]
    "projects": [],    # [{title, description, technologies}]
    "certifications": [],
    "achievements": [],
    "metadata": {
        "source_file": None,
        "normalized_at": None,
        "schema_version": "1.0",
    }
}

# ---------------------------------------------------------------
# 2. PII REGEX PATTERNS (for pii_masker.py)
# ---------------------------------------------------------------
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"(\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}",
    "linkedin": r"(linkedin\.com/in/[A-Za-z0-9_-]+)",
    "github": r"(github\.com/[A-Za-z0-9_-]+)",
    "url": r"https?://[^\s]+",
    "address_pincode": r"\b\d{6}\b",   # Indian PIN
    "address_zip_us": r"\b\d{5}(-\d{4})?\b",
}

# ---------------------------------------------------------------
# 3. MASKING PLACEHOLDERS
# ---------------------------------------------------------------
MASK_PLACEHOLDERS = {
    "name": "[CANDIDATE_NAME]",
    "email": "[EMAIL_REDACTED]",
    "phone": "[PHONE_REDACTED]",
    "location": "[LOCATION_REDACTED]",
    "linkedin": "[LINKEDIN_REDACTED]",
    "github": "[GITHUB_REDACTED]",
    "url": "[URL_REDACTED]",
    "gender": "[GENDER_REDACTED]",
    "age": "[AGE_REDACTED]",
    "photo": "[PHOTO_REDACTED]",
    "caste_religion": "[DEMOGRAPHIC_REDACTED]",
    "marital_status": "[MARITAL_STATUS_REDACTED]",
    "college_tier": "[INSTITUTION_NAME]",
}

# ---------------------------------------------------------------
# 4. GENDER / DEMOGRAPHIC INDICATORS
# ---------------------------------------------------------------
GENDER_TERMS = [
    "male", "female", "mr", "mrs", "ms", "miss", "mister",
    "he/him", "she/her",
    "he", "she", "him", "her", "his", "hers",
]

MARITAL_TERMS = ["married", "single", "unmarried", "divorced", "widowed"]

CASTE_RELIGION_TERMS = [
    "hindu", "muslim", "christian", "sikh", "buddhist", "jain",
    "obc", "sc", "st", "general", "ews",
]

# ---------------------------------------------------------------
# 5. ELITE / TIER-1 INSTITUTIONS (for college-tier bias detection)
# ---------------------------------------------------------------
ELITE_INSTITUTIONS = [
    "iit", "iim", "nit", "iiit", "bits", "iisc",
    "harvard", "stanford", "mit", "cambridge", "oxford",
    "princeton", "yale", "berkeley",
]

# ---------------------------------------------------------------
# 6. BIAS-PRONE KEYWORDS (over-relied on by ATS)
# ---------------------------------------------------------------
GENERIC_BUZZWORDS = [
    "team player", "hardworking", "dynamic", "passionate",
    "go-getter", "rockstar", "ninja", "guru",
    "synergy", "leverage", "out-of-the-box",
]

# ---------------------------------------------------------------
# 7. SKILL SYNONYMS (reduce keyword over-dependence)
# ---------------------------------------------------------------
SKILL_SYNONYMS = {
    "ml": ["machine learning", "machinelearning", "ml"],
    "ai": ["artificial intelligence", "ai"],
    "nlp": ["natural language processing", "nlp"],
    "deep learning": ["deep learning", "dl", "neural networks",
                      "cnn", "rnn", "ann", "convolutional neural network"],
    "computer vision": ["computer vision", "cv", "image classification",
                        "image processing", "image recognition"],
    "tensorflow": ["tensorflow", "tf"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "kubernetes": ["kubernetes", "k8s"],
    "python": ["python", "py"],
    "problem solving": ["problem solving", "problem-solving",
                         "troubleshoot", "debugging"],
    "healthcare analytics": ["healthcare analytics", "medical analytics",
                              "clinical analytics", "health data"],
    "data analysis": ["data analysis", "data analytics", "eda",
                      "exploratory data analysis"],
}

# ---------------------------------------------------------------
# 8. SCORING NORMALIZATION CONFIG
# ---------------------------------------------------------------
NORMALIZATION_METHODS = ["min_max", "z_score", "percentile", "robust"]

DEFAULT_NORMALIZATION_METHOD = "min_max"

# ---------------------------------------------------------------
# 9. BIAS THRESHOLDS
# ---------------------------------------------------------------
BIAS_THRESHOLDS = {
    "max_acceptable_keyword_dependency": 0.60,   # >60% means too keyword-heavy
    "max_acceptable_score_variance": 0.25,        # variance across demographics
    "min_acceptable_pii_mask_rate": 0.95,         # 95% PII must be masked
    "max_elite_bias_gap": 10.0,                   # avg score gap (elite vs others)
}
