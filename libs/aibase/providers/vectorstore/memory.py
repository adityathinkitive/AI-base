from typing import Any

from aibase.providers.vectorstore.port import SearchHit, VectorRecord


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


class InMemoryVectorStore:
    """Cosine search over L2-normalised vectors. For tests and local dev only."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, VectorRecord]] = {}

    async def upsert(self, tenant_id: str, records: list[VectorRecord]) -> None:
        bucket = self._data.setdefault(tenant_id, {})
        for record in records:
            bucket[record.id] = record

    async def search(
        self,
        tenant_id: str,
        vector: list[float],
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        filters = filters or {}
        candidates = [
            r
            for r in self._data.get(tenant_id, {}).values()
            if all(r.metadata.get(k) == v for k, v in filters.items())
        ]
        hits = [
            SearchHit(id=r.id, score=_dot(vector, r.vector), text=r.text, metadata=r.metadata)
            for r in candidates
        ]
        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]

    async def delete(self, tenant_id: str, ids: list[str]) -> None:
        for id_ in ids:
            self._data.get(tenant_id, {}).pop(id_, None)
