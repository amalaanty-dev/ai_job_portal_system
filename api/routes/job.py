"""Job Description (JD) routes — upload single + batch."""
from __future__ import annotations

from fastapi import APIRouter, Request

from api.core.logging_config import get_logger
from api.schemas.job import (
    JobDescription,
    JobUploadResponse,
    JobBatchUploadRequest,
    JobBatchUploadResponse,
)
from api.services import storage

logger = get_logger(__name__)
router = APIRouter(prefix="/jd", tags=["Job Description"])


@router.post(
    "/upload",
    response_model=JobUploadResponse,
    summary="Upload a single Job Description",
)
async def upload_jd(jd: JobDescription, request: Request) -> JobUploadResponse:
    saved = storage.save_jd(jd.model_dump())
    logger.info(
        "JD uploaded",
        extra={"request_id": request.state.request_id, "job_id": saved["job_id"]},
    )
    return JobUploadResponse(job_id=saved["job_id"], job_title=saved["job_title"])


@router.post(
    "/upload/batch",
    response_model=JobBatchUploadResponse,
    summary="Upload multiple Job Descriptions",
)
async def upload_jds_batch(req: JobBatchUploadRequest, request: Request) -> JobBatchUploadResponse:
    job_ids: list[str] = []
    for jd in req.jobs:
        saved = storage.save_jd(jd.model_dump())
        job_ids.append(saved["job_id"])
    logger.info(
        f"Batch JD upload: {len(job_ids)} JDs",
        extra={"request_id": request.state.request_id},
    )
    return JobBatchUploadResponse(total=len(job_ids), job_ids=job_ids)
