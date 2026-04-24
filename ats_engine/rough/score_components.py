"""
score_components.py
Individual scoring functions for each ATS dimension.

Each function accepts the raw parsed JSON (or None if missing) and returns:
{
    "score":      float (0–100),
    "raw_inputs": dict  (data used in computation),
    "breakdown":  dict  (sub-scores / notes),
    "data_available": bool,
    "missing_fields": list[str],
}
"""

from typing import Optional


# ─── 1. SKILL MATCH ──────────────────────────────────────────────────────────

def compute_skill_score(data: Optional[dict]) -> dict:
    """
    Score based on skills JSON (*_skills.json).
    Uses confidence-weighted average across all detected skills.
    Bonus for breadth (tech + business + domain).
    """
    if not data:
        return _empty_result("skill_match", ["skills_json"])

    skills = data.get("skills", [])
    if not skills:
        return _empty_result("skill_match", ["skills list empty"])

    # ── Confidence-weighted average ─────────────────────────────────────────
    total_confidence = sum(s.get("confidence", 0) for s in skills)
    avg_confidence   = total_confidence / len(skills) if skills else 0

    # ── Category diversity bonus ─────────────────────────────────────────────
    categories = {s.get("category", "other") for s in skills}
    diversity_bonus = min(len(categories) * 3, 12)   # up to +12 pts

    # ── High-value skill bonus ────────────────────────────────────────────────
    high_value = {"python", "sql", "machine learning", "deep learning",
                  "nlp", "tensorflow", "pytorch", "spark", "airflow",
                  "kubernetes", "docker", "llm", "transformers"}
    present_hv = [s["skill"] for s in skills
                  if s.get("skill", "").lower() in high_value]
    hv_bonus = min(len(present_hv) * 2, 10)

    raw_score = avg_confidence * 100
    final = min(raw_score + diversity_bonus + hv_bonus, 100)

    return {
        "score":          round(final, 2),
        "data_available": True,
        "missing_fields": [],
        "raw_inputs": {
            "total_skills":  len(skills),
            "avg_confidence": round(avg_confidence, 3),
            "categories":    sorted(categories),
        },
        "breakdown": {
            "base_score":       round(raw_score, 2),
            "diversity_bonus":  diversity_bonus,
            "high_value_bonus": hv_bonus,
            "high_value_skills_found": present_hv,
        },
    }


# ─── 2. EDUCATION ALIGNMENT ──────────────────────────────────────────────────

def compute_education_score(data: Optional[dict]) -> dict:
    """
    Score based on sections JSON (*_sections.json → education_data).
    Uses education_strength, degree level, and certification count.
    """
    if not data:
        return _empty_result("education_alignment", ["sections_json"])

    edu_data = data.get("education_data", {})
    if not edu_data:
        return _empty_result("education_alignment", ["education_data key missing"])

    missing = []

    # ── Pre-computed strength ─────────────────────────────────────────────────
    academic  = edu_data.get("academic_profile", {})
    strength  = academic.get("education_strength", None)
    if strength is None:
        missing.append("education_strength")
        strength = 0

    # ── Degree level bonus ─────────────────────────────────────────────────
    degree_bonuses = {"phd": 20, "doctorate": 20, "mba": 12,
                      "msc": 12, "ms": 12, "master": 12,
                      "bsc": 5,  "bba": 5,  "bachelor": 5, "be": 5}
    highest = (academic.get("highest_degree") or "").lower()
    deg_bonus = degree_bonuses.get(highest, 0)

    # ── Certification bonus ────────────────────────────────────────────────
    cert_count  = academic.get("certification_count", 0) or 0
    cert_bonus  = min(cert_count * 5, 15)

    # ── Relevance score (pre-computed) ────────────────────────────────────
    relevance   = data.get("education_relevance_score", 0) or 0

    # ── Composite ─────────────────────────────────────────────────────────
    base   = strength * 0.5 + relevance * 0.5
    final  = min(base + deg_bonus * 0.3 + cert_bonus, 100)

    return {
        "score":          round(final, 2),
        "data_available": True,
        "missing_fields": missing,
        "raw_inputs": {
            "education_strength":      strength,
            "education_relevance_score": relevance,
            "highest_degree":          highest,
            "cert_count":              cert_count,
            "total_degrees":           academic.get("total_degrees", 0),
        },
        "breakdown": {
            "base_score":      round(base, 2),
            "degree_bonus":    round(deg_bonus * 0.3, 2),
            "cert_bonus":      cert_bonus,
        },
    }


# ─── 3. EXPERIENCE RELEVANCE ─────────────────────────────────────────────────

