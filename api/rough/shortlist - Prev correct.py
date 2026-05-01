"""Shortlist schemas."""
from __future__ import annotations
from pydantic import BaseModel, Field
from api.schemas.common import BaseResponse, StatusEnum


class CandidateRanking(BaseModel):
    candidate_id: str
    score: float = Field(ge=0, le=100)
    status: str  # Shortlisted / Rejected / Review
    rank: int


class ShortlistRequest(BaseModel):
    job_id: str
    threshold: float = Field(ge=0, le=100, default=70.0)
    top_n: int | None = Field(default=None, ge=1, le=500)


class ShortlistResponse(BaseResponse):
    status: StatusEnum = StatusEnum.completed
    job_id: str
    total_candidates: int
    shortlisted: int
    candidates: list[CandidateRanking]
