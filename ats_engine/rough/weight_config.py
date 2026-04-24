"""
ats_engine/weight_config.py
───────────────────────────
Dynamic weight profile management + JD config builder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Role-type auto-detection keywords
ROLE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "ml_engineering": [
        "machine learning engineer", "ml engineer", "mlops", "ml platform",
        "model deployment", "model serving",
    ],
    "data_science": [
        "data scientist", "data science", "research scientist",
        "applied scientist", "analytics engineer",
    ],
    "healthcare_analytics": [
        "healthcare", "clinical", "health analytics", "medical data",
        "population health", "healthcare ai", "health informatics",
        "biostatistics", "epidemiology",
    ],
    "business_analyst": [
        "business analyst", "business intelligence", "bi analyst",
        "product analyst", "operations analyst",
    ],
    "entry_level": [
        "junior", "entry level", "entry-level", "associate",
        "intern", "graduate", "trainee",
    ],
    "senior_ic": [
        "senior", "lead", "principal", "staff", "director", "head of",
    ],
}


def detect_role_type(job_title: str) -> str:
    t = job_title.lower()
    for profile, kws in ROLE_TYPE_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return profile
    return "default"


DIMENSIONS = [
    "skill_match",
    "experience_relevance",
    "education_alignment",
    "semantic_similarity",
]


def validate_profile(weights: dict) -> tuple[bool, str]:
    if not isinstance(weights, dict):
        return False, "Must be a dict"
    missing = set(DIMENSIONS) - set(weights.keys())
    if missing:
        return False, f"Missing dimensions: {missing}"
    extra = set(weights.keys()) - set(DIMENSIONS)
    if extra:
        return False, f"Unknown dimensions: {extra}"
    total = sum(weights.values())
    if abs(total - 1.0) > 0.005:
        return False, f"Weights must sum to 1.0; got {total:.4f}"
    neg = [k for k, v in weights.items() if v < 0]
    if neg:
        return False, f"Negative weights: {neg}"
    return True, "Valid"


def build_jd_config(
    job_title:          str,
    jd_id:              Optional[str] = None,
    required_skills:    Optional[list[str]] = None,
    preferred_skills:   Optional[list[str]] = None,
    target_years:       float = 3.0,
    role_keywords:      Optional[list[str]] = None,
    preferred_degrees:  Optional[list[str]] = None,
    preferred_fields:   Optional[list[str]] = None,
    min_cert_count:     int = 0,
    weight_profile:     Optional[str] = None,
) -> dict:
    profile = weight_profile or detect_role_type(job_title)
    return {
        "job_title":         job_title,
        "jd_id":             jd_id or job_title.lower().replace(" ", "_"),
        "required_skills":   required_skills  or [],
        "preferred_skills":  preferred_skills or [],
        "target_years":      target_years,
        "role_keywords":     role_keywords    or [],
        "preferred_degrees": preferred_degrees or [],
        "preferred_fields":  preferred_fields  or [],
        "min_cert_count":    min_cert_count,
        "weight_profile":    profile,
    }
