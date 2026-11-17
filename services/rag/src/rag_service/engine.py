import uuid
from pathlib import Path

from pydantic import BaseModel

from aibase.guardrails import injection_free
from aibase.prompts import PromptRegistry
from aibase.providers.factory import Providers
from aibase.providers.llm import LLMMessage
from aibase.providers.vectorstore import VectorRecord

PROMPTS = PromptRegistry(Path(__file__).parent / "prompts")
NO_ANSWER = "I don't have enough information in the provided documents."


class Citation(BaseModel):
    id: str
    score: float
    text: str


class Answer(BaseModel):
    answer: str
    citations: list[Citation]
    prompt: str


def chunk(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    step = size - overlap
    return [
        text[i : i + size].strip() for i in range(0, len(text), step) if text[i : i + size].strip()
    ]


async def ingest(
    providers: Providers, tenant_id: str, doc_id: str, text: str, metadata: dict[str, str]
) -> int:
    # De-identify before indexing so the vector store never holds raw PHI.
    clean = providers.phi.redact(text).text
    pieces = chunk(clean)
    vectors = await providers.embeddings.embed(pieces)
    await providers.vectorstore.upsert(
        tenant_id,
        [
            VectorRecord(
                id=f"{doc_id}:{i}", vector=v, text=p, metadata={**metadata, "doc_id": doc_id}
            )
            for i, (p, v) in enumerate(zip(pieces, vectors, strict=True))
        ],
    )
    return len(pieces)


async def answer(
    providers: Providers, tenant_id: str, question: str, top_k: int = 4, min_score: float = 0.05
) -> Answer:
    [qvec] = await providers.embeddings.embed([question])
    hits = [
        h
        for h in await providers.vectorstore.search(tenant_id, qvec, top_k=top_k)
        if h.score >= min_score
    ]
    # Indirect prompt injection: drop retrieved chunks that look like instructions to the model.
    safe_hits = [h for h in hits if injection_free(h.text)]
    if not safe_hits:
        return Answer(answer=NO_ANSWER, citations=[], prompt="none")
    prompt = PROMPTS.render("answer", sources=[h.text for h in safe_hits], question=question)
    response = await providers.llm.generate([LLMMessage(role="user", content=prompt.text)])
    return Answer(
        answer=response.text,
        citations=[Citation(id=h.id, score=round(h.score, 4), text=h.text) for h in safe_hits],
        prompt=prompt.tag,
    )


def new_doc_id() -> str:
    return uuid.uuid4().hex
