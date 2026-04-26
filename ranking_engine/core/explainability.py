"""
explainability.py
------------------
Generate human-readable explanations for each ranked candidate.

Every recruiter action (shortlist / review / reject) needs to be defensible.
This module produces a short `explanation` field answering: "why this
score and this zone?".
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


_SCORE_LABELS = {
    "ats_score":        "ATS match",
    "skill_score":      "Skill match",
    "experience_score": "Experience",
    "education_score":  "Education",
}


def _top_contributors(candidate: dict, k: int = 3) -> list[str]:
    """Return the top-k contributing sub-scores, weighted by effective weights."""
    subs = candidate.get("sub_scores", {})
    weights = candidate.get("effective_weights", {})
    contribs = []
    for name, score in subs.items():
        w = weights.get(name, 0)
        contribs.append((name, score, score * w))
    contribs.sort(key=lambda x: x[2], reverse=True)
    return [
        f"{_SCORE_LABELS.get(n, n)}={s:.0f}"
        for n, s, _ in contribs[:k]
    ]


def build_explanation(candidate: dict, thresholds: dict[str, float]) -> str:
    """Build a one-line explanation for this candidate's outcome."""
    zone = candidate.get("zone", "unknown")
    final = candidate.get("final_score", 0.0)
    top = ", ".join(_top_contributors(candidate))

    if candidate.get("hard_filter_failed"):
        reasons = candidate.get("rejection_reasons", [])
        return f"Auto-rejected (hard filter): {'; '.join(reasons)}"

    if zone == "shortlisted":
        return (f"Shortlisted: final={final} >= {thresholds['shortlist']}. "
                f"Top drivers: {top}.")
    if zone == "review":
        return (f"Review: final={final} between {thresholds['review']} and "
                f"{thresholds['shortlist']}. Top drivers: {top}.")
    return (f"Rejected: final={final} < {thresholds['review']}. "
            f"Top drivers: {top}.")


def annotate_explanations(
    candidates: list[dict],
    thresholds: dict[str, float],
) -> list[dict]:
    """Attach `explanation` to every candidate in-place. Returns the list."""
    for c in candidates:
        c["explanation"] = build_explanation(c, thresholds)
    return candidates
