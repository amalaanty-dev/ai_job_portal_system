import re
import logging
from datetime import date
from dateutil import parser as dateutil_parser
from utils.date_utils import parse_date, calculate_months

logger = logging.getLogger(__name__)

# ── Present-date tokens ───────────────────────────────────────────────
_PRESENT_TOKENS = {"present", "current", "now"}

# ── Date patterns ─────────────────────────────────────────────────────
_DATE     = r'(?:\d{4}-\d{2}-\d{2}|[a-zA-Z]+\.?\s+\d{4}|\d{4})'
_DATE_END = rf'(?:{_DATE}|[Pp]resent|[Cc]urrent|[Nn]ow)'

# ── Field capture — stops at separators only ──────────────────────────
_FIELD = r'[^,|()\n–—]+'

# ── Multi-format resume patterns (raw text path) ──────────────────────
_PATTERNS = [
    # Format 1 → Role at Company (Jan 2020 – Dec 2022)
    rf'({_FIELD}?)\s+at\s+({_FIELD}?)\s*\(\s*({_DATE})\s*[-–—]\s*({_DATE_END})\s*\)',

    # Format 2 → Role | Company | Jan 2020 – Dec 2022
    rf'({_FIELD}?)\s*\|\s*({_FIELD}?)\s*\|\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 3 → Role, Company, Jan 2020 – Dec 2022
    rf'({_FIELD}?),\s*({_FIELD}?),\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 4 → Fallback: Role Company DateRange
    rf'([a-zA-Z][^,|()\n–—]{{2,40}}?)\s+([a-zA-Z][^,|()\n–—]{{2,40}}?)\s+({_DATE})\s*[-–—]\s*({_DATE_END})',
]

# ── role_header pattern (sectioned resume format) ─────────────────────
# Matches: "Job Title | Company Name | MMM YYYY – MMM YYYY"
#          "Job Title | Company Name| MMM YYYY – Present"
_ROLE_HEADER_RE = re.compile(
    rf'^\s*(.+?)\s*\|\s*(.+?)\s*\|\s*({_DATE})\s*[-–—]\s*({_DATE_END})\s*$',
    re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────
def _resolve_end_date(raw: str) -> date | None:
    """Resolve end date string to a date object."""
    if not raw:
        return None

    clean = raw.strip().lower()
    if clean in _PRESENT_TOKENS:
        return date.today()

    parsed = parse_date(clean)
    if parsed:
        return parsed

    try:
        return dateutil_parser.parse(clean, fuzzy=True).date()
    except Exception:
        logger.debug("Could not parse end date: %r", raw)
        return None


def _normalize_text(text: str) -> str:
    """Strip PDF artifacts and normalize unicode punctuation."""
    text = re.sub(r'\bcid\s*\d+\b', ' ', text)
    text = re.sub(r'[ \t]{2,}',     ' ', text)
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return text.strip()


# ── ROLE HEADER PARSER (sectioned resume) ─────────────────────────────
def parse_role_header(role_header: str) -> dict | None:
    """
    Parse a role_header string from a sectioned resume into a structured
    experience dict.

    Expected formats:
        "Data Engineer II | Gupshup Technologies India Pvt. Ltd.|Jul 2021 – Dec 2024"
        "Deputy Manager – Banking Operations | Axis Bank| Oct 2020 – Nov 2021"
        "Clinical Data Analyst | Brigham and Women's Hospital | Mar 2022 – Present"

    Returns a structured dict or None if parsing fails.
    """
    if not role_header or not isinstance(role_header, str):
        return None

    header = _normalize_text(role_header)
    match  = _ROLE_HEADER_RE.match(header)

    if not match:
        logger.debug("role_header did not match pattern: %r", role_header)
        return None

    title     = match.group(1).strip()
    company   = match.group(2).strip()
    start_raw = match.group(3).strip()
    end_raw   = match.group(4).strip()

    if not title or not company or len(title) < 2 or len(company) < 2:
        return None

    start_date = parse_date(start_raw)
    end_date   = _resolve_end_date(end_raw)

    if not start_date or not end_date:
        logger.debug(
            "Skipping role_header — unparseable dates: title=%r start=%r end=%r",
            title, start_raw, end_raw,
        )
        return None

    return {
        "job_title":       title,
        "company":         company,
        "start_date":      start_date.isoformat(),
        "end_date":        end_date.isoformat(),
        "duration_months": calculate_months(start_date, end_date),
    }


def extract_from_role_headers(experience_list: list) -> list[dict]:
    """
    Extract structured experience entries from a sectioned resume's
    experience list (role_header + duties format).

    Handles two sub-cases:
      - Items with role_header string  → parsed via parse_role_header()
      - Items already fully structured → passed through as-is

    Deduplicates by (job_title, company, start_date).
    """
    results = []
    seen: set[tuple] = set()

    for item in experience_list:
        if not isinstance(item, dict):
            continue

        # Already fully structured — pass through directly
        if {"job_title", "company", "start_date", "end_date"}.issubset(item):
            dedup_key = (
                item["job_title"].lower(),
                item["company"].lower(),
                item["start_date"],
            )
            if dedup_key not in seen:
                seen.add(dedup_key)
                results.append(item)
            continue

        # Has role_header — parse it
        role_header = item.get("role_header", "")
        if role_header:
            entry = parse_role_header(role_header)
            if entry:
                dedup_key = (
                    entry["job_title"].lower(),
                    entry["company"].lower(),
                    entry["start_date"],
                )
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    results.append(entry)
            else:
                logger.warning("Could not parse role_header: %r", role_header)

    return results


# ── EXTRACT FROM RAW TEXT ─────────────────────────────────────────────
def extract_experience(text: str) -> list[dict]:
    """Extract structured experience entries from raw resume text."""
    experiences = []
    if not text or not isinstance(text, str):
        return experiences

    text = _normalize_text(text)
    seen: set[tuple] = set()

    for pattern in _PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) != 4:
                continue

            title     = match[0].strip().strip('-').strip()
            company   = match[1].strip().strip('-').strip()
            start_raw = match[2].strip()
            end_raw   = match[3].strip()

            if not title or not company or len(title) < 2 or len(company) < 2:
                continue

            start_date = parse_date(start_raw)
            end_date   = _resolve_end_date(end_raw)

            if not start_date or not end_date:
                logger.debug(
                    "Skipping entry — unparseable dates: title=%r start=%r end=%r",
                    title, start_raw, end_raw,
                )
                continue

            dedup_key = (title.lower(), company.lower(), start_date.isoformat())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            experiences.append({
                "job_title":       title,
                "company":         company,
                "start_date":      start_date.isoformat(),
                "end_date":        end_date.isoformat(),
                "duration_months": calculate_months(start_date, end_date),
            })

    return experiences


