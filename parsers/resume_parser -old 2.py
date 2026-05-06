"""
parsers/resume_parser.py
========================
Resume parser with robust extraction for diverse resume formats.

KEY IMPROVEMENTS over previous version:
1. Robust experience extraction with built-in fallback when build_structured_experience fails
2. Broader name detection (handles ALL CAPS, mixed case, with title prefixes)
3. Extended education patterns (BS, BA, BTech, MTech, BSc, MSc, BCA, MCA, PhD, MBA, BBA, etc.)
4. Consistent folder casing (uses 'JSON' uppercase to match downstream pipelines)
5. Skips already-parsed resumes (idempotent — safe to re-run)
6. Per-file error logging — clear diagnostics
7. Detects role/experience parsing failures and reports them

CRITICAL FIX (v2):
- _fallback_extract_roles() completely rewritten with 5 complementary patterns:
    A) Pipe-separated:  Title | Company | Date – Date
    B) At-pattern:      Title at/@ Company (Date – Date)
    C) Comma-separated: Title, Company, Date – Date
    D) Multi-line block: Title\nCompany\nDate – Date (most common in real PDFs)
    E) Header+date:     Title section header immediately followed by a date line
- date_utils warnings resolved: parse_date_string() now pre-filters lines that
  contain degree/domain keywords (Marketing, Administration, FY …) before forwarding
  to date_utils.
- duration_months properly computed via _compute_duration_months() for all paths.

Day: shared module
"""

import pdfplumber
import docx
import os
import re
import json
import sys
import logging
from datetime import datetime
from typing import Optional

# -----------------------------------------------------------------
# Path Setup & Imports
# -----------------------------------------------------------------
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Try to import the structured experience builder; fall back gracefully
try:
    from experience_engine.experience_parser import build_structured_experience
    HAS_STRUCTURED_EXP = True
except ImportError:
    try:
        from experience_parser import build_structured_experience
        HAS_STRUCTURED_EXP = True
    except ImportError:
        HAS_STRUCTURED_EXP = False
        build_structured_experience = None

# -----------------------------------------------------------------
# Paths (consistent casing - uses JSON uppercase to match pipelines)
# -----------------------------------------------------------------
INPUT_FOLDER = "data/resumes/raw_resumes/"
OUTPUT_FOLDER = "data/resumes/parsed_resumes/JSON/"   # uppercase JSON
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -----------------------------------------------------------------
# Logging
# -----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =================================================================
#                    TEXT EXTRACTION
# =================================================================
def extract_raw_text(file_path: str) -> str:
    """Extract raw text from PDF or DOCX. Returns empty string on failure."""
    ext = file_path.lower()
    text = ""
    try:
        if ext.endswith(".pdf"):
            with pdfplumber.open(file_path) as pdf:
                pages = []
                for p in pdf.pages:
                    page_text = p.extract_text() or ""
                    pages.append(page_text)
                text = "\n".join(pages)
        elif ext.endswith((".docx", ".doc")):
            doc = docx.Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            logger.warning(f"Unsupported format: {file_path}")
    except Exception as e:
        logger.error(f"Error extracting {file_path}: {e}")
    return text


def clean_text(text: str) -> str:
    """Normalize whitespace; preserve paragraph breaks."""
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


