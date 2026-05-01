"""Resume routes: upload (single + batch), parse (single + batch).

Parsing now persists the parsed profile to `api_data_results/parsed/{resume_id}.json`
so recruiters / downstream services can browse the artifacts directly.
"""
from __future__ import annotations
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, Request

from api.core.exceptions import InvalidInputError, ProcessingError
from api.core.logging_config import get_logger
from api.schemas.resume import (
    ResumeUploadResponse,
    ResumeBatchUploadResponse,
    ResumeBatchUploadItem,
    ResumeParseRequest,
    ResumeParseResponse,
    ResumeBatchParseRequest,
    ResumeBatchParseResponse,
    ParsedProfile,
)
from api.services import ats_adapter, storage

logger = get_logger(__name__)
router = APIRouter(prefix="/resume", tags=["Resume"])


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    summary="Upload a single resume (PDF / DOCX)",
)
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    job_id: Optional[str] = Form(None),
    candidate_id: Optional[str] = Form(None),
) -> ResumeUploadResponse:
    cid = candidate_id or f"C{uuid.uuid4().hex[:10].upper()}"
    meta = storage.save_resume(file, candidate_id=cid, job_id=job_id)
    logger.info(
        "Resume uploaded",
        extra={
            "request_id": request.state.request_id,
            "candidate_id": cid,
            "resume_id": meta["resume_id"],
            "job_id": job_id,
        },
    )
    return ResumeUploadResponse(
        resume_id=meta["resume_id"],
        candidate_id=cid,
        job_id=job_id,
        filename=meta["filename"],
        size_bytes=meta["size_bytes"],
    )


@router.post(
    "/upload/batch",
    response_model=ResumeBatchUploadResponse,
    summary="Upload multiple resumes at once",
)
async def upload_resumes_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    job_id: Optional[str] = Form(None),
) -> ResumeBatchUploadResponse:
    if not files:
        raise InvalidInputError("No files provided")

    items: list[ResumeBatchUploadItem] = []
    errors: list[dict[str, str]] = []
    for f in files:
        try:
            cid = f"C{uuid.uuid4().hex[:10].upper()}"
            meta = storage.save_resume(f, candidate_id=cid, job_id=job_id)
            items.append(ResumeBatchUploadItem(
                resume_id=meta["resume_id"],
                candidate_id=cid,
                filename=meta["filename"],
                size_bytes=meta["size_bytes"],
            ))
        except Exception as e:
            errors.append({"filename": f.filename or "<unknown>", "error": str(e)})

    logger.info(
        f"Batch resume upload: {len(items)} ok / {len(errors)} failed",
        extra={"request_id": request.state.request_id, "job_id": job_id},
    )
    return ResumeBatchUploadResponse(
        total=len(files),
        succeeded=len(items),
        failed=len(errors),
        items=items,
        errors=errors,
    )


@router.post(
    "/parse",
    response_model=ResumeParseResponse,
    summary="Parse an uploaded resume (writes api_data_results/parsed/{resume_id}.json)",
)
async def parse_resume(req: ResumeParseRequest, request: Request) -> ResumeParseResponse:
    meta = storage.get_resume(req.resume_id)
    try:
        parsed = ats_adapter.parse_resume(meta["stored_path"])
    except Exception as e:
        raise ProcessingError(f"Failed to parse resume: {e}") from e

    # Persist parsed result artifact
    storage.save_parsed_result(req.resume_id, meta["candidate_id"], parsed)

    logger.info(
        "Resume parsed",
        extra={
            "request_id": request.state.request_id,
            "candidate_id": meta["candidate_id"],
            "resume_id": req.resume_id,
        },
    )
    return ResumeParseResponse(
        candidate_id=meta["candidate_id"],
        resume_id=req.resume_id,
        parsed_profile=ParsedProfile(**parsed),
    )


@router.post(
    "/parse/batch",
    response_model=ResumeBatchParseResponse,
    summary="Parse multiple resumes; each persists to api_data_results/parsed/",
)
async def parse_resumes_batch(req: ResumeBatchParseRequest, request: Request) -> ResumeBatchParseResponse:
    parsed_results: list[ResumeParseResponse] = []
    errors: list[dict[str, str]] = []
    for rid in req.resume_ids:
        try:
            meta = storage.get_resume(rid)
            parsed = ats_adapter.parse_resume(meta["stored_path"])
            storage.save_parsed_result(rid, meta["candidate_id"], parsed)
            parsed_results.append(ResumeParseResponse(
                candidate_id=meta["candidate_id"],
                resume_id=rid,
                parsed_profile=ParsedProfile(**parsed),
            ))
        except Exception as e:
            errors.append({"resume_id": rid, "error": str(e)})

    logger.info(
        f"Batch parse: {len(parsed_results)} ok / {len(errors)} failed",
        extra={"request_id": request.state.request_id},
    )
    return ResumeBatchParseResponse(
        total=len(req.resume_ids),
        parsed=parsed_results,
        errors=errors,
    )
