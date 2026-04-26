"""
shortlister.py
---------------
Shortlisting automation module.

Assigns each ranked candidate to one of three zones based on final_score:
    SHORTLIST  >= shortlist threshold         (auto-advance to AI screening)
    REVIEW     >= review threshold  and  <    (recruiter reviews manually)
    REJECTED   <  review threshold            (auto-reject, polite rejection)

Candidates that already failed hard filters are forced to REJECTED with
their failure reasons preserved.

PRD Reference: Day 14 - "Create shortlisting thresholds, auto-reject and
review zones".
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Iterable

logger = logging.getLogger(__name__)


class Zone(str, Enum):
    SHORTLIST = "shortlisted"
    REVIEW    = "review"
    REJECTED  = "rejected"


def assign_zone(final_score: float, thresholds: dict[str, float]) -> Zone:
    if final_score >= thresholds["shortlist"]:
        return Zone.SHORTLIST
    if final_score >= thresholds["review"]:
        return Zone.REVIEW
    return Zone.REJECTED


def bucket_candidates(
    ranked: Iterable[dict],
    thresholds: dict[str, float],
) -> dict[str, list[dict]]:
    """
    Bucket ranked candidates into shortlisted / review / rejected lists.

    Candidates carrying `hard_filter_failed=True` are force-rejected regardless
    of their score, and their reasons are preserved under `rejection_reasons`.
    """
    buckets: dict[str, list[dict]] = {
        Zone.SHORTLIST.value: [],
        Zone.REVIEW.value:    [],
        Zone.REJECTED.value:  [],
    }

    for c in ranked:
        if c.get("hard_filter_failed"):
            c["zone"] = Zone.REJECTED.value
            c.setdefault("rejection_reasons", []).append("hard_filter")
            buckets[Zone.REJECTED.value].append(c)
            continue

        zone = assign_zone(float(c.get("final_score", 0.0)), thresholds)
        c["zone"] = zone.value
        if zone == Zone.REJECTED:
            c.setdefault("rejection_reasons", []).append(
                f"below_review_threshold ({c.get('final_score')} < {thresholds['review']})"
            )
        buckets[zone.value].append(c)

    logger.info(
        "Bucketing complete: shortlist=%d, review=%d, rejected=%d",
        len(buckets[Zone.SHORTLIST.value]),
        len(buckets[Zone.REVIEW.value]),
        len(buckets[Zone.REJECTED.value]),
    )
    return buckets
