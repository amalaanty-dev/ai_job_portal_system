"""
resume_sections/section_classifier.py
=====================================
Classifies resume content into sections (skills, experience, education,
projects, certifications, achievements, other).

FIXES applied to previous version:
1. "Date of Birth", "DOB", "Issued" etc. no longer treated as role headers
2. "GENERAL DETAILS", "PERSONAL DETAILS" sections recognized & routed to "other"
3. Section break injection no longer mangles "MACHINE LEARNING PROJECTS"
4. Stricter role-header detection (must look like Job Title at Company + dates)
5. Skills section filters out non-skill garbage ("MACHINE LEARNING" leftover)
6. Folder paths use uppercase JSON to match downstream pipelines

Day: shared module
"""

import os
import re
import json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── Paths ─────────────────────────────────────────────────────────────
INPUT_FOLDER  = "data/resumes/parsed_resumes/JSON/"     # uppercase JSON
OUTPUT_FOLDER = "data/resumes/sectioned_resumes/"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Section headers ──────────────────────────────────────────────────
SECTION_HEADERS = [
    ("skills",         "technical skills"),
    ("skills",         "core technical skills"),
    ("skills",         "core competencies"),
    ("skills",         "core skills"),
    ("skills",         "key skills"),
    ("skills",         "skills"),
    ("skills",         "areas of expertise"),
    ("experience",     "work experience"),
    ("experience",     "professional experience"),
    ("experience",     "employment history"),
    ("experience",     "work history"),
    ("experience",     "career history"),
    ("experience",     "experience"),
    ("education",      "educational background"),
    ("education",      "academic qualifications"),
    ("education",      "education"),
    ("projects",       "machine learning projects"),
    ("projects",       "personal projects"),
    ("projects",       "academic projects"),
    ("projects",       "key projects"),
    ("projects",       "projects"),
    ("certifications", "professional certifications"),
    ("certifications", "certifications"),
    ("achievements",   "key achievements"),
    ("achievements",   "achievements"),
    ("achievements",   "honors and awards"),
    ("achievements",   "awards"),
    ("achievements",   "rewards"),
    # NEW: route "general details" / "personal details" to "other"
    ("other",          "general details"),
    ("other",          "personal details"),
    ("other",          "additional information"),
    ("other",          "languages"),
    ("other",          "hobbies"),
    ("other",          "interests"),
    ("other",          "references"),
]

_SAFE_BREAK_PHRASES = [phrase for _, phrase in SECTION_HEADERS] + [
    "professional summary", "career summary", "objective", "profile", "summary"
]

# ── Sidebar / noise labels that bleed in from multi-column PDFs ───────
_SIDEBAR_NOISE_PATTERN = re.compile(
    r'\b(TECHNOLOGIES|TOOLS\s*&?|LANGUAGES|SOFT\s+SKILLS|TOOLS)\b',
    re.IGNORECASE
)

_DISCARD_LINES = {
    "technologies", "tools &", "tools", "languages", "soft skills",
    "tools & technologies",
}

# ── Lines that should NEVER be considered role headers ─────────────────
# (catches "Date of Birth: 15 June 1995" type pollution)
_NON_ROLE_LINE_PATTERNS = [
    re.compile(r'\bdate\s+of\s+birth\b',     re.IGNORECASE),
    re.compile(r'\bdob\b',                    re.IGNORECASE),
    re.compile(r'\bborn\b\s*[:\-]',          re.IGNORECASE),
    re.compile(r'\bissued\s*(on|date)?\b',   re.IGNORECASE),
    re.compile(r'\bvalid\s+(till|until)\b',  re.IGNORECASE),
    re.compile(r'\bnationality\b',           re.IGNORECASE),
    re.compile(r'\bavailability\b',          re.IGNORECASE),
    re.compile(r'\blinkedin\b',              re.IGNORECASE),
    re.compile(r'\bgithub\b',                re.IGNORECASE),
    re.compile(r'\bportfolio\b',             re.IGNORECASE),
    re.compile(r'\bphone\b',                 re.IGNORECASE),
    re.compile(r'\bemail\b',                 re.IGNORECASE),
    re.compile(r'\baddress\b',               re.IGNORECASE),
    re.compile(r'\bmarried\b|\bsingle\b',    re.IGNORECASE),
    re.compile(r'\bmother\s+tongue\b',       re.IGNORECASE),
    re.compile(r'\bsex\s*[:\-]\s*\w',        re.IGNORECASE),
    re.compile(r'\bgender\s*[:\-]\s*\w',     re.IGNORECASE),
    re.compile(r'^@',                         re.IGNORECASE),
    re.compile(r'\b\w+@\w+\.\w+\b'),  # email
]


