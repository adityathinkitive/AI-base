import time


class InMemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at <= time.monotonic():
            del self._data[key]
            return None
        return value

    async def set(self, key: str, value: str, *, ttl_s: int | None = None) -> None:
        self._data[key] = (value, time.monotonic() + ttl_s if ttl_s else None)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
