"""Config-driven provider lookup.

Adapters are imported lazily by dotted path, so deleting an adapter module (or not installing
its SDK extra) only matters if a config actually selects it.
Add your own at runtime with `register("llm", "my_vendor", MyLLM)`.
"""

import importlib
from typing import Any

from aibase.core.errors import ConfigError

_BUILTIN: dict[tuple[str, str], str] = {
    ("llm", "fake"): "aibase.providers.llm.fake:FakeLLM",
    ("llm", "openai_compat"): "aibase.providers.llm.openai_compat:OpenAICompatLLM",
    ("embeddings", "fake"): "aibase.providers.embeddings.fake:FakeEmbeddings",
    (
        "embeddings",
        "openai_compat",
    ): "aibase.providers.embeddings.openai_compat:OpenAICompatEmbeddings",
    ("vectorstore", "memory"): "aibase.providers.vectorstore.memory:InMemoryVectorStore",
    ("stt", "fake"): "aibase.providers.stt.fake:FakeSTT",
    ("stt", "faster_whisper"): "aibase.providers.stt.faster_whisper:FasterWhisperSTT",
    ("diarization", "fake"): "aibase.providers.diarization.fake:FakeDiarizer",
    ("storage", "local"): "aibase.providers.storage.local:LocalStorage",
    ("queue", "memory"): "aibase.providers.queue.memory:InMemoryQueue",
    ("cache", "memory"): "aibase.providers.cache.memory:InMemoryCache",
    ("cache", "redis"): "aibase.providers.cache.redis:RedisCache",
    ("redactor", "regex"): "aibase.phi.regex_redactor:RegexRedactor",
    ("redactor", "presidio"): "aibase.phi.presidio_redactor:PresidioRedactor",
}
_CUSTOM: dict[tuple[str, str], Any] = {}


def register(kind: str, name: str, factory: Any) -> None:
    _CUSTOM[(kind, name)] = factory


def available(kind: str) -> list[str]:
    return sorted({n for (k, n) in {*_BUILTIN, *_CUSTOM} if k == kind})


def create(kind: str, name: str, **options: Any) -> Any:
    key = (kind, name)
    if key in _CUSTOM:
        return _CUSTOM[key](**options)
    if key not in _BUILTIN:
        raise ConfigError(f"unknown {kind} provider '{name}'; available: {available(kind)}")
    module_path, _, attr = _BUILTIN[key].partition(":")
    try:
        factory = getattr(importlib.import_module(module_path), attr)
    except ImportError as exc:
        raise ConfigError(f"{kind} provider '{name}' is not installed: {exc}") from exc
    return factory(**options)
