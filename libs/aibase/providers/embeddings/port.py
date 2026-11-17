from typing import Protocol


class EmbeddingsPort(Protocol):
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