# ── Helpers ───────────────────────────────────────────────────────────
def _clean_text(text: str) -> str:
    text = re.sub(r'\(cid:\s*\d+\)', ' ', text)
    text = re.sub(r'\bcid\s*\d+\b', ' ', text)
    text = re.sub(r'\x00', ' ', text)
    text = _SIDEBAR_NOISE_PATTERN.sub(' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _inject_section_breaks(text: str) -> str:
    """
    Insert newlines around section header phrases so they appear on their own line.

    BUGFIX: Sort longer phrases first so 'machine learning projects' is matched
    before 'projects', preventing 'MACHINE LEARNING' from leaking into 'skills'.
    """
    phrases_sorted = sorted(_SAFE_BREAK_PHRASES, key=len, reverse=True)
    pattern = (
        r'(?i)(?<!\w)('
        + '|'.join(re.escape(p) for p in phrases_sorted)
        + r')(?!\w)'
    )
    return re.sub(pattern, r'\n\1\n', text)


def _detect_section(line: str) -> str:
    """Returns section key if line is a recognized section header, else None."""
    clean_line = line.lower().replace("header:", "").strip().rstrip(':')

    # Sort longer phrases first to win over shorter ones
    sorted_headers = sorted(SECTION_HEADERS, key=lambda x: -len(x[1]))
    for section_key, header_phrase in sorted_headers:
        if clean_line == header_phrase:
            return section_key
    return None


def _is_summary_header(line: str) -> bool:
    cleaned = line.strip().lower().rstrip(':')
    return cleaned in {
        "professional summary", "career summary", "summary",
        "objective", "career objective", "profile",
    }


_JOB_DATE_PATTERN = re.compile(
    r'(?:'
    r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}'
    r'|'
    r'\b\d{4}\s*[-\u2013]\s*(?:\d{4}|present|current)\b'
    r')',
    re.IGNORECASE
)


def _is_achievement_line(line: str) -> bool:
    ach_keywords = [
        "awarded", "top performer", "commendation", "recognition",
        "rewarded", "secured fd", "performance award",
    ]
    cleaned = line.lower()
    return any(kw in cleaned for kw in ach_keywords)


def _is_blacklisted_role_line(line: str) -> bool:
    """
    Returns True if this line should NEVER be considered a role header,
    even if it contains a date pattern. Catches 'Date of Birth: 15 June 1995',
    'Issued: 2020', 'LinkedIn: ...', etc.
    """
    for pat in _NON_ROLE_LINE_PATTERNS:
        if pat.search(line):
            return True
    return False


def _looks_like_job_header(line: str) -> bool:
    """
    Identifies role headers using a combination of signals:
      1. Must contain a date pattern
      2. Length < 120 chars
      3. NOT in academic/education line
      4. NOT in achievement line
      5. NOT a blacklisted line (DOB, LinkedIn, Issued, etc.)
      6. Should look like a job title (contains a separator or job keywords)
    """
    if len(line) > 120:
        return False
    if not bool(_JOB_DATE_PATTERN.search(line)):
        return False

    # Education
    academic_keywords = [
        "university", "college", "school", "bba", "mba", "btech", "b.sc",
        "b.com", "degree", "percentage", "%", "cgpa",
    ]
    cleaned = line.lower()
    if any(kw in cleaned for kw in academic_keywords):
        return False
    if _is_achievement_line(line):
        return False

    # NEW: blacklisted role lines (DOB, LinkedIn, Issued, etc.)
    if _is_blacklisted_role_line(line):
        return False

    # NEW: must contain a job-title-like separator OR job keyword
    # (helps avoid generic dated lines like "Project completed: 2023")
    has_separator = any(sep in line for sep in ['|', ' at ', ' @ ', ',', ' - '])
    job_keywords = [
        "developer", "engineer", "manager", "executive", "analyst",
        "scientist", "designer", "architect", "consultant", "officer",
        "associate", "lead", "director", "specialist", "administrator",
        "coordinator", "technician", "supervisor", "intern",
    ]
    has_job_word = any(kw in cleaned for kw in job_keywords)

    if not (has_separator or has_job_word):
        return False

    return True


def _is_noise_line(line: str) -> bool:
    return line.strip().lower().rstrip(':') in _DISCARD_LINES


def _is_certification_content(line: str) -> bool:
    keywords = [
        "certificate", "certification", "certified", "coursera",
        "udemy", "training",
    ]
    return any(k in line.lower() for k in keywords)


