"""
bias_guards.py
---------------
Bias-reduction guardrails for candidate ranking.

PRD Phase 2 reference: "Bias-reduced candidate scoring".

This module does NOT modify scoring itself (scores come from upstream engines).
It audits each candidate for known bias signals and attaches a
`bias_flags` field that surfaces in the recruiter report.

Flags raised (non-exhaustive):
  - pii_name_present       : full name present in scoring record (should be ID-only)
  - photo_reference        : resume contains a photo URL/reference
  - gender_indicator       : explicit gender/marital-status field
  - age_indicator          : DOB or explicit age field
  - demographic_term       : demographic-coded words in free text

We deliberately only flag, never auto-delete. Recruiters review.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# Keys in a candidate dict that, if present, signal bias risk.
_BIAS_KEY_HINTS: dict[str, str] = {
    "gender":        "gender_indicator",
    "sex":           "gender_indicator",
    "marital_status": "demographic_term",
    "religion":      "demographic_term",
    "nationality":   "demographic_term",
    "date_of_birth": "age_indicator",
    "dob":           "age_indicator",
    "age":           "age_indicator",
    "photo":         "photo_reference",
    "photo_url":     "photo_reference",
    "profile_pic":   "photo_reference",
}

_PHOTO_URL_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp)\b", re.IGNORECASE)


def scan_candidate(candidate: dict) -> list[str]:
    """Return a de-duplicated list of bias flags for a single candidate."""
    flags: set[str] = set()

    for key, flag in _BIAS_KEY_HINTS.items():
        if key in candidate and candidate[key] not in (None, "", []):
            flags.add(flag)

    # Name present alongside scoring data isn't inherently bad, but recruiters
    # should know it's in the record when reviewing "anonymous" rankings.
    if candidate.get("name") or candidate.get("candidate_name"):
        flags.add("pii_name_present")

    # Scan free-text fields for photo URLs.
    for field in ("resume_text", "summary", "about"):
        val = candidate.get(field)
        if isinstance(val, str) and _PHOTO_URL_RE.search(val):
            flags.add("photo_reference")
            break

    return sorted(flags)


def annotate_bias_flags(candidates: list[dict]) -> list[dict]:
    """Attach `bias_flags` to every candidate in-place. Returns the list."""
    flagged = 0
    for c in candidates:
        flags = scan_candidate(c)
        c["bias_flags"] = flags
        if flags:
            flagged += 1
    logger.info("Bias scan: %d / %d candidates carry one or more bias flags",
                flagged, len(candidates))
    return candidates
