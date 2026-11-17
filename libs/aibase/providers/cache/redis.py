from typing import Any

from aibase.core.errors import ConfigError


class RedisCache:
    """Requires `uv sync --extra redis`."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ConfigError("redis not installed; run `uv sync --extra redis`") from exc
        self._client: Any = aioredis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        value: str | None = await self._client.get(key)
        return value

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl_s)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)
