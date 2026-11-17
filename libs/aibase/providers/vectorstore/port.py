from typing import Any, Protocol

from pydantic import BaseModel, Field


class VectorRecord(BaseModel):
    id: str
    vector: list[float]
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchHit(BaseModel):
    id: str
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStorePort(Protocol):
    """`tenant_id` is mandatory on every call so cross-tenant leakage cannot be coded by accident."""

    async def upsert(self, tenant_id: str, records: list[VectorRecord]) -> None: ...

    async def search(
        self,
        tenant_id: str,
        vector: list[float],
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    async def delete(self, tenant_id: str, ids: list[str]) -> None: ...
