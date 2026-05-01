"""Middleware: request ID injection, global error handler in PRD format."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.core.exceptions import ATSException
from api.core.logging_config import get_logger

logger = get_logger(__name__)


def _now_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _err(code: str, msg: str, status: int, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "status": "error",
            "error_code": code,
            "message": msg,
            "timestamp": _now_z(),
            "request_id": request_id,
        },
    )


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID header on every request for log correlation."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ATSException)
    async def ats_handler(request: Request, exc: ATSException):
        rid = getattr(request.state, "request_id", "-")
        logger.warning(exc.message, extra={"request_id": rid, **exc.details})
        return _err(exc.error_code, exc.message, exc.http_status, rid)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", "-")
        msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
        logger.warning(f"Validation failed: {msg}", extra={"request_id": rid})
        return _err("INVALID_INPUT", msg, 400, rid)

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "-")
        logger.exception("Unhandled error", extra={"request_id": rid})
        return _err("SERVER_ERROR", "Internal system error", 500, rid)
