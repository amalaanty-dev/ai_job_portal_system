"""
call_queue_builder.py
----------------------
Emits a Phase-3 ready `call_queue.json` manifest listing shortlisted candidates.

Day 14's responsibility is RANKING, not contact resolution. The Day 13 ATS
JSON does not carry contact information (name, phone, email) — those come
from upstream resume parsers (Phase 1).

This builder therefore writes a queue with PII fields as `null` when the
candidate dict has no contact data. Phase 3 (AI Call Trigger Engine) is
responsible for resolving PII from the candidate database / parsed-resume
store before placing calls.

Contract:
  - The output file is ALWAYS written, even when the shortlist is empty
    (downstream phases poll a deterministic path).
  - NO candidate is silently dropped. Every shortlisted candidate appears
    in the queue.
  - `status` flags how the dispatcher should treat the entry:
        "ready"                 -> all required contact fields present, place call
        "needs_contact_lookup"  -> phone missing, dispatcher must resolve PII first

Schema (one object per shortlisted candidate):
  {
    "candidate_id":        "Resume_2_Clinical_Data_Analyst_skills",
    "name":                null,
    "phone":                null,
    "email":                null,
    "job_role":             "ai specialist in healthcare analytics",
    "final_score":          63.15,
    "language_preference":  null,
    "retry_count":          0,
    "status":               "needs_contact_lookup",
    "missing_fields":       ["name", "phone", "email"]
  }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from utils.io_utils import save_json

logger = logging.getLogger(__name__)


# Required-for-call fields. If `phone` is missing, the dispatcher cannot
# place a call without first resolving it from another data source.
REQUIRED_CONTACT_FIELDS: tuple[str, ...] = ("phone",)

# Other PII fields that are nice-to-have but not call-blocking.
OPTIONAL_CONTACT_FIELDS: tuple[str, ...] = ("name", "email")


def _pick(candidate: dict, *keys: str) -> str | None:
    """Return the first non-empty value among the given keys."""
    for k in keys:
        v = candidate.get(k)
        if v not in (None, "", []):
            return str(v)
    return None


def _extract_contact(candidate: dict) -> dict[str, str | None]:
    """
    Pull whatever contact info is already on the candidate dict.

    Day 13 ATS JSON typically has nothing; some upstream pipelines may
    inject these fields. We don't go fishing in the filesystem — that's
    Phase 3's job.
    """
    return {
        "name":  _pick(candidate, "name", "candidate_name", "full_name"),
        "phone": _pick(candidate, "phone", "phone_number", "contact_number", "mobile"),
        "email": _pick(candidate, "email", "email_address", "contact_email"),
    }


def build_call_queue(
    shortlisted: Iterable[dict],
    job_role: str,
    out_path: Path,
) -> Path:
    """
    Build the call-queue manifest from the shortlisted bucket.

    Args:
        shortlisted: iterable of shortlisted candidate dicts
        job_role:    role key for the queue
        out_path:    destination for call_queue.json

    Returns:
        Path to the written call_queue.json (ALWAYS written, even if empty).
    """
    out_path = Path(out_path)
    queue: list[dict] = []
    needs_lookup = 0
    ready = 0

    for c in shortlisted:
        contact = _extract_contact(c)

        # missing_fields lists every field that is null/empty
        all_fields = OPTIONAL_CONTACT_FIELDS + REQUIRED_CONTACT_FIELDS
        missing = [f for f in all_fields if not contact.get(f)]

        # status hinges only on REQUIRED fields (phone)
        required_missing = [f for f in REQUIRED_CONTACT_FIELDS if not contact.get(f)]
        status = "needs_contact_lookup" if required_missing else "ready"

        if status == "ready":
            ready += 1
        else:
            needs_lookup += 1

        queue.append({
            "candidate_id":        c.get("candidate_id"),
            "name":                contact["name"],
            "phone":               contact["phone"],
            "email":               contact["email"],
            "job_role":            c.get("job_role") or job_role,
            "final_score":         c.get("final_score"),
            "language_preference": c.get("language_preference"),
            "retry_count":         0,
            "status":              status,
            "missing_fields":      missing,
        })

    save_json(queue, out_path)

    n = len(queue)
    if n == 0:
        logger.warning(
            "Call queue is EMPTY (0 entries written to %s). "
            "No candidates cleared the shortlist threshold. "
            "See reports/summary.json for the score distribution; "
            "consider lowering thresholds or running with --recompute.",
            out_path,
        )
    else:
        logger.info(
            "Call queue written: %s (%d entries: %d ready, %d need contact lookup)",
            out_path, n, ready, needs_lookup,
        )
        if needs_lookup == n:
            logger.warning(
                "ALL %d shortlisted candidates lack phone numbers. "
                "Day 13 ATS JSON does not carry contact info; Phase 3 "
                "(Call Trigger Engine) is responsible for resolving PII "
                "from the candidate database before placing calls.",
                n,
            )
    return out_path