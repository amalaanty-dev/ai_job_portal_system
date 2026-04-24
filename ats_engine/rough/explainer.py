"""
explainer.py
Generates a structured, human-readable explanation of the ATS score.
"""

from typing import Dict, List


COMPONENT_LABELS = {
    "skill_match":         "Skill Match",
    "education_alignment": "Education Alignment",
    "experience_relevance":"Experience Relevance",
    "semantic_similarity": "Semantic Similarity",
}


def build_explanation(
    components: Dict[str, dict],
    weights: Dict[str, float],
    composite_score: float,
    gaps: List[dict],
) -> dict:
    """
    Return a structured explanation dict with:
    - summary_text        : one-line plain English summary
    - component_summaries : per-component human-readable notes
    - scoring_formula     : formula description
    - gap_notes           : gap-specific recommendations
    - improvement_tips    : top 3 actionable improvements
    """

    # ── Per-component summaries ───────────────────────────────────────────────
    component_summaries = {}
    for key, comp in components.items():
        label  = COMPONENT_LABELS.get(key, key)
        score  = comp["score"]
        weight = weights.get(key, 0)
        avail  = comp["data_available"]

        if not avail:
            note = f"⚠️  No data found for {label}. Score defaulted to 0."
        elif score >= 70:
            note = f"✅ Strong {label} ({score:.1f}/100). This dimension is a positive signal."
        elif score >= 50:
            note = f"👍 Moderate {label} ({score:.1f}/100). Acceptable but room for improvement."
        elif score >= 30:
            note = f"⚠️  Weak {label} ({score:.1f}/100). Needs targeted improvement."
        else:
            note = f"❌ Critical gap in {label} ({score:.1f}/100). High-priority action required."

        component_summaries[key] = {
            "label":  label,
            "score":  score,
            "weight": weight,
            "weighted_contribution": round(score * weight, 2),
            "note":   note,
        }

    # ── Scoring formula ────────────────────────────────────────────────────────
    total_weight = sum(weights.values())
    formula_parts = [
        f"({comp['score']:.1f} × {weights.get(k, 0):.2f})"
        for k, comp in components.items()
    ]
    formula = (
        "Composite = ("
        + " + ".join(formula_parts)
        + f") / {total_weight:.2f}"
        + f" = {composite_score:.2f}"
    )

    # ── Gap notes ─────────────────────────────────────────────────────────────
    gap_notes = [
        {
            "section":  g["section"],
            "severity": g["severity"],
            "action":   g["recommendation"],
        }
        for g in gaps
    ]

    # ── Improvement tips (top 3 by lowest score) ──────────────────────────────
    ranked = sorted(components.items(), key=lambda x: x[1]["score"])
    tips = []
    for key, comp in ranked[:3]:
        tips.append({
            "priority": len(tips) + 1,
            "area":     COMPONENT_LABELS.get(key, key),
            "current_score": comp["score"],
            "tip":      _tip_for(key, comp),
        })

    # ── Summary text ─────────────────────────────────────────────────────────
    top_strength = max(components.items(), key=lambda x: x[1]["score"])
    top_gap      = ranked[0]
    summary_text = (
        f"Composite ATS score: {composite_score:.1f}/100. "
        f"Strongest dimension: {COMPONENT_LABELS.get(top_strength[0])} "
        f"({top_strength[1]['score']:.1f}/100). "
        f"Key gap: {COMPONENT_LABELS.get(top_gap[0])} "
        f"({top_gap[1]['score']:.1f}/100)."
    )

    return {
        "summary_text":        summary_text,
        "component_summaries": component_summaries,
        "scoring_formula":     formula,
        "gap_notes":           gap_notes,
        "improvement_tips":    tips,
    }


def _tip_for(key: str, comp: dict) -> str:
    tips = {
        "skill_match": (
            "Add missing technical skills via portfolio projects or "
            "targeted online courses. Tailor skills section to mirror JD keywords."
        ),
        "education_alignment": (
            "Pursue relevant certifications (e.g., domain-specific courses, "
            "Google/Coursera certificates). List all credentials explicitly."
        ),
        "experience_relevance": (
            "Reframe existing experience using JD terminology. Add quantified "
            "achievements and domain-relevant project descriptions."
        ),
        "semantic_similarity": (
            "Review the job description carefully and incorporate its exact "
            "phrases into your resume summary, skills, and work experience sections."
        ),
    }
    return tips.get(key, "Review and strengthen this section.")
