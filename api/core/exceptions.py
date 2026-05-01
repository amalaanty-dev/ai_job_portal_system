"""Custom exception hierarchy → PRD error codes."""
from __future__ import annotations


class ATSException(Exception):
    """Base. Maps to PRD error format."""
    error_code: str = "SERVER_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidInputError(ATSException):
    error_code = "INVALID_INPUT"
    http_status = 400


class NotFoundError(ATSException):
    error_code = "NOT_FOUND"
    http_status = 404


class ProcessingError(ATSException):
    error_code = "PROCESSING_ERR"
    http_status = 422


class ServerError(ATSException):
    error_code = "SERVER_ERROR"
    http_status = 500
