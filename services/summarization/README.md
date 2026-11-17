# summarization

Chunk → map (parallel, bounded) → reduce. `format=soap` forces Subjective/Objective/Assessment/Plan
with "Not documented" rather than invention.

- `POST /v1/summaries` (`summarize:run`).
- Add a note format: extend `NoteFormat` and the `reduce` prompt (new version file, don't edit v1 in place).
- Recommended next step for production: faithfulness evals against your own gold notes via an
  `aibase.evals.metrics.MetricPort` adapter (Ragas/DeepEval/custom judge).