# =================================================================
#                    NAME EXTRACTION
# =================================================================
def extract_name(text: str) -> str:
    """
    Detect candidate name using multiple strategies:
      1. First clean Title Case line in first 15 lines
      2. ALL CAPS line (common in modern resumes)
      3. Line before email/phone if labeled
      4. Fall back to "Unknown"
    """
    if not text:
        return "Unknown"

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return "Unknown"

    # Common false-positives we should skip
    SKIP_KEYWORDS = {
        "resume", "curriculum vitae", "cv", "summary", "professional summary",
        "objective", "career objective", "profile", "address", "contact",
        "phone", "email", "linkedin", "github", "portfolio",
    }

    def looks_like_name(line: str) -> bool:
        """Check if a line could plausibly be a person's name."""
        s = line.strip()
        if not s or len(s) > 60 or len(s) < 3:
            return False
        # Reject lines with @, urls, or many digits
        if re.search(r'[@:/\\]', s):
            return False
        if re.search(r'\d{3,}', s):
            return False
        # Reject if it's a known section header
        if s.lower() in SKIP_KEYWORDS:
            return False
        # Words check: 2-5 words
        words = s.split()
        if not (2 <= len(words) <= 5):
            return False
        return True

    # Strategy 1: Title Case (first letter uppercase, rest of word lowercase)
    for line in lines[:15]:
        if looks_like_name(line) and re.match(
            r'^[A-Z][a-zA-Z\s\.\-\']{2,40}$', line
        ):
            return line

    # Strategy 2: ALL CAPS (common in modern resumes like "AMALA P ANTY")
    for line in lines[:15]:
        if looks_like_name(line) and line == line.upper():
            # Title-case it for consistency
            return " ".join(w.capitalize() for w in line.split())

    # Strategy 3: Mixed case but still plausible
    for line in lines[:15]:
        if looks_like_name(line):
            return line

    return "Unknown"


# =================================================================
#                    EDUCATION EXTRACTION
# =================================================================
def extract_full_education(text: str) -> list:
    """Extract education entries with extended degree patterns."""
    education_list = []

    # Extended degree pattern — covers common global degree abbreviations
    DEGREE_PATTERN = (
        r'\b('
        r'PH\.?D|PHD|DOCTORATE|'
        r'MBA|MTECH|M\.TECH|MSC|M\.SC|MS|MA|M\.A|MCA|MCOM|M\.COM|'
        r'BTECH|B\.TECH|BSC|B\.SC|BS|BA|B\.A|BBA|BCA|BCOM|B\.COM|BE|B\.E|'
        r'BACHELOR\s+OF\s+[A-Z]+|MASTER\s+OF\s+[A-Z]+|'
        r'DIPLOMA|HIGHER\s+SECONDARY|HSE|HSC|SSLC|SSC'
        r')\b'
    )
    YEAR_PATTERN = r'\b(19\d{2}|20\d{2})\b'

    lines = text.splitlines()
    for i, line in enumerate(lines):
        degree_match = re.search(DEGREE_PATTERN, line, re.IGNORECASE)
        if degree_match:
            # Look at a window of nearby lines to find years
            context = " ".join(lines[max(0, i - 1):min(len(lines), i + 3)])
            years = sorted(set(re.findall(YEAR_PATTERN, context)))

            education_list.append({
                "degree": degree_match.group(0).upper().replace(".", "").replace(" ", ""),
                "full_line": line.strip(),
                "years": years,
            })

    # Deduplicate by degree
    unique_edu = []
    seen = set()
    for edu in education_list:
        if edu["degree"] not in seen:
            unique_edu.append(edu)
            seen.add(edu["degree"])
    return unique_edu


# =================================================================
#                    DATE UTILITIES
# =================================================================

# Month name → number map (full + abbreviated)
_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Keywords that indicate the string is NOT a date (e.g. degree/domain lines)
_NON_DATE_KEYWORDS = re.compile(
    r'\b(marketing|administration|management|engineering|science|technology|'
    r'commerce|finance|arts|business|fy\s*\d{4}|fiscal)\b',
    re.IGNORECASE,
)


