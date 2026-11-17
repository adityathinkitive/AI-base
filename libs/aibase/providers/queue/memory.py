import asyncio
import logging
import uuid
from typing import Any

from aibase.core.errors import ConfigError, NotFound
from aibase.providers.queue.port import Handler, JobStatus

logger = logging.getLogger(__name__)


class InMemoryQueue:
    """Single-process queue for dev/tests. Swap for Celery/Arq/SQS adapters behind QueuePort."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        self._jobs: dict[str, JobStatus] = {}
        self._idempotency: dict[str, str] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self, task: str, handler: Handler) -> None:
        self._handlers[task] = handler

    async def enqueue(
        self, task: str, payload: dict[str, Any], *, idempotency_key: str | None = None
    ) -> str:
        if task not in self._handlers:
            raise ConfigError(f"no handler registered for task '{task}'")
        if idempotency_key and idempotency_key in self._idempotency:
            return self._idempotency[idempotency_key]
        job_id = uuid.uuid4().hex
        self._jobs[job_id] = JobStatus(id=job_id, state="queued")
        if idempotency_key:
            self._idempotency[idempotency_key] = job_id
        bg = asyncio.create_task(self._run(job_id, task, payload))
        self._tasks.add(bg)
        bg.add_done_callback(self._tasks.discard)
        return job_id

    async def _run(self, job_id: str, task: str, payload: dict[str, Any]) -> None:
        self._jobs[job_id] = JobStatus(id=job_id, state="running")
        try:
            result = await self._handlers[task](payload)
            self._jobs[job_id] = JobStatus(id=job_id, state="succeeded", result=result)
        except Exception as exc:
            logger.exception("job failed", extra={"job_id": job_id, "task": task})
            self._jobs[job_id] = JobStatus(id=job_id, state="failed", error=type(exc).__name__)

    async def status(self, job_id: str) -> JobStatus:
        if job_id not in self._jobs:
            raise NotFound("job not found")
        return self._jobs[job_id]
