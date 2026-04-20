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

# ── Section headers — longest phrases first (prevent partial matches) ─
SECTION_HEADERS = [
    ("summary",        "professional summary"),
    ("summary",        "career summary"),
    ("summary",        "career objective"),
    ("summary",        "about me"),
    ("summary",        "objective"),
    ("summary",        "profile"),
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
    ("education",      "academic background"),
    ("education",      "academic qualifications"),
    ("education",      "qualifications"),
    ("education",      "education"),
    ("projects",       "personal projects"),
    ("projects",       "academic projects"),
    ("projects",       "key projects"),
    ("projects",       "notable projects"),
    ("projects",       "projects"),
    ("certifications", "professional certifications"),
    ("certifications", "certifications & licenses"),
    ("certifications", "certifications and licenses"),
    ("certifications", "certifications"),
    ("certifications", "licenses"),
    ("certifications", "certificates"),
]

# ── CRITICAL: "skills" and "technologies" are NOT section break triggers
# because they appear mid-sentence constantly in these resumes.
# "core skills" and "work experience" ARE reliable triggers.
# Only inject breaks for these confirmed-safe standalone headers:
_SAFE_BREAK_PHRASES = [
    "professional summary",
    "career summary",
    "career objective",
    "about me",
    "core skills",
    "technical skills",
    "core competencies",
    "key skills",
    "areas of expertise",
    "work experience",
    "professional experience",
    "employment history",
    "work history",
    "career history",
    "educational background",
    "academic background",
    "academic qualifications",
    "education",
    "personal projects",
    "academic projects",
    "key projects",
    "notable projects",
    "projects",
    "professional certifications",
    "certifications & licenses",
    "certifications and licenses",
    "certifications",
    "certificates",
]


# ── Helpers ───────────────────────────────────────────────────────────
def _clean_text(text: str) -> str:
    """Strip PDF artifacts and normalize whitespace."""
    text = re.sub(r'\bcid\s*\d+\b', ' ', text)     # strip cid 127 tokens
    text = re.sub(r'\x00', ' ', text)               # null bytes
    text = re.sub(r'[ \t]{2,}', ' ', text)          # collapse spaces
    return text.strip()


def _inject_section_breaks(text: str) -> str:
    """
    Inject newlines before confirmed-safe section header phrases only.

    Key insight from actual resume data:
        - "experience" alone fires mid-sentence ("3 years of experience")
        - "skills" alone fires mid-sentence ("analytical skills")
        - "technologies" fires mid-sentence constantly
        - SAFE triggers: "work experience", "core skills", "professional summary" etc.
          because these multi-word phrases don't appear mid-sentence naturally.

    Uses lookbehind to only inject break when preceded by a space or
    start-of-string — not when embedded inside a longer word.
    """
    # Sort by length descending — longest phrases matched first
    phrases_sorted = sorted(_SAFE_BREAK_PHRASES, key=len, reverse=True)
    pattern = r'(?i)(?<!\w)(' + '|'.join(re.escape(p) for p in phrases_sorted) + r')(?!\w)'

    text = re.sub(pattern, r'\n\1\n', text)
    return text


def _detect_section(line: str) -> str | None:
    """
    Return section name if line exactly matches a known header phrase.
    Full-line match only — prevents mid-sentence content from switching sections.
    """
    cleaned = line.strip().lower()
    # Check longest phrases first
    for section, phrase in SECTION_HEADERS:
        if cleaned == phrase:
            return section
    return None


# ── JOB ENTRY DETECTOR ────────────────────────────────────────────────
# Fallback: detect lines that look like job entries even if misclassified
_JOB_ENTRY_PATTERN = re.compile(
    r'(?:'
    r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}'  # month year
    r'|'
    r'\b\d{4}\s*[-–]\s*(?:\d{4}|present|current)\b'                       # year-year
    r')',
    re.IGNORECASE
)


def _looks_like_job_entry(line: str) -> bool:
    """Return True if line contains a date range typical of a job entry."""
    return bool(_JOB_ENTRY_PATTERN.search(line))


# ── MAIN SEGMENTER ────────────────────────────────────────────────────
def segment_resume(text: str) -> dict:
    """
    Segment a single-line resume blob into labelled sections.

    Pipeline:
        1. Clean PDF noise (cid tokens, null bytes)
        2. Inject \\n only before SAFE multi-word section headers
        3. Walk lines — exact header match → switch section
        4. Fallback: lines with date ranges → force into experience
           if current section is skills/summary (common misclassification)
        5. Non-header lines → append to current section bucket

    Returns:
        Dict with keys: summary, skills, experience, education,
                        projects, certifications, other
    """
    text = _clean_text(text)
    text = _inject_section_breaks(text)

    lines = text.split('\n')

    sections = {
        "summary":        [],
        "skills":         [],
        "experience":     [],
        "education":      [],
        "projects":       [],
        "certifications": [],
        "other":          [],
    }

    current_section = "other"

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # ── Check for exact section header ────────────────────────────
        detected = _detect_section(line)
        if detected:
            current_section = detected
            continue                         # header is not content

        # ── Fallback: job entry date pattern in wrong section ─────────
        # If we're in skills/summary but line has a job date range,
        # it's a misclassified experience entry — reroute it
        if current_section in ("skills", "summary", "other"):
            if _looks_like_job_entry(line):
                sections["experience"].append(line)
                current_section = "experience"  # stay in experience for following lines
                continue

        sections[current_section].append(line)

    return sections


# ── PROCESS ALL RESUMES ───────────────────────────────────────────────
def process_resumes():
    files = [f for f in os.listdir(INPUT_FOLDER) if f.endswith(".json")]

    if not files:
        logger.error("❌ No JSON files found in: %s", INPUT_FOLDER)
        return

    logger.info("📄 Found %d resume(s) to process\n", len(files))

    processed = 0
    skipped   = 0

    for file in files:
        file_path = os.path.join(INPUT_FOLDER, file)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                parsed_data = json.load(f)
        except Exception as e:
            logger.warning("❌ Could not load '%s': %s", file, e)
            skipped += 1
            continue

        resume_text = parsed_data.get("clean_text", "")

        if not resume_text:
            logger.warning("⚠️ '%s' — 'clean_text' missing or empty", file)
            skipped += 1
            continue

        sections = segment_resume(resume_text)

        # ── Warn if experience still empty ────────────────────────────
        if not sections["experience"]:
            logger.warning(
                "⚠️ '%s' — experience section empty after segmentation",
                file
            )

        output_file = file.replace(".json", "_sections.json")
        output_path = os.path.join(OUTPUT_FOLDER, output_file)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(sections, f, indent=4)
        except Exception as e:
            logger.warning("❌ Could not write '%s': %s", output_file, e)
            skipped += 1
            continue

        logger.info(
            "✅ %-45s → summary=%d | skills=%d | experience=%d | education=%d | projects=%d | certs=%d",
            file,
            len(sections["summary"]),
            len(sections["skills"]),
            len(sections["experience"]),
            len(sections["education"]),
            len(sections["projects"]),
            len(sections["certifications"]),
        )

        processed += 1

    # ── Summary ───────────────────────────────────────────────────────
    logger.info("─" * 60)
    logger.info("✅ Section Classification Completed")
    logger.info("Processed : %d", processed)
    logger.info("Skipped   : %d", skipped)
    logger.info("Output    : %s", OUTPUT_FOLDER)


if __name__ == "__main__":
    process_resumes()