import re
import logging
from datetime import date
from dateutil import parser as dateutil_parser
from utils.date_utils import parse_date, calculate_months

logger = logging.getLogger(__name__)

# ── Present-date tokens ───────────────────────────────────────────────
_PRESENT_TOKENS = {"present", "current", "now"}

# ── Date patterns ─────────────────────────────────────────────────────
# UPDATED: Added \d{4}-\d{2}-\d{2} to support ISO format
_DATE     = r'(?:\d{4}-\d{2}-\d{2}|[a-zA-Z]+\.?\s+\d{4}|\d{4})'
_DATE_END = rf'(?:{_DATE}|[Pp]resent|[Cc]urrent|[Nn]ow)'

# ── Field capture — stops at separators only ──────────────────────────
_FIELD = r'[^,|()\n–—]+'

# ── Multi-format resume patterns ──────────────────────────────────────
_PATTERNS = [
    # Format 1 → Role at Company (Jan 2020 – Dec 2022)
    rf'({_FIELD}?)\s+at\s+({_FIELD}?)\s*\(\s*({_DATE})\s*[-–—]\s*({_DATE_END})\s*\)',

    # Format 2 → Role | Company | Jan 2020 – Dec 2022
    rf'({_FIELD}?)\s*\|\s*({_FIELD}?)\s*\|\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 3 → Role, Company, Jan 2020 – Dec 2022
    rf'({_FIELD}?),\s*({_FIELD}?),\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 4 → Role Company (blob)
    rf'([a-zA-Z][^,|()\n–—]{{3,40}}?)\s+([a-zA-Z][^,|()\n–—]{{3,40}}?)\s+({_DATE})\s*[-–—]?\s*({_DATE_END})',
]

# ── Helpers ───────────────────────────────────────────────────────────
def _resolve_end_date(raw: str) -> date | None:
    """Resolve end date string to a date object."""
    if not raw:
        return None

    clean = raw.strip().lower()
    if clean in _PRESENT_TOKENS:
        return date.today()

    # Try custom parse_date first for ISO consistency
    parsed = parse_date(clean)
    if parsed:
        return parsed

    try:
        return dateutil_parser.parse(clean, fuzzy=True).date()
    except Exception:
        return None


def _normalize_text(text: str) -> str:
    """Strip PDF artifacts and normalize unicode punctuation."""
    text = re.sub(r'\bcid\s*\d+\b', ' ', text)
    text = re.sub(r'[ \t]{2,}',     ' ', text)
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return text.strip()


# ── EXTRACT ───────────────────────────────────────────────────────────
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
            if len(match) != 4: continue

            title   = match[0].strip().strip('-').strip()
            company = match[1].strip().strip('-').strip()
            start_raw = match[2].strip()
            end_raw   = match[3].strip()

            if not title or not company or len(title) < 2 or len(company) < 2:
                continue

            start_date = parse_date(start_raw)
            end_date   = _resolve_end_date(end_raw)

            if not start_date or not end_date:
                continue

            dedup_key = (title.lower(), company.lower(), start_date.isoformat())
            if dedup_key in seen: continue
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
    """Return total unique months, merging overlapping ranges."""
    if not experiences: return 0

    intervals = []
    for exp in experiences:
        try:
            intervals.append((date.fromisoformat(exp["start_date"]), 
                              date.fromisoformat(exp["end_date"])))
        except: continue

    if not intervals: return 0

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
def detect_gaps(experiences: list[dict], min_gap_months: int = 3) -> list[dict]:
    """Detect employment gaps between consecutive roles."""
    if len(experiences) < 2: return []

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
    if len(experiences) < 2: return []

    sorted_exp = sorted(experiences, key=lambda x: x["start_date"])
    overlaps = []

    for i in range(len(sorted_exp)):
        for j in range(i + 1, len(sorted_exp)):
            a_start = date.fromisoformat(sorted_exp[i]["start_date"])
            a_end   = date.fromisoformat(sorted_exp[i]["end_date"])
            b_start = date.fromisoformat(sorted_exp[j]["start_date"])
            b_end   = date.fromisoformat(sorted_exp[j]["end_date"])

            # Logic: If Job B starts before Job A ends, they overlap
            if b_start < a_end:
                overlap_start = max(a_start, b_start)
                overlap_end   = min(a_end,   b_end)
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
    """Orchestrates extraction, totals, and timeline analysis."""
    entries = extract_experience(text)
    return {
        "entries":                 entries,
        "total_experience_months": calculate_total_experience(entries),
        "gaps":                    detect_gaps(entries),
        "overlaps":                detect_overlaps(entries),
    }