"""Resume request/response schemas."""
from __future__ import annotations
from typing import Any, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from api.schemas.common import BaseResponse, StatusEnum


class ParsedProfile(BaseModel):
    """Lenient profile model — accepts whatever the existing parser returns.

    Real-world resume parsers vary wildly in output shape:
      - email: str | list[str] | None
      - skills: list[str] | list[dict] | dict
      - experience: list[dict] | dict | str
      - total_experience_years: int | float | str | None

    Any unknown extra fields from the parser are kept (extra='allow') so the
    caller never loses data, but Pydantic still validates the well-known core.
    """

    model_config = ConfigDict(extra="allow")  # don't reject unknown keys

    name: Optional[str] = None
    email: Optional[Union[str, list[str]]] = None
    phone: Optional[Union[str, list[str]]] = None
    skills: list[Any] = Field(default_factory=list)
    experience: list[Any] = Field(default_factory=list)
    education: list[Any] = Field(default_factory=list)
    total_experience_years: Optional[Union[float, int, str]] = None
    raw_text_preview: Optional[str] = None


class ResumeUploadResponse(BaseResponse):
    status: StatusEnum = StatusEnum.success
    message: str = "Resume uploaded successfully"
    resume_id: str
    candidate_id: str
    job_id: Optional[str] = None
    filename: str
    size_bytes: int


class ResumeBatchUploadItem(BaseModel):
    resume_id: str
    candidate_id: str
    filename: str
    size_bytes: int


class ResumeBatchUploadResponse(BaseResponse):
    status: StatusEnum = StatusEnum.success
    message: str = "Batch resume upload completed"
    total: int
    succeeded: int
    failed: int
    items: list[ResumeBatchUploadItem]
    errors: list[dict[str, str]] = Field(default_factory=list)


class ResumeParseRequest(BaseModel):
    resume_id: str


class ResumeParseResponse(BaseResponse):
    status: StatusEnum = StatusEnum.completed
    candidate_id: str
    resume_id: str
    parsed_profile: ParsedProfile


class ResumeBatchParseRequest(BaseModel):
    resume_ids: list[str] = Field(min_length=1, max_length=200)


class ResumeBatchParseResponse(BaseResponse):
    status: StatusEnum = StatusEnum.completed
    total: int
    parsed: list[ResumeParseResponse]
    errors: list[dict[str, str]] = Field(default_factory=list)
