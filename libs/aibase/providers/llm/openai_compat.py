import json
from collections.abc import AsyncIterator

import httpx

from aibase.core.errors import ProviderError, ProviderUnavailable
from aibase.core.resilience import CircuitBreaker, retry_async
from aibase.observability.tracing import llm_span, record_usage
from aibase.providers.llm.port import LLMMessage, LLMResponse, Usage


class OpenAICompatLLM:
    """Any server speaking the OpenAI chat-completions wire format (vLLM, Ollama, LiteLLM,
    Azure/OpenAI, Together, ...). Vendor choice is just `base_url` + `api_key`."""

    provider_name = "openai_compat"

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "",
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_s
        )
        self._model = model
        self._breaker = CircuitBreaker()

    def _payload(
        self,
        messages: list[LLMMessage],
        model: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model or self._model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload = self._payload(messages, model, temperature, max_tokens)

        async def call() -> httpx.Response:
            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.TransportError as exc:
                raise ConnectionError(type(exc).__name__) from None
            if response.status_code in (429, 500, 502, 503, 504):
                raise ConnectionError(f"upstream status {response.status_code}")
            return response

        with llm_span("chat", provider=self.provider_name, model=str(payload["model"])) as span:
            try:
                response = await self._breaker.call(lambda: retry_async(call))
            except ConnectionError as exc:
                raise ProviderUnavailable(f"LLM provider unavailable: {exc}") from None
            if response.status_code >= 400:
                raise ProviderError(f"LLM provider rejected request: {response.status_code}")
            data = response.json()
            usage = data.get("usage") or {}
            result = LLMResponse(
                text=data["choices"][0]["message"]["content"] or "",
                model=data.get("model", str(payload["model"])),
                usage=Usage(
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                ),
            )
            record_usage(span, result.usage.input_tokens, result.usage.output_tokens)
            return result

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        payload = {**self._payload(messages, model, temperature, max_tokens), "stream": True}
        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            if response.status_code >= 400:
                raise ProviderError(f"LLM provider rejected request: {response.status_code}")
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line.endswith("[DONE]"):
                    continue
                delta = json.loads(line[6:])["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta
