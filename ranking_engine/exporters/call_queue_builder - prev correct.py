"""
call_queue_builder.py
----------------------
Emits a Phase-3 ready `call_queue.json` manifest listing shortlisted candidates
and the metadata the AI Call Trigger Engine needs to reach them.

Schema (one object per shortlisted candidate):
  {
    "candidate_id": "C001",
    "name":  "...",
    "phone": "+91...",
    "email": "...",
    "job_role": "mern_stack_developer",
    "final_score": 87.8,
    "language_preference": null,   # filled in upstream if known
    "retry_count": 0,
    "status": "pending"            # pending | in_progress | done | failed
  }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from utils.io_utils import save_json

logger = logging.getLogger(__name__)


def build_call_queue(
    shortlisted: Iterable[dict],
    job_role: str,
    out_path: Path,
) -> Path:
    """Build the call-queue manifest from the shortlisted bucket."""
    queue = []
    for c in shortlisted:
        entry = {
            "candidate_id":        c.get("candidate_id"),
            "name":                c.get("name") or c.get("candidate_name"),
            "phone":               c.get("phone"),
            "email":               c.get("email"),
            "job_role":            job_role,
            "final_score":         c.get("final_score"),
            "language_preference": c.get("language_preference"),
            "retry_count":         0,
            "status":              "pending",
        }
        if not entry["phone"]:
            logger.warning("Candidate %s has no phone; skipping from call queue",
                           entry["candidate_id"])
            continue
        queue.append(entry)

    save_json(queue, out_path)
    logger.info("Call queue written: %s (%d entries)", out_path, len(queue))
    return out_path
