"""ATS routes: score (1×1, N×M), shortlist.

Shortlists now persist to `api_data_results/shortlists/{job_id}.json`.
Score artifacts are written by `batch_runner` for both single and batch flows.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

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


@router.post(
    "/shortlist",
    response_model=ShortlistResponse,
    summary="Rank & shortlist scored candidates (writes api_data_results/shortlists/{job_id}.json)",
)
async def shortlist(req: ShortlistRequest, request: Request) -> ShortlistResponse:
    out = batch_runner.shortlist_for_job(req.job_id, threshold=req.threshold, top_n=req.top_n)

    # Persist shortlist artifact
    storage.save_shortlist_result(out)

    logger.info(
        f"Shortlist generated: {out['shortlisted']}/{out['total_candidates']}",
        extra={"request_id": request.state.request_id, "job_id": req.job_id},
    )
    return ShortlistResponse(
        job_id=out["job_id"],
        total_candidates=out["total_candidates"],
        shortlisted=out["shortlisted"],
        candidates=[CandidateRanking(**c) for c in out["candidates"]],
    )
