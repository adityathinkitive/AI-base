from typing import Protocol


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top = retrieved[:k]
    return sum(1 for r in top if r in relevant) / k if k else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for r in retrieved[:k] if r in relevant) / len(relevant)


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


class MetricPort(Protocol):
    """Adapter point for LLM-judged metrics (faithfulness, answer relevance) from
    Ragas/DeepEval/custom judges. Keep them out of the default offline gate."""

    name: str

    async def score(self, question: str, answer: str, contexts: list[str]) -> float: ...
