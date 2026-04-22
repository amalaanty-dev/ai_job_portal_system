"""
semantic_engine/similarity.py
──────────────────────────────
Cosine similarity utilities and section-level similarity computation.

FIXES in this version
─────────────────────
1. weighted_similarity() now accepts an optional `populated` dict.
   Sections that are genuinely empty (not populated) have their weight
   redistributed to the remaining populated sections proportionally.
   This prevents zero-filled empty sections from dragging down the
   overall score just because they were absent from the resume JSON.

2. identify_gaps() now accepts an `exclude_empty` parameter — genuinely
   empty sections (projects, education, certifications) are reported as
   "missing" rather than "critical gap", since they may simply not apply.

3. similarity_label() thresholds are calibrated for TF-IDF output range.
   TF-IDF cosine scores are typically in [0.15, 0.65] for real matches
   (not [0, 1] like sentence-transformer scores). Thresholds have been
   adjusted so labels are meaningful at this scale.

4. DEFAULT_WEIGHTS updated: education and certifications weight reduced
   for general matching; skills and experience raised.
"""

import numpy as np
from typing import Union


# ═══════════════════════════════════════════════════════════════
# CORE SIMILARITY
# ═══════════════════════════════════════════════════════════════

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Cosine similarity between two L2-normalised vectors.
    Returns float in [0, 1].
    """
    if vec_a is None or vec_b is None:
        return 0.0
    if vec_a.shape != vec_b.shape:
        return 0.0
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    score = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    return max(0.0, min(1.0, score))


def cosine_matrix(matrix_a: np.ndarray, matrix_b: np.ndarray) -> np.ndarray:
    """
    Pairwise cosine similarity between rows of two matrices.
    matrix_a: (M, D), matrix_b: (N, D) → returns (M, N)
    """
    norm_a = np.linalg.norm(matrix_a, axis=1, keepdims=True) + 1e-10
    norm_b = np.linalg.norm(matrix_b, axis=1, keepdims=True) + 1e-10
    return np.dot(matrix_a / norm_a, (matrix_b / norm_b).T).clip(0, 1)


# ═══════════════════════════════════════════════════════════════
# SECTION SIMILARITY
# ═══════════════════════════════════════════════════════════════

def section_similarity(
    resume_vec: np.ndarray,
    jd_vec:     np.ndarray,
    label:      str = "",
) -> dict:
    """
    Compare a single resume section vector to a single JD section vector.
    """
    score = cosine_similarity(resume_vec, jd_vec)
    confidence = (
        "high"   if score >= 0.55 else     # FIX: recalibrated for TF-IDF range
        "medium" if score >= 0.35 else
        "low"
    )
    return {
        "label":      label,
        "score":      round(score, 4),
        "confidence": confidence,
    }


def cross_section_similarity(
    resume_vec: np.ndarray,
    jd_vecs:    list,
    jd_labels:  list,
) -> dict:
    """
    Compare one resume section against multiple JD sections.
    Returns the best-matching JD section.
    """
    best_score = 0.0
    best_label = ""
    all_scores = {}

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

# FIX: Higher weights on skills + experience; reduced education/certs
# so that resumes missing those sections are not crushed.
DEFAULT_WEIGHTS = {
    "skills":             0.38,
    "experience_summary": 0.35,
    "projects":           0.15,
    "education":          0.07,
    "certifications":     0.05,
}


def weighted_similarity(
    section_scores: dict,
    weights:        dict | None = None,
    populated:      dict | None = None,   # FIX: new parameter
) -> float:
    """
    Compute a weighted aggregate similarity score.

    Args:
        section_scores : {section_name: similarity_score}
        weights        : {section_name: weight}  (should sum to 1.0)
        populated      : {section_name: bool} — if provided, sections where
                         populated=False have their weight redistributed to
                         populated sections proportionally. This prevents
                         genuinely missing sections (empty [] in JSON) from
                         dragging the score to zero.

    Returns:
        float in [0, 1]
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # ── FIX: redistribute weight away from genuinely empty sections ──
    if populated is not None:
        effective_weights = {}
        orphan_weight     = 0.0

        for section, w in weights.items():
            if populated.get(section, True):
                effective_weights[section] = w
            else:
                orphan_weight += w          # weight to redistribute

        # Spread orphan weight proportionally over populated sections
        if orphan_weight > 0 and effective_weights:
            scale = 1.0 + orphan_weight / sum(effective_weights.values())
            effective_weights = {s: w * scale for s, w in effective_weights.items()}
        elif orphan_weight > 0:
            effective_weights = weights     # fallback: all empty, use original
    else:
        effective_weights = weights

    total_weight = 0.0
    total_score  = 0.0

    for section, score in section_scores.items():
        w             = effective_weights.get(section, 0.0)
        total_score  += score * w
        total_weight += w

    if total_weight == 0:
        return 0.0

    return round(total_score / total_weight, 4)


# ═══════════════════════════════════════════════════════════════
# SIMILARITY LABEL
# ═══════════════════════════════════════════════════════════════

# FIX: TF-IDF cosine scores for genuine matches typically fall in [0.20, 0.65].
# The original thresholds (0.75 / 0.55 / 0.40 / 0.25) were calibrated for
# sentence-transformer output (dense, high-similarity range).
# These recalibrated thresholds produce meaningful labels for TF-IDF output.
TFIDF_THRESHOLDS = {
    "strong_match":  0.55,    # was 0.75
    "good_match":    0.40,    # was 0.55
    "partial_match": 0.28,    # was 0.40
    "weak_match":    0.18,    # was 0.25
}


def similarity_label(score: float, thresholds: dict | None = None) -> str:
    """
    Convert a numeric similarity score to a human-readable label.

    Calibrated thresholds for TF-IDF cosine scores:
        ≥ 0.55  → Strong Match
        ≥ 0.40  → Good Match
        ≥ 0.28  → Partial Match
        ≥ 0.18  → Weak Match
        <  0.18 → Mismatch

    Pass custom thresholds to override (e.g. when using a sentence transformer).
    """
    if thresholds is None:
        thresholds = TFIDF_THRESHOLDS

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
# GAP ANALYSIS
# ═══════════════════════════════════════════════════════════════

def identify_gaps(
    section_scores: dict,
    threshold:      float = 0.35,          # FIX: lowered from 0.45 to match TF-IDF range
    populated:      dict | None = None,    # FIX: distinguish missing vs low-scoring
) -> list:
    """
    Return sections that fall below the given threshold, sorted by severity.

    Args:
        section_scores : {section_name: score}
        threshold      : sections below this are flagged as gaps
        populated      : if provided, unpopulated sections are labelled
                         "missing" instead of "critical"

    Returns:
        list of {"section", "score", "gap_severity"}
    """
    gaps = []
    for section, score in section_scores.items():
        if score < threshold:
            # FIX: distinguish truly missing sections from genuinely poor matches
            if populated is not None and not populated.get(section, True):
                severity = "missing"
            else:
                severity = (
                    "critical" if score < 0.18 else
                    "moderate" if score < 0.28 else
                    "minor"
                )
            gaps.append({
                "section":      section,
                "score":        round(score, 4),
                "gap_severity": severity,
            })

    return sorted(gaps, key=lambda x: x["score"])
