"""Structured JSON logging — matches PRD log format exactly."""
from __future__ import annotations
import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from api.config import settings


class JsonFormatter(logging.Formatter):
    """Emit log lines in PRD format:
    {timestamp, service, level, message, candidate_id?, job_id?, request_id?}
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "service": settings.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Optional contextual fields
        for k in ("candidate_id", "job_id", "resume_id", "request_id", "task_id"):
            v = getattr(record, k, None)
            if v is not None:
                payload[k] = v
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()

    fmt = JsonFormatter()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    file_h = RotatingFileHandler(
        settings.log_dir / "ats_api.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_h.setFormatter(fmt)
    root.addHandler(file_h)

    # Quiet noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
