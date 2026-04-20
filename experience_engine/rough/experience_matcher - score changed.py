import logging
from datetime import date
from utils.role_utils import normalize_role, ROLE_SYNONYMS
from utils.date_utils import calculate_months

logger = logging.getLogger(__name__)

# ── Scoring tier weights ──────────────────────────────────────────────
_SCORE_DIRECT  = 3
_SCORE_SYNONYM = 2.5   # 🔥 increased weight
_SCORE_KEYWORD = 2     # 🔥 dynamic keyword scoring


# ── Helpers ───────────────────────────────────────────────────────────
def _safe_sort(experiences: list, label: str = "") -> list | None:
    try:
        return sorted(
            experiences,
            key=lambda x: date.fromisoformat(x["start_date"])
        )
    except Exception as e:
        suffix = f" ({label})" if label else ""
        logger.warning("⚠️ Could not sort experiences%s: %s", suffix, e)
        return None


def _safe_dates(exp_a: dict, exp_b: dict) -> tuple | None:
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

    if not experiences:
        return 0

    intervals = []
    for exp in experiences:
        try:
            start = date.fromisoformat(exp["start_date"])
            end   = date.fromisoformat(exp["end_date"])

            if end > date.today():
                end = date.today()

            intervals.append((start, end))

        except (KeyError, ValueError) as e:
            logger.debug("⚠️ Skipping bad interval: %s", e)
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

    sorted_exp = _safe_sort(experiences, label="detect_gaps")
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
                "gap_start":  a_end.isoformat(),
                "gap_end":    b_start.isoformat(),
                "gap_months": gap_months,
            })

    return gaps


# ── OVERLAP DETECTION ─────────────────────────────────────────────────
def detect_overlaps(experiences: list) -> list:

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

            if b_start < a_end:

                overlap_start  = max(a_start, b_start)
                overlap_end    = min(a_end, b_end)

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


# ── 🔥 FIXED RELEVANCE SCORING ────────────────────────────────────────
def experience_relevance_score(experiences: list, jd_roles: list | str) -> float:

    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences or not jd_roles:
        return 0.0

    # 🔥 Stronger resume text corpus
    resume_text = " ".join([
        " ".join(filter(None, [
            exp.get("job_title", ""),
            exp.get("company", ""),
            exp.get("raw_text", "")
        ]))
        for exp in experiences
    ]).lower()

    match_score = 0
    total_roles = len(jd_roles)

    for role in jd_roles:

        role_norm = normalize_role(role)
        role_tokens = role_norm.split()

        # ── 1. EXACT MATCH
        if role_norm in resume_text:
            match_score += _SCORE_DIRECT
            continue

        # ── 2. SYNONYM MATCH
        synonyms = ROLE_SYNONYMS.get(role_norm, [])

        found = False
        for syn in synonyms:
            syn_norm = normalize_role(syn)
            if syn_norm in resume_text:
                match_score += _SCORE_SYNONYM
                found = True
                break

        if found:
            continue

        # ── 3. SMART TOKEN MATCH
        token_matches = sum(1 for t in role_tokens if t in resume_text)

        if token_matches > 0:
            partial_score = (token_matches / len(role_tokens)) * _SCORE_KEYWORD
            match_score += partial_score

    max_possible = _SCORE_DIRECT * total_roles

    if max_possible == 0:
        return 0.0

    return round((match_score / max_possible) * 100, 2)


# ── FINAL OUTPUT BUILDER ──────────────────────────────────────────────
def build_experience_summary(experiences: list, jd_roles: list | str) -> dict:

    if isinstance(jd_roles, str):
        jd_roles = [jd_roles]

    if not experiences or not jd_roles:
        logger.warning("⚠️ build_experience_summary called with empty experiences or jd_roles")
        return {
            "relevance_score":          0.0,
            "total_experience_months":  0,
            "gaps":                     [],
            "overlaps":                 [],
        }

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