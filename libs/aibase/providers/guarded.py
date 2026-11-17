from collections.abc import AsyncIterator

from aibase.phi.guard import PHIGuard
from aibase.providers.llm.port import LLMMessage, LLMPort, LLMResponse


class GuardedLLM:
    """Wraps any LLMPort: redacts PHI from prompts before they leave the trust boundary and
    from completions before they return. Placeholders are restored only for the caller if
    `restore=True`; otherwise the caller sees de-identified text."""

    def __init__(self, inner: LLMPort, guard: PHIGuard, *, restore: bool = False) -> None:
        self._inner = inner
        self._guard = guard
        self._restore = restore
        self.provider_name = inner.provider_name

    def _redact(self, messages: list[LLMMessage]) -> tuple[list[LLMMessage], dict[str, str]]:
        mapping: dict[str, str] = {}
        redacted: list[LLMMessage] = []
        for message in messages:
            result = self._guard.redact(message.content)
            mapping.update(result.mapping)
            redacted.append(LLMMessage(role=message.role, content=result.text))
        return redacted, mapping

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        safe, mapping = self._redact(messages)
        response = await self._inner.generate(
            safe, model=model, temperature=temperature, max_tokens=max_tokens
        )
        text = self._guard.redact(response.text).text
        if self._restore:
            # Only placeholders from our own input are restored; any new PHI stays redacted.
            for placeholder, original in mapping.items():
                text = text.replace(placeholder, original)
        return response.model_copy(update={"text": text})

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        safe, _ = self._redact(messages)
        # Output redaction is chunk-local; entities split across chunks are caught by
        # re-scanning the accumulated tail.
        buffer = ""
        async for token in self._inner.stream(
            safe, model=model, temperature=temperature, max_tokens=max_tokens
        ):
            buffer += token
            if " " in token or "\n" in token:
                yield self._guard.redact(buffer).text
                buffer = ""
        if buffer:
            yield self._guard.redact(buffer).text
