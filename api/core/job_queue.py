"""In-memory async job queue.

Drop-in replaceable: implement the same `JobQueue` protocol with Redis/RQ/Celery
later — the rest of the codebase only depends on this interface.

Implementation note: jobs run on a dedicated background thread with its own
asyncio loop. This survives across FastAPI request boundaries (the TestClient
closes its per-request loop, which would cancel `create_task`-scheduled work).
"""
from __future__ import annotations
import asyncio
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from api.config import settings
from api.core.logging_config import get_logger

logger = get_logger(__name__)


class JobState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    kind: str
    state: JobState = JobState.QUEUED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: Optional[dict] = None
    error: Optional[str] = None
    result_url: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d


class JobQueue:
    """Asyncio job queue running on a dedicated background thread."""

    def __init__(self, max_workers: int = 4) -> None:
        self._jobs: dict[str, Job] = {}
        self._max_workers = max_workers
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sem: asyncio.Semaphore | None = None
        self._thread_started = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ats-jobqueue")
        self._thread.start()
        self._thread_started.wait(timeout=5)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._sem = asyncio.Semaphore(self._max_workers)
        self._thread_started.set()
        self._loop.run_forever()

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    async def submit(
        self,
        kind: str,
        func: Callable[..., Awaitable[dict]],
        *args: Any,
        result_url_template: str = "/v1/jobs/result/{job_id}",
        **kwargs: Any,
    ) -> Job:
        job_id = f"JOB{uuid.uuid4().hex[:10].upper()}"
        job = Job(job_id=job_id, kind=kind, result_url=result_url_template.format(job_id=job_id))
        self._jobs[job_id] = job
        logger.info(f"Job queued: {kind}", extra={"task_id": job_id})
        # Schedule on the dedicated background loop — independent of the
        # request loop, so the task survives across HTTP requests.
        assert self._loop is not None
        asyncio.run_coroutine_threadsafe(self._run(job, func, *args, **kwargs), self._loop)
        return job

    async def _run(self, job: Job, func: Callable[..., Awaitable[dict]], *args: Any, **kwargs: Any) -> None:
        assert self._sem is not None
        async with self._sem:
            job.state = JobState.PROCESSING
            job.updated_at = datetime.now(timezone.utc).isoformat()
            try:
                job.result = await func(*args, **kwargs)
                job.state = JobState.COMPLETED
                logger.info(f"Job completed: {job.kind}", extra={"task_id": job.job_id})
            except Exception as e:
                job.state = JobState.FAILED
                job.error = str(e)
                logger.exception(f"Job failed: {job.kind}", extra={"task_id": job.job_id})
            finally:
                job.updated_at = datetime.now(timezone.utc).isoformat()


# Singleton
queue = JobQueue(max_workers=settings.max_concurrent_workers)
