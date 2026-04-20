import logging
from datetime import date
from utils.role_utils import normalize_role, ROLE_SYNONYMS
from utils.date_utils import calculate_months

logger = logging.getLogger(__name__)

# ── Scoring tier weights ──────────────────────────────────────────────
_SCORE_DIRECT  = 3      # exact phrase match in resume text
_SCORE_SYNONYM = 2      # synonym match via ROLE_SYNONYMS
_SCORE_KEYWORD = 1      # partial keyword fallback


# ── Helpers ───────────────────────────────────────────────────────────
def _safe_sort(experiences: list, label: str = "") -> list | None:
    """Sort experiences by start_date. Returns None on failure."""
    try:
        return sorted(
            experiences,
            key=lambda x: date.fromisoformat(x["start_date"])
        )
    except Exception as e:
        suffix = f" ({label})" if label else ""     # pre-assign — avoids evaluating f-string in logger args
        logger.warning("⚠️ Could not sort experiences%s: %s", suffix, e)
        return None


def _safe_dates(exp_a: dict, exp_b: dict) -> tuple | None:
    """
    Parse start/end dates from two experience dicts.

    Returns:
        (a_start, a_end, b_start, b_end) or None on failure
    """
    try:
        return (
            date.fromisoformat(exp_a["start_date"]),
            date.fromisoformat(exp_a["end_date"]),
            date.fromisoformat(exp_b["start_date"]),
            date.fromisoformat(exp_b["end_date"]),
        )
    except Exception as e:
        logger.debug("⚠️ Skipping entry — bad date value: %s", e)
        return None


# ── TOTAL EXPERIENCE ──────────────────────────────────────────────────
def calculate_total_experience(experiences: list) -> int:
    """
    Return total unique months of experience, merging overlapping date ranges.

    Overlapping roles are collapsed so months are never double-counted.

    Args:
        experiences: List of structured experience dicts

    Returns:
        Total unique months (int)
    """
    if not experiences:
        return 0

    # Build intervals
    intervals = []
    for exp in experiences:
        try:
            start = date.fromisoformat(exp["start_date"])
            end   = date.fromisoformat(exp["end_date"])
            intervals.append((start, end))
        except (KeyError, ValueError) as e:
            logger.debug("⚠️ Skipping bad interval: %s", e)
            continue

    if not intervals:
        return 0

    # Sort and merge overlapping intervals
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:                   # overlapping — extend
            merged[-1] = (last_start, max(last_end, end))
        else:                                   # gap — new interval
            merged.append((start, end))

    return sum(calculate_months(s, e) for s, e in merged)


# ── GAP DETECTION ─────────────────────────────────────────────────────
def detect_gaps(experiences: list, min_gap_months: int = 3) -> list:
    """
    Detect employment gaps between consecutive roles.

    Args:
        experiences:     List of structured experience dicts
        min_gap_months:  Minimum gap size to report (default: 3 months)

    Returns:
        List of gap dicts with keys: gap_start, gap_end, gap_months
    """
    if len(experiences) < 2:
        return []

    sorted_exp = _safe_sort(experiences, label="detect_gaps")
    if not sorted_exp:
        return []

    gaps = []

    for i in range(1, len(sorted_exp)):
        dates = _safe_dates(sorted_exp[i - 1], sorted_exp[i])
        if not dates:
            continue

        a_start, a_end, b_start, b_end = dates      # explicit — no throwaway unpacking
        gap_months = calculate_months(a_end, b_start)

        if gap_months >= min_gap_months:
            gaps.append({
                "gap_start":  a_end.isoformat(),
                "gap_end":    b_start.isoformat(),
                "gap_months": gap_months,
            })

    return gaps


