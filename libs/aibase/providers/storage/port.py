from typing import Protocol


class StoragePort(Protocol):
    """Object storage. S3/GCS/Azure adapters must enable server-side encryption at rest."""

    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...
