"""
consolidated_exporter.py
-------------------------
Emits ONE consolidated JSON per zone (ranked / shortlisted / review / rejected),
grouping all candidates under a single identifier — `jd_id` — so the file
mirrors Day 13's ranked_<jd_id>.json shape.

Output structure for each consolidated file:
{
  "jd_id":            "<single identifier>",
  "job_role":         "<role string>",
  "category":         "ranked" | "shortlisted" | "review" | "rejected",
  "total_candidates": <int>,
  "generated_at":     "<ISO-8601 UTC>",
  "candidates":       [ {...}, {...}, ... ]
}

When the input pool spans multiple JDs, we ALSO write one file per JD into
the `<zone>_per_jd/` subfolder so each can be consumed independently.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from utils.io_utils import save_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _candidate_jd_id(candidate: dict) -> str:
    """Resolve the JD identifier for a candidate.

    Day 13 stores it under `identifiers.jd_id`; fall back to top-level keys.
    """
    ident = candidate.get("identifiers")
    if isinstance(ident, dict) and ident.get("jd_id"):
        return str(ident["jd_id"])
    for key in ("jd_id", "job_id", "posting_id"):
        if candidate.get(key):
            return str(candidate[key])
    # Last resort: derive from job_role
    role = candidate.get("job_role")
    if role:
        return str(role).strip().lower().replace(" ", "_")
    return "unknown_jd"


def _candidate_job_role(candidate: dict) -> str | None:
    ident = candidate.get("identifiers")
    if isinstance(ident, dict) and ident.get("job_role"):
        return str(ident["job_role"])
    return candidate.get("job_role")


def _build_envelope(
    jd_id: str,
    job_role: str | None,
    category: str,
    candidates: list[dict],
) -> dict:
    """Build the canonical consolidated envelope around a candidate list."""
    return {
        "jd_id":            jd_id,
        "job_role":         job_role or "unknown",
        "category":         category,
        "total_candidates": len(candidates),
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "candidates":       candidates,
    }


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def write_consolidated(
    candidates: Iterable[dict],
    category: str,
    zone_dir: Path,
    write_per_jd: bool = True,
) -> dict[str, Path]:
    """
    Write the consolidated JSON for a zone, plus optional per-JD breakdowns.

    Args:
        candidates:    rows belonging to this zone (already ranked + bucketed)
        category:      one of "ranked" | "shortlisted" | "review" | "rejected"
        zone_dir:      target directory (e.g. ranking_engine_results/ranked)
        write_per_jd:  if True, also emit zone_dir/<category>_per_jd/<jd>.json

    Returns:
        Mapping with paths of written artifacts:
          {"main": <consolidated path>, "per_jd_dir": <dir path or None>}
    """
    zone_dir = Path(zone_dir)
    zone_dir.mkdir(parents=True, exist_ok=True)

    # Group candidates by jd_id so each file uses ONE identifier
    grouped: dict[str, list[dict]] = defaultdict(list)
    role_lookup: dict[str, str | None] = {}
    for c in candidates:
        jd = _candidate_jd_id(c)
        grouped[jd].append(c)
        role_lookup.setdefault(jd, _candidate_job_role(c))

    # ---- Top-level consolidated file ----
    if not grouped:
        # Empty zone -> still write a well-formed envelope
        envelope = _build_envelope(
            jd_id="none",
            job_role=None,
            category=category,
            candidates=[],
        )
    elif len(grouped) == 1:
        only_jd = next(iter(grouped))
        envelope = _build_envelope(
            jd_id=only_jd,
            job_role=role_lookup[only_jd],
            category=category,
            candidates=grouped[only_jd],
        )
    else:
        flat = [c for rows in grouped.values() for c in rows]
        envelope = _build_envelope(
            jd_id="_all",
            job_role="multiple",
            category=category,
            candidates=flat,
        )
        envelope["jd_ids"] = sorted(grouped.keys())

    main_path = zone_dir / f"{category}_candidates.json"
    save_json(envelope, main_path)
    logger.info("Consolidated %s -> %s (jd_id=%s, total=%d)",
                category, main_path, envelope["jd_id"], envelope["total_candidates"])

    # ---- Per-JD breakdown ----
    per_jd_dir: Path | None = None
    if write_per_jd and len(grouped) > 1:
        per_jd_dir = zone_dir / f"{category}_per_jd"
        per_jd_dir.mkdir(parents=True, exist_ok=True)
        for jd, rows in grouped.items():
            sub_envelope = _build_envelope(
                jd_id=jd,
                job_role=role_lookup[jd],
                category=category,
                candidates=rows,
            )
            # Sanitise jd_id for use as a filename
            safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in jd)[:120]
            save_json(sub_envelope, per_jd_dir / f"{safe}.json")
        logger.info("Per-JD %s files written to %s (%d JDs)",
                    category, per_jd_dir, len(grouped))

    return {"main": main_path, "per_jd_dir": per_jd_dir}
