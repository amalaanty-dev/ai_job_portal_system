"""
score_utils.py
---------------
Helpers for composite score computation.

Adapted to the actual Day 13 ATS engine output shape:
  {
    "identifiers": {"resume_id": "...", "jd_id": "...", "job_role": "..."},
    "final_score": 57.3,
    "scoring_breakdown": {
        "skill_match":          90,
        "experience_relevance": 60,
        "education_alignment":  36,
        "semantic_similarity":  12
    },
    "score_interpretation": {"rating": "...", "recommendation": "...", ...}
  }

Two modes of operation:
  - PASS-THROUGH (default): Trust Day 13's `final_score`. Sub-scores are
    extracted only for reporting/explanation purposes.
  - RECOMPUTE (--recompute flag): Re-weight the four sub-scores with Day 14's
    role-specific weights to produce a fresh composite.
"""

from __future__ import annotations

import logging
from typing import Any

from utils.io_utils import safe_get

logger = logging.getLogger(__name__)


# Explicit alias paths tried in order. First non-None hit wins.
SCORE_KEY_ALIASES: dict[str, list[tuple[str, ...]]] = {
    # ats_score = the OVERALL/final ATS engine score
    "ats_score": [
        ("final_score",),
        ("ats_score",),
        ("scores", "ats_score"),
        ("scores", "overall"),
        ("scores", "total"),
        ("overall_score",),
        ("final_ats_score",),
        ("ats", "score"),
        ("match_score",),
    ],
    "skill_score": [
        ("scoring_breakdown", "skill_match"),     # Day 13 actual key
        ("skill_score",),
        ("scores", "skill_score"),
        ("skill_engine", "score"),
        ("skills", "score"),
    ],
    "experience_score": [
        ("scoring_breakdown", "experience_relevance"),  # Day 13 actual key
        ("experience_score",),
        ("scores", "experience_score"),
        ("experience_engine", "score"),
        ("experience", "score"),
    ],
    "education_score": [
        ("scoring_breakdown", "education_alignment"),   # Day 13 actual key
        ("education_score",),
        ("scores", "education_score"),
        ("education_engine", "score"),
        ("education", "score"),
    ],
    "semantic_score": [
        ("scoring_breakdown", "semantic_similarity"),   # Day 13 actual key
        ("semantic_score",),
        ("scores", "semantic_score"),
        ("semantic_engine", "score"),
    ],
}


def normalize_score(value: Any) -> float | None:
    """
    Normalize a score to the 0-100 scale.

    Accepts:
      - None / missing    -> None
      - 0.0 - 1.0 floats  -> scaled to 0-100
      - 0   - 100         -> passed through (clamped)
      - strings parseable as numbers
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return 0.0
    if 0.0 < v <= 1.0:
        v *= 100.0
    return min(100.0, v)


def extract_sub_scores(candidate: dict, debug: bool = False) -> dict[str, float | None]:
    """
    Pull every sub-score out of a candidate JSON, honouring all known aliases.

    Returns a dict with keys: ats_score, skill_score, experience_score,
    education_score, semantic_score. Missing values are None.
    """
    out: dict[str, float | None] = {}
    for score_name, alias_paths in SCORE_KEY_ALIASES.items():
        found = None
        hit_path = None
        for path in alias_paths:
            raw = safe_get(candidate, *path)
            if raw is not None:
                found = raw
                hit_path = path
                break
        out[score_name] = normalize_score(found)
        if debug and hit_path:
            logger.debug("  %s <- %s = %s", score_name, ".".join(hit_path), out[score_name])

    if debug and all(v is None for v in out.values()):
        logger.warning(
            "No scores extracted. Top-level keys present: %s",
            list(candidate.keys())[:20],
        )
    return out


def compute_composite_score(
    sub_scores: dict[str, float | None],
    weights: dict[str, float],
) -> tuple[float, dict[str, float]]:
    """
    Weighted sum of available sub-scores. Missing scores have their weight
    redistributed proportionally across the present scores.

    Returns:
        (composite_score_0_to_100, effective_weights_used)
    """
    present = {k: v for k, v in sub_scores.items() if v is not None and k in weights}
    if not present:
        return 0.0, {}

    total_weight = sum(weights[k] for k in present)
    if total_weight == 0:
        return 0.0, {}

    effective = {k: weights[k] / total_weight for k in present}
    composite = sum(present[k] * effective[k] for k in present)
    return round(composite, 2), {k: round(v, 4) for k, v in effective.items()}


def passthrough_score(candidate: dict) -> float | None:
    """Return Day 13's pre-computed final_score if present."""
    val = candidate.get("final_score")
    return normalize_score(val)
