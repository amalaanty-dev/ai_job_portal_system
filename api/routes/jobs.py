"""Async job lifecycle: start a long-running batch, poll status, fetch result."""
from __future__ import annotations
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.core.exceptions import NotFoundError
from api.core.job_queue import queue, JobState
from api.core.logging_config import get_logger
from api.schemas.common import JobStatusResponse, JobResultResponse, StatusEnum
from api.schemas.score import ScoreBatchRequest
from api.services import batch_runner

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Async Jobs"])


class StartJobRequest(BaseModel):
    kind: Literal["score_batch", "shortlist"] = Field(default="score_batch")
    payload: dict


@router.post(
    "/start",
    response_model=JobStatusResponse,
    summary="Submit an async batch task",
)
async def start_job(req: StartJobRequest, request: Request) -> JobStatusResponse:
    if req.kind == "score_batch":
        sb = ScoreBatchRequest(**req.payload)
        async def _runner():
            return await batch_runner.score_matrix(
                sb.candidate_ids, sb.job_ids, threshold=sb.shortlist_threshold
            )
        job = await queue.submit("score_batch", _runner)

    elif req.kind == "shortlist":
        job_id = req.payload["job_id"]
        threshold = req.payload.get("threshold", 70.0)
        top_n = req.payload.get("top_n")
        async def _runner():
            return batch_runner.shortlist_for_job(job_id, threshold, top_n)
        job = await queue.submit("shortlist", _runner)
    else:
        raise NotFoundError(f"Unknown job kind: {req.kind}")

    logger.info(
        f"Async job started: {req.kind}",
        extra={"request_id": request.state.request_id, "task_id": job.job_id},
    )
    return JobStatusResponse(
        job_id=job.job_id,
        status=StatusEnum(job.state.value),
        kind=job.kind,
        result_url=job.result_url,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Check status of an async job",
)
async def job_status(job_id: str) -> JobStatusResponse:
    job = queue.get(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    return JobStatusResponse(
        job_id=job.job_id,
        status=StatusEnum(job.state.value),
        kind=job.kind,
        result_url=job.result_url if job.state == JobState.COMPLETED else None,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/result/{job_id}",
    response_model=JobResultResponse,
    summary="Fetch result of a completed async job",
)
async def job_result(job_id: str) -> JobResultResponse:
    job = queue.get(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    if job.state != JobState.COMPLETED:
        return JobResultResponse(
            job_id=job_id,
            status=StatusEnum(job.state.value),
            result=None,
        )
    return JobResultResponse(
        job_id=job_id,
        status=StatusEnum.completed,
        result=job.result,
    )
