from dataclasses import dataclass
from typing import Any

from aibase.core.settings import ProviderSettings, Settings
from aibase.phi.guard import PHIGuard
from aibase.providers import registry
from aibase.providers.cache.port import CachePort
from aibase.providers.diarization.port import DiarizerPort
from aibase.providers.embeddings.port import EmbeddingsPort
from aibase.providers.guarded import GuardedLLM
from aibase.providers.llm.port import LLMPort
from aibase.providers.queue.port import QueuePort
from aibase.providers.storage.port import StoragePort
from aibase.providers.stt.port import STTPort
from aibase.providers.vectorstore.port import VectorStorePort


def _build(kind: str, cfg: ProviderSettings) -> Any:
    options = dict(cfg.options)
    if cfg.model and "model" not in options and kind in ("llm", "embeddings"):
        options["model"] = cfg.model
    return registry.create(kind, cfg.provider, **options)


def build_phi_guard(settings: Settings) -> PHIGuard:
    redactor = registry.create("redactor", settings.phi.redactor)
    return PHIGuard(redactor, fail_closed=settings.phi.fail_closed)


@dataclass
class Providers:
    """Everything a service needs, built once at startup from config."""

    llm: LLMPort
    embeddings: EmbeddingsPort
    vectorstore: VectorStorePort
    stt: STTPort
    diarizer: DiarizerPort
    storage: StoragePort
    queue: QueuePort
    cache: CachePort
    phi: PHIGuard


def build_providers(settings: Settings) -> Providers:
    guard = build_phi_guard(settings)
    llm: LLMPort = _build("llm", settings.llm)
    if settings.phi.enabled:
        llm = GuardedLLM(llm, guard)
    return Providers(
        llm=llm,
        embeddings=_build("embeddings", settings.embeddings),
        vectorstore=_build("vectorstore", settings.vectorstore),
        stt=_build("stt", settings.stt),
        diarizer=_build("diarization", settings.diarization),
        storage=_build("storage", settings.storage),
        queue=_build("queue", settings.queue),
        cache=_build("cache", settings.cache),
        phi=guard,
    )