def _is_skill_like(line: str) -> bool:
    """
    Heuristic: looks like a skill line (short comma/separator-separated tokens)
    rather than free-form sentence prose. Used to filter out section-header
    leftovers that landed in skills.
    """
    line = line.strip()
    if not line or len(line) > 200:
        return False
    # Reject full sentences (start with verb-like, end with period)
    if line.endswith('.') and len(line.split()) > 6:
        return False
    # Reject ALL-CAPS short lines that are likely headers ("MACHINE LEARNING")
    if line == line.upper() and len(line) < 30 and len(line.split()) <= 4:
        # check if it's likely a header (no commas, no specific tools)
        if ',' not in line and ':' not in line:
            return False
    return True


# ── MAIN SEGMENTER ────────────────────────────────────────────────────
def segment_resume(text: str) -> dict:
    text = _clean_text(text)
    text = _inject_section_breaks(text)
    lines = text.split('\n')

    sections = {
        "skills": [], "experience": [], "education": [],
        "projects": [], "certifications": [], "achievements": [], "other": []
    }

    current_section = "other"
    in_summary      = False

    for line in lines:
        line = line.strip()
        if not line or line == ".":
            continue

        # 1. Discard pure sidebar noise lines
        if _is_noise_line(line):
            continue

        # 2. Detect summary headers
        if _is_summary_header(line):
            current_section = "other"
            in_summary      = True
            sections["other"].append(f"HEADER: {line}")
            continue

        # 3. Achievement Override (only when we're not in projects/education)
        if _is_achievement_line(line) and current_section not in {"projects", "education"}:
            sections["achievements"].append(line)
            in_summary = False
            continue

        # 4. Header Detection
        detected = _detect_section(line)
        if detected:
            current_section = detected
            in_summary      = False
            sections["other"].append(f"HEADER: {line}")
            continue

        # 5. Work Experience Role Detection
        # Only trigger if we are CURRENTLY in experience section,
        # OR the line is unambiguously a job header outside any clear section.
        # This prevents random dated lines under "GENERAL DETAILS" from
        # being treated as roles.
        if _looks_like_job_header(line):
            # Extra guard: if we just left an "other" section after seeing
            # "GENERAL DETAILS"/"PERSONAL DETAILS", don't add roles
            if current_section == "other":
                # Check if we previously saw a "general details"-like header
                last_headers = [
                    h for h in sections["other"][-3:]
                    if h.startswith("HEADER:")
                ]
                if any(
                    "general details" in h.lower() or "personal details" in h.lower()
                    for h in last_headers
                ):
                    sections["other"].append(line)
                    continue
            sections["experience"].append({"role_header": line, "duties": []})
            current_section = "experience"
            in_summary      = False
            continue

        # 6. Education & Certification Rerouting
        if current_section == "education":
            if _is_certification_content(line):
                sections["certifications"].append(line)
            else:
                sections["education"].append(line)
            continue

        # 7. Summary routing
        if in_summary:
            sections["other"].append(line)
            continue

        # 8. Content Routing (Final bucket)
        if current_section == "experience":
            if sections["experience"]:
                if "hereby declare" in line.lower():
                    sections["other"].append(line)
                else:
                    sections["experience"][-1]["duties"].append(line)
            else:
                sections["other"].append(line)
        elif current_section == "skills":
            # Filter garbage from skills
            if _is_skill_like(line):
                sections["skills"].append(line)
            else:
                sections["other"].append(line)
        elif current_section in sections and current_section != "other":
            sections[current_section].append(line)
        else:
            sections["other"].append(line)

    return sections


# ── PROCESS ALL RESUMES ───────────────────────────────────────────────
def process_resumes():
    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".json")]
    if not files:
        logger.error("No JSON files found in: %s", INPUT_FOLDER)
        return

    success = 0
    for file in files:
        file_path = os.path.join(INPUT_FOLDER, file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to load %s: %s", file, e)
            continue

        sections = segment_resume(data.get("clean_text", ""))
        output_path = os.path.join(
            OUTPUT_FOLDER, file.replace(".json", "_sections.json")
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sections, f, indent=4, ensure_ascii=False)

        logger.info(
            "%-50s -> roles=%d  skills=%d  edu=%d  proj=%d  cert=%d  ach=%d",
            file,
            len(sections["experience"]),
            len(sections["skills"]),
            len(sections["education"]),
            len(sections["projects"]),
            len(sections["certifications"]),
            len(sections["achievements"]),
        )
        success += 1

    logger.info("-" * 70)
    logger.info("Sectioned %d/%d resumes -> %s", success, len(files), OUTPUT_FOLDER)


if __name__ == "__main__":
    process_resumes()
