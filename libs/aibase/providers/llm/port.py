import json
from collections.abc import AsyncIterator
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from aibase.core.errors import ProviderError

T = TypeVar("T", bound=BaseModel)


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    text: str
    model: str
    usage: Usage = Usage()


class LLMPort(Protocol):
    provider_name: str

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]: ...


async def generate_structured(
    llm: LLMPort, messages: list[LLMMessage], schema: type[T], *, retries: int = 1, **kwargs: object
) -> T:
    """Provider-neutral structured output: instruct JSON, validate with Pydantic, retry once."""
    instruction = LLMMessage(
        role="system",
        content="Respond with JSON only, matching this schema: "
        + json.dumps(schema.model_json_schema()),
    )
    last_error: Exception | None = None
    for _ in range(retries + 1):
        response = await llm.generate([instruction, *messages], **kwargs)  # type: ignore[arg-type]
        try:
            return schema.model_validate_json(
                response.text.strip().removeprefix("```json").removesuffix("```")
            )
        except ValidationError as exc:
            last_error = exc
    raise ProviderError("model returned output that failed schema validation") from last_error
