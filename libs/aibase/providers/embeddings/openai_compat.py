import httpx

from aibase.core.errors import ProviderError


class OpenAICompatEmbeddings:
    def __init__(
        self,
        base_url: str,
        model: str,
        dimension: int,
        api_key: str = "",
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_s
        )
        self._model = model
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            "/embeddings", json={"model": self._model, "input": texts}
        )
        if response.status_code >= 400:
            raise ProviderError(f"embeddings provider rejected request: {response.status_code}")
        return [item["embedding"] for item in response.json()["data"]]
