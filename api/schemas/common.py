"""Common Pydantic schemas — error, base, status."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class StatusEnum(str, Enum):
    success = "success"
    error = "error"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class BaseResponse(BaseModel):
    status: StatusEnum
    message: Optional[str] = None
    timestamp: str = Field(default_factory=_utc_now)


class ErrorResponse(BaseModel):
    status: StatusEnum = StatusEnum.error
    error_code: str
    message: str
    timestamp: str = Field(default_factory=_utc_now)
    request_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: StatusEnum
    kind: Optional[str] = None
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class JobResultResponse(BaseModel):
    job_id: str
    status: StatusEnum
    result: Optional[Any] = None
