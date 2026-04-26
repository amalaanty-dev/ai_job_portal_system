"""
csv_exporter.py
----------------
Recruiter-friendly CSV exports of ranked / shortlisted candidates.

Columns are aligned with the actual Day 13 ATS engine output (resume_id,
job_role, semantic_similarity, etc.) and Day 14 enrichment (zone,
explanation, bias_flags).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


# Columns shown to recruiters. Order matters.
CSV_COLUMNS: list[str] = [
    "rank",
    "candidate_id",
    "job_role",
    "final_score",
    "scoring_mode",
    "skill_score",
    "experience_score",
    "education_score",
    "semantic_score",
    "rating",
    "recommendation",
    "priority",
    "zone",
    "explanation",
    "bias_flags",
    "missing_scores",
    "rejection_reasons",
    "source_file",
]


def _flatten(row: dict) -> dict:
    """Flatten a ranked/bucketed candidate record into a CSV-safe row."""
    subs = row.get("sub_scores", {})
    interp = row.get("score_interpretation") or {}

    return {
        "rank":               row.get("rank", ""),
        "candidate_id":       row.get("candidate_id", ""),
        "job_role":           row.get("job_role", ""),
        "final_score":        row.get("final_score", ""),
        "scoring_mode":       row.get("scoring_mode", ""),
        "skill_score":        subs.get("skill_score", ""),
        "experience_score":   subs.get("experience_score", ""),
        "education_score":    subs.get("education_score", ""),
        "semantic_score":     subs.get("semantic_score", ""),
        "rating":             interp.get("rating", ""),
        "recommendation":     interp.get("recommendation", ""),
        "priority":           interp.get("priority", ""),
        "zone":               row.get("zone", ""),
        "explanation":        row.get("explanation", ""),
        "bias_flags":         ";".join(row.get("bias_flags") or []),
        "missing_scores":     ";".join(row.get("missing_scores") or []),
        "rejection_reasons":  ";".join(row.get("rejection_reasons") or []),
        "source_file":        row.get("_source_file", ""),
    }


def export_to_csv(rows: Iterable[dict], path: Path) -> Path:
    """Write rows to a CSV file at `path`. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(_flatten(r))
    logger.info("CSV exported: %s", path)
    return path
