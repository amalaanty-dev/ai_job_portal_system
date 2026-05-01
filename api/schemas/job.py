"""Job Description (JD) schemas."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from api.schemas.common import BaseResponse, StatusEnum


class JobDescription(BaseModel):
    """Input JD schema. Aligns with PRD Job Schema."""
    job_id: Optional[str] = None  # auto-generated if missing
    job_title: str = Field(min_length=1, max_length=200)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_required: float = Field(ge=0, le=50, default=0)
    education_required: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    description: Optional[str] = None
    jd_version: int = 1


class JobUploadResponse(BaseResponse):
    status: StatusEnum = StatusEnum.success
    message: str = "Job description uploaded successfully"
    job_id: str
    job_title: str


class JobBatchUploadRequest(BaseModel):
    jobs: list[JobDescription] = Field(min_length=1, max_length=100)


class JobBatchUploadResponse(BaseResponse):
    status: StatusEnum = StatusEnum.success
    message: str = "Batch JD upload completed"
    total: int
    job_ids: list[str]
