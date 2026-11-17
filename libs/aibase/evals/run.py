"""CI eval gate: python -m aibase.evals.run <datasets_dir>

Each dataset is a JSON file: {"thresholds": {"precision@3": 0.3, ...}, "documents": [...],
"cases": [{"query": ..., "relevant": [doc ids]}]}. Runs retrieval over the configured
embeddings + vector store (fake by default => fully offline) and fails on regression.
"""

import asyncio
import json
import sys
from pathlib import Path

from aibase.core.settings import get_settings
from aibase.evals.metrics import mrr, precision_at_k, recall_at_k
from aibase.providers import registry
from aibase.providers.vectorstore.port import VectorRecord

K = 3


async def run_dataset(path: Path) -> list[str]:
    data = json.loads(path.read_text())  # noqa: ASYNC240
    settings = get_settings()
    embeddings = registry.create(
        "embeddings", settings.embeddings.provider, **settings.embeddings.options
    )
    store = registry.create(
        "vectorstore", settings.vectorstore.provider, **settings.vectorstore.options
    )

    docs = data["documents"]
    vectors = await embeddings.embed([d["text"] for d in docs])
    await store.upsert(
        "eval",
        [
            VectorRecord(id=d["id"], vector=v, text=d["text"])
            for d, v in zip(docs, vectors, strict=True)
        ],
    )

    totals = {f"precision@{K}": 0.0, f"recall@{K}": 0.0, "mrr": 0.0}
    for case in data["cases"]:
        [qvec] = await embeddings.embed([case["query"]])
        retrieved = [h.id for h in await store.search("eval", qvec, top_k=K)]
        relevant = set(case["relevant"])
        totals[f"precision@{K}"] += precision_at_k(retrieved, relevant, K)
        totals[f"recall@{K}"] += recall_at_k(retrieved, relevant, K)
        totals["mrr"] += mrr(retrieved, relevant)

    n = len(data["cases"])
    failures = []
    for metric, total in totals.items():
        score = total / n
        threshold = data["thresholds"].get(metric)
        status = "ok"
        if threshold is not None and score < threshold:
            status = "FAIL"
            failures.append(f"{path.name}: {metric}={score:.3f} < {threshold}")
        print(f"{path.name} {metric}={score:.3f} threshold={threshold} {status}")
    return failures


async def main(directory: str) -> int:
    failures: list[str] = []
    datasets = sorted(Path(directory).glob("*.json"))  # noqa: ASYNC240
    if not datasets:
        print(f"no eval datasets in {directory}", file=sys.stderr)
        return 1
    for path in datasets:
        failures += await run_dataset(path)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "evals/datasets")))
