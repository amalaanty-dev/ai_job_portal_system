"""
ranker.py
----------
Auto-ranking engine.

Responsibilities:
  1. For each candidate, compute (or pass through) a final composite score.
  2. Attach ranking metadata (rank, effective weights, missing scores).
  3. Return a list sorted by final_score DESC, with deterministic tie-breaking.

Two scoring modes:
  - PASS-THROUGH: Use Day 13's pre-computed `final_score` as-is. (default)
  - RECOMPUTE   : Re-weight sub-scores (skill, experience, education,
                  semantic) using Day 14's role-specific weights.

Tie-break priority (highest wins):
  composite -> skill -> experience -> semantic -> education -> candidate_id
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.score_utils import (
    compute_composite_score,
    extract_sub_scores,
    passthrough_score,
)

logger = logging.getLogger(__name__)


# Reserved keys the ranker always owns on the output record.
# Pre-existing values on input are preserved as `_original_<key>`.
RESERVED_KEYS = (
    "sub_scores",
    "missing_scores",
    "effective_weights",
    "rank",
    "zone",
)


# Common ID keys across Day 1-13 outputs (Day 13 puts it under `identifiers`)
ID_KEY_CANDIDATES = (
    "candidate_id", "id", "resume_id", "applicant_id",
    "_id", "uuid", "candidate_uuid",
    "email", "contact_email",
    "phone", "contact_number", "mobile",
    "filename", "file_name", "resume_filename",
)


def _candidate_id(candidate: dict) -> str:
    """Best-effort stable ID. Day 13 stores resume_id under `identifiers`."""
    # Day 13 shape: identifiers.resume_id
    ident = candidate.get("identifiers")
    if isinstance(ident, dict):
        for k in ("resume_id", "candidate_id", "id"):
            v = ident.get(k)
            if v:
                return str(v).strip()

    # Top-level fallbacks
    for key in ID_KEY_CANDIDATES:
        v = candidate.get(key)
        if v:
            return str(v).strip()

    # Source filename (set by loader)
    src = candidate.get("_source_file")
    if src:
        return Path(str(src)).stem

    # Name-based last resort
    name = candidate.get("name") or candidate.get("candidate_name") or candidate.get("full_name")
    if name:
        return str(name).strip().replace(" ", "_").lower()

    return "unknown"


def _candidate_job_role(candidate: dict) -> str | None:
    """Day 13 stores job_role under `identifiers.job_role`."""
    ident = candidate.get("identifiers")
    if isinstance(ident, dict) and ident.get("job_role"):
        return str(ident["job_role"])
    return candidate.get("job_role")


def score_candidate(
    candidate: dict,
    weights: dict[str, float],
    *,
    recompute: bool = False,
    debug: bool = False,
) -> dict:
    """
    Score a single candidate and return an enriched record.

    Args:
        candidate: raw ATS JSON dict
        weights:   used only when recompute=True
        recompute: if True, weight sub-scores; if False (default), trust
                   Day 13's `final_score` as-is

    The returned dict preserves the original payload and adds:
      - candidate_id, sub_scores, missing_scores,
        effective_weights, final_score, scoring_mode
    """
    sub_scores = extract_sub_scores(candidate, debug=debug)
    missing = [k for k, v in sub_scores.items() if v is None]

    if recompute:
        # Recompute mode: weight the four sub-scores, ignore Day 13 final_score.
        # ats_score is excluded from the weighted sum because IT IS the
        # composite we are recomputing.
        recompute_subs = {k: v for k, v in sub_scores.items() if k != "ats_score"}
        final_score, effective = compute_composite_score(recompute_subs, weights)
        scoring_mode = "recomputed"
    else:
        # Pass-through: prefer Day 13's final_score, fall back to ats_score
        # alias chain (which itself starts with `final_score`).
        pre = passthrough_score(candidate)
        if pre is None:
            pre = sub_scores.get("ats_score")
        final_score = pre if pre is not None else 0.0
        effective = {"day13_final_score": 1.0}
        scoring_mode = "passthrough"

    out: dict = {}
    for k, v in candidate.items():
        if k in RESERVED_KEYS:
            out[f"_original_{k}"] = v
        else:
            out[k] = v

    out.update({
        "candidate_id":      _candidate_id(candidate),
        "job_role":          _candidate_job_role(candidate) or out.get("job_role"),
        "sub_scores":        {k: v for k, v in sub_scores.items() if v is not None},
        "missing_scores":    missing,
        "effective_weights": effective,
        "final_score":       round(float(final_score), 2),
        "scoring_mode":      scoring_mode,
    })
    return out


def _sort_key(c: dict) -> tuple:
    """Deterministic sort key. Higher is better for all fields except ID."""
    subs = c.get("sub_scores", {})
    return (
        -float(c.get("final_score", 0.0)),
        -float(subs.get("skill_score", 0.0) or 0.0),
        -float(subs.get("experience_score", 0.0) or 0.0),
        -float(subs.get("semantic_score", 0.0) or 0.0),
        -float(subs.get("education_score", 0.0) or 0.0),
        str(c.get("candidate_id", "")),
    )


def rank_candidates(
    candidates: list[dict],
    weights: dict[str, float],
    *,
    recompute: bool = False,
    debug: bool = False,
) -> list[dict]:
    """Score + sort + assign rank numbers. Returns a NEW list."""
    scored = [
        score_candidate(c, weights, recompute=recompute, debug=debug)
        for c in candidates
    ]
    scored.sort(key=_sort_key)
    for i, c in enumerate(scored, start=1):
        c["rank"] = i

    no_scores = sum(1 for c in scored if c.get("final_score", 0) == 0 and not c.get("sub_scores"))
    if no_scores:
        logger.warning(
            "%d / %d candidates had final_score=0 with no sub-scores. "
            "Run with --debug-extract to inspect the JSON shape.",
            no_scores, len(scored),
        )
    logger.info("Ranked %d candidates (mode=%s)", len(scored),
                "recomputed" if recompute else "passthrough")
    return scored
