import hashlib
import math
import re


class FakeEmbeddings:
    """Deterministic bag-of-words hashing embeddings: similar texts share tokens, so
    retrieval tests behave sensibly without a model."""

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            vec[int.from_bytes(digest[:4], "big") % self.dimension] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