def compute_experience_score(data: Optional[dict]) -> dict:
    """
    Score based on experience JSON (*_experience.json).
    Uses overall_relevance_score, tenure, recency, and role progression.
    """
    if not data:
        return _empty_result("experience_relevance", ["experience_json"])

    missing = []

    summary    = data.get("experience_summary", {})
    roles      = data.get("roles", [])
    rel_analysis = data.get("relevance_analysis", {})

    total_months = summary.get("total_experience_months", None)
    if total_months is None:
        missing.append("total_experience_months")
        total_months = 0

    relevance_score = rel_analysis.get("overall_relevance_score", None)
    if relevance_score is None:
        missing.append("overall_relevance_score")
        relevance_score = 0

    # ── Experience tenure score (logarithmic) ─────────────────────────────
    # 0 months→0, 12→25, 36→50, 60→65, 120→80, 180→90
    import math
    tenure_score = min(math.log1p(total_months) / math.log1p(180) * 90, 90)

    # ── Recency bonus: latest role's recency (end date proximity to now) ──
    recency_bonus = 0
    if roles:
        latest = sorted(roles, key=lambda r: r.get("end_date", ""), reverse=True)[0]
        end = latest.get("end_date", "")
        if end and end >= "2023":
            recency_bonus = 10
        elif end and end >= "2021":
            recency_bonus = 5

    # ── Gap penalty ────────────────────────────────────────────────────────
    timeline = data.get("timeline_analysis", {})
    gaps     = timeline.get("gaps", [])
    gap_penalty = len(gaps) * 3

    # ── Composite ─────────────────────────────────────────────────────────
    # Weight: 60% pre-computed relevance, 25% tenure, 15% recency - gaps
    final = (
        relevance_score * 0.60
        + tenure_score  * 0.25
        + recency_bonus * 0.15
        - gap_penalty
    )
    final = max(0, min(final, 100))

    return {
        "score":          round(final, 2),
        "data_available": True,
        "missing_fields": missing,
        "raw_inputs": {
            "total_months":          total_months,
            "total_roles":           len(roles),
            "overall_relevance_score": relevance_score,
            "timeline_gaps":         len(gaps),
            "latest_role_end":       roles[0].get("end_date", "N/A") if roles else "N/A",
        },
        "breakdown": {
            "relevance_component":  round(relevance_score * 0.60, 2),
            "tenure_component":     round(tenure_score   * 0.25, 2),
            "recency_bonus":        recency_bonus,
            "gap_penalty":          gap_penalty,
        },
    }


# ─── 4. SEMANTIC SIMILARITY ──────────────────────────────────────────────────

def compute_semantic_score(data: Optional[dict]) -> dict:
    """
    Score based on semantic JSON (*_sections_semantic.json).
    Uses section scores and best-match semantic score.
    """
    if not data:
        return _empty_result("semantic_similarity", ["semantic_json"])

    missing = []

    section_scores = data.get("section_scores", {})
    best_match     = data.get("best_match", {})

    best_sem_score = best_match.get("semantic_score", None)
    if best_sem_score is None:
        missing.append("semantic_score")
        best_sem_score = 0

    # ── Section-level contributions ───────────────────────────────────────
    skills_sem   = section_scores.get("skills",           0)
    exp_sem      = section_scores.get("experience_summary", 0)
    proj_sem     = section_scores.get("projects",          0)
    edu_sem      = section_scores.get("education",         0)
    full_doc_sem = section_scores.get("full_document",     0)

    # Weighted blend of section scores
    section_blend = (
        skills_sem   * 0.25
        + exp_sem    * 0.20
        + proj_sem   * 0.20
        + edu_sem    * 0.10
        + full_doc_sem * 0.25
    )

    # ── Final: blend best_match semantic + section blend ──────────────────
    final = best_sem_score * 0.50 + section_blend * 0.50

    return {
        "score":          round(min(final, 100), 2),
        "data_available": True,
        "missing_fields": missing,
        "raw_inputs": {
            "best_match_jd":        best_match.get("jd_title", "N/A"),
            "best_semantic_score":  best_sem_score,
            "section_scores":       section_scores,
        },
        "breakdown": {
            "best_match_component": round(best_sem_score * 0.50, 2),
            "section_blend":        round(section_blend  * 0.50, 2),
            "section_weights": {
                "skills":            0.25, "experience_summary": 0.20,
                "projects":          0.20, "education":           0.10,
                "full_document":     0.25,
            },
        },
    }


# ─── Utility ──────────────────────────────────────────────────────────────────

def _empty_result(component: str, missing_fields: list) -> dict:
    return {
        "score":          0.0,
        "data_available": False,
        "missing_fields": missing_fields,
        "raw_inputs":     {},
        "breakdown":      {"note": f"No data for {component}; score defaulted to 0."},
    }
