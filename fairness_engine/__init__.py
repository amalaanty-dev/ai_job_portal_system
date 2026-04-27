"""
Fairness Engine Package - Day 15
Path: ai_job_portal_system/fairness_engine/__init__.py

Modules:
    - resume_normalizer        : Standardize resumes to common schema
    - keyword_dependency_reducer: Reduce ATS over-reliance on raw keywords
    - score_normalizer         : Normalize scores (Min-Max / Z-score / Percentile)
    - pii_masker               : Mask personal identifiers to reduce bias
    - bias_evaluator           : Evaluate bias indicators across cohorts
    - fairness_pipeline        : End-to-end orchestrator
"""

from .resume_normalizer import ResumeNormalizer
from .keyword_dependency_reducer import KeywordDependencyReducer
from .score_normalizer import ScoreNormalizer
from .pii_masker import PIIMasker
from .bias_evaluator import BiasEvaluator
from .fairness_pipeline import FairnessPipeline

__all__ = [
    "ResumeNormalizer",
    "KeywordDependencyReducer",
    "ScoreNormalizer",
    "PIIMasker",
    "BiasEvaluator",
    "FairnessPipeline",
]

__version__ = "1.0.0"
