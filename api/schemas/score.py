"""Scoring schemas."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from api.schemas.common import BaseResponse, StatusEnum


class ScoreBreakdown(BaseModel):
    skills: float = Field(ge=0, le=100)
    experience: float = Field(ge=0, le=100)
    education: float = Field(ge=0, le=100)
    semantic: float = Field(ge=0, le=100)


class ScoreRequest(BaseModel):
    candidate_id: str
    job_id: str


class ScoreResponse(BaseResponse):
    status: StatusEnum = StatusEnum.completed
    candidate_id: str
    job_id: str
    final_score: float = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    matched_status: Optional[str] = None  # "Shortlisted" / "Rejected" / "Review"


class ScoreBatchRequest(BaseModel):
    """N×M scoring: every candidate against every job_id."""
    candidate_ids: list[str] = Field(min_length=1, max_length=500)
    job_ids: list[str] = Field(min_length=1, max_length=50)
    shortlist_threshold: float = Field(ge=0, le=100, default=70.0)


class ScoreBatchResponse(BaseResponse):
    status: StatusEnum = StatusEnum.completed
    total_pairs: int
    scores: list[ScoreResponse]
    errors: list[dict[str, str]] = Field(default_factory=list)