def _parse_date_safe(raw: str) -> Optional[str]:
    """
    Convert a raw date string from a resume to ISO format YYYY-MM-DD.
    Handles: "Jan 2020", "January 2020", "2020", "Present", "Current".
    Returns None if the string cannot be parsed or looks like a non-date.
    Suppresses warnings for known non-date patterns (fixes date_utils warnings).
    """
    if not raw:
        return None

    s = raw.strip()

    # Bail out early for known non-date content — avoids warning spam
    if _NON_DATE_KEYWORDS.search(s):
        return None

    sl = s.lower()

    # Present / Current → today's date
    if sl in {"present", "current", "till date", "ongoing", "now", "to date"}:
        return datetime.today().strftime("%Y-%m-%d")

    # "Month YYYY" or "Month, YYYY"
    m = re.match(r'^([A-Za-z]+)[,\s]+(\d{4})$', s)
    if m:
        month_name, year = m.groups()
        month_num = _MONTH_MAP.get(month_name.lower())
        if month_num:
            return f"{year}-{month_num:02d}-01"

    # Plain year only "YYYY"
    m = re.match(r'^(\d{4})$', s)
    if m:
        return f"{m.group(1)}-01-01"

    # "MM/YYYY" or "MM-YYYY"
    m = re.match(r'^(\d{1,2})[/\-](\d{4})$', s)
    if m:
        month_num, year = m.groups()
        return f"{year}-{int(month_num):02d}-01"

    return None


def _compute_duration_months(start_iso: Optional[str], end_iso: Optional[str]) -> int:
    """Return duration in months between two ISO date strings. Returns 0 on failure."""
    if not start_iso or not end_iso:
        return 0
    try:
        fmt = "%Y-%m-%d"
        s = datetime.strptime(start_iso, fmt)
        e = datetime.strptime(end_iso, fmt)
        delta = (e.year - s.year) * 12 + (e.month - s.month)
        return max(0, delta)
    except Exception:
        return 0


# =================================================================
#                    EXPERIENCE EXTRACTION
# =================================================================

# Separators between date range tokens (dash / en-dash / em-dash / "to")
_DATE_SEP = r'[\-\u2013\u2014]|to'

# A single date token: "Jan 2020", "January 2020", "2020", "Present"
_DATE_TOKEN = r'(?:[A-Za-z]+\s+\d{4}|\d{4}|[Pp]resent|[Cc]urrent)'

# Full date-range pattern
_DATE_RANGE_PAT = re.compile(
    rf'({_DATE_TOKEN})\s*(?:{_DATE_SEP})\s*({_DATE_TOKEN})',
    re.IGNORECASE,
)

# Section headers to ignore when scanning for roles
_SECTION_HEADERS = re.compile(
    r'^\s*(professional\s+experience|work\s+experience|employment(\s+history)?|'
    r'career\s+history|experience|internship|projects?|education|skills?|'
    r'certifications?|achievements?|references?|summary|objective|profile)\s*$',
    re.IGNORECASE,
)

# Words that indicate a line is NOT a job title
_NOT_A_TITLE = re.compile(
    r'\b(university|college|institute|school|bachelor|master|mba|btech|'
    r'bsc|msc|phd|gpa|cgpa|percentage|board|certification|certified|'
    r'linkedin|github|phone|email|address|http|www)\b',
    re.IGNORECASE,
)


def _looks_like_title(line: str) -> bool:
    """Heuristic: does this line look like a job title?"""
    s = line.strip()
    if not s or len(s) < 4 or len(s) > 100:
        return False
    if _SECTION_HEADERS.match(s):
        return False
    if _NOT_A_TITLE.search(s):
        return False
    # Should not contain dates by itself
    if _DATE_RANGE_PAT.search(s):
        return False
    # Must start with a letter (not a bullet/symbol)
    if not re.match(r'^[A-Za-z]', s):
        return False
    return True


def _looks_like_company(line: str) -> bool:
    """Heuristic: does this line look like a company name?"""
    s = line.strip()
    if not s or len(s) < 2 or len(s) > 120:
        return False
    if _NOT_A_TITLE.search(s):
        return False
    if not re.match(r'^[A-Za-z0-9]', s):
        return False
    return True


