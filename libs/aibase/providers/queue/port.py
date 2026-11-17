from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel

Handler = Callable[[dict[str, Any]], Awaitable[Any]]


class JobStatus(BaseModel):
    id: str
    state: Literal["queued", "running", "succeeded", "failed"]
    result: Any = None
    error: str | None = None


class QueuePort(Protocol):
    """Background jobs. Payloads must be opaque IDs, not PHI, when the broker is external."""

    def register(self, task: str, handler: Handler) -> None: ...

    async def enqueue(
        self, task: str, payload: dict[str, Any], *, idempotency_key: str | None = None
    ) -> str: ...

    async def status(self, job_id: str) -> JobStatus: ...
