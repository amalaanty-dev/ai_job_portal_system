import logging
from datetime import date
from difflib import SequenceMatcher
from utils.role_utils import normalize_role, ROLE_SYNONYMS
from utils.date_utils import calculate_months

logger = logging.getLogger(__name__)

# ── Scoring weights (TUNED FOR STRONG MATCH) ──────────────────────────
_ROLE_WEIGHT   = 5
_SKILL_WEIGHT  = 5
_DOMAIN_WEIGHT = 2
_EXP_WEIGHT    = 2


# ── Similarity Function ───────────────────────────────────────────────
def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


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
        except:
            continue

    if not intervals:
        return 0

    intervals.sort()
    merged = [intervals[0]]

    for s, e in intervals[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))

    return sum(calculate_months(s, e) for s, e in merged)


# ── GAP DETECTION ─────────────────────────────────────────────────────
def detect_gaps(experiences: list, min_gap_months: int = 3) -> list:
    if len(experiences) < 2:
        return []

    experiences = sorted(experiences, key=lambda x: x["start_date"])

    gaps = []

    for i in range(1, len(experiences)):
        prev_end = date.fromisoformat(experiences[i - 1]["end_date"])
        curr_start = date.fromisoformat(experiences[i]["start_date"])

        gap = calculate_months(prev_end, curr_start)

        if gap >= min_gap_months:
            gaps.append({
                "gap_start": prev_end.isoformat(),
                "gap_end": curr_start.isoformat(),
                "gap_months": gap
            })

    return gaps


# ── OVERLAPS ──────────────────────────────────────────────────────────
def detect_overlaps(experiences: list) -> list:
    overlaps = []

    for i in range(len(experiences)):
        for j in range(i + 1, len(experiences)):

            a = experiences[i]
            b = experiences[j]

            a_start = date.fromisoformat(a["start_date"])
            a_end   = date.fromisoformat(a["end_date"])
            b_start = date.fromisoformat(b["start_date"])
            b_end   = date.fromisoformat(b["end_date"])

            if b_start < a_end:
                overlap = calculate_months(max(a_start, b_start), min(a_end, b_end))

                if overlap > 0:
                    overlaps.append({
                        "role_a": a["job_title"],
                        "role_b": b["job_title"],
                        "overlap_months": overlap
                    })

    return overlaps


# ── 🔥 STRONG RELEVANCE ENGINE ────────────────────────────────────────
def experience_relevance_score(experiences, jd_roles, jd_skills=None):

    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences:
        return 0.0

    resume_text = " ".join([
        f"{exp.get('job_title','')} {exp.get('company','')} {exp.get('raw_text','')}"
        for exp in experiences
    ]).lower()

    total_score = 0
    max_score   = 0

    # ── 🔥 ROLE SIMILARITY (MAJOR FIX) ─────────────────
    for jd_role in jd_roles:

        jd_norm = normalize_role(jd_role)

        best_match = 0

        for exp in experiences:
            role = normalize_role(exp.get("job_title", ""))

            sim = _similar(jd_norm, role)

            # Check synonyms also
            for syn in ROLE_SYNONYMS.get(jd_norm, []):
                sim = max(sim, _similar(syn, role))

            best_match = max(best_match, sim)

        role_score = best_match * _ROLE_WEIGHT
        total_score += role_score
        max_score   += _ROLE_WEIGHT

    # ── 🔥 SKILL MATCH (HIGH IMPACT) ───────────────────
    if jd_skills:
        jd_skills = [s.lower() for s in jd_skills]

        matched = sum(1 for s in jd_skills if s in resume_text)

        skill_ratio = matched / len(jd_skills) if jd_skills else 0

        total_score += skill_ratio * _SKILL_WEIGHT
        max_score   += _SKILL_WEIGHT

    # ── 🔥 DOMAIN BOOST ────────────────────────────────
    domain_words = ["health", "clinical", "ehr", "emr", "hospital", "medical"]

    domain_hits = sum(1 for w in domain_words if w in resume_text)

    if domain_hits >= 2:
        total_score += _DOMAIN_WEIGHT
        max_score   += _DOMAIN_WEIGHT

    # ── 🔥 EXPERIENCE WEIGHT ───────────────────────────
    total_months = calculate_total_experience(experiences)

    if total_months >= 36:
        total_score += _EXP_WEIGHT
    max_score += _EXP_WEIGHT

    if max_score == 0:
        return 0.0

    return round((total_score / max_score) * 100, 2)


# ── FINAL BUILDER ─────────────────────────────────────────────────────
def build_experience_summary(experiences, jd_roles, jd_skills=None):

    return {
        "relevance_score": experience_relevance_score(experiences, jd_roles, jd_skills),
        "total_experience_months": calculate_total_experience(experiences),
        "gaps": detect_gaps(experiences),
        "overlaps": detect_overlaps(experiences)
    }