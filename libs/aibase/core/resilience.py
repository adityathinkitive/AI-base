import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aibase.core.errors import ProviderUnavailable

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    retry_on: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError),
) -> T:
    """Exponential backoff with full jitter. Only wrap idempotent calls."""
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except retry_on:
            if attempt == attempts:
                raise
            delay = random.uniform(0, min(max_delay, base_delay * 2**attempt))  # noqa: S311
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


class CircuitBreaker:
    """Opens after `failure_threshold` consecutive failures; half-opens after `reset_after`."""

    def __init__(self, failure_threshold: int = 5, reset_after: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        # Past reset_after the breaker is half-open: let one probe through.
        return time.monotonic() - self._opened_at < self.reset_after

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        if self.is_open:
            raise ProviderUnavailable("circuit open")
        try:
            result = await fn()
        except Exception:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
            raise
        self._failures = 0
        self._opened_at = None
        return result


async def with_fallback(
    primary: Callable[[], Awaitable[T]], fallback: Callable[[], Awaitable[T]]
) -> T:
    try:
        return await primary()
    except Exception:
        return await fallback()
