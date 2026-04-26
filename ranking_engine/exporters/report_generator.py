"""
report_generator.py
--------------------
Generates recruiter-ready summary reports:
  - summary.json    : run statistics (counts, avg scores, thresholds used)
  - top_candidates.md : human-readable top-N list
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from utils.io_utils import save_json

logger = logging.getLogger(__name__)


def _avg(values: list[float]) -> float:
    return round(statistics.fmean(values), 2) if values else 0.0


def generate_summary(
    ranked: list[dict],
    buckets: dict[str, list[dict]],
    config_snapshot: dict,
    run_meta: dict,
) -> dict:
    """Build the summary dict for summary.json."""
    all_scores = [float(c.get("final_score", 0.0)) for c in ranked]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "job_role":         run_meta.get("job_role", "default"),
        "total_candidates": len(ranked),
        "counts": {
            "shortlisted": len(buckets.get("shortlisted", [])),
            "review":      len(buckets.get("review", [])),
            "rejected":    len(buckets.get("rejected", [])),
        },
        "score_stats": {
            "average":  _avg(all_scores),
            "highest":  max(all_scores) if all_scores else 0.0,
            "lowest":   min(all_scores) if all_scores else 0.0,
            "median":   round(statistics.median(all_scores), 2) if all_scores else 0.0,
        },
        "config_used": config_snapshot,
        "run_meta":    run_meta,
    }


def generate_top_n_markdown(ranked: list[dict], top_n: int) -> str:
    """Build a markdown table of the top-N candidates for quick recruiter view."""
    lines = [
        f"# Top {min(top_n, len(ranked))} Candidates",
        "",
        "| Rank | Candidate ID | Role | Final | Skill | Exp | Edu | Sem | Zone | Rating |",
        "|------|--------------|------|-------|-------|-----|-----|-----|------|--------|",
    ]
    for c in ranked[:top_n]:
        subs = c.get("sub_scores", {})
        interp = c.get("score_interpretation") or {}
        lines.append(
            "| {rank} | {cid} | {role} | {fs} | {sk} | {ex} | {ed} | {sem} | {zone} | {rating} |".format(
                rank=c.get("rank", ""),
                cid=c.get("candidate_id", "")[:30],
                role=(c.get("job_role") or "-")[:30],
                fs=c.get("final_score", ""),
                sk=subs.get("skill_score", "-"),
                ex=subs.get("experience_score", "-"),
                ed=subs.get("education_score", "-"),
                sem=subs.get("semantic_score", "-"),
                zone=c.get("zone", "-"),
                rating=interp.get("rating", "-"),
            )
        )
    return "\n".join(lines) + "\n"


def write_reports(
    ranked: list[dict],
    buckets: dict[str, list[dict]],
    reports_dir: Path,
    config_snapshot: dict,
    run_meta: dict,
    top_n: int,
) -> dict[str, Path]:
    """Write both summary.json and top_candidates.md. Returns written paths."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary = generate_summary(ranked, buckets, config_snapshot, run_meta)
    summary_path = save_json(summary, reports_dir / "summary.json")

    md = generate_top_n_markdown(ranked, top_n)
    md_path = reports_dir / "top_candidates.md"
    md_path.write_text(md, encoding="utf-8")

    logger.info("Reports written: %s, %s", summary_path, md_path)
    return {"summary": summary_path, "top_candidates_md": md_path}