# ── TOTAL EXPERIENCE ──────────────────────────────────────────────────
def calculate_total_experience(experiences: list[dict]) -> int:
    """Return total unique months, merging overlapping ranges accurately."""
    if not experiences:
        return 0

    intervals = []
    for exp in experiences:
        try:
            intervals.append((
                date.fromisoformat(exp["start_date"]),
                date.fromisoformat(exp["end_date"]),
            ))
        except (KeyError, ValueError) as e:
            logger.debug("Skipping experience entry in total calc — bad dates: %s", e)
            continue

    if not intervals:
        return 0

    intervals.sort(key=lambda x: x[0])

    merged = []
    curr_start, curr_end = intervals[0]

    for next_start, next_end in intervals[1:]:
        if next_start <= curr_end:
            curr_end = max(curr_end, next_end)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end

    merged.append((curr_start, curr_end))

    return sum(calculate_months(s, e) for s, e in merged)


# ── GAP DETECTION ─────────────────────────────────────────────────────
def detect_gaps(experiences: list[dict], min_gap_months: int = 3) -> list[dict]:
    """Detect employment gaps between consecutive roles."""
    if len(experiences) < 2:
        return []

    sorted_exp = sorted(experiences, key=lambda x: x["start_date"])
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
    """Detect concurrent roles using pairwise comparison."""
    if len(experiences) < 2:
        return []

    sorted_exp = sorted(experiences, key=lambda x: x["start_date"])
    overlaps = []

    for i in range(len(sorted_exp)):
        for j in range(i + 1, len(sorted_exp)):
            a_start = date.fromisoformat(sorted_exp[i]["start_date"])
            a_end   = date.fromisoformat(sorted_exp[i]["end_date"])
            b_start = date.fromisoformat(sorted_exp[j]["start_date"])
            b_end   = date.fromisoformat(sorted_exp[j]["end_date"])

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


# ── STRUCTURED BUILDER ────────────────────────────────────────────────
def build_structured_experience(text: str) -> dict:
    """Orchestrates extraction, totals, and timeline analysis from raw text."""
    entries = extract_experience(text)
    return {
        "entries":                 entries,
        "total_experience_months": calculate_total_experience(entries),
        "gaps":                    detect_gaps(entries),
        "overlaps":                detect_overlaps(entries),
    }
