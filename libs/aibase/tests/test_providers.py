import json

import httpx
import pytest
from pydantic import BaseModel

from aibase.core.errors import ConfigError, ProviderError
from aibase.core.resilience import CircuitBreaker, retry_async
from aibase.providers import registry
from aibase.providers.cache.memory import InMemoryCache
from aibase.providers.embeddings.fake import FakeEmbeddings
from aibase.providers.llm import LLMMessage, generate_structured
from aibase.providers.llm.fake import FakeLLM
from aibase.providers.llm.openai_compat import OpenAICompatLLM
from aibase.providers.storage.local import LocalStorage
from aibase.providers.vectorstore.memory import InMemoryVectorStore
from aibase.testing.contracts import cache_contract, vectorstore_contract


async def test_vectorstore_contract():
    await vectorstore_contract(InMemoryVectorStore())


async def test_cache_contract():
    await cache_contract(InMemoryCache())


async def test_embeddings_are_normalised_and_deterministic():
    [a], [b] = (
        await FakeEmbeddings().embed(["chest pain"]),
        await FakeEmbeddings().embed(["chest pain"]),
    )
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_registry_unknown_provider_lists_options():
    with pytest.raises(ConfigError, match="available"):
        registry.create("llm", "nope")


def test_registry_custom_registration():
    registry.register("llm", "mine", lambda **_: FakeLLM("hi"))
    assert registry.create("llm", "mine").provider_name == "fake"


async def test_storage_blocks_path_traversal(tmp_path):
    storage = LocalStorage(str(tmp_path))
    await storage.put("a/b.bin", b"x")
    assert await storage.get("a/b.bin") == b"x"
    with pytest.raises(Exception, match="invalid storage key"):
        await storage.get("../etc/passwd")


class Note(BaseModel):
    summary: str


async def test_generate_structured_validates_and_retries():
    replies = iter(["not json", '{"summary": "ok"}'])
    llm = FakeLLM(lambda _: next(replies))
    note = await generate_structured(llm, [LLMMessage(role="user", content="x")], Note)
    assert note.summary == "ok"


async def test_generate_structured_gives_up():
    llm = FakeLLM("still not json")
    with pytest.raises(ProviderError):
        await generate_structured(llm, [LLMMessage(role="user", content="x")], Note)


async def test_retry_and_circuit_breaker():
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError
        return "ok"

    assert await retry_async(flaky, base_delay=0) == "ok"

    breaker = CircuitBreaker(failure_threshold=2, reset_after=60)

    async def fail() -> None:
        raise RuntimeError

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(fail)
    assert breaker.is_open


async def test_openai_compat_parses_response_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "m1"
        return httpx.Response(
            200,
            json={
                "model": "m1",
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://x/v1")
    llm = OpenAICompatLLM("http://x/v1", model="m1", client=client)
    response = await llm.generate([LLMMessage(role="user", content="hi")])
    assert response.text == "hello"
    assert response.usage.output_tokens == 2
