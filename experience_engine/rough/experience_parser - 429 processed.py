import re
import logging
from datetime import date, datetime
from dateutil import parser
from utils.date_utils import parse_date, calculate_months

logger = logging.getLogger(__name__)

# ── Present-date tokens ───────────────────────────────────────────────
_PRESENT_TOKENS = {"present", "current", "now"}

# ── Date patterns ─────────────────────────────────────────────────────
_DATE     = r'(?:[a-zA-Z]+\.?\s+\d{4}|\d{4})'
_DATE_END = rf'(?:{_DATE}|[Pp]resent|[Cc]urrent|[Nn]ow)'

# ── Field capture ─────────────────────────────────────────────────────
_FIELD = r'[^,|()\n–—]+'

# ── Multi-format resume patterns ──────────────────────────────────────
_PATTERNS = [
    # Format 1 → Role at Company (Jan 2020 – Dec 2022)
    rf'({_FIELD}?)\s+at\s+({_FIELD}?)\s*\(\s*({_DATE})\s*[-–—]\s*({_DATE_END})\s*\)',

    # Format 2 → Role | Company | Jan 2020 – Dec 2022
    rf'({_FIELD}?)\s*\|\s*({_FIELD}?)\s*\|\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 3 → Role, Company, Jan 2020 – Dec 2022
    rf'({_FIELD}?),\s*({_FIELD}?),\s*({_DATE})\s*[-–—]\s*({_DATE_END})',

    # Format 4 → Role Company Month YYYY – Month YYYY
    rf'([a-zA-Z][^,|()\n–—]{{3,40}}?)\s+([a-zA-Z][^,|()\n–—]{{3,40}}?)\s+({_DATE})\s*[-–—]?\s*({_DATE_END})',
]

REQUIRED_EXP_KEYS = {"job_title", "company", "start_date", "end_date"}

# ── Helpers ───────────────────────────────────────────────────────────

def _resolve_end_date(end_date_str):
    """Robust end date resolver. Returns (datetime_obj, is_present_flag)."""
    if not end_date_str:
        return None, False

    clean_str = str(end_date_str).strip().lower()

    if clean_str in _PRESENT_TOKENS:
        return datetime.today(), True

    try:
        parsed_date = parser.parse(clean_str, fuzzy=True)
        return parsed_date, False
    except Exception:
        return None, False

def _normalize_text(text: str) -> str:
    """Strip PDF artifacts and normalize unicode punctuation."""
    text = re.sub(r'\bcid\s*\d+\b', ' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    replacements = {
        "\u2013": "-", "\u2014": "-", 
        "\u2018": "'", "\u2019": "'", 
        "\u201c": '"', "\u201d": '"'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()

# ── EXTRACT ───────────────────────────────────────────────────────────

def extract_experience(text: str) -> list[dict]:
    experiences = []
    if not text or not isinstance(text, str):
        return experiences

    text = _normalize_text(text)
    seen = set()
    any_pattern_matched = False

    for pattern in _PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if not matches:
            continue

        any_pattern_matched = True
        for match in matches:
            if not isinstance(match, tuple) or len(match) != 4:
                continue

            title, company, start_raw, end_raw = match
            title = title.strip().strip('-').strip()
            company = company.strip().strip('-').strip()

            if not title or not company or len(title) < 3 or len(company) < 3:
                continue

            dedup_key = (title.lower(), company.lower(), start_raw.strip().lower(), end_raw.strip().lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # --- FIX: Unpack the tuple returned by _resolve_end_date ---
            start_date = parse_date(start_raw.strip())
            end_date_obj, is_present = _resolve_end_date(end_raw)

            if not start_date:
                logger.warning("⚠️ Unparseable start date %r", start_raw)
                continue
            if not end_date_obj:
                logger.warning("⚠️ Unparseable end date %r", end_raw)
                continue

            experiences.append({
                "job_title": title,
                "company": company,
                "start_date": start_date.isoformat(),
                "end_date": end_date_obj.isoformat(),
                "duration_months": calculate_months(start_date, end_date_obj),
            })

    return experiences

# ── ANALYSIS FUNCTIONS ────────────────────────────────────────────────

def _to_date(iso_str: str) -> date:
    """Helper to convert ISO string to date object safely."""
    return date.fromisoformat(iso_str.split('T')[0])

def calculate_total_experience(experiences: list[dict]) -> int:
    if not experiences:
        return 0

    intervals = []
    for exp in experiences:
        try:
            intervals.append((_to_date(exp["start_date"]), _to_date(exp["end_date"])))
        except (KeyError, ValueError):
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

def detect_gaps(experiences: list[dict], min_gap_months: int = 3) -> list[dict]:
    if len(experiences) < 2:
        return []

    sorted_exp = sorted(experiences, key=lambda x: _to_date(x["start_date"]))
    gaps = []

    for i in range(1, len(sorted_exp)):
        prev_end = _to_date(sorted_exp[i - 1]["end_date"])
        curr_start = _to_date(sorted_exp[i]["start_date"])
        gap_months = calculate_months(prev_end, curr_start)

        if gap_months >= min_gap_months:
            gaps.append({
                "gap_start": prev_end.isoformat(),
                "gap_end": curr_start.isoformat(),
                "gap_months": gap_months,
            })
    return gaps

def detect_overlaps(experiences: list[dict]) -> list[dict]:
    if len(experiences) < 2:
        return []

    sorted_exp = sorted(experiences, key=lambda x: _to_date(x["start_date"]))
    overlaps = []

    for i in range(len(sorted_exp)):
        for j in range(i + 1, len(sorted_exp)):
            a_start, a_end = _to_date(sorted_exp[i]["start_date"]), _to_date(sorted_exp[i]["end_date"])
            b_start, b_end = _to_date(sorted_exp[j]["start_date"]), _to_date(sorted_exp[j]["end_date"])

            if b_start < a_end:
                overlap_months = calculate_months(max(a_start, b_start), min(a_end, b_end))
                if overlap_months > 0:
                    overlaps.append({
                        "role_a": sorted_exp[i]["job_title"],
                        "company_a": sorted_exp[i]["company"],
                        "role_b": sorted_exp[j]["job_title"],
                        "company_b": sorted_exp[j]["company"],
                        "overlap_months": overlap_months,
                    })
    return overlaps

def build_structured_experience(text: str) -> dict:
    entries = extract_experience(text)
    return {
        "entries": entries,
        "total_experience_months": calculate_total_experience(entries),
        "gaps": detect_gaps(entries),
        "overlaps": detect_overlaps(entries),
    }