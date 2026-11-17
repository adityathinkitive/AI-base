from collections.abc import AsyncIterator, Callable

from aibase.providers.llm.port import LLMMessage, LLMResponse, Usage


class FakeLLM:
    """Deterministic offline LLM for tests/CI. Records calls so tests can assert on inputs."""

    provider_name = "fake"

    def __init__(
        self, reply: str | Callable[[list[LLMMessage]], str] | None = None, model: str = "fake-1"
    ) -> None:
        self._reply = reply
        self._model = model
        self.calls: list[list[LLMMessage]] = []

    def _text(self, messages: list[LLMMessage]) -> str:
        if callable(self._reply):
            return self._reply(messages)
        if self._reply is not None:
            return self._reply
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"echo: {last_user}"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self.calls.append(messages)
        text = self._text(messages)
        usage = Usage(
            input_tokens=sum(len(m.content.split()) for m in messages),
            output_tokens=len(text.split()),
        )
        return LLMResponse(text=text, model=model or self._model, usage=usage)

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.calls.append(messages)
        for token in self._text(messages).split(" "):
            yield token + " "
