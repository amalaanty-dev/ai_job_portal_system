import logging
from datetime import date
from utils.role_utils import normalize_role, ROLE_SYNONYMS
from utils.date_utils import calculate_months

logger = logging.getLogger(__name__)

# ── Scoring weights ───────────────────────────────────────────────────
_SCORE_DIRECT  = 3
_SCORE_SYNONYM = 2
_SCORE_KEYWORD = 1
_SCORE_SKILL   = 2   # NEW
_SCORE_DOMAIN  = 1   # NEW


# ── Helpers ───────────────────────────────────────────────────────────
def _safe_sort(experiences: list, label: str = "") -> list | None:
    try:
        return sorted(
            experiences,
            key=lambda x: date.fromisoformat(x["start_date"])
        )
    except Exception as e:
        logger.warning("⚠️ Could not sort experiences (%s): %s", label, e)
        return None


def _safe_dates(exp_a: dict, exp_b: dict) -> tuple | None:
    try:
        return (
            date.fromisoformat(exp_a["start_date"]),
            date.fromisoformat(exp_a["end_date"]),
            date.fromisoformat(exp_b["start_date"]),
            date.fromisoformat(exp_b["end_date"]),
        )
    except Exception:
        return None


# ── TOTAL EXPERIENCE ──────────────────────────────────────────────────
def calculate_total_experience(experiences: list) -> int:
    if not experiences:
        return 0

    intervals = []
    for exp in experiences:
        try:
            start = date.fromisoformat(exp["start_date"])
            end   = date.fromisoformat(exp["end_date"])
            intervals.append((start, end))
        except Exception:
            continue

    if not intervals:
        return 0

    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return sum(calculate_months(s, e) for s, e in merged)


# ── GAP DETECTION ─────────────────────────────────────────────────────
def detect_gaps(experiences: list, min_gap_months: int = 3) -> list:
    if len(experiences) < 2:
        return []

    sorted_exp = _safe_sort(experiences, "gaps")
    if not sorted_exp:
        return []

    gaps = []

    for i in range(1, len(sorted_exp)):
        dates = _safe_dates(sorted_exp[i - 1], sorted_exp[i])
        if not dates:
            continue

        a_start, a_end, b_start, b_end = dates
        gap_months = calculate_months(a_end, b_start)

        if gap_months >= min_gap_months:
            gaps.append({
                "gap_start": a_end.isoformat(),
                "gap_end": b_start.isoformat(),
                "gap_months": gap_months
            })

    return gaps


# ── OVERLAP DETECTION ─────────────────────────────────────────────────
def detect_overlaps(experiences: list) -> list:
    if len(experiences) < 2:
        return []

    sorted_exp = _safe_sort(experiences, "overlaps")
    if not sorted_exp:
        return []

    overlaps = []

    for i in range(len(sorted_exp)):
        for j in range(i + 1, len(sorted_exp)):
            dates = _safe_dates(sorted_exp[i], sorted_exp[j])
            if not dates:
                continue

            a_start, a_end, b_start, b_end = dates

            if b_start < a_end:
                overlap_start = max(a_start, b_start)
                overlap_end   = min(a_end, b_end)
                overlap_months = calculate_months(overlap_start, overlap_end)

                if overlap_months > 0:
                    overlaps.append({
                        "role_a": sorted_exp[i]["job_title"],
                        "company_a": sorted_exp[i]["company"],
                        "role_b": sorted_exp[j]["job_title"],
                        "company_b": sorted_exp[j]["company"],
                        "overlap_months": overlap_months
                    })

    return overlaps


# ── 🔥 ADVANCED RELEVANCE SCORING ─────────────────────────────────────
def experience_relevance_score(experiences: list, jd_roles: list | str, jd_skills: list | None = None) -> float:

    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences:
        return 0.0

    # ── Build resume corpus ─────────────────────────────
    resume_text = " ".join([
        f"{exp.get('job_title','')} {exp.get('company','')} {exp.get('raw_text','')}"
        for exp in experiences
    ]).lower()

    total_score = 0
    max_score   = 0

    # ── ROLE MATCH ─────────────────────────────────────
    for role in jd_roles:
        role_norm = normalize_role(role)
        role_score = 0

        if role_norm in resume_text:
            role_score = _SCORE_DIRECT

        else:
            synonyms = ROLE_SYNONYMS.get(role_norm, [])

            if any(normalize_role(s) in resume_text for s in synonyms):
                role_score = _SCORE_SYNONYM

            elif any(word in resume_text for word in role_norm.split()):
                role_score = _SCORE_KEYWORD

        total_score += role_score
        max_score   += _SCORE_DIRECT

    # ── 🔥 SKILL MATCH BOOST ───────────────────────────
    if jd_skills:
        jd_skills = [s.lower() for s in jd_skills]

        matches = sum(1 for skill in jd_skills if skill in resume_text)

        if jd_skills:
            skill_score = matches / len(jd_skills)
            total_score += skill_score * _SCORE_SKILL
            max_score   += _SCORE_SKILL

    # ── 🔥 DOMAIN BOOST ────────────────────────────────
    healthcare_keywords = [
        "health", "clinical", "ehr", "emr",
        "hospital", "patient", "medical"
    ]

    if any(word in resume_text for word in healthcare_keywords):
        total_score += _SCORE_DOMAIN
        max_score   += _SCORE_DOMAIN

    if max_score == 0:
        return 0.0

    return round((total_score / max_score) * 100, 2)


# ── FINAL SUMMARY BUILDER ─────────────────────────────────────────────
def build_experience_summary(experiences: list, jd_roles: list | str, jd_skills: list | None = None) -> dict:

    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences:
        logger.warning("⚠️ Empty experiences passed")
        return {
            "relevance_score": 0.0,
            "total_experience_months": 0,
            "gaps": [],
            "overlaps": []
        }

    relevance_score = experience_relevance_score(experiences, jd_roles, jd_skills)

    return {
        "relevance_score": relevance_score,
        "total_experience_months": calculate_total_experience(experiences),
        "gaps": detect_gaps(experiences),
        "overlaps": detect_overlaps(experiences)
    }