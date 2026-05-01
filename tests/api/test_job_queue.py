"""Unit tests for the in-memory job queue."""
from __future__ import annotations
import asyncio
import pytest

from api.core.job_queue import queue, JobState


@pytest.mark.asyncio
async def test_queue_completes_successful_job():
    async def work():
        await asyncio.sleep(0.05)
        return {"ok": True}

    job = await queue.submit("test_ok", work)
    for _ in range(100):
        if queue.get(job.job_id).state == JobState.COMPLETED:
            break
        await asyncio.sleep(0.05)
    assert queue.get(job.job_id).state == JobState.COMPLETED
    assert queue.get(job.job_id).result == {"ok": True}


@pytest.mark.asyncio
async def test_queue_marks_failed_job():
    async def boom():
        raise RuntimeError("kaboom")

    job = await queue.submit("test_fail", boom)
    for _ in range(100):
        if queue.get(job.job_id).state == JobState.FAILED:
            break
        await asyncio.sleep(0.05)
    assert queue.get(job.job_id).state == JobState.FAILED
    assert "kaboom" in queue.get(job.job_id).error
