import re
import logging
from datetime import date, datetime
from dateutil import parser as dateutil_parser
from utils.date_utils import parse_date, calculate_months

logger = logging.getLogger(__name__)

# ── Present-date tokens ───────────────────────────────────────────────
_PRESENT_TOKENS = {"present", "current", "now"}

# ── Date patterns ─────────────────────────────────────────────────────
_DATE     = r'(?:[a-zA-Z]+\.?\s+\d{4}|\d{4})'
_DATE_END = rf'(?:{_DATE}|[Pp]resent|[Cc]urrent|[Nn]ow)'

# ── Field capture — stops at separators only, NOT at digits ───────────
_FIELD = r'[^,|()\n–—]+'

# ── Multi-format resume patterns ──────────────────────────────────────
_PATTERNS = [
    # Format 1 → Role at Company (Jan 2020 – Dec 2022)
    rf'({_FIELD}?)\s+at\s+({_FIELD}?)\s*\(\s*({_DATE})\s*[-–—]\s*({_DATE_END})\s*\)',

    # Format 2 → Role | Company | Jan 2020 – Dec 2022
    rf'({_FIELD}?)\s*\|\s*({_FIELD}?)\s*\|\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 3 → Role, Company, Jan 2020 – Dec 2022
    rf'({_FIELD}?),\s*({_FIELD}?),\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 4 → Role Company Month YYYY – Month YYYY  (unstructured blob)
    rf'([a-zA-Z][^,|()\n–—]{{3,40}}?)\s+([a-zA-Z][^,|()\n–—]{{3,40}}?)\s+({_DATE})\s*[-–—]?\s*({_DATE_END})',
]

# ── Required keys for downstream validation ───────────────────────────
REQUIRED_EXP_KEYS = {"job_title", "company", "start_date", "end_date"}


# ── Helpers ───────────────────────────────────────────────────────────
def _resolve_end_date(raw: str) -> date | None:
    """
    Resolve end date string to a date object.

    Handles:
        - Present / Current / Now  → date.today()
        - Any parseable date string → date object via dateutil
        - Unparseable              → None

    Always returns date (not datetime) — prevents T00:00:00
    serialisation that breaks date.fromisoformat() downstream.
    """
    if not raw:
        return None

    clean = raw.strip().lower()

    # Present-token — currently employed
    if clean in _PRESENT_TOKENS:
        return date.today()

    # dateutil fuzzy parse → always extract .date() to strip time component
    try:
        return dateutil_parser.parse(clean, fuzzy=True).date()
    except Exception:
        return None


def _normalize_text(text: str) -> str:
    """Strip PDF artifacts and normalize unicode punctuation."""
    text = re.sub(r'\bcid\s*\d+\b', ' ', text)    # PDF artifact tokens
    text = re.sub(r'[ \t]{2,}',     ' ', text)    # collapse spaces
    text = text.replace("\u2013", "-")             # en-dash
    text = text.replace("\u2014", "-")             # em-dash
    text = text.replace("\u2018", "'")             # left single quote
    text = text.replace("\u2019", "'")             # right single quote
    text = text.replace("\u201c", '"')             # left double quote
    text = text.replace("\u201d", '"')             # right double quote
    return text.strip()


