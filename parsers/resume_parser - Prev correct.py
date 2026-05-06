"""
parsers/resume_parser.py
========================
UNIVERSAL Resume Parser - handles diverse PDF resume formats:
  - Classic style:    "Senior Backend Developer TechCorp Pvt Ltd | 2021-Present"
  - Modern style:     similar to Classic with variations
  - Creative style:   "Backend Developer Freshworks | 2021-Present"
  - Pipe-separated:   "Data Engineer II | Gupshup | Jul 2021 - Dec 2024"
  - Stacked:          "Health Information Analyst\nMedStar Health . Sep 2020 - Present"
  - Date-first:       "2021-2023 | Software Engineer at Microsoft"

KEY IMPROVEMENTS:
1. Section-aware parsing - finds Experience section first, then parses lines within it
2. Multi-pattern role detection - 6 fallback patterns for diverse formats
3. Title+Company splitting via known role-keyword detection
4. Robust date extraction (handles -, --, en-dash, em-dash, "to", "-")
5. Better name detection (3 strategies)
6. Extended education patterns
7. Per-resume diagnostics with extraction method labeled
8. Idempotent (skip-existing flag)

Day: shared module
"""

import pdfplumber
import docx
import os
import re
import json
import sys
import logging
from typing import Optional, List, Dict, Tuple

# -----------------------------------------------------------------
# Path Setup & Imports
# -----------------------------------------------------------------
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Try importing the structured experience builder; fall back gracefully
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
# Paths
# -----------------------------------------------------------------
INPUT_FOLDER = "data/resumes/raw_resumes/"
OUTPUT_FOLDER = "data/resumes/parsed_resumes/JSON/"
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
#                    CONSTANTS
# =================================================================
# Common job-role keywords that mark the END of a job title
# (used to split "Senior Backend Developer TechCorp Pvt Ltd" -> title|company)
ROLE_SUFFIXES = [
    # Tech
    "developer", "engineer", "architect", "programmer", "designer",
    "scientist", "analyst", "administrator", "specialist", "consultant",
    "lead", "head", "director", "vp", "cto", "ceo", "cio",
    # Tech variants
    "fullstack developer", "full stack developer", "full-stack developer",
    "frontend developer", "front end developer", "front-end developer",
    "backend developer", "back end developer", "back-end developer",
    "devops engineer", "data engineer", "ml engineer", "qa engineer",
    "software engineer", "systems engineer", "site reliability engineer",
    "cloud architect", "solution architect", "data scientist",
    "data analyst", "business analyst", "research analyst",
    # Non-tech
    "manager", "executive", "officer", "associate", "coordinator",
    "supervisor", "trainee", "intern", "assistant", "representative",
    "consultant", "advisor", "agent",
    # Non-tech variants
    "marketing manager", "marketing executive", "sales executive",
    "sales manager", "hr manager", "hr executive", "operations manager",
    "deputy manager", "assistant manager", "senior manager",
    "general manager", "regional manager", "product manager",
    "project manager", "program manager", "account manager",
    "business development", "business analyst",
    # Healthcare
    "technician", "nurse", "physician", "doctor", "therapist",
    "records technician", "information analyst",
]

# Section header keywords that indicate "Experience" section
EXPERIENCE_HEADERS = [
    "professional experience", "work experience", "experience",
    "employment history", "employment", "career history",
    "professional background", "work history",
]

# Section headers that mark the END of the experience section
NON_EXPERIENCE_HEADERS = [
    "education", "skills", "technical skills", "core skills", "core competencies",
    "projects", "personal projects", "machine learning projects",
    "certifications", "achievements", "key achievements", "awards",
    "publications", "languages", "soft skills", "tools", "interests",
    "hobbies", "general details", "personal details", "references",
    "summary", "professional summary", "objective", "career objective",
    "tools & technologies", "tools and technologies",
]


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
                pages = [(p.extract_text() or "") for p in pdf.pages]
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
    # Strip PDF cid placeholders (from glyph-mapping issues)
    text = re.sub(r'\(cid:\d+\)', '', text)
    # Normalize various dash characters to ASCII hyphen
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    # Normalize the middle-dot separator to pipe (for stacked formats)
    text = text.replace('\u00b7', '|')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


