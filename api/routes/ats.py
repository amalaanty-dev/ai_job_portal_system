"""ATS routes: score (1×1, N×M), shortlist (single JD, multi JD, or ALL).

Shortlist persistence: one file per JD at api_data_results/shortlists/{job_id}.json,
each containing only candidates whose final_score >= threshold.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from api.core.exceptions import InvalidInputError
from api.core.logging_config import get_logger
from api.schemas.score import (
    ScoreRequest,
    ScoreResponse,
    ScoreBreakdown,
    ScoreBatchRequest,
    ScoreBatchResponse,
)
from api.schemas.shortlist import (
    ShortlistRequest,
    ShortlistResponse,
    CandidateRanking,
)
from api.services import batch_runner, storage

logger = get_logger(__name__)
router = APIRouter(prefix="/ats", tags=["ATS Scoring"])


@router.post(
    "/score",
    response_model=ScoreResponse,
    summary="Score one candidate × one JD (writes api_data_results/scores/...)",
)
async def score_one(req: ScoreRequest, request: Request) -> ScoreResponse:
    result = await batch_runner._score_pair(req.candidate_id, req.job_id)
    result["matched_status"] = "Shortlisted" if result["final_score"] >= 70 else "Rejected"
    storage.save_score_result(result)
    logger.info(
        "Candidate scoring completed",
        extra={
            "request_id": request.state.request_id,
            "candidate_id": req.candidate_id,
            "job_id": req.job_id,
        },
    )
    return ScoreResponse(
        candidate_id=req.candidate_id,
        job_id=req.job_id,
        final_score=result["final_score"],
        breakdown=ScoreBreakdown(**result["breakdown"]),
        matched_status=result["matched_status"],
    )


@router.post(
    "/score/batch",
    response_model=ScoreBatchResponse,
    summary="Score N candidates × M JDs (each pair persisted to api_data_results/scores/)",
)
async def score_batch(req: ScoreBatchRequest, request: Request) -> ScoreBatchResponse:
    out = await batch_runner.score_matrix(
        req.candidate_ids, req.job_ids, threshold=req.shortlist_threshold
    )
    logger.info(
        f"Batch scoring complete: {len(out['scores'])} pairs scored, "
        f"{len(out['errors'])} errors",
        extra={"request_id": request.state.request_id},
    )
    scores = [
        ScoreResponse(
            candidate_id=s["candidate_id"],
            job_id=s["job_id"],
            final_score=s["final_score"],
            breakdown=ScoreBreakdown(**s["breakdown"]),
            matched_status=s["matched_status"],
        )
        for s in out["scores"]
    ]
    return ScoreBatchResponse(
        total_pairs=out["total_pairs"],
        scores=scores,
        errors=out["errors"],
    )


def _resolve_job_ids(req: ShortlistRequest) -> list[str]:
    """Resolve req.job_ids → concrete list of job_ids.

    Supports:
      - "ALL"            → every job that has at least one stored score
      - "J123"           → single JD as a string (back-compat with old singular shape)
      - ["J1","J2"]      → explicit list
    """
    raw = req.job_ids
    if isinstance(raw, str):
        if raw.upper() == "ALL":
            # Pick every job that has at least one score
            jobs_with_scores: set[str] = set()
            for jd in storage.list_jds():
                if storage.get_scores_for_job(jd["job_id"]):
                    jobs_with_scores.add(jd["job_id"])
            return sorted(jobs_with_scores)
        return [raw]
    if isinstance(raw, list):
        return list(raw)
    raise InvalidInputError(f"job_ids must be a string ('ALL' or single id) or list, got {type(raw).__name__}")


@router.post(
    "/shortlist",
    response_model=ShortlistResponse,
    summary="Rank & shortlist candidates for one or many JDs (writes api_data_results/shortlists/{job_id}.json each)",
)
async def shortlist(req: ShortlistRequest, request: Request) -> ShortlistResponse:
    job_ids = _resolve_job_ids(req)
    if not job_ids:
        raise InvalidInputError("No matching jobs found for shortlist request")

    if len(job_ids) == 1:
        # Single-JD response shape (backward compatible)
        jid = job_ids[0]
        out = batch_runner.shortlist_for_job(jid, threshold=req.threshold, top_n=req.top_n)
        storage.save_shortlist_result(out)
        logger.info(
            f"Shortlist generated: {out['shortlisted']}/{out['total_candidates']}",
            extra={"request_id": request.state.request_id, "job_id": jid},
        )
        return ShortlistResponse(
            job_id=jid,
            job_ids=None,
            total_candidates=out["total_candidates"],
            shortlisted=out["shortlisted"],
            candidates=[CandidateRanking(**c) for c in out["candidates"]],
        )

    # Multi-JD: aggregate. Returns per-JD shortlists; persist each as its own file.
    aggregated: list[CandidateRanking] = []
    total_candidates = 0
    total_shortlisted = 0
    for jid in job_ids:
        out = batch_runner.shortlist_for_job(jid, threshold=req.threshold, top_n=req.top_n)
        # Persist per-JD file (skip empty)
        if out["shortlisted"] > 0:
            storage.save_shortlist_result(out)
        # Tag rank with job_id prefix in aggregated response so consumers can disambiguate
        for c in out["candidates"]:
            aggregated.append(CandidateRanking(**c))
        total_candidates += out["total_candidates"]
        total_shortlisted += out["shortlisted"]

    logger.info(
        f"Multi-JD shortlist: {len(job_ids)} jobs, {total_shortlisted}/{total_candidates} shortlisted total",
        extra={"request_id": request.state.request_id},
    )
    return ShortlistResponse(
        job_id=None,
        job_ids=job_ids,
        total_candidates=total_candidates,
        shortlisted=total_shortlisted,
        candidates=aggregated,
    )
