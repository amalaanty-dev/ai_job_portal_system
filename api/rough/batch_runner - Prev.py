"""Batch orchestrator: N resumes × M JDs concurrent scoring.

Every score is persisted to `api_data_results/scores/{candidate_id}__{job_id}.json`
via `storage.save_score_result()`.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any

from api.services import ats_adapter, storage

logger = logging.getLogger(__name__)


async def _score_pair(candidate_id: str, job_id: str) -> dict[str, Any]:
    """Score one (candidate, job) pair off the event loop."""
    loop = asyncio.get_running_loop()

    resumes = [r for r in storage.list_resumes() if r["candidate_id"] == candidate_id]
    if not resumes:
        raise ValueError(f"No resume found for candidate_id={candidate_id}")
    resume = resumes[-1]  # most recent

    jd = storage.get_jd(job_id)

    parsed = await loop.run_in_executor(None, ats_adapter.parse_resume, resume["stored_path"])
    score = await loop.run_in_executor(None, ats_adapter.score_candidate, parsed, jd)

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "final_score": score["final_score"],
        "breakdown": {k: score[k] for k in ("skills", "experience", "education", "semantic")},
    }


async def score_matrix(
    candidate_ids: list[str],
    job_ids: list[str],
    threshold: float = 70.0,
    concurrency: int = 8,
) -> dict[str, Any]:
    """Score every candidate against every job concurrently. Persists each score."""
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(cid: str, jid: str):
        async with sem:
            try:
                res = await _score_pair(cid, jid)
                res["matched_status"] = "Shortlisted" if res["final_score"] >= threshold else "Rejected"
                storage.save_score_result(res)
                return ("ok", res)
            except Exception as e:
                logger.exception("score_pair failed", extra={"candidate_id": cid, "job_id": jid})
                return ("err", {"candidate_id": cid, "job_id": jid, "error": str(e)})

    tasks = [_bounded(c, j) for c in candidate_ids for j in job_ids]
    outcomes = await asyncio.gather(*tasks)

    scores = [r for tag, r in outcomes if tag == "ok"]
    errors = [r for tag, r in outcomes if tag == "err"]

    return {
        "total_pairs": len(tasks),
        "scores": scores,
        "errors": errors,
    }


def shortlist_for_job(job_id: str, threshold: float = 70.0, top_n: int | None = None) -> dict[str, Any]:
    """Pull stored scores for a job, rank, threshold, and (optionally) top-N."""
    rows = storage.get_scores_for_job(job_id)
    rows.sort(key=lambda r: r["final_score"], reverse=True)
    ranked = []
    for i, r in enumerate(rows, start=1):
        ranked.append({
            "candidate_id": r["candidate_id"],
            "score": r["final_score"],
            "status": "Shortlisted" if r["final_score"] >= threshold else "Rejected",
            "rank": i,
        })
    if top_n:
        ranked = ranked[:top_n]
    shortlisted = sum(1 for r in ranked if r["status"] == "Shortlisted")
    return {
        "job_id": job_id,
        "total_candidates": len(rows),
        "shortlisted": shortlisted,
        "candidates": ranked,
    }
