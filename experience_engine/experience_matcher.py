import logging
from difflib import SequenceMatcher
from utils.role_utils import normalize_role, ROLE_SYNONYMS
from experience_engine.experience_parser import (
    calculate_total_experience,
    detect_gaps,
    detect_overlaps,
)

logger = logging.getLogger(__name__)

# ── Scoring weights ────────────────────────────────────────────────────
_ROLE_WEIGHT   = 5
_SKILL_WEIGHT  = 5
_DOMAIN_WEIGHT = 2
_EXP_WEIGHT    = 2

_DOMAIN_WORDS         = {"health", "clinical", "ehr", "emr", "hospital", "medical"}
_DOMAIN_HIT_THRESHOLD = 2


# ── Similarity helper ─────────────────────────────────────────────────
def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ── RELEVANCE SCORE ───────────────────────────────────────────────────
def experience_relevance_score(
    experiences: list,
    jd_roles: list | str,
    jd_skills: list | None = None,
) -> float:
    """
    Score how well a candidate's experience matches the JD.

    Components
    ----------
    ROLE  : Best fuzzy-match similarity between each JD role and any
            resume title (including synonym expansion). Weight = _ROLE_WEIGHT
            per JD role.
    SKILL : Fraction of JD skills found anywhere in resume text.
            Only included in max_score when jd_skills is supplied.
            Weight = _SKILL_WEIGHT.
    DOMAIN: Bonus when resume contains >= _DOMAIN_HIT_THRESHOLD domain
            words. Always added to max_score so non-domain resumes
            are penalised. Weight = _DOMAIN_WEIGHT.
    EXP   : Full weight when total experience >= 36 months.
            Weight = _EXP_WEIGHT.

    Returns a float in [0.0, 100.0].
    """
    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences:
        return 0.0

    resume_text = " ".join(
        f"{exp.get('job_title', '')} {exp.get('company', '')} {exp.get('raw_text', '')}"
        for exp in experiences
    ).lower()

    total_score = 0.0
    max_score   = 0.0

    # ── Role similarity ───────────────────────────────────────────────
    for jd_role in jd_roles:
        jd_norm    = normalize_role(jd_role)
        best_match = 0.0

        for exp in experiences:
            role = normalize_role(exp.get("job_title", ""))
            sim  = _similar(jd_norm, role)

            for syn in ROLE_SYNONYMS.get(jd_norm, []):
                sim = max(sim, _similar(syn, role))

            best_match = max(best_match, sim)

        total_score += best_match * _ROLE_WEIGHT
        max_score   += _ROLE_WEIGHT

    # ── Skill match ───────────────────────────────────────────────────
    if jd_skills:
        normalised_skills = [s.lower() for s in jd_skills]
        matched      = sum(1 for s in normalised_skills if s in resume_text)
        skill_ratio  = matched / len(normalised_skills)
        total_score += skill_ratio * _SKILL_WEIGHT
        max_score   += _SKILL_WEIGHT

    # ── Domain boost ──────────────────────────────────────────────────
    # max_score always increases so non-domain resumes are penalised
    domain_hits  = sum(1 for w in _DOMAIN_WORDS if w in resume_text)
    max_score   += _DOMAIN_WEIGHT
    if domain_hits >= _DOMAIN_HIT_THRESHOLD:
        total_score += _DOMAIN_WEIGHT

    # ── Experience depth ──────────────────────────────────────────────
    total_months = calculate_total_experience(experiences)
    max_score   += _EXP_WEIGHT
    if total_months >= 36:
        total_score += _EXP_WEIGHT

    if max_score == 0.0:
        return 0.0

    return round((total_score / max_score) * 100, 2)


# ── SUMMARY BUILDER ───────────────────────────────────────────────────
def build_experience_summary(
    experiences: list,
    jd_roles: list | str,
    jd_skills: list | None = None,
) -> dict:
    """
    Build the full experience summary dict consumed by the formatter.

    Timeline functions are imported from experience_parser — the single
    source of truth for all timeline logic.
    """
    return {
        "relevance_score":         experience_relevance_score(experiences, jd_roles, jd_skills),
        "total_experience_months": calculate_total_experience(experiences),
        "gaps":                    detect_gaps(experiences),
        "overlaps":                detect_overlaps(experiences),
    }
