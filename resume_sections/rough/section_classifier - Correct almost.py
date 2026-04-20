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
INPUT_FOLDER  = "data/resumes/parsed_resumes/json/"
OUTPUT_FOLDER = "data/resumes/sectioned_resumes/"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Section headers ──────────────────────────────────────────────────
SECTION_HEADERS = [
    ("skills",         "technical skills"),
    ("skills",         "core competencies"),
    ("skills",         "core skills"),
    ("skills",         "key skills"),
    ("skills",         "areas of expertise"),
    ("experience",     "work experience"),
    ("experience",     "professional experience"),
    ("experience",     "employment history"),
    ("experience",     "work history"),
    ("experience",     "career history"),
    ("education",      "educational background"),
    ("education",      "academic qualifications"),
    ("education",      "education"),
    ("projects",       "personal projects"),
    ("projects",       "academic projects"),
    ("projects",       "projects"),
    ("certifications", "professional certifications"),
    ("certifications", "certifications"),
    ("achievements",   "key achievements"),
    ("achievements",   "achievements"),
    ("achievements",   "honors and awards"),
    ("achievements",   "awards"),
    ("achievements",   "rewards"),
]

_SAFE_BREAK_PHRASES = [phrase for _, phrase in SECTION_HEADERS] + [
    "professional summary", "career summary", "objective", "profile", "summary"
]

# ── Sidebar / noise labels that bleed in from multi-column PDFs ───────
# These are standalone uppercase labels the PDF parser injects mid-line.
# They carry no content themselves — strip them out entirely.
_SIDEBAR_NOISE_PATTERN = re.compile(
    r'\b(TECHNOLOGIES|TOOLS\s*&?|LANGUAGES|SOFT\s+SKILLS|TOOLS)\b',
    re.IGNORECASE
)

# Lines that are purely structural labels with no real content
_DISCARD_LINES = {
    "technologies", "tools &", "tools", "languages", "soft skills",
    "tools & technologies",
}

# ── Helpers ───────────────────────────────────────────────────────────
def _clean_text(text: str) -> str:
    # FIX 1: Strip both forms — (cid:NNN) with parens AND bare cid NNN
    text = re.sub(r'\(cid:\s*\d+\)', ' ', text)
    text = re.sub(r'\bcid\s*\d+\b',   ' ', text)
    text = re.sub(r'\x00', ' ', text)
    # FIX 2: Strip sidebar noise labels that bleed onto content lines
    text = _SIDEBAR_NOISE_PATTERN.sub(' ', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

def _inject_section_breaks(text: str) -> str:
    phrases_sorted = sorted(_SAFE_BREAK_PHRASES, key=len, reverse=True)
    pattern = r'(?i)(?<!\w)(' + '|'.join(re.escape(p) for p in phrases_sorted) + r')(?!\w)'
    return re.sub(pattern, r'\n\1\n', text)

def _detect_section(line: str) -> str | None:
    cleaned = line.strip().lower().rstrip(':')
    for section, phrase in SECTION_HEADERS:
        if cleaned == phrase:
            return section
    return None

def _is_summary_header(line: str) -> bool:
    """Returns True for standalone summary/objective/profile header lines."""
    cleaned = line.strip().lower().rstrip(':')
    return cleaned in {"professional summary", "career summary", "summary", "objective", "profile"}

_JOB_DATE_PATTERN = re.compile(
    r'(?:'
    r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}'
    r'|'
    r'\b\d{4}\s*[-–]\s*(?:\d{4}|present|current)\b'
    r')',
    re.IGNORECASE
)

def _is_achievement_line(line: str) -> bool:
    """Detects if a line is an award/achievement based on keywords."""
    ach_keywords = [
        "awarded", "top performer", "commendation", "recognition",
        "rewarded", "secured fd", "performance award"
    ]
    cleaned = line.lower()
    return any(kw in cleaned for kw in ach_keywords)

def _looks_like_job_header(line: str) -> bool:
    """Identifies role headers using dates, but excludes education and long duty descriptions."""
    if len(line) > 120: return False  # Headers are usually short
    if not bool(_JOB_DATE_PATTERN.search(line)): return False

    academic_keywords = [
        "university", "college", "school", "bba", "mba",
        "btech", "b.sc", "b.com", "degree", "percentage", "%"
    ]
    cleaned = line.lower()
    if any(kw in cleaned for kw in academic_keywords): return False
    if _is_achievement_line(line): return False

    return True

def _is_noise_line(line: str) -> bool:
    """Returns True for pure sidebar label lines that carry no useful content."""
    return line.strip().lower().rstrip(':') in _DISCARD_LINES

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
    in_summary      = False   # absorb summary text into "other" so it doesn't bleed

    for line in lines:
        line = line.strip()
        if not line or line == ".": continue

        # FIX 3: Discard pure sidebar noise lines (TECHNOLOGIES, LANGUAGES, etc.)
        if _is_noise_line(line):
            continue

        # FIX 4: Detect summary headers — park content in "other" until next real section
        if _is_summary_header(line):
            current_section = "other"
            in_summary      = True
            sections["other"].append(f"HEADER: {line}")
            continue

        # 1. Achievement Override
        if _is_achievement_line(line):
            sections["achievements"].append(line)
            in_summary = False
            continue

        # 2. Header Detection
        detected = _detect_section(line)
        if detected:
            current_section = detected
            in_summary      = False
            sections["other"].append(f"HEADER: {line}")
            continue

        # 3. Work Experience Role Detection
        if _looks_like_job_header(line):
            sections["experience"].append({"role_header": line, "duties": []})
            current_section = "experience"
            in_summary      = False
            continue

        # FIX 5: While inside summary block, route everything to "other"
        if in_summary:
            sections["other"].append(line)
            continue

        # 4. Content Routing
        if current_section == "experience":
            if sections["experience"]:
                # Ignore declaration text in duties
                if "hereby declare" in line.lower():
                    sections["other"].append(line)
                else:
                    sections["experience"][-1]["duties"].append(line)
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
        logger.error("❌ No JSON files found in: %s", INPUT_FOLDER)
        return

    for file in files:
        file_path = os.path.join(INPUT_FOLDER, file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception: continue

        sections = segment_resume(data.get("clean_text", ""))
        output_path = os.path.join(OUTPUT_FOLDER, file.replace(".json", "_sections.json"))

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sections, f, indent=4)

        logger.info("✅ %-45s -> roles=%d | ach=%d",
                    file, len(sections["experience"]), len(sections["achievements"]))

if __name__ == "__main__":
    process_resumes()