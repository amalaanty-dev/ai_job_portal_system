"""
scoring_config.py
Declarative scoring configuration used by the ATS engine.
Mirrors WeightConfig but in a config-file style for easy editing.
"""

# ── Role-specific weight definitions ──────────────────────────────────────────
# Each key corresponds to a role_type string passed to score_candidate().
# Values are relative weights; the engine normalizes them automatically.
# You can add new role types here without changing any other code.

ROLE_WEIGHTS = {

    "generic": {
        "skill_match":          0.35,
        "education_alignment":  0.15,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.20,
    },

    "healthcare_analytics": {
        "skill_match":          0.30,
        "education_alignment":  0.20,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.20,
    },

    "ml_engineer": {
        "skill_match":          0.40,
        "education_alignment":  0.10,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.20,
    },

    "data_scientist": {
        "skill_match":          0.35,
        "education_alignment":  0.15,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.20,
    },

    "data_analyst": {
        "skill_match":          0.35,
        "education_alignment":  0.15,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.20,
    },

    "senior_data": {
        "skill_match":          0.25,
        "education_alignment":  0.15,
        "experience_relevance": 0.40,
        "semantic_similarity":  0.20,
    },

    "junior_analyst": {
        "skill_match":          0.40,
        "education_alignment":  0.25,
        "experience_relevance": 0.15,
        "semantic_similarity":  0.20,
    },

    "finance": {
        "skill_match":          0.30,
        "education_alignment":  0.20,
        "experience_relevance": 0.35,
        "semantic_similarity":  0.15,
    },

    "nlp_specialist": {
        "skill_match":          0.40,
        "education_alignment":  0.10,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.20,
    },

    "public_health": {
        "skill_match":          0.25,
        "education_alignment":  0.30,
        "experience_relevance": 0.30,
        "semantic_similarity":  0.15,
    },
}

# ── Score thresholds for verdict labels ───────────────────────────────────────
VERDICT_THRESHOLDS = [
    (75, "Strong Match",  "#22c55e", "✅"),
    (55, "Good Match",    "#3b82f6", "👍"),
    (40, "Partial Match", "#f59e0b", "⚠️"),
    (25, "Weak Match",    "#f97316", "🔶"),
    (0,  "Mismatch",      "#ef4444", "❌"),
]

# ── Gap severity thresholds ───────────────────────────────────────────────────
GAP_CRITICAL_THRESHOLD  = 25   # score < this → critical
GAP_MODERATE_THRESHOLD  = 45   # score < this → moderate
GAP_MISSING_SCORE       = 0.0  # score == 0 and no data → missing

# ── Education degree level bonuses ────────────────────────────────────────────
DEGREE_BONUSES = {
    "phd":      20, "doctorate": 20,
    "mba":      12, "msc": 12, "ms": 12, "master": 12,
    "bsc":       5, "bba":  5, "bachelor": 5, "be": 5,
}

# ── High-value skills for bonus scoring ───────────────────────────────────────
HIGH_VALUE_SKILLS = {
    "python", "sql", "machine learning", "deep learning",
    "nlp", "tensorflow", "pytorch", "spark", "airflow",
    "kubernetes", "docker", "llm", "transformers",
    "r", "scala", "hadoop", "databricks", "snowflake",
}
