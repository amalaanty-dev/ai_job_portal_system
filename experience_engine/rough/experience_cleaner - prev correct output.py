import re
import logging

logger = logging.getLogger(__name__)

# ── Prefix noise injected by the sectioner ────────────────────────────
# These are section-label words that bleed into job_title / company when
# the sectioner concatenates adjacent lines without proper boundaries.
# Stripped as leading tokens only — never mid-string.

_TITLE_NOISE_PREFIXES: list[str] = [
    r"^[•\-–—*▪►◆]+\s*",
    r"^(a|an|the)\s+",
    r"^(tools?|technologies|technology|tech|languages?|language|skills?|"
    r"frameworks?|libraries|platforms?|software|systems?|applications?|"
    r"certifications?|achievements?|responsibilities|duties|summary|"
    r"overview|profile|objective|highlights?|accomplishments?|awards?|"
    r"education|training|courses?|projects?|activities?|interests?|"
    r"references?|publications?|patents?|licenses?|affiliations?)\s+",
]

_COMPANY_NOISE_PREFIXES: list[str] = [
    r"^[•\-–—*▪►◆]+\s*",
    r"^(a|an|the)\s+",
    r"^(technologies|technology|tech|languages?|tools?|skills?|"
    r"frameworks?|platforms?|software|systems?)\s*",
]

_TITLE_RE   = re.compile("|".join(_TITLE_NOISE_PREFIXES),   re.IGNORECASE)
_COMPANY_RE = re.compile("|".join(_COMPANY_NOISE_PREFIXES), re.IGNORECASE)

_MIN_FIELD_LEN = 2


def _strip_leading_noise(value: str, pattern: re.Pattern) -> str:
    """
    Repeatedly strip leading noise tokens until the value stabilises.
    Handles stacked prefixes like 'tools a clinical data analyst'.
    """
    prev = None
    while prev != value:
        prev  = value
        value = pattern.sub("", value).strip()
    return value


def clean_experience_entry(entry: dict) -> dict | None:
    """
    Clean a single structured experience dict.

    Strips sectioner bleed-in prefixes from job_title and company.
    Returns None if either field is too short after cleaning (junk entry).
    The input dict is never mutated — a new dict is returned.
    """
    raw_title   = entry.get("job_title", "").strip()
    raw_company = entry.get("company",   "").strip()

    clean_title   = _strip_leading_noise(raw_title,   _TITLE_RE)
    clean_company = _strip_leading_noise(raw_company, _COMPANY_RE)

    if len(clean_title) < _MIN_FIELD_LEN or len(clean_company) < _MIN_FIELD_LEN:
        logger.debug(
            "Dropping entry after cleaning — fields too short: "
            "title=%r → %r | company=%r → %r",
            raw_title, clean_title, raw_company, clean_company,
        )
        return None

    if clean_title != raw_title or clean_company != raw_company:
        logger.info(
            "Cleaned entry  title: %r → %r | company: %r → %r",
            raw_title, clean_title, raw_company, clean_company,
        )

    return {
        **entry,
        "job_title": clean_title,
        "company":   clean_company,
    }


def clean_experiences(experiences: list[dict]) -> list[dict]:
    """
    Clean a list of structured experience dicts.
    Entries that reduce to junk after cleaning are dropped and logged.
    Returns a new list; the original is never mutated.
    """
    cleaned = []
    for entry in experiences:
        result = clean_experience_entry(entry)
        if result is not None:
            cleaned.append(result)

    dropped = len(experiences) - len(cleaned)
    if dropped:
        logger.warning(
            "⚠️  clean_experiences: dropped %d entr%s that were junk after cleaning",
            dropped, "y" if dropped == 1 else "ies",
        )

    return cleaned
