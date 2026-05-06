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

Day: shared module
"""

import pdfplumber
import docx
import os
import re
import json
import sys
import logging
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
#                    EXPERIENCE EXTRACTION
# =================================================================
def _fallback_extract_roles(text: str) -> list:
    """
    Lightweight fallback role extractor. Used when build_structured_experience
    is unavailable or returns empty. Looks for patterns like:
        Software Engineer | Microsoft | 2020 - 2023
        Data Engineer at Google (Jan 2020 - Dec 2023)
        Senior Developer, IBM, 2019-2022
    """
    roles = []

    # Common role patterns - title + company + date range
    # Pattern A: "Title | Company | Dates"
    # Note: we anchor each line individually (not multiline regex) to avoid
    # capturing section headers like "PROFESSIONAL EXPERIENCE" together with
    # the role title on the next line.
    pattern_pipe = re.compile(
        r'^([A-Z][A-Za-z\s\-/&]+?)\s*[\|]\s*([A-Z][A-Za-z0-9\s\.\,\&]+?)\s*[\|]\s*'
        r'([A-Za-z]+\s*\d{4}|\d{4})\s*[\-\u2013\u2014to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)',
        re.IGNORECASE
    )

    # Pattern B: "Title at Company"
    pattern_at = re.compile(
        r'^([A-Z][A-Za-z\s\-/&]+?)\s+(?:at|@)\s+([A-Z][A-Za-z0-9\s\.\,\&]+?)\s*'
        r'\(?\s*([A-Za-z]+\s*\d{4}|\d{4})\s*[\-\u2013\u2014to]+\s*([A-Za-z]+\s*\d{4}|\d{4}|present|current)\)?',
        re.IGNORECASE
    )

    # Process line by line to avoid cross-line false matches
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for pat in [pattern_pipe, pattern_at]:
            m = pat.search(line)
            if m:
                title, company, start, end = m.groups()
                roles.append({
                    "job_title": title.strip(),
                    "company": company.strip(),
                    "start_date": start.strip(),
                    "end_date": end.strip(),
                    "duration_months": 0,  # heuristic only — proper calc by experience_engine
                })
                break  # only one role per line

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
