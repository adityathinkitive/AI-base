"""Reusable contract tests: run these against any new adapter to prove it honours its port.

Usage in an adapter's test module:
    async def test_contract(): await vectorstore_contract(MyVectorStore(...))
"""

from aibase.providers.cache.port import CachePort
from aibase.providers.vectorstore.port import VectorRecord, VectorStorePort


async def vectorstore_contract(store: VectorStorePort) -> None:
    await store.upsert(
        "t1", [VectorRecord(id="a", vector=[1.0, 0.0], text="alpha", metadata={"k": "x"})]
    )
    await store.upsert(
        "t1", [VectorRecord(id="b", vector=[0.0, 1.0], text="beta", metadata={"k": "y"})]
    )
    await store.upsert("t2", [VectorRecord(id="c", vector=[1.0, 0.0], text="other tenant")])

    hits = await store.search("t1", [1.0, 0.0], top_k=2)
    assert hits[0].id == "a"
    assert all(h.id != "c" for h in hits), "tenant isolation violated"

    filtered = await store.search("t1", [1.0, 0.0], top_k=5, filters={"k": "y"})
    assert [h.id for h in filtered] == ["b"]

    await store.delete("t1", ["a"])
    assert all(h.id != "a" for h in await store.search("t1", [1.0, 0.0]))


async def cache_contract(cache: CachePort) -> None:
    assert await cache.get("missing") is None
    await cache.set("k", "v")
    assert await cache.get("k") == "v"
    await cache.delete("k")
    assert await cache.get("k") is None