def _extract_date_range(text: str):
    """Return (start_raw, end_raw) or (None, None) from a text snippet."""
    m = _DATE_RANGE_PAT.search(text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def _build_role(title: str, company: str, start_raw: str, end_raw: str) -> dict:
    """Construct a role dict with ISO dates and duration."""
    start_iso = _parse_date_safe(start_raw)
    end_iso = _parse_date_safe(end_raw)
    return {
        "job_title": title.strip(),
        "company": company.strip(),
        "start_date": start_iso or start_raw,
        "end_date": end_iso or end_raw,
        "duration_months": _compute_duration_months(start_iso, end_iso),
    }


# -----------------------------------------------------------------
# Pattern A: "Title | Company | Date – Date"
# -----------------------------------------------------------------
_PAT_PIPE = re.compile(
    rf'^(.+?)\s*\|\s*(.+?)\s*\|\s*({_DATE_TOKEN})\s*(?:{_DATE_SEP})\s*({_DATE_TOKEN})',
    re.IGNORECASE,
)

# -----------------------------------------------------------------
# Pattern B: "Title at/@ Company  (Date – Date)" or without parens
# -----------------------------------------------------------------
_PAT_AT = re.compile(
    rf'^(.+?)\s+(?:at|@)\s+(.+?)\s*\(?\s*({_DATE_TOKEN})\s*(?:{_DATE_SEP})\s*({_DATE_TOKEN})\)?',
    re.IGNORECASE,
)

# -----------------------------------------------------------------
# Pattern C: "Title, Company  Date – Date"  (comma-separated)
# -----------------------------------------------------------------
_PAT_COMMA = re.compile(
    rf'^([A-Za-z][A-Za-z\s\-/&]+?),\s+([A-Za-z0-9][A-Za-z0-9\s\.\,\&\-]+?)\s+({_DATE_TOKEN})\s*(?:{_DATE_SEP})\s*({_DATE_TOKEN})',
    re.IGNORECASE,
)

# -----------------------------------------------------------------
# Pattern D (inline): "Title | Company  Date – Date"  (only 1 pipe)
# -----------------------------------------------------------------
_PAT_ONE_PIPE = re.compile(
    rf'^(.+?)\s*\|\s*(.+?)\s+({_DATE_TOKEN})\s*(?:{_DATE_SEP})\s*({_DATE_TOKEN})',
    re.IGNORECASE,
)


def _match_single_line(line: str) -> Optional[dict]:
    """
    Try all single-line patterns on one line.
    Returns a role dict or None.
    """
    stripped = line.strip()
    if not stripped:
        return None

    for pat in [_PAT_PIPE, _PAT_AT, _PAT_COMMA, _PAT_ONE_PIPE]:
        m = pat.match(stripped)
        if m:
            title, company, start_raw, end_raw = m.groups()
            if _looks_like_title(title) and _looks_like_company(company):
                return _build_role(title, company, start_raw, end_raw)

    return None


def _fallback_extract_roles(text: str) -> list:
    """
    Rewritten fallback role extractor — 5 complementary strategies.

    Strategy 1 (single-line):
        Title | Company | Date – Date
        Title at Company (Date – Date)
        Title, Company  Date – Date

    Strategy 2 (multi-line block — most common in real PDFs):
        Line N:   Job Title [possibly with | Company]
        Line N+1: Company Name  OR  "Company Name | City"
        Line N+2: Date – Date  (or same as N+1)

    Strategy 3 (title + date on same line, company on next):
        "Senior Engineer  Jan 2020 – Present"
        "Google Inc."

    Strategy 4 (PROFESSIONAL EXPERIENCE section scan):
        After detecting the experience section header, treat consecutive
        non-empty, non-bullet lines as (title, company, dates) blocks.

    Strategy 5 (date-anchored scan):
        Find lines that contain a date range; look backwards 1-2 lines
        for title and company.
    """
    roles: list = []
    seen: set = set()   # deduplicate by (title_lower, company_lower)

    def _normalize(s: str) -> str:
        """Strip punctuation/pipe artifacts for dedup comparison."""
        return re.sub(r'[|,\-\s]+', ' ', s).strip().lower()

    def _is_clean_field(s: str) -> bool:
        """Reject strings that look like concatenated role lines (false-positives)."""
        # Too many words → likely a full sentence, not a title/company
        if len(s.split()) > 10:
            return False
        # Contains a pipe AND a date range → almost certainly a mis-parsed adjacent line
        if '|' in s and _DATE_RANGE_PAT.search(s):
            return False
        # Contains a date range and looks like "Title at Company (dates)" → Strategy 5 artifact
        if _DATE_RANGE_PAT.search(s) and re.search(r'\bat\b', s, re.IGNORECASE):
            return False
        # Contains a date range with a comma → comma-pattern Strategy 5 artifact
        if _DATE_RANGE_PAT.search(s) and ',' in s:
            return False
        return True

    def add_role(r: dict):
        if not _is_clean_field(r["job_title"]):
            return
        if not _is_clean_field(r["company"]):
            return
        title_n = _normalize(r["job_title"])
        company_n = _normalize(r["company"])
        key = (title_n, company_n)
        if key not in seen and r["job_title"] and r["company"]:
            seen.add(key)
            roles.append(r)

    lines = [ln.rstrip() for ln in text.splitlines()]
    n = len(lines)

    # ----------------------------------------------------------------
    # Strategy 1: Single-line patterns
    # ----------------------------------------------------------------
    for line in lines:
        r = _match_single_line(line)
        if r:
            add_role(r)

    # ----------------------------------------------------------------
    # Strategy 2 & 3: Multi-line sliding window (size 2-3)
    # ----------------------------------------------------------------
    for i in range(n):
        line0 = lines[i].strip()
        if not line0 or _SECTION_HEADERS.match(line0):
            continue

        # Window: line0, line1, line2
        line1 = lines[i + 1].strip() if i + 1 < n else ""
        line2 = lines[i + 2].strip() if i + 2 < n else ""

        # --- Strategy 2: title on line0, company on line1, date on line2 ---
        if _looks_like_title(line0) and _looks_like_company(line1):
            start_raw, end_raw = _extract_date_range(line2)
            if start_raw:
                add_role(_build_role(line0, line1, start_raw, end_raw))
                continue

            # date might be embedded in line1 after the company name
            # e.g. "Google Inc. | Jan 2020 – Dec 2022"
            if '|' in line1:
                parts = line1.split('|', 1)
                company_part = parts[0].strip()
                date_part = parts[1].strip()
                start_raw, end_raw = _extract_date_range(date_part)
                if start_raw and _looks_like_company(company_part):
                    add_role(_build_role(line0, company_part, start_raw, end_raw))
                    continue

        # --- Strategy 3: title + date on line0, company on line1 ---
        if _looks_like_company(line1):
            start_raw, end_raw = _extract_date_range(line0)
            if start_raw:
                # Strip date portion from line0 to get title
                title_part = _DATE_RANGE_PAT.sub("", line0).strip(" |-–—,")
                if _looks_like_title(title_part):
                    add_role(_build_role(title_part, line1, start_raw, end_raw))
                    continue

    # ----------------------------------------------------------------
    # Strategy 4: Section-header-guided scan
    # ----------------------------------------------------------------
    _EXPERIENCE_HEADER = re.compile(
        r'^\s*(professional\s+experience|work\s+experience|employment(\s+history)?|'
        r'career\s+history|experience)\s*$',
        re.IGNORECASE,
    )
    _NEXT_SECTION = re.compile(
        r'^\s*(education|skills?|certifications?|projects?|achievements?|'
        r'references?|summary|objective|languages?|interests?|awards?)\s*$',
        re.IGNORECASE,
    )

    in_exp_section = False
    block: list = []   # accumulate non-empty lines within experience section

    def _flush_block(block: list):
        """Try to extract a role from an accumulated block of lines."""
        # Filter out pure bullet/symbol lines
        cleaned = [ln for ln in block if re.match(r'^[A-Za-z0-9]', ln)]
        if len(cleaned) < 2:
            return

        # Heuristic: first line = title, look for date anywhere in block
        title_candidate = cleaned[0]
        if not _looks_like_title(title_candidate):
            return

        date_line = ""
        company_candidate = ""
        for ln in cleaned[1:]:
            if _DATE_RANGE_PAT.search(ln) and not date_line:
                date_line = ln
            elif not company_candidate and _looks_like_company(ln):
                company_candidate = ln

        if date_line and company_candidate:
            start_raw, end_raw = _extract_date_range(date_line)
            if start_raw:
                add_role(_build_role(title_candidate, company_candidate, start_raw, end_raw))

    for line in lines:
        stripped = line.strip()

        if _EXPERIENCE_HEADER.match(stripped):
            in_exp_section = True
            block = []
            continue

        if in_exp_section:
            if _NEXT_SECTION.match(stripped):
                _flush_block(block)
                in_exp_section = False
                block = []
                continue

            if not stripped:
                # Empty line = end of current block
                _flush_block(block)
                block = []
            else:
                block.append(stripped)

    if block:
        _flush_block(block)

    # ----------------------------------------------------------------
    # Strategy 5: Date-anchored backward scan
    # ----------------------------------------------------------------
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        start_raw, end_raw = _extract_date_range(stripped)
        if not start_raw:
            continue

        # The date line itself might contain company or title after stripping dates
        remainder = _DATE_RANGE_PAT.sub("", stripped).strip(" |-–—,|")

        # Look backwards for title and company
        candidates = []
        for j in range(max(0, i - 3), i):
            prev = lines[j].strip()
            if prev and not _SECTION_HEADERS.match(prev) and not _DATE_RANGE_PAT.search(prev):
                candidates.append(prev)

        if len(candidates) >= 2:
            title_c = candidates[-2]
            company_c = candidates[-1]
        elif len(candidates) == 1:
            title_c = candidates[-1]
            company_c = remainder or ""
        else:
            continue

        if _looks_like_title(title_c) and _looks_like_company(company_c or title_c):
            company_final = company_c if company_c else remainder
            if company_final:
                add_role(_build_role(title_c, company_final, start_raw, end_raw))

    return roles


def _estimate_total_months_from_text(text: str) -> int:
    """
    Estimate total experience months from the raw text by finding
    'X years experience' phrases. Returns 0 if nothing matches.
    """
    text_l = text.lower()
    # Match e.g. "5 years", "3+ years", "2.5 years"
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*\+?\s*years?', text_l)
    if not matches:
        return 0
    try:
        max_years = max(float(m) for m in matches)
        return int(max_years * 12)
    except ValueError:
        return 0


def _compute_total_months_from_roles(roles: list) -> int:
    """Sum duration_months across all roles (non-overlapping assumption)."""
    return sum(r.get("duration_months", 0) for r in roles)


def extract_experience_safe(cleaned_text: str) -> dict:
    """
    Try the structured experience builder first; fall back to lightweight
    extraction if it fails or returns empty.
    """
    if HAS_STRUCTURED_EXP and build_structured_experience is not None:
        try:
            exp_data = build_structured_experience(cleaned_text) or {}
            entries = exp_data.get("entries") or []
            total_months = exp_data.get("total_experience_months") or 0
            if entries:
                return {
                    "entries": entries,
                    "total_experience_months": total_months,
                    "extraction_method": "structured",
                }
            else:
                logger.debug("Structured experience returned empty, trying fallback")
        except Exception as e:
            logger.warning(f"build_structured_experience failed: {e}; trying fallback")

    # Fallback path
    fallback_roles = _fallback_extract_roles(cleaned_text)
    # Prefer sum of role durations; use text-based estimate only if no roles found
    if fallback_roles:
        fallback_months = _compute_total_months_from_roles(fallback_roles)
        if fallback_months == 0:
            fallback_months = _estimate_total_months_from_text(cleaned_text)
    else:
        fallback_months = _estimate_total_months_from_text(cleaned_text)

    return {
        "entries": fallback_roles,
        "total_experience_months": fallback_months,
        "extraction_method": "fallback" if fallback_roles or fallback_months else "none",
    }


# =================================================================
#                    ORCHESTRATION
# =================================================================
def parse_resume(raw_text: str) -> dict:
    """Parse a single resume's raw text into structured fields."""
    cleaned = clean_text(raw_text)
    if not cleaned:
        return {
            "name": "Unknown",
            "roles": [],
            "experience": 0.0,
            "education": [],
            "clean_text": "",
            "_warnings": ["empty_text"],
        }

    exp_data = extract_experience_safe(cleaned)
    name = extract_name(cleaned)
    education = extract_full_education(cleaned)

    warnings = []
    if not exp_data["entries"]:
        warnings.append("no_roles_extracted")
    if not education:
        warnings.append("no_education_extracted")
    if name == "Unknown":
        warnings.append("name_unknown")

    return {
        "name": name,
        "roles": exp_data["entries"],
        "experience": round(exp_data["total_experience_months"] / 12, 1),
        "education": education,
        "clean_text": cleaned,
        "_extraction_method": exp_data.get("extraction_method", "unknown"),
        "_warnings": warnings,
    }


def process_resumes(skip_existing: bool = True) -> dict:
    """
    Process all resumes in INPUT_FOLDER and write parsed JSONs to OUTPUT_FOLDER.

    Args:
        skip_existing: if True, skip resumes that already have a parsed JSON.

    Returns:
        Dict summary: {processed, skipped, failed, warnings_per_resume}
    """
    if not os.path.isdir(INPUT_FOLDER):
        logger.error(f"Input folder does not exist: {INPUT_FOLDER}")
        return {"processed": 0, "skipped": 0, "failed": 0, "warnings": {}}

    files = [
        f for f in os.listdir(INPUT_FOLDER)
        if f.lower().endswith((".pdf", ".docx", ".doc"))
    ]

    if not files:
        logger.warning(f"No resumes found in {INPUT_FOLDER}")
        return {"processed": 0, "skipped": 0, "failed": 0, "warnings": {}}

    summary = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "warnings": {},  # filename -> list of warnings
    }

    logger.info(f"Found {len(files)} resume(s) in {INPUT_FOLDER}")
    for file in files:
        out_name = os.path.splitext(file)[0] + ".json"
        output_path = os.path.join(OUTPUT_FOLDER, out_name)

        if skip_existing and os.path.exists(output_path):
            # Check that existing file isn't null/empty
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing and existing.get("clean_text"):
                    logger.debug(f"Skip (already parsed): {file}")
                    summary["skipped"] += 1
                    continue
            except Exception:
                # Corrupt/null - re-process
                pass

        logger.info(f"Processing: {file}")
        raw_text = extract_raw_text(os.path.join(INPUT_FOLDER, file))
        if not raw_text:
            logger.error(f"  Failed to extract text from {file}")
            summary["failed"] += 1
            continue

        parsed = parse_resume(raw_text)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"resume_name": file, **parsed}, f, indent=4, ensure_ascii=False)
            logger.info(
                f"  Saved -> {out_name}  (method={parsed.get('_extraction_method')}, "
                f"roles={len(parsed['roles'])}, edu={len(parsed['education'])})"
            )
            summary["processed"] += 1
            if parsed.get("_warnings"):
                summary["warnings"][file] = parsed["_warnings"]
        except Exception as e:
            logger.error(f"  Failed to write {out_name}: {e}")
            summary["failed"] += 1

    # Summary
    logger.info("-" * 60)
    logger.info(
        f"DONE  processed={summary['processed']}  "
        f"skipped={summary['skipped']}  failed={summary['failed']}"
    )
    if summary["warnings"]:
        logger.warning(f"{len(summary['warnings'])} resume(s) had warnings:")
        for fn, warns in summary["warnings"].items():
            logger.warning(f"  - {fn}: {', '.join(warns)}")
    logger.info(f"Output: {OUTPUT_FOLDER}")

    return summary


if __name__ == "__main__":
    process_resumes()