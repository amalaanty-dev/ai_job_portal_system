"""
filters.py
-----------
Hard-filter gate. Applied BEFORE composite scoring so that candidates who
don't meet minimum eligibility are rejected up front, saving compute and
keeping the shortlist honest.

PRD Phase 2 reference: "Experience & qualification filtering".
"""

from __future__ import annotations

import logging
from typing import Any

from utils.io_utils import safe_get

logger = logging.getLogger(__name__)


def _candidate_experience_years(candidate: dict) -> float:
    """Best-effort extraction of a candidate's total experience in years."""
    for path in [
        ("total_experience_years",),
        ("experience", "total_years"),
        ("experience_engine", "total_years"),
        ("experience", "years"),
        ("parsed_resume", "total_experience_years"),
    ]:
        v = safe_get(candidate, *path)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return 0.0


def _candidate_skills(candidate: dict) -> set[str]:
    """Collect skills from common resume-parsing output shapes."""
    raw_sources = [
        safe_get(candidate, "skills") or [],
        safe_get(candidate, "parsed_resume", "skills") or [],
        safe_get(candidate, "skill_engine", "skills_found") or [],
        safe_get(candidate, "skill_engine", "matched_skills") or [],
    ]
    collected: set[str] = set()
    for src in raw_sources:
        if isinstance(src, dict):
            src = list(src.keys())
        if isinstance(src, (list, tuple, set)):
            for s in src:
                if isinstance(s, str) and s.strip():
                    collected.add(s.strip().lower())
                elif isinstance(s, dict):
                    name = s.get("name") or s.get("skill")
                    if isinstance(name, str) and name.strip():
                        collected.add(name.strip().lower())
    return collected


def apply_hard_filters(candidate: dict, filter_rules: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Evaluate hard filters. Returns (passed, failure_reasons).

    filter_rules keys:
      - min_experience_years  (float)
      - required_skills       (list[str])   ALL must be present
    """
    reasons: list[str] = []

    # 1) Minimum years of experience
    min_exp = float(filter_rules.get("min_experience_years") or 0)
    if min_exp > 0:
        exp = _candidate_experience_years(candidate)
        if exp < min_exp:
            reasons.append(f"min_experience_not_met (has {exp}, needs {min_exp})")

    # 2) Required skills (case-insensitive AND match)
    required = [s.lower().strip() for s in (filter_rules.get("required_skills") or []) if s]
    if required:
        have = _candidate_skills(candidate)
        missing = [s for s in required if s not in have]
        if missing:
            reasons.append(f"missing_required_skills: {missing}")

    return (len(reasons) == 0), reasons
