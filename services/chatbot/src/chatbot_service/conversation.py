import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

from aibase.phi import PHIGuard
from aibase.prompts import PromptRegistry
from aibase.providers.cache import CachePort
from aibase.providers.llm import LLMMessage, LLMPort

PROMPTS = PromptRegistry(Path(__file__).parent / "prompts")
MAX_TURNS = 10
SESSION_TTL_S = 3600

# Deterministic safety net that runs BEFORE any model call.
EMERGENCY = re.compile(
    r"\b(suicid\w*|kill myself|overdos\w*|can'?t breathe|chest pain|stroke|severe bleeding)\b", re.I
)
ESCALATION_REPLY = (
    "This may be an emergency. Please call your local emergency number now or go to the nearest "
    "emergency department. I am connecting you with a member of the care team."
)


class SessionStore:
    """Stores only de-identified history, scoped to tenant AND user, with a TTL."""

    def __init__(self, cache: CachePort, guard: PHIGuard) -> None:
        self._cache = cache
        self._guard = guard

    @staticmethod
    def key(tenant_id: str, subject: str, session_id: str) -> str:
        return f"chat:{tenant_id}:{subject}:{session_id}"

    async def load(self, key: str) -> list[LLMMessage]:
        raw = await self._cache.get(key)
        return [LLMMessage(**m) for m in json.loads(raw)] if raw else []

    async def append(self, key: str, history: list[LLMMessage], user: str, assistant: str) -> None:
        safe_user = self._guard.redact(user).text
        updated = [
            *history,
            LLMMessage(role="user", content=safe_user),
            LLMMessage(role="assistant", content=assistant),
        ]
        trimmed = updated[-MAX_TURNS * 2 :]
        await self._cache.set(
            key, json.dumps([m.model_dump() for m in trimmed]), ttl_s=SESSION_TTL_S
        )

    async def clear(self, key: str) -> None:
        await self._cache.delete(key)


def is_emergency(text: str) -> bool:
    return bool(EMERGENCY.search(text))


def build_messages(history: list[LLMMessage], user: str) -> tuple[list[LLMMessage], str]:
    system = PROMPTS.render("system")
    return [
        LLMMessage(role="system", content=system.text),
        *history,
        LLMMessage(role="user", content=user),
    ], system.tag


async def reply(llm: LLMPort, messages: list[LLMMessage]) -> str:
    return (await llm.generate(messages)).text


async def reply_stream(
    llm: LLMPort, messages: list[LLMMessage], sink: list[str]
) -> AsyncIterator[str]:
    async for token in llm.stream(messages):
        sink.append(token)
        yield token
