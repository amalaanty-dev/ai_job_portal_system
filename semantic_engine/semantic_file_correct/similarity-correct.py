"""
semantic_engine/similarity.py
──────────────────────────────
Cosine similarity utilities and section-level similarity computation.

Design:
  • cosine_similarity()        — raw 0–1 score between two vectors
  • section_similarity()       — compare one resume section to one JD section
  • cross_section_similarity() — best-match across multiple JD sections
  • weighted_similarity()      — weighted aggregate of section scores
"""

import numpy as np
from typing import Union


# ═══════════════════════════════════════════════════════════════
# CORE SIMILARITY
# ═══════════════════════════════════════════════════════════════

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Cosine similarity between two vectors.
    Returns float in [0, 1].  (vectors assumed L2-normalised → dot product = cosine)
    """
    if vec_a is None or vec_b is None:
        return 0.0
    if vec_a.shape != vec_b.shape:
        return 0.0
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    # Since embedder normalises to unit length, this is just the dot product
    score = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    return max(0.0, min(1.0, score))   # clamp to [0,1]


def cosine_matrix(matrix_a: np.ndarray, matrix_b: np.ndarray) -> np.ndarray:
    """
    Pairwise cosine similarity between rows of two matrices.
    matrix_a: (M, D), matrix_b: (N, D)
    Returns: (M, N) similarity matrix
    """
    # Normalise rows
    norm_a = np.linalg.norm(matrix_a, axis=1, keepdims=True) + 1e-10
    norm_b = np.linalg.norm(matrix_b, axis=1, keepdims=True) + 1e-10
    a_norm = matrix_a / norm_a
    b_norm = matrix_b / norm_b
    return np.dot(a_norm, b_norm.T).clip(0, 1)


# ═══════════════════════════════════════════════════════════════
# SECTION SIMILARITY
# ═══════════════════════════════════════════════════════════════

def section_similarity(
    resume_vec:  np.ndarray,
    jd_vec:      np.ndarray,
    label:       str = "",
) -> dict:
    """
    Compare a single resume section vector to a single JD section vector.

    Returns:
        {
            "label":       section label for reporting,
            "score":       float cosine similarity,
            "confidence":  "high" / "medium" / "low"
        }
    """
    score = cosine_similarity(resume_vec, jd_vec)
    confidence = (
        "high"   if score >= 0.70 else
        "medium" if score >= 0.45 else
        "low"
    )
    return {
        "label":      label,
        "score":      round(score, 4),
        "confidence": confidence,
    }


def cross_section_similarity(
    resume_vec:  np.ndarray,
    jd_vecs:     list[np.ndarray],
    jd_labels:   list[str],
) -> dict:
    """
    Compare one resume section against multiple JD sections.
    Returns the best-matching JD section.

    Useful for: matching resume skills → (JD required_skills OR preferred_skills).
    """
    best_score  = 0.0
    best_label  = ""
    all_scores  = {}

    for vec, label in zip(jd_vecs, jd_labels):
        score = cosine_similarity(resume_vec, vec)
        all_scores[label] = round(score, 4)
        if score > best_score:
            best_score = score
            best_label = label

    return {
        "best_match_section": best_label,
        "best_score":         round(best_score, 4),
        "all_scores":         all_scores,
    }


# ═══════════════════════════════════════════════════════════════
# WEIGHTED AGGREGATE
# ═══════════════════════════════════════════════════════════════

# Default section weights for resume ↔ JD matching
DEFAULT_WEIGHTS = {
    "skills":             0.35,
    "experience_summary": 0.30,
    "projects":           0.20,
    "education":          0.10,
    "certifications":     0.05,
}


def weighted_similarity(
    section_scores: dict[str, float],
    weights:        dict[str, float] | None = None,
) -> float:
    """
    Compute a weighted aggregate similarity score.

    Args:
        section_scores: {section_name: similarity_score}
        weights:        {section_name: weight}  (must sum to 1.0)

    Returns:
        float in [0, 1]
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total_weight = 0.0
    total_score  = 0.0

    for section, score in section_scores.items():
        w = weights.get(section, 0.0)
        total_score  += score * w
        total_weight += w

    if total_weight == 0:
        return 0.0

    return round(total_score / total_weight, 4)


# ═══════════════════════════════════════════════════════════════
# SIMILARITY LABEL  (human-readable)
# ═══════════════════════════════════════════════════════════════

def similarity_label(score: float, thresholds: dict | None = None) -> str:
    """
    Convert a numeric similarity score to a human-readable label.

    Default thresholds (tunable via threshold_tuner.py):
        ≥ 0.75  → Strong Match
        ≥ 0.55  → Good Match
        ≥ 0.40  → Partial Match
        ≥ 0.25  → Weak Match
        <  0.25 → Mismatch
    """
    if thresholds is None:
        thresholds = {
            "strong_match":  0.75,
            "good_match":    0.55,
            "partial_match": 0.40,
            "weak_match":    0.25,
        }

    if score >= thresholds["strong_match"]:
        return "Strong Match"
    if score >= thresholds["good_match"]:
        return "Good Match"
    if score >= thresholds["partial_match"]:
        return "Partial Match"
    if score >= thresholds["weak_match"]:
        return "Weak Match"
    return "Mismatch"


# ═══════════════════════════════════════════════════════════════
# GAP ANALYSIS  (identify weak sections)
# ═══════════════════════════════════════════════════════════════

def identify_gaps(
    section_scores: dict[str, float],
    threshold:      float = 0.45,
) -> list[dict]:
    """
    Return sections that fall below the given threshold,
    sorted by severity (lowest score first).

    Returns:
        list of {"section": str, "score": float, "gap_severity": str}
    """
    gaps = []
    for section, score in section_scores.items():
        if score < threshold:
            severity = (
                "critical" if score < 0.25 else
                "moderate" if score < 0.35 else
                "minor"
            )
            gaps.append({
                "section":      section,
                "score":        round(score, 4),
                "gap_severity": severity,
            })

    return sorted(gaps, key=lambda x: x["score"])