# ── OVERLAP DETECTION ─────────────────────────────────────────────────
def detect_overlaps(experiences: list) -> list:
    """
    Detect roles held concurrently (overlapping date ranges).

    Uses full pairwise comparison — catches non-adjacent overlaps
    that a consecutive-only loop would miss.

    Args:
        experiences: List of structured experience dicts

    Returns:
        List of overlap dicts with keys:
            role_a, company_a, role_b, company_b, overlap_months
    """
    if len(experiences) < 2:
        return []

    sorted_exp = _safe_sort(experiences, label="detect_overlaps")
    if not sorted_exp:
        return []

    overlaps = []

    for i in range(len(sorted_exp)):
        for j in range(i + 1, len(sorted_exp)):
            dates = _safe_dates(sorted_exp[i], sorted_exp[j])
            if not dates:
                continue

            a_start, a_end, b_start, b_end = dates

            # Overlap exists when b starts before a ends
            if b_start < a_end:
                overlap_start  = max(a_start, b_start)
                overlap_end    = min(a_end,   b_end)
                overlap_months = calculate_months(overlap_start, overlap_end)

                if overlap_months > 0:
                    overlaps.append({
                        "role_a":         sorted_exp[i]["job_title"],
                        "company_a":      sorted_exp[i]["company"],
                        "role_b":         sorted_exp[j]["job_title"],
                        "company_b":      sorted_exp[j]["company"],
                        "overlap_months": overlap_months,
                    })

    return overlaps


# ── ROLE RELEVANCE SCORING ────────────────────────────────────────────
def experience_relevance_score(experiences: list, jd_roles: list | str) -> float:
    """
    Score how relevant a candidate's experience is to a set of JD roles.

    Scoring tiers (per JD role):
        3 pts — direct phrase match in resume text
        2 pts — synonym match via ROLE_SYNONYMS
        1 pt  — keyword fallback (any word in role matches)

    Score is normalised against maximum possible (3 × len(jd_roles))
    to produce a 0–100% relevance percentage.

    Args:
        experiences: List of structured experience dicts
        jd_roles:    Required roles from the job description (str or list)

    Returns:
        Relevance score as float (0.0 – 100.0)
    """
    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences or not jd_roles:
        return 0.0

    # Build resume text corpus — job_title + company + raw_text (if available)
    resume_text = " ".join([
        " ".join(filter(None, [
            exp.get("job_title", ""),
            exp.get("company",   ""),
            exp.get("raw_text",  ""),   # populated if caller adds enriched text
        ]))
        for exp in experiences
    ]).lower()

    match_score  = 0
    max_possible = _SCORE_DIRECT * len(jd_roles)   # 3 pts per role = ceiling

    for role in jd_roles:
        role_norm = normalize_role(role)

        # Tier 1 — direct phrase match
        if role_norm in resume_text:
            match_score += _SCORE_DIRECT
            continue

        # Tier 2 — synonym match
        synonyms = ROLE_SYNONYMS.get(role_norm, [])
        if not synonyms:
            logger.debug("⚠️ No synonyms found for role: %r", role_norm)

        if any(normalize_role(syn) in resume_text for syn in synonyms):
            match_score += _SCORE_SYNONYM
            continue

        # Tier 3 — keyword fallback
        if any(word in resume_text for word in role_norm.split()):
            match_score += _SCORE_KEYWORD

    if max_possible == 0:
        return 0.0

    return round((match_score / max_possible) * 100, 2)


# ── FINAL OUTPUT BUILDER ──────────────────────────────────────────────
def build_experience_summary(experiences: list, jd_roles: list | str) -> dict:
    """
    Build the final experience summary for a resume × JD pair.

    Orchestrates: relevance scoring + total months + gaps + overlaps.

    Args:
        experiences: List of structured experience dicts
        jd_roles:    Required roles from the job description (str or list)

    Returns:
        Summary dict with keys:
            relevance_score, total_experience_months, gaps, overlaps
    """
    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    # ── Empty guard ───────────────────────────────────────────────────
    if not experiences or not jd_roles:
        logger.warning("⚠️ build_experience_summary called with empty experiences or jd_roles")
        return {
            "relevance_score":          0.0,
            "total_experience_months":  0,
            "gaps":                     [],
            "overlaps":                 [],
        }

    # ── Score + aggregate ─────────────────────────────────────────────
    relevance_score = experience_relevance_score(experiences, jd_roles)
    total_months    = calculate_total_experience(experiences)
    gaps            = detect_gaps(experiences)
    overlaps        = detect_overlaps(experiences)

    logger.debug(
        "📊 Summary built — score=%.2f%% | months=%d | gaps=%d | overlaps=%d",
        relevance_score,
        total_months,
        len(gaps),
        len(overlaps),
    )

    return {
        "relevance_score":          relevance_score,
        "total_experience_months":  total_months,
        "gaps":                     gaps,
        "overlaps":                 overlaps,
    }