# =================================================================
#                    NAME EXTRACTION
# =================================================================
def extract_name(text: str) -> str:
    """Detect candidate name using multiple strategies."""
    if not text:
        return "Unknown"

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return "Unknown"

    skip = {
        "resume", "curriculum vitae", "cv", "summary", "professional summary",
        "objective", "career objective", "profile", "address", "contact",
        "phone", "email", "linkedin", "github", "portfolio",
    }

    def looks_like_name(line: str) -> bool:
        s = line.strip()
        if not s or len(s) > 60 or len(s) < 3:
            return False
        # Reject lines with these characters
        if re.search(r'[@:/\\]', s):
            return False
        if re.search(r'\d{3,}', s):  # phone numbers
            return False
        if s.lower() in skip:
            return False
        # 2-5 words
        words = s.split()
        if not (2 <= len(words) <= 5):
            return False
        # Reject lines that are mostly punctuation
        if len(re.sub(r'[A-Za-z\s]', '', s)) > len(s) * 0.3:
            return False
        return True

    # Strategy 1: Title Case (e.g., "Arjun Menon")
    for line in lines[:15]:
        if looks_like_name(line) and re.match(
            r'^[A-Z][a-zA-Z\.\-\']*(\s+[A-Z][a-zA-Z\.\-\']*){1,4}$', line
        ):
            return line

    # Strategy 2: ALL CAPS (e.g., "AMALA P ANTY")
    for line in lines[:15]:
        if looks_like_name(line) and line == line.upper():
            return " ".join(w.capitalize() for w in line.split())

    # Strategy 3: First plausible 2-5 word line
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

    DEGREE_PATTERN = (
        r'\b('
        r'PH\.?\s?D|PHD|DOCTORATE|'
        r'M\.?\s?B\.?\s?A|'
        r'M\.?\s?TECH|MTECH|'
        r'M\.?\s?SC|MSC|'
        r'M\.?\s?S\b|'
        r'M\.?\s?A\b|MA\b|'
        r'M\.?\s?C\.?\s?A|MCA|'
        r'M\.?\s?COM|MCOM|'
        r'B\.?\s?TECH|BTECH|'
        r'B\.?\s?SC|BSC|'
        r'B\.?\s?S\b|BS\b|'
        r'B\.?\s?A\b|BA\b|'
        r'B\.?\s?B\.?\s?A|BBA|'
        r'B\.?\s?C\.?\s?A|BCA|'
        r'B\.?\s?COM|BCOM|'
        r'B\.?\s?E\b|BE\b|'
        r'BACHELOR\s+OF\s+[A-Z][A-Z\s]*|'
        r'MASTER\s+OF\s+[A-Z][A-Z\s]*|'
        r'DIPLOMA|HIGHER\s+SECONDARY|HSE|HSC|SSLC|SSC'
        r')\b'
    )
    YEAR_PATTERN = r'\b(19\d{2}|20\d{2})\b'

    lines = text.splitlines()
    for i, line in enumerate(lines):
        degree_match = re.search(DEGREE_PATTERN, line, re.IGNORECASE)
        if degree_match:
            context = " ".join(lines[max(0, i - 1):min(len(lines), i + 3)])
            years = sorted(set(re.findall(YEAR_PATTERN, context)))

            # Normalize degree label
            degree_text = degree_match.group(0).upper()
            degree_text = re.sub(r'[\.\s]', '', degree_text)

            education_list.append({
                "degree": degree_text,
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
#                    EXPERIENCE EXTRACTION
# =================================================================
def _strip_sidebar_pollution(line: str) -> str:
    """
    Remove trailing two-column sidebar pollution from a line.

    Heuristic: if line ends with a Title Case phrase (like 'Audit & Reporting'),
    strip it if the line also contains an obvious main-content boundary.
    """
    # If the line is a job-title-like phrase followed by another Title Case phrase,
    # try to keep only the first part. This is heuristic and conservative.
    # Match: "Job Title Words [SIDEBAR PHRASE]"
    return line.strip()


def _is_section_header_line(line: str, header: str) -> bool:
    """Check if a line cleanly represents a section header."""
    line_clean = line.strip()
    if not line_clean:
        return False
    line_lower = line_clean.lower()

    # Exact match (case-insensitive)
    if line_lower == header.lower():
        return True
    # ALL CAPS exact
    if line_clean == header.upper():
        return True
    # Header followed by short sidebar pollution (e.g., "EDUCATION LANGUAGES")
    # Both should be ALL CAPS for this to be valid
    if line_clean == line_clean.upper() and line_lower.startswith(header.lower() + " "):
        # Length cap: original header + max 25 chars of pollution
        if len(line_clean) <= len(header) + 25:
            return True
    return False


def _find_experience_section(text: str) -> str:
    """
    Locate the Experience section in the resume.

    Returns the text BETWEEN the Experience header and the next major
    non-experience header. Handles polluted headers from two-column PDFs.
    """
    lines = text.splitlines()

    # Find the start of the experience section
    start_idx = None
    for i, line in enumerate(lines):
        for hdr in EXPERIENCE_HEADERS:
            if _is_section_header_line(line, hdr):
                start_idx = i + 1
                break
        if start_idx is not None:
            break

    if start_idx is None:
        return text

    # Find the end - require a clean section header
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        for hdr in NON_EXPERIENCE_HEADERS:
            if _is_section_header_line(lines[i], hdr):
                end_idx = i
                break
        if end_idx != len(lines):
            break

    return "\n".join(lines[start_idx:end_idx])


def _split_title_and_company(text: str) -> Tuple[str, str]:
    """
    Split a string like "Senior Backend Developer TechCorp Pvt Ltd"
    into ("Senior Backend Developer", "TechCorp Pvt Ltd").

    Strategy: find the LAST role-keyword in the string; everything up to
    and including it is the title; everything after is the company.
    """
    text = text.strip()
    if not text:
        return "", ""

    text_lower = text.lower()

    # Sort role suffixes longest-first so multi-word matches win
    sorted_roles = sorted(ROLE_SUFFIXES, key=len, reverse=True)

    best_split = None
    for kw in sorted_roles:
        # Find all occurrences of this keyword as a word boundary
        for m in re.finditer(r'\b' + re.escape(kw) + r'\b', text_lower):
            end_pos = m.end()
            # Track the rightmost match (most likely the actual title boundary)
            if best_split is None or end_pos > best_split:
                best_split = end_pos

    if best_split is not None and best_split < len(text):
        title = text[:best_split].strip()
        company = text[best_split:].strip()
        # Clean up leading punctuation on company
        company = re.sub(r'^[,\.\-\s]+', '', company)
        return title, company

    # Fallback: split on whitespace heuristically (first 1-3 words = title)
    words = text.split()
    if len(words) <= 3:
        return text, ""
    return " ".join(words[:3]), " ".join(words[3:])


def _clean_line_for_parsing(line: str) -> str:
    """
    Remove trailing sidebar pollution from a line.

    Two-column PDFs sometimes interleave the main content with sidebar text.
    For lines that look like 'Job Title SIDEBAR_TEXT', try to recover just
    the job title portion using the role-keyword heuristic.
    """
    line = line.strip()
    if not line:
        return line

    # If the line contains a known role keyword and ends with extra Title Case
    # words (potential sidebar), trim back to the role keyword.
    line_lower = line.lower()
    sorted_roles = sorted(ROLE_SUFFIXES, key=len, reverse=True)
    for kw in sorted_roles:
        m = re.search(r'\b' + re.escape(kw) + r'\b', line_lower)
        if m:
            # Check what comes after - if it's Title Case sidebar phrase,
            # trim it off
            after = line[m.end():].strip()
            if not after:
                return line
            # If 'after' is short Title Case (likely sidebar), trim it
            if (len(after) < 30
                and re.match(r'^[A-Z][A-Za-z\s&]+$', after)
                and not re.search(r'\d', after)
                and len(after.split()) <= 3):
                # Looks like sidebar pollution
                return line[:m.end()].strip()
            break  # don't try other keywords once we found one

    return line


def _extract_roles_universal(text: str) -> List[Dict]:
    """
    Universal role extractor that tries multiple patterns.
    Operates on the experience-section text (or full text if no section found).
    """
    roles = []
    seen_signatures = set()  # avoid duplicates

    section_text = _find_experience_section(text)
    raw_lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    # Clean sidebar pollution from each line
    lines = [_clean_line_for_parsing(ln) for ln in raw_lines]

    # ============================================================
    # PATTERN 1: "Title | Company | Dates" (Amala-style)
    # ============================================================
    pat_pipe_three = re.compile(
        r'^(.+?)\s*\|\s*(.+?)\s*\|\s*'
        r'([A-Za-z]+\s*\d{4}|\d{4})\s*[-to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)',
        re.IGNORECASE
    )

    # ============================================================
    # PATTERN 2: "Title CompanyName | Year-Year" (Classic/Creative/Modern)
    #            Title and company are NOT separated; only date is.
    # ============================================================
    pat_no_sep = re.compile(
        r'^(.+?)\s*\|\s*'
        r'([A-Za-z]+\s*\d{4}|\d{4})\s*[-to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)',
        re.IGNORECASE
    )

    # ============================================================
    # PATTERN 3: Two-line stacked (Healthcare style)
    #   Line 1: "Health Information Analyst"
    #   Line 2: "MedStar Health · Sep 2020 - Present"
    # (After clean_text, "·" became "|")
    # ============================================================
    pat_company_dates = re.compile(
        r'^(.+?)\s*\|\s*'
        r'([A-Za-z]+\s*\d{4}|\d{4})\s*[-to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)',
        re.IGNORECASE
    )

    # ============================================================
    # PATTERN 4: "Title at Company (Dates)"
    # ============================================================
    pat_at = re.compile(
        r'^(.+?)\s+(?:at|@)\s+(.+?)\s*'
        r'\(?\s*([A-Za-z]+\s*\d{4}|\d{4})\s*[-to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)\)?',
        re.IGNORECASE
    )

    # ============================================================
    # PATTERN 5: Date-first "2020-2023 | Title at Company"
    # ============================================================
    pat_date_first = re.compile(
        r'^([A-Za-z]+\s*\d{4}|\d{4})\s*[-to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)\s*[\|:]+\s*(.+)',
        re.IGNORECASE
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        if len(line) < 5:
            i += 1
            continue

        # Skip bullet lines
        if line.startswith(('•', '\u2022', '-', '\u2013', '*', '\u2192', '\uf0b7', '\uf0d8')):
            i += 1
            continue

        # Try Pattern 1 (3 pipe-separated fields)
        m = pat_pipe_three.match(line)
        if m:
            title, company, start, end = m.groups()
            sig = (title.strip().lower(), company.strip().lower())
            if sig not in seen_signatures:
                roles.append({
                    "job_title": title.strip(),
                    "company": company.strip(),
                    "start_date": start.strip(),
                    "end_date": end.strip(),
                    "duration_months": _approx_months(start, end),
                })
                seen_signatures.add(sig)
            i += 1
            continue

        # Try Pattern 2 (Title Company | Dates) — needs split
        m = pat_no_sep.match(line)
        if m:
            head, start, end = m.groups()
            title, company = _split_title_and_company(head)
            if title and company:
                sig = (title.lower(), company.lower())
                if sig not in seen_signatures:
                    roles.append({
                        "job_title": title,
                        "company": company,
                        "start_date": start.strip(),
                        "end_date": end.strip(),
                        "duration_months": _approx_months(start, end),
                    })
                    seen_signatures.add(sig)
            i += 1
            continue

        # Try Pattern 4 (Title at Company)
        m = pat_at.match(line)
        if m:
            title, company, start, end = m.groups()
            sig = (title.strip().lower(), company.strip().lower())
            if sig not in seen_signatures:
                roles.append({
                    "job_title": title.strip(),
                    "company": company.strip(),
                    "start_date": start.strip(),
                    "end_date": end.strip(),
                    "duration_months": _approx_months(start, end),
                })
                seen_signatures.add(sig)
            i += 1
            continue

        # Try Pattern 5 (Date-first)
        m = pat_date_first.match(line)
        if m:
            start, end, rest = m.groups()
            title, company = _split_title_and_company(rest)
            sig = (title.lower(), company.lower())
            if sig not in seen_signatures:
                roles.append({
                    "job_title": title,
                    "company": company,
                    "start_date": start.strip(),
                    "end_date": end.strip(),
                    "duration_months": _approx_months(start, end),
                })
                seen_signatures.add(sig)
            i += 1
            continue

        # PATTERN 3: Two-line stacked (Healthcare style)
        # Current line might be a title; one of the next 1-3 lines might
        # have "Company | Dates" (sidebar pollution may have inserted noise)
        if _line_could_be_title(line):
            # Look ahead up to 3 lines for "Company | Dates"
            found = False
            for offset in range(1, 4):
                if i + offset >= len(lines):
                    break
                next_line = lines[i + offset]
                m_next = pat_company_dates.match(next_line)
                if m_next:
                    company, start, end = m_next.groups()
                    title = line.strip()
                    sig = (title.lower(), company.strip().lower())
                    if sig not in seen_signatures:
                        roles.append({
                            "job_title": title,
                            "company": company.strip(),
                            "start_date": start.strip(),
                            "end_date": end.strip(),
                            "duration_months": _approx_months(start, end),
                        })
                        seen_signatures.add(sig)
                    i += offset + 1
                    found = True
                    break
            if found:
                continue

        i += 1

    return roles


def _line_could_be_title(line: str) -> bool:
    """Heuristic: is this line plausibly a job title?"""
    line = line.strip()
    if not line or len(line) > 80 or len(line) < 5:
        return False
    if re.search(r'[@:/\\]', line):
        return False
    if re.search(r'\d{3,}', line):
        return False
    # Should not start with bullet
    if line[0] in {'•', '\u2022', '-', '*'}:
        return False
    # Should contain a role keyword
    line_lower = line.lower()
    return any(kw in line_lower for kw in ROLE_SUFFIXES)


def _approx_months(start: str, end: str) -> int:
    """Compute approximate months between two date strings."""
    if not start or not end:
        return 0
    end_lower = end.lower().strip()
    today_year = 2026
    today_month = 5

    # Parse start
    s_match = re.search(r'([A-Za-z]+)?\s*(\d{4})', start)
    if not s_match:
        return 0
    s_month_str, s_year = s_match.groups()
    s_year = int(s_year)
    s_month = _month_to_int(s_month_str) if s_month_str else 1

    # Parse end
    if end_lower in {"present", "current"}:
        e_year, e_month = today_year, today_month
    else:
        e_match = re.search(r'([A-Za-z]+)?\s*(\d{4})', end)
        if not e_match:
            return 0
        e_month_str, e_year = e_match.groups()
        e_year = int(e_year)
        e_month = _month_to_int(e_month_str) if e_month_str else 12

    return max(0, (e_year - s_year) * 12 + (e_month - s_month))


def _month_to_int(month_str: str) -> int:
    if not month_str:
        return 1
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10,
        "november": 11, "december": 12,
    }
    return months.get(month_str.strip().lower()[:4], 1)


def _total_months_from_roles(roles: List[Dict]) -> int:
    """Sum unique role durations in months."""
    return sum(r.get("duration_months", 0) for r in roles)


def _estimate_total_months_from_text(text: str) -> int:
    """Last-resort estimate from 'X years' phrases."""
    text_l = text.lower()
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*\+?\s*years?', text_l)
    if not matches:
        return 0
    try:
        max_years = max(float(m) for m in matches)
        return int(max_years * 12)
    except ValueError:
        return 0


def extract_experience_safe(cleaned_text: str) -> dict:
    """
    Three-tier fallback:
      1. structured experience builder (if available + works)
      2. universal multi-pattern extractor
      3. text-based years estimate
    """
    # Tier 1: structured
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
        except Exception as e:
            logger.debug(f"build_structured_experience failed: {e}")

    # Tier 2: universal pattern extractor
    universal_roles = _extract_roles_universal(cleaned_text)
    if universal_roles:
        total_months = _total_months_from_roles(universal_roles)
        # If duration_months were 0 across the board, fall back to text estimate
        if total_months == 0:
            total_months = _estimate_total_months_from_text(cleaned_text)
        return {
            "entries": universal_roles,
            "total_experience_months": total_months,
            "extraction_method": "universal_patterns",
        }

    # Tier 3: text-based year estimate
    text_months = _estimate_total_months_from_text(cleaned_text)
    return {
        "entries": [],
        "total_experience_months": text_months,
        "extraction_method": "years_estimate" if text_months else "none",
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


def process_resumes(skip_existing: bool = False) -> dict:
    """
    Process all resumes in INPUT_FOLDER and write parsed JSONs to OUTPUT_FOLDER.

    Args:
        skip_existing: if True, skip resumes that already have a non-null parsed JSON.

    Returns:
        Dict summary: {processed, skipped, failed, warnings}
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

    summary = {"processed": 0, "skipped": 0, "failed": 0, "warnings": {}}

    logger.info(f"Found {len(files)} resume(s) in {INPUT_FOLDER}")
    method_counts = {}

    for file in files:
        out_name = os.path.splitext(file)[0] + ".json"
        output_path = os.path.join(OUTPUT_FOLDER, out_name)

        if skip_existing and os.path.exists(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing and existing.get("clean_text") and existing.get("roles"):
                    summary["skipped"] += 1
                    continue
            except Exception:
                pass  # corrupt → reprocess

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
            method = parsed.get('_extraction_method', 'unknown')
            method_counts[method] = method_counts.get(method, 0) + 1
            logger.info(
                f"  Saved -> {out_name}  (method={method}, "
                f"roles={len(parsed['roles'])}, edu={len(parsed['education'])}, "
                f"yrs={parsed['experience']})"
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
    logger.info(f"Extraction methods used: {method_counts}")
    if summary["warnings"]:
        warn_count = len(summary["warnings"])
        logger.warning(f"{warn_count} resume(s) have warnings (showing first 10):")
        for fn, warns in list(summary["warnings"].items())[:10]:
            logger.warning(f"  - {fn}: {', '.join(warns)}")
    logger.info(f"Output: {OUTPUT_FOLDER}")

    return summary


if __name__ == "__main__":
    process_resumes(skip_existing=False)
