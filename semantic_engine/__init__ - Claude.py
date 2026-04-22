"""
semantic_engine
────────────────
Day 12 – Semantic Matching Engine

Public API:
    from semantic_engine import SemanticMatcher, ThresholdTuner, MatchingValidator
    from semantic_engine import embed, embed_batch, cosine_similarity
"""

from .embedder          import embed, embed_batch, embed_resume, embed_jd, get_model, cache_stats
from .similarity        import cosine_similarity, weighted_similarity, similarity_label, identify_gaps
from .semantic_matcher  import SemanticMatcher, MatchResult, WEIGHT_PROFILES
from .threshold_tuner   import ThresholdTuner, get_thresholds, apply_thresholds
from .validator         import MatchingValidator, ValidationReport

__all__ = [
    "SemanticMatcher",
    "MatchResult",
    "ThresholdTuner",
    "MatchingValidator",
    "ValidationReport",
    "WEIGHT_PROFILES",
    "embed",
    "embed_batch",
    "embed_resume",
    "embed_jd",
    "get_model",
    "cache_stats",
    "cosine_similarity",
    "weighted_similarity",
    "similarity_label",
    "identify_gaps",
    "get_thresholds",
    "apply_thresholds",
]