# ── EXTRACT ───────────────────────────────────────────────────────────
def extract_experience(text: str) -> list[dict]:
    """
    Extract structured experience entries from raw resume text.

    Supports formats:
        1. Role at Company (Jan 2020 – Dec 2022)
        2. Role | Company | Jan 2020 – Dec 2022
        3. Role, Company, Jan 2020 – Dec 2022
        4. Role Company Jun 2023 Dec 2023  (unstructured blob)

    Returns:
        List of experience dicts with keys:
            job_title, company, start_date, end_date, duration_months
    """
    experiences = []

    if not text or not isinstance(text, str):
        logger.warning("⚠️ Empty or invalid input — expected non-empty string")
        return experiences

    text = _normalize_text(text)

    seen: set[tuple]    = set()
    any_pattern_matched = False

    for pattern in _PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)

        if not matches:
            continue

        any_pattern_matched = True

        for match in matches:

            # Safety check — every pattern yields exactly 4 groups
            if not isinstance(match, tuple) or len(match) != 4:
                logger.debug("⚠️ Unexpected match shape, skipping: %r", match)
                continue

            title, company, start_raw, end_raw = match
            title   = title.strip().strip('-').strip()
            company = company.strip().strip('-').strip()

            # Skip empty captures or noise shorter than 3 chars
            if not title or not company or len(title) < 3 or len(company) < 3:
                logger.debug("⚠️ Too short — skipping: title=%r company=%r", title, company)
                continue

            # Deduplicate across patterns
            dedup_key = (title.lower(), company.lower(), start_raw.strip().lower(), end_raw.strip().lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Parse dates — both return date objects (never datetime)
            start_date = parse_date(start_raw.strip())
            end_date   = _resolve_end_date(end_raw)

            if not start_date:
                logger.warning("⚠️ Unparseable start date %r — skipping (%r at %r)", start_raw, title, company)
                continue
            if not end_date:
                logger.warning("⚠️ Unparseable end date %r — skipping (%r at %r)", end_raw, title, company)
                continue

            experiences.append({
                "job_title":       title,
                "company":         company,
                "start_date":      start_date.isoformat(),      # YYYY-MM-DD (no T00:00:00)
                "end_date":        end_date.isoformat(),        # YYYY-MM-DD (no T00:00:00)
                "duration_months": calculate_months(start_date, end_date),
            })

    if not any_pattern_matched:
        logger.warning("⚠️ No regex pattern matched resume text. Sample: %.300s", text)
    elif not experiences:
        logger.warning("⚠️ Patterns matched but all entries filtered out (date failures / duplicates)")

    return experiences


# ── TOTAL EXPERIENCE ──────────────────────────────────────────────────
def calculate_total_experience(experiences: list[dict]) -> int:
    """
    Return total unique months of experience, merging overlapping ranges.

    Overlapping roles are collapsed so months are never double-counted.

    Args:
        experiences: List of experience dicts from extract_experience()

    Returns:
        Total unique months (int)
    """
    if not experiences:
        return 0

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
def detect_gaps(experiences: list[dict], min_gap_months: int = 3) -> list[dict]:
    """
    Detect employment gaps between consecutive roles.

    Args:
        experiences:     List of experience dicts from extract_experience()
        min_gap_months:  Minimum gap size to report (default: 3 months)

    Returns:
        List of gap dicts with keys: gap_start, gap_end, gap_months
    """
    if len(experiences) < 2:
        return []

    sorted_exp = sorted(
        experiences,
        key=lambda x: date.fromisoformat(x["start_date"])
    )

    gaps = []

    for i in range(1, len(sorted_exp)):
        prev_end   = date.fromisoformat(sorted_exp[i - 1]["end_date"])
        curr_start = date.fromisoformat(sorted_exp[i]["start_date"])
        gap_months = calculate_months(prev_end, curr_start)

        if gap_months >= min_gap_months:
            gaps.append({
                "gap_start":  prev_end.isoformat(),
                "gap_end":    curr_start.isoformat(),
                "gap_months": gap_months,
            })

    return gaps


# ── OVERLAP DETECTION ─────────────────────────────────────────────────
def detect_overlaps(experiences: list[dict]) -> list[dict]:
    """
    Detect roles held concurrently (overlapping date ranges).

    Uses full pairwise comparison — catches non-adjacent overlaps
    that a consecutive-only loop would miss.

    Args:
        experiences: List of experience dicts from extract_experience()

    Returns:
        List of overlap dicts with keys:
            role_a, company_a, role_b, company_b, overlap_months
    """
    if len(experiences) < 2:
        return []

    sorted_exp = sorted(
        experiences,
        key=lambda x: date.fromisoformat(x["start_date"])
    )

    overlaps = []

    for i in range(len(sorted_exp)):
        for j in range(i + 1, len(sorted_exp)):

            a_start = date.fromisoformat(sorted_exp[i]["start_date"])
            a_end   = date.fromisoformat(sorted_exp[i]["end_date"])
            b_start = date.fromisoformat(sorted_exp[j]["start_date"])
            b_end   = date.fromisoformat(sorted_exp[j]["end_date"])

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


# ── STRUCTURED EXPERIENCE OBJECT ──────────────────────────────────────
def build_structured_experience(text: str) -> dict:
    """
    Full Day-10 deliverable — parse raw text into a structured experience object.

    Orchestrates: extract → total → gaps → overlaps into one clean output.

    Args:
        text: Raw resume experience section (string)

    Returns:
        Structured dict with keys:
            entries, total_experience_months, gaps, overlaps
    """
    entries = extract_experience(text)

    structured = {
        "entries":                 entries,
        "total_experience_months": calculate_total_experience(entries),
        "gaps":                    detect_gaps(entries),
        "overlaps":                detect_overlaps(entries),
    }

    logger.info(
        "📦 Structured experience built — entries=%d | months=%d | gaps=%d | overlaps=%d",
        len(entries),
        structured["total_experience_months"],
        len(structured["gaps"]),
        len(structured["overlaps"]),
    )

    return structured