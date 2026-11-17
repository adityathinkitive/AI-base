# AI-base

Vendor-agnostic, production-grade template for healthcare AI services (transcription, summarization,
RAG, chatbot, preprocessing). Use it via **GitHub "Use this template"** (or clone), then delete what you
don't need. Read [USAGE_GUIDE.md](USAGE_GUIDE.md) for the complete step-by-step guide.

```
libs/aibase/          shared, service-agnostic building blocks
  core/               settings, errors, JSON logging, retry + circuit breaker
  phi/                PHI detection/redaction, fail-closed guard
  audit/              append-only, hash-chained audit log
  observability/      OpenTelemetry (GenAI conventions), any OTLP backend
  providers/          ports + adapters: llm, embeddings, vectorstore, stt, diarization, storage, queue, cache
  guardrails/         input/output checks (injection, PHI, length)
  prompts/            versioned, hashed prompt files
  evals/              offline retrieval metrics + CI gate
  api/                FastAPI app factory: auth, rate limit, request IDs, health, metrics
  testing/            fakes, synthetic PHI, adapter contract tests
services/             one deployable FastAPI app per folder (each deletable)
  preprocessing/  rag/  summarization/  transcription/  chatbot/  _service_template/
deploy/               Dockerfile, OTel collector, k8s base
evals/datasets/       eval sets used by `make eval`
docs/                 architecture, HIPAA checklist, threat model, runbooks, ADRs
```

## Quick start (no API keys needed; all providers default to offline fakes)

```bash
make install            # uv sync
make check              # lint, types, boundaries, tests, eval gate
PYTHONPATH=libs:services/rag/src uv run uvicorn rag_service.main:create_service_app --factory --reload
docker compose up --build
```

## Vendor agnostic by design

Every external system sits behind a `Protocol` in `libs/aibase/providers/*/port.py`; config picks the adapter:

```bash
AIBASE_LLM__PROVIDER=openai_compat      # vLLM, Ollama, LiteLLM, Azure/OpenAI, any OpenAI-format server
AIBASE_LLM__OPTIONS='{"base_url":"https://...","api_key":"..."}'
AIBASE_STT__PROVIDER=faster_whisper
AIBASE_PHI__REDACTOR=presidio
```

Add your own vendor: implement the port, `registry.register("llm", "my_vendor", MyLLM)`, run the matching
contract test from `aibase.testing.contracts`. Vendor SDKs are optional extras, never core dependencies.

## Guarantees enforced by tests/CI

- PHI is redacted before any provider call and in logs, errors, traces and stored data; redaction failure blocks the request.
- Production settings refuse to start without auth and fail-closed PHI.
- Tenant ID is mandatory on vector store calls; sessions are scoped to tenant + user.
- Services never import each other; libs never import services (`scripts/check_boundaries.py`).
- CI proves each service can be deleted without breaking the rest.

Honest limits: see [docs/hipaa-checklist.md](docs/hipaa-checklist.md). This template supports compliance; it does not make a deployment compliant.
